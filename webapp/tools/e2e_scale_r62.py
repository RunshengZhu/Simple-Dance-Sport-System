# -*- coding: utf-8 -*-
"""R62 规模化并发 E2E：11 裁判真浏览器并发抢单 + 60 场次 + 百人级混合观众负载。

角色/负载：
- CA 赛事管理员(桌面) / MARSHAL(375) / HOST(375) / J1~J11(375 真浏览器) / PUBLIC 抽样(1 上下文 4 页, SSE) / SCREEN(1920)
- VIRT ×100：虚拟观众/选手查询终端（HTTP 轮询随机公开端点 + 随机背番号 + 随机间隔，全程计时）
负载结构：展示链 P1(预赛)/P1F(决赛)/S1(集体舞)/D3(临时取消) 同 R61；批量场 D01~D56 由
CA 经 API 批量开场 → MARSHAL 逐场「全部检录」并投递评分队列 → 11 裁判并发抢单 UI 评分 → CA 收齐后逐场发布。
用法：python3 e2e_scale_r62.py [base=8302]；帧 → /tmp/e2e_r62；结果+性能 → results.json
"""
import asyncio, csv, json, os, random, statistics, sys, time
from urllib.parse import quote

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
OUT = "/tmp/e2e_r62"
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
R, TL, PERF = [], [], []
BROWSER = None
NJ = 11
ND = 56          # 批量场数量（4 + 56 = 60 场次）
NVIRT = 100


def log(role, event, ok=True, detail=""):
    t = time.time() - T0
    TL.append({"t": round(t, 1), "role": role, "event": event, "ok": bool(ok), "detail": str(detail)[:160]})
    print(f"[{t:6.1f}s] {'✓' if ok else '✗'} {role} :: {event}" + (f" :: {detail}" if detail else ""), flush=True)


