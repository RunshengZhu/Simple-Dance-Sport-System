#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""体育舞蹈赛事评分系统 · 服务版（M1~M5）。FastAPI + Jinja2 + SQLite WAL + SSE，端口 8321。"""

import asyncio
import csv
import io
import json
import os
import secrets
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import ScoringType
from core.data_models import ScoringType as ST

from server import db, sse
from server.scoring_service import (
    calculate_event, load_results, roster, dances_of, judges_of, is_complete,
    advancement_proposal, confirm_advancement, scoring_type_of, scoring_kind,
)

ADMIN_PASSWORD = os.environ.get("DSPORT_ADMIN_PASSWORD", "admin123")
PORT = int(os.environ.get("DSPORT_PORT", "8321"))
BASE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="体育舞蹈赛事评分系统 · 服务版", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))


# ------------------------------------------------------------------ auth
def _session(request: Request):
    token = request.cookies.get("session")
    if not token:
        return None
    return db.rowdict(db.get_db().execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone())


def require_admin(request: Request):
    s = _session(request)
    if not s or s["role"] != "admin":
        raise HTTPException(status_code=401, detail="需要管理员登录")
    return s


def require_judge(request: Request):
    s = _session(request)
    if not s or s["role"] != "judge":
        raise HTTPException(status_code=401, detail="需要裁判登录")
    return s


def login_failures_window(ip: str):
    now = time.time()
    wins = _login_windows.setdefault(ip, [])
    while wins and now - wins[0] > 60:
        wins.pop(0)
    return wins


def login_blocked(ip: str) -> bool:
    return len(login_failures_window(ip)) >= 5


_login_windows = {}
_failed = {}


@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    role = body.get("role")
    ip = request.client.host if request.client else "?"
    if login_blocked(ip):
        raise HTTPException(status_code=429, detail="失败次数过多，请稍后再试")
    token = secrets.token_urlsafe(32)
    conn = db.get_db()
    if role == "admin":
        if body.get("password") != ADMIN_PASSWORD:
            login_failures_window(ip).append(time.time())
            raise HTTPException(status_code=403, detail="口令错误")
        conn.execute("INSERT INTO sessions(token, role) VALUES(?, 'admin')", (token,))
    elif role == "judge":
        code = str(body.get("judge_id") or "")
        row = conn.execute("SELECT * FROM judges WHERE code=? ", (code,)).fetchone()
        # 需限定赛事：任一赛事存在该裁判即可（单激活赛事语义）
        if not row:
            login_failures_window(ip).append(time.time())
            raise HTTPException(status_code=403, detail="裁判 ID 不存在")
        conn.execute("INSERT INTO sessions(token, role, judge_code) VALUES(?, 'judge', ?)", (token, code))
    else:
        raise HTTPException(status_code=400, detail="未知角色")
    conn.commit()
    resp = JSONResponse({"ok": True, "role": role})
    resp.set_cookie("session", token, httponly=True, samesite="lax")
    return resp


@app.post("/api/logout")
async def api_logout(request: Request):
    token = request.cookies.get("session")
    if token:
        db.get_db().execute("DELETE FROM sessions WHERE token=?", (token,))
        db.get_db().commit()
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp


def _active_competition():
    return db.rowdict(db.get_db().execute("SELECT * FROM competitions WHERE active=1 ORDER BY id DESC").fetchone())


def _comp_or_404(competition_id):
    c = db.rowdict(db.get_db().execute("SELECT * FROM competitions WHERE id=?", (competition_id,)).fetchone())
    if not c:
        raise HTTPException(status_code=404, detail="赛事不存在")
    return c


def _event_or_404(ceid):
    ev = db.rowdict(db.get_db().execute("SELECT * FROM events WHERE id=?", (ceid,)).fetchone())
    if not ev:
        raise HTTPException(status_code=404, detail="场次不存在")
    return ev


# ------------------------------------------------------------------ pages
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    s = _session(request)
    if s and s["role"] == "admin":
        return RedirectResponse("/events")
    if s and s["role"] == "judge":
        return RedirectResponse("/judge")
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})


@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request):
    require_admin(request)
    comps = db.rows(db.get_db().execute("SELECT * FROM competitions ORDER BY id DESC"))
    return templates.TemplateResponse(request, "events.html", {"request": request, "comps": comps})


