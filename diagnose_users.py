#!/usr/bin/env python3
"""
诊断线上服务器用户角色问题
"""
import requests

BASE_URL = "http://59.110.90.21"

def diagnose_user_count():
    """诊断用户数量问题"""
    print("=" * 50)
    print("诊断用户角色问题")
    print("服务器地址:", BASE_URL)
    print("=" * 50)

    # 尝试检查用户数量
    print("\n[1] 检查用户数量...")
    
    # 尝试各种可能的端点
    endpoints = [
        "/api/v1/users",
        "/api/v1/users/list",
        "/api/v1/auth/users"
    ]
    
    found_users = False
    for endpoint in endpoints:
        try:
            resp = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            if resp.status_code == 200:
                print(f"找到用户列表端点: {endpoint}")
                print(f"响应: {resp.text[:200]}")
                found_users = True
                break
        except Exception as e:
            pass
    
    if not found_users:
        print("未找到用户列表端点")

    # 尝试检查是否有数据库初始化问题
    print("\n[2] 检查系统初始化状态...")
    
    # 创建一个简单的测试用户，看看第一个用户是否能成为admin
    test_username = f"test_user_{int(time.time())}"
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        params={"username": test_username, "password": "test123"},
        timeout=30
    )
    
    if resp.status_code == 200:
        print(f"创建测试用户成功: {test_username}")
        
        # 登录检查角色
        login_resp = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": test_username, "password": "test123"},
            timeout=30
        )
        
        if login_resp.status_code == 200:
            data = login_resp.json()
            role = data.get("role", "unknown")
            print(f"测试用户角色: {role}")
            
            if role == "admin":
                print("✅ 第一个用户成功成为管理员!")
                print("问题原因: 之前已有其他用户存在")
            else:
                print("❌ 即使是新用户也不是管理员")
                print("问题原因: 代码逻辑有问题或数据库已有用户")
    else:
        print(f"创建测试用户失败: {resp.status_code}")

if __name__ == "__main__":
    import time
    diagnose_user_count()
