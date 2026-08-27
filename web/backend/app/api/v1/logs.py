from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_admin_user
from app.models.unit_points import User, OperationLog

router = APIRouter()


@router.get("/")
async def list_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(OperationLog)

    if user_id:
        query = query.where(OperationLog.user_id == user_id)

    if action:
        query = query.where(OperationLog.action.contains(action))

    if resource:
        query = query.where(OperationLog.resource.contains(resource))

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(OperationLog.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(OperationLog.created_at <= end_dt)
        except ValueError:
            pass

    if keyword:
        query = query.where(
            OperationLog.username.contains(keyword) |
            OperationLog.action.contains(keyword) |
            OperationLog.resource.contains(keyword)
        )

    query = query.order_by(desc(OperationLog.created_at))
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "method": log.method,
                "path": log.path,
                "ip_address": log.ip_address,
                "response_status": log.response_status,
                "error_message": log.error_message,
                "created_at": log.created_at
            }
            for log in logs
        ],
        "total": len(logs),
        "skip": skip,
        "limit": limit
    }


@router.get("/stats")
async def get_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    start_date = datetime.utcnow() - timedelta(days=days)

    query = select(OperationLog).where(OperationLog.created_at >= start_date)
    result = await db.execute(query)
    logs = result.scalars().all()

    action_stats = {}
    user_stats = {}
    daily_stats = {}

    for log in logs:
        action_stats[log.action] = action_stats.get(log.action, 0) + 1

        if log.username:
            user_stats[log.username] = user_stats.get(log.username, 0) + 1

        date_key = log.created_at.strftime("%Y-%m-%d")
        daily_stats[date_key] = daily_stats.get(date_key, 0) + 1

    top_actions = sorted(action_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    top_users = sorted(user_stats.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_count": len(logs),
        "period_days": days,
        "top_actions": [{"action": a, "count": c} for a, c in top_actions],
        "top_users": [{"username": u, "count": c} for u, c in top_users],
        "daily_stats": [{"date": d, "count": c} for d, c in sorted(daily_stats.items())]
    }


@router.get("/{log_id}")
async def get_log(
    log_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(OperationLog).where(OperationLog.id == log_id))
    log = result.scalar_one_or_none()

    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="日志不存在")

    return {
        "id": log.id,
        "user_id": log.user_id,
        "username": log.username,
        "action": log.action,
        "resource": log.resource,
        "resource_id": log.resource_id,
        "method": log.method,
        "path": log.path,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "request_data": log.request_data,
        "response_status": log.response_status,
        "error_message": log.error_message,
        "created_at": log.created_at
    }
