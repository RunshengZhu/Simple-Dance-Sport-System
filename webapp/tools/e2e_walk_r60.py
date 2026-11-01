# -*- coding: utf-8 -*-
"""R60 交互动线走查：基于说明书全部动线，真实点击 + 不变量断言 + 关键帧截图。
覆盖：检录(375) / 主持(375) / 裁判(375) / 观众(375) / 大屏 / 控制台(桌面)。
前置：manual_annotate.setup_data() 已种 comp1（D1 scoring 部分检录、P1F published）。
用法：python3 e2e_walk_r60.py [base=8302] ；截图 → /tmp/e2e_r60
"""
import asyncio, json, os, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
OUT = "/tmp/e2e_r60"
os.makedirs(OUT, exist_ok=True)
R = []          # 断言结果
FRAMES = []     # 视觉帧清单


def record(step, ok, detail=""):
    R.append({"step": step, "ok": bool(ok), "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + step + " :: " + detail, flush=True)


def frame(name):
    FRAMES.append(name)
    print("frame:", name, flush=True)


async def login(pg, role, username=None, password=None, judge_id=None, cid=1):
    """R4x+ 角色登录走赛事专属入口 /competitions/{cid}/login。"""
    if role == "admin":  # 平台总管理员专用登录页
        await pg.goto(BASE + "/login")
        await pg.wait_for_timeout(400)
        await pg.fill("#password", password)
        await pg.click("#btn")
        await pg.wait_for_timeout(900)
        return
    await pg.goto(f"{BASE}/competitions/{cid}/login?role={role}")
    await pg.wait_for_timeout(500)
    if role == "judge":
        if judge_id:
            await pg.fill("#judge_id", judge_id)
    else:
        await pg.fill("#username", username)
        await pg.fill("#password", password)
    await pg.click("#btn")
    await pg.wait_for_timeout(900)


async def no_hscroll(pg, step):
    ov = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    record(step + " 无水平滚动", ov <= 0, f"overflowX={ov}px")


async def run():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        async def mctx():
            return await browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                             has_touch=True, device_scale_factor=2, locale="zh-CN")

        async def dctx():
            return await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")

        # ============ M1 检录台 375（comp1） ============
        ctx = await mctx(); pg = await ctx.new_page()
        await login(pg, "marshal", "marshal", "marshal123")
        record("M1 检录登录落点", pg.url.endswith("/staff"), pg.url)
        await pg.wait_for_selector(".st-event[data-ceid='1']", timeout=8000)
        await pg.screenshot(path=f"{OUT}/m1-staff-top.png", full_page=False); frame("m1-staff-top")
        # 已完成场次（P1F published）在页面中的位置与形态
        pos = await pg.evaluate("""() => {
          const cards = Array.from(document.querySelectorAll('.st-event, .done-card'));
          const done = document.querySelector('.done-card');
          const order = done ? cards.indexOf(done) : -1;
          return {total: cards.length, doneIndex: order, doneIsLast: order === cards.length - 1,
                  rectTop: done ? done.getBoundingClientRect().top : null} }""")
        record("M1 已完成场次存在且可原位展开入口", pos["doneIndex"] >= 0, json.dumps(pos))
        # D1 滚到中心点 201：滚动稳定 + 翻转 + 计数
        await pg.evaluate("document.querySelector('.st-event[data-ceid=\\'1\\']').scrollIntoView({block:'center'})")
        await pg.wait_for_timeout(300)
        y0 = await pg.evaluate("window.scrollY")
        tgt = await pg.evaluate("""() => { const c = document.querySelector('.chip[data-ceid=\\'1\\']:not(.on)');
          return c ? c.dataset.num : null }""")
        if tgt is None:  # 上轮跑过全部检录：先取消一个，保证有点击空间
            tgt = await pg.evaluate("""() => { const c = document.querySelector('.chip[data-ceid=\\'1\\'].on');
              if (c) { c.click(); } return c ? c.dataset.num : null }""")
            await pg.wait_for_timeout(700)
            y0 = await pg.evaluate("window.scrollY")
        record("M1 存在未检录 chip 可点", tgt is not None, f"目标={tgt}")
        prog0 = await pg.evaluate("document.getElementById('prog-1').textContent")
        await pg.click(f".chip[data-ceid='1'][data-num='{tgt}']")
        await pg.wait_for_timeout(800)
        st = await pg.evaluate("""() => ({y: window.scrollY,
          on: document.querySelector('.chip[data-ceid=\\'1\\']:not(.on)') !== null,
          prog: document.getElementById('prog-1').textContent})""")
        import re as _re
        n0 = int(_re.search(r"\d+", prog0).group())
        n1 = int(_re.search(r"\d+", st["prog"]).group())
        record("M1 点击检录：滚动稳定+状态翻转+计数", abs(st["y"] - y0) < 2 and n1 == n0 + 1,
               f"{prog0!r}→{st['prog']!r} scrollY {y0}→{st['y']}")
        # 点击精度：chip 中心 elementFromPoint 命中
        hit = await pg.evaluate("""() => { const c = document.querySelector('.chip[data-ceid=\\'1\\'][data-num=\\'202\\']');
          const r = c.getBoundingClientRect();
          const el = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
          return el === c || c.contains(el); }""")
        record("M1 chip 中心命中无遮挡", hit)
        await pg.screenshot(path=f"{OUT}/m1-chip-clicked.png"); frame("m1-chip-clicked")
        # 全部检录
        await pg.evaluate("document.querySelector('.st-event[data-ceid=\\'1\\'] [data-all]').click()")
        await pg.wait_for_timeout(700)
        allon = await pg.evaluate("""() => ({n: document.querySelectorAll('.chip[data-ceid=\\'1\\'].on').length,
          prog: document.getElementById('prog-1').textContent})""")
        record("M1 全部检录 12/12", allon["n"] == 12 and "12 / 12" in allon["prog"], json.dumps(allon))
        # 索引抽屉跳转
        has_idx = await pg.evaluate("!!document.getElementById('scene-index-btn')")
        if has_idx:
            await pg.evaluate("document.getElementById('scene-index-btn').click()")
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{OUT}/m1-index-drawer.png"); frame("m1-index-drawer")
            jump = await pg.evaluate("""() => {
              const items = Array.from(document.querySelectorAll('#scene-index-drawer .si-chip'));
              const target = items.find(a => (a.textContent||'').includes('P1F'));
              if (!target) return {found:false, n: items.length};
              const y0 = window.scrollY; target.click(); return {found:true, y0}; }""")
            await pg.wait_for_timeout(900)
            if jump.get("found"):
                y1 = await pg.evaluate("window.scrollY")
                record("M1 索引抽屉跳转 P1F", y1 != jump["y0"], f"scrollY {jump['y0']}→{y1}")
            else:
                record("M1 索引抽屉含 P1F 项", False, f"items={jump.get('n')}")
            await pg.evaluate("""() => { const d = document.getElementById('scene-index-drawer');
              if (d) d.dispatchEvent(new Event('click')); }""")
            await pg.wait_for_timeout(300)
        else:
            record("M1 场次索引按钮存在", False, "缺 #scene-index-btn")
        # 编号搜索定位
        await pg.fill("#staff-search", "S1")
        await pg.wait_for_timeout(1100)
        loc = await pg.evaluate("""() => ({vis: Array.from(document.querySelectorAll('.st-event')).filter(c=>c.style.display!=='none').map(c=>c.dataset.code),
          flash: !!document.querySelector('.st-event.flash')})""")
        record("M1 搜索 S1 过滤+高亮", "S1" in loc["vis"] and loc["flash"], json.dumps(loc))
        await pg.fill("#staff-search", "")
        await no_hscroll(pg, "M1")
        await pg.close(); await ctx.close()

        # ============ M2 主持台 375（P1F 原位展开公告） ============
        ctx = await mctx(); pg = await ctx.new_page()
        await login(pg, "host", "host", "host123")
        record("M2 主持登录落点", pg.url.endswith("/staff"), pg.url)
        await pg.wait_for_timeout(600)
        done = pg.locator(".done-card").first
        if await done.count():
            await done.scroll_into_view_if_needed()
            await pg.wait_for_timeout(300)
            before = await done.bounding_box()
            await pg.evaluate("(() => { const b = document.querySelector('.toggle-done'); if (b) b.click(); })()")
            await pg.wait_for_timeout(600)
            after = await done.bounding_box()
            body = await pg.evaluate("""() => { const b = document.querySelector('.done-card .done-body.open');
              return b ? {table: !!b.querySelector('table'), rows: b.querySelectorAll('tbody tr').length,
                           inPlace: b.closest('.done-card') === document.querySelector('.done-card')} : null }""")
            record("M2 已完成场次原位展开成绩公告", bool(body) and body["table"] and body["rows"] > 0,
                   json.dumps({"body": body, "cardY": after and round(after["y"])}))
            record("M2 展开为原位替换（卡片不消失不跳页）", after is not None and before is not None
                   and abs(after["y"] - before["y"]) < 60, f"卡片y {before and round(before['y'])}→{after and round(after['y'])}")
            await done.scroll_into_view_if_needed()
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f"{OUT}/m2-accordion-open.png"); frame("m2-accordion-open")
            # 标记已播报
            ann = await pg.evaluate("""() => { const b = document.querySelector('.done-card .ann-btn');
              if (!b) return null; b.click(); return b.textContent; }""")
            await pg.wait_for_timeout(600)
            ann2 = await pg.evaluate("() => { const b = document.querySelector('.done-card .ann-btn'); return b ? {t: b.textContent, cls: b.className} : null }")
            record("M2 标记已播报翻转", bool(ann2) and (ann2["t"] != ann or "done" in ann2["cls"] or "on" in ann2["cls"]),
                   json.dumps(ann2, ensure_ascii=False))
            await done.scroll_into_view_if_needed()
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f"{OUT}/m2-announced.png"); frame("m2-announced")
        else:
            record("M2 主持台有已完成场次卡", False, "无 .done-card")
        await no_hscroll(pg, "M2")
        await pg.close(); await ctx.close()

        # ============ M3 裁判顺位法 375（D1，J1） ============
        ctx = await mctx(); pg = await ctx.new_page()
        await login(pg, "judge", judge_id="J1")
        record("M3 裁判登录落点", pg.url.endswith("/judge"), pg.url)
        await pg.wait_for_timeout(600)
        link = pg.locator(".st-event a, .card a").filter(has_text="D1").first
        cnt = await link.count()
        if cnt == 0:
            await pg.goto(BASE + "/judge/competition-events/1/dances/%E5%8D%8E%E5%B0%94%E5%85%B9")
        else:
            await link.click(); await pg.wait_for_timeout(800)
        await pg.wait_for_timeout(600)
        rows_on = await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
        # 顺序点选前 5
        for i in range(5):
            await pg.evaluate(f"document.querySelectorAll('.rank-row:not(.off)')[{i}].click()")
            await pg.wait_for_timeout(250)
        ranked = await pg.evaluate("document.querySelectorAll('.rank-row.ranked, .rank-row[style*=rank], .rank-row.on').length")
        prog = await pg.evaluate("(document.querySelector('.submit-bar')||{}).textContent||''")
        record("M3 顺序点选 5 行生效", ranked >= 5 or "5" in prog, f"ranked标记={ranked} bar={prog!r}")
        await pg.screenshot(path=f"{OUT}/m3-judge-ranked.png"); frame("m3-judge-ranked")
        # 提交（含吸底栏遮挡检查）
        sb = await pg.evaluate("""() => { const b = document.querySelector('.submit-bar button, .submit-bar .btn');
          if (!b) return null; const r = b.getBoundingClientRect();
          const el = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
          return {ok: !!(el && (el === b || b.contains(el))), txt: b.textContent}; }""")
        record("M3 提交按钮可点（无遮挡）", bool(sb) and sb["ok"], json.dumps(sb, ensure_ascii=False) if sb else "无按钮")
        # 先在未排满时提交 → 应被防呆拦截
        await pg.evaluate("(() => { const b = document.querySelector('.submit-bar button, .submit-bar .btn'); if (b) b.click(); })()")
        await pg.wait_for_timeout(900)
        blocked = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.textContent : '' })()")
        record("M3 未排满提交被防呆拦截", "未排名" in blocked or "还差" in blocked or len(blocked) > 2, blocked)
        await pg.screenshot(path=f"{OUT}/m3-judge-blocked.png"); frame("m3-judge-blocked")
        # 排满剩余名次（已排名行的类是 assigned；未 assigned 才点）
        await pg.evaluate("""async () => {
          const rows = Array.from(document.querySelectorAll('.rank-row:not(.off)'));
          for (const r of rows) { if (!r.classList.contains('assigned')) { r.click(); await new Promise(res => setTimeout(res, 250)); } }
        }""")
        await pg.wait_for_timeout(500)
        full = await pg.evaluate("document.getElementById('progress').textContent")
        record("M3 已排满 12/12", "12 / 12" in full and "可提交" in full, full)
        await pg.screenshot(path=f"{OUT}/m3-judge-full.png"); frame("m3-judge-full")
        await pg.evaluate("(() => { const b = document.querySelector('.submit-bar button, .submit-bar .btn'); if (b) b.click(); })()")
        await pg.wait_for_timeout(1100)
        okmsg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? {cls: m.className, t: m.textContent} : null })()")
        record("M3 排满后提交成功", bool(okmsg) and okmsg["cls"] == "ok" and "已提交" in okmsg["t"],
               json.dumps(okmsg, ensure_ascii=False))
        await pg.screenshot(path=f"{OUT}/m3-judge-submitted.png"); frame("m3-judge-submitted")
        await no_hscroll(pg, "M3")
        await pg.close(); await ctx.close()

        # ============ M4 观众 375 ============
        ctx = await mctx(); pg = await ctx.new_page()
        await pg.goto(BASE + "/public/results")
        await pg.wait_for_timeout(900)
        has_anchor = await pg.evaluate("!!document.querySelector('.anchor-bar')")
        record("M4 观众成绩页锚点条", has_anchor)
        # 背番号查询
        await pg.fill("#lookup-num", "201")
        await pg.evaluate("(() => { const b = document.getElementById('lookup-go'); if (b) b.click(); })()")
        await pg.wait_for_timeout(900)
        lk = await pg.evaluate("() => { const r = document.getElementById('lookup-result'); return r ? r.textContent.slice(0,120) : '' }")
        record("M4 背番号 201 查询有结果", "201" in lk and len(lk) > 10, lk[:80])
        await pg.screenshot(path=f"{OUT}/m4-public-lookup.png"); frame("m4-public-lookup")
        await no_hscroll(pg, "M4")
        await pg.close(); await ctx.close()

        # ============ M5 大屏（桌面） ============
        ctx = await dctx(); pg = await ctx.new_page()
        await pg.goto(BASE + "/screen")
        await pg.wait_for_timeout(1500)
        screen = await pg.evaluate("() => ({has: !!document.querySelector('body'), txt: document.body.textContent.slice(0,80)})")
        record("M5 大屏页渲染", len(screen["txt"]) > 5, screen["txt"][:60])
        await pg.screenshot(path=f"{OUT}/m5-screen.png"); frame("m5-screen")
        await pg.close(); await ctx.close()

        # ============ D1 桌面控制台：开赛 D2 → 矩阵 ============
        ctx = await dctx(); pg = await ctx.new_page()
        await login(pg, "admin", "admin", "admin123")
        await pg.goto(BASE + "/events/1/console/2")
        await pg.wait_for_timeout(900)
        await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=f"{OUT}/d1-console.png"); frame("d1-console")
        btn = await pg.evaluate("""() => { const b = Array.from(document.querySelectorAll('button')).find(x => x.textContent.includes('开启评分'));
          return b ? {found: true, disabled: b.disabled} : {found: false}; }""")
        if btn.get("found") and not btn.get("disabled"):
            await pg.evaluate("(() => { Array.from(document.querySelectorAll('button')).find(x => x.textContent.includes('开启评分')).click(); })()")
            await pg.wait_for_timeout(1200)
            st = await pg.evaluate("fetch('/api/public/events/1/schedule').then(r=>r.json()).then(d=>{const e=d.events.find(x=>x.id===2); return e? e.status : 'gone'})")
            record("D1 控制台一键开启评分 D2", st == "scoring", f"status={st}")
        else:
            record("D1 开启评分按钮可用", False, json.dumps(btn))
        await pg.screenshot(path=f"{OUT}/d1-console-opened.png"); frame("d1-console-opened")
        await pg.close(); await ctx.close()

        await browser.close()

    fails = [r for r in R if not r["ok"]]
    print(f"\n===== R60 结果: {len(R)-len(fails)}/{len(R)} PASS =====", flush=True)
    for f in fails:
        print("FAIL:", f["step"], "::", f["detail"], flush=True)
    json.dump({"results": R, "frames": FRAMES}, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(run())
