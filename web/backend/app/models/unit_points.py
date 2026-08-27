from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, DateTime, Text
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
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="viewer", index=True)
    full_name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    avatar = Column(String(500))

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

class Role(Base):
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100))
    description = Column(String(500))
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")

    def __repr__(self):
        return f"<Role {self.name}>"

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(String(36), primary_key=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100))
    resource = Column(String(50))
    action = Column(String(50))
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")

    def __repr__(self):
        return f"<Permission {self.code}>"

class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(String(36), primary_key=True)
    role_id = Column(String(36), ForeignKey("roles.id", ondelete="CASCADE"))
    permission_id = Column(String(36), ForeignKey("permissions.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    token = Column(String(500), unique=True, nullable=False, index=True)
    device_info = Column(String(500))
    ip_address = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

    def __repr__(self):
        return f"<UserSession {self.id}>"

class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    username = Column(String(100))
    action = Column(String(100), index=True)
    resource = Column(String(100))
    resource_id = Column(String(100))
    method = Column(String(10))
    path = Column(String(500))
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    request_data = Column(Text)
    response_status = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")

    def __repr__(self):
        return f"<OperationLog {self.action} by {self.username}>"
