#!/bin/bash
# 阿里云ECS服务器 - 一键部署脚本
# 适用于 Ubuntu 22.04 LTS

set -e

echo "========================================="
echo "体育舞蹈赛事评分系统 - 部署脚本"
echo "========================================="

# 1. 更新系统
echo "[1/6] 更新系统..."
apt update && apt upgrade -y

# 2. 安装Docker
echo "[2/6] 安装Docker..."
apt install -y apt-transport-https ca-certificates curl software-properties-common

# 添加Docker官方GPG密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 添加Docker仓库
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动Docker
systemctl start docker
systemctl enable docker

# 3. 创建项目目录
echo "[3/6] 创建项目目录..."
mkdir -p /opt/dancesport
cd /opt/dancesport

# 4. 创建docker-compose.yml
echo "[4/6] 创建配置文件..."

cat > /opt/dancesport/docker-compose.yml << 'EOF'
version: '3.8'

services:
  backend:
    image: python:3.12-slim
    container_name: dancesport-backend
    ports:
      - "8000:8000"
    working_dir: /app
    volumes:
      - ./data:/app/data
      - ./backend:/app
    command: >
      sh -c "pip install fastapi uvicorn sqlalchemy aiosqlite python-jose passlib python-multipart aiofiles pydantic-settings && 
             uvicorn app.main:app --host 0.0.0.0 --port 8000"
    restart: unless-stopped
    environment:
      - DATABASE_URL=sqlite:///./data/dancesport.db

  frontend:
    image: nginx:alpine
    container_name: dancesport-frontend
    ports:
      - "80:80"
    volumes:
      - ./frontend:/usr/share/nginx/html
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  data:
EOF

# 5. 创建Nginx配置
echo "[5/6] 配置Nginx..."

cat > /opt/dancesport/nginx.conf << 'EOF'
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # 前端静态文件
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API代理
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

# 6. 创建前端目录并下载构建文件
echo "[6/6] 下载前端文件..."
mkdir -p /opt/dancesport/frontend

# 下载构建好的前端（您需要先在本地构建）
# 这里提供占位符，您稍后需要上传构建文件

echo ""
echo "========================================="
echo "基础环境部署完成！"
echo "========================================="
echo ""
echo "下一步操作："
echo "1. 上传前端构建文件到 /opt/dancesport/frontend/"
echo "2. 上传后端代码到 /opt/dancesport/backend/"
echo ""
echo "快速启动："
echo "  cd /opt/dancesport"
echo "  docker-compose up -d"
echo ""
echo "查看日志："
echo "  docker-compose logs -f"
echo ""
