from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CompetitorBase(BaseModel):
    number: str
    name: str
    unit: Optional[str] = None
    unit_code: Optional[str] = None
    group_name: Optional[str] = None
    partner_number: Optional[str] = None
    partner_unit: Optional[str] = None
    is_couple: bool = False


class CompetitorCreate(CompetitorBase):
    pass


class CompetitorUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    unit_code: Optional[str] = None
    group_name: Optional[str] = None
    partner_number: Optional[str] = None
    partner_unit: Optional[str] = None
    is_couple: Optional[bool] = None


class CompetitorResponse(CompetitorBase):
    id: str
    competition_id: str
    created_at: datetime

    class Config:
        from_attributes = True
