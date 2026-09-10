#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理模块
"""

import os
import logging
import logging.handlers
from datetime import datetime
from .config import config


def setup_logger() -> logging.Logger:
    """设置日志记录器"""
    # 确保日志目录存在
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建日志文件路径
    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    
    # 创建日志记录器
    logger = logging.getLogger("dance_sport_competition")
    logger.setLevel(getattr(logging, config.get("log_level", "INFO")))
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 创建文件处理器
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=config.get("backup_count", 5),
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 设置格式化器
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger() -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger("dance_sport_competition")