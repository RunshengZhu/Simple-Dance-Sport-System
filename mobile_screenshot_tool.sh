#!/bin/bash
# 移动端截图工具 - 使用浏览器CLI模式截图

BASE_URL="http://59.110.90.21"
OUTPUT_DIR="/tmp/mobile_screenshots"
mkdir -p "$OUTPUT_DIR"

echo "📱 体育舞蹈评分系统 - 移动端截图工具"
echo "========================================"
echo ""

# 检查是否有截图工具
if ! command -v screencapture &> /dev/null && ! command -v gnome-screenshot &> /dev/null; then
    echo "⚠️  没有找到截图工具"
    echo "请手动打开浏览器访问: $BASE_URL"
    exit 1
fi

echo "✅ 测试服务器连接..."
if curl -s --max-time 5 "$BASE_URL" > /dev/null; then
    echo "✅ 服务器连接正常"
else
    echo "❌ 服务器连接失败"
    exit 1
fi

echo ""
echo "📸 截图将保存到: $OUTPUT_DIR"
echo ""
echo "请在浏览器中执行以下操作:"
echo ""
echo "1. 打开浏览器访问: $BASE_URL"
echo "2. 按 F12 打开开发者工具"
echo "3. 按 Ctrl+Shift+M (Mac: Cmd+Shift+M) 启用设备模式"
echo "4. 选择设备: iPhone SE 或设置 375x667"
echo "5. 执行以下测试并截图:"
echo ""
echo "   a) 登录页面 (保存为: login_mobile.png)"
echo "   b) 管理员登录后 (保存为: admin_dashboard.png)"
echo "   c) 赛事管理页面 (保存为: competitions.png)"
echo "   d) 侧边栏展开状态 (保存为: sidebar.png)"
echo "   e) 裁判评分页面 (保存为: judge_page.png)"
echo "   f) 观众查看页面 (保存为: viewer_page.png)"
echo ""
echo "6. 将截图保存到: $OUTPUT_DIR"
echo ""

# 尝试打开浏览器
if command -v open &> /dev/null; then
    echo "🌐 正在打开浏览器..."
    open "$BASE_URL"
elif command -v xdg-open &> /dev/null; then
    echo "🌐 正在打开浏览器..."
    xdg-open "$BASE_URL"
fi

echo ""
echo "✅ 完成后，运行以下命令查看截图:"
echo "   ls -la $OUTPUT_DIR"
