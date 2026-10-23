# -*- coding: utf-8 -*-
"""R59 培训幻灯片专用干净截图：元素级聚焦，无标注、无半截行。
本地 8302 + manual_annotate 的演示数据。产出 static/manual/r59/。
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import manual_annotate as ma  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "server", "static", "manual", "r59")
os.makedirs(OUT, exist_ok=True)


async def run():
    demo, ids = ma.setup_data()
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        async def login(page, role, kw=None):
            body = {"role": role}
            body.update(kw or {})
            await page.evaluate("""async (b) => { await fetch('/api/login', {method:'POST',
                headers:{'Content-Type':'application/json'}, body: JSON.stringify(b)}); }""", body)

        # ---- 1 控制台：上场名单卡（desktop）----
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                        device_scale_factor=2, locale="zh-CN")
        pg = await ctx.new_page()
        await pg.goto(ma.BASE + "/login")
        await login(pg, "admin", {"password": "admin123"})
        await pg.goto(f"{ma.BASE}/events/{demo}/console/{ids['D2']}")
        await pg.wait_for_timeout(800)
        await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
        await pg.wait_for_timeout(400)
        card = pg.locator("details.card").first
        await card.screenshot(path=os.path.join(OUT, "a-console-open.png"))
        print("shot a-console-open")
        await ctx.close()

        # ---- 2 主持台：已完成场次原位展开（mobile）----
        ctx = await browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                        has_touch=True, device_scale_factor=2, locale="zh-CN")
        pg = await ctx.new_page()
        await pg.goto(ma.BASE + "/staff")
        await login(pg, "marshal", {"username": "marshal", "password": "marshal123"})
        await pg.goto(ma.BASE + "/staff")
        await pg.wait_for_timeout(800)
        await pg.evaluate("(() => { const b = document.querySelector('.toggle-done'); if (b) b.click(); })()")
        await pg.wait_for_timeout(600)
        card = pg.locator(".done-card").first
        await card.scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        await card.screenshot(path=os.path.join(OUT, "m-accordion.png"))
        print("shot m-accordion")
        await ctx.close()

        # ---- 3 裁判顺位法：首屏视口（表头+模式切换+前排名次行+固定提交栏）----
        from urllib.parse import quote
        ctx = await browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                        has_touch=True, device_scale_factor=2, locale="zh-CN")
        pg = await ctx.new_page()
        await pg.goto(ma.BASE + "/judge")
        await login(pg, "judge", {"judge_id": "J1"})
        await pg.goto(f"{ma.BASE}/judge/competition-events/{ids['D1']}/dances/{quote('华尔兹')}")
        await pg.wait_for_timeout(900)
        await pg.evaluate("window.scrollTo(0, 0)")
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=os.path.join(OUT, "j-skating.png"))
        print("shot j-skating")
        await ctx.close()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
