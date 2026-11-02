# -*- coding: utf-8 -*-
"""R61 全角色全要素 E2E 模拟：一个脚本驱动 9 个浏览器上下文按里程碑时间线并发，
从建赛筹备到比赛收官走完整赛事，并注入 4 类异常处置：

EX1 选手检录未到场   —— P1 预赛 205/206 不检录（结果/晋级不得出现）
EX2 检录后未到场     —— 204 检录后取消（结果/晋级不得出现）
EX3 场次临时变更     —— D3 误开场后「关闭评分」取消（检录台/裁判即时不可评）
EX4 裁判评分作废重算 —— P1F 收齐后「退回评分」（观众页同步隐藏），J1/J3 重交、
                        J2 改判 207/208 重交 → 重算发布 → 验证三裁多数决名次稳定

角色：CA 赛事管理员(桌面，兼向导筹备) / MARSHAL 检录(375) / HOST 主持(375) /
J1 J2 J3 裁判(375) / S1J1~S1J3 集体舞评分(375) / PUBLIC 观众(桌面) / SCREEN 大屏(1920)。
用法：python3 e2e_full_show_r61.py [base=8302]；帧 → /tmp/e2e_show，结果 → results.json
"""
import asyncio, csv, json, os, sys, time
from urllib.parse import quote

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
OUT = "/tmp/e2e_show"
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
R, TL = [], []
BROWSER = None


def log(role, event, ok=True, detail=""):
    t = time.time() - T0
    TL.append({"t": round(t, 1), "role": role, "event": event, "ok": bool(ok), "detail": str(detail)[:160]})
    print(f"[{t:6.1f}s] {'✓' if ok else '✗'} {role} :: {event}" + (f" :: {detail}" if detail else ""), flush=True)


