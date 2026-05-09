from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from app.core.database import get_db
from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate, EventResponse

router = APIRouter()

@router.get("/competitions/{competition_id}/events", response_model=List[EventResponse])
async def list_events(competition_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.competition_id == competition_id))
    return result.scalars().all()

@router.post("/competitions/{competition_id}/events", response_model=EventResponse)
async def create_event(
    competition_id: str,
    data: EventCreate,
    db: AsyncSession = Depends(get_db)
):
    event = Event(
        id=str(uuid.uuid4()),
        competition_id=competition_id,
        name=data.name,
        project_id=data.project_id,
        round=data.round,
        scoring_type=data.scoring_type,
        dances=data.dances,
        advancement_count=data.advancement_count,
        status=data.status
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event

@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")
    return event

@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)
    
    await db.commit()
    await db.refresh(event)
    return event

@router.delete("/events/{event_id}")
async def delete_event(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")
    
    await db.delete(event)
    await db.commit()
    return {"message": "删除成功"}

@router.post("/events/{event_id}/start")
async def start_event(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")
    
    event.status = "scoring"
    await db.commit()
    return {"message": "场次已开始", "status": "scoring"}

@router.post("/events/{event_id}/complete")
async def complete_event(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="场次不存在")
    
    event.status = "completed"
    await db.commit()
    return {"message": "场次已完成", "status": "completed"}
