#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化后的数据管理模块
将数据拆分为多个文件，提高性能
"""

import os
import json
import shutil
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import uuid
import threading
from pathlib import Path

from .data_models import Competition, Competitor, Judge, Event, ScoreRecord, Result, CompetitionResult, ScoringType, EventStatus
from ..utils.config import config
from ..utils.logger import get_logger
from ..utils.results_view_manager import ResultsViewManager

logger = get_logger()


class OptimizedDataManager:
    """优化后的数据管理类，使用分文件存储提高性能"""
    
    def __init__(self):
        """初始化数据管理器"""
        self.current_competition: Optional[Competition] = None
        self.current_event_name: Optional[str] = None
        self.logger = get_logger()
        self._data_lock = threading.RLock()  # 数据访问锁，防止并发问题
        
        # 数据文件路径映射
        self._file_paths = {
            'competition': 'competition.json',  # 比赛基本信息
            'competitors': 'competitors.json',  # 选手信息
            'judges': 'judges.json',  # 裁判信息
            'events': 'events.json',  # 场次信息
            'scores': 'scores',  # 评分记录目录，每个场次一个文件
            'results': 'results',  # 结果目录，每个场次一个文件
            'exports': 'exports'  # 导出文件目录
        }
    
    def _get_event_dir(self, event_name: str) -> str:
        """获取赛事目录路径"""
        return config.get_event_dir(event_name)
    
    def _get_file_path(self, event_name: str, file_type: str, sub_path: Optional[str] = None) -> str:
        """
        获取数据文件路径
        
        Args:
            event_name: 赛事名称
            file_type: 文件类型
            sub_path: 子路径（用于评分记录和结果）
            
        Returns:
            str: 文件路径
        """
        event_dir = self._get_event_dir(event_name)
        
        if file_type in ['scores', 'results'] and sub_path:
            # 评分记录和结果使用子目录
            subdir = os.path.join(event_dir, self._file_paths[file_type])
            if not os.path.exists(subdir):
                os.makedirs(subdir)
            return os.path.join(subdir, f"{sub_path}.json")
        else:
            # 其他类型直接在赛事目录下
            return os.path.join(event_dir, self._file_paths[file_type])
    
    def _load_json_file(self, file_path: str, default: Any = None) -> Any:
        """
        加载JSON文件
        
        Args:
            file_path: 文件路径
            default: 默认值（如果文件不存在）
            
        Returns:
            加载的数据或默认值
        """
        if not os.path.exists(file_path):
            return default
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载文件失败 {file_path}: {e}")
            return default
    
    def _save_json_file(self, file_path: str, data: Any) -> bool:
        """
        保存数据到JSON文件
        
        Args:
            file_path: 文件路径
            data: 要保存的数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 保存数据
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            self.logger.error(f"保存文件失败 {file_path}: {e}")
            return False
    
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
        with self._data_lock:
            try:
                # 生成赛事文件夹名称（名称+日期）
                event_name = f"{name}_{date.replace('-', '')}"
                
                # 检查是否已存在
                event_dir = self._get_event_dir(event_name)
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
                
                # 保存比赛基本信息
                competition_file = self._get_file_path(event_name, 'competition')
                if not self._save_json_file(competition_file, competition.to_dict()):
                    return False
                
                # 创建其他空的数据文件
                self._save_json_file(self._get_file_path(event_name, 'competitors'), {})
                self._save_json_file(self._get_file_path(event_name, 'judges'), {})
                self._save_json_file(self._get_file_path(event_name, 'events'), {})
                
                # 创建评分记录和结果目录
                os.makedirs(os.path.join(event_dir, self._file_paths['scores']), exist_ok=True)
                os.makedirs(os.path.join(event_dir, self._file_paths['results']), exist_ok=True)
                
                self.current_competition = competition
                self.current_event_name = event_name
                config.set_current_event(event_name)
                self.logger.info(f"成功创建赛事: {name}")
                return True
                
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
        with self._data_lock:
            try:
                # 检查赛事目录是否存在
                event_dir = self._get_event_dir(event_name)
                if not os.path.exists(event_dir):
                    self.logger.error(f"赛事目录不存在: {event_dir}")
                    return False
                
                # 检查是否是新格式（有分文件）
                competition_file = self._get_file_path(event_name, 'competition')
                if os.path.exists(competition_file):
                    # 新格式：加载分文件数据
                    return self._load_competition_from_split_files(event_name)
                else:
                    # 旧格式：加载单一JSON文件并迁移
                    return self._load_and_migrate_competition(event_name)
                
            except Exception as e:
                self.logger.error(f"打开赛事失败: {e}")
                return False
    
    def _load_competition_from_split_files(self, event_name: str) -> bool:
        """
        从分文件加载比赛数据
        
        Args:
            event_name: 赛事名称
            
        Returns:
            bool: 加载是否成功
        """
        try:
            # 加载比赛基本信息（包含 competitor_mapping）
            competition_file = self._get_file_path(event_name, 'competition')
            competition_data = self._load_json_file(competition_file)
            if not competition_data:
                self.logger.error(f"无法加载比赛基本信息: {competition_file}")
                return False
            
            competition = Competition.from_dict(competition_data)
            
            # 加载选手信息
            competitors_file = self._get_file_path(event_name, 'competitors')
            competitors_data = self._load_json_file(competitors_file, {})
            competition.competitors = {
                num: Competitor.from_dict(comp_data) 
                for num, comp_data in competitors_data.items()
            }
            
            # 加载裁判信息
            judges_file = self._get_file_path(event_name, 'judges')
            judges_data = self._load_json_file(judges_file, {})
            competition.judges = {
                judge_id: Judge.from_dict(judge_data) 
                for judge_id, judge_data in judges_data.items()
            }
            
            # 加载场次信息
            events_file = self._get_file_path(event_name, 'events')
            events_data = self._load_json_file(events_file, {})
            competition.events = {
                event_id: Event.from_dict(event_data) 
                for event_id, event_data in events_data.items()
            }
            
            # 加载评分记录
            scores_dir = os.path.join(self._get_event_dir(event_name), self._file_paths['scores'])
            competition.score_records = []
            if os.path.exists(scores_dir):
                for score_file in os.listdir(scores_dir):
                    if score_file.endswith('.json'):
                        event_id = os.path.splitext(score_file)[0]
                        score_file_path = os.path.join(scores_dir, score_file)
                        scores_data = self._load_json_file(score_file_path, [])
                        
                        for score_data in scores_data:
                            competition.score_records.append(ScoreRecord.from_dict(score_data))
            
            # 加载结果
            results_dir = os.path.join(self._get_event_dir(event_name), self._file_paths['results'])
            competition.results = {}
            if os.path.exists(results_dir):
                for result_file in os.listdir(results_dir):
                    if result_file.endswith('.json'):
                        event_id = os.path.splitext(result_file)[0]
                        result_file_path = os.path.join(results_dir, result_file)
                        result_data = self._load_json_file(result_file_path)
                        
                        if result_data:
                            competition.results[event_id] = CompetitionResult.from_dict(result_data)
            
            self.current_competition = competition
            self.current_event_name = event_name
            config.set_current_event(event_name)
            
            self.logger.info(f"成功打开赛事: {event_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"从分文件加载赛事失败: {e}")
            return False
    
    def _load_and_migrate_competition(self, event_name: str) -> bool:
        """
        加载旧格式数据并迁移到新格式
        
        Args:
            event_name: 赛事名称
            
        Returns:
            bool: 加载和迁移是否成功
        """
        try:
            # 加载旧格式数据
            event_file = config.get_event_data_file(event_name)
            if not os.path.exists(event_file):
                self.logger.error(f"赛事数据文件不存在: {event_file}")
                return False
            
            with open(event_file, 'r', encoding='utf-8') as f:
                event_data = json.load(f)
            
            # 创建比赛对象
            competition = Competition.from_dict(event_data)
            
            # 迁移到新格式
            if self._migrate_to_split_files(event_name, competition):
                # 重新加载迁移后的数据
                return self._load_competition_from_split_files(event_name)
            else:
                self.logger.error(f"迁移赛事数据失败: {event_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"加载和迁移赛事失败: {e}")
            return False
    
    def _migrate_to_split_files(self, event_name: str, competition: Competition) -> bool:
        """
        将比赛数据迁移到分文件格式
        
        Args:
            event_name: 赛事名称
            competition: 比赛对象
            
        Returns:
            bool: 迁移是否成功
        """
        try:
            event_dir = self._get_event_dir(event_name)
            
            # 保存比赛基本信息
            competition_file = self._get_file_path(event_name, 'competition')
            if not self._save_json_file(competition_file, competition.to_dict()):
                return False
            
            # 保存选手信息
            competitors_data = {
                str(num): comp.to_dict() 
                for num, comp in competition.competitors.items()
            }
            competitors_file = self._get_file_path(event_name, 'competitors')
            if not self._save_json_file(competitors_file, competitors_data):
                return False
            
            # 保存裁判信息
            judges_data = {
                judge_id: judge.to_dict() 
                for judge_id, judge in competition.judges.items()
            }
            judges_file = self._get_file_path(event_name, 'judges')
            if not self._save_json_file(judges_file, judges_data):
                return False
            
            # 保存场次信息
            events_data = {
                event_id: event.to_dict() 
                for event_id, event in competition.events.items()
            }
            events_file = self._get_file_path(event_name, 'events')
            if not self._save_json_file(events_file, events_data):
                return False
            
            # 按场次分组保存评分记录
            scores_dir = os.path.join(event_dir, self._file_paths['scores'])
            os.makedirs(scores_dir, exist_ok=True)
            
            scores_by_event = {}
            for record in competition.score_records:
                if record.event_id not in scores_by_event:
                    scores_by_event[record.event_id] = []
                scores_by_event[record.event_id].append(record.to_dict())
            
            for event_id, scores in scores_by_event.items():
                score_file = self._get_file_path(event_name, 'scores', event_id)
                if not self._save_json_file(score_file, scores):
                    return False
            
            # 按场次保存结果
            results_dir = os.path.join(event_dir, self._file_paths['results'])
            os.makedirs(results_dir, exist_ok=True)
            
            for event_id, result in competition.results.items():
                result_file = self._get_file_path(event_name, 'results', event_id)
                if not self._save_json_file(result_file, result.to_dict()):
                    return False
            
            # 备份原始文件
            original_file = config.get_event_data_file(event_name)
            backup_file = os.path.join(event_dir, "event_original_backup.json")
            if os.path.exists(original_file):
                shutil.copy2(original_file, backup_file)
            
            self.logger.info(f"成功迁移赛事数据到新格式: {event_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"迁移赛事数据失败: {e}")
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
        
        with self._data_lock:
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
            
            # 保存比赛基本信息
            competition_file = self._get_file_path(event_name, 'competition')
            if not self._save_json_file(competition_file, competition.to_dict()):
                return False
            
            # 保存选手信息
            competitors_data = {
                str(num): comp.to_dict() 
                for num, comp in competition.competitors.items()
            }
            competitors_file = self._get_file_path(event_name, 'competitors')
            if not self._save_json_file(competitors_file, competitors_data):
                return False
            
            # 保存裁判信息
            judges_data = {
                judge_id: judge.to_dict() 
                for judge_id, judge in competition.judges.items()
            }
            judges_file = self._get_file_path(event_name, 'judges')
            if not self._save_json_file(judges_file, judges_data):
                return False
            
            # 保存场次信息
            events_data = {
                event_id: event.to_dict() 
                for event_id, event in competition.events.items()
            }
            events_file = self._get_file_path(event_name, 'events')
            if not self._save_json_file(events_file, events_data):
                return False
            
            self.logger.debug(f"成功保存赛事数据: {event_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存赛事数据失败: {e}")
            return False
    
    def get_competition(self) -> Optional[Competition]:
        """获取当前比赛对象"""
        return self.current_competition
    
    def get_competitor(self, number: str) -> Optional[Competitor]:
        """获取选手信息"""
        if not self.current_competition:
            return None
        return self.current_competition.competitors.get(number)
    
    def add_competitor(self, competitor: Competitor, project_id: Optional[str] = None) -> bool:
        """添加选手"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            # 添加到内存
            self.current_competition.competitors[competitor.number] = competitor
            
            # 如果有项目编号，添加到选手映射
            if project_id:
                if competitor.number not in self.current_competition.competitor_mapping:
                    self.current_competition.competitor_mapping[competitor.number] = {}
                self.current_competition.competitor_mapping[competitor.number][project_id] = competitor
            
            # 保存到文件
            competitors_data = {
                str(num): comp.to_dict() 
                for num, comp in self.current_competition.competitors.items()
            }
            competitors_file = self._get_file_path(self.current_event_name, 'competitors')
            return self._save_json_file(competitors_file, competitors_data)
    
    def add_competitor_mapping(self, competitor: Competitor, project_id: str) -> bool:
        """添加选手映射（背番号+项目编号→选手）"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            # 确保competitor_mapping存在
            if not hasattr(self.current_competition, 'competitor_mapping'):
                self.current_competition.competitor_mapping = {}
            
            # 使用字符串类型的背番号
            number = competitor.number
            
            # 添加到选手映射
            if number not in self.current_competition.competitor_mapping:
                self.current_competition.competitor_mapping[number] = {}
            self.current_competition.competitor_mapping[number][project_id] = competitor
            
            # 同时添加到普通选手字典
            if number not in self.current_competition.competitors:
                self.current_competition.competitors[number] = competitor
            
            # 保存到文件
            return self.save_competition()
    
    def get_competitor_by_number_and_project(self, number: str, project_id: str) -> Optional[Competitor]:
        """通过背番号和项目编号获取选手信息"""
        if not self.current_competition:
            return None
        
        # 首先尝试从选手映射中获取
        if hasattr(self.current_competition, 'competitor_mapping'):
            if number in self.current_competition.competitor_mapping:
                return self.current_competition.competitor_mapping[number].get(project_id)
        
        # 如果映射中没有，返回默认的选手信息
        return self.current_competition.competitors.get(number)
    
    def update_competitor(self, competitor: Competitor, project_id: Optional[str] = None) -> bool:
        """更新选手信息"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            if competitor.number not in self.current_competition.competitors:
                self.logger.warning(f"选手背番号不存在: {competitor.number}")
                return False
            
            # 更新内存中的选手信息
            self.current_competition.competitors[competitor.number] = competitor
            
            # 如果有项目编号，只更新指定项目的映射
            if project_id:
                if competitor.number in self.current_competition.competitor_mapping:
                    self.current_competition.competitor_mapping[competitor.number][project_id] = competitor
            else:
                # 如果没有项目编号，更新所有项目的映射
                if competitor.number in self.current_competition.competitor_mapping:
                    for proj_id in self.current_competition.competitor_mapping[competitor.number]:
                        self.current_competition.competitor_mapping[competitor.number][proj_id] = competitor
            
            # 保存到文件
            competitors_data = {
                str(num): comp.to_dict() 
                for num, comp in self.current_competition.competitors.items()
            }
            competitors_file = self._get_file_path(self.current_event_name, 'competitors')
            return self._save_json_file(competitors_file, competitors_data)
    
    def delete_competitor(self, number: str, project_id: Optional[str] = None) -> bool:
        """删除选手"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            if number not in self.current_competition.competitors:
                self.logger.warning(f"选手背番号不存在: {number}")
                return False
            
            # 如果有项目编号，只删除指定项目的映射
            if project_id:
                if number in self.current_competition.competitor_mapping:
                    if project_id in self.current_competition.competitor_mapping[number]:
                        del self.current_competition.competitor_mapping[number][project_id]
                    # 如果该背番号没有其他项目映射，从主字典中删除
                    if not self.current_competition.competitor_mapping[number]:
                        del self.current_competition.competitor_mapping[number]
                        del self.current_competition.competitors[number]
            else:
                # 如果没有项目编号，删除所有相关信息
                if number in self.current_competition.competitor_mapping:
                    del self.current_competition.competitor_mapping[number]
                del self.current_competition.competitors[number]
            
            # 保存到文件
            competitors_data = {
                str(num): comp.to_dict() 
                for num, comp in self.current_competition.competitors.items()
            }
            competitors_file = self._get_file_path(self.current_event_name, 'competitors')
            return self._save_json_file(competitors_file, competitors_data)
    
    def get_judge(self, judge_id: str) -> Optional[Judge]:
        """获取裁判信息"""
        if not self.current_competition:
            return None
        return self.current_competition.judges.get(judge_id)
    
    def add_judge(self, judge: Judge) -> bool:
        """添加裁判"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            # 检查裁判ID是否已存在
            if judge.id in self.current_competition.judges:
                self.logger.warning(f"裁判ID已存在: {judge.id}")
                return False
            
            # 添加到内存
            self.current_competition.judges[judge.id] = judge
            
            # 保存到文件
            judges_data = {
                judge_id: judge_obj.to_dict() 
                for judge_id, judge_obj in self.current_competition.judges.items()
            }
            judges_file = self._get_file_path(self.current_event_name, 'judges')
            return self._save_json_file(judges_file, judges_data)
    
    def update_judge(self, judge: Judge) -> bool:
        """更新裁判信息"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            if judge.id not in self.current_competition.judges:
                self.logger.warning(f"裁判ID不存在: {judge.id}")
                return False
            
            # 更新内存
            self.current_competition.judges[judge.id] = judge
            
            # 保存到文件
            judges_data = {
                judge_id: judge_obj.to_dict() 
                for judge_id, judge_obj in self.current_competition.judges.items()
            }
            judges_file = self._get_file_path(self.current_event_name, 'judges')
            return self._save_json_file(judges_file, judges_data)
    
    def delete_judge(self, judge_id: str) -> bool:
        """删除裁判"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            if judge_id not in self.current_competition.judges:
                self.logger.warning(f"裁判ID不存在: {judge_id}")
                return False
            
            # 从内存中删除
            del self.current_competition.judges[judge_id]
            
            # 保存到文件
            judges_data = {
                judge_id: judge_obj.to_dict() 
                for judge_id, judge_obj in self.current_competition.judges.items()
            }
            judges_file = self._get_file_path(self.current_event_name, 'judges')
            return self._save_json_file(judges_file, judges_data)
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """获取场次信息"""
        if not self.current_competition:
            return None
        return self.current_competition.events.get(event_id)
    
    def add_event(self, event: Event) -> bool:
        """添加场次"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            # 检查场次ID是否已存在
            if event.id in self.current_competition.events:
                self.logger.warning(f"场次ID已存在: {event.id}")
                return False
            
            # 添加到内存
            self.current_competition.events[event.id] = event
            
            # 保存到文件
            events_data = {
                event_id: event_obj.to_dict() 
                for event_id, event_obj in self.current_competition.events.items()
            }
            events_file = self._get_file_path(self.current_event_name, 'events')
            return self._save_json_file(events_file, events_data)
    
    def update_event(self, event: Event) -> bool:
        """更新场次信息"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            if event.id not in self.current_competition.events:
                self.logger.warning(f"场次ID不存在: {event.id}")
                return False
            
            # 更新内存
            self.current_competition.events[event.id] = event
            
            # 保存到文件
            events_data = {
                event_id: event_obj.to_dict() 
                for event_id, event_obj in self.current_competition.events.items()
            }
            events_file = self._get_file_path(self.current_event_name, 'events')
            return self._save_json_file(events_file, events_data)
    
    def delete_event(self, event_id: str) -> bool:
        """删除场次"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            if event_id not in self.current_competition.events:
                self.logger.warning(f"场次ID不存在: {event_id}")
                return False
            
            # 从内存中删除
            del self.current_competition.events[event_id]
            
            # 保存到文件
            events_data = {
                event_id: event_obj.to_dict() 
                for event_id, event_obj in self.current_competition.events.items()
            }
            events_file = self._get_file_path(self.current_event_name, 'events')
            return self._save_json_file(events_file, events_data)
    
    def add_score_record(self, record: ScoreRecord) -> bool:
        """添加评分记录"""
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
                return False
            
            # 生成ID（如果没有）
            if not record.id:
                record.id = str(uuid.uuid4())
            
            # 检查是否已存在相同的评分记录（同一裁判、同一选手、同一舞种）
            for i, existing_record in enumerate(self.current_competition.score_records):
                if (existing_record.event_id == record.event_id and
                    existing_record.judge_id == record.judge_id and
                    existing_record.competitor_number == record.competitor_number and
                    existing_record.dance_name == record.dance_name):
                    # 更新现有记录而不是添加新记录
                    self.current_competition.score_records[i] = record
                    return self._save_score_records_for_event(record.event_id)
            
            # 如果没有找到现有记录，添加新记录
            self.current_competition.score_records.append(record)
            return self._save_score_records_for_event(record.event_id)
    
    def _save_score_records_for_event(self, event_id: str) -> bool:
        """
        保存指定场次的评分记录
        
        Args:
            event_id: 场次ID
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 获取该场次的所有评分记录
            event_scores = [
                record.to_dict() for record in self.current_competition.score_records 
                if record.event_id == event_id
            ]
            
            # 保存到文件
            score_file = self._get_file_path(self.current_event_name, 'scores', event_id)
            return self._save_json_file(score_file, event_scores)
            
        except Exception as e:
            self.logger.error(f"保存评分记录失败: {e}")
            return False
    
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
        with self._data_lock:
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
                        return self._save_score_records_for_event(record.event_id)
                
                # 如果没有找到记录，记录警告
                self.logger.warning(f"没有找到要更新的评分记录: {record.event_id}, {record.judge_id}, {record.competitor_number}, {record.dance_name}")
                return False
                
            except Exception as e:
                self.logger.error(f"更新评分记录时发生错误: {str(e)}")
                return False
    
    def delete_score_records(self, event_id: str, judge_id: str, competitor_number: str, dance_name: str) -> bool:
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
        with self._data_lock:
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
                    return self._save_score_records_for_event(event_id)
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
        with self._data_lock:
            if not self.current_competition or not self.current_event_name:
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
                
                # 保存到内存
                self.current_competition.results[event_id] = result
                
                # 保存到文件
                result_file = self._get_file_path(self.current_event_name, 'results', event_id)
                return self._save_json_file(result_file, result.to_dict())
            
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
        return self.current_competition.competitors.get(player_id)
        
        return None
    
    def get_players_by_event(self, event_id: str) -> List[Competitor]:
        """
        获取指定场次的所有选手
        
        Args:
            event_id: 场次ID
            
        Returns:
            List[Competitor]: 选手列表
        """
        if not self.current_competition:
            return []
        
        event = self.current_competition.events.get(event_id)
        if not event:
            return []
        
        players = []
        for competitor_number in event.competitors:
            competitor = self.current_competition.competitors.get(competitor_number)
            if competitor:
                players.append(competitor)
        
        return players
    
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
                competitors=all_competitors,
                scoring_type=event.scoring_type,
                advancement_count=event.advancement_count,
                advancement_rule=event.advancement_rule
            )
            
            if not success:
                self.logger.error(f"计算结果失败: {errors}")
                return False
            
            # 保存结果
            if self.save_results(event_id, results_dict):
                self.logger.info(f"场次 {event_id} 的结果计算完成")
                return True
            else:
                self.logger.error(f"保存场次 {event_id} 的结果失败")
                return False
                
        except Exception as e:
            self.logger.error(f"计算场次 {event_id} 结果时发生错误: {str(e)}")
            return False
    
    def get_event_data_file(self, event_name: str) -> str:
        """
        获取赛事数据文件路径
        
        Args:
            event_name: 赛事名称
            
        Returns:
            str: 赛事数据文件路径
        """
        return self._get_file_path(event_name, 'competition')
    
    def clear_event_directory(self) -> bool:
        """
        清空当前赛事目录
        
        Returns:
            bool: 清空是否成功
        """
        if not self.current_competition or not self.current_event_name:
            self.logger.error("没有当前赛事")
            return False
        
        try:
            # 获取当前赛事目录
            event_dir = self._get_event_dir(self.current_event_name)
            
            # 清空内存中的赛事数据
            self.current_competition.competitors.clear()
            self.current_competition.events.clear()
            self.current_competition.judges.clear()
            self.current_competition.score_records.clear()
            self.current_competition.results.clear()
            self.current_competition.competitor_mapping.clear()
            
            # 删除赛事目录中的所有文件和子目录
            if os.path.exists(event_dir):
                # 遍历目录中的所有文件和子目录
                for root, dirs, files in os.walk(event_dir, topdown=False):
                    # 删除所有文件
                    for file in files:
                        file_path = os.path.join(root, file)
                        os.remove(file_path)
                    # 删除所有子目录
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        os.rmdir(dir_path)
            
            # 重新创建必要的子目录结构
            for file_type in ['scores', 'results']:
                subdir = os.path.join(event_dir, self._file_paths[file_type])
                if not os.path.exists(subdir):
                    os.makedirs(subdir)
            
            self.logger.info(f"成功清空赛事目录: {event_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"清空赛事目录失败: {e}")
            return False
    
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
    
    def clear_event_results(self, event_id: str) -> bool:
        """
        清除指定场次的所有评分记录和结果
        
        Args:
            event_id: 场次ID
            
        Returns:
            bool: 清除是否成功
        """
        with self._data_lock:
            if not self.current_competition:
                self.logger.error("没有当前赛事")
                return False
            
            try:
                # 清除内存中的评分记录
                records_to_remove = [
                    record for record in self.current_competition.score_records
                    if record.event_id == event_id
                ]
                
                for record in records_to_remove:
                    self.current_competition.score_records.remove(record)
                
                # 清除内存中的结果
                if event_id in self.current_competition.results:
                    del self.current_competition.results[event_id]
                
                # 删除评分记录文件
                if self.current_event_name:
                    score_file = self._get_file_path(self.current_event_name, 'scores', event_id)
                    if os.path.exists(score_file):
                        os.remove(score_file)
                
                # 删除结果文件
                if self.current_event_name:
                    result_file = self._get_file_path(self.current_event_name, 'results', event_id)
                    if os.path.exists(result_file):
                        os.remove(result_file)
                
                # 更新场次状态为未开始
                event = self.current_competition.events.get(event_id)
                if event:
                    from .data_models import EventStatus
                    event.status = EventStatus.NOT_STARTED
                    self.update_event(event)
                
                self.logger.info(f"已清除场次 {event_id} 的所有评分记录和结果")
                return True
                
            except Exception as e:
                self.logger.error(f"清除场次 {event_id} 结果时发生错误: {str(e)}")
                return False
    
    def _get_export_dir(self, event_name: str) -> str:
        """
        获取导出目录路径
        
        Args:
            event_name: 赛事名称
            
        Returns:
            str: 导出目录路径
        """
        # 首先检查配置中是否有自定义导出目录
        custom_export_dir = config.get("export_dir")
        if custom_export_dir and os.path.exists(custom_export_dir):
            # 使用自定义导出目录，创建以赛事名称命名的子目录
            export_dir = os.path.join(custom_export_dir, event_name)
        else:
            # 使用默认导出目录（赛事目录下的exports子目录）
            event_dir = self._get_event_dir(event_name)
            export_dir = os.path.join(event_dir, self._file_paths['exports'])
        
        # 确保导出目录存在
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        
        # 创建子目录结构
        subdirs = ['results_pdf', 'details_pdf', 'details_markdown']
        for subdir in subdirs:
            subdir_path = os.path.join(export_dir, subdir)
            if not os.path.exists(subdir_path):
                os.makedirs(subdir_path)
        
        return export_dir
    
    def get_export_file_path(self, event_id: str, file_type: str, file_extension: str = 'pdf') -> str:
        """
        获取导出文件的完整路径，按照"场次编号-场次名称-项目编号-导出文件类型"命名
        
        Args:
            event_id: 场次ID
            file_type: 导出文件类型 (results_pdf, details_pdf, details_markdown)
            file_extension: 文件扩展名 (pdf, md)
            
        Returns:
            str: 导出文件的完整路径
        """
        if not self.current_competition or not self.current_event_name:
            return None
        
        # 获取场次信息
        event = self.current_competition.events.get(event_id)
        if not event:
            return None
        
        # 获取导出目录
        export_dir = self._get_export_dir(self.current_event_name)
        
        # 确定子目录
        subdir = file_type
        subdir_path = os.path.join(export_dir, subdir)
        
        # 构建文件名: 场次编号-场次名称-项目编号-导出文件类型
        file_name = f"{event_id}-{event.name}-{event.project_id}-{file_type}.{file_extension}"
        
        return os.path.join(subdir_path, file_name)
    
    def auto_export_event_results(self, event_id: str) -> bool:
        """
        自动导出场次结果，包括结果PDF、明细PDF和明细Markdown
        
        Args:
            event_id: 场次ID
            
        Returns:
            bool: 导出是否成功
        """
        if not self.current_competition or not self.current_event_name:
            self.logger.error("没有当前赛事")
            return False
        
        try:
            # 检查场次是否存在
            event = self.current_competition.events.get(event_id)
            if not event:
                self.logger.error(f"场次不存在: {event_id}")
                return False
            
            # 检查评分是否完成
            if not self.is_scoring_complete(event_id):
                self.logger.error(f"场次 {event_id} 评分未完成，无法导出")
                return False
            
            # 获取结果数据
            result = self.get_results(event_id)
            if not result:
                self.logger.error(f"场次 {event_id} 没有结果数据")
                return False
            
            # 获取评分记录
            score_records = self.get_score_records(event_id)
            
            # 获取选手信息
            competitors = {}
            for competitor_number in event.competitors:
                competitor = self.current_competition.competitors.get(competitor_number)
                if competitor:
                    competitors[competitor_number] = competitor
            
            # 导入导出功能
            results_view_manager = ResultsViewManager()
            
            # 导出结果PDF
            results_pdf_path = self.get_export_file_path(event_id, 'results_pdf', 'pdf')
            if results_pdf_path:
                success, errors = results_view_manager.export_overall_results_to_pdf(event_id, results_pdf_path, self)
                if success:
                    self.logger.info(f"已导出结果PDF: {results_pdf_path}")
                else:
                    self.logger.error(f"导出结果PDF失败: {errors}")
            
            # 导出明细PDF
            details_pdf_path = self.get_export_file_path(event_id, 'details_pdf', 'pdf')
            if details_pdf_path:
                success, errors = results_view_manager.export_detailed_results_to_pdf(event_id, details_pdf_path, self)
                if success:
                    self.logger.info(f"已导出明细PDF: {details_pdf_path}")
                else:
                    self.logger.error(f"导出明细PDF失败: {errors}")
            
            # 导出明细Markdown
            details_md_path = self.get_export_file_path(event_id, 'details_markdown', 'md')
            if details_md_path:
                success, errors = results_view_manager.export_score_details_to_markdown(event_id, details_md_path, self)
                if success:
                    self.logger.info(f"已导出明细Markdown: {details_md_path}")
                else:
                    self.logger.error(f"导出明细Markdown失败: {errors}")
            
            self.logger.info(f"场次 {event_id} 的所有导出文件已生成")
            return True
            
        except Exception as e:
            self.logger.error(f"自动导出场次 {event_id} 结果时发生错误: {str(e)}")
            return False
    
    def delete_competition(self, event_name: str) -> bool:
        """
        删除赛事
        
        Args:
            event_name: 赛事名称
            
        Returns:
            bool: 删除是否成功
        """
        try:
            event_dir = self._get_event_dir(event_name)
            
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

data_manager = OptimizedDataManager()