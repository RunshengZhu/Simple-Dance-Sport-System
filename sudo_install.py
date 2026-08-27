#!/usr/bin/env python3
import os
import sys
import pexpect

def run_with_sudo():
    # 使用pexpect创建带有伪终端的SSH连接
    child = pexpect.spawn(
        'ssh', 
        ['sport-coder@59.110.90.21', 'sudo', 'apt-get', 'update'],
        encoding='utf-8'
    )
    
    # 设置超时
    child.timeout = 30
    
    try:
        # 等待密码提示
        i = child.expect(['password for', pexpect.TIMEOUT, pexpect.EOF])
        
        if i == 0:
            print("需要sudo密码...")
            # 读取密码
            password = os.environ.get('SUDO_PASSWORD', '')
            if not password:
                print("请设置SUDO_PASSWORD环境变量")
                sys.exit(1)
            
            # 发送密码
            child.sendline(password)
            
            # 等待命令完成
            child.expect(pexpect.EOF, timeout=120)
            print(child.before)
            print("apt-get update 完成")
        else:
            print("无需密码或超时")
            print(child.before)
            
    except pexpect.TIMEOUT:
        print("命令执行超时")
        print(child.before)
    except Exception as e:
        print(f"错误: {e}")
    finally:
        child.close()

if __name__ == "__main__":
    run_with_sudo()
