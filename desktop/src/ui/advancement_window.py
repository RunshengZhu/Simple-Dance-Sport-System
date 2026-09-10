#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
晋级选手选择窗口模块
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Optional, Any

from ..models.data_models import EventStatus
from ..utils.logger import get_logger
from .window_utils import center_window

logger = get_logger()


class AdvancementWindow:
    """晋级选手选择窗口类"""
    
    def __init__(self, parent, data_manager, event):
        """
        初始化晋级选手选择窗口
        
        Args:
            parent: 父窗口
            data_manager: 数据管理器实例
            event: 当前场次对象（需要导入晋级选手的场次）
        """
        self.parent = parent
        self.data_manager = data_manager
        self.event = event
        self.logger = logger
        
        # 查找所有前置轮次
        self.previous_events = self._find_previous_events()
        
        # 当前选中的前置轮次
        self.selected_previous_event = None
        
        # 前置轮次结果
        self.previous_results = None
        
        # 晋级选手列表
        self.advanced_competitors = []
        
        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title(f"导入晋级选手 - {self.event.name}")
        self.window.geometry("900x700")
        self.window.resizable(True, True)
        
        # 使窗口居中
        self.window.transient(parent)
        self.window.grab_set()
        center_window(self.window, parent)
        
        # 创建UI组件
        self._create_widgets()
        
        # 加载前置轮次列表
        self._load_previous_events_list()
    
    def _find_previous_events(self) -> List[Any]:
        """
        查找所有前置轮次
        
        Returns:
            前置轮次Event对象列表
        """
        if not self.data_manager.current_competition:
            return []
        
        # 获取所有场次
        events = list(self.data_manager.current_competition.events.values())
        
        # 按轮次类型排序
        round_order = {"初赛": 0, "复赛": 1, "半决赛": 2, "决赛": 3}
        
        # 筛选相同项目编号的场次
        same_project_events = [
            e for e in events 
            if e.project_id == self.event.project_id
        ]
        
        # 按轮次排序（使用原始轮次数据）
        try:
            # 尝试将轮次转换为数字进行排序
            same_project_events.sort(key=lambda e: int(e.round) if e.round.isdigit() else 0)
        except (ValueError, AttributeError):
            # 如果转换失败，使用默认排序
            same_project_events.sort(key=lambda e: str(e.round))
        
        # 查找当前场次之前的所有场次
        previous_events = []
        for e in same_project_events:
            if e.id == self.event.id:
                break
            previous_events.append(e)
        
        return previous_events
    
    def _create_widgets(self):
        """创建UI组件"""
        # 标题
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        title_text = f"从同项目的前置轮次导入晋级选手到 {self.event.name}"
        title_label = ttk.Label(title_frame, text=title_text, font=("TkDefaultFont", 14, "bold"))
        title_label.pack()
        
        # 前置轮次选择区域
        event_select_frame = ttk.LabelFrame(self.window, text="选择前置轮次")
        event_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 场次选择下拉框
        event_frame = ttk.Frame(event_select_frame)
        event_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(event_frame, text="前置轮次:").pack(side=tk.LEFT, padx=(0, 5))
        self.previous_event_var = tk.StringVar()
        self.previous_event_combo = ttk.Combobox(
            event_frame, 
            textvariable=self.previous_event_var, 
            state="readonly"
        )
        self.previous_event_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.previous_event_combo.bind("<<ComboboxSelected>>", self._on_previous_event_changed)
        
        # 结果说明
        info_frame = ttk.LabelFrame(self.window, text="前置轮次结果")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.results_label = ttk.Label(info_frame, text="请先选择一个前置轮次")
        self.results_label.pack(padx=10, pady=5)
        
        # 选手选择区域
        select_frame = ttk.LabelFrame(self.window, text="选择晋级选手")
        select_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建选手表格
        columns = ("rank", "number", "name", "unit", "score", "select")
        self.competitors_tree = ttk.Treeview(select_frame, columns=columns, show="headings")
        
        # 设置列标题
        self.competitors_tree.heading("rank", text="排名")
        self.competitors_tree.heading("number", text="背番号")
        self.competitors_tree.heading("name", text="姓名")
        self.competitors_tree.heading("unit", text="学校/单位")
        self.competitors_tree.heading("score", text="得分")
        self.competitors_tree.heading("select", text="晋级")
        
        # 设置列宽
        self.competitors_tree.column("rank", width=60)
        self.competitors_tree.column("number", width=80)
        self.competitors_tree.column("name", width=120)
        self.competitors_tree.column("unit", width=150)
        self.competitors_tree.column("score", width=80)
        self.competitors_tree.column("select", width=60)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(select_frame, orient=tk.VERTICAL, command=self.competitors_tree.yview)
        self.competitors_tree.configure(yscrollcommand=scrollbar.set)
        
        self.competitors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定点击事件
        self.competitors_tree.bind("<ButtonRelease-1>", self._on_item_click)
        
        # 操作按钮
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        select_all_btn = ttk.Button(btn_frame, text="全选", command=self._select_all)
        select_all_btn.pack(side=tk.LEFT, padx=5)
        
        deselect_all_btn = ttk.Button(btn_frame, text="取消全选", command=self._deselect_all)
        deselect_all_btn.pack(side=tk.LEFT, padx=5)
        
        # 晋级人数选择框架
        adv_frame = ttk.LabelFrame(self.window, text="晋级设置")
        adv_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 晋级人数选择
        adv_count_frame = ttk.Frame(adv_frame)
        adv_count_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(adv_count_frame, text="晋级人数:").pack(side=tk.LEFT, padx=(10, 5))
        
        # 晋级人数变量
        self.advancement_count = tk.IntVar(value=4)  # 默认晋级4人
        
        # 晋级人数输入框
        count_spinbox = ttk.Spinbox(
            adv_count_frame, 
            from_=1, 
            to=20, 
            textvariable=self.advancement_count,
            width=5
        )
        count_spinbox.pack(side=tk.LEFT, padx=(0, 10))
        
        # 自动选择按钮
        auto_select_btn = ttk.Button(
            adv_count_frame, 
            text="自动选择前N名", 
            command=self._auto_select
        )
        auto_select_btn.pack(side=tk.LEFT)
        
        # 保存按钮
        save_btn = ttk.Button(btn_frame, text="保存晋级选手", command=self._save_advancement)
        save_btn.pack(side=tk.RIGHT, padx=5)
        
        # 取消按钮
        cancel_btn = ttk.Button(btn_frame, text="取消", command=self.window.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
    
    def _load_previous_events_list(self):
        """加载前置轮次列表"""
        if not self.previous_events:
            self.results_label.config(text="没有找到前置轮次")
            return
        
        # 设置下拉框选项
        event_values = []
        for event in self.previous_events:
            # 显示场次名称和ID
            event_values.append(f"{event.name} ({event.id})")
        
        self.previous_event_combo['values'] = event_values
        
        # 默认选择第一个
        if event_values:
            self.previous_event_combo.current(0)
            self._on_previous_event_changed(None)
    
    def _on_previous_event_changed(self, event):
        """前置轮次选择改变事件"""
        # 获取选中的前置轮次
        selection = self.previous_event_var.get()
        if not selection:
            self.selected_previous_event = None
            return
        
        # 从选择字符串中提取场次ID
        event_id = selection.split("(")[-1].strip(")")
        
        # 查找对应的场次对象
        for prev_event in self.previous_events:
            if prev_event.id == event_id:
                self.selected_previous_event = prev_event
                break
        
        # 加载前置轮次结果
        self._load_previous_results()
    
    def _load_previous_results(self):
        """加载前置轮次结果"""
        # 清空表格
        for item in self.competitors_tree.get_children():
            self.competitors_tree.delete(item)
        
        try:
            # 检查前置轮次是否存在
            if not self.selected_previous_event:
                self.results_label.config(text="没有选择前置轮次")
                return
            
            # 检查前置轮次状态
            if self.selected_previous_event.status != EventStatus.COMPLETED:
                self.results_label.config(text=f"前置轮次状态为 {self.selected_previous_event.status.value}，结果不可用")
                return
            
            # 使用ResultsViewManager获取综合结果
            from ..utils.results_view_manager import ResultsViewManager
            results_view_manager = ResultsViewManager()
            
            # 获取综合结果
            success, results, errors = results_view_manager.get_overall_results_from_data(
                self.data_manager.current_competition,
                self.selected_previous_event
            )
            
            if not success:
                self.results_label.config(text=f"获取结果失败: {'; '.join(errors)}")
                return
            
            # 更新结果标签
            scoring_type = self.selected_previous_event.scoring_type.value
            self.results_label.config(text=f"评分类型: {scoring_type}, 结果选手数: {len(results)}")
            
            # 添加选手到表格
            for result in results:
                competitor_number = result.get('competitor_number')
                rank = result.get('rank')
                
                # 查找选手详细信息，使用背番号+项目编号获取
                competitor = self.data_manager.get_competitor_by_number_and_project(competitor_number, self.selected_previous_event.project_id)
                if competitor:
                    # 根据评分类型显示不同的分数信息
                    if scoring_type == "顺位法":
                        score_text = f"排名: {rank}"
                    else:  # Mark制
                        total_score = result.get('total_score', 0)
                        score_text = f"得分: {total_score:.2f}"
                    
                    self.competitors_tree.insert("", "end", iid=str(competitor_number), values=(
                        rank,
                        competitor_number,
                        competitor.name,
                        competitor.unit,
                        score_text,
                        "否"  # 默认不晋级
                    ))
            
            # 如果是顺位法，更新列标题为"排名"
            if scoring_type == "顺位法":
                self.competitors_tree.heading("score", text="排名")
            else:  # Mark制
                self.competitors_tree.heading("score", text="得分")
            
        except Exception as e:
            self.logger.error(f"加载前置轮次结果失败: {e}")
            self.results_label.config(text=f"加载结果失败: {str(e)}")
    
    def _on_item_click(self, event):
        """处理表格项点击事件"""
        # 获取点击的位置
        region = self.competitors_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        
        # 获取点击的行和列
        column = self.competitors_tree.identify_column(event.x)
        item = self.competitors_tree.identify_row(event.y)
        
        # 如果点击的是晋级列
        if column == "#6" and item:  # 第6列是晋级列
            current_values = list(self.competitors_tree.item(item, "values"))
            # 切换晋级状态
            current_values[5] = "是" if current_values[5] == "否" else "否"
            self.competitors_tree.item(item, values=current_values)
    
    def _select_all(self):
        """全选所有选手"""
        for item in self.competitors_tree.get_children():
            values = list(self.competitors_tree.item(item, "values"))
            values[5] = "是"
            self.competitors_tree.item(item, values=values)
    
    def _deselect_all(self):
        """取消全选所有选手"""
        for item in self.competitors_tree.get_children():
            values = list(self.competitors_tree.item(item, "values"))
            values[5] = "否"
            self.competitors_tree.item(item, values=values)
    
    def _auto_select(self):
        """自动选择前N名选手，处理同分情况"""
        try:
            count = int(self.advancement_count.get())
            
            # 先取消所有选择
            self._deselect_all()
            
            # 按排名排序
            items = sorted(self.competitors_tree.get_children(), 
                          key=lambda x: int(self.competitors_tree.item(x, "values")[0]))
            
            # 获取结果数据以检查同分情况
            from ..utils.results_view_manager import ResultsViewManager
            results_view_manager = ResultsViewManager()
            
            # 获取综合结果
            success, results, errors = results_view_manager.get_overall_results_from_data(
                self.data_manager.current_competition,
                self.selected_previous_event
            )
            
            if not success:
                messagebox.showerror("错误", f"获取结果失败: {'; '.join(errors)}")
                return
            
            # 创建背番号到结果的映射
            result_map = {}
            for result in results:
                competitor_number = result.get('competitor_number')
                if competitor_number is not None:
                    if self.selected_previous_event.scoring_type.value == "顺位法":
                        # 顺位法使用排名
                        result_map[competitor_number] = result.get('rank', 0)
                    else:
                        # Mark制使用总分
                        result_map[competitor_number] = result.get('total_score', 0)
            
            # 选择前count名，处理同分情况
            selected = 0
            last_rank = 0
            last_score = None
            
            for item in items:
                values = list(self.competitors_tree.item(item, "values"))
                rank = int(values[0])  # 排名
                competitor_number = int(values[1])  # 背番号
                
                # 获取选手分数
                score = result_map.get(competitor_number, 0)
                
                # 如果已经选够了，且当前排名不是同分，则停止选择
                if selected >= count and rank != last_rank:
                    break
                
                # 如果是同分情况，即使超过预定人数也要选择
                if selected >= count and rank == last_rank and score == last_score:
                    pass  # 继续选择同分选手
                elif selected >= count:
                    break
                
                # 选择选手
                values[5] = "是"
                self.competitors_tree.item(item, values=values)
                selected += 1
                last_rank = rank
                last_score = score
            
            # 检查是否有同分情况导致超出预定人数
            if selected > count:
                messagebox.showinfo(
                    "提示", 
                    f"由于存在同分情况，已自动选择{selected}名选手晋级（超过预设的{count}名）"
                )
            else:
                messagebox.showinfo("提示", f"已自动选择前{selected}名选手晋级")
                
        except ValueError:
            messagebox.showerror("错误", "请输入有效的晋级人数")
        except Exception as e:
            self.logger.error(f"自动选择失败: {e}")
            messagebox.showerror("错误", f"自动选择失败: {str(e)}")
    
    def _save_advancement(self):
        """保存晋级选手"""
        try:
            # 获取选中的选手
            selected_competitors = []
            for item in self.competitors_tree.get_children():
                values = self.competitors_tree.item(item, "values")
                if values[5] == "是":  # 晋级列
                    selected_competitors.append(values[1])  # 背番号（保持字符串类型）
            
            if not selected_competitors:
                messagebox.showwarning("警告", "请至少选择一名晋级选手")
                return
            
            # 获取当前已有的选手列表（避免重复导入）
            existing_competitors = set(self.event.competitors) if hasattr(self.event, 'competitors') and self.event.competitors else set()
            
            # 将新选择的选手添加到现有列表（去重）
            updated_competitors = list(existing_competitors.union(selected_competitors))
            
            # 更新当前场次的选手列表
            self.event.competitors = updated_competitors
            
            # 保存更新后的赛事数据
            self.data_manager.save_competition()
            
            messagebox.showinfo("成功", f"已成功保存{len(selected_competitors)}名晋级选手到 {self.event.name}")
            self.window.destroy()
            
        except Exception as e:
            self.logger.error(f"保存晋级选手失败: {e}")
            messagebox.showerror("错误", f"保存晋级选手失败: {str(e)}")
    
    def show(self):
        """显示窗口"""
        self.window.transient(self.parent)
        self.window.grab_set()
        self.window.wait_window()