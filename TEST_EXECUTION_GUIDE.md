# 🎯 移动端WebUI测试 - 执行指南

## ✅ 当前准备状态

### 服务器状态
- ✅ 后端API: http://59.110.90.21/api/v1 （已修复配置）
- ✅ 前端页面: http://59.110.90.21 （已打开）
- ✅ 浏览器已启动

### 测试工具
- ✅ 9场景完整测试脚本: `test_mobile_complete_9_scenarios.py`
- ✅ 快速测试清单: `QUICK_TEST_CHECKLIST.md`
- ✅ API验证脚本: `test_api_complete.py`
- ✅ 移动端测试指南: `MOBILE_WEBUI_TEST_GUIDE.md`

---

## 🚀 立即开始测试

### 方法1: 在已打开的浏览器中测试（推荐）

浏览器已经打开 http://59.110.90.21，请执行以下操作：

#### 步骤1: 启用移动端模拟
1. 按 **F12** 打开开发者工具
2. 按 **Cmd+Shift+M** (Mac) 切换设备模式
3. 选择 **iPhone SE** 或设置 **375x667**

#### 步骤2: 执行9场景测试

在开发者工具的 **Console** 标签页中，先运行此代码测试API连接：

```javascript
// 测试API连接
fetch('http://59.110.90.21/api/v1/auth/login', {
  method: 'POST',
  headers: {'Content-Type': 'application/x-www-form-urlencoded'},
  body: 'username=admin&password=admin123'
})
.then(r => r.json())
.then(d => {
  if(d.access_token) {
    console.log('✅ API连接成功!');
    console.log('✅ 管理员登录成功!');
    console.log('角色:', d.role);
  }
})
.catch(e => console.error('❌ API连接失败'));
```

然后按照以下清单逐一测试：

| # | 场景 | 操作 | 预期结果 |
|---|------|------|----------|
| 1 | 管理员登录 | admin/admin123 | 跳转dashboard |
| 2 | 侧边栏 | 点击菜单按钮 | 展开/收起 |
| 3 | 赛事管理 | 点击创建赛事 | 表单打开 |
| 4 | 选手管理 | 查看列表 | 正常显示 |
| 5 | 裁判登录 | judge1/judge123 | 登录成功 |
| 6 | 观众查看 | viewer/viewer123 | 只读模式 |
| 7 | 响应式布局 | 切换视口 | 无溢出 |
| 8 | 表单交互 | 填写表单 | 正常输入 |
| 9 | 错误处理 | 错误登录 | 提示错误 |

---

## 📋 快速验证清单

### 浏览器Console快速命令

在F12的Console中运行以下命令进行快速验证：

```javascript
// 1. 测试管理员登录
fetch('http://59.110.90.21/api/v1/auth/login', {
  method: 'POST',
  body: 'username=admin&password=admin123'
}).then(r=>r.json()).then(console.log);

// 2. 测试裁判登录
fetch('http://59.110.90.21/api/v1/auth/login', {
  method: 'POST',
  body: 'username=judge1&password=judge123'
}).then(r=>r.json()).then(console.log);

// 3. 测试观众登录
fetch('http://59.110.90.21/api/v1/auth/login', {
  method: 'POST',
  body: 'username=viewer&password=viewer123'
}).then(r=>r.json()).then(console.log);
```

---

## 🔍 检查页面元素

打开开发者工具的 **Elements** 标签，检查以下元素：

### 登录表单
- `input[placeholder="用户名"]`
- `input[placeholder="密码"]`
- `button:has-text("登 录")`

### 导航菜单
- `.header__toggle` 或 `.hamburger`
- `.sidebar` 或 `.el-menu`

### 页面内容
- 检查是否有 `404` 或错误提示
- 检查网络请求是否有红色失败项

---

## 📸 截图保存

发现问题时立即截图：

**Mac**: Cmd+Shift+4 (选择区域) / Cmd+Shift+3 (全屏)
**Windows**: Win+PrintScreen

---

## 📝 测试记录模板

测试完成后，请告诉我：

```
✅ 通过的场景:
1. [场景名称] - [简短说明]

❌ 失败的场景:
1. [场景名称] - [问题描述]
   - 操作步骤: [如何复现]
   - 预期结果: [应该怎样]
   - 实际结果: [实际怎样]
   - 截图: [附加截图]

💡 建议:
[任何改进建议]
```

---

## 🎯 测试通过标准

**9个场景全部 ✅ = 测试成功！**

如果有任何场景失败，请详细记录问题，我会帮你修复。

---

## 📞 技术支持

测试过程中遇到任何问题：
1. 截图保存
2. 记录控制台错误（F12 > Console）
3. 记录网络请求错误（F12 > Network）
4. 告诉我具体的错误信息

---

**立即开始测试！** 🚀

浏览器地址: http://59.110.90.21