@app.get("/events/{competition_id}/import", response_class=HTMLResponse)
async def import_page(request: Request, competition_id: int):
    require_admin(request)
    return templates.TemplateResponse(request, "import.html", {"request": request, "comp": _comp_or_404(competition_id)})


@app.get("/events/{competition_id}/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, competition_id: int):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    evs = db.rows(db.get_db().execute(
        "SELECT * FROM events WHERE competition_id=? ORDER BY project_code, round, code", (competition_id,)))
    for ev in evs:
        ev["dances"] = dances_of(ev["id"])
        ev["roster"] = roster(ev["id"])
    return templates.TemplateResponse(request, "schedule.html", {"request": request, "comp": comp, "events": evs})


@app.get("/events/{competition_id}/console/{ceid}", response_class=HTMLResponse)
async def console_page(request: Request, competition_id: int, ceid: int):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    ev = _event_or_404(ceid)
    all_competitors = db.rows(db.get_db().execute(
        "SELECT DISTINCT number, name, unit FROM competitors WHERE competition_id=? ORDER BY number", (competition_id,)))
    return templates.TemplateResponse(request, "console.html", {
        "comp": comp, "ev": ev,
        "dances": dances_of(ev["id"]), "roster": roster(ev["id"]),
        "all_competitors": all_competitors,
        "judges": judges_of(competition_id), "result": load_results(ev["id"]),
    })


@app.get("/events/{competition_id}/results", response_class=HTMLResponse)
async def results_page(request: Request, competition_id: int):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    evs = db.rows(db.get_db().execute(
        "SELECT * FROM events WHERE competition_id=? AND status IN ('calculated','published') ORDER BY project_code, round, code",
        (competition_id,)))
    payload = []
    for ev in evs:
        res = load_results(ev["id"])
        if res:
            payload.append({"ev": ev, "results": res})
    return templates.TemplateResponse(request, "results.html", {"request": request, "comp": comp, "payload": payload})


@app.get("/judge", response_class=HTMLResponse)
async def judge_home(request: Request):
    s = require_judge(request)
    comp = _active_competition()
    assignments = []
    if comp:
        evs = db.rows(db.get_db().execute(
            "SELECT * FROM events WHERE competition_id=? AND status='scoring' ORDER BY code", (comp["id"],)))
        for ev in evs:
            ev["dances"] = dances_of(ev["id"])
            ev["my_done"] = _judge_sheet_status(ev["id"], s["judge_code"])
            assignments.append(ev)
    return templates.TemplateResponse(request, "judge_home.html", {
        "comp": comp, "judge_code": s["judge_code"], "assignments": assignments})


def _judge_sheet_status(event_id, judge_code):
    conn = db.get_db()
    dances = dances_of(event_id)
    roster_list = roster(event_id)
    done = []
    for d in dances:
        n = conn.execute(
            "SELECT COUNT(*) c FROM score_records WHERE event_id=? AND dance_name=? AND judge_code=?",
            (event_id, d, judge_code)).fetchone()["c"]
        done.append({"dance": d, "submitted": n >= len(roster_list) and len(roster_list) > 0})
    return done


@app.get("/judge/competition-events/{ceid}/dances/{dance}", response_class=HTMLResponse)
async def judge_sheet_page(request: Request, ceid: int, dance: str):
    s = require_judge(request)
    ev = _event_or_404(ceid)
    comp = _comp_or_404(ev["competition_id"])
    roster_list = roster(ev["id"])
    rows = {}
    for num in roster_list:
        rows[num] = db.rowdict(db.get_db().execute(
            "SELECT * FROM score_records WHERE event_id=? AND judge_code=? AND dance_name=? AND competitor_number=?",
            (ev["id"], s["judge_code"], dance, num)).fetchone())
    competitors = {c["number"]: c for c in db.rows(db.get_db().execute(
        "SELECT number, name, unit FROM competitors WHERE competition_id=?", (ev["competition_id"],)))}
    return templates.TemplateResponse(request, "judge_sheet.html", {
        "ev": ev, "comp": comp, "dance": dance,
        "roster": roster_list, "rows": rows, "competitors": competitors,
        "is_skating": scoring_type_of(ev) == ScoringType.SKATING,
        "is_mark": scoring_kind(ev) == "mark",
        "is_score": scoring_kind(ev) == "score",
        "n": len(roster_list),
    })