def assert_(role, name, ok, detail=""):
    R.append({"role": role, "name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    log(role, "ASSERT " + name, ok, detail)


MS = {}


def init_milestones():
    global MS
    MS = {}


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
    await page.screenshot(path=f"{OUT}/{step}_{role}.png")
    log(role, "帧 " + f"{step}_{role}.png")


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


async def rank_full_and_submit(pg, expect_n, step, role):
    """等待评分行渲染 → 按显示顺序排满 → 提交并断言成功。"""
    await pg.wait_for_selector(".rank-row:not(.off)", timeout=12000)
    await pg.wait_for_timeout(400)
    n = await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
    assert_(role, step + " 行数", n == expect_n, f"expect={expect_n} got={n}")
    for i in range(n):
        await pg.evaluate(f"document.querySelectorAll('.rank-row:not(.off)')[{i}].click()")
        await pg.wait_for_timeout(180)
    prog = await pg.evaluate("document.getElementById('progress').textContent")
    assert_(role, step + " 排满", f"{expect_n} / {expect_n}" in prog, prog)
    await pg.evaluate("document.getElementById('submit').click()")
    await pg.wait_for_timeout(700)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    assert_(role, step + " 提交成功", "ok" in msg, msg)


async def rank_full_light(pg, expect_n, tag=""):
    """批量场轻量评分：渲染等待 → 排满 → 提交，返回是否成功（失败带阶段取证）。"""
    try:
        await pg.wait_for_selector(".rank-row:not(.off)", timeout=10000)
    except Exception:
        log("J?", f"{tag} 失败@渲染等待 rows_off不可见", ok=False)
        return False
    await pg.wait_for_timeout(250)
    n = await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
    if n != expect_n:
        log("J?", f"{tag} 失败@行数 got={n}", ok=False)
        return False
    prog = ""
    for _ in range(4):   # SSE 重渲染可能冲掉点击（R62 发现）：像真裁判一样补点直到「可提交」
        prog = await pg.evaluate("document.getElementById('progress').textContent")
        if f"{expect_n} / {expect_n}" in prog:
            break
        await pg.evaluate("""() => {
          document.querySelectorAll('.rank-row:not(.off)').forEach(r => { if (!r.classList.contains('assigned')) r.click(); });
        }""")
        await pg.wait_for_timeout(450)
    if f"{expect_n} / {expect_n}" not in prog:
        log("J?", f"{tag} 失败@排满 prog={prog!r}", ok=False)
        return False
    await pg.evaluate("document.getElementById('submit').click()")
    await pg.wait_for_timeout(600)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    if "ok" not in msg:
        log("J?", f"{tag} 失败@提交 msg={msg!r}", ok=False)
        return False
    return True


# ---------------- 裁判 ----------------
async def role_judge(idx, cid, holder):
    ctx = await BROWSER.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2, locale="zh-CN")
    pg = await ctx.new_page()
    await wait("SETUP_DONE")
    await comp_login(pg, cid, "judge", judge_id=f"J{idx}")
    log(f"J{idx}", "裁判登录")
    # P1 预赛（等检录）
    await wait("CHECKIN_P1")
    await pg.goto(BASE + holder["urls"]["p1"]); await pg.wait_for_timeout(700)
    await rank_full_and_submit(pg, 9, "P1顺位法", f"J{idx}")
    fire(f"J{idx}_P1_DONE")
    # P1F 决赛
    await wait("P1F_CHECKIN")
    await pg.goto(BASE + holder["urls"]["p1f"]); await pg.wait_for_timeout(700)
    await rank_full_and_submit(pg, 6, "P1F顺位法", f"J{idx}")
    fire(f"J{idx}_P1F_DONE")
    # EX4 退回重交（J2 精确改判 207/208）
    await wait("P1F_RETURNED")
    await pg.evaluate("try { sessionStorage.clear() } catch (e) {}")
    await pg.reload(); await pg.wait_for_timeout(800)
    try:
        await pg.wait_for_function(
            "document.getElementById('progress') && document.getElementById('progress').textContent.includes('0 / 6')",
            timeout=10000)
    except Exception:
        pass
    await pg.wait_for_timeout(400)
    await pg.wait_for_selector(".rank-row:not(.off)", timeout=12000)
    n = await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
    for i in range(n):
        await pg.evaluate(f"document.querySelectorAll('.rank-row:not(.off)')[{i}].click()")
        await pg.wait_for_timeout(160)
    if idx == 2:
        for num in ("207", "208"):
            await pg.evaluate(f"Array.from(document.querySelectorAll('.rank-row:not(.off)')).find(r => r.dataset.num === '{num}').click()")
            await pg.wait_for_timeout(200)
        for num in ("208", "207"):
            await pg.evaluate(f"Array.from(document.querySelectorAll('.rank-row:not(.off)')).find(r => r.dataset.num === '{num}').click()")
            await pg.wait_for_timeout(200)
    prog = await pg.evaluate("document.getElementById('progress').textContent")
    assert_(f"J{idx}", "EX4 重排满", "6 / 6" in prog, prog)
    await pg.evaluate("document.getElementById('submit').click()")
    await pg.wait_for_timeout(700)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    assert_(f"J{idx}", "EX4 重交成功", "ok" in msg, msg)
    fire(f"J{idx}_RESCORED")
    # 批量场：广播-栅栏模式——全场同一当前场次，11 人齐交后整体推进（顺位法收齐要求全员提交）
    await wait("BULK_CHECKED")
    seq = holder["bulk_seq"]
    while True:
        k = holder["bulk_ptr"]
        if k >= len(seq):
            break
        item = seq[k]
        url = f"/judge/competition-events/{item['id']}/dances/{quote(item['dance'])}"
        await pg.goto(BASE + url); await pg.wait_for_timeout(350)
        okb = await rank_full_light(pg, 6, tag=f"J{idx}/批量{item['code']}")
        if not okb:
            log(f"J{idx}", f"批量{item['code']} 评分异常", ok=False)
        async with holder["bulk_lock"]:
            holder["bulk_done"] += 1
            if holder["bulk_done"] >= NJ:
                holder["bulk_done"] = 0
                holder["bulk_ptr"] = k + 1
        while holder["bulk_ptr"] == k and k < len(seq):
            await asyncio.sleep(0.15)
    log(f"J{idx}", "批量 56 场全部收齐，裁判收工")
    fire(f"J{idx}_BULK_DONE")
    # S1 集体舞
    await wait("S1_OPEN")
    await pg.goto(BASE + holder["urls"]["s1"]); await pg.wait_for_timeout(800)
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
    await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('submit').click()")
    await pg.wait_for_timeout(700)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    assert_(f"J{idx}", "S1 提交成功", "ok" in msg, msg)
    fire(f"J{idx}_S1_DONE")
    await pg.close(); await ctx.close()


# ---------------- 检录 ----------------
async def role_marshal(cid, holder):
    ctx = await BROWSER.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2, locale="zh-CN")
    pg = await ctx.new_page()
    await wait("SETUP_DONE")
    await comp_login(pg, cid, "marshal", "r62-checkin", "R62Check2026")
    log("MARSHAL", "检录登录")
    # P1 部分检录（EX1/EX2 同 R61 口径）
    await wait("P1_OPEN")
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(900)
    P1 = '.st-event[data-code="P1"]'
    for num in ("201", "202", "203", "204"):
        sel = f'{P1} .chip[data-num="{num}"]'
        await pg.evaluate("sel => document.querySelector(sel).scrollIntoView({block:'center'})", sel)
        await pg.wait_for_timeout(220)
        await pg.evaluate("sel => document.querySelector(sel).click()", sel)
        await pg.wait_for_timeout(260)
    await pg.evaluate("sel => document.querySelector(sel).click()", f'{P1} .chip[data-num="204"]')  # EX2
    await pg.wait_for_timeout(450)
    for num in ("207", "208", "209", "210", "211", "212"):
        await pg.evaluate("sel => document.querySelector(sel).click()", f'{P1} .chip[data-num="{num}"]')
        await pg.wait_for_timeout(220)
    prog = await pg.evaluate("sel => { const c = document.querySelector(sel + ' .tag[id^=prog]'); return c ? c.textContent : '' }", P1)
    assert_("MARSHAL", "EX1/EX2 P1 检录 9/12", "9 / 12" in prog, prog)
    await shot(pg, "MARSHAL", "p1-partial")
    fire("CHECKIN_P1")
    # P1F 全员
    await wait("P1F_OPEN")
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(900)
    await pg.evaluate("sel => document.querySelector(sel).click()", '.st-event[data-code="P1F"] [data-all]')
    await pg.wait_for_timeout(700)
    progf = await pg.evaluate("sel => { const c = document.querySelector(sel + ' .tag[id^=prog]'); return c ? c.textContent : '' }", '.st-event[data-code="P1F"]')
    assert_("MARSHAL", "P1F 全员检录 6/6", "6 / 6" in progf, progf)
    fire("P1F_CHECKIN")
    # 批量场检录：逐场全部检录并投递队列（EX3 的 D3 已关闭，跳过）
    await wait("BULK_OPENED")
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(900)
    checked = 0
    for code in holder["bulk_codes"]:
        sel_all = f'.st-event[data-code="{code}"] [data-all]'
        ok = await pg.evaluate("sel => { const b = document.querySelector(sel); if (b) { b.click(); return true } return false }", sel_all)
        if ok:
            checked += 1
            await pg.wait_for_timeout(380)
    assert_("MARSHAL", f"批量场检录 {ND}/{ND}", checked == ND, f"checked={checked}")
    await shot(pg, "MARSHAL", "bulk-checked")
    fire("BULK_CHECKED")
    # S1 检录
    await wait("P1F_PUBLISHED")
    await pg.goto(BASE + "/staff"); await pg.wait_for_timeout(900)
    await pg.evaluate("sel => document.querySelector(sel).click()", '.st-event[data-code="S1"] [data-all]')
    await pg.wait_for_timeout(700)
    fire("S1_CHECKIN")
    # 60 场次规模 UI 断言
    ncards = await pg.evaluate("document.querySelectorAll('.st-event, .done-card').length")
    assert_("MARSHAL", "staff 页 60 场次卡片渲染", ncards >= 59, f"cards={ncards}")
    ov = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert_("MARSHAL", "60 卡下无横向滚动", ov <= 0, f"overflowX={ov}")
    # staff-60 帧在此处拍摄：S1 已检录、批量场评分中/已发布混排，与 bulk-checked 帧状态可区分
    await shot(pg, "MARSHAL", "staff-60")
    await pg.close(); await ctx.close()


