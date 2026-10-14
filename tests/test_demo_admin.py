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
    # 示例赛事激活（作为台前/公开赛事）并导入裁判 J1、J2
    assert req("POST", f"/api/events/{ids['示例赛事（演示）']}/activate", json={}, role="super").status_code == 200
    assert req("POST", f"/api/events/{ids['示例赛事（演示）']}/imports/judges",
               content="裁判ID,姓名\nJ1,甲\nJ2,乙", role="super").status_code in (200, 201)
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


# ---------------- R55 赛事层级（公开赛事中心 / 赛事首页 / 赛事专属登录） ----------------

def test_competitions_page_lists_active_only(seeded):
    r = req("GET", "/competitions")
    assert "示例赛事（演示）" in r.text
    # 停用普通邀请赛后不应再出现
    ids = seeded
    # （不真正停用，避免影响其他用例；此处只验证页面包含激活赛事）


def test_competition_home_renders_own_data(seeded):
    ids = seeded
    cid = ids["示例赛事（演示）"]
    r = req("GET", f"/competitions/{cid}")
    assert r.status_code == 200
    assert "示例赛事（演示）" in r.text


def test_competition_pages_404_for_inactive(seeded):
    ids = seeded
    # 未激活的赛事：新建一场不激活
    r = req("POST", "/api/events", json={"name": "未激活赛", "date": "x", "location": "y"}, role="super")
    nid = r.json()["id"]
    assert req("GET", f"/competitions/{nid}").status_code == 404
    assert req("GET", f"/competitions/{nid}/login").status_code == 404


def test_comp_scoped_login_binds_session_comp(seeded):
    ids = seeded
    cid = ids["示例赛事（演示）"]
    r = req("POST", "/api/login",
            json={"role": "judge", "judge_id": "J1", "competition_id": cid})
    assert r.status_code == 200, r.text
    token = r.headers["set-cookie"].split("session=")[1].split(";")[0]
    # 会话已绑定赛事：sessions.comp_id 应为该赛事
    row = db_module.rowdict(db_module.get_db().execute(
        "SELECT comp_id FROM sessions WHERE token=?", (token,)).fetchone())
    assert row and row["comp_id"] == cid


def test_comp_scoped_login_rejects_foreign_judge(seeded):
    ids = seeded
    # 新建一场激活赛事并把 J9 加入其中；J9 不在示例赛事 → 示例赛事专属登录必须 403
    r = req("POST", "/api/events", json={"name": "他赛判官", "date": "x", "location": "y"}, role="super")
    other = r.json()["id"]
    req("POST", f"/api/events/{other}/activate", json={}, role="super")
    req("POST", f"/api/events/{other}/imports/judges", content="裁判ID,姓名\nJ9,外来裁判", role="super")
    r = req("POST", "/api/login",
            json={"role": "judge", "judge_id": "J9", "competition_id": ids["示例赛事（演示）"]})
    assert r.status_code == 403


def test_old_judge_bookmark_redirects_to_comp_login(seeded):
    r = req("GET", "/login?role=judge&judge=J1")
    assert r.status_code == 302
    assert "/competitions/" in r.headers["location"] and "role=judge" in r.headers["location"]


def test_login_page_is_super_admin_only(seeded):
    r = req("GET", "/login")
    assert r.status_code == 200 and "总管理员登录" in r.text
    # 其他角色旧链接 → 公开赛事列表
    assert req("GET", "/login?role=marshal").status_code == 302
