from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict
import json
import uuid
from app.core.database import get_db
from app.models.unit_points import AwardConfig, UnitPoints, UnitPointRecord
from app.models.event import Event
from app.models.result import Result
from app.models.competitor import Competitor
from app.schemas.ranking import AwardConfigCreate
from app.services.ranking_service import RankingService

router = APIRouter()
ranking_service = RankingService()

DEFAULT_POINTS = {"1": 9.0, "2": 7.0, "3": 6.0, "4": 5.0,
                  "5": 4.0, "6": 3.0, "7": 2.0, "8": 1.0}


@router.get("/competitions/{competition_id}/ranking")
async def get_ranking(competition_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UnitPoints).where(UnitPoints.competition_id == competition_id))
    unit_points_list = result.scalars().all()

    items = []
    for up in unit_points_list:
        records_result = await db.execute(
            select(UnitPointRecord).where(UnitPointRecord.unit_points_id == up.id)
        )
        records = records_result.scalars().all()

        items.append({
            "unit": up.unit,
            "total_points": up.total_points,
            "record_count": up.record_count,
            "records": [{
                "id": r.id,
                "event_name": r.event_name,
                "competitor_number": r.competitor_number,
                "competitor_name": r.competitor_name,
                "rank": r.rank,
                "points": r.points,
                "is_split": r.is_split
            } for r in records]
        })

    items.sort(key=lambda x: x["total_points"], reverse=True)

    for i, item in enumerate(items):
        item["rank"] = i + 1

    return {"total": len(items), "items": items}


@router.post("/competitions/{competition_id}/calculate-ranking")
async def calculate_competition_ranking(competition_id: str, db: AsyncSession = Depends(get_db)):
    events_result = await db.execute(select(Event).where(Event.competition_id == competition_id))
    events = events_result.scalars().all()

    competitors_result = await db.execute(select(Competitor).where(Competitor.competition_id == competition_id))
    competitors = [{
        "number": c.number,
        "name": c.name,
        "unit": c.unit,
        "is_couple": c.is_couple,
        "partner_unit": c.partner_unit
    } for c in competitors_result.scalars().all()]

    all_unit_points = []
    award_configs = {}

    for event in events:
        config_result = await db.execute(select(AwardConfig).where(AwardConfig.event_id == event.id))
        config = config_result.scalar_one_or_none()
        if config:
            award_configs[event.id] = json.loads(config.points)
        else:
            award_configs[event.id] = DEFAULT_POINTS

        if event.status != "completed":
            continue

        results_result = await db.execute(select(Result).where(Result.event_id == event.id))
        results = results_result.scalars().all()
        results_list = [{"competitor_number": r.competitor_number, "rank": r.rank} for r in results]

        unit_points = ranking_service.calculate_unit_points(
            results_list, competitors, award_configs, event.name, event.id
        )
        all_unit_points.extend(unit_points)

    aggregated = {}
    for up in all_unit_points:
        unit = up["unit"]
        if unit not in aggregated:
            aggregated[unit] = {"total_points": 0.0, "record_count": 0, "records": [], "units": []}
        aggregated[unit]["total_points"] += up["total_points"]
        aggregated[unit]["record_count"] += up["record_count"]
        aggregated[unit]["records"].extend(up["records"])
        aggregated[unit]["units"] = list(set(aggregated[unit]["units"] + [r.get("partner_unit", "") for r in up["records"] if r.get("partner_unit")] + [unit]))

    await db.execute(delete(UnitPoints).where(UnitPoints.competition_id == competition_id))

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

    return {"message": "单位总分计算完成", "units": len(aggregated)}


@router.get("/events/{event_id}/award-config")
async def get_award_config(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AwardConfig).where(AwardConfig.event_id == event_id))
    config = result.scalar_one_or_none()

    if not config:
        return {"event_id": event_id, "points": DEFAULT_POINTS}

    return {"event_id": event_id, "points": json.loads(config.points)}


@router.put("/events/{event_id}/award-config")
async def update_award_config(
    event_id: str,
    data: AwardConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(AwardConfig).where(AwardConfig.event_id == event_id))
    config = result.scalar_one_or_none()

    points_json = json.dumps(data.points)

    if config:
        config.points = points_json
    else:
        config = AwardConfig(
            id=str(uuid.uuid4()),
            event_id=event_id,
            points=points_json
        )
        db.add(config)

    await db.commit()
    return {"message": "配置已保存", "event_id": event_id, "points": data.points}


@router.get("/competitions/{competition_id}/ranking/{unit}")
async def get_unit_details(competition_id: str, unit: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UnitPoints).where(
            UnitPoints.competition_id == competition_id,
            UnitPoints.unit == unit
        )
    )
    up = result.scalar_one_or_none()
    if not up:
        raise HTTPException(status_code=404, detail="单位不存在")

    records_result = await db.execute(
        select(UnitPointRecord).where(UnitPointRecord.unit_points_id == up.id)
    )
    records = records_result.scalars().all()

    return {
        "unit": up.unit,
        "total_points": up.total_points,
        "record_count": up.record_count,
        "records": [{
            "id": r.id,
            "event_name": r.event_name,
            "event_id": r.event_id,
            "competitor_number": r.competitor_number,
            "competitor_name": r.competitor_name,
            "rank": r.rank,
            "points": r.points,
            "is_split": r.is_split
        } for r in records]
    }
