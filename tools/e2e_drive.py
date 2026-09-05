#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E 全栈驱动器：对既有(或新建)赛事执行 混排驱动 + 异常注入 + 观众负载 + 独立对照。

用法: .venv/bin/python tools/e2e_drive.py [BASE] [CID|new] [VIEWER_SECONDS]
  BASE 默认正式 8321；CID=new 则新建「E2E全栈赛」并导入，否则复用既有赛事(自动激活)。
数据集/HTTP 层复用 sim_robustness.py（运行时截取其 主流程之前 的纯函数段，单一数据源不复制）。
独立对照（E2E-STANDARD R4/R5）：
  R4 团体总分 = 全量复算（最末轮口径 r1~r8=9,7,6,5,4,3,2,1）vs /team-standings 逐单位逐项目；
  R5 单场复算 = SCORE 求和排名 / MARK 计票排名 / SKATING 用本地 core 同票复算，逐位对照。
"""
import json, random, sys, threading, time, urllib.parse
import http.cookiejar
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://59.110.90.21:8321"
CID_ARG = sys.argv[2] if len(sys.argv) > 2 else "new"
VIEWER_SECONDS = int(sys.argv[3]) if len(sys.argv) > 3 else 0
MODE = sys.argv[4] if len(sys.argv) > 4 else "drive"   # drive=全量驱动+校验 / verify=仅校验
random.seed(20260906)

# ---- 复用 sim_robustness.py 的数据集生成器与 HTTP 层（主流程标记之前=纯函数）----
_SIM = Path(__file__).resolve().parent / "sim_robustness.py"
_CUT = "# ---------- 主流程 ----------"
sys.argv = [sys.argv[0], BASE, "120", "0"]   # exec 段会按 sim 的约定解析 argv，喂安全值
exec(compile(_SIM.read_text().split(_CUT)[0], str(_SIM), "exec"))

# 硬化传输层：exec 进来的 req 在 HTTPError 分支的 e.read() 无保护（网络半包即崩），外包重试
_req_orig = req
def req(method, path, jar=None, body=None, raw=None, ctype="application/json", timeout=15, retries=3):
    for attempt in range(retries):
        try:
            return _req_orig(method, path, jar, body, raw, ctype, timeout)
        except Exception as e:
            if attempt == retries - 1:
                with lock: stats["errors"].append((method, path, str(e)[:80]))
                return 0, b""
            time.sleep(0.5 * (attempt + 1))

report = {"admin": [], "judges": [], "invariants": [], "verify": []}
stats = getattr(sys.modules["__main__"], "stats", None)
if stats is None:
    stats = {"codes": {}, "err5xx": [], "errors": []}
lock = threading.Lock()

def jreq2(method, path, jar=None, body=None, raw=None, ctype="application/json"):
    """jreq + 瞬断重试一次（code 0 = 连接异常）。"""
    code, d = jreq(method, path, jar, body, raw, ctype)
    if code == 0:
        time.sleep(1.0)
        code, d = jreq(method, path, jar, body, raw, ctype)
    return code, d

def event_status(ceid):
    c, d = jreq2("GET", f"/api/public/events/{cid}/schedule")
    for e in (d or {}).get("events", []):
        if e["id"] == ceid: return e["status"]
    return "?"

def invariant(name, cond, detail=""):
    report["invariants"].append((name, bool(cond), str(detail)[:120]))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(detail)[:120] if detail and not cond else ""))

# ---- 赛事就绪 ----
admin = login("admin", "admin123")
assert admin, "admin login failed"
if CID_ARG == "new":
    code, d = jreq2("POST", "/api/events", admin, {"name": f"E2E全栈赛-{time.strftime('%m%d-%H%M')}", "date": time.strftime("%Y-%m-%d"), "location": "全栈验证场馆"})
    cid = d["id"]
    _, c1 = jreq2("POST", f"/api/events/{cid}/imports/competitors", admin, raw=gen_competitors(), ctype="text/csv")
    _, c2 = jreq2("POST", f"/api/events/{cid}/imports/judges", admin, raw=gen_judges(), ctype="text/csv")
    sched_csv, E = gen_schedule()
    code, c3 = jreq2("POST", f"/api/events/{cid}/imports/schedule", admin, raw=sched_csv, ctype="text/csv")
    assert c3 and c3.get("imported") == len(E), f"schedule import mismatch: {c3}"
    code, _ = jreq2("POST", f"/api/events/{cid}/activate", admin, {})
    assert code == 200, f"activate {code}"
    report["admin"] += [f"new cid={cid}", f"competitors {c1}", f"judges {c2}", f"schedule {c3}"]
else:
    cid = int(CID_ARG)
    code, evs = jreq2("GET", "/api/events", admin)
    me = next(e for e in evs["events"] if e["id"] == cid)
    sched_csv, E = gen_schedule()   # 数据集与正式压测一致（同生成器）
    if not me.get("active"):
        code, _ = jreq2("POST", f"/api/events/{cid}/activate", admin, {})
        assert code == 200, f"activate {code}"
    report["admin"].append(f"reuse cid={cid} count={me.get('event_count')}")

c, sch = jreq2("GET", f"/api/public/events/{cid}/schedule")
invariant("赛事已激活且可见", c == 200 and (sch or {}).get("competition", {}).get("active") == 1, c)
ceid_by_code = {e["code"]: e["id"] for e in (sch or {}).get("events", [])}
invariant("ceid 映射完整", len(ceid_by_code) == len(E), f"{len(ceid_by_code)}/{len(E)}")

# ---- 裁判登录 ----
judges = []
if MODE == "drive":
    for k in range(1, 10):
        j = login("judge", f"J{k}")
        assert j, f"J{k} login failed"
        judges.append((f"J{k}", j))
    report["judges"].append(f"{len(judges)} judges logged in")

codes = [e[0] for e in E]
published_set = set(codes[:12]); calculated_set = set(codes[12:18])
scoring_set = set(codes[18:26]); pending_set = set(codes[26:])
full_projects = ["S1", "S2", "L1", "F1", "M1", "S10", "L10", "F10"]

def _target_of(code_):
    """与驱动循环同一套规则推导目标状态（供 mix 校验，防真空通过）。"""
    e = next(x for x in E if x[0] == code_)
    proj, rnd = e[2], e[3]
    if proj in full_projects:
        last_r = max(x[3] for x in E if x[2] == proj)
        if rnd != last_r: return "calculated"
    elif rnd != 1:
        return "pending"   # 非重点项目只驱动第 1 轮
    return ("published" if code_ in published_set else
            "calculated" if code_ in calculated_set else
            "scoring" if code_ in scoring_set else "pending")

def dance_of(c): return next(e[4] for e in E if e[0] == c)
def typ_of(c): return next(e[5] for e in E if e[0] == c)
def roster_of(c): return next(e[7] for e in E if e[0] == c).split(",")
def ceid_of(c): return ceid_by_code[c]

if MODE == "drive":
    def sheet_payload(typ, roster_list, seed):
        rnd = random.Random(seed)
        if typ == "SKATING":
            p = roster_list[:]; rnd.shuffle(p)
            return {num: i + 1 for i, num in enumerate(p)}
        if typ == "MARK":
            k = max(1, len(roster_list) // 2)
            return {num: True for num in rnd.sample(roster_list, k)}
        return {num: rnd.randint(60, 100) / 10.0 for num in roster_list}

    def submit_sheet(jar, code_, vals):
        path = f"/api/judge/competition-events/{ceid_of(code_)}/dances/{urllib.parse.quote(dance_of(code_))}/sheet"
        return jreq2("PUT", path, jar, {"values": vals})[0]

    def drive_event(code_, target):
        ceid = ceid_of(code_); typ = typ_of(code_); ros = roster_of(code_)
        c, _ = jreq2("POST", f"/api/competition-events/{ceid}/open", admin, {"roster": ros, "reset": False})
        log = [(c, f"open {code_}")]
        if target in ("published", "calculated"):
            def sub(jt):
                _, jar = jt
                return submit_sheet(jar, code_, sheet_payload(typ, ros, seed=f"{code_}-{jt[0]}"))
            with ThreadPoolExecutor(max_workers=9) as ex:
                rs = list(ex.map(sub, judges))
            log.append((f"9J->{rs.count(200)}x200", code_))
            c, _ = jreq2("POST", f"/api/competition-events/{ceid}/calculate", admin, {})
            log.append((c, f"calc {code_}"))
            if target == "published":
                c, _ = jreq2("POST", f"/api/competition-events/{ceid}/publish", admin, {})
                if c != 200 and event_status(ceid) == "published":
                    c = 200   # 以服务端状态为准（瞬态 400/传输失真不误报）
                log.append((c, f"pub {code_}"))
        elif target == "scoring":
            for jn, jar in judges[:4]:
                c = submit_sheet(jar, code_, sheet_payload(typ, ros, seed=f"{code_}-p-{jn}"))
                log.append((c, f"partial {jn}"))
        return log

    by_project = defaultdict(list)
    for e in E: by_project[e[2]].append(e)

    for proj in full_projects:
        rounds = defaultdict(list)
        for e in by_project[proj]: rounds[e[3]].append(e)
        max_r = max(rounds)
        for rnd in sorted(rounds):
            group = rounds[rnd]
            is_last = rnd == max_r
            for e in group:
                code_ = e[0]
                target = "calculated" if not is_last else _target_of(code_)
                if target == "pending": continue
                for c, t in drive_event(code_, target): report["admin"].append(f"{c} {t}")
            if not is_last:
                adv_total = sum(g[6] for g in group)   # 合并名额 = 各组名额之和
                c, prop = jreq2("GET", f"/api/projects/{proj}/rounds/{rnd}/advancement-proposal", admin)
                names = [p["competitor_number"] for p in (prop.get("proposal") or [])][:adv_total] if prop else []
                invariant(f"{proj} R{rnd} 合并晋级={adv_total}", len(names) == adv_total, f"got {len(names)}")
                if names:
                    c, _ = jreq2("POST", f"/api/projects/{proj}/rounds/{rnd}/advancement-confirm", admin, {"advancing": names})
                    report["admin"].append(f"confirm {proj} R{rnd} x{len(names)} -> {c}")

    for e in E:
        code_ = e[0]
        if e[3] != 1 or e[2] in full_projects: continue
        target = _target_of(code_)
        if target == "pending": continue
        for c, t in drive_event(code_, target): report["admin"].append(f"{c} {t}")

    # ---- 异常注入面（R2/D5）----
    ceid_p = ceid_by_code[sorted(pending_set)[0]]
    c, _ = jreq2("POST", f"/api/competition-events/{ceid_p}/open", admin, {"roster": [], "reset": False})
    invariant("空名单开场=400", c == 400, c)
    c, _ = jreq2("PUT", f"/api/judge/competition-events/{ceid_p}/dances/X/sheet", judges[0][1], {"values": {}})
    invariant("pending 提交=400", c == 400, c)
    c, _ = jreq2("POST", "/api/login", http.cookiejar.CookieJar(), {"role": "judge", "judge_id": "HACK9"})
    invariant("非法裁判=403", c == 403, c)
    c, _ = jreq2("GET", f"/api/events/{cid}/team-standings")
    invariant("无会话 standings=401", c == 401, c)
    invariant("错口令拒绝", login("admin", "wrong-password-1") is None)
    sc_score = sorted(c0 for c0 in scoring_set if _target_of(c0) == "scoring")
    if sc_score:
        c0 = sc_score[0]
        ce, da, ro = ceid_by_code[c0], dance_of(c0), roster_of(c0)
        c, _ = jreq2("PUT", f"/api/judge/competition-events/{ce}/dances/{urllib.parse.quote(da)}/sheet",
                     judges[8][1], {"values": {n: 11 for n in ro}})
        invariant("评分越界=400", c == 400, c)
    sk_sk = sorted(c0 for c0 in scoring_set if typ_of(c0) == "SKATING" and _target_of(c0) == "scoring")
    if sk_sk:
        c0 = sk_sk[0]
        bad = {n: (1 if i % 2 else 2) for i, n in enumerate(roster_of(c0))}
        c, _ = jreq2("PUT", f"/api/judge/competition-events/{ceid_by_code[c0]}/dances/{urllib.parse.quote(dance_of(c0))}/sheet",
                     judges[8][1], {"values": bad})
        invariant("重复名次=400", c == 400, c)

    # ---- 观众负载（可选）----
    stop = threading.Event()
    ENDPOINTS = ["/public/schedule", "/public/results", "/screen",
                 f"/api/public/events/{cid}/results", f"/api/public/events/{cid}/schedule",
                 f"/api/public/events/{cid}/screen-state", f"/api/public/events/{cid}/team-standings",
                 f"/api/events/{cid}/stream"]
    def viewer(vid):
        deadline = time.time() + VIEWER_SECONDS
        while time.time() < deadline and not stop.is_set():
            req("GET", random.choice(ENDPOINTS), timeout=10)
            time.sleep(random.uniform(0.2, 1.5))
    if VIEWER_SECONDS > 0:
        vts = [threading.Thread(target=viewer, args=(f"V{i:02d}",), daemon=True) for i in range(30)]
        for t in vts: t.start()

    sc_active = sorted(c0 for c0 in scoring_set if _target_of(c0) == "scoring")
    if sc_active:
        c0 = sc_active[0]
        def resubmit(jt):
            _, jar = jt
            return submit_sheet(jar, c0, sheet_payload(typ_of(c0), roster_of(c0), seed=f"re-{jt[0]}"))
        with ThreadPoolExecutor(max_workers=9) as ex:
            wr = list(ex.map(resubmit, judges))
        report["admin"].append(f"concurrent rewrites -> {wr.count(200)}x200")
    if VIEWER_SECONDS > 0:
        time.sleep(max(0, VIEWER_SECONDS - 5))
        stop.set()
        for t in vts: t.join()

# ---- 防影子运行：驱动后服务端状态分布必须与同规则推导的期望一致 ----
c, sch2 = jreq2("GET", f"/api/public/events/{cid}/schedule")
mix = defaultdict(int)
for e in (sch2 or {}).get("events", []): mix[e["status"]] += 1
exp_mix = defaultdict(int)
for e in E:
    t = _target_of(e[0])
    if t != "pending": exp_mix[t] += 1
got_mix = {k: v for k, v in mix.items() if k != "pending"}
invariant("状态分布=同规则推导期望", got_mix == dict(exp_mix), f"got {dict(mix)} exp {dict(exp_mix)}")
bad_drives = []
for ent in report["admin"]:
    if isinstance(ent, tuple) and len(ent) == 2 and isinstance(ent[0], int) and ent[0] >= 400:
        bad_drives.append(ent)
    elif isinstance(ent, str) and " -> 4" in ent:
        bad_drives.append(ent)
invariant("驱动调用无非预期 4xx/5xx", not bad_drives, bad_drives[:5])

# ---- R4：团体总分全量独立复算（最末轮口径）----
POINTS = {1: 9.0, 2: 7.0, 3: 6.0, 4: 5.0, 5: 4.0, 6: 3.0, 7: 2.0, 8: 1.0}
unit_map = {}
for line in gen_competitors().strip().splitlines()[1:]:
    num, proj, name, unit = line.split(",", 3)
    unit_map[num] = unit
exp_pp = defaultdict(lambda: defaultdict(float))
proj_last = {}
for e in E:
    code_ = e[0]; proj = e[2]; rnd = e[3]
    c, d = jreq2("GET", f"/api/competition-events/{ceid_of(code_)}/results", admin)
    rows = (d or {}).get("data", {}).get("overall_results") if d else None
    if rows:
        cur = proj_last.get(proj)
        if cur is None or rnd > cur[0]:
            proj_last[proj] = (rnd, [rows])
        elif rnd == cur[0]:
            cur[1].append(rows)   # 同轮多场（分组）全部计入
for proj, (rnd, rows_list) in proj_last.items():
    for rows in rows_list:
        for r in rows:
            u = unit_map.get(str(r["competitor_number"]))
            if u: exp_pp[u][proj] += POINTS.get(int(r["rank"]), 0.0)
c, st = jreq2("GET", f"/api/events/{cid}/team-standings", admin)
api = {s["unit"]: s for s in (st or {}).get("standings", [])}
mismatch = []
for u in set(list(api.keys()) + list(exp_pp.keys())):
    et = round(sum(exp_pp[u].values()), 1); at = round(float(api.get(u, {}).get("total", 0)), 1)
    if et != at: mismatch.append((u, et, at)); continue
    for p in set(exp_pp[u].keys()) | set(api.get(u, {}).get("per_project", {}).keys()):
        ep = round(exp_pp[u].get(p, 0), 1); ap = round(float(api.get(u, {}).get("per_project", {}).get(p, 0)), 1)
        if ep != ap: mismatch.append((u, p, ep, ap))
invariant("R4 团体总分独立对照 ALL MATCH", not mismatch and len(proj_last) >= 8 and api,
          mismatch[:4] or f"proj_last={len(proj_last)} api_units={len(api)}")
invariant("R1 全程无 5xx", not stats["err5xx"], stats["err5xx"][:3])
real_conn_errs = [e for e in stats["errors"] if not e[1].endswith("/stream")]
invariant("R1 全程无连接异常(SSE 短连超时按设计剔除)", not real_conn_errs, real_conn_errs[:3])

# ---- R5：三类型抽样单场复算 ----
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.data_models import ScoreRecord, ScoringType
from core.scoring import ScoringAlgorithm

status_by_code = {e["code"]: e["status"] for e in (sch2 or {}).get("events", [])}
for typ in ("SKATING", "MARK", "SCORE"):
    done = [c0 for c0 in codes if typ_of(c0) == typ and status_by_code.get(c0) in ("published", "calculated")]
    c0 = sorted(done)[0] if done else None
    if not c0: report["verify"].append(f"{typ}: 无已算完样本"); continue
    c, d = jreq2("GET", f"/api/competition-events/{ceid_of(c0)}/detail-scores", admin)
    recs = (d or {}).get("records", [])
    if not recs:
        report["verify"].append(f"{typ} {c0}: detail-scores 为空，跳过"); continue
    ros = roster_of(c0); dance = dance_of(c0)
    if typ == "SCORE":
        sums = defaultdict(float)
        for r in recs: sums[str(r["number"])] += float(r["mark"] or 0)
        order = sorted(sums.items(), key=lambda kv: -kv[1])
        exp_rank, prev, pr = {}, None, 0
        for i, (num, sc) in enumerate(order, 1):
            rk = pr if prev is not None and abs(sc - prev) < 1e-9 else i
            exp_rank[num] = rk; prev, pr = sc, rk
    elif typ == "MARK":
        votes = defaultdict(int)
        for r in recs:
            if r.get("mark"): votes[str(r["number"])] += 1
        order = sorted(votes.items(), key=lambda kv: (-kv[1], str(kv[0])))
        exp_rank, prev, pr = {}, None, 0
        for i, (num, v) in enumerate(order, 1):
            rk = pr if prev is not None and v == prev else i
            exp_rank[num] = rk; prev, pr = v, rk
    else:
        records = [ScoreRecord(id=str(i), event_id="x", judge_id=r["judge"], competitor_number=str(r["number"]),
                               dance_name=dance, placement=r.get("placement")) for i, r in enumerate(recs)]
        alg = ScoringAlgorithm()
        ok, res, errs, _, _ = alg.calculate_results(records, ScoringType.SKATING, advancement_count=0)
        assert ok, f"local core failed {errs}"
        exp_rank = {str(r.competitor_number): r.rank for r in res["overall_results"]}
    c, d = jreq2("GET", f"/api/competition-events/{ceid_of(c0)}/results", admin)
    api_rank = {str(r["competitor_number"]): int(r["rank"]) for r in d["data"]["overall_results"]}
    diff = {n: (exp_rank.get(n), api_rank.get(n)) for n in set(exp_rank) | set(api_rank)
            if exp_rank.get(n) != api_rank.get(n)}
    invariant(f"R5 {typ} {c0} 复算逐位一致", not diff, diff)

out = {"cid": cid, "report": report, "codes": stats["codes"], "standings_units": len(api)}
print(json.dumps(out, ensure_ascii=False)[:1500])
Path("/tmp/ds_e2e_result.json").write_text(json.dumps(out, ensure_ascii=False))
print(f"\nE2E drive done cid={cid} invariants={sum(1 for _,ok,_ in report['invariants'] if ok)}/{len(report['invariants'])}")
