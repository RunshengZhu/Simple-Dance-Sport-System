#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口模块
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
from datetime import datetime

from ..models.data_manager import data_manager
from ..utils.config import config
from ..utils.logger import get_logger
from .event_management_tab import EventManagementTab
from .data_import_tab import DataImportTab
from .schedule_management_tab import ScheduleManagementTab
from .window_utils import center_window

logger = get_logger()


class MainWindow:
    """主窗口类"""
    
    def __init__(self, root):
        """初始化主窗口"""
        self.root = root
        self.logger = logger
        
        # 设置窗口属性
        self.root.title(config.get("app_name", "体育舞蹈赛事独立打分软件"))
        
        # 设置窗口大小和位置
        window_size = config.get("ui.window_size", "1200x800")
        self.root.geometry(window_size)
        
        # 设置窗口最小尺寸
        self.root.minsize(1000, 600)
        
        # 设置窗口居中（如果配置为居中）
        if config.get("ui.window_position", "center") == "center":
            self.center_window()
        
        # 创建主框架
        self.create_main_frame()
        
        # 创建顶部标题区域
        self.create_header()
        
        # 创建选项卡
        self.create_notebook()
        
        # 加载当前打开的赛事
        self.load_current_event()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.logger.info("主窗口初始化完成")
    
    def center_window(self):
        """将窗口居中显示"""
        center_window(self.root)
    
    def create_main_frame(self):
        """创建主框架"""
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def create_header(self):
        """创建顶部标题区域"""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 左侧标题
        title_label = ttk.Label(
            header_frame, 
            text=config.get("app_name", "体育舞蹈赛事独立打分软件"),
            font=("TkDefaultFont", 16, "bold")
        )
        title_label.pack(side=tk.LEFT)
        
        # 右侧当前赛事信息
        self.current_event_label = ttk.Label(
            header_frame,
            text="未打开赛事",
            font=("TkDefaultFont", 10)
        )
        self.current_event_label.pack(side=tk.RIGHT)
    
    def create_notebook(self):
        """创建选项卡"""
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建各个选项卡
        self.event_management_tab = EventManagementTab(self.notebook, self)
        self.data_import_tab = DataImportTab(self.notebook, self)
        self.schedule_management_tab = ScheduleManagementTab(self.notebook, self)
        
        # 添加选项卡到notebook
        self.notebook.add(
            self.event_management_tab.frame, 
            text="赛事管理"
        )
        self.notebook.add(
            self.data_import_tab.frame, 
            text="数据导入"
        )
        self.notebook.add(
            self.schedule_management_tab.frame, 
            text="赛程管理"
        )
        
        # 绑定选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
    
    def on_tab_changed(self, event):
        """选项卡切换事件处理"""
        selected_tab = event.widget.tab('current')['text']
        self.logger.debug(f"切换到选项卡: {selected_tab}")
        
        # 通知当前选项卡刷新数据
        if selected_tab == "赛事管理":
            self.event_management_tab.refresh()
        elif selected_tab == "数据导入":
            self.data_import_tab.refresh()
        elif selected_tab == "赛程管理":
            self.schedule_management_tab.refresh()
    
    def load_current_event(self):
        """加载当前打开的赛事"""
        current_event_name = config.get("current_event")
        if current_event_name and data_manager.open_competition(current_event_name):
            self.update_current_event_display()
            self.logger.info(f"自动加载赛事: {current_event_name}")
        else:
            self.logger.info("没有当前打开的赛事")
    
    def update_current_event_display(self):
        """更新当前赛事显示"""
        if data_manager.current_competition:
            event_name = data_manager.current_competition.name
            event_date = data_manager.current_competition.date
            self.current_event_label.config(
                text=f"当前赛事: {event_name} ({event_date})"
            )
        else:
            self.current_event_label.config(text="未打开赛事")
    
    def refresh_all_tabs(self):
        """刷新所有选项卡"""
        self.event_management_tab.refresh()
        self.data_import_tab.refresh()
        self.schedule_management_tab.refresh()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        if messagebox.askokcancel("退出", "确定要退出体育舞蹈赛事独立打分软件吗？"):
            self.logger.info("体育舞蹈赛事独立打分软件正常退出")
            self.root.destroy()