def assert_(role, name, ok, detail=""):
    R.append({"role": role, "name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    log(role, "ASSERT " + name, ok, detail)


MS_NAMES = ["COMP_READY", "SETUP_DONE", "P1_OPEN", "D3_OPENED", "D3_CANCELLED", "CHECKIN_P1", "P1_SCORED",
            "P1_PUBLISHED", "ADV_DONE", "P1F_OPEN", "P1F_CHECKIN", "P1F_SCORED",
            "P1F_RETURNED", "P1F_RESCORED", "P1F_PUBLISHED", "S1_OPEN", "S1_CHECKIN",
            "S1_SCORED", "S1_PUBLISHED", "ALL_DONE"]
MS = {}


def init_milestones():
    """必须在事件循环内调用（Event 绑定当前 loop）。"""
    global MS
    MS = {k: asyncio.Event() for k in MS_NAMES}


def fire(k):
    if k not in MS:
        MS[k] = asyncio.Event()
    MS[k].set()


async def wait(k):
    if k not in MS:
        MS[k] = asyncio.Event()
    await MS[k].wait()


def api(method, path, body=None, cookie=""):
    import urllib.request
    r = urllib.request.Request(BASE + path, method=method)
    if cookie: r.add_header("Cookie", cookie)
    if body is not None:
        r.data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            sc = resp.headers.get("Set-Cookie", "").split(";")[0]
            return resp.status, json.loads(resp.read() or b"{}"), sc
    except urllib.error.HTTPError as e:
        try: d = json.loads(e.read())
        except Exception: d = {}
        return e.code, d, ""


async def shot(page, role, step):
    name = f"{step}_{role}.png"
    await page.screenshot(path=f"{OUT}/{name}")
    log(role, "帧 " + name)


async def comp_login(pg, cid, role, username=None, password=None, judge_id=None):
    await pg.goto(f"{BASE}/competitions/{cid}/login?role={role}")
    await pg.wait_for_timeout(400)
    if judge_id: await pg.fill("#judge_id", judge_id)
    if username: await pg.fill("#username", username)
    if password: await pg.fill("#password", password)
    await pg.click("#btn")
    await pg.wait_for_timeout(900)


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([header] + rows)


async def rank_by_display_order(pg, expect_n, step, role):
    """顺位法：把全部可评行按显示顺序点满并提交，断言排满与成功。"""
    await pg.wait_for_selector(".rank-row:not(.off)", timeout=10000)
    await pg.wait_for_timeout(400)
    n = await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
    assert_(role, step + " 渲染行数>0", n > 0, f"got={n}")
    assert_(role, step + " 可评行数", n == expect_n, f"expect={expect_n} got={n}")
    for i in range(n):
        await pg.evaluate(f"document.querySelectorAll('.rank-row:not(.off)')[{i}].click()")
        await pg.wait_for_timeout(220)
    prog = await pg.evaluate("document.getElementById('progress').textContent")
    assert_(role, step + " 排满", f"{expect_n} / {expect_n}" in prog, prog)
    await pg.evaluate("document.getElementById('submit').click()")
    await pg.wait_for_timeout(900)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    assert_(role, step + " 提交成功", "ok" in msg, msg)


async def role_judge(idx, cid, urls):
    ctx = await BROWSER.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2, locale="zh-CN")
    pg = await ctx.new_page()
    await wait("SETUP_DONE")
    await comp_login(pg, cid, "judge", judge_id=f"J{idx}")
    log(f"J{idx}", "裁判登录")
    # P1 预赛（等检录完成再评分）
    await wait("CHECKIN_P1")
    await pg.goto(BASE + urls["p1"]); await pg.wait_for_timeout(800)
    await rank_by_display_order(pg, 9, "P1顺位法", f"J{idx}")
    await shot(pg, f"J{idx}", "p1-ranked")
    # P1F 决赛
    await wait("P1F_CHECKIN")
    await pg.goto(BASE + urls["p1f"]); await pg.wait_for_timeout(800)
    await rank_by_display_order(pg, 6, "P1F顺位法", f"J{idx}")
    await shot(pg, f"J{idx}", "p1f-ranked")
    fire(f"J{idx}_P1F_DONE")
    # EX4：退回后重交
    await wait("P1F_RETURNED")
    # 产品行为：退回后页面会把 sessionStorage 草稿（旧名次）恢复出来——模拟裁判重新评分先清草稿
    await pg.evaluate("try { sessionStorage.clear() } catch (e) {}")
    await pg.reload(); await pg.wait_for_timeout(900)
    try:
        await pg.wait_for_function(
            "document.getElementById('progress') && document.getElementById('progress').textContent.includes('0 / 6')",
            timeout=8000)
    except Exception:
        pass
    await pg.wait_for_timeout(400)
    if idx == 2:
        # J2 改判：全新排满（207=4、208=5），再点 [207,208,208,207] —— 等效把两者让 208 先行
        await pg.wait_for_selector(".rank-row:not(.off)", timeout=10000)
        await pg.wait_for_timeout(400)
        n2 = await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
        for i in range(n2):
            await pg.evaluate(f"document.querySelectorAll('.rank-row:not(.off)')[{i}].click()")
            await pg.wait_for_timeout(220)
        for sel_seq in (["207", "208"], ["208", "207"]):
            for num in sel_seq:
                await pg.evaluate(f"Array.from(document.querySelectorAll('.rank-row:not(.off)')).find(r => r.dataset.num === '{num}').click()")
                await pg.wait_for_timeout(250)
        prog = await pg.evaluate("document.getElementById('progress').textContent")
        assert_("J2", "EX4 改判后仍排满 6/6", "6 / 6" in prog, prog)
    else:
        await pg.wait_for_selector(".rank-row:not(.off)", timeout=10000)
        await pg.wait_for_timeout(400)
        n = await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
        for i in range(n):
            await pg.evaluate(f"document.querySelectorAll('.rank-row:not(.off)')[{i}].click()")
            await pg.wait_for_timeout(220)
    dbg = await pg.evaluate("""() => ({
      prog: document.getElementById('progress') ? document.getElementById('progress').textContent : 'none',
      assigned: document.querySelectorAll('.rank-row.assigned').length,
      rows: document.querySelectorAll('.rank-row:not(.off)').length,
      mode: (document.querySelector('.mt-btn.active') || {}).textContent || 'none',
      sheet: JSON.stringify(sessionStorage.getItem('sheet:' + CEID + ':' + encodeURIComponent(DANCE)))
    })""")
    log(f"J{idx}", "EX4 重交前现场 " + json.dumps(dbg, ensure_ascii=False))
    await pg.evaluate("document.getElementById('submit').click()")
    await pg.wait_for_timeout(900)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    assert_(f"J{idx}", "EX4 重交成功", "ok" in msg, msg)
    fire(f"J{idx}_RESCORED")
    await shot(pg, f"J{idx}", "p1f-resubmitted")
    # S1 集体舞（同 context 顺序评分，减少并发浏览器占用）
    await wait("S1_OPEN")
    await pg.goto(BASE + urls["s1"]); await pg.wait_for_timeout(900)
    n = await pg.evaluate("document.querySelectorAll('.score-row').length")
    assert_(f"J{idx}", "S1 评分行数 4", n == 4, f"got={n}")
    vals = {"201": 9.5, "202": 9.0, "203": 8.5, "204": 8.0}
    await pg.evaluate("""(vals) => {
      document.querySelectorAll('.score-row').forEach(r => {
        const inp = r.querySelector('input');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(inp, String(vals[r.dataset.num] ?? 8.0));
        inp.dispatchEvent(new Event('input', {bubbles: true}));
        inp.dispatchEvent(new Event('change', {bubbles: true}));
      });
    }""", vals)
    await pg.wait_for_timeout(400)
    prog = await pg.evaluate("document.getElementById('progress').textContent")
    assert_(f"J{idx}", "S1 已填 4/4", "4 / 4" in prog, prog)
    await pg.evaluate("document.getElementById('submit').click()")
    await pg.wait_for_timeout(900)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    assert_(f"J{idx}", "S1 提交成功", "ok" in msg, msg)
    fire(f"S1J{idx}_DONE")
    await shot(pg, f"J{idx}", "s1-scored")
    await pg.close(); await ctx.close()


async def role_marshal(cid):
    ctx = await BROWSER.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2, locale="zh-CN")
    pg = await ctx.new_page()
    await wait("SETUP_DONE")
    await comp_login(pg, cid, "marshal", "show-checkin-01", "ShowCheck2026")
    log("MARSHAL", "检录登录")
    # EX3 前半：先停在 staff 页，D3 误开事件一到立即刷新检查（窗口期内）
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(600)
    await wait("D3_OPENED")
    await pg.reload(); await pg.wait_for_timeout(500)
    d3 = await pg.evaluate("Array.from(document.querySelectorAll('.st-event')).some(c => c.dataset.code === 'D3' && c.dataset.status === 'scoring')")
    assert_("MARSHAL", "EX3 D3 误开期间出现在检录台（评分中）", d3)
    # P1 检录
    await wait("P1_OPEN")
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(900)
    P1 = '.st-event[data-code="P1"]'
    ys = []
    for num in ("201", "202", "203", "204"):
        sel = f'{P1} .chip[data-num="{num}"]'
        await pg.evaluate("sel => document.querySelector(sel).scrollIntoView({block:'center'})", sel)
        await pg.wait_for_timeout(250)
        y0 = await pg.evaluate("window.scrollY")
        await pg.evaluate("sel => document.querySelector(sel).click()", sel)   # 真人轻点：无自动滚动
        await pg.wait_for_timeout(300)
        y1 = await pg.evaluate("window.scrollY")
        ys.append((num, y0, y1))
    assert_("MARSHAL", "连续检录点击滚动稳定", all(abs(b - a) < 3 for _, a, b in ys), str(ys))
    sel204 = f'{P1} .chip[data-num="204"]'
    await pg.evaluate("sel => document.querySelector(sel).scrollIntoView({block:'center'})", sel204)
    await pg.wait_for_timeout(250)
    await pg.evaluate("sel => document.querySelector(sel).click()", sel204)   # EX2 检录后取消
    await pg.wait_for_timeout(500)
    on204 = await pg.evaluate("sel => document.querySelector(sel).classList.contains('on')", sel204)
    assert_("MARSHAL", "EX2 204 检录后取消成功", not on204)
    for num in ("207", "208", "209", "210", "211", "212"):
        await pg.evaluate("sel => document.querySelector(sel).click()", f'{P1} .chip[data-num="{num}"]')
        await pg.wait_for_timeout(250)
    prog = await pg.evaluate("sel => { const c = document.querySelector(sel); return c ? c.textContent : '' }", P1 + " .tag[id^=prog]")
    assert_("MARSHAL", "EX1 P1 检录 9/12（204/205/206 未到场）", "9 / 12" in prog, prog)
    await shot(pg, "MARSHAL", "p1-partial")
    fire("CHECKIN_P1")
    # EX3 后半：D3 关闭后不再是评分中
    await wait("D3_CANCELLED")
    await pg.reload(); await pg.wait_for_timeout(900)
    d3b = await pg.evaluate("Array.from(document.querySelectorAll('.st-event')).some(c => c.dataset.code === 'D3' && c.dataset.status === 'scoring')")
    assert_("MARSHAL", "EX3 关闭后 D3 不再评分中", not d3b)
    # P1F 全员检录
    await wait("P1F_OPEN")
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(900)
    await pg.evaluate("document.querySelector(\".st-event[data-code='P1F'] [data-all]\").click()")
    await pg.wait_for_timeout(800)
    progf = await pg.evaluate("document.querySelector(\".st-event[data-code='P1F'] .tag[id^=prog]\").textContent")
    assert_("MARSHAL", "P1F 全员检录 6/6", "6 / 6" in progf, progf)
    await shot(pg, "MARSHAL", "p1f-all")
    fire("P1F_CHECKIN")
    # S1 检录
    await wait("P1F_PUBLISHED")
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(900)
    await pg.evaluate("document.querySelector(\".st-event[data-code='S1'] [data-all]\").click()")
    await pg.wait_for_timeout(800)
    progs = await pg.evaluate("document.querySelector(\".st-event[data-code='S1'] .tag[id^=prog]\").textContent")
    assert_("MARSHAL", "S1 全员检录 4/4", "4 / 4" in progs, progs)
    fire("S1_CHECKIN")
    await pg.close(); await ctx.close()


