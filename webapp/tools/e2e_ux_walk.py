# -*- coding: utf-8 -*-
"""R57 用户体验审计：从零走完 建赛→筹备→检录→裁判→控制/发布→晋级→播报→观众 全闭环。"""
import asyncio, json, os, time, urllib.request, urllib.parse
BASE = "https://dancetkt.com"
SHOTS = "/tmp/e2e_ux"
SUPER = "CE9DoLRhkb37R9w_bgrpDA55"
NOTES = []
T0 = time.time()

def note(msg):
    NOTES.append(msg); print("NOTE:", msg, flush=True)

def api(method, path, body=None, cookie=""):
    r = urllib.request.Request(BASE + path, method=method)
    if cookie: r.add_header("Cookie", cookie)
    if body is not None:
        r.data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            sc = resp.headers.get("Set-Cookie", "").split(";")[0]
            return resp.status, json.loads(resp.read() or b"{}"), sc
    except urllib.error.HTTPError as e:
        try: d = json.loads(e.read())
        except Exception: d = {}
        return e.code, d, ""

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        def ctx():
            return browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        async def shot(page, name):
            await page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)
            print("shot:", name, flush=True)

        # ============ A 总管理员：建赛 + 一步同建赛事管理员 ============
        ctxA = await ctx(); pg = await ctxA.new_page()
        c, d, ck = api("POST", "/api/login", {"role": "admin", "password": SUPER})
        await pg.goto(BASE + "/login"); await pg.wait_for_timeout(300)
        await pg.fill("#password", SUPER); await pg.click("#btn"); await pg.wait_for_timeout(1000)
        print("A 落点:", pg.url, flush=True)
        await pg.goto(BASE + "/events"); await pg.wait_for_timeout(600)
        await shot(pg, "A1_赛事管理页")
        t = time.time()
        await pg.fill("#name", "E2E流程验收赛")
        await pg.fill("#date", "2026-10-20")
        await pg.fill("#location", "验收馆")
        await pg.click("details.wiz-admin summary")
        CA_USER = "e2e-org-" + str(int(time.time()) % 100000)
        await pg.fill("#ca-username", CA_USER)
        await pg.fill("#ca-password", "E2eOrg2026")
        await pg.click("#create-btn"); await pg.wait_for_timeout(1500)
        msg = await pg.evaluate("document.getElementById('create-msg').textContent")
        note(f"[建赛] 表单反馈: {msg!r}；从填表到建赛+发管理员 {round(time.time()-t,1)}s；共 5 个输入项分散在 2 层")
        await shot(pg, "A2_建赛结果")
        _, d, _ = api("GET", "/api/events", cookie=ck)
        cid = next(e["id"] for e in d["events"] if e["name"] == "E2E流程验收赛")
        _, d, _ = api("GET", f"/api/public/events/{cid}/schedule")
        ids = {e["code"]: e["id"] for e in d["events"]}
        print("cid:", cid, "ids:", ids, flush=True)
        await ctxA.close()

        # ============ B 赛事管理员：专属登录 → 向导 ============
        ctxB = await ctx(); pg = await ctxB.new_page()
        t = time.time()
        await pg.goto(f"{BASE}/competitions/{cid}/login?role=admin"); await pg.wait_for_timeout(400)
        await shot(pg, "B1_赛事专属登录页")
        await pg.fill("#username", CA_USER); await pg.fill("#password", "E2eOrg2026")
        await pg.click("#btn")
        for _ in range(8):
            await pg.wait_for_timeout(1000)
            if "/login" not in pg.url: break
        print("B 登录落点:", pg.url, flush=True)
        await shot(pg, "B2_向导步骤1")
        comp = ["背番号,项目编号,姓名,学校/单位"]
        for i in range(1, 9): comp.append(f"10{i},P1,选手{i:02d},单位{'ABC'[(i-1)%3]}")
        for i in range(1, 9): comp.append(f"20{i},L1,舞者{i:02d},单位{'ABC'[(i-1)%3]}")
        open("/tmp/e2e_comp.csv", "w").write("\n".join(comp) + "\n")
        open("/tmp/e2e_judges.csv", "w").write("裁判ID,姓名\nJ1,裁判甲\nJ2,裁判乙\nJ3,裁判丙\n")
        sched = ["场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手",
                 "P1,标准舞预赛,P1,1,华尔兹,SKATING,3," + ",".join(f"10{i}" for i in range(1, 9)),
                 "P1F,标准舞决赛,P1,2,华尔兹,SKATING,0,",
                 "L1,恰恰预赛,L1,1,恰恰,MARK,4," + ",".join(f"20{i}" for i in range(1, 9))]
        open("/tmp/e2e_sched.csv", "w").write("\n".join(sched) + "\n")
        async def wiz_import(kind, path):
            await pg.click(f'[data-go="{ {"competitors":2,"judges":3,"schedule":4}[kind] }"]')
            await pg.wait_for_timeout(200)
            await pg.set_input_files(f'.wiz-file[data-kind="{kind}"]', path)
            await pg.click(f'.wiz-upload-btn[data-kind="{kind}"]')
            await pg.wait_for_timeout(1000)
            r = await pg.evaluate(f"document.querySelector('.wiz-result[data-kind=\\'{kind}\\']').textContent")
            note(f"[向导·{kind}] 反馈: {r!r}")
        await wiz_import("competitors", "/tmp/e2e_comp.csv")
        await shot(pg, "B3_向导选手步")
        await wiz_import("judges", "/tmp/e2e_judges.csv")
        await wiz_import("schedule", "/tmp/e2e_sched.csv")
        # 步骤5 工作人员
        await pg.click('[data-go="5"]'); await pg.wait_for_timeout(200)
        await pg.select_option("#s-role", "marshal")
        await pg.fill("#s-username", "e2e-checkin"); await pg.fill("#s-display", "验收检录员")
        await pg.fill("#s-password", "E2eCheck2026"); await pg.click("#s-create")
        await pg.wait_for_timeout(700)
        await pg.select_option("#s-role", "host")
        await pg.fill("#s-username", "e2e-host"); await pg.fill("#s-display", "验收主持人")
        await pg.fill("#s-password", "E2eHost2026"); await pg.click("#s-create")
        await pg.wait_for_timeout(700)
        await shot(pg, "B4_向导工作人员步")
        # 完成
        await pg.click('[data-go="6"]'); await pg.wait_for_timeout(500)
        await shot(pg, "B5_向导完成摘要")
        await pg.click("#wiz-finish"); await pg.wait_for_timeout(1000)
        print("B 完成落点:", pg.url, flush=True)
        note(f"[向导] 五步+2账号 总耗时 {round(time.time()-t,1)}s")
        # 赛程编排页（向导后的落点）截图
        await shot(pg, "B6_赛程编排页")
        # 控制台逐场「开启评分」（真实流程必需；向导未提示此步——UX 断点）
        _, d2, _ = api("GET", f"/api/public/events/{cid}/schedule")
        ids = {e["code"]: e["id"] for e in d2["events"]}
        for code in ("P1", "L1"):
            await pg.goto(f"{BASE}/events/{cid}/console/{ids[code]}")
            await pg.wait_for_timeout(1500)
            await pg.click('button:has-text("一键开启评分")')
            await pg.wait_for_timeout(1000)
        await shot(pg, "B7_两场次已开场")

        # ============ C 检录：部分检录 P1 6/8 ============
        ctxC = await ctx(); pg = await ctxC.new_page()
        await pg.goto(f"{BASE}/competitions/{cid}/login?role=marshal"); await pg.wait_for_timeout(300)
        await pg.fill("#username", "e2e-checkin"); await pg.fill("#password", "E2eCheck2026")
        await pg.click("#btn"); await pg.wait_for_timeout(2000)
        print("C 检录落点:", pg.url, flush=True)
        await shot(pg, "C1_检录台")
        chips = pg.locator('.st-event[data-code="P1"] .chip-row .chip')
        n = await chips.count()
        print("P1 芯片数:", n, flush=True)
        for i in range(min(6, n)):
            await chips.nth(i).click(); await pg.wait_for_timeout(150)
        await pg.wait_for_timeout(800)
        await shot(pg, "C2_P1检录6of8")
        # L1 全检录 8/8
        chips2 = pg.locator('.st-event[data-code="L1"] .chip-row .chip')
        n2 = await chips2.count()
        for i in range(n2):
            await chips2.nth(i).click(); await pg.wait_for_timeout(120)
        await pg.wait_for_timeout(600)
        await shot(pg, "C3_L1全检录")

        # ============ D 裁判 J1：Mark 制 + 顺位法 ============
        ctxD = await ctx(); pg = await ctxD.new_page()
        await pg.goto(f"{BASE}/login?role=judge&judge=J1"); await pg.wait_for_timeout(900)
        print("D 书签落点:", pg.url, flush=True)
        await pg.click("#btn"); await pg.wait_for_timeout(1500)
        print("D 裁判台:", pg.url, flush=True)
        await shot(pg, "D1_裁判工作台")
        # L1 Mark
        await pg.locator("a.btn", has_text="恰恰").first.click(); await pg.wait_for_timeout(1000)
        rows = pg.locator(".mark-row:not(.off)"); mn = await rows.count()
        print("L1 可评行:", mn, flush=True)
        for i in range(min(4, mn)):
            await rows.nth(i).click(); await pg.wait_for_timeout(150)
        await shot(pg, "D2_Mark制勾选")
        await pg.click("text=提交Mark 名单"); await pg.wait_for_timeout(1000)
        # P1 顺位法
        await pg.goto(BASE + "/judge"); await pg.wait_for_timeout(1000)
        await pg.locator("a.btn", has_text="华尔兹").first.click(); await pg.wait_for_timeout(1000)
        rrows = pg.locator(".rank-row:not(.off)"); rn = await rrows.count()
        print("P1 可评行:", rn, flush=True)
        for i in range(rn):
            await rrows.nth(i).click(); await pg.wait_for_timeout(180)
        await shot(pg, "D3_顺位法排完")
        await pg.click("text=提交名次表"); await pg.wait_for_timeout(1000)
        await shot(pg, "D4_提交后")
        # J2 J3 快速提交（API 代打，页面体验已由 J1 覆盖）
        for j in (2, 3):
            _, _, ckJ = api("POST", "/api/login", {"role": "judge", "judge_id": f"J{j}"})
            api("PUT", f"/api/judge/competition-events/{ids['P1']}/dances/{urllib.parse.quote('华尔兹')}/sheet",
                {"values": {f"10{i}": r for r, i in enumerate(
                    (list(range(6))[::-1] if j == 2 else [3, 0, 1, 5, 2, 4]), 1)}}, ckJ)
        # L1 也让 J2/J3 提交（每人勾前4）
        for j in (2, 3):
            _, _, ckJ = api("POST", "/api/login", {"role": "judge", "judge_id": f"J{j}"})
            api("PUT", f"/api/judge/competition-events/{ids['L1']}/dances/{urllib.parse.quote('恰恰')}/sheet",
                {"values": {f"20{i}": True for i in ([1,2,3,4] if j==2 else [5,6,7,8])}}, ckJ)

        # ============ E 赛事管理员：控制台 → 发布 → 晋级 → 决赛 ============
        pg = await ctxB.new_page()
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        _, dprop, _ = api("GET", "/api/projects/P1/rounds/1/advancement-proposal", cookie=ck)
        prop = [x["competitor_number"] for x in dprop["proposal"]][:3]
        await pg.goto(f"{BASE}/events/{cid}/console/{ids['P1']}"); await pg.wait_for_timeout(1500)
        await shot(pg, "E1_控制台矩阵")
        # 发布 P1（结果中心）
        await pg.goto(f"{BASE}/events/{cid}/results"); await pg.wait_for_timeout(1200)
        await shot(pg, "E2_结果中心")
        pub = pg.locator("button", has_text="发布").first
        await pub.click(); await pg.wait_for_timeout(1200)
        await shot(pg, "E3_P1已发布")
        # 晋级确认
        await pg.goto(f"{BASE}/events/{cid}/advancement?project=P1&round=1"); await pg.wait_for_timeout(1200)
        await shot(pg, "E4_晋级确认页")
        await pg.click("text=生成预案"); await pg.wait_for_timeout(1000)
        cbs = pg.locator(".card input[type=checkbox]"); cn = await cbs.count()
        print("预案复选框:", cn, flush=True)
        await shot(pg, "E5_晋级预案")
        await pg.click("text=确认并蛇形回填下一轮"); await pg.wait_for_timeout(1200)
        # 开启 P1F 决赛
        await pg.goto(f"{BASE}/events/{cid}/console/{ids['P1F']}"); await pg.wait_for_timeout(1200)
        await pg.click("text=开启评分"); await pg.wait_for_timeout(800)
        await shot(pg, "E6_P1F已开场")
        # P1F 检录 + 评分（检录员 + J1 页面）
        await pg.goto(f"{BASE}/staff"); await pg.wait_for_timeout(1500)
        chips3 = pg.locator('.st-event[data-code="P1F"] .chip-row .chip')
        n3 = await chips3.count()
        for i in range(n3):
            await chips3.nth(i).click(); await pg.wait_for_timeout(120)
        pgd = await ctxD.new_page()
        await pgd.goto(BASE + "/judge"); await pgd.wait_for_timeout(1000)
        await pgd.locator("a.btn", has_text="华尔兹").first.click(); await pgd.wait_for_timeout(1000)
        rr = pgd.locator(".rank-row:not(.off)"); rn2 = await rr.count()
        for i in range(rn2):
            await rr.nth(i).click(); await pgd.wait_for_timeout(150)
        await pgd.click("text=提交名次表"); await pgd.wait_for_timeout(1000)
        for j in (2, 3):
            _, _, ckJ = api("POST", "/api/login", {"role": "judge", "judge_id": f"J{j}"})
            api("PUT", f"/api/judge/competition-events/{ids['P1F']}/dances/{urllib.parse.quote('华尔兹')}/sheet",
                {"values": {p: r for r, p in enumerate(prop, 1)}}, ckJ)
        # P1F 发布
        await pg.goto(f"{BASE}/events/{cid}/results"); await pg.wait_for_timeout(1200)
        pub = pg.locator("button", has_text="发布").first
        await pub.click(); await pg.wait_for_timeout(500); await pub.click(); await pg.wait_for_timeout(1200)
        await shot(pg, "E7_P1F已发布")

        # ============ F 主持人播报 ============
        ctxF = await ctx(); pg = await ctxF.new_page()
        await pg.goto(f"{BASE}/competitions/{cid}/login?role=host"); await pg.wait_for_timeout(300)
        await pg.fill("#username", "e2e-host"); await pg.fill("#password", "E2eHost2026")
        await pg.click("#btn"); await pg.wait_for_timeout(2000)
        await shot(pg, "F1_主持台")
        ann = pg.locator(".ann-btn").first
        await ann.click(); await pg.wait_for_timeout(800)
        await shot(pg, "F2_已播报")

        # ============ G 观众视角 ============
        pg = await ctxF.new_page()
        await pg.goto(BASE + "/public/results"); await pg.wait_for_timeout(1500)
        await shot(pg, "G1_观众成绩页")
        await pg.goto(BASE + "/public/team-standings"); await pg.wait_for_timeout(1200)
        await shot(pg, "G2_观众团体总分")

        await browser.close()

asyncio.run(main())
print("\n=== NOTES ===")
for n in NOTES: print(n)
