#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 全局配置。

1. 将 worktree 根目录加入 sys.path，使 `core` 与 `src` 均可直接导入。
2. 依赖垫片（shims）：
   本环境无法访问 PyPI（网络策略限制），而 src.algorithms.skating_system
   顶层 `import pandas`、src.utils.config 顶层 `import appdirs`。
   为了把 src/ 作为对照基准导入，这里在【真实包不可用】时注入最小垫片：
   - pandas: 仅实现 src.generate_detail_table 用到的 DataFrame API 子集
   - appdirs: user_data_dir 指向临时目录
   真实的 pandas/appdirs 若已安装则优先使用真实包。
   core/ 本身是纯标准库实现，完全不依赖这些垫片。
"""

import os
import sys
import tempfile

# 确保 worktree 根目录在 sys.path 中（core/ 位于根级）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# 桌面版源码目录（desktop/src 以顶层包名 `src` 导入，作为算法对照基准）
DESKTOP = os.path.join(ROOT, "desktop")
if DESKTOP not in sys.path:
    sys.path.insert(0, DESKTOP)


# ---------------------------------------------------------------- appdirs 垫片
try:
    import appdirs  # noqa: F401
except ImportError:
    import types

    _appdirs = types.ModuleType("appdirs")


    def _user_data_dir(appname=None, appauthor=None, version=None, *args, **kwargs):
        d = os.path.join(tempfile.gettempdir(), "dsh-dancesport-test-appdata")
        os.makedirs(d, exist_ok=True)
        return d


    _appdirs.user_data_dir = _user_data_dir
    sys.modules["appdirs"] = _appdirs


# ---------------------------------------------------------------- pandas 垫片
try:
    import pandas  # noqa: F401
except ImportError:
    import types

    _pandas = types.ModuleType("pandas")

    class _Column(list):
        """单列数据，支持 astype/replace 链式调用"""

        def astype(self, dtype):
            if dtype is str or dtype == "str":
                return _Column(str(v) for v in self)
            raise NotImplementedError("shim only supports astype(str)")

        def replace(self, old, new):
            return _Column(new if v == old else v for v in self)

    class _LocAt:
        def __init__(self, frame):
            self._frame = frame

        def __setitem__(self, key, value):
            idx, col = key
            self._frame._rows[idx][col] = value

    class DataFrame:
        """最小 DataFrame：list-of-dict 行 + 列访问/astype/replace/at/iterrows/sort_values"""

        def __init__(self, data=None, columns=None):
            if columns is None:
                raise NotImplementedError("shim requires explicit columns")
            self.columns = list(columns)
            self._rows = []
            for item in (data or []):
                if isinstance(item, dict):
                    self._rows.append({c: item.get(c) for c in self.columns})
                else:
                    self._rows.append(dict(zip(self.columns, item)))

        def __getitem__(self, col):
            if col not in self.columns:
                raise KeyError(col)
            return _Column(row[col] for row in self._rows)

        def __setitem__(self, col, values):
            if col not in self.columns:
                self.columns.append(col)
            for row, v in zip(self._rows, values):
                row[col] = v

        @property
        def at(self):
            return _LocAt(self)

        def sort_values(self, by, ascending=True):
            self._rows.sort(key=lambda r: r[by], reverse=not ascending)
            return self

        def reset_index(self, drop=False):
            return self

        def iterrows(self):
            for i, row in enumerate(self._rows):
                yield i, row

        def __len__(self):
            return len(self._rows)

        def __iter__(self):
            return iter(self.columns)

        def to_string(self, **kwargs):
            return "\n".join(str(row) for row in self._rows)

    _pandas.DataFrame = DataFrame
    sys.modules["pandas"] = _pandas


# ------------------------------------------------------------- reportlab 垫片
# src/models/__init__ → data_manager → optimized_data_manager →
# results_view_manager 顶层 import reportlab；算法对照只需要 src 包可导入。
try:
    import reportlab  # noqa: F401
except ImportError:
    import types

    _rl = types.ModuleType("reportlab")

    _rl_lib = types.ModuleType("reportlab.lib")
    _rl_pagesizes = types.ModuleType("reportlab.lib.pagesizes")
    _rl_pagesizes.A4 = (595.2755905511812, 841.8897637795277)
    _rl_pagesizes.letter = (612.0, 792.0)
    _rl_colors = types.ModuleType("reportlab.lib")
    _rl_colors.black = 0
    _rl_colors.white = 1
    _rl_colors.red = 2
    _rl_colors.grey = 3
    _rl_units = types.ModuleType("reportlab.lib.units")
    _rl_units.inch = 72.0
    _rl_styles = types.ModuleType("reportlab.lib.styles")


    def _getSampleStyleSheet():
        return {}


    def _ParagraphStyle(name, **kwargs):
        return {"name": name}


    _rl_styles.getSampleStyleSheet = _getSampleStyleSheet
    _rl_styles.ParagraphStyle = _ParagraphStyle
    _rl_platypus = types.ModuleType("reportlab.platypus")
    for _n in ("SimpleDocTemplate", "Table", "TableStyle", "Paragraph", "Spacer"):
        setattr(_rl_platypus, _n, lambda *a, **k: None)
    _rl_pdfbase = types.ModuleType("reportlab.pdfbase")
    _rl_pdfmetrics = types.ModuleType("reportlab.pdfbase.pdfmetrics")
    _rl_pdfmetrics.registerFont = lambda *a, **k: None
    _rl_ttfonts = types.ModuleType("reportlab.pdfbase.ttfonts")
    _rl_ttfonts.TTFont = lambda *a, **k: None

    _rl.lib = _rl_lib
    _rl.platypus = _rl_platypus
    _rl.pdfbase = _rl_pdfbase
    _rl_lib.pagesizes = _rl_pagesizes
    _rl_lib.styles = _rl_styles
    _rl_lib.units = _rl_units
    _rl_lib.colors = _rl_colors
    _rl_pdfbase.pdfmetrics = _rl_pdfmetrics
    _rl_pdfbase.ttfonts = _rl_ttfonts

    sys.modules.update({
        "reportlab": _rl,
        "reportlab.lib": _rl_lib,
        "reportlab.lib.pagesizes": _rl_pagesizes,
        "reportlab.lib.styles": _rl_styles,
        "reportlab.lib.units": _rl_units,
        "reportlab.lib.colors": _rl_colors,
        "reportlab.platypus": _rl_platypus,
        "reportlab.pdfbase": _rl_pdfbase,
        "reportlab.pdfbase.pdfmetrics": _rl_pdfmetrics,
        "reportlab.pdfbase.ttfonts": _rl_ttfonts,
    })
