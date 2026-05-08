#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest配置文件
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def sample_competition_data():
    """示例赛事数据"""
    return {
        "name": "测试赛事",
        "date": "2024-10-26",
        "location": "体育馆",
        "competitors": {},
        "judges": {},
        "events": {}
    }


@pytest.fixture
def sample_skating_scores():
    """示例顺位法评分数据"""
    players = ['1', '2', '3', '4', '5']
    scores = {
        'J1': {'1': 1, '2': 2, '3': 3, '4': 4, '5': 5},
        'J2': {'1': 1, '2': 2, '3': 3, '4': 4, '5': 5},
        'J3': {'1': 2, '2': 1, '3': 3, '4': 5, '5': 4},
        'J4': {'1': 1, '2': 2, '3': 3, '4': 4, '5': 5},
        'J5': {'1': 2, '2': 1, '3': 3, '4': 5, '5': 4},
    }
    return players, scores


@pytest.fixture
def sample_mark_scores():
    """示例Mark制评分数据"""
    competitors = ['101', '102', '103', '104', '105']
    judges = ['J1', 'J2', 'J3', 'J4', 'J5']
    marks = {
        'J1': {'101': True, '102': False, '103': True, '104': True, '105': False},
        'J2': {'101': True, '102': True, '103': False, '104': True, '105': False},
        'J3': {'101': True, '102': False, '103': True, '104': False, '105': True},
        'J4': {'101': False, '102': True, '103': True, '104': True, '105': False},
        'J5': {'101': True, '102': True, '103': True, '104': False, '105': True},
    }
    return competitors, judges, marks
