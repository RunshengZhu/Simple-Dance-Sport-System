#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core/ 算法编排：DB 行 → core 模型 → calculate_results → JSON。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ScoringAlgorithm, ScoreRecord, ScoringType, snake_distribution  # noqa: E402

from . import db  # noqa: E402

_TYPE_MAP = {
    "MARK": ScoringType.MARK,
    "Mark制": ScoringType.MARK,
    "SKATING": ScoringType.SKATING,
    "顺位法": ScoringType.SKATING,
}


def scoring_kind(event):
    """返回 'skating' | 'mark' | 'score'（评分制，M6 集体项目：裁判打分值，汇总排名）。"""
    raw = str(event["scoring_type"]).strip().upper()
    if raw.startswith("MARK"):
        return "mark"
    if raw.startswith("SCORE") or "评分" in str(event["scoring_type"]):
        return "score"
    return "skating"


def scoring_type_of(event):
    key = str(event["scoring_type"]).strip().upper()
    return ScoringType.MARK if key.startswith("MARK") else ScoringType.SKATING


def load_score_records(event_id):
    rows = db.rows(db.get_db().execute(
        "SELECT * FROM score_records WHERE event_id=? ORDER BY id", (event_id,)))
    return [ScoreRecord(
        id=str(r["id"]), event_id=str(r["event_id"]), judge_id=r["judge_code"],
        competitor_number=str(r["competitor_number"]), dance_name=r["dance_name"],
        score=None, mark=(bool(r["mark"]) if r["mark"] is not None else None),
        placement=r["placement"],
    ) for r in rows]


def calculate_event(event):
    """计算单场次结果，写入 results 表（幂等覆盖）。返回 results_dict。"""
    if scoring_kind(event) == "score":
        data = _calculate_score_event(event)
        conn = db.get_db()
        conn.execute(
            "INSERT INTO results(event_id, calculation_time, results_data) VALUES(?,datetime('now','localtime'),?) "
            "ON CONFLICT(event_id) DO UPDATE SET calculation_time=datetime('now','localtime'), results_data=excluded.results_data",
            (event["id"], db.dump_results(data)))
        conn.execute("UPDATE events SET status='calculated' WHERE id=?", (event["id"],))
        conn.commit()
        return data
    records = load_score_records(event["id"])
    alg = ScoringAlgorithm()
    ok, results, errors, details, overall_details = alg.calculate_results(
        records, scoring_type_of(event),
        advancement_count=event["advancement_count"] or None,
        advancement_rule=event["advancement_rule"],
    )
    if not ok:
        raise ValueError("；".join(errors) or "计算失败")
    data = {
        "dance_results": {k: [r.to_dict() for r in v] for k, v in results["dance_results"].items()},
        "overall_results": [r.to_dict() for r in results["overall_results"]],
        # FR-E1/E4：打分明细（仅管理端可查）；顺位法为 SkatingScoreDetail 字典，Mark制为 null
        "score_details": _serialize_details(details),
        "overall_score_details": _serialize_overall_details(overall_details),
    }
    conn = db.get_db()
    conn.execute(
        "INSERT INTO results(event_id, calculation_time, results_data) VALUES(?,datetime('now','localtime'),?) "
        "ON CONFLICT(event_id) DO UPDATE SET calculation_time=datetime('now','localtime'), results_data=excluded.results_data",
        (event["id"], db.dump_results(data)))
    conn.execute("UPDATE events SET status='calculated' WHERE id=?", (event["id"],))
    conn.commit()
    return data


def load_results(event_id):
    row = db.rowdict(db.get_db().execute(
        "SELECT results_data FROM results WHERE event_id=?", (event_id,)).fetchone())
    return db.load_results(row["results_data"]) if row else None


def _rank_desc(sums):
    """{num: score} → [(num, rank, score)]：总分降序，标准竞赛排名（同分并列 1,1,3）。"""
    order = sorted(sums.items(), key=lambda kv: (-kv[1], str(kv[0])))
    out = []
    prev_score = None
    prev_rank = 0
    for i, (num, sc) in enumerate(order, start=1):
        rk = prev_rank if (prev_score is not None and abs(sc - prev_score) < 1e-9) else i
        out.append((str(num), rk, round(float(sc), 2)))
        prev_score, prev_rank = sc, rk
    return out


def _calculate_score_event(event):
    """评分制（M6 集体项目）：每裁判每队伍给 0~10 分值。
    分舞种/总分 = 全部裁判分数求和；名次 = 降序标准竞赛排名（同分并列 1,1,3）；
    晋级 = 名次 ≤ advancement_count（>0 时）。结果形态与 core 路径完全一致。"""
    conn = db.get_db()
    rows = db.rows(conn.execute(
        "SELECT judge_code, competitor_number, dance_name, mark FROM score_records WHERE event_id=? ORDER BY id",
        (event["id"],)))
    dances = dances_of(event["id"])
    per = {d: {} for d in dances}
    for r in rows:
        v = r["mark"]
        if v is None:
            continue
        per.setdefault(r["dance_name"], {}).setdefault(str(r["competitor_number"]), {})[r["judge_code"]] = float(v)

    dance_results = {}
    for d in dances:
        sums = {num: sum(jm.values()) for num, jm in per.get(d, {}).items()}
        dance_results[d] = [
            {"event_id": str(event["id"]), "competitor_number": num, "rank": rk,
             "dance_name": d, "score": sc, "total_score": sc, "details": {},
             "advancement_status": False, "tied_with": []}
            for num, rk, sc in _rank_desc(sums)]

    totals = {}
    for d in dances:
        for num, jm in per.get(d, {}).items():
            totals[num] = totals.get(num, 0.0) + sum(jm.values())
    adv_n = event["advancement_count"] or 0
    overall = []
    for num, rk, sc in _rank_desc(totals):
        overall.append({"event_id": str(event["id"]), "competitor_number": num, "rank": rk,
                        "dance_name": "综合", "score": sc, "total_score": sc, "details": {},
                        "advancement_status": bool(adv_n and rk <= adv_n), "tied_with": []})

    details = {d: {num: dict(jm) for num, jm in per.get(d, {}).items()} for d in dances}
    return {
        "dance_results": dance_results,
        "overall_results": overall,
        "score_details": details,
        "overall_score_details": None,
    }


