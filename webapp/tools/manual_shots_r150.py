#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R150 手册/指南/引导页截图管线：真实页面 → 标注图（PIL 红框+编号）+ 引导页纯截图
→ server/static/manual/r150/。

自足式：脚本通过 API 造演示赛（三项目 × Mark 链/顺位/评分制、部分检录、晋级回填、
审计、证书、打印员账号），不依赖既有库状态。分两阶段拍摄：
  阶段1（晋级未确认）：晋级预案默认落点、检录/主持/裁判/公众、大屏、打印台
  阶段2（确认回填+复赛评分中）：执行总表（裁判栏/已回填标记/自动展开矩阵）、结果中心、Mark 提交引导
用法: python3 tools/manual_shots_r150.py [BASE]   # BASE 默认 http://127.0.0.1:8302
"""
import io
import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error

MANUAL_VER = "r150"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "server", "static", "manual", MANUAL_VER)
ONB = os.path.join(OUT, "onb")
os.makedirs(OUT, exist_ok=True)
os.makedirs(ONB, exist_ok=True)
DB = os.environ.get("MANUAL_DB", "")

CK = {}


def req(method, path, body=None, raw=None, sess="admin", expect=None):
    import urllib.parse
    if not urllib.parse.urlsplit(path).query and any(ord(ch) > 127 for ch in path):
        path = urllib.parse.quote(path)
    r = urllib.request.Request(BASE + path, method=method)
    if CK.get(sess):
        r.add_header("Cookie", CK[sess])
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
            payload, code = resp.read(), resp.status
    except urllib.error.HTTPError as e:
        payload, code = e.read(), e.code
    if expect and code != expect:
        raise AssertionError("%s %s → %s: %s" % (method, path, code, payload[:200]))
    return code, payload


def seed():
    """造演示赛数据（阶段1：晋级未确认，R2 无名单）。"""
    req("POST", "/api/login", {"role": "admin", "password": "admin123"}, expect=200)
    c, o = req("GET", "/api/events")
    demo = next((e["id"] for e in json.loads(o)["events"] if e["name"] == "使用说明演示赛"), None)
    if not demo:
        c, o = req("POST", "/api/events", {"name": "使用说明演示赛", "date": "2026-12-05", "location": "说明馆"})
        demo = json.loads(o)["id"]
    req("POST", "/api/events/%d/activate" % demo, {}, expect=200)

    rows = []
    for i in range(1, 13):
        rows.append("P1,摩登组华尔兹单项,%d,选手%d,新生,演示大学,舞伴%d,新生,演示大学" % (200 + i, 200 + i, 100 + i))
        rows.append("P2,拉丁组恰恰单项,%d,选手%d,新生,演示大学,舞伴%d,新生,演示大学" % (400 + i, 400 + i, 300 + i))
    for i in range(1, 7):
        rows.append("P3,师生同乐团体舞,%d,团结队%d,,,," % (300 + i, i))
    req("POST", "/api/events/%d/imports/competitors" % demo,
        raw="项目编号,项目名称,背番号,选手姓名,选手身份,选手单位,搭档姓名,搭档身份,搭档单位\n" + "\n".join(rows),
        expect=200)
    req("POST", "/api/events/%d/imports/judges" % demo,
        raw="姓名,单位\n演示裁判1\n演示裁判2\n演示裁判3\n", expect=200)
    sched = ("场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n"
             "M1,华尔兹预赛A,P1,1,华尔兹,MARK,4,\"201,202,203,204,205,206\"\n"
             "M2,华尔兹预赛B,P1,1,华尔兹,MARK,4,\"207,208,209,210,211,212\"\n"
             "R2,华尔兹复赛,P1,2,华尔兹,MARK,4,\"\"\n"
             "F1,华尔兹决赛,P1,3,华尔兹,SKATING,0,\"\"\n"
             "D1,恰恰初赛A,P2,1,恰恰,SKATING,0,\"401,402,403,404,405,406\"\n"
             "D2,恰恰初赛B,P2,1,恰恰,SKATING,0,\"407,408,409,410,411,412\"\n"
             "D3,恰恰初赛C,P2,1,恰恰,SKATING,0,\"401,402,403,404,405,406\"\n"
             "PF,恰恰决赛,P2,2,恰恰,SKATING,0,\"401,402,403,404,405,406\"\n"
             "S1,团体舞决赛,P3,1,现代舞,SCORE,0,\"301,302,303,304,305,306\"\n")
    req("POST", "/api/events/%d/imports/schedule" % demo, raw=sched, expect=200)
    ids = {e["code"]: e["id"] for e in
           json.loads(req("GET", "/api/public/events/%d/schedule" % demo)[1])["events"]}
    if DB:
        conn = sqlite3.connect(DB, timeout=15)
        conn.execute("UPDATE events SET judges_assigned='J1,J2,J3' WHERE competition_id=?", (demo,))
        conn.execute(
            "UPDATE events SET run_seq=(SELECT COUNT(*) FROM events e2 "
            "WHERE e2.competition_id=events.competition_id AND e2.id<=events.id) "
            "WHERE competition_id=? AND run_seq IS NULL", (demo,))
        conn.commit()
        conn.close()

    for j in ("J1", "J2", "J3"):
        req("POST", "/api/login", {"role": "judge", "judge_id": j}, sess=j, expect=200)
    skate = {"40%d" % i: str(i) for i in range(1, 7)}

    # D1：4/6 部分检录（评分中）
    req("POST", "/api/competition-events/%d/open" % ids["D1"], {"roster": list(skate)}, expect=200)
    req("POST", "/api/competition-events/%d/checkin" % ids["D1"],
        {"numbers": ["401", "402", "403", "404"], "state": True}, expect=200)
    # PF：决赛 → 三裁顺位 → 发布
    req("POST", "/api/competition-events/%d/open" % ids["PF"], {"roster": list(skate)}, expect=200)
    req("POST", "/api/competition-events/%d/checkin" % ids["PF"], {"numbers": list(skate), "state": True}, expect=200)
    for j in ("J1", "J2", "J3"):
        req("PUT", "/api/judge/competition-events/%d/dances/恰恰/sheet" % ids["PF"],
            {"values": skate}, sess=j, expect=200)
    req("POST", "/api/competition-events/%d/publish" % ids["PF"], {}, expect=200)
    # D3：同样跑完但「不发布」→ 已计算·未发布（结果中心/一键发布演示）
    req("POST", "/api/competition-events/%d/open" % ids["D3"], {"roster": list(skate)}, expect=200)
    req("POST", "/api/competition-events/%d/checkin" % ids["D3"], {"numbers": list(skate), "state": True}, expect=200)
    for j in ("J1", "J2", "J3"):
        req("PUT", "/api/judge/competition-events/%d/dances/恰恰/sheet" % ids["D3"],
            {"values": skate}, sess=j, expect=200)
    # S1：评分制全检录；J2 已交（评分页有值演示）
    req("POST", "/api/competition-events/%d/open" % ids["S1"], {"roster": ["30%d" % i for i in range(1, 7)]}, expect=200)
    req("POST", "/api/competition-events/%d/checkin" % ids["S1"],
        {"numbers": ["30%d" % i for i in range(1, 7)], "state": True}, expect=200)
    req("PUT", "/api/judge/competition-events/%d/dances/现代舞/sheet" % ids["S1"],
        {"values": {"301": "9.5", "302": "9.0", "303": "8.5", "304": "8.0", "305": "7.5", "306": "7.0"}},
        sess="J2", expect=200)
    # M1/M2：Mark 预赛 → 发布
    for code, marked, roster in (("M1", (201, 202, 203, 204), (201, 202, 203, 204, 205, 206)),
                                 ("M2", (207, 208, 209, 210), (207, 208, 209, 210, 211, 212))):
        ev = ids[code]
        req("POST", "/api/competition-events/%d/open" % ev, {"roster": [str(n) for n in roster]}, expect=200)
        req("POST", "/api/competition-events/%d/checkin" % ev,
            {"numbers": [str(n) for n in roster], "state": True}, expect=200)
        for j in ("J1", "J2", "J3"):
            req("PUT", "/api/judge/competition-events/%d/dances/华尔兹/sheet" % ev,
                {"values": {str(n): True for n in marked}}, sess=j, expect=200)
        req("POST", "/api/competition-events/%d/publish" % ev, {}, expect=200)
    # 审计留痕样例 + 账号 + 打印员 + 证书设计
    req("POST", "/api/competition-events/%d/checkin" % ids["D1"], {"numbers": ["405"], "state": False}, expect=200)
    req("POST", "/api/competition-events/%d/checkin" % ids["D1"], {"numbers": ["405"], "state": True}, expect=200)
    c, o = req("POST", "/api/users", {"username": "marshal-li", "display_name": "检录员-李老师",
                                      "role": "marshal", "password": "demo123456"})
    if c == 200:
        uid = next(u["id"] for u in json.loads(req("GET", "/api/users")[1])["users"]
                   if u["username"] == "marshal-li")
        req("POST", "/api/users/%d/password" % uid, {"password": "demo654321"}, expect=200)
    req("POST", "/api/users", {"username": "printer-demo", "display_name": "打印员-王老师",
                               "role": "printer", "password": "print123456"}, expect=200)
    req("POST", "/api/competition-events/%d/return-scores" % ids["PF"], {}, expect=200)
    for j in ("J1", "J2", "J3"):
        req("PUT", "/api/judge/competition-events/%d/dances/恰恰/sheet" % ids["PF"], {"values": skate}, sess=j, expect=200)
    req("POST", "/api/competition-events/%d/publish" % ids["PF"], {}, expect=200)
    req("POST", "/api/events/%d/certs/designs" % demo,
        {"id": 0, "name": "演示证书设计", "bg_type": "none",
         "fields": [
             {"type": "name", "x": 40, "y": 54, "w": 30, "size": 18, "align": "center", "bold": True, "text": ""},
             {"type": "rank_cn", "x": 40, "y": 64, "w": 30, "size": 16, "align": "center", "bold": False, "text": ""},
             {"type": "date", "x": 40, "y": 74, "w": 30, "size": 12, "align": "center", "bold": False, "text": ""}]},
        expect=200)
    c, o = req("GET", "/api/events")
    if not any(e["name"] == "春季邀请赛（示例）" for e in json.loads(o)["events"]):
        req("POST", "/api/events", {"name": "春季邀请赛（示例）", "date": "2026-12-20", "location": "示例体育馆"})
    print("阶段1数据就绪 cid=%s 场次=%s" % (demo, sorted(ids)))
    return demo, ids, skate


# ---------------- 标注绘制（Pillow） ----------------
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ACCENT = (225, 29, 29)


def _font(size):
    return ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", size)


def annotate(img, boxes, dpr):
    d = ImageDraw.Draw(img)
    for i, (x, y, w, h) in enumerate(boxes, 1):
        x2, y2, w2, h2 = int(x * dpr), int(y * dpr), int(w * dpr), int(h * dpr)
        d.rounded_rectangle([x2 - 4, y2 - 4, x2 + w2 + 4, y2 + h2 + 4], radius=10, outline=ACCENT, width=5)
        r = 19
        d.ellipse([x2 - 2 - r, y2 - 2 - r, x2 - 2 + r, y2 - 2 + r], fill=ACCENT, outline="white", width=3)
        d.text((x2 - 2, y2 - 2), str(i), font=_font(26), fill="white", anchor="mm")
    return img


# ---------------- 拍摄 ----------------
from playwright.sync_api import sync_playwright  # noqa: E402

COUNT = [0]


class Shooter:
    def __init__(self, browser):
        self.browser = browser

    def ctx(self, vp):
        mobile = vp == "mobile"
        c = self.browser.new_context(
            viewport={"width": (375 if mobile else 1440), "height": (812 if mobile else 900)},
            is_mobile=mobile, has_touch=mobile, device_scale_factor=2, locale="zh-CN")
        # 预关角色引导首访弹层（遮挡点击与画面）
        c.add_init_script("try{['judge','marshal','host','admin'].forEach(function(k){"
                          "localStorage.setItem('onb:'+k,'1')})}catch(e){};"
                          "window.__pageOwnSSE = true")   # 拍摄期间禁用基础页 SSE 自动重载，避免测量被打断
        return c

    def shoot(self, name, vp, url, role=None, pw=None, judge=None, comp=None,
              pre_js=None, pre_click=(), scroll_to=None, clip_sel=None, full=False,
              focus=(), wait=800, to_onb=False):
        ctx = self.ctx(vp)
        page = ctx.new_page()
        if role == "judge":
            r = ctx.request.post(BASE + "/api/login", data=json.dumps({"role": "judge", "judge_id": judge}),
                                 headers={"Content-Type": "application/json"})
            assert r.ok
        elif role == "printer":
            r = ctx.request.post(BASE + "/api/login",
                                 data=json.dumps({"role": "printer", "username": "printer-demo",
                                                  "password": pw, "competition_id": comp}),
                                 headers={"Content-Type": "application/json"})
            assert r.ok, "printer login"
        elif role:
            r = ctx.request.post(BASE + "/api/login", data=json.dumps({"role": role, "password": pw}),
                                 headers={"Content-Type": "application/json"})
            assert r.ok
        page.goto(BASE + url)
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        page.wait_for_timeout(wait)
        if pre_js:
            page.evaluate(pre_js)
            page.wait_for_timeout(600)
        for sel in pre_click:
            el = page.query_selector(sel)
            if el:
                el.click()
                page.wait_for_timeout(500)
            else:
                print("  no-preclick %s: %s" % (name, sel))
        if scroll_to:
            page.evaluate("""(sel) => { const el = document.querySelector(sel);
                if (el) el.scrollIntoView({block:'center', behavior:'instant'}); }""", scroll_to)
            page.wait_for_timeout(400)
        path = os.path.join(ONB if to_onb else OUT, name.split("/")[-1] + ".png")
        if focus:
            boxes = []
            for sel, _txt in focus:
                if sel.startswith("js:"):
                    box = page.evaluate("""(expr) => {
                      const el = eval(expr);
                      if (!el) return null;
                      const r = el.getBoundingClientRect();
                      return {x: r.x, y: r.y, width: r.width, height: r.height};
                    }""", sel[3:])
                else:
                    loc = page.locator(sel).first
                    try:
                        box = loc.bounding_box()
                    except Exception:
                        box = None
                if box and box.get("width", 0) > 2:
                    boxes.append((box["x"], box["y"], box["width"], box["height"]))
                else:
                    print("  no-box %s: %s" % (name, sel[:70]))
            if not boxes:
                print("SKIP %s" % name)
                ctx.close()
                return
            xs = [b[0] for b in boxes]; ys = [b[1] for b in boxes]
            xe = [b[0] + b[2] for b in boxes]; ye = [b[1] + b[3] for b in boxes]
            m = 24
            w = 375 if vp == "mobile" else 1440
            h = 812 if vp == "mobile" else 900
            cx = max(0, min(xs) - m); cy = max(0, min(ys) - m)
            cw = min(w, max(xe) + m) - cx; ch = min(h, max(ye) + m) - cy
            shot = page.screenshot(clip={"x": cx, "y": cy, "width": cw, "height": ch})
            img = Image.open(io.BytesIO(shot))
            rel = [(bx - cx, by - cy, bw, bh) for (bx, by, bw, bh) in boxes]
            annotate(img, rel, 2).save(path)
            print("shot:", name, "(annotated)")
        elif clip_sel:
            el = page.query_selector(clip_sel)
            if el:
                el.screenshot(path=path)
                print("shot:", name, "(clipped)")
            else:
                print("SKIP %s (no clip el)" % name)
                ctx.close()
                return
        else:
            if full:
                page.add_style_tag(content="header{position:static!important}")
            page.screenshot(path=path, full_page=full)
            print("shot:", name)
        COUNT[0] += 1
        ctx.close()


def main():
    demo, ids, skate = seed()
    code_r2 = [k for k in ids if k.startswith("R2")][0]
    r2 = ids[code_r2]

    with sync_playwright() as p:
        sh = Shooter(p.chromium.launch())
        D1_URL = "/judge/competition-events/%d/dances/恰恰" % ids["D1"]
        S1_URL = "/judge/competition-events/%d/dances/现代舞" % ids["S1"]

        # ================= 阶段 1：晋级未确认 =================
        # --- 管理员桌面 ---
        sh.shoot("a-comp-login", "desktop", "/competitions/%d/login?role=admin" % demo,
                 focus=[("#role", "r"), ("#username", "r"), ("#btn", "r")])
        sh.shoot("a-advancement", "desktop", "/events/%d/advancement" % demo, role="admin", pw="admin123", wait=1100,
                 focus=[("#proj", "r"),
                        ("js:document.querySelectorAll('.adv-check')[0].closest('.adv-next-tbl')", "r")])
        sh.shoot("a-runorder", "desktop", "/events/%d/schedule" % demo, role="admin", pw="admin123", wait=1100,
                 scroll_to="#run-order-card",
                 focus=[("#run-order-card h2", "r"), ("#ro-list", "r")])
        sh.shoot("a-print-desk", "desktop", "/print", role="printer", pw="print123456", comp=demo, wait=1100,
                 focus=[(".pt-actions", "r"), ("js:document.querySelectorAll('.pt-row')[0]", "r")])
        sh.shoot("s-screen-results", "desktop", "/screen?comp=%d" % demo,
                 pre_js="fetch('/api/screen-control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'results'})})",
                 wait=1800)
        ctx = sh.ctx("desktop")
        ctx.request.post(BASE + "/api/screen-control", data=json.dumps({"mode": "auto"}),
                         headers={"Content-Type": "application/json"})
        ctx.close()

        # --- 裁判移动端 ---
        sh.shoot("j-login", "mobile", "/login?role=judge&judge=J1",
                 focus=[("#judge-box", "r"), ("#btn", "r")])
        sh.shoot("j-workbench", "mobile", "/judge", role="judge", judge="J1", wait=1000,
                 focus=[("#jh-seg", "r"), ("js:document.querySelector('.judge-now')", "r"),
                        ("js:[...document.querySelectorAll('.jh-card')].find(c => c.offsetParent).querySelector('.quota-badge')", "r")])
        sh.shoot("j-skating", "mobile", D1_URL, role="judge", judge="J1", wait=1000,
                 focus=[("#skate-mode-bar", "r"), ("js:document.querySelectorAll('.rank-row')[0]", "r"),
                        (".submit-bar", "r")])
        sh.shoot("j-score", "mobile", S1_URL, role="judge", judge="J2", wait=1000,
                 focus=[("js:document.querySelectorAll('.score-row')[0]", "r"), (".submit-bar", "r")])
        # 评分页「? 规则」弹层
        ctx = sh.ctx("mobile")
        ctx.request.post(BASE + "/api/login", data=json.dumps({"role": "judge", "judge_id": "J1"}),
                         headers={"Content-Type": "application/json"})
        page = ctx.new_page(); page.goto(BASE + D1_URL); page.wait_for_timeout(900)
        page.click("#guide-btn"); page.wait_for_timeout(400)
        page.screenshot(path=os.path.join(OUT, "j-guide-pop.png")); print("shot: j-guide-pop")
        ctx.close()

        # --- 检录/主持移动端 ---
        sh.shoot("m-staff-landing", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000,
                 focus=[(".status-filter", "r"), ("#st-now", "r"),
                        ("js:[...document.querySelectorAll('.st-event')].find(c => c.offsetParent)", "r")])
        sh.shoot("m-checkin-chips", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000,
                 scroll_to=".st-event[data-code='D1']",
                 focus=[("js:document.querySelector('.st-event[data-code=\\'D1\\']').querySelector('.chip-row')", "r"),
                        ("js:Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='全部检录')", "r"),
                        ("js:document.querySelector('.st-event[data-code=\\'D1\\']').querySelector('[id^=prog-]')", "r")])
        sh.shoot("m-index-drawer", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000,
                 pre_click=("#scene-index-btn",),
                 focus=[("js:document.getElementById('scene-index-drawer')", "r")])
        sh.shoot("m-done-mark", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000,
                 pre_click=('.status-filter .sf-btn[data-f="done"]', ".done-card .toggle-done"),
                 focus=[("js:document.querySelector('.done-card')", "r"),
                        ("js:document.querySelector('.done-card th')", "r"),
                        ("js:document.querySelector('.done-card .ann-btn')", "r")])
        sh.shoot("host-open", "mobile", "/staff", role="host", pw="host123", wait=1000,
                 scroll_to="[data-open]",
                 focus=[("js:document.querySelector('[data-open]')", "r"),
                        ("js:document.querySelector('[data-open]').closest('.st-event').querySelector('.chip-row')", "r")])

        # --- 公众移动端 ---
        sh.shoot("p-home", "mobile", "/competitions/%d" % demo, wait=1000,
                 focus=[(".home-status", "r"), ("js:document.querySelector('.anchor-bar')", "r"),
                        ("js:document.querySelector('#lookup-input')", "r")])
        sh.shoot("p-results", "mobile", "/public/results?comp=%d" % demo, wait=1000,
                 focus=[("js:document.querySelector('.anchor-bar')", "r"),
                        ("js:document.querySelector('.card table')", "r")])

        # --- onb 幻灯（阶段1 部分，纯截图）---
        sh.shoot("dl-qr", "desktop", "/events/%d/direct-links" % demo, role="admin", pw="admin123",
                 pre_js="document.querySelector('.dl-row') && document.querySelector('.dl-row').click()",
                 clip_sel=".dl-qr-box", to_onb=True)
        sh.shoot("j-workbench", "mobile", "/judge", role="judge", judge="J1", wait=1000, to_onb=True)
        sh.shoot("j-skating", "mobile", D1_URL, role="judge", judge="J1", wait=1000, to_onb=True)
        sh.shoot("j-score", "mobile", S1_URL, role="judge", judge="J2", wait=1000, to_onb=True)
        sh.shoot("m-check", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000,
                 scroll_to=".st-event[data-code='D1']", to_onb=True)
        sh.shoot("m-chiprow", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000,
                 clip_sel=".st-event[data-code='D1'] .chip-row", to_onb=True)
        sh.shoot("m-filter", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000, to_onb=True)
        sh.shoot("m-done", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000,
                 pre_click=('.status-filter .sf-btn[data-f="done"]', ".done-card .toggle-done"), to_onb=True)
        sh.shoot("host-open", "mobile", "/staff", role="host", pw="host123", wait=1000,
                 scroll_to="[data-open]", to_onb=True)

        # --- 指南整页图 ---
        sh.shoot("staff-marshal-home", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000)
        sh.shoot("staff-host-home", "mobile", "/staff", role="host", pw="host123", wait=1000)
        sh.shoot("m-staff-done", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000,
                 pre_click=('.status-filter .sf-btn[data-f="done"]', ".done-card .toggle-done"), full=True)
        sh.shoot("j-workbench-now", "mobile", "/judge", role="judge", judge="J1", wait=1000)
        sh.shoot("j-mark-blank", "mobile", D1_URL, role="judge", judge="J3", wait=1000)

        # ================= 阶段 2：晋级确认回填 + 复赛评分中 =================
        req("POST", "/api/projects/P1/rounds/1/advancement-confirm",
            {"assign": {code_r2: ["201", "202", "203", "204", "207", "208", "209", "210"]},
             "append": True, "competition_id": demo}, expect=200)
        req("POST", "/api/competition-events/%d/open" % r2,
            {"roster": [str(n) for n in (201, 202, 203, 204, 207, 208, 209, 210)]}, expect=200)
        req("POST", "/api/competition-events/%d/checkin" % r2,
            {"numbers": [str(n) for n in (201, 202, 203, 204, 207, 208, 209, 210)], "state": True}, expect=200)
        req("PUT", "/api/judge/competition-events/%d/dances/华尔兹/sheet" % r2,
            {"values": {"201": True, "202": True, "207": True, "208": True}}, sess="J1", expect=200)
        R2_URL = "/judge/competition-events/%d/dances/华尔兹" % r2

        sh.shoot("a-runboard", "desktop", "/events/%d/runboard" % demo, role="admin", pw="admin123", wait=1100,
                 pre_click=("#judge-bar-toggle",),
                 focus=[("#judge-bar", "r"), ("js:document.querySelectorAll('.rb-row')[0]", "r"),
                        ("js:document.querySelector('.rb-row .rb-actions')", "r")])
        sh.shoot("a-results-center", "desktop", "/events/%d/results" % demo, role="admin", pw="admin123", wait=1100,
                 focus=[("#bulk-publish-btn", "r"),
                        ("js:document.querySelector('details.res-card[open]')", "r")])
        sh.shoot("a-results-publish", "desktop", "/events/%d/results" % demo, role="admin", pw="admin123", wait=1100,
                 focus=[("js:document.querySelector('details.res-card[open] p')", "r"),
                        ("js:document.querySelector('details.res-card[open] table')", "r")])
        sh.shoot("j-mark", "mobile", R2_URL, role="judge", judge="J1", wait=1000,
                 focus=[(".quota-badge", "r"), ("js:document.querySelectorAll('.mark-cell')[0]", "r"),
                        (".submit-bar", "r")])
        # j-mark-submitted：J2 现场提交 → 「本舞种已提交 ✓」+ 返回待评引导
        ctx = sh.ctx("mobile")
        ctx.request.post(BASE + "/api/login", data=json.dumps({"role": "judge", "judge_id": "J2"}),
                         headers={"Content-Type": "application/json"})
        page = ctx.new_page(); page.goto(BASE + R2_URL); page.wait_for_timeout(900)
        for num in ("203", "204", "209", "210"):
            b = page.query_selector('.mark-row[data-num="%s"]' % num)
            if b:
                b.click(); page.wait_for_timeout(120)
        page.click("#submit"); page.wait_for_timeout(900)
        page.screenshot(path=os.path.join(ONB, "j-mark-submitted.png")); print("shot: onb/j-mark-submitted")
        ctx.close()

        # onb rb-*（桌面）
        d2_ceid = ids["D2"]; pf_ceid = ids["PF"]
        sh.shoot("rb-open", "desktop", "/events/%d/runboard" % demo, role="admin", pw="admin123", wait=1100,
                 scroll_to=".rb-row[data-ceid='%d']" % d2_ceid, to_onb=True)
        sh.shoot("rb-checkin", "desktop", "/events/%d/runboard" % demo, role="admin", pw="admin123", wait=1100,
                 pre_click=(".rb-row[data-ceid='%d'] .rb-main" % d2_ceid,), to_onb=True)
        sh.shoot("rb-judgebar", "desktop", "/events/%d/runboard" % demo, role="admin", pw="admin123", wait=1100,
                 pre_click=("#judge-bar-toggle",), to_onb=True)
        sh.shoot("rb-scoring", "desktop", "/events/%d/runboard" % demo, role="admin", pw="admin123", wait=1100,
                 scroll_to=".rb-row.scoring-now", to_onb=True)
        sh.shoot("rb-published", "desktop", "/events/%d/runboard" % demo, role="admin", pw="admin123", wait=1100,
                 scroll_to=".rb-row[data-ceid='%d']" % pf_ceid, to_onb=True)
        sh.shoot("adv", "desktop", "/events/%d/advancement" % demo, role="admin", pw="admin123", wait=1100, to_onb=True)
        sh.shoot("a-runboard-full", "desktop", "/events/%d/runboard" % demo, role="admin", pw="admin123",
                 wait=1100, full=True)
        # staff-marshal-home 在阶段 2 重拍（有复赛评分中，画面更完整）
        sh.shoot("staff-marshal-home", "mobile", "/staff", role="marshal", pw="marshal123", wait=1000)

        sh.browser.close()
    print("\n完成：%d 张 → %s" % (COUNT[0], OUT))


if __name__ == "__main__":
    main()
