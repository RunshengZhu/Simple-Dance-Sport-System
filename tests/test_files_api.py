#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R43 文件分层托管 API 测试（httpx ASGITransport 直连，不出网）。

覆盖：三种层权限（public/token/admin）的建层/上传/下载/列表/删除、
凭证模型（Bearer 上传、?token= 下载、一次性明文、重置失效）、同名覆盖、
路径 slug 校验、下载计数。TestClient 与 httpx 0.28 不兼容，故用 ASGI 直连 +
asyncio.run 同步封装；lifespan 不自动执行，模块级手动 init_db()。
"""
import os
import tempfile

# 在导入 server.app 之前固定隔离环境（FILES_ROOT 与 DB 路径在导入时求值）
_TMP = tempfile.mkdtemp(prefix="dsh-files-test-")
os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from server import app as app_module, db as db_module  # noqa: E402

db_module.init_db()   # ASGITransport 不执行 lifespan，手动建表

_ADMIN = {"session": None}


def req(method, path, content=None, json=None, admin=False, bearer=None,
        token=None, no_redirect=False):
    """同步 ASGI 请求。admin=True 自动附管理员会话；bearer/token 附层凭证。"""
    headers = {}
    if admin and _ADMIN["session"]:
        headers["Cookie"] = "session=" + _ADMIN["session"]
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    url = path + (f"?token={token}" if token else "")

    async def _run():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(method, url, content=content, json=json, headers=headers)

    return asyncio.run(_run())


@pytest.fixture(scope="module", autouse=True)
def _admin_session():
    r = req("POST", "/api/login", json={"role": "admin", "password": "admin123"})
    assert r.status_code == 200
    _ADMIN["session"] = r.headers["set-cookie"].split("session=")[1].split(";")[0]
    yield


# ---------------- 建层 ----------------

@pytest.fixture(scope="module")
def pub_tier(_admin_session):
    assert req("POST", "/api/files/tiers",
               json={"name": "pub", "perm": "public", "note": "公开层"}, admin=True).status_code == 200
    return "pub"


@pytest.fixture(scope="module")
def token_tier(_admin_session):
    r = req("POST", "/api/files/tiers", json={"name": "tok", "perm": "token"}, admin=True)
    assert r.status_code == 200
    token = r.json()["token"]
    assert token, "token 层必须返回一次性明文凭证"
    assert req("PUT", "/api/files/tok/build.bin",
               content=b"\x00\x01binary", bearer=token).status_code == 200
    return {"name": "tok", "token": token}


@pytest.fixture(scope="module")
def adm_tier(_admin_session):
    assert req("POST", "/api/files/tiers", json={"name": "adm", "perm": "admin"}, admin=True).status_code == 200
    assert req("PUT", "/api/files/adm/x.txt", content=b"secret", admin=True).status_code == 200
    return "adm"


def test_tier_duplicate_rejected(_admin_session, pub_tier):
    assert req("POST", "/api/files/tiers", json={"name": "pub", "perm": "public"},
               admin=True).status_code == 400


def test_tier_bad_names_and_perm_rejected(_admin_session):
    for bad in ("../evil", "a/b", "-lead"):
        assert req("POST", "/api/files/tiers", json={"name": bad, "perm": "public"},
                   admin=True).status_code == 400
    assert req("POST", "/api/files/tiers", json={"name": "okname", "perm": "weird"},
               admin=True).status_code == 400


def test_tier_list_aggregates(_admin_session, pub_tier):
    r = req("GET", "/api/files/tiers", admin=True)
    assert r.status_code == 200
    tier = [t for t in r.json()["tiers"] if t["name"] == "pub"][0]
    assert tier["perm"] == "public" and "files" in tier and "bytes" in tier


# ---------------- 上传 ----------------

def test_upload_admin_public(_admin_session, pub_tier):
    r = req("PUT", "/api/files/pub/hello.txt", content=b"hello world", admin=True)
    assert r.status_code == 200
    body = r.json()
    assert body["overwritten"] is False and body["size"] == 11 and len(body["sha256"]) == 64


def test_upload_bearer_token_layer(token_tier):
    r = req("PUT", "/api/files/tok/another.bin", content=b"bb", bearer=token_tier["token"])
    assert r.status_code == 200


def test_upload_token_layer_without_cred_rejected(token_tier):
    assert req("PUT", "/api/files/tok/no-cred.bin", content=b"x").status_code == 401


def test_upload_empty_rejected(_admin_session, pub_tier):
    assert req("PUT", "/api/files/pub/empty.txt", content=b"", admin=True).status_code == 400


def test_upload_bad_filename_rejected(_admin_session, pub_tier):
    assert req("PUT", "/api/files/pub/..%2Fevil", content=b"x", admin=True).status_code in (400, 404)
    assert req("PUT", "/api/files/pub/a%2Fb.txt", content=b"x", admin=True).status_code in (400, 404)


def test_upload_overwrite(_admin_session, pub_tier):
    first = req("PUT", "/api/files/pub/over.txt", content=b"v1", admin=True).json()
    second = req("PUT", "/api/files/pub/over.txt", content=b"version-2-longer", admin=True).json()
    assert first["overwritten"] is False and second["overwritten"] is True
    assert second["sha256"] != first["sha256"]


def test_upload_admin_layer_needs_session(adm_tier):
    assert req("PUT", "/api/files/adm/x.txt", content=b"x").status_code == 401
    assert req("PUT", "/api/files/adm/x2.txt", content=b"x", admin=True).status_code == 200


# ---------------- 下载 ----------------

def test_download_public_anonymous(pub_tier):
    print("FILES_ROOT:", os.environ["DSPORT_FILES_DIR"], "app:", app_module.FILES_ROOT)
    r = req("GET", "/files/pub/hello.txt")
    assert r.status_code == 200 and r.content == b"hello world"
    # /files 是下载渠道：Content-Disposition: attachment 为预期语义（inline 请走 /apps）
    assert "attachment" in r.headers.get("content-disposition", "")
    assert r.headers["content-type"].startswith("text/plain")
    assert r.headers["etag"].startswith('"')


def test_download_public_head_ok(pub_tier):
    assert req("HEAD", "/files/pub/hello.txt").status_code == 200


def test_download_token_layer_with_token(token_tier):
    r = req("GET", f"/files/tok/build.bin?token={token_tier['token']}")
    assert r.status_code == 200 and r.content == b"\x00\x01binary"


def test_download_token_layer_missing_cred_redirects(token_tier):
    assert req("GET", "/files/tok/build.bin", no_redirect=True).status_code == 302
    assert req("GET", "/files/tok/build.bin?token=wrong", no_redirect=True).status_code == 302


def test_download_admin_layer(adm_tier):
    assert req("GET", "/files/adm/x.txt", no_redirect=True).status_code == 302
    assert req("GET", "/files/adm/x.txt", admin=True).status_code == 200


def test_download_missing_404(pub_tier):
    assert req("GET", "/files/pub/ghost.txt").status_code == 404


def test_download_counter_increments(_admin_session, pub_tier):
    files = req("GET", "/api/files/pub").json()["files"]
    n0 = [f["downloads"] for f in files if f["filename"] == "hello.txt"][0]
    req("GET", "/files/pub/hello.txt")
    files2 = req("GET", "/api/files/pub").json()["files"]
    n1 = [f["downloads"] for f in files2 if f["filename"] == "hello.txt"][0]
    assert n1 == n0 + 1


# ---------------- 列表与删除 ----------------

def test_list_public_anonymous_ok(pub_tier):
    r = req("GET", "/api/files/pub")
    assert r.status_code == 200 and r.json()["perm"] == "public"


def test_list_token_layer_requires_cred(token_tier):
    assert req("GET", "/api/files/tok").status_code == 401
    r = req("GET", "/api/files/tok", bearer=token_tier["token"])
    names = {f["filename"] for f in r.json()["files"]}
    assert {"build.bin", "another.bin"} <= names


def test_delete_file_then_404(_admin_session, pub_tier):
    req("PUT", "/api/files/pub/todel.txt", content=b"delme", admin=True)
    assert req("DELETE", "/api/files/pub/todel.txt", admin=True).status_code == 200
    assert req("GET", "/files/pub/todel.txt").status_code == 404


def test_delete_tier_cascades(_admin_session):
    assert req("POST", "/api/files/tiers", json={"name": "temp", "perm": "public"}, admin=True).status_code == 200
    assert req("PUT", "/api/files/temp/f.bin", content=b"data", admin=True).status_code == 200
    assert req("DELETE", "/api/files/tiers/temp", admin=True).status_code == 200
    assert req("GET", "/api/files/temp").status_code == 404
    assert req("GET", "/files/temp/f.bin").status_code == 404


def test_tier_token_reset_invalidates_old(_admin_session, token_tier):
    old = token_tier["token"]
    r = req("PUT", "/api/files/tiers/tok/token", admin=True)
    assert r.status_code == 200
    new = r.json()["token"]
    assert new != old
    assert req("GET", f"/files/tok/build.bin?token={new}").status_code == 200
    assert req("GET", f"/files/tok/build.bin?token={old}", no_redirect=True).status_code == 302


# ---------------- /apps 静态 inline 直出（R43b） ----------------

def test_apps_inline_serves_public_layer(_admin_session, pub_tier):
    req("PUT", "/api/files/pub/index.html", content=b"<h1>app</h1>", admin=True)
    r = req("GET", "/apps/pub/index.html")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html; charset=utf-8")
    assert r.headers.get("content-disposition", "").startswith("inline")
    assert r.headers.get("cache-control") == "no-cache"


def test_apps_index_default_page(_admin_session, pub_tier):
    assert req("GET", "/apps/pub/").status_code == 200
    assert req("GET", "/apps/pub").status_code == 200
    assert req("GET", "/apps/pub/index.html").content == b"<h1>app</h1>"


def test_apps_non_public_layer_hidden(adm_tier):
    # 仅 public 层可从 /apps 直出（token/admin 层不泄漏到在线分发面）
    assert req("GET", "/apps/adm/x.txt").status_code == 404
    assert req("GET", "/apps/tok/index.html").status_code == 404
