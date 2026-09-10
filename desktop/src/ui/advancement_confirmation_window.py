#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
晋级信息确认窗口
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional, Tuple
import logging

from ..models.data_models import Event, Competitor
from ..algorithms.advancement import distribute_competitors_to_events, get_advancing_competitors
from ..models.data_manager import DataManager
from ..utils.logger import get_logger
from .window_utils import center_window

logger = get_logger()


class AdvancementConfirmationWindow:
    """晋级信息确认窗口"""
    
    def __init__(
        self, 
        parent: tk.Widget, 
        data_manager: DataManager,
        project_id: str,
        current_round: str,
        previous_round_events: List[Event],
        next_round_events: List[Event]
    ):
        """
        初始化晋级信息确认窗口
        
        Args:
            parent: 父窗口
            data_manager: 数据管理器
            project_id: 项目编号
            current_round: 当前轮次
            previous_round_events: 前置轮次场次列表
            next_round_events: 下一轮次场次列表
        """
        self.parent = parent
        self.data_manager = data_manager
        self.project_id = project_id
        self.current_round = current_round
        self.previous_round_events = previous_round_events
        self.next_round_events = next_round_events
        
        # 晋级选手列表
        self.advancing_competitors: List[int] = []
        # 选手信息缓存
        self.competitor_info: Dict[int, Competitor] = {}
        
        # 当前选择的分配方法
        self.distribution_method = tk.StringVar(value="snake")
        
        # 分组结果
        self.event_assignments: Dict[str, List[int]] = {}
        
        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title("晋级信息确认")
        self.window.geometry("900x700")
        self.window.resizable(True, True)
        
        # 模态窗口
        self.window.transient(parent)
        self.window.grab_set()
        
        # 居中显示
        center_window(self.window, parent)
        
        # 创建UI
        self._create_widgets()
        
        # 初始化数据
        self._load_data()
        
        # 计算初始分组
        self._calculate_distribution()
        
        # 绑定窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_widgets(self):
        """创建窗口组件"""
        # 主框架
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部信息框架
        info_frame = ttk.LabelFrame(main_frame, text="轮次信息", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 前置轮次信息
        prev_frame = ttk.Frame(info_frame)
        prev_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(prev_frame, text="前置轮次:").pack(side=tk.LEFT)
        prev_text = ", ".join([f"{event.name} ({event.id})" for event in self.previous_round_events])
        ttk.Label(prev_frame, text=prev_text).pack(side=tk.LEFT, padx=(10, 0))
        
        # 下一轮次信息
        next_frame = ttk.Frame(info_frame)
        next_frame.pack(fill=tk.X)
        
        ttk.Label(next_frame, text="下一轮次:").pack(side=tk.LEFT)
        next_text = ", ".join([f"{event.name} ({event.id})" for event in self.next_round_events])
        ttk.Label(next_frame, text=next_text).pack(side=tk.LEFT, padx=(10, 0))
        
        # 中间部分 - 分为左右两栏
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 左侧 - 晋级选手列表
        left_frame = ttk.LabelFrame(middle_frame, text="晋级选手", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 创建选手表格
        columns = ("rank", "number", "name", "score", "advancement")
        self.competitors_tree = ttk.Treeview(left_frame, columns=columns, show="headings")
        
        # 设置列标题
        self.competitors_tree.heading("rank", text="排名")
        self.competitors_tree.heading("number", text="背番号")
        self.competitors_tree.heading("name", text="姓名")
        self.competitors_tree.heading("score", text="总分")
        self.competitors_tree.heading("advancement", text="晋级")
        
        # 设置列宽
        self.competitors_tree.column("rank", width=60, anchor="center")
        self.competitors_tree.column("number", width=80, anchor="center")
        self.competitors_tree.column("name", width=120, anchor="center")
        self.competitors_tree.column("score", width=80, anchor="center")
        self.competitors_tree.column("advancement", width=60, anchor="center")
        
        # 添加滚动条
        competitors_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.competitors_tree.yview)
        self.competitors_tree.configure(yscrollcommand=competitors_scrollbar.set)
        
        self.competitors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        competitors_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 右侧 - 晋级分组预览
        right_frame = ttk.LabelFrame(middle_frame, text="晋级分组预览", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 创建滚动框架用于容纳所有场次视图
        self.groups_canvas = tk.Canvas(right_frame)
        self.groups_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.groups_canvas.yview)
        self.groups_scrollable_frame = ttk.Frame(self.groups_canvas)
        
        # 配置滚动
        self.groups_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.groups_canvas.configure(scrollregion=self.groups_canvas.bbox("all"))
        )
        
        self.groups_canvas.create_window((0, 0), window=self.groups_scrollable_frame, anchor="nw")
        self.groups_canvas.configure(yscrollcommand=self.groups_scrollbar.set)
        
        # 存储各场次视图的字典
        self.event_views = {}
        
        self.groups_canvas.pack(side="left", fill="both", expand=True)
        self.groups_scrollbar.pack(side="right", fill="y")
        
        # 底部控制框架
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X)
        
        # 晋级方式选择
        method_frame = ttk.Frame(control_frame)
        method_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(method_frame, text="晋级方式:").pack(side=tk.LEFT)
        method_combo = ttk.Combobox(
            method_frame, 
            textvariable=self.distribution_method,
            values=[("snake", "蛇形排列法"), ("random", "随机分配法")],
            state="readonly",
            width=20
        )
        method_combo.pack(side=tk.LEFT, padx=(10, 0))
        method_combo.bind("<<ComboboxSelected>>", lambda e: self._calculate_distribution())
        
        # 按钮框架
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.RIGHT)
        
        # 重新计算按钮
        ttk.Button(
            button_frame, 
            text="重新计算晋级", 
            command=self._calculate_distribution
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # 确认晋级按钮
        ttk.Button(
            button_frame, 
            text="确认晋级", 
            command=self._confirm_advancement
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # 取消按钮
        ttk.Button(
            button_frame, 
            text="取消", 
            command=self._on_close
        ).pack(side=tk.LEFT)
    
    def _load_data(self):
        """加载数据"""
        # 获取晋级选手
        self.advancing_competitors = get_advancing_competitors(
            self.project_id, 
            self.current_round, 
            self.data_manager
        )
        
        # 获取选手信息
        if self.data_manager.current_competition:
            for number in self.advancing_competitors:
                competitor = self.data_manager.current_competition.competitors.get(number)
                if competitor:
                    self.competitor_info[number] = competitor
        
        # 更新选手表格
        self._update_competitors_tree()
    
    def _update_competitors_tree(self):
        """更新选手表格"""
        # 清空表格
        for item in self.competitors_tree.get_children():
            self.competitors_tree.delete(item)
        
        # 获取选手成绩信息
        competitor_scores = {}
        competitor_ranks = {}
        
        # 从前置轮次结果中获取选手成绩和排名
        for event in self.previous_round_events:
            result = self.data_manager.get_results(event.id)
            if not result:
                continue
            
            results_data = result.results_data
            
            if 'overall_results' in results_data:
                overall_results = results_data['overall_results']
                for result_item in overall_results:
                    # 处理字典格式的结果项
                    if isinstance(result_item, dict):
                        advancement_status = result_item.get('advancement_status', False)
                        if advancement_status:
                            number = result_item.get('competitor_number')
                            score = result_item.get('total_score', result_item.get('score', 0))
                            rank = result_item.get('rank', 0)
                            if number is not None:
                                competitor_scores[number] = score
                                competitor_ranks[number] = rank
                    # 处理对象格式的结果项
                    else:
                        if hasattr(result_item, 'advancement_status') and result_item.advancement_status:
                            number = result_item.competitor_number
                            competitor_scores[number] = result_item.total_score
                            competitor_ranks[number] = result_item.rank
        
        # 添加选手到表格
        for i, number in enumerate(self.advancing_competitors):
            competitor = self.competitor_info.get(number)
            name = competitor.name if competitor else f"选手{number}"
            score = competitor_scores.get(number, 0)
            rank = competitor_ranks.get(number, i + 1)
            
            self.competitors_tree.insert(
                "", 
                "end", 
                values=(
                    rank,
                    number,
                    name,
                    f"{score:.1f}",
                    "是"
                )
            )
    
    def _calculate_distribution(self):
        """计算分组"""
        if not self.advancing_competitors or not self.next_round_events:
            return
        
        # 获取分配方法
        method = self.distribution_method.get()
        
        # 计算分组
        self.event_assignments = distribute_competitors_to_events(
            self.advancing_competitors,
            self.next_round_events,
            method
        )
        
        # 更新分组预览
        self._update_groups_tree()
    
    def _create_event_view(self, parent_frame, event):
        """
        为单个场次创建视图
        
        Args:
            parent_frame: 父框架
            event: 场次对象
            
        Returns:
            Tuple[ttk.LabelFrame, ttk.Treeview]: 场次框架和参赛选手表格
        """
        # 创建场次框架
        event_frame = ttk.LabelFrame(parent_frame, text=f"{event.name} ({event.id})", padding="5")
        event_frame.pack(fill="x", pady=5)
        
        # 场次信息
        info_frame = ttk.Frame(event_frame)
        info_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Label(info_frame, text=f"项目: {event.project_id}").pack(side="left", padx=(0, 10))
        ttk.Label(info_frame, text=f"轮次: {event.round}").pack(side="left", padx=(0, 10))
        
        # 获取舞种信息
        dances = ", ".join([dance.name for dance in event.dances]) if event.dances else "无"
        ttk.Label(info_frame, text=f"舞种: {dances}").pack(side="left")
        
        # 创建参赛选手表格
        columns = ("number", "name")
        competitors_tree = ttk.Treeview(event_frame, columns=columns, show="headings", height=5)
        
        # 设置列标题
        competitors_tree.heading("number", text="背番号")
        competitors_tree.heading("name", text="姓名")
        
        # 设置列宽
        competitors_tree.column("number", width=80, anchor="center")
        competitors_tree.column("name", width=150, anchor="w")
        
        competitors_tree.pack(fill="both", expand=True)
        
        return event_frame, competitors_tree

    def _update_groups_tree(self):
        """更新分组预览"""
        # 清空现有视图
        for event_id in self.event_views:
            for widget in self.event_views[event_id]["frame"].winfo_children():
                widget.destroy()
            self.event_views[event_id]["frame"].destroy()
        self.event_views.clear()
        
        # 按场次ID排序
        sorted_events = sorted(self.next_round_events, key=lambda e: e.id)
        
        # 为每个场次创建视图
        for event in sorted_events:
            # 创建场次视图
            event_frame, competitors_tree = self._create_event_view(self.groups_scrollable_frame, event)
            
            # 存储视图引用
            self.event_views[event.id] = {
                "frame": event_frame,
                "tree": competitors_tree
            }
            
            # 获取该场次的参赛选手
            competitors = self.event_assignments.get(event.id, [])
            
            # 添加选手到表格
            for number in competitors:
                competitor = self.competitor_info.get(number)
                name = competitor.name if competitor else f"选手{number}"
                
                competitors_tree.insert(
                    "", 
                    "end", 
                    values=(
                        number,
                        name
                    )
                )
    
    def _confirm_advancement(self):
        """确认晋级"""
        try:
            # 更新下一轮次场次的参赛选手
            for event_id, competitors in self.event_assignments.items():
                event = self.data_manager.current_competition.events.get(event_id)
                if event:
                    event.competitors = competitors
            
            # 保存赛事数据
            if self.data_manager.save_competition():
                # 导入必要的模块
                import os
                from ..utils.config import config
                from datetime import datetime
                
                # 创建导出目录（与之前总评分表同一目录）
                event_dir = config.get_event_dir(self.data_manager.current_event_name)
                export_dir = os.path.join(event_dir, "评分表")
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)
                
                # 导入ReportLab的相关模块
                from reportlab.lib.pagesizes import A4, landscape
                from reportlab.lib.units import mm
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from reportlab.lib import colors
                from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer, PageBreak
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from ..models.data_models import ScoringType
                
                # 为下一轮次的每个场次生成PDF评分表
                for event_id, competitors in self.event_assignments.items():
                    event = self.data_manager.current_competition.events.get(event_id)
                    if not event:
                        continue
                    
                    # 获取选手数据
                    players = []
                    for number in competitors:
                        player = self.data_manager.current_competition.competitors.get(number)
                        if player:
                            players.append(player)
                    if not players:
                        continue
                    
                    # 构建文件路径，处理文件名中的特殊字符
                    safe_event_name = event.name.replace('/', '_').replace('\\', '_')
                    file_name = f"{event.id}-{safe_event_name}.pdf"
                    file_path = os.path.join(export_dir, file_name)
                    
                    # 创建PDF文档
                    doc = SimpleDocTemplate(file_path, pagesize=landscape(A4),
                                          leftMargin=15*mm, rightMargin=15*mm,
                                          topMargin=15*mm, bottomMargin=15*mm)
                    
                    # 设置字体（支持中文）
                    font_name = 'Helvetica'  # 默认字体
                    try:
                        # 尝试注册中文字体
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
                                    break
                                except Exception as e:
                                    logger.warning(f"注册字体失败 {font_path}: {e}")
                                    continue
                    except Exception as e:
                        logger.error(f"注册中文字体失败: {e}")
                    
                    # 获取样式
                    styles = getSampleStyleSheet()
                    
                    # 创建标题样式
                    title_style = ParagraphStyle(
                        name='CustomTitle',
                        parent=styles['Title'],
                        fontName=font_name,
                        fontSize=18,
                        leading=22,
                        alignment=1,
                        spaceAfter=15
                    )
                    
                    # 生成PDF内容
                    content = []
                    
                    # 计算晋级规则
                    if event.scoring_type == ScoringType.MARK:
                        advancement_rule = f"{len(players)}进{event.advancement_count}"
                    else:
                        advancement_rule = f"{event.advancement_count}顺位"
                    
                    # 添加标题
                    title = Paragraph(f"{event.id}. {event.name}     {advancement_rule}", title_style)
                    content.append(title)
                    content.append(Spacer(1, 15))
                    
                    # 计算横向A4纸的实际可用尺寸
                    a4_width, a4_height = landscape(A4)
                    available_width = a4_width - 40*mm  # 左右边距各20mm，总计40mm
                    
                    # 创建评分表（行为舞种，列为背番号）
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
                            if event.scoring_type.value == "mark":
                                row.append("")  # Mark制：空白单元格用于填写分数
                            else:
                                row.append("")  # 顺位法：空白单元格用于填写名次
                        
                        table_data.append(row)
                    
                    # 动态计算列宽
                    num_columns = len(table_data[0])
                    dance_col_width = 35*mm
                    player_col_width = (available_width - dance_col_width) / (num_columns - 1)
                    col_widths = [dance_col_width] + [player_col_width] * (num_columns - 1)
                    
                    # 创建表格
                    table = Table(table_data, colWidths=col_widths, repeatRows=1, rowHeights=[45]*len(table_data))
                    
                    # 设置表格样式
                    table.setStyle(TableStyle([
                        # 表头样式
                        ('FONTNAME', (0, 0), (-1, 0), font_name),
                        ('FONTSIZE', (0, 0), (-1, 0), 14),
                        ('BOLD', (0, 0), (-1, 0), True),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        
                        # 数据行样式
                        ('FONTNAME', (0, 1), (-1, -1), font_name),
                        ('FONTSIZE', (0, 1), (-1, -1), 13),
                        
                        # 选手列样式
                        ('VALIGN', (1, 1), (-1, -1), 'TOP'),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        
                        # 舞种列样式
                        ('BOLD', (0, 1), (0, -1), True),
                        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                        ('VALIGN', (0, 1), (0, -1), 'MIDDLE'),
                        
                        # 表格边框
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
                    ]))
                    
                    content.append(table)
                    content.append(Spacer(1, 20))
                    
                    # 添加裁判签名
                    signature_data = [["裁判签名：_________________________"]]
                    signature_table = Table(signature_data, colWidths=[150*mm])
                    signature_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 14),
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    
                    content.append(signature_table)
                    
                    # 生成PDF
                    doc.build(content)
                    logger.info(f"成功生成下一轮次场次 {event.id} 的PDF评分表到: {file_path}")
            
            messagebox.showinfo("成功", "晋级信息已确认并保存，下一轮次的PDF评分表已生成！")
            self.window.destroy()
        except Exception as e:
            logger.error(f"确认晋级时发生错误: {str(e)}")
            messagebox.showerror("错误", f"确认晋级时发生错误: {str(e)}")
    
    def _on_close(self):
        """关闭窗口"""
        self.window.destroy()