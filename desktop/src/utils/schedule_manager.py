#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛程管理工具模块
"""

from typing import Dict, List, Tuple, Optional
import os
import json
import re
from datetime import datetime

from ..models.data_models import Event, EventStatus, Dance, ScoringType
from ..utils.logger import get_logger

logger = get_logger()


class ScheduleManager:
    """赛程管理器类"""
    
    def __init__(self):
        """初始化赛程管理器"""
        self.logger = logger
    
    def initialize(self):
        """初始化赛程管理器"""
        self.logger.info("赛程管理器初始化")
        # 这里可以添加初始化逻辑，如加载配置、连接数据库等
        return True
    
    def create_event(
        self, event_id: str, name: str, dance_names: List[str], scoring_type: ScoringType,
        round_type: str,
        advancement_count: int = 0
    ) -> Tuple[bool, Optional[Event], List[str]]:
        """
        创建场次
        
        Args:
            event_id: 场次ID
            name: 场次名称
            dance_names: 舞种名称列表
            scoring_type: 评分类型
            round_type: 轮次
            advancement_count: 晋级人数
        
        Returns:
            (是否成功, 场次对象, 错误信息列表)
        """
        self.logger.debug(f"开始创建场次: {event_id}")
        
        errors = []
        
        # 验证场次ID
        if not event_id:
            errors.append("场次ID不能为空")
        elif not self._is_valid_event_id(event_id):
            errors.append("场次ID格式无效，应为字母、数字和下划线的组合")
        
        # 验证场次名称
        if not name:
            errors.append("场次名称不能为空")
        
        # 验证舞种
        if not dance_names:
            errors.append("至少需要一个舞种")
        else:
            for dance_name in dance_names:
                if not dance_name:
                    errors.append("舞种名称不能为空")
        
        # 如果有错误，返回
        if errors:
            return False, None, errors
        
        # 创建舞种对象
        dances = [Dance(name=dance_name) for dance_name in dance_names]
        
        # 创建场次对象
        event = Event(
            id=event_id,
            name=name,
            dances=dances,
            scoring_type=scoring_type,
            round=round_type,  # 使用原始轮次数据
            advancement_count=advancement_count
        )
        
        self.logger.debug(f"场次创建成功: {event_id}")
        return True, event, errors
    
    def update_event(
        self,
        event: Event,
        name: Optional[str] = None,
        dance_names: Optional[List[str]] = None,
        scoring_type: Optional[ScoringType] = None,
        round: Optional[str] = None
    ) -> Tuple[bool, Event, List[str]]:
        """
        更新场次信息
        
        Args:
            event: 场次对象
            name: 新的场次名称
            dance_names: 新的舞种名称列表
            scoring_type: 新的评分类型
            round: 新的轮次
        
    Returns:
        (是否成功, 更新后的场次对象, 错误信息列表)
    """
        self.logger.debug(f"开始更新场次: {event.id}")
        
        errors = []
        
        # 检查场次状态
        if event.status == EventStatus.IN_PROGRESS:
            errors.append("场次进行中，无法修改")
        elif event.status == EventStatus.COMPLETED:
            errors.append("场次已完成，无法修改")
        
        # 如果有错误，返回
        if errors:
            return False, event, errors
        
        # 更新场次名称
        if name is not None:
            if not name:
                errors.append("场次名称不能为空")
            else:
                event.name = name
        
        # 更新舞种
        if dance_names is not None:
            if not dance_names:
                errors.append("至少需要一个舞种")
            else:
                for dance_name in dance_names:
                    if not dance_name:
                        errors.append("舞种名称不能为空")
                
                if not errors:
                    event.dances = [Dance(name=dance_name) for dance_name in dance_names]
        
        # 更新评分类型
        if scoring_type is not None:
            event.scoring_type = scoring_type
        
        # 更新轮次类型
        if round is not None:
            event.round = round
        
        # 如果有错误，返回
        if errors:
            return False, event, errors
        
        self.logger.debug(f"场次更新成功: {event.id}")
        return True, event, errors
    
    def delete_event(self, event: Event) -> Tuple[bool, List[str]]:
        """
        删除场次
        
        Args:
            event: 场次对象
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始删除场次: {event.id}")
        
        errors = []
        
        # 检查场次状态
        if event.status == EventStatus.IN_PROGRESS:
            errors.append("场次进行中，无法删除")
        elif event.status == EventStatus.COMPLETED:
            errors.append("场次已完成，无法删除")
        
        # 如果有错误，返回
        if errors:
            return False, errors
        
        self.logger.debug(f"场次删除成功: {event.id}")
        return True, errors
    
    def start_event(self, event: Event) -> Tuple[bool, List[str]]:
        """
        开始场次
        
        Args:
            event: 场次对象
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始场次: {event.id}")
        
        errors = []
        
        # 检查场次状态
        if event.status == EventStatus.IN_PROGRESS:
            errors.append("场次已经在进行中")
        elif event.status == EventStatus.COMPLETED:
            errors.append("场次已完成，无法重新开始")
        
        # 如果有错误，返回
        if errors:
            return False, errors
        
        # 更新场次状态
        event.status = EventStatus.IN_PROGRESS
        event.start_time = datetime.now()
        
        self.logger.debug(f"场次开始成功: {event.id}")
        return True, errors
    
    def complete_event(self, event: Event) -> Tuple[bool, List[str]]:
        """
        完成场次
        
        Args:
            event: 场次对象
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"完成场次: {event.id}")
        
        errors = []
        
        # 检查场次状态
        if event.status == EventStatus.NOT_STARTED:
            errors.append("场次尚未开始")
        elif event.status == EventStatus.COMPLETED:
            errors.append("场次已完成")
        
        # 如果有错误，返回
        if errors:
            return False, errors
        
        # 更新场次状态
        event.status = EventStatus.COMPLETED
        event.end_time = datetime.now()
        
        self.logger.debug(f"场次完成成功: {event.id}")
        return True, errors
    
    def get_event_status(self, event: Event) -> Tuple[bool, str, List[str]]:
        """
        获取场次状态
        
        Args:
            event: 场次对象
            
        Returns:
            (是否成功, 状态描述, 错误信息列表)
        """
        errors = []
        
        # 检查场次状态
        status_text = ""
        if event.status == EventStatus.NOT_STARTED:
            status_text = "待开始"
        elif event.status == EventStatus.IN_PROGRESS:
            status_text = "进行中"
        elif event.status == EventStatus.COMPLETED:
            status_text = "已完成"
        else:
            status_text = "未知状态"
            errors.append("未知的场次状态")
        
        return len(errors) == 0, status_text, errors
    
    def get_event_info(self, event: Event) -> Dict:
        """
        获取场次信息
        
        Args:
            event: 场次对象
            
        Returns:
            场次信息字典
        """
        # 获取状态描述
        _, status_text, _ = self.get_event_status(event)
        
        # 获取评分类型描述
        scoring_type_text = ""
        if event.scoring_type == ScoringType.MARK:
            scoring_type_text = "Mark制"
        elif event.scoring_type == ScoringType.SKATING:
            scoring_type_text = "顺位法"
        else:
            scoring_type_text = "未知"
        
        # 获取轮次类型描述
        round_type_text = ""
        if event.round_type == RoundType.PRELIMINARY:
            round_type_text = "预赛"
        elif event.round_type == RoundType.SEMIFINAL:
            round_type_text = "半决赛"
        elif event.round_type == RoundType.FINAL:
            round_type_text = "决赛"
        else:
            round_type_text = "未知"
        
        # 获取舞种列表
        dance_names = [dance.name for dance in event.dances]
        
        # 格式化时间
        start_time_str = ""
        if event.start_time:
            start_time_str = event.start_time.strftime("%Y-%m-%d %H:%M:%S")
        
        end_time_str = ""
        if event.end_time:
            end_time_str = event.end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "id": event.id,
            "name": event.name,
            "status": status_text,
            "scoring_type": scoring_type_text,
            "round": event.round,
            "dance_names": dance_names,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "advancement_count": event.advancement_count
        }
    
    def export_schedule_to_json(self, events: Dict[str, Event], file_path: str) -> Tuple[bool, List[str]]:
        """
        导出赛程到JSON文件
        
        Args:
            events: 场次字典
            file_path: 文件路径
            
        Returns:
            (是否成功, 错误信息列表)
        """
        self.logger.debug(f"开始导出赛程到JSON: {file_path}")
        
        errors = []
        
        try:
            # 准备数据
            data = {}
            for event_id, event in events.items():
                data[event_id] = self.get_event_info(event)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"赛程导出成功: {file_path}")
            return True, errors
            
        except Exception as e:
            self.logger.error(f"导出赛程失败: {e}")
            errors.append(f"文件写入失败: {str(e)}")
            return False, errors
    
    def import_schedule_from_json(self, file_path: str) -> Tuple[bool, Dict[str, Event], List[str]]:
        """
        从JSON文件导入赛程
        
        Args:
            file_path: 文件路径
            
        Returns:
            (是否成功, 场次字典, 错误信息列表)
        """
        self.logger.debug(f"开始从JSON导入赛程: {file_path}")
        
        errors = []
        events = {}
        
        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 逐个处理场次
            for event_id, event_info in data.items():
                # 获取评分类型
                scoring_type_str = event_info.get("scoring_type", "")
                if scoring_type_str == "Mark制":
                    scoring_type = ScoringType.MARK
                elif scoring_type_str == "顺位法":
                    scoring_type = ScoringType.SKATING
                else:
                    errors.append(f"场次 {event_id}: 无效的评分类型: {scoring_type_str}")
                    continue
                
                # 获取原始轮次值
                round_value = str(event_info.get("round", ""))
                
                # 创建场次
                success, event, event_errors = self.create_event(
                    event_id=event_id,
                    name=event_info.get("name", ""),
                    dance_names=event_info.get("dance_names", []),
                    scoring_type=scoring_type,
                    round_type=round_value,  # 直接使用原始轮次值
                    advancement_count=event_info.get("advancement_count", 0)
                )
                
                if not success:
                    errors.extend([f"场次 {event_id}: {error}" for error in event_errors])
                    continue
                
                # 设置场次状态
                status_str = event_info.get("status", "")
                if status_str == "进行中":
                    event.status = EventStatus.IN_PROGRESS
                elif status_str == "已完成":
                    event.status = EventStatus.COMPLETED
                
                # 设置时间
                start_time_str = event_info.get("start_time", "")
                if start_time_str:
                    try:
                        event.start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        errors.append(f"场次 {event_id}: 无效的开始时间格式: {start_time_str}")
                
                end_time_str = event_info.get("end_time", "")
                if end_time_str:
                    try:
                        event.end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        errors.append(f"场次 {event_id}: 无效的结束时间格式: {end_time_str}")
                
                events[event_id] = event
            
            self.logger.debug(f"赛程导入成功: {len(events)}个场次，{len(errors)}个错误")
            return len(events) > 0, events, errors
            
        except Exception as e:
            self.logger.error(f"导入赛程失败: {e}")
            errors.append(f"文件读取失败: {str(e)}")
            return False, {}, errors
    
    def _is_valid_event_id(self, event_id: str) -> bool:
        """
        验证场次ID是否有效
        
        Args:
            event_id: 场次ID
            
        Returns:
            是否有效
        """
        # 场次ID应为字母、数字和下划线的组合
        return bool(re.match(r'^[a-zA-Z0-9_]+$', event_id))


# 创建全局赛程管理器实例
schedule_manager = ScheduleManager()