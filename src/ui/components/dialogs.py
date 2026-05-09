#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用对话框组件
"""

import tkinter as tk
from tkinter import ttk, messagebox


class ScoreInputDialog:
    """评分输入对话框"""

    def __init__(self, parent, player_number, player_name, current_score, scoring_type):
        self.parent = parent
        self.player_number = player_number
        self.player_name = player_name
        self.current_score = current_score
        self.scoring_type = scoring_type
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("评分输入")
        self.dialog.geometry("300x150")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._center_window()
        self._create_widgets()
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.score_entry.focus_set()

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

        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(info_frame, text=f"选手: {self.player_name} ({self.player_number})").pack(anchor=tk.W)

        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        from ..models.data_models import ScoringType
        if self.scoring_type == ScoringType.MARK:
            ttk.Label(input_frame, text="分数 (5.0-10.0):").pack(anchor=tk.W)
        else:
            ttk.Label(input_frame, text="名次:").pack(anchor=tk.W)

        self.score_var = tk.StringVar(value=str(self.current_score) if self.current_score else "")
        self.score_entry = ttk.Entry(input_frame, textvariable=self.score_var)
        self.score_entry.pack(fill=tk.X, pady=(5, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="确定", command=self.on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=self.on_cancel).pack(side=tk.RIGHT)

    def on_ok(self):
        """确定按钮事件处理"""
        score_str = self.score_var.get().strip()
        if not score_str:
            messagebox.showwarning("警告", "请输入评分")
            return

        try:
            from ..models.data_models import ScoringType
            if self.scoring_type == ScoringType.MARK:
                score = float(score_str)
                if not (5.0 <= score <= 10.0):
                    messagebox.showwarning("警告", "分数必须在5.0-10.0之间")
                    return
            else:
                score = int(score_str)
                if score < 1:
                    messagebox.showwarning("警告", "名次必须大于0")
                    return

            self.result = score
            self.dialog.destroy()
        except ValueError:
            messagebox.showwarning("警告", "请输入有效的数字")

    def on_cancel(self):
        """取消按钮事件处理"""
        self.dialog.destroy()

    def show(self):
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result
