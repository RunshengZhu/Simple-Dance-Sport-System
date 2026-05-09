from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True)
    competition_id = Column(String(36), ForeignKey("competitions.id", ondelete="CASCADE"))
    name = Column(String(200), nullable=False)
    project_id = Column(String(50))
    round = Column(String(50))
    scoring_type = Column(String(50), nullable=False)
    dances = Column(JSON, default=[])
    advancement_count = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    parent_event_id = Column(String(36), ForeignKey("events.id"))
    child_event_id = Column(String(36), ForeignKey("events.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    competition = relationship("Competition", back_populates="events")
    score_records = relationship("ScoreRecord", back_populates="event", cascade="all, delete-orphan")
    results = relationship("Result", back_populates="event", cascade="all, delete-orphan")
    award_config = relationship("AwardConfig", back_populates="event", uselist=False, cascade="all, delete-orphan")
