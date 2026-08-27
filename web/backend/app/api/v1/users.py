from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional
from datetime import datetime
import uuid
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.core.dependencies import get_current_user, get_admin_user
from app.models.unit_points import User, OperationLog

router = APIRouter()


@router.get("/")
async def list_users(
    request: Request,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(User)

    if role:
        query = query.where(User.role == role)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    if keyword:
        query = query.where(
            or_(
                User.username.contains(keyword),
                User.full_name.contains(keyword),
                User.email.contains(keyword)
            )
        )

    query = query.order_by(User.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    users = result.scalars().all()

    total_result = await db.execute(
        select(User).where(User.role != "admin") if role == "admin" else select(User)
    )
    total = len(total_result.scalars().all())

    await log_operation(
        db, current_user.id, "LIST_USERS", "用户列表", None,
        "GET", "/api/v1/users/", request.client.host if request.client else None,
        f"role={role}, is_active={is_active}, keyword={keyword}", 200, None
    )

    return {
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "full_name": u.full_name,
                "email": u.email,
                "phone": u.phone,
                "is_active": u.is_active,
                "created_at": u.created_at,
                "last_login": u.last_login
            }
            for u in users
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/")
async def create_user(
    request: Request,
    user_data: dict,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    username = user_data.get("username")
    password = user_data.get("password")
    role = user_data.get("role", "viewer")
    full_name = user_data.get("full_name")
    email = user_data.get("email")
    phone = user_data.get("phone")

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=get_password_hash(password),
        role=role,
        full_name=full_name,
        email=email,
        phone=phone
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await log_operation(
        db, current_user.id, "CREATE_USER", "创建用户", user.id,
        "POST", "/api/v1/users/", request.client.host if request.client else None,
        str(user_data), 200, None
    )

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "created_at": user.created_at
    }


@router.get("/{user_id}")
async def get_user(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await log_operation(
        db, current_user.id, "GET_USER", "查看用户", user_id,
        "GET", f"/api/v1/users/{user_id}", request.client.host if request.client else None,
        None, 200, None
    )

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "last_login": user.last_login
    }


@router.put("/{user_id}")
async def update_user(
    request: Request,
    user_id: str,
    user_data: dict,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_fields = ["full_name", "email", "phone", "role", "is_active"]
    for field in update_fields:
        if field in user_data:
            setattr(user, field, user_data[field])

    await db.commit()
    await db.refresh(user)

    await log_operation(
        db, current_user.id, "UPDATE_USER", "更新用户", user_id,
        "PUT", f"/api/v1/users/{user_id}", request.client.host if request.client else None,
        str(user_data), 200, None
    )

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active
    }


@router.delete("/{user_id}")
async def delete_user(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能删除管理员账户")

    user.is_active = False
    await db.commit()

    await log_operation(
        db, current_user.id, "DELETE_USER", "禁用用户", user_id,
        "DELETE", f"/api/v1/users/{user_id}", request.client.host if request.client else None,
        None, 200, None
    )

    return {"message": "用户已禁用"}


@router.put("/{user_id}/reset-password")
async def reset_password(
    request: Request,
    user_id: str,
    new_password: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password_hash = get_password_hash(new_password)
    await db.commit()

    await log_operation(
        db, current_user.id, "RESET_PASSWORD", "重置密码", user_id,
        "PUT", f"/api/v1/users/{user_id}/reset-password", request.client.host if request.client else None,
        None, 200, None
    )

    return {"message": "密码重置成功"}


@router.get("/roles/list")
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    roles = [
        {"name": "admin", "display_name": "管理员", "description": "完全访问权限"},
        {"name": "judge", "display_name": "裁判", "description": "评分和管理权限"},
        {"name": "viewer", "display_name": "观众", "description": "只读访问权限"}
    ]
    return roles


async def log_operation(
    db: AsyncSession,
    user_id: str,
    action: str,
    resource: str,
    resource_id: str,
    method: str,
    path: str,
    ip_address: str,
    request_data: str,
    response_status: int,
    error_message: str
):
    try:
        log = OperationLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            method=method,
            path=path,
            ip_address=ip_address,
            request_data=request_data,
            response_status=response_status,
            error_message=error_message
        )
        db.add(log)
        await db.commit()
    except Exception:
        pass
