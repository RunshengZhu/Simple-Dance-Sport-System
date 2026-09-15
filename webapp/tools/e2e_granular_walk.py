#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R45 细粒度全动线 E2E：五角色逐步真实驱动，每步断言+关键帧截图。

与既有走查的差异：动线级粒度——从建赛到发布收官的完整生命周期逐步点击，
重点覆盖 R44 新功能（CSV 模板下载/花名册批量勾选/计算并发布/下一场跳转/公开页锚点/toast）。
环境：本地压测库（8302），新建独立测试赛事，不污染压测数据。
用法：python3 tools/e2e_granular_walk.py [BASE]
"""
import asyncio
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ux-review-r45")
os.makedirs(OUT, exist_ok=True)
results = []


def record(step, ok, detail):
    results.append({"step": step, "ok": bool(ok), "detail": str(detail)[:240]})
    print(("PASS " if ok else "FAIL ") + step + " :: " + str(detail)[:240])


async def run():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        async def new_ctx(w=375, h=812, mobile=True, theme=None):
            ctx = await browser.new_context(viewport={"width": w, "height": h},
                                            is_mobile=mobile, has_touch=mobile,
                                            device_scale_factor=2, locale="zh-CN")
            if theme:
                await ctx.add_init_script(
                    "try{localStorage.setItem('ds-theme','%s')}catch(e){}" % theme)
            return ctx

        async def login(page, **kw):
            await page.goto(BASE + "/login")
            await page.wait_for_timeout(250)
            st = await page.evaluate("""async (b) => {
              const r = await fetch('/api/login', {method:'POST',
                headers:{'Content-Type':'application/json'}, body: JSON.stringify(b)});
              return r.status;
            }""", dict(**kw))
            return st

        # ================= ADMIN-L：管理员完整生命周期（桌面 dark） =================
        ctx = await new_ctx(1440, 900, False, "dark")
        page = await ctx.new_page()
        await login(page, role="admin", password="admin123")
        # A1 建赛
        await page.goto(BASE + "/events")
        await page.wait_for_timeout(500)
        await page.fill('input[placeholder="赛事名称（必填）"]', "R45动线测试赛")
        await page.fill('input[placeholder="日期 YYYY-MM-DD"]', "2026-09-14")
        await page.fill('input[placeholder="地点"]', "动线馆")
        await page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === '创建');
          b.click();
        }""")
        await page.wait_for_timeout(900)
        created = await page.evaluate("document.body.textContent.includes('R45动线测试赛')")
        record("A1 建赛并出现在列表", created, "R45动线测试赛")
        # 取 cid
        cid = await page.evaluate("""() => {
          const rows = Array.from(document.querySelectorAll('table tr'));
          for (const r of rows) if (r.textContent.includes('R45动线测试赛')) {
            const a = r.querySelector('a'); const m = a && a.href.match(/events\\/(\\d+)/);
            if (m) return m[1];
          } return null;
        }""")
        record("A1b 取得 cid", cid is not None, f"cid={cid}")
        # 激活赛事（系统单激活赛事模型；多赛事时需显式激活）
        await page.evaluate(f"async () => {{ await fetch('/api/events/{cid}/activate', {{method:'POST'}}); }}")
        await page.wait_for_timeout(300)
        await page.screenshot(path=os.path.join(OUT, "a1-events.png"))
        # A2 导入页：三模板下载断言（R44 新功能）
        await page.goto(BASE + f"/events/{cid}/import")
        await page.wait_for_timeout(500)
        tpl = await page.evaluate("""async () => {
          const out = {};
          for (const kind of ['competitors', 'judges', 'schedule']) {
            const r = await fetch('/api/templates/' + kind);
            const cd = r.headers.get('content-disposition') || '';
            const txt = await r.text();
            out[kind] = r.status + '|' + (cd.includes('attachment') ? 'att' : 'noatt') + '|' + txt.split('\\n')[0].slice(0, 20);
          }
          return out;
        }""")
        record("A2 三模板下载（表头即解析列）",
               all(v.startswith("200|att") for v in tpl.values()), json.dumps(tpl, ensure_ascii=False))
        # A2b CSV 表单真实导入（选手/裁判/赛程）
        csv_data = {
            "competitors": "背番号,项目编号,姓名,学校/单位\n901,P9,动线甲,动线大学\n902,P9,动线乙,动线大学\n903,P9,动线丙,动线大学\n904,P9,动线丁,动线大学",
            "judges": "裁判ID,姓名\nJ1,动线裁1\nJ2,动线裁2\nJ3,动线裁3",
            "schedule": "场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\nP9F,P9决赛,P9,1,集体舞,SCORE,0,901,902,903,904",
        }
        await page.evaluate("""async (d) => {
          for (const kind of ['competitors', 'judges', 'schedule']) {
            await fetch(`/api/events/${window.CID || location.pathname.match(/events\\/(\\d+)/)[1]}/imports/${kind}`,
              {method: 'POST', headers: {'Content-Type': 'text/csv; charset=utf-8'}, body: d[kind]});
          }
        }""", csv_data)
        await page.wait_for_timeout(600)
        # 赛程页确认场次
        await page.goto(BASE + f"/events/{cid}/schedule")
        await page.wait_for_timeout(600)
        sched_ok = await page.evaluate("document.body.textContent.includes('P9F')")
        record("A2c CSV 导入后场次出现", sched_ok, "P9F")
        # A3 控制台：花名册批量勾选（R44 新功能）→ 开启评分
        ceid = await page.evaluate("""async () => {
          const r = await fetch('/api/public/events/%s/schedule');
          const o = await r.json();
          return o.events.find(e => e.code === 'P9F').id;
        }""" % cid)
        await page.goto(BASE + f"/events/{cid}/console/{ceid}")
        await page.wait_for_timeout(700)
        await page.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
        await page.evaluate("(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent === '全选'); if (b) b.click(); })()")
        await page.wait_for_timeout(250)
        cnt = await page.evaluate("document.getElementById('cand-count') ? document.getElementById('cand-count').textContent : ''")
        record("A3 花名册全选+计数", "4 / 4" in cnt, cnt)
        await page.screenshot(path=os.path.join(OUT, "a3-console-selectall.png"))
        await page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('开启评分'));
          if (b) b.click();
        }""")
        await page.wait_for_timeout(1000)
        scoring = await page.evaluate("(document.getElementById('status')||{}).textContent")
        record("A4 开启评分", scoring == "评分中", scoring)
        # A5 下一场跳转链接（P9 单场无下一场 → 断言不出现即正确）
        nextlink = await page.evaluate("!!document.querySelector('a[href*=\\'console\\']')")
        record("A5 单场次无下一场链接（正确）", nextlink is False, f"nextlink={nextlink}")
        # A6 toast：未收齐时点「计算并发布」→ 报错 toast 出现
        await page.evaluate("(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('计算并发布')); if (b) b.click(); })()")
        await page.wait_for_timeout(800)
        calc_msg = await page.evaluate("document.getElementById('calc-msg') ? document.getElementById('calc-msg').textContent : ''")
        record("A6 计算并发布失败→行内报错", len(calc_msg.strip()) > 0, calc_msg[:80])
        await page.screenshot(path=os.path.join(OUT, "a6-toast-err.png"))
        await page.close()
        await ctx.close()

        # ================= MARSHAL-L：检录台（移动 dark） =================
        ctx = await new_ctx(375, 812, True, "dark")
        page = await ctx.new_page()
        await login(page, role="marshal", username="marshal", password="marshal123")
        await page.goto(BASE + "/staff")
        await page.wait_for_timeout(800)
        # 检录 R45 测试赛 P9F（ceid）——先定位该卡的背号 901
        has_card = await page.evaluate("!!document.querySelector('.st-event[data-ceid=\\'%s\\']')" % ceid)
        record("M1 检录台含新赛事卡", has_card, f"ceid={ceid}")
        if has_card:
            await page.evaluate(f"document.querySelector('.st-event[data-ceid=\\'{ceid}\\']').scrollIntoView({{block:'center', behavior:'instant'}})")
            await page.wait_for_timeout(300)
            y0 = await page.evaluate("window.scrollY")
            await page.evaluate(f'document.querySelector(".chip[data-ceid=\'{ceid}\'][data-num=\'901\']").click()')
            await page.wait_for_timeout(700)
            st = await page.evaluate(f"""() => ({{
              y: window.scrollY,
              on: document.querySelector('.chip[data-ceid="{ceid}"][data-num="901"]').classList.contains('on') }})""")
            record("M2 检录点击稳定+翻转", abs(st["y"] - y0) < 2 and st["on"], json.dumps(st))
            # 批量全清 → 重新全检录
            await page.evaluate(f"""() => {{
              const card = document.querySelector('.st-event[data-ceid=\\'{ceid}\\']');
              Array.from(card.querySelectorAll('button')).find(b => b.textContent === '全清').click();
            }}""")
            await page.wait_for_timeout(600)
            cleared = await page.evaluate(f"document.getElementById('prog-{ceid}').textContent")
            record("M3 全清", "0 / 4" in cleared, cleared)
            await page.evaluate(f"""() => {{
              const card = document.querySelector('.st-event[data-ceid=\\'{ceid}\\']');
              Array.from(card.querySelectorAll('button')).find(b => b.textContent === '全部检录').click();
            }}""")
            await page.wait_for_timeout(600)
            full = await page.evaluate(f"document.getElementById('prog-{ceid}').textContent")
            record("M4 全部检录", "4 / 4" in full, full)
        # 已完成手风琴（P9F 已发布后出现在已完成区）

        # ================= JUDGE-L：裁判三制式（移动 dark） =================
        # 用 API 让 4 名裁判提交后 J1 修改提交（覆盖动线）
        ctx = await new_ctx(375, 812, True, "dark")
        page = await ctx.new_page()
        await login(page, role="judge", judge_id="J1")
        # 检录已由 MARSHAL-L 段完成（全部检录 4/4），裁判直接评分
        await login(page, role="judge", judge_id="J1")
        await page.goto(BASE + f"/judge/competition-events/{ceid}/dances/%E9%9B%86%E4%BD%93%E8%88%9E")
        await page.wait_for_timeout(700)
        rows_on = await page.evaluate("document.querySelectorAll('.score-row:not(.off)').length")
        record("J1 评分制 4 行可用", rows_on == 4, f"rows={rows_on}")
        for num, v in [("901", "8"), ("902", "7.5"), ("903", "9"), ("904", "6.5")]:
            await page.fill(f'.score-row input.val[data-num="{num}"]', v)
        await page.wait_for_timeout(300)
        prog = await page.evaluate("document.getElementById('progress').textContent")
        record("J2 评分进度可提交", "可提交" in prog, prog)
        await page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('提交'));
          if (b) b.click();
        }""")
        await page.wait_for_timeout(900)
        jmsg = await page.evaluate("""() => {
          const el = document.querySelector('.submit-bar .ok, .submit-bar .err, #submit-msg');
          return el ? el.className + '|' + el.textContent : '(no msg)';
        }""")
        record("J3 提交成功回显", jmsg.startswith("ok"), jmsg)
        await page.screenshot(path=os.path.join(OUT, "j3-score-submitted.png"))
        # 其余裁判（J2/J3）提交 → 收齐自动计算（admin fetch 直驱）
        await page.evaluate("""async (ceid) => {
          for (const j of ['J2', 'J3']) {
            await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'},
              body: JSON.stringify({role:'judge', judge_id:j})});
            const vals = {};
            for (const n of ['901','902','903','904']) vals[n] = 6 + Math.random()*3;
            await fetch(`/api/judge/competition-events/${ceid}/dances/%E9%9B%86%E4%BD%93%E8%88%9E/sheet`, {method:'PUT',
              headers:{'Content-Type':'application/json'}, body: JSON.stringify({values: vals})});
          }
        }""", ceid)
        await login(page, role="admin", password="admin123")   # console 需管理员会话
        await page.goto(BASE + f"/events/{cid}/console/{ceid}")
        await page.wait_for_timeout(800)
        calc_state = await page.evaluate("""() => ({
          status: (document.getElementById('status')||{}).textContent,
          complete: (document.body.textContent.includes('已收齐')) })""")
        record("J4 全员收齐（裁判矩阵收齐）", calc_state["complete"] is True, json.dumps(calc_state, ensure_ascii=False))
        # 计算并发布（R44 新按钮）
        await page.evaluate("(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('计算并发布')); if (b) b.click(); })()")
        await page.wait_for_timeout(1400)
        pub = await page.evaluate("(document.getElementById('status')||{}).textContent")
        record("J5 计算并发布一击完成", pub == "已发布", pub)
        await page.screenshot(path=os.path.join(OUT, "j5-published.png"))
        await page.close()
        await ctx.close()

        # ================= PUBLIC-L：观众（移动 light） =================
        ctx = await new_ctx(375, 812, True, "light")
        page = await ctx.new_page()
        await page.goto(BASE + f"/public/results")
        await page.wait_for_timeout(800)
        anchor = await page.evaluate("""() => {
          const bar = document.querySelector('.anchor-bar');
          const chip = bar && bar.querySelector('a.anchor-chip');
          return { bar: !!bar, chipHref: chip && chip.getAttribute('href') };
        }""")
        record("P1 锚点条渲染", anchor["bar"] and bool(anchor["chipHref"]), json.dumps(anchor))
        y0 = await page.evaluate("window.scrollY")
        if anchor["chipHref"]:
            await page.evaluate(f"(() => {{ const a = document.querySelector('a.anchor-chip'); a.click(); }})()")
            await page.wait_for_timeout(1600)   # 长距平滑滚动需更长时间
            y1 = await page.evaluate("""() => {
              const target = document.querySelector('a.anchor-chip');
              const id = target && target.getAttribute('href').slice(1);
              const el = id && document.getElementById(id);
              if (!el) return -1;
              const r = el.getBoundingClientRect();
              return Math.round(r.top);
            }""")
            vh = await page.evaluate("window.innerHeight")
            record("P2 锚点滚动目标可见", 0 <= y1 < vh, f"target top={y1}px vh={vh}")
        await page.screenshot(path=os.path.join(OUT, "p2-anchor.png"))
        # 观众查询
        await page.fill(".lookup-row input", "901")
        await page.evaluate("(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('查询')); if (b) b.click(); })()")
        await page.wait_for_timeout(700)
        hit = await page.evaluate("document.body.textContent.includes('动线甲')")
        record("P3 查询命中选手", hit, "动线甲")
        await page.close()
        await ctx.close()

        # ---- 发布后：已完成手风琴（新开 marshal 会话） ----
        ctx = await new_ctx(375, 812, True, "dark")
        page = await ctx.new_page()
        await login(page, role="marshal", username="marshal", password="marshal123")
        await page.goto(BASE + "/staff")
        await page.wait_for_timeout(900)
        done_exists = await page.evaluate("!!document.querySelector('.done-card')")
        record("M5 已完成卡出现", done_exists, f"done={done_exists}")
        if done_exists:
            await page.evaluate("(() => { const b = document.querySelector('.toggle-done'); if (b) b.click(); })()")
            await page.wait_for_timeout(450)
            acc = await page.evaluate("""() => {
              const b = document.querySelector('.done-card .done-body.open table');
              return !!b && b.getBoundingClientRect().height > 30;
            }""")
            record("M6 手风琴展开可见成绩表", acc, "table visible")
            await page.screenshot(path=os.path.join(OUT, "m6-accordion.png"))
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
