#!/bin/bash
# 重启服务器上的服务

echo "🔄 连接到服务器并重启服务..."
ssh sport-coder@59.110.90.21 << 'ENDSSH'
  echo "📦 检查Docker容器状态..."
  docker ps -a | grep dancesport
  
  echo "🛑 停止现有容器..."
  cd ~/dance-sport-system/web/deploy/aliyun
  docker-compose down 2>/dev/null || true
  
  echo "🚀 启动服务..."
  docker-compose up -d
  
  echo "⏳ 等待服务启动..."
  sleep 5
  
  echo "📊 检查服务状态..."
  docker ps | grep dancesport
  
  echo "🌐 测试HTTP访问..."
  curl -s -o /dev/null -w "HTTP状态码: %{http_code}\n" http://localhost:80 || echo "服务可能还在启动中"
  
  echo "✅ 服务重启完成"
ENDSSH

if [ $? -eq 0 ]; then
  echo "✅ 服务器服务重启成功"
else
  echo "❌ SSH连接失败或服务重启失败"
fi
