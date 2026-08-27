#!/usr/bin/env python3
"""
体育舞蹈评分系统 - 移动端测试清单生成器
生成可以在浏览器开发者工具中执行的测试步骤
"""

import json
from datetime import datetime

BASE_URL = "http://59.110.90.21"

def generate_test_checklist():
    """生成移动端测试清单"""
    
    checklist = {
        "system": "体育舞蹈评分系统",
        "version": "1.0.0",
        "test_date": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "mobile_viewport": {"width": 375, "height": 667, "device": "iPhone SE"},
        "test_users": {
            "admin": {"username": "admin", "password": "admin123", "role": "管理员"},
            "judge1": {"username": "judge1", "password": "judge123", "role": "裁判"},
            "viewer": {"username": "viewer", "password": "viewer123", "role": "观众"}
        },
        "test_scenarios": [
            {
                "id": "TC001",
                "name": "管理员登录",
                "priority": "高",
                "steps": [
                    "打开浏览器，访问 http://59.110.90.21",
                    "按 F12 打开开发者工具",
                    "点击左上角的设备图标 (Toggle device toolbar)",
                    "在设备下拉框中选择 'iPhone SE' 或设置自定义视口 375x667",
                    "在用户名输入框中输入: admin",
                    "在密码输入框中输入: admin123",
                    "点击 '登 录' 按钮",
                    "等待3秒，观察是否跳转到 dashboard 页面"
                ],
                "expected_result": "成功登录并跳转到仪表盘页面",
                "verification_points": [
                    "URL包含 /dashboard",
                    "页面显示 '仪表盘' 或 'Dashboard'",
                    "顶部显示 admin 用户信息"
                ]
            },
            {
                "id": "TC002",
                "name": "移动端侧边栏响应",
                "priority": "高",
                "steps": [
                    "在仪表盘页面",
                    "点击左上角的菜单/汉堡图标按钮",
                    "观察侧边栏是否展开",
                    "点击页面其他区域，观察侧边栏是否收起"
                ],
                "expected_result": "侧边栏可以正常展开和收起",
                "verification_points": [
                    "菜单按钮可见且可点击",
                    "侧边栏宽度约250px（移动端模式）",
                    "侧边栏包含主要导航菜单"
                ]
            },
            {
                "id": "TC003",
                "name": "赛事管理功能",
                "priority": "高",
                "steps": [
                    "点击侧边栏中的 '赛事管理' 或 '赛事列表'",
                    "观察赛事列表页面",
                    "检查是否有 '创建赛事' 按钮",
                    "点击 '创建赛事' 按钮"
                ],
                "expected_result": "赛事管理页面正常显示",
                "verification_points": [
                    "页面标题包含 '赛事'",
                    "可以查看到赛事列表",
                    "创建按钮可点击"
                ]
            },
            {
                "id": "TC004",
                "name": "裁判登录和评分",
                "priority": "高",
                "steps": [
                    "点击右上角用户名，下拉菜单中选择 '退出登录'",
                    "返回登录页面",
                    "输入用户名: judge1，密码: judge123",
                    "点击登录",
                    "登录成功后，点击 '裁判评分' 或直接访问 /judge"
                ],
                "expected_result": "裁判可以登录并访问评分页面",
                "verification_points": [
                    "登录成功",
                    "页面包含评分相关元素",
                    "显示当前待评分选手"
                ]
            },
            {
                "id": "TC005",
                "name": "观众登录和查看",
                "priority": "中",
                "steps": [
                    "退出当前登录",
                    "使用观众账号登录: viewer / viewer123",
                    "登录后访问 /viewer 或点击 '观众查看'",
                    "观察实时排名页面"
                ],
                "expected_result": "观众可以登录并查看排名",
                "verification_points": [
                    "登录成功",
                    "页面显示排名列表",
                    "没有管理/编辑功能（只读）"
                ]
            },
            {
                "id": "TC006",
                "name": "移动端表单交互",
                "priority": "中",
                "steps": [
                    "使用管理员登录",
                    "进入赛事管理",
                    "点击 '创建赛事'",
                    "尝试填写表单: 赛事名称、日期、地点等",
                    "检查输入框是否适配移动端"
                ],
                "expected_result": "表单在移动端可以正常填写",
                "verification_points": [
                    "输入框大小适中，适合触摸",
                    "日期选择器可正常弹出",
                    "提交按钮足够大，易于点击"
                ]
            },
            {
                "id": "TC007",
                "name": "移动端响应式布局",
                "priority": "高",
                "steps": [
                    "在不同视口下测试: 375x667, 414x896, 768x1024",
                    "观察页面布局变化",
                    "检查元素是否溢出屏幕",
                    "测试横向滚动是否平滑"
                ],
                "expected_result": "布局在不同视口下都能正常显示",
                "verification_points": [
                    "没有横向溢出",
                    "文字大小合适，可读性强",
                    "按钮和链接间距合理"
                ]
            },
            {
                "id": "TC008",
                "name": "网络错误处理",
                "priority": "低",
                "steps": [
                    "在开发者工具的 Network 标签中设置 'Offline'",
                    "尝试刷新页面或提交表单",
                    "观察错误提示",
                    "恢复网络连接"
                ],
                "expected_result": "有适当的错误提示",
                "verification_points": [
                    "显示友好的错误消息",
                    "提供重试选项",
                    "不影响用户体验"
                ]
            }
        ],
        "test_execution_guide": """
📱 移动端测试执行指南
=====================================================================

准备工作:
1. 确保服务器正在运行: http://59.110.90.21
2. 使用 Chrome/Edge/Safari 浏览器
3. 打开开发者工具 (F12)

启用移动端模拟:
1. 点击开发者工具左上角的设备图标 📱
2. 或按 Ctrl+Shift+M (Windows) / Cmd+Shift+M (Mac)
3. 在设备下拉框选择: iPhone SE / iPhone X / iPhone 12
4. 或手动设置视口: 宽度 375px，高度 667px

测试执行:
1. 按清单顺序执行每个测试场景
2. 记录实际结果
3. 截图保存异常情况
4. 标记通过/失败状态

常见问题:
- 如果页面加载慢，等待更长的时间
- 如果按钮点击无效，检查是否有loading状态
- 如果表单无法提交，检查必填字段
- 如果样式异常，检查是否需要刷新页面
        """,
        "browser_console_checkpoints": [
            "检查 Console 是否有 Error 级别日志",
            "检查 Network 是否有失败的请求 (红色)",
            "检查 Application/Storage 是否有异常数据",
            "检查 Performance 是否有性能问题"
        ]
    }
    
    return checklist

