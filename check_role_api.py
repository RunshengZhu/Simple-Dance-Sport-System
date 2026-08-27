#!/usr/bin/env python3
"""
为线上服务器添加临时角色修改API
"""
import requests

BASE_URL = "http://59.110.90.21"

def add_role_api():
    """检查是否有修改角色的API"""
    print("检查可用的API端点...")
    
    # 尝试各种可能的端点
    endpoints = [
        "/api/v1/users/{user_id}/role",
        "/api/v1/users/role",
        "/api/v1/auth/role",
        "/api/v1/admin/set-role"
    ]
    
    # 获取当前用户信息
    print("\n获取当前用户信息...")
    token, role, user_id = login("admin", "admin123")
    
    if not token:
        print("无法登录")
        return
    
    print(f"当前用户ID: {user_id}")
    print(f"当前角色: {role}")
    
    # 尝试修改角色
    print("\n尝试修改角色...")
    
    for endpoint in endpoints:
        # 替换user_id
        url = endpoint.replace("{user_id}", user_id)
        
        try:
            resp = requests.put(
                f"{BASE_URL}{url}",
                json={"role": "admin"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30
            )
            print(f"PUT {url}: {resp.status_code}")
            
            if resp.status_code == 200:
                print("✅ 角色修改成功!")
                # 验证
                token2, role2, _ = login("admin", "admin123")
                if role2 == "admin":
                    print("✅ 验证成功! admin现在是管理员")
                    return True
        except Exception as e:
            pass
    
    print("\n❌ 未找到修改角色的API")
    return False

def login(username, password):
    """登录获取token"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": username, "password": password},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("access_token"), data.get("role"), data.get("user_id")
        return None, None, None
    except Exception as e:
        return None, None, None

if __name__ == "__main__":
    success = add_role_api()
    
    if not success:
        print("\n" + "=" * 50)
        print("需要手动修复")
        print("=" * 50)
        print("\n请联系服务器管理员执行以下操作:")
        print("1. 删除数据库文件并重启服务")
        print("2. 或手动修改数据库中admin用户的role字段")
        print("\n数据库文件通常位于:")
        print("  /path/to/backend/database.db")
        print("\nSQL命令:")
        print("  UPDATE users SET role = 'admin' WHERE username = 'admin';")
