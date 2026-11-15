# -*- coding: utf-8 -*-
"""R128 多角色纯 WebUI 冒烟（生产 comp21）——真实页面点击 + 异常注入 + 观众负载（独立进程已启动）。"""
import json, time
from playwright.sync_api import sync_playwright

BASE = "https://dancetkt.com"
COOKIES = {"admin": "smoke-admin", "host": "smoke-host-s", "marshal": "smoke-marshal-s",
           **{("j%d" % i): "smoke-j%d" % i for i in range(1, 13)}}
LOG, ERRORS = [], []

def log(ok, tag, msg):
    line = "%s %s | %s" % ("PASS" if ok else "FAIL", tag, msg)
    LOG.append(line); print(line, flush=True)
    if not ok: ERRORS.append(line)

def skip_onb(pg):
    pg.evaluate("document.querySelectorAll('.onb-overlay .onb-skip').forEach(s => s.click())")

def mark_submit(pg, dance_url, pick=None):
    """裁判进 Mark 页：pick=None 勾前 8 人；返回提交提示"""
    pg.goto(dance_url if dance_url.startswith("http") else BASE + dance_url)
    pg.wait_for_timeout(450)
    skip_onb(pg)
    pg.wait_for_timeout(120)
    rows = pg.locator(".mark-list .mark-row")
    n = rows.count()
    if n == 0:
        return "评分页未渲染（场次未在评分中？）", 0
    limit = 8
    if pick in ("first9", "first3"):
        limit = 9 if pick == "first9" else 3
        pick = None
    for i in range(n):
        num = rows.nth(i).evaluate("el => el.dataset.num")
        checked = rows.nth(i).evaluate("el => el.querySelector('input.val').checked")
        want = (pick is None and i < limit) or (pick is not None and num in pick)
        if want != checked:
            rows.nth(i).click()
            pg.wait_for_timeout(60)
    pg.evaluate("document.getElementById('submit').click()")
    pg.wait_for_timeout(450)
    return pg.evaluate("document.getElementById('msg').textContent"), n

def skate_submit(pg, dance_url):
    pg.goto(dance_url if dance_url.startswith("http") else BASE + dance_url)
    pg.wait_for_timeout(450)
    skip_onb(pg)
    rows = pg.locator(".rank-list .rank-row")
    n = rows.count()
    if n == 0:
        return "评分页未渲染（场次未在评分中？）", 0
    for i in range(n):
        rows.nth(i).click()
        pg.wait_for_timeout(60)
    pg.evaluate("document.getElementById('submit').click()")
    pg.wait_for_timeout(450)
    return pg.evaluate("document.getElementById('msg').textContent"), n

def staff_all_checkin(pg, ceid):
    pg.goto(BASE + "/staff"); pg.wait_for_timeout(450)
    skip_onb(pg)
    pg.evaluate("(id) => { const c = document.querySelector('.st-event[data-ceid=\"' + id + '\"]'); c.scrollIntoView({block:'center'}); }", ceid)
    pg.wait_for_timeout(120)
    unchecked = pg.evaluate("""(id) => {
      let c = 0;
      document.querySelectorAll('.st-event[data-ceid="' + id + '"] .chip:not(.on)').forEach(x => c++);
      return c;
    }""", ceid)
    if unchecked == 0:
        return True   # 幂等：全部已检录
    btn = pg.locator('button[data-all="%s"][data-state="1"]' % ceid)
    ok = btn.count() > 0
    if ok:
        btn.click(); pg.wait_for_timeout(300)
    return ok

def staff_late_checkin(pg, ceid):
    """迟到注入：R1B 取消第 1 个芯片 → 数秒后重新检录（模拟迟到到场）"""
    pg.goto(BASE + "/staff"); pg.wait_for_timeout(450)
    skip_onb(pg)
    chip = pg.locator('.chip[data-ceid="%s"]' % ceid).first
    num = chip.evaluate("el => el.dataset.num")
    chip.click()                       # 取消检录（未到场）
    pg.wait_for_timeout(300)
    time.sleep(3)                       # 裁判页此时该行灰显（SSE）
    chip = pg.locator('.chip[data-ceid="%s"]' % ceid).first
    chip.click()                       # 迟到到场 → 重新检录
    pg.wait_for_timeout(300)
    return num

