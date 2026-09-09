#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R39 压测数据构造器：在全新 DB 上复刻真实规模赛事，制造复杂边界条件。

用法：DSPORT_DB=/tmp/ds_stress.db python3 tools/build_stress_data.py [BASE]
  先用该 DB 起服务（DSPORT_PORT=8302），再跑本脚本完成数据铺排。

数据规模与边界设计：
- 1 赛事 / 13 单位（含超长单位名）/ 101 选手 / 9 裁判 / 12 场次
- 项目：W1 标准舞（顺位法 48 人 R1×4 组→R2 24→F6，双舞种华尔兹+探戈）
        L1 拉丁（Mark 制 32 人 R1×2 组→F）、S1 集体舞（评分制 12 队）、T1 团体（顺位法 6 队）
- 检录边界：全检 / 部分 7/12（灰行）/ 0 检录 / 决赛缺席（晋级后未到场）
- 评分边界：W1R1A 构造顺位法平分（majority 全平→并列）、S1F 三裁判同分 8.5→并列
- 状态混合：published / calculated / scoring（部分裁判提交）/ pending
"""
import io
import json
import sqlite3
import sys
import time

import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
DB = sys.argv[2] if len(sys.argv) > 2 else "/tmp/ds_stress.db"

CK = {"admin": "", "marshal": "", "judge": ""}


def req(method, path, body=None, raw=False, sess="admin"):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Cookie", CK.get(sess, ""))
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, data=data, timeout=30) as resp:
            setc = resp.headers.get("Set-Cookie")
            if setc:
                CK[sess] = setc.split(";")[0]
            return resp.status, (resp.read() if raw else json.loads(resp.read() or b"{}"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def must(code, out, what):
    if code not in (200, 201):
        print(f"FAIL {what}: {code} {str(out)[:200]}")
        sys.exit(1)
    return out


UNITS = ["北京大学", "清华大学", "复旦大学", "上海交通大学", "浙江大学", "南京大学",
         "武汉大学", "中山大学", "四川大学", "西安交通大学", "哈尔滨工业大学", "同济大学",
         "某某市青少年体育舞蹈运动培训中心示范基地"]
NAMES = ["王伟", "李娜", "张敏", "刘洋", "陈静", "杨帆", "赵磊", "黄晓明", "周杰", "吴倩",
         "徐峥", "孙俪", "马龙", "朱婷", "胡军", "郭富城", "林丹", "何炅", "高圆圆", "梁朝伟"]

# ---------- 1. 登录 + 建赛事 ----------
must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 登录")
code, out = req("POST", "/api/events", {"name": "2026城市体育舞蹈公开赛", "date": "2026-09-09", "location": "滨江体育馆"})
if code == 200:
    cid = out.get("id") or must(*req("GET", "/api/events", None, False), "赛事列表")["events"][0]["id"]
else:
    evs = must(*req("GET", "/api/events", None, False), "赛事列表")["events"]
    cid = evs[0]["id"]
must(*req("POST", f"/api/events/{cid}/activate", {}), "激活赛事")
print(f"赛事 cid={cid}")

# ---------- 2. SQL 直插选手库 / 裁判 ----------
conn = sqlite3.connect(DB)
rows = []


def add_players(prefix, start, count, project):
    for i in range(count):
        num = f"{prefix}{start + i}"
        name = NAMES[i % len(NAMES)] + ("" if i < len(NAMES) else str(i // len(NAMES) + 1))
        unit = UNITS[i % len(UNITS)]
        rows.append((cid, num, project, name, unit))


add_players("", 101, 48, "W1")     # 101-148 标准舞
add_players("", 201, 32, "L1")     # 201-232 拉丁
add_players("", 301, 12, "S1")     # 301-312 集体舞（队）
add_players("", 401, 6, "T1")      # 401-406 团体
for i in (3, 10, 15):              # 双人跨单位样例（名次赋分归主报）
    rows.append((cid, f"5{i:02d}", "T1", NAMES[i] + "/" + NAMES[(i + 5) % len(NAMES)], UNITS[i % len(UNITS)]))
conn.executemany("INSERT OR REPLACE INTO competitors(competition_id, number, project_code, name, unit) VALUES(?,?,?,?,?)", rows)
conn.executemany("INSERT OR REPLACE INTO judges(competition_id, code, name) VALUES(?,?,?)",
                 [(cid, f"J{i}", f"裁判{i}号") for i in range(1, 10)])
conn.commit()
print(f"选手 {len(rows)} 人 / 裁判 9 名")


# ---------- 3. 建场次 ----------
def add_event(code_e, name, project, round_no, typ, dances, adv, roster=None):
    c2, o2 = req("POST", f"/api/events/{cid}/schedule/add",
                 {"code": code_e, "name": name, "project": project, "round": round_no,
                  "type": typ, "dances": dances, "adv": adv, "roster": roster or ""})
    if c2 != 200:
        # 已存在则查 id
        c3, o3 = req("GET", f"/api/public/events/{cid}/schedule")
        for e in o3["events"]:
            if e["code"] == code_e:
                return e["id"]
        print(f"FAIL 建场 {code_e}: {c2} {str(o2)[:200]}")
        sys.exit(1)
    return o2["event_id"]


grp = lambda rng: ",".join(str(x) for x in rng)
W1R1 = [add_event(f"W1R1{g}", f"W1第1轮{g}组", "W1", 1, "SKATING", "华尔兹", 6,
                  grp(range(101 + 12 * i, 113 + 12 * i))) for i, g in enumerate("ABCD")]
W1R2 = add_event("W1R2", "W1第2轮", "W1", 2, "SKATING", "华尔兹,探戈", 6)   # roster 由晋级回填
W1F = add_event("W1F", "W1决赛", "W1", 3, "SKATING", "华尔兹,探戈", 0)
L1R1 = [add_event(f"L1R1{g}", f"L1第1轮{g}组", "L1", 1, "MARK", "恰恰", 8,
                  grp(range(201 + 16 * i, 217 + 16 * i))) for i, g in enumerate("AB")]
L1F = add_event("L1F", "L1决赛", "L1", 2, "MARK", "恰恰", 6)
S1F = add_event("S1F", "S1集体舞决赛", "S1", 2, "SCORE", "集体舞", 0, grp(range(301, 313)))
T1F = add_event("T1F", "T1团体决赛", "T1", 2, "SKATING", "团体舞", 0,
                ",".join([str(x) for x in range(401, 407)] + [f"5{i:02d}" for i in (3, 10, 15)]))
S2R1 = add_event("S2R1", "S2第1轮", "S2", 1, "SCORE", "集体舞", 6,
                 ",".join(str(x) for x in range(301, 313)))
print("场次建立完成")


# ---------- 4. 动线工具 ----------
JUDGES = [f"J{i}" for i in range(1, 10)]


def judge_login(j):
    must(*req("POST", "/api/login", {"role": "judge", "judge_id": j}, sess="judge"), f"{j} 登录")


def marshal_login():
    must(*req("POST", "/api/login", {"role": "marshal", "username": "marshal",
                                     "password": "marshal123"}, sess="marshal"), "marshal 登录")


def open_ev(ceid, roster_nums):
    return req("POST", f"/api/competition-events/{ceid}/open",
               {"roster": [str(n) for n in roster_nums], "reset": False}, sess="admin")


def checkin(ceid, nums, state=True):
    marshal_login()
    return req("POST", f"/api/competition-events/{ceid}/checkin",
               {"numbers": [str(n) for n in nums], "state": state}, sess="marshal")


def submit(ceid, dance, judge, values):
    from urllib.parse import quote
    return req("PUT", f"/api/judge/competition-events/{ceid}/dances/{quote(dance)}/sheet",
               {"values": values}, sess="judge")


def calc(ceid):
    return req("POST", f"/api/competition-events/{ceid}/calculate", {}, sess="admin")


def publish(ceid):
    return req("POST", f"/api/competition-events/{ceid}/publish", {}, sess="admin")


def qualified_of(ceid, dance, n):
    c2, o2 = req("GET", f"/api/competition-events/{ceid}/results")
    if c2 != 200:
        print(f"FAIL 读结果 {ceid}")
        sys.exit(1)
    data = o2["data"]
    rows_r = (data.get("dance_results") or {}).get(dance) or []
    out = [str(r["competitor_number"]) for r in rows_r[:n]]
    assert len(out) == n, f"晋级名单不足: {ceid} {dance} -> {len(out)}"
    return out


def run_skating_group(ceid, nums, judges, tie=False):
    """顺位法组：全检录 → 每裁判提交顺位 → 计算（收齐自动/手动兜底）。
    tie=True 时构造前两名 2v2 对称顺位（complete majority tie，系统按编号序确定性打破）。"""
    must(*open_ev(ceid, nums), f"{ceid} open")
    must(*checkin(ceid, nums), f"{ceid} checkin")
    base = list(map(int, nums))
    for k, j in enumerate(judges):
        judge_login(j)
        vals = {}
        order = base[:]
        if tie and k % 2 == 0:
            order = [102, 101] + order[2:]   # J1/J3/J5: 102 先
        elif tie:
            order = [101, 102] + order[2:]   # J2/J4: 101 先 → 101/102 各 2/3 个第1：构造全平用 3+2
        for rank, num in enumerate(order):
            vals[str(num)] = rank + 1
        must(*submit(ceid, "华尔兹", j, vals), f"{ceid} {j} 提交")
    must(*calc(ceid), f"{ceid} 计算")


# ---------- 5. W1R1 四组（A 组平分构造，B 组正常发布，C 组只算不发，D 组部分检录评分中） ----------
must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 重登")
run_skating_group(W1R1[0], range(101, 113), JUDGES[:4], tie=True)   # 4 裁判 2v2 均衡 → majority 全平 → 并列
publish(W1R1[0])
run_skating_group(W1R1[1], range(113, 125), JUDGES[:5])
publish(W1R1[1])
run_skating_group(W1R1[2], range(125, 137), JUDGES[:5])

# D 组：12 人中 5 人未检录（灰行），5 裁判仅对已检录 7 人提交，scoring 停在部分提交
ceid_d = W1R1[3]
must(*open_ev(ceid_d, range(137, 149)), "D组 open")
must(*checkin(ceid_d, range(137, 144)), "D组 checkin 7/12")   # 137-143 检录，144-148 灰行
for k, j in enumerate(JUDGES[:5]):
    judge_login(j)
    vals = {str(n): i + 1 for i, n in enumerate(range(137, 144))}
    must(*submit(ceid_d, "华尔兹", j, vals), f"D组 {j} 提交")
print("W1R1 A/B/C/D 铺排完成")

# ---------- 6. W1R2：晋级回填（A/B 组各前 6 → 12 人），双舞种，4/9 裁判提交 ----------
q = []
for ceid in W1R1[:2]:
    q += qualified_of(ceid, "华尔兹", 6)
must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 重登")
must(*open_ev(W1R2, q), f"W1R2 open roster={q}")
must(*checkin(W1R2, q), "W1R2 checkin")
for j in JUDGES[4:]:
    judge_login(j)
    for dance in ("华尔兹", "探戈"):
        vals = {str(n): i + 1 for i, n in enumerate(q)}
        must(*submit(W1R2, dance, j, vals), f"W1R2 {j} {dance}")
must(*calc(W1R2), "W1R2 计算")
q2 = qualified_of(W1R2, "华尔兹", 6)
# 退回评分：W1R2 回到 scoring（评分清空、检录保留）供裁判续评走查；W1F 名单已由真实 R2 结果驱动
must(*req("POST", f"/api/competition-events/{W1R2}/return-scores", {}, sess="admin"), "W1R2 退回评分")
print(f"W1R2 铺排完成（{len(q)} 人收齐→计算→退回 scoring；晋级 {len(q2)} → W1F）")

# ---------- 7. W1F：R2 晋级 6 人中 1 人缺席（晋级但未检录），双舞种 3/9 提交 ----------
must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 重登")
must(*open_ev(W1F, q2), "W1F open")
must(*checkin(W1F, q2[1:6]), "W1F checkin（首位缺席）")
for j in JUDGES[:3]:
    judge_login(j)
    for dance in ("华尔兹", "探戈"):
        vals = {str(n): i + 1 for i, n in enumerate(q2[1:6])}
        must(*submit(W1F, dance, j, vals), f"W1F {j} {dance}")
print("W1F 铺排完成（5/6 到场，双舞种 3/9 提交）")

# ---------- 8. L1R1 A/B（Mark 制）：A 发布、B 只算 ----------
must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 重登")
for idx, ceid in enumerate(L1R1):
    nums = list(range(201 + 16 * idx, 217 + 16 * idx))
    must(*open_ev(ceid, nums), f"L1R1{idx} open")
    must(*checkin(ceid, nums if idx == 0 else nums[:12]), f"L1R1{idx} checkin")   # B 组 12/16（4 灰）
    for j in JUDGES[2:7]:                            # 5 裁判
        judge_login(j)
        vals = {str(n): (i < 8) for i, n in enumerate(nums[:12])}
        must(*submit(ceid, "恰恰", j, vals), f"L1R1 {ceid} {j}")
    must(*calc(ceid), f"L1R1 {ceid} 计算")
publish(L1R1[0])
print("L1R1 A/B 铺排完成")

# ---------- 9. S1F 评分制：全检录、3/9 裁判提交、构造两队同分 8.5 ----------
must(*open_ev(S1F, range(301, 313)), "S1F open")
must(*checkin(S1F, range(301, 313)), "S1F checkin")
for j in JUDGES[:3]:
    judge_login(j)
    vals = {}
    for i, n in enumerate(range(301, 313)):
        v = 8.5 if i in (0, 1) else round(6.0 + (i - 2) * 0.4, 1)   # 301/302 三裁判全同分
        vals[str(n)] = v
    must(*submit(S1F, "集体舞", j, vals), f"S1F {j}")
must(*calc(S1F), "S1F 计算（平分并列 4,4）")
print("S1F 铺排完成（calculated，301/302 平分并列边界，待走查发布）")

# ---------- 10. 汇总 ----------
c2, o2 = req("GET", f"/api/public/events/{cid}/schedule")
from collections import Counter
cnt = Counter(e["status"] for e in o2["events"])
print(f"\n== 压测数据就绪：{len(o2['events'])} 场次，状态分布 {dict(cnt)} ==")
print(f"ceid 映射: W1R1A={W1R1[0]} B={W1R1[1]} C={W1R1[2]} D={W1R1[3]} R2={W1R2} F={W1F} "
      f"L1A={L1R1[0]} B={L1R1[1]} LF={L1F} S1F={S1F} T1F={T1F} S2R1={S2R1}")
