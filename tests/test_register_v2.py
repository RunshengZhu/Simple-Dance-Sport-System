#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R143 报名入口体系与去重机制回归。"""
import os
import sys
import tempfile

if "server.app" not in sys.modules:
    _TMP = tempfile.mkdtemp(prefix="dsh-regv2-")
    os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
    os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
import urllib.parse  # noqa: E402

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


@pytest.fixture(scope="module", autouse=True)
def env():
    _login("admin", {"role": "admin", "password": "admin123"})
    r = req("POST", "/api/events", json={"name": "报名v2赛", "date": "", "location": ""}, role="admin")
    cid = r.json()["id"]
    req("POST", "/api/events/%d/activate" % cid, role="admin")
    req("POST", "/api/events/%d/projects" % cid, json={"name": "新生平四单项"}, role="admin")
    req("POST", "/api/events/%d/projects" % cid, json={"name": "新生伦巴单项"}, role="admin")
    r = req("POST", "/api/events/%d/registrations/settings" % cid,
            json={"reg_open": True, "reg_modes": ["individual", "unit"], "reg_note": "", "reg_unit_code": ""},
            role="admin")
    assert r.status_code == 200
    return {"cid": cid}


def test_entry_links_with_qr(env):
    r = req("GET", "/api/events/%d/registrations/entry-links" % env["cid"], role="admin")
    d = r.json()
    assert d["public_qr"].startswith("data:image/png;base64,")
    assert "/register" in d["public_url"]
    r = req("POST", "/api/events/%d/registrations/unit-links" % env["cid"],
            json={"unit": "测试二队"}, role="admin")
    assert r.status_code == 200 and "unit-register" in r.json()["url"]


def test_individual_gender_required_and_dedup(env):
    cid = env["cid"]
    r = req("POST", "/api/public/events/%d/register" % cid,
            json={"mode": "individual", "contact_name": "张三", "contact_phone": "13800000102",
                  "members": [{"name": "张三", "role": "新生", "projects": ["1"]}]})
    assert r.status_code == 400 and "性别" in r.text   # 缺性别
    r = req("POST", "/api/public/events/%d/register" % cid,
            json={"mode": "individual", "contact_name": "李星辰", "contact_phone": "13800000101",
                  "members": [{"name": "李星辰", "gender": "男", "partner": "武文婕", "projects": ["1"]}]})
    assert r.status_code == 200
    # 重提交同姓名+同联系方式 → 项目合并（1+2）
    r = req("POST", "/api/public/events/%d/register" % cid,
            json={"mode": "individual", "contact_name": "李星辰", "contact_phone": "13800000101",
                  "members": [{"name": "李星辰", "gender": "男", "partner": "武文婕", "projects": ["1", "2"]}]})
    assert r.status_code == 200
    d = req("GET", "/api/events/%d/registrations" % cid, role="admin").json()
    rows = [x for x in d["rows"] if x["name"] == "李星辰"]
    assert len(rows) == 1 and sorted(rows[0]["projects"].split(",")) == ["1", "2"]
    assert rows[0]["gender"] == "男"


def test_resubmit_returns_persisted_code_r148(env):
    """R148 回归：合并去重的重复提交必须返回库里真实存在的提交码——
    旧实现返回新生成但未落库的码，选手凭它查询永远「未找到」（幽灵码）。"""
    cid = env["cid"]
    body = {"mode": "individual", "contact_name": "码回归", "contact_phone": "13800000148",
            "members": [{"name": "码回归", "gender": "女", "projects": ["1"]}]}
    r1 = req("POST", "/api/public/events/%d/register" % cid, json=body)
    assert r1.status_code == 200
    code1 = r1.json()["submit_code"]
    r2 = req("POST", "/api/public/events/%d/register" % cid, json=body)
    assert r2.status_code == 200
    code2 = r2.json()["submit_code"]
    assert code2 == code1, "重复提交应沿用首次落库的提交码（旧=%s 新=%s）" % (code1, code2)
    # 该码必须真实可查
    q = req("GET", "/api/public/events/%d/register/status?code=%s" % (cid, code2)).json()
    assert q["ok"] and len(q["entries"]) == 1


def test_unit_manager_link_flow(env):
    cid = env["cid"]
    r = req("POST", "/api/events/%d/registrations/unit-links" % cid,
            json={"unit": "测试二队"}, role="admin")
    url = r.json()["url"]
    m = url.split("/unit-register/")[1]
    unit_enc, token = m.split("/")
    api = "/api/public/events/%d/unit-register/%s/%s" % (cid, unit_enc, token)
    # 免登录页面可达
    r = req("GET", url.replace("/api/public", "").replace("/competitions/%d/unit-register" % cid,
                                                          "/competitions/%d/unit-register" % cid))
    r = req("GET", "/competitions/%d/unit-register/%s/%s" % (cid, unit_enc, token))
    assert r.status_code == 200 and "测试二队" in r.text
    # 错误 token → 页面 302 跳转（HTML 路由 403 转 /login）；API 直打 403
    r = req("GET", "/competitions/%d/unit-register/%s/badtoken" % (cid, unit_enc))
    assert r.status_code in (302, 403)
    r2 = req("POST", "/api/public/events/%d/unit-register/%s/badtoken" % (cid, unit_enc),
             json={"contact_name": "x", "contact_phone": "y", "members": [{"name": "a", "gender": "男", "projects": ["1"]}]})
    assert r2.status_code == 403
    # 提交 + 去重合并
    r = req("POST", api, json={"contact_name": "王领队", "contact_phone": "139",
                               "members": [{"name": "胡一帆", "gender": "男", "partner": "潘迪", "projects": ["1"]}]})
    assert r.status_code == 200 and r.json()["added"] == 1
    r = req("POST", api, json={"contact_name": "王领队", "contact_phone": "139",
                               "members": [{"name": "胡一帆", "gender": "男", "partner": "潘迪", "projects": ["1", "2"]}]})
    assert r.status_code == 200 and r.json()["updated"] == 1
    d = req("GET", "/api/events/%d/registrations" % cid, role="admin").json()
    row = [x for x in d["rows"] if x["name"] == "胡一帆"][0]
    assert sorted(row["projects"].split(",")) == ["1", "2"]
    # CSV 导入（项目编号列）
    csv = "姓名,性别,身份,搭档姓名,搭档单位,搭档身份,1,2\n吴骏哲,男,新生,农茜茜,测试二队,新生,,1\n".encode("utf-8")
    r = req("POST", api + "/import", content=csv)
    assert r.status_code == 200 and r.json()["added"] == 1
    # 缺性别被拒：全条目均无效时 400（问题列表在 detail 中）
    r = req("POST", api, json={"contact_name": "王", "contact_phone": "139",
                               "members": [{"name": "无性别", "partner": "", "projects": ["1"]}]})
    assert r.status_code == 400 and "性别" in r.text
