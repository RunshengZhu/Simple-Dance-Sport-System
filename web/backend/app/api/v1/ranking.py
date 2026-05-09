from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict
import json
from app.core.database import get_db
from app.models.unit_points import AwardConfig, UnitPoints, UnitPointRecord
from app.schemas.ranking import AwardConfigCreate, AwardConfigResponse, RankingResponse, UnitPointsResponse, UnitPointRecordResponse

router = APIRouter()

DEFAULT_POINTS = {"1": 9.0, "2": 7.0, "3": 6.0, "4": 5.0, "5": 4.0, "6": 3.0, "7": 2.0, "8": 1.0}

@router.get("/competitions/{competition_id}/ranking")
async def get_ranking(competition_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UnitPoints).where(UnitPoints.competition_id == competition_id))
    unit_points_list = result.scalars().all()
    
    items = []
    for up in unit_points_list:
        records_result = await db.execute(select(UnitPointRecord).where(UnitPointRecord.unit_points_id == up.id))
        records = records_result.scalars().all()
        
        items.append(UnitPointsResponse(
            unit=up.unit,
            total_points=up.total_points,
            record_count=up.record_count,
            records=[UnitPointRecordResponse(
                id=r.id,
                event_name=r.event_name,
                competitor_number=r.competitor_number,
                competitor_name=r.competitor_name,
                rank=r.rank,
                points=r.points,
                is_split=r.is_split
            ) for r in records]
        ))
    
    items.sort(key=lambda x: x.total_points, reverse=True)
    return RankingResponse(total=len(items), items=items)

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
    import uuid
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
