#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""团体总分（M6 / D12 / D13）。纯函数、零第三方依赖。

口径（D12 拍板）：
- 默认 preset = 名次赋分：前 8 名 9-7-6-5-4-3-2-1，第 8 名以后 0 分
- 口径参数化：points 映射可替换；best_n = 每单位每项目只计最好 N 项（None=全部计入）
归属（D13 拍板）：
- 双人跨单位舞伴 → 归主报单位；集体队伍 → 归队伍单位。
  本模块不做归属判断，由调用方在 entries 里给每个结果条目标好 unit。

entries 形态（与 server results_data.overall_results 对齐的最小集）：
    {"project": "S1", "number": "101", "unit": "北京大学", "rank": 2}
"""

DEFAULT_POINTS = {1: 9, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}


def entry_points(rank, points=None):
    """单个名次的分值（并列名次同分值；超出 preset 范围 = 0 分）。"""
    table = DEFAULT_POINTS if points is None else points
    try:
        return float(table.get(int(rank), 0))
    except (TypeError, ValueError):
        return 0.0


def compute_team_standings(entries, points=None, best_n=None):
    """按单位聚合团体总分。

    entries: iterable of {"project", "number", "unit", "rank"}
             unit 为空/缺失的条目计入 unattributed（不参与聚合，不报错）。
    points:  名次→分值映射；None 用 DEFAULT_POINTS。
    best_n:  每单位每项目计入的最高分条目数（None = 全部计入）。
             并列名次的多个条目各按其分值计入，仅以数量截断（按 (rank, number) 稳定排序）。

    返回：
    {
      "standings": [ {"unit", "total", "counted",
                      "per_project": {project: points_sum}} ... ],   # total 降序，同分按单位名
      "unattributed": [entry, ...],
      "preset": {"points": {...}, "best_n": best_n},
    }
    """
    table = dict(DEFAULT_POINTS if points is None else points)
    per_unit_project = {}   # unit -> project -> [ (rank, number, pts) ]
    unattributed = []
    for e in entries:
        unit = (e.get("unit") or "").strip()
        if not unit:
            unattributed.append(e)
            continue
        pts = entry_points(e.get("rank"), table)
        bucket = per_unit_project.setdefault(unit, {})
        bucket.setdefault(str(e.get("project") or ""), []).append(
            (e.get("rank"), str(e.get("number") or ""), pts))

    standings = []
    for unit, bucket in per_unit_project.items():
        total = 0.0
        counted = 0
        per_project = {}
        for project, lst in bucket.items():
            lst.sort(key=lambda t: (entry_points(t[0], table), t[0], t[2]), reverse=True)
            # 以分值降序为主序（并列名次同分值全保留，截断只看条数）
            lst.sort(key=lambda t: (t[2], -(t[0] or 0)), reverse=True)
            if best_n is not None:
                lst = lst[: max(0, int(best_n))]
            s = sum(t[2] for t in lst)
            per_project[project] = round(s, 2)
            total += s
            counted += len(lst)
        standings.append({"unit": unit, "total": round(total, 2),
                          "counted": counted, "per_project": per_project})
    standings.sort(key=lambda x: (-x["total"], x["unit"]))
    return {
        "standings": standings,
        "unattributed": unattributed,
        "preset": {"points": table, "best_n": best_n},
    }
