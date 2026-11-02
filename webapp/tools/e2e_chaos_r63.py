# -*- coding: utf-8 -*-
"""R63 混沌压测：全部终端真浏览器 + 多源 IP + 网络混沌代理 + 裁判随机干扰。

- 网络混沌：net_chaos 透明 TCP 代理两档——
  wild（观众：延迟 0~500ms、3% 连接中途断流，触发 EventSource 重连）
  mild（裁判/工作人员：延迟 0~120ms、0.5% 断流）
- 多 IP：代理监听多个 loopback IP，回源以不同 local_addr 连接 → 应用侧可见不同客户端 IP
- 终端（全部真浏览器）：CA/MARSHAL/HOST(温和档) + J1~J11(温和档+随机干扰) +
  观众 60 页(狂野档, 6 上下文×10 页, 随机访问/背番号查询) + 大屏
- 裁判随机干扰：错点后撤销 / 排名中随机停顿 / 未排满提前提交(验证防呆) /
  排名中离场再返回(验证 R63 草稿根治：进度必须保留)
用法：python3 e2e_chaos_r63.py [base=8302]；帧 → /tmp/e2e_r63；结果+混沌统计 → results.json
"""
import asyncio, csv, json, os, random, sys, time
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net_chaos import start_chaos_proxy, ChaosStats  # noqa: E402

APP = "http://127.0.0.1:8302"
MILD_PORTS = [8421, 8422, 8423, 8424]
WILD_PORTS = [8412, 8413, 8414, 8415, 8416, 8417, 8418, 8419]
NJ = 11
ND = 56
OUT = "/tmp/e2e_r63"
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
R, TL, PERF = [], [], []
BROWSER = None
HOLDER = {}


def log(role, event, ok=True, detail=""):
    t = time.time() - T0
    TL.append({"t": round(t, 1), "role": role, "event": event, "ok": bool(ok), "detail": str(detail)[:160]})
    print(f"[{t:6.1f}s] {'✓' if ok else '✗'} {role} :: {event}" + (f" :: {detail}" if detail else ""), flush=True)


