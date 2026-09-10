#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务版包初始化：把仓库根加入 sys.path，使共享算法内核 `core/` 可导入。
本包位于 <repo>/webapp/server，core 位于 <repo>/core；无论以
`python run.py`、`python -m server.seed` 还是 `uvicorn server.app:app` 启动，
均从本文件完成路径引导，无需额外 PYTHONPATH 设置。"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
