#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础数据模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ScoringType(Enum):
    """评分类型枚举"""
    MARK = "Mark制"  # 淘汰法
    SKATING = "顺位法"  # Skating System


class EventStatus(Enum):
    """赛事状态枚举"""
    NOT_STARTED = "未开始"
    IN_PROGRESS = "进行中"
    COMPLETED = "已完成"





@dataclass
class Competitor:
    """选手数据模型"""
    number: str  # 背番号
    name: str  # 姓名
    unit: str  # 学校/单位
    group: str  # 参赛组别
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "number": self.number,
            "name": self.name,
            "unit": self.unit,
            "group": self.group
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Competitor':
        """从字典创建实例"""
        return cls(
            number=str(data.get("number", "0")),
            name=data.get("name", ""),
            unit=data.get("unit", ""),
            group=data.get("group", "")
        )


@dataclass
class Judge:
    """裁判数据模型"""
    id: str  # 裁判ID
    name: str = ""  # 裁判姓名（可选）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Judge':
        """从字典创建实例"""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "")
        )


@dataclass
class Dance:
    """舞种数据模型"""
    name: str  # 舞种名称
    order: int = 0  # 顺序
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "order": self.order
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dance':
        """从字典创建实例"""
        return cls(
            name=data.get("name", ""),
            order=data.get("order", 0)
        )


@dataclass
class Event:
    """场次数据模型"""
    id: str  # 场次ID
    name: str  # 场次名称
    project_id: str  # 项目编号
    round: str  # 轮次（使用原始数字值）
    scoring_type: ScoringType  # 评分类型
    dances: List[Dance] = field(default_factory=list)  # 舞种列表
    competitors: List[str] = field(default_factory=list)  # 参赛选手背番号列表
    status: EventStatus = EventStatus.NOT_STARTED  # 场次状态
    advancement_count: int = 0  # 晋级人数（非决赛场次）
    advancement_rule: str = field(default='all_tied_advance')  # 晋级规则: 'all_tied_advance'或'strict_count'
    parent_event_id: Optional[str] = None  # 上一轮场次ID
    child_event_id: Optional[str] = None  # 下一轮场次ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "project_id": self.project_id,
            "round": self.round,
            "scoring_type": self.scoring_type.value,
            "dances": [dance.to_dict() for dance in self.dances],
            "competitors": self.competitors,
            "status": self.status.value,
            "advancement_count": self.advancement_count,
            "advancement_rule": self.advancement_rule,
            "parent_event_id": self.parent_event_id,
            "child_event_id": self.child_event_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """从字典创建实例"""
        dances = [Dance.from_dict(dance_data) for dance_data in data.get("dances", [])]
        scoring_type = ScoringType(data.get("scoring_type", ScoringType.MARK.value))
        status = EventStatus(data.get("status", EventStatus.NOT_STARTED.value))
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            project_id=data.get("project_id", ""),
            round=data.get("round", ""),
            scoring_type=scoring_type,
            dances=dances,
            competitors=[str(comp) for comp in data.get("competitors", [])],
            status=status,
            advancement_count=data.get("advancement_count", 0),
            advancement_rule=data.get("advancement_rule", "all_tied_advance"),
            parent_event_id=data.get("parent_event_id"),
            child_event_id=data.get("child_event_id")
        )


@dataclass
class ScoreRecord:
    """评分记录数据模型"""
    id: str  # 记录ID
    event_id: str  # 场次ID
    judge_id: str  # 裁判ID
    competitor_number: str  # 选手背番号
    dance_name: str  # 舞种名称
    score: Optional[float] = None  # 评分值（顺位法为float，Mark制为None）
    mark: Optional[bool] = None  # 标记（Mark制为bool，顺位制为None）
    placement: Optional[int] = None  # 名次（顺位法为int，Mark制为None）
    timestamp: datetime = field(default_factory=datetime.now)  # 记录时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "event_id": self.event_id,
            "judge_id": self.judge_id,
            "competitor_number": self.competitor_number,
            "dance_name": self.dance_name,
            "score": self.score,
            "mark": self.mark,
            "placement": self.placement,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScoreRecord':
        """从字典创建实例"""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        return cls(
            id=data.get("id", ""),
            event_id=data.get("event_id", ""),
            judge_id=data.get("judge_id", ""),
            competitor_number=str(data.get("competitor_number", "0")),
            dance_name=data.get("dance_name", ""),
            score=data.get("score"),
            mark=data.get("mark"),
            placement=data.get("placement"),
            timestamp=timestamp
        )


@dataclass
class Result:
    """比赛结果数据模型"""
    event_id: str  # 场次ID
    competitor_number: str  # 选手背番号
    rank: int  # 名次
    dance_name: str = ""  # 舞种名称
    score: float = 0.0  # 分数（Mark制为分数，顺位法中不使用此字段）
    total_score: float = 0.0  # 总分
    details: Dict[str, Any] = field(default_factory=dict)  # 详细得分信息
    advancement_status: bool = False  # 晋级状态：True(晋级)、False(未晋级)
    tied_with: List[str] = field(default_factory=list)  # 并列选手背番号列表
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "competitor_number": self.competitor_number,
            "rank": self.rank,
            "dance_name": self.dance_name,
            "score": self.score,
            "total_score": self.total_score,
            "details": self.details,
            "advancement_status": self.advancement_status,
            "tied_with": self.tied_with
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Result':
        """从字典创建实例"""
        return cls(
            event_id=data.get("event_id", ""),
            competitor_number=str(data.get("competitor_number", "0")),
            rank=data.get("rank", 0),
            dance_name=data.get("dance_name", ""),
            score=data.get("score", 0.0),
            total_score=data.get("total_score", 0.0),
            details=data.get("details", {}),
            advancement_status=data.get("advancement_status", False),
            tied_with=[str(tied) for tied in data.get("tied_with", [])]
        )


