#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R48 超大规模赛事测试数据生成器（自足式）。

基于2026首都高校体育舞蹈比赛竞赛规程设项表（44项）+ 实际报名数据（40校2524人）。
用法：python3 webapp/tools/build_mega_data.py [BASE]
"""
import io, json, random, sys, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302").rstrip("/")
random.seed(20260530)
CK = {"admin": "", "marshal": "", "judge": ""}


def req(method, path, body=None, raw=None, sess="admin"):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Cookie", CK.get(sess, ""))
    data = None
    if raw is not None:
        data = raw if isinstance(raw, bytes) else raw.encode()
        r.add_header("Content-Type", "text/csv; charset=utf-8")
    elif body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(r, data=data, timeout=60) as resp:
                sc = resp.headers.get("Set-Cookie")
                if sc:
                    CK[sess] = sc.split(";")[0]
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except Exception:
                return e.code, {}
        except Exception:
            import time as _t
            _t.sleep(1 + attempt)
    return 599, {}


def must(code, out, what):
    if code not in (200, 201):
        print(f"FAIL {what}: {code} {str(out)[:150]}")
        sys.exit(1)
    return out


# ===== 1. 登录 + 建赛 =====
must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 登录")
code, out = req("POST", "/api/events", {"name": "首都高校体育舞蹈比赛", "date": "2026-05-30", "location": "北京联合大学体育馆"})
cid = out.get("id") if code == 200 else None
if not cid:
    c, o = req("GET", "/api/events")
    cid = next((e["id"] for e in o.get("events", []) if "首都高校" in e["name"]), None)
    if not cid:
        print("FAIL 找不到赛事")
        sys.exit(1)
must(*req("POST", f"/api/events/{cid}/activate", {}), "激活赛事")
print(f"赛事 cid={cid}")

# ===== 2. 学校与选手 =====
SCHOOLS = [
    ("北京交通大学", 397), ("北京联合大学", 230), ("北京林业大学", 153),
    ("中央民族大学", 124), ("清华大学", 89), ("北京大学", 66),
    ("北京城市学院", 61), ("北京邮电大学", 59), ("北京化工大学", 51),
    ("北京理工大学", 41), ("中国传媒大学", 34), ("中国人民大学", 32),
    ("北京师范大学", 22), ("北京航空航天大学", 21), ("北京中医药大学", 16),
    ("中国农业大学", 14), ("华北电力大学", 10), ("首都师范大学", 8),
    ("中国石油大学（北京）", 320), ("中国人民公安大学", 140),
    ("对外经济贸易大学", 132), ("北京语言大学", 124), ("北京印刷学院", 119),
    ("北京信息科技大学", 64), ("国际关系学院", 48), ("中央财经大学", 36),
    ("民政职业大学", 28), ("首都经济贸易大学", 17), ("中国地质大学（北京）", 13),
    ("中国劳动关系学院", 12), ("北京第二外国语学院", 11), ("中华女子学院", 9),
    ("北京工商大学", 8), ("中国科学院大学", 5),
]
SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙",
            "马", "朱", "胡", "郭", "何", "林", "罗", "郑"]
GIVEN = ["明", "华", "文", "博", "雅", "婷", "宇", "浩", "思", "远",
         "欣", "怡", "俊", "洁", "丹", "静", "琳", "晶", "云", "飞"]

csv_comp = io.StringIO()
csv_comp.write("背番号,项目编号,姓名,学校/单位\n")
num = 1001
for school, count in SCHOOLS:
    for i in range(count):
        sn = SURNAMES[i % 20]
        gn = GIVEN[(i * 7 + num) % 20]
        csv_comp.write(f"{num},MULTI,{sn}{gn},{school}\n")
        num += 1
must(*req("POST", f"/api/events/{cid}/imports/competitors", raw=csv_comp.getvalue()), "导入选手")
TOTAL_PLAYERS = num - 1001
print(f"选手: {TOTAL_PLAYERS}")

csv_judge = io.StringIO()
csv_judge.write("裁判ID,姓名\n")
for i in range(1, 31):
    csv_judge.write(f"J{i},裁判{i:02d}\n")
must(*req("POST", f"/api/events/{cid}/imports/judges", raw=csv_judge.getvalue()), "导入裁判")

# ===== 3. 全部背号 =====
ALL = list(range(1001, 1001 + TOTAL_PLAYERS))


def seq(a, b):
    return [str(x) for x in range(a, b + 1)]


# ===== 4. 背号段分配 =====
STD_A = 1001;  STD_A_N = 24
LAT_A = 1025;  LAT_A_N = 24
STD_B = 1049;  STD_B_N = 18
LAT_B = 1067;  LAT_B_N = 18
STD_C = 1085;  STD_C_N = 10
LAT_C = 1095;  LAT_C_N = 10
STD_D = 1105;  STD_D_N = 6
LAT_D = 1111;  LAT_D_N = 6
FEMALE = 1117; FEM_N = 12
SIX_M = 1129;  SIX_M_N = 6
SIX_F = 1135;  SIX_F_N = 6
SIX_M2 = 1141; SIX_M2_N = 6
SIX_F2 = 1147; SIX_F2_N = 6
SIX_M3 = 1153; SIX_M3_N = 6
SIX_F3 = 1159; SIX_F3_N = 6
SIX_M4 = 1165; SIX_M4_N = 6
SIX_F4 = 1171; SIX_F4_N = 6
SIX_M5 = 1177; SIX_M5_N = 6
SIX_F5 = 1183; SIX_F5_N = 6
SIX_M6 = 1189; SIX_M6_N = 6
SIX_F6 = 1195; SIX_F6_N = 6
SIX_M7 = 1201; SIX_M7_N = 6
SIX_F7 = 1207; SIX_F7_N = 6
SIX_VW = 1213; SIX_VW_N = 18
QUEEN = 1231;  QUEEN_N = 12

EVENTS_DEF = [
    ("ZTAW",   "特长标准舞A组",   "SKATING", "华尔兹,探戈,维也纳华尔兹,狐步,快步", STD_A, STD_A_N),
    ("ZTAL",   "特长拉丁舞A组",   "SKATING", "桑巴,恰恰恰,伦巴,斗牛,牛仔",         LAT_A, LAT_A_N),
    ("ZTCW",   "特长标准舞C组",   "SKATING", "华尔兹,探戈,快步",                    STD_A + STD_A_N, 10),
    ("ZTCL",   "特长拉丁舞C组",   "SKATING", "恰恰恰,伦巴,牛仔",                    LAT_A + LAT_A_N, 10),
    ("ASTDP1", "A组标准舞预赛1组", "SKATING", "华尔兹,探戈,维也纳华尔兹,狐步,快步", STD_B, 9),
    ("ASTDP2", "A组标准舞预赛2组", "SKATING", "华尔兹,探戈,维也纳华尔兹,狐步,快步", STD_B + 9, 9),
    ("ALATP1", "A组拉丁舞预赛1组", "SKATING", "桑巴,恰恰恰,伦巴,斗牛,牛仔",         LAT_B, 9),
    ("ALATP2", "A组拉丁舞预赛2组", "SKATING", "桑巴,恰恰恰,伦巴,斗牛,牛仔",         LAT_B + 9, 9),
    ("BSTD",   "B组标准舞",       "SKATING", "华尔兹,探戈,狐步,快步",               STD_C, STD_C_N),
    ("BLAT",   "B组拉丁舞",       "SKATING", "桑巴,恰恰恰,伦巴,牛仔",               LAT_C, LAT_C_N),
    ("CSTD",   "C组标准舞",       "SKATING", "华尔兹,探戈,快步",                    STD_D, STD_D_N),
    ("CLAT",   "D组拉丁舞",       "SKATING", "恰恰恰,伦巴",                         LAT_D, LAT_D_N),
    ("DSTD",   "D组标准舞",       "SKATING", "华尔兹,探戈",                         STD_A + STD_A_N + 10, 4),
    ("DLAT",   "D组拉丁舞",       "SKATING", "恰恰恰,伦巴",                         LAT_A + LAT_A_N + 10, 4),
    ("WSOLO",  "华尔兹单项组",     "SKATING", "华尔兹",       STD_A + STD_A_N + 14, 6),
    ("TSOLO",  "探戈单项组",       "SKATING", "探戈",         LAT_A + LAT_A_N + 14, 6),
    ("VWSOLO", "维也纳华尔兹单项组","SKATING", "维也纳华尔兹", STD_B + STD_B_N, 6),
    ("FSOLO",  "狐步单项组",       "SKATING", "狐步",         LAT_B + LAT_B_N, 6),
    ("QSOLO",  "快步单项组",       "SKATING", "快步",         STD_C + STD_C_N, 4),
    ("WNEW",   "华尔兹新人组",     "SKATING", "华尔兹",       LAT_C + LAT_C_N, 6),
    ("CNEW",   "恰恰恰新人组",     "SKATING", "恰恰恰",       LAT_D + LAT_D_N, 6),
    ("SSOLO",  "桑巴单项组",       "SKATING", "桑巴",         LAT_A + LAT_A_N + 14, 4),
    ("CCSOLO", "恰恰恰单项组",     "SKATING", "恰恰恰",       LAT_B + LAT_B_N + 4, 4),
    ("RSOLO",  "伦巴单项组",       "SKATING", "伦巴",         LAT_C + LAT_C_N, 4),
    ("PSOLO",  "斗牛单项组",       "SKATING", "斗牛",         LAT_D + LAT_D_N + 6, 3),
    ("JSOLO",  "牛仔单项组",       "SKATING", "牛仔",         STD_D + STD_D_N, 3),
    ("FRSOLO", "女子单人伦巴组",   "SCORE",   "伦巴",         FEMALE, FEM_N),
    ("FCSOLO", "女子单人恰恰组",   "SCORE",   "恰恰恰",       FEMALE, FEM_N),
    ("STDQUE", "标准舞队列舞",     "SKATING", "华尔兹,探戈,维也纳华尔兹,狐步,快步", QUEEN, QUEEN_N),
    ("LATQUE", "拉丁舞队列舞",     "SKATING", "桑巴,恰恰恰,伦巴,斗牛,牛仔",         QUEEN + QUEEN_N, 4),
]

# 六人规定套路（14项）
six_dances = [("W", "华尔兹"), ("T", "探戈"), ("C", "恰恰恰"), ("R", "伦巴"),
              ("J", "牛仔"), ("S", "桑巴"), ("P", "斗牛")]
six_start = SIX_M
for gi, (gender, glabel) in enumerate([("男", "M"), ("女", "F")]):
    for di, (dl, dn) in enumerate(six_dances):
        code = f"6{glabel}{dl}"
        start = SIX_M + (gi * 7 + di) * SIX_M_N
        EVENTS_DEF.append((code, f"{gender}子{dl}六人规定套路组", "SCORE", [dn], start, SIX_M_N))
# 校园维也纳
EVENTS_DEF.append(("6VW", "六人校园维也纳华尔兹", "SCORE", ["维也纳华尔兹"], SIX_VW, SIX_VW_N))

print(f"总场次定义: {len(EVENTS_DEF)}")

# ===== 5. 建场 + 开场 + 检录 =====
ceid_map = {}
for code, name, typ, dances, start, count in EVENTS_DEF:
    roster = [str(x) for x in range(start, start + count)]
    c, o = req("POST", f"/api/events/{cid}/schedule/add",
               {"code": code, "name": name, "project": code[:3],
                "round": 1, "type": typ, "dances": ",".join(dances),
                "adv": 0, "roster": ",".join(roster)})
    if c != 200:
        print(f"WARN add {code}: {c} {str(o)[:100]}")
        continue
    ceid = o["event_id"]
    ceid_map[code] = ceid
    c2, o2 = req("POST", f"/api/competition-events/{ceid}/open",
                 {"roster": roster, "reset": False})
    if c2 != 200:
        print(f"WARN open {code}: {c2} {str(o2)[:80]}")
        continue
    # 检录（85% 全检、15% 检录 70%）
    check_n = count if i % 4 != 3 else int(count * 0.7)
    check_nums = roster[:check_n]
    if check_nums:
        req("POST", f"/api/competition-events/{ceid}/checkin",
            {"numbers": check_nums, "state": True}, sess="marshal")

print(f"场次建完+开场+检录: {len(ceid_map)}")

# ===== 6. 部分场次提交评分 =====
must(*req("POST", "/api/login", {"role": "admin", "password": "admin123"}), "admin 重登")
submitted = 0
for i, (code, ceid) in enumerate(list(ceid_map.items())[:25]):
    c, o = req("GET", f"/api/competition-events/{ceid}/progress")
    if c != 200:
        continue
    prog = o if isinstance(o, dict) else {}
    dances = prog.get("dances", [])
    checked_n = prog.get("checked_n", 0)
    if not dances or not checked_n:
        continue
    for j_idx in range(1, min(6, 31)):
        jid = f"J{j_idx}"
        req("POST", "/api/login", {"role": "judge", "judge_id": jid}, sess="judge")
        c4, o4 = req("GET", f"/api/competition-events/{ceid}/checkin")
        nums = o4.get("checked", []) if c4 == 200 else []
        if not nums:
            continue
        for dance in dances:
            if "SCORE" in str(code) or code.startswith("6") or "FR" in code or "FC" in code:
                vals = {n: round(6 + random.random() * 3.5, 1) for n in nums}
            else:
                order = nums[:]
                random.shuffle(order)
                vals = {n: idx + 1 for idx, n in enumerate(order)}
            from urllib.parse import quote
            c5, _ = req("PUT",
                        f"/api/judge/competition-events/{ceid}/dances/{quote(dance)}/sheet",
                        {"values": vals}, sess="judge")
            if c5 == 200:
                submitted += 1

print(f"评分提交: {submitted} 舞次")

# ===== 7. 汇总 =====
print(f"\n== 超大规模测试数据就绪 ==")
print(f"赛事 cid: {cid}")
print(f"总场次: {len(ceid_map)}, 评分提交: {submitted} 舞次")

with open("/tmp/mega_ids.json", "w") as f:
    json.dump({"cid": cid, "ceids": ceid_map}, f, ensure_ascii=False, indent=2)
print(f"映射文件: /tmp/mega_ids.json")