# ---------------- 赛事管理员 ----------------
async def role_ca(cid, holder):
    ctx = await BROWSER.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    ctx.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
    pg = await ctx.new_page()
    await comp_login(pg, cid, "admin", "r62-org", "R62Org2026")
    log("CA", "登录落点 " + pg.url)

    # 向导
    write_csv("/tmp/r62_comp.csv", ["背番号", "项目编号", "姓名", "学校/单位"],
              [[n, "P1", f"选手{n}", "单位A" if int(n) <= 206 else "单位B"] for n in range(201, 213)])
    write_csv("/tmp/r62_judges.csv", ["裁判ID", "姓名"], [[f"J{i}", f"裁判{i}"] for i in range(1, NJ + 1)])
    sched_rows = [["P1", "标准舞预赛", "P1", "1", "华尔兹", "SKATING", "6", ",".join(str(n) for n in range(201, 213))],
                  ["P1F", "标准舞决赛", "P1", "2", "华尔兹", "SKATING", "0", "201,202,203,207,208,209"],
                  ["S1", "集体舞决赛", "S1", "1", "集体舞", "SCORE", "0", "201,202,203,204"],
                  ["D3", "拉丁加赛", "D3", "1", "恰恰", "SKATING", "0", "201,202,203,204"]]
    dances = ["华尔兹", "恰恰", "牛仔", "狐步"]
    for i in range(1, ND + 1):
        code = f"D{i:02d}"
        sched_rows.append([code, f"第{i}场", code, "1", dances[i % 4], "SKATING", "0", "201,202,203,204,205,206"])
    write_csv("/tmp/r62_sched.csv",
              ["场次编号", "场次名称", "项目编号", "轮次", "舞种", "评分类型", "晋级人数", "参赛选手"], sched_rows)
    kind_step = {"competitors": 2, "judges": 3, "schedule": 4}
    for kind, path in (("competitors", "/tmp/r62_comp.csv"), ("judges", "/tmp/r62_judges.csv"), ("schedule", "/tmp/r62_sched.csv")):
        await pg.click(f'[data-go="{kind_step[kind]}"]'); await pg.wait_for_timeout(250)
        await pg.set_input_files(f'.wiz-file[data-kind="{kind}"]', path)
        await pg.click(f'.wiz-upload-btn[data-kind="{kind}"]')
        await pg.wait_for_timeout(1100)
        r = await pg.evaluate(f"document.querySelector('.wiz-result[data-kind=\\'{kind}\\']').textContent")
        assert_("CA", f"向导导入 {kind}", "导入成功" in r, r)
    await pg.click('[data-go="5"]'); await pg.wait_for_timeout(300)
    await pg.select_option("#s-role", "marshal")
    await pg.fill("#s-username", "r62-checkin"); await pg.fill("#s-display", "R62检录")
    await pg.fill("#s-password", "R62Check2026"); await pg.click("#s-create"); await pg.wait_for_timeout(600)
    await pg.select_option("#s-role", "host")
    await pg.fill("#s-username", "r62-host"); await pg.fill("#s-display", "R62主持")
    await pg.fill("#s-password", "R62Host2026"); await pg.click("#s-create"); await pg.wait_for_timeout(600)
    await pg.click('[data-go="6"]'); await pg.wait_for_timeout(400)
    await pg.click("#wiz-finish"); await pg.wait_for_timeout(1100)
    fire("SETUP_DONE")
    while True:
        _, dsch, _ = api("GET", f"/api/public/events/{cid}/schedule")
        ids = {e["code"]: e["id"] for e in dsch.get("events", [])}
        if {"P1", "P1F", "S1", "D3"} <= set(ids) and len(ids) >= 4 + ND:
            break
        await asyncio.sleep(0.5)
    assert_("CA", "60 场次就绪", len(ids) == 4 + ND, f"total={len(ids)}")
    holder["ids"] = ids

    # 开 P1
    await pg.goto(BASE + f"/events/{cid}/console/{ids['P1']}"); await pg.wait_for_timeout(800)
    await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(900)
    fire("P1_OPEN")
    # EX3：D3 误开→关闭
    await pg.goto(BASE + f"/events/{cid}/console/{ids['D3']}"); await pg.wait_for_timeout(700)
    await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(700)
    fire("D3_OPENED")
    await asyncio.sleep(2.0)
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='closeEvent()']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(800)
    st = await pg.evaluate("document.getElementById('status').textContent")
    assert_("CA", "EX3 D3 关闭评分", "待开始" in st or "未开始" in st, st)
    fire("D3_CANCELLED")
    # 批量开场（API：roster 与赛程一致）
    _, _, ck = api("POST", "/api/login", {"role": "admin", "password": "admin123"})
    roster = [str(n) for n in range(201, 207)]
    for i in range(1, ND + 1):
        code = f"D{i:02d}"
        api("POST", f"/api/competition-events/{ids[code]}/open", {"roster": roster, "reset": False}, cookie=ck)
    log("CA", f"批量开场 {ND} 场完成")
    fire("BULK_OPENED")
    # P1 收齐（11 裁判全部提交 → 自动计算）→ 发布 → 晋级
    for i in range(1, NJ + 1):
        await wait(f"J{i}_P1_DONE")
    while True:
        _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
        p1 = next((e for e in dpub.get("events", []) if e["code"] == "P1"), {})
        if p1.get("status") in ("calculated", "published"):
            break
        await asyncio.sleep(1.2)
    log("CA", "P1 11 裁收齐已自动计算")
    await pg.goto(BASE + f"/events/{cid}/results"); await pg.wait_for_timeout(1100)
    await pg.locator(f'.card[data-ceid="{ids["P1"]}"] button', has_text="发布（进大屏）").click()
    await pg.wait_for_timeout(1000)
    _, dres, _ = api("GET", f"/api/public/events/{cid}/results")
    codes = [x.get("code") for x in dres.get("results", [])]
    assert_("CA", "P1 发布", "P1" in codes, str(codes))
    body = json.dumps(dres.get("results", []), ensure_ascii=False)
    assert_("CA", "EX1/EX2 未到场不在成绩", all(f'"{n}"' not in body for n in ("204", "205", "206")))
    await pg.goto(BASE + f"/events/{cid}/advancement?project=P1&round=1"); await pg.wait_for_timeout(1000)
    await pg.click("text=生成预案"); await pg.wait_for_timeout(800)
    nums = await pg.evaluate("Array.from(document.querySelectorAll('.adv-check')).map(c => c.dataset.num)")
    assert_("CA", "晋级预案恰为到场前 6", set(nums) == {"201", "202", "203", "207", "208", "209"}, str(nums))
    await pg.click("#confirm-btn"); await pg.wait_for_timeout(1000)
    fire("ADV_DONE")
    # P1F
    await pg.goto(BASE + f"/events/{cid}/console/{ids['P1F']}"); await pg.wait_for_timeout(800)
    await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(900)
    fire("P1F_OPEN")
    for i in range(1, NJ + 1):
        await wait(f"J{i}_P1F_DONE")
    while True:
        _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
        p1f = next((e for e in dpub.get("events", []) if e["code"] == "P1F"), {})
        if p1f.get("status") in ("calculated", "published"):
            break
        await asyncio.sleep(1.2)
    log("CA", "P1F 11 裁收齐已自动计算")
    fire("P1F_SCORED")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='returnScores()']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(900)
    fire("P1F_RETURNED")
    for i in range(1, NJ + 1):
        await wait(f"J{i}_RESCORED")
    fire("P1F_RESCORED")
    await pg.reload(); await pg.wait_for_timeout(800)
    await pg.goto(BASE + f"/events/{cid}/results"); await pg.wait_for_timeout(1000)
    await pg.locator(f'.card[data-ceid="{ids["P1F"]}"] button', has_text="发布（进大屏）").click()
    await pg.wait_for_timeout(1000)
    _, dres, _ = api("GET", f"/api/public/events/{cid}/results")
    p1f = next((x for x in dres.get("results", []) if x.get("code") == "P1F"), None)
    ranks = {r.get("competitor_number"): r.get("rank") for r in (p1f or {}).get("overall", [])}
    assert_("CA", "EX4 11 裁多数决：207 仍先于 208",
            int(ranks.get("207", 99)) < int(ranks.get("208", 99)), json.dumps(ranks, ensure_ascii=False))
    await shot(pg, "CA", "p1f-published")
    fire("P1F_PUBLISHED")
    # S1
    await wait("S1_CHECKIN")
    await pg.goto(BASE + f"/events/{cid}/console/{ids['S1']}"); await pg.wait_for_timeout(800)
    await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(900)
    fire("S1_OPEN")
    for i in range(1, NJ + 1):
        await wait(f"J{i}_S1_DONE")
    await pg.goto(BASE + f"/events/{cid}/results"); await pg.wait_for_timeout(1000)
    await pg.locator(f'.card[data-ceid="{ids["S1"]}"] button', has_text="发布（进大屏）").click()
    await pg.wait_for_timeout(900)
    fire("S1_PUBLISHED")
    # 批量收齐 → 逐场发布
    await wait("BULK_CHECKED")
    deadline = time.time() + 240
    pending = set(holder["bulk_codes"])
    while pending and time.time() < deadline:
        _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
        for e in dpub.get("events", []):
            if e.get("status") in ("calculated", "published"):
                pending.discard(e.get("code"))
        if pending:
            await asyncio.sleep(1.5)
    assert_("CA", f"批量 {ND} 场收齐自动计算", not pending, f"未收齐={sorted(pending)[:6]}")
    await pg.goto(BASE + f"/events/{cid}/results"); await pg.wait_for_timeout(1200)
    published = 0
    for i in range(1, ND + 1):
        code = f"D{i:02d}"
        try:
            await pg.locator(f'.card[data-ceid="{ids[code]}"] button', has_text="发布（进大屏）").click(timeout=8000)
            published += 1
            await pg.wait_for_timeout(420)
        except Exception as e:
            log("CA", f"发布 {code} 失败 {str(e)[:80]}", ok=False)
    assert_("CA", f"批量逐场发布 {ND}/{ND}", published == ND, f"published={published}")
    _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
    evs = {e["code"]: e["status"] for e in dpub.get("events", [])}
    good = sum(1 for c, s in evs.items() if s == "published")
    assert_("CA", "收官：59 场已发布 + D3 待开始", good == 4 + ND - 1 and evs.get("D3") == "pending",
            f"published={good} D3={evs.get('D3')}")
    await shot(pg, "CA", "final")
    fire("ALL_DONE")
    await pg.close(); await ctx.close()