@app.get("/public/schedule", response_class=HTMLResponse)
async def public_schedule(request: Request):
    comp = _active_competition()
    evs = []
    if comp:
        evs = db.rows(db.get_db().execute(
            "SELECT code,name,project_code,round,status FROM events WHERE competition_id=? ORDER BY project_code, round, code",
            (comp["id"],)))
    return templates.TemplateResponse(request, "public_schedule.html", {"request": request, "comp": comp, "events": evs})


@app.get("/public/results", response_class=HTMLResponse)
async def public_results(request: Request):
    comp = _active_competition()
    payload = []
    if comp:
        evs = db.rows(db.get_db().execute(
            "SELECT * FROM events WHERE competition_id=? AND published=1 ORDER BY project_code, round, code", (comp["id"],)))
        for ev in evs:
            res = load_results(ev["id"])
            if res:
                payload.append({"ev": ev, "results": res})
    standings = _team_standings(comp["id"], published_only=True) if comp else {"standings": []}
    return templates.TemplateResponse(request, "public_results.html", {"request": request, "comp": comp, "payload": payload, "standings": standings})


@app.get("/screen", response_class=HTMLResponse)
async def screen_page(request: Request):
    comp = _active_competition()
    return templates.TemplateResponse(request, "screen.html", {"request": request, "comp": comp})


# ------------------------------------------------------------------ admin API
@app.get("/api/events")
async def api_events(request: Request):
    require_admin(request)
    comps = db.rows(db.get_db().execute(
        "SELECT c.*, (SELECT COUNT(*) FROM events e WHERE e.competition_id=c.id) event_count FROM competitions c ORDER BY c.id DESC"))
    return {"events": comps}


@app.post("/api/events")
async def api_create_event(request: Request):
    require_admin(request)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="赛事名称必填")
    conn = db.get_db()
    cur = conn.execute("INSERT INTO competitions(name, date, location, active) VALUES(?,?,?,0)",
                       (name, body.get("date") or "", body.get("location") or ""))
    conn.commit()
    return {"ok": True, "id": cur.lastrowid}


@app.post("/api/events/{competition_id}/activate")
async def api_activate(competition_id: int, request: Request = None):
    require_admin(request)
    _comp_or_404(competition_id)
    conn = db.get_db()
    conn.execute("UPDATE competitions SET active=0")
    conn.execute("UPDATE competitions SET active=1 WHERE id=?", (competition_id,))
    conn.commit()
    return {"ok": True}


@app.delete("/api/events/{competition_id}")
async def api_delete_event(competition_id: int, request: Request = None):
    require_admin(request)
    conn = db.get_db()
    for ev in db.rows(conn.execute("SELECT id FROM events WHERE competition_id=?", (competition_id,))):
        conn.execute("DELETE FROM score_records WHERE event_id=?", (ev["id"],))
        conn.execute("DELETE FROM event_dances WHERE event_id=?", (ev["id"],))
        conn.execute("DELETE FROM event_competitors WHERE event_id=?", (ev["id"],))
        conn.execute("DELETE FROM results WHERE event_id=?", (ev["id"],))
    for t in ("events", "competitors", "judges", "projects"):
        conn.execute("DELETE FROM {0} WHERE competition_id=?".format(t), (competition_id,))
    conn.execute("DELETE FROM competitions WHERE id=?", (competition_id,))
    conn.commit()
    return {"ok": True}


def _read_csv_body(raw: bytes):
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="CSV 至少需要表头和一行数据")
    header = [h.strip() for h in rows[0]]
    return header, rows[1:]


def _col(header_map, *names):
    for n in names:
        if n in header_map:
            return header_map[n]
    return None


