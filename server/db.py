#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite 存储层：连接（WAL）、schema 初始化、种子数据。"""

import json
import os
import sqlite3
import threading

DEFAULT_DB = os.environ.get(
    "DSPORT_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dancesport.db"),
)

_local = threading.local()


def get_db():
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(DEFAULT_DB), exist_ok=True)
        conn = sqlite3.connect(DEFAULT_DB, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        _local.conn = conn
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT DEFAULT '',
    location TEXT DEFAULT '',
    active INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    code TEXT NOT NULL,
    name TEXT DEFAULT '',
    UNIQUE(competition_id, code)
);
CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    number TEXT NOT NULL,
    project_code TEXT DEFAULT '',
    name TEXT DEFAULT '',
    unit TEXT DEFAULT '',
    UNIQUE(competition_id, number, project_code)
);
CREATE TABLE IF NOT EXISTS judges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    code TEXT NOT NULL,
    name TEXT DEFAULT '',
    UNIQUE(competition_id, code)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    code TEXT NOT NULL,
    name TEXT DEFAULT '',
    project_code TEXT DEFAULT '',
    round INTEGER DEFAULT 1,
    scoring_type TEXT DEFAULT '顺位法',
    advancement_count INTEGER DEFAULT 0,
    advancement_rule TEXT DEFAULT 'all_tied_advance',
    status TEXT DEFAULT 'pending',
    published INTEGER DEFAULT 0,
    UNIQUE(competition_id, code)
);
CREATE TABLE IF NOT EXISTS event_dances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    name TEXT NOT NULL,
    ord INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS event_competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    competitor_number TEXT NOT NULL,
    UNIQUE(event_id, competitor_number)
);
CREATE TABLE IF NOT EXISTS score_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    judge_code TEXT NOT NULL,
    competitor_number TEXT NOT NULL,
    dance_name TEXT NOT NULL,
    mark INTEGER,
    placement INTEGER,
    timestamp TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(event_id, dance_name, judge_code, competitor_number)
);
CREATE TABLE IF NOT EXISTS results (
    event_id INTEGER PRIMARY KEY REFERENCES events(id),
    calculation_time TEXT DEFAULT (datetime('now','localtime')),
    results_data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    judge_code TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_events_comp_round ON events(competition_id, project_code, round);
CREATE INDEX IF NOT EXISTS idx_scores_event ON score_records(event_id);
"""


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    # 轻量迁移：已存在的库补列（run_seq = 比赛顺序，防连场编排用）
    cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    if "run_seq" not in cols:
        conn.execute("ALTER TABLE events ADD COLUMN run_seq INTEGER")
        conn.commit()


def rowdict(row):
    return dict(row) if row is not None else None


def rows(rowlist):
    return [dict(r) for r in rowlist]


def event_to_dict(ev, dances=None):
    d = dict(ev)
    if dances is not None:
        d["dances"] = dances
    return d


def dump_results(results_dict):
    return json.dumps(results_dict, ensure_ascii=False, default=str)


def load_results(text):
    return json.loads(text)
