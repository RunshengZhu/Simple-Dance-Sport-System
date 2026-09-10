# -*- coding: utf-8 -*-
"""
结果查看选项卡
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Dict, List, Optional, Tuple, Any
import datetime

from src.models.data_models import Competition, Event, Competitor
from src.models.data_manager import DataManager
from src.utils.results_view_manager import ResultsViewManager


class ResultsViewTab:
    """结果查看选项卡"""
    
    def __init__(self, parent: tk.Widget, data_manager: DataManager):
        """
        初始化结果查看选项卡
        
        Args:
            parent: 父级窗口
            data_manager: 数据管理器
        """
        self.parent = parent
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)
        
        # 当前选中的场次ID
        self.current_event_id: Optional[str] = None
        
        # 结果查看管理器
        self.results_view_manager = ResultsViewManager()
        
        # 创建界面
        self._create_widgets()
        
        # 初始化界面
        self._initialize_ui()
    
    def _create_widgets(self) -> None:
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 上部控制区域
        control_frame = ttk.LabelFrame(main_frame, text="选择场次")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 场次选择
        event_frame = ttk.Frame(control_frame)
        event_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(event_frame, text="场次:").pack(side=tk.LEFT, padx=(0, 5))
        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(event_frame, textvariable=self.event_var, state="readonly")
        self.event_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.event_combo.bind("<<ComboboxSelected>>", self.on_event_changed)
        
        # 结果类型选择
        result_type_frame = ttk.Frame(control_frame)
        result_type_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(result_type_frame, text="结果类型:").pack(side=tk.LEFT, padx=(0, 5))
        self.result_type_var = tk.StringVar(value="综合结果")
        self.result_type_combo = ttk.Combobox(
            result_type_frame, 
            textvariable=self.result_type_var,
            values=["分舞种结果", "综合结果"],
            state="readonly"
        )
        self.result_type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.result_type_combo.bind("<<ComboboxSelected>>", self.on_result_type_changed)
        
        # 舞种选择框架
        self.dance_frame = ttk.Frame(control_frame)
        self.dance_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(self.dance_frame, text="舞种:").pack(side=tk.LEFT, padx=(0, 5))
        self.dance_var = tk.StringVar()
        self.dance_combo = ttk.Combobox(self.dance_frame, textvariable=self.dance_var, state="readonly")
        self.dance_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.dance_combo.bind("<<ComboboxSelected>>", self.on_dance_changed)
        
        # 初始隐藏舞种选择
        self.dance_frame.pack_forget()
        
        # 操作按钮区域
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 添加晋级信息确认按钮
        self.advancement_button = ttk.Button(
            button_frame, 
            text="晋级信息确认", 
            command=self.show_advancement_confirmation
        )
        self.advancement_button.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(button_frame, text="刷新", command=self.refresh_results).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 结果显示区域
        results_frame = ttk.LabelFrame(main_frame, text="结果")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建表格
        table_frame = ttk.Frame(results_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建Treeview
        self.results_tree = ttk.Treeview(table_frame)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
    
    def _initialize_ui(self) -> None:
        """初始化界面"""
        # 更新场次列表
        self.update_event_list()
        
        # 如果有场次，选择第一个
        if self.event_combo['values']:
            self.event_combo.current(0)
            self.on_event_changed(None)
    
    def refresh_ui(self) -> None:
        """刷新界面"""
        self.update_event_list()
        if self.current_event_id:
            self.update_results_table()
    
    def set_current_event(self, event_id: str) -> None:
        """
        设置当前选中的场次
        
        Args:
            event_id: 场次ID
        """
        if event_id != self.current_event_id:
            self.current_event_id = event_id
            
            # 更新界面选择
            if event_id in self.event_combo['values']:
                self.event_var.set(event_id)
                
                # 更新结果表格，默认显示综合评分
                self.result_type_var.set("综合结果")
                self.update_results_table()
    
    def update_event_list(self) -> None:
        """更新场次列表"""
        # 获取已完成的场次
        completed_events = []
        if self.data_manager.current_competition:
            for event_id, event in self.data_manager.current_competition.events.items():
                if event.is_completed:
                    completed_events.append(event_id)
        
        # 更新下拉框
        self.event_combo['values'] = completed_events
        
        # 如果当前选中的场次不在列表中，清除选择
        if self.current_event_id and self.current_event_id not in completed_events:
            self.current_event_id = None
            self.event_var.set("")
    
    def update_results_table(self) -> None:
        """更新结果表格"""
        # 清空表格
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        if not self.current_event_id:
            return
        
        # 获取结果类型
        result_type = self.result_type_var.get()
        
        # 根据结果类型更新表格
        if result_type == "分舞种结果":
            self.update_dance_results()
        elif result_type == "综合结果":
            self.update_overall_results()
    
    def update_dance_results(self) -> None:
        """更新舞种结果表格"""
        # 获取当前场次
        event = self.data_manager.get_event(self.current_event_id)
        if not event:
            return
        
        # 获取选中的舞种
        dance_name = self.dance_var.get()
        if not dance_name:
            return
        
        # 设置表格列
        self.results_tree['columns'] = ('rank', 'number', 'name', 'score', 'total_score')
        self.results_tree.column("#0", width=0, stretch=tk.NO)
        self.results_tree.column("rank", anchor=tk.CENTER, width=80)
        self.results_tree.column("number", anchor=tk.CENTER, width=100)
        self.results_tree.column("name", anchor=tk.W, width=200)
        self.results_tree.column("score", anchor=tk.CENTER, width=100)
        self.results_tree.column("total_score", anchor=tk.CENTER, width=100)
        
        self.results_tree.heading("#0", text="", anchor=tk.W)
        self.results_tree.heading("rank", text="排名", anchor=tk.CENTER)
        self.results_tree.heading("number", text="背番号", anchor=tk.CENTER)
        self.results_tree.heading("name", text="选手姓名", anchor=tk.CENTER)
        self.results_tree.heading("score", text="分数", anchor=tk.CENTER)
        self.results_tree.heading("total_score", text="总分", anchor=tk.CENTER)
        
        # 从后台数据获取舞种结果
        success, results, errors = self.results_view_manager.get_dance_results_from_data(
            self.data_manager.current_competition,
            event,
            dance_name
        )
        
        if not success:
            self.logger.error(f"获取舞种结果失败: {errors}")
            messagebox.showerror("错误", f"获取舞种结果失败: {'; '.join(errors)}")
            return
        
        # 添加结果到表格
        for result in results:
            # 从结果数据中获取背番号和选手姓名
            competitor_number = result.get('competitor_number')
            
            # 优先使用结果中的competitor_name字段（已从results.players获取）
            competitor_name = result.get('competitor_name', f"选手{competitor_number}")
            
            # 如果结果中没有选手姓名，再尝试从DataManager获取
            if competitor_name.startswith("选手"):
                # 使用背番号+项目编号获取选手信息
                competitor = self.data_manager.get_competitor_by_number_and_project(competitor_number, event.project_id)
                if competitor:
                    competitor_name = competitor.name
            
            self.results_tree.insert('', tk.END, values=(
                result.get('rank'),
                competitor_number,
                competitor_name,
                f"{result.get('score'):.2f}" if result.get('score') is not None else "",
                f"{result.get('total_score'):.2f}" if result.get('total_score') is not None else ""
            ))
    
    def update_overall_results(self) -> None:
        """更新综合结果表格"""
        # 获取当前场次
        event = self.data_manager.get_event(self.current_event_id)
        if not event:
            return
        
        # 设置表格列
        self.results_tree['columns'] = ('rank', 'number', 'name', 'total_score')
        self.results_tree.column("#0", width=0, stretch=tk.NO)
        self.results_tree.column("rank", anchor=tk.CENTER, width=80)
        self.results_tree.column("number", anchor=tk.CENTER, width=100)
        self.results_tree.column("name", anchor=tk.W, width=200)
        self.results_tree.column("total_score", anchor=tk.CENTER, width=100)
        
        self.results_tree.heading("#0", text="", anchor=tk.W)
        self.results_tree.heading("rank", text="排名", anchor=tk.CENTER)
        self.results_tree.heading("number", text="背番号", anchor=tk.CENTER)
        self.results_tree.heading("name", text="选手姓名", anchor=tk.CENTER)
        self.results_tree.heading("total_score", text="总分", anchor=tk.CENTER)
        
        # 从后台数据获取综合结果
        success, results, errors = self.results_view_manager.get_overall_results_from_data(
            self.data_manager.current_competition,
            event
        )
        
        if not success:
            self.logger.error(f"获取综合结果失败: {errors}")
            messagebox.showerror("错误", f"获取综合结果失败: {'; '.join(errors)}")
            return
        
        # 添加结果到表格
        for result in results:
            # 从结果数据中获取背番号和选手姓名
            competitor_number = result.get('competitor_number')
            
            # 优先使用结果中的competitor_name字段（已从results.players获取）
            competitor_name = result.get('competitor_name', f"选手{competitor_number}")
            
            # 如果结果中没有选手姓名，再尝试从DataManager获取
            if competitor_name.startswith("选手"):
                # 使用背番号+项目编号获取选手信息
                competitor = self.data_manager.get_competitor_by_number_and_project(competitor_number, event.project_id)
                if competitor:
                    competitor_name = competitor.name
            
            self.results_tree.insert('', tk.END, values=(
                result.get('rank'),
                competitor_number,
                competitor_name,
                f"{result.get('total_score'):.2f}" if result.get('total_score') is not None else ""
            ))
    
    def on_event_changed(self, event) -> None:
        """场次选择改变事件"""
        # 获取选中的场次ID
        event_id = self.event_var.get()
        if not event_id:
            return
        
        # 更新当前场次
        self.current_event_id = event_id
        
        # 更新舞种列表
        self.update_dance_list()
        
        # 更新结果表格
        self.update_results_table()
    
    def on_result_type_changed(self, event) -> None:
        """结果类型选择改变事件"""
        result_type = self.result_type_var.get()
        
        # 根据结果类型显示/隐藏舞种选择
        if result_type == "分舞种结果":
            self.dance_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        else:
            self.dance_frame.pack_forget()
        
        # 更新结果表格
        self.update_results_table()
    
    def on_dance_changed(self, event) -> None:
        """舞种选择改变事件"""
        # 更新结果表格
        self.update_results_table()
    
    def update_dance_list(self) -> None:
        """更新舞种列表"""
        # 获取当前场次
        event = self.data_manager.get_event(self.current_event_id)
        if not event:
            return
        
        # 获取舞种列表
        dance_names = [dance.name for dance in event.dances]
        
        # 更新下拉框
        self.dance_combo['values'] = dance_names
        
        # 如果有舞种，选择第一个
        if dance_names:
            self.dance_var.set(dance_names[0])
        else:
            self.dance_var.set("")
    
    def refresh_results(self) -> None:
        """刷新结果"""
        # 更新结果表格
        self.update_results_table()
    
    def show_advancement_confirmation(self) -> None:
        """显示晋级信息确认窗口"""
        if not self.current_event_id:
            messagebox.showwarning("提示", "请先选择一个场次")
            return
        
        # 获取当前场次
        event = self.data_manager.get_event(self.current_event_id)
        if not event:
            messagebox.showerror("错误", "获取场次信息失败")
            return
        
        # 获取项目编号和当前轮次
        project_id = event.project_id
        current_round = event.round
        
        # 检查当前轮次的所有场次是否完成评分
        if not self.data_manager.check_round_scoring_complete(project_id, current_round):
            messagebox.showwarning("提示", f"项目{project_id}的{current_round}轮次尚未全部完成评分")
            return
        
        # 获取下一轮次的所有场次
        next_round_events = self.data_manager.get_next_round_events(project_id, current_round)
        
        if not next_round_events:
            messagebox.showinfo("提示", f"项目{project_id}的{current_round}轮次已经是最后一轮，无需晋级")
            return
        
        # 获取当前轮次的所有场次
        current_round_events = self.data_manager.get_events_by_project_and_round(project_id, current_round)
        
        try:
            from .advancement_confirmation_window import AdvancementConfirmationWindow
            advancement_window = AdvancementConfirmationWindow(
                self.parent, 
                self.data_manager,
                project_id,
                current_round,
                current_round_events,
                next_round_events
            )
            self.logger.info(f"打开晋级信息确认窗口，项目: {project_id}, 轮次: {current_round}")
        except Exception as e:
            messagebox.showerror("错误", f"打开晋级信息确认窗口失败: {str(e)}")
            self.logger.error(f"打开晋级信息确认窗口失败: {str(e)}")