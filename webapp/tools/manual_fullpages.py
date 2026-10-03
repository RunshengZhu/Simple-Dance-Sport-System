#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手册全页截图（r50）：在演示环境上补齐全页上下文图，与 manual_annotate.py（聚焦标注图）配套。

前置：manual_annotate.py 已在同一环境跑过（演示赛 D1/S1/P1F/D2 就绪）。
本脚本追加：M1（Mark 制场次）→ D1 三裁判提交算分并发布（供晋级/结果/团体总分页有内容）
→ 逐页全页截图 → static/manual/r50/。幂等可重跑。
"""
import asyncio
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(HERE), "server", "static", "manual", "r50")
os.makedirs(OUT, exist_ok=True)

CK = {"admin": "", "marshal": "", "judge": ""}


def req(method, path, body=None, raw=None, sess="admin"):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Cookie", CK.get(sess, ""))
    data = None
    if raw is not None:
        data = raw if isinstance(raw, bytes) else raw.encode()
        r.add_header("Content-Type", "text/csv; charset=utf-8")
    elif body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, data=data, timeout=30) as resp:
            sc = resp.headers.get("Set-Cookie")
            if sc:
                CK[sess] = sc.split(";")[0]
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def must(*args):
    """must(code, payload?, what) —— 与 manual_annotate.py 同款，兼容 *req() 解包。"""
    code = args[0]
    what = args[-1] if len(args) > 1 else "setup"
    if code not in (200, 201):
        print(f"WARN {what}: {code}")


def prep_extra_data():
    """M1 Mark 制场次 + D1 三裁判算分并发布（幂等）。"""
    must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 登录")
    c, o = req("GET", "/api/events")
    evs = json.loads(o).get("events", [])
    cid = next(e["id"] for e in evs if e["name"] == "使用说明演示赛")
    # M1：Mark 制场次
    sched = ("场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n"
             "M1,M1预选赛,P1,1,华尔兹,MARK,0," + ",".join(f"20{i}" for i in range(1, 13)) + "\n")
    req("POST", f"/api/events/{cid}/imports/schedule", raw=sched)
    c, o = req("GET", f"/api/public/events/{cid}/schedule")
    ids = {e["code"]: e["id"] for e in json.loads(o).get("events", [])}
    must(*req("POST", "/api/login", {"role": "marshal", "username": "marshal", "password": "marshal123"},
              sess="marshal"), "marshal 登录")
    if "M1" in ids:
        req("POST", f"/api/competition-events/{ids['M1']}/open",
            {"roster": [f"20{i}" for i in range(1, 13)], "reset": False}, sess="admin")
        req("POST", f"/api/competition-events/{ids['M1']}/checkin",
            {"numbers": [f"20{i}" for i in range(1, 13)], "state": True}, sess="marshal")
    # D1：三位裁判提交名次（已检录 201~207）→ 自动算分 → 发布
    if "D1" in ids:
        orders = [
            {f"20{i}": r for r, i in enumerate(range(1, 8), 1)},
            {f"20{i}": r for r, i in enumerate(range(7, 0, -1), 1)},
            {f"20{i}": r for r, i in enumerate([3, 1, 2, 5, 4, 7, 6], 1)},
        ]
        dance = urllib.parse.quote("华尔兹")
        for j, vals in zip(("J1", "J2", "J3"), orders):
            must(*req("POST", "/api/login", {"role": "judge", "judge_id": j}, sess="judge"), f"{j} 登录")
            c, o = req("PUT", f"/api/judge/competition-events/{ids['D1']}/dances/{dance}/sheet",
                       {"values": vals}, sess="judge")
            if c not in (200, 201):
                print(f"  D1 {j} 提交: {c} {o[:100]}")
        req("POST", f"/api/competition-events/{ids['D1']}/publish", {}, sess="admin")
    # 晋级名额：P1 第 1 轮场次给 6 个晋级位（已开场场次不可经 API 编辑，直接写演示库）
    import sqlite3
    db_path = sys.argv[3] if len(sys.argv) > 3 else "/tmp/ds_manual_r50.db"
    try:
        dconn = sqlite3.connect(db_path, timeout=10)
        for code in ("D1", "M1"):
            if code in ids:
                dconn.execute("UPDATE events SET advancement_count=6 WHERE id=?", (ids[code],))
        dconn.commit()
        dconn.close()
    except Exception as e:
        print(f"  adv 直写跳过: {e}")
    # 名额变更后重算 D1，让结果带上晋级标记（晋级确认页才有预案内容）
    if "D1" in ids:
        req("POST", f"/api/competition-events/{ids['D1']}/calculate", {}, sess="admin")
    # 大屏锁定成绩公告画面
    req("POST", "/api/screen-control", {"mode": "results"}, sess="admin")
    print("全页数据就绪 cid=%s ids=%s" % (cid, ids))
    return cid, ids


# (文件名, 视口, url 模板, full_page)
SHOTS = [
    ("a4-schedule-tree", "desktop", "/events/{cid}/schedule", True),
    ("a5-console", "desktop", "/events/{cid}/console/{D1}", True),
    ("a6-advancement", "desktop", "/events/{cid}/advancement?project=P1&round=1", True),
    ("a7-results-center", "desktop", "/events/{cid}/results", True),
    ("a11-team-standings", "desktop", "/events/{cid}/team-standings", True),
    ("a12-screen-control", "desktop", "/events/{cid}/screen-control", True),
    ("u-users", "desktop", "/users", True),
    ("st-login-marshal", "mobile", "/login?role=marshal", True),
    ("j4-mark-selected", "mobile", "/judge/competition-events/{M1}/dances/%E5%8D%8E%E5%B0%94%E5%85%B9", True),
    ("p3-public-standings", "mobile", "/public/team-standings", True),
    ("s-screen-results", "bigscreen", "/screen", False),
]


async def run(cid, ids):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for name, vp, tpl, full in SHOTS:
            w, h = {"desktop": (1440, 900), "mobile": (375, 812), "bigscreen": (1920, 1080)}[vp]
            mobile = vp == "mobile"
            ctx = await browser.new_context(viewport={"width": w, "height": h},
                                            is_mobile=mobile, has_touch=mobile,
                                            device_scale_factor=2, locale="zh-CN")
            page = await ctx.new_page()
            url = tpl.replace("{cid}", str(cid))
            for k, v in ids.items():
                url = url.replace("{%s}" % k, str(v))
            await page.goto(BASE + url)
            await page.wait_for_timeout(700)
            # 登录态：按路径判定角色（url 为相对路径，公开页与大屏免登录）
            path = url
            if path.startswith(("/events", "/users")):
                role, body = "admin", {"role": "admin", "password": "admin123"}
            elif path.startswith("/judge"):
                role, body = "judge", {"role": "judge", "judge_id": "J1"}
            elif "role=marshal" in path:
                role, body = "marshal", {"role": "marshal", "username": "marshal", "password": "marshal123"}
            else:
                role, body = None, None
            if role:
                await page.evaluate("""async (b) => { await fetch('/api/login', {method:'POST',
                    headers:{'Content-Type':'application/json'}, body: JSON.stringify(b)}); }""", body)
                await page.goto(BASE + url)
                await page.wait_for_timeout(900)
            if name == "j4-mark-selected":
                # 勾前 8 名给 Mark，呈现「已选」状态
                await page.evaluate("""(() => {
                  const rows = document.querySelectorAll('.mark-row:not(.off), .rank-row:not(.off)');
                  for (let i = 0; i < Math.min(8, rows.length); i++) rows[i].click();
                })()""")
                await page.wait_for_timeout(500)
            path = os.path.join(OUT, name + ".png")
            await page.screenshot(path=path, full_page=full)
            print("shot:", name, os.path.getsize(path) // 1024, "KB")
            await ctx.close()
        await browser.close()


if __name__ == "__main__":
    cid, ids = prep_extra_data()
    asyncio.run(run(cid, ids))