@app.post("/api/events/{competition_id}/imports/{kind}")
async def api_import(competition_id: int, kind: str, request: Request = None):
    require_admin(request)
    _comp_or_404(competition_id)
    raw = await request.body()
    header, data_rows = _read_csv_body(raw)
    h = {name: i for i, name in enumerate(header)}
    conn = db.get_db()
    count, problems = 0, []

    if kind == "competitors":
        i_num, i_name = _col(h, "背番号", "number"), _col(h, "姓名", "name")
        i_unit, i_proj = _col(h, "学校/单位", "单位", "unit"), _col(h, "项目编号", "project")
        if i_num is None:
            raise HTTPException(status_code=400, detail="缺少列：背番号")
        for r in data_rows:
            num = r[i_num].strip()
            if not num:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO competitors(competition_id, number, project_code, name, unit) VALUES(?,?,?,?,?)",
                (competition_id, num, (r[i_proj].strip() if i_proj is not None and i_proj < len(r) else ""),
                 r[i_name].strip() if i_name is not None and i_name < len(r) else "",
                 r[i_unit].strip() if i_unit is not None and i_unit < len(r) else ""))
            count += 1
    elif kind == "judges":
        i_id, i_name = _col(h, "裁判ID", "裁判 ID", "judge"), _col(h, "姓名", "name")
        if i_id is None:
            raise HTTPException(status_code=400, detail="缺少列：裁判ID")
        for r in data_rows:
            code = r[i_id].strip()
            if not code:
                continue
            conn.execute("INSERT OR REPLACE INTO judges(competition_id, code, name) VALUES(?,?,?)",
                         (competition_id, code, r[i_name].strip() if i_name is not None and i_name < len(r) else ""))
            count += 1
    elif kind == "schedule":
        i_code = _col(h, "场次编号", "code")
        i_name, i_proj = _col(h, "场次名称", "name"), _col(h, "项目编号", "project")
        i_round, i_dance = _col(h, "轮次", "round"), _col(h, "舞种", "dances")
        i_type = _col(h, "评分类型", "scoring_type")
        i_adv = _col(h, "晋级人数", "advancement_count")
        i_comps = _col(h, "参赛选手", "competitors")
        if i_code is None or i_round is None:
            raise HTTPException(status_code=400, detail="缺少列：场次编号/轮次")
        for r in data_rows:
            code = r[i_code].strip()
            if not code:
                continue
            rnd = int(r[i_round].strip() or 1)
            styp = (r[i_type].strip() if i_type is not None and i_type < len(r) else "SKATING").upper()
            styp = {"SKATING": "顺位法", "MARK": "Mark制", "SCORE": "评分制"}.get(styp, "Mark制")
            proj = r[i_proj].strip() if i_proj is not None and i_proj < len(r) else ""
            conn.execute("INSERT OR IGNORE INTO projects(competition_id, code, name) VALUES(?,?,?)",
                         (competition_id, proj, proj))
            cur = conn.execute(
                "INSERT OR IGNORE INTO events(competition_id, code, name, project_code, round, scoring_type, advancement_count)"
                " VALUES(?,?,?,?,?,?,?)",
                (competition_id, code,
                 r[i_name].strip() if i_name is not None and i_name < len(r) else code,
                 proj, rnd, styp,
                 int(r[i_adv]) if i_adv is not None and i_adv < len(r) and r[i_adv].strip().isdigit() else 0))
            ev_id = cur.lastrowid
            if ev_id == 0:
                ev_id = conn.execute("SELECT id FROM events WHERE competition_id=? AND code=?",
                                     (competition_id, code)).fetchone()["id"]
            if i_dance is not None and i_dance < len(r):
                conn.execute("DELETE FROM event_dances WHERE event_id=?", (ev_id,))
                for k, dname in enumerate([x.strip() for x in r[i_dance].replace("，", ",").split(",") if x.strip()]):
                    conn.execute("INSERT INTO event_dances(event_id, name, ord) VALUES(?,?,?)", (ev_id, dname, k))
            if i_comps is not None and i_comps < len(r) and rnd == 1:
                conn.execute("DELETE FROM event_competitors WHERE event_id=?", (ev_id,))
                for num in [x.strip() for x in r[i_comps].replace("，", ",").split(",") if x.strip()]:
                    conn.execute("INSERT OR IGNORE INTO event_competitors(event_id, competitor_number) VALUES(?,?)",
                                 (ev_id, num))
            count += 1
    else:
        raise HTTPException(status_code=400, detail="未知导入类型")
    conn.commit()
    sse.bus.publish(competition_id, "schedule_changed")
    return {"ok": True, "imported": count, "problems": problems}


def _require_active_event(ceid):
    ev = _event_or_404(ceid)
    comp = _comp_or_404(ev["competition_id"])
    if not comp["active"]:
        raise HTTPException(status_code=400, detail="赛事未激活，无法操作场次")
    return ev, comp


