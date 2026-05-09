from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ScoreRecordBase(BaseModel):
    competitor_number: str
    dance_name: Optional[str] = None
    score: Optional[float] = None
    mark: Optional[bool] = None
    placement: Optional[int] = None

class ScoreRecordCreate(ScoreRecordBase):
    event_id: str
    judge_id: str

class ScoreRecordUpdate(ScoreRecordBase):
    pass

class ScoreRecordResponse(ScoreRecordBase):
    id: str
    event_id: str
    judge_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ScoringSubmit(BaseModel):
    judge_id: str
    records: List[ScoreRecordCreate]
