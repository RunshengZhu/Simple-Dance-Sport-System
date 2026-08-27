from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
from typing import Optional
import uuid
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.unit_points import User, OperationLog

router = APIRouter()


@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user:
        await log_operation(
            db, None, "LOGIN_FAILED", "用户登录", None,
            "POST", "/api/v1/auth/login", request.client.host if request.client else None,
            None, 401, "用户名不存在"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        if not verify_password(form_data.password, user.password_hash):
            await log_operation(
                db, user.id, "LOGIN_FAILED", "用户登录", user.id,
                "POST", "/api/v1/auth/login", request.client.host if request.client else None,
                None, 401, "密码错误"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception:
        await log_operation(
            db, user.id if 'user' in locals() else None, "LOGIN_FAILED", "用户登录", None,
            "POST", "/api/v1/auth/login", request.client.host if request.client else None,
            None, 401, "密码验证失败"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from datetime import datetime
    user.last_login = datetime.utcnow()
    await db.commit()

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    await log_operation(
        db, user.id, "LOGIN", "用户登录", user.id,
        "POST", "/api/v1/auth/login", request.client.host if request.client else None,
        None, 200, None
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "user_id": user.id,
        "full_name": user.full_name
    }


@router.post("/register")
async def register(
    request: Request,
    username: str,
    password: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        await log_operation(
            db, None, "REGISTER_FAILED", "用户注册", None,
            "POST", "/api/v1/auth/register", request.client.host if request.client else None,
            None, 400, "用户名已存在"
        )
        raise HTTPException(status_code=400, detail="用户名已存在")

    count_result = await db.execute(select(User))
    user_count = len(count_result.scalars().all())
    
    role = "admin" if user_count == 0 else "viewer"

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=get_password_hash(password),
        role=role
    )
    db.add(user)
    await db.commit()

    await log_operation(
        db, user.id, "REGISTER", "用户注册", user.id,
        "POST", "/api/v1/auth/register", request.client.host if request.client else None,
        None, 200, None
    )

    return {"message": "注册成功", "user_id": user.id}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await log_operation(
        db, current_user.id, "LOGOUT", "用户登出", current_user.id,
        "POST", "/api/v1/auth/logout", request.client.host if request.client else None,
        None, 200, None
    )

    return {"message": "登出成功"}


@router.put("/password")
async def change_password(
    request: Request,
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not verify_password(old_password, current_user.password_hash):
        await log_operation(
            db, current_user.id, "PASSWORD_CHANGE_FAILED", "修改密码", current_user.id,
            "PUT", "/api/v1/auth/password", request.client.host if request.client else None,
            None, 400, "旧密码错误"
        )
        raise HTTPException(status_code=400, detail="旧密码错误")

    current_user.password_hash = get_password_hash(new_password)
    await db.commit()

    await log_operation(
        db, current_user.id, "PASSWORD_CHANGE", "修改密码", current_user.id,
        "PUT", "/api/v1/auth/password", request.client.host if request.client else None,
        None, 200, None
    )

    return {"message": "密码修改成功"}


async def log_operation(
    db: AsyncSession,
    user_id: Optional[str],
    action: str,
    resource: str,
    resource_id: Optional[str],
    method: str,
    path: str,
    ip_address: Optional[str],
    request_data: Optional[str] = None,
    response_status: Optional[int] = None,
    error_message: Optional[str] = None
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
