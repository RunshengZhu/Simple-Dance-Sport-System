#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
奖项得分设置对话框
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional, Callable

from ...models.data_models import AwardPointsConfig


class AwardPointsDialog:
    """奖项得分设置对话框"""

    DEFAULT_POINTS = {1: 9, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
    MAX_RANK = 8

    def __init__(
        self,
        parent: tk.Widget,
        event_name: str,
        current_config: Optional[AwardPointsConfig] = None
    ):
        self.parent = parent
        self.event_name = event_name
        self.current_config = current_config
        self.result: Optional[AwardPointsConfig] = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"设置奖项得分 - {event_name}")
        self.dialog.geometry("400x450")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.entries: Dict[int, ttk.Entry] = {}
        self.vars: Dict[int, tk.StringVar] = {}

        self._center_window()
        self._create_widgets()

        if current_config:
            self._load_config(current_config)

        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.dialog.bind("<Escape>", lambda e: self.on_cancel())

    def _center_window(self):
        """使对话框居中"""
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """创建界面元素"""
        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text=f"场次: {self.event_name}",
            font=("Microsoft YaHei", 11, "bold")
        )
        title_label.pack(pady=(0, 10))

        desc_label = ttk.Label(
            main_frame,
            text="设置各名次的得分（默认前8名：9,7,6,5,4,3,2,1）",
            foreground="gray"
        )
        desc_label.pack(pady=(0, 15))

        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)

        headers = ["名次", "得分"]
        for col, header in enumerate(headers):
            ttk.Label(
                table_frame,
                text=header,
                font=("Microsoft YaHei", 10, "bold")
            ).grid(row=0, column=col, padx=5, pady=5, sticky="ew")

        for i in range(1, self.MAX_RANK + 1):
            default_val = self.DEFAULT_POINTS.get(i, 0)
            self.vars[i] = tk.StringVar(value=str(default_val))

            rank_label = ttk.Label(table_frame, text=f"第 {i} 名")
            rank_label.grid(row=i, column=0, padx=5, pady=3, sticky="w")

            entry = ttk.Entry(table_frame, textvariable=self.vars[i], width=15)
            entry.grid(row=i, column=1, padx=5, pady=3, sticky="ew")
            self.entries[i] = entry

        for i in range(2):
            table_frame.columnconfigure(i, weight=1)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))

        ttk.Button(
            button_frame,
            text="重置默认",
            command=self._reset_to_default
        ).pack(side=tk.LEFT)

        ttk.Button(
            button_frame,
            text="确定",
            command=self.on_ok
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="取消",
            command=self.on_cancel
        ).pack(side=tk.RIGHT)

    def _load_config(self, config: AwardPointsConfig):
        """加载现有配置"""
        for rank, points in config.points.items():
            if rank in self.vars:
                self.vars[rank].set(str(points))

    def _reset_to_default(self):
        """重置为默认值"""
        for rank, default_val in self.DEFAULT_POINTS.items():
            if rank in self.vars:
                self.vars[rank].set(str(default_val))

    def on_ok(self):
        """确定按钮事件"""
        try:
            points = {}
            for rank in range(1, self.MAX_RANK + 1):
                val_str = self.vars[rank].get().strip()
                if val_str:
                    try:
                        val = float(val_str)
                        if val < 0:
                            messagebox.showwarning("警告", f"第 {rank} 名得分不能为负数")
                            return
                        points[rank] = val
                    except ValueError:
                        messagebox.showwarning("警告", f"第 {rank} 名得分无效")
                        return

            event_id = ""
            if self.current_config:
                event_id = self.current_config.event_id

            self.result = AwardPointsConfig(event_id=event_id, points=points)
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")

    def on_cancel(self):
        """取消按钮事件"""
        self.dialog.destroy()

    def show(self) -> Optional[AwardPointsConfig]:
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result


class BatchAwardPointsDialog:
    """批量设置奖项得分对话框"""

    def __init__(
        self,
        parent: tk.Widget,
        events: list,
        on_apply: Optional[Callable] = None
    ):
        self.parent = parent
        self.events = events
        self.on_apply = on_apply
        self.result: Optional[Dict[str, AwardPointsConfig]] = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("批量设置奖项得分")
        self.dialog.geometry("500x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.vars: Dict[str, Dict[int, tk.StringVar]] = {}

        self._center_window()
        self._create_widgets()

        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def _center_window(self):
        """使对话框居中"""
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """创建界面元素"""
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text="批量设置奖项得分",
            font=("Microsoft YaHei", 12, "bold")
        ).pack(pady=(0, 10))

        ttk.Label(
            main_frame,
            text="为选中的场次统一设置得分规则",
            foreground="gray"
        ).pack(pady=(0, 10))

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        headers = ["场次", "1", "2", "3", "4", "5", "6", "7", "8"]
        for col, header in enumerate(headers):
            ttk.Label(
                scrollable_frame,
                text=header,
                font=("Microsoft YaHei", 9, "bold")
            ).grid(row=0, column=col, padx=3, pady=2)

        default_points = {1: 9, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}

        for row, event in enumerate(self.events, start=1):
            event_id = event.get("id", "")
            event_name = event.get("name", "")[:10]

            self.vars[event_id] = {}

            ttk.Label(
                scrollable_frame,
                text=f"{row}. {event_name}",
                font=("Microsoft YaHei", 9)
            ).grid(row=row, column=0, padx=3, pady=2, sticky="w")

            for rank in range(1, 9):
                self.vars[event_id][rank] = tk.StringVar(
                    value=str(default_points.get(rank, 0))
                )
                ttk.Entry(
                    scrollable_frame,
                    textvariable=self.vars[event_id][rank],
                    width=5
                ).grid(row=row, column=rank, padx=2, pady=2)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            button_frame,
            text="应用到所有选中场次",
            command=self._apply_to_all
        ).pack(side=tk.LEFT)

        ttk.Button(
            button_frame,
            text="确定",
            command=self.on_ok
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="取消",
            command=self.on_cancel
        ).pack(side=tk.RIGHT)

    def _apply_to_all(self):
        """将第一行的设置应用到所有行"""
        if not self.events:
            return

        first_event_id = self.events[0].get("id", "")
        if first_event_id not in self.vars:
            return

        first_values = {rank: self.vars[first_event_id][rank].get()
                        for rank in range(1, 9)}

        for event in self.events:
            event_id = event.get("id", "")
            if event_id in self.vars:
                for rank, val in first_values.items():
                    self.vars[event_id][rank].set(val)

    def on_ok(self):
        """确定按钮事件"""
        try:
            result = {}
            for event in self.events:
                event_id = event.get("id", "")
                if event_id in self.vars:
                    points = {}
                    for rank in range(1, 9):
                        try:
                            val = float(self.vars[event_id][rank].get())
                            points[rank] = val
                        except ValueError:
                            points[rank] = 0.0
                    result[event_id] = AwardPointsConfig(event_id=event_id, points=points)

            self.result = result
            self.dialog.destroy()

            if self.on_apply:
                self.on_apply(result)

        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")

    def on_cancel(self):
        """取消按钮事件"""
        self.dialog.destroy()

    def show(self) -> Optional[Dict[str, AwardPointsConfig]]:
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result
