#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R142 全动线纯 WebUI E2E：建赛→设项→报名(含异常)→审核转正→赛程→评分→晋级→决赛→证书→打印台。
使用新生赛（comp21）数据子集，覆盖已知异常场景。前置：SQL 已建 E2E 赛（is_debug=1）+ 预置会话。"""
import json, os, sys, time, zipfile, io as _io, base64, csv
from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "https://dancetkt.com")
CID = int(os.environ.get("E2E_CID", "97"))
SHOTS = "/tmp/e2e_r142/shots"
os.makedirs(SHOTS, exist_ok=True)
LOG, ERRORS = [], []

def log(ok, tag, msg=""):
    line = "%s %s | %s" % ("PASS" if ok else "FAIL", tag, msg)
    LOG.append(line); print(line, flush=True)
    if not ok: ERRORS.append(line)
    return ok

def shot(pg, name): pg.screenshot(path=os.path.join(SHOTS, name + ".png"))
def skip_onb(pg):
    try: pg.evaluate("document.querySelectorAll('.onb-overlay .onb-skip').forEach(s => s.click())")
    except: pass

def make_cert_docx():
    doc = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           '<w:p><w:r><w:t>荣誉证书</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>兹授予 {{选手名单}}</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>在{{赛事名称}}{{项目名称}}中获得{{名次}}。</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>{{单位}} {{日期}}</w:t></w:r></w:p>'
           '<w:sectPr/></w:body></w:document>')
    buf = _io.BytesIO(); z = zipfile.ZipFile(buf, "w")
    z.writestr("[Content_Types].xml", "<Types/>"); z.writestr("word/document.xml", doc); z.close()
    return buf.getvalue()

def main():
    from playwright.sync_api import sync_playwright
    d21 = json.load(open("/tmp/comp21_data.json"))
    with sync_playwright() as pw:
        b = pw.chromium.launch()
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

        # ===== Phase 1: 数据导入（新生赛数据，按步骤走对应页面） =====
        # ③ 参赛名单 → 导入选手
        pa.goto(BASE + "/events/%d/roster" % CID); pa.wait_for_timeout(1200); skip_onb(pa)
        pa.set_input_files("#f-competitors", "/tmp/e2e_r142/competitors.csv")
        pa.locator("#go-competitors").click(); pa.wait_for_timeout(2000)
        m = pa.locator("#msg-competitors").text_content() or ""
        log("错误" not in m, "P3 导入选手", m[:50])
        # ⑤ 工作人员 → 导入裁判
        pa.goto(BASE + "/events/%d/staff-links" % CID); pa.wait_for_timeout(1000); skip_onb(pa)
        pa.set_input_files("#f-judges", "/tmp/e2e_r142/judges.csv")
        pa.locator("#go-judges").click(); pa.wait_for_timeout(1500)
        m = pa.locator("#msg-judges").text_content() or ""
        log("错误" not in m, "P5 导入裁判", m[:50])
        # ④ 赛程编排 → 导入赛程
        pa.goto(BASE + "/events/%d/schedule?tab=projects" % CID); pa.wait_for_timeout(1200); skip_onb(pa)
        pa.set_input_files("#f-schedule", "/tmp/e2e_r142/schedule.csv")
        pa.locator("#go-schedule").click(); pa.wait_for_timeout(2500)
        m = pa.locator("#msg-schedule").text_content() or ""
        log("错误" not in m, "P4 导入赛程", m[:50])
        n_events = pa.evaluate("fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>d.events.length)" % CID)
        log(n_events >= 6, "六场结构齐备", "events=%d" % n_events)
        shot(pa, "01-import")
        
        # ===== Phase 2: 设项（自然数编号） =====
        pa.goto(BASE + "/events/%d/registrations" % CID); pa.wait_for_timeout(1100); skip_onb(pa)
        pa.locator("#pj-add").click() if False else None
        # 设项在 proj-card：填名称+点添加（会自动编号）
        pj_names = ["新生平四单项", "新生伦巴单项", "新生交谊舞A三项"]
        for pn in pj_names:
            pa.fill("#pj-name", pn)
            pa.locator("#pj-add").click()
            pa.wait_for_timeout(800)
        pa.wait_for_timeout(500)
        proj_count = pa.evaluate("fetch('/api/events/%d/registrations').then(r=>r.json()).then(d=>d.projects.length)" % CID)
        log(proj_count >= 3, "② 设项（自然数编号 1,2,3…）", "projects=%d" % proj_count)
        shot(pa, "02-projects")

        # ===== Phase 3: 开放报名 + 提交（含异常） =====
        pa.locator("#s-open").check()
        pa.locator("#s-mode-individual").check()
        pa.locator("#s-mode-unit").check()
        pa.fill("#s-unit-code", "XM2026")
        pa.fill("#s-note", "R142 E2E 须知")
        pa.locator("#s-save").click()
        pa.wait_for_timeout(1000)
        log(any("已保存" in t for t in pa.locator(".toast").all_text_contents()), "开放报名设置")
        # 入口卡
        qr_ok = pa.locator("#entry-qr").get_attribute("src") or ""
        log(qr_ok.startswith("data:image/png"), "公开入口二维码渲染")
        shot(pa, "03-entry-links")

        # 公开报名页：个人（正常+缺性别+去重）
        pr = b.new_context(viewport={"width": 390, "height": 844})
        pr.add_cookies([{"name": "session", "value": "e2e-admin", "url": BASE}])
        prp = pr.new_page()
        prp.goto(BASE + "/competitions/%d/register" % CID)
        prp.wait_for_timeout(1000); skip_onb(prp)
        # a. 正常提交（双项目）
        prp.locator('.reg-tab[data-mode="individual"]').click()
        prp.fill("#f-contact", "李星辰"); prp.fill("#f-phone", "138001")
        row = prp.locator(".member-row").first
        row.locator(".m-name").fill("李星辰"); row.locator(".m-gender").select_option("男")
        row.locator(".m-partner").fill("武文婕"); row.locator(".m-role").fill("新生")
        row.locator('.proj-chip[data-code="1"]').click()
        row.locator('.proj-chip[data-code="2"]').click()
        prp.locator("#reg-submit").click(); prp.wait_for_timeout(1400)
        code1 = prp.locator("#done-code").text_content() or ""
        log(len(code1) >= 6, "个人正常提交", code1)
        # b. 缺性别 → 400
        prp.locator("#reg-again").click()
        prp.locator('.reg-tab[data-mode="individual"]').click()
        prp.fill("#f-contact", "张三"); prp.fill("#f-phone", "138002")
        row = prp.locator(".member-row").first
        row.locator(".m-name").fill("张三"); row.locator(".m-gender").select_option("")
        row.locator('.proj-chip[data-code="1"]').click()
        prp.locator("#reg-submit").click(); prp.wait_for_timeout(800)
        log("性别" in prp.locator("#reg-msg").text_content(), "缺性别被拒", prp.locator("#reg-msg").text_content()[:40])
        # c. 去重：同姓名同联系方式重提交 → 项目合并
        prp.fill("#f-contact", "李星辰"); prp.fill("#f-phone", "138001")
        row = prp.locator(".member-row").first
        row.locator(".m-name").fill("李星辰"); row.locator(".m-gender").select_option("男")
        row.locator(".m-partner").fill("武文婕")
        row.locator('.proj-chip[data-code="1"]').click()
        row.locator('.proj-chip[data-code="2"]').click()
        prp.locator("#reg-submit").click(); prp.wait_for_timeout(1400)
        d = pa.evaluate("fetch('/api/events/%d/registrations').then(r=>r.json()).then(d=>d.rows.filter(r=>r.name==='李星辰')[0].projects)" % CID)
        projs = sorted(d.split(","))
        log(projs == ["1", "2"], "去重合并（项目集合并）", "projects=%s" % projs)
        # d. 单位：口令错误 → 403
        prp.locator("#reg-again").click()
        prp.locator('.reg-tab[data-mode="unit"]').click()
        prp.fill("#f-unit", "测试二队"); prp.fill("#f-contact", "领队"); prp.fill("#f-phone", "139")
        prp.fill("#f-unit-code", "WRONG")
        for i in range(3):
            if i > 0: prp.locator("#add-member").click()
            row = prp.locator(".member-row").nth(i)
            row.locator(".m-name").fill("队员%d" % (i + 1)); row.locator(".m-gender").select_option("男")
            row.locator(".m-role").fill("新生")
            row.locator('.proj-chip[data-code="1"]').click()
        prp.locator("#reg-submit").click(); prp.wait_for_timeout(800)
        log("口令" in prp.locator("#reg-msg").text_content(), "单位口令错误被拒", prp.locator("#reg-msg").text_content()[:40])
        prp.fill("#f-unit-code", "XM2026")
        prp.locator("#reg-submit").click(); prp.wait_for_timeout(1400)
        code2 = prp.locator("#done-code").text_content() or ""
        log(len(code2) >= 6, "单位正常提交（3 成员）", code2)
        shot(prp, "04-register")

        # ===== Phase 4: 审核 + 转正 =====
        pa.goto(BASE + "/events/%d/registrations" % CID); pa.wait_for_timeout(1100)
        ids_all = pa.evaluate(
            "fetch('/api/events/%d/registrations').then(r=>r.json()).then(d=>d.rows.filter(r=>r.status==='pending').map(r=>r.id))" % CID)
        pa.evaluate("review(%s, 'approve')" % json.dumps(ids_all))
        pa.wait_for_timeout(1400)
        appr = pa.evaluate("fetch('/api/events/%d/registrations').then(r=>r.json()).then(d=>d.rows.filter(r=>r.status==='approved').length)" % CID)
        log(appr == len(ids_all), "批量审核通过（%d 条）" % len(ids_all), "approved=%d" % appr)
        pa.fill("#c-start", "201")
        pa.evaluate("document.querySelectorAll('.r-sel').forEach(c => c.checked = true); document.getElementById('c-btn').click()")
        pa.wait_for_timeout(1800)
        conv = pa.evaluate("fetch('/api/events/%d/registrations').then(r=>r.json()).then(d=>d.rows.filter(r=>r.status==='imported').length)" % CID)
        log(conv == len(ids_all), "转正编入名单", "imported=%d" % conv)
        shot(pa, "05-converted")

        # ===== Phase 5: 赛程编排（添加场次） =====
        pa.goto(BASE + "/events/%d/schedule?tab=projects" % CID); pa.wait_for_timeout(1200); skip_onb(pa)
        add_form = [("P01Z01-R1A", "平四初赛A", 1, "MARK", 8, ",".join(d21["rosters"].get("P01Z01-R1A", []))),
                    ("P01Z01-R1B", "平四初赛B", 1, "MARK", 8, ",".join(d21["rosters"].get("P01Z01-R1B", []))),
                    ("P01Z01-R2A", "平四复赛A", 2, "MARK", 6, ""),
                    ("P01Z01-R2B", "平四复赛B", 2, "MARK", 6, ""),
                    ("P01Z01-R3", "平四半决赛", 3, "MARK", 8, ""),
                    ("P01Z01-R4", "平四决赛", 4, "SKATING", 8, "")]
        for code, name, rnd, typ, adv, roster in add_form:
            pa.goto(BASE + "/events/%d/schedule?tab=projects" % CID)
            pa.wait_for_timeout(1200); skip_onb(pa)
            pa.fill("#f-code", code); pa.fill("#f-name", name)
            pa.fill("#f-project", "1"); pa.fill("#f-round", str(rnd))
            pa.fill("#f-dances", "平四"); pa.select_option("#f-type", typ)
            pa.fill("#f-adv", str(adv))
            if roster: pa.fill("#f-roster", roster)
            pa.locator("#save-btn").click()
            pa.wait_for_timeout(1800)
        n_events = pa.evaluate("fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>d.events.length)" % CID)
        log(n_events == 6, "六场结构齐备", "events=%d" % n_events)
        shot(pa, "06-schedule")

        # ===== Phase 6: 比赛（Mark 矩阵 + 顺位槽位 + 晋级） =====
        pa.goto(BASE + "/events/%d/runboard" % CID); pa.wait_for_timeout(1300)
        ceids = pa.evaluate(
            "fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>{const o={};d.events.forEach(e=>{for(const w of ['P01Z01-R1A','P01Z01-R1B','P01Z01-R2A','P01Z01-R2B','P01Z01-R3','P01Z01-R4']){if(e.code===w||e.code.indexOf(w+'-')===0){if(!(w in o))o[w]=e.id;}}});return o;})" % CID)
        SKATING = {"P01Z01-R4"}

        def run_round(code, need):
            ceid = ceids[code]
            pa.evaluate("act(%d, 'open')" % ceid); pa.wait_for_timeout(1000)
            st = poll_runboard(pa, ceid, ("scoring",))
            log(st == "scoring", "%s 开赛" % code, st)
            pa.evaluate("act(%d, 'checkin')" % ceid); pa.wait_for_timeout(1200)
            checked = pa.evaluate("fetch('/api/competition-events/%d/checkin').then(r=>r.json()).then(d=>d.checked_n)" % ceid)
            log(checked > 0, "%s 检录" % code, "checked=%d" % checked)
            for i in range(1, 13):
                jn = "J%d" % i; jp = judges[jn]
                jp.goto(BASE + "/judge/competition-events/%d/dances/平四" % ceid)
                jp.wait_for_timeout(900); skip_onb(jp)
                if code in SKATING:
                    jp.locator('#skate-mode-bar .mt-btn[data-sm="seq"]').click()
                    jp.wait_for_timeout(200)
                    allnums = jp.evaluate("Array.from(document.querySelectorAll('.rank-row:not(.off)')).map(r=>r.dataset.num)")
                    for n2 in allnums:
                        jp.locator('.rank-cell[data-num="%s"]' % n2).click(); jp.wait_for_timeout(60)
                else:
                    nums = jp.evaluate("Array.from(document.querySelectorAll('.mark-row:not(.off)')).slice(0,%d).map(r=>r.dataset.num)" % need)
                    for n2 in nums:
                        jp.locator('.mark-cell[data-num="%s"]' % n2).click(); jp.wait_for_timeout(60)
                payload = jp.evaluate("collect()")
                jp.locator("#submit").click(); jp.wait_for_timeout(800)
                log("已提交" in jp.locator("#msg").text_content(), "%s %s 提交" % (code, jn), jp.locator("#msg").text_content()[:30])
            st = poll_runboard(pa, ceid, ("calculated", "published"))
            log(st in ("calculated", "published"), "%s 收齐自动算分" % code, st)
            pa.evaluate("act(%d, 'publish')" % ceid); pa.wait_for_timeout(1000)
            log(poll_runboard(pa, ceid, ("published",)) == "published", "%s 发布" % code, st)

        def confirm_round(rnd, event_id=None, expect_min=1):
            url = "/events/%d/advancement?project=P01Z01&round=%d" % (CID, rnd)
            if event_id: url += "&event=%d" % event_id
            pa.goto(BASE + url); pa.wait_for_timeout(1100); skip_onb(pa)
            n = pa.locator(".adv-check:checked").count()
            pa.locator("#confirm-btn").click(); pa.wait_for_timeout(2500)
            got = pa.evaluate("fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>{const evs=d.events.filter(e=>e.round===%d);return evs.reduce((s,e)=>s+e.roster.length,0);})" % (CID, rnd + 1))
            log(got >= expect_min and n >= expect_min, "R%d 晋级确认（%d → %d）" % (rnd, n, got), "")

        run_round("P01Z01-R1A", 8)
        run_round("P01Z01-R1B", 8)
        confirm_round(1, ceids["P01Z01-R1A"], 8)
        confirm_round(1, ceids["P01Z01-R1B"], 8)
        pa.goto(BASE + "/events/%d/runboard" % CID); pa.wait_for_timeout(1200)
        disjoint = pa.evaluate("fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>{const f=w=>d.events.filter(e=>e.code===w||e.code.indexOf(w+'-')===0)[0];const a=f('P01Z01-R2A').roster;const b2=f('P01Z01-R2B').roster;return a.filter(x=>b2.indexOf(x)>-1).length;})" % CID)
        log(disjoint == 0, "R2A/R2B 分场互斥", "交集=%d" % disjoint)
        shot(pa, "07-advancement")
        run_round("P01Z01-R2A", 6)
        run_round("P01Z01-R2B", 6)
        confirm_round(2, None, 12)
        run_round("P01Z01-R3", 8)
        confirm_round(3, None, 8)
        run_round("P01Z01-R4", 8)

        # ===== Phase 7: 证书 =====
        tags = pa.locator(".rb-row .tag.warn").all_text_contents()
        log(any("证书未打印" in t for t in tags), "证书未打印提示", tags[:2])
        pa.goto(BASE + "/events/%d/certs/%d" % (CID, ceids["P01Z01-R4"]))
        pa.wait_for_timeout(1100); skip_onb(pa)
        log(pa.locator(".cm-input").count() == 8, "证书页名次表")
        first = pa.locator(".cm-input").first
        first.fill("选手A\n选手B\n替补C"); first.dispatch_event("change"); pa.wait_for_timeout(500)
        with open("/tmp/e2e_r142/shots/../cert-tmpl.docx", "wb") as f:
            f.write(make_cert_docx())
        pa.fill("#t-name", "R142 荣誉证书")
        pa.set_input_files("#t-file", "/tmp/e2e_r142/shots/../cert-tmpl.docx")
        pa.locator("#t-upload").click(); pa.wait_for_timeout(1400)
        log(pa.locator('input[name="tmpl"]').count() >= 1, "模板上传")
        with pa.expect_download() as dl:
            pa.locator("#gen-btn").click()
        download = dl.value
        path = "/tmp/e2e_r142/certs-out.docx"
        download.save_as(path)
        z = zipfile.ZipFile(path)
        doc = z.read("word/document.xml").decode("utf-8")
        pages = doc.count('w:type="page"') + 1
        expect_pages = 3 + 7 * 2
        ok_content = ("选手A、选手B、替补C" in doc and "替补C、选手A" in doc and "第一名" in doc)
        log(pages == expect_pages and ok_content, "证书 docx 内容断言", "pages=%d" % pages)
        shot(pa, "08-certs")
        pa.goto(BASE + "/events/%d/runboard" % CID); pa.wait_for_timeout(1200)
        printed = pa.evaluate("fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>d.events.filter(e=>e.id===%d)[0].cert_printed)" % (CID, ceids["P01Z01-R4"]))
        log(printed, "已打印标记")

        # ===== Phase 8: 公示打印台 =====
        pr = b.new_context(viewport={"width": 1360, "height": 900})
        pr.add_cookies([{"name": "session", "value": "e2e-admin", "url": BASE}])
        pp = pr.new_page()
        pp.goto(BASE + "/print")
        pp.wait_for_timeout(1200)
        print_body = pp.inner_text("body")
        log("公示打印台" in print_body, "打印台页面")
        log("平四" in print_body, "场次列表")
        shot(pp, "09-print-desk")

        b.close()

    print("\n==== R142 E2E 汇总：%s ====" % ("全部通过" if not ERRORS else "有 %d 项失败" % len(ERRORS)))
    for e in ERRORS: print("  ✗", e)
    with open("/tmp/e2e_r142/log.txt", "w") as f: f.write("\n".join(LOG))
    sys.exit(1 if ERRORS else 0)


def skip_onb(pg):
    try: pg.evaluate("document.querySelectorAll('.onb-overlay .onb-skip').forEach(s => s.click())")
    except: pass

def shot(pg, name): pg.screenshot(path=os.path.join(SHOTS, name + ".png"))

def poll_runboard(pg, ceid, want, timeout=40):
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        last = pg.evaluate("fetch('/api/events/%d/runboard').then(r=>r.json()).then(d=>d.events.filter(e=>e.id===%d)[0].status)" % (CID, ceid))
        if last in want: return last
        time.sleep(1)
    return last

def make_cert_docx():
    doc = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           '<w:p><w:r><w:t>荣誉证书</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>兹授予 {{选手名单}}</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>在{{赛事名称}}{{项目名称}}中获得{{名次}}。</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>{{单位}} {{日期}}</w:t></w:r></w:p>'
           '<w:sectPr/></w:body></w:document>')
    buf = _io.BytesIO(); z = zipfile.ZipFile(buf, "w")
    z.writestr("[Content_Types].xml", "<Types/>"); z.writestr("word/document.xml", doc); z.close()
    return buf.getvalue()


if __name__ == "__main__":
    main()
