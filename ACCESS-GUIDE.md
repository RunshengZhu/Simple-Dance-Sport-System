# 📋 本地开发环境访问指南

## 🔧 当前服务状态

| 服务 | 状态 | 地址 |
|------|------|------|
| 后端服务 | ✅ 运行中 | http://127.0.0.1:8000 |
| 前端服务 | ✅ 运行中 | http://localhost:3000 |

## 🌐 如何正确访问

### 方法1: 本地访问（推荐）
打开浏览器访问：
```
http://localhost:3000
```

### 方法2: 局域网访问（手机测试）
1. 找到您电脑的局域网IP地址：
   - macOS/Linux: 在终端执行 `ifconfig | grep inet`
   - Windows: 在命令提示符执行 `ipconfig`
2. 手机和电脑连接到同一WiFi
3. 手机浏览器访问：
   ```
   http://<您的电脑IP>:3000
   ```
   例如：`http://192.168.1.100:3000`

## 🔑 登录账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 裁判1 | judge1 | judge123 |
| 裁判2 | judge2 | judge123 |
| 裁判3 | judge3 | judge123 |
| 裁判4 | judge4 | judge123 |
| 裁判5 | judge5 | judge123 |
| 观众 | viewer | viewer123 |

## 🚫 为什么会访问到 59.110.90.21？

从您的截图看到请求发送到了 `http://59.110.90.21`，这是因为：

1. **浏览器缓存了旧的代码**
2. **可能访问了线上部署版本**
3. **DNS缓存问题**

### 解决方案：

#### 1. 清除浏览器缓存
- **Chrome**: Ctrl+Shift+Delete → 选择"缓存图片和文件" → 删除
- **Safari**: 偏好设置 → 隐私 → 管理网站数据 → 删除所有

#### 2. 强制刷新页面
- Windows/Linux: Ctrl+Shift+R
- macOS: Cmd+Shift+R

#### 3. 确保访问正确地址
请确认地址栏显示的是：
```
http://localhost:3000
```
而不是 `http://59.110.90.21`

## 🧪 测试步骤

1. **打开浏览器** → 访问 `http://localhost:3000`
2. **清除缓存** → Ctrl+Shift+Delete
3. **强制刷新** → Ctrl+Shift+R (或 Cmd+Shift+R)
4. **尝试登录**:
   - 用户名: admin
   - 密码: admin123
5. **观察**: 应该跳转到首页，不再跳回登录页

## 📝 测试验证

如果登录成功，您应该看到：
- 左侧菜单栏（赛事管理等）
- 顶部显示用户名
- 首页仪表板内容

## 🔍 问题排查

如果仍然有问题，请按以下步骤检查：

### 步骤1: 检查前端服务是否正常
```bash
# 在终端查看服务状态
# 应该显示: VITE v5.4.21  ready in 645 ms
# ➜  Local:   http://localhost:3000/
```

### 步骤2: 检查后端服务是否正常
```bash
# 打开新终端执行
curl http://127.0.0.1:8000/api/v1/auth/login \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

正常应该返回包含 `access_token` 的JSON。

### 步骤3: 检查浏览器控制台
按 F12 打开开发者工具，查看：
- **Network** 标签: 检查 `/api/v1/auth/login` 请求的状态码
- **Console** 标签: 查看是否有错误信息

## 💡 关键配置说明

### Vite代理配置
```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true
    }
  }
}
```

这会将所有 `/api` 请求转发到本地后端服务。

### API基础路径
```typescript
// src/api/request.ts
const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
```

没有设置环境变量时，默认使用 `/api/v1`，通过Vite代理转发。

## 📱 移动端测试注意事项

1. 确保手机和电脑在**同一WiFi网络**
2. 使用**电脑的局域网IP**访问（不是localhost）
3. 示例：`http://192.168.1.100:3000`
4. 首次访问可能需要允许不安全连接（HTTP）

## 🛠️ 重启服务（如果需要）

如果服务异常，可以重启：

```bash
# 停止当前服务（Ctrl+C）

# 重启后端
cd web/backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 重启前端（新终端）
cd web/frontend
npm run dev
```

---

**总结**: 问题是浏览器访问了错误的地址。请确保访问 `http://localhost:3000` 并清除缓存！

如果还有问题，请提供新的截图或错误信息，我会继续帮您排查！
