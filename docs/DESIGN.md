# 体育舞蹈赛事评分系统 · 服务版设计（DESIGN）

> 版本：v0.2.4（GC 解冻实现：Q-R1~R4 拍板落为 D10~D13（REQUIREMENTS §7）；P-1/P-2/P-3 提案不纳入 M1→M5 实现，实现按本文正文执行；历史：v0.2.3 并入用户三点新要求并降级提案，v0.2.1 并入 R-1~R-4，v0.2 落 D1~D9）
> 日期：2026-08-27
> 上游：`docs/REQUIREMENTS.md` v0.2.4；算法内核：worktree `core/`（feat/service-core）；端口定稿 8321
> 说明：全新设计，不参考旧 web 实现结构。部署约束：服务器可从外网访问（对策见 §8「外网暴露对策」）。

---

## 1. 总体架构

```
┌─────────── 局域网 / 外网（受限访问）────────────┐
│  管理员浏览器   裁判手机   大屏/观众（只读）        │
└────────┬───────────┬─────────┬─────┘
         │ HTTP/SSE  │ HTTP    │ SSE
   ┌─────┴───────────┴─────────┴─────┐
   │  可选反向代理（HTTPS 终结，D9）    │
   │        服务进程（单进程）          │
   │  Web 框架 + 模板渲染 + 静态资源    │
   │  应用服务层（编排，无算法改动）      │
   │  core/ 算法内核（纯标准库）        │
   │  SQLite（WAL）  导出文件目录       │
   └─────────────────────────────────┘
```

- 单服务进程、单机部署；SQLite 单文件存储（WAL 模式支撑并发读）。
- 应用服务层调用 `core/` 完成计算；`core/` 零 UI/零第三方依赖，直接 import。
- 服务端渲染页面 + 少量原生 JS；实时用 **SSE**（见 §7）。

## 2. 角色与用户旅程

### 2.1 管理员
1. 登录 → 创建/打开赛事 → **激活赛事**（同一时间至多一个赛事激活运行，D6）→ 上传选手/赛程/裁判 CSV（或打包 zip）→ 系统生成第 1 轮场次。
2. 开场：进入"场次控制台"，选择场次 → 勾选上场选手 → **开启评分**，裁判端随即出现该场次评分表。
3. 监控：实时查看各裁判提交进度（已交/未交矩阵）。
4. 收齐后系统**默认自动计算**（D3）；管理员可手动触发/重算 → 在管理端查看分舞种/综合结果与评分明细（明细不对观众暴露，D5）→ 晋级确认（可手动调整名单）→ 确认 → 下一轮名单自动生成、下一轮场次可开场。
5. 发布结果到大屏/观众页（发布内容不含明细，D5）；决赛后导出综合名次表（打印友好 HTML / Markdown，D8）。
6. 大屏管理：暂停/切换/指定大屏画面（D4）。

### 2.2 裁判
1. 手机浏览器打开服务地址 → 以裁判 ID（+可选口令）登录 → 看到分配给自己的"待评场次"。
2. 管理员开场后，按舞种逐个给选手评分：顺位法下拉/步进器选择 1~N 唯一名次（客户端实时查重）；Mark制为布尔标记（通过/不通过，与 core/ 的 ScoreRecord.mark: Optional[bool] 语义一致，见 REQUIREMENTS §8 Q-R2）。
3. 提交（可多次修改，直到场次关闭）→ 页面显示"已提交，等待开算"；收齐后系统默认自动计算（D3）。

### 2.3 观众
1. 打开观众页/大屏 URL（免登录）：看到赛程、进行中场次、已发布成绩与名次榜，自动刷新。

### 2.4 角色核心动线（用户追加：低复杂度主线的验收基准）

**管理员**（10 步，页面→关键 API）：
1. 创建赛事（或复制上届，FR-J1（提案 P-3））→ `POST /api/events`、`POST /api/events/{eid}/duplicate（提案 P-3）`
2. 导入数据（选手/赛程/裁判/队伍，批量 zip）→ `POST .../imports/*`
3. 排程确认与轮次批量生成 → 赛程总览 → `GET/PATCH .../competition-events`
4. 激活赛事 → `POST /api/events/{eid}/activate`
5. 开场（勾选上场选手）→ `POST .../open`
6. 监控提交进度（实时推送）→ `GET .../progress` + SSE
7. 自动计算（必要时重算）→ `POST .../calculate`
8. 审核结果（结果中心/明细）→ `GET .../results?type=detail`
9. 公示（provisional）→ 正式发布（official）→ `POST .../publish?state=provisional|official（提案 P-2）`
10. 大屏轮播确认 → 大屏控制 → `POST /api/events/{eid}/screen-control`

**裁判**（5 步）：
1. 手机登录 → `/login` → `POST /api/login`
2. 看当前待评场次（实时推送开场）→ `/judge` → `GET /api/judge/me/assignments`
3. 打分（分舞种，顺位/Mark）→ `/judge/.../sheet` → `GET .../sheet`
4. 提交（乐观更新，可改）→ `PUT .../sheet`
5. 看进度与状态 → SSE `score_submitted` 等

