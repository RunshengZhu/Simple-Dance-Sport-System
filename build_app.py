#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
体育舞蹈赛事打分软件打包脚本
使用PyInstaller将Python程序打包成可执行文件
支持Windows和macOS平台
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def install_pyinstaller():
    """安装PyInstaller"""
    print("正在检查PyInstaller是否已安装...")
    try:
        import PyInstaller
        print(f"PyInstaller已安装，版本: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("PyInstaller未安装，正在安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller>=5.0.0"])
            print("PyInstaller安装成功")
            return True
        except subprocess.CalledProcessError:
            print("PyInstaller安装失败，请手动安装后重试")
            return False

def clean_build_files():
    """清理构建文件"""
    print("正在清理构建文件...")
    build_dirs = ["build", "dist", "*.spec"]
    
    for dir_pattern in build_dirs:
        if dir_pattern.endswith("*"):
            # 处理通配符模式
            for file in Path(".").glob(dir_pattern):
                if file.is_file():
                    try:
                        file.unlink()
                        print(f"已删除: {file}")
                    except Exception as e:
                        print(f"删除文件失败 {file}: {e}")
        else:
            # 处理目录
            if os.path.exists(dir_pattern):
                try:
                    if os.path.isdir(dir_pattern):
                        shutil.rmtree(dir_pattern)
                        print(f"已删除目录: {dir_pattern}")
                    else:
                        os.remove(dir_pattern)
                        print(f"已删除文件: {dir_pattern}")
                except Exception as e:
                    print(f"删除失败 {dir_pattern}: {e}")

def build_app():
    """使用PyInstaller打包应用"""
    # 确保PyInstaller已安装
    if not install_pyinstaller():
        return False
    
    # 清理旧的构建文件
    clean_build_files()
    
    # 获取当前平台
    current_platform = platform.system().lower()
    print(f"当前平台: {current_platform}")
    
    # 主程序入口
    main_script = "main.py"
    
    # 应用名称
    app_name = "dance_sport_app"
    
    # 构建PyInstaller命令
    pyinstaller_cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--onefile",           # 生成单个可执行文件
        "--windowed",           # 窗口模式，无控制台
        "--name", app_name,     # 应用名称
        "--add-data", "src/config.json:src",  # 包含配置文件
        "--clean",              # 清理临时文件
        main_script             # 主脚本
    ]
    
    # 根据平台添加特定选项
    if current_platform == "windows":
        # Windows特定选项
        pyinstaller_cmd.extend([
            "--icon", "",  # 可以添加图标文件路径
            "--version-file", "",  # 可以添加版本信息文件
        ])
    elif current_platform == "darwin":
        # macOS特定选项
        pyinstaller_cmd.extend([
            "--icon", "",  # 可以添加图标文件路径
            "--osx-bundle-identifier", "com.dancesport.app",
        ])
    
    print(f"执行打包命令: {' '.join(pyinstaller_cmd)}")
    
    try:
        # 执行PyInstaller命令
        subprocess.check_call(pyinstaller_cmd)
        print("\n✅ 打包成功！")
        
        # 显示输出文件位置
        if current_platform == "windows":
            output_file = os.path.join("dist", f"{app_name}.exe")
        else:  # macOS
            output_file = os.path.join("dist", f"{app_name}.app")
        
        if os.path.exists(output_file):
            print(f"输出文件: {os.path.abspath(output_file)}")
        else:
            print(f"输出文件可能在: {os.path.abspath('dist')}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 打包失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 打包过程中发生错误: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("体育舞蹈赛事打分软件打包脚本")
    print("=" * 60)
    
    # 检查是否在正确的目录
    if not os.path.exists("main.py"):
        print("错误: 请在ds-competition目录下运行此脚本")
        return 1
    
    # 检查requirements.txt是否存在
    if os.path.exists("requirements.txt"):
        print("正在检查依赖...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("依赖检查完成")
        except subprocess.CalledProcessError:
            print("警告: 依赖安装失败，可能影响打包结果")
    
    # 执行打包
    if build_app():
        print("\n🎉 打包完成！")
        print("你可以在dist目录中找到生成的可执行文件。")
        return 0
    else:
        print("\n❌ 打包失败，请检查错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