@app.post("/api/competition-events/{ceid}/open")
async def api_open(ceid: int, request: Request = None):
    require_admin(request)
    ev, comp = _require_active_event(ceid)
    body = await request.json()
    roster_list = [str(n) for n in body.get("roster") or []]
    if not roster_list:
        raise HTTPException(status_code=400, detail="上场选手名单不能为空")
    if dances_of(ev["id"]) == []:
        raise HTTPException(status_code=400, detail="场次未配置舞种，请检查赛程导入")
    had_scores = bool(db.get_db().execute(
        "SELECT 1 FROM score_records WHERE event_id=? LIMIT 1", (ceid,)).fetchone())
    conn = db.get_db()
    conn.execute("DELETE FROM event_competitors WHERE event_id=?", (ceid,))
    if had_scores or body.get("reset"):
        conn.execute("DELETE FROM score_records WHERE event_id=?", (ceid,))
        conn.execute("DELETE FROM results WHERE event_id=?", (ceid,))
    for num in roster_list:
        conn.execute("INSERT OR IGNORE INTO event_competitors(event_id, competitor_number) VALUES(?,?)", (ceid, num))
    conn.execute("UPDATE events SET status='scoring' WHERE id=?", (ceid,))
    conn.commit()
    sse.bus.publish(comp["id"], "competition_event_opened", {"event_id": ceid, "roster": roster_list})
    return {"ok": True, "roster": roster_list, "reset_scores": had_scores}


@app.post("/api/competition-events/{ceid}/close")
async def api_close(ceid: int, request: Request = None):
    require_admin(request)
    ev, comp = _require_active_event(ceid)
    db.get_db().execute("UPDATE events SET status='pending' WHERE id=?", (ceid,))
    db.get_db().commit()
    sse.bus.publish(comp["id"], "competition_event_closed", {"event_id": ceid})
    return {"ok": True}


@app.get("/api/competition-events/{ceid}/progress")
async def api_progress(ceid: int, request: Request = None):
    require_admin(request)
    ev = _event_or_404(ceid)
    roster_list = roster(ceid)
    dances = dances_of(ceid)
    jcodes = judges_of(ev["competition_id"])
    conn = db.get_db()
    matrix = {}
    for j in jcodes:
        per_dance = {}
        for d in dances:
            got = conn.execute(
                "SELECT competitor_number FROM score_records WHERE event_id=? AND judge_code=? AND dance_name=?",
                (ceid, j, d)).fetchall()
            per_dance[d] = sorted({r["competitor_number"] for r in got} & set(roster_list))
        matrix[j] = per_dance
    complete = is_complete(ev, roster_list, dances, jcodes)
    return {"roster": roster_list, "dances": dances, "judges": jcodes, "matrix": matrix,
            "complete": complete, "status": ev["status"]}


@app.post("/api/competition-events/{ceid}/calculate")
async def api_calculate(ceid: int, request: Request = None):
    require_admin(request)
    ev, comp = _require_active_event(ceid)
    try:
        data = calculate_event(ev)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sse.bus.publish(comp["id"], "calculation_done", {"event_id": ceid})
    return {"ok": True, "results": data}


def _auto_calculate_if_ready(ev, comp):
    if ev["status"] != "scoring":
        return False
    if not is_complete(ev, roster(ev["id"]), dances_of(ev["id"]), judges_of(comp["id"])):
        return False
    try:
        calculate_event(ev)
    except ValueError:
        return False
    sse.bus.publish(comp["id"], "calculation_done", {"event_id": ev["id"], "auto": True})
    return True


@app.get("/api/competition-events/{ceid}/results")
async def api_results(ceid: int, request: Request = None, type: str = "overall"):
    s = _session(request)
    if not s or s["role"] != "admin":
        raise HTTPException(status_code=401, detail="结果查询仅限管理端")
    _event_or_404(ceid)
    data = load_results(ceid)
    if not data:
        raise HTTPException(status_code=404, detail="尚未计算")
    if type == "detail":
        return {"type": "detail", "data": data}
    return {"type": type, "data": data}


@app.post("/api/competition-events/{ceid}/publish")
async def api_publish(ceid: int, request: Request = None):
    require_admin(request)
    ev, comp = _require_active_event(ceid)
    if ev["status"] != "calculated":
        raise HTTPException(status_code=400, detail="请先完成计算")
    conn = db.get_db()
    conn.execute("UPDATE events SET published=1, status='published' WHERE id=?", (ceid,))
    conn.commit()
    sse.bus.publish(comp["id"], "results_published", {"event_id": ceid})
    return {"ok": True}


