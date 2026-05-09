from sqlalchemy import Column, String, Float, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class ScoreRecord(Base):
    __tablename__ = "score_records"

    id = Column(String(36), primary_key=True)
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"))
    judge_id = Column(String(36), ForeignKey("judges.id", ondelete="CASCADE"))
    competitor_number = Column(String(50), nullable=False)
    dance_name = Column(String(100))
    score = Column(Float)
    mark = Column(Boolean)
    placement = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event = relationship("Event", back_populates="score_records")
    judge = relationship("Judge", back_populates="score_records")
