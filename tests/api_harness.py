#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享「API 造赛」配方（R150 收敛）。

此前 login→建赛→激活→导入→开赛→检录→评分→发布→晋级 这套配方在
test_release_gate / test_lifecycle_api / ci_suite / selftest 等 5+ 处各自内联实现；
本模块提供唯一可复用实现。

用法约定：
- 调用方必须在**导入 server.app 之前**自行设置 DSPORT_DB/DSPORT_FILES_DIR（导入时求值），
  并提供传输函数 req(method, path, json=None, content=None, role=None) → httpx.Response
  （ASGITransport 或真实 HTTP 均可），传入 Api(req)。
- role 参数 = 会话槽（"admin"/"J1"…），由 Api.login 登记会话 cookie。
"""
import json

# 标准数据集（与 ci_suite.py 场景同构）：Mark 预赛两分场 → 复赛两分场 → 顺位决赛 + 单项顺位决赛
CSV_COMPETITORS = (
    "背番号,姓名,学校/单位,项目编号\n"
    + "".join("%d,选手%d,%s,P01A\n" % (n, n, "甲院" if n % 4 in (1, 2) else "乙院") for n in range(101, 113))
    + "".join("%d,单项%d,%s,P02\n" % (n, n, "甲院" if n in (201, 202) else "乙院") for n in (201, 202, 203, 204))
    + "205,外项选手,丙院,P03\n"
).encode("utf-8")

CSV_JUDGES = ("裁判ID,姓名\nJ1,甲裁\nJ2,乙裁\nJ3,丙裁\n").encode("utf-8")

CSV_SCHEDULE = (
    "场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n"
    'P01Z01-R1A,平四初赛A,P01Z01,1,平四,MARK,4,"101,102,103,104,105,106"\n'
    'P01Z01-R1B,平四初赛B,P01Z01,1,平四,MARK,4,"107,108,109,110,111,112"\n'
    'P01Z01-R2A,平四复赛A,P01Z01,2,平四,MARK,2,""\n'
    'P01Z01-R2B,平四复赛B,P01Z01,2,平四,MARK,2,""\n'
    'P01Z01-R3,平四决赛,P01Z01,3,平四,SKATING,8,""\n'
    'P02-R1,单项决赛,P02,1,华尔兹,SKATING,8,"201,202,203,204"\n'
).encode("utf-8")


class Api:
    """基于注入 req() 的造赛助手。req 返回带 .status_code/.json()/.text 的响应对象。

    store：会话槽写透目标（通常传调用方 req() 读取的同一 dict），保证
    login() 登记的 cookie 立即对 req(role=...) 生效；缺省写到自带字典。"""

    def __init__(self, req, store=None):
        self.req = req
        self.cookies = {} if store is None else store   # slot → session token
        self._store = self.cookies

    # ---------- 会话 ----------
    def login(self, slot, payload):
        r = self.req("POST", "/api/login", json=payload)
        assert r.status_code == 200, r.text
        self._store[slot] = r.headers["set-cookie"].split("session=")[1].split(";")[0]
        return r

    def login_admin(self, password="admin123"):
        return self.login("admin", {"role": "admin", "password": password})

    def login_judges(self, codes=("J1", "J2", "J3")):
        for c in codes:
            self.login(c, {"role": "judge", "judge_id": c})

    def as_role(self, role):
        """req 包装：自动带该槽位会话。"""
        def _req(method, path, **kw):
            return self.req(method, path, role=role, **kw)
        return _req

    # ---------- 筹备 ----------
    def create_activate(self, name="测试赛", date="2026-01-01", location="CI"):
        r = self.req("POST", "/api/events", json={"name": name, "date": date, "location": location}, role="admin")
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        assert self.req("POST", "/api/events/%d/activate" % cid, json={}, role="admin").status_code == 200
        return cid

    def seed_competition(self, name="测试赛"):
        """建赛 + 三类导入 + 裁判登录。返回 (cid, ceid_by_code)。"""
        cid = self.create_activate(name)
        for kind, body in (("competitors", CSV_COMPETITORS), ("judges", CSV_JUDGES),
                           ("schedule", CSV_SCHEDULE)):
            r = self.req("POST", "/api/events/%d/imports/%s" % (cid, kind), content=body, role="admin")
            assert r.status_code == 200, (kind, r.text)
        self.login_judges()
        sched = self.req("GET", "/api/public/events/%d/schedule" % cid).json()["events"]
        ceid = {e["code"]: e["id"] for e in sched}
        return cid, ceid

    # ---------- 场次生命周期 ----------
    def open(self, ceid, roster, role="admin", expect=200):
        r = self.req("POST", "/api/competition-events/%d/open" % ceid, json={"roster": roster}, role=role)
        assert r.status_code == expect, "%d open → %d: %s" % (ceid, r.status_code, r.text[:200])
        return r

    def checkin_all(self, ceid, role="admin"):
        p = self.req("GET", "/api/competition-events/%d/progress" % ceid, role=role).json()
        r = self.req("POST", "/api/competition-events/%d/checkin" % ceid,
                     json={"numbers": p["roster"], "state": True}, role=role)
        assert r.status_code == 200, r.text
        return p["roster"]

    def score(self, ceid, dance, values, judge_slot):
        r = self.req("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (ceid, dance),
                     json={"values": values}, role=judge_slot)
        assert r.status_code == 200, r.text
        return r.json()

    def score_mark(self, ceid, marked, judges=("J1", "J2", "J3"), dance="平四"):
        """三裁 Mark：末裁应触发自动算分。"""
        for j in judges:
            d = self.score(ceid, dance, {n: True for n in marked}, j)
            if j == judges[-1]:
                assert d.get("auto_calculated") is True, d

    def score_skate(self, ceid, dance, placement, judges=("J1", "J2", "J3")):
        for j in judges:
            self.score(ceid, dance, placement, j)

    def publish(self, ceid, role="admin"):
        r = self.req("POST", "/api/competition-events/%d/publish" % ceid, json={}, role=role)
        assert r.status_code == 200, r.text

    def run_mark_round(self, ceid, marked, dance="平四"):
        """开赛（全名单）→ 检录 → 三裁 Mark → 发布。"""
        p = self.req("GET", "/api/competition-events/%d/progress" % ceid, role="admin").json()
        self.open(ceid, p["roster"])
        self.checkin_all(ceid)
        self.score_mark(ceid, marked, dance=dance)
        self.publish(ceid)
