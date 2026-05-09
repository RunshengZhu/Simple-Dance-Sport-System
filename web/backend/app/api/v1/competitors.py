from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from app.core.database import get_db
from app.models.competitor import Competitor
from app.schemas.competitor import CompetitorCreate, CompetitorUpdate, CompetitorResponse

router = APIRouter()

@router.get("/{competition_id}/competitors", response_model=List[CompetitorResponse])
async def list_competitors(competition_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Competitor).where(Competitor.competition_id == competition_id))
    return result.scalars().all()

@router.post("/{competition_id}/competitors", response_model=CompetitorResponse)
async def create_competitor(
    competition_id: str,
    data: CompetitorCreate,
    db: AsyncSession = Depends(get_db)
):
    competitor = Competitor(
        id=str(uuid.uuid4()),
        competition_id=competition_id,
        number=data.number,
        name=data.name,
        unit=data.unit,
        unit_code=data.unit_code,
        group_name=data.group_name,
        partner_number=data.partner_number,
        partner_unit=data.partner_unit,
        is_couple=data.is_couple
    )
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)
    return competitor

@router.put("/{competition_id}/competitors/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    competition_id: str,
    competitor_id: str,
    data: CompetitorUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Competitor).where(
        Competitor.id == competitor_id,
        Competitor.competition_id == competition_id
    ))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="选手不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(competitor, key, value)
    
    await db.commit()
    await db.refresh(competitor)
    return competitor

@router.delete("/{competition_id}/competitors/{competitor_id}")
async def delete_competitor(
    competition_id: str,
    competitor_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Competitor).where(
        Competitor.id == competitor_id,
        Competitor.competition_id == competition_id
    ))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="选手不存在")
    
    await db.delete(competitor)
    await db.commit()
    return {"message": "删除成功"}
