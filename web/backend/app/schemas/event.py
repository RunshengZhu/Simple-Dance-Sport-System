from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class EventBase(BaseModel):
    name: str
    project_id: Optional[str] = None
    round: Optional[str] = None
    scoring_type: str
    dances: List[str] = []
    advancement_count: int = 0
    competitor_numbers: List[str] = []
    status: str = "pending"


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    name: Optional[str] = None
    round: Optional[str] = None
    scoring_type: Optional[str] = None
    dances: Optional[List[str]] = None
    advancement_count: Optional[int] = None
    competitor_numbers: Optional[List[str]] = None
    status: Optional[str] = None


class EventResponse(EventBase):
    id: str
    competition_id: str
    parent_event_id: Optional[str] = None
    child_event_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
