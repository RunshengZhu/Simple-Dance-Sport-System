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
from app.models.unit_points import AwardConfig
from app.schemas.scoring import ScoreRecordCreate, ScoreRecordUpdate
from app.services.scoring_service import ScoringService
from app.services.ranking_service import RankingService

router = APIRouter()
scoring_service = ScoringService()
ranking_service = RankingService()


@router.get("/{event_id}/scores")
async def get_scores(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScoreRecord).where(ScoreRecord.event_id == event_id))
    records = result.scalars().all()
    return [{"id": r.id, "competitor_number": r.competitor_number, "judge_id": r.judge_id,
             "dance_name": r.dance_name, "mark": r.mark, "placement": r.placement} for r in records]


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
    return {"message": "评分已保存", "event_id": event_id}


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
