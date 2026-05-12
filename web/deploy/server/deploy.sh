#!/bin/bash
# 体育舞蹈赛事评分系统 - 一键部署脚本
# 适用于：Ubuntu 22.04 + SQLite
# 支持：11个裁判同时打分

set -e

echo "========================================="
echo "体育舞蹈赛事评分系统"
echo "一键部署脚本"
echo "========================================="

# 检查root
if [ "$EUID" -ne 0 ]; then
    echo "请使用sudo运行: sudo bash deploy.sh"
    exit 1
fi

# 1. 更新系统
echo "[1/6] 更新系统..."
apt update && apt upgrade -y

# 2. 安装Docker
echo "[2/6] 安装Docker..."
apt install -y apt-transport-https ca-certificates curl software-properties-common git

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl start docker
systemctl enable docker

# 3. 创建项目目录
echo "[3/6] 创建项目目录..."
mkdir -p /opt/dancesport/{backend,frontend,data,ssl}
cd /opt/dancesport

# 4. 创建docker-compose.yml
echo "[4/6] 创建Docker配置..."

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
      - ./data:/app/data
      - ./backend:/app
    environment:
      - DATABASE_URL=sqlite:///./data/dancesport.db
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

    client_max_body_size 100M;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
        index index.html;
    }

    location /api/ {
        proxy_pass http://dancesport-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
EOF

# 6. 创建后端Dockerfile
echo "[6/6] 创建后端Dockerfile..."

cat > /opt/dancesport/backend/Dockerfile << 'EOF'
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat > /opt/dancesport/backend/requirements.txt << 'EOF'
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
aiosqlite==0.19.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
aiofiles==23.2.1
pydantic-settings==2.1.0
EOF

echo ""
echo "========================================="
echo "Docker配置创建完成！"
echo "========================================="
echo ""
echo "下一步操作："
echo "1. 上传后端代码到 /opt/dancesport/backend/"
echo "2. 上传前端代码到 /opt/dancesport/frontend/"
echo "3. 执行构建和启动"
echo ""
