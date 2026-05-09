from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class AwardConfig(Base):
    __tablename__ = "award_configs"

    id = Column(String(36), primary_key=True)
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), unique=True)
    points = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event = relationship("Event", back_populates="award_config")

class UnitPoints(Base):
    __tablename__ = "unit_points"

    id = Column(String(36), primary_key=True)
    competition_id = Column(String(36), ForeignKey("competitions.id", ondelete="CASCADE"))
    unit = Column(String(200), nullable=False)
    total_points = Column(Float, default=0)
    record_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    competition = relationship("Competition", back_populates="unit_points")
    records = relationship("UnitPointRecord", back_populates="unit_points", cascade="all, delete-orphan")

class UnitPointRecord(Base):
    __tablename__ = "unit_point_records"

    id = Column(String(36), primary_key=True)
    unit_points_id = Column(String(36), ForeignKey("unit_points.id", ondelete="CASCADE"))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"))
    event_name = Column(String(200))
    competitor_number = Column(String(50))
    competitor_name = Column(String(100))
    rank = Column(Integer)
    points = Column(Float)
    is_split = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    unit_points = relationship("UnitPoints", back_populates="records")

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)