@app.post("/api/competition-events/{ceid}/unpublish")
async def api_unpublish(ceid: int, request: Request = None):
    require_admin(request)
    ev, comp = _require_active_event(ceid)
    db.get_db().execute("UPDATE events SET published=0, status='calculated' WHERE id=?", (ceid,))
    db.get_db().commit()
    sse.bus.publish(comp["id"], "results_unpublished", {"event_id": ceid})
    return {"ok": True}


# ------------------------------------------------------------------ judge API
@app.get("/api/judge/me/assignments")
async def api_assignments(request: Request = None):
    s = require_judge(request)
    comp = _active_competition()
    out = []
    if comp:
        for ev in db.rows(db.get_db().execute(
                "SELECT * FROM events WHERE competition_id=? AND status='scoring' ORDER BY code", (comp["id"],))):
            out.append({"event": ev, "dances": dances_of(ev["id"]),
                        "sheet_status": _judge_sheet_status(ev["id"], s["judge_code"])})
    return {"competition": comp, "assignments": out}


@app.get("/api/judge/competition-events/{ceid}/dances/{dance}/sheet")
async def api_sheet(ceid: int, dance: str, request: Request = None):
    s = require_judge(request)
    ev = _event_or_404(ceid)
    if ev["status"] != "scoring":
        raise HTTPException(status_code=400, detail="场次未在评分中")
    roster_list = roster(ceid)
    skating = scoring_type_of(ev) == ScoringType.SKATING
    marks = {}
    for num in roster_list:
        row = db.rowdict(db.get_db().execute(
            "SELECT placement, mark FROM score_records WHERE event_id=? AND judge_code=? AND dance_name=? AND competitor_number=?",
            (ceid, s["judge_code"], dance, num)).fetchone())
        marks[num] = (row or {}).get("placement" if skating else "mark")
    return {"dance": dance, "roster": roster_list, "skating": skating, "values": marks}



def _sheet_mark_value(kind, v):
    if kind == "mark":
        return 1 if v else 0
    if kind == "score":
        return float(v)
    return None


def _sheet_placement_value(kind, v):
    return int(v) if kind == "skating" else None


@app.put("/api/judge/competition-events/{ceid}/dances/{dance}/sheet")
async def api_submit_sheet(ceid: int, dance: str, request: Request = None):
    s = require_judge(request)
    ev, comp = _require_active_event(ceid)
    if ev["status"] != "scoring":
        raise HTTPException(status_code=400, detail="场次已关闭评分")
    body = await request.json()
    roster_list = set(roster(ceid))
    values = body.get("values") or {}
    kind = scoring_kind(ev)
    skating = kind == "skating"

    # 服务端复验（不信任客户端）
    if kind == "score":
        if set(values.keys()) != roster_list:
            raise HTTPException(status_code=400, detail="必须为全部上场队伍提交评分")
        for v in values.values():
            try:
                fv = float(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="评分必须为 0~10 的数值")
            if not (0 <= fv <= 10) or round(fv, 1) != fv:
                raise HTTPException(status_code=400, detail="评分须为 0~10 且最多一位小数")
    elif skating:
        if set(values.keys()) != roster_list:
            raise HTTPException(status_code=400, detail="必须为全部上场选手提交名次")
        placements = []
        for num, v in values.items():
            try:
                p = int(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="名次必须为 1~N 的整数")
            if not (1 <= p <= len(roster_list)):
                raise HTTPException(status_code=400, detail="名次超出范围 1~N")
            placements.append(p)
        if len(set(placements)) != len(roster_list):
            raise HTTPException(status_code=400, detail="名次必须为 1~N 且互不重复")
    else:
        if set(values.keys()) != roster_list:
            raise HTTPException(status_code=400, detail="必须为全部上场选手提交标记")
        for v in values.values():
            if not isinstance(v, bool):
                raise HTTPException(status_code=400, detail="Mark制为布尔标记（true/false）")

    conn = db.get_db()
    for num, v in values.items():
        conn.execute(
            "INSERT INTO score_records(event_id, judge_code, competitor_number, dance_name, mark, placement) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(event_id, dance_name, judge_code, competitor_number) "
            "DO UPDATE SET mark=excluded.mark, placement=excluded.placement, timestamp=datetime('now','localtime')",
            (ceid, s["judge_code"], str(num), dance,
             _sheet_mark_value(kind, v),
             _sheet_placement_value(kind, v)))
    conn.commit()
    sse.bus.publish(comp["id"], "score_submitted",
                    {"event_id": ceid, "dance": dance, "judge": s["judge_code"]})
    auto = _auto_calculate_if_ready(_event_or_404(ceid), comp)
    return {"ok": True, "auto_calculated": auto}


