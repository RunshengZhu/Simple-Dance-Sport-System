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
        valid_scores = self._validate_skating_scores(player_list, scores)

        if not valid_scores:
            return [{"competitor_number": p, "rank": 1} for p in player_list], {}

        num_judges = len(valid_scores)
        majority_threshold = num_judges // 2 + 1
        num_players = len(player_list)

        rankings = {}
        decision_ranges = {}
        remaining = player_list.copy()
        current_rank = 1

        while remaining:
            winner = self._determine_winner(
                remaining, valid_scores, majority_threshold, num_players
            )

            if winner:
                rankings[winner] = current_rank
                decision_ranges[winner] = self._find_decision_range(
                    winner, valid_scores, majority_threshold, num_players
                )
                remaining.remove(winner)
                current_rank += 1
            else:
                for p in remaining:
                    rankings[p] = current_rank
                break

        results = []
        for comp in competitors:
            results.append({
                "competitor_number": comp["number"],
                "competitor_name": comp.get("name", ""),
                "rank": rankings.get(comp["number"], current_rank),
                "decision_range": decision_ranges.get(comp["number"], {})
            })

        results.sort(key=lambda x: x["rank"])
        return results, decision_ranges

    def _validate_skating_scores(
        self,
        players: List[str],
        scores: Dict[str, Dict[str, int]]
    ) -> Dict[str, Dict[str, int]]:
        """验证滑冰系统评分"""
        valid_scores = {}
        n = len(players)

        for judge_id, judge_scores in scores.items():
            if len(judge_scores) != n:
                continue
            if any(p not in judge_scores for p in players):
                continue

            ranks = list(judge_scores.values())
            if min(ranks) < 1 or max(ranks) > n:
                continue
            if len(set(ranks)) != n:
                continue

            valid_scores[judge_id] = judge_scores

        return valid_scores

    def _calculate_majority_counts(
        self,
        players: List[str],
        scores: Dict[str, Dict[str, int]],
        position: int
    ) -> Dict[str, int]:
        """计算获得指定名次及以下票数的选手"""
        counts = {p: 0 for p in players}
        for judge in scores:
            for player in players:
                if scores[judge].get(player, 999) <= position:
                    counts[player] += 1
        return counts

    def _determine_winner(
        self,
        remaining: List[str],
        scores: Dict[str, Dict[str, int]],
        threshold: int,
        total_players: int
    ) -> Optional[str]:
        """确定当前名次的获胜者"""
        position = 1

        while position <= total_players:
            majority = self._calculate_majority_counts(remaining, scores, position)
            candidates = [p for p in remaining if majority[p] >= threshold]

            if len(candidates) == 1:
                return candidates[0]
            elif len(candidates) > 1:
                best = min(candidates, key=lambda p: scores[list(scores.keys())[0]][p])
                return best

            position += 1

        return remaining[0] if remaining else None

    def _find_decision_range(
        self,
        player: str,
        scores: Dict[str, Dict[str, int]],
        threshold: int,
        total_players: int
    ) -> Dict[str, Any]:
        """找出决胜区间"""
        rank = scores[list(scores.keys())[0]][player]
        start = max(1, rank - 2)
        end = min(total_players, rank + 2)

        for pos in range(1, total_players + 1):
            majority = self._calculate_majority_counts([player], scores, pos)
            if majority[player] >= threshold:
                end = pos
                break

        return {"start": start, "end": end, "rank": rank}

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
