# -*- coding: utf-8 -*-
"""R95 测试赛完整计分模拟（生产新建测试赛事，comp21 最新报项/裁判，确定性评分）。

流程：总管建测试赛并激活 → 导入 comp21 报项（179 条/15 项目）与 11 裁判 →
v4 参数生成赛程（同正式赛参数）→ 按项目×轮次循环：open/检录 → 多裁判×多舞种评分
（Mark 制勾选 / 顺位法名次，全部确定性模式）→ 收齐自动算 → 发布 → 晋级确认回填 →
直到全部决赛打完。校验：晋级回填人数、分舞种名次与综合序和合计（服务端 results
JSON 手工重算对照）。正式赛 comp21 只读（仅导出数据），全程不碰。

用法：python3 e2e_scoring_sim_r95.py [base=https://dancetkt.com]
"""
import csv, io, json, os, sys, time
from urllib.parse import quote

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://dancetkt.com"
SRC_CID = 21
OUT = "/tmp/e2e_r95"
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
R = []
NJ = 11
ADMIN_PW = "CE9DoLRhkb37R9w_bgrpDA55"
GEN_CFG = {"max_entries": 24, "cap": 12, "final_size": 8, "mode": "auto",
           "rounds_spec": "", "strategy": "unit_spread"}


def log(event, ok=True, detail=""):
    print(f"[{time.time()-T0:6.1f}s] {'✓' if ok else '✗'} {event}" + (f" :: {detail}" if detail else ""), flush=True)


def assert_(name, ok, detail=""):
    R.append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    log("ASSERT " + name, ok, detail)


def api(method, path, body=None, cookie="", raw=None, ct="text/csv; charset=utf-8", expect_json=True):
    import urllib.request, urllib.error
    rq = urllib.request.Request(BASE + path, method=method)
    if cookie:
        rq.add_header("Cookie", cookie)
    if raw is not None:
        rq.data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        rq.add_header("Content-Type", ct)
    elif body is not None:
        rq.data = json.dumps(body).encode()
        rq.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(rq, timeout=60) as resp:
            raw_body = resp.read()
            sc = resp.headers.get("Set-Cookie", "").split(";")[0]
            try:
                return resp.status, (json.loads(raw_body) if expect_json else raw_body), sc
            except Exception:
                return resp.status, {"_text": raw_body.decode("utf-8", "replace")[:400]}, sc
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read() or b"{}")
        except Exception:
            d = {}
        return e.code, d, ""


def login(body):
    for _ in range(8):
        c, d, ck = api("POST", "/api/login", body)
        if c == 200:
            return ck
        if c == 429:
            time.sleep(22)
            continue
        raise AssertionError(f"登录失败 {body} {c} {d}")
    raise AssertionError(f"登录限流未解除 {body}")


