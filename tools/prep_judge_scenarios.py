#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""裁判动线场景预置：为浏览器 E2E 准备特定状态的场次。
用法: python3 tools/prep_judge_scenarios.py [BASE] [CID]
  1. S7R1（SKATING/探戈）：开场 + J1-J8 已提交 —— 留浏览器 J9 收尾触发自动计算
  2. S9R1（SKATING 两舞种 华尔兹+探戈，现场新增）：开场 + J1-J4 已提交两舞 —— 浏览器验证分舞种提交
  3. 其余 scoring 态场次维持 J1-J4 部分评分（驱动器产物）
"""
import json, sys, time, urllib.parse

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8321"
CID = int(sys.argv[2]) if len(sys.argv) > 2 else 11
_SRC = None
try:
    _SRC = open(__file__.rsplit("/", 1)[0] + "/sim_robustness.py").read()
except OSError:
    pass
if _SRC is None:
    _SRC = open("tools/sim_robustness.py").read()
exec(compile(_SRC.split("# ---------- 主流程 ----------")[0], "sim", "exec"))

admin = login("admin", "admin123")
assert admin, "admin login"
judges = []
for k in range(1, 10):
    j = login("judge", f"J{k}")
    assert j, f"J{k} login"
    judges.append((f"J{k}", j))

_, pub = jreq("GET", f"/api/public/events/{CID}/schedule")
ceid = {e["code"]: e["id"] for e in pub.get("events", [])}

def status_of(code_):
    for e in pub.get("events", []):
        if e["code"] == code_: return e["status"]
    return "?"

# ---- 1. S7R1：8 裁判已评，留 J9 ----
roster = [str(101 + i) for i in range(8)]
c, _ = jreq("POST", f"/api/competition-events/{ceid['S7R1']}/open", admin, {"roster": roster, "reset": False})
print("open S7R1:", c)
for jn, jar in judges[:8]:
    rnd = __import__("random").Random(f"S7R1-{jn}")
    perm = roster[:]; rnd.shuffle(perm)
    vals = {n: i + 1 for i, n in enumerate(perm)}
    c, d = jreq("PUT", f"/api/judge/competition-events/{ceid['S7R1']}/dances/{urllib.parse.quote('探戈')}/sheet",
                jar, {"values": vals})
    print(f"S7R1 {jn}:", c)
print("S7R1 status:", status_of("S7R1"))

# ---- 2. S9R1：两舞种场次 ----
c, d = jreq("POST", f"/api/events/{CID}/schedule/add", admin, {
    "code": "S9R1", "name": "S9两舞验证", "project": "S9", "round": 1,
    "type": "SKATING", "adv": 0, "dances": "华尔兹,探戈", "roster": ",".join(roster)})
print("add S9R1:", c, d)
if c == 200:
    ceid["S9R1"] = d["event_id"]
    c, _ = jreq("POST", f"/api/competition-events/{ceid['S9R1']}/open", admin, {"roster": roster, "reset": False})
    print("open S9R1:", c)
    for jn, jar in judges[:4]:
        for dance in ("华尔兹", "探戈"):
            rnd = __import__("random").Random(f"S9R1-{jn}-{dance}")
            perm = roster[:]; rnd.shuffle(perm)
            vals = {n: i + 1 for i, n in enumerate(perm)}
            c, _ = jreq("PUT", f"/api/judge/competition-events/{ceid['S9R1']}/dances/{urllib.parse.quote(dance)}/sheet",
                        jar, {"values": vals})
            print(f"S9R1 {jn} {dance}:", c)
print("S9R1 status:", status_of("S9R1"))

# ---- 3. scoring 态总览 ----
c, pub2 = jreq("GET", f"/api/public/events/{CID}/schedule")
sc = [(e["code"], e["status"]) for e in pub2["events"] if e["status"] == "scoring"]
print("scoring events:", sc)
print("PREP DONE")