def assert_(role, name, ok, detail=""):
    R.append({"role": role, "name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    log(role, "ASSERT " + name, ok, detail)


MS = {}


def init_ms():
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
    r = urllib.request.Request(APP + path, method=method)
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


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([header] + rows)


def dances_map(code):
    return ["华尔兹", "恰恰", "牛仔", "狐步"][int(code[1:]) % 4]


async def shot(page, role, step):
    await page.screenshot(path=f"{OUT}/{step}_{role}.png")
    log(role, "帧 " + f"{step}_{role}.png")


def guarded(coro):
    name = coro.__name__

    async def wrap():
        try:
            await coro
        except Exception as e:
            log("TASK", f"{name} 异常 {type(e).__name__}: {str(e)[:140]}", ok=False)
    return wrap()


# ---------------- 裁判：随机干扰评分 ----------------
async def judge_rank_chaos(pg, base, url, expect_n, step, role, intensity="full"):
    """排名 + 随机干扰。full=逐条断言；light=只报失败。返回是否成功。"""
    await pg.goto(base + url)
    await pg.wait_for_timeout(600)
    try:
        await pg.wait_for_selector(".rank-row:not(.off)", timeout=25000)
    except Exception:
        log(role, f"{step} 失败@渲染", ok=False)
        return False
    await pg.wait_for_timeout(400)
    n = await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)').length")
    if n != expect_n:
        log(role, f"{step} 失败@行数 got={n}", ok=False)
        return False

    do_wrong = random.random() < 0.25 and intensity == "full"
    do_pause = random.random() < 0.20
    do_early = random.random() < 0.20 and intensity == "full"
    do_nav = random.random() < 0.15 and intensity == "full"

    # 干扰①：排名中离场再返回（验证草稿保留——R63 根治回归点）
    if do_nav:
        await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)')[0].click()")
        await pg.wait_for_timeout(250)
        before = await pg.evaluate("document.getElementById('progress').textContent")
        await pg.goto(base + "/judge"); await pg.wait_for_timeout(700)
        await pg.goto(base + url); await pg.wait_for_timeout(700)
        try:
            await pg.wait_for_selector(".rank-row:not(.off)", timeout=10000)
        except Exception:
            pass
        after = await pg.evaluate("document.getElementById('progress').textContent")
        kept = ("1 /" in after and "已排 0" not in after)
        assert_(role, f"{step} 干扰·离场返回草稿保留(R63根治)", kept and before[3] == after[3],
                f"离开前={before!r} 返回后={after!r}")

    # 干扰②：未排满提前提交（防呆拦截）
    if do_early:
        await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)')[0].click()")
        await pg.wait_for_timeout(200)
        await pg.evaluate("document.getElementById('submit').click()")
        await pg.wait_for_timeout(500)
        blocked = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + m.textContent : '' })()")
        assert_(role, f"{step} 干扰·未排满提交被防呆拦截", "err" in blocked, blocked)

    for i in range(n):
        # 干扰③：错点后撤销
        if do_wrong and i == 2 and n > 3:
            await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)')[3].click()")
            await pg.wait_for_timeout(160)
            await pg.evaluate("document.querySelectorAll('.rank-row:not(.off)')[3].click()")
            await pg.wait_for_timeout(160)
        await pg.evaluate(f"document.querySelectorAll('.rank-row:not(.off)')[{i}].click()")
        # 干扰④：排名中停顿（模拟裁判分心）
        if do_pause and i == 3:
            await asyncio.sleep(random.uniform(1.0, 2.2))
        await pg.wait_for_timeout(200 if intensity == "full" else 150)
    prog = await pg.evaluate("document.getElementById('progress').textContent")
    if f"{expect_n} / {expect_n}" not in prog:
        # 自愈补点（对抗 SSE 重渲染/SSE 丢包场景）
        for _ in range(4):
            prog = await pg.evaluate("document.getElementById('progress').textContent")
            if f"{expect_n} / {expect_n}" in prog:
                break
            await pg.evaluate("() => document.querySelectorAll('.rank-row:not(.off)').forEach(r => { if (!r.classList.contains('assigned')) r.click(); })")
            await pg.wait_for_timeout(500)
    if f"{expect_n} / {expect_n}" not in prog:
        log(role, f"{step} 失败@排满 prog={prog!r}", ok=False)
        return False
    await pg.evaluate("document.getElementById('submit').click()")
    await pg.wait_for_timeout(800)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    if "ok" not in msg:
        log(role, f"{step} 失败@提交 msg={msg!r}", ok=False)
        return False
    if intensity == "full":
        assert_(role, step + " 提交成功", True, msg)
    return True


async def judge_rank_retry(pg, base, url, expect_n, step, role, intensity="full"):
    """混沌/结构性重载(score_returned→softReload)会打断正在执行的 evaluate——自动重试。"""
    for attempt in range(3):
        try:
            return await judge_rank_chaos(pg, base, url, expect_n, step, role, intensity)
        except Exception as e:
            m = str(e)[:80]
            retryable = ("context was destroyed" in m or "reading 'click'" in m
                         or "Timeout" in type(e).__name__ or "ERR_ABORTED" in m
                         or "ERR_CONNECTION" in m or "Target closed" in m)
            if retryable:
                log(role, f"{step} 第{attempt+1}次被网络/导航打断，稍候重试 :: {m}")
                await asyncio.sleep(2.5)
                continue
            raise
    log(role, f"{step} 三次尝试均被打断，放弃本场（栅栏继续）", ok=False)
    return False