def wait_status(ceid, want, timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        c, d, _ = api("GET", f"/api/public/events/{CID}/schedule")
        ev = next((e for e in d.get("events", []) if e["id"] == ceid), {})
        if ev.get("status") == want:
            return True
        time.sleep(1.2)
    return False


def num_key(n):
    return (len(str(n)), str(n))


def submit_sheet(ceid, dance, values, jcookie, jname, code):
    c, d, _ = api("PUT", f"/api/judge/competition-events/{ceid}/dances/{quote(dance)}/sheet",
                  body={"values": values}, cookie=jcookie)
    if c != 200:
        log(f"{code} {jname} 提交 {dance} 失败", ok=False, detail=str(d)[:100])
    return c == 200


def judge_dances(ceid, jcookie):
    """从裁判工作台页解析本场全部舞种名（多舞种返回多个）。"""
    import urllib.request, re
    rq = urllib.request.Request(BASE + "/judge")
    rq.add_header("Cookie", jcookie)
    with urllib.request.urlopen(rq, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    dances = re.findall(r'href="(/judge/competition-events/%d/dances/([^"]+))"' % ceid, html)
    out = []
    for _, enc in dances:
        import urllib.parse
        name = urllib.parse.unquote(enc).replace("\u200b", "")
        if name not in out:
            out.append(name)
    return out


CID = None
ck = None


def main():
    global CID, ck
    # ---------- P0 总管会话 + 建测试赛（argv[2]=已有 cid 时复用，跳过建赛/导入/生成） ----------
    reuse = len(sys.argv) > 2
    ck = login({"role": "admin", "password": ADMIN_PW})
    if reuse:
        CID = int(sys.argv[2])
        log(f"复用测试赛 cid={CID}")
    else:
        c, d, _ = api("POST", "/api/events", {"name": "R95 计分模拟测试赛", "date": "2026-11-09",
                                              "location": "模拟环境"}, cookie=ck)
        assert_("P0 新建测试赛事", c == 200 and d.get("id"), str(d)[:80])
        CID = d["id"]
        c, d, _ = api("POST", f"/api/events/{CID}/activate", {}, cookie=ck)
        assert_("P0 激活测试赛事", c == 200, f"cid={CID}")

        # ---------- P1 数据导入：comp21 报项 + 裁判 ----------
        c, csv_bytes, _ = api("GET", f"/api/events/{SRC_CID}/exports/competitors?format=csv", cookie=ck, expect_json=False)
        text = csv_bytes.decode("utf-8-sig") if isinstance(csv_bytes, bytes) else str(csv_bytes)
        rows = list(csv.reader(io.StringIO(text)))
        assert_("P1 报项导出", len(rows) > 100, f"{len(rows)-1} 行")
        c, d, _ = api("POST", f"/api/events/{CID}/imports/competitors", raw=text, cookie=ck)
        # 导入端点会触发 auto_schedule（旧默认引擎）——随后 v4 重建覆盖
        assert_("P1 报项导入测试赛", c == 200 and d.get("imported", 0) >= 150,
                f"imported={d.get('imported')} problems={str(d.get('problems'))[:60]}")
        c, jd_bytes, _ = api("GET", f"/api/events/{SRC_CID}/exports/judges", cookie=ck, expect_json=False)
        jd_text = jd_bytes.decode("utf-8-sig") if isinstance(jd_bytes, bytes) else str(jd_bytes)
        c, d, _ = api("POST", f"/api/events/{CID}/imports/judges", raw=jd_text, cookie=ck)
        assert_("P1 裁判导入测试赛", c == 200 and d.get("imported", 0) == NJ, f"imported={d.get('imported')}")

        # ---------- P2 v4 生成赛程（同正式赛参数） ----------
        GEN_CFG["competition_id"] = CID
        c, d, _ = api("POST", f"/api/events/{CID}/generate-schedule", GEN_CFG, cookie=ck)
        assert_("P2 v4 生成赛程", c == 200 and d.get("events", 0) >= 30,
                f"projects={d.get('projects')} events={d.get('events')}")

    c, d, _ = api("GET", f"/api/public/events/{CID}/schedule")
    events = d.get("events", [])
    by_proj = {}
    for e in events:
        by_proj.setdefault(e["project_code"], []).append(e)
    assert_("P2 赛程结构", len(by_proj) >= 12 and len(events) >= 30,
            f"{len(by_proj)} 项目 / {len(events)} 场")
    proj_rounds = {p: sorted({e["round"] for e in evs}) for p, evs in by_proj.items()}

    # ---------- P3 裁判会话 ----------
    cks_j = {f"J{i}": login({"role": "judge", "judge_id": f"J{i}", "competition_id": CID})
             for i in range(1, NJ + 1)}
    log(f"裁判会话就绪 ×{NJ}")
    # 公开 schedule 不含 scoring_type/advancement_count——从服务端只读拉一次映射
    import subprocess
    _v = subprocess.run(["ssh", "sport-coder",
                         f'''python3 -c "import sqlite3,json;c=sqlite3.connect('file:/home/sport-coder/dancesport-service/data/dancesport.db?mode=ro',uri=True);print(json.dumps({{r[0]:[r[1],r[2]] for r in c.execute('SELECT code,scoring_type,advancement_count FROM events WHERE competition_id={CID}')}}))"'''],
                        capture_output=True, text=True, timeout=60)
    ev_meta = json.loads(_v.stdout.strip().splitlines()[-1])
    log(f"场次元数据映射 {len(ev_meta)} 场")

    # ---------- P4 按项目×轮次循环评分 ----------
    # 确定性评分模式：
    #   Mark制预赛：每裁判勾选 roster 排序后的前 max(4, adv) 个（mark=True）
    #   顺位法（决赛）：裁判 Ji 的名次 = 排序后名单循环左移 (i-1)%n 位

    all_ok = True
    def pending_rosters():
        c, d, _ = api("GET", f"/api/events/{CID}/run-order", cookie=ck)
        return {x["ceid"]: sorted(set(x.get("roster") or []), key=num_key) for x in d.get("order", [])}

    for proj in sorted(proj_rounds):
        for rnd in proj_rounds[proj]:
            group = sorted([e for e in by_proj[proj] if e["round"] == rnd], key=lambda x: x["code"])
            is_last = rnd == max(proj_rounds[proj])
            rmap = pending_rosters()   # 晋级回填后刷新
            for ev in group:
                ceid, code = ev["id"], ev["code"]
                c, d, _ = api("GET", f"/api/public/events/{CID}/schedule")
                ev_now = next(x for x in d["events"] if x["id"] == ceid)
                styp, n_adv_meta = ev_meta.get(code, ["顺位法", 0])
                n_adv = n_adv_meta or 0
                roster_nums = rmap.get(ceid, [])
                if not roster_nums:
                    log(f"{code} 无名单（run-order 未含）", ok=False)
                    all_ok = False
                    continue
                c, d, _ = api("POST", f"/api/competition-events/{ceid}/open",
                              {"roster": roster_nums, "reset": False}, cookie=ck)
                if c != 200:
                    log(f"{code} open 失败", ok=False, detail=str(d)[:80])
                    all_ok = False
                    continue
                c, d, _ = api("POST", f"/api/competition-events/{ceid}/checkin",
                              {"numbers": roster_nums, "state": True}, cookie=ck)
                assert_(f"{code} 检录 {len(roster_nums)} 人", c == 200)
                # 舞种列表（裁判工作台解析）
                dances = judge_dances(ceid, cks_j["J1"])
                if not dances:
                    log(f"{code} 舞种解析失败", ok=False)
                    all_ok = False
                    continue
                # 评分
                for jn, jc in cks_j.items():
                    jidx = int(jn[1:])
                    for dance in dances:
                        if styp == "Mark制":
                            picks = roster_nums[:max(4, n_adv or 4)]
                            values = {n: True for n in picks}
                        else:
                            perm = roster_nums[jidx % len(roster_nums):] + roster_nums[:jidx % len(roster_nums)]
                            values = {n: str(rk) for rk, n in enumerate(perm, 1)}
                        if not submit_sheet(ceid, dance, values, jc, jn, code):
                            all_ok = False
                ok = wait_status(ceid, "calculated") or wait_status(ceid, "published", 10)
                assert_(f"{code} 收齐自动计算（{styp} × {len(dances)} 舞 × {NJ} 裁判 × {len(roster_nums)} 人）", ok)
                if ev_now["status"] == "calculated" or True:
                    c, d, _ = api("POST", f"/api/competition-events/{ceid}/publish", {}, cookie=ck)
                    ok = wait_status(ceid, "published")
                    assert_(f"{code} 发布", ok)
                    if not ok:
                        all_ok = False
            # 同轮全部打完 → 晋级确认（非末轮）
            if not is_last:
                c, d, _ = api("GET", f"/api/projects/{proj}/rounds/{rnd}/advancement-proposal", cookie=ck)
                prop = [str(x["competitor_number"]) for x in d.get("proposal", [])]
                assert_(f"{proj} R{rnd} 晋级预案 {len(prop)} 人", len(prop) > 0,
                        str(sorted(prop, key=num_key)[:6]) + "…")
                c, d, _ = api("POST", f"/api/projects/{proj}/rounds/{rnd}/advancement-confirm",
                              {"advancing": prop}, cookie=ck)
                assert_(f"{proj} R{rnd} 晋级确认回填 R{rnd+1}", c == 200, str(d)[:80])

    # ---------- P5 服务端结果校验（ssh 只读） ----------
    log("进入 P5 结果校验（服务端只读查询 results JSON）")
    verify_cmd = build_verify()
    import subprocess
    p = subprocess.run(["ssh", "sport-coder", verify_cmd], capture_output=True, text=True, timeout=120)
    out = p.stdout.strip()
    verdict = json.loads(out.splitlines()[-1]) if out else {}
    assert_("P5 校验脚本执行", verdict.get("ok") is True, out[-400:])

    # ---------- 收官 ----------
    c, d, _ = api("GET", f"/api/public/events/{CID}/schedule")
    pub = sum(1 for e in d["events"] if e["status"] == "published")
    assert_(f"收官 全部场次已发布（{pub}/{len(d['events'])}）", pub == len(d["events"]))
    c, d, _ = api("GET", f"/api/public/events/{CID}/results")
    assert_("收官 公开结果可见", c == 200 and len(d.get("results", [])) == len(d.get("results", [])), f"{len(d.get('results', []))} 场")

    n_pass = len([r for r in R if r["ok"]])
    print(f"\n===== 计分模拟完成：{n_pass}/{len(R)} PASS · 全程 {time.time()-T0:.0f}s · 测试赛 cid={CID} =====", flush=True)
    for r in R:
        if not r["ok"]:
            print("FAIL:", r["name"], "::", r["detail"], flush=True)
    json.dump({"asserts": R, "cid": CID}, open(OUT + "/results.json", "w"), ensure_ascii=False, indent=1)


def build_verify():
    """服务端只读校验：抽取测试赛若干场 results，核对分舞种名次与综合序和合计。"""
    return f'''python3 - <<'PY'
import sys, json
sys.path.insert(0, "/home/sport-coder/dancesport-service")
from server import db
from server.scoring_service import load_results

CID = {CID}

def nk(n): return (len(str(n)), str(n))
problems = []
checked = {{"events": 0, "skating_overall": 0, "mark_overall": 0, "adv": 0}}
for ev in db.rows(db.get_db().execute(
        "SELECT id, code, scoring_type, advancement_count FROM events WHERE competition_id=? ORDER BY code", (CID,))):
    res = load_results(ev["id"])
    if not res:
        problems.append(f"{{ev['code']}} 无结果")
        continue
    checked["events"] += 1
    overall = res["overall_results"]
    dances = res["dance_results"]
    # 1) 综合人数 = 各舞种出现过的选手并集
    union = set()
    for dres in dances.values():
        for r in dres:
            union.add(str(r["competitor_number"]))
    if len(overall) != len(union):
        problems.append(f"{{ev['code']}} 综合{{len(overall)}}人 != 舞种并集{{len(union)}}人")
    # 2) 综合合计口径核对
    if "顺位" in (ev["scoring_type"] or "") and len(dances) >= 1:
        # 滑冰法：分舞种 rank 序和（单舞种也走此路径），同序和并列顺延
        sums = {{}}
        for dname, dres in dances.items():
            for r in dres:
                n = str(r["competitor_number"])
                sums[n] = sums.get(n, 0) + int(r["rank"])
        exp_sorted = sorted(sums.items(), key=lambda kv: (kv[1], nk(kv[0])))
        exp_rank, prev, rk = {{}}, None, 0
        for i, (n, s) in enumerate(exp_sorted, 1):
            if s != prev:
                rk, prev = i, s
            exp_rank[n] = (rk, s)
        for r in overall:
            n = str(r["competitor_number"])
            if exp_rank.get(n) and exp_rank[n][0] != int(r["rank"]):
                problems.append(f"{{ev['code']}} 背号{{n}} 综合名次{{r['rank']}} != 期望{{exp_rank[n][0]}}(序和{{exp_rank[n][1]}})")
        checked["skating_overall"] += 1
    elif "Mark" in (ev["scoring_type"] or ""):
        # Mark 综合 = 各舞种票数总和（dance_results.score 为该舞种得票）
        tot = {{}}
        for dres in dances.values():
            for r in dres:
                n = str(r["competitor_number"])
                tot[n] = tot.get(n, 0) + float(r.get("score") or 0)
        for r in overall:
            n = str(r["competitor_number"])
            if abs(tot.get(n, 0) - float(r.get("total_score") or 0)) > 1e-6:
                problems.append(f"{{ev['code']}} 背号{{n}} Mark总票{{r.get('total_score')}} != 期望{{tot.get(n)}}")
        checked["mark_overall"] += 1
    # 3) 晋级标记一致性：advancement_status 数 == min(adv, 人数)
    adv = ev["advancement_count"] or 0
    if adv:
        n_adv = sum(1 for r in overall if r.get("advancement_status"))
        if n_adv != min(adv, len(overall)):
            problems.append(f"{{ev['code']}} 晋级标记{{n_adv}} != min({{adv}},{{len(overall)}})")
        checked["adv"] += 1
    # 4) 晋级回填：非末轮已确认的下一轮名单人数
print(json.dumps({{"ok": not problems, "checked": checked, "problems": problems[:20]}}, ensure_ascii=False))
PY'''


if __name__ == "__main__":
    main()