**观众**（3 步）：
1. 扫码/点链接进入 → `/public/schedule`
2. 看大屏轮播/查公示与正式成绩 → `/public/results`、`/screen`（API 标注 provisional/official）
3. 查团体总分榜 → `/public/team-standings`

**动线审视结论（FR-J1/J2 轻量方案）**：
- 赛事/项目添加：新建赛事提供"复制上届"（提案 P-3，待确认；复制 units/competitors/projects/schedule 结构，不含成绩）；添加项目单页表单一步完成（类型选 couple/formation，formation 自动带出组队入口）；轮次场次按模板批量生成。
- 排程：维持 CSV 模板导入 + 轮次批量生成（已在 M1/M3），不新增拖拽排程等复杂交互。
- UI 适配核对（对照 R-1 策略）：管理页高频操作（开场/公示/发布）集中在场次控制台首屏动作区；裁判页保持单列大按钮触控；公示/正式状态在结果中心与公开页均以徽标显式呈现；动线外功能（口径方案管理、导入模板管理、审计日志、备份）统一收进"管理高级区"（设置页分组），主界面不出现。

## 3. 信息架构与页面清单（含适配策略，R-1）

| 页面 | 路由（草案） | 角色 | 覆盖 FR | 适配策略（R-1） |
|------|--------------|------|---------|-----------------|
| 登录 | `/login` | 全部 | §2 角色准入 | 移动优先（裁判手机登录），双端通用 |
| 赛事管理（列表/创建/复制上届（提案 P-3）/切换/删除/设置/**激活**，D6） | `/events` | 管理员 | FR-A1~A3、FR-G1、FR-J1（提案） | 桌面优先，平板可用 |
| 数据导入（三个上传区 + 批量 zip + 预览校验报告） | `/events/{eid}/import` | 管理员 | FR-B1~B6、FR-G2 | 桌面优先，平板可用 |
| 赛程总览（项目→轮次→场次树，状态标记） | `/events/{eid}/schedule` | 管理员 | FR-C1、FR-D5、FR-H3 | 桌面优先，平板可用 |
| 场次控制台（上场选手管理、开启/关闭/重开、裁判进度矩阵、自动/手动计算与重算、评分退回/作废、结果预览、晋级确认、发布/撤回） | `/events/{eid}/competition-events/{ceid}/console` | 管理员 | FR-C1/C5/C7、FR-D1~D3、FR-E3、FR-G3~G6/G8、FR-H3 | 桌面优先，平板可用 |
| 晋级确认（本轮结果 + 合并名单 + 手动调整） | `/events/{eid}/competition-events/{ceid}/advancement` | 管理员 | FR-D3~D6、FR-G7、FR-H3 | 桌面优先，平板可用 |
| 结果中心（分舞种/综合/名次表 + **评分明细仅此处可见**（D5）；发布三态操作（提案 P-2）；导出：打印友好 HTML/Markdown（D8）；发布/撤回） | `/events/{eid}/results` | 管理员 | FR-E1/E2/E4/E6（提案）、§3.6、FR-G8/G10、FR-H3 | 桌面优先，平板可用 |
| 大屏控制（暂停/切换/指定画面，D4） | `/events/{eid}/screen-control` | 管理员 | FR-F3、FR-G9 | 桌面优先，平板可用 |
| 裁判首页（待评/已评场次列表） | `/judge` | 裁判 | FR-C1、FR-H2 | 移动优先 |
| 裁判评分表（分舞种打分、提交/修改） | `/judge/events/{eid2}/dances/{dance}` | 裁判 | FR-C2/C3/C4/C5、FR-H2 | 移动优先（手机竖屏触控） |
| 观众赛程页 | `/public/schedule` | 公开 | FR-F1 | 自适应（手机/桌面通用） |
| 观众成绩页（名次榜） | `/public/results` | 公开 | FR-E5、FR-E3、FR-F1 | 自适应（手机/桌面通用） |
| 大屏页（轮播：进行中/名次榜/**团体总分榜**；默认自动轮播、内容跟随赛程，受管理员控制 D4） | `/screen` | 公开 | FR-F1/F2/F3、FR-I7 | 专为横屏大屏设计（1920×1080 基准，等比缩放） |
| 单位与队伍管理（单位列表、集体队伍组队/队员、同单位校验状态） | `/events/{eid}/teams` | 管理员 | FR-I1~I4 | 桌面优先，平板可用 |
| 团体总分榜（口径方案切换与即时重算（提案 P-1，收进高级区）/分组别积分/发布） | `/events/{eid}/team-standings` | 管理员 | FR-I6/I7/I8（提案）、FR-G8 | 桌面优先，平板可用 |
| 观众团体总分页 | `/public/team-standings` | 公开 | FR-I7 | 自适应 |

## 4. API 资源模型草案（REST，JSON）

```
POST   /api/login                                  # 管理员口令/裁判ID 换会话 cookie          [§2]
GET    /api/events                                 # 赛事列表                                 [FR-A2]
POST   /api/events                                 # 创建赛事                                 [FR-A1]
POST   /api/events/{eid}/duplicate                 # 复制上届赛事结构（提案 P-3，FR-J1）      [FR-J1（提案）]
DELETE /api/events/{eid}                           #                                          [FR-A3]
POST   /api/events/{eid}/open                      # 设为当前赛事                             [FR-A2]
POST   /api/events/{eid}/activate                  # 激活赛事（同时仅一个激活，D6）           [FR-A2]

POST   /api/events/{eid}/imports/competitors       # 上传 CSV/Excel                           [FR-B1]
POST   /api/events/{eid}/imports/schedule          #                                          [FR-B2]
POST   /api/events/{eid}/imports/judges            #                                          [FR-B3]
POST   /api/events/{eid}/imports/batch             # zip 批量                                 [FR-B4]
GET    /api/events/{eid}/imports/{imp_id}/report   # 导入校验报告                             [FR-B6]
                                             # （导入成功自动生成第1轮场次＝FR-B5 的实现副作用）

GET    /api/events/{eid}/projects                  # 项目列表                                 [§3.3]
GET    /api/events/{eid}/competitors?project=      #                                          [FR-B1]
GET    /api/events/{eid}/judges                    #                                          [FR-B3]

# 单位 / 集体队伍 / 团体总分（FR-I1~I7）
GET    /api/events/{eid}/units                     # 单位列表                                 [FR-I2]
GET    /api/events/{eid}/teams?project=            # 集体队伍（含队员、单位；校验状态）       [FR-I2、FR-I4]
POST   /api/events/{eid}/teams                     # 新建队伍（服务端强制"一队一单位"校验）   [FR-I4]
PATCH  /api/events/{eid}/teams/{tid}               # 调整队员/队名（触发同单位重校验）        [FR-I2、FR-I4]
POST   /api/events/{eid}/imports/teams             # 队伍名单导入（含同单位校验报告）         [FR-I2、FR-I4、FR-B6]
GET    /api/events/{eid}/team-standings            # 团体总分榜（管理端含明细口径，D5）       [FR-I6]
GET    /api/public/events/{eid}/team-standings     # 团体总分榜（已发布版，无明细）           [FR-I7]
PUT    /api/events/{eid}/standing-config           # 绑定口径方案（Q-R3/Q-R4 拍板后启用）     [FR-I6]
GET/POST /api/events/{eid}/standing-presets        # 命名口径方案的查询/保存（提案 P-1）      [FR-I8（提案）]
POST   /api/events/{eid}/team-standings/recalculate  # 切换方案后即时重算（提案 P-1，幂等）    [FR-I8（提案）]

GET    /api/events/{eid}/rounds/{round}/competition-events   # 场次列表                       [FR-C1]
PATCH  /api/competition-events/{ceid}              # 状态/上场选手增删/晋级人数（评分中调整
                                                    #  上场名单须二次确认并清空评分）          [FR-C1、FR-G4]
POST   /api/competition-events/{ceid}/open         # 开启评分（body: 上场选手）               [FR-C1、FR-G3]
POST   /api/competition-events/{ceid}/close        #                                          [FR-C6、FR-G3]
POST   /api/competition-events/{ceid}/reopen       # 重开场次（清空已有评分，二次确认）       [FR-G3]
DELETE /api/competition-events/{ceid}/scores/{judge_id}   # 作废某裁判本场评分（审计留痕；作废后
                                                    #  收齐判定不含该裁判直至重交）            [FR-C7、FR-G5]
POST   /api/competition-events/{ceid}/scores/{judge_id}/return   # 退回某裁判评分要求重交     [FR-C5、FR-G5]
GET    /api/competition-events/{ceid}/progress     # 裁判提交进度矩阵                         [FR-C6、§2.1-3]
POST   /api/competition-events/{ceid}/calculate    # 调 core/ 计算（收齐后系统自动调用，D3；
                                                   #  本端点供管理员手动触发/重算）           [FR-D1、FR-D2]
GET    /api/competition-events/{ceid}/results?type=dance|overall|detail   # detail 仅管理端（D5）  [FR-E1]
POST   /api/competition-events/{ceid}/publish?state=provisional|official   # 公示/正式发布（提案 P-2，FR-E6）[FR-E3、FR-G8]
POST   /api/competition-events/{ceid}/unpublish    # 撤回（official→provisional 或 →draft）   [FR-E3/E6、FR-G8]

GET    /api/projects/{pid}/rounds/{round}/advancement-proposal   # 晋级预案                  [FR-D3、FR-D4、FR-D6]
POST   /api/projects/{pid}/rounds/{round}/advancement-confirm    # body: 调整后名单          [FR-D4、FR-D5]

# 裁判
GET    /api/judge/me/assignments                   # 我的待评/已评场次                        [FR-C1]
GET    /api/judge/competition-events/{ceid}/dances/{dance}/sheet   # 我的评分表              [FR-C2/C3/C4]
PUT    /api/judge/competition-events/{ceid}/dances/{dance}/sheet   # 整表提交（原子）        [FR-C2/C3、FR-C5]

# 公开
GET    /api/public/events/{eid}/schedule           #                                          [FR-F1]
GET    /api/public/events/{eid}/results?scope=provisional|official   # 响应带 "state" 标注（提案 P-2/FR-E6）；明细不暴露（D5）  [FR-E3、FR-E5]
GET    /api/public/events/{eid}/screen-state       # 大屏轮播数据（仅 official，含轮播控制状态，D4）  [FR-F1]
POST   /api/events/{eid}/screen-control            # 管理员暂停/切换/指定大屏画面（D4）       [FR-F3]
GET    /api/events/{eid}/stream                    # SSE 事件流（见 §7）                      [FR-F2]

# 导出与备份
POST   /api/events/{eid}/exports                   # body: 范围+格式(html-print/markdown)（D8）[FR-E2]
POST   /api/backup                                 # 触发数据备份（管理端）                   [NFR-6、FR-G10]
```

约定：错误统一 `{code, message(中文)}`；写操作幂等键可选；裁判整表提交保证一次舞种一名次的原子校验在服务端复验（不信任客户端）。`[FR-x]` 为需求追溯标注，对应 REQUIREMENTS.md 编号。作废/退回/撤回/重开等敏感操作均写审计日志（见 §8.3-6）。

### 4.1 管理员控制面清单（R-4，全场全要素控制）

| # | 控制能力 | API | 需求 |
|---|----------|-----|------|
| 1 | 赛事全生命周期管理（创建/打开/激活/删除/设置） | `POST/GET/DELETE /api/events`、`/open`、`/activate` | FR-G1（FR-A1~A3） |
| 2 | 数据导入（选手/赛程/裁判/批量 + 校验报告） | `POST /api/events/{eid}/imports/*`、`GET .../report` | FR-G2（FR-B1~B6） |
| 3 | 场次开场/关闭/重开 | `POST .../open`、`/close`、`/reopen` | FR-G3 |
| 4 | 上场选手增删 | `PATCH /api/competition-events/{ceid}`（body: roster；评分中调整须二次确认并清空评分） | FR-G4 |
| 5 | 评分退回/作废 | `POST .../scores/{judge_id}/return`、`DELETE .../scores/{judge_id}` | FR-G5（FR-C5/C7） |
| 6 | 计算与重算 | `POST .../calculate`（系统收齐后亦自动调用，D3） | FR-G6（FR-C6/D1） |
| 7 | 晋级预案调整 | `GET .../advancement-proposal`、`POST .../advancement-confirm` | FR-G7（FR-D4） |
| 8 | 结果发布/撤回 | `POST .../publish`、`POST .../unpublish` | FR-G8（FR-E3） |
| 9 | 大屏内容强制切换 | `POST /api/events/{eid}/screen-control` | FR-G9（FR-F3） |
| 10 | 数据导出与备份 | `POST /api/events/{eid}/exports`、`POST /api/backup` | FR-G10（FR-E2/NFR-6） |

## 5. 数据模型（对齐 core/ 领域模型）

core/ 的 dataclass 为领域模型基准；服务层以关系表持久化，读写时与 core 模型互转：

| 表 | 关键列 | 对应 core 模型 |
|----|--------|----------------|
| competitions | id, name, date, location | Competition |
| competitors | id, competition_id, number, project_id, name, unit, group | Competitor（+competitor_mapping 语义落为 project_id 列） |
| judges | id, competition_id, judge_code, name | Judge |
| events（场次） | id, competition_id, name, project_id, round, scoring_type, advancement_count, advancement_rule, parent_id, child_id, status | Event（ScoringType/EventStatus 存枚举值字符串） |
| event_dances | event_id, name, ord | Dance |
| event_competitors | event_id, competitor_number | Event.competitors |
| score_records | id, event_id, judge_id, competitor_number, dance_name, score, mark, placement, timestamp, voided(默认false) | ScoreRecord（同名字段直映；voided 为服务层新增，作废评分不参与收齐判定与计算） |
| results | event_id, calculation_time, results_data(JSON) | CompetitionResult（results_data 内含 Result/SkatingScoreDetail 的 to_dict） |
| result_publication（原 published_flags） | id, scope, status(draft/provisional/official), provisional_at, official_at, withdrawn_at, scope_ref | 发布三态（提案 P-2/FR-E6；official 才进大屏，D5 兼容） |
| standing_presets | id, competition_id, name, config(JSON), is_default | 团体总分命名口径方案（提案 P-1/FR-I8） |
| standing_history | id, scope, preset_snapshot(JSON), computed_at, trigger | 重算历史（提案 P-1/FR-I8；配置快照可追溯） |
| users/sessions | 最简账号与会话 | 管理员口令 + 裁判 ID（可配口令），D2 |
| screen_state | event_id, mode(轮播/暂停/指定), target, updated_at | 大屏控制状态（D4） |
| activations | event_id, activated_at | 赛事激活标记（同时仅一个激活，D6） |
| units（单位/俱乐部） | id, competition_id, name, short_name | 单位实体（新增，FR-I2/I4） |
| team_memberships | competitor_id, unit_id, valid_from | 选手↔单位归属（一名选手可因跨单位组对关联多个单位，主归属标记 is_primary） |
| couples | id, project_id, leader_competitor_id, follower_competitor_id, registered_unit_id | 双人组对（新增）：允许 leader/follower 属不同单位（FR-I3）；registered_unit_id 为主报单位 |
| teams（集体队伍） | id, project_id, unit_id(NOT NULL), name, number(队伍背番号) | 集体队伍（新增，FR-I2）：**unit_id 强制非空且全员一致——"一队一单位"约束（FR-I4）** |
| team_members | team_id, competitor_id, is_substitute | 队员名单（含替补，FR-I2） |
| projects 补充列 | type('couple'|'formation'), team_standing_config(JSON) | 项目类型（FR-I1）；团体总分口径配置（Q-R3 拍板后生效） |

约束表达（FR-I3/I4）：
- `teams.unit_id NOT NULL` + 应用层校验"team_members 全员 memberships 均指向同一 unit"，导入/报名时违规即拒绝并列出违规队员（FR-I4）。
- `couples` 不做同单位约束；leader/follower 单位不同即跨单位组合，其团体归属按 Q-R4 拍板口径在聚合模块实现。

要点：
- `score_records` 上建唯一约束 (event_id, dance_name, judge_id, competitor_number)，从存储层杜绝重复评分。
- 顺位法完整性校验复用 core 的 `validate_scores` / `validate_judges_scores`，服务层在提交与计算前双重校验。
- 计算结果整包存 JSON（CompetitionResult.to_dict 形态），大屏/导出直接读，不重复计算。
- **集体项目与 core/ 的衔接（FR-I5）**：队伍整体映射为一个 `competitor_number`（如 "T01"），ScoreRecord/Result 全链路不变——core/ 顺位法、Mark制、晋级规则对"多人队伍"零改动即适用（队伍被视为一个评分对象）；裁判页评分表展示队名+单位而非选手姓名。
- **团体总分不进 core/ 现有算法**：聚合计算为**独立新增模块** `core/team_standing.py`（纯函数：输入各项目结果 + 口径配置，输出单位积分榜），不触碰 scoring/skating_system/advancement 现有文件，等价性基线不受影响（见 §6.1）。

## 6. 评分与计算流程（服务层编排）

1. 开场：管理员勾选上场选手 → `open`（未上场者不进评分表；已有评分则提示并清空，复刻桌面版语义）。
2. 裁判整表 PUT：服务端按评分类型校验（顺位：覆盖全部上场选手、1~N 唯一；Mark：布尔标记 仅取 true/false），通过后 UPSERT 落库（mark 字段与 core/ 的 ScoreRecord.mark: Optional[bool] 直映；票数排名由 core/ 计算，见 REQUIREMENTS §8 Q-R2）。
3. 收齐判定：按 (上场选手 × 舞种 × 裁判) 全有记录，**排除 voided（作废）与被退回（return 后未重交）的记录**。收齐后**系统自动触发第 4 步计算（D3 默认）**；管理员亦可手动触发或重算。
4. 计算：读 score_records（排除 voided）→ 构造 core 的 ScoreRecord 列表 → `ScoringAlgorithm.calculate_results(...)` → 存 results。**评分类型枚举、选手编号统一为字符串**（与 core 等价测试口径一致）。计算在线程池执行，落库后发 `calculation_done` SSE 事件；发布状态变化由 `results_state_changed` 统一承载（§6.2/§7.1）。
5. 晋级：`calculate_advancement`（all_tied_advance/strict_count）+ 多组合并（`get_advancing_competitors`）→ 生成预案 → 管理员确认/调整 → 回填下一轮场次名单 → 下一轮可开场。

### 6.1 团体总分计算编排（FR-I6，独立模块）

**core/ 差距评估**：顺位法/Mark制/晋级对集体项目（队伍=编号）零改动可用；**缺口仅在"团体总分聚合"**——core/ 现无跨项目按单位聚合的任何能力，需新增独立模块：

```
core/team_standing.py（新增，纯函数，不改现有文件）
  compute_team_standings(project_results, units, config) -> standings
    project_results: [{project_id, group, entries: [{unit_ids, rank, entry_type}]}]
    config: {
      mode: "rank_points" | "sum_scores",     # 名次赋分 / 累计小分（Q-R3）
      points_table: {1: 9, 2: 7, ...},        # rank_points 模式的赋分表（可配置）
      best_n: int | null,                     # 每单位取最佳 N 项（Q-R3）
      group_by: "overall" | "group",          # 是否分组别排名（Q-R3）
      couple_cross_unit: "split" | "registered" | "exclude",  # Q-R4
    }
```

- 并列处理：同分单位并列名次（与 calculate_overall_ranking 的并列顺延语义一致，在 team_standing 内独立实现，不调用也不修改现有函数）。
- 测试：新模块配独立单元测试（tests/test_core_team_standing.py），不触碰现有 74 项等价性测试。
- 编排：服务层在"某单位相关项目全部完赛并发布后"触发聚合 → 结果存 results（scope=team_standing）→ SSE `results_state_changed` 推送管理端/大屏。

### 6.2 结果发布三态（FR-E6（提案））

提案，待用户确认，详见附录 P-2（三态矩阵/撤回路径/自动化/模型扩展的内容主体已移至附录）。当前正文口径：结果发布沿用 D5 发布制（发布后进大屏），明细不对公开端暴露。
- 口径配置（team_standing_config）由管理端设置页维护，Q-R3/Q-R4 拍板前提供默认值（rank_points + best_n=空 + overall）并在 UI 标注"待赛事章程确认"。

**多方案配置与随时重算（FR-I8（提案））**：提案，待用户确认，详见附录 P-1（presets/重算/历史的内容主体已移至附录）。

## 7. 实时刷新方案（R-2/R-3 细化）

选型：**SSE（Server-Sent Events）单向下行 + 普通表单/JSON 上行**。
- 理由：只读下发场景（进度、成绩、大屏）不需要双向 WebSocket；SSE 零额外依赖、断线自动重连、1.6G 内存下连接开销远低于 WS。
- 事件流：`GET /api/events/{eid}/stream`，服务端维护每赛事一个订阅列表 + 进程内发布（无外部消息队列）；服务端产生事件后立即写入所有订阅连接（无批处理延迟）。

### 7.1 事件类型清单（按订阅方分组）

| 事件类型 | 组 | 触发时机 | 订阅方 |
|----------|-----|----------|--------|
| `competition_event_opened` | judge/admin | 管理员开场（含评分表/上场名单） | 裁判、管理端 |
| `competition_event_closed` | judge/admin | 关闭/重开场次 | 裁判、管理端 |
| `roster_changed` | judge/admin | 上场选手增删 | 裁判、管理端 |
| `score_submitted` | judge/admin | 任一裁判提交/修改评分 | 其他裁判（仅进度，不含评分内容）、管理端 |
| `score_returned` / `score_voided` | judge/admin | 管理员退回/作废评分 | 被退回裁判、管理端 |
| `calculation_started` / `calculation_done` | admin | 计算触发/完成（含自动计算 D3） | 管理端 |
| `advancement_ready` | admin | 本轮全部场次完成，晋级预案就绪 | 管理端 |
| `results_state_changed`（提案 P-2） | admin/public | 发布状态变化（draft/provisional/official；统一承载原 results_published/unpublished） | 管理端、公开端 |
| `schedule_changed` | admin/public | 赛程/名单结构变化 | 管理端、公开端 |
| `screen_state_changed` | public | 大屏控制（轮播/暂停/指定） | 大屏 |
| `team_changed` | admin | 集体队伍组队/队员调整、同单位校验状态变化（FR-I2/I4；M6 引入） | 管理端 |

### 7.2 到达策略与延迟目标

- **延迟目标 <2s（NFR-9）**：事件在服务端动作提交事务后同步 fan-out；同局域网典型到达 <200ms，外网链路 <1s，满足 <2s 目标。
- **裁判端（R-2）**：`EventSource` 常驻订阅 judge 组事件；收到 `competition_event_opened`/`roster_changed` 后立即拉取最新评分表并整页局部重渲染；收到 `score_submitted` 仅更新进度角标。**提交后乐观更新**：PUT 返回 202 前本地先标记"已提交"，服务端确认后以响应为准，失败回滚提示。
- **管理端（R-3）**：控制台/赛程总览/晋级确认/结果中心共用同一 SSE 连接，订阅 admin 组事件；收到事件后按类型局部刷新对应区块（进度矩阵、状态徽标、结果区），**不依赖手动刷新**。
- **公开端**：订阅 public 组事件；大屏额外由 `screen_state_changed` 驱动画面切换。
- **降级轮询（SSE 不可用/断连超时）**：裁判端 **2s**、管理端 **3s**、公开端 **5s**；连接恢复后自动切回 SSE。
- 一致性：事件只做"提示刷新"，客户端收到后拉取对应 REST 资源，避免事件体与数据双份维护；事件携带单调递增序号，客户端丢弃乱序旧事件。

## 8. 部署形态与外网暴露对策（目标：1.6G RAM）

### 8.1 SQLite WAL + 单进程充分性论证（D1：高频写/低频读）
- 负载画像：写＝裁判提交评分表（每场次 ≤ 20 裁判 × 每人每舞种 1 次整表 UPSERT，峰值每秒个位数请求）；读＝观众/大屏轮询与 SSE 拉取（数百只读连接，秒级频率）。
- WAL 模式下 SQLite 支持**读写并发**（读不阻塞写、写不阻塞读），单写者串行对本系统足够：评分提交事务极小（单表 UPSERT + 唯一约束校验，<1ms），单进程内以写队列/线程锁串行化即可，无写冲突热点。
- 单进程免去多进程写锁协调；FastAPI 异步 IO 承载数百 SSE 长连接（每个连接 ~几十 KB 内存），只读查询走同一连接池。
- 结论：该读写比下 SQLite WAL + 单进程是充分方案，无需 PostgreSQL/Redis 等组件；瓶颈若现（远超预期并发），扩展路径为"只读副本页缓存 + 限流"，仍不动存储模型。
- 兜底：写操作全部走服务层单写连接串行执行；开启 `busy_timeout` 与外键约束；数据文件定期 `sqlite3 .backup`。

### 8.2 部署参数

| 项 | 方案 |
|----|------|
| 运行形态 | 单 systemd 服务（或 docker run 单容器），单进程 + 线程池（计算任务在线程池执行，预计 <100ms，无队列组件） |
| 技术栈（已拍板 D1） | Python 3.11+ / FastAPI + Uvicorn + Jinja2；前端服务端渲染 + 原生 JS（无 Node 构建链） |
| 存储 | SQLite（WAL），数据目录：`/var/lib/dancesport/`（data.db + exports/ + uploads/） |
| 内存预估 | Python 进程 ~80–150MB + SQLite 缓存 + SSE 连接，**总占用 ≪1.6G** |
| 端口（D9） | 默认 **8477**（8xxx 高位非默认端口，写入部署配置默认值）；可配置 |
| 备份 | data.db 单文件 + exports/ 目录；提供 `POST /api/backup`（管理端）或 cron sqlite3 .backup |
| 接入 | `http://<server-ip>:8477`；现场可用路由器 DHCP 静态绑定或局域网域名 |
| 升级 | 替换代码目录 + 重启 systemd；迁移用 SQLite 简单脚本 |

### 8.3 外网暴露对策（D1/D9，必须项）
服务器可从外网访问，安全基线：
1. **认证与会话**：管理员/裁判端所有页面与写接口强制登录 + 服务端会话（HttpOnly/Secure/SameSite cookie，会话过期可配）；未登录访问跳转登录页。
2. **公开页只读**：观众页/大屏仅暴露白名单只读 GET 接口（赛程、已发布结果、大屏状态），不含任何评分明细（D5）；其余全部 401/403。
3. **登录防爆破**：登录接口限速（如每 IP 每分钟 ≤5 次）+ 连续失败锁定（如 5 次锁 10 分钟）+ 统一错误文案（不区分"用户不存在/密码错"）。
4. **非默认端口**：默认 8477，避免扫描面（D9）。
5. **可选反向代理 HTTPS**：生产建议 Nginx/Caddy 终结 TLS（Caddy 自动证书），反代仅转发 8477；服务自身保持 HTTP 明文（局域网内段）。注意：SSE 需关闭代理响应缓冲（Nginx `proxy_buffering off` / Caddy `flush_interval -1`），否则事件会被缓冲导致延迟。
6. **其他基线**：上传文件类型/大小白名单校验；服务以非 root 运行；管理口令强度要求与修改入口；审计日志（登录成功/失败、评分修改、晋级确认）。

## 9. 工程结构（建议）

```
server/
  app.py            # 入口、路由装配
  api/              # REST 资源
  views/            # 服务端渲染页面
  services/         # 编排层（导入/评分/自动计算/晋级/发布撤回/大屏控制/导出/备份/团体总分聚合）
  realtime/         # SSE 事件总线（分组 fan-out，见 §7）
  repo/             # SQLite 访问与 core 模型互转
  exporters/        # 打印友好 HTML + Markdown 导出（无服务端 PDF 依赖，D8）
tools/
  migrate_legacy/   # 一次性迁移工具（独立小工具：旧桌面版 JSON → 新格式，D7）
core/               # 既有算法内核（等价基线，不改动现有文件；新增 team_standing.py 独立模块）
tests/              # 既有 core 测试（74 项等价性基线）+ team_standing 新模块测试 + services/API 测试
docs/
```

## 10. 里程碑建议（待细化）
1. M1 服务骨架 + 认证/会话 + 赛事（含激活）/导入/赛程只读页
2. M2 场次控制台 + 裁判移动评分（移动优先）+ core 自动计算闭环 + SSE 事件总线（§7）
3. M3 晋级确认 + 下一轮回填 + 导出（HTML 打印/Markdown）+ 评分退回/作废/重开
4. M4 实时完善（<2s 指标验收、降级轮询）+ 观众页/大屏（含管理员大屏控制）+ 发布/撤回（发布三态为提案 P-2，待确认）+ 明细权限隔离
5. M5 外网暴露安全加固、部署脚本（端口 8477/反代可选）、备份、迁移工具、验收演示
6. M6 集体项目 + 团体总分（FR-I1~I7）：单位/队伍管理与"一队一单位"校验、队伍评分（队伍=编号映射，裁判页/控制台适配）、core/team_standing 模块（含独立测试）、团体总分榜/发布/大屏接入、Q-R3/Q-R4 口径配置落地（口径命名方案与即时重算 FR-I8 为提案 P-1，待确认后纳入）

---

## 11. 决策记录与残余问题

用户已对 v0.1/v0.1.1 的全部主要开放问题拍板，决策记录见 `REQUIREMENTS.md` §7 DECISIONS（D1~D9）；本文档相应章节（§2/§3/§4/§6/§8/§9/§10）已同步落决策。v0.2.1 并入 R-1~R-4（响应式适配→§3；裁判端实时性→§7.2；管理端状态同步→§7.1/7.2；管理员控制面→§4.1），需求编号见 REQUIREMENTS §3.7（FR-G*）与 §3.8（FR-H*）。v0.2.2 新增集体项目与团体总分（FR-I1~I7→§5/§6.1/§4/§3）。v0.2.3 并入用户三点新要求（口径多方案与重算 FR-I8、发布三态 FR-E6、角色动线与轻量易用 FR-J1/J2→§2.4/§6.1/§6.2）；**其中 FR-I8/FR-E6/FR-J1 三项经 GC 认定超出派发范围，已降级为提案（见附录 P-1/P-2/P-3），正文仅保留引用，待用户确认后转正**。

**残余开放问题**（继承 REQUIREMENTS §8，v0.2.2 新增 Q-R3/Q-R4）：
| # | 问题 | 现状/建议 |
|---|------|-----------|
| Q-R1 | 裁判设备是否固定（赛会配发）？影响"换设备续评"设计 | 默认按"裁判 ID 任意设备登录"实现，不锁设备 |
| Q-R2 | Mark制语义：布尔标记（core 现状）vs 0-10 分制（需扩展 core） | 按布尔标记实现 |
| Q-R3 | 团体总分口径：名次赋分 vs 累计小分；最佳 N 项/分组别/权重 | 默认名次赋分+总榜，配置可调，待拍板 |
| Q-R4 | 跨单位舞伴团体归属：各计半分 / 代表主报单位 / 不计团体 | 默认"代表主报单位"，待拍板 |

---

## 附录：提案清单（未获用户指令，仅建议）

> GC 管理指令：以下三项超出已派发范围，降级为提案；内容主体自正文移入本附录，待用户确认后方可转正。正文相应位置仅保留一句话引用。

### P-1 团体总分口径多方案与重算（FR-I8（提案）→ 原 §6.1 扩展段）
- **命名方案（presets）**：`standing_presets` 表（id, competition_id, name, config JSON, is_default）——保存多套口径方案；赛事/项目可各自绑定某个 preset（projects.team_standing_config 存 preset 引用或独立覆盖）。
- **重算语义**：切换方案/修改配置后点击重算 → 服务层调用 `compute_team_standings`（纯函数）重新聚合并**覆盖写入** team_standing 结果区——重算**幂等**（同输入同配置结果一致）、**不重复入账**（聚合源始终是各项目 results 原始数据，不叠加历史聚合结果）。
- **历史可追溯**：每次重算写 `standing_history`（id, scope, preset_snapshot(JSON), computed_at, trigger[manual/auto]）——榜单页可查看"当前由哪套方案、何时算出"，并可对比历史快照。
- API：`GET/POST /api/events/{eid}/standing-presets`、`PUT /api/events/{eid}/standing-config`（绑定 preset）、`POST /api/events/{eid}/team-standings/recalculate`（body: preset_id）。
- 不改 core 现有算法：presets/重算/历史全部在服务层与新模块内实现，与 M6 落地衔接。

### P-2 结果发布三态（FR-E6（提案）→ 原 §6.2）
结果生命周期：**draft → provisional（公示）→ official（正式）**；撤回为逆向转换。

| 状态 | 谁能看 | API 返回标注 | 允许修改？ | 撤回路径 |
|------|--------|--------------|------------|----------|
| draft | 仅管理端工作区（结果中心/控制台预览） | 不对公开 API 暴露 | 是（重算/编辑后覆盖 draft） | — |
| provisional（公示） | 管理端 + 主动查询的公开接口（观众页可查） | 公开 API 带 `"state": "provisional"` + 页面显式徽标「非最终成绩，以正式发布为准」 | **是**：公示期允许修改/重算，修改后**重新推送公示**（更新 provisional 数据与时间戳） | 管理员可撤回公示 → 回 draft |
| official（正式） | 管理端 + 公开接口 + 进大屏轮播 | `"state": "official"` | 否（如需修改：先撤回 official → 退回 provisional/draft，修改后重新逐级发布，全程审计留痕） | 管理员撤回 → provisional 或 draft |

- 与 D5 兼容：D5 的"发布制保留"语义由 official 承担（大屏只展示 official）；provisional 为新增的公示层，评分明细在任一状态均不对公开端暴露（D5 明细权限不变）。
- 自动化（可配置，默认关）：①计算完成自动进入 provisional；②满足条件（如全部项目 official）自动将团体总分榜转 official；③大屏轮播自动纳入新 official 榜单。
- 模型扩展：`published_flags` 升级为 `result_publication`（id, scope, status: draft/provisional/official, provisional_at, official_at, withdrawn_at, scope_ref）。
- 事件：SSE 新增 `results_state_changed`（admin/public 组；公开端收到后按标注刷新）。

### P-3 复制上届建赛（FR-J1（提案）→ 原 §2.4/§3/§4 相关条目）
新建赛事支持**复制上届**：`POST /api/events/{eid}/duplicate`（复制单位/选手/项目/赛程模板结构，不含成绩）；配合项目单页一步完成与轮次批量生成。
