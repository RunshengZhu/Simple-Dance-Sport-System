#!/usr/bin/env python3
"""
体育舞蹈评分系统 - API验证脚本
验证服务器功能是否正常，为移动端测试做准备
"""

import requests
import json

BASE_URL = "http://59.110.90.21"
API_BASE = f"{BASE_URL}/api/v1"

def log(msg, status="INFO"):
    symbols = {"INFO": "📋", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
    print(f"{symbols.get(status, '📋')} [{status}] {msg}")

def test_server():
    results = []
    
    print("\n" + "="*70)
    print("🔍 体育舞蹈评分系统 - 服务器验证")
    print("="*70)
    print(f"测试目标: {BASE_URL}")
    print("="*70 + "\n")
    
    # 测试1: Web首页
    log("测试1: Web首页...", "INFO")
    try:
        resp = requests.get(BASE_URL, timeout=10)
        has_title = "体育舞蹈" in resp.text or len(resp.text) > 0
        log(f"Web首页: HTTP {resp.status_code}")
        results.append(("Web首页访问", resp.status_code == 200 and has_title))
    except Exception as e:
        log(f"Web首页失败: {e}", "ERROR")
        results.append(("Web首页访问", False))
    
    # 测试2: API基础路径
    log("\n测试2: API基础路径...", "INFO")
    try:
        resp = requests.get(API_BASE, timeout=10)
        log(f"API基础: HTTP {resp.status_code}")
        results.append(("API基础路径", resp.status_code in [200, 404]))
    except Exception as e:
        log(f"API基础失败: {e}", "ERROR")
        results.append(("API基础路径", False))
    
    # 测试3: 登录API
    log("\n测试3: 管理员登录...", "INFO")
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": "admin", "password": "admin123"},
            timeout=10
        )
        data = resp.json()
        if resp.status_code == 200 and "access_token" in data:
            token = data["access_token"]
            log(f"登录成功: 获取到token")
            results.append(("管理员登录", True))
        else:
            log(f"登录失败: {data}", "ERROR")
            results.append(("管理员登录", False))
            token = None
    except Exception as e:
        log(f"登录异常: {e}", "ERROR")
        results.append(("管理员登录", False))
        token = None
    
    # 测试4: 赛事列表API
    log("\n测试4: 赛事列表API...", "INFO")
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = requests.get(f"{API_BASE}/competitions", headers=headers, timeout=10)
        log(f"赛事列表: HTTP {resp.status_code}")
        results.append(("赛事列表API", resp.status_code in [200, 401]))
    except Exception as e:
        log(f"赛事列表失败: {e}", "ERROR")
        results.append(("赛事列表API", False))
    
    # 测试5: 裁判登录
    log("\n测试5: 裁判登录...", "INFO")
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": "judge1", "password": "judge123"},
            timeout=10
        )
        if resp.status_code == 200:
            log("裁判登录成功")
            results.append(("裁判登录", True))
        else:
            results.append(("裁判登录", False))
    except Exception as e:
        log(f"裁判登录失败: {e}", "ERROR")
        results.append(("裁判登录", False))
    
    # 测试6: 观众登录
    log("\n测试6: 观众登录...", "INFO")
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": "viewer", "password": "viewer123"},
            timeout=10
        )
        if resp.status_code == 200:
            log("观众登录成功")
            results.append(("观众登录", True))
        else:
            results.append(("观众登录", False))
    except Exception as e:
        log(f"观众登录失败: {e}", "ERROR")
        results.append(("观众登录", False))
    
    # 汇总
    print("\n" + "="*70)
    print("📊 验证结果")
    print("="*70)
    
    passed = 0
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")
        if success:
            passed += 1
    
    print("="*70)
    print(f"通过: {passed}/{len(results)} ({passed/len(results)*100:.0f}%)")
    print("="*70 + "\n")
    
    if passed == len(results):
        print("🎉 服务器验证通过！")
        print("\n📱 移动端测试指南:")
        print(f"  1. 在浏览器中打开: {BASE_URL}")
        print("  2. 按 F12 打开开发者工具")
        print("  3. 点击左上角的设备图标 (Toggle device toolbar)")
        print("  4. 选择设备: iPhone X / iPhone SE / 自定义 375x667")
        print("  5. 测试登录和管理功能")
    else:
        print("⚠️  部分验证失败")
    
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    exit(test_server())
