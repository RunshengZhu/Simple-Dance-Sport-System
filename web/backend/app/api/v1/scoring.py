from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict, Optional
import uuid
import json
from app.core.database import get_db
from app.models.score import ScoreRecord
from app.models.event import Event
from app.models.competitor import Competitor
from app.models.result import Result
from app.models.unit_points import AwardConfig, UnitPoints, UnitPointRecord
from app.schemas.scoring import ScoreRecordCreate, ScoreRecordUpdate
from app.services.scoring_service import ScoringService
from app.services.ranking_service import RankingService

router = APIRouter()
scoring_service = ScoringService()
ranking_service = RankingService()

# 默认裁判列表
DEFAULT_JUDGES = ["judge1", "judge2", "judge3", "judge4", "judge5"]


@router.get("/{event_id}/scores")
async def get_scores(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScoreRecord).where(ScoreRecord.event_id == event_id))
    records = result.scalars().all()
    return [{"id": r.id, "competitor_number": r.competitor_number, "judge_id": r.judge_id,
             "dance_name": r.dance_name, "mark": r.mark, "placement": r.placement,
             "score": r.score} for r in records]


@router.post("/{event_id}/scores")
async def submit_scores(
    event_id: str,
    data: List[ScoreRecordCreate],
    db: AsyncSession = Depends(get_db)
):
    for record_data in data:
        if record_data.event_id != event_id:
            record_data.event_id = event_id

        existing = await db.execute(select(ScoreRecord).where(
            ScoreRecord.event_id == event_id,
            ScoreRecord.judge_id == record_data.judge_id,
            ScoreRecord.competitor_number == record_data.competitor_number,
            ScoreRecord.dance_name == record_data.dance_name
        ))
        existing_record = existing.scalar_one_or_none()

        if existing_record:
            existing_record.score = record_data.score
            existing_record.mark = record_data.mark
            existing_record.placement = record_data.placement
        else:
            record = ScoreRecord(
                id=str(uuid.uuid4()),
                event_id=event_id,
                judge_id=record_data.judge_id,
                competitor_number=record_data.competitor_number,
                dance_name=record_data.dance_name,
                score=record_data.score,
                mark=record_data.mark,
                placement=record_data.placement
            )
            db.add(record)

    await db.commit()

    # 自动检查是否所有裁判都已完成评分，如果是则自动计算成绩
    auto_calculate_result = await check_and_auto_calculate(event_id, db)

    response = {
        "message": "评分已保存",
        "event_id": event_id,
        "scores_submitted": len(data)
    }

    if auto_calculate_result:
        response["auto_calculated"] = True
        response["calculation_result"] = auto_calculate_result

    return response


async def check_and_auto_calculate(event_id: str, db: AsyncSession) -> Optional[Dict]:
    """检查是否所有裁判都已完成评分，如果是则自动计算成绩"""
    
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    
    if not event or event.status == "completed":
        return None

    # 获取该场次的参赛选手
    competitor_numbers = event.competitor_numbers or []
    if not competitor_numbers:
        return None

    num_competitors = len(competitor_numbers)
    
    # 获取该场次的舞种列表
    dances = event.dances or []
    num_dances = len(dances) if dances else 1  # 如果没有舞种，默认1个
    
    # 获取已提交评分的裁判列表
    scores_result = await db.execute(select(ScoreRecord).where(ScoreRecord.event_id == event_id))
    scores = scores_result.scalars().all()
    
    if not scores:
        return None

    # 按裁判分组统计评分数量
    judge_score_counts = {}
    for s in scores:
        if s.judge_id not in judge_score_counts:
            judge_score_counts[s.judge_id] = 0
        # 只有有效评分才计数（mark或placement不为空）
        if s.mark or s.placement or s.score:
            judge_score_counts[s.judge_id] += 1
    
    # 计算每个裁判需要提交的评分数量（选手数 * 舞种数）
    expected_scores_per_judge = num_competitors * num_dances
    
    # 检查是否所有默认裁判都已提交完整评分
    all_judges_completed = True
    for judge in DEFAULT_JUDGES:
        if judge_score_counts.get(judge, 0) < expected_scores_per_judge:
            all_judges_completed = False
            break

    if not all_judges_completed:
        return None

    # 所有裁判都已提交完整评分，自动计算成绩
    return await auto_calculate_results(event_id, db)


