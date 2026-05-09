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