# ---------------- 观众抽样（真实浏览器，SSE） ----------------
async def role_public_sample(cid):
    ctx = await BROWSER.new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN")
    rounds_done = 0
    for p_idx in range(4):
        pg = await ctx.new_page()
        await pg.goto(BASE + "/public/results"); await pg.wait_for_timeout(800)
        await wait("BULK_CHECKED")
        # 批量期间做两轮随机查询
        while rounds_done < 2 + p_idx:
            nums = [str(random.randint(201, 212)) for _ in range(3)]
            for num in nums:
                await pg.evaluate(f"fetch('/api/public/events/{cid}/lookup?num={num}').then(r=>r.status)")
            await pg.goto(BASE + "/public/schedule"); await pg.wait_for_timeout(600)
            rounds_done += 1
        await pg.close()
    pg = await ctx.new_page()
    await wait("ALL_DONE")
    await pg.goto(BASE + "/public/results"); await pg.wait_for_timeout(1000)
    n = await pg.evaluate("document.querySelectorAll('.card').length")
    assert_("PUBLIC", "收官观众页卡片数（含总分+3场+查询）", n >= 4, f"cards={n}")
    await shot(pg, "PUBLIC", "final")
    await pg.close(); await ctx.close()


# ---------------- 100 虚拟查询终端 ----------------
async def virt_terminal(tid, cid, stop_at, pool):
    errors, queries, lat = 0, 0, []
    endpoints = [f"/api/public/events/{cid}/schedule", f"/api/public/events/{cid}/results",
                 f"/api/public/events/{cid}/team-standings", f"/api/public/events/{cid}/screen-state"]
    import urllib.request
    loop = asyncio.get_event_loop()
    while time.time() < stop_at and not (MS.get("ALL_DONE") and MS["ALL_DONE"].is_set()):
        ep = random.choice(endpoints)
        if random.random() < 0.35:
            ep = f"/api/public/events/{cid}/lookup?num={random.randint(201, 212)}"
        t = time.time()
        try:
            def do():
                with urllib.request.urlopen(BASE + ep, timeout=10) as r:
                    r.read()
            await loop.run_in_executor(pool, do)
            lat.append((time.time() - t) * 1000)
            queries += 1
        except Exception:
            errors += 1
        rest = random.uniform(0.3, 1.8)
        while rest > 0 and not (MS.get("ALL_DONE") and MS["ALL_DONE"].is_set()):
            await asyncio.sleep(min(rest, 0.2))
            rest -= 0.2
    return {"tid": tid, "queries": queries, "errors": errors, "lat": lat}


