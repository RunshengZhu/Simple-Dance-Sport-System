#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R38 断线降级走查（P0 修复核心承诺）：
SSE 被阻断（模拟公网弱网/锁屏断连）时：
1) staff 检录台：不整页重载（__alive 存活），回退轮询走轻刷新（GET checkin）；
2) judge 评分页：同上，且输入中的分值不丢失；
3) public 成绩页：轮询为 softReload，滚动位置保持（8s 观察窗）。
用法：python3 tools/e2e_offline_walk.py [base_url]
"""
import asyncio
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8301"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ux-review-r38")
results = []


def record(step, ok, detail):
    results.append({"step": step, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + step + " :: " + str(detail))


async def api_login(page, role, **kw):
    body = {"role": role}
    body.update(kw)
    await page.goto(BASE + "/login")
    await page.wait_for_timeout(250)
    return await page.evaluate("""async (body) => {
        const r = await fetch('/api/login', {method: 'POST',
          headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
        return r.status;
      }""", body)


async def run():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # --- staff：阻断 SSE ---
        ctx = await browser.new_context(viewport={"width": 375, "height": 812},
                                        is_mobile=True, device_scale_factor=2, has_touch=True)
        await ctx.route("**/api/events/*/stream", lambda route: route.abort())
        page = await ctx.new_page()
        await api_login(page, "marshal", username="marshal", password="marshal123")
        await page.goto(BASE + "/staff")
        await page.wait_for_timeout(800)
        await page.evaluate("window.__alive = 'staff'")
        await page.evaluate("window.scrollTo(0, 99999)")
        y0 = await page.evaluate("window.scrollY")
        # 等 9s：覆盖 8s 轮询窗
        await page.wait_for_timeout(9500)
        st = await page.evaluate("""() => ({
          alive: window.__alive || '(RELOADED)',
          y: window.scrollY,
          badgeOff: !!document.getElementById('net-badge') })""")
        record("OFF1 staff 断线不重载+滚动保持",
               st["alive"] == "staff" and abs(st["y"] - y0) < 2, json.dumps(st) + f" y0={y0}")
        await page.close()
        await ctx.close()

        # --- judge：阻断 SSE + 输入保持 ---
        ctx2 = await browser.new_context(viewport={"width": 375, "height": 812},
                                         is_mobile=True, device_scale_factor=2, has_touch=True)
        await ctx2.route("**/api/events/*/stream", lambda route: route.abort())
        jpage = await ctx2.new_page()
        await api_login(jpage, "judge", judge_id="J1")
        # M1 已 4/4 检录且无提交（上轮 J3 拦截未提交），评分页可输入
        await jpage.goto(BASE + "/judge/competition-events/3/dances/%E7%8E%B0%E4%BB%A3%E8%88%9E")
        await jpage.wait_for_timeout(800)
        await jpage.evaluate("window.__alive = 'judge'")
        # 点击 201 行翻转 Mark（状态无关：无论回显与否，断言翻转成功）
        pre = await jpage.evaluate("document.querySelector('.mark-row[data-num=\\'201\\'] input.val').checked")
        await jpage.evaluate("document.querySelector('.mark-row[data-num=\\'201\\']').click()")
        await jpage.wait_for_timeout(300)
        post = await jpage.evaluate("document.querySelector('.mark-row[data-num=\\'201\\'] input.val').checked")
        record("OFF2a 行点击翻转生效", post != pre, f"pre={pre} post={post}")
        await jpage.wait_for_timeout(7000)  # 覆盖 6s 轻刷新轮询
        st2 = await jpage.evaluate("""() => ({
          alive: window.__alive || '(RELOADED)',
          checked: document.querySelector('.mark-row[data-num=\\'201\\'] input.val').checked })""")
        record("OFF2 judge 断线不重载+输入不丢",
               st2["alive"] == "judge" and st2["checked"] == post, json.dumps(st2) + f" post={post}")
        await jpage.close()
        await ctx2.close()

        # --- public：断线时轮询按期 softReload（标记消失+URL 不变）---
        ctx3 = await browser.new_context(viewport={"width": 375, "height": 812},
                                         is_mobile=True, device_scale_factor=2, has_touch=True)
        await ctx3.route("**/api/events/*/stream", lambda route: route.abort())
        ppage = await ctx3.new_page()
        await ppage.goto(BASE + "/public/results")
        await ppage.wait_for_timeout(600)
        url0 = ppage.url
        reloaded = False
        await ppage.evaluate("window.__alive = 'pub'")
        for _ in range(14):   # 最多 ~14s 覆盖 8s 轮询窗
            try:
                alive = await ppage.evaluate("window.__alive || '(RELOADED)'")
            except Exception:
                alive = '(NAV)'
            if alive != 'pub':
                reloaded = True
                break
            await ppage.wait_for_timeout(1000)
        record("OFF3 public 断线轮询按期 softReload（不堆积不熄火）",
               reloaded and ppage.url == url0, f"reloaded={reloaded} url_same={ppage.url == url0}")
        await ppage.close()
        await ctx3.close()
        await browser.close()

    fails = [r for r in results if not r["ok"]]
    print(f"\n== {len(results) - len(fails)}/{len(results)} PASS ==")
    if fails:
        print(json.dumps(fails, ensure_ascii=False, indent=1))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
