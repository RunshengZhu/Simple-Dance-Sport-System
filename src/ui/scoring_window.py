#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立评分窗口模块
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from ..models.data_manager import data_manager
from ..models.data_models import Event, ScoringType, EventStatus, ScoreRecord
from ..utils.logger import get_logger
from .window_utils import center_window
from .components.dialogs import ScoreInputDialog

logger = get_logger()


class ScoringWindow:
    """独立评分窗口类"""
    
    def __init__(self, parent, event_id, main_window):
        """初始化评分窗口"""
        self.parent = parent
        self.event_id = event_id
        self.main_window = main_window
        self.logger = logger
        
        # 获取场次信息
        self.event = data_manager.get_event(event_id)
        if not self.event:
            messagebox.showerror("错误", f"找不到场次: {event_id}")
            return
        
        # 评分数据
        self.scoring_records = {}  # 存储所有裁判的评分数据
        self.scoring_status = {}   # 存储每个裁判对每个舞种的评分状态
        
        # 当前选择的舞种索引
        self.current_dance_index = 0
        
        # 自动生成的裁判编号计数器
        self.judge_counter = 1
        
        # 背番号确认表相关变量
        self.player_checkboxes = {}  # 存储背番号复选框变量
        self.selected_players = set()  # 存储选中的选手背番号
        
        # 创建窗口
        self.create_window()
        
        # 初始化背番号确认表
        self.initialize_player_selection()
        
        # 加载已有评分数据
        self.load_existing_scores()
        
        # 更新界面
        self.update_all()
        
        self.logger.info(f"独立评分窗口初始化完成，场次: {event_id}")
    
    def load_existing_scores(self):
        """加载已有的评分数据"""
        try:
            # 获取该场次的评分记录
            score_records = data_manager.get_score_records(self.event_id)
            
            if not score_records:
                # 如果没有评分记录，初始化空的数据结构
                self.initialize_scoring_data()
                return
            
            # 按裁判和舞种组织评分数据
            for record in score_records:
                judge_id = record.judge_id
                dance_name = record.dance_name
                player_id = record.competitor_number  # 背番号作为字符串处理
                
                # 根据记录中的字段决定使用哪个字段的值，而不是依赖event.scoring_type
                # 这样可以正确处理不同舞种使用不同评分类型的情况
                if record.placement is not None:
                    # 顺位法：使用placement字段的值
                    score = record.placement
                elif record.mark is not None:
                    # Mark制：使用mark字段的值
                    score = record.mark
                else:
                    # 如果都没有值，跳过这条记录
                    self.logger.warning(f"评分记录缺少有效值: {record}")
                    continue
                
                # 确保数据结构存在
                if judge_id not in self.scoring_records:
                    self.scoring_records[judge_id] = {}
                    self.scoring_status[judge_id] = {}
                
                if dance_name not in self.scoring_records[judge_id]:
                    self.scoring_records[judge_id][dance_name] = {}
                    self.scoring_status[judge_id][dance_name] = True  # 标记为已评分
                
                # 存储评分
                self.scoring_records[judge_id][dance_name][player_id] = score
            
            # 创建评分表格
            for judge_id in self.scoring_records.keys():
                self.create_judge_scoring_table(judge_id)
                # 更新裁判编号计数器，避免重复
                if judge_id.startswith("J") and judge_id[1:].isdigit():
                    judge_num = int(judge_id[1:])
                    if judge_num >= self.judge_counter:
                        self.judge_counter = judge_num + 1
            
            # 如果没有评分记录，初始化空的数据结构
            if not self.scoring_records:
                self.initialize_scoring_data()
                
        except Exception as e:
            self.logger.error(f"加载已有评分数据时出错: {str(e)}")
            # 如果加载失败，初始化空的数据结构
            self.initialize_scoring_data()
    
    def create_window(self):
        """创建评分窗口"""
        # 创建窗口
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"评分输入 - {self.event.name}")
        self.window.geometry("1000x700")
        self.window.minsize(800, 600)
        
        # 使窗口居中
        self.window.transient(self.parent)
        self.window.grab_set()
        center_window(self.window, self.parent)
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建背番号确认表区域
        self.create_player_selection_frame()
        
        # 创建场次信息区域
        self.create_event_info_frame()
        
        # 创建评分数据表格区域
        self.create_scoring_tables_frame()
        
        # 创建操作按钮区域
        self.create_action_frame()
        
        # 绑定窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_player_selection_frame(self):
        """创建背番号确认表区域"""
        # 背番号确认表框架
        player_frame = ttk.LabelFrame(self.main_frame, text="参赛选手确认")
        player_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 第一行：背番号标签
        player_numbers_frame = ttk.Frame(player_frame)
        player_numbers_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 第二行：背番号复选框
        player_checkboxes_frame = ttk.Frame(player_frame)
        player_checkboxes_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 更新按钮
        update_button_frame = ttk.Frame(player_frame)
        update_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        update_button = ttk.Button(
            update_button_frame, 
            text="更新本场参赛选手", 
            command=self.update_selected_players
        )
        update_button.pack(side=tk.LEFT)
        
        # 保存框架引用以便后续更新
        self.player_numbers_frame = player_numbers_frame
        self.player_checkboxes_frame = player_checkboxes_frame
        
        return player_frame
    
    def initialize_player_selection(self):
        """初始化背番号确认表"""
        # 获取所有选手
        players = data_manager.get_players_by_event(self.event_id)
        
        # 清空现有控件
        for widget in self.player_numbers_frame.winfo_children():
            widget.destroy()
        for widget in self.player_checkboxes_frame.winfo_children():
            widget.destroy()
        
        # 清空数据
        self.player_checkboxes.clear()
        self.selected_players.clear()
        
        # 创建背番号标签和复选框
        for i, player in enumerate(players):
            # 第一行：背番号标签
            player_label = ttk.Label(
                self.player_numbers_frame, 
                text=str(player.number)
            )
            player_label.grid(row=0, column=i, padx=5, pady=2)
            
            # 第二行：复选框
            var = tk.BooleanVar(value=True)  # 默认全部选中
            checkbox = ttk.Checkbutton(
                self.player_checkboxes_frame,
                variable=var,
                command=lambda p=player.number, v=var: self.on_player_checkbox_change(p, v)
            )
            checkbox.grid(row=0, column=i, padx=5, pady=2)
            
            # 保存引用
            self.player_checkboxes[player.number] = var
            self.selected_players.add(player.number)
    
    def on_player_checkbox_change(self, player_number, var):
        """处理背番号复选框变化"""
        if var.get():
            self.selected_players.add(player_number)
        else:
            self.selected_players.discard(player_number)
    
    def update_selected_players(self):
        """更新选中的参赛选手"""
        # 检查是否有选中的选手
        if not self.selected_players:
            messagebox.showwarning("警告", "请至少选择一名参赛选手！")
            return
        
        # 确认对话框
        result = messagebox.askyesno(
            "确认更新", 
            f"更新参赛选手将清空当前所有评分数据，是否继续？\n"
            f"当前选中选手: {sorted(self.selected_players)}"
        )
        
        if not result:
            return
        
        try:
            # 清空后台结果和评分数据
            data_manager.clear_event_results(self.event_id)
            
            # 清空评分界面UI上的评分数据
            self.scoring_records.clear()
            self.scoring_status.clear()
            
            # 清空评分表格
            for table_widget in self.scoring_tables.values():
                # 获取表格框架并销毁
                if isinstance(table_widget, dict) and "frame" in table_widget:
                    table_widget["frame"].destroy()
                elif hasattr(table_widget, 'destroy'):
                    table_widget.destroy()
            self.scoring_tables.clear()
            
            # 清空所有可能的UI元素
            for child in self.scrollable_frame.winfo_children():
                if isinstance(child, ttk.LabelFrame) and child.cget("text").startswith("评分表 "):
                    child.destroy()
            
            # 重新显示初始提示
            if hasattr(self, 'initial_label') and self.initial_label is not None:
                self.initial_label.pack(pady=50)
            elif not hasattr(self, 'initial_label'):
                # 如果初始提示不存在，重新创建
                self.initial_label = ttk.Label(
                    self.scrollable_frame, 
                    text="点击'添加评分'按钮创建评分表格",
                    font=("TkDefaultFont", 12)
                )
                self.initial_label.pack(pady=50)
            
            # 重新初始化评分数据结构
            self.initialize_scoring_data()
            
            # 更新状态标签
            self.status_label.config(text="评分状态: 已更新参赛选手，请重新评分")
            
            self.logger.info(f"已更新场次 {self.event_id} 的参赛选手为: {sorted(self.selected_players)}")
            messagebox.showinfo("成功", f"已更新参赛选手为: {sorted(self.selected_players)}")
            
        except Exception as e:
            self.logger.error(f"更新参赛选手时出错: {str(e)}")
            messagebox.showerror("错误", f"更新参赛选手失败: {str(e)}")
    
    def create_event_info_frame(self):
        """创建场次信息区域"""
        # 场次信息框架
        info_frame = ttk.LabelFrame(self.main_frame, text="场次信息")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 场次基本信息
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X, padx=5, pady=5)
        
        # 场次ID
        ttk.Label(info_grid, text="场次ID:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.event_id).grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # 场次名称
        ttk.Label(info_grid, text="场次名称:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.event.name).grid(row=0, column=3, sticky=tk.W, padx=(0, 20))
        
        # 项目编号
        ttk.Label(info_grid, text="项目编号:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.event.project_id).grid(row=1, column=1, sticky=tk.W, padx=(0, 20))
        
        # 轮次
        ttk.Label(info_grid, text="轮次:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.event.round).grid(row=1, column=3, sticky=tk.W, padx=(0, 20))
        
        # 评分类型
        ttk.Label(info_grid, text="评分类型:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.event.scoring_type.value).grid(row=2, column=1, sticky=tk.W, padx=(0, 20))
        
        # 舞种
        ttk.Label(info_grid, text="舞种:").grid(row=2, column=2, sticky=tk.W, padx=(0, 5))
        dances_str = ", ".join([dance.name for dance in self.event.dances])
        ttk.Label(info_grid, text=dances_str).grid(row=2, column=3, sticky=tk.W, padx=(0, 20))
        
        # 参赛选手数量
        players = data_manager.get_players_by_event(self.event_id)
        ttk.Label(info_grid, text="参赛选手数量:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=str(len(players))).grid(row=3, column=1, sticky=tk.W, padx=(0, 20))
        
        # 场次状态
        ttk.Label(info_grid, text="场次状态:").grid(row=3, column=2, sticky=tk.W, padx=(0, 5))
        status_text = self.event.status.value if hasattr(self.event.status, 'value') else str(self.event.status)
        status_color = "green" if self.event.status == EventStatus.COMPLETED else "orange" if self.event.status == EventStatus.IN_PROGRESS else "black"
        status_label = ttk.Label(info_grid, text=status_text, foreground=status_color)
        status_label.grid(row=3, column=3, sticky=tk.W, padx=(0, 20))
    
    def create_scoring_tables_frame(self):
        """创建评分数据表格区域"""
        # 评分数据框架
        tables_frame = ttk.LabelFrame(self.main_frame, text="评分数据")
        tables_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建滚动区域
        canvas = tk.Canvas(tables_frame)
        scrollbar = ttk.Scrollbar(tables_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 初始提示
        self.initial_label = ttk.Label(
            self.scrollable_frame, 
            text="点击'添加评分'按钮创建评分表格",
            font=("TkDefaultFont", 12)
        )
        self.initial_label.pack(pady=50)
        
        # 存储评分表格
        self.scoring_tables = {}
    
    def create_action_frame(self):
        """创建操作按钮区域"""
        # 操作按钮框架
        action_frame = ttk.Frame(self.main_frame)
        action_frame.pack(fill=tk.X)
        
        # 按钮区域
        button_frame = ttk.Frame(action_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 添加评分按钮
        add_scoring_button = ttk.Button(
            button_frame, 
            text="添加评分", 
            command=self.add_scoring_table
        )
        add_scoring_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 随机生成评分按钮
        random_scores_button = ttk.Button(
            button_frame, 
            text="随机生成评分", 
            command=self.add_random_scores
        )
        random_scores_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 删除了保存评分按钮，现在通过完成按钮自动保存
        
        # 清空评分按钮
        clear_button = ttk.Button(
            button_frame, 
            text="清空评分", 
            command=self.clear_scoring
        )
        clear_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 完成按钮
        finish_button = ttk.Button(
            button_frame, 
            text="完成", 
            command=self.finish_and_view_results
        )
        finish_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 删除了重新计算结果按钮，现在通过完成按钮自动计算结果
        
        # 关闭按钮
        close_button = ttk.Button(
            button_frame, 
            text="关闭", 
            command=self.on_closing
        )
        close_button.pack(side=tk.RIGHT)
        
        # 状态标签
        status_text = "评分状态: "
        if self.event.status == EventStatus.COMPLETED:
            status_text += "已完成"
        elif self.event.status == EventStatus.IN_PROGRESS:
            status_text += "进行中"
        else:
            status_text += "未开始"
            
        self.status_label = ttk.Label(action_frame, text=status_text)
        self.status_label.pack(anchor=tk.W)
    
    def initialize_scoring_data(self):
        """初始化评分数据"""
        # 获取裁判列表
        judges = list(data_manager.current_competition.judges.keys()) if data_manager.current_competition.judges else []
        
        # 如果没有裁判，创建默认裁判
        if not judges:
            from ..models.data_models import Judge
            default_judge = Judge(id="J1", name="默认裁判")
            data_manager.add_judge(default_judge)
            judges = ["J1"]
        
        # 初始化评分数据结构
        for judge_id in judges:
            self.scoring_records[judge_id] = {}
            self.scoring_status[judge_id] = {}
            
            for dance in self.event.dances:
                self.scoring_records[judge_id][dance.name] = {}
                self.scoring_status[judge_id][dance.name] = False
    
    def add_scoring_table(self):
        """添加评分表格"""
        # 生成新的裁判编号
        judge_id = f"J{self.judge_counter}"
        self.judge_counter += 1
        
        # 创建评分表格
        self.create_judge_scoring_table(judge_id)
        self.update_scoring_status()
    
    def create_judge_scoring_table(self, judge_id):
        """为指定裁判创建评分表格"""
        # 移除初始提示
        if hasattr(self, 'initial_label') and self.initial_label:
            self.initial_label.destroy()
            self.initial_label = None
        
        # 创建裁判评分框架
        judge_frame = ttk.LabelFrame(self.scrollable_frame, text=f"评分表 {judge_id}")
        judge_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 裁判信息框架
        judge_info_frame = ttk.Frame(judge_frame)
        judge_info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 裁判姓名输入
        ttk.Label(judge_info_frame, text="裁判姓名:").pack(side=tk.LEFT, padx=(0, 5))
        judge_name_var = tk.StringVar(value=f"裁判{judge_id}")
        judge_name_entry = ttk.Entry(judge_info_frame, textvariable=judge_name_var, width=20)
        judge_name_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # 删除按钮
        delete_button = ttk.Button(
            judge_info_frame, 
            text="删除", 
            command=lambda: self.delete_judge_scoring_table(judge_id)
        )
        delete_button.pack(side=tk.RIGHT)
        
        # 创建评分表格框架
        table_frame = ttk.Frame(judge_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 获取选手数据，但只包含选中的选手
        all_players = data_manager.get_players_by_event(self.event_id)
        players = [p for p in all_players if p.number in self.selected_players]
        
        # 创建评分数据存储
        if judge_id not in self.scoring_records:
            self.scoring_records[judge_id] = {}
            self.scoring_status[judge_id] = {}
        
        if self.event.scoring_type == ScoringType.MARK:
            # Mark制：使用Treeview创建表格
            self._create_mark_scoring_table(table_frame, judge_id, judge_name_var, players)
        else:
            # 顺位法：保持原有实现
            self._create_placement_scoring_table(table_frame, judge_id, judge_name_var, players)
        
        # 保存表格引用
        self.scoring_tables[judge_id] = {
            "judge_name_var": judge_name_var,
            "frame": judge_frame  # 保存框架引用以便后续销毁
        }
    
    def _create_mark_scoring_table(self, parent_frame, judge_id, judge_name_var, players):
        """创建Mark制评分表格"""
        # 创建Treeview表格
        columns = ("dance",) + tuple(str(p.number) for p in players)
        tree = ttk.Treeview(parent_frame, columns=columns, show="headings", height=len(self.event.dances)+1)
        
        # 设置列标题
        tree.heading("dance", text="舞种")
        for p in players:
            tree.heading(str(p.number), text=str(p.number))
        
        # 设置列宽
        tree.column("dance", width=100)
        for p in players:
            tree.column(str(p.number), width=60)
        
        # 添加滚动条
        scrollbar_v = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar_h = ttk.Scrollbar(parent_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)
        
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_v.grid(row=0, column=1, sticky="ns")
        scrollbar_h.grid(row=1, column=0, sticky="ew")
        
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)
        
        # 添加舞种行数据
        item_ids = {}
        for dance in self.event.dances:
            # 确保该舞种的评分记录存在
            if dance.name not in self.scoring_records[judge_id]:
                self.scoring_records[judge_id][dance.name] = {}
                self.scoring_status[judge_id][dance.name] = False
            
            # 添加舞种行
            values = [dance.name]
            for p in players:
                # 检查是否已有评分数据
                # 对于Mark制表格，我们只关心mark字段的值
                has_score = False
                if p.number in self.scoring_records[judge_id][dance.name]:
                    score = self.scoring_records[judge_id][dance.name][p.number]
                    # 检查评分值是否为布尔类型（Mark制）
                    if isinstance(score, bool):
                        has_score = score
                
                values.append("☑" if has_score else "□")
            
            item_id = tree.insert("", tk.END, values=values)
            item_ids[dance.name] = item_id
        
        # 绑定点击事件
        def on_tree_click(event):
            # 获取点击的位置
            region = tree.identify_region(event.x, event.y)
            if region != "cell":
                return
            
            # 获取点击的行和列
            column = tree.identify_column(event.x)
            item = tree.identify_row(event.y)
            
            # 如果点击的不是第一列（舞种列）
            if column != "#1" and item:
                # 获取舞种名称
                dance_name = tree.item(item, "values")[0]
                
                # 获取选手编号
                col_index = int(column[1:]) - 2  # 从列号转换为选手索引（减去舞种列）
                if 0 <= col_index < len(players):
                    player_number = players[col_index].number
                    
                    # 确保评分记录存在
                    if dance_name not in self.scoring_records[judge_id]:
                        self.scoring_records[judge_id][dance_name] = {}
                        self.scoring_status[judge_id][dance_name] = False
                    
                    # 切换选择状态
                    if player_number in self.scoring_records[judge_id][dance_name]:
                        # 已有评分，移除
                        del self.scoring_records[judge_id][dance_name][player_number]
                        new_state = False
                    else:
                        # 没有评分，添加
                        # Mark制使用bool类型，True表示选中
                        self.scoring_records[judge_id][dance_name][player_number] = True
                        new_state = True
                    
                    # 更新显示
                    values = list(tree.item(item, "values"))
                    values[col_index+1] = "☑" if new_state else "□"  # +1因为values列表包含舞种名称
                    tree.item(item, values=values)
                    
                    # 更新状态
                    self.update_scoring_status(judge_id, dance_name)
        
        tree.bind("<ButtonRelease-1>", on_tree_click)
        
        # 添加控制按钮
        btn_frame = ttk.Frame(parent_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        
        def select_all():
            """全选所有选手在所有舞种"""
            for dance in self.event.dances:
                # 确保评分记录存在
                if dance.name not in self.scoring_records[judge_id]:
                    self.scoring_records[judge_id][dance.name] = {}
                    self.scoring_status[judge_id][dance.name] = False
                
                for p in players:
                    # 添加评分
                    # Mark制使用bool类型，True表示选中
                    self.scoring_records[judge_id][dance.name][p.number] = True
                
                # 更新状态
                self.scoring_status[judge_id][dance.name] = True
                
                # 更新显示
                if dance.name in item_ids:
                    item = item_ids[dance.name]
                    values = list(tree.item(item, "values"))
                    for i in range(len(players)):
                        values[i+1] = "☑"
                    tree.item(item, values=values)
            
            # 更新整体状态
            self.update_scoring_status()
        
        def deselect_all():
            """取消选择所有选手在所有舞种"""
            for dance in self.event.dances:
                # 清空评分
                self.scoring_records[judge_id][dance.name] = {}
                self.scoring_status[judge_id][dance.name] = False
                
                # 更新显示
                if dance.name in item_ids:
                    item = item_ids[dance.name]
                    values = list(tree.item(item, "values"))
                    for i in range(len(players)):
                        values[i+1] = "□"
                    tree.item(item, values=values)
            
            # 更新整体状态
            self.update_scoring_status()
        
        ttk.Button(btn_frame, text="全选", command=select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消全选", command=deselect_all).pack(side=tk.LEFT, padx=5)
        
        # 添加说明
        note_frame = ttk.Frame(parent_frame)
        note_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(note_frame, text="说明: 点击☑/□选择选手在该舞种中晋级").pack(side=tk.LEFT)
    
    def _create_placement_scoring_table(self, parent_frame, judge_id, judge_name_var, players):
        """创建顺位法评分表格（保持原有实现）"""
        # 创建表格标题行
        header_frame = ttk.Frame(parent_frame)
        header_frame.pack(fill=tk.X)
        
        # 舞种标题
        ttk.Label(header_frame, text="舞种", width=10, relief=tk.RAISED).pack(side=tk.LEFT, padx=1, pady=1)
        
        # 选手背番号标题
        for player in players:
            ttk.Label(header_frame, text=str(player.number), width=8, relief=tk.RAISED).pack(side=tk.LEFT, padx=1, pady=1)
        
        # 创建舞种行
        for dance in self.event.dances:
            dance_frame = ttk.Frame(parent_frame)
            dance_frame.pack(fill=tk.X)
            
            # 舞种名称
            ttk.Label(dance_frame, text=dance.name, width=10, relief=tk.SUNKEN).pack(side=tk.LEFT, padx=1, pady=1)
            
            # 确保该舞种的评分记录存在
            if dance.name not in self.scoring_records[judge_id]:
                self.scoring_records[judge_id][dance.name] = {}
                self.scoring_status[judge_id][dance.name] = False
            
            # 为每个选手创建评分单元格
            for player in players:
                player_id = player.number
                
                # 顺位法：使用文本输入框
                entry_var = tk.StringVar()
                entry = ttk.Entry(dance_frame, textvariable=entry_var, width=8)
                entry.pack(side=tk.LEFT, padx=1, pady=1)
                
                # 绑定输入验证
                entry.bind(
                    '<FocusOut>',
                    lambda e, j=judge_id, d=dance.name, p=player_id, v=entry_var: 
                        self.on_placement_entry_changed(e, j, d, p, v)
                )
                entry.bind(
                    '<Return>',
                    lambda e, j=judge_id, d=dance.name, p=player_id, v=entry_var: 
                        self.on_placement_entry_changed(e, j, d, p, v)
                )
                
                # 如果已有评分数据，设置输入框值
                if player_id in self.scoring_records[judge_id][dance.name]:
                    score = self.scoring_records[judge_id][dance.name][player_id]
                    # 对于顺位法表格，我们只关心placement字段的值
                    # 检查评分值是否为整数类型（顺位法）
                    if isinstance(score, int):
                        entry_var.set(str(score))
    
    def delete_judge_scoring_table(self, judge_id):
        """删除裁判评分表格"""
        if judge_id in self.scoring_tables:
            # 查找并删除裁判评分框架
            for child in self.scrollable_frame.winfo_children():
                if isinstance(child, ttk.LabelFrame) and child.cget("text") == f"评分表 {judge_id}":
                    child.destroy()
                    break
            
            # 删除表格引用
            del self.scoring_tables[judge_id]
            
            # 删除评分数据
            if judge_id in self.scoring_records:
                del self.scoring_records[judge_id]
            
            # 删除评分状态
            if judge_id in self.scoring_status:
                del self.scoring_status[judge_id]
            
            # 更新状态
            self.update_scoring_status()
            
            # 如果没有表格了，显示初始提示
            if not self.scoring_tables and not hasattr(self, 'initial_label'):
                self.initial_label = ttk.Label(
                    self.scrollable_frame, 
                    text="点击'添加评分'按钮创建评分表格",
                    font=("TkDefaultFont", 12)
                )
                self.initial_label.pack(pady=50)
    
    def on_mark_checkbox_changed(self, judge_id, dance_name, player_id, check_var):
        """处理Mark制复选框变化事件"""
        # 背番号作为字符串处理
        
        # 确保评分记录存在
        if judge_id not in self.scoring_records:
            self.scoring_records[judge_id] = {}
            self.scoring_status[judge_id] = {}
        
        if dance_name not in self.scoring_records[judge_id]:
            self.scoring_records[judge_id][dance_name] = {}
            self.scoring_status[judge_id][dance_name] = False
        
        # 更新评分
        if check_var.get():
            # 选中状态，设置为True（表示选中）
            self.scoring_records[judge_id][dance_name][player_id] = True
        else:
            # 取消选中状态，移除评分
            if player_id in self.scoring_records[judge_id][dance_name]:
                del self.scoring_records[judge_id][dance_name][player_id]
        
        # 更新状态
        self.update_scoring_status(judge_id, dance_name)
    
    def on_placement_entry_changed(self, event, judge_id, dance_name, player_id, entry_var):
        """处理顺位法输入框变化事件"""
        # 背番号作为字符串处理
        
        # 确保评分记录存在
        if judge_id not in self.scoring_records:
            self.scoring_records[judge_id] = {}
            self.scoring_status[judge_id] = {}
        
        if dance_name not in self.scoring_records[judge_id]:
            self.scoring_records[judge_id][dance_name] = {}
            self.scoring_status[judge_id][dance_name] = False
        
        # 获取输入值
        placement_str = entry_var.get().strip()
        
        if placement_str:
            try:
                # 验证输入
                placement = int(placement_str)
                if placement < 1:
                    messagebox.showwarning("警告", "名次必须大于0")
                    entry_var.set("")
                    if player_id in self.scoring_records[judge_id][dance_name]:
                        del self.scoring_records[judge_id][dance_name][player_id]
                    return
                
                # 更新评分
                self.scoring_records[judge_id][dance_name][player_id] = placement
                
            except ValueError:
                messagebox.showwarning("警告", "请输入有效的数字")
                entry_var.set("")
                if player_id in self.scoring_records[judge_id][dance_name]:
                    del self.scoring_records[judge_id][dance_name][player_id]
        else:
            # 空输入，移除评分
            if player_id in self.scoring_records[judge_id][dance_name]:
                del self.scoring_records[judge_id][dance_name][player_id]
        
        # 更新状态
        self.update_scoring_status(judge_id, dance_name)
    
    def add_random_scores(self):
        """添加随机评分"""
        # 如果没有评分表格，先创建一个
        if not self.scoring_tables:
            self.add_scoring_table()
        
        # 生成随机评分
        import random
        all_players = data_manager.get_players_by_event(self.event_id)
        players = [p for p in all_players if p.number in self.selected_players]
        
        for judge_id in self.scoring_tables:
            # 确保该裁判的评分记录存在
            if judge_id not in self.scoring_records:
                self.scoring_records[judge_id] = {}
                self.scoring_status[judge_id] = {}
            
            for dance in self.event.dances:
                # 确保该舞种的评分记录存在
                if dance.name not in self.scoring_records[judge_id]:
                    self.scoring_records[judge_id][dance.name] = {}
                if dance.name not in self.scoring_status[judge_id]:
                    self.scoring_status[judge_id][dance.name] = False
                
                if self.event.scoring_type == ScoringType.MARK:
                    # Mark制：随机选择部分选手给分
                    for player in players:
                        # 随机决定是否给该选手评分
                        if random.random() > 0.3:  # 70%的概率给分
                            self.scoring_records[judge_id][dance.name][player.number] = True  # Mark制使用True表示选中
                        else:
                            # 不给分的情况
                            if player.number in self.scoring_records[judge_id][dance.name]:
                                del self.scoring_records[judge_id][dance.name][player.number]
                    
                    # 检查是否有评分
                    if self.scoring_records[judge_id][dance.name]:
                        self.scoring_status[judge_id][dance.name] = True
                else:
                    # 顺位法：生成不重复的名次
                    placements = list(range(1, len(players) + 1))
                    random.shuffle(placements)
                    for i, player in enumerate(players):
                        self.scoring_records[judge_id][dance.name][player.number] = placements[i]
                    self.scoring_status[judge_id][dance.name] = True
        
        # 重新创建所有表格以更新显示
        self.recreate_all_tables()
        
        # 更新状态
        self.update_scoring_status()
        
        messagebox.showinfo("成功", "随机评分已生成")
    
    def recreate_all_tables(self):
        """重新创建所有评分表格"""
        # 保存当前评分数据
        temp_records = {}
        for judge_id in self.scoring_records:
            temp_records[judge_id] = {}
            for dance_name in self.scoring_records[judge_id]:
                temp_records[judge_id][dance_name] = {}
                for player_id, score in self.scoring_records[judge_id][dance_name].items():
                    temp_records[judge_id][dance_name][player_id] = score
        
        # 保存当前评分状态
        temp_status = {}
        for judge_id in self.scoring_status:
            temp_status[judge_id] = {}
            for dance_name, status in self.scoring_status[judge_id].items():
                temp_status[judge_id][dance_name] = status
        
        # 清除所有表格
        for child in self.scrollable_frame.winfo_children():
            if isinstance(child, ttk.LabelFrame) and child.cget("text").startswith("评分表 "):
                child.destroy()
        
        # 清空表格引用
        self.scoring_tables = {}
        
        # 重新创建表格
        for judge_id in temp_records:
            self.create_judge_scoring_table(judge_id)
        
        # 恢复评分数据
        self.scoring_records = temp_records
        self.scoring_status = temp_status
    
    def update_scoring_status(self, judge_id: str = None, dance_name: str = None):
        """更新评分状态"""
        if judge_id and dance_name:
            # 更新特定裁判和舞种的评分状态
            if judge_id not in self.scoring_records or dance_name not in self.scoring_records[judge_id]:
                self.scoring_status[judge_id][dance_name] = False
                return
            
            # 检查该舞种的评分类型
            # 通过检查评分值的类型来判断评分类型
            has_mark_scores = False
            has_placement_scores = False
            
            for player_id, score in self.scoring_records[judge_id][dance_name].items():
                if isinstance(score, bool):
                    has_mark_scores = True
                elif isinstance(score, int):
                    has_placement_scores = True
            
            # 根据评分类型判断是否已完成评分
            if has_mark_scores:
                # Mark制：只要有评分就认为已完成
                has_scores = len(self.scoring_records[judge_id][dance_name]) > 0
                self.scoring_status[judge_id][dance_name] = has_scores
            elif has_placement_scores:
                # 顺位法：检查是否所有选中的选手都有评分
                all_players = data_manager.get_players_by_event(self.event_id)
                players = [p for p in all_players if p.number in self.selected_players]
                player_count = len(players)
                scored_count = len(self.scoring_records[judge_id][dance_name])
                self.scoring_status[judge_id][dance_name] = scored_count == player_count
            else:
                # 没有评分数据
                self.scoring_status[judge_id][dance_name] = False
        
        # 更新评分状态显示
        # 统计已评分的裁判数量
        total_judges = len(self.scoring_status)
        scored_judges = 0
        
        for judge_id, dances in self.scoring_status.items():
            # 检查该裁判是否对所有舞种都已评分
            all_scored = all(dances.get(dance.name, False) for dance in self.event.dances)
            if all_scored:
                scored_judges += 1
        
        # 更新状态标签
        if total_judges > 0:
            percentage = int(scored_judges / total_judges * 100)
            self.status_label.config(
                text=f"评分状态: 已评分 {scored_judges}/{total_judges} 裁判 ({percentage}%)",
                foreground="green" if scored_judges == total_judges else "orange"
            )
        else:
            self.status_label.config(text="评分状态: 无裁判信息", foreground="gray")
    
    def validate_scoring_data(self):
        """验证评分数据完整性"""
        try:
            # 检查是否有评分表格
            if not self.scoring_records:
                messagebox.showwarning("警告", "没有评分数据！")
                return False
            
            # 检查评分完整性
            missing_scores = []
            for judge_id, judge_data in self.scoring_records.items():
                for dance in self.event.dances:
                    dance_name = dance.name if hasattr(dance, 'name') else dance
                    if dance_name not in judge_data:
                        missing_scores.append(f"裁判 {judge_id} - {dance_name}")
            
            if missing_scores:
                msg = "以下评分尚未完成:\n" + "\n".join(missing_scores)
                msg += "\n\n是否继续保存？"
                if not messagebox.askyesno("提示", msg):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证评分数据时出错: {str(e)}")
            messagebox.showerror("错误", f"验证评分数据失败: {str(e)}")
            return False
    
    def save_scoring(self):
        """保存评分数据"""
        try:
            # 验证评分数据完整性
            if not self.validate_scoring_data():
                return False
            
            # 收集所有评分数据
            all_scores = []
            
            for judge_id, judge_data in self.scoring_records.items():
                for dance_name, dance_data in judge_data.items():
                    for player_id, score in dance_data.items():
                        # 只保存选中的选手的评分数据
                        if player_id not in self.selected_players:
                            continue
                            
                        # 创建评分记录对象
                        import uuid
                        # 背番号作为字符串处理
                        
                        # 根据评分值的类型决定使用哪个字段，而不是依赖event.scoring_type
                        # 这样可以正确处理不同舞种使用不同评分类型的情况
                        if isinstance(score, bool):
                            # Mark制：评分值是布尔类型，保存到mark字段
                            score_record = ScoreRecord(
                                id=str(uuid.uuid4()),  # 生成唯一ID
                                event_id=self.event_id,
                                judge_id=judge_id,
                                dance_name=dance_name,
                                competitor_number=player_id,
                                score=None,  # Mark制下score字段为None
                                mark=score,  # Mark制下mark字段为评分值
                                placement=None  # Mark制下placement字段为None
                            )
                        else:
                            # 顺位法：评分值是整数，保存到placement字段
                            score_record = ScoreRecord(
                                id=str(uuid.uuid4()),  # 生成唯一ID
                                event_id=self.event_id,
                                judge_id=judge_id,
                                dance_name=dance_name,
                                competitor_number=player_id,
                                score=None,  # 顺位法下score字段为None
                                mark=None,   # 顺位法下mark字段为None
                                placement=score  # 顺位法下placement字段为评分值
                            )
                        all_scores.append(score_record)
            
            # 获取现有的评分记录，以便更新而不是删除再添加
            existing_records = data_manager.get_score_records(self.event_id)
            existing_records_map = {}  # 用于快速查找现有记录
            
            # 创建现有记录的映射表，键为 (judge_id, dance_name, competitor_number)
            for record in existing_records:
                key = (record.judge_id, record.dance_name, record.competitor_number)
                existing_records_map[key] = record
            
            # 保存新的评分数据到数据管理器
            save_success_count = 0
            save_total_count = len(all_scores)
            for score_record in all_scores:
                key = (score_record.judge_id, score_record.dance_name, score_record.competitor_number)
                
                # 如果记录已存在，更新它
                if key in existing_records_map:
                    existing_record = existing_records_map[key]
                    # 更新现有记录的值
                    existing_record.mark = score_record.mark
                    existing_record.placement = score_record.placement
                    existing_record.timestamp = score_record.timestamp
                    if data_manager.update_score_record(existing_record):
                        save_success_count += 1
                    else:
                        self.logger.error(f"更新评分记录失败: {existing_record}")
                else:
                    # 如果记录不存在，添加新记录
                    if data_manager.add_score_record(score_record):
                        save_success_count += 1
                    else:
                        self.logger.error(f"保存评分记录失败: {score_record}")
            
            # 检查是否所有记录都保存成功
            if save_success_count != save_total_count:
                self.logger.error(f"部分评分记录保存失败: 成功 {save_success_count}/{save_total_count}")
                messagebox.showerror("错误", f"部分评分记录保存失败: 成功 {save_success_count}/{save_total_count}")
                return False
            
            # 更新场次状态为进行中（如果当前是未开始状态）
            if self.event.status == EventStatus.NOT_STARTED:
                self.event.status = EventStatus.IN_PROGRESS
                data_manager.update_event(self.event)
                # 更新状态标签
                self.status_label.config(text="进行中", foreground="orange")
            
            self.logger.info(f"评分数据保存成功，场次: {self.event_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存评分数据时出错: {str(e)}")
            messagebox.showerror("错误", f"保存评分数据失败: {str(e)}")
            return False
    
    def clear_scoring(self):
        """清空评分"""
        if not self.scoring_tables:
            messagebox.showwarning("提示", "没有评分数据可清空")
            return
        
        # 确认清空
        if not messagebox.askyesno("确认", "确定要清空所有评分数据吗？\n此操作不可恢复！"):
            return
        
        try:
            # 删除所有评分记录
            for judge_id in self.scoring_records:
                for dance_name, dance_data in self.scoring_records[judge_id].items():
                    for player_id in dance_data:
                        # 直接使用player_id作为选手编号，不需要再次获取选手信息
                        data_manager.delete_score_records(
                            event_id=self.event_id,
                            judge_id=judge_id,
                            competitor_number=player_id,  # 已经是str类型
                            dance_name=dance_name
                        )
            
            # 清空内存中的评分记录
            self.scoring_records.clear()
            self.scoring_status.clear()
            
            # 重新创建所有表格
            self.recreate_all_tables()
            
            # 更新状态
            self.update_scoring_status()
            
            # 保存当前赛事
            data_manager.save_competition()
            
            messagebox.showinfo("成功", "所有评分已成功清空")
        
        except Exception as e:
            messagebox.showerror("错误", f"清空评分时发生错误: {str(e)}")
    
    def finish_and_view_results(self):
        """完成评分，自动保存、计算结果并关闭页面"""
        # 检查评分完成状态
        all_complete = True
        missing_scores = []
        
        for judge_id, table_data in self.scoring_tables.items():
            judge_name_var = table_data.get("judge_name_var")
            judge_name = judge_name_var.get() if judge_name_var else judge_id
            
            for dance in self.event.dances:
                if not self.scoring_status.get(judge_id, {}).get(dance.name, False):
                    all_complete = False
                    missing_scores.append(f"{judge_name} - {dance.name}")
        
        if not all_complete:
            msg = "以下评分尚未完成:\n" + "\n".join(missing_scores)
            msg += "\n\n是否继续完成评分？"
            if not messagebox.askyesno("提示", msg):
                return
        
        try:
            # 保存当前评分数据
            if not self.save_scoring():
                return
            
            # 调用评分算法计算结果
            from ..algorithms.scoring import ScoringAlgorithm
            scoring_algorithm = ScoringAlgorithm()
            
            # 获取评分记录
            score_records = data_manager.get_score_records(self.event_id)
            
            # 获取所有参赛选手
            all_competitors = self.event.competitors
            
            # 只包含选中的选手
            selected_competitors = [comp for comp in all_competitors if comp in self.selected_players]
            
            # 清除旧的结果，确保重新计算
            if hasattr(data_manager.current_competition, 'results') and self.event_id in data_manager.current_competition.results:
                del data_manager.current_competition.results[self.event_id]
                self.logger.info(f"已清除场次 {self.event_id} 的旧结果")
            
            # 强制重新计算结果，传递晋级人数参数和晋级规则
            self.logger.info(f"场次 {self.event_id} 正在重新计算结果...")
            success, results_dict, errors, score_details, overall_score_details = scoring_algorithm.calculate_results(
                score_records=score_records, 
                scoring_type=self.event.scoring_type,
                advancement_count=self.event.advancement_count,  # 传递晋级人数
                advancement_rule=self.event.advancement_rule,  # 传递晋级规则
                all_competitors=selected_competitors  # 只传递选中的参赛选手
            )
            
            if not success:
                error_msg = "\n".join(errors)
                self.logger.error(f"计算结果失败: {error_msg}")
                messagebox.showerror("错误", f"计算结果失败: {error_msg}")
                return
            
            # 添加日志确保计分方式和场次类型对应
            self.logger.info(f"场次 {self.event_id} 的评分类型: {self.event.scoring_type.value}, "
                            f"正在计算结果...")
            
            # 构建结果数据结构
            results_data = {
                'type': self.event.scoring_type.value,
                'dance_results': {},  # 按舞种分组的结果
                'overall_results': [],  # 综合结果
                'players': {},  # 选手信息
                'scoring_type': self.event.scoring_type.value  # 添加评分类型字段
            }
            
            # 处理按舞种分组的结果
            for dance_name, dance_results in results_dict.get('dance_results', {}).items():
                results_data['dance_results'][dance_name] = []
                for result in dance_results:
                    # 创建结果字典，包含晋级状态和并列信息
                    result_dict = {
                        'competitor_number': result.competitor_number,
                        'rank': result.rank,
                        'score': result.score,
                        'total_score': result.total_score,
                        'advancement_status': getattr(result, 'advancement_status', False),
                        'tied_with': getattr(result, 'tied_with', [])
                    }
                    results_data['dance_results'][dance_name].append(result_dict)
                    
                    # 添加选手信息
                    if result.competitor_number not in results_data['players']:
                        # 使用新的方法，通过背番号+项目编号获取选手信息
                        player = data_manager.get_competitor_by_number_and_project(result.competitor_number, self.event.project_id)
                        results_data['players'][result.competitor_number] = player.name if player else f"选手 {result.competitor_number}"
            
            # 处理综合结果，包含晋级状态
            for result in results_dict.get('overall_results', []):
                result_dict = {
                    'competitor_number': result.competitor_number,
                    'rank': result.rank,
                    'score': result.score,
                    'total_score': result.total_score,
                    'advancement_status': getattr(result, 'advancement_status', False),
                    'tied_with': getattr(result, 'tied_with', [])
                }
                results_data['overall_results'].append(result_dict)
            
            # 添加场次信息
            results_data['event_info'] = {
                'id': self.event.id,
                'name': self.event.name,
                'advancement_count': self.event.advancement_count,
                'scoring_type': self.event.scoring_type.value
            }
            
            # 添加打分明细（如果存在）
            if score_details:
                results_data['score_details'] = score_details
                self.logger.info(f"已添加舞种打分明细，包含 {len(score_details)} 个舞种的详细信息")
            
            if overall_score_details:
                results_data['overall_score_details'] = overall_score_details
                self.logger.info("已添加综合打分明细")
            
            # 保存结果数据，覆盖旧的结果
            if not data_manager.save_results(self.event_id, results_data):
                messagebox.showerror("错误", "保存结果失败")
                return
            
            # 刷新单位总分
            try:
                data_manager.calculate_unit_points()
                # 刷新打开的单位总分排名窗口
                from ..ui.main_window import _unit_ranking_windows
                for window in _unit_ranking_windows:
                    if hasattr(window, 'refresh'):
                        window.refresh()
            except Exception as e:
                self.logger.warning(f"刷新单位总分时出错: {str(e)}")
            
            self.logger.info(f"场次 {self.event_id} 的结果已重新计算并保存")
            
            # 更新场次状态为已完成
            self.event.status = EventStatus.COMPLETED
            data_manager.update_event(self.event)
            
            # 更新状态标签
            self.status_label.config(text="已完成", foreground="green")
            
            # 自动导出结果文件
            try:
                export_success = data_manager.auto_export_event_results(self.event_id)
                if export_success:
                    self.logger.info(f"场次 {self.event_id} 的结果已自动导出")
                else:
                    self.logger.warning(f"场次 {self.event_id} 的结果自动导出失败")
            except Exception as e:
                self.logger.error(f"自动导出结果时出错: {str(e)}")
            
            # 关闭评分窗口
            self.window.destroy()
            
            # 刷新赛程管理页面以显示最新结果
            if hasattr(self.main_window, 'schedule_management_tab'):
                self.main_window.schedule_management_tab.refresh()
                # 在赛程管理页面自动选中当前场次
                if hasattr(self.main_window.schedule_management_tab, 'event_tree'):
                    tree = self.main_window.schedule_management_tab.event_tree
                    # 遍历所有项目，找到匹配的场次ID
                    for item in tree.get_children():
                        values = tree.item(item, 'values')
                        if values and values[0] == self.event_id:  # 假设第一列是ID
                            tree.selection_set(item)
                            tree.focus(item)
                            tree.see(item)  # 滚动到可见区域
                            break
                
                # 调用calculate_results方法检查是否需要打开晋级确认窗口
                self.main_window.schedule_management_tab.calculate_results()
            
        except Exception as e:
            self.logger.error(f"完成评分时出错: {str(e)}")
            messagebox.showerror("错误", f"完成评分失败: {str(e)}")
    
    def recalculate_results(self):
        """重新计算结果"""
        try:
            # 保存当前评分数据
            if not self.save_scoring():
                return
            
            # 调用评分算法计算结果
            from ..algorithms.scoring import ScoringAlgorithm
            scoring_algorithm = ScoringAlgorithm()
            
            # 获取评分记录
            score_records = data_manager.get_score_records(self.event_id)
            
            # 获取所有参赛选手
            all_competitors = self.event.competitors
            
            # 只包含选中的选手
            selected_competitors = [comp for comp in all_competitors if comp in self.selected_players]
            
            # 计算结果
            success, results_dict, errors, score_details, overall_score_details = scoring_algorithm.calculate_results(
                score_records, 
                self.event.scoring_type,
                all_competitors=selected_competitors  # 只传递选中的参赛选手
            )
            
            if not success:
                error_msg = "\n".join(errors)
                self.logger.error(f"计算结果失败: {error_msg}")
                messagebox.showerror("错误", f"计算结果失败: {error_msg}")
                return
            
            # 添加日志确保计分方式和场次类型对应
            self.logger.info(f"场次 {self.event_id} 的评分类型: {self.event.scoring_type.value}, "
                            f"正在重新计算结果...")
            
            # 构建结果数据结构
            results_data = {
                'type': self.event.scoring_type.value,
                'dance_results': {},  # 按舞种分组的结果
                'overall_results': [],  # 综合结果
                'players': {},  # 选手信息
                'scoring_type': self.event.scoring_type.value  # 添加评分类型字段
            }
            
            # 处理按舞种分组的结果
            for dance_name, dance_results in results_dict.get('dance_results', {}).items():
                results_data['dance_results'][dance_name] = []
                for result in dance_results:
                    results_data['dance_results'][dance_name].append({
                        'competitor_number': result.competitor_number,
                        'rank': result.rank,
                        'score': result.score,
                        'total_score': result.total_score
                    })
                    
                    # 添加选手信息
                    if result.competitor_number not in results_data['players']:
                        # 使用新的方法，通过背番号+项目编号获取选手信息
                        player = data_manager.get_competitor_by_number_and_project(result.competitor_number, self.event.project_id)
                        results_data['players'][result.competitor_number] = player.name if player else f"选手 {result.competitor_number}"
            
            # 处理综合结果
            for result in results_dict.get('overall_results', []):
                results_data['overall_results'].append({
                    'competitor_number': result.competitor_number,
                    'rank': result.rank,
                    'score': result.score,
                    'total_score': result.total_score
                })
            
            # 添加打分明细（如果存在）
            if score_details:
                results_data['score_details'] = score_details
                self.logger.info(f"重新计算：已添加舞种打分明细，包含 {len(score_details)} 个舞种的详细信息")
            
            if overall_score_details:
                results_data['overall_score_details'] = overall_score_details
                self.logger.info("重新计算：已添加综合打分明细")
            
            # 保存结果数据
            data_manager.save_results(self.event_id, results_data)
            
            # 刷新单位总分
            try:
                data_manager.calculate_unit_points()
                from ..ui.main_window import _unit_ranking_windows
                for window in _unit_ranking_windows:
                    if hasattr(window, 'refresh'):
                        window.refresh()
            except Exception as e:
                self.logger.warning(f"刷新单位总分时出错: {str(e)}")
            
            # 更新场次状态为已完成
            self.event.status = EventStatus.COMPLETED
            data_manager.update_event(self.event)
            
            # 更新状态标签
            self.status_label.config(text="已完成", foreground="green")
            
            messagebox.showinfo("成功", "结果重新计算并保存成功！")
            
        except Exception as e:
            self.logger.error(f"重新计算结果时出错: {str(e)}")
            messagebox.showerror("错误", f"重新计算结果失败: {str(e)}")
    
    def is_scoring_complete(self):
        """检查评分是否完成"""
        try:
            # 检查是否有评分表格
            if not self.scoring_records:
                return False
            
            # 检查所有评分是否完成
            for judge_id, judge_data in self.scoring_records.items():
                for dance in self.event.dances:
                    dance_name = dance.name if hasattr(dance, 'name') else dance
                    if dance_name not in judge_data:
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"检查评分完成状态时出错: {str(e)}")
            return False
    
    def update_all(self):
        """更新所有界面元素"""
        self.update_scoring_status()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 检查是否有未保存的评分数据
        has_unsaved = False
        for judge_id, judge_data in self.scoring_records.items():
            for dance_name, dance_data in judge_data.items():
                if dance_data:  # 如果有评分数据
                    has_unsaved = True
                    break
            if has_unsaved:
                break
        
        if has_unsaved:
            result = messagebox.askyesnocancel(
                "确认关闭", 
                "有未保存的评分数据，是否保存？\n\n点击'是'保存并关闭\n点击'否'不保存直接关闭\n点击'取消'返回"
            )
            
            if result is None:  # 取消
                return
            elif result:  # 是
                self.save_scoring()
        
        # 关闭窗口
        self.window.destroy()
    
    def show_results_window(self, results):
        """显示结果窗口"""
        try:
            # 创建结果窗口
            results_window = tk.Toplevel(self.window)
            results_window.title(f"评分结果 - {self.event.name}")
            results_window.geometry("800x600")
            results_window.resizable(True, True)
            
            # 使窗口居中
            results_window.transient(self.window)
            results_window.grab_set()
            center_window(results_window, self.window)
            
            # 创建主框架
            main_frame = ttk.Frame(results_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 创建标题
            title_label = ttk.Label(main_frame, text=f"{self.event.name} - 评分结果")
            title_label.pack(pady=(0, 10))
            
            # 创建结果表格
            columns = ("排名", "选手编号", "选手姓名", "总分")
            tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=20)
            
            # 设置列标题
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150, anchor=tk.CENTER)
            
            # 添加结果数据
            for result in results:
                # 获取选手信息
                player = data_manager.get_competitor_by_number_and_project(result.competitor_number, self.event.project_id)
                player_name = player.name if player else f"选手 {result.competitor_number}"
                
                # 添加到表格
                tree.insert("", tk.END, values=(
                    result.rank,
                    result.competitor_number,
                    player_name,
                    f"{result.total_score:.2f}"
                ))
            
            # 添加滚动条
            scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            # 布局
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 添加按钮框架
            button_frame = ttk.Frame(results_window)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            # 导出按钮
            export_button = ttk.Button(button_frame, text="导出结果", 
                                      command=lambda: self.export_results(results))
            export_button.pack(side=tk.LEFT, padx=(0, 10))
            
            # 关闭按钮
            close_button = ttk.Button(button_frame, text="关闭", 
                                     command=results_window.destroy)
            close_button.pack(side=tk.RIGHT)
            
        except Exception as e:
            self.logger.error(f"显示结果窗口时出错: {str(e)}")
            messagebox.showerror("错误", f"显示结果窗口失败: {str(e)}")
    
    def export_results(self, results):
        """导出结果"""
        try:
            # 选择保存路径
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
                title="导出结果"
            )
            
            if not file_path:
                return
            
            # 导出CSV
            import csv
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # 写入标题
                writer.writerow(["排名", "选手编号", "选手姓名", "总分"])
                
                # 写入数据
                for result in results:
                    # 获取选手信息
                    player = data_manager.get_competitor_by_number_and_project(result.competitor_number, self.event.project_id)
                    player_name = player.name if player else f"选手 {result.competitor_number}"
                    
                    writer.writerow([
                        result.rank,
                        result.competitor_number,
                        player_name,
                        f"{result.total_score:.2f}"
                    ])
            
            messagebox.showinfo("成功", f"结果已导出到: {file_path}")
            
        except Exception as e:
            self.logger.error(f"导出结果时出错: {str(e)}")
            messagebox.showerror("错误", f"导出结果失败: {str(e)}")