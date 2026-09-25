#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_core_scoring — core.ScoringAlgorithm vs src.ScoringAlgorithm 等价性对照。

覆盖：
- Mark制正常评分 / 并列（同分）/ 边界（空输入、单选手、全并列）
- 顺位法正常评分 / 同多数票决胜链 / 边界
- 晋级规则 all_tied_advance / strict_count
"""
import pytest

from core import ScoringAlgorithm as CoreAlg, ScoringType, ScoreRecord
from src.algorithms.scoring import ScoringAlgorithm as SrcAlg
from src.models.data_models import ScoringType as SrcScoringType
from src.algorithms.scoring import ScoringAlgorithm as SrcAlg


# ------------------------------------------------------------------ 构造工具
def mark_records(votes, judges=("J1", "J2", "J3"), event="E1", dance="华尔兹"):
    """votes: {选手背番号: [bool, bool, ...]}，与 judges 一一对应"""
    records = []
    for comp, marks in votes.items():
        for judge, m in zip(judges, marks):
            records.append(ScoreRecord(
                id="{0}-{1}-{2}".format(comp, dance, judge),
                event_id=event, judge_id=judge, competitor_number=str(comp),
                dance_name=dance, mark=m,
            ))
    return records


def skating_records(placements, judges=("J1", "J2", "J3"), event="E1", dance="华尔兹"):
    """placements: {选手背番号: [名次, 名次, ...]}，与 judges 一一对应"""
    records = []
    for comp, pls in placements.items():
        for judge, p in zip(judges, pls):
            records.append(ScoreRecord(
                id="{0}-{1}-{2}".format(comp, dance, judge),
                event_id=event, judge_id=judge, competitor_number=str(comp),
                dance_name=dance, placement=p,
            ))
    return records


def norm_result_list(results):
    """把 Result 列表规范为可比较的元组列表（顺序无关）"""
    return sorted(
        (
            r.dance_name,
            str(r.competitor_number),
            r.rank,
            float(r.score),
            float(r.total_score),
            bool(r.advancement_status),
            tuple(sorted(str(t) for t in r.tied_with)),
        )
        for r in results
    )


def norm_results_dict(res):
    return {
        "dance_results": {
            dance: norm_result_list(lst) for dance, lst in res["dance_results"].items()
        },
        "overall_results": norm_result_list(res["overall_results"]),
    }


def run_both_mark(records, advancement_count=None, advancement_rule=None):
    # 各自使用本侧的 ScoringType 枚举（跨库枚举实例不相等）
    core_alg, src_alg = CoreAlg(), SrcAlg()
    core_out = core_alg.calculate_results(records, ScoringType.MARK,
                                          advancement_count=advancement_count,
                                          advancement_rule=advancement_rule)
    src_out = src_alg.calculate_results(records, SrcScoringType.MARK,
                                        advancement_count=advancement_count,
                                        advancement_rule=advancement_rule)
    return core_out, src_out


def run_both_skating(records, advancement_count=None, advancement_rule=None):
    core_alg, src_alg = CoreAlg(), SrcAlg()
    core_out = core_alg.calculate_results(records, ScoringType.SKATING,
                                          advancement_count=advancement_count,
                                          advancement_rule=advancement_rule)
    src_out = src_alg.calculate_results(records, SrcScoringType.SKATING,
                                        advancement_count=advancement_count,
                                        advancement_rule=advancement_rule)
    return core_out, src_out


# ------------------------------------------------------------------ Mark制
class TestMarkEquivalence:
    def test_normal_scoring(self):
        records = mark_records({
            1: [True, True, True],
            2: [True, True, False],
            3: [True, False, False],
        })
        core_out, src_out = run_both_mark(records)
        assert core_out[0] == src_out[0] is True
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])

    def test_ties_same_votes(self):
        records = mark_records({
            1: [True, True, False],
            2: [True, True, False],
            3: [False, False, True],
        })
        core_out, src_out = run_both_mark(records)
        assert core_out[0] == src_out[0] is True
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        # 1、2 并列第1，3 第3
        overall = {str(r.competitor_number): r for r in core_out[1]["overall_results"]}
        assert overall["1"].rank == overall["2"].rank == 1
        assert overall["3"].rank == 3

    def test_single_competitor(self):
        records = mark_records({7: [True, False, True]})
        core_out, src_out = run_both_mark(records)
        assert core_out[0] == src_out[0] is True
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        assert core_out[1]["overall_results"][0].rank == 1

    def test_all_tied(self):
        records = mark_records({
            1: [True] * 3,
            2: [True] * 3,
            3: [True] * 3,
            4: [True] * 3,
        })
        core_out, src_out = run_both_mark(records)
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        assert all(r.rank == 1 for r in core_out[1]["overall_results"])

    def test_empty_records(self):
        core_out, src_out = run_both_mark([])
        assert core_out == src_out
        assert core_out[0] is False
        assert core_out[2] == ["没有评分记录"]

    def test_multi_dance(self):
        records = (mark_records({1: [True, True, False], 2: [True, True, True]},
                                dance="华尔兹")
                   + mark_records({1: [True, False, False], 2: [True, True, False]},
                                  dance="探戈"))
        core_out, src_out = run_both_mark(records)
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])


# ------------------------------------------------------------------ Mark制晋级
class TestMarkAdvancement:
    def test_all_tied_advance_beyond_quota(self):
        # 晋级2人，但第2、3名同分 → 3人全部晋级
        records = mark_records({
            1: [True, True, True],
            2: [True, True, False],
            3: [True, True, False],
            4: [False, False, False],
        })
        core_out, src_out = run_both_mark(records, advancement_count=2,
                                          advancement_rule="all_tied_advance")
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        overall = {str(r.competitor_number): r for r in core_out[1]["overall_results"]}
        assert overall["1"].advancement_status is True
        assert overall["2"].advancement_status is True
        assert overall["3"].advancement_status is True
        assert overall["4"].advancement_status is False

    def test_strict_count(self):
        records = mark_records({
            1: [True, True, True],
            2: [True, True, False],
            3: [True, True, False],
            4: [False, False, False],
        })
        core_out, src_out = run_both_mark(records, advancement_count=2,
                                          advancement_rule="strict_count")
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        overall = core_out[1]["overall_results"]
        advanced = [str(r.competitor_number) for r in overall if r.advancement_status]
        assert len(advanced) == 2


# ------------------------------------------------------------------ 顺位法
class TestSkatingEquivalence:
    def test_normal_ranking(self):
        records = skating_records({
            1: [1, 1, 1],
            2: [2, 2, 2],
            3: [3, 3, 3],
        })
        core_out, src_out = run_both_skating(records)
        assert core_out[0] == src_out[0] is True
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])

    def test_majority_tie_broken_by_total_sum(self):
        # 选手2、3对第1名各有1票、对前2名各有2票（多数票相同），总序和决胜
        # J1: 1,2,3  J2: 1,3,2  J3: 2,3,1 → 2号: 1,3,2(序和6) 3号: 3,2,3(序和8)
        records = skating_records({
            1: [1, 1, 2],
            2: [2, 3, 3],
            3: [3, 2, 1],
        })
        core_out, src_out = run_both_skating(records)
        assert core_out[0] == src_out[0] is True
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        ranks = {str(r.competitor_number): r.rank for r in core_out[1]["overall_results"]}
        assert ranks == {"1": 1, "2": 3, "3": 2}

    def test_multi_dance_overall(self):
        records = (skating_records({1: [1, 1, 2], 2: [2, 2, 1], 3: [3, 3, 3]},
                                   dance="华尔兹")
                   + skating_records({1: [2, 1, 1], 2: [1, 2, 2], 3: [3, 3, 3]},
                                     dance="探戈"))
        core_out, src_out = run_both_skating(records)
        assert core_out[0] == src_out[0] is True
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        # 打分明细等价（忽略时间戳）
        core_details, src_details = core_out[3], src_out[3]
        for dance, comp_details in core_details.items():
            for comp, detail in comp_details.items():
                other = src_details[dance][comp]
                assert detail.judge_placements == other.judge_placements
                assert detail.placement_counts == other.placement_counts
                assert detail.cumulative_votes == other.cumulative_votes
                assert detail.sum_placement == other.sum_placement
                assert detail.final_rank == other.final_rank
                assert detail.majority_rank == other.majority_rank
        # 综合打分明细等价
        core_od, src_od = core_out[4], src_out[4]
        for comp, detail in core_od.items():
            other = src_od[comp]
            assert detail.total_sum_placement == other.total_sum_placement
            assert detail.overall_majority_rank == other.overall_majority_rank

    def test_single_competitor_single_judge(self):
        records = skating_records({5: [1]}, judges=("J1",))
        core_out, src_out = run_both_skating(records)
        assert core_out[0] == src_out[0] is True
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        assert core_out[1]["overall_results"][0].rank == 1

    def test_invalid_records_rejected(self):
        # 同一裁判给同一选手重复评分 → 校验失败
        records = skating_records({1: [1, 2, 3], 2: [2, 1, 2]})
        core_out, src_out = run_both_skating(records)
        assert core_out[0] == src_out[0] is False
        assert core_out[2] == src_out[2]
        assert len(core_out[2]) > 0

    def test_empty_records(self):
        core_out, src_out = run_both_skating([])
        assert core_out == src_out
        assert core_out[0] is False
        assert core_out[2] == ["没有评分记录"]

    def test_skating_advancement(self):
        records = skating_records({
            1: [1, 1, 1],
            2: [2, 2, 2],
            3: [3, 3, 3],
            4: [4, 4, 4],
        })
        core_out, src_out = run_both_skating(records, advancement_count=2,
                                             advancement_rule="all_tied_advance")
        assert norm_results_dict(core_out[1]) == norm_results_dict(src_out[1])
        advanced = {str(r.competitor_number) for r in core_out[1]["overall_results"]
                    if r.advancement_status}
        assert advanced == {"1", "2"}


# ------------------------------------------------------------------ 校验函数
class TestValidateScores:
    @pytest.mark.parametrize("records,st_core,st_src", [
        (mark_records({1: [True, True, False], 2: [False, True, True]}), ScoringType.MARK, SrcScoringType.MARK),
        (skating_records({1: [1, 2, 3], 2: [2, 1, 1]}), ScoringType.SKATING, SrcScoringType.SKATING),
    ])
    def test_validate_equivalence(self, records, st_core, st_src):
        core_alg, src_alg = CoreAlg(), SrcAlg()
        assert (core_alg.validate_scores(records, st_core)
                == src_alg.validate_scores(records, st_src))
