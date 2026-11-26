#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 发版门禁·全链路动线套件（R134 建，R150 按角色动线重组）。

对本地起的服务（临时库）走一遍完整赛事生命周期，按**角色动线**分节：
  A 筹备动线（管理员）      建赛/激活/导入/赛程/排班 + 越权与坏输入拒绝
  B 检录·主持动线           host/marshal 登录、staff 台、外项背号开赛拒绝、批量检录
  C 裁判动线（J1–J3）       裁判登录、 assignments、Mark 未收齐不自动算分、收齐即算
  D 发布动线（管理员）      发布/撤回可见性、控制台、明细权限口径、导出
  E 晋级动线                分场互斥/回填/多分场 lookup、复赛→顺位决赛、重复名次拒绝
  F 公众动线                团体总分独立复算对拍、公开 API、前端页面、SSE 具名事件
  G 打印·证书动线（printer）打印台、合并打印视图、证书设计+生成（真实 PDF 管线）
  H 恢复·体检               return-scores 演练、doctor 不变量、reset-scoring 加固

场景骨架（同 R134）：三场 Mark 预赛（两分组分场）→ 晋级确认（单场蛇形+互斥拒绝）
→ 复赛两场 → 顺位决赛 + 单项顺位决赛 → 团体总分对拍。全程标准库；
预期失败用例（400/409/403）逐一断言——comp21 事故回归用例全部保留。

