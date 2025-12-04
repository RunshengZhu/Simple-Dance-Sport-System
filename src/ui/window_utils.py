#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
窗口工具模块
"""

import tkinter as tk


def center_window(window, parent=None):
    """
    将窗口居中显示
    
    Args:
        window: 要居中的窗口对象
        parent: 父窗口对象，如果提供则相对于父窗口居中，否则相对于屏幕居中
    """
    window.update_idletasks()
    
    if parent and parent.winfo_exists():
        # 相对于父窗口居中
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        
        x = parent_x + (parent_width // 2) - (window_width // 2)
        y = parent_y + (parent_height // 2) - (window_height // 2)
    else:
        # 相对于屏幕居中
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        
        x = (window.winfo_screenwidth() // 2) - (window_width // 2)
        y = (window.winfo_screenheight() // 2) - (window_height // 2)
    
    # 确保窗口不会超出屏幕边界
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    if x + window_width > screen_width:
        x = screen_width - window_width
    if y + window_height > screen_height:
        y = screen_height - window_height
    
    window.geometry(f"+{x}+{y}")


def create_centered_dialog(parent, title, width=400, height=300, resizable=False):
    """
    创建一个居中的对话框
    
    Args:
        parent: 父窗口对象
        title: 对话框标题
        width: 对话框宽度
        height: 对话框高度
        resizable: 是否可调整大小
        
    Returns:
        创建的对话框对象
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry(f"{width}x{height}")
    
    if not resizable:
        dialog.resizable(False, False)
    
    # 使对话框居中
    dialog.transient(parent)
    dialog.grab_set()
    center_window(dialog, parent)
    
    return dialog