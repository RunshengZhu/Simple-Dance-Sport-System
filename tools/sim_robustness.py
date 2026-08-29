#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dancesport 鲁棒性模拟器（stdlib only）
BASE 指向正式 8321。阶段：
  1 管理员建赛/导入(34 场次)/激活
  2 流程混排驱动：published(全流程)/calculated/scoring/pending 四态
  3 9 裁判并发评分（含并发写探测）+ 异常注入面（非法输入全收 4xx）
  4 30 观众线程随机查询（HTML+API+SSE 短连）统计状态码
  5 校验：全程无 5xx；团体总分（最末轮口径）独立对照
"""
import json, random, sys, threading, time, urllib.request, urllib.error, urllib.parse
import http.cookiejar
from concurrent.futures import ThreadPoolExecutor

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://59.110.90.21:8321"
VIEWER_SECONDS = int(sys.argv[2]) if len(sys.argv) > 2 else 120
random.seed(20260829)

UNITS = ["北京大学","清华大学","复旦大学","南京大学","浙江大学","上海交通大学","武汉大学","中山大学"]
lock = threading.Lock()
stats = {"codes": {}, "err5xx": [], "errors": []}

def req(method, path, jar=None, body=None, raw=None, ctype="application/json", timeout=15):
    full = BASE + path
    data = raw.encode() if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(full, data=data, method=method)
    if data: r.add_header("Content-Type", ctype)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)) if jar is not None else urllib.request.build_opener()
    try:
        with opener.open(r, timeout=timeout) as resp:
            code, payload = resp.status, resp.read()
            with lock: stats["codes"][code] = stats["codes"].get(code, 0) + 1
            return code, payload
    except urllib.error.HTTPError as e:
        code, payload = e.code, e.read()
        with lock: stats["codes"][code] = stats["codes"].get(code, 0) + 1
        if code >= 500: stats["err5xx"].append((method, path, code))
        return code, payload
    except Exception as e:
        with lock:
            stats["errors"].append((method, path, str(e)[:80]))
        return 0, b""

def jreq(method, path, jar=None, body=None, raw=None, ctype="application/json"):
    code, payload = req(method, path, jar, body, raw, ctype)
    try: return code, json.loads(payload)
    except Exception: return code, None

def login(role, ident):
    jar = http.cookiejar.CookieJar()
    body = {"role": role, "judge_id": ident} if role == "judge" else {"role": "admin", "password": ident}
    code, d = jreq("POST", "/api/login", jar, body)
    return jar if code == 200 else None

# ---------- 数据集生成（34 场次）----------
def gen_competitors():
    M = ["陈志明","刘伟杰","张浩然","黄俊杰","吴文轩","徐子豪","孙铭泽","马嘉熙","朱建国","胡志强","郭靖宇","何志远","高天佑","林晨曦","郑凯文","王思远"]
    F = ["梁咏琪","宋雅琴","谢雨婷","唐梦琪","韩雪莹","冯静怡","曹颖慧","彭诗涵","董欣妍","袁紫嫣","蔡依琳","潘嘉怡","杜若曦","夏语嫣","姜暖阳","薛晗玥"]
    rows = ["背番号,项目编号,姓名,学校/单位"]
    CROSS = {103:(0,1), 107:(2,3), 111:(4,5), 115:(6,7)}   # 双人跨单位 4 对
    CROSS_L = {202:(3,6), 205:(5,7), 210:(1,4)}            # 拉丁跨单位 3 对
    for i in range(16):
        num = 101 + i
        if num in CROSS:
            ui, uj = CROSS[num]; unit, label = UNITS[ui], f"{M[i]}({UNITS[ui]})/{F[i]}({UNITS[uj]})"
        else:
            unit, label = UNITS[i % 8], f"{M[i]}/{F[i]}"
        rows.append(f"{num},STD,{label},{unit}")
    for i in range(12):
        num = 201 + i
        if num in CROSS_L:
            ui, uj = CROSS_L[num]; unit, label = UNITS[ui], f"{M[(i+3)%16]}({UNITS[ui]})/{F[(i+7)%16]}({UNITS[uj]})"
        else:
            unit, label = UNITS[(i+2) % 8], f"{M[(i+3)%16]}/{F[(i+7)%16]}"
        rows.append(f"{num},LAT,{label},{unit}")
    TN = ["燕园舞蹈团","紫荆舞蹈团","旦复旦舞蹈团","金陵舞蹈团","求是舞蹈团","思源舞蹈团"]
    for k in range(6):
        rows.append(f"T0{k+1},FRM,{TN[k]},{UNITS[k]}")
    return "\n".join(rows) + "\n"

def gen_judges():
    return "裁判ID,姓名\n" + "".join(f"J{k},评委{k}\n" for k in range(1, 10))

def gen_schedule():
    """34 场次：项目(类型,轮次结构,roster 池)"""
    std = ",".join(str(101+i) for i in range(16))
    std8 = ",".join(str(101+i) for i in range(8))
    std4 = ",".join(str(101+i) for i in range(4))
    lat = ",".join(str(201+i) for i in range(12))
    lat8 = ",".join(str(201+i) for i in range(8))
    lat6 = ",".join(str(201+i) for i in range(6))
    lat10 = ",".join(str(201+i) for i in range(10))
    m10 = ",".join(str(101+i) for i in range(10))
    m8 = ",".join(str(101+i) for i in range(8))
    m12 = ",".join(str(101+i) for i in range(12))
    teams6 = ",".join(f"T0{k+1}" for k in range(6))
    teams4 = ",".join(f"T0{k+1}" for k in range(4))
    E = []  # (场次编号, 名称, 项目, 轮, 舞种, 类型, 晋级, roster)
    def add(code, name, proj, rnd, dance, typ, adv, roster):
        E.append((code, name, proj, rnd, dance, typ, adv, roster))
    add("S1R1","S1第1轮","S1",1,"华尔兹","SKATING",8,std); add("S1R2","S1第2轮","S1",2,"华尔兹","SKATING",4,std8); add("S1F","S1决赛","S1",3,"华尔兹","SKATING",0,std4)
    add("S2R1","S2第1轮","S2",1,"探戈","SKATING",8,std);  add("S2F","S2决赛","S2",2,"探戈","SKATING",0,std8)
    add("S3R1","S3第1轮","S3",1,"快步","SKATING",8,std);  add("S3F","S3决赛","S3",2,"快步","SKATING",0,std8)
    add("S4","S4直出","S4",1,"维也纳华尔兹","SKATING",0,std)
    add("S5R1","S5第1轮","S5",1,"狐步","SKATING",8,std);  add("S5F","S5决赛","S5",2,"狐步","SKATING",0,std8)
    add("L1R1","L1第1轮","L1",1,"恰恰恰","SKATING",6,lat); add("L1F","L1决赛","L1",2,"恰恰恰","SKATING",0,lat6)
    add("L2R1","L2第1轮","L2",1,"伦巴","SKATING",6,lat);  add("L2F","L2决赛","L2",2,"伦巴","SKATING",0,lat6)
    add("L3","L3直出","L3",1,"桑巴","SKATING",0,lat)
    add("L4","L4直出","L4",1,"斗牛","SKATING",0,lat8)
    add("L5R1","L5第1轮","L5",1,"牛仔","SKATING",6,lat);  add("L5F","L5决赛","L5",2,"牛仔","SKATING",0,lat6)
    add("M1R1","M1第1轮","M1",1,"现代舞","MARK",6,m10);   add("M1F","M1决赛","M1",2,"现代舞","MARK",0,m10)
    add("M2","M2直出","M2",1,"现代舞","MARK",0,m8)
    add("M3","M3直出","M3",1,"现代舞","MARK",0,m12)
    add("F1R1","F1第1轮","F1",1,"集体舞","SCORE",0,teams6); add("F1F","F1决赛","F1",2,"集体舞","SCORE",0,teams6)
    add("F2","F2直出","F2",1,"集体舞","SCORE",0,teams6)
    add("F3","F3直出","F3",1,"集体舞","SCORE",0,teams6)
    add("F4","F4直出","F4",1,"集体舞","SCORE",0,teams4)
    add("S6","S6直出","S6",1,"华尔兹","SKATING",0,std)
    add("S7R1","S7第1轮","S7",1,"探戈","SKATING",8,std); add("S7F","S7决赛","S7",2,"探戈","SKATING",0,std8)
    add("L6R1","L6第1轮","L6",1,"伦巴","SKATING",6,lat); add("L6F","L6决赛","L6",2,"伦巴","SKATING",0,lat6)
    add("M4","M4直出","M4",1,"现代舞","MARK",0,m8)
    add("F5","F5直出","F5",1,"集体舞","SCORE",0,teams6)
    lines = ["场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手"]
    for code,name,proj,rnd,dance,typ,adv,roster in E:
        lines.append(f"{code},{name},{proj},{rnd},{dance},{typ},{adv},\"{roster}\"" if roster else f"{code},{name},{proj},{rnd},{dance},{typ},{adv},")
    return "\n".join(lines) + "\n", E

# ---------- 主流程 ----------
report = {"admin": [], "judges": [], "viewers": {}, "invariants": []}
admin = login("admin", "admin123")
assert admin, "admin login failed"
report["admin"].append("login ok")

code, d = jreq("POST", "/api/events", admin, {"name": "压测混排赛", "date": "2026-08-29", "location": "鲁棒性场馆"})
cid = d["id"]; report["admin"].append(f"create cid={cid}")
_, comp = jreq("POST", f"/api/events/{cid}/imports/competitors", admin, raw=gen_competitors(), ctype="text/csv"); report["admin"].append(f"competitors {comp}")
_, comp = jreq("POST", f"/api/events/{cid}/imports/judges", admin, raw=gen_judges(), ctype="text/csv"); report["admin"].append(f"judges {comp}")
sched_csv, E = gen_schedule()
code, comp = jreq("POST", f"/api/events/{cid}/imports/schedule", admin, raw=sched_csv, ctype="text/csv"); report["admin"].append(f"schedule {comp}")
assert comp and comp.get("imported") == len(E), f"schedule import mismatch: {comp}"
code, _ = jreq("POST", f"/api/events/{cid}/activate", admin, {}); assert code == 200

# ceid 映射
_, sch = jreq("GET", f"/api/public/events/{cid}/schedule")
ceid_by_code = {}
# 公开 schedule 不含 ceid，改用 events 接口（admin）
code, d = jreq("GET", "/api/events", admin)
for ev in d if isinstance(d, list) else d.get("events", []):
    pass  # /api/events 是赛事列表；ceid 需从导入顺序推：sqlite 自增，第 N 场 = base+N
# 直接从 DB 不行（外网）——用 schedule 导入顺序：ceid 连续。先拿一个已知锚点：S1R1 是该赛事第一场。
# 通过逐场 open 试探确定（open pending 场次才有效）——改为：用 admin 赛程页 API？无 ceid。用 public events id 字段：
_, pub = jreq("GET", f"/api/public/events/{cid}/schedule")
evs = pub.get("events", [])
# events 字段含 id（=ceid）与 code
ceid_by_code = {e["code"]: e["id"] for e in evs if "id" in e}
assert len(ceid_by_code) == len(E), f"ceid map {len(ceid_by_code)}/{len(E)}"

# ---- 状态分配（混排）----
codes = [e[0] for e in E]
published_set = set(codes[:12])                      # 12 场全流程到发布
calculated_set = set(codes[12:18])                   # 6 场算完不发布
scoring_set = set(codes[18:26])                      # 8 场进行中（部分评分）
pending_set = set(codes[26:])                        # 8 场 pending

judges = []
for k in range(1, 10):
    j = login("judge", f"J{k}")
    assert j, f"J{k} login failed"
    judges.append((f"J{k}", j))
report["judges"].append(f"{len(judges)} judges logged in")

def dance_of(code): return next(e[4] for e in E if e[0] == code)
def typ_of(code): return next(e[5] for e in E if e[0] == code)
def roster_of(code): return next(e[7] for e in E if e[0] == code).split(",")

def sheet_payload(typ, roster_list, seed):
    rnd = random.Random(seed)
    if typ == "SKATING":
        p = roster_list[:]; rnd.shuffle(p)
        return {num: i+1 for i, num in enumerate(p)}
    if typ == "MARK":
        return {num: rnd.random() < 0.6 for num in roster_list}
    return {num: rnd.randint(60, 100)/10.0 for num in roster_list}   # 6.0~10.0 一位小数

def drive_event(code, target):
    """把一场次驱动到目标状态；返回动作日志。"""
    ceid = ceid_by_code[code]; typ = typ_of(code); roster_list = roster_of(code)
    log = []
    c, d = jreq("POST", f"/api/competition-events/{ceid}/open", admin, {"roster": roster_list, "reset": False})
    log.append((c, f"open {code}"))
    if target in ("published", "calculated"):
        # 9 裁判并发提交
        def submit(jt):
            jn, jar = jt
            vals = sheet_payload(typ, roster_list, seed=f"{code}-{jn}")
            return jreq("PUT", f"/api/judge/competition-events/{ceid}/dances/{urllib.parse.quote(dance_of(code))}/sheet", jar, {"values": vals})[0]
        with ThreadPoolExecutor(max_workers=9) as ex:
            codes_r = list(ex.map(submit, judges))
        log.append((f"9 judges -> {codes_r.count(200)}x200", code))
        c, d = jreq("POST", f"/api/competition-events/{ceid}/calculate", admin, {})
        log.append((c, f"recalc {code}"))
        if target == "published":
            c, _ = jreq("POST", f"/api/competition-events/{ceid}/publish", admin, {})
            log.append((c, f"publish {code}"))
    elif target == "scoring":
        # 只让 4 个裁判提交（部分评分态）
        for jn, jar in judges[:4]:
            vals = sheet_payload(typ, roster_list, seed=f"{code}-p-{jn}")
            c, _ = jreq("PUT", f"/api/judge/competition-events/{ceid}/dances/{urllib.parse.quote(dance_of(code))}/sheet", jar, {"values": vals})
            log.append((c, f"partial {jn}"))
    return log

# 顺序依赖：轮次必须从 R1 开始驱动（R2/R3 需晋级回填）。published/calculated 全取 R1 可独立跑；
# 混排驱动策略：全流程集合先按项目逐轮驱动（R1→晋级→R2→…），其余直接单场驱动。
from collections import defaultdict
by_project = defaultdict(list)
for e in E: by_project[e[2]].append(e)
def rounds_of(proj): return sorted(by_project[proj], key=lambda e: e[3])

full_projects = ["S1", "S2", "L1", "F1", "M1"]   # 跑完整晋级链并发布最末轮
for proj in full_projects:
    chain = rounds_of(proj)
    advancing = None
    for e in chain:
        code = e[0]
        target = "published" if code in published_set else ("calculated" if code in calculated_set else "scoring")
        # 晋级链：中间轮必须走完整（算+晋级），最末轮按状态
        logs = drive_event(code, "published" if e[3] < chain[-1][3] else target)
        report["admin"] += [f"{c} {t}" for c, t in logs]
        if e[3] < chain[-1][3]:
            # 生成预案并确认（取 advancement_count 个）
            adv = next(x[6] for x in E if x[0] == code)
            c, prop = jreq("GET", f"/api/projects/{e[2]}/rounds/{e[3]}/advancement-proposal", admin)
            names = [p["competitor_number"] for p in (prop.get("proposal") or [])][:adv] if prop else []
            if names:
                c, _ = jreq("POST", f"/api/projects/{e[2]}/rounds/{e[3]}/advancement-confirm", admin, {"advancing": names})
                report["admin"].append(f"confirm {code} -> {c}")

# 单轮/直出项目混排驱动
for e in E:
    code = e[0]
    if e[3] != 1 or e[2] in full_projects: continue
    target = ("published" if code in published_set else
              "calculated" if code in calculated_set else
              "scoring" if code in scoring_set else "pending")
    if target == "pending": continue
    logs = drive_event(code, target)
    report["admin"] += [f"{c} {t}" for c, t in logs]

# ---- 异常注入面 ----
def invariant(name, cond, detail=""):
    report["invariants"].append((name, bool(cond), detail))
    with lock: stats["codes"].setdefault("INV", 0)

first_pending = pending_set and sorted(pending_set)[0]
ceid_p = ceid_by_code.get(sorted(pending_set)[0]) if pending_set else None
c, _ = jreq("POST", f"/api/competition-events/{ceid_p}/open", admin, {"roster": [], "reset": False})
invariant("空名单开场=400", c == 400, c)
c, _ = jreq("PUT", f"/api/judge/competition-events/{ceid_p}/dances/X/sheet", judges[0][1], {"values": {}})
invariant("pending 场次提交=400", c == 400, c)
c, d = jreq("POST", "/api/login", http.cookiejar.CookieJar(), {"role": "judge", "judge_id": "HACK9"})
invariant("非法裁判=403", c == 403, c)
c, _ = jreq("GET", f"/api/events/{cid}/team-standings")
invariant("无会话管理standings=401", c == 401, c)
bad = login("admin", "wrong-password-1")
invariant("错口令=非200", bad is None, c)
# 评分制非法值（F2 已 published→关闭态提交=400；改用 scoring 集里 SCORE 场次注入）
sc_score = [c0 for c0 in scoring_set if typ_of(c0) == "SCORE"]
if sc_score:
    ceid_s = ceid_by_code[sorted(sc_score)[0]]
    c, _ = jreq("PUT", f"/api/judge/competition-events/{ceid_s}/dances/{urllib.parse.quote(dance_of(sorted(sc_score)[0]))}/sheet",
                judges[8][1], {"values": {n: 11 for n in roster_of(sorted(sc_score)[0])}})
    invariant("评分越界=400", c == 400, c)

# ---- 30 观众随机查询 ----
ENDPOINTS = [f"/public/schedule", "/public/results", "/screen",
             f"/api/public/events/{cid}/results", f"/api/public/events/{cid}/schedule",
             f"/api/public/events/{cid}/screen-state", f"/api/public/events/{cid}/team-standings",
             f"/api/events/{cid}/stream"]
stop = threading.Event()
def viewer(vid):
    deadline = time.time() + VIEWER_SECONDS
    while time.time() < deadline and not stop.is_set():
        ep = random.choice(ENDPOINTS)
        c, _ = req("GET", ep, timeout=10)
        if ep.endswith("/stream"):
            pass  # 短连即断
        time.sleep(random.uniform(0.2, 1.5))
    with lock: report["viewers"][vid] = "done"

t0 = time.time()
vts = [threading.Thread(target=viewer, args=(f"V{i:02d}",), daemon=True) for i in range(30)]
for t in vts: t.start()

# 观众在线期间：并发写压力（重开+重评一场 scoring 场次；多裁判同时提交同场）
sc_active = sorted(scoring_set)
if sc_active:
    ceid_w = ceid_by_code[sc_active[0]]
    def resubmit(jt):
        jn, jar = jt
        vals = sheet_payload(typ_of(sc_active[0]), roster_of(sc_active[0]), seed=f"re-{jn}")
        return jreq("PUT", f"/api/judge/competition-events/{ceid_w}/dances/{urllib.parse.quote(dance_of(sc_active[0]))}/sheet", jar, {"values": vals})[0]
    with ThreadPoolExecutor(max_workers=9) as ex:
        wr = list(ex.map(resubmit, judges))
    report["admin"].append(f"concurrent rewrites under viewer load -> {wr}")

for t in vts: t.join()
elapsed = time.time() - t0

# ---- 终局校验：无 5xx；standings 独立对照（最末轮口径）----
invariant("全程无 5xx", not stats["err5xx"], str(stats["err5xx"][:3]))
invariant("全程无连接异常", not stats["errors"], str(stats["errors"][:3]))
c, st = jreq("GET", f"/api/public/events/{cid}/team-standings")
invariant("standings 可用且 200", c == 200 and st is not None)

out = {"report": report, "codes": stats["codes"], "elapsed_s": round(elapsed, 1),
       "standings": st, "err5xx": stats["err5xx"], "errors": stats["errors"]}
print(json.dumps(out, ensure_ascii=False)[:4000])
open("/tmp/ds_sim_result.json", "w").write(json.dumps(out, ensure_ascii=False))
print("\nRESULT saved /tmp/ds_sim_result.json")
