# 阿里云ECS部署指南

## 一、购买阿里云ECS

### 选型配置
```
地域：离您最近的区域
实例规格：ecs.e-c1m1.small (1核1G) 或 ecs.e-c1m2.small (1核2G)
操作系统：Ubuntu 22.04 LTS (免费)
存储：默认40GB
带宽：1Mbps 按量付费
购买时长：1年（享折扣）
```

### 必开放端口（安全组）
```
TCP 22    SSH远程连接
TCP 80    HTTP网页访问
TCP 443   HTTPS安全访问
```

---

## 二、SSH连接服务器

购买后在控制台找到公网IP，然后：
```bash
ssh root@您的公网IP
```

---

## 三、运行部署脚本

复制以下命令到服务器执行：

```bash
# 1. 安装必要软件
apt update && apt install -y curl git

# 2. 下载部署包
cd /opt
curl -L https://github.com/您的用户名/Simple-Dance-Sport-System/releases/latest/download/deploy.tar.gz -o deploy.tar.gz
tar -xzf deploy.tar.gz
cd dancesport

# 3. 启动服务
chmod +x deploy.sh
./deploy.sh

# 4. 访问系统
http://您的公网IP
```

---

## 四、配置域名（可选）

如果您有域名，可以配置反向代理和SSL：

```bash
# 安装Nginx和Certbot
apt install -y nginx certbot python3-certbot-nginx

# 获取SSL证书
certbot --nginx -d your-domain.com

# 重启Nginx
systemctl restart nginx
```

---

## 五、常见问题

### Q: 访问不了？
```bash
# 检查安全组是否开放80端口
# 检查Docker是否运行
docker ps
# 查看日志
docker-compose logs
```

### Q: 数据库在哪里？
```bash
# 数据库文件位置
/opt/dancesport/data/dancesport.db
```

### Q: 如何备份数据？
```bash
# 备份数据库
cp /opt/dancesport/data/dancesport.db ./backup_$(date +%Y%m%d).db
```
