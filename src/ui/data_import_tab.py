#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据导入选项卡模块
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import pandas as pd

from ..models.data_manager import data_manager
from ..models.data_models import Competitor, Judge, Event, Dance, ScoringType
from ..utils.config import config
from ..utils.logger import get_logger

logger = get_logger()


class DataImportTab:
    """数据导入选项卡类"""
    
    def __init__(self, parent, main_window):
        """初始化数据导入选项卡"""
        self.parent = parent
        self.main_window = main_window
        self.logger = logger
        
        # 创建选项卡框架
        self.frame = ttk.Frame(parent)
        
        # 创建界面元素
        self.create_widgets()
        
        # 刷新数据
        self.refresh()
        
        self.logger.debug("数据导入选项卡初始化完成")
    
    def create_widgets(self):
        """创建界面元素"""
        # 创建上下分区
        top_frame = ttk.Frame(self.frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        bottom_frame = ttk.Frame(self.frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        # 上部：批量导入区域和单独导入区域
        self.create_batch_import_frame(top_frame)
        self.create_separate_import_frame(top_frame)
        
        # 下部：数据预览区域
        self.create_preview_frame(bottom_frame)
    
    def create_batch_import_frame(self, parent):
        """创建批量导入区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="批量导入", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 5))
        
        # 说明文字
        info_label = ttk.Label(
            parent, 
            text="从指定目录一次性导入所有赛事数据（选手、赛程、裁判）"
        )
        info_label.pack(pady=(0, 10))
        
        # 按钮框架
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 选择目录并批量导入按钮
        batch_import_button = ttk.Button(
            button_frame, 
            text="选择目录并批量导入", 
            command=self.batch_import_from_directory
        )
        batch_import_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 从test_data目录导入按钮
        test_data_button = ttk.Button(
            button_frame, 
            text="从test_data目录导入", 
            command=self.batch_import_from_test_data
        )
        test_data_button.pack(side=tk.LEFT)
        
        # 状态标签
        self.batch_status_label = ttk.Label(parent, text="")
        self.batch_status_label.pack(pady=(0, 10))
    
    def create_separate_import_frame(self, parent):
        """创建单独导入区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="单独导入", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(10, 5))
        
        # 选手信息导入区域
        competitor_frame = ttk.Frame(parent)
        competitor_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(competitor_frame, text="选手信息导入:").pack(side=tk.LEFT)
        competitor_button = ttk.Button(
            competitor_frame, 
            text="选择Excel/CSV文件", 
            command=self.import_competitors
        )
        competitor_button.pack(side=tk.LEFT, padx=(10, 0))
        self.competitor_status_label = ttk.Label(competitor_frame, text="")
        self.competitor_status_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 赛程表导入区域
        schedule_frame = ttk.Frame(parent)
        schedule_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(schedule_frame, text="赛程表导入:").pack(side=tk.LEFT)
        schedule_button = ttk.Button(
            schedule_frame, 
            text="选择Excel/CSV文件", 
            command=self.import_schedule
        )
        schedule_button.pack(side=tk.LEFT, padx=(10, 0))
        self.schedule_status_label = ttk.Label(schedule_frame, text="")
        self.schedule_status_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 裁判信息导入区域
        judge_frame = ttk.Frame(parent)
        judge_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(judge_frame, text="裁判信息导入:").pack(side=tk.LEFT)
        judge_button = ttk.Button(
            judge_frame, 
            text="选择Excel/CSV文件", 
            command=self.import_judges
        )
        judge_button.pack(side=tk.LEFT, padx=(10, 0))
        self.judge_status_label = ttk.Label(judge_frame, text="")
        self.judge_status_label.pack(side=tk.LEFT, padx=(10, 0))
    
    def create_preview_frame(self, parent):
        """创建数据预览区域"""
        # 标题
        title_label = ttk.Label(
            parent, 
            text="数据预览", 
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 5))
        
        # 数据类型选择
        type_frame = ttk.Frame(parent)
        type_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(type_frame, text="数据类型:").pack(side=tk.LEFT)
        self.data_type_var = tk.StringVar(value="选手信息")
        data_type_combo = ttk.Combobox(
            type_frame, 
            textvariable=self.data_type_var,
            values=["选手信息", "赛程信息", "裁判信息"],
            state="readonly"
        )
        data_type_combo.pack(side=tk.LEFT, padx=(10, 0))
        data_type_combo.bind("<<ComboboxSelected>>", self.on_data_type_changed)
        
        # 表格框架
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview
        self.preview_tree = ttk.Treeview(table_frame)
        
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.preview_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 布局
        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # 配置行权重和列权重
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
    
    def refresh(self):
        """刷新数据预览"""
        self.update_preview_data()
    
    def on_data_type_changed(self, event):
        """数据类型改变事件处理"""
        self.update_preview_data()
    
    def update_preview_data(self):
        """更新预览数据"""
        # 清空当前表格
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        
        # 检查是否有打开的赛事
        if not data_manager.current_competition:
            return
        
        data_type = self.data_type_var.get()
        
        if data_type == "选手信息":
            self.update_competitor_preview()
        elif data_type == "赛程信息":
            self.update_schedule_preview()
        elif data_type == "裁判信息":
            self.update_judge_preview()
    
    def update_competitor_preview(self):
        """更新选手预览数据"""
        # 设置列
        self.preview_tree["columns"] = ("number", "name", "unit", "group")
        self.preview_tree.heading("#0", text="")
        self.preview_tree.heading("number", text="背番号")
        self.preview_tree.heading("name", text="姓名")
        self.preview_tree.heading("unit", text="学校/单位")
        self.preview_tree.heading("group", text="参赛组别")
        
        self.preview_tree.column("#0", width=0, stretch=False)
        self.preview_tree.column("number", width=80)
        self.preview_tree.column("name", width=150)
        self.preview_tree.column("unit", width=200)
        self.preview_tree.column("group", width=150)
        
        # 添加数据
        for number, competitor in data_manager.current_competition.competitors.items():
            self.preview_tree.insert(
                "", 
                tk.END, 
                values=(
                    number,
                    competitor.name,
                    competitor.unit,
                    competitor.group
                )
            )
    
    def update_schedule_preview(self):
        """更新赛程预览数据"""
        # 设置列
        self.preview_tree["columns"] = ("id", "name", "project_id", "round", "scoring_type", "status")
        self.preview_tree.heading("#0", text="")
        self.preview_tree.heading("id", text="场次ID")
        self.preview_tree.heading("name", text="场次名称")
        self.preview_tree.heading("project_id", text="项目编号")
        self.preview_tree.heading("round", text="轮次")
        self.preview_tree.heading("scoring_type", text="评分类型")
        self.preview_tree.heading("status", text="状态")
        
        self.preview_tree.column("#0", width=0, stretch=False)
        self.preview_tree.column("id", width=100)
        self.preview_tree.column("name", width=150)
        self.preview_tree.column("project_id", width=100)
        self.preview_tree.column("round", width=100)
        self.preview_tree.column("scoring_type", width=100)
        self.preview_tree.column("status", width=100)
        
        # 添加数据
        for event_id, event in data_manager.current_competition.events.items():
            self.preview_tree.insert(
                "", 
                tk.END, 
                values=(
                    event_id,
                    event.name,
                    event.project_id,
                    event.round,
                    event.scoring_type.value,
                    event.status.value
                )
            )
    
    def update_judge_preview(self):
        """更新裁判预览数据"""
        # 设置列
        self.preview_tree["columns"] = ("id", "name")
        self.preview_tree.heading("#0", text="")
        self.preview_tree.heading("id", text="裁判ID")
        self.preview_tree.heading("name", text="裁判姓名")
        
        self.preview_tree.column("#0", width=0, stretch=False)
        self.preview_tree.column("id", width=100)
        self.preview_tree.column("name", width=200)
        
        # 添加数据
        for judge_id, judge in data_manager.current_competition.judges.items():
            self.preview_tree.insert(
                "", 
                tk.END, 
                values=(
                    judge_id,
                    judge.name
                )
            )
    
    def batch_import_from_directory(self):
        """从选择的目录批量导入"""
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先创建或打开一个赛事")
            return
        
        # 选择目录
        directory = filedialog.askdirectory(title="选择包含数据文件的目录")
        if not directory:
            return
        
        self.batch_status_label.config(text=f"正在导入目录: {directory}...")
        self.frame.update()
        
        # 尝试导入
        try:
            imported_count = 0
            
            # 清空当前赛事目录
            if data_manager.clear_event_directory():
                self.logger.info("已清空当前赛事目录")
            else:
                self.logger.error("清空赛事目录失败")
                return False
            
            # 导入选手信息
            competitor_files = [
                f for f in os.listdir(directory) 
                if f.lower().endswith(('.csv', '.xlsx', '.xls')) and 
                ('competitor' in f.lower() or '选手' in f.lower())
            ]
            
            for file in competitor_files:
                file_path = os.path.join(directory, file)
                if self._import_competitors_from_file(file_path):
                    imported_count += 1
            
            # 导入赛程信息
            schedule_files = [
                f for f in os.listdir(directory) 
                if f.lower().endswith(('.csv', '.xlsx', '.xls')) and 
                ('schedule' in f.lower() or '赛程' in f.lower())
            ]
            
            for file in schedule_files:
                file_path = os.path.join(directory, file)
                if self._import_schedule_from_file(file_path):
                    imported_count += 1
            
            # 导入裁判信息
            judge_files = [
                f for f in os.listdir(directory) 
                if f.lower().endswith(('.csv', '.xlsx', '.xls')) and 
                ('judge' in f.lower() or '裁判' in f.lower())
            ]
            
            for file in judge_files:
                file_path = os.path.join(directory, file)
                if self._import_judges_from_file(file_path):
                    imported_count += 1
            
            # 更新状态
            if imported_count > 0:
                self.batch_status_label.config(text=f"成功导入 {imported_count} 个文件")
                self.update_preview_data()
                # 导入完成后，导出所有轮次为1的场次的PDF评分表
                self.export_round1_scoring_sheets()
                # 生成检录表
                self.export_check_in_sheet()
            else:
                self.batch_status_label.config(text="未找到可导入的文件")
                
        except Exception as e:
            self.logger.error(f"批量导入失败: {e}")
            self.batch_status_label.config(text=f"导入失败: {str(e)}")
            messagebox.showerror("错误", f"导入失败: {str(e)}")
    
    def batch_import_from_test_data(self):
        """从test_data目录批量导入"""
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先创建或打开一个赛事")
            return
        
        test_data_dir = config.get("default_data_dir")
        if not os.path.exists(test_data_dir):
            messagebox.showerror("错误", f"测试数据目录不存在: {test_data_dir}")
            return
        
        self.batch_status_label.config(text=f"正在导入测试数据...")
        self.frame.update()
        
        # 尝试导入
        try:
            imported_count = 0
            
            # 清空当前赛事目录
            if data_manager.clear_event_directory():
                self.logger.info("已清空当前赛事目录")
            else:
                self.logger.error("清空赛事目录失败")
                return False
            
            # 导入选手信息
            competitor_file = os.path.join(test_data_dir, "test_competitors.csv")
            if os.path.exists(competitor_file):
                if self._import_competitors_from_file(competitor_file):
                    imported_count += 1
            
            # 导入赛程信息
            schedule_file = os.path.join(test_data_dir, "test_schedule.csv")
            if os.path.exists(schedule_file):
                if self._import_schedule_from_file(schedule_file):
                    imported_count += 1
            
            # 更新状态
            if imported_count > 0:
                self.batch_status_label.config(text=f"成功导入 {imported_count} 个测试文件")
                self.update_preview_data()
                # 导入完成后，导出所有轮次为1的场次的PDF评分表
                self.export_round1_scoring_sheets()
            else:
                self.batch_status_label.config(text="未找到可导入的测试文件")
                
        except Exception as e:
            self.logger.error(f"测试数据导入失败: {e}")
            self.batch_status_label.config(text=f"导入失败: {str(e)}")
            messagebox.showerror("错误", f"导入失败: {str(e)}")
    
    def import_competitors(self):
        """导入选手信息"""
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先创建或打开一个赛事")
            return
        
        # 选择文件
        file_path = filedialog.askopenfilename(
            title="选择选手信息文件",
            filetypes=[("Excel文件", "*.xlsx *.xls"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        self.competitor_status_label.config(text=f"正在导入: {os.path.basename(file_path)}...")
        self.frame.update()
        
        try:
            # 清空当前赛事目录
            if data_manager.clear_event_directory():
                self.logger.info("已清空当前赛事目录")
            else:
                self.logger.error("清空赛事目录失败")
                self.competitor_status_label.config(text="导入失败: 清空赛事目录失败")
                return
                
            if self._import_competitors_from_file(file_path):
                self.competitor_status_label.config(text=f"导入成功: {os.path.basename(file_path)}")
                self.update_preview_data()
                # 导入完成后，导出所有轮次为1的场次的PDF评分表
                self.export_round1_scoring_sheets()
            else:
                self.competitor_status_label.config(text=f"导入失败: {os.path.basename(file_path)}")
        except Exception as e:
            self.logger.error(f"选手信息导入失败: {e}")
            self.competitor_status_label.config(text=f"导入失败: {str(e)}")
            messagebox.showerror("错误", f"导入失败: {str(e)}")
    
    def import_schedule(self):
        """导入赛程信息"""
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先创建或打开一个赛事")
            return
        
        # 选择文件
        file_path = filedialog.askopenfilename(
            title="选择赛程表文件",
            filetypes=[("Excel文件", "*.xlsx *.xls"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        self.schedule_status_label.config(text=f"正在导入: {os.path.basename(file_path)}...")
        self.frame.update()
        
        try:
            # 清空当前赛事目录
            if data_manager.clear_event_directory():
                self.logger.info("已清空当前赛事目录")
            else:
                self.logger.error("清空赛事目录失败")
                self.schedule_status_label.config(text="导入失败: 清空赛事目录失败")
                return
                
            if self._import_schedule_from_file(file_path):
                self.schedule_status_label.config(text=f"导入成功: {os.path.basename(file_path)}")
                self.update_preview_data()
                # 导入完成后，导出所有轮次为1的场次的PDF评分表
                self.export_round1_scoring_sheets()
            else:
                self.schedule_status_label.config(text=f"导入失败: {os.path.basename(file_path)}")
        except Exception as e:
            self.logger.error(f"赛程信息导入失败: {e}")
            self.schedule_status_label.config(text=f"导入失败: {str(e)}")
            messagebox.showerror("错误", f"导入失败: {str(e)}")
    
    def import_judges(self):
        """导入裁判信息"""
        if not data_manager.current_competition:
            messagebox.showwarning("提示", "请先创建或打开一个赛事")
            return
        
        # 选择文件
        file_path = filedialog.askopenfilename(
            title="选择裁判信息文件",
            filetypes=[("Excel文件", "*.xlsx *.xls"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        self.judge_status_label.config(text=f"正在导入: {os.path.basename(file_path)}...")
        self.frame.update()
        
        try:
            # 清空当前赛事目录
            if data_manager.clear_event_directory():
                self.logger.info("已清空当前赛事目录")
            else:
                self.logger.error("清空赛事目录失败")
                self.judge_status_label.config(text="导入失败: 清空赛事目录失败")
                return
                
            if self._import_judges_from_file(file_path):
                self.judge_status_label.config(text=f"导入成功: {os.path.basename(file_path)}")
                self.update_preview_data()
                # 导入完成后，导出所有轮次为1的场次的PDF评分表
                self.export_round1_scoring_sheets()
            else:
                self.judge_status_label.config(text=f"导入失败: {os.path.basename(file_path)}")
        except Exception as e:
            self.logger.error(f"裁判信息导入失败: {e}")
            self.judge_status_label.config(text=f"导入失败: {str(e)}")
            messagebox.showerror("错误", f"导入失败: {str(e)}")
    
    def _import_competitors_from_file(self, file_path: str) -> bool:
        """从文件导入选手信息"""
        try:
            # 读取文件
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, encoding='utf-8-sig', dtype={'背番号': str})
            else:
                df = pd.read_excel(file_path)
                # 确保背番号列是字符串类型
                df['背番号'] = df['背番号'].astype(str)
        
            # 检查必要的列，只支持新格式：背番号,项目编号,姓名,学校/单位
            required_columns = ['背番号', '项目编号', '姓名', '学校/单位']
            if not all(col in df.columns for col in required_columns):
                missing_columns = [col for col in required_columns if col not in df.columns]
                self.logger.error(f"选手信息文件格式错误：缺少必要的列 {missing_columns}。只支持新格式：背番号,项目编号,姓名,学校/单位")
                return False
        
            # 导入数据
            import_count = 0
        
            # 新格式处理：为每个背番号+项目编号组合创建选手
            for _, row in df.iterrows():
                try:
                    # 获取必要信息
                    number = str(row['背番号']).strip()
                    project_id = str(row['项目编号']).strip()
                    name = str(row['姓名']).strip()
                    unit = str(row['学校/单位']).strip()
                    
                    # 组合参赛组别（使用项目编号）
                    group = project_id
                    
                    competitor = Competitor(
                        number=number,
                        name=name,
                        unit=unit,
                        group=group
                    )
                    
                    # 使用新的add_competitor_mapping方法添加选手映射
                    if data_manager.add_competitor_mapping(competitor, project_id):
                        import_count += 1
                except Exception as e:
                    self.logger.error(f"导入选手信息失败: {row}, {e}")
        
            self.logger.info(f"成功导入 {import_count} 名选手")
            return import_count > 0
        
        except Exception as e:
            self.logger.error(f"读取选手信息文件失败: {e}")
            return False
    
    def _import_schedule_from_file(self, file_path: str) -> bool:
        """从文件导入赛程信息"""
        try:
            # 读取文件
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, encoding='utf-8-sig', converters={'参赛选手': str})
            else:
                df = pd.read_excel(file_path)
                # 确保参赛选手列是字符串类型
                if '参赛选手' in df.columns:
                    df['参赛选手'] = df['参赛选手'].astype(str)
            
            # 检查必要的列 - 支持两种列名格式
            required_columns = ['场次编号', '场次名称', '项目编号', '评分类型']
            # 检查轮次列（支持"轮次"或"轮次类型"两种列名）
            has_round_column = False
            if '轮次' in df.columns:
                has_round_column = True
                round_column_name = '轮次'
            elif '轮次类型' in df.columns:
                has_round_column = True
                round_column_name = '轮次类型'
            
            if not has_round_column:
                self.logger.error("赛程信息文件缺少必要的列: 轮次或轮次类型")
                return False
                
            # 检查其他必要列
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"赛程信息文件缺少必要的列: {', '.join(missing_columns)}")
                return False
            
            # 首先收集所有场次数据，用于后续计算轮次名称
            events_data = []
            for _, row in df.iterrows():
                try:
                    # 解析舞种
                    dances = []
                    if '舞种' in row and pd.notna(row['舞种']):
                        dance_names = str(row['舞种']).split(',')
                        for i, dance_name in enumerate(dance_names):
                            dances.append(Dance(name=dance_name.strip(), order=i))
                    
                    # 解析评分类型
                    scoring_type_str = str(row['评分类型']).lower()
                    if scoring_type_str == "mark" or "mark" in scoring_type_str:
                        scoring_type = ScoringType.MARK
                    else:
                        # 默认为SKATING（顺位法），包括"ranking"和其他值
                        scoring_type = ScoringType.SKATING
                    
                    # 获取原始轮次数据
                    round_value = str(row[round_column_name])
                    
                    # 解析参赛选手
                    competitors = []
                    
                    # 解析晋级人数（可选）
                    advancement_count = 0
                    if '晋级人数' in row and pd.notna(row['晋级人数']):
                        try:
                            advancement_count = int(row['晋级人数'])
                        except ValueError:
                            self.logger.warning(f"晋级人数格式错误: {row['晋级人数']}")
                            advancement_count = 0
                    if '参赛选手' in row and pd.notna(row['参赛选手']):
                        competitor_numbers = str(row['参赛选手']).split(',')
                        for comp_num in competitor_numbers:
                            comp_num = comp_num.strip()
                            if comp_num:
                                try:
                                    # 查找选手（保持字符串类型）
                                    competitor = data_manager.get_competitor(comp_num)
                                    if competitor:
                                        # 只有轮次为1时才添加选手编号到competitors列表
                                        # 其他轮次的competitors字段应保持为空，等待晋级名单导入
                                        if round_value == '1':
                                            competitors.append(competitor.number)
                                except ValueError:
                                    self.logger.warning(f"无效的选手背番号: {comp_num}")
                    
                    # 保存场次数据，不立即创建Event对象
                    events_data.append({
                        'id': str(row['场次编号']),
                        'name': str(row['场次名称']),
                        'project_id': str(row['项目编号']),
                        'round_value': round_value,
                        'scoring_type': scoring_type,
                        'dances': dances,
                        'competitors': competitors,
                        'advancement_count': advancement_count
                    })
                except Exception as e:
                    self.logger.error(f"处理赛程数据失败: {row}, {e}")
            
            # 按项目ID分组，计算每个项目的轮次名称
            project_groups = {}
            for event_data in events_data:
                project_id = event_data['project_id']
                if project_id not in project_groups:
                    project_groups[project_id] = []
                project_groups[project_id].append(event_data)
            
            # 为每个项目计算轮次名称
            for project_id, project_events in project_groups.items():
                # 尝试将轮次值转换为数字，如果不能转换则设为0
                for event_data in project_events:
                    try:
                        event_data['round_number'] = int(event_data['round_value'])
                    except ValueError:
                        event_data['round_number'] = 0
                
                # 按轮次数值降序排序
                project_events.sort(key=lambda x: x['round_number'], reverse=True)
                
                # 使用原始轮次数据，不再计算轮次名称
                for event_data in project_events:
                    event_data['round_type'] = event_data['round_value']
            
            # 创建并添加场次对象
            import_count = 0
            for event_data in events_data:
                try:
                    # 创建场次
                    event = Event(
                        id=event_data['id'],
                        name=event_data['name'],
                        project_id=event_data['project_id'],
                        round=event_data['round_type'],  # 使用原始轮次数据
                        scoring_type=event_data['scoring_type'],
                        dances=event_data['dances'],
                        advancement_count=event_data.get('advancement_count', 0)
                    )
                    
                    # 添加参赛选手
                    event.competitors = event_data['competitors']
                    
                    if data_manager.add_event(event):
                        import_count += 1
                except Exception as e:
                    self.logger.error(f"导入赛程信息失败: {event_data}, {e}")
            
            self.logger.info(f"成功导入 {import_count} 个场次")
            return import_count > 0
            
        except Exception as e:
            self.logger.error(f"读取赛程信息文件失败: {e}")
            return False
    
    def _import_judges_from_file(self, file_path: str) -> bool:
        """从文件导入裁判信息"""
        try:
            # 读取文件
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, encoding='utf-8')
            else:
                df = pd.read_excel(file_path)
            
            # 检查必要的列
            required_columns = ['裁判ID', '姓名']
            for col in required_columns:
                if col not in df.columns:
                    self.logger.error(f"裁判信息文件缺少必要的列: {col}")
                    return False
            
            # 导入数据
            import_count = 0
            for _, row in df.iterrows():
                try:
                    judge = Judge(
                        id=str(row['裁判ID']),
                        name=str(row['姓名'])
                    )
                    
                    if data_manager.add_judge(judge):
                        import_count += 1
                except Exception as e:
                    self.logger.error(f"导入裁判信息失败: {row}, {e}")
            
            self.logger.info(f"成功导入 {import_count} 名裁判")
            return import_count > 0
            
        except Exception as e:
            self.logger.error(f"读取裁判信息文件失败: {e}")
            return False
            
    def export_round1_scoring_sheets(self):
        """导出所有轮次为1的场次的PDF评分表，合并为一个独立的PDF文件"""
        try:
            if not data_manager.current_competition:
                return
            
            # 找出所有轮次为1的场次，并按场次ID排序
            round1_events = []
            for event in data_manager.current_competition.events.values():
                if event.round == '1':
                    round1_events.append(event)
            
            # 按场次ID排序
            round1_events.sort(key=lambda x: int(x.id))
            
            if not round1_events:
                self.logger.info("没有找到轮次为1的场次")
                return
            
            # 创建导出目录
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 使用正确的赛事目录路径
            event_dir = config.get_event_dir(data_manager.current_event_name)
            export_dir = os.path.join(event_dir, "评分表")
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            self.logger.info(f"评分表将导出到目录: {export_dir}")
            
            # 构建合并后的PDF文件路径
            merged_file_name = f"轮次1评分表_{timestamp}.pdf"
            merged_file_path = os.path.join(export_dir, merged_file_name)
            
            # 导入ReportLab的相关模块
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib import colors
            from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from ..models.data_models import ScoringType
            
            # 创建合并后的PDF文档
            doc = SimpleDocTemplate(merged_file_path, pagesize=landscape(A4),
                                  leftMargin=15*mm, rightMargin=15*mm,
                                  topMargin=15*mm, bottomMargin=15*mm)
            
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
            
            # 合并所有场次的PDF内容
            merged_content = []
            
            # 为每个轮次为1的场次生成PDF内容
            for event in round1_events:
                try:
                    # 获取选手数据
                    players = data_manager.get_players_by_event(event.id)
                    if not players:
                        self.logger.warning(f"场次 {event.id} 没有参赛选手，跳过导出")
                        continue
                    
                    # 计算横向A4纸的实际可用尺寸
                    a4_width, a4_height = landscape(A4)
                    available_width = a4_width - 40*mm  # 左右边距各20mm，总计40mm
                    
                    # 计算晋级规则
                    if event.scoring_type == ScoringType.MARK:
                        # Mark制：M进N，M为本场选手数量，N为赛程预订的晋级下一场的人数
                        advancement_rule = f"{len(players)}进{event.advancement_count}"
                    else:
                        # 顺位制：N顺位，N为赛程预订的录取人数
                        advancement_rule = f"{event.advancement_count}顺位"
                    
                    # 添加标题（场次编号. 场次名称     晋级规则）
                    title = Paragraph(f"{event.id}. {event.name}     {advancement_rule}", title_style)
                    merged_content.append(title)
                    merged_content.append(Spacer(1, 15))
                    
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
                    dance_col_width = 35*mm  # 增大舞种列宽度
                    player_col_width = (available_width - dance_col_width) / (num_columns - 1)  # 动态计算选手列宽度
                    col_widths = [dance_col_width] + [player_col_width] * (num_columns - 1)  # 动态计算列宽
                    
                    # 使用固定行高创建表格，确保行高生效
                    table = Table(table_data, colWidths=col_widths, repeatRows=1, rowHeights=[45]*len(table_data))
                    
                    # 设置表格样式，优化内容大小和空间利用率
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
                        
                        # 选手列样式：顶部对齐，方便裁判从上到下填充内容
                        ('VALIGN', (1, 1), (-1, -1), 'TOP'),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        
                        # 舞种列样式：水平和垂直居中，突出显示
                        ('BOLD', (0, 1), (0, -1), True),
                        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                        ('VALIGN', (0, 1), (0, -1), 'MIDDLE'),
                        
                        # 表格边框
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
                    ]))
                    
                    merged_content.append(table)
                    merged_content.append(Spacer(1, 20))
                    
                    # 添加裁判签名
                    signature_data = [["裁判签名：_________________________"]]
                    signature_table = Table(signature_data, colWidths=[150*mm])
                    signature_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 14),
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    
                    merged_content.append(signature_table)
                    
                    # 添加分页符，确保每个场次都在新的一页
                    merged_content.append(PageBreak())
                    
                    self.logger.info(f"成功处理场次 {event.id} 的PDF内容")
                except Exception as e:
                    self.logger.error(f"处理场次 {event.id} 的PDF内容失败: {e}")
            
            # 生成合并后的PDF文件
            if merged_content:
                # 移除最后一个不必要的分页符
                if isinstance(merged_content[-1], PageBreak):
                    merged_content.pop()
                
                doc.build(merged_content)
                self.logger.info(f"成功导出合并后的PDF评分表到: {merged_file_path}")
            
        except Exception as e:
            self.logger.error(f"导出轮次1评分表失败: {e}")
    
    def export_check_in_sheet(self):
        """导出检录表PDF，包含评分表中除了裁判签名的部分，紧凑排列"""
        try:
            if not data_manager.current_competition:
                return
            
            # 找出所有轮次为1的场次，并按场次ID排序
            round1_events = []
            for event in data_manager.current_competition.events.values():
                if event.round == '1':
                    round1_events.append(event)
            
            # 按场次ID排序
            round1_events.sort(key=lambda x: int(x.id))
            
            if not round1_events:
                self.logger.info("没有找到轮次为1的场次，跳过生成检录表")
                return
            
            # 创建导出目录
            import os
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 使用正确的赛事目录路径
            event_dir = config.get_event_dir(data_manager.current_event_name)
            # 直接保存到赛事目录，不创建子目录
            check_in_file_name = f"检录表_{timestamp}.pdf"
            check_in_file_path = os.path.join(event_dir, check_in_file_name)
            
            # 导入ReportLab的相关模块
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib import colors
            from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from ..models.data_models import ScoringType
            
            # 计算页面尺寸和可用空间
            a4_width, a4_height = landscape(A4)
            left_margin = 10*mm
            right_margin = 10*mm
            top_margin = 10*mm
            bottom_margin = 10*mm
            
            available_width = a4_width - left_margin - right_margin
            available_height = a4_height - top_margin - bottom_margin
            
            # 创建PDF文档，使用横向A4格式
            doc = SimpleDocTemplate(check_in_file_path, pagesize=landscape(A4),
                                  leftMargin=left_margin, rightMargin=right_margin,
                                  topMargin=top_margin, bottomMargin=bottom_margin)
            
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
            
            # 创建标题样式，紧凑排列
            title_style = ParagraphStyle(
                name='CustomTitle',
                parent=styles['Title'],
                fontName=font_name,
                fontSize=14,  # 进一步减小字体大小
                leading=18,    # 进一步减小行间距
                alignment=1,
                spaceAfter=6  # 进一步减小标题后的间距
            )
            
            # 创建检录表内容
            check_in_content = []
            
            # 为每个轮次为1的场次生成检录表内容
            for event in round1_events:
                try:
                    # 获取选手数据
                    players = data_manager.get_players_by_event(event.id)
                    if not players:
                        self.logger.warning(f"场次 {event.id} 没有参赛选手，跳过生成检录表")
                        continue
                    
                    # 计算晋级规则
                    if event.scoring_type == ScoringType.MARK:
                        advancement_rule = f"{len(players)}进{event.advancement_count}"
                    else:
                        advancement_rule = f"{event.advancement_count}顺位"
                    
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
                    
                    # 动态计算列宽，让内容占据纸张的大部分，紧凑排列
                    num_columns = len(table_data[0])
                    dance_col_width = 25*mm  # 进一步减小舞种列宽度
                    player_col_width = (available_width - dance_col_width) / (num_columns - 1)  # 动态计算选手列宽度
                    col_widths = [dance_col_width] + [player_col_width] * (num_columns - 1)  # 动态计算列宽
                    
                    # 使用更小的固定行高，进一步紧凑排列
                    row_height = 25  # 进一步减小行高
                    table = Table(table_data, colWidths=col_widths, repeatRows=1, rowHeights=[row_height]*len(table_data))
                    
                    # 设置表格样式，优化内容大小和空间利用率，紧凑排列
                    table.setStyle(TableStyle([
                        # 表头样式
                        ('FONTNAME', (0, 0), (-1, 0), font_name),
                        ('FONTSIZE', (0, 0), (-1, 0), 11),  # 进一步减小字体大小
                        ('BOLD', (0, 0), (-1, 0), True),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        
                        # 数据行样式
                        ('FONTNAME', (0, 1), (-1, -1), font_name),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),  # 进一步减小字体大小
                        
                        # 选手列样式：顶部对齐，方便裁判从上到下填充内容
                        ('VALIGN', (1, 1), (-1, -1), 'TOP'),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        
                        # 舞种列样式：水平和垂直居中，突出显示
                        ('BOLD', (0, 1), (0, -1), True),
                        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                        ('VALIGN', (0, 1), (0, -1), 'MIDDLE'),
                        
                        # 表格边框
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # 减小边框宽度
                        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),  # 减小边框宽度
                    ]))
                    
                    # 使用KeepTogether确保每个赛事的内容保持在一起
                    from reportlab.platypus import KeepTogether
                    
                    # 创建当前赛事的内容组
                    event_content = []
                    
                    # 添加标题（场次编号. 场次名称     晋级规则）
                    title = Paragraph(f"{event.id}. {event.name}     {advancement_rule}", title_style)
                    event_content.append(title)
                    event_content.append(Spacer(1, 8))  # 减小间距
                    
                    event_content.append(table)
                    event_content.append(Spacer(1, 15))  # 减小间距，只添加少量空白
                    
                    # 将当前赛事的内容用KeepTogether包装，确保不会被分割到不同页面
                    check_in_content.append(KeepTogether(event_content))
                    
                    self.logger.info(f"成功处理场次 {event.id} 的检录表内容")
                except Exception as e:
                    self.logger.error(f"处理场次 {event.id} 的检录表内容失败: {e}")
            
            # 生成检录表PDF文件
            if check_in_content:
                # 移除最后一个不必要的间距
                if isinstance(check_in_content[-1], Spacer):
                    check_in_content.pop()
                
                doc.build(check_in_content)
                self.logger.info(f"成功导出检录表到: {check_in_file_path}")
            
        except Exception as e:
            self.logger.error(f"导出检录表失败: {e}")
    
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
            
            # 生成PDF
            doc.build(content)
            
            self.logger.info(f"成功生成PDF文件: {file_path}")
        except Exception as e:
            self.logger.error(f"导出评分表到PDF失败: {e}")
            raise