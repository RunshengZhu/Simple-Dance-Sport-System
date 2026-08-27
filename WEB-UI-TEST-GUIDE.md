# Web UI自动化测试使用指南

## 📋 概述

本文档说明了如何运行基于Playwright的Web UI自动化测试。

## 🚀 快速开始

### 方法一：一键启动（推荐）

```bash
# 给脚本添加执行权限
chmod +x run-web-tests.sh

# 运行启动脚本
./run-web-tests.sh
```

脚本会自动：
1. 检查依赖
2. 启动后端服务
3. 创建测试账号
4. 安装前端依赖
5. 提示运行测试

### 方法二：手动启动

#### 1. 启动后端服务

```bash
cd web/backend
uvicorn app.main:app --reload --port 8000
```

#### 2. 启动前端服务

```bash
cd web/frontend
npm run dev
```

#### 3. 运行测试

```bash
cd web/frontend

# 运行所有测试
npx playwright test

# 只运行特定测试
npx playwright test -k "登录"
npx playwright test -k "隐私保护"
npx playwright test -k "移动端"
```

## 📝 测试用例

测试文件位于 `web/frontend/tests/e2e.spec.ts`

### 测试清单

| 序号 | 测试名称 | 说明 |
|------|----------|------|
| 1 | 登录功能测试 | 验证用户登录功能 |
| 2 | 管理员创建赛事流程 | 验证创建赛事功能 |
| 3 | 导入选手数据 | 验证CSV导入功能 |
| 4 | 裁判评分界面隐私保护测试 | 验证只显示背号 |
| 5 | 裁判评分交互测试 | 验证评分操作 |
| 6 | 成绩查看功能测试 | 验证成绩显示 |
| 7 | 移动端响应式布局测试 | 验证移动端适配 |
| 8 | 多裁判评分自动计算测试 | 验证自动计算 |
| 9 | 用户权限测试 | 验证角色权限 |
| 10 | 退出登录测试 | 验证退出功能 |

## 🔑 测试账号

系统已预置以下测试账号：

| 角色 | 用户名 | 密码 | 权限 |
|------|--------|------|------|
| 管理员 | admin | admin123 | 全部功能 |
| 裁判 | judge1 | judge123 | 评分 |
| 裁判 | judge2 | judge123 | 评分 |
| 裁判 | judge3 | judge123 | 评分 |
| 裁判 | judge4 | judge123 | 评分 |
| 裁判 | judge5 | judge123 | 评分 |
| 观众 | viewer | viewer123 | 查看 |

## 📊 查看测试报告

### HTML报告

```bash
cd web/frontend
npx playwright show-report
```

报告将自动在浏览器中打开。

### 控制台输出

```bash
npx playwright test --reporter=list
```

### 截图和视频

测试失败时，会自动保存截图和视频到：
- `web/frontend/test-results/`
- `web/frontend/playwright-report/`

## 🎯 重点验证项

### 1. 隐私保护（最重要）

```typescript
test('4. 裁判评分界面隐私保护测试', async ({ page }) => {
  // 检查评分卡片只显示背号
  const scoringItems = page.locator('.scoring-item');
  
  // 验证只渲染背号
  const numberDiv = scoringItems.first().locator('.number');
  await expect(numberDiv).toBeVisible();
  
  // 验证不渲染姓名和单位
  const nameDiv = scoringItems.first().locator('.name');
  const nameVisible = await nameDiv.isVisible().catch(() => false);
  expect(nameVisible).toBe(false);
});
```

### 2. 自动计算

```typescript
test('8. 多裁判评分自动计算测试', async ({ page }) => {
  // 5个裁判依次评分
  for (let i = 0; i < 5; i++) {
    await judgeItems.nth(i).click();
    await scoringItems.nth(0).click();
    await submitBtn.click();
  }
  
  // 验证自动计算触发
  await page.waitForTimeout(2000);
  const completedEvents = page.locator('.event-card:has-text("已完成")');
  expect(await completedEvents.count()).toBeGreaterThan(0);
});
```

### 3. 移动端适配

```typescript
test('7. 移动端响应式布局测试', async ({ page }) => {
  // 设置移动端视口
  await page.setViewportSize({ width: 375, height: 667 });
  
  // 验证响应式元素
  const menuBtn = page.locator('.menu-btn');
  await expect(menuBtn).toBeVisible();
});
```

## ⚙️ Playwright配置

配置文件位于 `web/frontend/playwright.config.ts`

### 主要配置

- **测试目录**: `./tests`
- **测试浏览器**: Chromium, Mobile Chrome
- **视口大小**: 
  - Desktop: 1280x720
  - Mobile: Pixel 5 (390x844)
- **超时时间**: 30秒
- **重试次数**: CI环境重试2次

## 🔧 常见问题

### 1. 测试超时

如果测试超时，可以增加超时时间：

```typescript
// playwright.config.ts
export default defineConfig({
  timeout: 60000, // 60秒
});
```

### 2. 元素找不到

使用 `waitForSelector` 等待元素：

```typescript
await page.waitForSelector('.scoring-item', { state: 'visible' });
```

### 3. 需要登录状态

在测试中使用 `login()` 辅助函数：

```typescript
async function login(page, username, password) {
  await page.goto('/login');
  await page.fill('input[placeholder="用户名"]', username);
  await page.fill('input[placeholder="密码"]', password);
  await page.click('button:has-text("登 录")');
  await page.waitForURL('**/dashboard');
}
```

## 📈 性能基准

- 页面加载时间: < 3秒
- 测试执行时间: < 5分钟（完整套件）
- 并行测试: 支持

## 🎓 扩展测试

### 添加新测试

在 `tests/e2e.spec.ts` 中添加：

```typescript
test('新测试名称', async ({ page }) => {
  // 测试代码
});
```

### 添加页面对象

创建 `tests/pages/` 目录：

```typescript
// tests/pages/LoginPage.ts
export class LoginPage {
  constructor(page) {
    this.page = page;
    this.usernameInput = page.locator('input[placeholder="用户名"]');
    this.passwordInput = page.locator('input[placeholder="密码"]');
    this.loginButton = page.locator('button:has-text("登 录")');
  }

  async login(username, password) {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
    await this.page.waitForURL('**/dashboard');
  }
}
```

## 📞 支持

如有问题，请检查：
1. 服务是否正常运行 (http://localhost:8000, http://localhost:5173)
2. 测试账号是否已创建
3. 浏览器控制台是否有错误
4. Playwright是否正确安装

---

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