@dataclass
class CompetitionResult:
    """比赛结果数据模型（用于保存整个场次的结果）"""
    event_id: str  # 场次ID
    calculation_time: datetime  # 计算时间
    results_data: Dict[str, Any]  # 结果数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        # 确保results_data中的所有对象都是可序列化的
        serializable_results_data = {}
        
        for key, value in self.results_data.items():
            if hasattr(value, 'to_dict'):
                # 如果对象有to_dict方法，调用它
                serializable_results_data[key] = value.to_dict()
            elif isinstance(value, dict):
                # 如果是字典，递归处理其中的值
                serializable_results_data[key] = self._make_dict_serializable(value)
            else:
                # 其他类型直接使用
                serializable_results_data[key] = value
        
        return {
            "event_id": self.event_id,
            "calculation_time": self.calculation_time.isoformat(),
            "results_data": serializable_results_data
        }
    
    def _make_dict_serializable(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """递归地将字典中的所有值转换为可序列化格式"""
        result = {}
        for key, value in data_dict.items():
            if hasattr(value, 'to_dict'):
                result[key] = value.to_dict()
            elif isinstance(value, dict):
                result[key] = self._make_dict_serializable(value)
            elif isinstance(value, list):
                result[key] = [self._make_value_serializable(item) for item in value]
            else:
                result[key] = value
        return result
    
    def _make_value_serializable(self, value: Any) -> Any:
        """将单个值转换为可序列化格式"""
        if hasattr(value, 'to_dict'):
            return value.to_dict()
        elif isinstance(value, dict):
            return self._make_dict_serializable(value)
        elif isinstance(value, list):
            return [self._make_value_serializable(item) for item in value]
        else:
            return value
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CompetitionResult':
        """从字典创建实例"""
        calculation_time = data.get("calculation_time")
        if isinstance(calculation_time, str):
            calculation_time = datetime.fromisoformat(calculation_time)
        
        return cls(
            event_id=data.get("event_id", ""),
            calculation_time=calculation_time,
            results_data=data.get("results_data", {})
        )


@dataclass
class Competition:
    """比赛数据模型"""
    name: str  # 赛事名称
    date: str  # 赛事日期
    location: str  # 赛事地点
    competitors: Dict[str, Competitor] = field(default_factory=dict)  # 选手字典（键为背番号，兼容旧数据）
    competitor_mapping: Dict[str, Dict[str, Competitor]] = field(default_factory=dict)  # 选手映射：背番号→项目编号→选手信息
    judges: Dict[str, Judge] = field(default_factory=dict)  # 裁判字典（键为裁判ID）
    events: Dict[str, Event] = field(default_factory=dict)  # 场次字典（键为场次ID）
    score_records: List[ScoreRecord] = field(default_factory=list)  # 评分记录列表
    results: Dict[str, CompetitionResult] = field(default_factory=dict)  # 结果字典（键为场次ID）
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    updated_at: datetime = field(default_factory=datetime.now)  # 更新时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "date": self.date,
            "location": self.location,
            "competitors": {num: comp.to_dict() for num, comp in self.competitors.items()},
            "competitor_mapping": {
                number: {project_id: comp.to_dict() for project_id, comp in project_map.items()}
                for number, project_map in self.competitor_mapping.items()
            },
            "judges": {judge_id: judge.to_dict() for judge_id, judge in self.judges.items()},
            "events": {event_id: event.to_dict() for event_id, event in self.events.items()},
            "score_records": [record.to_dict() for record in self.score_records],
            "results": {event_id: result.to_dict() for event_id, result in self.results.items()},
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Competition':
        """从字典创建实例"""
        competitors = {
            num: Competitor.from_dict(comp_data) 
            for num, comp_data in data.get("competitors", {}).items()
        }
        
        # 构建选手映射
        competitor_mapping = {
            number: {
                project_id: Competitor.from_dict(comp_data) 
                for project_id, comp_data in project_map.items()
            }
            for number, project_map in data.get("competitor_mapping", {}).items()
        }
        
        judges = {
            judge_id: Judge.from_dict(judge_data) 
            for judge_id, judge_data in data.get("judges", {}).items()
        }
        
        events = {
            event_id: Event.from_dict(event_data) 
            for event_id, event_data in data.get("events", {}).items()
        }
        
        score_records = [
            ScoreRecord.from_dict(record_data) 
            for record_data in data.get("score_records", [])
        ]
        
        results = {
            event_id: CompetitionResult.from_dict(result_data)
            for event_id, result_data in data.get("results", {}).items()
        }
        
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        
        return cls(
            name=data.get("name", ""),
            date=data.get("date", ""),
            location=data.get("location", ""),
            competitors=competitors,
            competitor_mapping=competitor_mapping,
            judges=judges,
            events=events,
            score_records=score_records,
            results=results,
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now()
        )
    
    def update_timestamp(self):
        """更新时间戳"""
        self.updated_at = datetime.now()
    
    def get_score_record(self, event_id: str, dance_name: str, judge_id: str, competitor_number: str) -> Optional[ScoreRecord]:
        """获取指定条件下的评分记录"""
        for record in self.score_records:
            if (record.event_id == event_id and 
                record.dance_name == dance_name and 
                record.judge_id == judge_id and 
                record.competitor_number == competitor_number):
                return record
        return None
    
    def get_competitor(self, number: str) -> Optional[Competitor]:
        """获取指定编号的选手"""
        return self.competitors.get(number)
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """获取指定ID的场次"""
        return self.events.get(event_id)