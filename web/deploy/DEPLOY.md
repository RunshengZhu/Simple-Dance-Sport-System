# 部署到云服务器

## 前提条件
- 一台有公网IP的云服务器（建议2核4G配置）
- 已安装Docker和Docker Compose

## 快速部署步骤

### 1. 上传代码到服务器
```bash
scp -r ./deploy user@your-server:/home/user/dancesport
```

### 2. SSH登录到服务器
```bash
ssh user@your-server
cd dancesport
```

### 3. 启动服务
```bash
docker-compose up -d
```

### 4. 访问系统
- 前端地址: http://your-server-ip
- API文档: http://your-server-ip:8000/docs

## 默认账号
- 用户名: admin
- 密码: admin123

## 常用命令

### 查看服务状态
```bash
docker-compose ps
```

### 查看日志
```bash
docker-compose logs -f
```

### 停止服务
```bash
docker-compose down
```

### 更新代码后重启
```bash
docker-compose up -d --build
```

## 配置HTTPS（可选但推荐）

### 使用Let's Encrypt免费证书
```bash
# 安装nginx反向代理
docker run -d \
  --name nginx-proxy \
  -p 80:80 \
  -p 443:443 \
  -v /etc/nginx/conf.d \
  -v /etc/letsencrypt \
  --restart=always \
  nginx:latest

# 使用certbot获取证书
certbot --nginx -d your-domain.com
```

## 数据备份

### 备份数据库
```bash
docker exec dancesport-backend cp /app/data/dancesport.db /app/data/backup_$(date +%Y%m%d).db
docker cp dancesport-backend:/app/data/backup_*.db ./backups/
```

### 定时备份（crontab）
```bash
0 2 * * * docker exec dancesport-backend cp /app/data/dancesport.db /app/data/backup_$(date +\%Y\%m\%d).db
```

## 生产环境建议

1. **修改默认密码**
   - 首次登录后立即修改admin密码

2. **配置防火墙**
   ```bash
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```

3. **使用环境变量存储密钥**
   ```bash
   export SECRET_KEY=your-secure-random-key
   ```

4. **配置反向代理和SSL**
   - 使用Nginx作为反向代理
   - 配置Let's Encrypt免费证书

5. **监控服务**
   ```bash
   # 使用Portainer管理容器
   docker volume create portainer_data
   docker run -d -p 9000:9000 -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer
   ```
