# 体育舞蹈赛事评分系统 - Web版本开发状态

> 创建时间: 2026-05-12
> 状态: 开发完成，待部署

## 项目概述

将桌面版体育舞蹈赛事评分系统（Python/Tkinter）扩展为Web版本，支持局域网部署和多设备访问。

### 技术栈
- **后端**: FastAPI + SQLAlchemy + SQLite/PostgreSQL
- **前端**: Vue 3 + TypeScript + Element Plus
- **认证**: JWT Token
- **部署**: Docker + Nginx

## 已完成功能

### 1. 用户认证
- [x] 用户注册/登录
- [x] JWT Token认证
- [x] 角色管理（管理员/操作员）

### 2. 赛事管理
- [x] 创建/编辑/删除赛事
- [x] 赛事列表和详情查看
- [x] 赛事状态管理

### 3. 选手管理
- [x] 添加/编辑/删除选手
- [x] CSV批量导入选手
- [x] 选手与单位关联
- [x] 双人项目支持

### 4. 场次管理
- [x] 创建场次（Mark制/顺位法）
- [x] CSV批量导入赛程
- [x] 参赛选手配置
- [x] 场次状态管理

### 5. 评分系统
- [x] **Mark制评分** - 裁判选择晋级选手，票数统计排名
- [x] **顺位法评分** - 多裁判排名评分，综合排名计算
- [x] 多裁判同时打分支持（11人）
- [x] 评分数据实时保存

### 6. 成绩计算
- [x] Mark制成绩计算（票数统计）
- [x] 顺位法成绩计算（平均排名+第一名票数）
- [x] 晋级选手自动标记
- [x] 场次成绩查看

### 7. 单位总分
- [x] 单位总分计算
- [x] 双人项目分数分摊
- [x] 排名展示
- [x] 得分明细查看

### 8. 数据导入
- [x] CSV选手导入（支持格式：背番号,姓名,学校/单位,参赛组别）
- [x] CSV赛程导入（支持格式：场次编号,场次名称,项目名称,项目编号,轮次,评分类型,舞种,参赛选手,晋级人数）
- [x] 一键导入测试数据

### 9. 数据导出
- [x] 单位总分排名导出（CSV）
- [x] 单场次成绩导出（CSV）
- [x] 所有场次成绩导出（CSV）

### 10. 前端界面
- [x] 响应式设计（PC/平板/手机）
- [x] 登录页面
- [x] 赛事管理页面
- [x] 选手管理页面（带导入功能）
- [x] 场次管理页面（带赛程导入）
- [x] 评分页面（Mark制/顺位法）
- [x] 单位总分排名页面
- [x] 成绩查看弹窗

## 评分算法

### Mark制（淘汰赛）
1. 每位裁判选择晋级的选手
2. 统计每个选手被选中的次数
3. 按票数降序排名
4. 达到晋级人数后停止

### 顺位法（排名赛）
1. 每位裁判对选手进行排名
2. 计算每位选手的平均排名
3. 统计获得第一名的票数
4. 排名规则：
   - 第一名票数多者优先
   - 第一名票数相同则平均排名低者优先
   - 平均排名相同则总排名分低者优先

## 文件结构

```
web/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API路由
│   │   │   ├── auth.py       # 认证
│   │   │   ├── competitions.py # 赛事
│   │   │   ├── competitors.py  # 选手
│   │   │   ├── events.py      # 场次
│   │   │   ├── scoring.py     # 评分
│   │   │   ├── ranking.py     # 排名
│   │   │   ├── import_data.py # 导入
│   │   │   └── export.py      # 导出
│   │   ├── core/
│   │   │   ├── config.py      # 配置
│   │   │   ├── database.py    # 数据库
│   │   │   └── security.py    # 安全
│   │   ├── models/           # 数据模型
│   │   ├── schemas/          # Pydantic模型
│   │   ├── services/         # 业务逻辑
│   │   │   ├── scoring_service.py  # 评分算法
│   │   │   └── ranking_service.py  # 排名算法
│   │   └── main.py           # 入口
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/              # API调用
│   │   ├── views/            # 页面组件
│   │   ├── router/           # 路由
│   │   ├── store/            # 状态管理
│   │   └── App.vue
│   ├── package.json
│   └── vite.config.ts
└── deploy/
    ├── docker-compose.yml     # Docker部署
    ├── one-click-deploy.sh    # 一键部署脚本
    └── aliyun/               # 阿里云部署配置
```

## 数据库模型

### 核心表
- `User` - 用户表
- `Competition` - 赛事表
- `Competitor` - 选手表
- `Event` - 场次表
- `ScoreRecord` - 评分记录表
- `Result` - 成绩表
- `UnitPoints` - 单位总分表
- `AwardConfig` - 奖项配置表

## 待部署服务器

- **服务器**: 阿里云ECS
- **公网IP**: 59.110.90.21
- **SSH**: sport-coder@59.110.90.21
- **配置**: 2vCPU 2GB, Ubuntu 22.04
- **部署方式**: Docker

## 部署状态

- [x] 代码开发完成
- [x] 部署脚本准备完成
- [ ] 服务器部署待执行
- [ ] 域名配置（可选）
- [ ] SSL证书配置（可选）

## 使用说明

### 快速部署
```bash
# 在服务器上执行
wget https://raw.githubusercontent.com/RunshengZhu/Simple-Dance-Sport-System/main/web/deploy/one-click-deploy.sh
chmod +x one-click-deploy.sh
sudo ./one-click-deploy.sh
```

### Docker部署
```bash
cd /opt/dancesport
docker-compose up -d
```

### 默认账号
- 用户名: admin
- 密码: admin123

## API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/login | 登录 |
| POST | /api/v1/auth/register | 注册 |
| GET/POST | /api/v1/competitions | 赛事列表/创建 |
| GET/POST | /api/v1/competitions/{id}/competitors | 选手列表/导入 |
| GET/POST | /api/v1/competitions/{id}/events | 场次列表/导入 |
| POST | /api/v1/events/{id}/scores | 提交评分 |
| POST | /api/v1/events/{id}/calculate | 计算成绩 |
| GET | /api/v1/events/{id}/results | 获取成绩 |
| GET/POST | /api/v1/competitions/{id}/ranking | 单位排名 |
| GET | /api/v1/competitions/{id}/export-ranking | 导出排名 |

## 测试数据

测试数据文件位于 `src/test_data/`:
- `test_competitors.csv` - 107名选手
- `test_schedule.csv` - 27场赛事

### CSV格式

**选手导入格式:**
```csv
背番号,姓名,学校/单位,参赛组别
1001,张三,清华大学,交谊舞组
1002,李四/王五,北京大学,华尔兹组双人
```

**赛程导入格式:**
```csv
场次编号,场次名称,项目名称,项目编号,轮次,评分类型,舞种,参赛选手,晋级人数
1,交谊舞组新生类平四单项A预赛,交谊舞组新生类平四单项,1,1,mark,平四,"1001,1002,1003",5
```

## 后续工作

1. [ ] 完成服务器部署
2. [ ] 配置HTTPS（可选）
3. [ ] 配置域名（可选）
4. [ ] 编写用户使用手册
5. [ ] 添加单元测试
6. [ ] 性能优化

## 联系方式

- 项目维护者: RunshengZhu
- GitHub: https://github.com/RunshengZhu/Simple-Dance-Sport-System

## 更新日志

### 2026-05-12
- 完成Web版本核心功能开发
- 实现Mark制和顺位法评分算法
- 实现CSV导入导出功能
- 完成响应式前端界面
- 准备Docker部署方案