async def role_host(cid):
    ctx = await BROWSER.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2, locale="zh-CN")
    pg = await ctx.new_page()
    await wait("SETUP_DONE")
    await comp_login(pg, cid, "host", "show-host-01", "ShowHost2026")
    log("HOST", "主持登录")
    await wait("P1F_PUBLISHED")
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(1000)
    card = pg.locator(".done-card", has_text="P1F").first
    await card.scroll_into_view_if_needed(); await pg.wait_for_timeout(300)
    title = await pg.evaluate("""() => {
      const c = Array.from(document.querySelectorAll('.done-card')).find(x => x.textContent.includes('P1F'));
      const b = c && c.querySelector('.toggle-done');
      if (b) b.click();
      return c ? (c.querySelector('h3') || {}).textContent || c.textContent.slice(0, 30) : 'no-card'; }""")
    await pg.wait_for_timeout(700)
    body = await pg.evaluate("""() => {
      const c = Array.from(document.querySelectorAll('.done-card')).find(x => x.textContent.includes('P1F'));
      const b = c && c.querySelector('.done-body.open');
      return b ? {rows: b.querySelectorAll('tbody tr').length, title: (c.querySelector('h3') || {}).textContent} : null; }""")
    assert_("HOST", "P1F 公告原位展开（定位 P1F 卡）", bool(body) and body["rows"] >= 6 and "决赛" in (body.get("title") or ""),
            json.dumps(body, ensure_ascii=False))
    await shot(pg, "HOST", "p1f-announce")
    await pg.evaluate("""() => {
      const c = Array.from(document.querySelectorAll('.done-card')).find(x => x.textContent.includes('P1F'));
      const b = c && c.querySelector('.ann-btn');
      if (b) b.click(); }""")
    await pg.wait_for_timeout(700)
    ann = await pg.evaluate("""() => {
      const c = Array.from(document.querySelectorAll('.done-card')).find(x => x.textContent.includes('P1F'));
      const b = c && c.querySelector('.ann-btn');
      return b ? b.textContent : ''; }""")
    assert_("HOST", "标记已播报翻转", "取消播报" in ann, ann)
    await shot(pg, "HOST", "p1f-announced")
    fire("ANNOUNCED")
    await wait("S1_PUBLISHED")
    await pg.reload(); await pg.wait_for_timeout(1000)
    await pg.evaluate("(() => { const b = document.querySelector('.toggle-done'); if (b) b.click(); })()")
    await pg.wait_for_timeout(600)
    await shot(pg, "HOST", "s1-announce")
    await pg.close(); await ctx.close()


