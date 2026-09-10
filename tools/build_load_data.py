#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R41 压测数据构造器（API 驱动，面向远程测试服务器）。

规模：1 赛事 / 300 选手 / 13 裁判 / 9 场次（含 100 人大场×3 / 48 人顺位×4 / 32 人 Mark / 8 人决赛）。
用法：python3 tools/build_load_data.py [BASE]（默认 http://59.110.90.21:8321）
输出：/tmp/load_ids.json（场次 ceid 映射，供压测脚本使用）。幂等：重复运行复用已有场次。
"""
import io
import json
import time
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://59.110.90.21:8321").rstrip("/")
OUT = "/tmp/load_ids.json"
UNITS = ["压测大学", "清华大学", "复旦大学", "上海交通大学", "浙江大学", "南京大学",
         "武汉大学", "中山大学", "四川大学", "西安交通大学", "哈尔滨工业大学", "同济大学"]

CK = {"admin": "", "marshal": ""}


def req(method, path, body=None, raw_body=None, content_type=None, sess="admin"):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Cookie", CK.get(sess, ""))
    data = None
    if raw_body is not None:
        data = raw_body if isinstance(raw_body, bytes) else raw_body.encode()
        r.add_header("Content-Type", content_type or "text/csv; charset=utf-8")
    elif body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    last = None
    for attempt in range(4):   # 公网半包/瞬断重试
        try:
            with urllib.request.urlopen(r, data=data, timeout=90) as resp:
                sc = resp.headers.get("Set-Cookie")
                if sc:
                    CK[sess] = sc.split(";")[0]
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except Exception:
                return e.code, {}
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    return 599, {"detail": f"transport: {last}"}


def must(code, out, what):
    if code not in (200, 201):
        print(f"FAIL {what}: {code} {str(out)[:200]}")
        sys.exit(1)
    return out


# ---- 登录 + 建赛（口令走环境变量，禁止写死）----
import os
ADMIN_PW = os.environ.get("DSPORT_ADMIN_PASSWORD", "admin123")
must(*req("POST", "/api/login", {"role": "admin", "password": ADMIN_PW}), "admin 登录")
c0, o0 = req("GET", "/api/events")
existing = [e for e in o0.get("events", []) if e["name"] == "压测公开赛"]
if existing:
    cid = existing[0]["id"]
    print(f"复用已有压测赛事 cid={cid}")
else:
    code, out = req("POST", "/api/events", {"name": "压测公开赛", "date": "2026-09-10", "location": "压测馆"})
    cid = must(code, out, "建赛")["id"]
must(*req("POST", f"/api/events/{cid}/activate", {}), "激活")
print(f"赛事 cid={cid}")

# ---- 300 选手 CSV（背号 1001-1300，项目 P1）----
csv = io.StringIO()
csv.write("背番号,项目编号,姓名,学校/单位\n")
for i in range(300):
    num = 1001 + i
    csv.write(f"{num},P1,压测选手{i},{UNITS[i % len(UNITS)]}\n")
must(*req("POST", f"/api/events/{cid}/imports/competitors", raw_body=csv.getvalue()), "导入 300 选手")

# ---- 13 裁判 CSV ----
csv = io.StringIO()
csv.write("裁判ID,姓名\n")
for i in range(1, 14):
    csv.write(f"J{i},压测裁判{i}\n")
must(*req("POST", f"/api/events/{cid}/imports/judges", raw_body=csv.getvalue()), "导入 13 裁判")

# ---- 场次 ----
def ensure_event(code_e, name, typ, dances, roster):
    """存在则复用（补开场/检录），否则建场。"""
    c, o = req("GET", f"/api/public/events/{cid}/schedule")
    ceid = None
    if c == 200:
        for e in o.get("events", []):
            if e["code"] == code_e:
                ceid = e["id"]
                break
    if ceid is None:
        c2, o2 = req("POST", f"/api/events/{cid}/schedule/add",
                     {"code": code_e, "name": name, "project": code_e.rstrip("0123456789") or code_e,
                      "round": 1, "type": typ, "dances": dances, "adv": 0, "roster": roster})
        must(c2, o2, f"建场 {code_e}")
        ceid = o2["event_id"]
    # 开场（幂等：已 scoring 也会成功）+ 全检录
    c3, o3 = req("POST", f"/api/competition-events/{ceid}/open",
                 {"roster": roster.split(","), "reset": False})
    if c3 != 200:
        print(f"WARN open {code_e}: {c3} {str(o3)[:120]}")
    must(*req("POST", "/api/login", {"role": "marshal", "username": "marshal",
                                     "password": os.environ.get("DSPORT_MARSHAL_PASSWORD", "marshal123")},
              sess="marshal"), "marshal 登录")
    c4, o4 = req("POST", f"/api/competition-events/{ceid}/checkin",
                 {"numbers": roster.split(","), "state": True}, sess="marshal")
    if c4 != 200:
        print(f"WARN checkin {code_e}: {c4} {str(o4)[:120]}")
    return ceid


grp = lambda a, b: ",".join(str(x) for x in range(a, b + 1))
ids = {
    "cid": cid,
    "F1": ensure_event("F1", "F1压测决赛", "SCORE", "集体舞", grp(1001, 1008)),
    "W1A": ensure_event("W1A", "W1压测A组", "SKATING", "华尔兹", grp(1009, 1020)),
    "W1B": ensure_event("W1B", "W1压测B组", "SKATING", "华尔兹", grp(1021, 1032)),
    "W1C": ensure_event("W1C", "W1压测C组", "SKATING", "华尔兹", grp(1033, 1044)),
    "W1D": ensure_event("W1D", "W1压测D组", "SKATING", "华尔兹", grp(1045, 1056)),
    "L1": ensure_event("L1", "L1压测", "MARK", "恰恰", grp(1057, 1088)),
    "S1A": ensure_event("S1A", "S1压测A组", "SCORE", "集体舞", grp(1089, 1188)),
    "S1B": ensure_event("S1B", "S1压测B组", "SCORE", "集体舞", grp(1189, 1288)),
    "S1C": ensure_event("S1C", "S1压测C组", "SCORE", "集体舞", grp(1189, 1300)),
}
with open(OUT, "w") as f:
    json.dump(ids, f)
print("压测数据就绪 →", OUT)
print(json.dumps(ids, ensure_ascii=False))
