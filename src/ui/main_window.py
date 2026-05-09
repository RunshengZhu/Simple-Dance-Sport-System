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
from .components.unit_ranking_panel import UnitRankingWindow

logger = get_logger()

# Store references to unit ranking windows
_unit_ranking_windows = []


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
        
        # 创建菜单栏
        self.create_menu_bar()
        
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
    
    def create_menu_bar(self):
        """创建菜单栏"""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        tools_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="工具", menu=tools_menu)
        
        tools_menu.add_command(label="设置奖项得分", command=self.open_award_points_dialog)
        tools_menu.add_command(label="单位总分排名", command=self.open_unit_ranking)
        tools_menu.add_separator()
        tools_menu.add_command(label="刷新总分", command=self.refresh_unit_points)
    
    def open_award_points_dialog(self):
        """打开奖项得分设置对话框"""
        from .components.award_points_dialog import BatchAwardPointsDialog
        
        if not data_manager.current_competition:
            messagebox.showwarning("警告", "请先打开一个赛事")
            return
        
        events = []
        for event in data_manager.current_competition.events:
            events.append({"id": event.id, "name": event.name})
        
        if not events:
            messagebox.showinfo("提示", "当前赛事没有场次")
            return
        
        def on_apply(configs):
            for event_id, config in configs.items():
                data_manager.save_award_config(event_id, config)
            messagebox.showinfo("成功", f"已保存 {len(configs)} 个场次的奖项得分配置")
        
        dialog = BatchAwardPointsDialog(self.root, events, on_apply=on_apply)
        dialog.show()
    
    def open_unit_ranking(self):
        """打开单位总分排名窗口"""
        global _unit_ranking_windows
        
        if not data_manager.current_competition:
            messagebox.showwarning("警告", "请先打开一个赛事")
            return
        
        window = UnitRankingWindow(self.root, data_manager=data_manager)
        _unit_ranking_windows.append(window)
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_unit_ranking_window(window))
    
    def _close_unit_ranking_window(self, window):
        """关闭单位总分排名窗口"""
        global _unit_ranking_windows
        if window in _unit_ranking_windows:
            _unit_ranking_windows.remove(window)
        window.destroy()
    
    def refresh_unit_points(self):
        """刷新单位总分"""
        for window in _unit_ranking_windows:
            if hasattr(window, 'refresh'):
                window.refresh()
        
        if not _unit_ranking_windows:
            data_manager.calculate_unit_points()
            messagebox.showinfo("成功", "单位总分已刷新")
    
    def on_closing(self):
        """窗口关闭事件处理"""
        if messagebox.askokcancel("退出", "确定要退出体育舞蹈赛事独立打分软件吗？"):
            self.logger.info("体育舞蹈赛事独立打分软件正常退出")
            self.root.destroy()