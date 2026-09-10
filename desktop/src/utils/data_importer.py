#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据导入工具模块
"""

import os
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
import re

from ..models.data_models import Competitor, Judge, Dance, Event, ScoringType
from ..utils.logger import get_logger

logger = get_logger()


class DataImporter:
    """数据导入器类"""
    
    def __init__(self):
        """初始化数据导入器"""
        self.logger = logger
    
    def import_competitors_from_file(self, file_path: str) -> Tuple[bool, List[Competitor], Dict[str, Dict[str, Competitor]], List[str]]:
        """
        从文件导入选手信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            (是否成功, 选手列表, 选手映射字典, 错误信息列表)
        """
        self.logger.debug(f"开始导入选手信息: {file_path}")
        
        errors = []
        competitors = []
        competitor_mapping = {}  # 背番号→项目编号→选手信息
        
        try:
            # 读取文件
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, encoding='utf-8-sig', dtype={'背番号': str})
            else:
                df = pd.read_excel(file_path)
                # 确保背番号列是字符串类型
                df['背番号'] = df['背番号'].astype(str)
            
            # 检查必要的列，只支持新格式：背番号,项目编号,姓名,学校/单位
            required_columns = ['背番号', '项目编号', '姓名', '学校/单位']
            if not all(col in df.columns for col in required_columns):
                missing_columns = [col for col in required_columns if col not in df.columns]
                errors.append(f"文件格式错误：缺少必要的列 {missing_columns}。只支持新格式：背番号,项目编号,姓名,学校/单位")
                return False, [], {}, errors
            
            # 新格式处理：为每个背番号+项目编号组合创建选手
            for index, row in df.iterrows():
                try:
                    # 获取必要信息
                    number = str(row['背番号']).strip()
                    project_id = str(row['项目编号']).strip()
                    name = str(row['姓名']).strip()
                    unit = str(row['学校/单位']).strip()
                    
                    # 检查必要信息
                    if not number or not project_id or not name or not unit:
                        errors.append(f"第{index+1}行: 缺少必要信息")
                        continue
                    
                    # 组合参赛组别（使用项目编号）
                    group = project_id
                    
                    # 创建选手对象
                    competitor = Competitor(
                        number=number,
                        name=name,
                        unit=unit,
                        group=group
                    )
                    
                    # 添加到选手列表
                    competitors.append(competitor)
                    
                    # 更新选手映射
                    if number not in competitor_mapping:
                        competitor_mapping[number] = {}
                    competitor_mapping[number][project_id] = competitor
                    
                except Exception as e:
                    errors.append(f"第{index+1}行处理失败: {str(e)}")
            
            self.logger.debug(f"成功导入{len(competitors)}名选手，{len(errors)}个错误")
            return len(competitors) > 0, competitors, competitor_mapping, errors
            
        except Exception as e:
            self.logger.error(f"导入选手信息失败: {e}")
            errors.append(f"文件读取失败: {str(e)}")
            return False, [], {}, errors
    
    def import_judges_from_file(self, file_path: str) -> Tuple[bool, List[Judge], List[str]]:
        """
        从文件导入裁判信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            (是否成功, 裁判列表, 错误信息列表)
        """
        self.logger.debug(f"开始导入裁判信息: {file_path}")
        
        errors = []
        judges = []
        
        try:
            # 读取文件
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            else:
                df = pd.read_excel(file_path)
            
            # 检查必要的列
            required_columns = ['裁判编号', '姓名']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                errors.append(f"缺少必要的列: {', '.join(missing_columns)}")
                return False, [], errors
            
            # 逐行处理
            for index, row in df.iterrows():
                try:
                    # 获取必要信息
                    judge_id = str(row['裁判编号']).strip()
                    name = str(row['姓名']).strip()
                    
                    # 检查必要信息
                    if not judge_id or not name:
                        errors.append(f"第{index+1}行: 缺少必要信息")
                        continue
                    
                    # 创建裁判对象
                    judge = Judge(
                        id=judge_id,
                        name=name
                    )
                    
                    judges.append(judge)
                    
                except Exception as e:
                    errors.append(f"第{index+1}行处理失败: {str(e)}")
            
            self.logger.debug(f"成功导入{len(judges)}名裁判，{len(errors)}个错误")
            return len(judges) > 0, judges, errors
            
        except Exception as e:
            self.logger.error(f"导入裁判信息失败: {e}")
            errors.append(f"文件读取失败: {str(e)}")
            return False, [], errors
    
    def import_schedule_from_file(self, file_path: str) -> Tuple[bool, List[Event], List[str]]:
        """
        从文件导入赛程信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            (是否成功, 场次列表, 错误信息列表)
        """
        self.logger.debug(f"开始导入赛程信息: {file_path}")
        
        errors = []
        events = []
        
        try:
            # 读取文件
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            else:
                df = pd.read_excel(file_path)
            
            # 检查必要的列
            required_columns = ['场次编号', '场次名称', '舞种', '评分类型', '轮次']
            # 晋级人数列是可选的，但如果存在则会使用
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                errors.append(f"缺少必要的列: {', '.join(missing_columns)}")
                return False, [], errors
            
            # 逐行处理
            for index, row in df.iterrows():
                try:
                    # 获取必要信息
                    event_id = str(row['场次编号']).strip()
                    name = str(row['场次名称']).strip()
                    dance_name = str(row['舞种']).strip()
                    scoring_type_str = str(row['评分类型']).strip()
                    round_type_str = str(row['轮次']).strip()
                    
                    # 获取晋级人数（可选）
                    advancement_count = 0
                    if '晋级人数' in row and pd.notna(row['晋级人数']):
                        try:
                            advancement_count = int(row['晋级人数'])
                        except ValueError:
                            errors.append(f"第{index+1}行: 晋级人数格式错误: {row['晋级人数']}")
                            advancement_count = 0
                    
                    # 检查必要信息
                    if not event_id or not name or not dance_name or not scoring_type_str or not round_type_str:
                        errors.append(f"第{index+1}行: 缺少必要信息")
                        continue
                    
                    # 转换评分类型
                    if scoring_type_str == "Mark制":
                        scoring_type = ScoringType.MARK
                    elif scoring_type_str == "顺位法":
                        scoring_type = ScoringType.SKATING
                    else:
                        errors.append(f"第{index+1}行: 无效的评分类型: {scoring_type_str}")
                        continue
                    
                    # 使用原始轮次值
                    round_value = round_type_str
                    
                    # 创建舞种对象
                    dance = Dance(name=dance_name)
                    
                    # 创建场次对象
                    event = Event(
                        id=event_id,
                        name=name,
                        dances=[dance],
                        scoring_type=scoring_type,
                        round=round_value,  # 使用原始轮次值
                        advancement_count=advancement_count
                    )
                    
                    events.append(event)
                    
                except Exception as e:
                    errors.append(f"第{index+1}行处理失败: {str(e)}")
            
            self.logger.debug(f"成功导入{len(events)}个场次，{len(errors)}个错误")
            return len(events) > 0, events, errors
            
        except Exception as e:
            self.logger.error(f"导入赛程信息失败: {e}")
            errors.append(f"文件读取失败: {str(e)}")
            return False, [], errors
    
    def import_batch_from_directory(self, directory_path: str) -> Dict[str, Tuple[bool, Any, Any, List[str]]]:
        """
        从目录批量导入数据
        
        Args:
            directory_path: 目录路径
            
        Returns:
            导入结果字典，包含各类数据的导入结果
        """
        self.logger.debug(f"开始批量导入数据: {directory_path}")
        
        results = {}
        
        # 检查目录是否存在
        if not os.path.exists(directory_path):
            error_msg = f"目录不存在: {directory_path}"
            self.logger.error(error_msg)
            return {"error": (False, None, None, [error_msg])}
        
        # 查找选手信息文件
        competitors_file = None
        for file in os.listdir(directory_path):
            if file.startswith('test_competitors') and (file.endswith('.csv') or file.endswith('.xlsx')):
                competitors_file = os.path.join(directory_path, file)
                break
        
        if competitors_file:
            success, competitors, competitor_mapping, errors = self.import_competitors_from_file(competitors_file)
            results["competitors"] = (success, competitors, competitor_mapping, errors)
        else:
            results["competitors"] = (False, [], {}, ["未找到选手信息文件"])
        
        # 查找赛程信息文件
        schedule_file = None
        for file in os.listdir(directory_path):
            if file.startswith('test_schedule') and (file.endswith('.csv') or file.endswith('.xlsx')):
                schedule_file = os.path.join(directory_path, file)
                break
        
        if schedule_file:
            success, events, errors = self.import_schedule_from_file(schedule_file)
            results["events"] = (success, events, None, errors)
        else:
            results["events"] = (False, [], None, ["未找到赛程信息文件"])
        
        # 查找裁判信息文件
        judges_file = None
        for file in os.listdir(directory_path):
            if file.startswith('test_judges') and (file.endswith('.csv') or file.endswith('.xlsx')):
                judges_file = os.path.join(directory_path, file)
                break
        
        if judges_file:
            success, judges, errors = self.import_judges_from_file(judges_file)
            results["judges"] = (success, judges, None, errors)
        else:
            results["judges"] = (False, [], None, ["未找到裁判信息文件"])
        
        self.logger.debug("批量导入完成")
        return results
    
    def export_competitors_to_file(self, competitors: List[Competitor], file_path: str) -> Tuple[bool, List[str]]:
        """
        导出选手信息到文件
        
        Args:
            competitors: 选手列表
            file_path: 文件路径
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出选手信息: {file_path}")
        
        errors = []
        
        try:
            # 准备数据
            data = []
            for competitor in competitors:
                data.append({
                    '背番号': competitor.number,
                    '姓名': competitor.name,
                    '学校/单位': competitor.unit,
                    '参赛组别': competitor.group
                })
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 导出文件
            if file_path.lower().endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                df.to_excel(file_path, index=False)
            
            self.logger.debug(f"成功导出{len(competitors)}名选手信息")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出选手信息失败: {e}")
            errors.append(f"文件写入失败: {str(e)}")
            return False, errors
    
    def export_judges_to_file(self, judges: List[Judge], file_path: str) -> Tuple[bool, List[str]]:
        """
        导出裁判信息到文件
        
        Args:
            judges: 裁判列表
            file_path: 文件路径
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出裁判信息: {file_path}")
        
        errors = []
        
        try:
            # 准备数据
            data = []
            for judge in judges:
                data.append({
                    '裁判编号': judge.id,
                    '姓名': judge.name
                })
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 导出文件
            if file_path.lower().endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                df.to_excel(file_path, index=False)
            
            self.logger.debug(f"成功导出{len(judges)}名裁判信息")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出裁判信息失败: {e}")
            errors.append(f"文件写入失败: {str(e)}")
            return False, errors
    
    def export_schedule_to_file(self, events: List[Event], file_path: str) -> Tuple[bool, List[str]]:
        """
        导出赛程信息到文件
        
        Args:
            events: 场次列表
            file_path: 文件路径
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出赛程信息: {file_path}")
        
        errors = []
        
        try:
            # 准备数据
            data = []
            for event in events:
                for dance in event.dances:
                    scoring_type_str = "Mark制" if event.scoring_type == ScoringType.MARK else "顺位法"
                    round_type_str = {
                        RoundType.PRELIMINARY: "预赛",
                        RoundType.SEMIFINAL: "半决赛",
                        RoundType.FINAL: "决赛"
                    }.get(event.round_type, "未知")
                    
                    data.append({
                        '场次编号': event.id,
                        '场次名称': event.name,
                        '舞种': dance.name,
                        '评分类型': scoring_type_str,
                        '轮次': round_type_str
                    })
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 导出文件
            if file_path.lower().endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                df.to_excel(file_path, index=False)
            
            self.logger.debug(f"成功导出{len(events)}个场次信息")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出赛程信息失败: {e}")
            errors.append(f"文件写入失败: {str(e)}")
            return False, errors


# 创建全局数据导入器实例
data_importer = DataImporter()