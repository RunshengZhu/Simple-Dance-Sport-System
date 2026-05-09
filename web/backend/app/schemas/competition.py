from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class CompetitionBase(BaseModel):
    name: str
    date: date
    location: Optional[str] = None
    status: str = "draft"

class CompetitionCreate(CompetitionBase):
    pass

class CompetitionUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    location: Optional[str] = None
    status: Optional[str] = None

class CompetitionResponse(CompetitionBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CompetitionListResponse(BaseModel):
    total: int
    items: List[CompetitionResponse]
