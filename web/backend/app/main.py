from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base, import_all_models
from app.api.v1.auth import router as auth_router
from app.api.v1.competitions import router as competitions_router
from app.api.v1.events import router as events_router
from app.api.v1.competitors import router as competitors_router
from app.api.v1.scoring import router as scoring_router
from app.api.v1.results import router as results_router
from app.api.v1.ranking import router as ranking_router

app = FastAPI(
    title="体育舞蹈赛事评分系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(competitions_router, prefix="/api/v1/competitions", tags=["赛事"])
app.include_router(events_router, prefix="/api/v1", tags=["场次"])
app.include_router(competitors_router, prefix="/api/v1/competitions", tags=["选手"])
app.include_router(scoring_router, prefix="/api/v1/events", tags=["评分"])
app.include_router(results_router, prefix="/api/v1/events", tags=["成绩"])
app.include_router(ranking_router, prefix="/api/v1", tags=["排名"])

@app.on_event("startup")
async def startup():
    import_all_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {"message": "体育舞蹈赛事评分系统 API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
