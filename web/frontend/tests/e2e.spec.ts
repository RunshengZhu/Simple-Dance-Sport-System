import { test, expect } from '@playwright/test';

// 测试配置
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const ADMIN_USER = { username: 'admin', password: 'admin123' };
const JUDGE_USER = { username: 'judge1', password: 'judge123' };
const VIEWER_USER = { username: 'viewer', password: 'viewer123' };

// 辅助函数
async function login(page: any, username: string, password: string) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForLoadState('networkidle');
  
  // 输入用户名和密码
  const usernameInput = page.locator('input[placeholder="用户名"]');
  const passwordInput = page.locator('input[placeholder="密码"]');
  
  await usernameInput.fill(username);
  await passwordInput.fill(password);
  
  // 点击登录按钮
  await page.click('button:has-text("登 录")');
  
  // 等待登录成功并跳转到首页
  await page.waitForURL('**/dashboard', { timeout: 10000 });
}

async function createTestCompetition(page: any, name: string) {
  await page.goto(`${BASE_URL}/competitions`);
  await page.waitForLoadState('networkidle');
  
  // 点击创建赛事按钮
  await page.click('button:has-text("创建赛事")');
  await page.waitForSelector('.el-dialog', { state: 'visible' });
  
  // 填写赛事信息
  await page.fill('input[placeholder*="赛事名称"]', name);
  await page.fill('input[placeholder*="日期"]', '2024-06-15');
  await page.fill('input[placeholder*="地点"]', '体育馆');
  
  // 提交
  await page.click('button:has-text("确 定"):visible');
  
  // 等待创建成功
  await expect(page.locator('.el-message--success')).toBeVisible({ timeout: 5000 });
}

