#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_core_skating — core.skating_system 各函数 vs src.algorithms.skating_system 对照。
包含正常 / 并列决胜链 / 边界（空输入、单选手、全对角并列不可行的替代边界）。
"""
import pytest

from core import skating_system as core_sk
from src.algorithms import skating_system as src_sk


def score(players, judge_placements):
    """{裁判: {选手序号: 名次}} → {裁判: {选手: 名次}}"""
    return {
        judge: {p: pls[i] for i, p in enumerate(players)}
        for judge, pls in judge_placements.items()
    }


class TestValidateJudgesScores:
    def test_valid_kept_invalid_filtered(self):
        players = ["1", "2", "3"]
        scores = {
            "J1": {"1": 1, "2": 2, "3": 3},   # 有效
            "J2": {"1": 1, "2": 2},            # 缺选手
            "J3": {"1": 1, "2": 2, "3": 2},    # 重复名次
            "J4": {"1": 0, "2": 2, "3": 3},    # 范围非法
        }
        expected = {"J1": scores["J1"]}
        assert core_sk.validate_judges_scores(players, scores) == expected
        assert src_sk.validate_judges_scores(players, scores) == expected

    def test_empty_scores(self):
        assert core_sk.validate_judges_scores(["1"], {}) == {}
        assert src_sk.validate_judges_scores(["1"], {}) == {}


class TestCountAndSums:
    PLAYERS = ["1", "2", "3", "4"]
    SCORES = {
        "J1": {"1": 1, "2": 2, "3": 3, "4": 4},
        "J2": {"1": 2, "2": 1, "3": 4, "4": 3},
        "J3": {"1": 3, "2": 2, "3": 1, "4": 4},
    }

    def test_majority_counts(self):
        for pos in range(1, 5):
            assert (core_sk.calculate_majority_counts(self.PLAYERS, self.SCORES, pos)
                    == src_sk.calculate_majority_counts(self.PLAYERS, self.SCORES, pos))

    def test_position_sum(self):
        for pos in range(1, 5):
            assert (core_sk.calculate_position_sum(self.PLAYERS, self.SCORES, pos)
                    == src_sk.calculate_position_sum(self.PLAYERS, self.SCORES, pos))

    def test_total_sum(self):
        assert (core_sk.calculate_total_sum(self.PLAYERS, self.SCORES)
                == src_sk.calculate_total_sum(self.PLAYERS, self.SCORES))

    def test_empty_players(self):
        assert (core_sk.calculate_majority_counts([], self.SCORES, 1)
                == src_sk.calculate_majority_counts([], self.SCORES, 1))
        assert (core_sk.calculate_position_sum([], self.SCORES, 1)
                == src_sk.calculate_position_sum([], self.SCORES, 1))
        assert (core_sk.calculate_total_sum([], self.SCORES)
                == src_sk.calculate_total_sum([], self.SCORES))


class TestRanking:
    def assert_ranking_equivalent(self, players, judge_placements):
        scores = score(players, judge_placements)
        core_r, core_d = core_sk.skating_system_ranking(players, scores)
        src_r, src_d = src_sk.skating_system_ranking(players, scores)
        assert core_r == src_r
        assert core_d == src_d
        return core_r

    def test_clear_majority(self):
        ranks = self.assert_ranking_equivalent(
            ["1", "2", "3"],
            {"J1": [1, 2, 3], "J2": [1, 2, 3], "J3": [1, 3, 2]},
        )
        assert ranks == {"1": 1, "2": 2, "3": 3}

    def test_tie_broken_by_total_sum(self):
        # 2号与3号在第1名的多数票相同，序和不同
        ranks = self.assert_ranking_equivalent(
            ["1", "2", "3"],
            {"J1": [1, 2, 3], "J2": [1, 3, 2], "J3": [2, 3, 1]},
        )
        assert ranks == {"1": 1, "3": 2, "2": 3}

    def test_two_way_tie_position_sum(self):
        # 构造需要区间名次和决胜的场景
        ranks = self.assert_ranking_equivalent(
            ["1", "2", "3", "4"],
            {"J1": [1, 3, 2, 4], "J2": [1, 4, 2, 3], "J3": [2, 3, 1, 4], "J4": [2, 4, 1, 3]},
        )
        assert sorted(ranks.values()) == [1, 2, 3, 4]

    def test_single_player_single_judge(self):
        ranks = self.assert_ranking_equivalent(["9"], {"J1": [1]})
        assert ranks == {"9": 1}

    def test_single_judge_many_players(self):
        ranks = self.assert_ranking_equivalent(
            ["1", "2", "3", "4", "5"],
            {"J1": [3, 1, 5, 2, 4]},
        )
        assert ranks == {"2": 1, "4": 2, "1": 3, "5": 4, "3": 5}

    def test_no_valid_scores_raises(self):
        for mod in (core_sk, src_sk):
            with pytest.raises(ValueError):
                mod.skating_system_ranking(["1", "2"], {})

    def test_larger_field(self):
        import itertools
        players = [str(i) for i in range(1, 7)]
        placements = {
            "J1": [2, 4, 1, 6, 3, 5],
            "J2": [3, 1, 2, 5, 6, 4],
            "J3": [1, 3, 4, 2, 5, 6],
            "J4": [4, 2, 3, 1, 6, 5],
        }
        # 全排列唯一性自检
        for pls in placements.values():
            assert sorted(pls) == [1, 2, 3, 4, 5, 6]
        ranks = self.assert_ranking_equivalent(players, placements)
        assert sorted(ranks.values()) == list(range(1, 7))
        assert set(itertools.permutations([]))  # keep itertools import meaningful


class TestDetailTable:
    def assert_detail_equivalent(self, players, judge_placements):
        scores = score(players, judge_placements)
        backnum = {p: int(p) for p in players}
        core_rows, core_stats = core_sk.generate_detail_table(players, scores, backnum)
        src_df, src_stats = src_sk.generate_detail_table(players, scores, backnum)
        # 统计数据完全一致
        assert core_stats == src_stats
        # 行数据一致（逐行逐列；dict 比较与键序无关）
        src_rows = []
        for _, row in src_df.iterrows():
            src_rows.append({col: row[col] for col in src_df.columns})
        assert [set(r.keys()) for r in core_rows] == [set(src_df.columns)] * len(core_rows)
        for c_row, s_row in zip(core_rows, src_rows):
            assert c_row == s_row

    def test_detail_normal(self):
        self.assert_detail_equivalent(
            ["1", "2", "3"],
            {"J1": [1, 2, 3], "J2": [1, 2, 3], "J3": [2, 1, 3]},
        )

    def test_detail_with_ties(self):
        self.assert_detail_equivalent(
            ["1", "2", "3", "4"],
            {"J1": [1, 3, 2, 4], "J2": [1, 4, 2, 3], "J3": [2, 3, 1, 4], "J4": [2, 4, 1, 3]},
        )

    def test_detail_no_backnum_map(self):
        players = ["1", "2", "3"]
        scores = score(players, {"J1": [1, 2, 3], "J2": [2, 1, 3], "J3": [3, 2, 1]})
        core_rows, core_stats = core_sk.generate_detail_table(players, scores)
        src_df, src_stats = src_sk.generate_detail_table(players, scores)
        assert core_stats == src_stats
        src_rows = [{col: row[col] for col in src_df.columns} for _, row in src_df.iterrows()]
        assert core_rows == src_rows


class TestOverallRanking:
    def test_no_ties(self):
        dance_rankings = {"华尔兹": {"1": 1, "2": 2, "3": 3},
                          "探戈": {"1": 2, "2": 1, "3": 3}}
        assert (core_sk.calculate_overall_ranking(dance_rankings)
                == src_sk.calculate_overall_ranking(dance_rankings))

    def test_ties_same_rank_skip(self):
        # 1号与2号序和并列最低（均3）→ 并列第1，3号第3
        dance_rankings = {"华尔兹": {"1": 1, "2": 2, "3": 3},
                          "探戈": {"1": 2, "2": 1, "3": 3}}
        core_out = core_sk.calculate_overall_ranking(dance_rankings)
        src_out = src_sk.calculate_overall_ranking(dance_rankings)
        assert core_out == src_out
        assert core_out["1"]["最终名次"] == core_out["2"]["最终名次"] == 1
        assert core_out["3"]["最终名次"] == 3

    def test_all_tied(self):
        dance_rankings = {"华尔兹": {"1": 1, "2": 1, "3": 1}}
        core_out = core_sk.calculate_overall_ranking(dance_rankings)
        src_out = src_sk.calculate_overall_ranking(dance_rankings)
        assert core_out == src_out
        assert all(d["最终名次"] == 1 for d in core_out.values())

    def test_empty(self):
        assert core_sk.calculate_overall_ranking({}) == src_sk.calculate_overall_ranking({})


class TestMarkdownParsing:
    MARKDOWN = """| 背号 | J1 | J2 | J3 | 1 | 1-2 | 1-3 | 名次 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 2 | 3 | 3 | 3 | 1 |
| 2 | 2 | 3 | 1 | 1 | 2 | 3 | 2 |
| 3 | 3 | 2 | 3 | 0 | 1 | 3 | 3 |"""

    def test_parse_equivalence(self):
        assert (core_sk.parse_markdown_table(self.MARKDOWN)
                == src_sk.parse_markdown_table(self.MARKDOWN))


class TestOverallRankingTable:
    def test_table_generation_equivalence(self):
        rankings = {"1": {"综合得分": 3, "最终名次": 1},
                    "2": {"综合得分": 5, "最终名次": 2},
                    "33": {"综合得分": 7, "最终名次": 3},
                    "4": {"综合得分": 9, "最终名次": 4}}
        assert (core_sk.generate_overall_ranking_table(rankings)
                == src_sk.generate_overall_ranking_table(rankings))