async def role_judge(idx, cid, holder):
    ctx = await BROWSER.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2, locale="zh-CN")
    pg = await ctx.new_page()
    host = f"127.0.0.1:{MILD_PORTS[idx % len(MILD_PORTS)]}"
    base = f"http://{host}"
    await wait("SETUP_DONE")
    await comp_login(pg, cid, "judge", judge_id=f"J{idx}", base=base)
    log(f"J{idx}", "裁判登录(经混沌代理 " + host + ")")
    await wait("CHECKIN_P1")
    await judge_rank_retry(pg, base, holder["urls"]["p1"], 9, "P1顺位法", f"J{idx}")
    fire(f"J{idx}_P1_DONE")
    await wait("P1F_CHECKIN")
    await judge_rank_retry(pg, base, holder["urls"]["p1f"], 6, "P1F顺位法", f"J{idx}")
    fire(f"J{idx}_P1F_DONE")
    await wait("P1F_RETURNED")
    await pg.evaluate("try { sessionStorage.clear() } catch (e) {}")
    okr = await judge_rank_chaos(pg, base, holder["urls"]["p1f"], 6, "EX4重交", f"J{idx}")
    if idx == 2 and okr:
        # J2 精确改判 207/208（让 208 先行）
        for seq in ("207", "208", "208", "207"):
            await pg.evaluate(f"Array.from(document.querySelectorAll('.rank-row:not(.off)')).find(r => r.dataset.num === '{seq}').click()")
            await pg.wait_for_timeout(220)
        prog = await pg.evaluate("document.getElementById('progress').textContent")
        assert_("J2", "EX4 改判后仍排满", "6 / 6" in prog, prog)
        await pg.evaluate("document.getElementById('submit').click()")
        await pg.wait_for_timeout(800)
    fire(f"J{idx}_RESCORED")
    # 批量：广播-栅栏
    await wait("BULK_CHECKED")
    seq = holder["bulk_seq"]
    fails = 0
    while True:
        k = holder["bulk_ptr"]
        if k >= len(seq):
            break
        item = seq[k]
        okb = await judge_rank_retry(pg, base, f"/judge/competition-events/{item['id']}/dances/{quote(item['dance'])}",
                                     6, f"批量{item['code']}", f"J{idx}", intensity="light")
        if not okb:
            fails += 1
        async with holder["bulk_lock"]:
            holder["bulk_done"] += 1
            if holder["bulk_done"] >= NJ:
                holder["bulk_done"] = 0
                holder["bulk_ptr"] = k + 1
        while holder["bulk_ptr"] == k and k < len(seq):
            await asyncio.sleep(0.2)
    assert_(f"J{idx}", "批量评分失败场数", fails == 0, f"fails={fails}")
    fire(f"J{idx}_BULK_DONE")
    # S1
    await wait("S1_OPEN")
    await pg.goto(base + holder["urls"]["s1"]); await pg.wait_for_timeout(800)
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
    await pg.wait_for_timeout(800)
    msg = await pg.evaluate("(() => { const m = document.getElementById('msg'); return m ? m.className + ':' + m.textContent : '' })()")
    assert_(f"J{idx}", "S1 提交成功", "ok" in msg, msg)
    fire(f"J{idx}_S1_DONE")
    await pg.close(); await ctx.close()


async def comp_login(pg, cid, role, base=None, username=None, password=None, judge_id=None):
    base = base or f"http://127.0.0.1:{MILD_PORTS[0]}"
    await pg.goto(f"{base}/competitions/{cid}/login?role={role}")
    await pg.wait_for_timeout(500)
    if judge_id: await pg.fill("#judge_id", judge_id)
    if username: await pg.fill("#username", username)
    if password: await pg.fill("#password", password)
    await pg.click("#btn")
    await pg.wait_for_timeout(1000)


