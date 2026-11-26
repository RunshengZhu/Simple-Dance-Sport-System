# CI 与测试体系（R150 三层结构）

## 总览

```
L1  tests/                  pytest 单测 + ASGI 层 API 测试（最快，~2min）
L2  webapp/tools/ci_suite.py 真实 HTTP 全链路·角色动线 A–H（CI: release-gate job，~1min）
L3  tests-ui/               Playwright 纯 WebUI 固化动线（CI: webui job，~1.5min）
```

三个 job 互相独立、并行执行；全绿才算通过。流水线定义在 `.github/workflows/ci.yml`，
均跑在 ubuntu-latest + Python 3.11。触发时机：push 到 `main` / `feat/*`，以及所有 PR。

**数据安全**：L2/L3 都对「自己起的临时库服务器」运行（mktemp + 空闲端口），与生产数据
完全隔离；tests-ui 另有硬护栏——`DSPORT_UI_BASE` 指向非本机地址时直接拒绝运行
（除非显式 `DSPORT_UI_ALLOW_REMOTE=1`）。

## 角色 × 动线覆盖矩阵

| 动线 | L2 ci_suite（HTTP 全链路） | L3 tests-ui（真实浏览器） |
| --- | --- | --- |
| A 筹备（管理员） | 建赛/激活/三类导入/坏 CSV 拒绝/排班/越权 401·403 | 超管登录→建赛→向导导入→生成赛程→总表行展开→开场 |
| B 检录·主持 | host/marshal 登录、外项背号拒绝、批量检录 | 默认「待检录」视图、当前场次条定位、场次索引、芯片检录、开赛、播报 |
| C 裁判（J1–J3） | 登录、assignments、未收齐不自动算分、收齐即算、明细权限 | 工作台过滤+快速横幅、Mark 点选提交、顺位法顺序点选、评分制输入 |
| D 发布（管理员） | 发布/撤回可见性、控制台、明细口径、导出 | 结果中心折叠卡、一键发布待发布 |
| E 晋级 | 分场互斥/回填/lookup、重复名次拒绝 | 晋级页默认落点=待确认轮、勾选确认回填 |
| F 公众 | 公开 API、团体总分独立复算对拍、SSE 具名事件 | 首页状态条/分区锚点/行展开/成绩查询、大屏锁定场次+去内部编号 |
| G 打印·证书（printer） | 打印台、合并打印视图、generate-v2 真实 PDF | 打印台勾选→合并打印弹窗 |
| H 恢复·体检 | return-scores 演练、doctor 不变量、reset 加固 | —（HTTP 层覆盖） |
| 手机端 390px | — | 总览步骤 Tab 单行、评分页首屏 <400px、芯片触点 |

回归基线：comp21（2026-09 事故）五项修复全部固化为 L1 `tests/test_release_gate.py`
与 L2 动线 B/E/H 中的断言；R148/R149 人工走查确认的交互（提交后引导、折叠卡、
当前场次条、手机布局等）固化为 L3。

## 怎么看结果

1. 仓库 GitHub 页面 **Actions** 标签页，按分支或 commit 找到 run。
2. 绿勾 = test / lint / release-gate / webui 四个 job 全部通过。
3. 失败时点进 run → job → 红色步骤看日志；L2 会打印按动线分组的失败清单。

## 本地等效命令

```bash
# 依赖（一次性）
python3 -m pip install -r requirements.txt pytest

# L1：单测 + API 层（秒级~2min）
python3 -m pytest -q

# L2：真实 HTTP 全链路（临时库自起服，~1min）
bash webapp/tools/ci.sh

# L3：纯 WebUI 动线（自起临时库 + Chromium，~1min）
python3 -m pip install -r requirements-ui.txt
python3 -m playwright install chromium
python3 -m pytest tests-ui -q

# lint
python3 -m compileall webapp/server core
```

测试代码约定：

- 「API 造赛」配方（登录→建赛→导入→开赛→检录→评分→发布→晋级）唯一实现在
  `tests/api_harness.py`（L1/L3 共用其数据集与流程函数）；L2 因无第三方依赖约束
  在 `ci_suite.py` 内自带 stdlib 实现。
- L2 新增检查请按动线挂到 `sec_a`…`sec_h` 对应小节，并在 commit message 注明覆盖的动线。
- L3 新增动线 = 新增 `tests-ui/test_<角色>_<动线>.py`，选择器只依赖模板中稳定的
  id/data 属性；页面不得有 JS 异常（conftest 统一收集断言）。

## 历史脚本说明

R38–R148 期间的一次性 walk/smoke/rehearsal 脚本（约 24 个，多数指向生产环境）已于
R150 清理，其有效断言分别并入 L1/L2/L3；需要追溯时查 git 历史。保留的非 CI 工具：
`doctor.py`（生产只读体检）、`load_test_*.py`（压测）、`build_*.py`（数据构造）、
`manual_*.py` / `shoot_r59_slides.py`（手册截图）、`gen_training_slides*`（培训物料）。

## 设计要点（L1）

- **无需外部网络**：webapp 测试经 httpx `ASGITransport` 直连 ASGI app。
- **不安装 pandas/appdirs/reportlab**：core 测试以 `desktop/src` 为对照基准，
  `tests/conftest.py` 提供垫片（真实包存在时优先用真实包）。
- **httpx 锁 0.28.x**：starlette 内置 TestClient 与 httpx>=0.28 不兼容，本仓库测试
  不依赖 TestClient；若未来恢复使用 TestClient，需把 httpx 降到 0.27.*。
