#!/usr/bin/env python3
"""极简测试"""
from playwright.sync_api import sync_playwright
import time

print("启动浏览器...")
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-gpu', '--disable-web-security']
    )
    page = browser.new_page()
    
    print("访问登录页...")
    page.goto("http://localhost/login", wait_until='commit', timeout=15000)
    print(f"标题: {page.title()}")
    
    print("输入账号...")
    page.fill('input[type="text"]', 'admin')
    page.fill('input[type="password"]', 'admin123')
    
    print("点击登录...")
    page.click('button')
    time.sleep(2)
    
    print(f"当前URL: {page.url}")
    
    page.screenshot(path="/tmp/test.png")
    print("截图已保存")
    
    browser.close()

print("测试完成!")
