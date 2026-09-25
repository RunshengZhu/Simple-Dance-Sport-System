# CI 说明

## CI 做什么

流水线定义在 `.github/workflows/ci.yml`,包含两个 job,均跑在 ubuntu-latest + Python 3.11:

| Job | 内容 |
| --- | --- |
| **test** | 按 `requirements.txt` 锁定组合安装依赖(fastapi / starlette / uvicorn / jinja2 / httpx / pytest),然后全量跑 `python -m pytest -q`(当前 130 项)。 |
| **lint** | `python -m compileall webapp/server core`,秒级语法层检查,不做风格 lint。 |

触发时机:push 到 `main` 或 `feat/*` 分支,以及所有 pull request。

几个设计要点:

- **无需浏览器、无需外部网络**:webapp 测试经 httpx `ASGITransport` 直连 ASGI app,不起真实服务;playwright E2E 只在本地手动跑,不在 CI 必装层。
- **不安装 pandas/appdirs/reportlab**:core 测试以 `desktop/src` 为算法对照基准,`tests/conftest.py` 对缺失的重依赖提供垫片(真实包存在时优先用真实包),CI 环境直接走垫片路径,已实测通过。`desktop/src` 源码由 `actions/checkout` 随全仓库一并拉取。
- **httpx 锁 0.28.x**:starlette 内置 TestClient 与 httpx>=0.28 不兼容,但本仓库测试不依赖 TestClient,锁定当前实测可用组合即可;若未来恢复使用 TestClient,需把 httpx 降到 0.27.*。

## 怎么看结果

1. 打开仓库 GitHub 页面的 **Actions** 标签页,按分支或 commit 找到对应 run。
2. 绿色勾 = test 与 lint 两个 job 全部通过;红色叉 = 至少一个 job 失败。
3. 点进失败的 run → 点 job 名 → 展开红色步骤看日志。测试失败会打印 pytest 的 `FAILED`/`ERROR` 明细;编译失败会打印 `SyntaxError` 所在文件与行号。
4. PR 页面底部也会显示 CI 检查状态,失败时会在合并前看到提示。

## 本地等效命令

在仓库根目录执行:

```bash
# 等效 CI test job 的依赖安装(一次性)
python3 -m pip install -r requirements.txt

# 等效 CI test job 的测试步骤
python3 -m pytest -q

# 等效 CI lint job
python3 -m compileall webapp/server core
```

playwright E2E(CI 之外,手动):

```bash
pip install playwright && python3 -m playwright install chromium
```
