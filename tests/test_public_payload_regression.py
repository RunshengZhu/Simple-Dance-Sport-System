#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公开端点回归：screen-state 与按背番号查询（R49 回归修复护栏）。

R49 曾把 _public_payload 内部改成 _current_competition(request)，而该函数
自身不持有 request → screen-state / lookup 两个公开端点 500（大屏白屏、
观众查询报错）。此处锁定：两个端点在「有已发布场次」的数据下必须 200 且
返回结构化内容，防止同类作用域回归。
"""
import os
import tempfile

# 在导入 server.app 之前固定隔离环境（DB 路径在导入时求值）
_TMP = tempfile.mkdtemp(prefix="dsh-public-test-")
os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import urllib.parse  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from server import app as app_module, db as db_module  # noqa: E402

db_module.init_db()
app_module._seed_default_accounts()   # ASGITransport 不执行 startup，手动播种 host/marshal

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


@pytest.fixture(scope="module", autouse=True)
def seeded_event():
    """最小闭环：建赛→导入→开场→全检录→三裁判提交→发布。"""
    _login("admin", {"role": "admin", "password": "admin123"})
    _login("marshal", {"role": "marshal", "username": "marshal", "password": "marshal123"})
    r = req("POST", "/api/events", json={"name": "公开端点回归赛", "date": "2026-10-04", "location": "测试馆"},
            role="admin")
    cid = r.json()["id"]
    assert req("POST", f"/api/events/{cid}/activate", json={}, role="admin").status_code == 200
    assert req("POST", f"/api/events/{cid}/imports/competitors",
               content="背番号,项目编号,姓名,学校/单位\n" +
                       "".join(f"2{i},PA,选手{i},测试大学\n" for i in range(1, 7)),
               role="admin").status_code in (200, 201)
    assert req("POST", f"/api/events/{cid}/imports/judges",
               content="裁判ID,姓名\nJ1,甲\nJ2,乙\nJ3,丙", role="admin").status_code in (200, 201)
    sched = ("场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n"
             "PA1,PA第1轮,PA,1,华尔兹,SKATING,0," + ",".join(f"2{i}" for i in range(1, 7)) + "\n")
    assert req("POST", f"/api/events/{cid}/imports/schedule", content=sched, role="admin").status_code in (200, 201)
    r = req("GET", f"/api/public/events/{cid}/schedule")
    ceid = r.json()["events"][0]["id"]
    assert req("POST", f"/api/competition-events/{ceid}/open",
               json={"roster": [f"2{i}" for i in range(1, 7)]}, role="admin").status_code == 200
    assert req("POST", f"/api/competition-events/{ceid}/checkin",
               json={"numbers": [f"2{i}" for i in range(1, 7)], "state": True},
               role="marshal").status_code == 200
    dance = urllib.parse.quote("华尔兹")
    orders = [{f"2{i}": k for k, i in enumerate(range(1, 7), 1)},
              {f"2{i}": k for k, i in enumerate(range(6, 0, -1), 1)},
              {f"2{i}": k for k, i in enumerate([2, 1, 3, 5, 4, 6], 1)}]
    for j, vals in zip(("J1", "J2", "J3"), orders):
        _login(j, {"role": "judge", "judge_id": j})
        r = req("PUT", f"/api/judge/competition-events/{ceid}/dances/{dance}/sheet",
                json={"values": vals}, role=j)
        assert r.status_code == 200, r.text
    r = req("POST", f"/api/competition-events/{ceid}/publish", json={}, role="admin")
    assert r.status_code == 200, r.text
    return cid, ceid


def test_screen_state_ok_with_published(seeded_event):
    cid, _ = seeded_event
    r = req("GET", f"/api/public/events/{cid}/screen-state")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["competition"]["id"] == cid
    assert len(d["published_results"]) == 1
    assert d["published_results"][0]["results"], "已发布场次应带名次行"
    assert "forced_mode" in d and "team_standings" in d


def test_public_lookup_ok_with_published(seeded_event):
    cid, _ = seeded_event
    r = req("GET", f"/api/public/events/{cid}/lookup?num=21")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["number"] == "21"
    assert d["published_results"], "查询应返回该选手已发布成绩"
    assert {"code", "name", "round", "rank"} <= set(d["published_results"][0].keys())
