#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
晋级分组算法内核
从 src/algorithms/advancement.py 提取；算法行为与 src/ 逐位等价。

差异（接口优化，行为不变）：
- 不依赖 src.utils.logger（改用标准 logging）
- random_distribution / distribute_competitors_to_events 增加可选 rng 参数
  （默认仍使用全局 random 模块，行为与 src 完全一致）
- get_advancing_competitors 保持 duck-typed data_manager 参数，零 UI 耦合
"""

import logging
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger("core.dancesport")


def snake_distribution(competitors: List[Any], group_count: int) -> Dict[int, List[Any]]:
    """
    蛇形排列法分配选手到各组

    Args:
        competitors: 选手背番号列表（已按成绩排序）
        group_count: 组数

    Returns:
        Dict[int, List]: 组号到选手列表的映射
    """
    if not competitors or group_count <= 0:
        return {}

    # 初始化各组
    groups = {i: [] for i in range(group_count)}

    # 蛇形分配
    for i, competitor in enumerate(competitors):
        group_index = i % group_count

        # 奇数轮（第1, 3, 5...轮）正向分配
        # 偶数轮（第2, 4, 6...轮）反向分配
        round_num = i // group_count
        if round_num % 2 == 1:
            # 偶数轮反向分配
            group_index = group_count - 1 - (i % group_count)

        groups[group_index].append(competitor)

    logger.debug("蛇形分配完成: %s名选手分配到%s组", len(competitors), group_count)
    return groups


def random_distribution(competitors: List[Any], group_count: int,
                        rng: Optional[random.Random] = None) -> Dict[int, List[Any]]:
    """
    随机分配法分配选手到各组

    Args:
        competitors: 选手背番号列表
        group_count: 组数
        rng: 可选的 random.Random 实例（用于可复现随机；缺省用全局 random 模块，
             与 src 行为完全一致）

    Returns:
        Dict[int, List]: 组号到选手列表的映射
    """
    if not competitors or group_count <= 0:
        return {}

    shuffler = rng if rng is not None else random

    # 随机打乱选手顺序
    shuffled_competitors = competitors.copy()
    shuffler.shuffle(shuffled_competitors)

    # 初始化各组
    groups = {i: [] for i in range(group_count)}

    # 轮流分配选手到各组
    for i, competitor in enumerate(shuffled_competitors):
        group_index = i % group_count
        groups[group_index].append(competitor)

    logger.debug("随机分配完成: %s名选手分配到%s组", len(competitors), group_count)
    return groups


def distribute_competitors_to_events(
    competitors: List[Any],
    events: List[Any],
    method: str = "snake",
    rng: Optional[random.Random] = None
) -> Dict[str, List[Any]]:
    """
    将选手分配到各个场次

    Args:
        competitors: 选手背番号列表（已按成绩排序）
        events: 场次列表（需要具有 id 属性）
        method: 分配方法，"snake"或"random"
        rng: 可选的 random.Random 实例（仅 random 方法使用）

    Returns:
        Dict[str, List]: 场次ID到选手列表的映射
    """
    if not competitors or not events:
        return {}

    # 按场次ID排序，确保分配顺序一致
    sorted_events = sorted(events, key=lambda e: e.id)
    group_count = len(sorted_events)

    # 根据方法选择分配算法
    if method == "snake":
        groups = snake_distribution(competitors, group_count)
    elif method == "random":
        groups = random_distribution(competitors, group_count, rng=rng)
    else:
        logger.error("未知的分配方法: %s", method)
        return {}

    # 将组号映射到场次ID
    event_assignments = {}
    for i, event in enumerate(sorted_events):
        event_assignments[event.id] = groups.get(i, [])

    logger.debug("选手分配完成: 使用%s方法分配到%s个场次", method, group_count)
    return event_assignments


def get_advancing_competitors(project_id: str, round: str, data_manager: Any) -> List[Any]:
    """
    获取指定项目和轮次的所有晋级选手

    Args:
        project_id: 项目编号
        round: 轮次
        data_manager: 数据管理器实例（duck-typed，需要
            get_events_by_project_and_round / get_results 方法）

    Returns:
        List: 晋级选手背番号列表（按成绩排序）
    """
    # 获取该轮次的所有场次
    events = data_manager.get_events_by_project_and_round(project_id, round)
    if not events:
        return []

    # 收集所有晋级的选手
    advancing_competitors = set()

    for event in events:
        # 获取场次结果
        result = data_manager.get_results(event.id)
        if not result:
            continue

        results_data = result.results_data

        # 从结果中获取晋级选手
        if 'overall_results' in results_data:
            overall_results = results_data['overall_results']
            # 筛选晋级状态为True的选手
            for result_item in overall_results:
                # 处理字典格式的结果项
                if isinstance(result_item, dict):
                    if result_item.get('advancement_status', False):
                        advancing_competitors.add(result_item.get('competitor_number'))
                else:
                    # 处理对象格式的结果项
                    if result_item.advancement_status:
                        advancing_competitors.add(result_item.competitor_number)

    # 获取选手成绩信息并排序
    competitor_scores = {}
    for event in events:
        result = data_manager.get_results(event.id)
        if not result:
            continue

        results_data = result.results_data

        if 'overall_results' in results_data:
            overall_results = results_data['overall_results']
            for result_item in overall_results:
                # 处理字典格式的结果项
                if isinstance(result_item, dict):
                    if result_item.get('advancement_status', False):
                        competitor_scores[result_item.get('competitor_number')] = result_item.get('total_score', result_item.get('score', 0))
                else:
                    # 处理对象格式的结果项
                    if result_item.advancement_status:
                        competitor_scores[result_item.competitor_number] = result_item.total_score

    # 按成绩从高到低排序（Mark制分数越高越好）
    sorted_competitors = sorted(
        advancing_competitors,
        key=lambda x: competitor_scores.get(x, 0),
        reverse=True
    )

    logger.debug("获取晋级选手完成: 项目%s轮次%s共%s名选手晋级", project_id, round, len(sorted_competitors))
    return sorted_competitors
