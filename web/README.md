# 体育舞蹈赛事评分系统 Web 版

局域网部署的体育舞蹈赛事评分系统，支持多设备访问。

## 快速开始

### 开发环境

**后端启动：**
```bash
cd web/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端启动：**
```bash
cd web/frontend
npm install
npm run dev
```

访问 http://localhost:3000

### Docker 部署

```bash
cd web
docker-compose up -d
```

访问 http://localhost

## 功能特性

- 赛事管理
- 选手管理（支持单人/双人）
- 场次编排
- 评分系统（Mark制/顺位法）
- 实时成绩展示
- 单位总分统计
- 大屏展示
- PDF/Excel 导出

## 设备适配

| 设备 | 布局 |
|------|------|
| 桌面 | 侧边导航，完整表格 |
| 平板 | 可折叠侧边栏，大按钮 |
| 手机 | 底部导航，单列布局 |
| 大屏 | 全屏展示，醒目大字 |

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite
- **前端**: Vue 3 + Element Plus + TypeScript
- **部署**: Docker Compose
