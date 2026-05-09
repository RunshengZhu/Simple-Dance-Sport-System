from sqlalchemy import Column, String, Date, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Competition(Base):
    __tablename__ = "competitions"

    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    date = Column(Date, nullable=False)
    location = Column(String(200))
    status = Column(String(50), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("Event", back_populates="competition", cascade="all, delete-orphan")
    competitors = relationship("Competitor", back_populates="competition", cascade="all, delete-orphan")
    judges = relationship("Judge", back_populates="competition", cascade="all, delete-orphan")
    unit_points = relationship("UnitPoints", back_populates="competition", cascade="all, delete-orphan")