环境变量：CI_BASE（默认 http://127.0.0.1:8399）、CI_DB（临时库路径，用于 judges_assigned 排班）。
退出码：0=全部通过；1=有失败（失败清单打印到最后）。
"""
import csv
import http.client
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import urllib.parse

BASE = os.environ.get("CI_BASE", "http://127.0.0.1:8399")
DB = os.environ.get("CI_DB", "")
POINTS = {1: 9, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
COMP_NAME = "CI冒烟赛"
RESULTS = []   # (ok, section, tag, msg)
SECTION = ["—"]


def check(ok, tag, msg=""):
    RESULTS.append((bool(ok), SECTION[0], tag, str(msg)[:160]))
    print(("PASS " if ok else "FAIL ") + tag + (" | " + str(msg)[:160] if msg else ""), flush=True)
    return ok


class Client:
    """带 cookie 的极简 HTTP 客户端（urllib）。"""

    def __init__(self):
        self.cookie = ""

    def req(self, method, path, body=None, raw=None, ctype="application/json", expect=None):
        url = BASE + path
        data = None
        if raw is not None:
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
        r = urllib.request.Request(url, data=data, method=method)
        r.add_header("Content-Type", ctype)
        if self.cookie:
            r.add_header("Cookie", self.cookie)
        try:
            resp = urllib.request.urlopen(r, timeout=20)
            payload = resp.read()
            status = resp.status
            setc = resp.headers.get("Set-Cookie") or ""
        except urllib.error.HTTPError as e:
            payload = e.read()
            status = e.code
            setc = e.headers.get("Set-Cookie") or ""
        if setc:
            for part in setc.split(","):
                p = part.strip()
                if p.startswith("session="):
                    self.cookie = p.split(";")[0]
        if expect is not None and status != expect:
            raise AssertionError("%s %s → %s（预期 %s）: %s" % (method, path, status, expect, payload[:200].decode("utf-8", "replace")))
        try:
            return status, json.loads(payload.decode("utf-8"))
        except Exception:
            return status, payload.decode("utf-8", "replace")


def csv_body(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def wait_status(c, ceid, want, timeout=15):
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        st, d = c.req("GET", "/api/competition-events/%d/progress" % ceid)
        last = d.get("status", "")
        if last in want:
            return last
        time.sleep(0.5)
    return last


def run_round(c, ceid, dance, judges, marks=None, placements=None):
    """全检录 → 逐裁判提交 → 等待收齐自动算分 → 发布（开赛由调用方完成）。

    第一位裁判提交后额外断言「未收齐不自动算分」（C 动线回归点）。"""
    st, d = c.req("GET", "/api/competition-events/%d/progress" % ceid)
    nums = d["roster"]
    c.req("POST", "/api/competition-events/%d/checkin" % ceid, body={"numbers": nums, "state": True}, expect=200)
    for i, j in enumerate(judges):
        jc = Client()
        jc.cookie = judge_cookies[j]
        body = {"values": (marks if marks is not None else placements)}
        st2, d2 = jc.req("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (ceid, urllib.parse.quote(dance)),
                         body=body, expect=200)
        if i == 0 and len(judges) > 1:
            got = wait_status(c, ceid, ("scoring",), timeout=2)
            check(got == "scoring", "%d 首裁提交未收齐不自动算分" % ceid, "status=%s auto=%s" % (got, d2.get("auto_calculated")))
        elif i == len(judges) - 1:
            check(d2.get("auto_calculated") is True, "%d 末裁提交触发自动算分" % ceid, d2)
    got = wait_status(c, ceid, ("calculated", "published"))
    if not check(got in ("calculated", "published"), "%d 收齐自动算分落位" % ceid, "status=%s" % got):
        return False
    c.req("POST", "/api/competition-events/%d/publish" % ceid, body={}, expect=200)
    return True


judge_cookies = {}   # J1/J2/J3 → "session=…"（C 动线真实登录取得）


def sec_a_setup(c):
    """A 筹备动线：越权拒绝 → 建赛 → 导入 → 赛程结构 → 排班。"""
    st, _ = c.req("POST", "/api/login", body={"role": "admin", "password": "wrong"})
    check(st == 403, "A·错误口令被拒 403")
    st, _ = c.req("POST", "/api/login", body={"role": "judge", "judge_id": "JX"})
    check(st == 403, "A·非法裁判 ID 被拒 403")
    st, _ = c.req("GET", "/api/events")
    check(st == 401, "A·未登录访问管理 API 401")

    st, d = c.req("POST", "/api/login", body={"role": "admin", "password": "admin123"}, expect=200)
    check(True, "A·管理员登录")
    st, d = c.req("POST", "/api/events", body={"name": COMP_NAME, "date": "2026-01-01", "location": "CI"}, expect=200)
    cid = d["id"]
    c.req("POST", "/api/events/%d/activate" % cid, body={}, expect=200)
    check(True, "A·建赛+激活 cid=%d" % cid)

    st, d = c.req("POST", "/api/events/%d/imports/competitors" % cid, raw="背面番,x\n1,y\n", ctype="text/csv")
    check(st == 400, "A·坏 CSV（非法列）被拒 400", d if isinstance(d, str) else d.get("detail", ""))

    comp_csv = csv_body(["背番号", "姓名", "学校/单位", "项目编号"],
                        [["205", "外项测试员", "外院", "P03"]])
    c.req("POST", "/api/events/%d/imports/competitors" % cid, raw=comp_csv, ctype="text/csv", expect=200)
    judges_csv = csv_body(["裁判ID", "姓名"], [["J1", "裁判一"], ["J2", "裁判二"], ["J3", "裁判三"]])
    c.req("POST", "/api/events/%d/imports/judges" % cid, raw=judges_csv, ctype="text/csv", expect=200)
    check(True, "A·选手/裁判导入（含外项 205）")

    units = {101: "甲院", 102: "甲院", 103: "乙院", 104: "乙院", 105: "丙院", 106: "丙院",
             107: "甲院", 108: "甲院", 109: "乙院", 110: "乙院", 111: "丙院", 112: "丙院",
             201: "A院", 202: "A院", 203: "B院", 204: "C院"}
    # R1 预赛与单项决赛走 schedule-full（带名单导入）；空名单的晋级轮走 schedule/add
    # （schedule-full 会跳过无背号行）
    rows = []

    def add(seq, code, name, rnd, typ, adv, tmode, nums):
        for n in nums:
            rows.append([seq, code, name, rnd, n, "选手%d" % n, units.get(int(n), "丁院"), "",
                         "", "", "", typ, adv, tmode, ""])

    add(1, "P01Z01", "平四 Z01组 初赛A", 1, "Mark制", 4, "standard", [101, 102, 103, 104, 105, 106])
    add(2, "P01Z01", "平四 Z01组 初赛B", 1, "Mark制", 4, "standard", [107, 108, 109, 110, 111, 112])
    add(6, "P02", "华尔兹单项 决赛", 1, "顺位法", 8, "standard", [201, 202, 203, 204])
    sched_csv = csv_body(["场次", "项目序号", "项目名称", "轮次", "背番号", "选手姓名", "选手单位",
                          "选手身份", "搭档姓名", "搭档单位", "搭档身份", "评分类型", "晋级人数", "团体计分", "时间"], rows)
    st, d = c.req("POST", "/api/events/%d/imports/schedule-full" % cid, raw=sched_csv, ctype="text/csv", expect=200)
    check(d.get("ok"), "A·schedule-full 导入 3 场")
    for seq, code, name, rnd, typ, adv in ((3, "P01Z01-R2A", "平四 Z01组 复赛A", 2, "MARK", 2),
                                           (4, "P01Z01-R2B", "平四 Z01组 复赛B", 2, "MARK", 2),
                                           (5, "P01Z01-R3", "平四 Z01组 决赛", 3, "SKATING", 8)):
        c.req("POST", "/api/events/%d/schedule/add" % cid,
              body={"code": code, "name": name, "project": "P01Z01", "round": rnd,
                    "dances": "平四", "type": typ, "adv": adv}, expect=200)
    check(True, "A·schedule/add 补 3 个晋级轮场次")

    st, d = c.req("GET", "/api/events/%d/runboard" % cid)
    all_evs = {e["code"]: e["id"] for e in d["events"]}
    # schedule-full 生成码带轮次后缀（如 P01Z01-R1A-R1）——按前缀映射
    evs = {}
    for want in ("P01Z01-R1A", "P01Z01-R1B", "P01Z01-R2A", "P01Z01-R2B", "P01Z01-R3", "P02-R1"):
        match = [k for k in all_evs if k == want or k.startswith(want + "-")]
        evs[want] = all_evs[match[0]] if match else None
    check(all(evs.values()), "A·六场结构齐备", sorted(all_evs)[:10])
    # 裁判排班（events.judges_assigned）——用赛事编辑接口不可行（仅 pending 字段集），直接 SQL
    conn = sqlite3.connect(DB, timeout=15)
    conn.execute("UPDATE events SET judges_assigned='J1,J2,J3' WHERE competition_id=?", (cid,))
    conn.commit()
    conn.close()
    check(True, "A·裁判排班 J1-J3")

    st, body = c.req("GET", "/events")
    check(st == 200 and 'id="create-btn"' in (body if isinstance(body, str) else "")
          and 'onclick="createEvent()' not in (body if isinstance(body, str) else ""),
          "A·/events 创建按钮 id 绑定（D-1 回归）")
    return cid, evs, units


def sec_b_staff(c, cid, evs):
    """B 检录·主持动线：默认账号登录、staff 台、外项背号拒绝、批量检录。
    host/marshal 用独立会话；c 保持管理员会话供后续动线使用。"""
    host = Client()
    st, d = host.req("POST", "/api/login", body={"role": "host", "username": "host", "password": "host123",
                                                 "competition_id": cid}, expect=200)
    check(True, "B·主持人登录（host/host123）")
    st, body = host.req("GET", "/staff")
    check(st == 200 and "场次流程" in (body if isinstance(body, str) else ""), "B·主持台 /staff 200")

    marshal = Client()
    st, d = marshal.req("POST", "/api/login", body={"role": "marshal", "username": "marshal", "password": "marshal123",
                                                    "competition_id": cid}, expect=200)
    check(True, "B·检录长登录（marshal/marshal123）")

    r1a = evs["P01Z01-R1A"]
    st, d = host.req("POST", "/api/competition-events/%d/open" % r1a,
                     body={"roster": ["101", "102", "103", "104", "105", "205"]})
    check(st == 400, "B·开赛拒绝外项背号(205) → 400", d if isinstance(d, str) else d.get("detail", ""))

    st, d = marshal.req("POST", "/api/competition-events/%d/checkin" % r1a,
                        body={"numbers": ["101", "102"], "state": True}, expect=200)
    check(d.get("updated") == 2, "B·检录员批量检录 2 对")
    st, d = c.req("GET", "/api/competition-events/%d/checkin" % r1a)
    check(d.get("checked_n") == 2, "B·检录状态快照 checked_n=2")

    st, d = host.req("POST", "/api/competition-events/%d/open" % r1a,
                     body={"roster": ["101", "102", "103", "104", "105", "106"]}, expect=200)
    check(True, "B·主持人开赛 R1A（6 对）")
    return {"host": host.cookie, "marshal": marshal.cookie}


def sec_c_judges(c, cid, evs):
    """C 裁判动线：真实登录、assignments、Mark 未收齐不自动算分 → 收齐即算（R1A/R1B）。"""
    for j in ("J1", "J2", "J3"):
        jc = Client()
        st, _ = jc.req("POST", "/api/login", body={"role": "judge", "judge_id": j}, expect=200)
        judge_cookies[j] = jc.cookie
        check(st == 200, "C·裁判 %s 登录（免口令）" % j)
    jc = Client()
    jc.cookie = judge_cookies["J1"]
    st, d = jc.req("GET", "/api/judge/me/assignments")
    codes = {a["event"]["code"] for a in d.get("assignments", [])}
    check(any(k.startswith("P01Z01-R1A") for k in codes), "C·assignments 含 R1A", sorted(codes)[:6])
    st, _ = jc.req("GET", "/api/competition-events/%d/results" % evs["P01Z01-R1A"])
    check(st == 401, "C·裁判访问结果 API 401（明细权限）")

    r1a = evs["P01Z01-R1A"]
    run_round(c, r1a, "平四", ["J1", "J2", "J3"], marks={"101": True, "102": True, "103": True, "104": True})
    r1b = evs["P01Z01-R1B"]
    c.req("POST", "/api/competition-events/%d/open" % r1b, body={"roster": ["107", "108", "109", "110", "111", "112"]}, expect=200)
    run_round(c, r1b, "平四", ["J1", "J2", "J3"], marks={"107": True, "108": True, "109": True, "110": True})


def sec_d_publish(c, cid, evs):
    """D 发布动线：发布可见性、控制台、明细口径、导出。"""
    r1a, r1b = evs["P01Z01-R1A"], evs["P01Z01-R1B"]
    st, d = c.req("POST", "/api/competition-events/%d/unpublish" % r1a, body={}, expect=200)
    st, d = c.req("GET", "/api/public/events/%d/results" % cid)
    check(len(d.get("results", [])) == 1 and d["results"][0]["code"].startswith("P01Z01-R1B"),
          "D·撤回 R1A 后公开端只剩 R1B", [r["code"] for r in d.get("results", [])])
    c.req("POST", "/api/competition-events/%d/publish" % r1a, body={}, expect=200)
    st, d = c.req("GET", "/api/public/events/%d/results" % cid)
    check(len(d.get("results", [])) == 2, "D·重新发布后公开端 2 场")

    st, body = c.req("GET", "/events/%d/console/%d" % (cid, r1b))
    check(st == 200 and "尚未计算" not in (body if isinstance(body, str) else ""),
          "D·控制台已计算态 200")
    st, d = c.req("GET", "/api/competition-events/%d/results?type=detail" % r1a)
    check(st == 200 and (d.get("data") or {}).get("score_details") is None,
          "D·Mark 制明细为 null（无打分明细，D-3 回归）")
    st, body = c.req("GET", "/api/events/%d/exports?format=markdown" % cid)
    check(st == 200 and "平四" in (body if isinstance(body, str) else ""), "D·Markdown 成绩导出")
    st, body = c.req("GET", "/api/events/%d/exports?format=html" % cid)
    check(st == 200 and "<table>" in (body if isinstance(body, str) else ""), "D·打印 HTML 导出")


def sec_e_advancement(c, cid, evs, units):
    """E 晋级动线：互斥/回填/lookup → 复赛推进 → 顺位决赛（重复名次拒绝）→ 单项决赛。"""
    r2a, r2b = evs["P01Z01-R2A"], evs["P01Z01-R2B"]
    st, d = c.req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
                  body={"assign": {"P01Z01-R2A": ["105"], "P01Z01-R2B": ["105"]}, "append": True,
                        "competition_id": cid})
    check(st == 400, "E·同请求跨分场重复 → 400", d if isinstance(d, str) else d.get("detail", ""))
    st, d = c.req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
                  body={"assign": {"P01Z01-R2A": ["101", "102", "103", "104"]}, "append": True,
                        "competition_id": cid}, expect=200)
    check(d.get("filled", {}).get("P01Z01-R2A") == ["101", "102", "103", "104"], "E·R1A 晋级回填 R2A 4 对")
    st, d = c.req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
                  body={"assign": {"P01Z01-R2B": ["101"]}, "append": True, "competition_id": cid})
    check(st == 400, "E·与既有分场冲突(101 已在 R2A) → 400", d if isinstance(d, str) else d.get("detail", ""))
    c.req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
          body={"assign": {"P01Z01-R2B": ["107", "108", "109", "110"]}, "append": True,
                "competition_id": cid}, expect=200)
    st, da = c.req("GET", "/api/competition-events/%d/progress" % r2a)
    st, db_ = c.req("GET", "/api/competition-events/%d/progress" % r2b)
    inter = set(da["roster"]) & set(db_["roster"])
    check(not inter, "E·R2A/R2B 分场互斥", "交集=%s" % sorted(inter))

    # 多分场成绩查询晋级判定（802 案例回归）
    st, d = c.req("GET", "/api/public/events/%d/lookup?num=107" % cid)
    r1b_row = next((r for r in d.get("schedule", []) if r["code"].startswith("P01Z01-R1B")), {})
    check(r1b_row.get("advancement") is True, "E·lookup: R2B 侧选手显示已晋级（fetchone 回归）",
          "adv=%s" % r1b_row.get("advancement"))
    st, d = c.req("GET", "/api/public/events/%d/lookup?num=105" % cid)
    r1a_row = next((r for r in d.get("schedule", []) if r["code"].startswith("P01Z01-R1A")), {})
    check(r1a_row.get("advancement") is False, "E·lookup: 未晋级者显示未晋级", "adv=%s" % r1a_row.get("advancement"))

    # 复赛两场 → 半决赛（顺位法）→ 单项决赛
    c.req("POST", "/api/competition-events/%d/open" % r2a, body={"roster": ["101", "102", "103", "104"]}, expect=200)
    run_round(c, r2a, "平四", ["J1", "J2", "J3"], marks={"101": True, "102": True})
    c.req("POST", "/api/competition-events/%d/open" % r2b, body={"roster": ["107", "108", "109", "110"]}, expect=200)
    run_round(c, r2b, "平四", ["J1", "J2", "J3"], marks={"107": True, "108": True})
    c.req("POST", "/api/projects/P01Z01/rounds/2/advancement-confirm",
          body={"assign": {"P01Z01-R3": ["101", "102", "107", "108"]}, "append": True,
                "competition_id": cid}, expect=200)
    r3 = evs["P01Z01-R3"]
    c.req("POST", "/api/competition-events/%d/open" % r3,
          body={"roster": ["101", "102", "107", "108"]}, expect=200)
    # 重复名次被拒（顺位法服务端校验）
    jdup = Client()
    jdup.cookie = judge_cookies["J1"]
    st, d = jdup.req("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (r3, urllib.parse.quote("平四")),
                     body={"values": {"101": "1", "102": "1", "107": "3", "108": "4"}})
    check(st == 400, "E·顺位法重复名次 → 400", d if isinstance(d, str) else d.get("detail", ""))
    run_round(c, r3, "平四", ["J1", "J2", "J3"],
              placements={"101": "1", "107": "2", "102": "3", "108": "4"})
    p2 = evs["P02-R1"]
    c.req("POST", "/api/competition-events/%d/open" % p2, body={"roster": ["201", "202", "203", "204"]}, expect=200)
    run_round(c, p2, "华尔兹", ["J1", "J2", "J3"],
              placements={"201": "1", "202": "2", "203": "3", "204": "4"})

    # 顺位法明细含裁判名次（D-3 回归，需要已计算的 SKATING 场）
    st, d = c.req("GET", "/api/competition-events/%d/results?type=detail" % r3)
    sd = (d.get("data") or {}).get("score_details") or {}
    first = next(iter(sd.values()), {})
    jd = next(iter(first.values()), {}) if first else {}
    check(st == 200 and bool(jd.get("judge_placements")), "E·顺位法明细含 judge_placements（D-3 回归）",
          {"keys": list(sd.keys())[:3]})
    return r3, p2


def sec_f_public(c, cid, evs, units):
    """F 公众动线：团体总分对拍、公开 API、前端页面、SSE 具名事件。"""
    expect = {}
    for num, rank, unit in ((101, 1, units[101]), (107, 2, units[107]), (102, 3, units[102]),
                            (108, 4, units[108]), (201, 1, units[201]), (202, 2, units[202]),
                            (203, 3, units[203]), (204, 4, units[204])):
        expect[unit] = expect.get(unit, 0) + POINTS[rank]
    st, d = c.req("GET", "/api/public/events/%d/team-standings" % cid)
    got = {s["unit"]: s["total"] for s in d["standings"]}
    check(got == expect, "F·公开团体总分 == 独立复算", "got=%s expect=%s" % (got, expect))
    st, html = c.req("GET", "/events/%d/team-standings" % cid)
    admin_totals = {}
    if st == 200 and isinstance(html, str):
        for m in re.finditer(r"<td>([^<]+)</td><td class=\"num\">([\d.]+)</td>", html):
            admin_totals[m.group(1)] = float(m.group(2))
    check(admin_totals == {u: float(t) for u, t in expect.items()},
          "F·管理榜 == 公开榜（单一来源回归）", "admin=%s" % admin_totals)

    for path, marker in (("/competitions/%d" % cid, COMP_NAME),
                         ("/events/%d/results" % cid, COMP_NAME),
                         ("/events/%d/team-standings" % cid, "团体总分榜"),
                         ("/events/%d/advancement?project=P01Z01&round=1" % cid, "晋级")):
        st, body = c.req("GET", path)
        check(st == 200 and marker in (body if isinstance(body, str) else ""), "F·页面 %s" % path, "marker=%s" % marker)
    st, d = c.req("GET", "/api/public/events/%d/schedule" % cid)
    check(st == 200 and isinstance(d, dict) and d.get("competition"), "F·公开赛程 API")
    st, d = c.req("GET", "/api/public/events/%d/screen-state" % cid)
    check(st == 200 and isinstance(d, dict) and (d.get("published_results") or []),
          "F·大屏 screen-state API（含已发布成绩）")

    # SSE 具名事件可达前端（D-4 回归）：连接 stream 后触发 publish
    p2 = evs["P02-R1"]
    chunks = []

    def read_sse():
        try:
            u = urllib.parse.urlsplit(BASE)
            conn = http.client.HTTPConnection(u.hostname or "127.0.0.1", u.port or 80, timeout=10)
            conn.request("GET", "/api/events/%d/stream" % cid)
            resp = conn.getresponse()
            buf = ""
            deadline = time.time() + 6
            while time.time() < deadline:
                chunk = resp.read1(512).decode("utf-8", "replace") if hasattr(resp, "read1") else resp.read(512).decode("utf-8", "replace")
                if not chunk:
                    break
                buf += chunk
                chunks.append(chunk)
                if "event: results_published" in buf:
                    break
        except Exception:
            pass

    th = threading.Thread(target=read_sse)
    th.start()
    time.sleep(0.8)
    c.req("POST", "/api/competition-events/%d/unpublish" % p2, body={}, expect=200)
    c.req("POST", "/api/competition-events/%d/publish" % p2, body={}, expect=200)
    th.join(timeout=10)
    sse_text = "".join(chunks)
    check("event: results_published" in sse_text and '"type":"results_published"' in sse_text.replace(" ", ""),
          "F·SSE 具名事件 results_published 可达（D-4 回归）", sse_text[:200])


def sec_g_print(c, cid, evs):
    """G 打印·证书动线：printer 账号（管理员创建）→ 打印台 → 合并打印视图 → 证书生成。"""
    st, d = c.req("POST", "/api/users", body={"username": "ci-printer", "password": "print123",
                                              "role": "printer", "display_name": "CI打印员"})
    if st == 200:
        check(True, "G·管理员创建 printer 账号")
    else:
        check(st == 400, "G·printer 账号已存在（可重复执行）", d)
    pc = Client()
    st, _ = pc.req("POST", "/api/login", body={"role": "printer", "username": "ci-printer",
                                               "password": "print123", "competition_id": cid}, expect=200)
    check(True, "G·printer 登录")
    st, body = pc.req("GET", "/print")
    check(st == 200 and "合并打印所选结果表" in (body if isinstance(body, str) else ""), "G·打印台紧凑表 200")

    r3, p2 = evs["P01Z01-R3"], evs["P02-R1"]
    st, body = pc.req("GET", "/events/%d/print/view/%d" % (cid, p2))
    check(st == 200 and "<table>" in (body if isinstance(body, str) else ""), "G·单场公示表打印视图 200")
    st, body = pc.req("GET", "/events/%d/print/view?ids=%d,%d" % (cid, r3, p2))
    n_sec = (body if isinstance(body, str) else "").count('class="pv-sec"')
    check(st == 200 and n_sec == 2, "G·合并打印视图 2 节（ids=）", "pv-sec=%d" % n_sec)

    # 证书：设计（预设字段）→ generate-v2 真实 PDF 管线
    fields = [
        {"type": "name", "x": 40, "y": 54, "w": 30, "size": 18, "align": "center", "bold": True, "text": ""},
        {"type": "rank_cn", "x": 40, "y": 64, "w": 30, "size": 16, "align": "center", "bold": False, "text": ""},
        {"type": "date", "x": 40, "y": 74, "w": 30, "size": 12, "align": "center", "bold": False, "text": ""},
    ]
    st, d = c.req("POST", "/api/events/%d/certs/designs" % cid,
                  body={"id": 0, "name": "CI证书设计", "bg_type": "none", "fields": fields}, expect=200)
    design_id = d.get("id")
    check(bool(design_id), "G·证书设计创建")
    st, body = c.req("POST", "/api/events/%d/certs/%d/generate-v2" % (cid, p2),
                     body={"design_id": design_id})
    ok = st == 200 and isinstance(body, str) and body.lstrip().startswith("%PDF")
    check(ok, "G·generate-v2 证书 PDF 生成", {"st": st, "head": str(body)[:20]})


def sec_h_recover(c, cid, evs):
    """H 恢复·体检：doctor 不变量 → return-scores 演练 → reset-scoring 加固。"""
    env = dict(os.environ, CI_BASE=BASE, CI_ADMIN_COOKIE=c.cookie, CI_COMP=str(cid))
    p = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "doctor.py")],
                       env=env, capture_output=True, text=True, timeout=60)
    check(p.returncode == 0, "H·doctor 不变量体检", (p.stdout + p.stderr)[-300:])

    # return-scores 演练：P02-R1 已发布 → 退回评分 → 重新提交 → 自动重算 → 再发布
    p2 = evs["P02-R1"]
    c.req("POST", "/api/competition-events/%d/return-scores" % p2, body={}, expect=200)
    st, d = c.req("GET", "/api/competition-events/%d/progress" % p2)
    check(d.get("status") == "scoring", "H·退回评分 → 回到评分中")
    run_round(c, p2, "华尔兹", ["J1", "J2", "J3"],
              placements={"201": "1", "202": "2", "203": "3", "204": "4"})
    st, d = c.req("GET", "/api/public/events/%d/screen-state" % cid)
    check(any(r["id"] == p2 for r in d.get("published_results", [])), "H·重算后重新发布可见")

    st, d = c.req("POST", "/api/events/%d/reset-scoring" % cid, body={})
    check(st == 400, "H·reset 无确认 → 400", d if isinstance(d, str) else d.get("detail", ""))
    st, d = c.req("POST", "/api/events/%d/reset-scoring" % cid, body={"confirm": "错误的赛事名"})
    check(st == 400, "H·reset 赛事名不符 → 400", d if isinstance(d, str) else d.get("detail", ""))
    st, d = c.req("POST", "/api/events/%d/reset-scoring" % cid, body={"confirm": COMP_NAME}, expect=200)
    check(d.get("events_reset", 0) > 0, "H·reset 赛事名匹配 → 200")


def main():
    c = Client()
    ctx = {}   # 动线间共享：cid / evs / units / staff cookies…

    def run(key, title, fn):
        SECTION[0] = key
        print("\n──── 动线 %s：%s ────" % (key, title), flush=True)
        try:
            fn()
        except AssertionError as e:
            check(False, "%s·动线中断（预期状态码未满足）" % key, str(e))

    run("A", "筹备动线（管理员）", lambda: ctx.update(
        dict(zip(("cid", "evs", "units"), sec_a_setup(c)))))
    run("B", "检录·主持动线", lambda: ctx.update(
        staff=sec_b_staff(c, ctx["cid"], ctx["evs"])))
    run("C", "裁判动线（J1–J3）", lambda: sec_c_judges(c, ctx["cid"], ctx["evs"]))
    run("D", "发布动线（管理员）", lambda: sec_d_publish(c, ctx["cid"], ctx["evs"]))
    run("E", "晋级动线", lambda: ctx.update(
        finals=sec_e_advancement(c, ctx["cid"], ctx["evs"], ctx["units"])))
    run("F", "公众动线", lambda: sec_f_public(c, ctx["cid"], ctx["evs"], ctx["units"]))
    run("G", "打印·证书动线（printer）", lambda: sec_g_print(c, ctx["cid"], ctx["evs"]))
    run("H", "恢复·体检", lambda: sec_h_recover(c, ctx["cid"], ctx["evs"]))
    failed = [r for r in RESULTS if not r[0]]
    print("\n==== CI 动线套件汇总：%d 通过 / %d 失败 ====" % (len(RESULTS) - len(failed), len(failed)))
    cur = None
    for _, sec, tag, msg in failed:
        if sec != cur:
            print("  【动线 %s】" % sec)
            cur = sec
        print("  ✗ %s | %s" % (tag, msg))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
