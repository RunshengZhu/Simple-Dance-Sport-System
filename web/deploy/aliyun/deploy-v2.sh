#!/bin/bash
# 体育舞蹈赛事评分系统 - 一键部署脚本
# 适用于：Ubuntu 22.04 LTS + PostgreSQL
# 支持：11个裁判同时打分

set -e

echo "========================================="
echo "体育舞蹈赛事评分系统"
echo "一键部署脚本 v2.0"
echo "========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用root权限运行: sudo bash deploy.sh${NC}"
    exit 1
fi

# 获取数据库连接信息
read -p "请输入RDS PostgreSQL连接地址: " DB_HOST
read -p "请输入RDS端口(默认5432): " DB_PORT
DB_PORT=${DB_PORT:-5432}
read -p "请输入数据库名: " DB_NAME
read -p "请输入用户名: " DB_USER
read -sp "请输入密码: " DB_PASSWORD
echo ""

# 1. 更新系统
echo -e "${GREEN}[1/7] 更新系统...${NC}"
apt update && apt upgrade -y

# 2. 安装Docker
echo -e "${GREEN}[2/7] 安装Docker...${NC}"
apt install -y apt-transport-https ca-certificates curl software-properties-common git

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl start docker
systemctl enable docker

# 3. 创建项目目录
echo -e "${GREEN}[3/7] 创建项目目录...${NC}"
mkdir -p /opt/dancesport/{backend,frontend,ssl}
cd /opt/dancesport

# 4. 创建docker-compose.yml
echo -e "${GREEN}[4/7] 创建配置文件...${NC}"

cat > /opt/dancesport/docker-compose.yml << 'EOF'
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: dancesport-backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
    restart: unless-stopped
    command: >
      uvicorn app.main:app 
      --host 0.0.0.0 
      --port 8000 
      --workers 4
      --limit-concurrency 100

  frontend:
    image: nginx:alpine
    container_name: dancesport-frontend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./frontend:/usr/share/nginx/html
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  backend_data:
EOF

# 5. 创建Nginx配置
echo -e "${GREEN}[5/7] 配置Nginx...${NC}"

cat > /opt/dancesport/nginx.conf << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    # 前端静态文件
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
        index index.html;
    }

    # API请求 - 反向代理到后端
    location /api/ {
        proxy_pass http://dancesport-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置 - 支持长时间操作
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        proxy_send_timeout 300s;
        
        # 缓冲设置
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # WebSocket支持（如需要实时通信）
    location /ws/ {
        proxy_pass http://dancesport-backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
EOF

# 6. 复制后端代码
echo -e "${GREEN}[6/7] 准备后端代码...${NC}"
# 注意：您需要先上传backend代码到 /opt/dancesport/backend/

# 7. 复制前端代码
echo -e "${GREEN}[7/7] 准备前端代码...${NC}"
# 注意：您需要先上传frontend代码到 /opt/dancesport/frontend/

# 环境变量
cat > /opt/dancesport/.env << EOF
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
EOF

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}配置文件创建完成！${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${YELLOW}下一步操作：${NC}"
echo ""
echo "1. 上传后端代码:"
echo "   scp -r backend/* root@YOUR_IP:/opt/dancesport/backend/"
echo ""
echo "2. 上传前端代码:"
echo "   scp -r frontend/* root@YOUR_IP:/opt/dancesport/frontend/"
echo ""
echo "3. 上传数据库驱动（如需要）"
echo ""
echo "4. 启动服务:"
echo "   cd /opt/dancesport"
echo "   docker-compose up -d --build"
echo ""
echo "5. 查看日志:"
echo "   docker-compose logs -f"
echo ""
echo -e "${YELLOW}访问地址：http://YOUR_IP${NC}"
echo ""
