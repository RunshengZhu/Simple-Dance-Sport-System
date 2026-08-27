"""
单位总分统计服务
"""
from typing import Dict, List, Any
from collections import defaultdict
import json


class RankingService:
    """单位总分统计服务"""

    DEFAULT_POINTS = {"1": 9.0, "2": 7.0, "3": 6.0, "4": 5.0,
                      "5": 4.0, "6": 3.0, "7": 2.0, "8": 1.0}

    async def update_unit_points(self, competition_id: str, event_id: str, db):
        """
        单个场次完成后更新单位总分
        
        Args:
            competition_id: 比赛ID
            event_id: 场次ID
            db: 数据库会话
        """
        from sqlalchemy import select, delete
        from app.models.event import Event
        from app.models.result import Result
        from app.models.competitor import Competitor
        from app.models.unit_points import AwardConfig, UnitPoints, UnitPointRecord
        import json
        
        # 获取场次信息
        event_result = await db.execute(select(Event).where(Event.id == event_id))
        event = event_result.scalar_one_or_none()
        if not event or event.status != "completed":
            return
        
        # 获取所有选手信息
        competitors_result = await db.execute(select(Competitor).where(Competitor.competition_id == competition_id))
        competitors = [{
            "number": c.number,
            "name": c.name,
            "unit": c.unit,
            "is_couple": c.is_couple,
            "partner_unit": c.partner_unit
        } for c in competitors_result.scalars().all()]
        
        # 获取奖项配置
        config_result = await db.execute(select(AwardConfig).where(AwardConfig.event_id == event_id))
        config = config_result.scalar_one_or_none()
        award_configs = {}
        if config:
            award_configs[event_id] = json.loads(config.points)
        else:
            award_configs[event_id] = self.DEFAULT_POINTS
        
        # 获取本场次的结果
        results_result = await db.execute(select(Result).where(Result.event_id == event_id))
        results = results_result.scalars().all()
        results_list = [{"competitor_number": r.competitor_number, "rank": r.rank} for r in results]
        
        # 计算本场次的单位得分
        unit_points = self.calculate_unit_points(
            results_list, competitors, award_configs, event.name, event_id
        )
        
        # 获取所有已完成场次，重新计算完整排名
        events_result = await db.execute(select(Event).where(Event.competition_id == competition_id))
        all_events = events_result.scalars().all()
        
        all_unit_points = []
        
        for evt in all_events:
            if evt.status != "completed":
                continue
            
            # 获取该场次的奖项配置
            evt_config_result = await db.execute(select(AwardConfig).where(AwardConfig.event_id == evt.id))
            evt_config = evt_config_result.scalar_one_or_none()
            if evt_config:
                award_configs[evt.id] = json.loads(evt_config.points)
            else:
                award_configs[evt.id] = self.DEFAULT_POINTS
            
            # 获取该场次的结果
            evt_results_result = await db.execute(select(Result).where(Result.event_id == evt.id))
            evt_results = evt_results_result.scalars().all()
            evt_results_list = [{"competitor_number": r.competitor_number, "rank": r.rank} for r in evt_results]
            
            # 计算单位得分
            evt_unit_points = self.calculate_unit_points(
                evt_results_list, competitors, award_configs, evt.name, evt.id
            )
            all_unit_points.extend(evt_unit_points)
        
        # 聚合所有单位得分
        aggregated = {}
        for up in all_unit_points:
            unit = up["unit"]
            if unit not in aggregated:
                aggregated[unit] = {"total_points": 0.0, "record_count": 0, "records": []}
            aggregated[unit]["total_points"] += up["total_points"]
            aggregated[unit]["record_count"] += up["record_count"]
            aggregated[unit]["records"].extend(up["records"])
        
        # 删除旧的单位总分记录
        await db.execute(delete(UnitPoints).where(UnitPoints.competition_id == competition_id))
        
        # 重新创建单位总分记录
        for unit, data in aggregated.items():
            up = UnitPoints(
                id=str(uuid.uuid4()),
                competition_id=competition_id,
                unit=unit,
                total_points=data["total_points"],
                record_count=data["record_count"]
            )
            db.add(up)
            await db.flush()
            
            for record in data["records"]:
                rec = UnitPointRecord(
                    id=str(uuid.uuid4()),
                    unit_points_id=up.id,
                    event_id=record["event_id"],
                    event_name=record["event_name"],
                    competitor_number=record["competitor_number"],
                    competitor_name=record["competitor_name"],
                    rank=record["rank"],
                    points=record["points"],
                    is_split=record.get("is_split", False)
                )
                db.add(rec)
        
        await db.commit()

    def calculate_unit_points(
        self,
        results: List[Dict],
        competitors: List[Dict],
        award_configs: Dict[str, Dict[str, float]],
        event_name: str,
        event_id: str
    ) -> List[Dict]:
        """
        计算单位总分

        Args:
            results: 比赛结果 [{competitor_number, rank}]
            competitors: 选手列表 [{number, name, unit, is_couple, partner_unit}]
            award_configs: 奖项得分配置 {event_id: {rank: points}}
            event_name: 场次名称
            event_id: 场次ID

        Returns:
            单位得分记录 [{unit, points, records: []}]
        """
        unit_points = defaultdict(lambda: {"total": 0.0, "records": []})
        config = award_configs.get(event_id, self.DEFAULT_POINTS)

        competitor_map = {c["number"]: c for c in competitors}

        for result in results:
            comp_num = result["competitor_number"]
            rank = result["rank"]
            competitor = competitor_map.get(comp_num)

            if not competitor or not competitor.get("unit"):
                continue

            base_points = config.get(str(rank), 0.0)
            if base_points <= 0:
                continue

            unit = competitor["unit"]
            is_couple = competitor.get("is_couple", False)
            partner_unit = competitor.get("partner_unit")

            if is_couple and partner_unit and partner_unit != unit:
                points = base_points / 2.0
                unit_points[unit]["records"].append({
                    "event_name": event_name,
                    "event_id": event_id,
                    "competitor_number": comp_num,
                    "competitor_name": competitor.get("name", ""),
                    "rank": rank,
                    "points": points,
                    "is_split": True,
                    "partner_unit": partner_unit
                })
                unit_points[unit]["total"] += points

                unit_points[partner_unit]["records"].append({
                    "event_name": event_name,
                    "event_id": event_id,
                    "competitor_number": comp_num,
                    "competitor_name": competitor.get("name", ""),
                    "rank": rank,
                    "points": points,
                    "is_split": True,
                    "partner_unit": unit
                })
                unit_points[partner_unit]["total"] += points
            else:
                unit_points[unit]["records"].append({
                    "event_name": event_name,
                    "event_id": event_id,
                    "competitor_number": comp_num,
                    "competitor_name": competitor.get("name", ""),
                    "rank": rank,
                    "points": base_points,
                    "is_split": False
                })
                unit_points[unit]["total"] += base_points

        return [
            {
                "unit": unit,
                "total_points": data["total"],
                "record_count": len(data["records"]),
                "records": data["records"]
            }
            for unit, data in unit_points.items()
        ]

    def get_ranking(self, unit_points: List[Dict]) -> List[Dict]:
        """获取排名"""
        sorted_points = sorted(unit_points, key=lambda x: x["total_points"], reverse=True)
        for i, up in enumerate(sorted_points):
            up["rank"] = i + 1
        return sorted_points