# ---------------- 检录 / 主持 / CA ----------------
async def role_marshal(cid, holder):
    ctx = await BROWSER.new_context(viewport={"width": 375, "height": 812}, is_mobile=True,
                                    has_touch=True, device_scale_factor=2, locale="zh-CN")
    pg = await ctx.new_page()
    await wait("SETUP_DONE")
    await comp_login(pg, cid, "marshal", username="r63-checkin", password="R63Check2026")
    log("MARSHAL", "检录登录")
    await wait("P1_OPEN")
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[1]}/staff"); await pg.wait_for_timeout(1000)
    P1 = '.st-event[data-code="P1"]'
    for num in ("201", "202", "203", "204"):
        sel = f'{P1} .chip[data-num="{num}"]'
        await pg.evaluate("sel => document.querySelector(sel).scrollIntoView({block:'center'})", sel)
        await pg.wait_for_timeout(260)
        await pg.evaluate("sel => document.querySelector(sel).click()", sel)
        await pg.wait_for_timeout(300)
    await pg.evaluate("sel => document.querySelector(sel).click()", f'{P1} .chip[data-num="204"]')
    await pg.wait_for_timeout(450)
    for num in ("207", "208", "209", "210", "211", "212"):
        await pg.evaluate("sel => document.querySelector(sel).click()", f'{P1} .chip[data-num="{num}"]')
        await pg.wait_for_timeout(240)
    # 自愈（双向）：SSE 重渲染可能冲掉/翻转点击（混沌延迟下尤甚）——该绿的补绿，204/205/206 该灰的强制摘除
    for _ in range(3):
        state = await pg.evaluate("""sel => Array.from(document.querySelectorAll(sel + ' .chip'))
            .map(c => ({num: c.dataset.num, on: c.classList.contains('on')}))""", P1)
        need = [c["num"] for c in state
                if (not c["on"] and c["num"] not in ("204", "205", "206"))
                or (c["on"] and c["num"] in ("204", "205", "206"))]
        if not need:
            break
        for num in need:
            await pg.evaluate("sel => document.querySelector(sel).click()", f'{P1} .chip[data-num="{num}"]')
            await pg.wait_for_timeout(350)
    prog = await pg.evaluate("sel => { const c = document.querySelector(sel + ' .tag[id^=prog]'); return c ? c.textContent : '' }", P1)
    assert_("MARSHAL", "EX1/EX2 P1 检录 9/12", "9 / 12" in prog, prog)
    await shot(pg, "MARSHAL", "p1-partial")
    fire("CHECKIN_P1")
    await wait("P1F_OPEN")
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[1]}/staff")
    await pg.wait_for_selector('.st-event[data-code="P1F"]', timeout=25000)
    await pg.wait_for_timeout(400)
    await pg.evaluate("sel => document.querySelector(sel).click()", '.st-event[data-code="P1F"] [data-all]')
    await pg.wait_for_timeout(800)
    progf = await pg.evaluate("sel => { const c = document.querySelector(sel + ' .tag[id^=prog]'); return c ? c.textContent : '' }", '.st-event[data-code="P1F"]')
    assert_("MARSHAL", "P1F 全员检录 6/6", "6 / 6" in progf, progf)
    fire("P1F_CHECKIN")
    await wait("BULK_OPENED")
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[1]}/staff")
    await pg.wait_for_selector('.st-event[data-code="D01"]', timeout=25000)
    await pg.wait_for_timeout(600)
    checked = 0
    for code in holder["bulk_codes"]:
        ok = await pg.evaluate("sel => { const b = document.querySelector(sel); if (b) { b.click(); return true } return false }",
                               f'.st-event[data-code="{code}"] [data-all]')
        if ok:
            checked += 1
            await pg.wait_for_timeout(430)
    assert_("MARSHAL", f"批量场检录 {ND}/{ND}", checked == ND, f"checked={checked}")
    fire("BULK_CHECKED")
    await wait("P1F_PUBLISHED")
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[1]}/staff")
    await pg.wait_for_selector('.st-event[data-code="S1"], .done-card', timeout=25000)
    await pg.wait_for_timeout(500)
    await pg.evaluate("sel => document.querySelector(sel).click()", '.st-event[data-code="S1"] [data-all]')
    await pg.wait_for_timeout(800)
    fire("S1_CHECKIN")
    ncards = await pg.evaluate("document.querySelectorAll('.st-event, .done-card').length")
    assert_("MARSHAL", "staff 页 60 场次卡片", ncards >= 59, f"cards={ncards}")
    await pg.close(); await ctx.close()