async def role_public(cid):
    ctx = await BROWSER.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    pg = await ctx.new_page()
    await wait("P1F_RETURNED")
    await pg.goto(BASE + "/public/results"); await pg.wait_for_timeout(900)
    hidden = await pg.evaluate("!document.body.textContent.includes('标准舞决赛')")
    assert_("PUBLIC", "EX4 退回后 P1F 成绩同步隐藏", hidden)
    await shot(pg, "PUBLIC", "ex4-hidden")
    await wait("P1F_PUBLISHED")
    await pg.goto(BASE + "/public/results"); await pg.wait_for_timeout(1000)
    vis = await pg.evaluate("document.body.textContent.includes('标准舞决赛')")
    assert_("PUBLIC", "重发后 P1F 成绩可见", vis)
    lk = await pg.evaluate(f"""fetch('/api/public/events/{cid}/lookup?num=201').then(x=>x.json())
      .then(r => JSON.stringify((r.published_results||[]).map(x=>x.name)))""")
    assert_("PUBLIC", "背番号 201 查询含 P1/P1F", "标准舞预赛" in lk and "标准舞决赛" in lk, lk[:120])
    await shot(pg, "PUBLIC", "p1f-results")
    await wait("S1_PUBLISHED")
    await pg.goto(BASE + "/public/results"); await pg.wait_for_timeout(1000)
    st = await pg.evaluate("document.body.textContent.includes('团体总分')")
    assert_("PUBLIC", "团体总分榜可见", st)
    await shot(pg, "PUBLIC", "standings")
    await pg.close(); await ctx.close()


