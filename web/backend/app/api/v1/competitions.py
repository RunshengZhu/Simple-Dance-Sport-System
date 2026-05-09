from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import uuid
from datetime import date
from app.core.database import get_db
from app.models.competition import Competition
from app.schemas.competition import CompetitionCreate, CompetitionUpdate, CompetitionResponse, CompetitionListResponse

router = APIRouter()

@router.get("", response_model=CompetitionListResponse)
async def list_competitions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Competition).offset(skip).limit(limit))
    items = result.scalars().all()
    
    count_result = await db.execute(select(func.count(Competition.id)))
    total = count_result.scalar()
    
    return CompetitionListResponse(total=total, items=items)

@router.post("", response_model=CompetitionResponse)
async def create_competition(
    data: CompetitionCreate,
    db: AsyncSession = Depends(get_db)
):
    competition = Competition(
        id=str(uuid.uuid4()),
        name=data.name,
        date=data.date,
        location=data.location,
        status=data.status
    )
    db.add(competition)
    await db.commit()
    await db.refresh(competition)
    return competition

@router.get("/{competition_id}", response_model=CompetitionResponse)
async def get_competition(competition_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="赛事不存在")
    return competition

@router.put("/{competition_id}", response_model=CompetitionResponse)
async def update_competition(
    competition_id: str,
    data: CompetitionUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="赛事不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(competition, key, value)
    
    await db.commit()
    await db.refresh(competition)
    return competition

@router.delete("/{competition_id}")
async def delete_competition(competition_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="赛事不存在")
    
    await db.delete(competition)
    await db.commit()
    return {"message": "删除成功"}
