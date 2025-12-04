#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评分算法模块
实现Mark制和顺位法评分算法
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
from collections import defaultdict

from ..models.data_models import ScoreRecord, Result, ScoringType
from ..models.skating_score_details import SkatingScoreDetail, SkatingOverallDetail
from ..utils.logger import get_logger

logger = get_logger()


class ScoringAlgorithm:
    """评分算法类"""
    
    def __init__(self):
        """初始化评分算法"""
        self.logger = logger
        self.advancement_rule = "all_tied_advance"  # 默认晋级规则：同分者全部晋级
        # 导入滑冰系统算法
        try:
            from .skating_system import skating_system_ranking, generate_detail_table, calculate_overall_ranking
            self.skating_system_available = True
        except ImportError:
            self.logger.warning("无法导入滑冰系统算法，将使用基本算法")
            self.skating_system_available = False
        
    def set_advancement_rule(self, rule: str):
        """
        设置晋级规则
        
        Args:
            rule: 晋级规则
                - "all_tied_advance": 同分者全部晋级（即使超出原定晋级人数）
                - "strict_count": 严格按照晋级人数，同分者通过其他规则决定
        """
        valid_rules = ["all_tied_advance", "strict_count"]
        if rule in valid_rules:
            self.advancement_rule = rule
            self.logger.info(f"已设置晋级规则: {rule}")
        else:
            self.logger.warning(f"无效的晋级规则: {rule}，使用默认规则: all_tied_advance")
    
    def calculate_advancement(self, results: List[Result], advancement_count: int) -> List[Result]:
        """
        计算选手晋级状态
        
        Args:
            results: 已排序的结果列表（按排名升序）
            advancement_count: 计划晋级人数
            
        Returns:
            更新后的结果列表，包含晋级状态和并列信息
        """
        if not results or advancement_count <= 0:
            return results
            
        # 按分数排序（对于不同评分类型可能有不同的排序规则）
        # 假设传入的results已经按正确顺序排列
        
        # 初始化并列信息
        self._mark_tied_results(results)
        
        # 根据晋级规则计算晋级状态
        if self.advancement_rule == "all_tied_advance":
            return self._calculate_advancement_all_tied_advance(results, advancement_count)
        else:
            return self._calculate_advancement_strict_count(results, advancement_count)
    
    def _mark_tied_results(self, results: List[Result]):
        """
        标记并列选手
        
        Args:
            results: 结果列表
        """
        # 重置所有并列信息
        for result in results:
            result.tied_with = []
        
        # 标记并列
        i = 0
        while i < len(results):
            current_score = results[i].total_score
            tied_indices = [i]
            
            # 找出所有同分的结果
            j = i + 1
            while j < len(results) and results[j].total_score == current_score:
                tied_indices.append(j)
                j += 1
            
            # 如果有并列
            if len(tied_indices) > 1:
                for idx in tied_indices:
                    # 为每个并列选手添加其他并列选手的背番号
                    for other_idx in tied_indices:
                        if idx != other_idx:
                            results[idx].tied_with.append(results[other_idx].competitor_number)
            
            i = j
    
    def _calculate_advancement_all_tied_advance(self, results: List[Result], advancement_count: int) -> List[Result]:
        """
        同分者全部晋级规则
        
        Args:
            results: 结果列表
            advancement_count: 计划晋级人数
            
        Returns:
            更新后的结果列表
        """
        # 首先找出所有同分组
        tied_groups = []
        processed_indices = set()
        
        for i in range(len(results)):
            if i in processed_indices:
                continue
                
            current_score = results[i].total_score
            current_group = [i]
            processed_indices.add(i)
            
            # 找出所有同分的选手
            for j in range(i + 1, len(results)):
                if j not in processed_indices and results[j].total_score == current_score:
                    current_group.append(j)
                    processed_indices.add(j)
            
            tied_groups.append(current_group)
        
        # 确定晋级组
        advancing_indices = set()
        count_so_far = 0
        
        for group in tied_groups:
            group_size = len(group)
            
            # 如果整个组都能晋级，或者组内部分选手已经达到晋级线
            if count_so_far < advancement_count:
                # 如果添加这组后不会超过晋级名额太多，或者组内已有选手在晋级线内
                if count_so_far + group_size <= advancement_count or count_so_far < advancement_count:
                    # 整组晋级
                    for idx in group:
                        advancing_indices.add(idx)
            
            count_so_far += group_size
        
        # 设置晋级状态
        for i, result in enumerate(results):
            result.advancement_status = i in advancing_indices
            
        return results
    
    def _calculate_advancement_strict_count(self, results: List[Result], advancement_count: int) -> List[Result]:
        """
        严格按照晋级人数规则
        
        Args:
            results: 结果列表
            advancement_count: 计划晋级人数
            
        Returns:
            更新后的结果列表
        """
        for i, result in enumerate(results):
            if i < advancement_count:
                result.advancement_status = True
            else:
                result.advancement_status = False
        
        return results
    
    def calculate_results(
        self, 
        score_records: List[ScoreRecord], 
        scoring_type: ScoringType,
        advancement_count: Optional[int] = None,
        advancement_rule: Optional[str] = None,
        all_competitors: Optional[List[int]] = None
    ) -> Tuple[bool, Dict[str, List[Result]], List[str], Optional[Dict], Optional[Dict]]:
        """
        计算结果
        
        Args:
            score_records: 评分记录列表
            scoring_type: 评分类型
            advancement_count: 晋级人数（可选）
            advancement_rule: 晋级规则（可选）
            all_competitors: 所有参赛选手背番号列表（可选，用于确保所有选手都被包含在结果中）
            
        Returns:
            (是否成功, 计算结果字典, 错误信息列表, 打分明细, 综合打分明细)
            结果字典格式: {
                "dance_results": {舞种名: [Result对象]},
                "overall_results": [Result对象]
            }
            打分明细格式: {舞种名: {选手编号: SkatingScoreDetail}}
            综合打分明细格式: {选手编号: SkatingOverallDetail}
        """
        errors = []
        score_details = None
        overall_score_details = None
        
        # 验证评分记录
        if not score_records:
            errors.append("没有评分记录")
            return False, {}, errors, None, None
        
        # 验证评分记录有效性
        is_valid, validation_errors = self.validate_scores(score_records, scoring_type)
        if not is_valid:
            errors.extend(validation_errors)
            return False, {}, errors, None, None
        
        try:
            if scoring_type == ScoringType.MARK:
                dance_results = self._calculate_mark_results(score_records, all_competitors)
            elif scoring_type == ScoringType.SKATING:
                # 使用新的滑冰系统计算
                dance_results, score_details = self._calculate_skating_results(score_records, all_competitors)
            else:
                errors.append(f"不支持的评分类型: {scoring_type}")
                return False, {}, errors, None, None
            
            # 按舞种分组结果
            dance_results_by_dance = defaultdict(list)
            for result in dance_results:
                dance_results_by_dance[result.dance_name].append(result)
            
            # 计算综合结果
            overall_results = self.calculate_overall_results(dance_results, scoring_type, all_competitors, score_details)
            
            # 如果是顺位制且有打分明细，获取综合打分明细（不再重复计算排名）
            if scoring_type == ScoringType.SKATING and score_details and self.skating_system_available:
                overall_score_details = self._calculate_overall_score_details(score_details)
                
                # 注意：不再需要更新排名，因为已经在calculate_overall_results中处理了
                self.logger.debug("顺位制综合结果排名已在calculate_overall_results中处理")
            
            # 如果提供了晋级人数，则计算晋级状态
            if advancement_count is not None and advancement_count > 0:
                # 设置晋级规则，如果提供了的话
                if advancement_rule is not None:
                    self.set_advancement_rule(advancement_rule)
                    
                # 为综合结果计算晋级状态
                overall_results = self.calculate_advancement(overall_results, advancement_count)
                
                # 为每个舞种的结果计算晋级状态
                for dance_name, dance_results_list in dance_results_by_dance.items():
                    dance_results_by_dance[dance_name] = self.calculate_advancement(dance_results_list, advancement_count)
            
            # 构建结果字典
            results_dict = {
                "dance_results": dict(dance_results_by_dance),
                "overall_results": overall_results
            }
            
            return True, results_dict, errors, score_details, overall_score_details
        except Exception as e:
            errors.append(f"计算结果时发生错误: {str(e)}")
            self.logger.error(f"计算结果错误: {str(e)}")
            return False, {}, errors, None, None
    
    def _calculate_mark_results(self, score_records: List[ScoreRecord], all_competitors: Optional[List[int]] = None) -> List[Result]:
        """
        计算Mark制结果
        
        Args:
            score_records: 评分记录列表
            all_competitors: 所有参赛选手背番号列表（可选，用于确保所有选手都被包含在结果中）
            
        Returns:
            结果列表
        """
        self.logger.debug("开始计算Mark制结果")
        
        # 按舞种分组
        dance_scores = defaultdict(list)
        for record in score_records:
            if record.mark is not None:
                dance_scores[record.dance_name].append(record)
        
        # 获取所有舞种名称
        all_dance_names = set()
        for record in score_records:
            all_dance_names.add(record.dance_name)
        
        # 如果没有提供所有参赛选手列表，则从评分记录中提取
        if all_competitors is None:
            all_competitors = set()
            for record in score_records:
                all_competitors.add(record.competitor_number)
            all_competitors = list(all_competitors)
        
        results = []
        
        # 对每个舞种分别计算结果
        for dance_name in all_dance_names:
            # 按选手分组，计算每个选手的票数
            competitor_votes = defaultdict(int)
            competitor_count = defaultdict(int)
            
            # 只处理当前舞种的记录
            records = dance_scores.get(dance_name, [])
            for record in records:
                if record.mark is True:
                    competitor_votes[record.competitor_number] += 1
                competitor_count[record.competitor_number] += 1
            
            # 确保所有参赛选手都被包含在结果中
            for competitor_number in all_competitors:
                if competitor_number not in competitor_votes:
                    competitor_votes[competitor_number] = 0
                if competitor_number not in competitor_count:
                    competitor_count[competitor_number] = 0
            
            # 按票数排序
            sorted_competitors = sorted(
                competitor_votes.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            # 创建结果对象
            for rank, (competitor_number, votes) in enumerate(sorted_competitors, 1):
                result = Result(
                    event_id=score_records[0].event_id if score_records else "",  # 添加event_id参数
                    competitor_number=competitor_number,
                    dance_name=dance_name,
                    rank=rank,  # 临时排名，稍后通过_resolve_mark_ties处理同分
                    score=votes,  # 使用票数作为分数
                    total_score=votes  # Mark制中，票数即为总分
                )
                results.append(result)
            
            # 处理同分情况 - 为当前舞种的结果设置正确的排名
            dance_results = [r for r in results if r.dance_name == dance_name]
            # 按票数排序
            dance_results_sorted = sorted(dance_results, key=lambda x: x.total_score, reverse=True)
            # 处理同分
            dance_results_with_correct_ranks = self._resolve_mark_ties(dance_results_sorted)
            
            # 更新结果列表中的排名
            rank_map = {r.competitor_number: r.rank for r in dance_results_with_correct_ranks}
            for r in results:
                if r.dance_name == dance_name:
                    r.rank = rank_map[r.competitor_number]
        
        self.logger.debug(f"Mark制结果计算完成，共{len(results)}条结果")
        return results
    


    
    def calculate_overall_results(
        self, 
        dance_results: List[Result], 
        scoring_type: ScoringType,
        all_competitors: Optional[List[int]] = None,
        score_details: Optional[Dict[str, Dict[int, SkatingScoreDetail]]] = None
    ) -> List[Result]:
        """
        计算综合结果
        
        Args:
            dance_results: 各舞种结果列表
            scoring_type: 评分类型
            all_competitors: 所有参赛选手背番号列表（可选，用于确保所有选手都被包含在结果中）
            score_details: 打分明细字典（可选，用于顺位制综合结果计算）
            
        Returns:
            综合结果列表
        """
        self.logger.debug("开始计算综合结果")
        
        # 如果没有提供所有参赛选手列表，则从舞种结果中提取
        if all_competitors is None:
            all_competitors = set()
            for result in dance_results:
                all_competitors.add(result.competitor_number)
            all_competitors = list(all_competitors)
        
        # 按选手分组
        competitor_results = defaultdict(list)
        for result in dance_results:
            competitor_results[result.competitor_number].append(result)
        
        # 确保所有参赛选手都在结果中
        for competitor_number in all_competitors:
            if competitor_number not in competitor_results:
                competitor_results[competitor_number] = []
        
        overall_results = []
        
        # 计算每个选手的综合得分
        for competitor_number, results in competitor_results.items():
            if scoring_type == ScoringType.MARK:
                # Mark制：计算各舞种得票数的总和
                if results:
                    total_votes = sum(result.score for result in results)
                    # 计算平均票数（考虑舞种数量）
                    avg_votes = total_votes / len(results)
                else:
                    # 没有舞种结果的选手得分为0
                    total_votes = 0
                    avg_votes = 0
                
                overall_result = Result(
                    event_id=dance_results[0].event_id if dance_results else "",
                    competitor_number=competitor_number,
                    dance_name="综合",
                    rank=0,  # 排名将在排序后确定
                    score=avg_votes,
                    total_score=total_votes  # 总票数作为最终排名依据
                )
                overall_results.append(overall_result)
            else:
                # 顺位制：使用新的滑冰法计算综合结果
                # 这里我们不再计算总序和，而是使用滑冰法计算器来处理综合结果
                # 先创建一个临时的结果对象，稍后会被滑冰法计算器更新
                overall_result = Result(
                    event_id=dance_results[0].event_id if dance_results else "",
                    competitor_number=competitor_number,
                    dance_name="综合",
                    rank=0,  # 排名将在排序后确定
                    score=0,   # 分数将在滑冰法计算器中更新
                    total_score=0  # 总分将在滑冰法计算器中更新
                )
                overall_results.append(overall_result)
        
        # 如果是顺位制且有打分明细，使用滑冰系统算法计算综合结果
        if scoring_type == ScoringType.SKATING and score_details and self.skating_system_available:
            # 使用滑冰系统算法计算综合结果和排名
            overall_results = self._calculate_overall_results_with_skating_system(overall_results, score_details)
        else:
            # 对于Mark制或其他情况，按总分排序
            overall_results = sorted(overall_results, key=lambda x: x.total_score, reverse=True)
            # 处理同分情况
            if scoring_type == ScoringType.MARK:
                overall_results = self._resolve_mark_ties(overall_results)
            else:
                # 非Mark制的其他评分类型，设置简单排名
                for i, result in enumerate(overall_results):
                    result.rank = i + 1
        
        self.logger.debug(f"综合结果计算完成，共 {len(overall_results)} 名选手")
        return overall_results
    
    def validate_scores(self, score_records: List[ScoreRecord], scoring_type: ScoringType) -> Tuple[bool, List[str]]:
        """
        验证评分记录的有效性
        
        Args:
            score_records: 评分记录列表
            scoring_type: 评分类型
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        # 检查是否有评分记录
        if not score_records:
            errors.append("没有评分记录")
            return False, errors
        
        # 按舞种和裁判分组
        dance_judge_records = defaultdict(lambda: defaultdict(list))
        for record in score_records:
            dance_judge_records[record.dance_name][record.judge_id].append(record)
        
        # 检查每个舞种-裁判组合的评分
        for dance_name, judge_records in dance_judge_records.items():
            for judge_id, records in judge_records.items():
                # 检查是否有重复评分
                competitor_set = set(record.competitor_number for record in records)
                if len(competitor_set) != len(records):
                    errors.append(f"舞种 {dance_name} 裁判 {judge_id} 存在重复评分")
                
                # 检查评分类型一致性
                if scoring_type == ScoringType.MARK:
                    # Mark制：应该只使用mark字段
                    for record in records:
                        if record.mark is None:
                            errors.append(f"舞种 {dance_name} 裁判 {judge_id} 的评分记录缺少mark字段")
                        elif record.score is not None or record.placement is not None:
                            errors.append(f"舞种 {dance_name} 裁判 {judge_id} 的评分记录使用了错误的字段")
                elif scoring_type == ScoringType.SKATING:
                    # 顺位法：应该只使用placement字段
                    for record in records:
                        if record.placement is None:
                            errors.append(f"舞种 {dance_name} 裁判 {judge_id} 的评分记录缺少placement字段")
                        elif record.mark is not None or record.score is not None:
                            errors.append(f"舞种 {dance_name} 裁判 {judge_id} 的评分记录使用了错误的字段")
                    
                    # 检查顺位法的名次完整性
                    placements = [record.placement for record in records if record.placement is not None]
                    if placements:
                        # 检查是否有重复名次
                        placement_set = set(placements)
                        if len(placement_set) != len(placements):
                            duplicates = []
                            for placement in placement_set:
                                count = placements.count(placement)
                                if count > 1:
                                    duplicates.append(f"{placement}({count}次)")
                            errors.append(f"舞种 {dance_name} 裁判 {judge_id} 存在重复名次: {', '.join(duplicates)}")
                        
                        # 检查是否漏打名次
                        expected_placements = set(range(1, len(placements) + 1))
                        missing_placements = expected_placements - placement_set
                        if missing_placements:
                            errors.append(f"舞种 {dance_name} 裁判 {judge_id} 漏打名次: {sorted(missing_placements)}")
                        
                        # 检查是否有超出范围的名次
                        invalid_placements = [p for p in placements if p < 1 or p > len(placements)]
                        if invalid_placements:
                            errors.append(f"舞种 {dance_name} 裁判 {judge_id} 存在无效名次: {invalid_placements}")
        
        return len(errors) == 0, errors
    
    def _resolve_mark_ties(self, sorted_results: List[Result]) -> List[Result]:
        """
        解决Mark制同分问题
        
        Args:
            sorted_results: 按分数排序的结果列表
            
        Returns:
            处理同分后的结果列表
        """
        if not sorted_results:
            return []
        
        # 设置排名，处理同分情况
        rank = 1
        i = 0
        
        while i < len(sorted_results):
            current_result = sorted_results[i]
            current_score = current_result.total_score
            
            # 查找所有相同分数的选手
            tied_results = [current_result]
            j = i + 1
            
            while j < len(sorted_results) and sorted_results[j].total_score == current_score:
                tied_results.append(sorted_results[j])
                j += 1
            
            # 为所有同分选手设置相同排名
            for result in tied_results:
                result.rank = rank
            
            # 更新下一个排名
            rank += len(tied_results)
            i = j
        
        return sorted_results
    
    def _calculate_skating_results(self, score_records: List[ScoreRecord], all_competitors: Optional[List[str]] = None) -> Tuple[List[Result], Dict[str, Dict[str, SkatingScoreDetail]]]:
        """
        使用滑冰系统算法计算顺位制结果
        
        Args:
            score_records: 评分记录列表
            all_competitors: 所有参赛选手背番号列表（可选，用于确保所有选手都被包含在结果中）
            
        Returns:
            (结果列表, 打分明细字典)
            打分明细格式: {舞种名: {选手编号: SkatingScoreDetail}}
        """
        from .skating_system import validate_judges_scores, skating_system_ranking, generate_detail_table
        
        # 按舞种分组评分记录
        dance_records = defaultdict(list)
        for record in score_records:
            dance_records[record.dance_name].append(record)
        
        # 如果没有提供所有参赛选手列表，则从评分记录中提取
        if all_competitors is None:
            all_competitors = set()
            for record in score_records:
                all_competitors.add(str(record.competitor_number))
            all_competitors = list(all_competitors)
        else:
            # 确保所有参赛选手都是字符串类型
            all_competitors = [str(comp) for comp in all_competitors]
        
        results = []
        score_details = {}
        
        # 对每个舞种分别计算结果
        for dance_name, records in dance_records.items():
            # 按裁判分组评分记录
            judge_records = defaultdict(list)
            for record in records:
                judge_records[record.judge_id].append(record)
            
            # 构建滑冰系统算法需要的输入格式
            # {裁判ID: {选手ID: 名次}}
            players = all_competitors  # 已经是字符串列表
            scores = {}
            
            for judge_id, j_records in judge_records.items():
                judge_scores = {}
                for record in j_records:
                    judge_scores[str(record.competitor_number)] = record.placement
                scores[judge_id] = judge_scores
            
            # 验证评分数据
            valid_scores = validate_judges_scores(players, scores)
            
            if not valid_scores:
                self.logger.warning(f"舞种 {dance_name} 没有有效的裁判评分数据")
                continue
            
            # 计算排名
            player_backnum_map = {comp: comp for comp in all_competitors}
            rankings, decision_ranges = skating_system_ranking(players, valid_scores, player_backnum_map)
            
            # 创建结果对象
            for player_id, rank in rankings.items():
                competitor_number = player_id  # 直接使用字符串类型
                result = Result(
                    event_id=records[0].event_id if records else "",
                    competitor_number=competitor_number,
                    dance_name=dance_name,
                    rank=rank,
                    score=rank,  # 顺位制中，名次即为分数
                    total_score=rank  # 顺位制中，名次即为总分
                )
                results.append(result)
            
            # 生成明细表并创建打分明细
            try:
                detail_table, detail_stats = generate_detail_table(players, valid_scores, player_backnum_map)
                
                # 为每个选手创建打分明细
                dance_score_details = {}
                for player_id in players:
                    competitor_number = player_id  # 直接使用字符串类型
                    rank = rankings[player_id]
                    
                    # 获取裁判打分
                    judge_placements = {}
                    for judge_id, judge_scores in valid_scores.items():
                        judge_placements[judge_id] = judge_scores[player_id]
                    
                    # 计算名次出现次数
                    placement_counts = {}
                    for placement in judge_placements.values():
                        placement_counts[placement] = placement_counts.get(placement, 0) + 1
                    
                    # 计算累积得票数（1, 1-2, 1-3等列的内容）
                    cumulative_votes = {}
                    for position in range(1, len(players) + 1):
                        count = sum(1 for placement in judge_placements.values() if placement <= position)
                        cumulative_votes[position] = count
                    
                    # 计算序和
                    sum_placement = sum(judge_placements.values())
                    
                    # 获取多数裁决名次
                    majority_rank = None
                    for position in range(1, len(players) + 1):
                        if cumulative_votes[position] > len(valid_scores) // 2:
                            majority_rank = position
                            break
                    
                    # 获取区间统计信息
                    details = {}
                    if player_id in detail_stats:
                        details = {
                            "range_stats": detail_stats[player_id]["range_stats"],
                            "decision_range": detail_stats[player_id]["decision_range"],
                            "needs_special_format": detail_stats[player_id].get("needs_special_format", False)
                        }
                    else:
                        # 如果没有详细统计，使用原有的计算逻辑
                        decision_range = decision_ranges[player_id]
                        range_stats = {}
                        
                        # 计算每个区间的统计值
                        for i in range(1, len(players) + 1):
                            # 统计名次≤i的裁判次数
                            count = sum(1 for judge in valid_scores if valid_scores[judge][player_id] <= i)
                            range_name = "1" if i == 1 else f"1-{i}"
                            
                            # 只在决胜区间及之前显示统计，否则显示空字符串
                            if i <= decision_range:
                                # 检查是否需要特殊格式（多数票数量(区间名次和)）
                                if i == decision_range:
                                    # 计算该选手在决胜区间的多数票数量
                                    majority_count = sum(1 for judge in valid_scores if valid_scores[judge][player_id] <= decision_range)
                                    
                                    # 找出所有在决胜区间获得相同多数票数量的选手
                                    same_majority_players = []
                                    for other_player in players:
                                        if other_player != player_id:
                                            other_majority = sum(1 for judge in valid_scores if valid_scores[judge][other_player] <= decision_range)
                                            if other_majority == majority_count:
                                                same_majority_players.append(other_player)
                                    
                                    # 如果没有其他选手有相同的多数票数量，则不需要特殊格式
                                    if same_majority_players:
                                        # 检查总名次和是否相同
                                        player_total_sum = sum(valid_scores[judge][player_id] for judge in valid_scores)
                                        needs_special_format = False
                                        
                                        for other_player in same_majority_players:
                                            other_total_sum = sum(valid_scores[judge][other_player] for judge in valid_scores)
                                            if player_total_sum == other_total_sum:
                                                # 检查区间名次和是否不同
                                                from .skating_system import calculate_position_sum
                                                player_position_sum = calculate_position_sum([player_id], valid_scores, decision_range)[player_id]
                                                other_position_sum = calculate_position_sum([other_player], valid_scores, decision_range)[other_player]
                                                if player_position_sum != other_position_sum:
                                                    needs_special_format = True
                                                    break
                                        
                                        if needs_special_format:
                                            from .skating_system import calculate_position_sum
                                            position_sum = calculate_position_sum([player_id], valid_scores, decision_range)[player_id]
                                            range_stats[range_name] = f"{majority_count}({position_sum})"
                                        else:
                                            range_stats[range_name] = str(count)
                                    else:
                                        range_stats[range_name] = str(count)
                                else:
                                    range_stats[range_name] = str(count)
                            else:
                                range_stats[range_name] = ""
                        
                        details = {
                            "range_stats": range_stats,
                            "decision_range": decision_range
                        }
                    
                    # 创建打分明细对象
                    score_detail = SkatingScoreDetail(
                        event_id=records[0].event_id if records else "",
                        dance_name=dance_name,
                        competitor_number=competitor_number,
                        judge_placements=judge_placements,
                        placement_counts=placement_counts,
                        cumulative_votes=cumulative_votes,
                        sum_placement=sum_placement,
                        final_rank=rank,
                        majority_rank=majority_rank,
                        details=details
                    )
                    
                    dance_score_details[competitor_number] = score_detail
                
                score_details[dance_name] = dance_score_details
                
            except Exception as e:
                self.logger.error(f"生成舞种 {dance_name} 的明细表时出错: {str(e)}")
        
        return results, score_details
    
    def _calculate_overall_results_with_skating_system(self, overall_results: List[Result], score_details: Dict[str, Dict[str, SkatingScoreDetail]]) -> List[Result]:
        """
        使用滑冰系统算法计算综合结果
        
        Args:
            overall_results: 综合结果列表（仅包含选手信息，排名和分数将被更新）
            score_details: 打分明细字典 {舞种名: {选手编号: SkatingScoreDetail}}
            
        Returns:
            更新后的综合结果列表
        """
        from .skating_system import calculate_overall_ranking
        
        # 构建滑冰系统算法需要的输入格式
        # {舞种: {背号: 名次}}
        dance_rankings = {}
        
        for dance_name, dance_details in score_details.items():
            rankings = {}
            for competitor_number, detail in dance_details.items():
                rankings[competitor_number] = detail.final_rank
            dance_rankings[dance_name] = rankings
        
        # 计算综合排名
        overall_rankings = calculate_overall_ranking(dance_rankings)
        
        # 更新结果对象
        for result in overall_results:
            competitor_number = result.competitor_number
            # 确保competitor_number是字符串类型
            competitor_number_str = str(competitor_number)
            if competitor_number_str in overall_rankings:
                result.rank = overall_rankings[competitor_number_str]["最终名次"]
                result.total_score = overall_rankings[competitor_number_str]["综合得分"]
                result.score = result.total_score  # 顺位制中，综合得分即为分数
        
        # 按排名排序
        overall_results = sorted(overall_results, key=lambda x: x.rank)
        
        return overall_results
    
    def _calculate_overall_score_details(self, score_details: Dict[str, Dict[str, SkatingScoreDetail]]) -> Dict[str, SkatingOverallDetail]:
        """
        计算综合打分明细
        
        Args:
            score_details: 打分明细字典 {舞种名: {选手编号: SkatingScoreDetail}}
            
        Returns:
            综合打分明细字典 {选手编号: SkatingOverallDetail}
        """
        overall_details = {}
        
        # 获取所有选手
        all_competitors = set()
        for dance_details in score_details.values():
            all_competitors.update(dance_details.keys())
        
        # 为每个选手创建综合打分明细
        for competitor_number in all_competitors:
            # 收集该选手在各舞种的明细
            dance_details_dict = {}
            total_sum_placement = 0
            
            for dance_name, dance_details in score_details.items():
                if competitor_number in dance_details:
                    detail = dance_details[competitor_number]
                    dance_details_dict[dance_name] = detail
                    total_sum_placement += detail.sum_placement
            
            # 计算综合多数裁决名次（各舞种多数裁决名次的中位数）
            majority_ranks = []
            for detail in dance_details_dict.values():
                if detail.majority_rank is not None:
                    majority_ranks.append(detail.majority_rank)
            
            overall_majority_rank = None
            if majority_ranks:
                majority_ranks.sort()
                n = len(majority_ranks)
                if n % 2 == 1:
                    overall_majority_rank = majority_ranks[n // 2]
                else:
                    overall_majority_rank = (majority_ranks[n // 2 - 1] + majority_ranks[n // 2]) / 2
            
            # 创建综合打分明细对象
            overall_detail = SkatingOverallDetail(
                event_id=dance_details_dict[next(iter(dance_details_dict))].event_id if dance_details_dict else "",
                competitor_number=competitor_number,
                dance_details=dance_details_dict,
                total_sum_placement=total_sum_placement,
                final_rank=0,  # 将在综合结果计算中设置
                overall_majority_rank=overall_majority_rank
            )
            
            overall_details[competitor_number] = overall_detail
        
        return overall_details
    

    

    

    

    



# 创建全局评分算法实例（延迟导入以避免循环导入）
def get_scoring_algorithm():
    """获取评分算法实例"""
    return ScoringAlgorithm()

# 为了向后兼容，保留全局变量
scoring_algorithm = None