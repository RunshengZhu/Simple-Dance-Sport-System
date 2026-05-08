#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据管理模块 - 从 optimized_data_manager 重新导出
"""

from .optimized_data_manager import OptimizedDataManager

data_manager = OptimizedDataManager()

__all__ = ['OptimizedDataManager', 'data_manager']
