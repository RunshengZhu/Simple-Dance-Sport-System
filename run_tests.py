#!/usr/bin/env python3
"""
测试报告生成器
运行Playwright测试并生成HTML报告
"""

import subprocess
import sys
import os
from datetime import datetime
import json

def run_tests():
    """运行Playwright测试"""
    print("=" * 60)
    print("体育舞蹈评分系统 - Web UI自动化测试")
    print("=" * 60)
    print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n正在安装依赖...")
    
    # 安装依赖
    result = subprocess.run(
        ['npm', 'install'],
        cwd='../frontend',
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ 依赖安装失败: {result.stderr}")
        return False
    
    print("✅ 依赖安装完成")
    print("\n正在运行测试...")
    
    # 运行Playwright测试
    result = subprocess.run(
        ['npx', 'playwright', 'test', '--reporter=html'],
        cwd='../frontend',
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    if result.stderr:
        print(result.stderr)
    
    return result.returncode == 0

def generate_report(test_results):
    """生成HTML测试报告"""
    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>体育舞蹈评分系统 - Web UI自动化测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f7fa;
            padding: 40px 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 24px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .stat-card .value {{ font-size: 36px; font-weight: bold; color: #409eff; }}
        .stat-card .label {{ color: #666; margin-top: 8px; }}
        .test-list {{
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .test-item {{
            padding: 20px;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .test-item:last-child {{ border-bottom: none; }}
        .test-item.pass {{ background: #f6ffed; }}
        .test-item.fail {{ background: #fff2f0; }}
        .test-icon {{ font-size: 24px; width: 40px; text-align: center; }}
        .test-content {{ flex: 1; }}
        .test-title {{ font-weight: 600; color: #333; margin-bottom: 4px; }}
        .test-desc {{ font-size: 14px; color: #999; }}
        .badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .badge-pass {{ background: #d9f7be; color: #52c41a; }}
        .badge-fail {{ background: #fff1f0; color: #f5222d; }}
        .badge-pending {{ background: #f0f5ff; color: #1890ff; }}
        .section {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .section h2 {{ margin-bottom: 16px; color: #333; }}
        .feature-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 16px;
        }}
        .feature-item {{
            padding: 16px;
            background: #fafafa;
            border-radius: 8px;
            border-left: 4px solid #409eff;
        }}
        .feature-item h3 {{ color: #409eff; margin-bottom: 8px; }}
        .feature-item p {{ color: #666; font-size: 14px; line-height: 1.6; }}
        .footer {{
            text-align: center;
            color: #999;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e8e8e8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏆 体育舞蹈评分系统</h1>
            <p>Web UI 自动化测试报告</p>
            <p style="margin-top: 16px; font-size: 14px;">
                生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="value">{test_results.get('total', 0)}</div>
                <div class="label">总测试数</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color: #52c41a;">{test_results.get('passed', 0)}</div>
                <div class="label">通过</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color: #f5222d;">{test_results.get('failed', 0)}</div>
                <div class="label">失败</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color: #1890ff;">{test_results.get('duration', 'N/A')}</div>
                <div class="label">耗时(秒)</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📋 测试项目清单</h2>
            <div class="test-list">
                {''.join([
                    f'''<div class="test-item {'pass' if t['status'] == 'passed' else 'fail'}">
                        <div class="test-icon">{'✅' if t['status'] == 'passed' else '❌'}</div>
                        <div class="test-content">
                            <div class="test-title">{t['title']}</div>
                            <div class="test-desc">{t['description']}</div>
                        </div>
                        <span class="badge badge-{'pass' if t['status'] == 'passed' else 'fail'}">
                            {t['status']}
                        </span>
                    </div>'''
                    for t in test_results.get('tests', [])
                ])}
            </div>
        </div>
        
        <div class="section">
            <h2>🎯 重点测试项</h2>
            <div class="feature-grid">
                <div class="feature-item">
                    <h3>🔐 隐私保护</h3>
                    <p>裁判评分时只显示背号，不显示选手姓名和单位信息，防止评分偏见。</p>
                </div>
                <div class="feature-item">
                    <h3>⚡ 自动计算</h3>
                    <p>当所有裁判提交评分后，系统自动计算成绩，无需手动触发。</p>
                </div>
                <div class="feature-item">
                    <h3>📱 移动端适配</h3>
                    <p>响应式布局，支持手机、平板等多种设备，触摸操作友好。</p>
                </div>
                <div class="feature-item">
                    <h3>👥 角色权限</h3>
                    <p>区分管理员、裁判、观众角色，不同角色看到不同内容。</p>
                </div>
                <div class="feature-item">
                    <h3>📊 实时排名</h3>
                    <p>成绩计算后实时更新单位排名，支持多维度统计。</p>
                </div>
                <div class="feature-item">
                    <h3>🔄 完整流程</h3>
                    <p>覆盖从创建赛事到成绩发布的全流程测试。</p>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>📝 测试说明</h2>
            <div class="feature-item">
                <h3>测试环境要求</h3>
                <p>
                    1. Node.js >= 16.0.0<br>
                    2. Python >= 3.8 (用于后端服务)<br>
                    3. 现代浏览器 (Chrome/Firefox/Safari)<br>
                    4. 后端服务运行在 http://localhost:8000<br>
                    5. 前端服务运行在 http://localhost:5173
                </p>
            </div>
            <div class="feature-item" style="margin-top: 16px;">
                <h3>运行测试命令</h3>
                <p>
                    # 安装依赖<br>
                    cd web/frontend<br>
                    npm install<br>
                    <br>
                    # 运行测试<br>
                    npx playwright test<br>
                    <br>
                    # 查看HTML报告<br>
                    npx playwright show-report
                </p>
            </div>
        </div>
        
        <div class="footer">
            <p>体育舞蹈评分系统 - Web UI自动化测试报告</p>
            <p>Generated by Playwright</p>
        </div>
    </div>
</body>
</html>
"""
    
    # 保存报告
    report_path = os.path.join(os.path.dirname(__file__), 'test-report.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ HTML报告已生成: {report_path}")
    return report_path

def main():
    # 默认测试结果（用于生成模板报告）
    test_results = {
        'total': 10,
        'passed': 0,
        'failed': 0,
        'duration': 'N/A',
        'tests': [
            {'title': '1. 登录功能测试', 'description': '验证用户登录功能', 'status': 'pending'},
            {'title': '2. 管理员创建赛事流程', 'description': '验证管理员创建赛事功能', 'status': 'pending'},
            {'title': '3. 导入选手数据', 'description': '验证导入选手数据功能', 'status': 'pending'},
            {'title': '4. 裁判评分界面隐私保护测试', 'description': '验证裁判评分时只显示背号，不显示选手信息', 'status': 'pending'},
            {'title': '5. 裁判评分交互测试', 'description': '验证裁判评分交互功能', 'status': 'pending'},
            {'title': '6. 成绩查看功能测试', 'description': '验证成绩查看和排名显示功能', 'status': 'pending'},
            {'title': '7. 移动端响应式布局测试', 'description': '验证移动端适配功能', 'status': 'pending'},
            {'title': '8. 多裁判评分自动计算测试', 'description': '验证多裁判评分后自动计算成绩', 'status': 'pending'},
            {'title': '9. 用户权限测试', 'description': '验证不同角色的访问权限', 'status': 'pending'},
            {'title': '10. 退出登录测试', 'description': '验证退出登录功能', 'status': 'pending'},
        ]
    }
    
    # 生成报告
    report_path = generate_report(test_results)
    
    print("\n" + "=" * 60)
    print("下一步操作")
    print("=" * 60)
    print(f"\n1. 打开报告预览: {report_path}")
    print("\n2. 运行实际测试:")
    print("   cd web/frontend")
    print("   npm run dev &")
    print("   cd ../backend && uvicorn app.main:app --reload --port 8000 &")
    print("   cd ../frontend")
    print("   npx playwright test")
    print("\n3. 查看Playwright HTML报告:")
    print("   npx playwright show-report")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
