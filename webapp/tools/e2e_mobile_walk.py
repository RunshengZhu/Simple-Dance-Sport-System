#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R38 移动端 375 交互走查：staff 检录动线 + judge 评分动线 + public 观众动线。
每步断言交互不变量（滚动稳定/状态翻转/计数同步/无横滑），并截关键帧。
用法：python3 tools/e2e_mobile_walk.py [base_url]（默认 http://127.0.0.1:8301）
前置：E1 已开启评分（scoring）、裁判 J1 存在、marshal 账号可用（本地默认口令）。
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
    print(("PASS " if ok else "FAIL ") + step + " :: " + detail)


async def new_page(ctx, w, h, mobile):
    page = await ctx.new_page()
    await page.set_viewport_size({"width": w, "height": h})
    return page


async def login(page, role, username=None, password=None, judge_id=None):
    await page.goto(BASE + "/login?role=" + role)
    await page.wait_for_load_state("domcontentloaded")
    if judge_id:
        await page.fill("#judge_id", judge_id)
    if username is not None:
        await page.fill("#username", username)
    if password is not None:
        await page.fill("#password", password)
    await page.click("#btn")
    await page.wait_for_timeout(900)


async def run():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 375, "height": 812}, is_mobile=True,
            device_scale_factor=2, has_touch=True)

        # ---------- B: 检录长移动端 ----------
        page = await new_page(ctx, 375, 812, True)
        await login(page, "marshal", "marshal", "marshal123")
        record("B1 marshal 登录跳转", page.url.endswith("/staff"), page.url)
        await page.wait_for_selector(".st-event[data-ceid='1']")
        # B2 初始截图
        await page.screenshot(path=os.path.join(OUT, "m-staff-top.png"))
        # B3 先全清 E1（保证点击=检录方向），滚到卡片中心，点 101 检录，断言滚动稳定 + 状态翻转 + 计数
        await page.evaluate("document.querySelector('.st-event[data-ceid=\\'1\\'] [data-all][data-state=\\'0\\']').click()")
        await page.wait_for_timeout(700)
        await page.evaluate("document.querySelector('.st-event[data-ceid=\\'1\\']').scrollIntoView({block:'center'})")
        y0 = await page.evaluate("window.scrollY")
        await page.click(".chip[data-ceid='1'][data-num='101']")
        await page.wait_for_timeout(800)
        st = await page.evaluate("""() => ({
          y: window.scrollY,
          on: document.querySelector('.chip[data-ceid=\\'1\\'][data-num=\\'101\\']').classList.contains('on'),
          prog: document.getElementById('prog-1').textContent })""")
        record("B3 移动端检录点击滚动稳定+翻转+计数",
               abs(st["y"] - y0) < 2 and st["on"] and st["prog"] == "检录 1 / 4",
               json.dumps(st, ensure_ascii=False))
        await page.screenshot(path=os.path.join(OUT, "m-staff-checked.png"))
        # B3b 点击精度：chip 中心 elementFromPoint 命中自身
        hit = await page.evaluate("""() => {
          const c = document.querySelector('.chip[data-ceid=\\'1\\'][data-num=\\'102\\']');
          const r = c.getBoundingClientRect();
          const el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return el === c || c.contains(el);
        }""")
        record("B3b chip 中心命中无遮挡", hit, "elementFromPoint==chip")
        # B4 批量全部检录
        await page.evaluate("document.querySelector('.st-event[data-ceid=\\'1\\'] [data-all]').click()")
        await page.wait_for_timeout(700)
        allon = await page.evaluate("""() => ({
          n: document.querySelectorAll('.chip[data-ceid=\\'1\\'].on').length,
          prog: document.getElementById('prog-1').textContent })""")
        record("B4 全部检录", allon["n"] == 4 and allon["prog"] == "检录 4 / 4", json.dumps(allon, ensure_ascii=False))
        # B2 筛选 chips
        await page.evaluate("Array.from(document.querySelectorAll('.sf-btn')).find(b=>b.textContent==='待检录').click()")
        vis = await page.evaluate("Array.from(document.querySelectorAll('.st-event')).filter(c=>c.style.display!=='none').map(c=>c.dataset.code)")
        record("B2 待检录筛选（E1 满检仍因评分中可见）", "E1" in vis and "M1" in vis, str(vis))
        await page.evaluate("Array.from(document.querySelectorAll('.sf-btn')).find(b=>b.textContent==='全部').click()")
        # B2b 搜索定位
        await page.fill("#staff-search", "M1")
        await page.wait_for_timeout(1100)
        loc = await page.evaluate("""() => ({
          vis: Array.from(document.querySelectorAll('.st-event')).filter(c=>c.style.display!=='none').map(c=>c.dataset.code),
          flash: !!document.querySelector('.st-event.flash') })""")
        record("B2b 搜索 M1 过滤+高亮", "M1" in loc["vis"] and "E1" not in loc["vis"] and loc["flash"], json.dumps(loc))
        await page.fill("#staff-search", "")
        # B7 无横滑断言（整页）
        hsw = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        record("B7 检录台无水平滚动", hsw <= 0, f"overflowX={hsw}px")
        await page.close()

        # ---------- D: 裁判移动端 ----------
        page = await new_page(ctx, 375, 812, True)
        await login(page, "judge", judge_id="J1")
        record("D1 裁判登录跳转", page.url.endswith("/judge"), page.url)
        await page.wait_for_timeout(500)
        await page.screenshot(path=os.path.join(OUT, "m-judge-home.png"))
        # D2 进 E1 评分页（顺位法）
        await page.goto(BASE + "/judge/competition-events/1/dances/%E5%8D%8E%E5%B0%94%E5%85%B9")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(500)
        has_rows = await page.evaluate("document.querySelectorAll('.rank-row').length")
        record("D2 进入顺位法评分页", has_rows >= 4, f"rank-rows={has_rows} url={page.url}")
        # D5 检录后行应可用（E1 已 4/4 检录）→ 无 off 行
        offn = await page.evaluate("document.querySelectorAll('.rank-row.off').length")
        record("D5 满检录时无置灰行", offn == 0, f"off rows={offn}")
        # 顺位法顺序点选：点 101 → rank badge 1
        await page.evaluate("document.querySelector('.rank-row[data-num=\\'101\\']').click()")
        await page.wait_for_timeout(300)
        b1 = await page.evaluate("document.querySelector('.rank-row[data-num=\\'101\\'] .rank-badge').textContent")
        record("D2a 顺序点选 101=第1名", b1.strip() == "1", f"badge={b1!r}")
        await page.evaluate("document.querySelector('.rank-row[data-num=\\'102\\']').click()")
        await page.evaluate("document.querySelector('.rank-row[data-num=\\'103\\']').click()")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(OUT, "m-judge-sheet.png"))
        # 直接指定模式
        await page.evaluate("Array.from(document.querySelectorAll('.mt-btn')).find(b=>b.dataset.mode==='direct').click()")
        await page.wait_for_timeout(300)
        kp0 = await page.evaluate("document.getElementById('keypad').style.display")
        await page.evaluate("document.querySelector('.rank-row[data-num=\\'103\\']').click()")
        await page.wait_for_timeout(300)
        kp = await page.evaluate("document.getElementById('keypad').style.display")
        kpnum = await page.evaluate("document.getElementById('kp-num').textContent")
        record("D2b 直接指定：点击选手后弹键盘", kp0 == "none" and kp == "block" and "103" in kpnum,
               f"before={kp0} after={kp} kp-num={kpnum}")
        # D7 无横滑
        hsw2 = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        record("D7 评分页无水平滚动", hsw2 <= 0, f"overflowX={hsw2}px")
        await page.close()

        await browser.close()

    fails = [r for r in results if not r["ok"]]
    print(f"\n== {len(results) - len(fails)}/{len(results)} PASS ==")
    if fails:
        print(json.dumps(fails, ensure_ascii=False, indent=1))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
