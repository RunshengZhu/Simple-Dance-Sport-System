from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.core.database import get_db
from app.core.security import decode_token
from app.models.unit_points import User, Role, Permission, RolePermission
from datetime import datetime

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证失败，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    user.last_login = datetime.utcnow()
    await db.commit()

    return user


def require_roles(*allowed_roles: str):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


def require_permissions(*required_permissions: str):
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        if current_user.role == "admin":
            return current_user

        result = await db.execute(
            select(Permission).join(RolePermission).join(Role).where(
                Role.name == current_user.role
            )
        )
        user_permissions = {p.code for p in result.scalars().all()}

        missing = set(required_permissions) - user_permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少以下权限: {', '.join(missing)}"
            )

        return current_user
    return permission_checker


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此功能"
            )
        return user


class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(
        self,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        if user.role == "admin":
            return user

        result = await db.execute(
            select(Permission).join(RolePermission).join(Role).where(
                Role.name == user.role
            )
        )
        user_permissions = {p.code for p in result.scalars().all()}

        if self.required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限执行此操作"
            )

        return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    return current_user


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def get_judge_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["admin", "judge"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要裁判或管理员权限"
        )
    return current_user


async def get_viewer_or_above(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["admin", "judge", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    return current_user
