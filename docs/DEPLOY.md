# 部署指南（Docker + HTTPS）

本指南面向**零部署经验**的使用者，目标是把体育舞蹈评分系统以 Docker + 自动 HTTPS 的方式部署到一台服务器上。全程只需要复制粘贴命令和修改一个配置文件。

---

## 1. 前置条件

### 1.1 一台服务器

- **推荐大陆以外的服务器**（如香港、新加坡、美国等地区的云主机）：域名**免备案**，开通即可用。
- 若用大陆服务器，域名必须**已完成 ICP 备案**，否则 80/443 会被拦截。
- 配置要求不高：1 核 2GB 内存、20GB 磁盘即可运行本系统。
- 操作系统建议 Ubuntu 22.04 / Debian 12（其他 Linux 亦可）。

### 1.2 一个域名

- 在任意域名服务商购买域名，添加一条 **A 记录**指向服务器公网 IP。
  - 例：域名 `ds.example.com`，在 DNS 控制台添加记录类型 `A`、主机记录 `@`（或 `ds` 等子域名前缀）、记录值填服务器 IP。
  - 解析生效通常几分钟到半小时不等（可用 `ping 你的域名` 验证是否已指向服务器 IP）。

### 1.3 放行端口

在云服务商的**安全组 / 防火墙**中放行：

| 端口 | 用途 |
| --- | --- |
| 80 | HTTP（证书申请与跳转 HTTPS） |
| 443 | HTTPS（实际服务入口） |

> 其余端口一律不用放行。应用本身监听的 8321 端口只在 Docker 内部网络使用，**不对外暴露**。

### 1.4 安装 Docker

在服务器上执行（Ubuntu/Debian 通用官方脚本）：

```bash
curl -fsSL https://get.docker.com | sh
```

安装完成后验证：

```bash
docker --version          # 应显示 20.10 以上版本
docker compose version    # 应显示 v2.x
```

---

## 2. 部署步骤

### 2.1 获取代码

```bash
git clone <仓库地址>
cd dancesport
```

### 2.2 配置 .env

```bash
cp .env.example .env
nano .env    # 不熟悉 nano 可用 vi 或其他编辑器
```

需要修改的内容：

```ini
SITE_DOMAIN=ds.example.com          # 改成你的真实域名（不带 https:// 前缀）
DSPORT_ADMIN_PASSWORD=change-me     # 管理员口令，务必改成强口令
DSPORT_HOST_PASSWORD=change-me      # 主持人（控台）口令
DSPORT_MARSHAL_PASSWORD=change-me   # 检录员口令
```

> **重要**：程序对三种角色有内置的默认口令（admin123 / host123 / marshal123）。`.env` 中的三个口令会**覆盖**默认值，生产环境必须全部改成自己的强口令。

### 2.3 启动

```bash
docker compose up -d
```

首次启动时：

1. Docker 自动构建应用镜像（联网下载依赖，约 1~3 分钟）；
2. Caddy 自动向 Let's Encrypt **申请 HTTPS 证书**（免费、自动续期）。

证书签发的前提：域名解析已生效、80/443 均可达。之后浏览器访问：

```
https://你的域名
```

看到系统页面即部署成功。

常用查看命令：

```bash
docker compose ps          # 查看两个容器是否都是 running
docker compose logs -f     # 实时查看日志（Ctrl+C 退出）
```

---

## 3. 必读约束（请勿违反）

### 3.1 uvicorn 必须单 worker（workers=1）

镜像中的启动命令已固定 `--workers 1`，**这是硬约束，任何情况下不要改成多 worker**：

- SSE 实时推送（评委打分、大屏刷新）依赖**进程内存中的广播连接表**；
- 公开页的渲染缓存、大屏控制状态同样保存在**单进程内存**中；
- 多 worker 会把这些状态拆散到多个进程，直接导致**实时推送丢失、大屏控制失灵**。

单 worker 不影响并发能力：Python 异步（uvicorn）本身就能同时处理大量长连接，评分系统的规模下绰绰有余。

