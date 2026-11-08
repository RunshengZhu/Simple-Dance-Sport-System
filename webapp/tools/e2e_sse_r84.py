# -*- coding: utf-8 -*-
"""R84 页面级 SSE 实时流转 E2E（11 裁判，生产 comp21 / P02-R1）。

场景：14 个浏览器页面并发（管理员控制台、检录员、主持人、裁判 J1-J11 评分页），
全程不手动刷新任何目标页，验证：
  S1 控制台矩阵 11 名裁判对齐
  S2 检录员全部检录 → 控制台检录徽章、11 个裁判评分页置灰解锁 自动更新
  S3 裁判逐个提交 → 控制台进度矩阵逐行自动刷新（局部、无整页）；第 11 名交齐 → 自动计算
  S4 发布 → 主持人/检录员页面自动出现已完成场次与已发布状态
  S5 退回评分 → 裁判评分页/控制台自动回退到评分中
用法：python3 e2e_sse_r84.py [base=https://dancetkt.com]
"""
import json, os, random, re, sys, time
import urllib.request, urllib.error
from urllib.parse import urlparse, quote
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
CID = 21
CODE = "P02-R1"
DANCE = "慢三单项"
ROSTER = ['160', '162', '163', '164', '165', '166', '167', '171']
OUT = "/tmp/e2e_r84"
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
R = []


def api(method, path, body=None, cookie=""):
    import urllib.request, urllib.error
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
    r = urllib.request.Request(BASE + path, method=method)
    if cookie:
        r.add_header("Cookie", cookie)
    if body is not None:
        r.data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    for _ in range(6):
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                raw = resp.read()
                try:
                    return resp.status, json.loads(raw or b"{}"), resp.headers.get("Set-Cookie", "").split(";")[0]
                except Exception:
                    return resp.status, raw.decode("utf-8-sig"), ""
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(25)
                continue
            return e.code, {}, ""
        except urllib.error.URLError:
            time.sleep(2)
    raise RuntimeError("网络重试耗尽: " + path)


def login(b):
    for _ in range(8):
        c, d, ck = api("POST", "/api/login", b)
        if c == 200:
            return ck
        if c == 429:
            time.sleep(25)
            continue
        raise AssertionError((c, d))
    raise RuntimeError("限流未解除")


def assert_(name, ok, detail=""):
    R.append({"name": name, "ok": bool(ok), "detail": str(detail)[:160]})
    print(f"[{time.time()-T0:6.1f}s] {'✓' if ok else '✗'} {name}" + (f" :: {detail}" if detail else ""), flush=True)


def wait_dom(page, expr, timeout=9000):
    """轮询页面 JS 表达式为真（不刷新页面）"""
    try:
        page.wait_for_function(f"() => Boolean({expr})", timeout=timeout, polling=300)
        return True
    except Exception:
        return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OP_NR = None   # 构建期传入 NoRedirect 才能真正禁用跟随（add_handler 不移除默认处理器）


def judge_cookie(link):
    import urllib.request, urllib.error
    global OP_NR
    if OP_NR is None:
        OP_NR = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    path = urlparse(link).path
    for _ in range(4):
        try:
            with OP_NR.open(BASE + path, timeout=30) as r:
                ck = (r.headers.get("Set-Cookie") or "").split(";")[0]
                if "session=" in ck:
                    return ck
        except urllib.error.HTTPError as e:
            ck = (e.headers.get("Set-Cookie") or "").split(";")[0]
            if "session=" in ck:
                return ck
        except urllib.error.URLError:
            pass
        time.sleep(2)
    raise RuntimeError("直达链接会话获取失败: " + path)


