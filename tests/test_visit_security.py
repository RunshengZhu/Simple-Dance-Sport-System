#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R53 访问统计与基础防护回归。

覆盖：visit_stats 页面计数（只数 HTML 200，接口/静态不计）、
安全响应头（nosniff / SAMEORIGIN / Referrer-Policy）、
登录接口按 IP 限速（默认 10 次/60s，超出 429）、
/api/stats 管理员权限。
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="dsh-visit-test-")
os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from server import app as app_module, db as db_module  # noqa: E402

db_module.init_db()
app_module._seed_default_accounts()


def req(method, path, content=None, json=None, headers=None):
    """同步 ASGI 请求（无 client 信息 → 不参与限速，与既有测试一致）。"""

    async def _run():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(method, path, content=content, json=json, headers=headers)

    return asyncio.run(_run())


def req_as(ip, method, path, json=None):
    """带真实 client IP 的请求（限速生效）。"""

    async def _run():
        transport = httpx.ASGITransport(app=app_module.app, client=(ip, 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(method, path, json=json)

    return asyncio.run(_run())


def test_visit_counts_html_pages_only():
    assert req("GET", "/").status_code == 200            # 门户
    assert req("GET", "/login").status_code == 200       # 评分系统入口
    assert req("GET", "/manual").status_code == 200      # 手册
    rows = {r["slug"]: r["n"] for r in db_module.rows(
        db_module.get_db().execute("SELECT slug, n FROM visit_stats"))}
    assert rows.get("portal", 0) >= 1
    assert rows.get("scoring", 0) >= 1
    assert rows.get("manual", 0) >= 1
    before = dict(rows)
    assert req("GET", "/api/public/events/999/schedule").status_code in (200, 404)
    assert req("GET", "/static/style.css").status_code == 200
    rows2 = {r["slug"]: r["n"] for r in db_module.rows(
        db_module.get_db().execute("SELECT slug, n FROM visit_stats"))}
    assert rows2 == before, "接口与静态资源不得计入访问统计"


def test_security_headers_present():
    r = req("GET", "/")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "SAMEORIGIN"
    assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_general_rate_limit_per_ip():
    """中间件常规限速（默认 300/10s per IP）：超过后 429 + Retry-After，其他 IP 不受影响。"""
    ip = "192.0.2.9"
    codes = [req_as(ip, "GET", "/?probe=%d" % i).status_code for i in range(310)]
    assert codes.count(429) >= 5, f"常规限速未生效: 尾部 {codes[-10:]}"
    assert req_as("198.51.100.7", "GET", "/").status_code == 200
    # 429 带 Retry-After（拿一个 429 验证）
    retry = None
    for i in range(310, 320):
        r = req_as(ip, "GET", "/?probe=%d" % i)
        if r.status_code == 429:
            retry = r.headers.get("retry-after")
            break
    assert retry is not None and retry.isdigit()


def test_existing_login_failure_lockout_still_works():
    """既有防线回归：同一 IP 连续 5 次口令错误后 429（登录失败锁定，先于中间件限速触发）。"""
    ip = "203.0.113.9"
    codes = [req_as(ip, "POST", "/api/login",
                    json={"role": "admin", "password": "wrong"}).status_code
             for _ in range(8)]
    assert codes[0] == 403 and codes[-1] == 429, f"登录失败锁定异常: {codes}"
    # 其他 IP 不受影响
    assert req_as("198.51.100.7", "POST", "/api/login",
                  json={"role": "admin", "password": "wrong"}).status_code == 403


def test_stats_api_requires_admin():
    r = req("GET", "/api/stats")
    assert r.status_code in (401, 403), "访问统计必须管理员可见"
    # 管理员可读且含 slug 结构
    async def _run():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            login = await c.post("/api/login", json={"role": "admin", "password": "admin123"})
            token = login.headers["set-cookie"].split("session=")[1].split(";")[0]
            return await c.get("/api/stats", headers={"Cookie": "session=" + token})
    r = asyncio.run(_run())
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list) and items
    assert {"slug", "total", "today", "d7"} <= set(items[0].keys())
