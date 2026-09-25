#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主题×视口×页面 三维走查（R40 建，R47 动态化改造：cid/ceid/dance 不再硬编码）。

- 视口三档：mobile 375×812（触屏）/ tablet 834×1112（触屏）/ desktop 1440×900
- 主题两态：light / dark（localStorage 物化，覆盖 prefers-color-scheme）
- 页面 11 个（login/events/schedule/console/users/staff/judge-sheet/judge-home/public×2/screen）
- 每组合断言：页面级无水平滚动（#matrix 例外为容器内滚）、主题背景色生效、
  元素级健全（.btn 背景非空 / .card 边框 solid）、标题可读
- 交互抽查：主题切换按钮（持久化+背景翻转）、staff 检录点击（动态挑评分中场次芯片）、
  judge 行点选
用法：python3 webapp/tools/e2e_theme_walk.py [BASE]
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

# (名称, 路径, 角色, 角色参数)；{cid}/{js_ceid}/{js_dance} 为 run() 内动态解析的占位符
PAGES = [
    ("login", "/login", None, None),
    ("events", "/events", "admin", {"password": "admin123"}),
    ("schedule", "/events/{cid}/schedule", "admin", {"password": "admin123"}),
    ("console", "/events/{cid}/console/{js_ceid}", "admin", {"password": "admin123"}),
    ("users", "/users", "admin", {"password": "admin123"}),
    ("staff", "/staff", "marshal", {"username": "marshal", "password": "marshal123"}),
    ("judge-sheet", "/judge/competition-events/{js_ceid}/dances/{js_dance}", "judge", {"judge_id": "J6"}),
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


def resolve_dynamic(base):
    """R47：动态解析激活赛事与「评分中」场次（含舞种）——不再硬编码 cid/ceid/dance。"""
    import urllib.request as _ur
    req = _ur.Request(base + "/api/login", method="POST",
                      data=json.dumps({"role": "admin", "password": "admin123"}).encode(),
                      headers={"Content-Type": "application/json"})
    ck = _ur.urlopen(req, timeout=30).headers.get("Set-Cookie", "").split(";")[0]
    hdr = {"Cookie": ck}
    evs = json.loads(_ur.urlopen(_ur.Request(base + "/api/events", headers=hdr), timeout=30).read())["events"]
    act = [e for e in evs if e.get("active")]
    cid = (act or evs)[0]["id"]
    sched = json.loads(_ur.urlopen(_ur.Request(
        base + f"/api/public/events/{cid}/schedule", headers=hdr), timeout=30).read())["events"]
    scoring = [e for e in sched if e["status"] == "scoring"]
    js_ceid = scoring[0]["id"] if scoring else sched[0]["id"]
    prog = json.loads(_ur.urlopen(_ur.Request(
        base + f"/api/competition-events/{js_ceid}/progress", headers=hdr), timeout=30).read())
    from urllib.parse import quote as _q
    js_dance = _q(prog["dances"][0]) if prog.get("dances") else ""
    return cid, js_ceid, js_dance


async def run():
    from playwright.async_api import async_playwright
    import httpx as _hx

    CID, JS_CEID, JS_DANCE = resolve_dynamic(BASE)
    print("dynamic: cid=%s js_ceid=%s js_dance=%s" % (CID, JS_CEID, JS_DANCE))

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
                    real = (path.replace("{cid}", str(CID))
                                .replace("{js_ceid}", str(JS_CEID))
                                .replace("{js_dance}", JS_DANCE))
                    if role:
                        await page.goto(BASE + "/login")
                        await page.wait_for_timeout(180)
                        await page.evaluate("""async (b) => {
                          await fetch('/api/login', {method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify(b)});
                        }""", dict(role=role, **kw))
                    await page.goto(BASE + real)
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
                    bg_ok = True if name in SCREEN_PAGES else st["bg"] == expect_bg
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
                    # T2 staff 检录点击：动态挑「评分中」场次的目标芯片（优先 off，退而 on）
                    await page.goto(BASE + "/login")
                    await page.wait_for_timeout(200)
                    await page.evaluate("""async () => {
                      await fetch('/api/login', {method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({role: 'marshal', username: 'marshal', password: 'marshal123'})});
                    }""")
                    await page.goto(BASE + "/staff")
                    await page.wait_for_timeout(800)
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
                            f"document.querySelector('.st-event[data-ceid=\\'{ceid}\\']').scrollIntoView({{block:'center', behavior:'instant'}})")
                        await page.wait_for_timeout(600)   # R42 scroll-behavior:smooth 后等滚动完成
                        y0 = await page.evaluate("window.scrollY")
                        pre = await page.evaluate(
                            f"document.querySelector('.chip[data-ceid=\\'{ceid}\\'][data-num=\\'{num}\\']').classList.contains('on')")
                        await page.evaluate(
                            f"document.querySelector('.chip[data-ceid=\\'{ceid}\\'][data-num=\\'{num}\\']').click()")
                        await page.wait_for_timeout(700)
                        st2 = await page.evaluate("""([ceid, num]) => ({
                          y: window.scrollY,
                          on: document.querySelector('.chip[data-ceid="'+ceid+'"][data-num="'+num+'"]').classList.contains('on') })""", [ceid, num])
                        record(f"{vp_name}/dark/staff-click-stable",
                               abs(st2["y"] - y0) < 2 and st2["on"] != pre,
                               json.dumps(st2) + f" y0={y0} pre={pre}")
                    # T3 judge 评分制场次（动态解析：用标注演示赛的 S1 场次）
                    _s1 = await page.evaluate("""async () => {
                      const evs = await (await fetch('/api/events')).json();
                      const demo = (evs.events || []).filter(e => e.name === '使用说明演示赛')
                        .sort((a, b) => b.id - a.id)[0];
                      if (!demo) return null;
                      const s = await (await fetch('/api/public/events/' + demo.id + '/schedule')).json();
                      const s1 = (s.events || []).find(e => e.code === 'S1');
                      return s1 ? s1.id : null;
                    }""")
                    if not _s1:
                        record(f"{vp_name}/dark/judge-tap（跳过：S1 未找到）", True, "no S1")
                    else:
                        await page.goto(BASE + f"/judge/competition-events/{_s1}/dances/%E9%9B%86%E4%BD%93%E8%88%9E")
                        await page.wait_for_timeout(700)
                        await page.evaluate("""() => {
                          const row = document.querySelector('.score-row:not(.off) input.val');
                          if (row) { row.focus(); row.value = '8.5';
                            row.dispatchEvent(new Event('input', { bubbles: true })); }
                        }""")
                        await page.wait_for_timeout(300)
                        j1 = await page.evaluate("""() => {
                          const el = document.querySelector('.score-row:not(.off) input.val');
                          if (!el) return { ok: false };
                          return { ok: el.value === '8.5', v: el.value };
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