async def role_ca(cid, holder):
    ctx = await BROWSER.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    ctx.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
    pg = await ctx.new_page()
    await comp_login(pg, cid, "admin", username="r63-org", password="R63Org2026")
    log("CA", "登录落点 " + pg.url)
    write_csv("/tmp/r63_comp.csv", ["背番号", "项目编号", "姓名", "学校/单位"],
              [[n, "P1", f"选手{n}", "单位A" if int(n) <= 206 else "单位B"] for n in range(201, 213)])
    write_csv("/tmp/r63_judges.csv", ["裁判ID", "姓名"], [[f"J{i}", f"裁判{i}"] for i in range(1, NJ + 1)])
    dances = ["华尔兹", "恰恰", "牛仔", "狐步"]
    rows = [["P1", "标准舞预赛", "P1", "1", "华尔兹", "SKATING", "6", ",".join(str(n) for n in range(201, 213))],
            ["P1F", "标准舞决赛", "P1", "2", "华尔兹", "SKATING", "0", "201,202,203,207,208,209"],
            ["S1", "集体舞决赛", "S1", "1", "集体舞", "SCORE", "0", "201,202,203,204"],
            ["D3", "拉丁加赛", "D3", "1", "恰恰", "SKATING", "0", "201,202,203,204"]]
    for i in range(1, ND + 1):
        rows.append([f"D{i:02d}", f"第{i}场", f"D{i:02d}", "1", dances[i % 4], "SKATING", "0", "201,202,203,204,205,206"])
    write_csv("/tmp/r63_sched.csv", ["场次编号", "场次名称", "项目编号", "轮次", "舞种", "评分类型", "晋级人数", "参赛选手"], rows)
    kind_step = {"competitors": 2, "judges": 3, "schedule": 4}
    for kind, path in (("competitors", "/tmp/r63_comp.csv"), ("judges", "/tmp/r63_judges.csv"), ("schedule", "/tmp/r63_sched.csv")):
        await pg.click(f'[data-go="{kind_step[kind]}"]'); await pg.wait_for_timeout(300)
        await pg.set_input_files(f'.wiz-file[data-kind="{kind}"]', path)
        await pg.click(f'.wiz-upload-btn[data-kind="{kind}"]')
        await pg.wait_for_timeout(1300)
        r = await pg.evaluate(f"document.querySelector('.wiz-result[data-kind=\\'{kind}\\']').textContent")
        assert_("CA", f"向导导入 {kind}", "导入成功" in r, r)
    await pg.click('[data-go="5"]'); await pg.wait_for_timeout(300)
    await pg.select_option("#s-role", "marshal")
    await pg.fill("#s-username", "r63-checkin"); await pg.fill("#s-display", "R63检录")
    await pg.fill("#s-password", "R63Check2026"); await pg.click("#s-create"); await pg.wait_for_timeout(700)
    await pg.select_option("#s-role", "host")
    await pg.fill("#s-username", "r63-host"); await pg.fill("#s-display", "R63主持")
    await pg.fill("#s-password", "R63Host2026"); await pg.click("#s-create"); await pg.wait_for_timeout(700)
    await pg.click('[data-go="6"]'); await pg.wait_for_timeout(400)
    await pg.click("#wiz-finish"); await pg.wait_for_timeout(1200)
    fire("SETUP_DONE")
    while True:
        _, dsch, _ = api("GET", f"/api/public/events/{cid}/schedule")
        ids = {e["code"]: e["id"] for e in dsch.get("events", [])}
        if len(ids) >= 4 + ND:
            break
        await asyncio.sleep(0.5)
    holder["ids"] = ids
    holder["urls"] = {
        "p1": f"/judge/competition-events/{ids['P1']}/dances/{quote('华尔兹')}",
        "p1f": f"/judge/competition-events/{ids['P1F']}/dances/{quote('华尔兹')}",
        "s1": f"/judge/competition-events/{ids['S1']}/dances/{quote('集体舞')}",
    }
    holder["bulk_seq"] = [{"id": ids[c], "code": c, "dance": dances_map(c)} for c in holder["bulk_codes"]]

    async def open_console(ceid):
        await pg.goto(f"http://127.0.0.1:{MILD_PORTS[0]}/events/{cid}/console/{ceid}")
        await pg.wait_for_selector("button[onclick='openEvent(false)'], #status", timeout=25000)
        await pg.wait_for_timeout(600)
        await pg.evaluate("(() => { const d = document.querySelector('details.card'); if (d) d.open = true; })()")
        await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='openEvent(false)']\"); if (b) b.click(); })()")
        await pg.wait_for_timeout(1000)

    await open_console(ids["P1"])
    fire("P1_OPEN")
    await open_console(ids["D3"])
    fire("D3_OPENED")
    await asyncio.sleep(2.0)
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='closeEvent()']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(900)
    fire("D3_CANCELLED")
    _, _, ck = api("POST", "/api/login", {"role": "admin", "password": "admin123"})
    roster = [str(n) for n in range(201, 207)]
    for code in holder["bulk_codes"]:
        api("POST", f"/api/competition-events/{holder['ids'][code]}/open", {"roster": roster, "reset": False}, cookie=ck)
    log("CA", f"批量开场 {ND} 场完成")
    fire("BULK_OPENED")
    for i in range(1, NJ + 1):
        await wait(f"J{i}_P1_DONE")
    while True:
        _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
        p1 = next((e for e in dpub.get("events", []) if e["code"] == "P1"), {})
        if p1.get("status") in ("calculated", "published"):
            break
        await asyncio.sleep(1.2)
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[0]}/events/{cid}/results"); await pg.wait_for_timeout(1300)
    await pg.locator(f'.card[data-ceid="{ids["P1"]}"] button', has_text="发布（进大屏）").click(timeout=15000)
    await pg.wait_for_timeout(1100)
    _, dres, _ = api("GET", f"/api/public/events/{cid}/results")
    codes = [x.get("code") for x in dres.get("results", [])]
    assert_("CA", "P1 发布", "P1" in codes, str(codes))
    body = json.dumps(dres.get("results", []), ensure_ascii=False)
    assert_("CA", "EX1/EX2 未到场不在成绩", all(f'"{n}"' not in body for n in ("204", "205", "206")))
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[0]}/events/{cid}/advancement?project=P1&round=1")
    await pg.wait_for_timeout(1200)
    await pg.click("text=生成预案"); await pg.wait_for_timeout(900)
    nums = await pg.evaluate("Array.from(document.querySelectorAll('.adv-check')).map(c => c.dataset.num)")
    assert_("CA", "晋级预案恰为到场前 6", set(nums) == {"201", "202", "203", "207", "208", "209"}, str(nums))
    await pg.click("#confirm-btn"); await pg.wait_for_timeout(1100)
    fire("ADV_DONE")
    await open_console(ids["P1F"])
    fire("P1F_OPEN")
    for i in range(1, NJ + 1):
        await wait(f"J{i}_P1F_DONE")
    while True:
        _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
        p1f = next((e for e in dpub.get("events", []) if e["code"] == "P1F"), {})
        if p1f.get("status") in ("calculated", "published"):
            break
        await asyncio.sleep(1.2)
    fire("P1F_SCORED")
    await pg.evaluate("(() => { const b = document.querySelector(\"button[onclick='returnScores()']\"); if (b) b.click(); })()")
    await pg.wait_for_timeout(1000)
    fire("P1F_RETURNED")
    for i in range(1, NJ + 1):
        await wait(f"J{i}_RESCORED")
    fire("P1F_RESCORED")
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[0]}/events/{cid}/results"); await pg.wait_for_timeout(1200)
    await pg.locator(f'.card[data-ceid="{ids["P1F"]}"] button', has_text="发布（进大屏）").click(timeout=15000)
    await pg.wait_for_timeout(1100)
    _, dres, _ = api("GET", f"/api/public/events/{cid}/results")
    p1f = next((x for x in dres.get("results", []) if x.get("code") == "P1F"), None)
    ranks = {r.get("competitor_number"): r.get("rank") for r in (p1f or {}).get("overall", [])}
    assert_("CA", "EX4 11 裁多数决：207 仍先于 208",
            int(ranks.get("207", 99)) < int(ranks.get("208", 99)), json.dumps(ranks, ensure_ascii=False))
    await shot(pg, "CA", "p1f-published")
    fire("P1F_PUBLISHED")
    await wait("S1_CHECKIN")
    await open_console(ids["S1"])
    fire("S1_OPEN")
    for i in range(1, NJ + 1):
        await wait(f"J{i}_S1_DONE")
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[0]}/events/{cid}/results"); await pg.wait_for_timeout(1100)
    await pg.locator(f'.card[data-ceid="{ids["S1"]}"] button', has_text="发布（进大屏）").click(timeout=15000)
    await pg.wait_for_timeout(1000)
    fire("S1_PUBLISHED")
    await wait("BULK_CHECKED")
    deadline = time.time() + 300
    pending = set(holder["bulk_codes"])
    while pending and time.time() < deadline:
        _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
        for e in dpub.get("events", []):
            if e.get("status") in ("calculated", "published"):
                pending.discard(e.get("code"))
        if pending:
            await asyncio.sleep(2.0)
    assert_("CA", f"混沌网络下批量 {ND} 场收齐计算", not pending, f"未收齐={sorted(pending)[:6]}")
    await pg.goto(f"http://127.0.0.1:{MILD_PORTS[0]}/events/{cid}/results"); await pg.wait_for_timeout(1300)
    published = 0
    for code in holder["bulk_codes"]:
        done = False
        for attempt in (1, 2):   # 混沌断流可能吃掉发布请求：核对后重试
            try:
                await pg.locator(f'.card[data-ceid="{holder["ids"][code]}"] button', has_text="发布（进大屏）").click(timeout=10000)
                await pg.wait_for_timeout(600)
                _, dpub2, _ = api("GET", f"/api/public/events/{cid}/schedule")
                st2 = next((e.get("status") for e in dpub2.get("events", []) if e.get("code") == code), None)
                if st2 == "published":
                    done = True
                    break
                log("CA", f"发布 {code} 第{attempt}次未生效（status={st2}），重试")
            except Exception as e:
                log("CA", f"发布 {code} 第{attempt}次异常 {str(e)[:60]}，重试")
                await pg.goto(f"http://127.0.0.1:{MILD_PORTS[0]}/events/{cid}/results")
                await pg.wait_for_timeout(1000)
        if done:
            published += 1
        else:
            log("CA", f"发布 {code} 两次尝试均失败", ok=False)
    assert_("CA", f"批量逐场发布 {ND}/{ND}", published == ND, f"published={published}")
    _, dpub, _ = api("GET", f"/api/public/events/{cid}/schedule")
    evs = {e["code"]: e["status"] for e in dpub.get("events", [])}
    good = sum(1 for c, st in evs.items() if st == "published")
    assert_("CA", "收官：59 场已发布 + D3 待开始", good == 4 + ND - 1 and evs.get("D3") == "pending",
            f"published={good} D3={evs.get('D3')}")
    await shot(pg, "CA", "final")
    fire("ALL_DONE")
    await pg.close(); await ctx.close()


