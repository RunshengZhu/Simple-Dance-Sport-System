# 注意：不写 "# syntax=docker/dockerfile:1" 指令——该指令会让每次构建都去拉取
# docker/dockerfile 前端镜像，在受限网络（如大陆）会直接失败；本文件只用了
# BuildKit 内置前端就支持的基础指令，不写反而更稳。
FROM python:3.11-slim

WORKDIR /app

# 只拷贝运行时需要的代码（tools/docs/desktop/tests 不进镜像，见 .dockerignore）：
#   webapp/server -> /app/server  服务包（含 static 前端资源、templates 模板、seed 演示数据）
#   core          -> /app/core    共享评分内核，与 server 同在 /app 下，可直接 import
#   webapp/run.py -> /app/run.py  启动入口备用（容器实际用下方 CMD 的 uvicorn 启动）
COPY webapp/server /app/server
COPY core /app/core
COPY webapp/run.py /app/run.py

# 运行时依赖仅此三项（应用不依赖 python-multipart）
RUN pip install --no-cache-dir fastapi uvicorn jinja2

ENV DSPORT_PORT=8321 \
    DSPORT_DB=/app/data/dancesport.db \
    DSPORT_FILES_DIR=/app/data/files \
    # server 包初始化时会自动把“仓库根”加进 sys.path；容器内代码平铺在 /app，
    # 用 PYTHONPATH 兜底，保证任何启动方式（uvicorn / python -m server.seed）都能 import server 与 core
    PYTHONPATH=/app

# SQLite 数据库与上传的托管文件全部落在 /app/data，必须挂卷持久化
VOLUME /app/data
EXPOSE 8321

# 硬约束：--workers 必须为 1，不可调大。
# SSE 实时广播、公开页渲染缓存、大屏控制均为单进程内存态，
# 多 worker 会导致实时推送丢失与控制失灵。
# --proxy-headers --forwarded-allow-ips="*"：信任反代（Caddy）传来的 X-Forwarded-* 头，
# 登录防爆破才能按真实客户端 IP 记账；8321 只在 compose 内网暴露，不映射公网端口。
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8321", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*"]
