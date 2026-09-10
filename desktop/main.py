#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
体育舞蹈赛事独立打分软件
主程序入口文件
"""

import sys
import os
import logging
import tkinter as tk
from tkinter import messagebox
import traceback

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ui.main_window import MainWindow
from src.utils.config import Config
from src.utils.logger import setup_logger
from src.utils import schedule_manager, scoring_input_manager, results_view_manager


def main():
    """主程序入口函数"""
    try:
        # 设置日志
        logger = setup_logger()
        logger.info("体育舞蹈赛事独立打分软件启动")
        
        # 初始化赛程管理器
        schedule_manager.initialize()
        logger.info("赛程管理器初始化完成")
        
        # 初始化评分输入管理器
        scoring_input_manager.initialize()
        logger.info("评分输入管理器初始化完成")
        
        # 初始化结果查看管理器
        results_view_manager.initialize()
        logger.info("结果查看管理器初始化完成")
        
        # 创建主窗口
        root = tk.Tk()
        app = MainWindow(root)
        
        # 设置窗口关闭事件
        def on_closing():
            if messagebox.askokcancel("退出", "确定要退出体育舞蹈赛事独立打分软件吗？"):
                logger.info("体育舞蹈赛事独立打分软件正常退出")
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # 启动主循环
        root.mainloop()
        
    except Exception as e:
        error_msg = f"程序启动失败: {str(e)}\n\n详细错误信息:\n{traceback.format_exc()}"
        logging.error(error_msg)
        if 'root' in locals():
            messagebox.showerror("启动错误", error_msg)
        else:
            print(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()