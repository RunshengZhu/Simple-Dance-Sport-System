#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发版门禁回归（R134，comp21 复盘产物）——把比赛日五项事故固化为断言：

1. api_open 名单归属校验：外项背号混入 → 400（事故：P03/P04 背号被写进 P01Z02 场）
2. api_open 有评分重开须显式 reset=true（事故：had_scores 隐式清场静默重建名单）
3. api_confirm 同轮跨分场互斥：请求内重复 / 与既有分场冲突 → 400
   （事故：全量视图重蛇形 + 追加不清理 → R2A/R2B 6 对双场）
4. 成绩查询多分场晋级判定：fetchone 单场缺陷回归（事故：802 等 25 人误显未晋级）
5. 团体总分单一来源：管理榜 == 公开榜（事故：admin 页旧口径差 41.5 分）
6. reset_scoring 赛事名确认（事故：比赛日被全量 reset 三次）
7. 全链路冒烟：Mark 预赛→晋级→复赛→顺位决赛→团体分独立复算对拍 + 前端页面响应
"""
import os
import tempfile

# 在导入 server.app 之前固定隔离环境（DB 路径在导入时求值）
_TMP = tempfile.mkdtemp(prefix="dsh-release-gate-")
os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from server import app as app_module, db as db_module  # noqa: E402

db_module.init_db()

_SESSIONS = {}


def req(method, path, content=None, json=None, role=None):
    headers = {}
    token = _SESSIONS.get(role)
    if token:
        headers["Cookie"] = "session=" + token

    async def _run():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(method, path, content=content, json=json, headers=headers)

    return asyncio.run(_run())


def _login(slot, payload):
    r = req("POST", "/api/login", json=payload)
    assert r.status_code == 200, r.text
    _SESSIONS[slot] = r.headers["set-cookie"].split("session=")[1].split(";")[0]


COMP_NAME = "发版门禁赛"
POINTS = {1: 9, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}

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


@pytest.fixture(scope="module", autouse=True)
def env():
    _login("admin", {"role": "admin", "password": "admin123"})
    r = req("POST", "/api/events", json={"name": COMP_NAME, "date": "2026-01-01",
                                         "location": "CI"}, role="admin")
    assert r.status_code == 200
    cid = r.json()["id"]
    assert req("POST", "/api/events/%d/activate" % cid, role="admin").status_code == 200
    for kind, body in (("competitors", CSV_COMPETITORS), ("judges", CSV_JUDGES),
                       ("schedule", CSV_SCHEDULE)):
        r = req("POST", "/api/events/%d/imports/%s" % (cid, kind), content=body, role="admin")
        assert r.status_code == 200, (kind, r.text)
    for code in ("J1", "J2", "J3"):
        _login(code, {"role": "judge", "judge_id": code})
    sched = req("GET", "/api/public/events/%d/schedule" % cid).json()["events"]
    ceid = {e["code"]: e["id"] for e in sched}
    yield {"cid": cid, "ceid": ceid}


def _checkin(cid, ceid):
    p = req("GET", "/api/competition-events/%d/progress" % ceid, role="admin").json()
    r = req("POST", "/api/competition-events/%d/checkin" % ceid,
            json={"numbers": p["roster"], "state": True}, role="admin")
    assert r.status_code == 200, r.text


def _score_mark(ceid, marked):
    for role in ("J1", "J2", "J3"):
        r = req("PUT", "/api/judge/competition-events/%d/dances/平四/sheet" % ceid,
                json={"values": {n: True for n in marked}}, role=role)
        assert r.status_code == 200, r.text
        if role == "J3":
            assert r.json().get("auto_calculated") is True


def _score_skate(ceid, dance, placement):
    for role in ("J1", "J2", "J3"):
        r = req("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (ceid, dance),
                json={"values": placement}, role=role)
        assert r.status_code == 200, r.text


# ---------------- 1) 开赛名单归属（事故回归） ----------------

def test_open_rejects_foreign_number(env):
    r1a = env["ceid"]["P01Z01-R1A"]
    r = req("POST", "/api/competition-events/%d/open" % r1a,
            json={"roster": ["101", "102", "103", "104", "205"]}, role="admin")
    assert r.status_code == 400 and "205" in r.text   # 205 仅报名 P03


def test_open_requires_explicit_reset_when_scored(env):
    r1a = env["ceid"]["P01Z01-R1A"]
    r = req("POST", "/api/competition-events/%d/open" % r1a,
            json={"roster": ["101", "102", "103", "104", "105", "106"]}, role="admin")
    assert r.status_code == 200
    _checkin(env["cid"], r1a)
    _score_mark(r1a, ["101", "102", "103", "104"])          # → calculated
    assert req("POST", "/api/competition-events/%d/publish" % r1a, json={}, role="admin").status_code == 200
    r = req("POST", "/api/competition-events/%d/open" % r1a,
            json={"roster": ["101", "102", "103", "104", "105", "106"]}, role="admin")
    assert r.status_code == 409 and "reset" in r.text


# ---------------- 2) R1B + 晋级确认互斥（事故回归） ----------------

def test_confirm_mutex_and_backfill(env):
    r1b = env["ceid"]["P01Z01-R1B"]
    assert req("POST", "/api/competition-events/%d/open" % r1b,
               json={"roster": ["107", "108", "109", "110", "111", "112"]}, role="admin").status_code == 200
    _checkin(env["cid"], r1b)
    _score_mark(r1b, ["107", "108", "109", "110"])
    assert req("POST", "/api/competition-events/%d/publish" % r1b, json={}, role="admin").status_code == 200

    cid = env["cid"]
    # 同一请求跨分场重复 → 400
    r = req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
            json={"assign": {"P01Z01-R2A": ["101"], "P01Z01-R2B": ["101"]},
                  "append": True, "competition_id": cid}, role="admin")
    assert r.status_code == 400 and "互斥" in r.text
    # 单场蛇形回填
    r = req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
            json={"assign": {"P01Z01-R2A": ["101", "102", "103", "104"]},
                  "append": True, "competition_id": cid}, role="admin")
    assert r.status_code == 200 and r.json()["filled"]["P01Z01-R2A"] == ["101", "102", "103", "104"]
    # 与既有分场冲突 → 400
    r = req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
            json={"assign": {"P01Z01-R2B": ["101"]}, "append": True, "competition_id": cid}, role="admin")
    assert r.status_code == 400 and "互斥" in r.text
    r = req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
            json={"assign": {"P01Z01-R2B": ["107", "108", "109", "110"]},
                  "append": True, "competition_id": cid}, role="admin")
    assert r.status_code == 200
    # 分场互斥不变量
    pa = req("GET", "/api/competition-events/%d/progress" % env["ceid"]["P01Z01-R2A"], role="admin").json()
    pb = req("GET", "/api/competition-events/%d/progress" % env["ceid"]["P01Z01-R2B"], role="admin").json()
    assert not (set(pa["roster"]) & set(pb["roster"]))


# ---------------- 3) 成绩查询多分场晋级（802 事故回归） ----------------

def test_lookup_multi_heat_advancement(env):
    cid = env["cid"]
    d = req("GET", "/api/public/events/%d/lookup?num=107" % cid).json()
    row = next(r for r in d["schedule"] if r["code"] == "P01Z01-R1B")
    assert row["advancement"] is True          # 107 在 R2B——旧 fetchone 单场逻辑误判 False
    d = req("GET", "/api/public/events/%d/lookup?num=105" % cid).json()
    row = next(r for r in d["schedule"] if r["code"] == "P01Z01-R1A")
    assert row["advancement"] is False


# ---------------- 4) 复赛/决赛推进 + 团体总分单一来源 + 前端 ----------------

def test_full_chain_team_standings_and_pages(env):
    cid = env["cid"]
    ceid = env["ceid"]
    for code, marked in (("P01Z01-R2A", ["101", "102"]), ("P01Z01-R2B", ["107", "108"])):
        e = ceid[code]
        assert req("POST", "/api/competition-events/%d/open" % e,
                   json={"roster": ["101", "102", "103", "104"] if "A" in code
                         else ["107", "108", "109", "110"]}, role="admin").status_code == 200
        _checkin(cid, e)
        _score_mark(e, marked)
        assert req("POST", "/api/competition-events/%d/publish" % e, json={}, role="admin").status_code == 200
    r = req("POST", "/api/projects/P01Z01/rounds/2/advancement-confirm",
            json={"assign": {"P01Z01-R3": ["101", "102", "107", "108"]},
                  "append": True, "competition_id": cid}, role="admin")
    assert r.status_code == 200
    for code, dance, placement in (("P01Z01-R3", "平四", {"101": "1", "107": "2", "102": "3", "108": "4"}),
                                   ("P02-R1", "华尔兹", {"201": "1", "202": "2", "203": "3", "204": "4"})):
        e = ceid[code]
        p = req("GET", "/api/competition-events/%d/progress" % e, role="admin").json()
        assert req("POST", "/api/competition-events/%d/open" % e,
                   json={"roster": p["roster"]}, role="admin").status_code == 200
        _checkin(cid, e)
        _score_skate(e, dance, placement)
        assert req("POST", "/api/competition-events/%d/publish" % e, json={}, role="admin").status_code == 200

    # 团体总分：独立复算（计分轮 = R3 + P02-R1 两个最末轮）
    expect = {}
    for num, rank in ((101, 1), (107, 2), (102, 3), (108, 4),
                      (201, 1), (202, 2), (203, 3), (204, 4)):
        unit = "甲院" if num % 4 in (1, 2) else "乙院"
        expect[unit] = expect.get(unit, 0) + POINTS[rank]
    d = req("GET", "/api/public/events/%d/team-standings" % cid).json()
    got = {s["unit"]: s["total"] for s in d["standings"]}
    assert got == expect, "公开榜 %s != 复算 %s" % (got, expect)
    # 管理口径（admin API）与公开口径一致（全部已发布）
    adm = {s["unit"]: s["total"] for s in req("GET", "/api/events/%d/team-standings" % cid, role="admin").json()["standings"]}
    assert {u: t for u, t in adm.items() if t} == expect
    # admin 页面与公开榜同源（HTML 含相同总分）
    html = req("GET", "/events/%d/team-standings" % cid, role="admin").text
    for unit, total in expect.items():
        assert unit in html and ("<td>%s</td>" % unit) in html

    # 前端页面响应
    assert req("GET", "/competitions/%d" % cid).status_code == 200
    assert req("GET", "/events/%d/results" % cid, role="admin").status_code == 200
    assert "团体总分榜" in req("GET", "/events/%d/team-standings" % cid, role="admin").text
    assert "晋级" in req("GET", "/events/%d/advancement?project=P01Z01&round=1" % cid, role="admin").text
    assert req("GET", "/judge", role="J1").status_code == 200
    assert req("GET", "/staff", role="admin").status_code == 200


# ---------------- 5) reset_scoring 破坏性操作确认 ----------------

def test_reset_scoring_requires_confirm(env):
    cid = env["cid"]
    r = req("POST", "/api/events/%d/reset-scoring" % cid, json={}, role="admin")
    assert r.status_code == 400
    r = req("POST", "/api/events/%d/reset-scoring" % cid, json={"confirm": "错误的赛事名"}, role="admin")
    assert r.status_code == 400
    r = req("POST", "/api/events/%d/reset-scoring" % cid, json={"confirm": COMP_NAME}, role="admin")
    assert r.status_code == 200 and r.json()["events_reset"] >= 6
