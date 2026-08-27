#!/usr/bin/env python3
"""
初始化测试账号脚本
为体育舞蹈评分系统创建不同角色的测试账号
"""

import asyncio
import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import engine, async_session
from app.core.security import get_password_hash
from app.models.unit_points import User, Role, Permission
import uuid


async def create_test_users():
    """创建测试账号"""
    
    async with async_session() as session:
        # 检查是否已有用户
        result = await session.execute(select(User))
        existing_users = result.scalars().all()
        
        if existing_users:
            print(f"系统中已有 {len(existing_users)} 个用户：")
            for user in existing_users:
                print(f"  - {user.username} ({user.role})")
            print("\n是否要继续创建新账号？(当前账号不会被删除)")
            
        # 定义测试账号
        test_users = [
            {
                "username": "admin",
                "password": "admin123",
                "role": "admin",
                "full_name": "系统管理员"
            },
            {
                "username": "judge1",
                "password": "judge123",
                "role": "judge",
                "full_name": "裁判1号"
            },
            {
                "username": "judge2",
                "password": "judge123",
                "role": "judge",
                "full_name": "裁判2号"
            },
            {
                "username": "judge3",
                "password": "judge123",
                "role": "judge",
                "full_name": "裁判3号"
            },
            {
                "username": "judge4",
                "password": "judge123",
                "role": "judge",
                "full_name": "裁判4号"
            },
            {
                "username": "judge5",
                "password": "judge123",
                "role": "judge",
                "full_name": "裁判5号"
            },
            {
                "username": "viewer",
                "password": "viewer123",
                "role": "viewer",
                "full_name": "观众用户"
            }
        ]
        
        created_count = 0
        
        for user_data in test_users:
            # 检查用户是否已存在
            result = await session.execute(
                select(User).where(User.username == user_data["username"])
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"用户已存在: {user_data['username']} ({user_data['role']})")
                continue
            
            # 创建新用户
            user = User(
                id=str(uuid.uuid4()),
                username=user_data["username"],
                password_hash=get_password_hash(user_data["password"]),
                role=user_data["role"],
                full_name=user_data["full_name"],
                is_active=True
            )
            session.add(user)
            created_count += 1
            print(f"创建用户: {user_data['username']} ({user_data['role']})")
        
        await session.commit()
        
        print(f"\n✅ 成功创建 {created_count} 个测试账号！")
        print("\n" + "="*60)
        print("测试账号列表")
        print("="*60)
        
        for user_data in test_users:
            print(f"{user_data['role']:10} | {user_data['username']:15} | 密码: {user_data['password']}")
        
        print("="*60)
        print("\n角色说明：")
        print("  admin    - 管理员：可管理赛事、场次、选手，查看所有成绩")
        print("  judge    - 裁判：只能进行评分操作")
        print("  viewer   - 观众：只能查看成绩和排名，不能评分")
        print("\n提示：裁判账号在评分时只能看到选手背号，不能看到个人信息")


if __name__ == "__main__":
    print("正在初始化测试账号...")
    asyncio.run(create_test_users())
