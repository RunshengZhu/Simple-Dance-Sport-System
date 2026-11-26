# 体育舞蹈赛事评分系统 · 服务版

局域网/公网 Web 评分服务（FastAPI + Jinja2 + SQLite WAL + SSE）。
算法内核为仓库根的 `core/`（纯标准库，与桌面版逐位等价）；本包初始化时自动把仓库根
加入 `sys.path`，`run.py` / `python -m server.seed` / `uvicorn server.app:app` 均可直接启动。
本地版桌面软件见仓库根 `desktop/`，共享内核说明见仓库根 `README.md`。

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

三层测试体系（详见 `docs/CI.md`），全部对临时库运行、不碰生产数据：

```bash
# L1：单测 + ASGI 层 API（最快）
python -m pytest -q

# L2：真实 HTTP 全链路·角色动线 A–H（临时库自起服；含 comp21 事故回归 + doctor 体检）
bash webapp/tools/ci.sh

# L3：纯 WebUI 固化动线（Playwright 真实浏览器按角色点击；自起临时库）
pip install -r requirements-ui.txt && python -m playwright install chromium
python -m pytest tests-ui -q
```

覆盖：登录/越权、导入校验、开场检录、三制评分（Mark/顺位/评分制）、收齐自动计算、
发布/撤回可见性、晋级互斥回填、公开端与大屏、打印/证书管线、恢复与 reset 加固，
以及手机端关键布局。

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
