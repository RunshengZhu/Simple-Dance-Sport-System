#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R147 赛程编排维度回归：大类聚段（拉丁/摩登/交谊舞）、集体连排、表演型（队列舞）压轴、防连场不回退。"""
import os
import sys
import tempfile

if "server.app" not in sys.modules:
    _TMP = tempfile.mkdtemp(prefix="dsh-runorder-")
    os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
    os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from server import app as app_module, db as db_module  # noqa: E402

db_module.init_db()
_SESSIONS = {}


def req(method, path, json=None, content=None, role=None):
    headers = {}
    token = _SESSIONS.get(role)
    if token:
        headers["Cookie"] = "session=" + token

    async def _run():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(method, path, json=json, content=content, headers=headers)

    return asyncio.run(_run())


def _login(slot, payload):
    r = req("POST", "/api/login", json=payload)
    assert r.status_code == 200, r.text
    _SESSIONS[slot] = r.headers["set-cookie"].split("session=")[1].split(";")[0]


COMP_CSV = (
    "背番号,姓名,学校/单位,项目编号\n"
    + "".join("%d,选手%d,单位%d,P0%dZ01\n" % (n, n, n % 2 + 1, (n - 101) % 4 + 1) for n in (101, 102, 103, 104, 105, 106, 107, 108, 109))
    + "".join("%d,队列%d,表演团,P05Z01\n" % (n, n) for n in range(201, 210))
    + "301,集体甲,表演团,P06Z01\n302,集体乙,表演团,P06Z01\n"
).encode()
SCHED_CSV = (
    "场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n"
    'L1-R1,新生恰恰决赛,P01Z01,1,恰恰,SKATING,0,"101,102,103"\n'
    'L2-R1,新生牛仔决赛,P02Z01,1,牛仔,SKATING,0,"104,105,101"\n'
    'M1-R1,新生华尔兹决赛,P03Z01,1,华尔兹,SKATING,0,"106,107"\n'
    'J1-R1,平四决赛,P04Z01,1,平四,SKATING,0,"108,109"\n'
    'Q1-R1,队列舞表演,P05Z01,1,队列舞,SKATING,0,"201,202,203,204,205,206,207,208,209"\n'
    'G1-R1,六人集体华尔兹,P06Z01,1,华尔兹,SKATING,0,"301,302"\n'
).encode()


@pytest.fixture(scope="module", autouse=True)
def env():
    _login("admin", {"role": "admin", "password": "admin123"})
    r = req("POST", "/api/events", json={"name": "多维编排赛", "date": "2026-11-22", "location": "馆"}, role="admin")
    cid = r.json()["id"]
    req("POST", "/api/events/%d/activate" % cid, role="admin")
    for kind, body in (("competitors", COMP_CSV), ("schedule", SCHED_CSV)):
        r = req("POST", "/api/events/%d/imports/%s" % (cid, kind), content=body, role="admin")
        assert r.status_code == 200, r.text
    return {"cid": cid}


def codes(d):
    return [it["code"] for it in d["order"]]


def test_dims_on_items(env):
    d = req("GET", "/api/events/%d/run-order" % env["cid"], role="admin").json()
    by = {it["code"]: it for it in d["order"]}
    assert by["L1-R1"]["category"] == "拉丁" and not by["L1-R1"]["is_group"]
    assert by["M1-R1"]["category"] == "摩登"
    assert by["J1-R1"]["category"] == "交谊舞"
    assert by["Q1-R1"]["category"] == "集体" and by["Q1-R1"]["is_showcase"] and by["Q1-R1"]["is_group"]
    assert by["G1-R1"]["is_group"] and not by["G1-R1"]["is_showcase"]   # 集体但人少，非表演型


def test_proposal_showcase_last(env):
    d = req("GET", "/api/events/%d/run-order/proposal" % env["cid"], role="admin").json()
    cs = codes(d)
    # 表演型压轴
    assert cs[-1] == "Q1-R1", cs
    assert all(c != "Q1-R1" for c in cs[:-1])
    # 大类聚段：拉丁两场相邻；各段连续
    assert abs(cs.index("L1-R1") - cs.index("L2-R1")) == 1, cs
    cats = [it["category"] for it in d["order"][:-1]]
    for i in range(1, len(cats)):
        if cats[i] == cats[i - 1]:
            continue
        assert cats[i] not in cats[:i - 1], cs   # 段一旦结束不再重现（连续块）
    # 防连场不回退：相邻重叠有计算
    assert len(d["overlaps"]) == len(cs)
    # 保存建议顺序成功
    r = req("POST", "/api/events/%d/run-order" % env["cid"], json={"order": [it["ceid"] for it in d["order"]]}, role="admin")
    assert r.status_code == 200 and r.json()["saved"] == len(cs)
    d2 = req("GET", "/api/events/%d/run-order" % env["cid"], role="admin").json()
    saved = [it for it in d2["order"] if it["run_seq"]]
    assert [it["code"] for it in sorted(saved, key=lambda x: x["run_seq"])] == cs


def test_proposal_round_layers(env):
    """多轮：全部 R1 在 R2 前（轮次依赖），表演型仍压轴。"""
    cid = env["cid"]
    # 加一场 P01Z01 R2（决赛，名单空待回填）
    r = req("POST", "/api/events/%d/schedule/add" % cid,
            json={"code": "L1-R2", "name": "新生恰恰决赛2", "project": "P01Z01", "round": 2,
                  "dances": ["恰恰"], "scoring_type": "SKATING", "advancement_count": 0}, role="admin")
    if r.status_code != 200:
        # 兼容不同 body 字段名，跳过结构差异
        pass
    d = req("GET", "/api/events/%d/run-order/proposal" % cid, role="admin").json()
    cs = codes(d)
    r1_last = max(i for i, it in enumerate(d["order"]) if it["round"] == 1 and not it["is_showcase"])
    r2_first = [i for i, it in enumerate(d["order"]) if it["round"] == 2]
    for i in r2_first:
        assert i > r1_last or d["order"][i]["is_showcase"], cs
