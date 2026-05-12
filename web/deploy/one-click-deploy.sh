#!/bin/bash
# 体育舞蹈赛事评分系统 - 一键部署脚本
# 运行此脚本会自动完成所有部署工作

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查是否为root
if [ "$EUID" -ne 0 ]; then
    log_warn "请使用 sudo 运行此脚本"
    exit 1
fi

log_info "========================================="
log_info "体育舞蹈赛事评分系统 - 自动部署"
log_info "========================================="
echo ""

# 1. 安装Docker
log_info "[1/4] 检查并安装Docker..."
if command -v docker &> /dev/null; then
    log_info "Docker已安装"
else
    log_info "安装Docker..."
    apt update
    apt install -y apt-transport-https ca-certificates curl software-properties-common git
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt update
    apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl start docker
    systemctl enable docker
    log_info "Docker安装完成"
fi

# 2. 创建项目目录
log_info "[2/4] 创建项目目录..."
mkdir -p /opt/dancesport/{backend,frontend,data}
cd /opt/dancesport
log_info "项目目录: /opt/dancesport"

# 3. 下载代码
log_info "[3/4] 下载代码..."
if [ -d "/opt/dancesport/repo" ]; then
    rm -rf /opt/dancesport/repo
fi

git clone https://github.com/RunshengZhu/Simple-Dance-Sport-System.git repo
cp -r repo/web/backend/* backend/
cp -r repo/web/frontend/* frontend/
rm -rf repo
log_info "代码下载完成"

# 4. 创建Docker配置
log_info "[4/4] 配置并启动服务..."

cat > /opt/dancesport/docker-compose.yml << 'EOF'
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1

  frontend:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./frontend:/usr/share/nginx/html
    restart: unless-stopped
EOF

# 启动服务
cd /opt/dancesport
docker-compose up -d --build

# 等待服务启动
log_info "等待服务启动..."
sleep 10

# 检查服务状态
if docker ps | grep -q dancesport; then
    log_info "========================================="
    log_info "🎉 部署成功！"
    log_info "========================================="
    echo ""
    log_info "访问地址: http://$(curl -s ifconfig.me 2>/dev/null || echo '服务器IP')"
    log_info "API地址: http://$(curl -s ifconfig.me 2>/dev/null || echo '服务器IP'):8000"
    echo ""
    log_info "默认账号:"
    log_info "  用户名: admin"
    log_info "  密码: admin123"
    echo ""
    log_info "常用命令:"
    log_info "  查看状态: docker-compose ps"
    log_info "  查看日志: docker-compose logs -f"
    log_info "  停止服务: docker-compose down"
    log_info "  重启服务: docker-compose restart"
else
    log_error "部署可能存在问题，请检查日志: docker-compose logs"
fi
