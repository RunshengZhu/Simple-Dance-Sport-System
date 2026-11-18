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
        conn.execute("PRAGMA synchronous=NORMAL")   # R70：WAL 下安全档，写路径不再每 commit 全量 fsync
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
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    mode TEXT DEFAULT 'individual',            -- R137：individual=个人报名 / unit=单位报名（批量）
    batch_id TEXT DEFAULT '',                  -- 单位批量提交分组（同一次提交共享）
    unit TEXT DEFAULT '',                      -- 单位名称
    contact_name TEXT DEFAULT '',              -- 联系人
    contact_phone TEXT DEFAULT '',             -- 联系电话
    name TEXT DEFAULT '',                      -- 选手（主报）姓名
    unit_self TEXT DEFAULT '',                 -- 选手单位（个人模式可与批次单位不同）
    role TEXT DEFAULT '',                      -- 选手身份（新生/老生等）
    partner TEXT DEFAULT '',                   -- 搭档姓名
    partner_unit TEXT DEFAULT '',
    partner_role TEXT DEFAULT '',
    projects TEXT DEFAULT '',                  -- 报名项目（逗号分隔项目编号）
    note TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',             -- pending 待审 / approved 通过 / rejected 不通过 / imported 已转正式名单
    submit_code TEXT DEFAULT '',               -- 提交码（供选手自查进度）
    created_at TEXT DEFAULT (datetime('now','localtime')),
    reviewed_at TEXT DEFAULT '',
    review_note TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_reg_comp ON registrations(competition_id, status);
CREATE TABLE IF NOT EXISTS cert_designs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    name TEXT DEFAULT '',
    bg_type TEXT DEFAULT 'none',               -- R141：none / pdf / image
    bg_fname TEXT DEFAULT '',
    fields TEXT DEFAULT '[]',                  -- 文本框 JSON [{type,text,x,y,size,align,bold}]
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS cert_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    name TEXT DEFAULT '',
    fname TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS cert_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    number TEXT NOT NULL,
    members TEXT DEFAULT '',                   -- 每行一个姓名（覆盖自动名单：主报+搭档）
    UNIQUE(event_id, number)
);
CREATE INDEX IF NOT EXISTS idx_reg_comp ON registrations(competition_id, status);
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
    partner TEXT DEFAULT '',
    partner_unit TEXT DEFAULT '',
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
    user_id INTEGER,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_events_comp_round ON events(competition_id, project_code, round);
CREATE INDEX IF NOT EXISTS idx_scores_event ON score_records(event_id);
"""


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    # 轻量迁移：已存在的库补列/补表
    ev_cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    if "run_seq" not in ev_cols:
        conn.execute("ALTER TABLE events ADD COLUMN run_seq INTEGER")
    if "announced" not in ev_cols:
        conn.execute("ALTER TABLE events ADD COLUMN announced INTEGER DEFAULT 0")   # 播报标记（备忘）
    if "team_mode" not in ev_cols:
        conn.execute("ALTER TABLE events ADD COLUMN team_mode TEXT DEFAULT 'standard'")   # R73：项目团体计分模式（standard/freshman_half）
    if "judges_assigned" not in ev_cols:
        conn.execute("ALTER TABLE events ADD COLUMN judges_assigned TEXT DEFAULT ''")   # R112 起：列废弃（保留兼容），改用竞赛级 judges_disabled
    comp_cols = {r[1] for r in conn.execute("PRAGMA table_info(competitions)")}
    if "judges_disabled" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN judges_disabled TEXT DEFAULT ''")   # R112：禁用裁判名单（逗号分隔；空=全部启用）
    if "is_trial" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN is_trial INTEGER DEFAULT 0")   # R122c：试用赛（练习专用，公开侧隐藏，评分页刷新即重置）
    if "is_debug" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN is_debug INTEGER DEFAULT 0")   # R135：调试专用赛（仅总管理员可见，公开侧/管理端列表均隐藏）
    if "reg_open" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN reg_open INTEGER DEFAULT 0")       # R137：开放报名开关
    if "reg_modes" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN reg_modes TEXT DEFAULT 'individual'")  # R137：报名模式（逗号分隔 individual/unit）
    if "reg_note" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN reg_note TEXT DEFAULT ''")         # R137：报名须知（公示）
    if "reg_unit_code" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN reg_unit_code TEXT DEFAULT ''")    # R137：单位报名口令（可空=不校验）
    ev_cols0 = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    if "cert_printed_at" not in ev_cols0:
        conn.execute("ALTER TABLE events ADD COLUMN cert_printed_at TEXT DEFAULT ''")   # R139：证书打印时间（空=未打印）
    user_cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    if "pw_plain" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN pw_plain TEXT DEFAULT ''")   # R76c：口令留档（设置/重置时同步记录，供口令表导出；与直达链接同库同等保护）
    judge_cols = {r[1] for r in conn.execute("PRAGMA table_info(judges)")}
    if "unit" not in judge_cols:
        conn.execute("ALTER TABLE judges ADD COLUMN unit TEXT DEFAULT ''")   # R81：裁判单位（可选项；报项导入极简格式）
    # R71 组合语义：搭档姓名（展示列）。背番号仍一人一号（双人项目以男选手号为准，
    # 女伴名挂搭档列；单人项目留空）——计分/检录/晋级/唯一键全部不动。
    comp_cols = {r[1] for r in conn.execute("PRAGMA table_info(competitors)")}
    if "partner" not in comp_cols:
        conn.execute("ALTER TABLE competitors ADD COLUMN partner TEXT DEFAULT ''")
    if "partner_unit" not in comp_cols:
        conn.execute("ALTER TABLE competitors ADD COLUMN partner_unit TEXT DEFAULT ''")   # R71h：搭档单位（跨单位对半拆分的数据基础）
    if "role" not in comp_cols:
        conn.execute("ALTER TABLE competitors ADD COLUMN role TEXT DEFAULT ''")            # R73：选手身份（新生/老生…，老带新计分用）
    if "partner_role" not in comp_cols:
        conn.execute("ALTER TABLE competitors ADD COLUMN partner_role TEXT DEFAULT ''")    # R73：搭档身份
    ec_cols = {r[1] for r in conn.execute("PRAGMA table_info(event_competitors)")}
    if "checked_in" not in ec_cols:
        conn.execute("ALTER TABLE event_competitors ADD COLUMN checked_in INTEGER DEFAULT 0")  # 检录
        conn.execute("ALTER TABLE event_competitors ADD COLUMN checked_by TEXT")
        conn.execute("ALTER TABLE event_competitors ADD COLUMN checked_at TEXT")
    if "file_tiers" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_tiers'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS file_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    perm TEXT NOT NULL DEFAULT 'public',
    token_hash TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS file_objects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tier_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    content_type TEXT DEFAULT 'application/octet-stream',
    downloads INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(tier_id, filename)
);
""")
    if "audit_log" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,            -- 操作人（display_name/username/角色）
    action TEXT NOT NULL,           -- 动作标识，如 'return_scores'/'uncheckin'/'user_password'/'user_active'/'event_delete'/'ce_delete'/'tier_delete'/'file_delete'
    target TEXT DEFAULT '',         -- 对象描述（如 'event:3'/'user:2'/'tier:release/file:x.txt'）
    detail TEXT DEFAULT '',         -- 关键细节（如 撤销的背号列表、新状态）
    ip TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