# ------------------------------------------------------------------ advancement
@app.get("/api/projects/{project_code}/rounds/{round_no}/advancement-proposal")
async def api_proposal(project_code: str, round_no: int, request: Request = None, competition_id: int = None):
    require_admin(request)
    comp = _active_competition()
    cid = competition_id or (comp or {}).get("id")
    if not cid:
        raise HTTPException(status_code=400, detail="无激活赛事")
    return {"proposal": advancement_proposal(cid, project_code, round_no)}


@app.post("/api/projects/{project_code}/rounds/{round_no}/advancement-confirm")
async def api_confirm(project_code: str, round_no: int, request: Request = None):
    require_admin(request)
    comp = _active_competition()
    if not comp:
        raise HTTPException(status_code=400, detail="无激活赛事")
    body = await request.json()
    advancing = body.get("advancing") or []
    if not advancing:
        raise HTTPException(status_code=400, detail="晋级名单为空")
    filled = confirm_advancement(comp["id"], project_code, round_no, advancing)
    sse.bus.publish(comp["id"], "schedule_changed", {"filled": filled})
    return {"ok": True, "filled": filled}


# ------------------------------------------------- team standings (M6/D12/D13)
def _team_standings(competition_id, published_only):
    """按单位聚合团体总分：双人=主报单位（D13），集体=队伍单位（competitors.unit）。
    published_only=True 仅统计已发布场次（公开口径）；False 统计全部已计算（管理预览）。"""
    conn = db.get_db()
    _comp_or_404(competition_id)
    q = "SELECT * FROM events WHERE competition_id=? AND status IN ('calculated','published')"
    if published_only:
        q += " AND published=1"
    events = db.rows(conn.execute(q + " ORDER BY project_code, round, code", (competition_id,)))
    unit_by_number = {c["number"]: (c["unit"] or "") for c in db.rows(conn.execute(
        "SELECT number, unit FROM competitors WHERE competition_id=?", (competition_id,)))}
    # 口径（用户拍板 2026-08-29）：团体总分只统计每个项目的「最末轮」——
    # 该项目有结果的轮次中轮号最大者（初赛名次不计，仅最终名次赋分）。
    with_results = []
    last_round = {}
    for ev in events:
        data = load_results(ev["id"])
        if data and (data.get("overall_results") or data.get("dance_results")):
            with_results.append((ev, data))
            pr = ev["project_code"]
            if pr not in last_round or ev["round"] > last_round[pr]:
                last_round[pr] = ev["round"]
    entries = []
    for ev, data in with_results:
        if ev["round"] != last_round[ev["project_code"]]:
            continue
        for r in data.get("overall_results") or []:
            num = str(r["competitor_number"])
            entries.append({"project": ev["project_code"], "number": num,
                            "unit": unit_by_number.get(num, ""), "rank": r["rank"]})
    from core.team_standing import compute_team_standings
    return compute_team_standings(entries)


@app.get("/api/events/{competition_id}/team-standings")
async def api_team_standings_admin(competition_id: int, request: Request = None):
    require_admin(request)
    return _team_standings(competition_id, published_only=False)


# ------------------------------------------------------------------ public API
def _public_payload():
    comp = _active_competition()
    if not comp:
        return None
    events = db.rows(db.get_db().execute(
        "SELECT code,name,project_code,round,status,published,id FROM events WHERE competition_id=? ORDER BY project_code, round, code",
        (comp["id"],)))
    published = []
    for ev in events:
        if ev["published"]:
            res = load_results(ev["id"])
            if res:
                published.append({"code": ev["code"], "name": ev["name"], "project": ev["project_code"],
                                  "round": ev["round"], "results": res["overall_results"]})
    return {"competition": {k: comp[k] for k in ("id", "name", "date", "location")},
            "events": events, "published_results": published,
            "team_standings": _team_standings(comp["id"], published_only=True)}


@app.get("/api/public/events/{competition_id}/schedule")
async def api_public_schedule(competition_id: int):
    comp = _comp_or_404(competition_id)
    events = db.rows(db.get_db().execute(
        "SELECT id, code,name,project_code,round,status FROM events WHERE competition_id=? ORDER BY project_code, round, code",
        (competition_id,)))
    return {"competition": comp, "events": events}


