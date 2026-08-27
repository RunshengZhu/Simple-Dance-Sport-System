from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def import_all_models():
    from app.models.competition import Competition
    from app.models.event import Event
    from app.models.competitor import Competitor
    from app.models.judge import Judge
    from app.models.score import ScoreRecord
    from app.models.result import Result
    from app.models.unit_points import (
        AwardConfig, UnitPoints, UnitPointRecord, User,
        Role, Permission, RolePermission, UserSession, OperationLog
    )
    return [
        Competition, Event, Competitor, Judge,
        ScoreRecord, Result, AwardConfig, UnitPoints,
        UnitPointRecord, User, Role, Permission,
        RolePermission, UserSession, OperationLog
    ]