async def role_screen(cid):
    ctx = await BROWSER.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
    pg = await ctx.new_page()
    await pg.goto(BASE + "/screen"); await pg.wait_for_timeout(1200)
    await shot(pg, "SCREEN", "welcome")
    await wait("P1_PUBLISHED")
    s = await pg.evaluate(f"fetch('/api/public/events/{cid}/screen-state').then(r=>r.json())")
    pub = [x.get("code") for x in s.get("published_results", [])]
    assert_("SCREEN", "大屏状态含已发布 P1", "P1" in pub, str(pub))
    await wait("P1F_PUBLISHED")
    await pg.reload(); await pg.wait_for_timeout(1500)
    s = await pg.evaluate(f"fetch('/api/public/events/{cid}/screen-state').then(r=>r.json())")
    pub = [x.get("code") for x in s.get("published_results", [])]
    assert_("SCREEN", "大屏状态含 P1F", "P1F" in pub, str(pub))
    await shot(pg, "SCREEN", "results")
    await pg.close(); await ctx.close()


async def role_ca(cid):
    """赛事管理员：向导筹备 → 控制台全程 → 异常处置 → 收官。"""
    ctx = await BROWSER.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    ctx.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
    pg = await ctx.new_page()
    await comp_login(pg, cid, "admin", "show-org", "ShowOrg2026")
    log("CA", "登录落点 " + pg.url)

    # ---- 向导：选手 / 裁判 / 赛程 / 工作人员 ----
    write_csv("/tmp/r61_comp.csv", ["背番号", "项目编号", "姓名", "学校/单位"],
              [[n, "P1", f"选手{n}", "单位A" if int(n) <= 206 else "单位B"] for n in range(201, 213)])
    write_csv("/tmp/r61_judges.csv", ["裁判ID", "姓名"], [[f"J{i}", f"裁判{i}"] for i in (1, 2, 3)])
    write_csv("/tmp/r61_sched.csv",
              ["场次编号", "场次名称", "项目编号", "轮次", "舞种", "评分类型", "晋级人数", "参赛选手"],
              [["P1", "标准舞预赛", "P1", "1", "华尔兹", "SKATING", "6", ",".join(str(n) for n in range(201, 213))],
               ["P1F", "标准舞决赛", "P1", "2", "华尔兹", "SKATING", "0", "201,202,203,207,208,209"],
               ["S1", "集体舞决赛", "S1", "1", "集体舞", "SCORE", "0", "201,202,203,204"],
               ["D3", "拉丁加赛", "D3", "1", "恰恰", "SKATING", "0", "201,202,203,204"]])
    kind_step = {"competitors": 2, "judges": 3, "schedule": 4}
    for kind, path in (("competitors", "/tmp/r61_comp.csv"), ("judges", "/tmp/r61_judges.csv"), ("schedule", "/tmp/r61_sched.csv")):
        await pg.click(f'[data-go="{kind_step[kind]}"]'); await pg.wait_for_timeout(250)
        await pg.set_input_files(f'.wiz-file[data-kind="{kind}"]', path)
        await pg.click(f'.wiz-upload-btn[data-kind="{kind}"]')
        await pg.wait_for_timeout(1000)
        r = await pg.evaluate(f"document.querySelector('.wiz-result[data-kind=\\'{kind}\\']').textContent")
        assert_("CA", f"向导导入 {kind}", "导入成功" in r, r)
    await pg.click('[data-go="5"]'); await pg.wait_for_timeout(300)
    await pg.select_option("#s-role", "marshal")
    await pg.fill("#s-username", "show-checkin-01"); await pg.fill("#s-display", "模拟检录员")
    await pg.fill("#s-password", "ShowCheck2026"); await pg.click("#s-create"); await pg.wait_for_timeout(700)
    await pg.select_option("#s-role", "host")
    await pg.fill("#s-username", "show-host-01"); await pg.fill("#s-display", "模拟主持")
    await pg.fill("#s-password", "ShowHost2026"); await pg.click("#s-create"); await pg.wait_for_timeout(700)
    staff_rows = await pg.evaluate("document.querySelectorAll('#s-rows tr').length")
    assert_("CA", "向导创建检录+主持账号", staff_rows >= 2, f"rows={staff_rows}")
    await pg.click('[data-go="6"]'); await pg.wait_for_timeout(400)
    await pg.click("#wiz-finish"); await pg.wait_for_timeout(1100)
    log("CA", "向导完成，落点 " + pg.url)
    fire("SETUP_DONE")
    # 取赛程映射（向导已导入）
    while True:
        _, dsch, _ = api("GET", f"/api/public/events/{cid}/schedule")
        ids = {e["code"]: e["id"] for e in dsch.get("events", [])}
        if {"P1", "P1F", "S1", "D3"} <= set(ids):
            break
        await asyncio.sleep(0.5)

    # ---- 开 P1 ----
    await pg.goto(BASE + f"/events/{cid}/console/{ids['P1']}"); await pg.wait_for_timeout(900)
    await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(1000)
    st = await pg.evaluate("document.getElementById('status').textContent")
    assert_("CA", "P1 一键开启评分", "评分中" in st, st)
    fire("P1_OPEN")
    # ---- EX3：D3 误开 → 关闭 ----
    await pg.goto(BASE + f"/events/{cid}/console/{ids['D3']}"); await pg.wait_for_timeout(800)
    await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(800)
    fire("D3_OPENED")
    await asyncio.sleep(2.2)   # 给检录台留出「误开可见」窗口
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='closeEvent()']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(900)
    st = await pg.evaluate("document.getElementById('status').textContent")
    assert_("CA", "EX3 D3 误开后关闭评分", "待开始" in st or "未开始" in st, st)
    fire("D3_CANCELLED")
    # ---- 等 P1 三裁收齐 → 发布 P1 ----
    while True:
        _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
        p1 = next((e for e in dpub.get("events", []) if e["code"] == "P1"), {})
        if p1.get("status") in ("calculated", "published"):
            break
        await asyncio.sleep(1.2)
    log("CA", "P1 三裁收齐已自动计算")
    fire("P1_SCORED")
    await pg.goto(BASE + f"/events/{cid}/results"); await pg.wait_for_timeout(1200)
    await pg.locator(f'.card[data-ceid="{ids["P1"]}"] button', has_text="发布（进大屏）").click()
    await pg.wait_for_timeout(1100)
    _, dres, _ = api("GET", f"/api/public/events/{cid}/results")
    codes = [x.get("code") for x in dres.get("results", [])]
    assert_("CA", "P1 发布进公开页", "P1" in codes, str(codes))
    body = json.dumps(dres.get("results", []), ensure_ascii=False)
    assert_("CA", "EX1/EX2 未到场 204/205/206 不在成绩", all(f'"{n}"' not in body for n in ("204", "205", "206")))
    await shot(pg, "CA", "p1-published")
    fire("P1_PUBLISHED")
    # ---- 晋级确认 → 回填 ----
    await pg.goto(BASE + f"/events/{cid}/advancement?project=P1&round=1"); await pg.wait_for_timeout(1100)
    await pg.click("text=生成预案"); await pg.wait_for_timeout(900)
    nums = await pg.evaluate("Array.from(document.querySelectorAll('.adv-check')).map(c => c.dataset.num)")
    assert_("CA", "晋级预案恰为到场前 6", set(nums) == {"201", "202", "203", "207", "208", "209"}, str(nums))
    await pg.click("#confirm-btn"); await pg.wait_for_timeout(1100)
    fire("ADV_DONE")
    # ---- 开 P1F ----
    await pg.goto(BASE + f"/events/{cid}/console/{ids['P1F']}"); await pg.wait_for_timeout(900)
    await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(900)
    fire("P1F_OPEN")
    # ---- EX4：P1F 收齐 → 退回评分 ----
    while True:
        _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
        p1f = next((e for e in dpub.get("events", []) if e["code"] == "P1F"), {})
        if p1f.get("status") in ("calculated", "published"):
            break
        await asyncio.sleep(1.2)
    fire("P1F_SCORED")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='returnScores()']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(1000)
    st = await pg.evaluate("document.getElementById('status').textContent")
    assert_("CA", "EX4 退回评分（作废全部评分）", "评分中" in st, st)
    fire("P1F_RETURNED")
    for k in ("J1_RESCORED", "J2_RESCORED", "J3_RESCORED"):
        await wait(k)
    log("CA", "EX4 三裁已重交")
    fire("P1F_RESCORED")
    await pg.reload(); await pg.wait_for_timeout(900)
    await pg.goto(BASE + f"/events/{cid}/results"); await pg.wait_for_timeout(1100)
    await pg.locator(f'.card[data-ceid="{ids["P1F"]}"] button', has_text="发布（进大屏）").click()
    await pg.wait_for_timeout(1100)
    _, dres, _ = api("GET", f"/api/public/events/{cid}/results")
    p1f = next((x for x in dres.get("results", []) if x.get("code") == "P1F"), None)
    ranks = {r.get("competitor_number"): r.get("rank") for r in (p1f or {}).get("overall", [])}
    assert_("CA", "EX4 多数决：207 仍先于 208",
            int(ranks.get("207", 99)) < int(ranks.get("208", 99)), json.dumps(ranks, ensure_ascii=False))
    await shot(pg, "CA", "p1f-published")
    fire("P1F_PUBLISHED")
    # ---- S1 集体舞 ----
    await wait("S1_CHECKIN")
    await pg.goto(BASE + f"/events/{cid}/console/{ids['S1']}"); await pg.wait_for_timeout(900)
    await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(900)
    st = await pg.evaluate("document.getElementById('status').textContent")
    assert_("CA", "S1 开启评分", "评分中" in st, st)
    fire("S1_OPEN")
    for k in ("S1J1_DONE", "S1J2_DONE", "S1J3_DONE"):
        await wait(k)
    fire("S1_SCORED")
    await pg.goto(BASE + f"/events/{cid}/results"); await pg.wait_for_timeout(1100)
    await pg.locator(f'.card[data-ceid="{ids["S1"]}"] button', has_text="发布（进大屏）").click()
    await pg.wait_for_timeout(1100)
    _, dres, _ = api("GET", f"/api/public/events/{cid}/results")
    codes = [x.get("code") for x in dres.get("results", [])]
    assert_("CA", "S1 发布；P1/P1F/S1 全在", {"P1", "P1F", "S1"} <= set(codes), str(codes))
    fire("S1_PUBLISHED")
    _, dall, _ = api("GET", f"/api/public/events/{cid}/schedule")
    evs = dall.get("events", [])
    done = [e.get("code") for e in evs if e.get("code") in ("P1", "P1F", "S1") and e.get("status") == "published"]
    assert_("CA", "全赛事收官：三场全部已发布", len(done) == 3, str(done))
    await shot(pg, "CA", "final")
    fire("ALL_DONE")
    await pg.close(); await ctx.close()