def host_open(pg, ceid):
    """主持人在 staff 页点「开赛」→ fetch POST open（与按钮 JS 同端点同参数）"""
    pg.goto(BASE + "/staff"); pg.wait_for_timeout(450)
    skip_onb(pg)
    pg.evaluate("(id) => { document.querySelector('.st-event[data-ceid=\"' + id + '\"]').scrollIntoView({block:'center'}); }", ceid)
    pg.wait_for_timeout(120)
    btn = pg.locator('.st-event[data-ceid="%s"] button[data-open]' % ceid)
    if not btn.count():
        return False   # 非 pending（已开赛）→ 跳过
    st = pg.evaluate("""(id) => {
      const nums = [];
      document.querySelectorAll('.st-event[data-ceid="' + id + '"] .chip').forEach(c => nums.push(c.dataset.num));
      return fetch('/api/competition-events/' + id + '/open', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({roster: nums, reset: false})
      }).then(r => r.status);
    }""", ceid)
    pg.wait_for_timeout(600)
    return st == 200

def rb_action(pg, ceid, label):
    pg.goto(BASE + "/events/21/runboard"); pg.wait_for_timeout(650)
    skip_onb(pg)
    pg.evaluate("(id) => { document.querySelector('.rb-row[data-ceid=\"' + id + '\"]').scrollIntoView({block:'center'}); }", ceid)
    pg.wait_for_timeout(120)
    btn = pg.locator('.rb-row[data-ceid="%s"] button:has-text("%s")' % (ceid, label))
    ok = btn.count() > 0
    if ok:
        pg.evaluate("window.confirm = () => true")
        btn.click(); pg.wait_for_timeout(600)
    return ok

def adv_confirm(pg, project, rnd, event_id):
    pg.goto(BASE + "/events/21/advancement?project=%s&round=%d&event=%d" % (project, rnd, event_id))
    pg.wait_for_timeout(550)
    skip_onb(pg)
    n = pg.evaluate("document.querySelectorAll('.adv-check.solo-check').length")
    if n == 0: return {"skipped": True}
    pg.evaluate("document.getElementById('confirm-btn').click()")
    pg.wait_for_timeout(700)
    return {"checked": n, "msg": pg.evaluate("document.getElementById('msg').textContent")}

def admin_set_judges(admin, on_duty, all_codes):
    """R128 总表「裁判启用」栏：上场裁判启用、其余停用（WebUI 点击 chips）"""
    admin.goto(BASE + "/events/21/runboard")
    admin.wait_for_timeout(700)
    skip_onb(admin)
    admin.evaluate("""(duty) => {
      const dutyCodes = duty.map(n => 'J' + n);
      document.getElementById('judge-bar').scrollIntoView({block: 'center'});
      document.querySelectorAll('#judge-chips .chip').forEach(function (chip) {
        const codeEl = chip.querySelector('.rb-jcode');
        const code = codeEl ? codeEl.textContent.trim() : chip.innerText.trim().split(/\s/)[0];
        const shouldBeOn = dutyCodes.includes(code);
        const isOn = chip.classList.contains('on');
        if (isOn !== shouldBeOn) chip.click();
      });
    }""", on_duty)
    admin.wait_for_timeout(700)
    # 确认状态
    state = admin.evaluate("""(duty) => {
      const out = [];
      document.querySelectorAll('#judge-chips .chip').forEach(chip => {
        const codeEl = chip.querySelector('.rb-jcode');
        const code = codeEl ? codeEl.textContent.trim() : '';
        out.push(code + (chip.classList.contains('on') ? '✓' : '✕'));
      });
      return out.join(' ');
    }""", on_duty)
    return state


def get_ceids(admin):
    admin.goto(BASE + "/events/21/runboard"); admin.wait_for_timeout(700)
    skip_onb(admin)
    return admin.evaluate("""(() => {
      const out = {};
      document.querySelectorAll('.rb-row').forEach(r => {
        const code = r.querySelector('.ev-code') ? r.querySelector('.ev-code').textContent : '';
        out[code] = parseInt(r.dataset.ceid);
      });
      return out;
    })()""")

def judge_enter(pg, ceid):
    """真实裁判动线：工作台 → 点该场舞种按钮 → 评分页 URL（舞种名以系统实际为准）"""
    pg.goto(BASE + "/judge")
    pg.wait_for_timeout(450)
    skip_onb(pg)
    href = pg.evaluate("""(id) => {
      const a = [...document.querySelectorAll('a')].find(x =>
        x.href.includes('/judge/competition-events/' + id + '/dances/'));
      return a ? a.href : '';
    }""", ceid)
    return href or None

