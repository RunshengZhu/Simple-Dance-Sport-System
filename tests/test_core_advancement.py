#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_core_advancement — core.advancement vs src.algorithms.advancement 对照。
蛇形分组：正常 / 边界（空输入、单选手、组数多于人数、全并列成绩）。
"""
import random
import types

import pytest

from core import advancement as core_adv
from src.algorithms import advancement as src_adv


class TestSnakeDistribution:
    @pytest.mark.parametrize("n,groups", [
        (10, 2), (7, 3), (6, 3), (5, 2), (12, 4),
    ])
    def test_equivalence(self, n, groups):
        competitors = list(range(1, n + 1))
        assert (core_adv.snake_distribution(competitors, groups)
                == src_adv.snake_distribution(competitors, groups))

    def test_snake_pattern(self):
        # 8人2组：组1 = 1,4,5,8；组2 = 2,3,6,7
        groups = core_adv.snake_distribution([1, 2, 3, 4, 5, 6, 7, 8], 2)
        assert groups == {0: [1, 4, 5, 8], 1: [2, 3, 6, 7]}

    def test_empty_input(self):
        assert core_adv.snake_distribution([], 3) == {}
        assert src_adv.snake_distribution([], 3) == {}

    def test_zero_or_negative_groups(self):
        for g in (0, -1):
            assert core_adv.snake_distribution([1, 2, 3], g) == {}
            assert src_adv.snake_distribution([1, 2, 3], g) == {}

    def test_single_competitor(self):
        assert core_adv.snake_distribution([42], 3) == src_adv.snake_distribution([42], 3)
        assert core_adv.snake_distribution([42], 3) == {0: [42], 1: [], 2: []}

    def test_fewer_competitors_than_groups(self):
        assert (core_adv.snake_distribution([1, 2], 5)
                == src_adv.snake_distribution([1, 2], 5))

    def test_all_tied_scores_input(self):
        # 全并列时输入为同分选手序列，蛇形分配只依赖顺序
        competitors = [str(i) for i in range(1, 10)]
        assert (core_adv.snake_distribution(competitors, 3)
                == src_adv.snake_distribution(competitors, 3))

    def test_partition_preserved(self):
        competitors = list(range(1, 11))
        groups = core_adv.snake_distribution(competitors, 3)
        merged = sorted(x for members in groups.values() for x in members)
        assert merged == competitors


class TestRandomDistribution:
    def test_equivalence_with_seed(self):
        competitors = list(range(1, 9))
        random.seed(1234)
        src_out = src_adv.random_distribution(competitors, 3)
        core_out = core_adv.random_distribution(competitors, 3, rng=random.Random(1234))
        assert core_out == src_out

    def test_edge_cases(self):
        assert core_adv.random_distribution([], 3) == {}
        assert core_adv.random_distribution([1], 0) == {}
        assert core_adv.random_distribution([1], 2, rng=random.Random(0)) == {0: [1], 1: []}


class TestDistributeToEvents:
    @staticmethod
    def make_events(*ids):
        return [types.SimpleNamespace(id=i) for i in ids]

    def test_snake(self):
        events = self.make_events("E2", "E1")  # 乱序传入，应按 id 排序后分配
        out = core_adv.distribute_competitors_to_events([1, 2, 3, 4], events, "snake")
        src_out = src_adv.distribute_competitors_to_events([1, 2, 3, 4],
                                                           self.make_events("E2", "E1"), "snake")
        assert out == src_out
        assert out == {"E1": [1, 4], "E2": [2, 3]}

    def test_random(self):
        events = self.make_events("E1", "E2")
        src_out = src_adv.distribute_competitors_to_events(list(range(1, 7)), events, "random")
        core_out = core_adv.distribute_competitors_to_events(
            list(range(1, 7)), self.make_events("E1", "E2"), "random",
            rng=random.Random(99))
        random.seed(99)
        src_out2 = src_adv.distribute_competitors_to_events(list(range(1, 7)), events, "random")
        assert core_out == src_out2 or core_out == src_out  # 随机方法只验证结构

    def test_unknown_method(self):
        assert core_adv.distribute_competitors_to_events(
            [1, 2], self.make_events("E1"), "unknown") == {}
        assert src_adv.distribute_competitors_to_events(
            [1, 2], self.make_events("E1"), "unknown") == {}

    def test_empty(self):
        assert core_adv.distribute_competitors_to_events([], self.make_events("E1")) == {}
        assert core_adv.distribute_competitors_to_events([1], []) == {}


class TestGetAdvancingCompetitors:
    @staticmethod
    def make_manager(events_with_results):
        """events_with_results: [(event_id, results_data_or_None), ...]"""

        class Manager:
            def __init__(self):
                self._events = [types.SimpleNamespace(id=eid) for eid, _ in events_with_results]
                self._results = {eid: r for eid, r in events_with_results}

            def get_events_by_project_and_round(self, project_id, rnd):
                return self._events

            def get_results(self, event_id):
                res = self._results.get(event_id)
                if res is None:
                    return None
                return types.SimpleNamespace(results_data=res)

        return Manager()

    @staticmethod
    def results_data(advancing):
        # advancing: [(背号, 总分, 是否晋级)]
        return {"overall_results": [
            types.SimpleNamespace(competitor_number=str(n),
                                  total_score=s,
                                  advancement_status=a)
            for n, s, a in advancing
        ]}

    def test_collect_and_sort(self):
        manager = self.make_manager([
            ("E1", self.results_data([("3", 5, True), ("1", 9, True), ("2", 7, False)])),
            ("E2", self.results_data([("4", 8, True)])),
        ])
        assert (core_adv.get_advancing_competitors("P1", "1", manager)
                == src_adv.get_advancing_competitors("P1", "1", manager)
                == ["1", "4", "3"])

    def test_no_events(self):
        manager = self.make_manager([])
        assert core_adv.get_advancing_competitors("P1", "1", manager) == []
        assert src_adv.get_advancing_competitors("P1", "1", manager) == []

    def test_no_results(self):
        manager = self.make_manager([("E1", None)])
        assert core_adv.get_advancing_competitors("P1", "1", manager) == []
        assert src_adv.get_advancing_competitors("P1", "1", manager) == []

    def test_dict_format_results(self):
        class Manager:
            def get_events_by_project_and_round(self, pid, rnd):
                return [types.SimpleNamespace(id="E1")]

            def get_results(self, eid):
                return types.SimpleNamespace(results_data={
                    "overall_results": [
                        {"competitor_number": "5", "total_score": 6, "advancement_status": True},
                        {"competitor_number": "6", "total_score": 9, "advancement_status": True},
                    ]
                })

        assert (core_adv.get_advancing_competitors("P1", "1", Manager())
                == src_adv.get_advancing_competitors("P1", "1", Manager())
                == ["6", "5"])
