#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 WebUI 动线测试（R150）：真实浏览器（Playwright）按角色动线点击，固化 R148/R149
人工走查验证过的交互行为。运行前提 `playwright install chromium`；
入口 `python -m pytest tests-ui -q`。

数据安全（硬护栏，见 ui_lib.py）：默认自起本地服务器（mktemp 临时库），
DSPORT_UI_BASE 非本机地址一律拒绝运行。
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import pytest

from ui_lib import (Api, ui_login, cookie_login, BASE, REPO, WEBAPP,
                    _BASE_holder, _free_port)   # noqa: F401


@pytest.fixture(scope="session")
def base_url():
    """目标服务器：默认自起临时库实例；DSPORT_UI_BASE 可指向已在本机跑的实例。"""
    if BASE:
        yield BASE
        return
    tmp = tempfile.mkdtemp(prefix="dsport-ui-")
    port = _free_port()
    db = os.path.join(tmp, "ui.db")
    env = dict(os.environ, DSPORT_DB=db, DSPORT_PORT=str(port),
               DSPORT_FILES_DIR=os.path.join(tmp, "files"))
    proc = subprocess.Popen([sys.executable, "run.py"], cwd=WEBAPP, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/competitions" % port, timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.3)
    else:
        proc.terminate()
        raise RuntimeError("UI 测试服务器未就绪（port %d）" % port)
    _BASE_holder["db"] = db
    yield "http://127.0.0.1:%d" % port
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def client(base_url):
    """管理员会话 API 客户端 + 造赛助手。"""
    api = Api(base_url)
    api.db_path = _BASE_holder.get("db")
    api.login_admin()
    api.create_printer()
    return api


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def ctx(browser, base_url):
    """每测试一个浏览器上下文；收集 JS pageerror，测试结束断言为零。
    context 级预关 onboarding 首访弹层（cookie 注入的角色不经登录页，会被弹层遮挡点击）。"""
    context = browser.new_context(viewport={"width": 1280, "height": 900}, base_url=base_url)
    context._js_errors = []
    context.on("pageerror", lambda e: context._js_errors.append(str(e)))
    context.add_init_script(
        "try{['judge','marshal','host','admin'].forEach(function(k){localStorage.setItem('onb:'+k,'1')})}catch(e){}")
    yield context
    errs = context._js_errors
    context.close()
    assert not errs, "页面 JS 异常：%s" % errs


@pytest.fixture()
def page(ctx):
    return ctx.new_page()


@pytest.fixture()
def as_admin(page, ctx, base_url, client):
    """管理员已登录的 page（API cookie 注入）。"""
    cookie_login(ctx, base_url, client.cookie)
    return page
