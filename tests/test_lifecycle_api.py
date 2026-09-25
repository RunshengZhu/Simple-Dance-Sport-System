#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""赛事生命周期 API 测试（httpx ASGITransport 直连，不出网）。

覆盖生命周期状态机与权限矩阵：建赛/激活（全局单激活）、CSV 三类导入
（评分类型只认英文 SKATING/MARK/SCORE）、schedule/add 校验前置（不留幽灵场）、
开场（空名单 400、二次 open 保留检录、reset/had_scores 全清）、检录
（host/marshal 权限、撤销检录删评分）、裁判评分（顺位法服务端复验、
三裁判收齐自动计算）、手动计算/发布/撤回/退回。
TestClient 与 httpx 0.28 不兼容，故用 ASGI 直连 + asyncio.run 同步封装；
lifespan 不自动执行，模块级手动 init_db()。
"""
import os
import tempfile

# 在导入 server.app 之前固定隔离环境（DB 路径在导入时求值）
_TMP = tempfile.mkdtemp(prefix="dsh-lifecycle-test-")
os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from server import app as app_module, db as db_module  # noqa: E402

db_module.init_db()   # ASGITransport 不执行 lifespan，手动建表

_SESSIONS = {}   # 会话槽：admin / marshal / J1 / J2 / J3 互不覆盖


def req(method, path, content=None, json=None, role=None):
    """同步 ASGI 请求；role 指定会话槽（不传 = 匿名）。"""
    headers = {}
    token = _SESSIONS.get(role)
    if token:
        headers["Cookie"] = "session=" + token

    async def _run():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(method, path, content=content, json=json, headers=headers)

    return asyncio.run(_run())


def _login(slot, payload):
    r = req("POST", "/api/login", json=payload)
    assert r.status_code == 200, r.text
    _SESSIONS[slot] = r.headers["set-cookie"].split("session=")[1].split(";")[0]


CSV_COMPETITORS = (
    "背番号,姓名,学校/单位,项目编号\n"
    "101,张三,北京舞蹈学院,SK\n"
    "102,李四,上海体育大学,SK\n"
    "103,王五,北京舞蹈学院,SK\n"
    "104,赵六,上海体育大学,SK\n"
    "105,钱七,南京艺术学院,AD\n"
    "106,孙八,南京艺术学院,AD\n"
).encode("utf-8")

CSV_JUDGES = (
    "裁判ID,姓名\n"
    "J1,王裁判\n"
    "J2,李裁判\n"
    "J3,张裁判\n"
).encode("utf-8")

CSV_SCHEDULE = (
    "场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n"
    'SK-R1,拉丁初赛,SK,1,ChaCha,SKATING,2,"101,102,103,104"\n'
    'SC-E1,集体评分场,SC,1,Waltz,SCORE,0,""\n'
).encode("utf-8")


@pytest.fixture(scope="module", autouse=True)
def _sessions():
    """管理员 + 检录员（账号制）会话；裁判会话待裁判库导入后在 env 中登录。"""
    _login("admin", {"role": "admin", "password": "admin123"})
    req("POST", "/api/users", json={"username": "marshal_t", "password": "marshalpw1",
                                    "role": "marshal", "display_name": "检录员甲"}, role="admin")
    _login("marshal", {"role": "marshal", "username": "marshal_t", "password": "marshalpw1"})
    yield


@pytest.fixture(scope="module")
def env(_sessions):
    """建赛 → 激活 → 三类导入 → 追加场 AD1 → 开场 SK-R1（模块级共享生命周期数据）。"""
    r = req("POST", "/api/events", json={"name": "生命周期测试赛", "date": "2026-09-26",
                                         "location": "上海"}, role="admin")
    assert r.status_code == 200
    cid = r.json()["id"]
    assert req("POST", f"/api/events/{cid}/activate", role="admin").status_code == 200
    imp = {kind: req("POST", f"/api/events/{cid}/imports/{kind}", content=body, role="admin")
           for kind, body in (("competitors", CSV_COMPETITORS), ("judges", CSV_JUDGES),
                              ("schedule", CSV_SCHEDULE))}
    for kind, r in imp.items():
        assert r.status_code == 200, (kind, r.text)
    for code in ("J1", "J2", "J3"):   # 裁判登录要求裁判库已有该 ID
        _login(code, {"role": "judge", "judge_id": code})
    sched = req("GET", f"/api/public/events/{cid}/schedule").json()["events"]
    ceid = {e["code"]: e["id"] for e in sched}
    r = req("POST", f"/api/events/{cid}/schedule/add",
            json={"code": "AD1", "name": "追加场", "project": "AD", "round": 1,
                  "dances": "Tango", "type": "SKATING", "roster": "105,106"}, role="admin")
    assert r.status_code == 200
    ceid["AD1"] = r.json()["event_id"]
    r = req("POST", f"/api/competition-events/{ceid['SK-R1']}/open",
            json={"roster": ["101", "102", "103", "104"]}, role="admin")
    assert r.status_code == 200 and r.json()["reset_scores"] is False
    return {"cid": cid, "imp": imp, "ceid": ceid}


# ---------------- 建赛 / 激活 ----------------

def test_create_event_ok_and_duplicate_name_allowed():
    r1 = req("POST", "/api/events",
             json={"name": "测试赛甲", "date": "2026-09-26", "location": "北京"}, role="admin")
    assert r1.status_code == 200 and r1.json()["ok"] is True and r1.json()["id"] > 0
    r2 = req("POST", "/api/events", json={"name": "测试赛甲"}, role="admin")   # 同名允许（系统行为）
    assert r2.status_code == 200 and r2.json()["id"] != r1.json()["id"]
    assert req("POST", "/api/events", json={"name": "   "}, role="admin").status_code == 400   # 空白名拒绝


def test_activate_public_schedule_visible(env):
    r = req("GET", f"/api/public/events/{env['cid']}/schedule")   # 公开 API：匿名可读
    assert r.status_code == 200
    body = r.json()
    assert body["competition"]["name"] == "生命周期测试赛"
    assert {"SK-R1", "SC-E1", "AD1"} <= {e["code"] for e in body["events"]}
    page = req("GET", "/public/schedule")   # 公开 HTML 页（激活赛事即公开赛程）
    assert page.status_code == 200 and "SK-R1" in page.text


# ---------------- 导入 ----------------

def test_import_three_kinds_ok(env):
    assert env["imp"]["competitors"].json()["imported"] == 6
    assert env["imp"]["judges"].json()["imported"] == 3
    assert env["imp"]["schedule"].json()["imported"] == 2


def test_schedule_import_scoring_type_mapping(env):
    """评分类型只认英文 SKATING/MARK/SCORE；中文/未知值落 Mark制。"""
    rows = (
        "场次编号,场次名称,项目编号,轮次,舞种,评分类型\n"
        "ST-SCORE,评分制,ST,1,Waltz,SCORE\n"
        "ST-CN,中文类型,ST,2,Waltz,评分制\n"
        "ST-XXX,未知类型,ST,3,Waltz,SOMETHING\n"
        "ST-SKAT,顺位法,ST,4,Waltz,SKATING\n"
    )
    r = req("POST", f"/api/events/{env['cid']}/imports/schedule",
            content=rows.encode("utf-8"), role="admin")
    assert r.status_code == 200
    got = {x["code"]: x["scoring_type"] for x in db_module.rows(db_module.get_db().execute(
        "SELECT code, scoring_type FROM events WHERE competition_id=? AND code LIKE 'ST-%'",
        (env["cid"],)))}
    assert got == {"ST-SCORE": "评分制", "ST-CN": "Mark制",
                   "ST-XXX": "Mark制", "ST-SKAT": "顺位法"}


# ---------------- schedule/add（校验前置） ----------------

def test_schedule_add_ok(env):
    r = req("POST", f"/api/events/{env['cid']}/schedule/add",
            json={"code": "AD2", "name": "第二轮追加", "project": "AD", "round": 2,
                  "dances": "Tango", "type": "MARK", "roster": "105,106"}, role="admin")
    assert r.status_code == 200
    p = req("GET", f"/api/competition-events/{r.json()['event_id']}/progress",
            role="admin").json()
    assert p["roster"] == ["105", "106"] and p["status"] == "pending"


def test_schedule_add_unknown_number_400_no_ghost_row(env):
    r = req("POST", f"/api/events/{env['cid']}/schedule/add",
            json={"code": "GHOST-1", "project": "AD", "round": 1, "roster": "105,999"}, role="admin")
    assert r.status_code == 400 and "背号不在选手库中" in r.json()["detail"]
    n = db_module.get_db().execute(
        "SELECT COUNT(*) c FROM events WHERE competition_id=? AND code='GHOST-1'",
        (env["cid"],)).fetchone()["c"]
    assert n == 0   # 校验前置：不留幽灵场次行


def test_schedule_add_duplicate_code_400(env):
    r = req("POST", f"/api/events/{env['cid']}/schedule/add",
            json={"code": "AD1", "project": "AD", "round": 1}, role="admin")
    assert r.status_code == 400 and "已存在" in r.json()["detail"]


# ---------------- 开场（open） ----------------

def test_open_ok_status_scoring(env):
    p = req("GET", f"/api/competition-events/{env['ceid']['SK-R1']}/progress",
            role="admin").json()
    assert p["status"] == "scoring"
    assert p["roster"] == ["101", "102", "103", "104"]
    assert p["dances"] == ["ChaCha"] and p["judges"] == ["J1", "J2", "J3"]


def test_open_empty_roster_400(env):
    ceid = env["ceid"]["SC-E1"]
    assert req("POST", f"/api/competition-events/{ceid}/open",
               json={"roster": []}, role="admin").status_code == 400
    r = req("POST", f"/api/competition-events/{ceid}/open", json={"roster": ""}, role="admin")
    assert r.status_code == 400 and "不能为空" in r.json()["detail"]


def test_open_unknown_number_400_state_unchanged(env):
    ceid = env["ceid"]["SK-R1"]
    r = req("POST", f"/api/competition-events/{ceid}/open",
            json={"roster": ["101", "999"]}, role="admin")
    assert r.status_code == 400 and "背号不在选手库中" in r.json()["detail"]
    p = req("GET", f"/api/competition-events/{ceid}/progress", role="admin").json()
    assert p["roster"] == ["101", "102", "103", "104"] and p["status"] == "scoring"


def test_publish_before_calculate_400(env):
    r = req("POST", f"/api/competition-events/{env['ceid']['SK-R1']}/publish", role="admin")
    assert r.status_code == 400 and "先完成计算" in r.json()["detail"]


# ---------------- 检录（checkin） ----------------

def test_checkin_permissions(env):
    checkin = f"/api/competition-events/{env['ceid']['SK-R1']}/checkin"
    body = {"numbers": ["101"], "state": True}
    assert req("POST", checkin, json=body).status_code == 401                 # 匿名
    assert req("POST", checkin, json=body, role="admin").status_code == 401   # 检录需 host/marshal
    assert req("POST", checkin, json=body, role="J1").status_code == 401      # 裁判亦无检录权
    assert req("GET", checkin).status_code == 401                             # 状态快照也需登录


def test_checkin_marshal_on_off_cycle(env):
    checkin = f"/api/competition-events/{env['ceid']['SK-R1']}/checkin"
    r = req("POST", checkin, json={"numbers": ["101", "102", "103", "104"], "state": True},
            role="marshal")
    assert r.status_code == 200 and r.json()["checked_n"] == 4
    assert req("POST", checkin, json={"numbers": ["999"], "state": True},
               role="marshal").status_code == 400   # 名单外背号拒绝
    r = req("POST", checkin, json={"numbers": ["103", "104"], "state": False}, role="marshal")
    assert r.status_code == 200 and r.json()["checked_n"] == 2
    r = req("POST", checkin, json={"numbers": ["103", "104"], "state": True}, role="marshal")
    assert r.status_code == 200 and r.json()["checked_n"] == 4
    state = req("GET", checkin, role="marshal").json()
    assert state["checked"] == ["101", "102", "103", "104"] and state["total"] == 4


def test_open_again_preserves_checkin(env):
    ceid = env["ceid"]["SK-R1"]
    checkin = f"/api/competition-events/{ceid}/checkin"
    assert req("POST", checkin, json={"numbers": ["103", "104"], "state": False},
               role="marshal").status_code == 200
    r = req("POST", f"/api/competition-events/{ceid}/open",
            json={"roster": ["101", "102", "103", "104"]}, role="admin")
    assert r.status_code == 200 and r.json()["reset_scores"] is False
    state = req("GET", checkin, role="marshal").json()
    assert state["checked"] == ["101", "102"]   # 普通二次开场保留已有检录
    # 恢复全员检录，供后续评分/发布用例使用
    assert req("POST", checkin, json={"numbers": ["103", "104"], "state": True},
               role="marshal").status_code == 200


def test_uncheck_deletes_scores_then_reset_open_clears_all(env):
    ceid = env["ceid"]["AD1"]
    assert req("POST", f"/api/competition-events/{ceid}/open",
               json={"roster": ["105", "106"]}, role="admin").status_code == 200
    assert req("POST", f"/api/competition-events/{ceid}/checkin",
               json={"numbers": ["105", "106"], "state": True}, role="marshal").status_code == 200
    sheet = f"/api/judge/competition-events/{ceid}/dances/Tango/sheet"
    assert req("PUT", sheet, json={"values": {"105": 1, "106": 2}}, role="J1").status_code == 200
    # 撤销检录 = 该选手退出：其已有评分记录一并作废
    assert req("POST", f"/api/competition-events/{ceid}/checkin",
               json={"numbers": ["106"], "state": False}, role="marshal").status_code == 200
    recs = req("GET", f"/api/competition-events/{ceid}/detail-scores",
               role="admin").json()["records"]
    assert recs and all(x["number"] != "106" for x in recs)
    assert any(x["number"] == "105" for x in recs)
    # 已有评分 → 再次 open 走全清：检录一并重置，reset_scores=True
    r = req("POST", f"/api/competition-events/{ceid}/open",
            json={"roster": ["105", "106"]}, role="admin")
    assert r.status_code == 200 and r.json()["reset_scores"] is True
    state = req("GET", f"/api/competition-events/{ceid}/checkin", role="marshal").json()
    assert state["checked"] == [] and state["total"] == 2


# ---------------- 裁判评分（sheet） ----------------

def test_sheet_requires_judge_role(env):
    sheet = f"/api/judge/competition-events/{env['ceid']['SK-R1']}/dances/ChaCha/sheet"
    body = {"values": {"101": 1, "102": 2, "103": 3, "104": 4}}
    assert req("PUT", sheet, json=body).status_code == 401                # 匿名
    assert req("PUT", sheet, json=body, role="admin").status_code == 401  # 管理员非裁判
    assert req("PUT", sheet, json=body, role="marshal").status_code == 401


def test_sheet_placement_out_of_range_400(env):
    sheet = f"/api/judge/competition-events/{env['ceid']['SK-R1']}/dances/ChaCha/sheet"
    r = req("PUT", sheet, json={"values": {"101": 1, "102": 2, "103": 3, "104": 5}}, role="J1")
    assert r.status_code == 400 and "名次超出范围" in r.json()["detail"]
    r = req("PUT", sheet, json={"values": {"101": 1, "102": 1, "103": 3, "104": 4}}, role="J1")
    assert r.status_code == 400 and "互不重复" in r.json()["detail"]


def test_sheet_missing_checked_competitor_400(env):
    sheet = f"/api/judge/competition-events/{env['ceid']['SK-R1']}/dances/ChaCha/sheet"
    r = req("PUT", sheet, json={"values": {"101": 1, "102": 2, "103": 3}}, role="J1")
    assert r.status_code == 400 and "全部已检录" in r.json()["detail"]


def test_three_judges_auto_calculate(env):
    """三裁判收齐 → 第三笔 PUT 自动计算并落结果；已计算场次拒绝再提交。"""
    ceid = env["ceid"]["SK-R1"]
    sheet = f"/api/judge/competition-events/{ceid}/dances/ChaCha/sheet"
    full = {"101": 1, "102": 2, "103": 3, "104": 4}
    assert req("PUT", sheet, json={"values": full}, role="J1").json()["auto_calculated"] is False
    assert req("PUT", sheet, json={"values": full}, role="J2").json()["auto_calculated"] is False
    r3 = req("PUT", sheet, json={"values": full}, role="J3")
    assert r3.status_code == 200 and r3.json()["auto_calculated"] is True
    p = req("GET", f"/api/competition-events/{ceid}/progress", role="admin").json()
    assert p["status"] == "calculated" and p["complete"] is True
    res = req("GET", f"/api/competition-events/{ceid}/results", role="admin")
    assert res.status_code == 200
    assert {x["competitor_number"]: x["rank"] for x in res.json()["data"]["overall_results"]} \
        == {"101": 1, "102": 2, "103": 3, "104": 4}
    r = req("PUT", sheet, json={"values": full}, role="J1")   # 状态机关门
    assert r.status_code == 400 and "已关闭评分" in r.json()["detail"]


# ---------------- 发布 / 撤回 / 退回 ----------------

def test_publish_ok_public_results_visible(env):
    ceid, cid = env["ceid"]["SK-R1"], env["cid"]
    assert req("POST", f"/api/competition-events/{ceid}/publish", role="admin").status_code == 200
    p = req("GET", f"/api/competition-events/{ceid}/progress", role="admin").json()
    assert p["status"] == "published"
    pub = req("GET", f"/api/public/events/{cid}/results").json()["results"]   # 匿名可读
    row = [x for x in pub if x["code"] == "SK-R1"]
    assert row and len(row[0]["overall"]) == 4


def test_unpublish_hides_from_public_admin_still_sees(env):
    ceid, cid = env["ceid"]["SK-R1"], env["cid"]
    assert req("POST", f"/api/competition-events/{ceid}/unpublish", role="admin").status_code == 200
    pub = req("GET", f"/api/public/events/{cid}/results").json()["results"]
    assert all(x["code"] != "SK-R1" for x in pub)   # 公开页撤下
    assert req("GET", f"/api/competition-events/{ceid}/results", role="admin").status_code == 200
    p = req("GET", f"/api/competition-events/{ceid}/progress", role="admin").json()
    assert p["status"] == "calculated"              # 撤回回计算态


def test_return_scores_clears_results_keeps_checkin(env):
    ceid = env["ceid"]["SK-R1"]
    assert req("POST", f"/api/competition-events/{ceid}/return-scores",
               role="admin").status_code == 200
    p = req("GET", f"/api/competition-events/{ceid}/progress", role="admin").json()
    assert p["status"] == "scoring"
    assert all(not nums for j in p["matrix"].values() for nums in j.values())   # 评分记录已清空
    assert req("GET", f"/api/competition-events/{ceid}/results", role="admin").status_code == 404
    state = req("GET", f"/api/competition-events/{ceid}/checkin", role="marshal").json()
    assert state["checked_n"] == 4   # 退回不清检录


# ---------------- 评分制 / 手动计算 / 权限抽测 ----------------

def test_score_type_event_auto_and_manual_calculate(env):
    """SCORE（评分制）场次端到端：开场→检录→三裁判收齐自动算→admin 手动重算。"""
    ceid = env["ceid"]["SC-E1"]
    assert req("POST", f"/api/competition-events/{ceid}/open",
               json={"roster": ["105", "106"]}, role="admin").status_code == 200
    assert req("POST", f"/api/competition-events/{ceid}/checkin",
               json={"numbers": ["105", "106"], "state": True}, role="marshal").status_code == 200
    sheet = f"/api/judge/competition-events/{ceid}/dances/Waltz/sheet"
    values = {"105": 8.5, "106": 7.0}   # 评分制：0~10 且最多一位小数
    assert req("PUT", sheet, json={"values": values}, role="J1").json()["auto_calculated"] is False
    assert req("PUT", sheet, json={"values": values}, role="J2").json()["auto_calculated"] is False
    r3 = req("PUT", sheet, json={"values": values}, role="J3")
    assert r3.status_code == 200 and r3.json()["auto_calculated"] is True
    res = req("GET", f"/api/competition-events/{ceid}/results", role="admin").json()["data"]
    assert {x["competitor_number"]: x["rank"] for x in res["overall_results"]} \
        == {"105": 1, "106": 2}   # 分值求和降序
    assert req("POST", f"/api/competition-events/{ceid}/calculate",
               role="admin").status_code == 200   # admin 手动计算（幂等重算）


def test_calculate_and_results_permissions(env):
    ceid = env["ceid"]["SK-R1"]
    assert req("POST", f"/api/competition-events/{ceid}/calculate", role="J1").status_code == 401
    assert req("GET", f"/api/competition-events/{ceid}/results").status_code == 401
