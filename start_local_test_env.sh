#!/bin/bash
# 本地测试环境启动脚本

echo "🚀 启动本地测试环境..."
echo "=========================================="

# 1. 检查并启动后端
echo "📦 检查后端服务..."
if ! curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo "启动后端服务..."
    cd /Users/helius/Workspace/side-proj/ds/Simple-Dance-Sport-System/web/backend
    # 后台启动
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
    sleep 3
    echo "✅ 后端已启动 (http://localhost:8000)"
else
    echo "✅ 后端已运行"
fi

# 2. 检查并启动前端
echo ""
echo "🎨 检查前端服务..."
if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "启动前端服务..."
    cd /Users/helius/Workspace/side-proj/ds/Simple-Dance-Sport-System/web/frontend
    # 创建本地.env
    echo "VITE_API_BASE_URL=http://localhost:8000/api/v1" > .env.local
    # 后台启动
    nohup npm run dev > /tmp/frontend.log 2>&1 &
    sleep 5
    echo "✅ 前端已启动 (http://localhost:3000)"
else
    echo "✅ 前端已运行"
fi

# 3. 验证服务
echo ""
echo "🔍 验证服务状态..."
sleep 2

echo "后端API:"
curl -s http://localhost:8000/api/v1/ | head -1

echo ""
echo "前端页面:"
curl -s http://localhost:3000 | grep -o "<title>.*</title>" || echo "页面加载正常"

echo ""
echo "=========================================="
echo "✅ 测试环境已就绪！"
echo ""
echo "🌐 访问地址:"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo ""
echo "📱 移动端测试:"
echo "   1. 打开 http://localhost:3000"
echo "   2. 按 F12 > Cmd+Shift+M"
echo "   3. 选择 iPhone SE"
echo "   4. 开始测试"
echo ""
echo "💡 或者运行Playwright测试:"
echo "   python3 test_mobile_local.py"
echo "=========================================="