def main():
    checklist = generate_test_checklist()
    
    # 输出JSON格式
    print("\n" + "="*70)
    print("🏆 体育舞蹈评分系统 - 移动端测试清单")
    print("="*70)
    print(f"\n📅 测试时间: {checklist['test_date']}")
    print(f"🌐 测试地址: {checklist['base_url']}")
    print(f"📱 移动视口: {checklist['mobile_viewport']['device']} ({checklist['mobile_viewport']['width']}x{checklist['mobile_viewport']['height']})")
    print("\n" + "="*70)
    
    print("\n👥 测试账号:")
    for key, user in checklist['test_users'].items():
        print(f"  - {user['role']}: {user['username']} / {user['password']}")
    
    print("\n📋 测试场景列表:")
    for i, scenario in enumerate(checklist['test_scenarios'], 1):
        print(f"\n  {i}. [{scenario['id']}] {scenario['name']} (优先级: {scenario['priority']})")
        print(f"     步骤数: {len(scenario['steps'])}")
        print(f"     预期结果: {scenario['expected_result']}")
    
    print("\n" + "="*70)
    print(checklist['test_execution_guide'])
    print("="*70)
    
    # 保存为JSON文件
    with open('/tmp/mobile_test_checklist.json', 'w', encoding='utf-8') as f:
        json.dump(checklist, f, ensure_ascii=False, indent=2)
    print("\n✅ 测试清单已保存到: /tmp/mobile_test_checklist.json")

if __name__ == "__main__":
    main()