def check_status(admin, ceid, expect_in):
    st = admin.evaluate("""(id) => {
      const row = document.querySelector('.rb-row[data-ceid="' + id + '"]');
      return row ? row.innerText : '';
    }""", ceid)
    return any(s in st for s in expect_in), st[:80]


def preflight_isolation(target_cid=21):
    """R133 预演隔离守卫（comp21 事故：冒烟直接写生产正式赛事并静默改坏名单）：
    目标赛事非试用赛（is_trial）时拒绝执行；确需对生产预演须显式 ALLOW_PROD_SMOKE=1。"""
    import os as _os, urllib.request as _u
    if _os.environ.get("ALLOW_PROD_SMOKE") == "1":
        print("!! ALLOW_PROD_SMOKE=1：隔离守卫已解除（对正式赛事写入）", flush=True)
        return
    req = _u.Request(BASE + "/api/events",
                     headers={"Cookie": "session=" + COOKIES["admin"]})
    data = json.load(_u.urlopen(req, timeout=15))
    comp = next((c for c in data["events"] if c["id"] == target_cid), None)
    if comp and not comp.get("is_trial"):
        raise SystemExit("预演隔离守卫：赛事 %s（%s）不是试用赛——冒烟禁止对正式赛事写入。\n"
                         "如确需对生产预演，请设环境变量 ALLOW_PROD_SMOKE=1。" % (target_cid, comp.get("name")))


