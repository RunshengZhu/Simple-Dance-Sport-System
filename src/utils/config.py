#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import os
import json
from typing import Dict, Any, Optional
import appdirs


class Config:
    """配置管理类"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.app_name = "体育舞蹈赛事独立打分软件"
        self.app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 使用appdirs获取跨平台的系统应用目录
        self.user_data_dir = appdirs.user_data_dir(self.app_name, appauthor="DanceSport")
        self.config_file = os.path.join(self.user_data_dir, "config.json")
        
        # 确保用户数据目录存在
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)
        
        self.default_config = {
            "app_name": self.app_name,
            "version": "1.0.0",
            "current_event": None,
            "recent_events": [],
            "default_data_dir": os.path.join(self.user_data_dir, "test_data"),
            "events_dir": os.path.join(self.user_data_dir, "events"),
            "log_level": "INFO",
            "auto_save": True,
            "auto_save_interval": 300,  # 5分钟
            "backup_count": 5,
            "ui": {
                "theme": "default",
                "font_size": 10,
                "window_size": "1200x800",
                "window_position": "center"
            }
        }
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置和加载的配置，确保所有配置项都存在
                # 只使用非null的配置值，避免覆盖默认配置
                merged_config = self.default_config.copy()
                for key, value in config.items():
                    if value is not None:
                        if isinstance(value, dict) and key in merged_config and isinstance(merged_config[key], dict):
                            # 递归合并字典，只替换非null值
                            for sub_key, sub_value in value.items():
                                if sub_value is not None:
                                    merged_config[key][sub_key] = sub_value
                        else:
                            merged_config[key] = value
                return merged_config
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return self.default_config.copy()
        else:
            # 如果配置文件不存在，创建默认配置文件
            self._save_config(self.default_config)
            return self.default_config.copy()
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置项"""
        keys = key.split('.')
        config = self.config
        
        # 导航到最后一级的父级
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
        
        # 保存配置
        return self._save_config(self.config)
    
    def add_recent_event(self, event_path: str) -> None:
        """添加最近打开的赛事"""
        recent_events = self.get("recent_events", [])
        
        # 如果已存在，先移除
        if event_path in recent_events:
            recent_events.remove(event_path)
        
        # 添加到开头
        recent_events.insert(0, event_path)
        
        # 限制数量
        recent_events = recent_events[:10]
        
        # 保存
        self.set("recent_events", recent_events)
    
    def set_current_event(self, event_path: Optional[str]) -> None:
        """设置当前打开的赛事"""
        self.set("current_event", event_path)
        if event_path:
            self.add_recent_event(event_path)
    
    def get_events_dir(self) -> str:
        """获取赛事数据目录，优先使用export_dir"""
        # 优先使用export_dir作为赛事数据目录
        export_dir = self.get("export_dir")
        if export_dir and os.path.exists(export_dir):
            return export_dir
        # 否则使用默认的events_dir，直接访问配置字典避免递归
        return self.config.get("events_dir", os.path.join(self.user_data_dir, "events"))
    
    def ensure_events_dir(self) -> str:
        """确保赛事目录存在"""
        events_dir = self.get_events_dir()
        if not os.path.exists(events_dir):
            os.makedirs(events_dir)
        return events_dir
    
    def get_event_dir(self, event_name: str) -> str:
        """获取赛事目录路径"""
        events_dir = self.ensure_events_dir()
        return os.path.join(events_dir, event_name)
    
    def get_event_data_file(self, event_name: str) -> str:
        """获取赛事数据文件路径"""
        event_dir = self.get_event_dir(event_name)
        return os.path.join(event_dir, "event.json")
    
    def get_event_backup_file(self, event_name: str) -> str:
        """获取赛事备份文件路径"""
        event_dir = self.get_event_dir(event_name)
        return os.path.join(event_dir, "event_backup.json")


# 全局配置实例
config = Config()