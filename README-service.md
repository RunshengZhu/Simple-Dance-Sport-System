# 体育舞蹈赛事评分系统 · 服务版

局域网 Web 评分服务（FastAPI + Jinja2 + SQLite WAL + SSE），算法内核为 `core/`（纯标准库，与桌面版逐位等价）。

## 运行环境

- Python 3.9+，依赖：`fastapi` `uvicorn` `jinja2`（无 python-multipart 需求，CSV 以原始文本上传）
- 端口默认 **8321**（`DSPORT_PORT` 可改）
- 管理员口令默认 `admin123`（**生产必须**用 `DSPORT_ADMIN_PASSWORD` 覆盖）

## 本地启动（生产方式）

```bash
# 使用任一含 fastapi/uvicorn/jinja2 的解释器，例如：
VENV=/path/to/venv  # 需 fastapi uvicorn jinja2
$VENV/bin/python -m server.seed        # 可选：写入演示种子赛事
$VENV/bin/python run.py                # 监听 0.0.0.0:8321
```

数据文件：`data/dancesport.db`（SQLite WAL；备份 API 会另存 `*.backup-时间戳`）。

## 页面

| 路径 | 角色 |
|------|------|
| `/login` | 管理员（口令）/ 裁判（裁判 ID） |
| `/events` · `/events/{id}/import` · `/events/{id}/schedule` · `/events/{id}/console/{ceid}` · `/events/{id}/results` | 管理员 |
| `/judge`（→ `/judge/competition-events/{ceid}/dances/{dance}`） | 裁判（移动优先） |
| `/public/schedule` · `/public/results` · `/screen` | 公开（大屏自动轮播：进行中→成绩→欢迎） |

## CSV 格式（UTF-8）

- 选手：`背番号,项目编号,姓名,学校/单位`
- 裁判：`裁判ID,姓名`
- 赛程：`场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手`
  - 评分类型 `SKATING`/`MARK`；舞种多支用逗号分隔；参赛选手仅第 1 轮填写，逗号分隔

## 测试

```bash
# 1) core 等价性测试（pytest 环境）
python -m pytest            # 74 passed（对照 src/ 桌面实现）

# 2) 服务端 E2E 冒烟（需服务已启动、全新 DB）
rm -rf data && python run.py &      # 另一终端
python server/selftest.py           # 31 项：登录/越权/导入/开场/评分/自动计算/发布/晋级回填/导出/备份
```

E2E 覆盖：登录（含错误口令、非法裁判 ID）、未登录越权、导入校验、开场、双端评分提交、重复名次拒绝、收齐自动计算、结果与桌面版口径对照、发布/撤回与公开可见性、明细权限隔离、晋级预案与下一轮回填、Markdown/打印 HTML 导出、备份。

## 部署（Linux 服务器，1.6G RAM 可用）

目标目录 `~/dancesport-service`（勿动现有 `~/dancesport`）。任选其一：

**A. systemd user service**（推荐）
```ini
# ~/.config/systemd/user/dancesport.service
[Unit]
Description=DanceSport Service
After=network.target
[Service]
WorkingDirectory=%h/dancesport-service
Environment=DSPORT_PORT=8321
Environment=DSPORT_ADMIN_PASSWORD=change-me
ExecStart=%h/dancesport-service/venv/bin/python run.py
Restart=always
[Install]
WantedBy=default.target
```
```bash
systemctl --user enable --now dancesport
loginctl enable-linger $USER   # 退出登录后保活
```

**B. nohup + 重试脚本**
```bash
while true; do venv/bin/python run.py; sleep 3; done   # 经 nohup 启动
```

备份：`POST /api/backup`（管理员会话），或 cron `sqlite3 data/dancesport.db ".backup ..."`。

安全基线（外网暴露时）：修改默认口令、登录接口已带失败限速（5 次/分锁定）、公开页只读、建议前置 Nginx/Caddy 加 HTTPS（SSE 需关闭代理缓冲：`proxy_buffering off` / `flush_interval -1`）。