# ---------------- 观众 60 真实页（狂野混沌档） ----------------
async def role_spectators(cid, holder):
    until = lambda: MS.get("ALL_DONE") and MS["ALL_DONE"].is_set()
    pages_meta = []
    total_jserr, total_failed = 0, 0

    async def spectator_page(ctx, pid):
        nonlocal total_jserr, total_failed
        pg = await ctx.new_page()
        fails, jerr = [], []
        pg.on("requestfailed", lambda r: fails.append(1))
        pg.on("pageerror", lambda e: jerr.append(str(e)[:200]))
        base = f"http://127.0.0.1:{WILD_PORTS[pid % len(WILD_PORTS)]}"
        targets = ["/public/results", "/public/schedule", "/public/team-standings", "/screen"]
        nav_err = 0
        rounds = 0
        while not until():
            tgt = random.choice(targets)
            try:
                await pg.goto(base + tgt, timeout=25000)
                await pg.wait_for_timeout(random.randint(500, 1600))
                if tgt == "/public/results" and random.random() < 0.4:
                    num = random.randint(201, 212)
                    try:
                        await pg.fill("#lookup-num", str(num), timeout=4000)
                        await pg.evaluate("(() => { const b = document.getElementById('lookup-go'); if (b) b.click(); })()")
                    except Exception:
                        pass
            except Exception:
                nav_err += 1
            rounds += 1
            rest = random.uniform(0.8, 2.5)
            while rest > 0 and not until():
                await asyncio.sleep(min(rest, 0.25))
                rest -= 0.25
        pages_meta.append({"pid": pid, "rounds": rounds, "nav_err": nav_err,
                           "req_failed": len(fails), "js_errors": len(jerr),
                           "js_err_msgs": jerr[:5]})
        total_jserr += len(jerr)
        total_failed += len(fails)
        await pg.close()

    async def batch(bid):
        ctx = await BROWSER.new_context(viewport={"width": 1100, "height": 760}, locale="zh-CN")
        await asyncio.gather(*[spectator_page(ctx, bid * 10 + k) for k in range(10)])
        await ctx.close()

    await asyncio.gather(*[guarded(batch(b)) for b in range(6)])
    err_msgs = [m for p in pages_meta for m in p.get("js_err_msgs", [])]
    holder["spec_report"] = {"pages": len(pages_meta), "js_errors": total_jserr,
                             "req_failed": total_failed, "js_err_msgs": err_msgs[:10],
                             "detail": pages_meta[:6]}
    rounds = sum(p.get("rounds", 0) for p in pages_meta)
    assert_("SPECTATOR", "60 观众页全程 0 JS 错误", total_jserr == 0 and len(pages_meta) == 60,
            f"pages={len(pages_meta)} rounds={rounds} req_failed={total_failed}")
    log("SPECTATOR", f"观众负载汇总: 60 页, JS错误={total_jserr}, 断连请求={total_failed}(混沌预期)")