""")
    se_cols2 = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
    if "comp_id" not in se_cols2:
        conn.execute("ALTER TABLE sessions ADD COLUMN comp_id INTEGER")

    if "score_change_log" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='score_change_log'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS score_change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    judge_code TEXT NOT NULL,
    competitor_number TEXT NOT NULL,
    dance_name TEXT NOT NULL,
    old_mark INTEGER,
    new_mark INTEGER,
    old_placement INTEGER,
    new_placement INTEGER,
    changed_by TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_scl_event ON score_change_log(event_id);
CREATE INDEX idx_scl_ts ON score_change_log(created_at);
""")
    if "snapshot_meta" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snapshot_meta'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS snapshot_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    created_by TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    sha256 TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
""")

    se_cols3 = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    if "comp_id" not in se_cols3:
        conn.execute("ALTER TABLE users ADD COLUMN comp_id INTEGER")
    comp_cols = {r[1] for r in conn.execute("PRAGMA table_info(competitions)")}
    if "setup_done" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN setup_done INTEGER DEFAULT 0")
    if "auto_publish" not in comp_cols:
        conn.execute("ALTER TABLE competitions ADD COLUMN auto_publish INTEGER DEFAULT 0")

    if "app_meta" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_meta'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
""")
        conn.commit()
    if "visit_stats" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='visit_stats'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS visit_stats (
    slug TEXT NOT NULL,
    day TEXT NOT NULL,
    n INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (slug, day)
);
""")

    if "project_splits" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_splits'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS project_splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    parent_code TEXT NOT NULL,
    child_code TEXT NOT NULL,
    label TEXT DEFAULT '',
    cap INTEGER DEFAULT 0,
    strategy TEXT DEFAULT 'random',
    rounds TEXT DEFAULT '',
    UNIQUE(competition_id, child_code)
);
""")   # R89：项目拆分/分组配置——parent 为路由别名（新导入自适应归属），child 为实际参赛项目

    if "schedule_gen_config" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_gen_config'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS schedule_gen_config (
    competition_id INTEGER NOT NULL,
    project_code TEXT NOT NULL DEFAULT '',
    max_entries INTEGER NOT NULL DEFAULT 24,
    cap INTEGER NOT NULL DEFAULT 12,
    final_size INTEGER NOT NULL DEFAULT 8,
    mode TEXT NOT NULL DEFAULT 'auto',
    rounds_spec TEXT NOT NULL DEFAULT '',
    strategy TEXT NOT NULL DEFAULT 'unit_spread',
    team_mode TEXT NOT NULL DEFAULT '',
    updated_at TEXT,
    PRIMARY KEY (competition_id, project_code)
);
""")   # R91：赛程生成配置 v4（项目上限/每场上限/决赛人数/晋级模式/分配策略）
    else:
        sgc_cols = {r[1] for r in conn.execute("PRAGMA table_info(schedule_gen_config)")}
        if "team_mode" not in sgc_cols:
            conn.execute("ALTER TABLE schedule_gen_config ADD COLUMN team_mode TEXT NOT NULL DEFAULT ''")
        if "final_size" not in sgc_cols:   # 旧 v3 表结构升级（配置数据可丢弃）
            conn.execute("DROP TABLE schedule_gen_config")
            conn.executescript("""
CREATE TABLE IF NOT EXISTS schedule_gen_config (
    competition_id INTEGER NOT NULL,
    project_code TEXT NOT NULL DEFAULT '',
    max_entries INTEGER NOT NULL DEFAULT 24,
    cap INTEGER NOT NULL DEFAULT 12,
    final_size INTEGER NOT NULL DEFAULT 8,
    mode TEXT NOT NULL DEFAULT 'auto',
    rounds_spec TEXT NOT NULL DEFAULT '',
    strategy TEXT NOT NULL DEFAULT 'unit_spread',
    team_mode TEXT NOT NULL DEFAULT '',
    updated_at TEXT,
    PRIMARY KEY (competition_id, project_code)
);
""")

    if "users" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")}:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
""")
    se_cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
    if "user_id" not in se_cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
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
