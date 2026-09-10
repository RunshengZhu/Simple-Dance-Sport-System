#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R39 压测数据全动线走查（配合 tools/build_stress_data.py 的 12 场次边界数据集）。

分区：S=检录台大规模索引 / J=裁判多舞种+缺席灰行 / P=观众平分公示+查询边界 / A=管理矩阵+大屏。
每步断言交互不变量并截图。用法：python3 tools/e2e_stress_walk.py [BASE]
前置：build_stress_data.py 已就绪（ceid: W1R1A=1 B=2 C=3 D=4 R2=5 F=6 L1A=7 B=8 LF=9 S1F=10 T1F=11 S2R1=12）。
"""
import asyncio
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ux-review-r39")
os.makedirs(OUT, exist_ok=True)
results = []


def record(step, ok, detail):
    results.append({"step": step, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + step + " :: " + str(detail)[:300])


async def api_login(page, session_cookie_box, role, **kw):
    """在页面上下文里登录并把 cookie 读出来（多会话隔离用独立 context）。"""
    body = {"role": role}
    body.update(kw)
    await page.goto(BASE + "/login")
    await page.wait_for_timeout(250)
    st = await page.evaluate("""async (b) => {
        const r = await fetch('/api/login', {method: 'POST',
          headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
        return r.status;
      }""", body)
    return st


async def run():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # ============ S 区：检录台大规模 ============
        ctx = await browser.new_context(viewport={"width": 375, "height": 812},
                                        is_mobile=True, device_scale_factor=2, has_touch=True)
        page = await ctx.new_page()
        await api_login(page, ctx, "marshal", username="marshal", password="marshal123")
        await page.goto(BASE + "/staff")
        await page.wait_for_timeout(900)
        n_cards = await page.evaluate("document.querySelectorAll('.st-event').length")
        hsw = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        record("S1 12 卡渲染无横滑", n_cards == 12 and hsw <= 0, f"cards={n_cards} hsw={hsw}")
        await page.screenshot(path=os.path.join(OUT, "s1-staff-top.png"))
        # S2 搜索定位
        await page.fill("#staff-search", "W1R1D")
        await page.wait_for_timeout(1100)
        loc = await page.evaluate("""() => ({
            vis: Array.from(document.querySelectorAll('.st-event')).filter(c => c.style.display !== 'none').map(c => c.dataset.code),
            flash: !!document.querySelector('.st-event.flash') })""")
        record("S2 搜索 W1R1D 定位高亮", loc["vis"] == ["W1R1D"] and loc["flash"], json.dumps(loc))
        await page.fill("#staff-search", "")
        await page.wait_for_timeout(300)
        # S3 检录点击滚动稳定（W1R1D 7/12 → 点 144 → 8/12）
        await page.evaluate("document.querySelector('.st-event[data-ceid=\\'4\\']').scrollIntoView({block:'center'})")
        y0 = await page.evaluate("window.scrollY")
        await page.click(".chip[data-ceid='4'][data-num='144']")
        await page.wait_for_timeout(800)
        st = await page.evaluate("""() => ({
            y: window.scrollY,
            on: document.querySelector('.chip[data-ceid=\\'4\\'][data-num=\\'144\\']').classList.contains('on'),
            prog: document.getElementById('prog-4').textContent })""")
        record("S3 检录点击稳定+计数 8/12", abs(st["y"] - y0) < 2 and st["on"] and st["prog"] == "检录 8 / 12",
               json.dumps(st))
        # S3b 撤销检录恢复 7/12
        await page.evaluate("document.querySelector('.chip[data-ceid=\\'4\\'][data-num=\\'144\\']').click()")
        await page.wait_for_timeout(700)
        st2 = await page.evaluate("document.getElementById('prog-4').textContent")
        record("S3b 撤销恢复 7/12", st2 == "检录 7 / 12", st2)
        # S4 待检录筛选（已计算场次检录锁定不再出现；评分中/未满检录/空名单 pending 均应出现）
        await page.evaluate("Array.from(document.querySelectorAll('.sf-btn')).find(b=>b.textContent==='待检录').click()")
        need = await page.evaluate("Array.from(document.querySelectorAll('.st-event')).filter(c=>c.style.display!=='none').map(c=>c.dataset.code)")
        record("S4 待检录筛选", set(need) == {"W1R1D", "W1R2", "W1F", "S2R1", "T1F"},
               json.dumps(need))
        # S5 已完成筛选 + 手风琴互斥
        await page.evaluate("Array.from(document.querySelectorAll('.sf-btn')).find(b=>b.textContent==='已完成').click()")
        done = await page.evaluate("Array.from(document.querySelectorAll('.st-event')).filter(c=>c.style.display!=='none').map(c=>c.dataset.code)")
        record("S5 已完成筛选", set(done) == {"W1R1A", "W1R1B", "W1R1C", "L1R1A", "L1R1B", "S1F"}, json.dumps(done))
        await page.evaluate("Array.from(document.querySelectorAll('.sf-btn')).find(b=>b.textContent==='全部').click()")
        await page.wait_for_timeout(200)
        await page.evaluate("""() => {
          const cards = Array.from(document.querySelectorAll('.done-card'));
          cards.find(c => c.dataset.code === 'W1R1A').querySelector('.toggle-done').click();
        }""")
        await page.wait_for_timeout(300)
        open1 = await page.evaluate("""() => {
          const open = Array.from(document.querySelectorAll('.done-card .done-body')).filter(b => !b.hidden);
          return open.map(b => b.closest('.done-card').dataset.code);
        }""")
        await page.evaluate("""() => {
          const cards = Array.from(document.querySelectorAll('.done-card'));
          cards.find(c => c.dataset.code === 'W1R1B').querySelector('.toggle-done').click();
        }""")
        await page.wait_for_timeout(300)
        open2 = await page.evaluate("""() => {
          const open = Array.from(document.querySelectorAll('.done-card .done-body')).filter(b => !b.hidden);
          return open.map(b => b.closest('.done-card').dataset.code);
        }""")
        record("S6 手风琴互斥", open1 == ["W1R1A"] and open2 == ["W1R1B"], f"open1={open1} open2={open2}")
        # S7 W1R1A 公告含并列信息与姓名
        await page.evaluate("""() => {
          const cards = Array.from(document.querySelectorAll('.done-card'));
          cards.find(c => c.dataset.code === 'W1R1A').querySelector('.toggle-done').click();
        }""")
        await page.wait_for_timeout(300)
        ann = await page.evaluate("""() => {
          const card = Array.from(document.querySelectorAll('.done-card')).find(c => c.dataset.code === 'W1R1A');
          return Array.from(card.querySelectorAll('table tr')).map(tr =>
            Array.from(tr.children).map(td => td.textContent.trim()));
        }""")
        record("S7 W1R1A 公告表渲染",
               len(ann) == 13 and ann[0][0] == "名次" and ann[1][0] == "1" and len(ann[1]) == 4,
               f"rows={len(ann)} head={ann[0]} first={ann[1]}")
        await page.screenshot(path=os.path.join(OUT, "s7-staff-accordion.png"))
        await page.close()
        await ctx.close()

        # ============ J 区：裁判多舞种 + 缺席灰行 ============
        ctx = await browser.new_context(viewport={"width": 375, "height": 812},
                                        is_mobile=True, device_scale_factor=2, has_touch=True)
        page = await ctx.new_page()
        await api_login(page, ctx, "judge", judge_id="J6")
        await page.goto(BASE + "/judge")
        await page.wait_for_timeout(800)
        bench = await page.evaluate("""() => ({
            cards: Array.from(document.querySelectorAll('.st-event, .card')).length,
            text: document.body.textContent.includes('W1R2') })""")
        record("J1 工作台渲染场次", bench["text"], json.dumps(bench))
        await page.screenshot(path=os.path.join(OUT, "j1-workbench.png"))
        # J2 W1R2 双舞种之华尔兹（J6 可能已有完整提交回显——两种前提都适配）
        await page.goto(BASE + "/judge/competition-events/5/dances/%E5%8D%8E%E5%B0%94%E5%85%B9")
        await page.wait_for_timeout(800)
        rows_on = await page.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
        placed0 = await page.evaluate("Array.from(document.querySelectorAll('.rank-row:not(.off) .rank-badge')).filter(b => b.textContent.trim()).length")
        record("J2 W1R2 华尔兹 12 行可用", rows_on == 12, f"rows={rows_on} placed0={placed0}")
        if placed0 == 0:
            # 空表：顺序点选 12 名
            await page.evaluate("""async () => {
              const rows = Array.from(document.querySelectorAll('.rank-row:not(.off)'));
              for (const r of rows) { r.click(); await new Promise(res => setTimeout(res, 60)); }
            }""")
            await page.wait_for_timeout(400)
        placed = await page.evaluate("Array.from(document.querySelectorAll('.rank-row:not(.off) .rank-badge')).filter(b => b.textContent.trim()).length")
        record("J2b 排位完整性", placed == 12, f"placed={placed}")
        # J2c 守卫：取消 1 人后提交必须被拦截（保护裁判误操作）
        await page.evaluate("document.querySelector('.rank-row:not(.off)').click()")
        await page.wait_for_timeout(250)
        await page.evaluate("window.__alive = 'w1r2'")
        await page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('提交'));
          if (b) b.click();
        }""")
        await page.wait_for_timeout(900)
        msg = await page.evaluate("""() => {
          const el = document.querySelector('.submit-bar .ok, .submit-bar .err, #submit-msg');
          return (el ? el.className + '|' + el.textContent : '(no msg)') + ' alive=' + (window.__alive || '(RELOADED)');
        }""")
        record("J2c 缺 1 人提交被守卫拦截且不重载",
               "err" in msg and "还有 1 名" in msg and "alive=w1r2" in msg, msg)
        # J2c2 恢复：把取消的人点回（追加到末位）→ 提交成功
        await page.evaluate("document.querySelector('.rank-row:not(.off)').click()")
        await page.wait_for_timeout(300)
        await page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('提交'));
          if (b) b.click();
        }""")
        await page.wait_for_timeout(900)
        msg2 = await page.evaluate("""() => {
          const el = document.querySelector('.submit-bar .ok, .submit-bar .err, #submit-msg');
          return el ? el.className + '|' + el.textContent : '(no msg)';
        }""")
        record("J2c2 恢复后提交成功", msg2.startswith("ok"), msg2)
        # J3 探戈（第二舞种独立表）
        await page.goto(BASE + "/judge/competition-events/5/dances/%E6%8E%A2%E6%88%88")
        await page.wait_for_timeout(800)
        t_rows = await page.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
        t_badges = await page.evaluate("Array.from(document.querySelectorAll('.rank-row:not(.off) .rank-badge')).filter(b => b.textContent.trim()).length")
        record("J3 探戈表独立（空表）", t_rows == 12 and t_badges == 0, f"rows={t_rows} placed={t_badges}")
        # J4 W1F 缺席边界：5 可评 + 1 置灰
        await page.goto(BASE + "/judge/competition-events/6/dances/%E5%8D%8E%E5%B0%94%E5%85%B9")
        await page.wait_for_timeout(800)
        f_on = await page.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
        f_off = await page.evaluate("document.querySelectorAll('.rank-row.off').length")
        note = await page.evaluate("document.getElementById('roster-note') ? document.getElementById('roster-note').textContent : ''")
        record("J4 W1F 缺席 5 可评 1 置灰", f_on == 5 and f_off == 1 and "未检录 1 人" in note,
               f"on={f_on} off={f_off} note={note}")
        await page.screenshot(path=os.path.join(OUT, "j4-final-absent.png"))
        await page.close()
        await ctx.close()

        # ============ P 区：观众公示 ============
        ctx = await browser.new_context(viewport={"width": 375, "height": 812},
                                        is_mobile=True, device_scale_factor=2, has_touch=True)
        page = await ctx.new_page()
        await page.goto(BASE + "/public/schedule")
        await page.wait_for_timeout(800)
        sched = await page.evaluate("""() => ({
            rows: document.querySelectorAll('table tr, .card').length,
            hsw: document.documentElement.scrollWidth - document.documentElement.clientWidth })""")
        record("P1 公开赛程渲染无横滑", sched["hsw"] <= 0, json.dumps(sched))
        # P2 成绩页查询边界
        await page.goto(BASE + "/public/results")
        await page.wait_for_timeout(700)
        await page.fill(".lookup-row input, .card input", "101")
        await page.evaluate("(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('查询')); if (b) b.click(); })()")
        await page.wait_for_timeout(700)
        hit = await page.evaluate("document.body.textContent.includes('101') && document.body.textContent.length > 100")
        await page.fill(".lookup-row input, .card input", "99999999")
        await page.evaluate("(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('查询')); if (b) b.click(); })()")
        await page.wait_for_timeout(700)
        miss = await page.evaluate("""() => {
          const el = document.getElementById('lookup-result');
          return el ? el.textContent : document.body.textContent.slice(0, 80);
        }""")
        record("P2 查询命中与未命中文案", hit and "未找到" in miss,
               f"miss={miss[:80]}")
        await page.screenshot(path=os.path.join(OUT, "p2-lookup-miss.png"))
        # P3 S1F 发布 → 公示并列
        spage = await ctx.new_page()
        await api_login(spage, ctx, "admin", password="admin123")
        await spage.evaluate("""async () => {
          await fetch('/api/competition-events/10/publish', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: '{}'});
        }""")
        await page.goto(BASE + "/public/results")
        await page.wait_for_timeout(900)
        tie = await page.evaluate("""() => {
          const card = Array.from(document.querySelectorAll('.card')).find(c => {
            const h = c.querySelector('h2');
            return h && h.textContent.includes('集体舞');
          });
          if (!card || !card.querySelector('table')) return { found: false };
          const rows = Array.from(card.querySelectorAll('table tr')).map(tr =>
            Array.from(tr.children).map(td => td.textContent.trim()));
          const r301 = rows.find(r => r[0] === '4' && r[1] === '301');
          const r302 = rows.find(r => r[0] === '4' && r[1] === '302');
          return { found: true, tie301: !!r301, tie302: !!r302, sample: rows[1] };
        }""")
        record("P3 评分制平分公示（301/302 并列名次 4）",
               tie.get("found") and tie.get("tie301") and tie.get("tie302"), json.dumps(tie, ensure_ascii=False))
        await page.screenshot(path=os.path.join(OUT, "p3-tie-publish.png"), full_page=False)
        await spage.close()
        await page.close()
        await ctx.close()

        # ============ A 区：管理矩阵 + 大屏 ============
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        page = await ctx.new_page()
        await api_login(page, ctx, "admin", password="admin123")
        await page.goto(BASE + "/events/1/console/4")
        await page.wait_for_timeout(900)
        console = await page.evaluate("""() => ({
            status: (document.getElementById('status')||{}).textContent,
            rosterChk: (document.body.textContent.match(/检录 \\d+\\/\\d+|检录 \\d+ \\/ \\d+/) || [''])[0],
            matrixRows: document.querySelectorAll('#matrix tr').length })""")
        record("A1 console D组矩阵+状态中文", console["status"] == "评分中" and ("7/12" in console["rosterChk"] or "7 / 12" in console["rosterChk"]),
               json.dumps(console))
        await page.screenshot(path=os.path.join(OUT, "a1-console-d.png"))
        # A2 大屏 scoring 态（W1R1D 评分中）
        await page.goto(BASE + "/screen")
        await page.wait_for_timeout(1200)
        screen = await page.evaluate("""() => ({
            title: (document.querySelector('#sec-scoring h1, #sec-welcome h1') || {}).textContent,
            bodyLen: document.body.textContent.length })""")
        record("A2 大屏渲染", (screen["bodyLen"] or 0) > 50, json.dumps(screen))
        await page.screenshot(path=os.path.join(OUT, "a2-screen.png"))
        await page.close()
        await ctx.close()
        await browser.close()

    fails = [r for r in results if not r["ok"]]
    print(f"\n== {len(results) - len(fails)}/{len(results)} PASS ==")
    if fails:
        print(json.dumps(fails, ensure_ascii=False, indent=1))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
