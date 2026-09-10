# 体育舞蹈赛事打分软件打包说明

## 脚本功能

- 📦 **跨平台支持**：支持Windows和macOS平台
- 🤖 **自动依赖管理**：自动安装PyInstaller和项目依赖
- 🧹 **自动清理**：打包前自动清理旧的构建文件
- 🎯 **单文件输出**：生成单个可执行文件，便于分发
- 📋 **资源文件处理**：自动包含配置文件等资源

## 环境要求

### 通用要求
- Python 3.8+ 
- pip 20.0+

### Windows平台额外要求
- Visual Studio C++ Build Tools
- Windows 10+ 

### macOS平台额外要求
- Xcode Command Line Tools
- macOS 10.15+ (Catalina)

## 使用方法

### 1. 准备工作

确保你在正确的目录中：
```bash
cd ds-competition
```

### 2. 安装项目依赖（可选）

```bash
pip install -r requirements.txt
```

### 3. 运行打包脚本

```bash
python build_app.py
```

### 4. 查看输出结果

打包成功后，可执行文件将生成在 `dist/` 目录中：

- **Windows**：`dist/dance_sport_app.exe`
- **macOS**：`dist/dance_sport_app.app`

## 打包流程

1. **检查环境**：验证Python和pip版本
2. **安装依赖**：自动安装PyInstaller（如果未安装）
3. **清理旧文件**：删除之前的构建文件
4. **执行打包**：使用PyInstaller生成可执行文件
5. **输出结果**：显示打包成功信息和输出文件位置

## 平台注意事项

### Windows平台
- 打包生成的`.exe`文件可以直接双击运行
- 首次运行可能会被Windows Defender拦截，需要允许运行
- 建议使用32位Python打包，以兼容更多Windows版本

### macOS平台
- 打包生成的`.app`文件是一个应用包
- 首次运行需要右键点击并选择"打开"，以绕过Gatekeeper验证
- 可以使用`codesign`命令对应用进行签名（可选）

## 自定义配置

### 修改应用名称

编辑`build_app.py`文件中的`app_name`变量：

```python
app_name = "dance_sport_app"  # 修改为你想要的应用名称
```

### 添加应用图标

1. 准备图标文件：
   - Windows：`.ico`格式
   - macOS：`.icns`格式

2. 修改`build_app.py`文件中的图标路径：

```python
# Windows平台
"--icon", "path/to/icon.ico",

# macOS平台  
"--icon", "path/to/icon.icns",
```

### 包含更多资源文件

在`build_app.py`文件中添加`--add-data`参数：

```python
pyinstaller_cmd.extend([
    "--add-data", "src/config.json:src",
    "--add-data", "assets/:assets",  # 添加更多资源目录
])
```

## 常见问题及解决方法

### 1. PyInstaller安装失败

**问题**：`PyInstaller安装失败，请手动安装后重试`

**解决方法**：
```bash
pip install pyinstaller>=5.0.0 --user
```

### 2. 打包过程中缺少模块

**问题**：打包时提示缺少某个模块

**解决方法**：
```bash
pip install 缺少的模块名称
python build_app.py
```

### 3. 应用运行时提示缺少配置文件

**问题**：运行打包后的应用时，提示找不到`config.json`

**解决方法**：确保`build_app.py`中包含了正确的`--add-data`参数

### 4. Windows平台打包后应用体积过大

**问题**：生成的`.exe`文件体积太大

**解决方法**：
- 使用虚拟环境进行打包
- 清理不必要的依赖
- 使用UPX压缩（需要安装UPX）

## 清理构建文件

如果需要手动清理构建文件，可以运行：

```bash
# 删除build目录
rm -rf build

# 删除dist目录
rm -rf dist

# 删除spec文件
rm *.spec
```

或者直接重新运行打包脚本，它会自动清理旧文件。

## 分发建议

### Windows平台
1. 可以将`.exe`文件直接分发给用户
2. 建议创建一个压缩包，包含应用程序和使用说明
3. 可以使用Inno Setup等工具创建安装程序

### macOS平台
1. 可以将`.app`文件直接分发给用户
2. 建议创建DMG镜像文件，便于用户安装
3. 对于大规模分发，建议进行代码签名和公证

## 技术说明

### 打包工具

使用[PyInstaller](https://pyinstaller.org/)进行打包，它可以将Python应用程序及其所有依赖打包成单个可执行文件。

### 打包原理

1. **分析依赖**：PyInstaller分析Python脚本的依赖关系
2. **收集文件**：收集所有必要的Python模块和资源文件
3. **创建可执行文件**：生成平台特定的可执行文件
4. **压缩资源**：将所有资源压缩到可执行文件中

### 输出文件结构

```
dist/
├── dance_sport_app.exe  # Windows可执行文件
└── dance_sport_app.app  # macOS应用包
```

## 版本历史

### v1.0.0 (2025-12-04)
- 初始版本
- 支持Windows和macOS平台
- 自动依赖管理
- 单文件输出

## 联系方式

如有问题或建议，请联系开发团队。

---

**提示**：打包后的应用程序包含了所有必要的依赖，用户无需安装Python或任何其他软件即可运行。
