#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI 动线测试共享助手（R150）：API 客户端/造赛、浏览器登录助手。
独立模块名避免与 tests/conftest.py 在 sys.path 上撞名。"""
import json
import os
import sqlite3
import urllib.parse
import urllib.request
import urllib.error

import sys

import pytest


# ---------------------------------------------------------------- 数据安全护栏
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(REPO, "webapp")
sys.path.insert(0, os.path.join(REPO, "tests"))   # 复用 L1 数据集常量（单一来源）

BASE = os.environ.get("DSPORT_UI_BASE", "")
_HOST = urllib.parse.urlsplit(BASE).hostname if BASE else "127.0.0.1"
if BASE and _HOST not in ("127.0.0.1", "localhost", "::1") and \
        os.environ.get("DSPORT_UI_ALLOW_REMOTE") != "1":
    raise SystemExit(
        "拒绝运行：DSPORT_UI_BASE=%s 不是本机地址。UI 动线测试会建赛/写库，\n"
        "绝不允许指向生产。如确需远程调试，设 DSPORT_UI_ALLOW_REMOTE=1。" % BASE)

_BASE_holder = {"db": None}


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Api:
    """对活服务器的极简 HTTP 客户端（urllib，同 ci_suite.Client）。"""

    def __init__(self, base):
        self.base = base
        self.cookie = ""

    def req(self, method, path, body=None, raw=None, ctype="application/json", expect=None):
        import urllib.parse
        data = None
        if raw is not None:
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
        r = urllib.request.Request(self.base + path, data=data, method=method)
        r.add_header("Content-Type", ctype)
        if self.cookie:
            r.add_header("Cookie", self.cookie)
        try:
            resp = urllib.request.urlopen(r, timeout=20)
            payload, status, setc = resp.read(), resp.status, resp.headers.get("Set-Cookie") or ""
        except urllib.error.HTTPError as e:
            payload, status, setc = e.read(), e.code, e.headers.get("Set-Cookie") or ""
        if setc:
            for part in setc.split(","):
                p = part.strip()
                if p.startswith("session="):
                    self.cookie = p.split(";")[0]
        if expect is not None and status != expect:
            raise AssertionError("%s %s → %s（预期 %s）: %s" % (
                method, path, status, expect, payload[:200].decode("utf-8", "replace")))
        try:
            return status, json.loads(payload.decode("utf-8"))
        except Exception:
            return status, payload.decode("utf-8", "replace")

    # ---------- 高层动线 ----------
    def login_admin(self):
        self.req("POST", "/api/login", body={"role": "admin", "password": "admin123"}, expect=200)

    def login_staff(self, role, username, password):
        self.req("POST", "/api/login", body={"role": role, "username": username,
                                             "password": password, "competition_id": 0}, expect=200)
        return self.cookie

    def login_judge(self, code):
        c = Api(self.base)
        c.req("POST", "/api/login", body={"role": "judge", "judge_id": code}, expect=200)
        return c.cookie

    def create_printer(self, username="ui-printer", password="print123"):
        st, d = self.req("POST", "/api/users", body={"username": username, "password": password,
                                                     "role": "printer", "display_name": "UI打印员"})
        return st

    def seed_comp(self, name):
        """建赛+激活+三类导入+追加评分制场次+裁判排班。返回 {cid, ceid}。"""
        from api_harness import CSV_COMPETITORS, CSV_JUDGES, CSV_SCHEDULE   # L1 数据集单一来源

        self.req("POST", "/api/events", body={"name": name, "date": "2026-01-01", "location": "UI"}, expect=200)
        st, d = self.req("GET", "/api/events")
        cid = max(e["id"] for e in d["events"])
        self.req("POST", "/api/events/%d/activate" % cid, body={}, expect=200)
        # 评分制队伍（P03）并进同一次导入：competitors 导入是「全量对齐」语义，
        # 二次上传会移除未含的旧报项（曾把预赛报名连带名单一起清掉）
        combined = CSV_COMPETITORS + "301,团队A,甲院,P03\n302,团队B,乙院,P03\n".encode("utf-8")
        for kind, body in (("competitors", combined), ("judges", CSV_JUDGES),
                           ("schedule", CSV_SCHEDULE)):
            self.req("POST", "/api/events/%d/imports/%s" % (cid, kind), raw=body, ctype="text/csv", expect=200)
        self.req("POST", "/api/events/%d/schedule/add" % cid,
                 body={"code": "P03-R1", "name": "集体舞决赛", "project": "P03", "round": 1,
                       "dances": "现代舞", "type": "SCORE", "adv": 8}, expect=200)
        # 裁判排班：events.judges_assigned 无独立 API（与 ci_suite 同法直改临时库）
        if self.db_path:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute("UPDATE events SET judges_assigned='J1,J2,J3' WHERE competition_id=?", (cid,))
            conn.commit()
            conn.close()
        sched = self.req("GET", "/api/public/events/%d/schedule" % cid)[1]["events"]
        ceid = {e["code"]: e["id"] for e in sched}
        return {"cid": cid, "ceid": ceid}

    # ---------- 场次生命周期 ----------
    def open(self, ceid, roster):
        self.req("POST", "/api/competition-events/%d/open" % ceid, body={"roster": roster}, expect=200)

    def roster_of(self, ceid):
        return self.req("GET", "/api/competition-events/%d/progress" % ceid)[1]["roster"]

    def checkin_all(self, ceid):
        nums = self.roster_of(ceid)
        self.req("POST", "/api/competition-events/%d/checkin" % ceid,
                 body={"numbers": nums, "state": True}, expect=200)
        return nums

    def submit_sheet(self, ceid, dance, values, judge_cookie):
        import urllib.parse
        c = Api(self.base)
        c.cookie = judge_cookie
        c.req("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (ceid, urllib.parse.quote(dance)),
              body={"values": values}, expect=200)

    def calc(self, ceid):
        self.req("POST", "/api/competition-events/%d/calculate" % ceid, body={}, expect=200)

    def publish(self, ceid):
        self.req("POST", "/api/competition-events/%d/publish" % ceid, body={}, expect=200)

    def run_mark_round(self, ceid, marked, judges=("J1", "J2", "J3"), dance="平四"):
        self.open(ceid, self.roster_of(ceid))
        self.checkin_all(ceid)
        for j in judges:
            self.submit_sheet(ceid, dance, {n: True for n in marked}, self.login_judge(j))
        self.publish(ceid)

    def confirm_adv(self, cid, project, rnd, assign):
        self.req("POST", "/api/projects/%s/rounds/%d/advancement-confirm" % (project, rnd),
                 body={"assign": assign, "append": True, "competition_id": cid}, expect=200)


def _csv_body(header, rows):
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


# ---------------------------------------------------------------- 登录助手
def ui_login(page, role, cid=None, username=None, password=None, judge_id=None):
    """走真实登录页登录（固化 R149 角色感知表单）。返回落地页 URL。
    预写 onboarding 已读标记：登录落地后不再弹首访轮播遮挡点击。"""
    page.add_init_script(
        "try{['judge','marshal','host','admin'].forEach(function(k){localStorage.setItem('onb:'+k,'1')})}catch(e){}")
    path = "/competitions/%s/login?role=%s" % (cid, role) if cid else "/login"
    page.goto(path)
    page.wait_for_timeout(300)
    if role == "judge":
        assert page.is_visible("#judge-box"), "裁判角色应只显示裁判 ID 表单"
        assert not page.is_visible("#user-box"), "裁判角色不应显示用户名框"
        page.fill("#judge_id", judge_id or "J1")
    else:
        if username is not None:
            page.fill("#username", username)
        page.fill("#password", password or "")
    page.click("#btn")
    page.wait_for_timeout(800)
    return page.url


def cookie_login(ctx, base, token):
    """API 会话 token 直接注入（免重复走登录页）。token 兼容带/不带 `session=` 前缀。"""
    if token.startswith("session="):
        token = token[len("session="):]
    ctx.add_cookies([{"name": "session", "value": token, "url": base}])


@pytest.fixture()
def as_admin(page, ctx, base_url, client):
    """管理员已登录的 page（API cookie 注入）。"""
    cookie_login(ctx, base_url, client.cookie)
    return page