### 3.2 不要绕过 compose 直接把 8321 暴露到公网

- 8321 是**明文 HTTP**，直接暴露意味着口令和成绩数据明文传输；
- 绕过 Caddy 还会让应用拿不到代理头（见第 8 节），登录防爆破会按错误来源记账；
- 正确做法只有一个入口：**80/443 → Caddy → 容器内网 8321**。

---

## 4. 初始化演示数据（可选）

如需一套演示赛事（选手、裁判、场次 CSV）用于熟悉系统：

```bash
docker compose exec app python -m server.seed
```

- 该命令**幂等**：演示赛事「演示测试赛」已存在时会自动跳过，可放心重复执行。
- 管理员口令来自 `.env` 的 `DSPORT_ADMIN_PASSWORD`。

---

## 5. 备份

所有业务数据（SQLite 数据库 + 上传的托管文件）都在数据卷 `/app/data` 中。备份命令：

```bash
docker compose exec app tar czf - /app/data > backup-$(date +%F).tar.gz
```

会在当前目录生成如 `backup-2026-09-13.tar.gz` 的备份文件，下载到本地保存即可。

**建议每天自动备份**（cron）。在服务器上执行 `crontab -e`，加一行（每天 03:00 备份到 `/root/backups`）：

```cron
0 3 * * * cd /root/dancesport && docker compose exec app tar czf - /app/data > /root/backups/backup-$(date +\%F).tar.gz
```

> 提示：运行中的 SQLite 使用 WAL 模式，热备文件可用但非最严谨；对一致性要求极高时，选择低峰期先 `docker compose stop app`、改用 `docker run --rm -v <项目名>_app-data:/app/data:ro alpine tar czf - /app/data > 备份文件` 冷备后再 `docker compose start app`。

---

## 6. 升级

```bash
git pull
docker compose build
docker compose up -d
```

- 数据存在命名卷中，升级**不会丢失**任何数据；
- 升级过程有几十秒服务中断，建议在赛事开始前完成；
- 如需回退：`git checkout <旧版本标签或提交>` 后重复 build / up 即可。

---

## 7. 故障排查

| 现象 | 原因与处理 |
| --- | --- |
| 页面/大屏更新卡顿、SSE 不实时 | 多为反代缓冲所致。确认 `Caddyfile` 中 `flush_interval -1` 未被删改，然后 `docker compose restart caddy`。 |
| 大文件上传报 413 | 请求体超过上限。Caddy 侧上限在 `Caddyfile` 的 `request_body max_size 256MB`（应用层上限 200MB，`DSPORT_MAX_UPLOAD_MB` 可调）；如需更大，两处都要核对。 |
| 登录返回 429 | 防爆破已触发：**同一 IP 在 60 秒窗口内失败 5 次即锁定**。等待 60 秒后再试，或换网络；口令忘记可改 `.env` 后 `docker compose up -d` 重启生效。 |
| 证书未签发、浏览器提示不安全 | 检查域名解析是否已生效、80/443 是否放行，再看 `docker compose logs caddy` 中的报错。 |
| 容器起不来 | `docker compose logs -f app` 查看原因；最常见是 `.env` 缺失（`cp .env.example .env`）或 SITE_DOMAIN 未填。 |

---

## 8. 代理头说明（为什么这样是安全的）

应用容器启动命令带：

```
--proxy-headers --forwarded-allow-ips="*"
```

含义与安全性：

- uvicorn 会信任反向代理传来的 `X-Forwarded-For` / `X-Forwarded-Proto` 头，从而拿到**访客的真实 IP**（登录防爆破按真实 IP 记账）和真实协议（HTTPS）；
- `--forwarded-allow-ips="*"` 表示"信任所有连接方"，看似宽泛，但因为 8321 **只在 Docker 内部网络暴露、没有映射公网端口**，能连上 8321 的只有同一 compose 网络里的 Caddy——即"仅容器内网可信"；
- 若你自行更换反代（如 nginx），必须同样传递 `X-Forwarded-For` 等头，并遵守第 3 节约束。