# ---------------- 大屏 ----------------
async def role_screen(cid):
    ctx = await BROWSER.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
    pg = await ctx.new_page()
    await pg.goto(f"http://127.0.0.1:{WILD_PORTS[0]}/screen"); await pg.wait_for_timeout(1500)
    await shot(pg, "SCREEN", "welcome")
    await wait("ALL_DONE")
    await pg.reload(); await pg.wait_for_timeout(1800)
    s = await pg.evaluate(f"fetch('/api/public/events/{cid}/screen-state').then(r=>r.json())")
    pub = [x.get("code") for x in s.get("published_results", [])]
    assert_("SCREEN", "大屏状态含全部已发布场次", len(pub) >= 58, f"{len(pub)} 场")
    await shot(pg, "SCREEN", "final")
    await pg.close(); await ctx.close()


async def main():
    global BROWSER
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        BROWSER = await p.chromium.launch()
        init_ms()

        wild_stats, mild_stats = ChaosStats(), ChaosStats()
        wild_srv, _ = await start_chaos_proxy(WILD_PORTS, 8302, delay_max_ms=500, abort_pct=3.0, stats=wild_stats)
        mild_srv, _ = await start_chaos_proxy(MILD_PORTS, 8302, delay_max_ms=120, abort_pct=0.5, stats=mild_stats)
        log("CHAOS", "混沌代理就绪 wild(500ms/3%断流) mild(120ms/0.5%)")

        code, d, ck = api("POST", "/api/login", {"role": "admin", "password": "admin123"})
        assert_("SUPER", "总管理员登录", code == 200)
        code, d, _ = api("POST", "/api/events", {"name": "R63混沌压测赛", "date": "2026-11-22", "location": "风暴馆"}, cookie=ck)
        cid = d.get("id")
        api("POST", f"/api/events/{cid}/activate", {}, cookie=ck)
        code, d, _ = api("POST", "/api/users", {"username": "r63-org", "display_name": "R63管理员",
                                                 "role": "compadmin", "competition_id": cid, "password": "R63Org2026"}, cookie=ck)
        assert_("SUPER", "建赛+激活+管理员", bool(cid) and code in (200, 201), f"cid={cid}")

        HOLDER.clear()
        HOLDER.update({"ids": {}, "urls": {}, "bulk_codes": [f"D{i:02d}" for i in range(1, ND + 1)],
                       "bulk_seq": [], "bulk_ptr": 0, "bulk_done": 0, "bulk_lock": asyncio.Lock()})

        async def ca_safe():
            try:
                await role_ca(cid, HOLDER)
            except Exception:
                import traceback
                tb = traceback.format_exc().strip().split("\n")
                log("CA", "异常 " + " || ".join(tb[-3:]), ok=False)
        ca_task = asyncio.create_task(ca_safe())
        await wait("SETUP_DONE")
        while not HOLDER["ids"]:
            await asyncio.sleep(0.3)

        tasks = [ca_task,
                 asyncio.create_task(guarded(role_marshal(cid, HOLDER))),
                 asyncio.create_task(guarded(role_spectators(cid, HOLDER))),
                 asyncio.create_task(guarded(role_screen(cid)))]
        await asyncio.sleep(0.5)
        for i in range(1, NJ + 1):
            tasks.append(asyncio.create_task(guarded(role_judge(i, cid, HOLDER))))
            await asyncio.sleep(0.3)

        try:
            await asyncio.wait_for(wait("ALL_DONE"), timeout=1050)
        except asyncio.TimeoutError:
            log("MAIN", "全局超时 1050s，输出部分结果", ok=False)
        await asyncio.sleep(12)   # 观众页退出+汇报窗口
        for t in tasks:
            t.cancel()

        for srv in wild_srv + mild_srv:
            srv.close()
        PERF.append({"wild": {"conns": wild_stats.conns, "aborted": wild_stats.aborted, "errors": wild_stats.errors},
                     "mild": {"conns": mild_stats.conns, "aborted": mild_stats.aborted, "errors": mild_stats.errors},
                     "spectators": HOLDER.get("spec_report", {})})

    fails = [r for r in R if not r["ok"]]
    print(f"\n===== R63 结果: {len(R)-len(fails)}/{len(R)} PASS · 时间线 {len(TL)} 步 · 全程 {time.time()-T0:.0f}s =====", flush=True)
    for f in fails:
        print("FAIL:", f["role"], f["name"], "::", f["detail"], flush=True)
    print("PERF:", json.dumps(PERF, ensure_ascii=False), flush=True)
    json.dump({"asserts": R, "timeline": TL, "perf": PERF}, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
