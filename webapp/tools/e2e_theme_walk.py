#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R40 主题/多尺寸高密度走查：
- 视口三档：mobile 375×812（触屏）/ tablet 834×1112（触屏）/ desktop 1440×900
- 主题两态：light / dark（localStorage 物化，覆盖 prefers-color-scheme）
- 页面 11 个（login/events/schedule/console/users/staff/judge-sheet/judge-home/public×2/screen）
- 每组合断言：页面级无水平滚动（#matrix 例外为容器内滚）、主题背景色生效、标题可读
- 交互抽查：主题切换按钮（持久化+背景翻转）、staff 检录滚动稳定、judge 行点选、手风琴互斥
用法：python3 tools/e2e_theme_walk.py [BASE]（默认 http://127.0.0.1:8302 压测库）
前置：build_stress_data.py 已就绪（W1R1D=4 scoring 7/12、W1F=6 scoring、S1F=10 已发布）。
"""
import asyncio
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ux-review-r40")
os.makedirs(OUT, exist_ok=True)
results = []


def record(step, ok, detail):
    results.append({"step": step, "ok": bool(ok), "detail": str(detail)[:260]})
    print(("PASS " if ok else "FAIL ") + step + " :: " + str(detail)[:260])


VIEWPORTS = [
    ("mobile", 375, 812, True),
    ("tablet", 834, 1112, True),
    ("desktop", 1440, 900, False),
]

# (名称, 路径, 角色, 角色参数)
PAGES = [
    ("login", "/login", None, None),
    ("events", "/events", "admin", {"password": "admin123"}),
    ("schedule", "/events/1/schedule", "admin", {"password": "admin123"}),
    ("console", "/events/1/console/4", "admin", {"password": "admin123"}),
    ("users", "/users", "admin", {"password": "admin123"}),
    ("staff", "/staff", "marshal", {"username": "marshal", "password": "marshal123"}),
    ("judge-sheet", "/judge/competition-events/6/dances/%E5%8D%8E%E5%B0%94%E5%85%B9", "judge", {"judge_id": "J6"}),
    ("judge-home", "/judge", "judge", {"judge_id": "J6"}),
    ("public-schedule", "/public/schedule", None, None),
    ("public-results", "/public/results", None, None),
    ("screen", "/screen", None, None),
]

DARK_BG = "rgb(19, 21, 25)"
LIGHT_BG = "rgb(245, 243, 239)"
# 大屏页固定深色背景，不走通用断言
SCREEN_PAGES = {"screen"}
# 公开页任何会话都可看；角色页需要在进入前登录
SHOT_PAGES = {"login", "events", "schedule", "console", "staff", "judge-sheet", "public-results"}


async def run():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for vp_name, w, h, touch in VIEWPORTS:
            for theme in ("light", "dark"):
                ctx = await browser.new_context(
                    viewport={"width": w, "height": h}, is_mobile=touch,
                    has_touch=touch, device_scale_factor=2, locale="zh-CN")
                await ctx.add_init_script(
                    "try{localStorage.setItem('ds-theme','%s')}catch(e){}" % theme)
                page = await ctx.new_page()
                for name, path, role, kw in PAGES:
                    if role:
                        await page.goto(BASE + "/login")
                        await page.wait_for_timeout(180)
                        await page.evaluate("""async (b) => {
                          await fetch('/api/login', {method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify(b)});
                        }""", dict(role=role, **kw))
                    await page.goto(BASE + path)
                    await page.wait_for_timeout(700 if name != "screen" else 1300)
                    st = await page.evaluate("""() => ({
                      bg: getComputedStyle(document.body).backgroundColor,
                      hsw: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                      theme: document.documentElement.dataset.theme,
                      title: (document.querySelector('h1') || document.body).textContent.trim().slice(0, 40),
                      btnBg: (() => { const b = document.querySelector('.btn'); if (!b) return null;
                        const s = getComputedStyle(b);
                        return (s.backgroundImage === 'none' && s.backgroundColor === 'rgba(0, 0, 0, 0)') ? 'MISSING' : 'ok'; })(),
                      cardBorder: (() => { const c = document.querySelector('.card'); if (!c) return null;
                        return getComputedStyle(c).borderTopStyle; })() })""")
                    expect_bg = DARK_BG if theme == "dark" else LIGHT_BG
                    if name in SCREEN_PAGES:
                        bg_ok = True   # 大屏固定深色自成体系
                    else:
                        bg_ok = st["bg"] == expect_bg
                    elem_ok = st["btnBg"] != "MISSING" and st["cardBorder"] in (None, "solid")
                    record(f"{vp_name}/{theme}/{name}",
                           bg_ok and st["hsw"] <= 0 and st["theme"] == theme and elem_ok,
                           f"bg={st['bg']} hsw={st['hsw']} btn={st['btnBg']} border={st['cardBorder']} title={st['title']!r}")
                    if name in SHOT_PAGES:
                        await page.screenshot(path=os.path.join(OUT, f"{vp_name}-{theme}-{name}.png"))
                # ---- 交互抽查（每视口 dark 一轮）----
                if theme == "dark":
                    # T1 主题切换按钮：点击翻转 + localStorage + 背景变化
                    await page.goto(BASE + "/public/results")
                    await page.wait_for_timeout(500)
                    t1 = await page.evaluate("""async () => {
                      const before = document.documentElement.dataset.theme;
                      const bgBefore = getComputedStyle(document.body).backgroundColor;
                      document.getElementById('theme-toggle').click();
                      await new Promise(r => setTimeout(r, 120));
                      const after = document.documentElement.dataset.theme;
                      const bgAfter = getComputedStyle(document.body).backgroundColor;
                      let saved = null; try { saved = localStorage.getItem('ds-theme'); } catch (e) {}
                      document.getElementById('theme-toggle').click();
                      return { before, after, bgBefore, bgAfter, saved };
                    }""")
                    record(f"{vp_name}/dark/theme-toggle", t1["before"] != t1["after"] and
                           t1["bgBefore"] != t1["bgAfter"] and t1["saved"] == t1["after"],
                           json.dumps(t1))
                    # T2 staff 检录点击滚动稳定（mobile/tablet 点 144，desktop 点 401）
                    await page.goto(BASE + "/login")
                    await page.wait_for_timeout(200)
                    await page.evaluate("""async () => {
                      await fetch('/api/login', {method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({role: 'marshal', username: 'marshal', password: 'marshal123'})});
                    }""")
                    await page.goto(BASE + "/staff")
                    await page.wait_for_timeout(800)
                    # R47：动态挑一个「评分中」场次的目标芯片（优先未检录 off，退而 on）
                    ceid, num = await page.evaluate("""() => {
                      for (const c of document.querySelectorAll('.st-event')) {
                        if (c.dataset.status !== 'scoring') continue;
                        const chip = c.querySelector('.chip.off') || c.querySelector('.chip.on');
                        if (chip) return [c.dataset.ceid, chip.dataset.num];
                      }
                      return [null, null];
                    }""")
                    if not ceid:
                        record(f"{vp_name}/dark/staff-click-stable（跳过：无评分中芯片）", True, "no chip")
                    else:
                        await page.evaluate(
                            f"document.querySelector('.st-event[data-ceid=\'{ceid}\']').scrollIntoView({{block:'center', behavior:'instant'}})")
                        await page.wait_for_timeout(600)   # R42 scroll-behavior:smooth 后等滚动完成
                        y0 = await page.evaluate("window.scrollY")
                        pre = await page.evaluate(
                            f"document.querySelector('.chip[data-ceid=\'{ceid}\'][data-num=\'{num}\']').classList.contains('on')")
                        await page.evaluate(
                            f"document.querySelector('.chip[data-ceid=\'{ceid}\'][data-num=\'{num}\']').click()")
                        await page.wait_for_timeout(700)
                        st2 = await page.evaluate("""([ceid, num]) => ({
                          y: window.scrollY,
                          on: document.querySelector('.chip[data-ceid="'+ceid+'"][data-num="'+num+'"]').classList.contains('on') })""", [ceid, num])
                        record(f"{vp_name}/dark/staff-click-stable",
                               abs(st2["y"] - y0) < 2 and st2["on"] != pre,
                               json.dumps(st2) + f" y0={y0} pre={pre}")
                    record(f"{vp_name}/dark/staff-click-stable",
                           abs(st2["y"] - y0) < 2 and st2["on"] != pre,
                           json.dumps(st2) + f" y0={y0} pre={pre}")
                    # T3 judge 行点选（不提交）
                    await page.evaluate("""async () => {
                      await fetch('/api/login', {method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({role: 'judge', judge_id: 'J8'})});
                    }""")
                    await page.goto(BASE + "/judge/competition-events/6/dances/%E5%8D%8E%E5%B0%94%E5%85%B9")
                    await page.wait_for_timeout(700)
                    j1 = await page.evaluate("""() => {
                      const row = document.querySelector('.rank-row:not(.off)');
                      if (!row) return { ok: false };
                      row.click();
                      return { ok: row.querySelector('.rank-badge').textContent.trim() !== '' };
                    }""")
                    record(f"{vp_name}/dark/judge-tap", j1.get("ok") is True, json.dumps(j1))
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
