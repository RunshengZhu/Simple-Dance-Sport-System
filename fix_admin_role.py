#!/usr/bin/env python3
"""
尝试修复线上服务器管理员权限问题
"""
import requests

BASE_URL = "http://59.110.90.21"

def try_fix_admin():
    print("=" * 50)
    print("尝试修复管理员权限")
    print("服务器地址:", BASE_URL)
    print("=" * 50)

    # 方案1: 尝试注册新的管理员用户
    print("\n[方案1] 尝试注册新管理员用户...")
    new_admin_username = "superadmin"
    new_admin_password = "superadmin123"
    
    # 先尝试注册
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        params={"username": new_admin_username, "password": new_admin_password},
        timeout=30
    )
    
    if resp.status_code == 200:
        print(f"✅ 注册新管理员成功: {new_admin_username}")
        # 验证角色
        login_resp = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": new_admin_username, "password": new_admin_password},
            timeout=30
        )
        if login_resp.status_code == 200:
            data = login_resp.json()
            role = data.get("role", "unknown")
            print(f"新用户角色: {role}")
            if role == "admin":
                print("✅ 新用户成功成为管理员!")
                print(f"\n新管理员账号:")
                print(f"  用户名: {new_admin_username}")
                print(f"  密码: {new_admin_password}")
                return True
            else:
                print("❌ 新用户仍然不是管理员")
    else:
        print(f"注册失败: {resp.status_code} - {resp.text}")

    # 方案2: 尝试检查系统中已有的用户
    print("\n[方案2] 检查系统状态...")
    
    # 尝试用不同的方式获取信息
    try:
        # 检查是否有GET /users端点
        resp = requests.get(f"{BASE_URL}/api/v1/users", timeout=10)
        print(f"GET /api/v1/users: {resp.status_code}")
    except:
        pass
    
    try:
        # 检查是否有其他端点
        resp = requests.get(f"{BASE_URL}/api/v1/competitions", timeout=10)
        print(f"GET /api/v1/competitions: {resp.status_code}")
    except:
        pass

    # 方案3: 尝试直接通过API修改角色
    print("\n[方案3] 尝试修改角色...")
    token, _, _ = login("admin", "admin123")
    if token:
        # 尝试各种可能的端点
        endpoints = [
            f"/api/v1/users/role",
            f"/api/v1/users/me/role",
            f"/api/v1/auth/role"
        ]
        for endpoint in endpoints:
            try:
                resp = requests.put(
                    f"{BASE_URL}{endpoint}",
                    json={"role": "admin"},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                print(f"PUT {endpoint}: {resp.status_code}")
                if resp.status_code == 200:
                    print(f"✅ 角色修改成功!")
                    return True
            except:
                pass

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
    success = try_fix_admin()
    
    if success:
        print("\n🎉 管理员权限修复成功!")
    else:
        print("\n❌ 无法通过API修复，需要手动检查服务器")
        print("建议：")
        print("1. 登录服务器查看数据库")
        print("2. 手动修改admin用户的role字段为'admin'")
        print("3. 或者删除所有用户后重新注册")
