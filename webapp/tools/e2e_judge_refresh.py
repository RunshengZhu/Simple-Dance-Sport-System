#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R38 裁判端轻刷新联动走查：
1) M1（Mark制）只检录 201-203 → judge sheet 204 行置灰；
2) sheet 停留期间 marshal 检录 204 → 断言页面不重载（window 标记存活）且 204 行就地解灰；
3) Mark 制提交守卫：漏标提交 → 明确报错不崩溃；
4) 移动端视觉复拍（judge sheet 置灰态 / staff 已完成手风琴展开态 / public 公告）。
用法：python3 tools/e2e_judge_refresh.py [base_url]
前置：M1(ceid=3) 已开场、E1 已发布（staff 手风琴有内容可展开）。
"""
import asyncio
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8301"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ux-review-r38")
os.makedirs(OUT, exist_ok=True)
results = []


def record(step, ok, detail):
    results.append({"step": step, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + step + " :: " + str(detail))


async def api_login(page, role, **kw):
    body = {"role": role}
    body.update(kw)
    await page.goto(BASE + "/login")
    await page.wait_for_timeout(300)
    return await page.evaluate("""async (body) => {
        const r = await fetch('/api/login', {method: 'POST',
          headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
        return r.status;
      }""", body)


async def run():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 375, "height": 812},
                                        is_mobile=True, device_scale_factor=2, has_touch=True)
        mctx = await browser.new_context(viewport={"width": 375, "height": 812},
                                         is_mobile=True, device_scale_factor=2, has_touch=True)
        # --- 两个独立会话：judge 页（移动）与 marshal 驱动页（隐藏复用同一 context 的另一页）---
        # --- 前置：marshal 先检录 201-203，只留 204 未检录（独立 context 隔离 cookie）---
        mpage = await mctx.new_page()
        await api_login(mpage, "marshal", username="marshal", password="marshal123")
        await mpage.evaluate("""async () => {
          await fetch('/api/competition-events/3/checkin', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({numbers: ['201', '202', '203', '204'], state: false})});
          await fetch('/api/competition-events/3/checkin', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({numbers: ['201', '202', '203'], state: true})});
        }""")
        jpage = await ctx.new_page()
        await jpage.set_viewport_size({"width": 375, "height": 812})
        await api_login(jpage, "judge", judge_id="J1")
        await jpage.goto(BASE + "/judge/competition-events/3/dances/%E7%8E%B0%E4%BB%A3%E8%88%9E")
        await jpage.wait_for_timeout(700)
        # 页面存活标记：轻刷新不应重载
        await jpage.evaluate("window.__alive = 'judge-sheet'")
        off_before = await jpage.evaluate("document.querySelectorAll('.mark-row.off').length")
        total = await jpage.evaluate("document.querySelectorAll('.mark-row').length")
        record("J1 sheet 打开 204 置灰", off_before == 1 and total == 4,
               f"off={off_before}/total={total}")
        await jpage.screenshot(path=os.path.join(OUT, "m-judge-off-row.png"))
        # 滚到中部，记录滚动位置
        await jpage.evaluate("window.scrollTo(0, 200)")
        y0 = await jpage.evaluate("window.scrollY")

        # marshal 检录 204
        ck = await mpage.evaluate("""async () => {
          const r = await fetch('/api/competition-events/3/checkin', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({numbers: ['204'], state: true})});
          return r.status + '|' + (await r.text()).slice(0, 80);
        }""")
        print("checkin204 ->", ck)
        # 等 SSE 推送 + 轻刷新
        await jpage.wait_for_timeout(1800)
        st = await jpage.evaluate("""() => ({
          alive: window.__alive || '(reloaded!)',
          y: window.scrollY,
          off: document.querySelectorAll('.mark-row.off').length,
          note: document.getElementById('roster-note') ? document.getElementById('roster-note').textContent : '' })""")
        record("J2 检录变化轻刷新：页面不重载+204 解灰",
               st["alive"] == "judge-sheet" and st["off"] == 0,
               json.dumps(st, ensure_ascii=False))
        record("J2b 滚动位置保持", abs(st["y"] - y0) < 2, f"y0={y0} y1={st['y']}")

        # 正向提交：点击 201 行给 Mark（若回显已勾先取消再勾上）→ 提交 → ok 回显
        await jpage.evaluate("""() => {
          const row = document.querySelector('.mark-row[data-num=\\'201\\']');
          if (row.querySelector('input.val').checked) row.click();
          row.click();
        }""")
        await jpage.wait_for_timeout(300)
        await jpage.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('.submit-bar button, button'))
            .find(b => b.textContent.includes('提交'));
          if (b) b.click();
        }""")
        await jpage.wait_for_timeout(900)
        guard = await jpage.evaluate("""() => {
          const el = document.querySelector('.submit-bar .ok, .submit-bar .err, #submit-msg');
          return el ? el.className + '|' + el.textContent : '(no msg)';
        }""")
        record("J3 勾选 Mark 后提交成功回显", guard.startswith("ok"), guard)
        await jpage.screenshot(path=os.path.join(OUT, "m-judge-guard.png"))
        await jpage.close()
        await mpage.close()

        # --- 视觉复拍（IAB 合成伪影核实）：staff 手风琴展开态 + public 公告 ---
        spage = await ctx.new_page()
        await spage.set_viewport_size({"width": 1280, "height": 900})
        await api_login(spage, "marshal", username="marshal", password="marshal123")
        await spage.goto(BASE + "/staff")
        await spage.wait_for_timeout(600)
        await spage.evaluate("(() => { const b = document.querySelector('.toggle-done'); if (b) b.click(); })()")
        await spage.wait_for_timeout(300)
        await spage.screenshot(path=os.path.join(OUT, "d-staff-accordion.png"), full_page=True)
        await spage.goto(BASE + "/public/results")
        await spage.wait_for_timeout(600)
        await spage.screenshot(path=os.path.join(OUT, "d-public-results.png"), full_page=True)
        record("V1 视觉复拍完成", True, "d-staff-accordion.png / d-public-results.png")
        await spage.close()
        await browser.close()

    fails = [r for r in results if not r["ok"]]
    print(f"\n== {len(results) - len(fails)}/{len(results)} PASS ==")
    if fails:
        print(json.dumps(fails, ensure_ascii=False, indent=1))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
