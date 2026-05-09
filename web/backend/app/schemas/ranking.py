from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class AwardConfigBase(BaseModel):
    points: Dict[str, float]

class AwardConfigCreate(AwardConfigBase):
    event_id: str

class AwardConfigResponse(AwardConfigBase):
    id: str
    event_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class UnitPointRecordResponse(BaseModel):
    id: str
    event_name: str
    competitor_number: str
    competitor_name: str
    rank: int
    points: float
    is_split: bool

    class Config:
        from_attributes = True

class UnitPointsResponse(BaseModel):
    unit: str
    total_points: float
    record_count: int
    records: List[UnitPointRecordResponse]

class RankingResponse(BaseModel):
    total: int
    items: List[UnitPointsResponse]
