from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(String(36), primary_key=True)
    competition_id = Column(String(36), ForeignKey("competitions.id", ondelete="CASCADE"))
    number = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    unit = Column(String(200))
    unit_code = Column(String(50))
    group_name = Column(String(100))
    partner_number = Column(String(50))
    partner_unit = Column(String(200))
    is_couple = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    competition = relationship("Competition", back_populates="competitors")