async def auto_calculate_results(event_id: str, db: AsyncSession) -> Dict:
    """自动计算成绩"""
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        return {"success": False, "message": "场次不存在"}

    competitor_numbers_in_event = event.competitor_numbers or []
    
    if competitor_numbers_in_event:
        comp_query = select(Competitor).where(
            Competitor.competition_id == event.competition_id,
            Competitor.number.in_(competitor_numbers_in_event)
        )
    else:
        comp_query = select(Competitor).where(Competitor.competition_id == event.competition_id)
    
    comp_result = await db.execute(comp_query)
    competitors = [{"id": c.id, "number": c.number, "name": c.name, "unit": c.unit,
                     "is_couple": c.is_couple, "partner_unit": c.partner_unit}
                    for c in comp_result.scalars().all()]

    scores_result = await db.execute(select(ScoreRecord).where(ScoreRecord.event_id == event_id))
    scores = scores_result.scalars().all()

    event_competitor_numbers = [c["number"] for c in competitors]

    if event.scoring_type == "mark":
        scores_by_judge: Dict[str, List[str]] = {}
        for s in scores:
            if s.judge_id not in scores_by_judge:
                scores_by_judge[s.judge_id] = []
            if s.mark and s.competitor_number in event_competitor_numbers:
                scores_by_judge[s.judge_id].append(s.competitor_number)

        results = scoring_service.calculate_mark_results(event_competitor_numbers, scores_by_judge)

        competitor_map = {c["number"]: c for c in competitors}
        for r in results:
            comp = competitor_map.get(r["competitor_number"], {})
            r["competitor_name"] = comp.get("name", "")
            r["unit"] = comp.get("unit", "")

    else:
        scores_by_judge: Dict[str, Dict[str, int]] = {}
        for s in scores:
            if s.judge_id not in scores_by_judge:
                scores_by_judge[s.judge_id] = {}
            if s.placement and s.competitor_number in event_competitor_numbers:
                scores_by_judge[s.judge_id][s.competitor_number] = s.placement

        event_competitors = [c for c in competitors if c["number"] in event_competitor_numbers]
        results, _ = scoring_service.calculate_skating_results(event_competitors, scores_by_judge)

    await db.execute(delete(Result).where(Result.event_id == event_id))

    for r in results:
        result = Result(
            id=str(uuid.uuid4()),
            event_id=event_id,
            competitor_number=r["competitor_number"],
            competitor_name=r.get("competitor_name", ""),
            unit=r.get("unit", ""),
            rank=r["rank"],
            score=r.get("mark_count", 0),
            total_score=r.get("mark_count", 0),
            dance_name=None
        )
        db.add(result)

    event.status = "completed"
    await db.commit()

    # 自动更新单位总分
    await ranking_service.update_unit_points(event.competition_id, event_id, db)

    return {
        "success": True,
        "message": "成绩已自动计算",
        "event_id": event_id,
        "results_count": len(results)
    }


