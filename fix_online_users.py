#!/usr/bin/env python3
"""
修复线上服务器用户角色问题
"""
import requests

BASE_URL = "http://59.110.90.21"

def delete_user(user_id, token):
    """删除用户"""
    try:
        resp = requests.delete(
            f"{BASE_URL}/api/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        print(f"删除用户 {user_id}: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"删除用户出错: {e}")
        return False

def register_user(username, password):
    """注册用户"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            params={"username": username, "password": password},
            timeout=30
        )
        print(f"注册用户 {username}: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"注册用户出错: {e}")
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
            print(f"登录成功: {username} (角色: {data['role']})")
            return data["access_token"], data["role"], data["user_id"]
        print(f"登录失败: {resp.status_code}")
        return None, None, None
    except Exception as e:
        print(f"登录出错: {e}")
        return None, None, None

def main():
    print("=" * 50)
    print("修复线上服务器用户角色问题")
    print("服务器地址:", BASE_URL)
    print("=" * 50)

    # 先尝试登录admin看看当前状态
    print("\n[1] 检查当前admin用户状态...")
    token, role, user_id = login("admin", "admin123")
    
    if role == "admin":
        print("✅ admin用户已经是管理员角色")
        return
    elif role == "viewer":
        print("❌ admin用户当前是viewer角色，需要修复")
    else:
        print("⚠️  用户不存在或登录失败")

    # 方案：删除所有用户，重新按正确顺序注册
    print("\n[2] 尝试重置用户数据...")
    
    # 尝试删除现有用户（如果有权限）
    if token:
        print("尝试删除用户...")
        delete_user(user_id, token)
    
    # 重新注册用户，第一个注册的会自动成为admin
    print("\n[3] 重新注册用户（第一个注册的用户会成为管理员）...")
    register_user("admin", "admin123")
    
    # 验证admin角色
    print("\n[4] 验证admin角色...")
    token, role, user_id = login("admin", "admin123")
    if role == "admin":
        print("✅ admin用户现在是管理员角色！")
    else:
        print(f"❌ 角色仍然是: {role}")
        print("需要手动检查数据库")
        return
    
    # 注册其他用户
    print("\n[5] 注册其他测试用户...")
    register_user("judge1", "judge123")
    register_user("judge2", "judge123")
    register_user("judge3", "judge123")
    register_user("judge4", "judge123")
    register_user("judge5", "judge123")
    register_user("viewer", "viewer123")

    print("\n" + "=" * 50)
    print("用户角色修复完成!")
    print("=" * 50)
    print(f"\n登录信息:")
    print(f"  服务器地址: {BASE_URL}")
    print(f"  管理员: admin / admin123")
    print(f"  裁判: judge1~judge5 / judge123")
    print(f"  观众: viewer / viewer123")
    print("=" * 50)

if __name__ == "__main__":
    main()