def main():
    # ---------- 准备：导入 J8-J11（裁判扩到 11 人）+ 退回评分 + 开场 ----------
    c, d, ck = api("POST", "/api/login", {"role": "admin", "password": "CE9DoLRhkb37R9w_bgrpDA55"})
    csv_judges = "裁判ID,姓名\n" + "".join(f"J{i},模拟裁判{i}\n" for i in range(8, 12))   # 显式 ID：幂等，不自动续号
    c, d, _ = api("POST", f"/api/events/{CID}/imports/judges", body=csv_judges, cookie=ck) if False else \
        (None, None, "")
    import urllib.request
    rq = urllib.request.Request(BASE + f"/api/events/{CID}/imports/judges", method="POST")
    rq.data = csv_judges.encode()
    rq.add_header("Content-Type", "text/csv; charset=utf-8")
    rq.add_header("Cookie", ck)
    with urllib.request.urlopen(rq, timeout=60) as resp:
        print("导入 J8-J11:", resp.status, resp.read()[:80], flush=True)
    c, d, _ = api("GET", "/api/events/21/direct-links", cookie=ck)
    links = {x["username"]: x["url"] for x in d["links"]}
    ceid = next(e["id"] for e in api("GET", f"/api/public/events/{CID}/schedule")[1]["events"] if e["code"] == CODE)
    c, d, _ = api("POST", f"/api/competition-events/{ceid}/unpublish", {}, cookie=ck)
    c, d, _ = api("POST", f"/api/competition-events/{ceid}/return-scores", {}, cookie=ck)
    c, d, _ = api("POST", f"/api/events/{CID}/auto-publish", {"auto_publish": False}, cookie=ck)
    c, d, _ = api("POST", f"/api/competition-events/{ceid}/open", {"roster": ROSTER, "reset": False}, cookie=ck)
    # 撤销全部检录（浏览器里由检录员完成，制造「置灰→解锁」的可观测变化）
    c, d, _ = api("POST", f"/api/competition-events/{ceid}/checkin", {"numbers": ROSTER, "state": False},
                  cookie=login({"role": "marshal", "username": "xinsheng-checkin", "password": "XsCheck2026",
                                "competition_id": CID}))
    print("准备完成：11 裁判 / P02-R1 评分中 / 检录清零", flush=True)

    sheet_path = f"/judge/competition-events/{ceid}/dances/{quote(DANCE, safe='')}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        def ctx_for(cookie):
            ctx = browser.new_context(viewport={"width": 1100, "height": 900}, device_scale_factor=1)
            token = cookie.split("=", 1)[1] if "=" in cookie else cookie
            ctx.add_cookies([{"name": "session", "value": token, "domain": urlparse(BASE).hostname, "path": "/"}])
            return ctx

        # 页面：控制台 / 检录 / 主持 / 11 裁判评分页
        c_admin = ctx_for(ck)
        ck_m = login({"role": "marshal", "username": "xinsheng-checkin", "password": "XsCheck2026", "competition_id": CID})
        ck_h = login({"role": "host", "username": "xinsheng-host", "password": "XsHost2026", "competition_id": CID})
        p_admin = c_admin.new_page()
        p_admin.goto(f"{BASE}/events/{CID}/console/{ceid}", wait_until="domcontentloaded")
        p_admin.wait_for_timeout(1500)
        p_marshal = ctx_for(ck_m).new_page()
        p_marshal.goto(f"{BASE}/staff", wait_until="domcontentloaded")
        p_marshal.wait_for_timeout(1200)
        p_host = ctx_for(ck_h).new_page()
        p_host.goto(f"{BASE}/staff", wait_until="domcontentloaded")
        p_host.wait_for_timeout(1200)
        p_j = {}
        for i in range(1, 12):
            ckj, _loc = None, None
            ckj = judge_cookie(links[f"J{i}"])
            ctxj = ctx_for(ckj)
            pj = ctxj.new_page()
            pj.goto(BASE + sheet_path, wait_until="domcontentloaded")
            pj.wait_for_timeout(1000)
            p_j[f"J{i}"] = pj
        preflight = []
        for jn, pj in p_j.items():
            n_rows = pj.locator(".rank-row").count()
            if n_rows != 8:
                preflight.append(f"{jn}: rows={n_rows} url={pj.url[:90]} body={pj.locator('body').inner_text()[:80]!r}")
        assert_("T0 14 页面就绪（控制台/检录/主持/11 裁判评分页）", not preflight, "; ".join(preflight[:3]))

        # S1 控制台矩阵 11 名裁判
        ok = wait_dom(p_admin, "document.querySelectorAll('#matrix tr').length >= 12", 8000)
        ok2 = wait_dom(p_admin, "document.querySelector('#matrix').innerText.includes('J11')", 6000)
        assert_("S1 控制台矩阵含 11 名裁判（J11 在列）", ok and ok2)

        # S2 检录员全部检录 → 三方自动对齐（不刷新）
        p_marshal.locator(f'button[data-all="{ceid}"]').first.click()
        ok_console = wait_dom(p_admin, "document.body.innerText.includes('检录 8/8')", 9000)
        # 裁判评分页置灰解锁（refreshOffState 局部）：任选 J5/J9 断言 off 行清零
        ok_j5 = wait_dom(p_j["J5"], "!document.querySelector('.rank-row.off') && !document.body.innerText.includes('未检录')", 9000)
        ok_j9 = wait_dom(p_j["J9"], "!document.querySelector('.rank-row.off')", 9000)
        assert_("S2 检录 → 控制台检录徽章自动更新", ok_console, "检录 8/8")
        assert_("S2 检录 → 裁判评分页置灰自动解锁（J5/J9 局部刷新）", ok_j5 and ok_j9)

        # S3 11 名裁判逐个从页面提交 → 控制台矩阵逐行自动刷新；第 11 名交齐自动计算
        scenario_log = []
        rng = random.Random("sse-r84")
        all_ok = True
        for i in range(1, 12):
            jn = f"J{i}"
            pj = p_j[jn]
            perm = ROSTER[:]
            rng.shuffle(perm)
            for num in perm:   # 顺序点选：按名次依次点击选手行
                try:
                    pj.locator(f'.rank-row[data-num="{num}"]').first.click(timeout=8000)
                    pj.wait_for_timeout(100)
                except Exception as e:
                    pj.screenshot(path=f"{OUT}/fail_{jn}_{num}.png")
                    raise AssertionError(f"{jn} 点击 {num} 失败: url={pj.url[:80]} rows={pj.locator('.rank-row').count()} :: {str(e)[:80]}")
            pj.locator("#submit").click()
            ok_prog = wait_dom(pj, "document.getElementById('progress').innerText.includes('8 / 8') || "
                                   "document.body.innerText.includes('已提交')", 10000)
            prog_txt = pj.locator("#progress").inner_text() if pj.locator("#progress").count() else "?"
            if not ok_prog:
                scenario_log.append({"裁判": jn, "progress": prog_txt,
                                     "body": pj.locator("body").inner_text()[:120]})
            # 控制台矩阵该裁判行自动变 8/8（局部刷新，无整页）
            ok_console = wait_dom(p_admin,
                                  f"document.querySelector('#matrix').innerText.includes('{jn}') && "
                                  f"/{jn}\\n?\\s*8\\/8|{jn}\\s*8\\/8/.test(document.querySelector('#matrix').innerText.replace(/\\u2713/g,''))",
                                  8000)
            if not ok_prog or not ok_console:
                all_ok = False
                print(f"  … {jn} prog={ok_prog} console={ok_console}", flush=True)
        assert_("S3 11 裁判逐个页面提交 → 控制台矩阵逐行自动对齐", all_ok)
        ok_calc = wait_dom(p_admin, "document.getElementById('status').innerText.includes('已计算')", 20000)
        assert_("S3 第 11 名交齐 → 控制台自动显示已计算/已收齐", ok_calc)

        # S4 发布 → 主持/检录页面自动出现已完成与已发布
        p_admin.locator("text=发布（进大屏）").first.click()
        ok_pub = wait_dom(p_admin, "document.body.innerText.includes('已发布')", 9000)
        ok_host = wait_dom(p_host, "document.body.innerText.includes('标记已播报') || "
                                   "document.body.innerText.includes('P02-R1') && document.body.innerText.includes('已发布')", 15000)
        if not ok_host:
            scenario_log.append({"host页面": p_host.url[:60], "body": p_host.locator("body").inner_text()[:200]})
        ok_m = wait_dom(p_marshal, "document.body.innerText.includes('已发布')", 12000)
        assert_("S4 发布 → 主持人页面自动出现已完成场次（标记已播报入口）", ok_pub and ok_host)
        assert_("S4 发布 → 检录员页面场次卡自动变已发布", ok_m)

        # S5 退回评分 → 裁判评分页/控制台自动回退（原生 confirm() 需 expect_dialog 接管）
        p_admin.once("dialog", lambda d: d.accept())
        p_admin.evaluate("Array.from(document.querySelectorAll('button')).forEach(function (b) { if (b.textContent.indexOf('退回评分') >= 0) b.click(); });")
        p_admin.wait_for_timeout(600)
        ok_j = wait_dom(p_j["J1"], "document.body.innerText.includes('已排 0') || document.getElementById('progress').innerText.includes('0 / 8') || document.body.innerText.includes('评分页')", 12000)
        ok_console = wait_dom(p_admin, "document.getElementById('status').innerText.includes('评分中')", 10000)
        assert_("S5 退回评分 → 裁判评分页自动清空重评", ok_j)
        assert_("S5 退回评分 → 控制台自动回退评分中", ok_console)

        browser.close()

    print(f"\n===== SSE 页面 E2E：{len(R) - len([r for r in R if not r['ok']])}/{len(R)} PASS · {time.time()-T0:.0f}s =====", flush=True)
    for r in R:
        if not r["ok"]:
            print("FAIL:", r["name"], "::", r["detail"], flush=True)
    json.dump(R, open(OUT + "/results.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
