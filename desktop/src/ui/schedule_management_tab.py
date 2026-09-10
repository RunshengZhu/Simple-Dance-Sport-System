#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛程管理选项卡模块
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
from ..models.data_manager import data_manager
from ..models.data_models import Event, Dance, ScoringType, EventStatus
from ..utils.logger import get_logger
from .window_utils import center_window

logger = get_logger()


class ScheduleManagementTab:
    """赛程管理选项卡类"""
    
    def __init__(self, parent, main_window):
        """初始化赛程管理选项卡"""
        self.parent = parent
        self.main_window = main_window
        self.logger = logger
        
        # 初始化管理器
        self.event_manager = data_manager
        from ..utils.results_view_manager import results_view_manager
        self.results_view_manager = results_view_manager
        
        # 创建选项卡框架
        self.frame = ttk.Frame(parent)
        
        # 创建界面元素
        self.create_widgets()
        
        # 刷新数据
        self.refresh()
        
        self.logger.debug("赛程管理选项卡初始化完成")
    
    def create_widgets(self):
        """创建界面元素"""
        # 创建左右分区
        main_paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # 左侧：场次列表区域
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)
        
        # 右侧：分为上下两个区域
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        # 创建左侧内容
        self.create_left_frame(left_frame)
        
        # 创建右侧上下分区
        right_paned = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)
        
        # 右上：参赛选手列表区域
        competitors_frame = ttk.Frame(right_paned)
        right_paned.add(competitors_frame, weight=1)
        
        # 右下：结果查看区域
        results_frame = ttk.Frame(right_paned)
        right_paned.add(results_frame, weight=1)
        
        # 创建参赛选手列表内容
        self.create_competitors_list_frame(competitors_frame)
        
        # 创建结果查看内容
        self.create_right_frame(results_frame)
    
    def create_left_frame(self, parent):
        """创建左侧场次列表区域"""
        # 上部：操作按钮区域
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 标题
        title_label = ttk.Label(
            action_frame, 
            text="赛程管理", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # 按钮框架
        button_frame = ttk.Frame(action_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 添加场次按钮
        add_event_button = ttk.Button(
            button_frame, 
            text="添加场次", 
            command=self.add_event
        )
        add_event_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 编辑场次按钮
        edit_event_button = ttk.Button(
            button_frame, 
            text="编辑场次", 
            command=self.edit_event
        )
        edit_event_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 删除场次按钮
        delete_event_button = ttk.Button(
            button_frame, 
            text="删除场次", 
            command=self.delete_event
        )
        delete_event_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 开始评分按钮
        start_scoring_button = ttk.Button(
            button_frame, 
            text="开始评分", 
            command=self.start_scoring
        )
        start_scoring_button.pack(side=tk.LEFT, padx=(0, 5))
        

        
        # 状态标签
        self.status_label = ttk.Label(action_frame, text="")
        self.status_label.pack(pady=(0, 10))
        
        # 下部：场次列表区域
        self.create_event_list_frame(parent)
    
    def create_right_frame(self, parent):
        """创建右侧结果查看区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="结果查看", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # 结果类型选择
        result_type_frame = ttk.Frame(parent)
        result_type_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(result_type_frame, text="结果类型:").pack(side=tk.LEFT, padx=(0, 5))
        self.result_type_var = tk.StringVar(value="综合结果")
        result_type_combo = ttk.Combobox(
            result_type_frame,
            textvariable=self.result_type_var,
            values=["分舞种结果", "综合结果"],
            state="readonly",
            width=15
        )
        result_type_combo.pack(side=tk.LEFT, padx=(0, 10))
        result_type_combo.bind("<<ComboboxSelected>>", self.on_result_type_changed)
        
        # 舞种选择（仅在选择"舞种结果"时显示）
        self.dance_frame = ttk.Frame(parent)
        self.dance_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(self.dance_frame, text="舞种:").pack(side=tk.LEFT, padx=(0, 5))
        self.dance_var = tk.StringVar()
        self.dance_combo = ttk.Combobox(
            self.dance_frame,
            textvariable=self.dance_var,
            state="readonly",
            width=15
        )
        self.dance_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.dance_combo.bind("<<ComboboxSelected>>", self.on_dance_changed)
        
        # 结果表格
        results_frame = ttk.Frame(parent)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建Treeview
        self.results_tree = ttk.Treeview(results_frame)
        
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        h_scrollbar = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 布局
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # 配置行权重和列权重
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        
        # 绑定选择事件
        self.results_tree.bind("<<TreeviewSelect>>", self.on_result_select)
        
        # 操作按钮
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)
        
        # 导出结果按钮
        export_button = ttk.Button(
            button_frame,
            text="导出结果",
            command=self.export_results
        )
        export_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 导出明细按钮
        export_detail_button = ttk.Button(
            button_frame,
            text="导出明细",
            command=self.export_detailed_results
        )
        export_detail_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 导出Markdown明细按钮
        export_markdown_button = ttk.Button(
            button_frame,
            text="导出Markdown明细",
            command=self.export_markdown_results
        )
        export_markdown_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 确认本场晋级信息按钮
        confirm_current_advancement_button = ttk.Button(
            button_frame,
            text="确认本场晋级信息",
            command=self.show_current_advancement_confirmation
        )
        confirm_current_advancement_button.pack(side=tk.LEFT)
        
        # 保存按钮框架引用
        self.results_button_frame = button_frame
        
        # 初始化结果表格
        self.update_results_table()
        
        # 初始隐藏舞种选择
        self.dance_frame.pack_forget()
    
    def create_competitors_list_frame(self, parent):
        """创建参赛选手列表区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="参赛选手列表", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # 选手表格框架
        competitors_table_frame = ttk.Frame(parent)
        competitors_table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建Treeview
        self.competitors_tree = ttk.Treeview(competitors_table_frame)
        
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(competitors_table_frame, orient=tk.VERTICAL, command=self.competitors_tree.yview)
        h_scrollbar = ttk.Scrollbar(competitors_table_frame, orient=tk.HORIZONTAL, command=self.competitors_tree.xview)
        self.competitors_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 设置列
        self.competitors_tree["columns"] = ("competitor_number", "name", "team")
        self.competitors_tree.column("#0", width=0, stretch=tk.NO)
        self.competitors_tree.column("competitor_number", anchor=tk.CENTER, width=80, minwidth=80, stretch=tk.NO)
        self.competitors_tree.column("name", anchor=tk.W, width=200)
        self.competitors_tree.column("team", anchor=tk.W, width=150)
        
        # 设置列标题
        self.competitors_tree.heading("competitor_number", text="背番号")
        self.competitors_tree.heading("name", text="选手姓名")
        self.competitors_tree.heading("team", text="所属团队")
        
        # 布局
        self.competitors_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # 配置行权重和列权重
        competitors_table_frame.grid_rowconfigure(0, weight=1)
        competitors_table_frame.grid_columnconfigure(0, weight=1)
        
        # 操作按钮
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)
        
        # 确认前置晋级信息按钮
        advancement_button = ttk.Button(
            button_frame,
            text="确认前置晋级信息",
            command=self.show_previous_advancement_confirmation
        )
        advancement_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 导出评分表按钮
        export_scoring_sheet_button = ttk.Button(
            button_frame,
            text="导出评分表",
            command=self.export_scoring_sheet
        )
        export_scoring_sheet_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 导出pdf评分表按钮
        export_pdf_scoring_sheet_button = ttk.Button(
            button_frame,
            text="导出pdf评分表",
            command=self.export_pdf_scoring_sheet
        )
        export_pdf_scoring_sheet_button.pack(side=tk.LEFT)
        
        # 保存按钮框架引用
        self.competitors_button_frame = button_frame
        
        # 初始化选手表格
        self.update_competitors_table()
    
    def create_event_list_frame(self, parent):
        """创建场次列表区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="场次列表", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 5))
        
        # 表格框架
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview
        self.event_tree = ttk.Treeview(table_frame)
        
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.event_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.event_tree.xview)
        self.event_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 布局
        self.event_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # 配置行权重和列权重
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # 绑定双击事件和选择事件
        self.event_tree.bind("<Double-1>", self.on_event_double_click)
        self.event_tree.bind("<<TreeviewSelect>>", self.on_event_select)
        
        # 右键菜单
        self.context_menu = tk.Menu(self.event_tree, tearoff=0)
        self.context_menu.add_command(label="编辑场次", command=self.edit_event)
        self.context_menu.add_command(label="删除场次", command=self.delete_event)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="开始评分", command=self.start_scoring)
        
        self.event_tree.bind("<Button-3>", self.show_context_menu)
    
    def refresh(self):
        """刷新场次列表"""
        # 清空当前表格
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)
        
        # 检查是否有打开的赛事
        if not data_manager.current_competition:
            return
        
        # 设置列
        self.event_tree["columns"] = ("id", "name", "project_id", "round", "scoring_type", "dances", "advancement_count", "status")
        self.event_tree.heading("#0", text="")
        self.event_tree.heading("id", text="场次ID")
        self.event_tree.heading("name", text="场次名称")
        self.event_tree.heading("project_id", text="项目编号")
        self.event_tree.heading("round", text="轮次")
        self.event_tree.heading("scoring_type", text="评分类型")
        self.event_tree.heading("dances", text="舞种")
        self.event_tree.heading("advancement_count", text="晋级/录取")
        self.event_tree.heading("status", text="状态")
        
        self.event_tree.column("#0", width=0, stretch=False)
        self.event_tree.column("id", width=100)
        self.event_tree.column("name", width=150)
        self.event_tree.column("project_id", width=100)
        self.event_tree.column("round", width=100)
        self.event_tree.column("scoring_type", width=100)
        self.event_tree.column("dances", width=150)
        self.event_tree.column("advancement_count", width=100)
        self.event_tree.column("status", width=100)
        
        # 添加数据
        for event_id, event in data_manager.current_competition.events.items():
            # 格式化舞种
            dances_str = ", ".join([dance.name for dance in event.dances])
            
            # 格式化状态
            status_str = event.status.value
            
            # 获取晋级/录取数量
            advancement_count = getattr(event, 'advancement_count', 0)
            
            self.event_tree.insert(
                "", 
                tk.END, 
                values=(
                    event_id,
                    event.name,
                    event.project_id,
                    event.round,
                    event.scoring_type.value,
                    dances_str,
                    advancement_count,
                    status_str
                )
            )
    
    def on_event_double_click(self, event):
        """场次双击事件处理"""
        self.start_scoring()
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        # 选择当前项
        item = self.event_tree.identify_row(event.y)
        if item:
            self.event_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def get_selected_event_id(self):
        """获取选中的场次ID"""
        selection = self.event_tree.selection()
        if not selection:
            return None
        
        item = selection[0]
        values = self.event_tree.item(item, "values")
        if not values:
            return None
        
        return values[0]  # 第一列是场次ID
    
    def add_event(self):
        """添加场次"""
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先创建或打开一个赛事")
            return
        
        # 创建添加场次对话框
        dialog = EventDialog(self.parent, title="添加场次")
        result = dialog.show()
        
        if result:
            event_id, name, project_id, round, scoring_type, dances, advancement_count = result
            
            # 创建场次
            event = Event(
                id=event_id,
                name=name,
                project_id=project_id,
                round=round,
                scoring_type=scoring_type,
                dances=dances,
                advancement_count=advancement_count
            )
            
            # 添加场次
            if data_manager.add_event(event):
                self.status_label.config(text=f"成功添加场次: {event_id}")
                self.refresh()
            else:
                messagebox.showerror("错误", f"添加场次失败: 场次ID {event_id} 已存在")
    
    def edit_event(self):
        """编辑场次"""
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先创建或打开一个赛事")
            return
        
        # 获取选中的场次ID
        event_id = self.get_selected_event_id()
        if not event_id:
            messagebox.showwarning("提示", "请先选择一个场次")
            return
        
        # 获取场次
        event = data_manager.get_event(event_id)
        if not event:
            messagebox.showerror("错误", f"找不到场次: {event_id}")
            return
        
        # 创建编辑场次对话框
        dialog = EventDialog(
            self.parent, 
            title="编辑场次",
            event_id=event_id,
            name=event.name,
            project_id=event.project_id,
            round=event.round,
            scoring_type=event.scoring_type,
            dances=event.dances,
            advancement_count=event.advancement_count
        )
        result = dialog.show()
        
        if result:
            new_event_id, name, project_id, round, scoring_type, dances, advancement_count = result
            
            # 更新场次
            if event_id != new_event_id:
                # 场次ID改变，需要删除旧场次并添加新场次
                if data_manager.remove_event(event_id):
                    event = Event(
                        id=new_event_id,
                        name=name,
                        project_id=project_id,
                        round=round,
                        scoring_type=scoring_type,
                        dances=dances,
                        advancement_count=advancement_count
                    )
                    
                    if data_manager.add_event(event):
                        self.status_label.config(text=f"成功更新场次: {new_event_id}")
                        self.refresh()
                    else:
                        messagebox.showerror("错误", f"更新场次失败: 场次ID {new_event_id} 已存在")
                else:
                    messagebox.showerror("错误", f"删除旧场次失败: {event_id}")
            else:
                # 场次ID未改变，直接更新
                event.name = name
                event.project_id = project_id
                event.round = round
                event.scoring_type = scoring_type
                event.dances = dances
                event.advancement_count = advancement_count
                
                self.status_label.config(text=f"成功更新场次: {event_id}")
                self.refresh()
    
    def delete_event(self):
        """删除场次"""
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先创建或打开一个赛事")
            return
        
        # 获取选中的场次ID
        event_id = self.get_selected_event_id()
        if not event_id:
            messagebox.showwarning("提示", "请先选择一个场次")
            return
        
        # 确认删除
        if not messagebox.askyesno("确认", f"确定要删除场次 {event_id} 吗？"):
            return
        
        # 删除场次
        if data_manager.delete_event(event_id):
            self.status_label.config(text=f"成功删除场次: {event_id}")
            self.refresh()
        else:
            messagebox.showerror("错误", f"删除场次失败: {event_id}")
    
    def start_scoring(self):
        """开始评分"""
        # 检查是否有打开的赛事
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先打开一个赛事")
            return
        
        # 获取选中的场次
        selection = self.event_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请选择一个场次")
            return
        
        item = selection[0]
        values = self.event_tree.item(item, "values")
        if not values:
            return
        
        event_id = values[0]
        event = data_manager.get_event(event_id)
        if not event:
            messagebox.showerror("错误", "找不到选中的场次")
            return
        
        # 检查场次是否有参赛选手
        if not event.competitors:
            messagebox.showwarning("提示", f"场次 {event_id} 没有参赛选手，请先从上一轮次导入晋级选手")
            return
        
        # 移除场次状态检查，允许对任何状态的场次进行评分
        # 只在未开始状态时更新为进行中
        if event.status == EventStatus.NOT_STARTED:
            event.status = EventStatus.IN_PROGRESS
            self.status_label.config(text=f"场次 {event_id} 已开始评分")
        else:
            self.status_label.config(text=f"场次 {event_id} 已打开，可以修改评分")
        
        # 如果没有裁判，创建默认裁判
        if not data_manager.current_competition.judges:
            # 根据设计文档，裁判信息可以缺省，系统应自动生成默认裁判
            from ..models.data_models import Judge
            default_judge = Judge(id="J1", name="默认裁判")
            data_manager.add_judge(default_judge)
            messagebox.showinfo("提示", "已自动创建默认裁判，可以开始评分")
        
        # 打开独立评分窗口
        try:
            from .scoring_window import ScoringWindow
            scoring_window = ScoringWindow(self.main_window.root, event_id, self.main_window)
            self.logger.info(f"打开独立评分窗口，场次: {event_id}")
        except Exception as e:
            messagebox.showerror("错误", f"打开评分窗口失败: {str(e)}")
            self.logger.error(f"打开评分窗口失败: {str(e)}")
            # 评分窗口打开失败，但不需要回退到不存在的选项卡
        
        self.refresh()
    
    def show_previous_advancement_confirmation(self) -> None:
        """显示前置轮次的晋级信息确认窗口"""
        # 获取选中的场次ID
        event_id = self.get_selected_event_id()
        if not event_id:
            messagebox.showwarning("提示", "请先选择一个场次")
            return
        
        # 获取当前场次
        event = data_manager.get_event(event_id)
        if not event:
            messagebox.showerror("错误", "获取场次信息失败")
            return
        
        # 获取项目编号和当前轮次
        project_id = event.project_id
        current_round = event.round
        
        # 计算前置轮次
        try:
            current_round_num = int(current_round)
            if current_round_num <= 1:
                messagebox.showinfo("提示", f"项目{project_id}的{current_round}轮次没有前置轮次")
                return
            previous_round = str(current_round_num - 1)
        except ValueError:
            messagebox.showerror("错误", "轮次格式不正确")
            return
        
        # 获取前置轮次的所有场次
        previous_round_events = data_manager.get_events_by_project_and_round(project_id, previous_round)
        
        if not previous_round_events:
            messagebox.showinfo("提示", f"项目{project_id}的{previous_round}轮次没有场次")
            return
        
        # 获取当前轮次的所有场次
        current_round_events = data_manager.get_events_by_project_and_round(project_id, current_round)
        
        try:
            from .advancement_confirmation_window import AdvancementConfirmationWindow
            # 使用前置轮次作为当前轮次，当前轮次作为下一轮次
            advancement_window = AdvancementConfirmationWindow(
                self.parent, 
                data_manager,
                project_id,
                previous_round,
                previous_round_events,
                current_round_events
            )
            self.logger.info(f"打开前置轮次晋级信息确认窗口，项目: {project_id}, 前置轮次: {previous_round}")
        except Exception as e:
            messagebox.showerror("错误", f"打开前置轮次晋级信息确认窗口失败: {str(e)}")
            self.logger.error(f"打开前置轮次晋级信息确认窗口失败: {str(e)}")
    
    def show_current_advancement_confirmation(self) -> None:
        """显示当前轮次的晋级信息确认窗口"""
        # 获取选中的场次ID
        event_id = self.get_selected_event_id()
        if not event_id:
            messagebox.showwarning("提示", "请先选择一个场次")
            return
        
        # 获取当前场次
        event = data_manager.get_event(event_id)
        if not event:
            messagebox.showerror("错误", "获取场次信息失败")
            return
        
        # 获取项目编号和当前轮次
        project_id = event.project_id
        current_round = event.round
        
        # 检查当前轮次的所有场次是否完成评分
        if not data_manager.check_round_scoring_complete(project_id, current_round):
            messagebox.showwarning("提示", f"项目{project_id}的{current_round}轮次尚未全部完成评分")
            return
        
        # 获取下一轮次的所有场次
        next_round_events = data_manager.get_next_round_events(project_id, current_round)
        
        if not next_round_events:
            messagebox.showinfo("提示", f"项目{project_id}的{current_round}轮次已经是最后一轮，无需晋级")
            return
        
        # 获取当前轮次的所有场次
        current_round_events = data_manager.get_events_by_project_and_round(project_id, current_round)
        
        try:
            from .advancement_confirmation_window import AdvancementConfirmationWindow
            advancement_window = AdvancementConfirmationWindow(
                self.parent, 
                data_manager,
                project_id,
                current_round,
                current_round_events,
                next_round_events
            )
            self.logger.info(f"打开当前轮次晋级信息确认窗口，项目: {project_id}, 轮次: {current_round}")
        except Exception as e:
            messagebox.showerror("错误", f"打开当前轮次晋级信息确认窗口失败: {str(e)}")
            self.logger.error(f"打开当前轮次晋级信息确认窗口失败: {str(e)}")
    
    def show_advancement_confirmation(self) -> None:
        """显示晋级信息确认窗口"""
        # 获取选中的场次ID
        event_id = self.get_selected_event_id()
        if not event_id:
            messagebox.showwarning("提示", "请先选择一个场次")
            return
        
        # 获取当前场次
        event = data_manager.get_event(event_id)
        if not event:
            messagebox.showerror("错误", "获取场次信息失败")
            return
        
        # 获取项目编号和当前轮次
        project_id = event.project_id
        current_round = event.round
        
        # 检查当前轮次的所有场次是否完成评分
        if not data_manager.check_round_scoring_complete(project_id, current_round):
            messagebox.showwarning("提示", f"项目{project_id}的{current_round}轮次尚未全部完成评分")
            return
        
        # 获取下一轮次的所有场次
        next_round_events = data_manager.get_next_round_events(project_id, current_round)
        
        if not next_round_events:
            messagebox.showinfo("提示", f"项目{project_id}的{current_round}轮次已经是最后一轮，无需晋级")
            return
        
        # 获取当前轮次的所有场次
        current_round_events = data_manager.get_events_by_project_and_round(project_id, current_round)
        
        try:
            from .advancement_confirmation_window import AdvancementConfirmationWindow
            advancement_window = AdvancementConfirmationWindow(
                self.parent, 
                data_manager,
                project_id,
                current_round,
                current_round_events,
                next_round_events
            )
            self.logger.info(f"打开晋级信息确认窗口，项目: {project_id}, 轮次: {current_round}")
        except Exception as e:
            messagebox.showerror("错误", f"打开晋级信息确认窗口失败: {str(e)}")
            self.logger.error(f"打开晋级信息确认窗口失败: {str(e)}")
    
    def calculate_results(self):
        """计算结果并检查是否需要打开晋级确认窗口"""
        # 获取选中的场次ID
        event_id = self.get_selected_event_id()
        if not event_id:
            self.logger.info("没有选中的场次ID")
            return
        
        # 获取场次
        event = data_manager.get_event(event_id)
        if not event:
            self.logger.info(f"找不到场次: {event_id}")
            return
        
        self.logger.info(f"处理场次 {event_id}, 项目 {event.project_id}, 轮次 {event.round}")
        
        # 检查评分是否完成
        scoring_complete = data_manager.is_scoring_complete(event_id)
        self.logger.info(f"场次 {event_id} 评分完成状态: {scoring_complete}")
        if not scoring_complete:
            return  # 如果评分未完成，不进行后续处理
        
        # 确保当前场次状态为已完成
        if event.status != EventStatus.COMPLETED:
            self.logger.info(f"更新场次 {event_id} 状态为已完成")
            event.status = EventStatus.COMPLETED
            data_manager.update_event(event)
        
        # 检查是否同一项目同一轮次的所有比赛都已完成
        project_id = event.project_id
        current_round = event.round
        
        round_complete, incomplete_events = data_manager.check_round_scoring_complete(project_id, current_round)
        self.logger.info(f"项目 {project_id} 轮次 {current_round} 完成状态: {round_complete}, 未完成场次: {incomplete_events}")
        
        if round_complete:
            # 获取下一轮次的所有场次
            next_round_events = data_manager.get_next_round_events(project_id, current_round)
            self.logger.info(f"下一轮次场次数量: {len(next_round_events)}")
            
            if next_round_events:
                # 获取当前轮次的所有场次
                current_round_events = data_manager.get_events_by_project_and_round(project_id, current_round)
                self.logger.info(f"当前轮次场次数量: {len(current_round_events)}")
                
                # 打开晋级信息确认窗口
                try:
                    from .advancement_confirmation_window import AdvancementConfirmationWindow
                    advancement_window = AdvancementConfirmationWindow(
                        self.parent, 
                        data_manager,
                        project_id,
                        current_round,
                        current_round_events,
                        next_round_events
                    )
                    self.logger.info(f"打开晋级信息确认窗口，项目: {project_id}, 轮次: {current_round}")
                except Exception as e:
                    messagebox.showerror("错误", f"打开晋级信息确认窗口失败: {str(e)}")
                    self.logger.error(f"打开晋级信息确认窗口失败: {str(e)}")
            else:
                self.logger.info(f"项目 {project_id} 轮次 {current_round} 没有下一轮次场次")
        else:
            self.logger.info(f"项目 {project_id} 轮次 {current_round} 尚未完成所有场次评分")
    

    
    def on_event_select(self, event):
        """场次选择事件处理"""
        # 更新结果表格
        self.update_results_table()
        # 更新选手列表
        self.update_competitors_table()
        # 更新导出按钮可见性
        event_id = self.get_selected_event_id()
        if event_id:
            self.update_export_buttons_visibility(event_id)
    
    def on_result_type_changed(self, event):
        """处理结果类型变化事件"""
        result_type = self.result_type_var.get()
        
        # 根据结果类型显示或隐藏舞种选择
        if result_type == "分舞种结果":
            self.dance_frame.pack(fill=tk.X, pady=(0, 10))
            self.update_dance_list()
        else:
            self.dance_frame.pack_forget()
        
        # 更新结果表格
        self.update_results_table()
    
    def on_dance_changed(self, event):
        """处理舞种变化事件"""
        self.update_results_table()
    
    def update_dance_list(self):
        """更新舞种列表"""
        selected_event_id = self.get_selected_event_id()
        if not selected_event_id:
            self.dance_combo['values'] = []
            return
        
        try:
            # 获取选中的场次
            event = self.event_manager.get_event(selected_event_id)
            if event and event.dances:
                dance_names = [dance.name for dance in event.dances]
                self.dance_combo['values'] = dance_names
                if dance_names and not self.dance_var.get():
                    self.dance_var.set(dance_names[0])
            else:
                self.dance_combo['values'] = []
        except Exception as e:
            self.status_label.config(text=f"获取舞种列表失败: {str(e)}")
            self.dance_combo['values'] = []
    
    def update_results_table(self):
        """更新结果表格"""
        # 清空表格
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        selected_event_id = self.get_selected_event_id()
        if not selected_event_id:
            return
        
        result_type = self.result_type_var.get()
        
        try:
            if result_type == "分舞种结果":
                dance_name = self.dance_var.get()
                if dance_name:
                    self._update_dance_results(selected_event_id, dance_name)
            elif result_type == "综合结果":
                self._update_overall_results(selected_event_id)
        except Exception as e:
            self.status_label.config(text=f"获取结果失败: {str(e)}")
    
    def _update_dance_results(self, event_id, dance_name):
        """更新舞种结果表格"""
        # 设置列
        columns = ("rank", "competitor_number", "competitor", "total_score")
        self.results_tree['columns'] = columns
        self.results_tree["show"] = "headings"
        
        # 设置列标题
        self.results_tree.heading("rank", text="排名")
        self.results_tree.heading("competitor_number", text="背番号")
        self.results_tree.heading("competitor", text="选手")
        self.results_tree.heading("total_score", text="总分")
        
        # 设置列宽
        self.results_tree.column("rank", width=60)
        self.results_tree.column("competitor_number", width=80)
        self.results_tree.column("competitor", width=150)
        self.results_tree.column("total_score", width=100)
        
        # 获取比赛和场次对象
        competition = self.event_manager.get_competition()
        event = self.event_manager.get_event(event_id)
        
        if not competition or not event:
            self.status_label.config(text="获取比赛或场次信息失败")
            return
        
        # 获取舞种结果
        success, dance_results, errors = self.results_view_manager.get_dance_results_from_data(
            competition, event, dance_name
        )
        
        if not success:
            self.status_label.config(text=f"获取舞种结果失败: {', '.join(errors)}")
            return
        
        # 填充数据
        for result in dance_results:
            rank = result.get("rank", "")
            competitor_number = result.get("competitor_number", "")
            competitor_name = result.get("competitor_name", "")
            total_score = result.get("total_score", 0)
            
            # 获取晋级状态并显示
            advancement_status = result.get("advancement_status", False)
            advancement_display = "✓" if advancement_status else ""
            
            self.results_tree.insert("", "end", values=(
                rank, competitor_number, competitor_name, total_score, advancement_display
            ))
    
    def _update_overall_results(self, event_id):
        """更新综合结果表格"""
        # 设置列
        columns = ("rank", "competitor_number", "competitor", "total_score", "advancement")
        self.results_tree['columns'] = columns
        self.results_tree["show"] = "headings"
        
        # 设置列标题
        self.results_tree.heading("rank", text="排名")
        self.results_tree.heading("competitor_number", text="背番号")
        self.results_tree.heading("competitor", text="选手")
        self.results_tree.heading("total_score", text="总分")
        self.results_tree.heading("advancement", text="晋级/录取")
        
        # 设置列宽
        self.results_tree.column("rank", width=60, anchor="center")
        self.results_tree.column("competitor_number", width=80, anchor="center")
        self.results_tree.column("competitor", width=120, anchor="center")
        self.results_tree.column("total_score", width=80, anchor="center")
        self.results_tree.column("advancement", width=100, anchor="center")
        
        # 获取比赛和场次对象
        competition = self.event_manager.get_competition()
        event = self.event_manager.get_event(event_id)
        
        if not competition or not event:
            self.status_label.config(text="获取比赛或场次信息失败")
            return
        
        # 获取综合结果
        success, overall_results, errors = self.results_view_manager.get_overall_results_from_data(
            competition, event
        )
        
        if not success:
            self.status_label.config(text=f"获取综合结果失败: {', '.join(errors)}")
            return
        
        # 填充数据
        for result in overall_results:
            rank = result.get("rank", "")
            competitor_number = result.get("competitor_number", "")
            competitor_name = result.get("competitor_name", "")
            total_score = result.get("total_score", 0)
            
            # 获取晋级状态并显示
            advancement_status = result.get("advancement_status", False)
            advancement_display = "✓" if advancement_status else ""
            
            self.results_tree.insert("", "end", values=(
                rank, competitor_number, competitor_name, total_score, advancement_display
            ))
    
    def on_result_select(self, event):
        """处理结果选择事件"""
        # 可以在这里添加选择结果后的处理逻辑
        pass
    
    def export_results(self):
        """导出结果"""
        selected_event_id = self.get_selected_event_id()
        if not selected_event_id:
            messagebox.showwarning("警告", "请先选择一个场次")
            return
        
        # 选择保存位置，默认为PDF格式
        file_path = filedialog.asksaveasfilename(
            title="导出结果",
            defaultextension=".pdf",
            filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            result_type = self.result_type_var.get()
            
            if result_type == "分舞种结果":
                dance_name = self.dance_var.get()
                if dance_name:
                    self.results_view_manager.export_dance_results_to_pdf(selected_event_id, dance_name, file_path, self.event_manager)
                else:
                    messagebox.showwarning("警告", "请选择一个舞种")
                    return
            elif result_type == "综合结果":
                self.results_view_manager.export_overall_results_to_pdf(selected_event_id, file_path, self.event_manager)
            
            messagebox.showinfo("成功", f"结果已导出到: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出结果失败: {str(e)}")
    
    def export_detailed_results(self):
        """导出详细评分结果"""
        selected_event_id = self.get_selected_event_id()
        if not selected_event_id:
            messagebox.showwarning("警告", "请先选择一个场次")
            return
        
        # 选择保存位置，默认为PDF格式
        file_path = filedialog.asksaveasfilename(
            title="导出详细评分结果",
            defaultextension=".pdf",
            filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # 调用导出明细功能
            success, errors = self.results_view_manager.export_detailed_results_to_pdf(
                selected_event_id, file_path, self.event_manager
            )
            
            if success:
                messagebox.showinfo("成功", f"详细评分结果已导出到: {file_path}")
            else:
                error_msg = "\n".join(errors) if errors else "未知错误"
                messagebox.showerror("错误", f"导出详细评分结果失败: {error_msg}")
        except Exception as e:
            messagebox.showerror("错误", f"导出详细评分结果失败: {str(e)}")
    
    def export_markdown_results(self):
        """导出Markdown格式的详细评分结果"""
        selected_event_id = self.get_selected_event_id()
        if not selected_event_id:
            messagebox.showwarning("警告", "请先选择一个场次")
            return
        
        # 选择保存位置，默认为Markdown格式
        file_path = filedialog.asksaveasfilename(
            title="导出Markdown详细评分结果",
            defaultextension=".md",
            filetypes=[("Markdown文件", "*.md"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # 获取场次信息
            event = self.event_manager.get_event(selected_event_id)
            if not event:
                messagebox.showerror("错误", "获取场次信息失败")
                return
                
            # 调用导出Markdown明细功能，不传递event_type参数，让系统自动判断
            success, errors = self.results_view_manager.export_score_details_to_markdown(
                selected_event_id, file_path, self.event_manager
            )
            
            if success:
                messagebox.showinfo("成功", f"Markdown详细评分结果已导出到: {file_path}")
            else:
                error_msg = "\n".join(errors) if errors else "未知错误"
                messagebox.showerror("错误", f"导出Markdown详细评分结果失败: {error_msg}")
        except Exception as e:
            messagebox.showerror("错误", f"导出Markdown详细评分结果失败: {str(e)}")
    
    def update_export_buttons_visibility(self, event_id):
        """根据场次类型更新导出按钮的可见性"""
        if not event_id:
            return
        
        # 获取场次信息
        event = self.event_manager.get_event(event_id)
        if not event:
            return
        
        # 判断是否为最终轮次（现在使用原始轮次数据）
        is_final_round = False
        # 获取该项目的所有场次，找出最大轮次
        if event and event.project_id:
            all_events = self.event_manager.get_all_events()
            # 检查返回类型，如果是字典则获取values，如果是列表则直接使用
            if isinstance(all_events, dict):
                project_events = [e for e in all_events.values() if e.project_id == event.project_id]
            else:
                # 确保只处理具有project_id属性的对象
                project_events = [e for e in all_events if hasattr(e, 'project_id') and e.project_id == event.project_id]
            
            if project_events:
                try:
                    # 尝试将轮次转换为数字进行比较
                    max_round = max(int(e.round) for e in project_events if hasattr(e, 'round') and e.round and e.round.isdigit())
                    is_final_round = hasattr(event, 'round') and event.round and event.round.isdigit() and int(event.round) == max_round
                except (ValueError, AttributeError):
                    # 如果转换失败，则保持is_final_round为False
                    pass
        
        # 根据轮次显示或隐藏导出综合名次表按钮
        if is_final_round:
            # 最终轮次：显示导出综合名次表按钮
            if not hasattr(self, 'export_overall_button'):
                self.export_overall_button = ttk.Button(
                    self.results_button_frame,
                    text="导出综合名次表",
                    command=self.export_overall_results
                )
                self.export_overall_button.pack(side=tk.LEFT, padx=(0, 5))
        else:
            # 非最终轮次：隐藏导出综合名次表按钮
            if hasattr(self, 'export_overall_button'):
                self.export_overall_button.pack_forget()
    
    def update_competitors_table(self):
        """更新参赛选手列表"""
        # 确保competitors_tree已初始化
        if not hasattr(self, 'competitors_tree'):
            return
        
        # 清空表格
        for item in self.competitors_tree.get_children():
            self.competitors_tree.delete(item)
        
        # 获取选中的场次ID
        event_id = self.get_selected_event_id()
        if not event_id:
            return
        
        # 获取场次信息
        event = data_manager.get_event(event_id)
        if not event or not hasattr(event, 'competitors'):
            return
        
        # 获取参赛选手并按背番号排序
        competitors = []
        
        # 使用event中的选手信息，并从data_manager中获取真实选手姓名
        for competitor_number in event.competitors:
            # 使用背番号+项目编号获取选手信息
            player = data_manager.get_competitor_by_number_and_project(competitor_number, event.project_id)
            
            # 准备选手信息
            name = "未知选手"
            team = ""
            
            if player:
                # 尝试获取选手名称
                if hasattr(player, 'name') and player.name:
                    name = player.name
                else:
                    # 如果没有选手名称，使用背番号
                    name = str(competitor_number)
                
                # 尝试获取团队信息
                if hasattr(player, 'team') and player.team:
                    team = player.team
                elif hasattr(player, 'school') and player.school:
                    team = player.school
                elif hasattr(player, 'unit') and player.unit:
                    team = player.unit
            else:
                # 如果找不到选手信息，只使用背番号
                name = str(competitor_number)
            
            competitors.append({
                'competitor_number': competitor_number,
                'name': name,
                'team': team
            })
        
        # 按背番号排序（尝试将背番号转换为整数进行比较）
        def sort_key(item):
            try:
                return int(item['competitor_number'])
            except (ValueError, TypeError):
                return str(item['competitor_number'])
        
        competitors.sort(key=sort_key)
        
        # 添加到表格
        for competitor in competitors:
            self.competitors_tree.insert('', tk.END, values=(
                competitor['competitor_number'],
                competitor['name'],
                competitor['team']
            ))
    
    def export_scoring_sheet(self):
        """导出可打印评分表（空白表格，用于裁判打分）"""
        selected_event_id = self.get_selected_event_id()
        if not selected_event_id:
            messagebox.showwarning("提示", "请先选择一个场次")
            return
        
        # 获取场次
        event = data_manager.get_event(selected_event_id)
        if not event:
            return
        
        # 获取选手数据
        players = data_manager.get_players_by_event(selected_event_id)
        if not players:
            messagebox.showwarning("提示", "该场次没有选手")
            return
        
        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            title=f"导出评分表 - {event.name}",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("PDF文件", "*.pdf")]
        )
        
        if not file_path:
            return
        
        try:
            if file_path.lower().endswith('.pdf'):
                # 导出为PDF
                self._export_scoring_sheet_to_pdf(event, players, file_path)
            else:
                # 导出为Excel
                self._export_scoring_sheet_to_excel(event, players, file_path)
            
            messagebox.showinfo("成功", f"评分表已导出到: {os.path.basename(file_path)}")
            
        except Exception as e:
            self.logger.error(f"导出评分表失败: {e}")
            messagebox.showerror("错误", f"导出评分表失败: {str(e)}")
    
    def _export_scoring_sheet_to_excel(self, event, players, file_path):
        """导出空白评分表为Excel格式（行为舞种，列为背番号，节省打印空间）"""
        import pandas as pd
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        
        # 创建工作簿
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # 创建数据结构 - 行为舞种，列为背番号
            data = []
            
            # 表头行（第一列为"舞种"，其余为背番号）
            header = {"舞种": "舞种"}
            for player in players:
                header[player.number] = str(player.number)
            data.append(header)
            
            # 为每个舞种添加一行
            for dance in event.dances:
                dance_row = {"舞种": dance.name}  # 第一列是舞种名称
                
                # 为每个选手添加空白评分单元格
                for player in players:
                    # 根据评分类型添加提示文本
                    if event.scoring_type.value == "mark":
                        dance_row[player.number] = ""  # Mark制：空白单元格用于填写分数
                    else:
                        dance_row[player.number] = ""  # 顺位法：空白单元格用于填写名次
                
                data.append(dance_row)
            
            # 创建DataFrame并写入工作表
            df = pd.DataFrame(data)
            df.to_excel(writer, index=False, sheet_name="评分表")
            
            # 获取工作表对象以设置格式
            worksheet = writer.sheets["评分表"]
            
            # 设置列宽
            column_widths = {}
            for i, col in enumerate(df.columns):
                col_letter = chr(ord('A') + i)
                if i == 0:
                    column_widths[col_letter] = 20  # 第一列（舞种名称）较宽
                else:
                    column_widths[col_letter] = 10  # 背番号列（较窄）
            
            for col, width in column_widths.items():
                if col in [chr(ord('A') + i) for i in range(len(df.columns))]:
                    worksheet.column_dimensions[col].width = width
            
            # 设置行高
            for row in range(1, len(df) + 3):  # 包括标题行和签名行
                worksheet.row_dimensions[row].height = 25
            
            # 定义边框样式
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # 定义居中对齐
            center_alignment = Alignment(horizontal='center', vertical='center')
            
            # 定义左对齐（用于舞种名称）
            left_alignment = Alignment(horizontal='left', vertical='center')
            
            # 定义右对齐（用于签名）
            right_alignment = Alignment(horizontal='right', vertical='center')
            
            # 定义表头样式
            header_font = Font(name='微软雅黑', size=12, bold=True)
            header_fill = PatternFill(start_color='E6E6FA', end_color='E6E6FA', fill_type='solid')
            
            # 应用表头样式
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_alignment
                cell.border = thin_border
            
            # 应用数据行样式
            for row in range(2, len(event.dances) + 2):
                for col in range(1, len(df.columns) + 1):
                    cell = worksheet.cell(row=row, column=col)
                    cell.border = thin_border
                    
                    # 第一列（舞种名称）使用左对齐和加粗字体
                    if col == 1:
                        cell.font = Font(name='微软雅黑', size=11, bold=True)
                        cell.alignment = left_alignment
                    else:
                        # 其他列使用居中对齐
                        cell.font = Font(name='微软雅黑', size=11)
                        cell.alignment = center_alignment
            
            # 添加裁判签名行（在表格下方）
            signature_row = len(event.dances) + 3
            signature_cell = worksheet.cell(row=signature_row, column=1)
            signature_cell.value = "裁判签名：_________________________"
            signature_cell.font = Font(name='微软雅黑', size=11)
            signature_cell.alignment = right_alignment
            signature_cell.border = thin_border
            
            # 合并裁判签名行的所有单元格
            if len(df.columns) > 0:
                last_col_letter = chr(ord('A') + len(df.columns) - 1)
                worksheet.merge_cells(f'A{signature_row}:{last_col_letter}{signature_row}')
                
                # 为合并后的单元格添加边框
                for col in range(1, len(df.columns) + 1):
                    cell = worksheet.cell(row=signature_row, column=col)
                    cell.border = thin_border
            
            # 添加标题行（在表格上方）
            title_row = 1
            title_cell = worksheet.cell(row=title_row, column=1)
            title_cell.value = f"{event.name} - 评分表"
            title_cell.font = Font(name='微软雅黑', size=16, bold=True)
            title_cell.alignment = center_alignment
            
            # 合并标题行的所有单元格
            if len(df.columns) > 0:
                last_col_letter = chr(ord('A') + len(df.columns) - 1)
                worksheet.merge_cells(f'A{title_row}:{last_col_letter}{title_row}')
            
            # 创建汇总工作表
            summary_data = []
            summary_header = {
                "场次名称": event.name,
                "场次ID": event.id,
                "项目编号": event.project_id,
                "轮次": event.round,
                "评分类型": event.scoring_type.value,
                "舞种数量": len(event.dances),
                "选手数量": len(players),
                "打印时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            summary_data.append(summary_header)
            
            # 添加舞种列表
            for i, dance in enumerate(event.dances):
                dance_info = {"舞种": dance.name}
                summary_data.append(dance_info)
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, index=False, sheet_name="场次信息")
    
    def export_pdf_scoring_sheet(self):
        """直接导出PDF评分表"""
        selected_event_id = self.get_selected_event_id()
        if not selected_event_id:
            messagebox.showwarning("提示", "请先选择一个场次")
            return
        
        # 获取场次
        event = data_manager.get_event(selected_event_id)
        if not event:
            return
        
        # 获取选手数据
        players = data_manager.get_players_by_event(selected_event_id)
        if not players:
            messagebox.showwarning("提示", "该场次没有选手")
            return
        
        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            title=f"导出PDF评分表 - {event.name}",
            defaultextension=".pdf",
            filetypes=[("PDF文件", "*.pdf")]
        )
        
        if not file_path:
            return
        
        try:
            # 直接调用PDF导出方法
            self._export_scoring_sheet_to_pdf(event, players, file_path)
            messagebox.showinfo("成功", f"PDF评分表已导出到: {os.path.basename(file_path)}")
        except Exception as e:
            self.logger.error(f"导出PDF评分表失败: {e}")
            messagebox.showerror("错误", f"导出PDF评分表失败: {str(e)}")
    
    def _export_scoring_sheet_to_pdf(self, event, players, file_path):
        """导出空白评分表为PDF格式（行为舞种，列为背番号，与Excel评分表第一个sheet格式保持一致）"""
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.units import mm, inch
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib import colors
            from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            # 导入ScoringType枚举类
            from ..models.data_models import ScoringType
            
            # 计算横向A4纸的实际可用尺寸，提升空间利用率
            a4_width, a4_height = landscape(A4)
            available_width = a4_width - 40*mm  # 左右边距各20mm，总计40mm
            available_height = a4_height - 40*mm  # 上下边距各20mm，总计40mm
            
            # 创建PDF文档 - 使用横向打印，优化边距
            doc = SimpleDocTemplate(file_path, pagesize=landscape(A4),
                                   leftMargin=15*mm, rightMargin=15*mm,  # 减少边距，从20mm改为15mm
                                   topMargin=15*mm, bottomMargin=15*mm)  # 减少边距，从20mm改为15mm
            
            # 设置字体（支持中文）
            font_name = 'Helvetica'  # 默认字体
            try:
                # 尝试注册中文字体，确保中文能够正确显示
                font_paths = [
                    # macOS系统字体路径
                    '/System/Library/Fonts/PingFang.ttc',
                    '/System/Library/Fonts/STHeiti Light.ttc',
                    '/System/Library/Fonts/STHeiti Medium.ttc',
                    '/System/Library/Fonts/Arial Unicode MS.ttf',
                    # Linux系统字体路径
                    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
                    '/usr/share/fonts/truetype/arphic/uming.ttc',
                    # Windows系统字体路径
                    'C:/Windows/Fonts/simhei.ttf',
                    'C:/Windows/Fonts/simsun.ttc',
                ]
                
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        try:
                            # 对于 TTC 字体文件，需要指定字体索引
                            if font_path.endswith('.ttc'):
                                pdfmetrics.registerFont(TTFont('chinese', font_path, subfontIndex=0))
                            else:
                                pdfmetrics.registerFont(TTFont('chinese', font_path))
                            font_name = 'chinese'
                            self.logger.info(f"成功注册中文字体: {font_path}")
                            break
                        except Exception as e:
                            self.logger.warning(f"注册字体失败 {font_path}: {e}")
                            continue
            except Exception as e:
                self.logger.error(f"注册中文字体失败: {e}")
            
            # 获取样式
            styles = getSampleStyleSheet()
            
            # 创建标题样式 - 适当增加字体大小
            title_style = ParagraphStyle(
                name='CustomTitle',
                parent=styles['Title'],
                fontName=font_name,
                fontSize=18,  # 增大标题字体大小，从16改为18
                leading=22,   # 增大行间距
                alignment=1,  # 居中对齐
                spaceAfter=15  # 增大标题后的间距
            )
            
            # 创建内容列表
            content = []
            
            # 计算晋级规则
            if event.scoring_type == ScoringType.MARK:
                # Mark制：M进N，M为本场选手数量，N为赛程预订的晋级下一场的人数
                advancement_rule = f"{len(players)}进{event.advancement_count}"
            else:
                # 顺位制：N顺位，N为赛程预订的录取人数
                advancement_rule = f"{event.advancement_count}顺位"
            
            # 添加标题（场次编号. 场次名称     晋级规则）
            title = Paragraph(f"{event.id}. {event.name}     {advancement_rule}", title_style)
            content.append(title)
            content.append(Spacer(1, 15))  # 增大标题与表格之间的间距
            
            # 创建评分表（行为舞种，列为背番号，与Excel格式一致）
            table_data = []
            
            # 表头行（第一列为"舞种"，其余为背番号）
            header = ["舞种"]
            for player in players:
                header.append(str(player.number))
            table_data.append(header)
            
            # 为每个舞种添加一行
            for dance in event.dances:
                row = [dance.name]  # 第一列是舞种名称
                
                # 为每个选手添加空白评分单元格
                for player in players:
                    # 根据评分类型添加提示文本
                    if event.scoring_type.value == "mark":
                        row.append("")  # Mark制：空白单元格用于填写分数
                    else:
                        row.append("")  # 顺位法：空白单元格用于填写名次
                
                table_data.append(row)
            
            # 动态计算列宽，让内容占据纸张的大部分
            num_columns = len(table_data[0])
            dance_col_width = 35*mm  # 增大舞种列宽度，从30mm改为35mm
            player_col_width = (available_width - dance_col_width) / (num_columns - 1)  # 动态计算选手列宽度
            col_widths = [dance_col_width] + [player_col_width] * (num_columns - 1)  # 动态计算列宽
            
            # 使用固定行高创建表格，确保行高生效
            table = Table(table_data, colWidths=col_widths, repeatRows=1, rowHeights=[45]*len(table_data))
            
            # 设置表格样式，优化内容大小和空间利用率
            table.setStyle(TableStyle([
                # 表头样式
                ('FONTNAME', (0, 0), (-1, 0), font_name),
                ('FONTSIZE', (0, 0), (-1, 0), 14),  # 增大表头字体大小，从12改为14
                ('BOLD', (0, 0), (-1, 0), True),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # 居中对齐
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                
                # 数据行样式
                ('FONTNAME', (0, 1), (-1, -1), font_name),
                ('FONTSIZE', (0, 1), (-1, -1), 13),  # 增大数据行字体大小，从11改为13
                
                # 选手列样式：顶部对齐，方便裁判从上到下填充内容
                ('VALIGN', (1, 1), (-1, -1), 'TOP'),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                
                # 舞种列样式：水平和垂直居中，突出显示
                ('BOLD', (0, 1), (0, -1), True),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # 舞种列水平居中
                ('VALIGN', (0, 1), (0, -1), 'MIDDLE'),  # 舞种列垂直居中
                
                # 表格边框
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
            ]))
            
            content.append(table)
            content.append(Spacer(1, 20))  # 增大表格与签名之间的间距
            
            # 添加裁判签名（适当增大字体大小）
            signature_data = [["裁判签名：_________________________"]]
            signature_table = Table(signature_data, colWidths=[150*mm])  # 增大签名区域宽度
            signature_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 14),  # 增大签名字体大小，从11改为14
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            content.append(signature_table)
            
            # 构建PDF文档
            doc.build(content)
            return True
        except Exception as e:
            self.logger.error(f"导出PDF评分表失败: {e}")
            messagebox.showerror("错误", f"导出PDF失败: {str(e)}")
            return False

    def export_overall_results(self):
        """导出综合名次表"""
        selected_event_id = self.get_selected_event_id()
        if not selected_event_id:
            messagebox.showwarning("警告", "请先选择一个场次")
            return
        
        # 选择保存位置
        file_path = filedialog.asksaveasfilename(
            title="导出综合名次表",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # 导出综合名次表
            success, errors = self.results_view_manager.export_overall_results(
                selected_event_id, file_path, self.event_manager
            )
            
            if success:
                messagebox.showinfo("成功", f"综合名次表已导出到: {file_path}")
            else:
                messagebox.showerror("错误", f"导出失败: {'; '.join(errors)}")
        except Exception as e:
            messagebox.showerror("错误", f"导出综合名次表失败: {str(e)}")


class EventDialog:
    """场次对话框类"""
    
    def __init__(self, parent, title="场次", event_id="", name="", project_id="", 
                 round="", scoring_type=ScoringType.MARK, dances=None, advancement_count=0):
        """初始化场次对话框"""
        self.parent = parent
        self.title = title
        self.event_id = event_id
        self.name = name
        self.project_id = project_id
        self.round = round
        self.scoring_type = scoring_type
        self.dances = dances or []
        self.advancement_count = advancement_count
        self.result = None
        
        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x400")
        self.dialog.resizable(False, False)
        
        # 使对话框居中
        self.dialog.transient(parent)
        self.dialog.grab_set()
        center_window(self.dialog, parent)
        
        # 创建界面元素
        self.create_widgets()
        
        # 绑定关闭事件
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)
    
    def create_widgets(self):
        """创建界面元素"""
        # 主框架
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 场次ID
        ttk.Label(main_frame, text="场次ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.event_id_var = tk.StringVar(value=self.event_id)
        ttk.Entry(main_frame, textvariable=self.event_id_var, width=30).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # 场次名称
        ttk.Label(main_frame, text="场次名称:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=self.name)
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 项目编号
        ttk.Label(main_frame, text="项目编号:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.project_id_var = tk.StringVar(value=self.project_id)
        ttk.Entry(main_frame, textvariable=self.project_id_var, width=30).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # 轮次
        ttk.Label(main_frame, text="轮次:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.round_var = tk.StringVar(value=self.round)
        ttk.Entry(main_frame, textvariable=self.round_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # 晋级人数（非决赛场次）
        ttk.Label(main_frame, text="晋级人数:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.advancement_count_var = tk.IntVar(value=self.advancement_count)
        self.advancement_count_spinbox = ttk.Spinbox(
            main_frame, 
            from_=0, 
            to=50, 
            textvariable=self.advancement_count_var,
            width=10
        )
        self.advancement_count_spinbox.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # 评分类型
        ttk.Label(main_frame, text="评分类型:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.scoring_type_var = tk.StringVar(value=self.scoring_type.value)
        scoring_type_combo = ttk.Combobox(
            main_frame, 
            textvariable=self.scoring_type_var,
            values=[ScoringType.MARK.value, ScoringType.SKATING.value],
            state="readonly"
        )
        scoring_type_combo.grid(row=5, column=1, sticky=tk.W, pady=5)
        scoring_type_combo.bind("<<ComboboxSelected>>", self.on_scoring_type_changed)
        
        # 舞种
        ttk.Label(main_frame, text="舞种:").grid(row=6, column=0, sticky=tk.NW, pady=5)
        
        # 舞种框架
        dances_frame = ttk.Frame(main_frame)
        dances_frame.grid(row=6, column=1, sticky=tk.W, pady=5)
        
        # 舞种列表
        self.dances_listbox = tk.Listbox(dances_frame, height=5, width=30)
        self.dances_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 舞种滚动条
        dances_scrollbar = ttk.Scrollbar(dances_frame, orient=tk.VERTICAL, command=self.dances_listbox.yview)
        dances_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.dances_listbox.configure(yscrollcommand=dances_scrollbar.set)
        
        # 舞种按钮
        dances_button_frame = ttk.Frame(main_frame)
        dances_button_frame.grid(row=7, column=1, sticky=tk.W, pady=5)
        
        ttk.Button(dances_button_frame, text="添加舞种", command=self.add_dance).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(dances_button_frame, text="删除舞种", command=self.remove_dance).pack(side=tk.LEFT)
        
        # 初始化舞种列表
        for dance in self.dances:
            self.dances_listbox.insert(tk.END, dance.name)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="取消", command=self.on_cancel).pack(side=tk.LEFT)
        
        # 初始化晋级人数输入框状态
        self.update_advancement_count_state()
    
    def update_advancement_count_state(self):
        """更新晋级人数输入框状态"""
        # 默认可用晋级人数输入
        self.advancement_count_spinbox.config(state="normal")
        # 如果当前值为0，设置默认值为4
        if self.advancement_count_var.get() == 0:
            self.advancement_count_var.set(4)
    
    def on_scoring_type_changed(self, event):
        """评分类型改变事件处理"""
        scoring_type_str = self.scoring_type_var.get()
        
        # 根据评分类型设置默认舞种
        self.dances_listbox.delete(0, tk.END)
        
        if scoring_type_str == ScoringType.MARK.value:
            # Mark制默认舞种
            default_dances = ["华尔兹", "探戈", "维也纳华尔兹", "狐步", "快步"]
        else:
            # 顺位法默认舞种
            default_dances = ["华尔兹", "探戈", "狐步", "快步"]
        
        for dance_name in default_dances:
            self.dances_listbox.insert(tk.END, dance_name)
    
    def add_dance(self):
        """添加舞种"""
        # 创建输入对话框
        dialog = tk.Toplevel(self.dialog)
        dialog.title("添加舞种")
        dialog.geometry("300x100")
        dialog.resizable(False, False)
        
        # 使对话框居中
        dialog.transient(self.dialog)
        dialog.grab_set()
        center_window(dialog, self.dialog)
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 输入框
        ttk.Label(main_frame, text="舞种名称:").pack(anchor=tk.W, pady=(0, 5))
        dance_name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=dance_name_var, width=30).pack(fill=tk.X, pady=(0, 10))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack()
        
        def on_ok():
            dance_name = dance_name_var.get().strip()
            if dance_name:
                self.dances_listbox.insert(tk.END, dance_name)
            dialog.destroy()
        
        ttk.Button(button_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT)
    
    def remove_dance(self):
        """删除舞种"""
        selection = self.dances_listbox.curselection()
        if selection:
            self.dances_listbox.delete(selection[0])
    
    def on_ok(self):
        """确定按钮事件处理"""
        # 获取输入值
        event_id = self.event_id_var.get().strip()
        name = self.name_var.get().strip()
        project_id = self.project_id_var.get().strip()
        round_value = self.round_var.get().strip()
        scoring_type_str = self.scoring_type_var.get().strip()
        
        # 验证输入
        if not event_id:
            messagebox.showerror("错误", "请输入场次ID")
            return
        
        if not name:
            messagebox.showerror("错误", "请输入场次名称")
            return
        
        if not project_id:
            messagebox.showerror("错误", "请输入项目编号")
            return
        
        if not round_value:
            messagebox.showerror("错误", "请输入轮次")
            return
        
        # 获取舞种
        dance_names = [self.dances_listbox.get(i) for i in range(self.dances_listbox.size())]
        if not dance_names:
            messagebox.showerror("错误", "请至少添加一个舞种")
            return
        
        # 创建舞种对象
        dances = [Dance(name=name, order=i) for i, name in enumerate(dance_names)]
        
        # 解析评分类型
        scoring_type = ScoringType.MARK if scoring_type_str == ScoringType.MARK.value else ScoringType.SKATING
        
        # 获取晋级人数
        advancement_count = self.advancement_count_var.get()
        
        # 设置结果
        self.result = (event_id, name, project_id, round_value, scoring_type, dances, advancement_count)
        
        # 关闭对话框
        self.dialog.destroy()
    
    def on_cancel(self):
        """取消按钮事件处理"""
        self.dialog.destroy()
    
    def show(self):
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result