#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛事管理选项卡模块
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import os
from datetime import datetime

from ..models.data_manager import data_manager
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger()


class EventManagementTab:
    """赛事管理选项卡类"""
    
    def __init__(self, parent, main_window):
        """初始化赛事管理选项卡"""
        self.parent = parent
        self.main_window = main_window
        self.logger = logger
        
        # 创建选项卡框架
        self.frame = ttk.Frame(parent)
        
        # 创建界面元素
        self.create_widgets()
        
        # 刷新数据
        self.refresh()
        
        self.logger.debug("赛事管理选项卡初始化完成")
    
    def create_widgets(self):
        """创建界面元素"""
        # 创建左右分区
        left_frame = ttk.Frame(self.frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        right_frame = ttk.Frame(self.frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 左侧：创建新赛事区域
        self.create_new_event_frame(left_frame)
        
        # 左侧下方：导出目录设置区域
        self.create_export_settings_frame(left_frame)
        
        # 右侧：打开现有赛事区域
        self.open_existing_event_frame(right_frame)
    
    def create_new_event_frame(self, parent):
        """创建新赛事区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="创建新赛事", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # 输入框架
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 赛事名称
        name_frame = ttk.Frame(input_frame)
        name_frame.pack(fill=tk.X, pady=5)
        ttk.Label(name_frame, text="赛事名称:").pack(side=tk.LEFT)
        self.event_name_entry = ttk.Entry(name_frame)
        self.event_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # 赛事日期
        date_frame = ttk.Frame(input_frame)
        date_frame.pack(fill=tk.X, pady=5)
        ttk.Label(date_frame, text="赛事日期:").pack(side=tk.LEFT)
        self.event_date_entry = ttk.Entry(date_frame)
        self.event_date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        # 设置默认日期为今天
        self.event_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        
        # 赛事地点
        location_frame = ttk.Frame(input_frame)
        location_frame.pack(fill=tk.X, pady=5)
        ttk.Label(location_frame, text="赛事地点:").pack(side=tk.LEFT)
        self.event_location_entry = ttk.Entry(location_frame)
        self.event_location_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # 创建按钮
        create_button = ttk.Button(
            parent, 
            text="创建赛事", 
            command=self.create_event
        )
        create_button.pack(pady=10)
    
    def open_existing_event_frame(self, parent):
        """打开现有赛事区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="打开现有赛事", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # 赛事列表框架
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建Treeview
        columns = ("name", "date", "location")
        self.event_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings")
        
        # 设置列标题
        self.event_tree.heading("#0", text="赛事名称")
        self.event_tree.heading("name", text="赛事名称")
        self.event_tree.heading("date", text="日期")
        self.event_tree.heading("location", text="地点")
        
        # 设置列宽
        self.event_tree.column("#0", width=0, stretch=False)  # 隐藏第一列
        self.event_tree.column("name", width=150)
        self.event_tree.column("date", width=100)
        self.event_tree.column("location", width=150)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.event_tree.yview)
        self.event_tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        self.event_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定双击事件
        self.event_tree.bind("<Double-1>", self.on_event_double_click)
        
        # 按钮框架
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)
        
        # 打开按钮
        open_button = ttk.Button(
            button_frame, 
            text="打开", 
            command=self.open_selected_event
        )
        open_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 删除按钮
        delete_button = ttk.Button(
            button_frame, 
            text="删除", 
            command=self.delete_selected_event
        )
        delete_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 刷新按钮
        refresh_button = ttk.Button(
            button_frame, 
            text="刷新", 
            command=self.refresh
        )
        refresh_button.pack(side=tk.LEFT)
    
    def refresh(self):
        """刷新赛事列表"""
        # 清空当前列表
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)
        
        # 获取所有赛事
        events = data_manager.get_all_events()
        
        # 添加到列表
        for event_name in events:
            try:
                # 尝试获取赛事信息
                event_file = data_manager.get_event_data_file(event_name)
                if os.path.exists(event_file):
                    import json
                    with open(event_file, 'r', encoding='utf-8') as f:
                        event_data = json.load(f)
                    
                    # 添加到树形控件
                    self.event_tree.insert(
                        "", 
                        tk.END, 
                        values=(
                            event_data.get("name", event_name),
                            event_data.get("date", ""),
                            event_data.get("location", "")
                        ),
                        tags=(event_name,)  # 使用标签存储事件名称
                    )
                else:
                    # 尝试使用旧格式文件路径
                    old_event_file = os.path.join(
                        data_manager._get_event_dir(event_name),
                        "event.json"
                    )
                    if os.path.exists(old_event_file):
                        import json
                        with open(old_event_file, 'r', encoding='utf-8') as f:
                            event_data = json.load(f)
                        
                        # 添加到树形控件
                        self.event_tree.insert(
                            "", 
                            tk.END, 
                            values=(
                                event_data.get("name", event_name),
                                event_data.get("date", ""),
                                event_data.get("location", "")
                            ),
                            tags=(event_name,)  # 使用标签存储事件名称
                        )
                    else:
                        # 如果文件不存在，也添加基本信息
                        self.event_tree.insert(
                            "", 
                            tk.END, 
                            values=(event_name, "", ""),
                            tags=(event_name,)
                        )
            except Exception as e:
                self.logger.error(f"读取赛事信息失败: {event_name}, {e}")
                # 即使读取失败，也添加基本信息
                self.event_tree.insert(
                    "", 
                    tk.END, 
                    values=(event_name, "", ""),
                    tags=(event_name,)
                )
        
        # 高亮当前打开的赛事
        if data_manager.current_event_name:
            for item in self.event_tree.get_children():
                tags = self.event_tree.item(item, "tags")
                if data_manager.current_event_name in tags:
                    self.event_tree.selection_set(item)
                    self.event_tree.see(item)
                    break
        
        # 更新导出目录显示
        self.update_export_directory_display()
    
    def create_event(self):
        """创建新赛事"""
        name = self.event_name_entry.get().strip()
        date = self.event_date_entry.get().strip()
        location = self.event_location_entry.get().strip()
        
        # 验证输入
        if not name:
            messagebox.showerror("错误", "请输入赛事名称")
            return
        
        if not date:
            messagebox.showerror("错误", "请输入赛事日期")
            return
        
        if not location:
            messagebox.showerror("错误", "请输入赛事地点")
            return
        
        # 创建赛事
        if data_manager.create_competition(name, date, location):
            messagebox.showinfo("成功", f"赛事 '{name}' 创建成功")
            
            # 清空输入框
            self.event_name_entry.delete(0, tk.END)
            self.event_location_entry.delete(0, tk.END)
            self.event_date_entry.delete(0, tk.END)
            self.event_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
            
            # 刷新列表
            self.refresh()
            
            # 更新主窗口显示
            self.main_window.update_current_event_display()
            
            # 刷新所有选项卡
            self.main_window.refresh_all_tabs()
            
            # 更新导出目录显示
            self.update_export_directory_display()
        else:
            messagebox.showerror("错误", "创建赛事失败，请检查输入信息")
    
    def open_selected_event(self):
        """打开选中的赛事"""
        selection = self.event_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个赛事")
            return
        
        # 获取选中的事件名称
        item = selection[0]
        tags = self.event_tree.item(item, "tags")
        if not tags:
            messagebox.showerror("错误", "无法获取赛事信息")
            return
        
        event_name = tags[0]
        
        # 打开赛事
        if data_manager.open_competition(event_name):
            messagebox.showinfo("成功", f"赛事 '{event_name}' 打开成功")
            
            # 更新主窗口显示
            self.main_window.update_current_event_display()
            
            # 刷新所有选项卡
            self.main_window.refresh_all_tabs()
            
            # 更新导出目录显示
            self.update_export_directory_display()
        else:
            messagebox.showerror("错误", "打开赛事失败")
    
    def on_event_double_click(self, event):
        """事件双击事件处理"""
        self.open_selected_event()
    
    def delete_selected_event(self):
        """删除选中的赛事"""
        selection = self.event_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个赛事")
            return
        
        # 获取选中的事件名称
        item = selection[0]
        tags = self.event_tree.item(item, "tags")
        if not tags:
            messagebox.showerror("错误", "无法获取赛事信息")
            return
        
        event_name = tags[0]
        
        # 确认删除
        if messagebox.askyesno(
            "确认删除", 
            f"确定要删除赛事 '{event_name}' 吗？\n\n此操作不可恢复！"
        ):
            # 删除赛事
            if data_manager.delete_competition(event_name):
                messagebox.showinfo("成功", f"赛事 '{event_name}' 删除成功")
                
                # 刷新列表
                self.refresh()
                
                # 更新主窗口显示
                self.main_window.update_current_event_display()
                
                # 刷新所有选项卡
                self.main_window.refresh_all_tabs()
                
                # 更新导出目录显示
                self.update_export_directory_display()
            else:
                messagebox.showerror("错误", "删除赛事失败")
    
    def create_export_settings_frame(self, parent):
        """创建导出设置区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="导出设置", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(20, 10))
        
        # 导出目录设置框架
        export_frame = ttk.Frame(parent)
        export_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 导出目录标签
        dir_label = ttk.Label(export_frame, text="导出目录:")
        dir_label.pack(anchor=tk.W, pady=(0, 5))
        
        # 导出目录显示
        self.export_dir_var = tk.StringVar()
        self.export_dir_label = ttk.Label(export_frame, textvariable=self.export_dir_var, width=40, wraplength=300)
        self.export_dir_label.pack(anchor=tk.W, fill=tk.X, pady=(0, 10))
        
        # 按钮框架
        button_frame = ttk.Frame(export_frame)
        button_frame.pack(fill=tk.X)
        
        # 选择目录按钮
        select_button = ttk.Button(
            button_frame, 
            text="选择目录", 
            command=self.select_export_directory
        )
        select_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 打开目录按钮
        open_button = ttk.Button(
            button_frame, 
            text="打开目录", 
            command=self.open_export_directory
        )
        open_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 重置为默认按钮
        reset_button = ttk.Button(
            button_frame, 
            text="重置为默认", 
            command=self.reset_export_directory
        )
        reset_button.pack(side=tk.LEFT)
        
        # 初始化导出目录显示
        self.update_export_directory_display()
    
    def update_export_directory_display(self):
        """根据当前赛事更新导出目录显示"""
        # 使用与get_events_dir方法相同的逻辑来获取基础导出目录
        base_export_dir = config.get_events_dir()
        
        if data_manager.current_competition and data_manager.current_event_name:
            # 如果有当前赛事，显示赛事特定的导出目录
            event_export_dir = os.path.join(base_export_dir, data_manager.current_event_name)
            self.export_dir_var.set(event_export_dir)
        else:
            # 如果没有当前赛事，显示基础导出目录
            self.export_dir_var.set(base_export_dir)
    
    def select_export_directory(self):
        """选择导出目录"""
        import shutil
        
        # 获取当前基础导出目录
        old_export_dir = config.get("export_dir", os.path.join(os.path.expanduser("~"), "DanceSportExports"))
        old_events_dir = config.get("events_dir")
        
        # 打开目录选择对话框
        new_directory = filedialog.askdirectory(
            title="选择导出目录",
            initialdir=old_export_dir
        )
        
        if new_directory:
            # 迁移数据
            migrated = False
            migrated_count = 0
            
            # 迁移赛事数据
            if old_events_dir and os.path.exists(old_events_dir) and os.listdir(old_events_dir):
                # 复制旧赛事目录下的所有赛事数据到新目录
                for event_name in os.listdir(old_events_dir):
                    old_event_path = os.path.join(old_events_dir, event_name)
                    new_event_path = os.path.join(new_directory, event_name)
                    if os.path.isdir(old_event_path):
                        # 如果目标目录已存在，先删除
                        if os.path.exists(new_event_path):
                            shutil.rmtree(new_event_path)
                        # 复制赛事数据
                        shutil.copytree(old_event_path, new_event_path)
                        migrated_count += 1
                        migrated = True
            
            # 迁移导出内容
            if old_export_dir and os.path.exists(old_export_dir) and os.listdir(old_export_dir):
                # 复制旧导出目录下的所有内容到新目录
                for item_name in os.listdir(old_export_dir):
                    old_item_path = os.path.join(old_export_dir, item_name)
                    new_item_path = os.path.join(new_directory, item_name)
                    if os.path.isdir(old_item_path):
                        # 如果目标目录已存在，先删除
                        if os.path.exists(new_item_path):
                            shutil.rmtree(new_item_path)
                        # 复制导出内容
                        shutil.copytree(old_item_path, new_item_path)
                        migrated_count += 1
                        migrated = True
                    else:
                        # 如果是文件，直接复制
                        if not os.path.exists(new_item_path):
                            shutil.copy2(old_item_path, new_item_path)
                            migrated_count += 1
                            migrated = True
            
            # 更新基础导出目录
            config.set("export_dir", new_directory)
            
            # 更新显示
            self.update_export_directory_display()
            
            # 如果有当前打开的赛事，创建赛事子目录结构
            if data_manager.current_competition and data_manager.current_event_name:
                # 确保基础目录存在
                if not os.path.exists(new_directory):
                    os.makedirs(new_directory)
                
                # 创建赛事子目录
                event_export_dir = os.path.join(new_directory, data_manager.current_event_name)
                if not os.path.exists(event_export_dir):
                    os.makedirs(event_export_dir)
                
                # 创建子目录结构
                subdirs = ['results_pdf', 'details_pdf', 'details_markdown']
                for subdir in subdirs:
                    subdir_path = os.path.join(event_export_dir, subdir)
                    if not os.path.exists(subdir_path):
                        os.makedirs(subdir_path)
            
            # 显示结果
            if migrated:
                messagebox.showinfo("成功", f"基础导出目录已更新为: {new_directory}\n已迁移 {migrated_count} 个项目到新目录")
            else:
                messagebox.showinfo("成功", f"基础导出目录已更新为: {new_directory}")
    
    def reset_export_directory(self):
        """重置导出目录为默认值"""
        default_dir = os.path.join(os.path.expanduser("~"), "DanceSportExports")
        config.set("export_dir", default_dir)
        
        # 更新显示
        self.update_export_directory_display()
        
        messagebox.showinfo("成功", f"导出目录已重置为默认值: {default_dir}")
    
    def open_export_directory(self):
        """打开导出目录"""
        import os
        import sys
        import subprocess
        
        # 获取当前显示的导出目录
        export_dir = self.export_dir_var.get()
        
        # 检查目录是否存在
        if not os.path.exists(export_dir):
            messagebox.showwarning("警告", f"目录不存在: {export_dir}")
            return
        
        try:
            # 根据不同系统调用不同的命令打开文件管理器
            if os.name == 'nt':  # Windows
                subprocess.Popen(['explorer.exe', export_dir])
            elif os.name == 'posix':  # macOS或Linux
                if sys.platform == 'darwin':  # macOS
                    subprocess.Popen(['open', export_dir])
                else:  # Linux
                    subprocess.Popen(['xdg-open', export_dir])
            messagebox.showinfo("成功", f"已打开目录: {export_dir}")
        except Exception as e:
            self.logger.error(f"打开目录失败: {e}")
            messagebox.showerror("错误", f"打开目录失败: {str(e)}")