#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顺位法（Skating System）算法内核
从 src/algorithms/skating_system.py 提取；与 src/ 实现算法行为逐位等价。

差异（接口优化，行为不变）：
- 不依赖 pandas：generate_detail_table 返回 (rows, all_stats_data)，
  rows 为与原 DataFrame 行等价的 List[Dict[str, Any]]（列语义一致）。
- 调试 print 改为 logging.debug（返回值不受影响）。
- 移除仅用于手工验证的 test_with_markdown_table / verify_overall_ranking。
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("core.dancesport")


def validate_judges_scores(players: List[str], scores: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    """
    验证裁判评分的有效性
    - 必须给所有选手分配1~N的唯一名次
    - 无遗漏、无重复、名次范围合法

    Args:
        players: 选手ID列表
        scores: 原始评分数据 {裁判ID: {选手ID: 名次}}

    Returns:
        过滤后的有效评分数据
    """
    valid_scores = {}
    N = len(players)

    for judge_id, judge_scores in scores.items():
        # 检查是否给所有选手打分
        if len(judge_scores) != N or any(p not in judge_scores for p in players):
            continue

        # 检查名次范围是否合法（1~N）
        ranks = list(judge_scores.values())
        if min(ranks) < 1 or max(ranks) > N:
            continue

        # 检查名次是否唯一（无重复）
        if len(set(ranks)) != N:
            continue

        valid_scores[judge_id] = judge_scores

    return valid_scores


def calculate_majority_counts(players: List[str], scores: Dict[str, Dict[str, int]],
                             position: int) -> Dict[str, int]:
    """
    计算每个选手在指定名次及以下获得的票数

    Args:
        players: 选手ID列表
        scores: 有效评分数据
        position: 名次位置（如1表示第1名，2表示第2名及以下）

    Returns:
        每个选手在该名次及以下获得的票数
    """
    counts = {player: 0 for player in players}

    for player in players:
        for judge in scores:
            if scores[judge][player] <= position:
                counts[player] += 1

    return counts


def calculate_position_sum(players: List[str], scores: Dict[str, Dict[str, int]],
                          position: int) -> Dict[str, int]:
    """
    计算每个选手在指定名次及以下的区间名次和（只考虑给出≤position排名的裁判）

    Args:
        players: 选手ID列表
        scores: 有效评分数据
        position: 名次位置

    Returns:
        每个选手在该名次及以下的区间名次和
    """
    sums = {player: 0 for player in players}

    for player in players:
        for judge in scores:
            if scores[judge][player] <= position:
                sums[player] += scores[judge][player]

    return sums


def calculate_total_sum(players: List[str], scores: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    """
    计算每个选手的总名次和（所有裁判的评分总和）

    Args:
        players: 选手ID列表
        scores: 有效评分数据

    Returns:
        每个选手的总名次和
    """
    sums = {player: 0 for player in players}

    for player in players:
        for judge in scores:
            sums[player] += scores[judge][player]

    return sums


def skating_system_ranking(players: List[str], scores: Dict[str, Dict[str, int]],
                           player_backnum_map: Dict[str, Any] = None) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    使用滑冰系统计算选手排名

    Args:
        players: 选手ID列表
        scores: 有效评分数据
        player_backnum_map: 选手ID到背号的映射（可选，用于调试输出）

    Returns:
        (排名结果, 决胜区间)
        排名结果: {选手ID: 最终名次}
        决胜区间: {选手ID: 决胜区间}
    """
    if not scores:
        raise ValueError("没有有效的裁判评分数据")

    num_judges = len(scores)
    majority_threshold = num_judges // 2 + 1  # 过半数阈值
    num_players = len(players)

    rankings = {}
    decision_ranges = {}
    remaining_players = players.copy()
    current_rank = 1

    logger.debug("滑冰系统排名开始: 选手数量=%s, 裁判数量=%s, 多数票阈值=%s",
                 num_players, num_judges, majority_threshold)

    # 主排名流程
    while remaining_players:
        logger.debug("确定第 %s 名, 剩余选手: %s", current_rank, remaining_players)

        # 名次确定流程
        winner = determine_rank_position(current_rank, remaining_players, scores, majority_threshold, num_players)

        logger.debug("第 %s 名确定: %s", current_rank,
                     player_backnum_map[winner] if player_backnum_map else winner)

        # 确定获胜者的决胜区间
        decision_range = find_decision_range(winner, scores, majority_threshold, num_players)
        decision_ranges[winner] = decision_range

        # 设置排名并从剩余选手中移除
        rankings[winner] = current_rank
        remaining_players.remove(winner)

        current_rank += 1

    logger.debug("滑冰系统排名完成")
    return rankings, decision_ranges


def determine_rank_position(target_rank: Optional[int], remaining_players: List[str],
                           scores: Dict[str, Dict[str, int]], majority_threshold: int,
                           num_players: int, position: int = 1) -> str:
    """
    名次确定流程

    Args:
        target_rank: 目标名次
        remaining_players: 未排名选手列表
        scores: 有效评分数据
        majority_threshold: 多数票阈值
        num_players: 选手总数
        position: 当前名次范围上限

    Returns:
        确定名次的选手
    """
    # 计算当前名次及以下的多数票
    majority_counts = calculate_majority_counts(remaining_players, scores, position)

    # 找出获得多数票的选手
    candidates = [p for p in remaining_players if majority_counts[p] >= majority_threshold]

    if len(candidates) == 1:
        # 情况一：单个选手获得多数票
        return candidates[0]
    elif len(candidates) == 0:
        # 情况二：无选手获得多数票
        if position < num_players:
            # 扩大名次范围
            return determine_rank_position(target_rank, remaining_players, scores,
                                          majority_threshold, num_players, position + 1)
        else:
            # 当position=num_players时，理论上不应该出现这种情况
            # 但为了代码健壮性，使用总名次和作为决胜条件
            total_sums = calculate_total_sum(remaining_players, scores)
            return min(total_sums, key=total_sums.get)
    else:
        # 情况三：多个选手获得多数票
        return compare_position_sums(candidates, scores, majority_threshold,
                                    num_players, position)


def compare_position_sums(candidates: List[str], scores: Dict[str, Dict[str, int]],
                         majority_threshold: int, num_players: int, position: int) -> str:
    """
    名次和比较流程

    Args:
        candidates: 获得多数票的选手列表
        scores: 有效评分数据
        majority_threshold: 多数票阈值
        num_players: 选手总数
        position: 当前名次范围上限

    Returns:
        排名最高的选手
    """
    # 第一轮：多数票数量比较（根据Skating System官方规则）
    majority_counts = {}
    for player in candidates:
        majority_count = sum(1 for judge in scores if scores[judge][player] <= position)
        majority_counts[player] = majority_count

    max_majority = max(majority_counts[p] for p in candidates)
    best_candidates = [p for p in candidates if majority_counts[p] == max_majority]

    logger.debug("名次和比较流程 (position=%s): 候选=%s 多数票=%s 最佳候选=%s",
                 position, candidates, majority_counts, best_candidates)

    if len(best_candidates) == 1:
        return best_candidates[0]

    # 第二轮：总名次和比较
    total_sums = calculate_total_sum(best_candidates, scores)
    min_total_sum = min(total_sums[p] for p in best_candidates)
    final_candidates = [p for p in best_candidates if total_sums[p] == min_total_sum]

    logger.debug("总名次和=%s 最终候选=%s", total_sums, final_candidates)

    if len(final_candidates) == 1:
        return final_candidates[0]

    # 第三轮：区间名次和比较
    position_sums = calculate_position_sum(final_candidates, scores, position)
    min_position_sum = min(position_sums[p] for p in final_candidates)
    final_candidates = [p for p in final_candidates if position_sums[p] == min_position_sum]

    logger.debug("区间名次和=%s 最终候选=%s", position_sums, final_candidates)

    if len(final_candidates) == 1:
        return final_candidates[0]

    # 如果仍然相同，扩大名次范围重新计算
    if position < num_players:
        logger.debug("扩大名次范围至 %s 重新计算", position + 1)
        return determine_rank_position(None, final_candidates, scores,
                                      majority_threshold, num_players, position + 1)
    else:
        # 当position=num_players时，使用总名次和作为决胜条件
        return min(final_candidates, key=lambda p: total_sums[p])


def find_decision_range(player: str, scores: Dict[str, Dict[str, int]],
                       majority_threshold: int, num_players: int) -> int:
    """
    找到选手获得多数票的最小区间作为决胜区间

    Args:
        player: 选手ID
        scores: 有效评分数据
        majority_threshold: 多数票阈值
        num_players: 选手总数

    Returns:
        决胜区间
    """
    for i in range(1, num_players + 1):
        majority_count = sum(1 for j in scores if scores[j][player] <= i)
        if majority_count >= majority_threshold:
            return i

    # 如果没有找到获得多数票的区间，使用num_players-1作为决胜区间
    return num_players - 1


def _range_columns(num_players: int) -> List[str]:
    """区间列名：["1", "1-2", ..., "1-N"]"""
    return ["1"] + ["1-{0}".format(i) for i in range(2, num_players + 1)]


def generate_detail_table(players: List[str], scores: Dict[str, Dict[str, int]],
                          player_backnum_map: Dict[str, Any] = None
                          ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    生成滑冰系统明细表（纯 Python 版，无 pandas）

    与 src.generate_detail_table 等价：单元格语义、列名、排序、
    "决胜区间后置空"、"0置空"、以及"最后一列仅剩单个值时置空"的
    后处理规则完全一致。

    Args:
        players: 选手ID列表
        scores: 原始评分数据
        player_backnum_map: 选手ID到背号的映射

    Returns:
        (rows, all_stats_data)
        rows: 明细行列表（每行为 {列名: 值}），按背号排序，
              列顺序与原 DataFrame 一致：["背号"] + 裁判列 + 区间列 + ["名次"]
        all_stats_data: 所有统计数据（与 src 完全一致的结构）
    """
    # 验证并过滤评分数据
    valid_scores = validate_judges_scores(players, scores)

    if not valid_scores:
        raise ValueError("没有有效的裁判评分数据")

    # 计算排名和决胜区间
    rankings, decision_ranges = skating_system_ranking(players, valid_scores)

    # 如果没有提供背号映射，使用选手ID作为背号
    if player_backnum_map is None:
        player_backnum_map = {p: p for p in players}

    # 获取裁判ID列表
    judge_ids = list(valid_scores.keys())
    num_judges = len(valid_scores)
    majority_threshold = num_judges // 2 + 1
    num_players = len(players)

    # 创建区间列名
    range_columns = _range_columns(num_players)

    # 计算每个选手的区间统计
    range_stats = {}
    for player in players:
        stats = {}
        decision_range = decision_ranges[player]

        for i in range(1, num_players + 1):
            # 统计名次≤i的裁判次数
            count = sum(1 for judge in valid_scores if valid_scores[judge][player] <= i)
            range_name = "1" if i == 1 else "1-{0}".format(i)

            # 只在决胜区间及之前显示统计，否则显示空字符串
            if i <= decision_range:
                stats[range_name] = str(count)
            else:
                stats[range_name] = ""

        range_stats[player] = stats

    # 判断是否需要使用"多数票数量(区间名次和)"格式的辅助函数
    def needs_position_sum_format(player: str) -> bool:
        """判断选手是否需要使用"多数票数量(区间名次和)"格式"""
        decision_range = decision_ranges[player]

        # 计算该选手在决胜区间的多数票数量
        majority_count = sum(1 for judge in valid_scores if valid_scores[judge][player] <= decision_range)

        # 找出所有在决胜区间获得相同多数票数量的选手
        same_majority_players = []
        for other_player in players:
            if other_player != player:
                other_majority = sum(1 for judge in valid_scores if valid_scores[judge][other_player] <= decision_range)
                if other_majority == majority_count:
                    same_majority_players.append(other_player)

        # 如果没有其他选手有相同的多数票数量，则不需要特殊格式
        if not same_majority_players:
            return False

        # 检查总名次和是否相同
        player_total_sum = calculate_total_sum([player], valid_scores)[player]
        for other_player in same_majority_players:
            other_total_sum = calculate_total_sum([other_player], valid_scores)[other_player]
            if player_total_sum != other_total_sum:
                return False

        # 检查区间名次和是否不同（如果相同，则无法通过区间名次和决胜）
        player_position_sum = calculate_position_sum([player], valid_scores, decision_range)[player]
        for other_player in same_majority_players:
            other_position_sum = calculate_position_sum([other_player], valid_scores, decision_range)[other_player]
            if player_position_sum != other_position_sum:
                return True  # 需要使用区间名次和决胜

        return False

    # 构建数据行
    rows = []
    # 收集所有统计数据，用于保存到后台
    all_stats_data = {}

    for player in players:
        row = {
            "背号": player_backnum_map[player],
            "名次": rankings[player]
        }

        # 添加裁判打分
        judge_scores = {}
        for judge in judge_ids:
            score = valid_scores[judge][player]
            row[judge] = score
            judge_scores[judge] = score

        # 添加区间统计
        decision_range = decision_ranges[player]
        needs_special_format = needs_position_sum_format(player)

        # 收集区间统计数据
        player_range_stats = {}
        for range_col in range_columns:
            # 提取区间数字
            if range_col == "1":
                range_num = 1
            else:
                range_num = int(range_col.split("-")[1])

            if range_num <= decision_range:
                if range_num == decision_range and needs_special_format:
                    # 在决胜区间显示"多数票数量(区间名次和)"格式
                    majority_count = sum(1 for judge in valid_scores if valid_scores[judge][player] <= decision_range)
                    position_sum = calculate_position_sum([player], valid_scores, decision_range)[player]
                    row[range_col] = "{0}({1})".format(majority_count, position_sum)
                    player_range_stats[range_col] = {
                        "count": majority_count,
                        "position_sum": position_sum,
                        "formatted": "{0}({1})".format(majority_count, position_sum)
                    }
                else:
                    row[range_col] = range_stats[player][range_col]
                    player_range_stats[range_col] = {
                        "count": int(range_stats[player][range_col]) if range_stats[player][range_col] else 0,
                        "formatted": range_stats[player][range_col]
                    }
            else:
                row[range_col] = ""
                player_range_stats[range_col] = {
                    "count": 0,
                    "formatted": ""
                }

        # 收集所有统计数据
        all_stats_data[player] = {
            "competitor_number": player_backnum_map[player],
            "rank": rankings[player],
            "decision_range": decision_range,
            "judge_scores": judge_scores,
            "range_stats": player_range_stats,
            "needs_special_format": needs_special_format
        }

        rows.append(row)

    # 组合列顺序（与原 DataFrame 一致）
    target_columns = ["背号"] + judge_ids + range_columns + ["名次"]

    # 按背号排序（与 df.sort_values("背号") 等价）
    rows.sort(key=lambda r: r["背号"])

    # --- 后处理 1：决胜区间列为字符串类型，"0" 置空 ---
    for row in rows:
        for col in range_columns:
            value = str(row[col])
            if value == "0":
                value = ""
            elif value == "nan":
                value = ""
            row[col] = value

    # --- 后处理 2：决胜区间后的所有列置空 ---
    for row in rows:
        # 找到对应的选手ID
        player_id = None
        for pid, backnum in player_backnum_map.items():
            if backnum == row["背号"]:
                player_id = pid
                break

        if player_id:
            decision_range = decision_ranges.get(player_id, 0)
            # 将决胜区间后的所有列设为空
            for i in range(decision_range + 1, num_players + 1):
                col_name = "1" if i == 1 else "1-{0}".format(i)
                if col_name in target_columns:
                    row[col_name] = ""

    # --- 后处理 3：从最后一列开始向前，若某区间内仅当前选手有数据则置空 ---
    for row in rows:
        # 从最后一列开始向前查找第一个有数据的区间
        last_data_col = None

        for i in range(len(range_columns) - 1, -1, -1):
            col_name = range_columns[i]
            if col_name in target_columns:
                cell_value = row[col_name]
                # 检查单元格是否有有效数据（非空且不是nan）
                if cell_value and cell_value != "" and cell_value != "nan":
                    last_data_col = col_name
                    break

        # 如果找到了最后一个有数据的列
        if last_data_col is not None:
            # 检查该列中所有选手的数据，看是否只有当前选手有数据
            only_one_value = True
            for other_row in rows:
                if other_row is row:
                    continue
                other_value = other_row[last_data_col]
                # 如果其他选手在这一列也有数据，则不是唯一值
                if other_value and other_value != "" and other_value != "nan":
                    only_one_value = False
                    break

            # 如果只有当前选手在这一列有数据，则清空该值
            if only_one_value:
                row[last_data_col] = ""

    return rows, all_stats_data


def parse_markdown_table(markdown_text: str) -> Tuple[Dict[str, Dict[str, int]], List[List[str]], List[str]]:
    """
    解析Markdown格式的表格文本，提取裁判打分和目标表格数据

    Args:
        markdown_text: Markdown格式的表格文本

    Returns:
        (原始裁判打分, 目标表格数据, 列名)
        原始裁判打分: {裁判ID: {选手ID: 名次}}
        目标表格数据: 二维列表，每行代表一个选手的数据
        列名: 表格列名列表
    """
    # 分割行
    lines = markdown_text.strip().split('\n')

    # 提取表头
    header_line = lines[0]
    columns = [col.strip() for col in header_line.split('|')[1:-1]]  # 去掉首尾空元素

    # 找到分隔线
    separator_line = lines[1]

    # 提取数据行
    data_rows = []
    for line in lines[2:]:
        if line.strip():
            row_data = [cell.strip() for cell in line.split('|')[1:-1]]  # 去掉首尾空元素
            data_rows.append(row_data)

    # 提取背号和选手ID映射
    player_backnum_map = {}
    player_ids = []
    for i, row in enumerate(data_rows):
        backnum = int(row[0])
        player_id = "P{0}".format(i + 1)  # 生成选手ID
        player_backnum_map[player_id] = backnum
        player_ids.append(player_id)

    # 提取裁判ID列表（从背号列之后到1列之前）
    judge_start_idx = 1  # 背号列之后
    judge_end_idx = columns.index("1")  # 1列之前
    judge_ids = columns[judge_start_idx:judge_end_idx]

    # 构建原始裁判打分
    raw_scores = {}
    for j, judge_id in enumerate(judge_ids):
        judge_scores = {}
        for i, player_id in enumerate(player_ids):
            rank = int(data_rows[i][judge_start_idx + j])
            judge_scores[player_id] = rank
        raw_scores[judge_id] = judge_scores

    # 构建目标表格数据（确保决胜区间计分为字符串）
    target_data = []
    for i, row in enumerate(data_rows):
        target_row = []
        for j, cell in enumerate(row):
            if j >= judge_start_idx and j < judge_end_idx:
                # 裁判打分列，保持为整数
                target_row.append(int(cell) if cell else "")
            elif j >= judge_end_idx:
                # 决胜区间计分列，转换为字符串
                target_row.append(cell if cell else "")
            else:
                # 背号列，保持为整数
                target_row.append(int(cell) if cell else "")
        target_data.append(target_row)

    return raw_scores, target_data, columns


def calculate_overall_ranking(dance_rankings: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, Any]]:
    """
    计算综合总名次

    将每对选手在所有舞的名次进行"序和"相加，序和越小，总排名越前；
    同序和者并列（名次相同并顺延）。

    Args:
        dance_rankings: 各舞种的名次字典 {舞种: {背号: 名次}}

    Returns:
        综合名次字典 {背号: {"综合得分": int, "最终名次": int}}
    """
    # 获取所有选手背号
    all_players = set()
    for dance, rankings in dance_rankings.items():
        all_players.update(rankings.keys())
    all_players = sorted(all_players)

    # 计算每个选手的总序和
    player_sums = {}
    for player in all_players:
        total_sum = 0
        for dance, rankings in dance_rankings.items():
            if player in rankings:
                total_sum += rankings[player]
        player_sums[player] = total_sum

    # 初始排名（按总序和）
    sorted_players = sorted(all_players, key=lambda p: player_sums[p])

    # 处理并列情况
    final_rankings = {}
    current_rank = 1
    i = 0

    while i < len(sorted_players):
        # 找出所有总序和相同的选手
        tied_players = [sorted_players[i]]
        j = i + 1
        while j < len(sorted_players) and player_sums[sorted_players[j]] == player_sums[sorted_players[i]]:
            tied_players.append(sorted_players[j])
            j += 1

        if len(tied_players) == 1:
            # 没有并列，直接分配名次
            player = tied_players[0]
            final_rankings[player] = {
                "综合得分": player_sums[player],
                "最终名次": current_rank
            }
            current_rank += 1
        else:
            # 有并列，所有并列选手获得相同的名次（当前名次）
            for player in tied_players:
                final_rankings[player] = {
                    "综合得分": player_sums[player],
                    "最终名次": current_rank
                }

            # 名次顺延：跳过这些选手占用的名次数
            current_rank += len(tied_players)

        i = j

    return final_rankings


def generate_overall_ranking_table(overall_rankings: Dict[str, Dict[str, Any]]) -> str:
    """
    生成综合名次表字符串

    Args:
        overall_rankings: 综合名次字典 {背号: {"综合得分": int, "最终名次": int}}

    Returns:
        综合名次表字符串
    """
    # 按最终名次排序
    sorted_players = sorted(overall_rankings.items(), key=lambda x: x[1]["最终名次"])

    # 构建表格
    table_lines = []
    table_lines.append("| 背号  | 综合得分 | 最终名次  |")
    table_lines.append("| --- | ---- | ----- |")

    for player, data in sorted_players:
        backnum = player
        score = data["综合得分"]
        rank = data["最终名次"]

        # 根据背号位数调整空格数量
        backnum_str = str(backnum)
        if len(backnum_str) == 2:
            backnum_str = "{0} ".format(backnum_str)
        else:
            backnum_str = "{0}".format(backnum_str)

        # 根据得分位数调整空格数量
        score_str = str(score)
        if len(score_str) == 1:
            score_str = "{0}   ".format(score_str)
        elif len(score_str) == 2:
            score_str = "{0}  ".format(score_str)

        # 添加名次描述
        rank_desc = str(rank)
        if rank == 1:
            rank_desc = "{0}（冠军）".format(rank)
        elif rank == 2:
            rank_desc = "{0}（亚军）".format(rank)
        elif rank == 3:
            rank_desc = "{0}（季军）".format(rank)
        else:
            rank_desc = "{0}    ".format(rank)

        table_lines.append("| {0} | {1} | {2} |".format(backnum_str, score_str, rank_desc))

    return "\n".join(table_lines)
