#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据管理模块
"""

import os
import json
import shutil
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid

from .data_models import Competition, Competitor, Judge, Event, ScoreRecord, Result, CompetitionResult, ScoringType, EventStatus
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger()

# 导入优化的数据管理器
from .optimized_data_manager import OptimizedDataManager


class DataManager:
    """数据管理类"""
    
    def __init__(self):
        """初始化数据管理器"""
        self.current_competition: Optional[Competition] = None
        self.current_event_name: Optional[str] = None
        self.logger = get_logger()
    
    def create_competition(self, name: str, date: str, location: str) -> bool:
        """
        创建新赛事
        
        Args:
            name: 赛事名称
            date: 赛事日期
            location: 赛事地点
            
        Returns:
            bool: 创建是否成功
        """
        try:
            # 生成赛事文件夹名称（名称+日期）
            event_name = f"{name}_{date.replace('-', '')}"
            
            # 检查是否已存在
            event_dir = config.get_event_dir(event_name)
            if os.path.exists(event_dir):
                self.logger.warning(f"赛事目录已存在: {event_dir}")
                return False
            
            # 创建赛事目录
            os.makedirs(event_dir)
            
            # 创建赛事对象
            competition = Competition(
                name=name,
                date=date,
                location=location
            )
            
            # 保存赛事数据
            if self._save_competition(competition, event_name):
                self.current_competition = competition
                self.current_event_name = event_name
                config.set_current_event(event_name)
                self.logger.info(f"成功创建赛事: {name}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"创建赛事失败: {e}")
            return False
    
    def open_competition(self, event_name: str) -> bool:
        """
        打开赛事
        
        Args:
            event_name: 赛事名称
            
        Returns:
            bool: 打开是否成功
        """
        try:
            event_file = config.get_event_data_file(event_name)
            
            if not os.path.exists(event_file):
                self.logger.error(f"赛事数据文件不存在: {event_file}")
                return False
            
            # 读取赛事数据
            with open(event_file, 'r', encoding='utf-8') as f:
                event_data = json.load(f)
            
            # 创建赛事对象
            competition = Competition.from_dict(event_data)
            
            self.current_competition = competition
            self.current_event_name = event_name
            config.set_current_event(event_name)
            
            # 创建赛事特定的导出目录结构
            self._create_event_export_dirs(event_name)
            
            self.logger.info(f"成功打开赛事: {event_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"打开赛事失败: {e}")
            return False
    
    def save_competition(self) -> bool:
        """
        保存当前赛事
        
        Returns:
            bool: 保存是否成功
        """
        if not self.current_competition or not self.current_event_name:
            self.logger.error("没有打开的赛事可保存")
            return False
        
        return self._save_competition(self.current_competition, self.current_event_name)
    
    def _save_competition(self, competition: Competition, event_name: str) -> bool:
        """
        保存赛事数据到文件
        
        Args:
            competition: 赛事对象
            event_name: 赛事名称
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 更新时间戳
            competition.update_timestamp()
            
            # 确保赛事目录存在
            event_dir = config.get_event_dir(event_name)
            if not os.path.exists(event_dir):
                os.makedirs(event_dir)
            
            # 获取数据文件路径
            event_file = config.get_event_data_file(event_name)
            backup_file = config.get_event_backup_file(event_name)
            
            # 如果原文件存在，先备份
            if os.path.exists(event_file):
                shutil.copy2(event_file, backup_file)
            
            # 保存数据
            with open(event_file, 'w', encoding='utf-8') as f:
                json.dump(competition.to_dict(), f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"成功保存赛事数据: {event_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存赛事数据失败: {e}")
            return False
    
    def get_competition(self) -> Optional[Competition]:
        """获取当前比赛对象"""
        return self.current_competition
    
    def get_competitor(self, number: int) -> Optional[Competitor]:
        """获取选手信息"""
        if not self.current_competition:
            return None
        return self.current_competition.competitors.get(number)
    
    def add_competitor(self, competitor: Competitor) -> bool:
        """添加选手"""
        if not self.current_competition:
            return False
        
        # 检查背番号是否已存在
        if competitor.number in self.current_competition.competitors:
            self.logger.warning(f"选手背番号已存在: {competitor.number}")
            return False
        
        self.current_competition.competitors[competitor.number] = competitor
        return self.save_competition()
    
    def update_competitor(self, competitor: Competitor) -> bool:
        """更新选手信息"""
        if not self.current_competition:
            return False
        
        if competitor.number not in self.current_competition.competitors:
            self.logger.warning(f"选手背番号不存在: {competitor.number}")
            return False
        
        self.current_competition.competitors[competitor.number] = competitor
        return self.save_competition()
    
    def delete_competitor(self, number: int) -> bool:
        """删除选手"""
        if not self.current_competition:
            return False
        
        if number not in self.current_competition.competitors:
            self.logger.warning(f"选手背番号不存在: {number}")
            return False
        
        del self.current_competition.competitors[number]
        return self.save_competition()
    
    def get_judge(self, judge_id: str) -> Optional[Judge]:
        """获取裁判信息"""
        if not self.current_competition:
            return None
        return self.current_competition.judges.get(judge_id)
    
    def add_judge(self, judge: Judge) -> bool:
        """添加裁判"""
        if not self.current_competition:
            return False
        
        # 检查裁判ID是否已存在
        if judge.id in self.current_competition.judges:
            self.logger.warning(f"裁判ID已存在: {judge.id}")
            return False
        
        self.current_competition.judges[judge.id] = judge
        return self.save_competition()
    
    def update_judge(self, judge: Judge) -> bool:
        """更新裁判信息"""
        if not self.current_competition:
            return False
        
        if judge.id not in self.current_competition.judges:
            self.logger.warning(f"裁判ID不存在: {judge.id}")
            return False
        
        self.current_competition.judges[judge.id] = judge
        return self.save_competition()
    
    def delete_judge(self, judge_id: str) -> bool:
        """删除裁判"""
        if not self.current_competition:
            return False
        
        if judge_id not in self.current_competition.judges:
            self.logger.warning(f"裁判ID不存在: {judge_id}")
            return False
        
        del self.current_competition.judges[judge_id]
        return self.save_competition()
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """获取场次信息"""
        if not self.current_competition:
            return None
        return self.current_competition.events.get(event_id)
    
    def add_event(self, event: Event) -> bool:
        """添加场次"""
        if not self.current_competition:
            return False
        
        # 检查场次ID是否已存在
        if event.id in self.current_competition.events:
            self.logger.warning(f"场次ID已存在: {event.id}")
            return False
        
        self.current_competition.events[event.id] = event
        return self.save_competition()
    
    def update_event(self, event: Event) -> bool:
        """更新场次信息"""
        if not self.current_competition:
            return False
        
        if event.id not in self.current_competition.events:
            self.logger.warning(f"场次ID不存在: {event.id}")
            return False
        
        self.current_competition.events[event.id] = event
        return self.save_competition()
    
    def delete_event(self, event_id: str) -> bool:
        """删除场次"""
        if not self.current_competition:
            return False
        
        if event_id not in self.current_competition.events:
            self.logger.warning(f"场次ID不存在: {event_id}")
            return False
        
        del self.current_competition.events[event_id]
        return self.save_competition()
    
    def add_score_record(self, record: ScoreRecord) -> bool:
        """添加评分记录"""
        if not self.current_competition:
            return False
        
        # 生成ID（如果没有）
        if not record.id:
            record.id = str(uuid.uuid4())
        
        # 检查是否已存在相同的评分记录（同一裁判、同一选手、同一舞种）
        for existing_record in self.current_competition.score_records:
            if (existing_record.event_id == record.event_id and
                existing_record.judge_id == record.judge_id and
                existing_record.competitor_number == record.competitor_number and
                existing_record.dance_name == record.dance_name):
                # 更新现有记录而不是添加新记录
                existing_record.score = record.score
                existing_record.placement = record.placement
                existing_record.mark = record.mark  # 确保mark字段也被更新
                existing_record.timestamp = record.timestamp
                return self.save_competition()
        
        # 如果没有找到现有记录，添加新记录
        self.current_competition.score_records.append(record)
        return self.save_competition()
    
    def get_score_records(self, event_id: str, judge_id: Optional[str] = None) -> List[ScoreRecord]:
        """获取评分记录"""
        if not self.current_competition:
            return []
        
        records = [
            record for record in self.current_competition.score_records 
            if record.event_id == event_id
        ]
        
        if judge_id:
            records = [record for record in records if record.judge_id == judge_id]
        
        return records
    
    def update_score_record(self, record: ScoreRecord) -> bool:
        """
        更新评分记录
        
        Args:
            record: 评分记录对象
            
        Returns:
            bool: 更新是否成功
        """
        if not self.current_competition:
            self.logger.error("没有当前赛事")
            return False
        
        try:
            # 找到要更新的记录
            for i, existing_record in enumerate(self.current_competition.score_records):
                if (existing_record.event_id == record.event_id and
                    existing_record.judge_id == record.judge_id and
                    existing_record.competitor_number == record.competitor_number and
                    existing_record.dance_name == record.dance_name):
                    # 更新记录
                    self.current_competition.score_records[i] = record
                    return self.save_competition()
            
            # 如果没有找到记录，记录警告
            self.logger.warning(f"没有找到要更新的评分记录: {record.event_id}, {record.judge_id}, {record.competitor_number}, {record.dance_name}")
            return False
            
        except Exception as e:
            self.logger.error(f"更新评分记录时发生错误: {str(e)}")
            return False
    
    def delete_score_records(self, event_id: str, judge_id: str, competitor_number: int, dance_name: str) -> bool:
        """
        删除指定的评分记录
        
        Args:
            event_id: 场次ID
            judge_id: 裁判ID
            competitor_number: 选手背番号
            dance_name: 舞种名称
            
        Returns:
            bool: 删除是否成功
        """
        if not self.current_competition:
            self.logger.error("没有当前赛事")
            return False
        
        try:
            # 找到并删除匹配的评分记录
            records_to_remove = []
            for record in self.current_competition.score_records:
                if (record.event_id == event_id and 
                    record.judge_id == judge_id and 
                    record.competitor_number == competitor_number and 
                    record.dance_name == dance_name):
                    records_to_remove.append(record)
            
            # 从列表中移除记录
            for record in records_to_remove:
                self.current_competition.score_records.remove(record)
            
            if records_to_remove:
                self.logger.info(f"已删除 {len(records_to_remove)} 条评分记录")
                return self.save_competition()
            else:
                self.logger.warning(f"没有找到匹配的评分记录")
                return False
        
        except Exception as e:
            self.logger.error(f"删除评分记录时发生错误: {str(e)}")
            return False
    
    def save_results(self, event_id: str, results_data: dict) -> bool:
        """
        保存比赛结果
        
        Args:
            event_id: 场次ID
            results_data: 结果数据字典
            
        Returns:
            bool: 保存是否成功
        """
        if not self.current_competition:
            self.logger.error("没有当前赛事")
            return False
        
        try:
            # 创建结果对象
            from datetime import datetime
            from .data_models import CompetitionResult
            result = CompetitionResult(
                event_id=event_id,
                calculation_time=datetime.now(),
                results_data=results_data
            )
            
            # 保存到赛事中
            if not hasattr(self.current_competition, 'results'):
                self.current_competition.results = {}
            
            self.current_competition.results[event_id] = result
            
            self.logger.info(f"场次 {event_id} 的结果已保存")
            return self.save_competition()
        
        except Exception as e:
            self.logger.error(f"保存场次 {event_id} 结果时发生错误: {str(e)}")
            return False
    
    def get_results(self, event_id: str) -> Optional[CompetitionResult]:
        """
        获取比赛结果
        
        Args:
            event_id: 场次ID
            
        Returns:
            Optional[CompetitionResult]: 比赛结果，如果不存在则返回None
        """
        if not self.current_competition:
            return None
        
        if not hasattr(self.current_competition, 'results'):
            return None
        
        return self.current_competition.results.get(event_id)
    
    def is_scoring_complete(self, event_id: str) -> bool:
        """
        检查指定场次的评分是否完成
        
        Args:
            event_id: 场次ID
            
        Returns:
            bool: 评分是否完成
        """
        if not self.current_competition:
            return False
        
        # 获取场次信息
        event = self.current_competition.events.get(event_id)
        if not event:
            self.logger.warning(f"场次不存在: {event_id}")
            return False
        
        # 获取该场次的评分记录
        score_records = self.get_score_records(event_id)
        self.logger.info(f"场次 {event_id} 共有 {len(score_records)} 条评分记录")
        
        # 检查是否有评分记录
        if not score_records:
            self.logger.info(f"场次 {event_id} 没有评分记录")
            return False
        
        # 检查是否有晋级结果
        result = self.get_results(event_id)
        if not result:
            self.logger.info(f"场次 {event_id} 没有晋级结果")
            return False
        
        self.logger.info(f"场次 {event_id} 的评分已完成")
        return True
    
    def get_player(self, player_id: str) -> Optional[Competitor]:
        """
        根据选手ID获取选手信息
        
        Args:
            player_id: 选手ID
            
        Returns:
            Optional[Competitor]: 选手信息，如果不存在则返回None
        """
        if not self.current_competition:
            return None
        
        # 遍历所有选手，查找匹配的ID
        for competitor in self.current_competition.competitors.values():
            if hasattr(competitor, 'id') and competitor.id == player_id:
                return competitor
        
        # 如果没有找到匹配的ID，尝试将player_id作为背番号处理
        try:
            number = int(player_id)
            return self.current_competition.competitors.get(number)
        except (ValueError, TypeError):
            pass
        
        return None
    
    def calculate_results(self, event_id: str) -> bool:
        """
        计算指定场次的结果，自动生成晋级状态
        
        Args:
            event_id: 场次ID
            
        Returns:
            bool: 计算是否成功
        """
        if not self.current_competition:
            self.logger.error("没有当前赛事")
            return False
        
        # 获取场次信息
        event = self.current_competition.events.get(event_id)
        if not event:
            self.logger.error(f"场次不存在: {event_id}")
            return False
        
        try:
            # 获取评分记录
            score_records = self.get_score_records(event_id)
            if not score_records:
                self.logger.warning(f"场次 {event_id} 没有评分记录")
                return False
            
            # 获取所有参赛选手
            all_competitors = [player.number for player in self.get_players_by_event(event_id)]
            
            # 导入评分算法
            from ..algorithms.scoring import get_scoring_algorithm
            scoring_algorithm = get_scoring_algorithm()
            
            # 计算结果，传递晋级人数参数和晋级规则
            success, results_dict, errors, score_details, overall_score_details = scoring_algorithm.calculate_results(
                score_records=score_records,
                scoring_type=event.scoring_type,
                advancement_count=event.advancement_count,  # 从场次信息中获取晋级人数
                advancement_rule=event.advancement_rule,  # 传递晋级规则
                all_competitors=all_competitors  # 传递所有参赛选手列表
            )
            
            if not success:
                self.logger.error(f"计算结果失败: {', '.join(errors)}")
                return False
            
            # 构建结果数据
            results_data = {
                'type': event.scoring_type.name,
                'overall_results': results_dict['overall_results'],
                'dance_results': results_dict['dance_results'],
                'event_info': {
                    'id': event.id,
                    'name': event.name,
                    'advancement_count': event.advancement_count
                }
            }
            
            # 如果有打分明细，添加到结果数据中
            if score_details:
                # 将打分明细转换为可序列化的格式
                serializable_score_details = {}
                for dance_name, dance_details in score_details.items():
                    serializable_score_details[dance_name] = {}
                    for competitor_number, detail in dance_details.items():
                        serializable_score_details[dance_name][str(competitor_number)] = detail.to_dict()
                
                results_data['score_details'] = serializable_score_details
            
            # 如果有综合打分明细，添加到结果数据中
            if overall_score_details:
                # 将综合打分明细转换为可序列化的格式
                serializable_overall_details = {}
                for competitor_number, detail in overall_score_details.items():
                    serializable_overall_details[str(competitor_number)] = detail.to_dict()
                
                results_data['overall_score_details'] = serializable_overall_details
            
            # 保存结果
            return self.save_results(event_id, results_data)
            
        except Exception as e:
            self.logger.error(f"计算场次 {event_id} 结果时发生错误: {str(e)}")
            return False
    
    def save_results(self, event_id: str, results_data: dict) -> bool:
        """
        保存比赛结果
        
        Args:
            event_id: 场次ID
            results_data: 结果数据
            
        Returns:
            bool: 保存是否成功
        """
        if not self.current_competition:
            self.logger.error("没有当前赛事")
            return False
        
        try:
            # 创建结果对象
            from datetime import datetime
            from .data_models import CompetitionResult
            result = CompetitionResult(
                event_id=event_id,
                calculation_time=datetime.now(),
                results_data=results_data
            )
            
            # 保存到赛事中
            if not hasattr(self.current_competition, 'results'):
                self.current_competition.results = {}
            
            self.current_competition.results[event_id] = result
            
            # 保存到文件
            success = self.save_competition()
            if success:
                self.logger.info(f"场次 {event_id} 的结果已保存")
            else:
                self.logger.error(f"场次 {event_id} 的结果保存失败")
            
            return success
        
        except Exception as e:
            self.logger.error(f"保存场次 {event_id} 结果时发生错误: {str(e)}")
            return False
    
    def get_results(self, event_id: str) -> Optional[CompetitionResult]:
        """
        获取比赛结果
        
        Args:
            event_id: 场次ID
            
        Returns:
            Optional[CompetitionResult]: 比赛结果，如果不存在则返回None
        """
        if not self.current_competition:
            return None
        
        if not hasattr(self.current_competition, 'results'):
            return None
        
        return self.current_competition.results.get(event_id)
    
    def get_players_by_event(self, event_id: str) -> List[Competitor]:
        """
        获取指定场次的参赛选手列表
        
        Args:
            event_id: 场次ID
            
        Returns:
            List[Competitor]: 参赛选手列表
        """
        if not self.current_competition:
            return []
        
        # 获取场次信息
        event = self.current_competition.events.get(event_id)
        if not event:
            self.logger.warning(f"场次不存在: {event_id}")
            return []
        
        # 获取参赛选手
        players = []
        
        # 如果场次中指定了competitors，则使用指定的选手
        if event.competitors:
            for player_number in event.competitors:
                player = self.current_competition.competitors.get(player_number)
                if player:
                    players.append(player)
        else:
            # 如果场次中没有指定competitors，则返回所有选手
            for player in self.current_competition.competitors.values():
                players.append(player)
        
        return players
    
    def get_all_events(self) -> List[str]:
        """获取所有赛事列表"""
        events_dir = config.ensure_events_dir()
        
        if not os.path.exists(events_dir):
            return []
        
        events = []
        for item in os.listdir(events_dir):
            item_path = os.path.join(events_dir, item)
            if os.path.isdir(item_path):
                events.append(item)
        
        return sorted(events, reverse=True)  # 按名称倒序排列
    
    def delete_competition(self, event_name: str) -> bool:
        """删除赛事"""
        try:
            event_dir = config.get_event_dir(event_name)
            
            if not os.path.exists(event_dir):
                self.logger.warning(f"赛事目录不存在: {event_dir}")
                return False
            
            # 删除整个目录
            shutil.rmtree(event_dir)
            
            # 如果是当前打开的赛事，清空当前状态
            if self.current_event_name == event_name:
                self.current_competition = None
                self.current_event_name = None
                config.set_current_event(None)
            
            self.logger.info(f"成功删除赛事: {event_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除赛事失败: {e}")
            return False
    
    def get_events_by_project_and_round(self, project_id: str, round: str) -> List[Event]:
        """
        获取指定项目和轮次的所有场次
        
        Args:
            project_id: 项目编号
            round: 轮次
            
        Returns:
            List[Event]: 场次列表
        """
        if not self.current_competition:
            return []
        
        # 筛选相同项目和轮次的场次
        events = [
            event for event in self.current_competition.events.values()
            if event.project_id == project_id and event.round == round
        ]
        
        return events
    
    def get_advancing_competitors(self, project_id: str, current_round: str) -> List[int]:
        """
        获取指定项目和轮次的晋级选手
        
        Args:
            project_id: 项目编号
            current_round: 当前轮次
            
        Returns:
            晋级选手背番号列表
        """
        # 获取当前轮次的所有场次
        current_events = self.get_events_by_project_and_round(project_id, current_round)
        
        if not current_events:
            return []
        
        # 收集所有晋级选手
        advancing_competitors = set()
        
        for event in current_events:
            result = self.get_results(event.id)
            if not result:
                continue
            
            results_data = result.results_data
            
            if 'overall_results' in results_data:
                overall_results = results_data['overall_results']
                for result_item in overall_results:
                    if result_item.advancement_status:
                        advancing_competitors.add(result_item.competitor_number)
        
        # 按背番号排序返回
        return sorted(list(advancing_competitors))
    
    def check_round_scoring_complete(self, project_id: str, round: str) -> Tuple[bool, List[str]]:
        """
        检查指定项目和轮次的所有场次是否已完成评分且状态为已完成
        
        Args:
            project_id: 项目编号
            round: 轮次
            
        Returns:
            Tuple[bool, List[str]]: (是否全部完成, 未完成的场次ID列表)
        """
        if not self.current_competition:
            return False, []
        
        # 获取该轮次的所有场次
        events = self.get_events_by_project_and_round(project_id, round)
        if not events:
            return False, []
        
        # 检查每个场次是否完成评分且状态为已完成
        incomplete_events = []
        for event in events:
            # 检查评分是否完成
            if not self.is_scoring_complete(event.id):
                incomplete_events.append(event.id)
                continue
            
            # 检查场次状态是否为已完成
            if event.status != EventStatus.COMPLETED:
                incomplete_events.append(event.id)
        
        return len(incomplete_events) == 0, incomplete_events
    
    def get_next_round_events(self, project_id: str, current_round: str) -> List[Event]:
        """
        获取指定项目和当前轮次的下一轮次的所有场次
        
        Args:
            project_id: 项目编号
            current_round: 当前轮次
            
        Returns:
            List[Event]: 下一轮次的场次列表
        """
        if not self.current_competition:
            return []
        
        # 获取该项目的所有场次
        project_events = [
            event for event in self.current_competition.events.values()
            if event.project_id == project_id
        ]
        
        # 尝试将轮次转换为数字进行比较
        try:
            current_round_num = int(current_round)
            next_round_num = current_round_num + 1
            
            # 获取下一轮次的所有场次
            next_round_events = [
                event for event in project_events
                if int(event.round) == next_round_num
            ]
        except (ValueError, AttributeError):
            # 如果转换失败，使用字符串比较
            next_round_events = []
            # 这里可以根据实际需求实现更复杂的轮次比较逻辑
            
        return next_round_events

    def import_advancement_to_next_round(self, current_event_id: str, target_event_id: str, advancement_count: Optional[int] = None) -> bool:
        """
        将当前场次的晋级选手导入到下一轮
        
        Args:
            current_event_id: 当前场次ID
            target_event_id: 目标场次ID
            advancement_count: 晋级人数（可选，默认使用当前场次配置的晋级人数）
            
        Returns:
            bool: 导入是否成功
        """
        if not self.current_competition:
            self.logger.error("没有当前赛事")
            return False
        
        try:
            # 获取当前场次信息
            current_event = self.current_competition.events.get(current_event_id)
            if not current_event:
                self.logger.error(f"当前场次不存在: {current_event_id}")
                return False
            
            # 获取目标场次信息
            target_event = self.current_competition.events.get(target_event_id)
            if not target_event:
                self.logger.error(f"目标场次不存在: {target_event_id}")
                return False
            
            # 获取当前场次的结果
            current_result = self.get_results(current_event_id)
            if not current_result:
                self.logger.error(f"当前场次 {current_event_id} 没有结果数据")
                return False
            
            # 从结果中获取晋级选手
            results_data = current_result.results_data
            
            # 优先使用overall_results中的晋级状态
            if 'overall_results' in results_data:
                overall_results = results_data['overall_results']
                # 筛选晋级状态为'晋级'的选手
                advancing_players = [
                    result.competitor_number 
                    for result in overall_results 
                    if result.advancement_status is True
                ]
            else:
                # 降级方案：使用旧的逻辑
                if 'results' not in results_data:
                    self.logger.error(f"场次 {current_event_id} 的结果数据格式不正确")
                    return False
                
                # 根据评分类型处理结果
                if results_data.get('type') == 'MARK':
                    # Mark制：分数从高到低排序
                    sorted_results = sorted(results_data['results'], key=lambda x: x[1], reverse=True)
                else:
                    # 顺位法：名次从小到大排序
                    sorted_results = sorted(results_data['results'], key=lambda x: x[1])
                
                # 获取前N名选手的背番号
                actual_advancement_count = advancement_count or current_event.advancement_count
                advancing_players = [player_number for player_number, _ in sorted_results[:actual_advancement_count]]
            
            # 更新目标场次的参赛选手
            target_event.competitors = advancing_players
            self.logger.info(f"已更新目标场次 {target_event_id} 的参赛选手")
            
            # 保存赛事
            success = self.save_competition()
            if success:
                self.logger.info(f"成功导入{len(advancing_players)}名选手到目标场次 {target_event_id}")
            
            return success
        
        except Exception as e:
            self.logger.error(f"导入晋级选手到下一轮时发生错误: {str(e)}")
            return False
    
    def _create_event_export_dirs(self, event_name: str) -> None:
        """
        为指定赛事创建导出目录结构
        
        Args:
            event_name: 赛事名称
        """
        try:
            # 获取基础导出目录
            base_export_dir = config.get("export_dir", os.path.join(os.path.expanduser("~"), "DanceSportExports"))
            
            # 确保基础目录存在
            if not os.path.exists(base_export_dir):
                os.makedirs(base_export_dir)
            
            # 创建赛事子目录
            event_export_dir = os.path.join(base_export_dir, event_name)
            if not os.path.exists(event_export_dir):
                os.makedirs(event_export_dir)
            
            # 创建子目录结构
            subdirs = ['results_pdf', 'details_pdf', 'details_markdown']
            for subdir in subdirs:
                subdir_path = os.path.join(event_export_dir, subdir)
                if not os.path.exists(subdir_path):
                    os.makedirs(subdir_path)
            
            self.logger.info(f"已创建赛事导出目录结构: {event_export_dir}")
            
        except Exception as e:
            self.logger.error(f"创建赛事导出目录结构失败: {e}")


# 创建全局数据管理器实例
data_manager = OptimizedDataManager()