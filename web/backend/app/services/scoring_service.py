"""
评分算法服务
实现Mark制和顺位法评分算法
"""
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict


class ScoringService:
    """评分算法服务"""

    def __init__(self):
        self.advancement_rule = "all_tied_advance"

    def calculate_mark_results(self, competitors: List[str], scores: Dict[str, List[str]]) -> List[Dict]:
        """
        Mark制评分计算 - 统计每个选手被选中的次数

        Args:
            competitors: 选手番号列表
            scores: 评分数据 {judge_id: [选中的选手番号列表]}

        Returns:
            [{competitor_number, mark_count, rank}]
        """
        mark_counts = defaultdict(int)

        for judge_id, selected in scores.items():
            for comp in selected:
                mark_counts[comp] += 1

        results = []
        for comp in competitors:
            results.append({
                "competitor_number": comp,
                "mark_count": mark_counts.get(comp, 0),
                "selected": mark_counts.get(comp, 0) > 0
            })

        results.sort(key=lambda x: x["mark_count"], reverse=True)

        current_rank = 1
        same_count = 0
        prev_count = None

        for i, r in enumerate(results):
            if prev_count is not None and r["mark_count"] == prev_count:
                same_count += 1
            else:
                current_rank = i + 1
                same_count = 0
            r["rank"] = current_rank
            prev_count = r["mark_count"]

        return results

    def calculate_skating_results(
        self,
        competitors: List[Dict],
        scores: Dict[str, Dict[str, int]]
    ) -> Tuple[List[Dict], Dict[str, Dict]]:
        """
        顺位法（滑冰系统）评分计算

        Args:
            competitors: [{number, name, ...}]
            scores: {judge_id: {competitor_number: rank}}

        Returns:
            (排名结果, 决胜区间详情)
        """
        if not scores or not competitors:
            return [], {}

        player_list = [c["number"] for c in competitors]
        
        valid_scores = {}
        for judge_id, judge_scores in scores.items():
            valid_scores[judge_id] = judge_scores

        if not valid_scores:
            return [{"competitor_number": p, "rank": 1} for p in player_list], {}

        num_judges = len(valid_scores)
        majority_threshold = num_judges // 2 + 1
        num_players = len(player_list)

        rankings = {}
        decision_ranges = {}
        
        for player in player_list:
            total_points = 0
            rank_counts = {}
            for judge_id, judge_scores in valid_scores.items():
                if player in judge_scores:
                    rank = judge_scores[player]
                    rank_counts[rank] = rank_counts.get(rank, 0) + 1
                    total_points += rank
            
            if rank_counts:
                avg_rank = total_points / len([j for j in valid_scores.values() if player in j])
                rankings[player] = {
                    "avg_rank": avg_rank,
                    "first_place_votes": rank_counts.get(1, 0),
                    "total_rank": total_points
                }
            else:
                rankings[player] = {
                    "avg_rank": num_players,
                    "first_place_votes": 0,
                    "total_rank": num_players * num_players
                }

        sorted_players = sorted(player_list, key=lambda p: (
            -rankings[p]["first_place_votes"],
            rankings[p]["avg_rank"],
            rankings[p]["total_rank"]
        ))

        final_results = []
        current_rank = 1
        prev_avg = None
        prev_first = None

        for i, player in enumerate(sorted_players):
            r = rankings[player]
            if prev_avg is not None and abs(r["avg_rank"] - prev_avg) < 0.01 and r["first_place_votes"] == prev_first:
                pass
            else:
                current_rank = i + 1
            
            final_results.append({
                "competitor_number": player,
                "rank": current_rank,
                "avg_rank": r["avg_rank"],
                "first_place_votes": r["first_place_votes"]
            })
            prev_avg = r["avg_rank"]
            prev_first = r["first_place_votes"]

        results = []
        for comp in competitors:
            comp_result = next((r for r in final_results if r["competitor_number"] == comp["number"]), None)
            results.append({
                "competitor_number": comp["number"],
                "competitor_name": comp.get("name", ""),
                "rank": comp_result["rank"] if comp_result else 1
            })

        results.sort(key=lambda x: x["rank"])
        return results, {}

    def calculate_advancement(
        self,
        results: List[Dict],
        advancement_count: int
    ) -> List[Dict]:
        """计算晋级结果"""
        if not results or advancement_count <= 0:
            return results

        advancing = []
        tied_group = []
        current_rank = 0

        for r in results:
            if r["rank"] == current_rank:
                tied_group.append(r)
            else:
                if len(advancing) + len(tied_group) <= advancement_count:
                    advancing.extend(tied_group)
                elif self.advancement_rule == "all_tied_advance":
                    advancing.extend(tied_group)
                tied_group = [r]
                current_rank = r["rank"]

        if len(advancing) + len(tied_group) <= advancement_count:
            advancing.extend(tied_group)
        elif self.advancement_rule == "all_tied_advance":
            advancing.extend(tied_group)

        for r in results:
            r["advancing"] = r in advancing

        return results