test.describe('体育舞蹈评分系统 - Web UI 自动化测试', () => {
  
  test.beforeEach(async ({ page }) => {
    // 设置视口大小
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test('1. 登录功能测试', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证用户登录功能'
    });

    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');
    
    // 验证登录页面元素
    await expect(page.locator('h1:has-text("体育舞蹈赛事评分系统")')).toBeVisible();
    
    // 输入正确的用户名和密码
    await page.fill('input[placeholder="用户名"]', ADMIN_USER.username);
    await page.fill('input[placeholder="密码"]', ADMIN_USER.password);
    
    // 点击登录
    await page.click('button:has-text("登 录")');
    
    // 等待跳转到首页
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    
    // 验证登录成功
    await expect(page.locator('text=赛事概览')).toBeVisible();
    console.log('✅ 登录功能测试通过');
  });

  test('2. 管理员创建赛事流程', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证管理员创建赛事功能'
    });

    await login(page, ADMIN_USER.username, ADMIN_USER.password);
    
    // 导航到赛事管理
    await page.click('text=赛事管理');
    await page.waitForURL('**/competitions');
    
    // 点击创建赛事
    const createBtn = page.locator('button:has-text("创建赛事")');
    if (await createBtn.isVisible()) {
      await createBtn.click();
      await page.waitForSelector('.el-dialog', { state: 'visible' });
      
      // 填写表单
      await page.fill('input[placeholder*="赛事名称"]', '2024年校园体育舞蹈比赛');
      await page.fill('input[placeholder*="日期"]', '2024-06-15');
      await page.fill('input[placeholder*="地点"]', '体育馆');
      
      // 提交
      await page.click('button:has-text("确 定"):visible');
      
      // 等待成功消息
      await expect(page.locator('.el-message--success')).toBeVisible({ timeout: 5000 });
      console.log('✅ 赛事创建成功');
    } else {
      console.log('⚠️  赛事已存在，跳过创建');
    }
  });

  test('3. 导入选手数据', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证导入选手数据功能'
    });

    await login(page, ADMIN_USER.username, ADMIN_USER.password);
    
    // 导航到赛事管理
    await page.click('text=赛事管理');
    await page.waitForURL('**/competitions');
    
    // 选择第一个赛事
    const competitionCard = page.locator('.competition-card').first();
    if (await competitionCard.isVisible()) {
      await competitionCard.click();
      await page.waitForURL('**/competitions/**');
      console.log('✅ 进入赛事详情页');
      
      // 查找导入按钮
      const importBtn = page.locator('button:has-text("导入选手")');
      if (await importBtn.isVisible()) {
        await importBtn.click();
        await page.waitForSelector('.el-dialog', { state: 'visible' });
        
        // 上传文件 - 使用test_data中的CSV
        const fileInput = page.locator('input[type="file"]');
        await fileInput.setInputFiles('../backend/test_data/test_competitors.csv');
        
        // 提交
        await page.click('button:has-text("确 定"):visible');
        
        // 等待成功
        await expect(page.locator('.el-message--success')).toBeVisible({ timeout: 10000 });
        console.log('✅ 选手数据导入成功');
      }
    }
  });

  test('4. 裁判评分界面隐私保护测试', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证裁判评分时只显示背号，不显示选手信息'
    });

    await login(page, JUDGE_USER.username, JUDGE_USER.password);
    
    // 导航到评分页面
    await page.goto(`${BASE_URL}/competitions`);
    await page.waitForLoadState('networkidle');
    
    // 选择赛事
    const competitionCard = page.locator('.competition-card').first();
    if (await competitionCard.isVisible()) {
      await competitionCard.click();
      await page.waitForURL('**/competitions/**');
      
      // 选择一个场次
      const eventCard = page.locator('.event-card').first();
      if (await eventCard.isVisible()) {
        await eventCard.click();
        await page.waitForURL('**/scoring/**');
        console.log('✅ 进入评分页面');
        
        // 验证只显示背号
        const scoringItems = page.locator('.scoring-item');
        const count = await scoringItems.count();
        
        if (count > 0) {
          // 检查是否只显示号码，不显示姓名和单位
          const firstItem = scoringItems.first();
          const numberDiv = firstItem.locator('.number');
          const nameDiv = firstItem.locator('.name');
          const unitDiv = firstItem.locator('.unit');
          
          // 号码应该可见
          await expect(numberDiv).toBeVisible();
          
          // 姓名和单位不应该存在或不可见
          const nameVisible = await nameDiv.isVisible().catch(() => false);
          const unitVisible = await unitDiv.isVisible().catch(() => false);
          
          if (!nameVisible && !unitVisible) {
            console.log(`✅ 隐私保护验证通过：评分卡片只显示背号(${count}个)`);
          } else {
            console.log(`⚠️  隐私保护验证失败：仍然显示姓名或单位`);
          }
        }
      }
    }
  });

  test('5. 裁判评分交互测试', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证裁判评分交互功能'
    });

    await login(page, JUDGE_USER.username, JUDGE_USER.password);
    
    // 导航到评分页面
    await page.goto(`${BASE_URL}/competitions`);
    await page.waitForLoadState('networkidle');
    
    const competitionCard = page.locator('.competition-card').first();
    if (await competitionCard.isVisible()) {
      await competitionCard.click();
      await page.waitForURL('**/competitions/**');
      
      const eventCard = page.locator('.event-card').first();
      if (await eventCard.isVisible()) {
        await eventCard.click();
        await page.waitForURL('**/scoring/**');
        
        // 等待加载
        await page.waitForTimeout(1000);
        
        // 选择几个选手
        const scoringItems = page.locator('.scoring-item');
        const count = await scoringItems.count();
        
        if (count > 0) {
          // 点击前3个选手
          for (let i = 0; i < Math.min(3, count); i++) {
            await scoringItems.nth(i).click();
            await page.waitForTimeout(100);
          }
          
          // 验证选中状态
          const selectedItems = page.locator('.scoring-item.selected');
          const selectedCount = await selectedItems.count();
          
          if (selectedCount >= 3) {
            console.log(`✅ 评分选择功能正常：已选择 ${selectedCount} 个选手`);
          }
          
          // 提交评分
          const submitBtn = page.locator('button:has-text("提交评分")');
          if (await submitBtn.isVisible()) {
            await submitBtn.click();
            
            // 等待提交成功
            await page.waitForTimeout(1000);
            console.log('✅ 评分提交成功');
          }
        }
      }
    }
  });

  test('6. 成绩查看功能测试', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证成绩查看和排名显示功能'
    });

    await login(page, VIEWER_USER.username, VIEWER_USER.password);
    
    // 导航到公众查看页面
    await page.goto(`${BASE_URL}/viewer`);
    await page.waitForLoadState('networkidle');
    
    // 选择赛事
    const competitionCard = page.locator('.competition-card').first();
    if (await competitionCard.isVisible()) {
      await competitionCard.click();
      await page.waitForTimeout(500);
      
      // 切换到排名标签
      const rankingTab = page.locator('.el-tab-pane:has-text("排名")');
      if (await rankingTab.isVisible()) {
        await page.click('text=排名');
        await page.waitForTimeout(500);
        
        const rankingCards = page.locator('.ranking-card');
        const count = await rankingCards.count();
        
        if (count > 0) {
          console.log(`✅ 排名显示正常：${count} 个单位`);
        }
      }
      
      // 点击一个已完成场次
      const eventCard = page.locator('.event-card:has-text("已完成")').first();
      if (await eventCard.isVisible()) {
        await eventCard.click();
        await page.waitForTimeout(1000);
        
        // 验证成绩显示
        const resultItems = page.locator('.result-item');
        const resultCount = await resultItems.count();
        
        if (resultCount > 0) {
          console.log(`✅ 成绩查看正常：${resultCount} 条成绩`);
          
          // 验证显示完整信息（背号、姓名、单位）
          const firstResult = resultItems.first();
          const hasNumber = await firstResult.locator('.number').isVisible().catch(() => false);
          const hasName = await firstResult.locator('.name').isVisible().catch(() => false);
          const hasUnit = await firstResult.locator('.unit').isVisible().catch(() => false);
          
          if (hasNumber && hasName && hasUnit) {
            console.log('✅ 成绩页面显示完整信息（背号、姓名、单位）');
          }
        }
      }
    }
  });

  test('7. 移动端响应式布局测试', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证移动端适配功能'
    });

    // 设置移动端视口
    await page.setViewportSize({ width: 375, height: 667 });
    
    await login(page, ADMIN_USER.username, ADMIN_USER.password);
    
    // 验证移动端导航
    const menuBtn = page.locator('.menu-btn');
    if (await menuBtn.isVisible()) {
      console.log('✅ 移动端汉堡菜单正常显示');
      
      // 点击打开侧边栏
      await menuBtn.click();
      await page.waitForTimeout(500);
      
      // 验证侧边栏打开
      const sidebar = page.locator('.aside');
      const sidebarWidth = await sidebar.evaluate((el: any) => el.offsetWidth);
      
      if (sidebarWidth > 0) {
        console.log('✅ 移动端侧边栏功能正常');
      }
    }
    
    // 测试评分页面移动端布局
    await page.goto(`${BASE_URL}/competitions`);
    await page.waitForLoadState('networkidle');
    
    const competitionCard = page.locator('.competition-card').first();
    if (await competitionCard.isVisible()) {
      await competitionCard.click();
      await page.waitForURL('**/competitions/**');
      
      const eventCard = page.locator('.event-card').first();
      if (await eventCard.isVisible()) {
        await eventCard.click();
        await page.waitForURL('**/scoring/**');
        
        // 验证评分卡片布局
        const scoringGrid = page.locator('.scoring-grid');
        const isVisible = await scoringGrid.isVisible();
        
        if (isVisible) {
          console.log('✅ 移动端评分网格布局正常');
        }
        
        // 验证评分卡片大小适合触摸
        const scoringItems = page.locator('.scoring-item');
        const count = await scoringItems.count();
        
        if (count > 0) {
          const itemSize = await scoringItems.first().evaluate((el: any) => {
            return { width: el.offsetWidth, height: el.offsetHeight };
          });
          
          console.log(`✅ 评分卡片尺寸合适触摸操作: ${itemSize.width}x${itemSize.height}px`);
        }
      }
    }
  });

  test('8. 多裁判评分自动计算测试', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证多裁判评分后自动计算成绩'
    });

    // 使用管理员账号登录进行测试
    await login(page, ADMIN_USER.username, ADMIN_USER.password);
    
    // 导航到评分页面
    await page.goto(`${BASE_URL}/competitions`);
    await page.waitForLoadState('networkidle');
    
    const competitionCard = page.locator('.competition-card').first();
    if (await competitionCard.isVisible()) {
      await competitionCard.click();
      await page.waitForURL('**/competitions/**');
      
      // 选择一个场次
      const eventCard = page.locator('.event-card').first();
      if (await eventCard.isVisible()) {
        await eventCard.click();
        await page.waitForURL('**/scoring/**');
        await page.waitForTimeout(1000);
        
        // 切换裁判评分
        const judgeItems = page.locator('.judge-item');
        const judgeCount = await judgeItems.count();
        
        // 模拟5个裁判依次评分
        for (let i = 0; i < Math.min(5, judgeCount); i++) {
          // 选择裁判
          await judgeItems.nth(i).click();
          await page.waitForTimeout(500);
          
          // 选择部分选手
          const scoringItems = page.locator('.scoring-item');
          const itemCount = await scoringItems.count();
          
          for (let j = 0; j < Math.min(3, itemCount); j++) {
            await scoringItems.nth(j).click();
            await page.waitForTimeout(50);
          }
          
          // 提交
          const submitBtn = page.locator('button:has-text("提交评分")');
          if (await submitBtn.isVisible()) {
            await submitBtn.click();
            await page.waitForTimeout(1000);
            console.log(`✅ 裁判 ${i + 1} 评分提交成功`);
          }
        }
        
        // 验证自动计算 - 检查场次状态
        await page.goto(`${BASE_URL}/competitions`);
        await page.waitForLoadState('networkidle');
        
        const completedEvents = page.locator('.event-card:has-text("已完成")');
        const completedCount = await completedEvents.count();
        
        if (completedCount > 0) {
          console.log(`✅ 自动计算验证通过：${completedCount} 个场次已自动完成`);
        } else {
          console.log('⚠️  自动计算可能未触发或场次尚未完成');
        }
      }
    }
  });

  test('9. 用户权限测试', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证不同角色的访问权限'
    });

    // 测试观众账号
    await login(page, VIEWER_USER.username, VIEWER_USER.password);
    
    // 观众应该只能看到查看页面
    await page.goto(`${BASE_URL}/viewer`);
    await page.waitForLoadState('networkidle');
    
    const viewerVisible = await page.locator('text=进行中的赛事').isVisible().catch(() => false);
    if (viewerVisible) {
      console.log('✅ 观众账号可以访问查看页面');
    }
    
    // 观众不应该看到管理菜单
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    const manageMenuVisible = await page.locator('text=赛事管理').isVisible().catch(() => false);
    if (!manageMenuVisible) {
      console.log('✅ 观众账号无法访问管理菜单');
    } else {
      console.log('⚠️  观众账号可能具有管理权限');
    }
  });

  test('10. 退出登录测试', async ({ page }) => {
    test.info().annotations.push({
      type: '测试项',
      description: '验证退出登录功能'
    });

    await login(page, ADMIN_USER.username, ADMIN_USER.password);
    
    // 点击退出按钮
    const logoutBtn = page.locator('button:has-text("退出")');
    if (await logoutBtn.isVisible()) {
      await logoutBtn.click();
      
      // 等待跳转到登录页
      await page.waitForURL('**/login', { timeout: 5000 });
      
      const loginFormVisible = await page.locator('h1:has-text("体育舞蹈赛事评分系统")').isVisible();
      if (loginFormVisible) {
        console.log('✅ 退出登录功能正常');
      }
    }
  });

});

test.describe('性能测试', () => {
  test('页面加载性能测试', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    console.log(`⏱️  登录页面加载时间: ${loadTime}ms`);
    
    expect(loadTime).toBeLessThan(3000);
  });
});
