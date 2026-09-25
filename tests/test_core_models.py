#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_core_models — core 数据模型 vs src 数据模型 序列化等价 + 自身 round-trip。
"""
from datetime import datetime

from core import (Competition, CompetitionResult, Competitor, Dance, Event,
                  EventStatus, Judge, Result, ScoringType, ScoreRecord,
                  SkatingOverallDetail, SkatingScoreDetail)
from src.models import data_models as src_dm
from src.models import skating_score_details as src_sd


def test_scoring_type_values():
    assert ScoringType.MARK.value == src_dm.ScoringType.MARK.value == "Mark制"
    assert ScoringType.SKATING.value == src_dm.ScoringType.SKATING.value == "顺位法"


def test_event_status_values():
    for member in ("NOT_STARTED", "IN_PROGRESS", "COMPLETED"):
        assert getattr(EventStatus, member).value == getattr(src_dm.EventStatus, member).value


def test_competitor_roundtrip():
    data = {"number": "7", "name": "张三", "unit": "A校", "group": "标准舞"}
    assert Competitor.from_dict(data).to_dict() == data
    core_c = Competitor.from_dict(data)
    src_c = src_dm.Competitor.from_dict(data)
    assert core_c.to_dict() == src_c.to_dict()


def test_judge_and_dance_roundtrip():
    assert Judge.from_dict({"id": "J1"}).to_dict() == {"id": "J1", "name": ""}
    assert Judge.from_dict({"id": "J1", "name": "李裁判"}).to_dict() == {"id": "J1", "name": "李裁判"}
    d = Dance.from_dict({"name": "华尔兹", "order": 1})
    assert d.to_dict() == {"name": "华尔兹", "order": 1}


def _full_event_dict():
    return {
        "id": "E1", "name": "预选赛", "project_id": "P1", "round": "1",
        "scoring_type": "顺位法",
        "dances": [{"name": "华尔兹", "order": 1}, {"name": "探戈", "order": 2}],
        "competitors": ["1", "2", "3"],
        "status": "进行中",
        "advancement_count": 2, "advancement_rule": "strict_count",
        "parent_event_id": None, "child_event_id": "E2",
    }


def test_event_roundtrip_matches_src():
    data = _full_event_dict()
    core_e = Event.from_dict(data)
    src_e = src_dm.Event.from_dict(data)
    assert core_e.to_dict() == src_e.to_dict() == data
    # 缺省字段
    minimal = Event.from_dict({"id": "X", "name": "n", "project_id": "p", "round": "1",
                               "scoring_type": "Mark制"})
    src_minimal = src_dm.Event.from_dict({"id": "X", "name": "n", "project_id": "p",
                                          "round": "1", "scoring_type": "Mark制"})
    assert minimal.to_dict() == src_minimal.to_dict()


def test_score_record_roundtrip_matches_src():
    ts = datetime(2026, 8, 27, 12, 0, 0)
    record = ScoreRecord(id="R1", event_id="E1", judge_id="J1", competitor_number="3",
                         dance_name="华尔兹", score=None, mark=True, placement=None,
                         timestamp=ts)
    data = record.to_dict()
    assert data["timestamp"] == "2026-08-27T12:00:00"
    assert ScoreRecord.from_dict(data).to_dict() == data
    src_record = src_dm.ScoreRecord(id="R1", event_id="E1", judge_id="J1",
                                    competitor_number="3", dance_name="华尔兹",
                                    score=None, mark=True, placement=None, timestamp=ts)
    assert record.to_dict() == src_record.to_dict()


def test_result_roundtrip_matches_src():
    r = Result(event_id="E1", competitor_number="2", rank=1, dance_name="综合",
               score=6.0, total_score=6, details={"a": 1},
               advancement_status=True, tied_with=["3"])
    assert r.to_dict() == src_dm.Result(
        event_id="E1", competitor_number="2", rank=1, dance_name="综合",
        score=6.0, total_score=6, details={"a": 1},
        advancement_status=True, tied_with=["3"]).to_dict()
    assert Result.from_dict(r.to_dict()).to_dict() == r.to_dict()


def test_competition_result_serializable():
    ts = datetime(2026, 8, 27, 12, 0, 0)
    inner = {"overall_results": [Result(event_id="E1", competitor_number="1", rank=1)]}
    core_cr = CompetitionResult(event_id="E1", calculation_time=ts, results_data=inner)
    src_cr = src_dm.CompetitionResult(
        event_id="E1", calculation_time=ts,
        results_data={"overall_results": [src_dm.Result(event_id="E1", competitor_number="1", rank=1)]})

    def normalize(obj):
        """递归转换（注意：src 对顶层 list 值不做转换——该行为已在 core 忠实保留）"""
        if hasattr(obj, "to_dict"):
            return normalize(obj.to_dict())
        if isinstance(obj, dict):
            return {k: normalize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [normalize(v) for v in obj]
        return obj

    assert normalize(core_cr.to_dict()) == normalize(src_cr.to_dict())
    assert CompetitionResult.from_dict(normalize(core_cr.to_dict())).event_id == "E1"


def test_competition_roundtrip():
    ts = datetime(2026, 8, 27, 12, 0, 0)
    comp = Competition(name="测试赛", date="2026-08-27", location="体育馆",
                       competitors={"1": Competitor.from_dict(
                           {"number": "1", "name": "张三", "unit": "A", "group": "G"})},
                       judges={"J1": Judge(id="J1")},
                       events={"E1": Event.from_dict(_full_event_dict())},
                       created_at=ts, updated_at=ts)
    data = comp.to_dict()
    assert Competition.from_dict(data).to_dict() == data

    src_comp = src_dm.Competition.from_dict(data)
    assert comp.to_dict() == src_comp.to_dict()


def test_competition_lookup_helpers():
    comp = Competition(name="n", date="d", location="l",
                       competitors={"1": Competitor.from_dict(
                           {"number": "1", "name": "x", "unit": "u", "group": "g"})},
                       events={"E1": Event.from_dict(_full_event_dict())})
    assert comp.get_competitor("1").name == "x"
    assert comp.get_competitor("99") is None
    assert comp.get_event("E1").name == "预选赛"
    assert comp.get_event("missing") is None


def test_skating_details_roundtrip():
    ts = datetime(2026, 8, 27, 12, 0, 0)
    detail = SkatingScoreDetail(
        event_id="E1", dance_name="华尔兹", competitor_number="1",
        judge_placements={"J1": 1, "J2": 2}, placement_counts={1: 1, 2: 1},
        cumulative_votes={1: 1, 2: 2}, sum_placement=3, final_rank=1,
        majority_rank=2, details={"decision_range": 2}, calculation_time=ts)
    assert SkatingScoreDetail.from_dict(detail.to_dict()).to_dict() == detail.to_dict()

    src_detail = src_sd.SkatingScoreDetail(
        event_id="E1", dance_name="华尔兹", competitor_number="1",
        judge_placements={"J1": 1, "J2": 2}, placement_counts={1: 1, 2: 1},
        cumulative_votes={1: 1, 2: 2}, sum_placement=3, final_rank=1,
        majority_rank=2, details={"decision_range": 2}, calculation_time=ts)
    assert detail.to_dict() == src_detail.to_dict()

    overall = SkatingOverallDetail(event_id="E1", competitor_number="1",
                                   dance_details={"华尔兹": detail},
                                   total_sum_placement=3, final_rank=1,
                                   overall_majority_rank=2, calculation_time=ts)
    assert SkatingOverallDetail.from_dict(overall.to_dict()).to_dict() == overall.to_dict()
