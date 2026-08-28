#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E 冒烟（urllib，无第三方依赖）：管理员/裁判全动线 + 越权与非法输入用例。
用法：python server/selftest.py   # 需服务已在本机 8321 运行且 DB 为空
"""
import json
import os
import urllib.request
import urllib.parse

BASE = os.environ.get("DSPORT_BASE", "http://127.0.0.1:8321")
PASS, FAIL = [], []


def call(method, path, body=None, headers=None, cookie=None, raw=None):
    if "?" in path:
        p, q = path.split("?", 1)
        encoded = urllib.parse.quote(p) + "?" + q
    else:
        encoded = urllib.parse.quote(path)
    req = urllib.request.Request(BASE + encoded, method=method)
    if cookie:
        req.add_header("Cookie", "session=" + cookie)
    data = None
    if raw is not None:
        data = raw.encode("utf-8")
        req.add_header("Content-Type", "text/csv; charset=utf-8")
    elif body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data) as r:
            set_cookie = r.headers.get("Set-Cookie", "")
            token = set_cookie.split("session=")[1].split(";")[0] if "session=" in set_cookie else cookie
            return r.status, json.loads(r.read().decode()) if r.headers.get("Content-Type", "").startswith("application/json") else r.read().decode(), token
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode()), cookie
        except Exception:
            return e.code, {}, cookie


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name + ("" if cond else "  ← " + str(extra)[:200]))
    print(("✓" if cond else "✗"), name, "" if cond else extra)


# --- 登录与越权
st, _, tok = call("POST", "/api/login", {"role": "admin", "password": "admin123"})
check("管理员登录", st == 200 and tok)
st, d, _ = call("POST", "/api/login", {"role": "admin", "password": "wrong"})
check("错误口令被拒", st == 403)
st, d, _ = call("POST", "/api/login", {"role": "judge", "judge_id": "JX"})
check("非法裁判ID被拒", st == 403)
st, d, _ = call("GET", "/api/events")
check("未登录访问管理 API 被拒", st == 401)

# --- 建赛与导入
st, d, tok = call("POST", "/api/login", {"role": "admin", "password": "admin123"})
st, d, _ = call("POST", "/api/events", {"name": "自测赛", "date": "2026-08-27", "location": "馆"}, cookie=tok)
cid = d["id"]
check("创建赛事", st == 200 and cid)
call("POST", "/api/events/%d/activate" % cid, {}, cookie=tok)
csv_c = "背番号,项目编号,姓名,学校/单位\n101,W1,张三,A大\n102,W1,李四,B大\n103,W1,王五,C大\n104,W1,赵六,D大\n"
csv_m = "背番号,项目编号,姓名,学校/单位\n201,M1,甲,A大\n202,M1,乙,B大\n203,M1,丙,C大\n204,M1,丁,D大\n"
csv_j = "裁判ID,姓名\nJ1,王\nJ2,李\nJ3,张\n"
csv_s = ('场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n'
         'E1,W1第1轮,W1,1,华尔兹,SKATING,2,"101,102,103,104"\n'
         'E2,W1第2轮,W1,2,华尔兹,SKATING,0,\n'
         'M1,M1第1轮,M1,1,现代舞,MARK,2,"201,202,203,204"\n')
for kind, raw in [("competitors", csv_c), ("competitors", csv_m), ("judges", csv_j), ("schedule", csv_s)]:
    st, d, _ = call("POST", "/api/events/%d/imports/%s" % (cid, kind), raw=raw, cookie=tok)
    check("导入 %s" % kind, st == 200 and d.get("imported", 0) > 0, d)
st, d, _ = call("POST", "/api/events/%d/imports/competitors" % cid, raw="背面番,x\n1,y\n", cookie=tok)
check("非法 CSV 列被拒", st == 400, d)

# --- 顺位法场次 E1：开场 + 三裁判提交 → 自动计算
evs = db_events = call("GET", "/api/public/events/%d/schedule" % cid)[1]["events"]
e1 = next(e for e in db_events if e["code"] == "E1")
roster = ["101", "102", "103", "104"]
st, d, _ = call("POST", "/api/competition-events/%d/open" % e1["id"], {"roster": roster}, cookie=tok)
check("E1 开场", st == 200)

sheets = {
    "J1": {"101": 1, "102": 2, "103": 3, "104": 4},
    "J2": {"101": 1, "102": 2, "103": 3, "104": 4},
    "J3": {"101": 2, "102": 1, "103": 3, "104": 4},
}
jtoks = {}
auto = False
for j, vals in sheets.items():
    st, _, jtoks[j] = call("POST", "/api/login", {"role": "judge", "judge_id": j})
    check("%s 裁判登录" % j, st == 200)
    st, d, _ = call("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (e1["id"], "华尔兹"),
                    {"values": vals}, cookie=jtoks[j])
    check("%s 提交名次表" % j, st == 200, d)
    auto = auto or d.get("auto_calculated")
check("收齐后自动计算触发", auto)

# 名次与桌面版口径一致：101:1, 102:2, 103:3, 104:4
st, d, _ = call("GET", "/api/competition-events/%d/results" % e1["id"], cookie=tok)
ranks = {r["competitor_number"]: r["rank"] for r in d["data"]["overall_results"]}
check("E1 结果与桌面版口径一致", ranks == {"101": 1, "102": 2, "103": 3, "104": 4}, ranks)

# 重复名次被拒
st, d, _ = call("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (e1["id"], "华尔兹"),
                {"values": {"101": 1, "102": 1, "103": 3, "104": 4}}, cookie=jtoks["J1"])
check("重复名次被拒", st == 400, d)
# 裁判访问管理端点被拒
st, d, _ = call("GET", "/api/competition-events/%d/results" % e1["id"], cookie=jtoks["J1"])
check("裁判访问结果 API 被拒（明细权限）", st == 401)
# 未收齐的 Mark 场次不应自动计算
m1 = next(e for e in db_events if e["code"] == "M1")
call("POST", "/api/competition-events/%d/open" % m1["id"], {"roster": ["201", "202", "203", "204"]}, cookie=tok)
st, _, jt = call("POST", "/api/login", {"role": "judge", "judge_id": "J1"})
st, d, _ = call("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (m1["id"], "现代舞"),
                {"values": {"201": True, "202": True, "203": False, "204": True}}, cookie=jt)
check("Mark 制提交（未收齐不自动计算）", st == 200 and not d.get("auto_calculated"), d)

# --- 发布 E1 → 公开可见
st, d, _ = call("POST", "/api/competition-events/%d/publish" % e1["id"], {}, cookie=tok)
check("E1 发布", st == 200)
st, d, _ = call("GET", "/api/public/events/%d/results" % cid)
pub = d["results"]
check("公开端可见已发布成绩", len(pub) == 1 and pub[0]["code"] == "E1")
st, d, _ = call("POST", "/api/competition-events/%d/unpublish" % e1["id"], {}, cookie=tok)
st, d, _ = call("GET", "/api/public/events/%d/results" % cid)
check("撤回后公开端不可见", len(d["results"]) == 0)
call("POST", "/api/competition-events/%d/publish" % e1["id"], {}, cookie=tok)

# --- 晋级预案与回填
st, d, _ = call("GET", "/api/projects/W1/rounds/1/advancement-proposal?competition_id=%d" % cid, cookie=tok)
props = [x["competitor_number"] for x in d["proposal"]]
check("晋级预案 2 人", props == ["101", "102"], props)
st, d, _ = call("POST", "/api/projects/W1/rounds/1/advancement-confirm",
                {"advancing": props}, cookie=tok)
check("晋级确认回填下一轮", st == 200 and sum(len(v) for v in d["filled"].values()) == 2, d)
e2 = next(e for e in db_events if e["code"] == "E2")
st, d, _ = call("GET", "/api/public/events/%d/schedule" % cid)
check("第2轮场次存在（回填目标）", any(e["code"] == "E2" for e in d["events"]))

# --- 导出与备份
st, body, _ = call("GET", "/api/events/%d/exports?format=markdown" % cid, cookie=tok)
check("Markdown 导出", st == 200 and "W1第1轮" in body)
st, body, _ = call("GET", "/api/events/%d/exports?format=html" % cid, cookie=tok)
check("打印 HTML 导出", st == 200 and "<table>" in body)
st, d, _ = call("POST", "/api/backup", {}, cookie=tok)
check("备份", st == 200 and d.get("path"))

# ------------------------------------------------------------------ 回归：D-1~D-4
import http.client
import threading
import time as _time

# D-2 控制台未计算态不再 500
st, html, _ = call("GET", "/events/%d/console/%d" % (cid, m1["id"]), cookie=tok)
check("R-D2 控制台未计算态 200 且含占位提示", st == 200 and "尚未计算" in html, (st, str(html)[:120]))
st, html, _ = call("GET", "/events/%d/console/%d" % (cid, e1["id"]), cookie=tok)
check("R-D2 控制台已计算态 200", st == 200, st)

# D-3 明细落库并可查（顺位法 E1）
st, d, _ = call("GET", "/api/competition-events/%d/results?type=detail" % e1["id"], cookie=tok)
sd = (d.get("data") or {}).get("score_details")
first = next(iter((sd or {}).values())) if sd else {}
jd = next(iter(first.values()), {}) if first else {}
check("R-D3 detail 含打分明细（judge_placements）", st == 200 and bool(sd) and bool(jd.get("judge_placements")),
      {"st": st, "keys": list((d.get("data") or {}).keys())})
st, d, _ = call("GET", "/api/competition-events/%d/results?type=detail" % m1["id"], cookie=tok)
if st == 404:
    # M1 未收齐未计算：补齐 J2/J3 后自动计算，再验证 Mark制无明细
    _, _, jt2 = call("POST", "/api/login", {"role": "judge", "judge_id": "J2"})
    _, _, jt3 = call("POST", "/api/login", {"role": "judge", "judge_id": "J3"})
    call("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (m1["id"], "现代舞"),
         {"values": {"201": True, "202": True, "203": False, "204": False}}, cookie=jt2)
    st, d, _ = call("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (m1["id"], "现代舞"),
                    {"values": {"201": False, "202": True, "203": True, "204": True}}, cookie=jt3)
check("R-D3 Mark制明细为 null（无明细）", st == 200 and (d.get("data") or {}).get("score_details") is None, d)

# D-4 SSE 命名事件（event: 行）可达
sse_chunks = []
def read_sse():
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 8321, timeout=10)
        conn.request("GET", "/api/events/%d/stream" % cid)
        resp = conn.getresponse()
        buf = ""
        deadline = _time.time() + 6
        while _time.time() < deadline:
            chunk = resp.read1(512).decode("utf-8", "replace") if hasattr(resp, "read1") else resp.read(512).decode("utf-8", "replace")
            if not chunk:
                break
            buf += chunk
            sse_chunks.append(chunk)
            if "event: results_published" in buf:
                break
    except Exception:
        pass

th = threading.Thread(target=read_sse)
th.start()
_time.sleep(0.8)
call("POST", "/api/competition-events/%d/unpublish" % e1["id"], {}, cookie=tok)
call("POST", "/api/competition-events/%d/publish" % e1["id"], {}, cookie=tok)
th.join(timeout=10)
sse_text = "".join(sse_chunks)
check("R-D4 SSE 命名事件（event: results_published）可达前端",
      "event: results_published" in sse_text and '"type":"results_published"' in sse_text.replace(" ", ""),
      sse_text[:300])

# D-1 页面结构回归（JS 行为由 reviewer playwright 覆盖）
st, html, _ = call("GET", "/events", cookie=tok)
check("R-D1 创建按钮为 id 绑定（无内联 onclick=createEvent）",
      st == 200 and 'id="create-btn"' in html and 'onclick="createEvent()' not in html)

print("\n=== PASS %d / FAIL %d ===" % (len(PASS), len(FAIL)))
for f in FAIL:
    print("FAILED:", f)
raise SystemExit(1 if FAIL else 0)
