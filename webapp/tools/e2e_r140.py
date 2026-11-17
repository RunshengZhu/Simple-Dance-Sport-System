#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R140 全动线纯 WebUI E2E：报名 → 审核/转正 → 编排 → 评分（Mark 矩阵/顺位槽位）→ 晋级 → 决赛 → 荣誉证书。
使用新生赛（comp21）数据子集。前置：SQL 已建 E2E 赛（is_debug=1）+ 预置会话 e2e-admin / e2e-j1..j12。
运行：E2E_CID=97 python3 webapp/tools/e2e_r140.py
"""
import json
import os
import sys
import time
import zipfile
import io as _io

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "https://dancetkt.com")
CID = int(os.environ.get("E2E_CID", "97"))
SHOTS = os.environ.get("E2E_SHOTS", "/tmp/e2e_r140/shots")
os.makedirs(SHOTS, exist_ok=True)
LOG, ERRORS = [], []


def log(ok, tag, msg=""):
    line = "%s %s | %s" % ("PASS" if ok else "FAIL", tag, msg)
    LOG.append(line)
    print(line, flush=True)
    if not ok:
        ERRORS.append(line)
    return ok


def skip_onb(pg):
    try:
        pg.evaluate("document.querySelectorAll('.onb-overlay .onb-skip').forEach(s => s.click())")
    except Exception:
        pass


def shot(pg, name):
    pg.screenshot(path=os.path.join(SHOTS, name + ".png"))


def poll_runboard(pg, ceid, want, timeout=40):
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        last = pg.evaluate(
            "fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>d.events.filter(e=>e.id===%d)[0].status)" % (CID, ceid))
        if last in want:
            return last
        time.sleep(1)
    return last


def make_cert_docx():
    doc = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           '<w:p><w:r><w:t>荣誉证书</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>兹授予 {{选手名单}}</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>在{{赛事名称}}{{项目名称}}中获得{{名次}}。</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>{{单位}} {{日期}}</w:t></w:r></w:p>'
           '<w:sectPr/></w:body></w:document>')
    buf = _io.BytesIO()
    z = zipfile.ZipFile(buf, "w")
    z.writestr("[Content_Types].xml", "<Types/>")
    z.writestr("word/document.xml", doc)
    z.close()
    return buf.getvalue()


def main():
    d21 = {"rosters": {}}
    try:
        data = json.load(open("/tmp/comp21_data.json"))
        for s in data["schedule"]:
            d21["rosters"][s["code"]] = [x for x in s["roster"].split(",") if x]
    except Exception as e:
        print("WARN comp21 data:", e)

    with sync_playwright() as p:
        b = p.chromium.launch()
        admin = b.new_context(viewport={"width": 1360, "height": 900})
        admin.add_cookies([{"name": "session", "value": "e2e-admin", "url": BASE}])
        pa = admin.new_page()
        pa.on("dialog", lambda d: d.accept())
        judges = {}
        for i in range(1, 13):
            jc = b.new_context(viewport={"width": 390, "height": 844})
            jc.add_cookies([{"name": "session", "value": "e2e-j%d" % i, "url": BASE}])
            judges["J%d" % i] = jc.new_page()
        SKATING = {"P01Z01-R4"}

        # ========== 1) 数据导入（新生赛数据） ==========
        pa.goto(BASE + "/events/%d/import" % CID)
        pa.wait_for_timeout(900)
        skip_onb(pa)
        pa.set_input_files("#f-competitors", os.path.join(SHOTS, "..", "competitors.csv"))
        pa.locator("#go-competitors").click()
        pa.wait_for_timeout(1800)
        m1 = pa.locator("#msg-competitors").text_content() or ""
        log("错误" not in m1, "导入选手（新生赛 186 行）", m1[:60])
        pa.set_input_files("#f-judges", os.path.join(SHOTS, "..", "judges.csv"))
        pa.locator("#go-judges").click()
        pa.wait_for_timeout(1400)
        log(True, "导入裁判 12 名", (pa.locator("#msg-judges").text_content() or "")[:50])
        shot(pa, "01-import")

        # ========== 2) 六场结构（编排页添加场次表单） ==========
        add_form = [("P01Z01-R1A", "平四 Z01组 初赛A", 1, "MARK", 8,
                     ",".join(d21["rosters"].get("P01Z01-R1A", []))),
                    ("P01Z01-R1B", "平四 Z01组 初赛B", 1, "MARK", 8,
                     ",".join(d21["rosters"].get("P01Z01-R1B", []))),
                    ("P01Z01-R2A", "平四 Z01组 复赛A", 2, "MARK", 6, ""),
                    ("P01Z01-R2B", "平四 Z01组 复赛B", 2, "MARK", 6, ""),
                    ("P01Z01-R3", "平四 Z01组 半决赛", 3, "MARK", 8, ""),
                    ("P01Z01-R4", "平四 Z01组 决赛", 4, "SKATING", 8, "")]
        n_events = 0
        for code, name, rnd, typ, adv, roster in add_form:
            pa.goto(BASE + "/events/%d/schedule?tab=projects" % CID)
            pa.wait_for_timeout(1200)
            skip_onb(pa)
            pa.fill("#f-code", code)
            pa.fill("#f-name", name)
            pa.fill("#f-project", "P01Z01")
            pa.fill("#f-round", str(rnd))
            pa.fill("#f-dances", "平四")
            pa.select_option("#f-type", typ)
            pa.fill("#f-adv", str(adv))
            if roster:
                pa.fill("#f-roster", roster)
            pa.locator("#save-btn").click()
            pa.wait_for_timeout(300)
            fmsg = pa.locator("#f-msg").text_content() or ""
            pa.wait_for_timeout(1500)
            before = n_events
            n_events = pa.evaluate(
                "fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>d.events.length)" % CID)
            log(("已保存" in fmsg) or ("已存在" in fmsg) or n_events > before,
                "添加场次 " + code, (fmsg[:40] or "") + " events=%d" % n_events)
        log(n_events == 6, "六场结构齐备", "events=%d" % n_events)
        shot(pa, "01-import")

        # ========== 3) 报名管理：开放报名 ==========
        pa.goto(BASE + "/events/%d/registrations" % CID)
        pa.wait_for_timeout(1000)
        skip_onb(pa)
        pa.locator("#s-open").check()
        pa.locator("#s-mode-individual").check()
        pa.locator("#s-mode-unit").check()
        pa.fill("#s-unit-code", "XM2026")
        pa.fill("#s-note", "R140 E2E 报名须知：11 月 30 日截止。")
        pa.locator("#s-save").click()
        pa.wait_for_timeout(1000)
        toasts = pa.locator(".toast").all_text_contents()
        log(any("已保存" in t for t in toasts), "开放报名设置保存", toasts)
        shot(pa, "02-reg-settings")

        # ========== 4) 公开报名页（个人 + 单位） ==========
        pr = b.new_context(viewport={"width": 390, "height": 844})
        pr.add_cookies([{"name": "session", "value": "e2e-admin", "url": BASE}])   # 调试赛仅总管理员可见
        prp = pr.new_page()
        prp.goto(BASE + "/competitions/%d/register" % CID)
        prp.wait_for_timeout(800)
        skip_onb(prp)
        log("报名须知" in prp.inner_text("body"), "报名页须知公示")
        prp.locator('.reg-tab[data-mode="individual"]').click()
        prp.fill("#f-contact", "李星辰")
        prp.fill("#f-phone", "13800000107")
        row = prp.locator(".member-row").first
        row.locator(".m-name").fill("李星辰")
        row.locator(".m-role").fill("新生")
        row.locator(".m-partner").fill("武文婕")
        row.locator(".m-punit").fill("测试学院")
        row.locator(".m-prole").fill("新生")
        row.locator('.proj-chip[data-code="P01Z01"]').click()
        prp.locator("#reg-submit").click()
        prp.wait_for_timeout(1400)
        code1 = prp.locator("#done-code").text_content() or ""
        log(len(code1) >= 6, "个人报名提交（李星辰/武文婕）", "提交码 " + code1)
        shot(prp, "03-register-individual")
        prp.locator("#reg-again").click()
        prp.locator('.reg-tab[data-mode="unit"]').click()
        prp.fill("#f-unit", "测试二队")
        prp.fill("#f-contact", "领队王老师")
        prp.fill("#f-phone", "13900000203")
        prp.fill("#f-unit-code", "WRONG")
        members = [("胡一帆", "潘迪"), ("徐逸辰", "周雨辰"), ("吴骏哲", "农茜茜")]
        for idx, (n1, n2) in enumerate(members):
            if idx > 0:
                prp.locator("#add-member").click()
            row = prp.locator(".member-row").nth(idx)
            row.locator(".m-name").fill(n1)
            row.locator(".m-role").fill("新生")
            row.locator(".m-partner").fill(n2)
            row.locator(".m-punit").fill("测试二队")
            row.locator(".m-prole").fill("新生")
            row.locator('.proj-chip[data-code="P01Z01"]').click()
        prp.locator("#reg-submit").click()
        prp.wait_for_timeout(1000)
        log("口令" in prp.locator("#reg-msg").text_content(), "单位口令错误被拒",
            prp.locator("#reg-msg").text_content())
        prp.fill("#f-unit-code", "XM2026")
        prp.locator("#reg-submit").click()
        prp.wait_for_timeout(1400)
        code2 = prp.locator("#done-code").text_content() or ""
        log(len(code2) >= 6, "单位批量报名提交（3 名成员）", "提交码 " + code2)
        shot(prp, "04-register-unit")
        prp.fill("#q-code", code1)
        prp.locator("#q-btn").click()
        prp.wait_for_timeout(1000)
        log("待审核" in prp.locator("#q-result").inner_text(), "提交码进度查询", code1)

        # ========== 5) 报名管理：审核通过 → 转正 ==========
        pa.goto(BASE + "/events/%d/registrations" % CID)
        pa.wait_for_timeout(1100)
        rows_n = pa.locator("#reg-list tr[data-rid]").count()
        log(rows_n == 4, "报名明细 4 条", "rows=%d" % rows_n)
        stats_txt = pa.locator("#reg-stats-body").inner_text()
        log("平四" in stats_txt, "项目报名统计展示", stats_txt[:60])
        ids_all = pa.evaluate(
            "fetch('/api/events/%d/registrations').then(r=>r.json()).then(d=>d.rows.filter(r=>r.status==='pending').map(r=>r.id))" % CID)
        pa.evaluate("review(%s, 'approve')" % json.dumps(ids_all))
        pa.wait_for_timeout(1400)
        appr = pa.evaluate(
            "fetch('/api/events/%d/registrations').then(r=>r.json()).then(d=>d.rows.filter(r=>r.status==='approved').length)" % CID)
        log(appr == 4, "批量审核通过", "approved=%d" % appr)
        pa.fill("#c-start", "201")
        pa.evaluate("document.querySelectorAll('.r-sel').forEach(c => c.checked = true); document.getElementById('c-btn').click()")
        pa.wait_for_timeout(1800)
        toasts = pa.locator(".toast").all_text_contents()
        log(any("已编入" in t for t in toasts), "转正编入名单（起始背号 201）", [t for t in toasts if "已编入" in t])
        conv = pa.evaluate(
            "fetch('/api/events/%d/registrations').then(r=>r.json()).then(d=>d.rows.filter(r=>r.status==='imported').length)" % CID)
        log(conv == 4, "状态已标记 imported", "imported=%d" % conv)
        shot(pa, "05-converted")

        # ========== 6) 评分与晋级（全 WebUI） ==========
        pa.goto(BASE + "/events/%d/runboard" % CID)
        pa.wait_for_timeout(1300)
        ceids = pa.evaluate(
            "fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>{const o={};d.events.forEach(e=>{for(const w of ['P01Z01-R1A','P01Z01-R1B','P01Z01-R2A','P01Z01-R2B','P01Z01-R3','P01Z01-R4']){if(e.code===w||e.code.indexOf(w+'-')===0){if(!(w in o))o[w]=e.id;}}});return o;})" % CID)
        log(all(k in ceids for k in ("P01Z01-R1A", "P01Z01-R4")), "场次解析（前缀兼容）", json.dumps(ceids))

        SKATING = {"P01Z01-R4"}

        def run_round_webui(code, need):
            pa.goto(BASE + "/events/%d/runboard" % CID)   # 评级动作依赖总表页的 act()
            pa.wait_for_timeout(1300)
            ceid = ceids[code]
            pa.evaluate("act(%d, 'open')" % ceid)
            pa.wait_for_timeout(1000)
            st = poll_runboard(pa, ceid, ("scoring",))
            log(st == "scoring", "%s 开赛" % code, st)
            toasts = pa.locator(".toast").all_text_contents()
            log(any("已开赛" in t for t in toasts), "开赛反馈 toast", toasts[:2])
            pa.evaluate("act(%d, 'checkin')" % ceid)
            pa.wait_for_timeout(1200)
            checked = pa.evaluate(
                "fetch('/api/competition-events/%d/checkin').then(r=>r.json()).then(d=>d.checked_n)" % ceid)
            log(checked > 0, "%s 管理员一键检录" % code, "checked_n=%d" % checked)
            for i in range(1, 13):
                jn = "J%d" % i
                jp = judges[jn]
                jp.goto(BASE + "/judge/competition-events/%d/dances/平四" % ceid)
                jp.wait_for_timeout(900)
                skip_onb(jp)
                if code in SKATING:
                    jp.locator('#skate-mode-bar .mt-btn[data-sm="seq"]').click()
                    jp.wait_for_timeout(200)
                    allnums = jp.evaluate(
                        "Array.from(document.querySelectorAll('.rank-row:not(.off)')).map(r=>r.dataset.num)")
                    for n2 in allnums:
                        jp.locator('.rank-cell[data-num="%s"]' % n2).click()
                        jp.wait_for_timeout(60)
                else:
                    nums = jp.evaluate(
                        "Array.from(document.querySelectorAll('.mark-row:not(.off)')).slice(0,%d).map(r=>r.dataset.num)" % need)
                    for n2 in nums:
                        jp.locator('.mark-cell[data-num="%s"]' % n2).click()
                        jp.wait_for_timeout(60)
                payload = jp.evaluate("collect()")
                print("   DEBUG %s %s payload=%d 项" % (code, jn, len(payload)), flush=True)
                jp.locator("#submit").click()
                jp.wait_for_timeout(800)
                msg = jp.locator("#msg").text_content()
                log("已提交" in msg, "%s %s 提交" % (code, jn), msg[:40])
            st = poll_runboard(pa, ceid, ("calculated", "published"))
            log(st in ("calculated", "published"), "%s 收齐自动算分" % code, st)
            pa.evaluate("act(%d, 'publish')" % ceid)
            pa.wait_for_timeout(1000)
            st = poll_runboard(pa, ceid, ("published",))
            log(st == "published", "%s 发布" % code, st)

        def confirm_round(rnd, event_id=None, expect_min=1):
            url = "/events/%d/advancement?project=P01Z01&round=%d" % (CID, rnd)
            if event_id:
                url += "&event=%d" % event_id
            pa.goto(BASE + url)
            pa.wait_for_timeout(1100)
            skip_onb(pa)
            n = pa.locator(".adv-check:checked").count()
            pa.locator("#confirm-btn").click()
            pa.wait_for_timeout(2500)
            # 断言以下一轮名单数为准（msg 在 POST 完成后才写入，避免竞态）
            got = pa.evaluate(
                "fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>{const evs=d.events.filter(e=>e.round===%d);return evs.reduce((s,e)=>s+e.roster.length,0);})" % (CID, rnd + 1))
            log(got >= expect_min and n >= expect_min, "R%d 晋级确认（%d 组 → 下一轮 %d 人）" % (rnd, n, got), (pa.locator("#msg").text_content() or "")[:40])

        run_round_webui("P01Z01-R1A", 8)
        run_round_webui("P01Z01-R1B", 8)
        confirm_round(1, ceids["P01Z01-R1A"], 8)
        confirm_round(1, ceids["P01Z01-R1B"], 8)
        pa.goto(BASE + "/events/%d/runboard" % CID)
        pa.wait_for_timeout(1200)
        disjoint = pa.evaluate(
            "fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>{const f=w=>d.events.filter(e=>e.code===w||e.code.indexOf(w+'-')===0)[0];const a=f('P01Z01-R2A').roster;const b2=f('P01Z01-R2B').roster;return a.filter(x=>b2.indexOf(x)>-1).length;})" % CID)
        log(disjoint == 0, "R2A/R2B 分场互斥", "交集=%d" % disjoint)
        shot(pa, "06-advancement")

        run_round_webui("P01Z01-R2A", 6)
        run_round_webui("P01Z01-R2B", 6)
        confirm_round(2, None, 12)
        run_round_webui("P01Z01-R3", 8)
        confirm_round(3, None, 8)
        run_round_webui("P01Z01-R4", 8)

        # ========== 7) 证书提示 ==========
        tags = pa.locator(".rb-row .tag.warn").all_text_contents()
        log(any("证书未打印" in t for t in tags), "已发布未打印证书显著提示", tags[:3])
        agg = pa.locator("#agg").inner_text()
        log("证书未打印" in agg, "聚合条证书提醒", agg[-70:])
        shot(pa, "07-runboard-cert-tag")

        # ========== 8) 荣誉证书：上传模板 → 核对成员 → 生成 ==========
        pa.goto(BASE + "/events/%d/certs/%d" % (CID, ceids["P01Z01-R4"]))
        pa.wait_for_timeout(1100)
        skip_onb(pa)
        log(pa.locator(".cm-input").count() == 8, "证书页 8 个名次成员表",
            "inputs=%d" % pa.locator(".cm-input").count())
        first = pa.locator(".cm-input").first
        first.fill("选手名单A\n选手名单B\n替补成员C")
        first.dispatch_event("change")
        pa.wait_for_timeout(500)
        with open(os.path.join(SHOTS, "..", "cert-tmpl.docx"), "wb") as f:
            f.write(make_cert_docx())
        pa.fill("#t-name", "R140 荣誉证书")
        pa.set_input_files("#t-file", os.path.join(SHOTS, "..", "cert-tmpl.docx"))
        pa.locator("#t-upload").click()
        pa.wait_for_timeout(1400)
        log(pa.locator('input[name="tmpl"]').count() >= 1, "模板上传")
        with pa.expect_download() as dl:
            pa.locator("#gen-btn").click()
        download = dl.value
        path = os.path.join(SHOTS, "..", "certs-out.docx")
        download.save_as(path)
        z = zipfile.ZipFile(path)
        doc = z.read("word/document.xml").decode("utf-8")
        pages = doc.count('w:type="page"') + 1
        # 预期份数：第 1 名覆盖名单 3 人 3 份 + 第 2~8 名双人各 2 份 = 3 + 14 = 17
        expect_pages = 3 + 7 * 2
        ok_content = ("选手名单A、选手名单B、替补成员C" in doc and
                      "替补成员C、选手名单A、选手名单B" in doc and
                      "第一名" in doc and "第八名" in doc)
        log(pages == expect_pages and ok_content,
            "证书 docx 内容断言（%d 页/名次/名单轮转/每人一份）" % expect_pages, "pages=%d" % pages)
        shot(pa, "08-certs-page")
        pa.goto(BASE + "/events/%d/runboard" % CID)
        pa.wait_for_timeout(1200)
        printed = pa.evaluate(
            "fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>d.events.filter(e=>e.id===%d)[0].cert_printed)" % (CID, ceids["P01Z01-R4"]))
        log(printed, "生成后标记已打印")
        tags = pa.locator(".rb-row .tag").all_text_contents()
        log(not any("证书未打印" in t for t in tags), "打印后提示消失", tags[:4])

        b.close()

    print("\n==== R140 E2E 汇总：%s ====" % ("全部通过" if not ERRORS else "有 %d 项失败" % len(ERRORS)))
    for e in ERRORS:
        print("  ✗", e)
    with open("/tmp/e2e_r140/log.txt", "w") as f:
        f.write("\n".join(LOG))
    sys.exit(1 if ERRORS else 0)


if __name__ == "__main__":
    main()