def guarded(coro):
    """任务异常必须留日志，不让静默死亡拖垮全局时间线。"""
    name = coro.__name__

    async def wrap():
        try:
            await coro
        except Exception as e:
            log("TASK", f"{name} 异常 {type(e).__name__}: {str(e)[:140]}", ok=False)
    return wrap()


async def main():
    global BROWSER
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        BROWSER = await p.chromium.launch()
        init_milestones()

        code, d, ck = api("POST", "/api/login", {"role": "admin", "password": "admin123"})
        assert_("SUPER", "总管理员登录", code == 200)
        code, d, _ = api("POST", "/api/events", {"name": "R61全要素模拟赛", "date": "2026-11-08", "location": "模拟馆"}, cookie=ck)
        cid = d.get("id")
        code, d, _ = api("POST", f"/api/events/{cid}/activate", {}, cookie=ck)   # API 建赛不会自动激活
        assert_("SUPER", "建赛并激活", bool(cid) and code in (200, 201), f"cid={cid} activate={code}")
        # 同建赛事管理员账号（UI 表单会一并创建，API 建赛需单独建）
        code, d, _ = api("POST", "/api/users", {"username": "show-org", "display_name": "模拟赛事管理员",
                                                 "role": "compadmin", "competition_id": cid, "password": "ShowOrg2026"}, cookie=ck)
        assert_("SUPER", "同建赛事管理员账号", code in (200, 201), f"code={code} {str(d)[:80]}")
        fire("COMP_READY")

        # CA 先行（向导筹备会导入赛程）；其余角色等 SETUP_DONE 再启动
        async def ca_safe():
            try:
                await role_ca(cid)
            except Exception:
                import traceback
                tb = traceback.format_exc().strip().split("\n")
                log("CA", "异常 " + " || ".join(tb[-3:]), ok=False)
        ca_task = asyncio.create_task(ca_safe())
        await wait("SETUP_DONE")
        _, dsch, _ = api("GET", f"/api/public/events/{cid}/schedule")
        idmap = {e["code"]: e["id"] for e in dsch.get("events", [])}
        assert_("SUPER", "赛程四场就绪", {"P1", "P1F", "S1", "D3"} <= set(idmap), str(idmap))
        urls = {
            "p1": f"/judge/competition-events/{idmap['P1']}/dances/{quote('华尔兹')}",
            "p1f": f"/judge/competition-events/{idmap['P1F']}/dances/{quote('华尔兹')}",
            "s1": f"/judge/competition-events/{idmap['S1']}/dances/{quote('集体舞')}",
        }
        # 把 urls 补给 CA（闭包参数在函数体内不再使用，占位即可）
        tasks = [ca_task,
                 asyncio.create_task(guarded(role_marshal(cid))),
                 asyncio.create_task(guarded(role_host(cid))),
                 asyncio.create_task(guarded(role_public(cid))),
                 asyncio.create_task(guarded(role_screen(cid)))]
        for i in (1, 2, 3):
            tasks.append(asyncio.create_task(guarded(role_judge(i, cid, urls))))

        try:
            await asyncio.wait_for(wait("ALL_DONE"), timeout=240)
        except asyncio.TimeoutError:
            log("MAIN", "全局超时 240s，输出部分结果", ok=False)
        await asyncio.sleep(1.5)
        for t in tasks:
            t.cancel()

    fails = [r for r in R if not r["ok"]]
    print(f"\n===== R61 结果: {len(R)-len(fails)}/{len(R)} PASS · 时间线 {len(TL)} 步 · 全程 {time.time()-T0:.0f}s =====", flush=True)
    for f in fails:
        print("FAIL:", f["role"], f["name"], "::", f["detail"], flush=True)
    json.dump({"asserts": R, "timeline": TL}, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
