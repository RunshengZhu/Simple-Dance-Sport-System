from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Judge(Base):
    __tablename__ = "judges"

    id = Column(String(36), primary_key=True)
    competition_id = Column(String(36), ForeignKey("competitions.id", ondelete="CASCADE"))
    name = Column(String(100))
    position = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    competition = relationship("Competition", back_populates="judges")
    score_records = relationship("ScoreRecord", back_populates="judge", cascade="all, delete-orphan")
