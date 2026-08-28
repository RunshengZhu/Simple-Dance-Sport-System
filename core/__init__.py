#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core — 体育舞蹈赛事评分系统纯 Python 算法内核

从 src/ 提取的零 UI 耦合内核包：
- 仅依赖 Python 标准库（dataclasses / enum / datetime / logging / random / typing / re）
- 不依赖 numpy / pandas / tkinter 或任何 src.* 模块
- 算法行为与 src/ 对应实现逐位等价（由 tests/test_core_*.py 保证）
"""

from .data_models import (
    ScoringType,
    EventStatus,
    Competitor,
    Judge,
    Dance,
    Event,
    ScoreRecord,
    Result,
    CompetitionResult,
    Competition,
)
from .skating_details import SkatingScoreDetail, SkatingOverallDetail
from .skating_system import (
    validate_judges_scores,
    calculate_majority_counts,
    calculate_position_sum,
    calculate_total_sum,
    skating_system_ranking,
    determine_rank_position,
    compare_position_sums,
    find_decision_range,
    generate_detail_table,
    calculate_overall_ranking,
    generate_overall_ranking_table,
)
from .scoring import ScoringAlgorithm, get_scoring_algorithm
from .advancement import (
    snake_distribution,
    random_distribution,
    distribute_competitors_to_events,
    get_advancing_competitors,
)

__all__ = [
    # 数据模型
    "ScoringType", "EventStatus",
    "Competitor", "Judge", "Dance", "Event",
    "ScoreRecord", "Result", "CompetitionResult", "Competition",
    "SkatingScoreDetail", "SkatingOverallDetail",
    # 顺位法（Skating System）
    "validate_judges_scores", "calculate_majority_counts",
    "calculate_position_sum", "calculate_total_sum",
    "skating_system_ranking", "determine_rank_position",
    "compare_position_sums", "find_decision_range",
    "generate_detail_table", "calculate_overall_ranking",
    "generate_overall_ranking_table",
    # 评分
    "ScoringAlgorithm", "get_scoring_algorithm",
    # 晋级分组
    "snake_distribution", "random_distribution",
    "distribute_competitors_to_events", "get_advancing_competitors",
]

__version__ = "0.1.0"
