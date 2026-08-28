#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""种子数据：创建演示赛事并导入 server/seed 下 CSV（用于开发/测试）。用法：
    python -m server.seed   # 幂等：名为「演示测试赛」的赛事存在则跳过
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import db  # noqa: E402

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")


def import_csv(competition_id, kind, filename):
    with open(os.path.join(SEED_DIR, filename), "rb") as f:
        raw = f.read()
    import csv
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    header, data = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
    h = {name: i for i, name in enumerate(header)}
    conn = db.get_db()

    def col(*names):
        for n in names:
            if n in h:
                return h[n]
        return None

    if kind == "competitors":
        for r in data:
            if r[h["背番号"]].strip():
                conn.execute(
                    "INSERT OR REPLACE INTO competitors(competition_id, number, project_code, name, unit) VALUES(?,?,?,?,?)",
                    (competition_id, r[h["背番号"]].strip(), r[col("项目编号")].strip(),
                     r[col("姓名")].strip(), r[col("学校/单位")].strip()))
    elif kind == "judges":
        for r in data:
            if r[h["裁判ID"]].strip():
                conn.execute("INSERT OR REPLACE INTO judges(competition_id, code, name) VALUES(?,?,?)",
                             (competition_id, r[h["裁判ID"]].strip(), r[col("姓名")].strip()))
    elif kind == "schedule":
        for r in data:
            code = r[h["场次编号"]].strip()
            if not code:
                continue
            styp = r[col("评分类型")].strip().upper()
            styp = "顺位法" if styp == "SKATING" else "Mark制"
            proj = r[col("项目编号")].strip()
            conn.execute("INSERT OR IGNORE INTO projects(competition_id, code, name) VALUES(?,?,?)",
                         (competition_id, proj, proj))
            cur = conn.execute(
                "INSERT OR IGNORE INTO events(competition_id, code, name, project_code, round, scoring_type, advancement_count)"
                " VALUES(?,?,?,?,?,?,?)",
                (competition_id, code, r[col("场次名称")].strip(), proj, int(r[col("轮次")]), styp,
                 int(r[col("晋级人数")]) if r[col("晋级人数")].strip().isdigit() else 0))
            ev_id = cur.lastrowid or conn.execute(
                "SELECT id FROM events WHERE competition_id=? AND code=?", (competition_id, code)).fetchone()["id"]
            conn.execute("DELETE FROM event_dances WHERE event_id=?", (ev_id,))
            for k, d in enumerate([x.strip() for x in r[col("舞种")].split(",") if x.strip()]):
                conn.execute("INSERT INTO event_dances(event_id, name, ord) VALUES(?,?,?)", (ev_id, d, k))
            if int(r[col("轮次")]) == 1 and r[col("参赛选手")].strip():
                for num in [x.strip() for x in r[col("参赛选手")].split(",") if x.strip()]:
                    conn.execute("INSERT OR IGNORE INTO event_competitors(event_id, competitor_number) VALUES(?,?)",
                                 (ev_id, num))


def main():
    db.init_db()
    conn = db.get_db()
    exists = conn.execute("SELECT id FROM competitions WHERE name='演示测试赛'").fetchone()
    if exists:
        print("种子赛事已存在（id=%s），跳过" % exists["id"])
        return
    cur = conn.execute("INSERT INTO competitions(name, date, location, active) VALUES('演示测试赛','2026-08-27','体育馆',1)")
    cid = cur.lastrowid
    import_csv(cid, "competitors", "competitors.csv")
    import_csv(cid, "competitors", "mark_competitors.csv")
    import_csv(cid, "judges", "judges.csv")
    import_csv(cid, "schedule", "schedule.csv")
    import_csv(cid, "schedule", "mark_schedule.csv")
    conn.commit()
    print("种子赛事已创建（id=%s）：项目 W1（顺位法，含第2轮回填目标）、M1（Mark制）" % cid)


if __name__ == "__main__":
    main()
