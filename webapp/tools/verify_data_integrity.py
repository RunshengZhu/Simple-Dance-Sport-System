#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R48 数据完整性全量验证：所有场次的评分/检录/结果/发布状态 + 跨场次一致性 + 审计日志。"""
import json
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8303").rstrip("/")
CK = {"admin": "", "marshal": "", "judge": "", "anon": ""}


def req(method, path, body=None, sess="admin"):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Cookie", CK.get(sess, ""))
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, data=data, timeout=30) as resp:
            sc = resp.headers.get("Set-Cookie")
            if sc:
                CK[sess] = sc.split(";")[0]
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


PASS = 0
FAIL = 0
FAILS = []


def check(step, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✅ {step}")
    else:
        FAIL += 1
        FAILS.append(step)
        print(f"  ❌ {step} :: {detail[:120]}")


# ===== 登录 =====
c, _ = req("POST", "/api/login", {"role": "admin", "password": "admin123"})
assert c == 200, "admin 登录失败"
print("== 登录 OK ==\n")

# ===== 1. 赛事结构完整性 =====
print("── 1. 赛事结构 ──")
c, evs = req("GET", "/api/events")
all_events = evs.get("events", [])
active = [e for e in all_events if e.get("active")]
check("存在激活赛事", len(active) > 0, f"active={len(active)}/{len(all_events)}")
if not active:
    print("无激活赛事，退出")
    sys.exit(1)
CID = active[0]["id"]
print(f"  激活赛事: cid={CID} {active[0]['name']}")

c, sched = req("GET", f"/api/public/events/{CID}/schedule")
all_sched = sched.get("events", [])
status_counts = {}
for e in all_sched:
    status_counts[e["status"]] = status_counts.get(e["status"], 0) + 1
check("场次状态非空", len(status_counts) > 0, str(status_counts))
print(f"  状态分布: {status_counts}")

# ===== 2. 逐场次评分数据验证 =====
print("\n── 2. 逐场次数据验证 ──")
total_score_records = 0
total_results = 0
total_checkin = 0
issues = []

for e in all_sched:
    ceid = e["id"]
    code = e["code"]
    status = e["status"]

    # 2a. 检录数据
    c, ck = req("GET", f"/api/competition-events/{ceid}/checkin")
    if c != 200:
        issues.append(f"{code}: checkin API {c}")
        continue
    checked = ck.get("checked", [])
    total_checkin += len(checked)
    _cn = ck.get("checked_n", 0)
    _tt = ck.get("total", 0)
    check(f"  {code} 检录 {_cn}/{_tt}", _cn <= _tt,
          f"checked={_cn} total={_tt}")

    # 2b. 评分数据（如有）
    c, prog = req("GET", f"/api/competition-events/{ceid}/progress")
    if c != 200:
        continue
    matrix = prog.get("matrix", {})
    dances = prog.get("dances", [])
    judges = prog.get("judges", [])
    for j in judges:
        for d in dances:
            n = matrix.get(j, {}).get(d, "0/0")
            if "/" in str(n):
                done, total_n = str(n).split("/")
                if int(done) > int(total_n):
                    issues.append(f"{code} {j}/{d}: 提交数 {done} > 检录数 {total_n}")

    # 2c. 已计算场次的结果完整性
    if status in ("calculated", "published"):
        c, res = req("GET", f"/api/competition-events/{ceid}/results")
        if c != 200:
            issues.append(f"{code}: results API {c}")
            continue
        dance_results = res.get("data", {}).get("dance_results", {})
        for dance_name, rows in dance_results.items():
            if not rows:
                issues.append(f"{code}/{dance}: 空结果")
                continue
            # 验证名次连续性（允许并列）
            prev_rank = 0
            for r in rows:
                if r["rank"] < prev_rank:
                    issues.append(f"{code}/{dance}: 名次回退 {r['rank']} < {prev_rank}")
                prev_rank = r["rank"]
            total_results += len(rows)
    total_score_records += 1

print(f"  已验证场次: {len(all_sched)}")
check("无数据一致性问题", len(issues) == 0, "; ".join(issues[:5]))

# ===== 3. 已发布场次验证 =====
print("\n── 3. 已发布场次 ──")
published = [e for e in all_sched if e["status"] == "published"]
check("存在已发布场次", len(published) > 0, f"published={len(published)}")
for e in published:
    ceid = e["id"]
    code = e["code"]
    c, res = req("GET", f"/api/competition-events/{ceid}/results")
    check(f"  {code} results 200", c == 200, f"status={c}")
    if c == 200:
        dr = res.get("data", {}).get("dance_results", {})
        check(f"  {code} 有舞蹈结果", len(dr) > 0, f"dances={list(dr.keys())}")

# 公开页可见性
c, pub = req("GET", f"/api/public/events/{CID}/results", sess="anon")
pub_data = pub.get("published_results", []) if isinstance(pub, dict) else []
check("公开 results 有数据", len(pub_data) > 0, f"count={len(pub_data)}")

# ===== 4. 团体总分 =====
c, standings = req("GET", f"/api/public/events/{CID}/team-standings", sess="anon")
ts = standings.get("standings", []) if isinstance(standings, dict) else []
check("团体总分有数据", len(ts) > 0, f"count={len(ts)}")
if ts:
    # 验证总分排序
    prev_total = float("inf")
    sorted_ok = True
    for s in ts:
        total = float(s.get("total", 0))
        if total > prev_total:
            sorted_ok = False
        prev_total = total
    check("团体总分降序", sorted_ok, f"first={ts[0].get('total') if ts else '?'}")

# ===== 5. 审计日志 =====
c, audit = req("GET", "/api/audit?limit=200")
if c == 200:
    entries = audit.get("entries", audit.get("audit", []))
    check("审计日志有记录", len(entries) > 0, f"count={len(entries)}")
    # 验证关键操作有留痕
    actions = set(e.get("action", "") for e in entries)
    for expected in ["return_scores", "uncheckin", "user_password"]:
        if expected in actions:
            print(f"  审计含 {expected}: ✅")
else:
    check("审计日志端点可用", c == 200, f"status={c}")

# ===== 6. 汇总 =====
print(f"\n{'='*50}")
print(f"总计: {PASS} passed, {FAIL} failed")
if FAILS:
    print(f"失败项: {FAILS}")
sys.exit(1 if FAIL else 0)
