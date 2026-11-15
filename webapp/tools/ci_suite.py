#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 全链路套件（R134）：对本地起的服务（临时库）跑核心后端接口 + 前端响应断言。

场景：三场 Mark 预赛（两个分组分场）→ 晋级确认（单场蛇形 + 互斥拒绝）→ 复赛两场 → 半决赛
顺位决赛 + 单项顺位决赛 → 团体总分独立复算对拍 → 成绩查询多分场晋级 → reset_scoring 加固。
全程只依赖标准库；预期失败用例（400/409）逐一断言——回归 comp21 事故的五项修复。

环境变量：CI_BASE（默认 http://127.0.0.1:8399）、CI_DB（临时库路径，用于预置裁判会话）。
退出码：0=全部通过；1=有失败（失败清单打印到最后）。
"""
import csv
import io
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

BASE = os.environ.get("CI_BASE", "http://127.0.0.1:8399")
DB = os.environ.get("CI_DB", "")
POINTS = {1: 9, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
COMP_NAME = "CI冒烟赛"
RESULTS = []   # (ok, tag, msg)


def check(ok, tag, msg=""):
    RESULTS.append((bool(ok), tag, str(msg)[:160]))
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


def seed_judge_sessions():
    """裁判会话无法走登录（裁判无账号）——直接向临时库预置 sessions 行（与 smoke 同法）。"""
    conn = sqlite3.connect(DB, timeout=15)
    for i in (1, 2, 3):
        conn.execute("INSERT OR REPLACE INTO sessions(token, role, judge_code, comp_id) VALUES(?,?,?,1)",
                     ("ci-j%d" % i, "judge", "J%d" % i))
    conn.commit()
    conn.close()


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
    """全检录 → 逐裁判提交 → 等待收齐自动算分 → 发布（开赛由调用方完成）。"""
    st, d = c.req("GET", "/api/competition-events/%d/progress" % ceid)
    nums = d["roster"]
    c.req("POST", "/api/competition-events/%d/checkin" % ceid, body={"numbers": nums, "state": True}, expect=200)
    for j in judges:
        jc = Client()
        jc.cookie = "session=ci-" + j.lower()
        body = {"values": (marks if marks is not None else placements)}
        jc.req("PUT", "/api/judge/competition-events/%d/dances/%s/sheet" % (ceid, urllib.parse.quote(dance)),
               body=body, expect=200)
    got = wait_status(c, ceid, ("calculated", "published"))
    if not check(got in ("calculated", "published"), "event-%d 收齐自动算分" % ceid, "status=%s" % got):
        return False
    c.req("POST", "/api/competition-events/%d/publish" % ceid, body={}, expect=200)
    return True


def main():
    seed_judge_sessions()
    ok_all = True
    c = Client()

    # ---------- 0) 管理员登录 + 建赛 ----------
    st, d = c.req("POST", "/api/login", body={"role": "admin", "password": "admin123"}, expect=200)
    check(True, "管理员登录")
    st, d = c.req("POST", "/api/events", body={"name": COMP_NAME, "date": "2026-01-01", "location": "CI"}, expect=200)
    cid = d["id"]
    c.req("POST", "/api/events/%d/activate" % cid, body={}, expect=200)
    check(True, "建赛+激活 cid=%d" % cid)

    # ---------- 1) 报名/裁判/赛程导入（真实导入接口） ----------
    comp_csv = csv_body(["背番号", "姓名", "学校/单位", "项目编号"],
                        [["205", "外项测试员", "外院", "P03"]])
    c.req("POST", "/api/events/%d/imports/competitors" % cid, raw=comp_csv, ctype="text/csv", expect=200)
    judges_csv = csv_body(["裁判ID", "姓名"], [["J1", "裁判一"], ["J2", "裁判二"], ["J3", "裁判三"]])
    c.req("POST", "/api/events/%d/imports/judges" % cid, raw=judges_csv, ctype="text/csv", expect=200)

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
    check(d.get("ok"), "schedule-full 导入 3 场")
    for seq, code, name, rnd, typ, adv in ((3, "P01Z01-R2A", "平四 Z01组 复赛A", 2, "MARK", 2),
                                           (4, "P01Z01-R2B", "平四 Z01组 复赛B", 2, "MARK", 2),
                                           (5, "P01Z01-R3", "平四 Z01组 决赛", 3, "SKATING", 8)):
        st, d = c.req("POST", "/api/events/%d/schedule/add" % cid,
                      body={"code": code, "name": name, "project": "P01Z01", "round": rnd,
                            "dances": "平四", "type": typ, "adv": adv}, expect=200)

    st, d = c.req("GET", "/api/events/%d/runboard" % cid)
    all_evs = {e["code"]: e["id"] for e in d["events"]}
    # schedule-full 生成码带轮次后缀（如 P01Z01-R1A-R1）——按前缀映射
    evs = {}
    for want in ("P01Z01-R1A", "P01Z01-R1B", "P01Z01-R2A", "P01Z01-R2B", "P01Z01-R3", "P02-R1"):
        match = [k for k in all_evs if k == want or k.startswith(want + "-")]
        evs[want] = all_evs[match[0]] if match else None
    check(all(evs.values()), "六场结构齐备", sorted(all_evs)[:10])
    # 裁判排班（events.judges_assigned）——用赛事编辑接口不可行（仅 pending 字段集），直接 SQL
    conn = sqlite3.connect(DB, timeout=15)
    conn.execute("UPDATE events SET judges_assigned='J1,J2,J3' WHERE competition_id=?", (cid,))
    conn.commit()
    conn.close()

    # ---------- 2) 开赛名单项目归属校验（comp21 事故回归） ----------
    r1a = evs["P01Z01-R1A"]
    st, d = c.req("POST", "/api/competition-events/%d/open" % r1a,
                  body={"roster": ["101", "102", "103", "104", "105", "205"]})
    check(st == 400, "开赛拒绝外项背号(205) → 400", d if isinstance(d, str) else d.get("detail", ""))
    st, d = c.req("POST", "/api/competition-events/%d/open" % r1a,
                  body={"roster": ["101", "102", "103", "104", "105", "106"]}, expect=200)
    check(True, "R1A 正常开赛（6 对）")

    # ---------- 3) Mark 三裁 → 收齐 → 发布（R1A/R1B） ----------
    run_round(c, r1a, "平四", ["J1", "J2", "J3"], marks={"101": True, "102": True, "103": True, "104": True})
    r1b = evs["P01Z01-R1B"]
    c.req("POST", "/api/competition-events/%d/open" % r1b, body={"roster": ["107", "108", "109", "110", "111", "112"]}, expect=200)
    run_round(c, r1b, "平四", ["J1", "J2", "J3"], marks={"107": True, "108": True, "109": True, "110": True})

    # ---------- 4) 晋级确认：单场蛇形 + 互斥拒绝（comp21 事故回归） ----------
    r2a, r2b = evs["P01Z01-R2A"], evs["P01Z01-R2B"]
    st, d = c.req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
                  body={"assign": {"P01Z01-R2A": ["105"], "P01Z01-R2B": ["105"]}, "append": True,
                        "competition_id": cid})
    check(st == 400, "同请求跨分场重复 → 400", d if isinstance(d, str) else d.get("detail", ""))
    st, d = c.req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
                  body={"assign": {"P01Z01-R2A": ["101", "102", "103", "104"]}, "append": True,
                        "competition_id": cid}, expect=200)
    check(d.get("filled", {}).get("P01Z01-R2A") == ["101", "102", "103", "104"], "R1A 晋级回填 R2A 4 对")
    st, d = c.req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
                  body={"assign": {"P01Z01-R2B": ["101"]}, "append": True, "competition_id": cid})
    check(st == 400, "与既有分场冲突(101 已在 R2A) → 400", d if isinstance(d, str) else d.get("detail", ""))
    c.req("POST", "/api/projects/P01Z01/rounds/1/advancement-confirm",
          body={"assign": {"P01Z01-R2B": ["107", "108", "109", "110"]}, "append": True,
                "competition_id": cid}, expect=200)
    st, da = c.req("GET", "/api/competition-events/%d/progress" % r2a)
    st, db_ = c.req("GET", "/api/competition-events/%d/progress" % r2b)
    inter = set(da["roster"]) & set(db_["roster"])
    check(not inter, "R2A/R2B 分场互斥", "交集=%s" % sorted(inter))

    # ---------- 5) 多分场成绩查询晋级判定（802 案例回归） ----------
    st, d = c.req("GET", "/api/public/events/%d/lookup?num=107" % cid)
    r1b_row = next((r for r in d.get("schedule", []) if r["code"].startswith("P01Z01-R1B")), {})
    check(r1b_row.get("advancement") is True, "lookup: R2B 侧选手显示已晋级（多分场 fetchone 回归）",
          "adv=%s" % r1b_row.get("advancement"))
    st, d = c.req("GET", "/api/public/events/%d/lookup?num=105" % cid)
    r1a_row = next((r for r in d.get("schedule", []) if r["code"].startswith("P01Z01-R1A")), {})
    check(r1a_row.get("advancement") is False, "lookup: 未晋级者显示未晋级", "adv=%s" % r1a_row.get("advancement"))

    # ---------- 6) 复赛两场 + 半决赛（顺位法决赛）+ 单项决赛 ----------
    c.req("POST", "/api/competition-events/%d/open" % r2a, body={"roster": ["101", "102", "103", "104"]}, expect=200)
    run_round(c, r2a, "平四", ["J1", "J2", "J3"], marks={"101": True, "102": True})
    c.req("POST", "/api/competition-events/%d/open" % r2b, body={"roster": ["107", "108", "109", "110"]}, expect=200)
    run_round(c, r2b, "平四", ["J1", "J2", "J3"], marks={"107": True, "108": True})
    st, d = c.req("POST", "/api/projects/P01Z01/rounds/2/advancement-confirm",
                  body={"assign": {"P01Z01-R3": ["101", "102", "107", "108"]}, "append": True,
                        "competition_id": cid}, expect=200)
    r3 = evs["P01Z01-R3"]
    c.req("POST", "/api/competition-events/%d/open" % r3,
          body={"roster": ["101", "102", "107", "108"]}, expect=200)
    run_round(c, r3, "平四", ["J1", "J2", "J3"],
              placements={"101": "1", "107": "2", "102": "3", "108": "4"})
    p2 = evs["P02-R1"]
    c.req("POST", "/api/competition-events/%d/open" % p2, body={"roster": ["201", "202", "203", "204"]}, expect=200)
    run_round(c, p2, "华尔兹", ["J1", "J2", "J3"],
              placements={"201": "1", "202": "2", "203": "3", "204": "4"})

    # ---------- 7) 团体总分独立复算对拍（公开 API == 期望；管理 == 公开） ----------
    # 计分轮：P01Z01-R3（名次 101=1,107=2,102=3,108=4）+ P02-R1（201=1,202=2,203=3,204=4）
    expect = {}
    for num, rank, unit in ((101, 1, units[101]), (107, 2, units[107]), (102, 3, units[102]),
                            (108, 4, units[108]), (201, 1, units[201]), (202, 2, units[202]),
                            (203, 3, units[203]), (204, 4, units[204])):
        expect[unit] = expect.get(unit, 0) + POINTS[rank]
    st, d = c.req("GET", "/api/public/events/%d/team-standings" % cid)
    got = {s["unit"]: s["total"] for s in d["standings"]}
    check(got == expect, "公开团体总分 == 独立复算", "got=%s expect=%s" % (got, expect))
    st, html = c.req("GET", "/events/%d/team-standings" % cid)
    admin_totals = {}
    if st == 200 and isinstance(html, str):
        import re
        for m in re.finditer(r"<td>([^<]+)</td><td class=\"num\">([\d.]+)</td>", html):
            admin_totals[m.group(1)] = float(m.group(2))
    check(admin_totals == {u: float(t) for u, t in expect.items()},
          "管理榜 == 公开榜（单一来源回归）", "admin=%s" % admin_totals)

    # ---------- 8) 前端响应 ----------
    for path, marker in (("/competitions/%d" % cid, COMP_NAME),
                         ("/events/%d/results" % cid, COMP_NAME),
                         ("/events/%d/team-standings" % cid, "团体总分榜"),
                         ("/events/%d/advancement?project=P01Z01&round=1" % cid, "晋级")):
        st, body = c.req("GET", path)
        check(st == 200 and marker in (body if isinstance(body, str) else ""), "页面 %s" % path, "marker=%s" % marker)
    jc = Client()
    jc.cookie = "session=ci-j1"
    st, body = jc.req("GET", "/judge")
    check(st == 200, "裁判工作台 200")
    st, body = c.req("GET", "/api/public/events/%d/schedule" % cid)
    check(st == 200 and isinstance(body, dict) and body.get("competition"), "公开赛程 API")

    # ---------- 9) doctor 不变量（名单归属/分场互斥/晋级闭包） ----------
    import subprocess
    env = dict(os.environ, CI_BASE=BASE, CI_ADMIN_COOKIE=c.cookie, CI_COMP=str(cid))
    p = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "doctor.py")],
                       env=env, capture_output=True, text=True, timeout=60)
    check(p.returncode == 0, "doctor 不变量体检", (p.stdout + p.stderr)[-300:])

    # ---------- 10) reset_scoring 破坏性操作加固 ----------
    st, d = c.req("POST", "/api/events/%d/reset-scoring" % cid, body={})
    check(st == 400, "reset 无确认 → 400", d if isinstance(d, str) else d.get("detail", ""))
    st, d = c.req("POST", "/api/events/%d/reset-scoring" % cid, body={"confirm": "错误的赛事名"})
    check(st == 400, "reset 赛事名不符 → 400", d if isinstance(d, str) else d.get("detail", ""))
    st, d = c.req("POST", "/api/events/%d/reset-scoring" % cid, body={"confirm": COMP_NAME}, expect=200)
    check(d.get("events_reset", 0) > 0, "reset 赛事名匹配 → 200")

    # ---------- 汇总 ----------
    fails = [r for r in RESULTS if not r[0]]
    print("\n==== CI 套件汇总：%d 通过 / %d 失败 ====" % (len(RESULTS) - len(fails), len(fails)))
    for _, tag, msg in fails:
        print("  ✗ %s | %s" % (tag, msg))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
