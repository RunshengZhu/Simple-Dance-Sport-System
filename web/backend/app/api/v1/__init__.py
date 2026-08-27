from fastapi import APIRouter
from app.api.v1 import auth, competitions, competitors, events, scoring, ranking, users, logs, results

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(competitions.router, prefix="/competitions", tags=["赛事管理"])
api_router.include_router(competitors.router, prefix="/competitions", tags=["选手管理"])
api_router.include_router(events.router, prefix="/competitions", tags=["场次管理"])
api_router.include_router(scoring.router, prefix="/events", tags=["评分管理"])
api_router.include_router(ranking.router, prefix="/competitions", tags=["排名管理"])
api_router.include_router(ranking.router, prefix="/events", tags=["排名管理"])
api_router.include_router(logs.router, prefix="/logs", tags=["操作日志"])
api_router.include_router(results.router, prefix="/results", tags=["结果管理"])
