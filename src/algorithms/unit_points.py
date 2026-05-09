#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单位总分统计模块
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime

from ..models.data_models import (
    AwardPointsConfig, UnitPointsRecord, UnitTotalPoints,
    CompetitionUnitPoints, Result, Event, Competitor
)


class UnitPointsCalculator:
    """单位总分计算器"""

    def __init__(self):
        self.award_configs: Dict[str, AwardPointsConfig] = {}
        self.unit_points: Dict[str, UnitTotalPoints] = {}

    def set_award_config(self, event_id: str, config: AwardPointsConfig):
        """设置奖项得分配置"""
        self.award_configs[event_id] = config

    def get_award_config(self, event_id: str) -> AwardPointsConfig:
        """获取奖项得分配置"""
        if event_id in self.award_configs:
            return self.award_configs[event_id]
        return AwardPointsConfig(event_id=event_id)

    def calculate_unit_points_from_results(
        self,
        event: Event,
        results: List[Result],
        competitors: Dict[str, Competitor],
        award_config: Optional[AwardPointsConfig] = None
    ) -> List[UnitPointsRecord]:
        """从比赛结果计算单位得分"""
        if award_config is None:
            award_config = self.get_award_config(event.id)

        records = []

        for result in results:
            competitor_number = result.competitor_number
            rank = result.rank

            if rank <= 0 or rank > award_config.get_max_rank():
                continue

            base_points = award_config.get_points(rank)
            if base_points <= 0:
                continue

            competitor = competitors.get(competitor_number)
            if not competitor:
                continue

            if competitor.is_couple and competitor.partner_unit:
                split_points = base_points / 2.0
                self_unit_record = UnitPointsRecord(
                    unit=competitor.unit,
                    event_id=event.id,
                    event_name=event.name,
                    competitor_number=competitor_number,
                    competitor_name=competitor.name,
                    rank=rank,
                    points=split_points,
                    is_split=True,
                    split_ratio=0.5,
                    is_couple=True
                )
                records.append(self_unit_record)

                partner_unit = competitor.partner_unit
                partner_record = UnitPointsRecord(
                    unit=partner_unit,
                    event_id=event.id,
                    event_name=event.name,
                    competitor_number=competitor.partner_number or "",
                    competitor_name=competitor.partner_name or "",
                    rank=rank,
                    points=split_points,
                    is_split=True,
                    split_ratio=0.5,
                    is_couple=True
                )
                records.append(partner_record)
            else:
                record = UnitPointsRecord(
                    unit=competitor.unit,
                    event_id=event.id,
                    event_name=event.name,
                    competitor_number=competitor_number,
                    competitor_name=competitor.name,
                    rank=rank,
                    points=base_points,
                    is_split=False,
                    split_ratio=1.0,
                    is_couple=False
                )
                records.append(record)

        return records

    def add_unit_points(self, records: List[UnitPointsRecord]):
        """添加单位得分记录"""
        for record in records:
            unit = record.unit
            if not unit:
                continue

            if unit not in self.unit_points:
                self.unit_points[unit] = UnitTotalPoints(unit=unit)

            self.unit_points[unit].add_record(record)

    def get_ranking(self) -> List[Tuple[str, float, int]]:
        """获取单位排名 (单位名, 总分, 排名)"""
        ranking = [(unit, pts.total_points, pts.rank)
                   for unit, pts in self.unit_points.items()]
        ranking.sort(key=lambda x: (-x[1], x[0]))

        for i, (unit, _, _) in enumerate(ranking):
            self.unit_points[unit].rank = i + 1

        return [(unit, pts.total_points, pts.rank)
                for unit, pts in self.unit_points.items()]

    def get_unit_details(self, unit: str) -> Optional[UnitTotalPoints]:
        """获取单位详细得分"""
        return self.unit_points.get(unit)

    def get_all_units(self) -> List[str]:
        """获取所有单位列表"""
        return list(self.unit_points.keys())

    def get_total_points(self, unit: str) -> float:
        """获取单位总分"""
        if unit in self.unit_points:
            return self.unit_points[unit].total_points
        return 0.0

    def clear_unit_points(self):
        """清除所有单位得分"""
        self.unit_points.clear()

    def clear_unit_points_by_event(self, event_id: str):
        """清除指定场次的单位得分"""
        for unit_pts in self.unit_points.values():
            unit_pts.records = [
                r for r in unit_pts.records if r.event_id != event_id
            ]
        for unit_pts in self.unit_points.values():
            unit_pts.total_points = sum(r.points for r in unit_pts.records)

    def export_to_competition_unit_points(self, competition_id: str) -> CompetitionUnitPoints:
        """导出为CompetitionUnitPoints对象"""
        result = CompetitionUnitPoints(
            competition_id=competition_id,
            unit_points=self.unit_points,
            last_update=datetime.now()
        )
        result.get_ranking()
        return result

    def import_from_competition_unit_points(self, data: CompetitionUnitPoints):
        """从CompetitionUnitPoints导入"""
        self.unit_points = data.unit_points
        for event_config in self.award_configs.values():
            if event_config.event_id not in self.award_configs:
                pass


def calculate_unit_points_for_event(
    event: Event,
    results: List[Result],
    competitors: Dict[str, Competitor],
    award_config: AwardPointsConfig
) -> List[UnitPointsRecord]:
    """便捷函数：计算单个场次的单位得分"""
    calculator = UnitPointsCalculator()
    return calculator.calculate_unit_points_from_results(
        event, results, competitors, award_config
    )


def merge_unit_points_lists(records_list: List[List[UnitPointsRecord]]) -> List[UnitPointsRecord]:
    """合并多个单位得分记录列表"""
    unit_records: Dict[Tuple[str, str], UnitPointsRecord] = {}

    for records in records_list:
        for record in records:
            key = (record.unit, record.event_id, record.competitor_number)
            if key not in unit_records:
                unit_records[key] = record
            else:
                existing = unit_records[key]
                if abs(existing.points - record.points) < 0.001:
                    pass
                else:
                    unit_records[key] = UnitPointsRecord(
                        unit=record.unit,
                        event_id=record.event_id,
                        event_name=record.event_name,
                        competitor_number=record.competitor_number,
                        competitor_name=record.competitor_name,
                        rank=record.rank,
                        points=existing.points + record.points,
                        is_split=record.is_split,
                        split_ratio=record.split_ratio,
                        is_couple=record.is_couple
                    )

    return list(unit_records.values())
