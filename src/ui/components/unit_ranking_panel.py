#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单位总分实时面板
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Optional, Callable
from datetime import datetime

from ...models.data_models import (
    CompetitionUnitPoints, UnitTotalPoints, UnitPointsRecord,
    AwardPointsConfig
)
from ...algorithms.unit_points import UnitPointsCalculator


class UnitRankingPanel(ttk.Frame):
    """单位总分排名面板"""

    def __init__(
        self,
        parent: tk.Widget,
        data_manager=None,
        on_refresh: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.data_manager = data_manager
        self.on_refresh = on_refresh
        self.calculator = UnitPointsCalculator()
        self.unit_points: Optional[CompetitionUnitPoints] = None
        self.auto_refresh_enabled = False
        self.refresh_job = None

        self._create_widgets()
        self._setup_auto_refresh()

    def _create_widgets(self):
        """创建界面元素"""
        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(
            toolbar_frame,
            text="单位总分排名",
            font=("Microsoft YaHei", 12, "bold")
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.refresh_btn = ttk.Button(
            toolbar_frame,
            text="刷新",
            command=self.refresh
        )
        self.refresh_btn.pack(side=tk.RIGHT, padx=2)

        self.auto_refresh_var = tk.BooleanVar(value=False)
        self.auto_refresh_check = ttk.Checkbutton(
            toolbar_frame,
            text="自动刷新(5秒)",
            variable=self.auto_refresh_var,
            command=self._toggle_auto_refresh
        )
        self.auto_refresh_check.pack(side=tk.RIGHT, padx=5)

        self.last_update_label = ttk.Label(
            toolbar_frame,
            text="",
            foreground="gray"
        )
        self.last_update_label.pack(side=tk.RIGHT, padx=10)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("rank", "unit", "total_points", "record_count")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        self.tree.heading("rank", text="排名")
        self.tree.heading("unit", text="参赛单位")
        self.tree.heading("total_points", text="总分")
        self.tree.heading("record_count", text="得分项目数")

        self.tree.column("rank", width=60, anchor="center")
        self.tree.column("unit", width=200, anchor="w")
        self.tree.column("total_points", width=100, anchor="center")
        self.tree.column("record_count", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-Button-1>", self._on_item_double_click)

        details_frame = ttk.LabelFrame(self, text="得分明细", padding=5)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.details_tree = ttk.Treeview(
            details_frame,
            columns=("event", "competitor", "rank", "points", "is_split"),
            show="headings",
            height=8
        )

        self.details_tree.heading("event", text="场次")
        self.details_tree.heading("competitor", text="选手")
        self.details_tree.heading("rank", text="名次")
        self.details_tree.heading("points", text="得分")
        self.details_tree.heading("is_split", text="分摊")

        self.details_tree.column("event", width=150, anchor="w")
        self.details_tree.column("competitor", width=120, anchor="w")
        self.details_tree.column("rank", width=60, anchor="center")
        self.details_tree.column("points", width=80, anchor="center")
        self.details_tree.column("is_split", width=60, anchor="center")

        self.details_tree.pack(fill=tk.BOTH, expand=True)

        self.details_tree.bind("<<TreeviewSelect>>", self._on_detail_select)

    def _setup_auto_refresh(self):
        """设置自动刷新"""
        pass

    def _toggle_auto_refresh(self):
        """切换自动刷新"""
        self.auto_refresh_enabled = self.auto_refresh_var.get()
        if self.auto_refresh_enabled:
            self._schedule_refresh()
        elif self.refresh_job:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None

    def _schedule_refresh(self):
        """安排下次刷新"""
        if self.auto_refresh_enabled:
            self.refresh_job = self.after(5000, self._do_refresh)

    def _do_refresh(self):
        """执行刷新"""
        self.refresh()
        self._schedule_refresh()

    def refresh(self):
        """刷新数据"""
        try:
            if self.data_manager and hasattr(self.data_manager, 'calculate_unit_points'):
                self.unit_points = self.data_manager.calculate_unit_points()
            self._update_display()
            self._update_last_time()
        except Exception as e:
            print(f"刷新单位总分失败: {e}")

    def _update_display(self):
        """更新显示"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.unit_points or not self.unit_points.unit_points:
            return

        ranking = self.unit_points.get_ranking()

        for unit, total_pts, rank in ranking:
            self.tree.insert("", "end", values=(
                rank,
                unit,
                f"{total_pts:.1f}",
                len(self.unit_points.unit_points[unit].records)
            ), tags=(unit,))

        self.tree.tag_configure("selected", background="#0078D7", foreground="white")

    def _update_last_time(self):
        """更新时间标签"""
        if self.unit_points:
            time_str = self.unit_points.last_update.strftime("%H:%M:%S")
            self.last_update_label.config(text=f"更新: {time_str}")

    def _on_item_double_click(self, event):
        """双击项目显示详情"""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tree.item(item, "values")
        if values:
            self._show_unit_details(values[1])

    def _show_unit_details(self, unit: str):
        """显示单位详细得分"""
        for item in self.details_tree.get_children():
            self.details_tree.delete(item)

        if not self.unit_points or unit not in self.unit_points.unit_points:
            return

        unit_pts = self.unit_points.unit_points[unit]
        for record in unit_pts.records:
            split_text = "是" if record.is_split else "否"
            self.details_tree.insert("", "end", values=(
                record.event_name[:15],
                record.competitor_name,
                record.rank,
                f"{record.points:.1f}",
                split_text
            ))

    def _on_detail_select(self, event):
        """选中详情项"""
        pass

    def set_unit_points(self, unit_points: CompetitionUnitPoints):
        """设置单位总分数据"""
        self.unit_points = unit_points
        self._update_display()
        self._update_last_time()

    def destroy(self):
        """销毁面板"""
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
        super().destroy()


class UnitRankingWindow(tk.Toplevel):
    """单位总分排名独立窗口"""

    def __init__(self, parent, data_manager=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("单位总分排名")
        self.geometry("700x600")
        self.data_manager = data_manager

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.panel = UnitRankingPanel(self, data_manager=data_manager)
        self.panel.pack(fill=tk.BOTH, expand=True)

        self.refresh()

    def refresh(self):
        """刷新数据"""
        if self.panel:
            self.panel.refresh()

    def on_closing(self):
        """关闭窗口"""
        self.destroy()
