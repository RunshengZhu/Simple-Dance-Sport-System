#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例赛事（演示）种子脚本：在目标环境重建一个囊括全部功能的演示赛事。

覆盖：三种评分制（顺位法/Mark制/评分制）、预赛→晋级→决赛全流程、
部分检录（未检录灰显）、已播报标记、团体总分、待开场场次。
幂等：已存在同名赛事则删除重建。

用法：python3 tools/build_demo_showcase.py <BASE> <管理员口令>
"""
import json
import sys
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302").rstrip("/")
ADMIN_PW = sys.argv[2] if len(sys.argv) > 2 else "admin123"
COMP_NAME = "示例赛事（演示）"

CK = {"admin": "", "judge": "", "marshal": "", "host": ""}

DEMO_STAFF = [("demo-checkin", "DemoCheckin2026", "marshal"),
              ("demo-host", "DemoHost2026", "host"),
              ("demo-admin", "DemoAdmin2026", "compadmin")]


def req(method, path, body=None, raw=None, sess="admin"):
    r = urllib.request.Request(BASE + path, method=method)
    ck = CK.get(sess, "")
    if ck:
        r.add_header("Cookie", ck)
    data = None
    if raw is not None:
        data = raw.encode() if isinstance(raw, str) else raw
        r.add_header("Content-Type", "text/csv; charset=utf-8")
    elif body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, data=data, timeout=60) as resp:
            sc = resp.headers.get("Set-Cookie")
            if sc:
                CK[sess] = sc.split(";")[0]
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def must(code, what, payload=b""):
    if code not in (200, 201):
        print(f"FAIL {what}: {code} {payload[:200]}")
        sys.exit(1)
    print(f"ok  {what}")


UNITS = ["北京舞蹈学院", "北京体育大学", "首都体育学院", "中央民族大学舞蹈学院",
         "百汇国标舞俱乐部", "芳星舞蹈艺术中心"]
NAMES = ["王雅婷", "李昊然", "张诗涵", "刘子墨", "陈思远", "杨雨薇", "赵晨曦", "黄浩宇",
         "周欣妍", "吴俊杰", "徐若彤", "孙铭泽", "胡梦琪", "朱天佑", "郭静怡", "何俊熙",
         "高雪晴", "林嘉豪", "罗诗琪", "郑博文", "梁咏琪", "谢明轩", "宋雅静", "唐一鸣",
         "韩冰雪", "冯绍峰", "曹艺涵", "邓紫琪", "许天奇", "傅清晨", "沈梦辰", "曾子航",
         "彭思思", "吕向阳", "苏婉宁", "蒋文博", "贾静雯", "韦小宝", "薛之谦", "贺美琪"]


def sk_order(n, j):
    """裁判 j（1..7）对 n 名选手的名次排列（确定性、两两不同）。"""
    order = list(range(n))
    if j == 1:
        pass
    elif j == 2:
        order = order[::-1]
    elif j == 3:
        order = order[1:] + order[:1]
    elif j == 4:
        order = order[2:] + order[:2]
    elif j == 5:
        order = order[::2] + order[1::2]
    elif j == 6:
        order = order[3:] + order[:3]
    else:
        order = order[::-2] + order[::2][::-1]
    return order


def submit_skating(ceid, dance, nums):
    dance_q = urllib.parse.quote(dance)
    for j in range(1, 8):
        req("POST", "/api/login", {"role": "judge", "judge_id": f"J{j}"}, sess="judge")
        vals = {nums[i]: r for r, i in enumerate(sk_order(len(nums), j), 1)}
        c, o = req("PUT", f"/api/judge/competition-events/{ceid}/dances/{dance_q}/sheet",
                   {"values": vals}, sess="judge")
        must(c, f"J{j} 提交 {dance} 名次表", o)


def main():
    must(*req("POST", "/api/login", {"role": "admin", "password": ADMIN_PW}), "管理员登录")

    # 重建：存在同名赛事先删
    c, o = req("GET", "/api/events")
    for e in json.loads(o).get("events", []):
        if e["name"] == COMP_NAME:
            must(*req("DELETE", f"/api/events/{e['id']}"), f"删除旧演示赛 id={e['id']}")
    must(*req("POST", "/api/events", {"name": COMP_NAME, "date": "2026-11-01", "location": "线上演示馆"}),
         "创建示例赛事")
    c, o = req("GET", "/api/events")
    cid = next(e["id"] for e in json.loads(o)["events"] if e["name"] == COMP_NAME)
    must(*req("POST", f"/api/events/{cid}/activate", {}), "激活示例赛事")

    # 演示专用账号（幂等：已存在则忽略；赛事管理员须绑定本赛事）
    for uname, upw, urole in DEMO_STAFF:
        body = {"username": uname, "password": upw, "role": urole, "display_name": f"演示-{uname}"}
        if urole == "compadmin":
            body["competition_id"] = cid
        c, o = req("POST", "/api/users", body)
        if c in (200, 201):
            print(f"ok  创建演示账号 {uname}（{urole}）")
        else:
            print(f"跳过 {uname}: {o[:60]}")

    # 选手：单位轮转，保证团体总分有 6 个单位竞争
    rows = ["背番号,项目编号,姓名,学校/单位"]
    plan = [("1%02d" % i, "P1") for i in range(1, 13)] + \
           [("2%02d" % i, "L1") for i in range(1, 13)] + \
           [("3%0d" % i, "R1") for i in range(1, 9)] + \
           [("T%02d" % i, "S1") for i in range(1, 7)]
    for k, (num, proj) in enumerate(plan):
        nm = NAMES[k % len(NAMES)]
        if num.startswith("T"):
            nm = f"{UNITS[k % len(UNITS)]}集体舞队"
        rows.append(f"{num},{proj},{nm},{UNITS[k % len(UNITS)]}")
    must(*req("POST", f"/api/events/{cid}/imports/competitors", raw="\n".join(rows) + "\n"),
         "导入选手 40 名（含 6 支集体舞队）")
    must(*req("POST", f"/api/events/{cid}/imports/judges",
              raw="裁判ID,姓名\n" + "".join(f"J{i},演示裁判{i}\n" for i in range(1, 8))),
         "导入裁判 J1-J7")

    sched = ("场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n"
             "W1,华尔兹单项赛,W1,1,华尔兹,SKATING,0," + ",".join("1%02d" % i for i in range(1, 13)) + "\n"
             "P1,标准舞预赛,P1,1,华尔兹,SKATING,6," + ",".join("1%02d" % i for i in range(1, 13)) + "\n"
             "P1F,标准舞决赛,P1,2,华尔兹,SKATING,0,\n"
             "L1,恰恰预赛,L1,1,恰恰,MARK,8," + ",".join("2%02d" % i for i in range(1, 13)) + "\n"
             "R1,伦巴决赛,R1,1,伦巴,SKATING,0," + ",".join("3%0d" % i for i in range(1, 9)) + "\n"
             "S1,集体舞决赛,S1,1,集体舞,SCORE,0," + ",".join("T%02d" % i for i in range(1, 7)) + "\n")
    must(*req("POST", f"/api/events/{cid}/imports/schedule", raw=sched), "导入赛程 6 场次")

    c, o = req("GET", f"/api/public/events/{cid}/schedule")
    ids = {e["code"]: e["id"] for e in json.loads(o)["events"]}

    # ---- P1 标准舞预赛：全检录 → 7 裁判 → 自动算分 → 发布 → 晋级确认回填决赛 ----
    must(*req("POST", f"/api/competition-events/{ids['P1']}/open",
              {"roster": ["1%02d" % i for i in range(1, 13)]}), "P1 开场")
    req("POST", "/api/login", {"role": "marshal", "username": "demo-checkin",
                               "password": "DemoCheckin2026"}, sess="marshal")
    must(*req("POST", f"/api/competition-events/{ids['P1']}/checkin",
              {"numbers": ["1%02d" % i for i in range(1, 13)], "state": True}, sess="marshal"), "P1 全检录 12/12")
    submit_skating(ids["P1"], "华尔兹", ["1%02d" % i for i in range(1, 13)])
    must(*req("POST", f"/api/competition-events/{ids['P1']}/publish", {}), "P1 发布")
    c, o = req("GET", f"/api/projects/P1/rounds/1/advancement-proposal")
    prop = [x["competitor_number"] for x in json.loads(o)["proposal"]][:6]
    must(*req("POST", f"/api/projects/P1/rounds/1/advancement-confirm",
              {"advancing": prop}), f"P1 晋级确认回填 P1F：{prop}")
    must(*req("POST", f"/api/competition-events/{ids['P1F']}/open",
              {"roster": prop}), "P1F 开场（晋级名单）")
    must(*req("POST", f"/api/competition-events/{ids['P1F']}/checkin",
              {"numbers": prop, "state": True}, sess="marshal"), "P1F 全检录 6/6")
    submit_skating(ids["P1F"], "华尔兹", prop)
    must(*req("POST", f"/api/competition-events/{ids['P1F']}/publish", {}), "P1F 发布")
    req("POST", "/api/login", {"role": "host", "username": "demo-host",
                               "password": "DemoHost2026"}, sess="host")
    must(*req("POST", f"/api/competition-events/{ids['P1F']}/announce",
              {"announced": True}, sess="host"), "P1F 标记已播报")

    # ---- R1 伦巴决赛：发布但不播报（主持人演示位） ----
    must(*req("POST", f"/api/competition-events/{ids['R1']}/open",
              {"roster": ["3%0d" % i for i in range(1, 9)]}), "R1 开场")
    must(*req("POST", f"/api/competition-events/{ids['R1']}/checkin",
              {"numbers": ["3%0d" % i for i in range(1, 9)], "state": True}, sess="marshal"), "R1 全检录 8/8")
    submit_skating(ids["R1"], "伦巴", ["3%0d" % i for i in range(1, 9)])
    must(*req("POST", f"/api/competition-events/{ids['R1']}/publish", {}), "R1 发布（未播报）")

    # ---- S1 集体舞：评分制 → 发布 → 播报 ----
    must(*req("POST", f"/api/competition-events/{ids['S1']}/open",
              {"roster": ["T%02d" % i for i in range(1, 7)]}), "S1 开场")
    must(*req("POST", f"/api/competition-events/{ids['S1']}/checkin",
              {"numbers": ["T%02d" % i for i in range(1, 7)], "state": True}, sess="marshal"), "S1 全检录 6/6")
    for j in range(1, 8):
        req("POST", "/api/login", {"role": "judge", "judge_id": f"J{j}"}, sess="judge")
        scores = {f"T%02d" % i: round(8.0 + ((i * 13 + j * 7) % 20) / 10, 1) for i in range(1, 7)}
        must(*req("PUT", f"/api/judge/competition-events/{ids['S1']}/dances/{urllib.parse.quote('集体舞')}/sheet",
                  {"values": scores}, sess="judge"), f"J{j} 提交 S1 评分")
    must(*req("POST", f"/api/competition-events/{ids['S1']}/publish", {}), "S1 发布")
    req("POST", "/api/login", {"role": "host", "username": "demo-host",
                               "password": "DemoHost2026"}, sess="host")
    must(*req("POST", f"/api/competition-events/{ids['S1']}/announce",
              {"announced": True}, sess="host"), "S1 标记已播报")

    # ---- L1 恰恰预赛：Mark 制，部分检录 8/12，评分中（裁判端灰显演示） ----
    must(*req("POST", f"/api/competition-events/{ids['L1']}/open",
              {"roster": ["2%02d" % i for i in range(1, 13)]}), "L1 开场")
    must(*req("POST", f"/api/competition-events/{ids['L1']}/checkin",
              {"numbers": ["2%02d" % i for i in range(1, 9)], "state": True}, sess="marshal"), "L1 部分检录 8/12")

    # ---- W1 保持待开始（控制台「开启评分」演示位） ----
    print("\n示例赛事就绪 cid=%s 场次=%s" % (cid, ids))


if __name__ == "__main__":
    main()
