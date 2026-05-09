#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
滑冰法打分明细数据模型
用于存储顺位制评分的详细计算过程
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class SkatingScoreDetail:
    """滑冰法打分明细数据模型"""
    event_id: str  # 场次ID
    dance_name: str  # 舞种名称
    competitor_number: str  # 选手背番号
    judge_placements: Dict[str, int] = field(default_factory=dict)  # 各裁判给出的名次 {裁判ID: 名次}
    placement_counts: Dict[int, int] = field(default_factory=dict)  # 各名次获得次数 {名次: 次数}
    cumulative_votes: Dict[int, int] = field(default_factory=dict)  # 累积得票数 {名次: 累积得票数}
    sum_placement: int = 0  # 序和（所有名次之和）
    final_rank: int = 0  # 最终排名
    majority_rank: Optional[int] = None  # 多数裁决名次（获得多数票的名次）
    details: Dict[str, Any] = field(default_factory=dict)  # 其他详细信息，如区间统计
    calculation_time: datetime = field(default_factory=datetime.now)  # 计算时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "dance_name": self.dance_name,
            "competitor_number": self.competitor_number,
            "judge_placements": self.judge_placements,
            "placement_counts": self.placement_counts,
            "cumulative_votes": self.cumulative_votes,
            "sum_placement": self.sum_placement,
            "final_rank": self.final_rank,
            "majority_rank": self.majority_rank,
            "details": self.details,
            "calculation_time": self.calculation_time.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkatingScoreDetail':
        """从字典创建实例"""
        calculation_time = data.get("calculation_time")
        if isinstance(calculation_time, str):
            calculation_time = datetime.fromisoformat(calculation_time)
        
        return cls(
            event_id=data.get("event_id", ""),
            dance_name=data.get("dance_name", ""),
            competitor_number=str(data.get("competitor_number", "0")),
            judge_placements=data.get("judge_placements", {}),
            placement_counts=data.get("placement_counts", {}),
            cumulative_votes=data.get("cumulative_votes", {}),
            sum_placement=data.get("sum_placement", 0),
            final_rank=data.get("final_rank", 0),
            majority_rank=data.get("majority_rank"),
            details=data.get("details", {}),
            calculation_time=calculation_time
        )


@dataclass
class SkatingOverallDetail:
    """滑冰法综合打分明细数据模型"""
    event_id: str  # 场次ID
    competitor_number: str  # 选手背番号
    dance_details: Dict[str, SkatingScoreDetail] = field(default_factory=dict)  # 各舞种明细 {舞种名: 明细}
    total_sum_placement: int = 0  # 总序和（所有舞种序和之和）
    final_rank: int = 0  # 最终排名
    overall_majority_rank: Optional[float] = None  # 综合多数裁决名次（各舞种多数裁决名次的中位数）
    calculation_time: datetime = field(default_factory=datetime.now)  # 计算时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "competitor_number": self.competitor_number,
            "dance_details": {dance: detail.to_dict() for dance, detail in self.dance_details.items()},
            "total_sum_placement": self.total_sum_placement,
            "final_rank": self.final_rank,
            "overall_majority_rank": self.overall_majority_rank,
            "calculation_time": self.calculation_time.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkatingOverallDetail':
        """从字典创建实例"""
        calculation_time = data.get("calculation_time")
        if isinstance(calculation_time, str):
            calculation_time = datetime.fromisoformat(calculation_time)
        
        dance_details = {}
        for dance_name, detail_data in data.get("dance_details", {}).items():
            dance_details[dance_name] = SkatingScoreDetail.from_dict(detail_data)
        
        return cls(
            event_id=data.get("event_id", ""),
            competitor_number=str(data.get("competitor_number", "0")),
            dance_details=dance_details,
            total_sum_placement=data.get("total_sum_placement", 0),
            final_rank=data.get("final_rank", 0),
            overall_majority_rank=data.get("overall_majority_rank"),
            calculation_time=calculation_time
        )