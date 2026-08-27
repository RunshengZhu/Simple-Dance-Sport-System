#!/usr/bin/env python3
import subprocess
import sys
import os

def run_ssh_command(cmd, password=None):
    """通过SSH执行命令，支持sudo"""
    ssh_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null']
    
    if password:
        ssh_cmd.extend(['-o', f'PasswordAuthentication={password}'])
    
    ssh_cmd.append(f'sport-coder@59.110.90.21')
    ssh_cmd.append(cmd)
    
    result = subprocess.run(ssh_cmd, capture_output=True, text=True)
    return result

# 检查是否可以无密码sudo
result = run_ssh_command('sudo -n apt-get update 2>&1 | head -5')
print("测试sudo权限...")
print(result.stdout or result.stderr)

if 'password' in (result.stdout + result.stderr).lower():
    print("需要密码，但用户说具备管理员权限，请手动执行以下命令：")
    print("ssh sport-coder@59.110.90.21")
    print("sudo apt-get update && sudo apt-get install -y libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2")
else:
    print("可以无密码sudo，继续安装依赖...")
    
    install_cmd = 'sudo apt-get update && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2'
    result = run_ssh_command(install_cmd)
    print(result.stdout)
    print(result.stderr)