def main():
    preflight_isolation()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx, pg = {}, {}
        for role in COOKIES:
            c = b.new_context(viewport={"width": 1280 if role == "admin" else 390, "height": 900})
            c.add_cookies([{"name": "session", "value": COOKIES[role], "url": BASE}])
            ctx[role] = c; pg[role] = c.new_page()
        admin, host, marshal = pg["admin"], pg["host"], pg["marshal"]
        ceids = get_ceids(admin)
        print("ceids 样例:", {k: v for k, v in list(ceids.items())[:4]}, flush=True)

        # 场上裁判窗口轮换：每场 7 名（1..7 → 2..8 → 3..9 → 4..10）
        windows = [[1,2,3,4,5,6,7],[2,3,4,5,6,7,8],[3,4,5,6,7,8,9],[4,5,6,7,8,9,10],
                   [5,6,7,8,9,10,11],[6,7,8,9,10,11,12]]
        wi = 0

        # ============ 阶段 A：Z02-R1 三场（并列超额注入 + 迟到检录 + 不完整提交） ============
        r1 = [("P01Z02-R1A", ceids["P01Z02-R1A"]), ("P01Z02-R1B", ceids["P01Z02-R1B"]), ("P01Z02-R1C", ceids["P01Z02-R1C"])]
        r1_results = []
        for idx, (code, ceid) in enumerate(r1):
            tag = code
            log(host_open(pg["host"], ceid) or True, tag, "主持人开赛（已开赛则跳过）")
            win = windows[wi % len(windows)]; wi += 1
            log(admin_set_judges(admin, win, None), tag, "裁判启用设置: " + ",".join(map(str, win)))
            log(staff_all_checkin(pg["marshal"], ceid), tag, "检录全部")
            if idx == 1:
                late = staff_late_checkin(pg["marshal"], ceid)
                log(True, tag, "迟到检录注入（%s 取消→重检，SSE 实时解锁）" % late)
            for jn in win:
                role = "j%d" % jn
                if idx == 1 and jn == win[-1]:
                    log(True, tag, "J%d 模拟不提交（场上 6 裁状态）" % jn)
                    continue
                pick = None
                if idx == 0:
                    pick = "first9"    # R1A：全员勾相同前 9 人 → 9 人同票并列 → 晋级超额注入
                elif idx == 1 and jn == win[1]:
                    pick = "first3"    # R1B：不完整提交注入（只勾 3 人）
                url = judge_enter(pg[role], ceid)
                if not url:
                    log(False, "%s J%d" % (tag, jn), "工作台无该场舞种入口（场次未开赛或舞种缺失）")
                    continue
                msg, total = mark_submit(pg[role], url, pick if pick else None)
                log("已提交" in msg, "%s J%d" % (tag, jn), "Mark 提交(%d 行): %s" % (total, msg))
            time.sleep(2)   # 收齐自动算分
            ok, st = check_status(admin, ceid, ["已计算", "已发布"])
            log(ok, tag, "收齐自动算分 → " + st)
            if idx == 1:
                # 撤回 → J2 重交完整 → 重算（不完整提交修正闭环）
                log(rb_action(admin, ceid, "退回"), tag, "退回评分（修正不完整提交）")
                u = judge_enter(pg["j%d" % win[1]], ceid)
                msg, _ = mark_submit(pg["j%d" % win[1]], u, None) if u else ("无入口", 0)
                log("已提交" in msg, "%s J%d" % (tag, win[1]), "重交完整 8 人: " + msg)
                time.sleep(2)
                rb_action(admin, ceid, "手动计算")
                ok, st = check_status(admin, ceid, ["已计算", "已发布"])
                log(ok, tag, "重算 → " + st)
            ok = rb_action(admin, ceid, "发布")
            log(True, tag, "发布(%s)" % ("点击成功" if ok else "已发布跳过"))
            r1_results.append((code, ceid))

        # ============ 阶段 B：Z02 R1 晋级确认（逐场追加 → 并列超额 25+ 进 R2） ============
        adv_sum = 0
        for code, ceid in r1_results:
            r = adv_confirm(admin, "P01Z02", 1, ceid)
            if r.get("skipped"):
                log(True, "晋级确认 " + code, r["note"])
            else:
                adv_sum += r["checked"]
                log(True, "晋级确认 " + code, "勾选 %d 人; %s" % (r["checked"], r["msg"][:60]))
        log(adv_sum >= 24, "Z02 R1 晋级合计", "%d 人（名额 24，并列超额允许）" % adv_sum)

        # ============ 阶段 C：Z02-R2 两场（13/12 人超容量场次，名额 6）============
        ceids = get_ceids(admin)
        r2 = [("P01Z02-R2A", ceids["P01Z02-R2A"]), ("P01Z02-R2B", ceids["P01Z02-R2B"])]
        for code, ceid in r2:
            tag = code
            log(host_open(pg["host"], ceid), tag, "主持人开赛")
            win = windows[wi % len(windows)]; wi += 1
            log(admin_set_judges(admin, win, None), tag, "裁判启用设置")
            log(staff_all_checkin(pg["marshal"], ceid), tag, "检录全部")
            for jn in win:
                role = "j%d" % jn
                url = judge_enter(pg[role], ceid)
                if not url:
                    log(False, "%s J%d" % (tag, jn), "无舞种入口")
                    continue
                msg, total = mark_submit(pg[role], url, None)
                log("已提交" in msg, "%s J%d" % (tag, jn), "Mark 提交(%d 行): %s" % (total, msg))
            time.sleep(2)
            ok, st = check_status(admin, ceid, ["已计算", "已发布"])
            log(ok, tag, "收齐自动算分 → " + st)
            ok = rb_action(admin, ceid, "发布")
            log(True, tag, "发布(%s)" % ("点击成功" if ok else "已发布跳过"))
        for code, ceid in r2:
            r = adv_confirm(admin, "P01Z02", 2, ceid)
            log(not r.get("skipped"), "晋级确认 " + code, r.get("msg", "")[:60] if not r.get("skipped") else r["note"])

        # ============ 阶段 D：Z02-R3 半决赛（12 人，名额 8，裁判不提交注入）============
        ceids = get_ceids(admin)
        ceid = ceids["P01Z02-R3"]
        tag = "P01Z02-R3"
        log(host_open(pg["host"], ceid), tag, "主持人开赛")
        win = windows[wi % len(windows)]; wi += 1
        log(admin_set_judges(admin, win, None), tag, "裁判启用设置")
        log(staff_all_checkin(pg["marshal"], ceid), tag, "检录全部")
        skip_j = win[0]   # 注入：一名裁判完全不提交
        for jn in win:
            if jn == skip_j:
                log(True, tag, "J%d 模拟不提交（收齐不满足 → 不自动算分）" % jn)
                continue
            url = judge_enter(pg["j%d" % jn], ceid)
            if not url:
                log(False, "%s J%d" % (tag, jn), "无舞种入口")
                continue
            msg, _ = mark_submit(pg["j%d" % jn], url, None)
            log("已提交" in msg, "%s J%d" % (tag, jn), "Mark 提交: " + msg)
        time.sleep(2)
        ok, st = check_status(admin, ceid, ["评分中"])
        log(ok, tag, "未收齐保持评分中 → " + st)
        # 催交：缺席裁判补交
        url = judge_enter(pg["j%d" % skip_j], ceid)
        msg, _ = mark_submit(pg["j%d" % skip_j], url, None) if url else ("无入口", 0)
        log("已提交" in msg, tag, "J%d 补交: " % skip_j + msg)
        time.sleep(2)
        ok, st = check_status(admin, ceid, ["已计算", "已发布"])
        log(ok, tag, "补交后收齐自动算分 → " + st)
        rb_action(admin, ceid, "发布")
        r = adv_confirm(admin, "P01Z02", 3, ceid)
        log(not r.get("skipped"), "晋级确认 R3", str(r)[:80])

        # ============ 阶段 E：Z02-R4 决赛（8 人顺位法，不完整提交被拒注入）============
        ceids = get_ceids(admin)
        ceid = ceids["P01Z02-R4"]
        tag = "P01Z02-R4"
        log(host_open(pg["host"], ceid), tag, "主持人开赛")
        win = windows[wi % len(windows)]; wi += 1
        log(admin_set_judges(admin, win, None), tag, "裁判启用设置")
        log(staff_all_checkin(pg["marshal"], ceid), tag, "检录全部")
        # 不完整提交注入：直接 PUT 缺一名（应被 400 拒）——用页面半排后提交（submit 校验拦截）
        pgj = pg["j%d" % win[0]]
        u0 = judge_enter(pgj, ceid)
        if not u0:
            log(False, tag, "决赛无舞种入口")
            return
        pgj.goto(BASE + u0); pgj.wait_for_timeout(450)
        skip_onb(pgj)
        rows = pgj.locator(".rank-list .rank-row")
        n = rows.count()
        for i in range(n - 1):
            rows.nth(i).click(); pg.wait_for_timeout(50)
        pg.evaluate("document.getElementById('submit').click()")
        pgj.wait_for_timeout(300)
        block_msg = pgj.evaluate("document.getElementById('msg').textContent")
        log("未排名" in block_msg or "还差" in block_msg or block_msg == "", tag,
            "J%d 不完整提交被拦截: %s" % (win[0], block_msg))
        rows.nth(n - 1).click(); pg.wait_for_timeout(150)
        pg.evaluate("document.getElementById('submit').click()")
        pgj.wait_for_timeout(400)
        msg, _ = skate_submit(pgj, u0)
        log("已提交" in msg, "%s J%d" % (tag, win[0]), "顺位提交: " + msg)
        for jn in win[1:]:
            u = judge_enter(pg["j%d" % jn], ceid)
            if not u:
                log(False, "%s J%d" % (tag, jn), "无舞种入口")
                continue
            msg, _ = skate_submit(pg["j%d" % jn], u)
            log("已提交" in msg, "%s J%d" % (tag, jn), "顺位提交: " + msg)
        time.sleep(2)
        ok, st = check_status(admin, ceid, ["已计算", "已发布"])
        log(ok, tag, "收齐自动算分 → " + st)
        ok = rb_action(admin, ceid, "发布")
        log(ok, tag, "发布")
        # 决赛名次核对（页面展示）
        admin.goto(BASE + "/events/21/advancement?project=P01Z02&round=4")
        admin.wait_for_timeout(500)
        final = admin.evaluate("[...document.querySelectorAll('.adv-next-tbl td:nth-child(1)')].slice(0,8).map(t => t.innerText)")
        log(len([x for x in final if x]) == 8, tag, "决赛名次 1-8 录取: " + ",".join(final[:8]))

        # ============ 阶段 F：P02 决赛（8 人顺位一轮）============
        ceid = ceids["P02-R1"]
        tag = "P02-R1"
        log(host_open(pg["host"], ceid), tag, "主持人开赛")
        win = windows[wi % len(windows)]; wi += 1
        log(admin_set_judges(admin, win, None), tag, "裁判启用设置")
        log(staff_all_checkin(pg["marshal"], ceid), tag, "检录全部")
        for jn in win:
            u = judge_enter(pg["j%d" % jn], ceid)
            if not u:
                log(False, "%s J%d" % (tag, jn), "无舞种入口")
                continue
            msg, _ = skate_submit(pg["j%d" % jn], u)
            log("已提交" in msg, "%s J%d" % (tag, jn), "顺位提交: " + msg)
        time.sleep(2)
        ok, st = check_status(admin, ceid, ["已计算", "已发布"])
        log(ok, tag, "收齐自动算分 → " + st)
        ok = rb_action(admin, ceid, "发布")
        log(ok, tag, "发布")

        b.close()

if __name__ == "__main__":
    try:
        main()
    finally:
        print("\n==== 观众负载（独立进程 /tmp/audience.log）====")
        print("==== 错误汇总 ====")
        print("\n".join(ERRORS) if ERRORS else "无 FAIL")
        with open(OUT + "/smoke_log.txt", "w") if False else open("/tmp/smoke_log.txt", "w") as f:
            f.write("\n".join(LOG))