@router.delete("/{event_id}/scores")
async def clear_scores(event_id: str, judge_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    if judge_id:
        await db.execute(delete(ScoreRecord).where(
            ScoreRecord.event_id == event_id,
            ScoreRecord.judge_id == judge_id
        ))
    else:
        await db.execute(delete(ScoreRecord).where(ScoreRecord.event_id == event_id))
    await db.commit()
    return {"message": "评分已清除"}


@router.post("/{event_id}/calculate")
async def calculate_results(event_id: str, db: AsyncSession = Depends(get_db)):
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")

    competitor_numbers_in_event = event.competitor_numbers or []
    
    if competitor_numbers_in_event:
        comp_query = select(Competitor).where(
            Competitor.competition_id == event.competition_id,
            Competitor.number.in_(competitor_numbers_in_event)
        )
    else:
        comp_query = select(Competitor).where(Competitor.competition_id == event.competition_id)
    
    comp_result = await db.execute(comp_query)
    competitors = [{"id": c.id, "number": c.number, "name": c.name, "unit": c.unit,
                     "is_couple": c.is_couple, "partner_unit": c.partner_unit}
                    for c in comp_result.scalars().all()]

    scores_result = await db.execute(select(ScoreRecord).where(ScoreRecord.event_id == event_id))
    scores = scores_result.scalars().all()

    event_competitor_numbers = [c["number"] for c in competitors]

    if event.scoring_type == "mark":
        scores_by_judge: Dict[str, List[str]] = {}
        for s in scores:
            if s.judge_id not in scores_by_judge:
                scores_by_judge[s.judge_id] = []
            if s.mark and s.competitor_number in event_competitor_numbers:
                scores_by_judge[s.judge_id].append(s.competitor_number)

        results = scoring_service.calculate_mark_results(event_competitor_numbers, scores_by_judge)

        competitor_map = {c["number"]: c for c in competitors}
        for r in results:
            comp = competitor_map.get(r["competitor_number"], {})
            r["competitor_name"] = comp.get("name", "")
            r["unit"] = comp.get("unit", "")

    else:
        scores_by_judge: Dict[str, Dict[str, int]] = {}
        for s in scores:
            if s.judge_id not in scores_by_judge:
                scores_by_judge[s.judge_id] = {}
            if s.placement and s.competitor_number in event_competitor_numbers:
                scores_by_judge[s.judge_id][s.competitor_number] = s.placement

        event_competitors = [c for c in competitors if c["number"] in event_competitor_numbers]
        results, _ = scoring_service.calculate_skating_results(event_competitors, scores_by_judge)

    await db.execute(delete(Result).where(Result.event_id == event_id))

    for r in results:
        result = Result(
            id=str(uuid.uuid4()),
            event_id=event_id,
            competitor_number=r["competitor_number"],
            competitor_name=r.get("competitor_name", ""),
            unit=r.get("unit", ""),
            rank=r["rank"],
            score=r.get("mark_count", 0),
            total_score=r.get("mark_count", 0),
            dance_name=None
        )
        db.add(result)

    event.status = "completed"
    await db.commit()

    # 更新单位总分
    await ranking_service.update_unit_points(event.competition_id, event_id, db)

    return {
        "message": "成绩计算完成",
        "event_id": event_id,
        "results": results[:10]
    }


@router.get("/{event_id}/results")
async def get_results(
    event_id: str,
    dance_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Result).where(Result.event_id == event_id)
    if dance_name:
        query = query.where(Result.dance_name == dance_name)
    else:
        query = query.where(Result.dance_name == None)

    query = query.order_by(Result.rank)
    result = await db.execute(query)
    results = result.scalars().all()

    return [{
        "id": r.id,
        "competitor_number": r.competitor_number,
        "competitor_name": r.competitor_name,
        "unit": r.unit,
        "rank": r.rank,
        "score": r.score,
        "total_score": r.total_score
    } for r in results]


@router.get("/{event_id}/score-details")
async def get_score_details(event_id: str, db: AsyncSession = Depends(get_db)):
    """获取评分明细 - 每个裁判对每个选手的评分"""
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")
    
    scores_result = await db.execute(select(ScoreRecord).where(ScoreRecord.event_id == event_id))
    scores = scores_result.scalars().all()
    
    if not scores:
        return {"event_id": event_id, "details": [], "dances": []}
    
    dance_names = list(set([s.dance_name for s in scores if s.dance_name]))
    judges = list(set([s.judge_id for s in scores]))
    competitors = list(set([s.competitor_number for s in scores]))
    
    details = []
    for score in scores:
        details.append({
            "judge_id": score.judge_id,
            "competitor_number": score.competitor_number,
            "dance_name": score.dance_name,
            "mark": score.mark,
            "placement": score.placement,
            "score": score.score
        })
    
    return {
        "event_id": event_id,
        "event_name": event.name,
        "scoring_type": event.scoring_type,
        "dances": dance_names,
        "judges": sorted(judges),
        "competitors": sorted(competitors, key=lambda x: int(x) if x.isdigit() else 0),
        "details": details,
        "completed_judges": len(judges),
        "total_judges": len(DEFAULT_JUDGES),
        "all_judges_completed": len(judges) >= len(DEFAULT_JUDGES)
    }


@router.get("/{event_id}/dance-results")
async def get_dance_results(event_id: str, dance_name: str, db: AsyncSession = Depends(get_db)):
    """获取指定舞种的结果"""
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")
    
    scores_result = await db.execute(select(ScoreRecord).where(
        ScoreRecord.event_id == event_id,
        ScoreRecord.dance_name == dance_name
    ))
    scores = scores_result.scalars().all()
    
    competitor_numbers_in_event = event.competitor_numbers or []
    
    if competitor_numbers_in_event:
        comp_query = select(Competitor).where(
            Competitor.competition_id == event.competition_id,
            Competitor.number.in_(competitor_numbers_in_event)
        )
    else:
        comp_query = select(Competitor).where(Competitor.competition_id == event.competition_id)
    
    comp_result = await db.execute(comp_query)
    competitors = {c.number: {"name": c.name, "unit": c.unit} for c in comp_result.scalars().all()}
    
    results = []
    if event.scoring_type == "mark":
        scores_by_judge = {}
        for s in scores:
            if s.judge_id not in scores_by_judge:
                scores_by_judge[s.judge_id] = []
            if s.mark:
                scores_by_judge[s.judge_id].append(s.competitor_number)
        
        competitor_mark_counts = {}
        for judge_id, marked_numbers in scores_by_judge.items():
            for number in marked_numbers:
                competitor_mark_counts[number] = competitor_mark_counts.get(number, 0) + 1
        
        for number, mark_count in competitor_mark_counts.items():
            comp_info = competitors.get(number, {"name": "", "unit": ""})
            results.append({
                "competitor_number": number,
                "competitor_name": comp_info["name"],
                "unit": comp_info["unit"],
                "mark_count": mark_count,
                "rank": 0
            })
        
        results.sort(key=lambda x: -x["mark_count"])
        for i, r in enumerate(results):
            r["rank"] = i + 1
    
    else:
        scores_by_judge = {}
        for s in scores:
            if s.judge_id not in scores_by_judge:
                scores_by_judge[s.judge_id] = {}
            if s.placement:
                scores_by_judge[s.judge_id][s.competitor_number] = s.placement
        
        competitor_placements = {}
        for judge_id, placements in scores_by_judge.items():
            for number, placement in placements.items():
                if number not in competitor_placements:
                    competitor_placements[number] = []
                competitor_placements[number].append(placement)
        
        competitor_sums = {}
        for number, placements in competitor_placements.items():
            competitor_sums[number] = sum(placements)
        
        for number, sum_placement in competitor_sums.items():
            comp_info = competitors.get(number, {"name": "", "unit": ""})
            results.append({
                "competitor_number": number,
                "competitor_name": comp_info["name"],
                "unit": comp_info["unit"],
                "sum_placement": sum_placement,
                "placements": competitor_placements[number],
                "rank": 0
            })
        
        results.sort(key=lambda x: x["sum_placement"])
        for i, r in enumerate(results):
            r["rank"] = i + 1
    
    return {
        "event_id": event_id,
        "dance_name": dance_name,
        "scoring_type": event.scoring_type,
        "results": results
    }
