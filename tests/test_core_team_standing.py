# -*- coding: utf-8 -*-
"""core/team_standing.py 团体总分单测：默认 preset / 并列 / best_n / 未归属 / 自定义口径。"""
from core.team_standing import (
    DEFAULT_POINTS,
    compute_team_standings,
    entry_points,
)


def _e(project, number, unit, rank):
    return {"project": project, "number": number, "unit": unit, "rank": rank}


def test_default_preset_points():
    assert entry_points(1) == 9 and entry_points(8) == 1
    assert entry_points(9) == 0 and entry_points(None) == 0 and entry_points("x") == 0


def test_basic_aggregation():
    entries = [
        _e("S1", "101", "北京大学", 1),
        _e("S1", "102", "清华大学", 2),
        _e("L1", "201", "北京大学", 3),
    ]
    out = compute_team_standings(entries)
    s = {x["unit"]: x for x in out["standings"]}
    assert s["北京大学"]["total"] == 9 + 6
    assert s["北京大学"]["per_project"] == {"S1": 9, "L1": 6}
    assert s["清华大学"]["total"] == 7
    assert out["standings"][0]["unit"] == "北京大学"
    assert out["unattributed"] == []


def test_tied_rank_same_points():
    entries = [_e("F1", "T01", "北京大学", 1), _e("F1", "T02", "清华大学", 1)]
    s = {x["unit"]: x for x in compute_team_standings(entries)["standings"]}
    assert s["北京大学"]["total"] == s["清华大学"]["total"] == 9


def test_best_n_per_project():
    entries = [
        _e("S1", "101", "北京大学", 4),
        _e("S1", "102", "北京大学", 1),   # best_n=1 只计这条 9 分
        _e("S1", "103", "复旦大学", 2),
    ]
    out = compute_team_standings(entries, best_n=1)
    s = {x["unit"]: x for x in out["standings"]}
    assert s["北京大学"]["total"] == 9 and s["北京大学"]["counted"] == 1
    assert s["复旦大学"]["total"] == 7


def test_unattributed_excluded():
    entries = [_e("S1", "101", "", 1), _e("S1", "102", None, 2), _e("S1", "103", "北京大学", 3)]
    out = compute_team_standings(entries)
    assert [x["unit"] for x in out["standings"]] == ["北京大学"]
    assert len(out["unattributed"]) == 2


def test_custom_points_preset():
    pts = {1: 5, 2: 3}
    entries = [_e("S1", "101", "A", 1), _e("S1", "102", "B", 2), _e("S1", "103", "C", 3)]
    out = compute_team_standings(entries, points=pts)
    s = {x["unit"]: x["total"] for x in out["standings"]}
    assert s == {"A": 5, "B": 3, "C": 0}
    assert out["preset"]["points"] == pts and out["preset"]["points"] is not DEFAULT_POINTS


def test_same_unit_many_pairs_counted_all():
    # 同单位多对选手全部计分（无 best_n 时）——大对数项目的口径
    entries = [_e("S1", str(100 + i), "北京大学", i) for i in range(1, 9)]
    out = compute_team_standings(entries)
    assert out["standings"][0]["total"] == float(sum(DEFAULT_POINTS.values()))
    assert out["standings"][0]["counted"] == 8
