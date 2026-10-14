#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R54 赛事管理员（compadmin）回归。

架构：users.role='compadmin' + comp_id 绑定；登录后会话角色为 admin（页面通行），
能力由 compadmin_scope 中间件按 comp_id 钳制——全局操作（用户管理/建赛/库级
导入导出/大屏全局设置）拒绝，带 competition_id 的路径仅放行自己的赛事，
晋级接口仅当台前赛事为自己时放行。总管理员（环境口令，无账号）永不受限。
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="dsh-compadmin-test-")
os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from server import app as app_module, db as db_module  # noqa: E402

db_module.init_db()
app_module._seed_default_accounts()

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
def seeded():
    _login("super", {"role": "admin", "password": "admin123"})
    # 两场赛事 + 一个绑定示例赛事的 compadmin
    ids = {}
    for name in ("示例赛事（演示）", "普通邀请赛"):
        r = req("POST", "/api/events", json={"name": name, "date": "2026-10-14", "location": "x"},
                role="super")
        ids[name] = r.json()["id"]
    r = req("POST", "/api/users",
            json={"username": "demo-admin", "password": "demopass1",
                  "role": "compadmin", "competition_id": ids["示例赛事（演示）"],
                  "display_name": "示例赛事管理员"}, role="super")
    assert r.status_code in (200, 201), r.text
    _login("ca", {"role": "admin", "username": "demo-admin", "password": "demopass1"})
    return ids


def test_compadmin_login_and_session_role(seeded):
    # compadmin 会话角色为 admin：管理页面通行（自己的赛事）
    assert _SESSIONS.get("ca")
    r = req("GET", "/api/events", role="ca")
    assert r.status_code == 200, "compadmin 可读赛事列表（页面重定向在 /events 上做）"


def test_compadmin_scope_on_own_comp(seeded):
    ids = seeded
    cid = ids["示例赛事（演示）"]
    assert req("POST", f"/api/events/{cid}/activate", json={}, role="ca").status_code == 200
    # 自己赛事的详情页/导入页可开
    assert req("GET", f"/events/{cid}/schedule", role="ca").status_code == 200
    assert req("GET", f"/events/{cid}/import", role="ca").status_code == 200
    # 可删除自己的赛事（本测试放最后验证会破坏其他用例 → 仅验证非删除路径）
    assert req("GET", f"/api/public/events/{cid}/schedule", role="ca").status_code == 200


def test_compadmin_blocked_on_other_comp(seeded):
    ids = seeded
    other = ids["普通邀请赛"]
    assert req("DELETE", f"/api/events/{other}", role="ca").status_code == 403
    assert req("POST", f"/api/events/{other}/activate", json={}, role="ca").status_code == 403
    assert req("GET", f"/events/{other}/schedule", role="ca").status_code == 403
    assert req("GET", f"/events/{other}/import", role="ca").status_code == 403


def test_compadmin_cannot_create_comp_or_manage_users(seeded):
    assert req("POST", "/api/events",
               json={"name": "偷建的赛事"}, role="ca").status_code == 403
    assert req("POST", "/api/users",
               json={"username": "x9", "password": "123456", "role": "marshal"}, role="ca").status_code == 403


def test_compadmin_cannot_touch_global_ops(seeded):
    assert req("POST", "/api/screen-control", json={"mode": "welcome"}, role="ca").status_code == 403
    assert req("GET", "/api/export/json", role="ca").status_code == 403
    assert req("GET", "/api/export/db", role="ca").status_code == 403
    assert req("POST", "/api/import/json", content=b"{}", role="ca").status_code == 403


def test_super_admin_unaffected(seeded):
    ids = seeded
    assert req("DELETE", f"/api/events/{ids['普通邀请赛']}", role="super").status_code == 200
    assert req("POST", "/api/screen-control", json={"mode": "welcome"}, role="super").status_code == 200
    assert req("POST", "/api/screen-control", json={"mode": "auto"}, role="super").status_code == 200


def test_super_admin_can_create_compadmin_accounts(seeded):
    r = req("POST", "/api/users",
            json={"username": "ca2", "password": "pass123456", "role": "compadmin",
                  "competition_id": seeded["示例赛事（演示）"]}, role="super")
    assert r.status_code in (200, 201), r.text
    # 缺 competition_id 必须报错
    r2 = req("POST", "/api/users",
             json={"username": "ca3", "password": "pass123456", "role": "compadmin"}, role="super")
    assert r2.status_code == 400
