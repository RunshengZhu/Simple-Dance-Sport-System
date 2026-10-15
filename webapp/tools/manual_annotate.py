#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手册标注截图管线：真实页面 → 元素聚焦截图 → PIL 视觉标注 → static/manual/<版本>/。

自足式：脚本开头通过 API 准备演示数据（演示赛/选手/裁判/场次三状态 +
第二场未激活赛事 + 审计留痕样例 + 文件分层样例），
不依赖任何既有库状态；/tmp 会话库，可随时重建。

标注视觉语言：
  红色圆角框 = 圈住关键控件；红底白数字圆标 = 步骤编号；
  中文说明由手册 HTML 图注承担（避免 PIL 字体缺字问题）。
"""
import asyncio
import io
import json
import os
import sys
import urllib.request

MANUAL_VER = "r50"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
OUT = sys.argv[2] if len(sys.argv) > 2 else None
if OUT is None:
    HERE = os.path.dirname(os.path.abspath(__file__))
    OUT = os.path.join(os.path.dirname(HERE), "server", "static", "manual", MANUAL_VER)
os.makedirs(OUT, exist_ok=True)

# ---------------- 数据准备（API） ----------------
CK = {"admin": "", "marshal": ""}


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
    code = args[0]
    what = args[-1] if len(args) > 1 else "setup"
    if code not in (200, 201):
        print(f"WARN setup {what}: {code} {str(args[1])[:80] if len(args) > 2 else ''}")
    return code in (200, 201)


def setup_data():
    must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 登录")
    c, o = req("GET", "/api/events")
    demo = None
    try:
        evs = json.loads(o).get("events", [])
        demo = next((e["id"] for e in evs if e["name"] == "使用说明演示赛"), None)
    except Exception:
        pass
    if not demo:
        c, o = req("POST", "/api/events", {"name": "使用说明演示赛", "date": "2026-09-20", "location": "说明馆"})
        demo = json.loads(o).get("id")
    req("POST", f"/api/events/{demo}/activate", {})
    # 数据（幂等：INSERT OR REPLACE）
    req("POST", f"/api/events/{demo}/imports/competitors",
        raw="背番号,项目编号,姓名,学校/单位\n" +
            "".join(f"20{i},P1,演示选手{i:02d},演示大学\n" for i in range(1, 13)))
    req("POST", f"/api/events/{demo}/imports/judges", raw="裁判ID,姓名\nJ1,演示裁判1\nJ2,演示裁判2\nJ3,演示裁判3\n")
    sched = ("场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n"
             "D1,D1第1轮,P1,1,华尔兹,SKATING,0," + ",".join(f"20{i}" for i in range(1, 13)) + "\n"
             "D2,D2第1轮,P1,1,华尔兹,SKATING,0," + ",".join(f"20{i}" for i in range(1, 13)) + "\n"
             "S1,S1集体舞,P1,1,集体舞,SCORE,0,201,202,203,204,205,206\n"
             "P1F,P1决赛,P1,2,华尔兹,SKATING,0,201,202,203,204,205,206\n")
    req("POST", f"/api/events/{demo}/imports/schedule", raw=sched)
    ids = {}
    c, o = req("GET", f"/api/public/events/{demo}/schedule")
    for e in json.loads(o).get("events", []):
        ids[e["code"]] = e["id"]
    # D1：7/12 部分检录（绿灰混合演示）
    req("POST", "/api/login", {"role": "marshal", "username": "marshal", "password": "marshal123"}, sess="marshal")
    req("POST", f"/api/competition-events/{ids['D1']}/open",
        {"roster": [f"20{i}" for i in range(1, 13)], "reset": False}, sess="admin")
    req("POST", f"/api/competition-events/{ids['D1']}/checkin",
        {"numbers": [f"20{i}" for i in range(1, 8)], "state": True}, sess="marshal")
    # S1：评分制全检录（scoring）
    req("POST", f"/api/competition-events/{ids['S1']}/open",
        {"roster": ["201", "202", "203", "204", "205", "206"], "reset": False}, sess="admin")
    req("POST", f"/api/competition-events/{ids['S1']}/checkin",
        {"numbers": ["201", "202", "203", "204", "205", "206"], "state": True}, sess="marshal")
    # P1F：发布一场（评委提交→自动计算→发布）
    req("POST", f"/api/competition-events/{ids['P1F']}/open",
        {"roster": ["201", "202", "203", "204", "205", "206"], "reset": False}, sess="admin")
    req("POST", f"/api/competition-events/{ids['P1F']}/checkin",
        {"numbers": ["201", "202", "203", "204", "205", "206"], "state": True}, sess="marshal")
    from urllib.parse import quote
    for j in ("J1", "J2", "J3"):
        req("POST", "/api/login", {"role": "judge", "judge_id": j}, sess="judge")
        vals = {n: i + 1 for i, n in enumerate(("201", "202", "203", "204", "205", "206"))}  # 顺位法：名次 1~6
        req("PUT", f"/api/judge/competition-events/{ids['P1F']}/dances/{quote('华尔兹')}/sheet",
            {"values": vals}, sess="judge")
    req("POST", f"/api/competition-events/{ids['P1F']}/publish", {}, sess="admin")
    # R50 手册 v4：第二场赛事（未激活）→ 赛事管理页多赛事列表演示
    c, o = req("GET", "/api/events")
    try:
        comps = json.loads(o).get("events", [])
        if not any(e["name"] == "春季邀请赛（示例）" for e in comps):
            req("POST", "/api/events", {"name": "春季邀请赛（示例）", "date": "2026-11-08", "location": "示例体育馆"})
    except Exception:
        pass
    # R50：审计留痕样例（撤销检录→补回 / 建号+重置口令 / 退回评分）
    req("POST", f"/api/competition-events/{ids['D1']}/checkin",
        {"numbers": ["205"], "state": False}, sess="marshal")
    req("POST", f"/api/competition-events/{ids['D1']}/checkin",
        {"numbers": ["205"], "state": True}, sess="marshal")
    c, o = req("POST", "/api/users", {"username": "marshal-li", "display_name": "检录员-李老师",
                                      "role": "marshal", "password": "demo123456"})
    if c in (200, 201):
        c, o = req("GET", "/api/users")
        try:
            uid = next(u["id"] for u in json.loads(o).get("users", []) if u["username"] == "marshal-li")
            req("POST", f"/api/users/{uid}/password", {"password": "demo654321"})
        except Exception:
            pass
    req("POST", f"/api/competition-events/{ids['S1']}/return-scores", {})
    # R50：文件分层演示（public 层 + 样例文件 + 下载计数）
    req("POST", "/api/files/tiers", {"name": "manual-demo", "perm": "public", "note": "手册演示层"})
    req("PUT", "/api/files/manual-demo/scoresheet-sample.txt",
        raw="成绩册样例：D1 第1轮 成绩公告\n", sess="admin")
    print("演示数据就绪 cid=%s ids=%s" % (demo, ids))
    return demo, ids


# ---------------- 场景表 ----------------
# focus: [(编号, css/JS 选择器, 标注文字)]；clip: auto（focus 并集外扩）
SCENES = [
    dict(name="a-login", vp="desktop", url="/login", role=None,
         focus=[("#role", "1 角色选「管理员」"), ("#password", "2 输入管理员口令"), ("#btn", "3 点「登录」进入系统")]),
    dict(name="a-events", vp="desktop", url="/events", role="admin",
         focus=[("js:document.querySelector('.card .row')", "1 填赛事名称点「创建」"),
                ("#tbl", "2 每场赛事独立进入 导入 / 赛程 / 结果"),
                ("js:Array.from(document.querySelectorAll('button')).find(b=>b.classList.contains('act-btn'))",
                 "3 未激活的赛事可随时「激活」")]),
    dict(name="a-users-audit", vp="desktop", url="/users", role="admin", pre_open_audit=True,
         focus=[("js:document.querySelector('#audit-box summary')", "1 「审计日志」默认收起，点开即看"),
                ("#audit-rows", "2 退回评分/撤销检录/口令/停启用/删除 全部署名留痕")]),
    dict(name="a-files", vp="desktop", url="/files", role="admin",
         focus=[("js:document.querySelector('.lookup-row')", "1 新建分层：public 公开 / token 凭证 / admin 管理"),
                ("js:document.querySelector('.copy-link')", "2 「复制链接」得到可直接分发的下载地址"),
                ("js:document.querySelector('.up-file')", "3 选文件上传（同名覆盖，下载次数累计）")]),
    dict(name="a-import", vp="desktop", url=None, role="admin", url_js="/events/{cid}/import",
         focus=[("a[href*='/api/templates/competitors']", "1 每类数据都有模板下载"), ("#f-competitors", "2 按模板填好后上传"),
                ("a[href*='/api/templates/schedule']", "3 赛程模板含全部列")],
         notes_line="导错可重传，逐行提示问题"),
    dict(name="a-console-open", vp="desktop", url_js="/events/{cid}/console/{D2}", role="admin",
         focus=[("js:document.querySelector('.roster-tools')", "1 全选/反选上场选手"),
                ("#cand-count", "2 勾选数实时显示"),
                ("js:Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('开启评分'))", "3 「开启评分」裁判即可打分")],
         pre_open_details=True),
    dict(name="a-results-publish", vp="desktop", url_js="/events/{cid}/results", role="admin",
         focus=[("js:Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('撤回发布'))",
                 "1 发布后可随时「撤回」重发"),
                ("js:Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('原始打分'))",
                 "2 可查看原始打分与判定表")]),
    dict(name="m-checkin-chips", vp="mobile", url="/staff", role="marshal",
         scroll_to='.st-event[data-code="D1"]',
         focus=[("js:document.querySelector('.st-event[data-code=\"D1\"]').querySelector('.chip-row')",
                 "1 点背号变绿=到场，再点取消"),
                ("js:Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='全部检录')",
                 "2 「全部检录」一键全到"),
                ("js:document.querySelector('.st-event[data-code=\"D1\"]').querySelector('.tag[id*=prog]')",
                 "3 「检录 N / M」实时更新")]),
    dict(name="m-checkin-locate", vp="mobile", url="/staff", role="marshal",
         focus=[(".status-filter", "1 按状态筛选场次"), ("#staff-search", "2 输入场次编号回车定位")]),
    dict(name="m-index", vp="mobile", url="/staff", role="marshal",
         focus=[("#staff-search", "1 场次很多时先按编号搜索"),
                ("#scene-index-btn", "2 或点「场次索引」按分组浏览")]),
    dict(name="m-index-drawer", vp="mobile", url="/staff", role="marshal", pre_click_index=True,
         focus=[("js:document.getElementById('scene-index-drawer')", "3 按「待检录 / 已完成」分组，点场次名即跳转")]),
    dict(name="m-accordion", vp="mobile", url="/staff", role="marshal", pre_click_accordion=True,
         scroll_to='.done-card', scroll_block='start',
         focus=[("js:document.querySelector('.toggle-done')", "1 「查看成绩」原位展开"),
                ("js:document.querySelector('.done-card .done-body.open table')", "2 公告表可宣读"),
                ("js:document.querySelector('.done-card .done-body.open a[href*=exports]')", "3 需要纸质稿点下载"),
                ("js:document.querySelector('.done-card .ann-btn')", "4 宣读完打播报标记")]),
    dict(name="j-login", vp="mobile", url="/login?role=judge&judge=J1", role=None,
         focus=[("#judge_id", "1 裁判 ID 已预填"), ("#btn", "2 直接登录（免口令）")]),
    dict(name="j-workbench", vp="mobile", url="/judge", role="judge", role_kw={"judge_id": "J1"},
         focus=[("js:document.querySelector('.tag.acc')", "1 页首实时「待评 N / M」计数"),
                ("js:document.querySelector('.st-event') || document.querySelector('.card')",
                 "2 点场次卡上的舞种进入评分")]),
    dict(name="j-skating", vp="mobile", url_js="/judge/competition-events/{D1}/dances/%E5%8D%8E%E5%B0%94%E5%85%B9",
         role="judge", role_kw={"judge_id": "J1"},
         focus=[(".mode-toggle", "1 两种模式随时切换"),
                ("js:document.querySelectorAll('.rank-row:not(.off)')[0]", "2 按名次依次点选手行"),
                (".submit-bar", "3 排完点提交")]),
    dict(name="j-score", vp="mobile", url_js="/judge/competition-events/{S1}/dances/%E9%9B%86%E4%BD%93%E8%88%9E",
         role="judge", role_kw={"judge_id": "J2"},
         focus=[("js:document.querySelectorAll('.score-row')[0]", "1 点输入框给 0~10 分"),
                (".submit-bar", "2 实时进度 · 收齐自动算名次")]),
    dict(name="p-results", vp="mobile", url="/public/results", role=None,
         focus=[(".anchor-bar", "1 锚点条快速跳到场次"),
                (".lookup-row", "2 输入背番号查选手"),
                ("js:document.querySelectorAll('.card h2').length>1 ? document.querySelectorAll('.card')[2] : document.querySelectorAll('.card')[1]",
                 "3 已发布成绩含选手名")]),
    dict(name="a-create-form", vp="desktop", url="/events", role="admin",
         pre_js="(function () {document.getElementById('name').value = '2026北京新生赛';document.getElementById('date').value = '2026-11-15';document.getElementById('location').value = '北京交通大学体育馆';var d = document.querySelector('details.wiz-admin'); if (d) d.open = true;document.getElementById('ca-username').value = 'bjtu-organizer';document.getElementById('ca-password').value = '********';})()",
         focus=[("#name", "1 填赛事名称 / 日期 / 地点"),
                ("#ca-username", "2 展开并填赛事管理员账号、口令"),
                ("#create-btn", "3 创建：自动激活并发账号")]),
    dict(name="a-create-done", vp="desktop", url="/events", role="admin",
         pre_js="(function () {document.getElementById('name').value = '2026北京新生赛';document.getElementById('date').value = '2026-11-15';document.getElementById('location').value = '北京交通大学体育馆';var d = document.querySelector('details.wiz-admin'); if (d) d.open = true;document.getElementById('ca-username').value = 'bjtu-organizer';document.getElementById('ca-password').value = '********';document.getElementById('create-btn').click();})()", pre_js_wait=1500,
         focus=[("#create-msg", "1 反馈：已激活、管理员账号就绪"),
                ("#tbl tr:nth-child(2)", "2 列表显示「激活中」")]),
    dict(name="a-users-create", vp="desktop", url="/users", role="admin",
         pre_js="(function () {document.getElementById('u-role').value = 'compadmin';document.getElementById('u-compid').value = '{cid}';document.getElementById('u-username').value = 'bjtu-organizer';document.getElementById('u-display').value = '北交大组织者';document.getElementById('u-password').value = '********';})()",
         focus=[("#u-role", "1 角色选「赛事管理员」"),
                ("#u-compid", "2 绑定赛事 ID（列表第一列）"),
                ("#u-username", "3 填账号、显示名、口令"),
                ("button[onclick='createUser()']", "4 创建账号")]),
    dict(name="a-comp-login", vp="desktop", url_js="/competitions/{cid}/login", role=None,
         focus=[("#role", "1 按角色登录（裁判/检录/主持/赛事管理员）"),
                ("#username", "2 账号口令（裁判免口令）"),
                ("#btn", "3 登录本赛事")]),
    dict(name="p-lookup", vp="mobile", url="/public/results", role=None, pre_lookup="201",
         focus=[("#lookup-num", "1 输入背番号回车"), ("#lookup-result", "2 显示单位与全部成绩")]),
]

# ---------------- 标注绘制（Pillow） ----------------
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ACCENT = (225, 29, 29)


def _font(size):
    """已验证：Hiragino Sans GB.ttc 的 index 0 含完整简体中文字形
    （PingFang.ttc 的 truetype 直开失败勿用）。"""
    return ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", size)


def annotate(img, boxes, dpr):
    """在截图上叠加红框 + 编号圆标（数字），中文说明由手册 HTML 图注承担。"""
    d = ImageDraw.Draw(img)
    for i, (x, y, w, h) in enumerate(boxes, 1):
        x2, y2, w2, h2 = int(x * dpr), int(y * dpr), int(w * dpr), int(h * dpr)
        d.rounded_rectangle([x2 - 4, y2 - 4, x2 + w2 + 4, y2 + h2 + 4], radius=10,
                            outline=ACCENT, width=5)
        r = 19
        cx, cy = x2 - 2, y2 - 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT, outline="white", width=3)
        d.text((cx, cy), str(i), font=_font(26), fill="white", anchor="mm")
    return img


# ---------------- 执行 ----------------
async def run():
    demo, ids = setup_data()
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        async def shoot(scene):
            name = scene["name"]
            w, h = (1440, 900) if scene["vp"] == "desktop" else (375, 812)
            mobile = scene["vp"] == "mobile"
            ctx = await browser.new_context(viewport={"width": w, "height": h},
                                            is_mobile=mobile, has_touch=mobile,
                                            device_scale_factor=2, locale="zh-CN")
            page = await ctx.new_page()
            url = scene.get("url")
            if not url:
                url = scene.get("url_js", "").replace("{cid}", str(demo))
                for k, v in ids.items():
                    url = url.replace("{%s}" % k, str(v))
            await page.goto(BASE + url)
            await page.wait_for_timeout(700)
            if scene.get("role"):
                kw = scene.get("role_kw") or {}
                body = {"role": scene["role"]}
                body.update(kw)
                import os as _os
                if scene["role"] == "admin":
                    body.setdefault("password", _os.environ.get("DSPORT_ADMIN_PASSWORD", "admin123"))
                elif scene["role"] == "marshal":
                    body.setdefault("password", _os.environ.get("DSPORT_MARSHAL_PASSWORD", "marshal123"))
                elif scene["role"] == "host":
                    body.setdefault("password", _os.environ.get("DSPORT_HOST_PASSWORD", "host123"))
                await page.evaluate("""async (b) => { await fetch('/api/login', {method:'POST',
                    headers:{'Content-Type':'application/json'}, body: JSON.stringify(b)}); }""", body)
                await page.goto(BASE + url)
                await page.wait_for_timeout(700)
            if scene.get("pre_js"):
                js = scene["pre_js"].replace("{cid}", str(demo))
                await page.evaluate(js)
                await page.wait_for_timeout(int(scene.get("pre_js_wait", 900)))
            if scene.get("pre_open_details"):
                await page.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
            if scene.get("pre_click_accordion"):
                await page.evaluate("(() => { const b = document.querySelector('.toggle-done'); if (b) b.click(); })()")
                await page.wait_for_timeout(450)   # 等展开动画结束，否则 scrollIntoView 按旧布局滚动
            if scene.get("pre_lookup"):
                v = scene["pre_lookup"]
                await page.fill("#lookup-num", v)
                await page.evaluate("(() => { const b = document.getElementById('lookup-go'); if (b) b.click(); })()")
            if scene.get("pre_open_audit"):
                await page.evaluate("(() => { const d = document.getElementById('audit-box'); if (d) d.open = true; })()")
                await page.wait_for_timeout(400)
            if scene.get("pre_click_index"):
                await page.evaluate("(() => { const b = document.getElementById('scene-index-btn'); if (b && !b.disabled) b.click(); })()")
                await page.wait_for_timeout(400)
            if scene.get("scroll_to"):
                sel = scene["scroll_to"].replace("'", '\\"')
                blk = scene.get("scroll_block", "center")
                await page.evaluate(f"(() => {{ const el = document.querySelector('{sel}'); "
                                    f"if (el) el.scrollIntoView({{block:'{blk}', behavior:'instant'}}); }})()")
            await page.wait_for_timeout(400)
            # focus 元素 boundingBox
            boxes, defs = [], []
            for num, (sel, txt) in enumerate(scene["focus"], 1):
                if sel.startswith("js:"):
                    expr = sel[3:]
                    box = await page.evaluate(f"""(() => {{
                      const el = ({expr});
                      if (!el) return null;
                      const r = el.getBoundingClientRect();
                      return {{x: r.x, y: r.y, width: r.width, height: r.height}};
                    }})()""")
                else:
                    loc = page.locator(sel).first
                    try:
                        box = await loc.bounding_box()
                    except Exception:
                        box = None
                if box and box.get("width", 0) > 2 and box.get("height", 0) > 2:
                    boxes.append((box["x"], box["y"], box["width"], box["height"]))
                    defs.append((len(boxes), txt))
                else:
                    print(f"  no-box {name} #{len(boxes)+1}: {sel[:60]} -> {box}")
            if not boxes:
                print(f"SKIP {name}: no focus boxes")
                await ctx.close()
                return
            # clip = 并集外扩
            xs = [b[0] for b in boxes]
            ys = [b[1] for b in boxes]
            xe = [b[0] + b[2] for b in boxes]
            ye = [b[1] + b[3] for b in boxes]
            m = 24
            cx = max(0, min(xs) - m)
            cy = max(0, min(ys) - m)
            cw = min(w, max(xe) + m) - cx
            ch = min(h, max(ye) + m) - cy
            if cx + cw > w:
                cw = w - cx
            if cy + ch > h:
                ch = h - cy
            shot = await page.screenshot(clip={"x": cx, "y": cy, "width": cw, "height": ch})
            img = Image.open(io.BytesIO(shot))
            rel = [(bx - cx, by - cy, bw, bh) for (bx, by, bw, bh) in boxes]
            out = annotate(img, rel, 2)
            out.save(os.path.join(OUT, name + ".png"))
            print("shot:", name, out.size)
            await ctx.close()

        for scene in SCENES:
            try:
                await shoot(scene)
            except Exception as e:
                print(f"FAIL {scene['name']}: {type(e).__name__} {str(e)[:120]}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
