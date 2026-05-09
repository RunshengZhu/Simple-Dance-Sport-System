from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from app.core.database import get_db
from app.models.score import ScoreRecord
from app.models.event import Event
from app.schemas.scoring import ScoreRecordCreate, ScoreRecordUpdate, ScoreRecordResponse

router = APIRouter()

@router.get("/{event_id}/scores")
async def get_scores(event_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScoreRecord).where(ScoreRecord.event_id == event_id))
    return result.scalars().all()

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
    return {"message": "评分已保存"}