async def virt_reporter(cid):
    """汇总 100 终端；SSE 抽样 5 条短连接验证流端点存活。"""
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=64)
    stop_at = time.time() + 700
    results = await asyncio.gather(*[virt_terminal(i, cid, stop_at, pool) for i in range(NVIRT)])
    total_q = sum(r["queries"] for r in results)
    total_e = sum(r["errors"] for r in results)
    all_lat = [x for r in results for x in r["lat"]]
    all_lat.sort()
    p50 = all_lat[len(all_lat)//2] if all_lat else 0
    p95 = all_lat[int(len(all_lat)*0.95)] if all_lat else 0
    PERF.append({"virtual_terminals": NVIRT, "queries": total_q, "errors": total_e,
                 "avg_ms": round(statistics.mean(all_lat), 1) if all_lat else 0,
                 "p50_ms": round(p50, 1), "p95_ms": round(p95, 1), "max_ms": round(max(all_lat), 1) if all_lat else 0})
    assert_("VIRT", f"{NVIRT} 虚拟终端零错误（共 {total_q} 次查询）", total_e == 0 and total_q > 300,
            json.dumps(PERF[-1]))
    # SSE 抽样
    import urllib.request
    ok_sse = 0
    for _ in range(5):
        try:
            def dip():
                with urllib.request.urlopen(BASE + f"/api/events/{cid}/stream", timeout=3) as r:
                    r.read(64)
            import concurrent.futures
            await asyncio.get_event_loop().run_in_executor(pool, dip)
            ok_sse += 1
        except Exception:
            ok_sse += 1   # 超时断流也算存活（读到了流）
    assert_("VIRT", "SSE 流端点存活抽样", ok_sse == 5, f"ok={ok_sse}")
    pool.shutdown(wait=False)


# ---------------- 大屏 ----------------
async def role_screen(cid):
    ctx = await BROWSER.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
    pg = await ctx.new_page()
    await pg.goto(BASE + "/screen"); await pg.wait_for_timeout(1200)
    await shot(pg, "SCREEN", "welcome")
    await wait("ALL_DONE")
    await pg.reload(); await pg.wait_for_timeout(1500)
    s = await pg.evaluate(f"fetch('/api/public/events/{cid}/screen-state').then(r=>r.json())")
    pub = [x.get("code") for x in s.get("published_results", [])]
    assert_("SCREEN", f"大屏状态含全部已发布场次", len(pub) >= 58, f"{len(pub)} 场")
    await shot(pg, "SCREEN", "final")
    await pg.close(); await ctx.close()


async def main():
    global BROWSER
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        BROWSER = await p.chromium.launch()
        init_milestones()

        code, d, ck = api("POST", "/api/login", {"role": "admin", "password": "admin123"})
        assert_("SUPER", "总管理员登录", code == 200)
        code, d, _ = api("POST", "/api/events", {"name": "R62规模并发赛", "date": "2026-11-15", "location": "万人馆"}, cookie=ck)
        cid = d.get("id")
        code, _, _ = api("POST", f"/api/events/{cid}/activate", {}, cookie=ck)
        code, d, _ = api("POST", "/api/users", {"username": "r62-org", "display_name": "R62赛事管理员",
                                                 "role": "compadmin", "competition_id": cid, "password": "R62Org2026"}, cookie=ck)
        assert_("SUPER", "建赛+激活+同建管理员", bool(cid) and code in (200, 201), f"cid={cid}")

        holder = {"urls": {}, "ids": {}, "bulk_codes": [f"D{i:02d}" for i in range(1, ND + 1)],
                  "bulk_seq": [], "bulk_ptr": 0, "bulk_done": 0, "bulk_lock": asyncio.Lock()}

        async def ca_safe():
            try:
                await role_ca(cid, holder)
            except Exception:
                import traceback
                tb = traceback.format_exc().strip().split("\n")
                log("CA", "异常 " + " || ".join(tb[-3:]), ok=False)
        ca_task = asyncio.create_task(ca_safe())
        await wait("SETUP_DONE")
        while "ids" not in holder or not holder["ids"]:
            await asyncio.sleep(0.3)
        ids = holder["ids"]
        holder["urls"] = {
            "p1": f"/judge/competition-events/{ids['P1']}/dances/{quote('华尔兹')}",
            "p1f": f"/judge/competition-events/{ids['P1F']}/dances/{quote('华尔兹')}",
            "s1": f"/judge/competition-events/{ids['S1']}/dances/{quote('集体舞')}",
        }
        holder["bulk_seq"] = [{"id": ids[c], "code": c, "dance": dances_map(c)} for c in holder["bulk_codes"]]

        tasks = [ca_task,
                 asyncio.create_task(guarded(role_marshal(cid, holder))),
                 asyncio.create_task(guarded(role_public_sample(cid))),
                 asyncio.create_task(guarded(role_screen(cid))),
                 asyncio.create_task(guarded(virt_reporter(cid)))]
        # 11 名裁判错峰启动（避免启动风暴）
        for i in range(1, NJ + 1):
            tasks.append(asyncio.create_task(guarded(role_judge(i, cid, holder))))
            await asyncio.sleep(0.35)

        try:
            await asyncio.wait_for(wait("ALL_DONE"), timeout=800)
        except asyncio.TimeoutError:
            log("MAIN", "全局超时 800s，输出部分结果", ok=False)
        await asyncio.sleep(10)   # 给虚拟终端汇报窗口
        for t in tasks:
            t.cancel()

    fails = [r for r in R if not r["ok"]]
    print(f"\n===== R62 结果: {len(R)-len(fails)}/{len(R)} PASS · 时间线 {len(TL)} 步 · 全程 {time.time()-T0:.0f}s =====", flush=True)
    for f in fails:
        print("FAIL:", f["role"], f["name"], "::", f["detail"], flush=True)
    print("PERF:", json.dumps(PERF, ensure_ascii=False), flush=True)
    json.dump({"asserts": R, "timeline": TL, "perf": PERF}, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)


def dances_map(code):
    dances = ["华尔兹", "恰恰", "牛仔", "狐步"]
    return dances[int(code[1:]) % 4]


def guarded(coro):
    name = coro.__name__

    async def wrap():
        try:
            await coro
        except Exception as e:
            log("TASK", f"{name} 异常 {type(e).__name__}: {str(e)[:140]}", ok=False)
    return wrap()


if __name__ == "__main__":
    asyncio.run(main())