@app.get("/api/public/events/{competition_id}/results")
async def api_public_results(competition_id: int, request: Request = None, scope: str = "published"):
    _comp_or_404(competition_id)
    # scope 参数保留（v0.2.3 正文单态：仅 published）；明细不对公开端暴露（D5）
    comp = _active_competition()
    out = []
    if comp and comp["id"] == competition_id:
        for ev in db.rows(db.get_db().execute(
                "SELECT * FROM events WHERE competition_id=? AND published=1", (competition_id,))):
            res = load_results(ev["id"])
            if res:
                out.append({"code": ev["code"], "name": ev["name"], "round": ev["round"],
                            "overall": res["overall_results"]})
    return {"results": out}


@app.get("/api/public/events/{competition_id}/team-standings")
async def api_team_standings_public(competition_id: int):
    _comp_or_404(competition_id)
    return _team_standings(competition_id, published_only=True)


@app.get("/api/public/events/{competition_id}/screen-state")
async def api_screen_state(competition_id: int):
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    scoring = db.rows(conn.execute(
        "SELECT code,name,project_code,round FROM events WHERE competition_id=? AND status='scoring'",
        (competition_id,)))
    payload = _public_payload() or {"published_results": [], "events": []}
    return {"competition": payload["competition"], "scoring_now": scoring,
            "published_results": payload["published_results"],
            "team_standings": _team_standings(comp["id"], published_only=True),
            "updated_at": int(time.time())}


# ------------------------------------------------------------------ SSE
@app.get("/api/events/{competition_id}/stream")
async def api_stream(competition_id: int, request: Request = None):
    _comp_or_404(competition_id)
    q = sse.bus.subscribe(competition_id)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_type, data = await asyncio.wait_for(q.get(), timeout=15)
                    yield "event: {0}\ndata: {1}\n\n".format(event_type, data)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            sse.unsubscribe(competition_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ exports & backup
@app.get("/api/events/{competition_id}/exports")
async def api_export(competition_id: int, request: Request = None, format: str = "markdown"):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    evs = db.rows(db.get_db().execute(
        "SELECT * FROM events WHERE competition_id=? AND published=1 ORDER BY project_code, round, code",
        (competition_id,)))
    if format == "markdown":
        lines = ["# {0} 成绩".format(comp["name"]), ""]
        for ev in evs:
            res = load_results(ev["id"])
            if not res:
                continue
            lines.append("## {0}（{1} 第{2}轮）".format(ev["name"], ev["project_code"], ev["round"]))
            lines.append("| 名次 | 背番号 | 总分 |")
            lines.append("|---|---|---|")
            for r in res["overall_results"]:
                lines.append("| {0} | {1} | {2} |".format(r["rank"], r["competitor_number"], r["total_score"]))
            lines.append("")
        return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8")
    elif format == "html":
        rows_html = []
        for ev in evs:
            res = load_results(ev["id"])
            if not res:
                continue
            body = "".join("<tr><td>{0}</td><td>{1}</td><td>{2}</td></tr>".format(
                r["rank"], r["competitor_number"], r["total_score"]) for r in res["overall_results"])
            rows_html.append("<h2>{0}（{1} 第{2}轮）</h2><table><tr><th>名次</th><th>背番号</th><th>总分</th></tr>{3}</table>".format(
                ev["name"], ev["project_code"], ev["round"], body))
        css = ("body{font-family:sans-serif;margin:2em}"
               "table{border-collapse:collapse}td,th{border:1px solid #999;padding:4px 12px}")
        html = ("<!doctype html><html><head><meta charset='utf-8'><title>" + comp["name"] + " 成绩</title>"
                "<style>" + css + "</style>"
                "</head><body><h1>" + comp["name"] + " 成绩</h1>" + "".join(rows_html) + "</body></html>")
        return HTMLResponse(html)
    raise HTTPException(status_code=400, detail="未知格式")


@app.post("/api/backup")
async def api_backup(request: Request = None):
    require_admin(request)
    import shutil
    src = db.DEFAULT_DB
    dst = src + ".backup-{0}".format(time.strftime("%Y%m%d%H%M%S"))
    conn = db.get_db()
    conn.execute("PRAGMA wal_checkpoint(FULL)")
    shutil.copy2(src, dst)
    return {"ok": True, "path": dst}


# ------------------------------------------------------------------ startup
@app.on_event("startup")
async def _startup():
    db.init_db()
