from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Result(Base):
    __tablename__ = "results"

    id = Column(String(36), primary_key=True)
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"))
    competitor_number = Column(String(50), nullable=False)
    competitor_name = Column(String(100))
    unit = Column(String(200))
    rank = Column(Integer)
    score = Column(Float)
    total_score = Column(Float)
    dance_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="results")
