# Simple Dance Sport System · 体育舞蹈赛事评分系统

同一套体育舞蹈赛事评分业务的两种形态，共享同一算法内核 `core/`（纯标准库，两版结果逐位等价）：

| 目录 | 形态 | 适用场景 | 技术栈 |
|------|------|----------|--------|
| [`desktop/`](desktop/) | 本地版赛事打分软件（单机桌面） | 单机评审、离线赛场、Windows/macOS 双击即用 | Python Tkinter + pandas |
| [`webapp/`](webapp/) | 线上打分系统（多端 Web 服务） | 多裁判移动端评分、检录/主持台、观众查询、大屏轮播 | FastAPI + Jinja2 + SQLite WAL + SSE |

## 目录结构

```
Simple-Dance-Sport-System/
├── core/        # 共享算法内核：顺位法(Skating)/Mark制/评分制、晋级、团体总分（纯标准库）
├── tests/       # 内核测试：以桌面版 src/ 算法为对照基准逐位验证（pytest 从仓库根运行）
├── desktop/     # 本地版：main.py 启动，src/ 桌面 UI 与算法，build_app.py 打包
└── webapp/      # 服务版：run.py 启动，server/ Web 应用，tools/ E2E 与截图脚本，docs/ 设计文档
```

## 快速开始

### 本地版（desktop/）

```bash
cd desktop
pip install -r requirements.txt
python main.py            # 启动桌面软件
python build_app.py       # PyInstaller 打包（见 build_readme.md）
```

详见 [desktop/README.md](desktop/README.md)。

### 线上打分系统（webapp/）

```bash
cd webapp
python -m server.seed     # 可选：写入演示种子赛事
python run.py             # 监听 0.0.0.0:8321（DSPORT_PORT 可改）
```

- 访问 `http://<主机>:8321/login`：管理员（口令，默认 `admin123`，生产必须用
  `DSPORT_ADMIN_PASSWORD` 等环境变量覆盖）、裁判（裁判 ID）、主持人/检录员（用户名+口令）
- 公开页无需登录：`/public/schedule`、`/public/results`、`/screen`（大屏自动轮播）
- 数据文件：`webapp/data/dancesport.db`（SQLite WAL）

详见 [webapp/README.md](webapp/README.md) 与 [webapp/docs/](webapp/docs/)（设计/需求/走查手册）。

### 运行测试（仓库根）

```bash
python -m pytest          # 内核测试（core/ 为被测对象，desktop/src 为对照基准）
```

## 部署提示

- 服务版生产部署：口令用 `DSPORT_ADMIN_PASSWORD` / `DSPORT_HOST_PASSWORD` /
  `DSPORT_MARSHAL_PASSWORD` 环境变量覆盖默认值；`webapp/tools/manual_shots.py` 等工具
  同样从环境变量读取凭据。
- `core/` 位于仓库根：webapp 的 `server` 包初始化时会自动把仓库根加入 `sys.path`，
  `run.py`、`python -m server.seed`、`uvicorn server.app:app` 三种启动方式均无需手动设置 PYTHONPATH。
