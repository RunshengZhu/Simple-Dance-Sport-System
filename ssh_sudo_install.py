#!/usr/bin/env python3
"""
使用paramiko通过SSH执行sudo命令 - 交互式版本
"""

import os
import sys
import time
import paramiko

def ssh_sudo_install():
    # SSH配置
    hostname = "59.110.90.21"
    port = 22
    username = "sport-coder"
    password = os.environ.get('SSH_PASSWORD', os.environ.get('SUDO_PASSWORD', ''))
    
    if not password:
        print("请设置SSH_PASSWORD或SUDO_PASSWORD环境变量")
        print("示例: SSH_PASSWORD=xxx python3 ssh_sudo_install.py")
        sys.exit(1)
    
    # 创建SSH客户端
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print(f"连接到 {hostname}...")
    ssh.connect(hostname, port=port, username=username, password=password)
    
    # 先检查是否需要密码
    print("测试sudo权限...")
    stdin, stdout, stderr = ssh.exec_command("sudo -n true 2>&1")
    result = stdout.read().decode() + stderr.read().decode()
    
    if 'password' in result.lower():
        print("需要sudo密码，将通过交互方式执行...")
        needs_password = True
    else:
        print("无需密码")
        needs_password = False
    
    # 使用transport创建交互式会话
    transport = ssh.get_transport()
    session = transport.open_session()
    session.setblocking(0)
    
    # 获取pseudo-tty
    session.get_pty()
    
    # 启动shell
    shell = ssh.invoke_shell()
    shell.setblocking(0)
    
    time.sleep(1)
    
    # 清空初始输出
    shell.recv(1024)
    
    # 发送apt-get update命令
    if needs_password:
        cmd = f"echo '{password}' | sudo -S apt-get update\n"
    else:
        cmd = "sudo apt-get update\n"
    
    print("执行 apt-get update...")
    shell.send(cmd)
    time.sleep(15)
    
    # 读取输出
    output = ""
    while True:
        try:
            data = shell.recv(1024)
            if data:
                output += data.decode()
            else:
                break
        except:
            break
        time.sleep(0.5)
    
    print("更新完成")
    
    # 发送安装命令
    if needs_password:
        cmd = f"echo '{password}' | sudo -S DEBIAN_FRONTEND=noninteractive apt-get install -y libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2\n"
    else:
        cmd = "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2\n"
    
    print("安装依赖库...")
    shell.send(cmd)
    
    # 等待安装完成
    for i in range(60):  # 最多等待60秒
        time.sleep(1)
        try:
            data = shell.recv(4096)
            if data:
                output += data.decode()
                # 检查是否完成
                if 'Setting up' in output or 'is already the newest' in output or 'unpacking' in output:
                    print(f"安装进度: {i+1}/60秒")
        except:
            break
    
    print("\n安装命令已发送")
    
    shell.close()
    ssh.close()
    
    print("脚本执行完成。请手动检查安装结果。")

if __name__ == "__main__":
    ssh_sudo_install()
