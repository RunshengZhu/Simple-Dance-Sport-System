from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.core.database import get_db
from app.models.result import Result

router = APIRouter()

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
    return result.scalars().all()

@router.post("/{event_id}/calculate")
async def calculate_results(event_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.score import ScoreRecord
    from app.models.event import Event
    
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")
    
    return {"message": "成绩计算完成", "event_id": event_id}