def _serialize_details(details):
    """{舞种: {选手: SkatingScoreDetail}} → JSON 安全字典"""
    if not details:
        return None
    return {dance: {str(num): d.to_dict() for num, d in comp_map.items()}
            for dance, comp_map in details.items()}


def _serialize_overall_details(overall_details):
    """{选手: SkatingOverallDetail} → JSON 安全字典"""
    if not overall_details:
        return None
    return {str(num): d.to_dict() for num, d in overall_details.items()}


def roster(event_id):
    return [r["competitor_number"] for r in db.rows(db.get_db().execute(
        "SELECT competitor_number FROM event_competitors WHERE event_id=? ORDER BY competitor_number",
        (event_id,)))]


def dances_of(event_id):
    return [r["name"] for r in db.rows(db.get_db().execute(
        "SELECT name FROM event_dances WHERE event_id=? ORDER BY ord", (event_id,)))]


def judges_of(competition_id):
    return [r["code"] for r in db.rows(db.get_db().execute(
        "SELECT code FROM judges WHERE competition_id=? ORDER BY code", (competition_id,)))]


def is_complete(event, roster_list, dances, judge_codes):
    """收齐判定（按评分类型区分，2026-08-29 对齐 core Mark制语义）：
    - 顺位法/评分制：上场选手 × 舞种 × 裁判 全有记录
    - Mark制（滑冰制预赛）：裁判只对选中的选手给 mark——每裁判每舞种存在任意提交记录
      即视为完成（core 仅统计 mark is True 的票数，未选中选手票数为 0）。"""
    if not roster_list or not dances or not judge_codes:
        return False
    if scoring_kind(event) == "mark":
        conn = db.get_db()
        for d in dances:
            for j in judge_codes:
                n = conn.execute(
                    "SELECT COUNT(*) c FROM score_records WHERE event_id=? AND dance_name=? AND judge_code=?",
                    (event["id"], d, j)).fetchone()["c"]
                if n < 1:
                    return False
        return True
    conn = db.get_db()
    for d in dances:
        for j in judge_codes:
            n = conn.execute(
                "SELECT COUNT(*) c FROM score_records WHERE event_id=? AND dance_name=? AND judge_code=?",
                (event["id"], d, j)).fetchone()["c"]
            if n < len(roster_list):
                return False
    return True


def advancement_proposal(competition_id, project_code, round_no):
    """合并同项目本轮所有已计算场次的晋级者，按总分排序生成预案。"""
    conn = db.get_db()
    events = db.rows(conn.execute(
        "SELECT * FROM events WHERE competition_id=? AND project_code=? AND round=? AND status IN ('calculated','published')",
        (competition_id, project_code, round_no)))
    best = {}
    for ev in events:
        data = load_results(ev["id"])
        if not data:
            continue
        skating = scoring_type_of(ev) == ScoringType.SKATING
        for r in data["overall_results"]:
            if not r.get("advancement_status"):
                continue
            num = str(r["competitor_number"])
            # 排序键：顺位法名次小者优；Mark制总分大者优
            key = (float(r["rank"]), 0.0) if skating else (0.0, -float(r.get("total_score") or 0))
            if num not in best or key < best[num][0]:
                best[num] = (key, float(r.get("total_score") or 0))
    ordered = sorted(best.items(), key=lambda kv: kv[1][0])
    return [{"competitor_number": n, "total_score": v[1]} for n, v in ordered]


def confirm_advancement(competition_id, project_code, round_no, advancing_numbers):
    """确认晋级：蛇形分配到下一轮场次并回填名单。"""
    conn = db.get_db()
    next_events = db.rows(conn.execute(
        "SELECT * FROM events WHERE competition_id=? AND project_code=? AND round=? ORDER BY code",
        (competition_id, project_code, round_no + 1)))
    if not next_events:
        raise ValueError("赛程中不存在下一轮场次，无法回填")
    groups = snake_distribution([str(n) for n in advancing_numbers], len(next_events))
    for i, ev in enumerate(next_events):
        conn.execute("DELETE FROM event_competitors WHERE event_id=?", (ev["id"],))
        for num in groups.get(i, []):
            conn.execute("INSERT OR IGNORE INTO event_competitors(event_id, competitor_number) VALUES(?,?)",
                         (ev["id"], num))
    conn.commit()
    return {ev["code"]: groups.get(i, []) for i, ev in enumerate(next_events)}
