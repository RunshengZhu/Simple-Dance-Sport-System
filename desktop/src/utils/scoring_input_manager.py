#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评分输入工具模块
"""

from typing import Dict, List, Tuple, Optional
import os
import json
import uuid
from datetime import datetime

from ..models.data_models import ScoreRecord, ScoringType
from ..utils.logger import get_logger

logger = get_logger()


class ScoringInputManager:
    """评分输入管理器类"""
    
    def __init__(self):
        """初始化评分输入管理器"""
        self.logger = logger
    
    def initialize(self):
        """初始化评分输入管理器"""
        self.logger.info("评分输入管理器初始化")
        # 这里可以添加初始化逻辑，如加载配置、连接数据库等
        return True
    
    def create_score_record(
        self,
        event_id: str,
        competitor_number: str,
        dance_name: str,
        judge_id: str,
        score: Optional[float] = None,
        mark: Optional[bool] = None,
        placement: Optional[int] = None
    ) -> Tuple[bool, Optional[ScoreRecord], List[str]]:
        """
        创建评分记录
        
        Args:
            event_id: 场次ID
            competitor_number: 选手编号
            dance_name: 舞种名称
            judge_id: 裁判ID
            score: 分数（顺位法）
            mark: 标记（Mark制）
            placement: 名次（顺位法）
            
        Returns:
            (是否成功, 评分记录对象, 错误信息列表)
        """
        self.logger.debug(f"开始创建评分记录: {competitor_number}, {dance_name}, {judge_id}")
        
        errors = []
        
        # 验证必要信息
        if not event_id:
            errors.append("场次ID不能为空")
            
        if not competitor_number:
            errors.append("选手编号不能为空")
        
        if not dance_name:
            errors.append("舞种名称不能为空")
        
        if not judge_id:
            errors.append("裁判ID不能为空")
        
        # 验证评分数据
        provided_fields = sum(1 for field in [score, mark, placement] if field is not None)
        if provided_fields == 0:
            errors.append("必须设置分数、标记或名次中的一个")
        elif provided_fields > 1:
            errors.append("只能设置分数、标记或名次中的一个")
        
        # 验证分数范围
        if score is not None and (score < 0 or score > 10):
            errors.append("分数必须在0-10之间")
        
        # 验证名次范围
        if placement is not None and placement < 1:
            errors.append("名次必须大于0")
        
        # 如果有错误，返回
        if errors:
            return False, None, errors
        
        # 创建评分记录
        record_id = str(uuid.uuid4())
        score_record = ScoreRecord(
            id=record_id,
            event_id=event_id,
            competitor_number=competitor_number,
            dance_name=dance_name,
            judge_id=judge_id,
            score=score,
            mark=mark,
            placement=placement
        )
        
        self.logger.debug(f"评分记录创建成功: {competitor_number}, {dance_name}, {judge_id}")
        return True, score_record, errors
    
    def update_score_record(
        self,
        score_record: ScoreRecord,
        score: Optional[float] = None,
        mark: Optional[bool] = None,
        placement: Optional[int] = None
    ) -> Tuple[bool, ScoreRecord, List[str]]:
        """
        更新评分记录
        
        Args:
            score_record: 评分记录对象
            score: 新的分数（顺位法）
            mark: 新的标记（Mark制）
            placement: 新的名次（顺位法）
            
        Returns:
            (是否成功, 更新后的评分记录对象, 错误信息列表)
        """
        self.logger.debug(f"开始更新评分记录: {score_record.competitor_number}, {score_record.dance_name}, {score_record.judge_id}")
        
        errors = []
        
        # 验证评分数据
        provided_fields = sum(1 for field in [score, mark, placement] if field is not None)
        if provided_fields == 0:
            errors.append("必须设置分数、标记或名次中的一个")
        elif provided_fields > 1:
            errors.append("只能设置分数、标记或名次中的一个")
        
        # 验证分数范围
        if score is not None and (score < 0 or score > 10):
            errors.append("分数必须在0-10之间")
        
        # 验证名次范围
        if placement is not None and placement < 1:
            errors.append("名次必须大于0")
        
        # 如果有错误，返回
        if errors:
            return False, score_record, errors
        
        # 更新评分记录
        score_record.score = score
        score_record.mark = mark
        score_record.placement = placement
        score_record.timestamp = datetime.now()
        
        self.logger.debug(f"评分记录更新成功: {score_record.competitor_number}, {score_record.dance_name}, {score_record.judge_id}")
        return True, score_record, errors
    
    def delete_score_record(self, score_record: ScoreRecord) -> Tuple[bool, List[str]]:
        """
        删除评分记录
        
        Args:
            score_record: 评分记录对象
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始删除评分记录: {score_record.competitor_number}, {score_record.dance_name}, {score_record.judge_id}")
        
        errors = []
        
        # 这里可以添加删除前的验证逻辑
        
        self.logger.debug(f"评分记录删除成功: {score_record.competitor_number}, {score_record.dance_name}, {score_record.judge_id}")
        return True, errors
    
    def validate_score_records(
        self,
        score_records: List[ScoreRecord],
        scoring_type: ScoringType
    ) -> Tuple[bool, List[str]]:
        """
        验证评分记录的有效性
        
        Args:
            score_records: 评分记录列表
            scoring_type: 评分类型
            
        Returns:
            (是否有效, 错误信息列表)
        """
        self.logger.debug("开始验证评分记录")
        
        errors = []
        
        # 检查是否有评分记录
        if not score_records:
            errors.append("没有评分记录")
            return False, errors
        
        # 按舞种和裁判分组
        dance_judge_records = {}
        for record in score_records:
            if record.dance_name not in dance_judge_records:
                dance_judge_records[record.dance_name] = {}
            
            if record.judge_id not in dance_judge_records[record.dance_name]:
                dance_judge_records[record.dance_name][record.judge_id] = []
            
            dance_judge_records[record.dance_name][record.judge_id].append(record)
        
        # 检查每个舞种-裁判组合的评分
        for dance_name, judge_records in dance_judge_records.items():
            for judge_id, records in judge_records.items():
                # 检查是否有重复评分
                competitor_set = set(record.competitor_number for record in records)
                if len(competitor_set) != len(records):
                    errors.append(f"舞种 {dance_name} 裁判 {judge_id} 存在重复评分")
                
                # 检查评分类型
                has_score = any(record.score is not None for record in records)
                has_placement = any(record.placement is not None for record in records)
                
                if has_score and has_placement:
                    errors.append(f"舞种 {dance_name} 裁判 {judge_id} 混合使用了分数和名次")
                elif not has_score and not has_placement:
                    errors.append(f"舞种 {dance_name} 裁判 {judge_id} 没有评分数据")
                elif scoring_type == ScoringType.MARK and not has_score:
                    errors.append(f"舞种 {dance_name} 裁判 {judge_id} 应使用Mark制评分")
                elif scoring_type == ScoringType.SKATING and not has_placement:
                    errors.append(f"舞种 {dance_name} 裁判 {judge_id} 应使用顺位法评分")
        
        self.logger.debug(f"评分记录验证完成，{len(errors)}个错误")
        return len(errors) == 0, errors
    
    def get_score_records_by_dance(
        self,
        score_records: List[ScoreRecord],
        dance_name: str
    ) -> List[ScoreRecord]:
        """
        获取指定舞种的评分记录
        
        Args:
            score_records: 评分记录列表
            dance_name: 舞种名称
            
        Returns:
            指定舞种的评分记录列表
        """
        return [record for record in score_records if record.dance_name == dance_name]
    
    def get_score_records_by_judge(
        self,
        score_records: List[ScoreRecord],
        judge_id: str
    ) -> List[ScoreRecord]:
        """
        获取指定裁判的评分记录
        
        Args:
            score_records: 评分记录列表
            judge_id: 裁判ID
            
        Returns:
            指定裁判的评分记录列表
        """
        return [record for record in score_records if record.judge_id == judge_id]
    
    def get_score_records_by_competitor(
        self,
        score_records: List[ScoreRecord],
        competitor_number: str
    ) -> List[ScoreRecord]:
        """
        获取指定选手的评分记录
        
        Args:
            score_records: 评分记录列表
            competitor_number: 选手编号
            
        Returns:
            指定选手的评分记录列表
        """
        return [record for record in score_records if record.competitor_number == competitor_number]
    
    def get_score_records_by_dance_judge(
        self,
        score_records: List[ScoreRecord],
        dance_name: str,
        judge_id: str
    ) -> List[ScoreRecord]:
        """
        获取指定舞种和裁判的评分记录
        
        Args:
            score_records: 评分记录列表
            dance_name: 舞种名称
            judge_id: 裁判ID
            
        Returns:
            指定舞种和裁判的评分记录列表
        """
        return [
            record for record in score_records 
            if record.dance_name == dance_name and record.judge_id == judge_id
        ]
    
    def export_score_records_to_json(
        self,
        score_records: List[ScoreRecord],
        file_path: str
    ) -> Tuple[bool, List[str]]:
        """
        导出评分记录到JSON文件
        
        Args:
            score_records: 评分记录列表
            file_path: 文件路径
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出评分记录到JSON: {file_path}")
        
        errors = []
        
        try:
            # 准备数据
            data = []
            for record in score_records:
                data.append({
                    "competitor_number": record.competitor_number,
                    "dance_name": record.dance_name,
                    "judge_id": record.judge_id,
                    "score": record.score,
                    "placement": record.placement,
                    "timestamp": record.timestamp.isoformat() if record.timestamp else None
                })
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"评分记录导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出评分记录失败: {e}")
            errors.append(f"文件写入失败: {str(e)}")
            return False, errors
    
    def import_score_records_from_json(
        self,
        file_path: str,
        event_id: str
    ) -> Tuple[bool, List[ScoreRecord], List[str]]:
        """
        从JSON文件导入评分记录
        
        Args:
            file_path: 文件路径
            event_id: 场次ID
            
        Returns:
            (是否成功, 评分记录列表, 错误信息列表)
        """
        self.logger.debug(f"开始从JSON导入评分记录: {file_path}")
        
        errors = []
        score_records = []
        
        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 逐个处理评分记录
            for i, record_data in enumerate(data):
                # 获取数据
                competitor_number = record_data.get("competitor_number", "")
                dance_name = record_data.get("dance_name", "")
                judge_id = record_data.get("judge_id", "")
                score = record_data.get("score")
                placement = record_data.get("placement")
                
                # 创建评分记录
                success, score_record, record_errors = self.create_score_record(
                    event_id=event_id,
                    competitor_number=competitor_number,
                    dance_name=dance_name,
                    judge_id=judge_id,
                    score=score,
                    placement=placement
                )
                
                if not success:
                    errors.extend([f"第{i+1}行: {error}" for error in record_errors])
                    continue
                
                # 设置时间
                timestamp_str = record_data.get("timestamp") or record_data.get("created_at", "")
                if timestamp_str:
                    try:
                        score_record.timestamp = datetime.fromisoformat(timestamp_str)
                    except ValueError:
                        errors.append(f"第{i+1}行: 无效的时间格式: {timestamp_str}")
                
                score_records.append(score_record)
            
            self.logger.debug(f"评分记录导入成功: {len(score_records)}条记录，{len(errors)}个错误")
            return len(score_records) > 0, score_records, errors
            
        except Exception as e:
            self.logger.error(f"导入评分记录失败: {e}")
            errors.append(f"文件读取失败: {str(e)}")
            return False, [], errors


# 创建全局评分输入管理器实例
scoring_input_manager = ScoringInputManager()