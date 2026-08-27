#!/bin/bash

# 体育舞蹈评分系统 - Web UI自动化测试启动脚本

echo "=================================================="
echo "  体育舞蹈评分系统 - Web UI自动化测试"
echo "=================================================="
echo ""

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ 错误: $1 未安装"
        echo "   请先安装: $2"
        exit 1
    fi
}

# 检查必要的命令
echo "📦 检查依赖..."
check_command "node" "Node.js (https://nodejs.org)"
check_command "npm" "npm (随Node.js安装)"
check_command "python3" "Python 3 (https://www.python.org)"

# 检查当前目录
if [ ! -d "web/frontend" ] || [ ! -d "web/backend" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

echo "✅ 依赖检查完成"
echo ""

# 创建测试报告目录
mkdir -p web/frontend/playwright-report
mkdir -p web/frontend/test-results

# 启动后端服务
echo "🚀 启动后端服务..."
cd web/backend
if ! pgrep -f "uvicorn app.main:app" > /dev/null; then
    uvicorn app.main:app --reload --port 8000 &
    BACKEND_PID=$!
    echo "✅ 后端服务已启动 (PID: $BACKEND_PID)"
    echo "   访问地址: http://localhost:8000"
else
    echo "✅ 后端服务已在运行"
fi
cd ../..

# 等待后端启动
echo "⏳ 等待后端服务就绪..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ 后端服务就绪"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️  后端服务启动超时，继续运行测试..."
    fi
    sleep 1
done
echo ""

# 安装前端依赖
echo "📦 安装前端依赖..."
cd web/frontend
npm install > /dev/null 2>&1
echo "✅ 依赖安装完成"
cd ../..

# 创建测试账号
echo "👤 创建测试账号..."
cd web/backend
python3 init_test_users.py > /dev/null 2>&1
echo "✅ 测试账号创建完成"
cd ../..

echo ""
echo "=================================================="
echo "  测试环境已就绪！"
echo "=================================================="
echo ""
echo "📝 可用的测试选项:"
echo ""
echo "  1. 运行完整测试套件"
echo "     命令: cd web/frontend && npx playwright test"
echo ""
echo "  2. 运行特定测试"
echo "     命令: cd web/frontend && npx playwright test -k '登录'"
echo ""
echo "  3. 查看HTML报告"
echo "     命令: cd web/frontend && npx playwright show-report"
echo ""
echo "  4. 打开前端预览"
echo "     命令: cd web/frontend && npm run dev"
echo ""
echo "=================================================="
echo ""
read -p "是否立即运行测试？(y/n): " choice

case $choice in
    [yY])
        echo ""
        echo "🧪 开始运行测试..."
        echo ""
        cd web/frontend
        npx playwright test --reporter=list
        ;;
    [nN])
        echo ""
        echo "📋 测试环境已准备好，您可以手动运行测试"
        echo ""
        echo "测试账号:"
        echo "  管理员: admin / admin123"
        echo "  裁判1:  judge1 / judge123"
        echo "  观众:   viewer / viewer123"
        echo ""
        ;;
    *)
        echo "无效选项，跳过"
        ;;
esac

echo ""
echo "=================================================="
echo "  测试完成"
echo "=================================================="
echo ""
