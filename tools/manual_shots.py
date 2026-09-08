#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动线指南截图批量生成器（Playwright 确定性全页截图）。

用法: python3 tools/manual_shots.py [BASE] [OUTDIR]
  BASE 默认 http://59.110.90.21:8321；OUTDIR 默认 server/static/manual/r21

视口规格（与 docs/UX-REVIEW-R30.md 一致）：
  桌面管理员 1440×900 · 裁判/观众移动 375×812 (isMobile) · 大屏 1920×1080
产出：a1-a12/u-users（桌面）、j1-j5（移动裁判）、p1-p3（移动公众）、s-*（大屏四态）
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://59.110.90.21:8321"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "server/static/manual/r21")
OUT.mkdir(parents=True, exist_ok=True)
ADMIN_PW = "CrmnJG5k9JKCuk9g"       # 线上已轮换的管理员口令（systemd override）
HOST_PW = "GRumqRvZVDTqGybh"
MARSHAL_PW = "MspQpW862RmQUGdc"
COMP = 15

results = []


def shot(page, name, full=False):
    page.screenshot(path=str(OUT / name), full_page=full)
    results.append(name)
    print("shot:", name)


def settle(page, ms=900):
    try:
        page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def api_login(ctx, role, password=None, judge_id=None):
    body = {"role": role, "password": password}
    if judge_id:
        body = {"role": "judge", "judge_id": judge_id}
    resp = ctx.request.post(BASE + "/api/login", data=json.dumps(body),
                            headers={"Content-Type": "application/json"})
    assert resp.ok, f"login {role} 失败: {resp.status}"


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ============ 桌面管理员 1440×900 ============
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              locale="zh-CN")
    page = ctx.new_page()
    page.goto(BASE + "/login")
    settle(page)
    shot(page, "a1-login.png")
    api_login(ctx, "admin", ADMIN_PW)
    page.goto(BASE + "/events")
    settle(page)
    shot(page, "a2-events.png")
    page.goto(BASE + "/users")
    settle(page)
    shot(page, "u-users.png")
    page.goto(BASE + f"/events/{COMP}/import")
    settle(page)
    shot(page, "a3-import.png")
    page.goto(BASE + f"/events/{COMP}/schedule")
    settle(page)
    shot(page, "a4-schedule-tree.png")
    sched = ctx.request.get(BASE + f"/api/public/events/{COMP}/schedule").json()
    ceid_scoring = [e["id"] for e in sched["events"] if e["status"] == "scoring"][0]
    page.goto(BASE + f"/events/{COMP}/console/{ceid_scoring}")
    settle(page)
    shot(page, "a5-console.png")
    page.goto(BASE + f"/events/{COMP}/advancement")
    settle(page)
    shot(page, "a6-advancement.png")
    page.goto(BASE + f"/events/{COMP}/results")
    settle(page)
    shot(page, "a7-results-center.png")
    page.goto(BASE + f"/events/{COMP}/teams")
    settle(page)
    shot(page, "a10-teams.png")
    page.goto(BASE + f"/events/{COMP}/team-standings")
    settle(page)
    shot(page, "a11-team-standings.png")
    page.goto(BASE + f"/events/{COMP}/screen-control")
    settle(page)
    shot(page, "a12-screen-control.png")
    ctx.close()

    # ============ 裁判移动端 375×812 ============
    ctx = browser.new_context(viewport={"width": 375, "height": 812},
                              is_mobile=True, has_touch=True, locale="zh-CN")
    page = ctx.new_page()
    api_login(ctx, "judge", judge_id="J1")
    page.goto(BASE + "/login?role=judge&judge=J1")
    settle(page)
    shot(page, "j1-login-prefill.png")
    page.goto(BASE + "/judge")
    settle(page)
    shot(page, "j2-workbench.png")
    # 顺位法（S11R1：16 人 8/16 检录，含灰行边界）
    page.goto(BASE + "/judge/competition-events/621/dances/%E5%8D%8E%E5%B0%94%E5%85%B9")
    settle(page)
    shot(page, "j3-sheet-skating.png")
    # Mark 制（M1F）
    page.goto(BASE + "/judge/competition-events/590/dances/%E7%8E%B0%E4%BB%A3%E8%88%9E")
    settle(page)
    shot(page, "j4-mark-selected.png")
    # 评分制（F2）
    page.goto(BASE + "/judge/competition-events/594/dances/%E9%9B%86%E4%BD%93%E8%88%9E")
    settle(page)
    shot(page, "j5-sheet-score.png")
    ctx.close()

    # ============ 观众移动端 375×812 ============
    ctx = browser.new_context(viewport={"width": 375, "height": 812},
                              is_mobile=True, has_touch=True, locale="zh-CN")
    page = ctx.new_page()
    for path, name in (("/public/schedule", "p1-public-schedule.png"),
                       ("/public/results", "p2-public-results.png"),
                       ("/public/team-standings", "p3-public-standings.png")):
        page.goto(BASE + path)
        settle(page)
        shot(page, name)
    ctx.close()

    # ============ 大屏 1920×1080（四态强制） ============
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
                              locale="zh-CN")
    page = ctx.new_page()
    api_login(ctx, "admin", ADMIN_PW)
    page.goto(BASE + "/login")
    settle(page)
    for mode, name in (("results", "s-screen-results.png"),
                       ("standings", "s-screen-standings.png"),
                       ("scoring", "s-screen-scoring.png"),
                       ("welcome", "s-screen-welcome.png")):
        ctx.request.post(BASE + "/api/screen-control",
                         data=json.dumps({"mode": mode}),
                         headers={"Content-Type": "application/json"})
        page.goto(BASE + "/screen")
        settle(page, 1600)
        shot(page, name)
    ctx.request.post(BASE + "/api/screen-control",
                     data=json.dumps({"mode": "auto"}),
                     headers={"Content-Type": "application/json"})
    ctx.close()

print("\n完成：共 %d 张 → %s" % (len(results), OUT))
