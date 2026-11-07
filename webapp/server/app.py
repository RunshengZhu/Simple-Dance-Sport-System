#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""体育舞蹈赛事评分系统 · 服务版（M1~M5）。FastAPI + Jinja2 + SQLite WAL + SSE，端口 8321。"""

import asyncio
import csv
import io
import json
import hashlib
import hmac
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import urllib.parse
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import ScoringType
from core.data_models import ScoringType as ST

from server import db, sse
from server.scoring_service import (
    calculate_event, load_results, roster, dances_of, judges_of, is_complete,
    advancement_proposal, confirm_advancement, scoring_type_of, scoring_kind,
    checked_roster,
)

ADMIN_PASSWORD = os.environ.get("DSPORT_ADMIN_PASSWORD", "admin123")
SCREEN_CONTROL = {"mode": "auto", "comp_id": None}   # 大屏强制模式（v1 内存态，重启归 auto）
PORT = int(os.environ.get("DSPORT_PORT", "8321"))
BASE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="体育舞蹈赛事评分系统 · 服务版", docs_url=None, redoc_url=None)


def _visit_slug(path: str):
    """R53 访问统计桶：把 HTML 页面路径归到工具级 slug；非页面/资源返回 None 不计数。"""
    if path == "/":
        return "portal"
    if path == "/login" or path == "/events" or path.startswith("/events/"):
        return "scoring"
    if path == "/judge" or path.startswith("/judge/"):
        return "scoring"
    if path in ("/staff", "/users"):
        return "scoring"
    if path == "/public" or path.startswith("/public/"):
        return "public"
    if path == "/screen":
        return "screen"
    if path == "/manual":
        return "manual"
    if path == "/competitions":
        return "competitions"
    if path == "/apps":
        return "apps"
    if path.startswith("/apps/"):
        rest = path[len("/apps/"):].strip("/")
        if rest and "/" not in rest:
            return "app:" + rest
    return None


def _parse_rate(s: str, default):
    """'N/窗口秒' → (N, 秒)；解析失败用默认。"""
    try:
        n, w = s.split("/")
        return (max(1, int(n)), max(1, int(w)))
    except Exception:
        return default


RATE_GENERAL = _parse_rate(os.environ.get("DSPORT_RATE_GENERAL", ""), (300, 10))   # 常规页面/接口
RATE_LOGIN = _parse_rate(os.environ.get("DSPORT_RATE_LOGIN", ""), (10, 60))        # 登录防爆破
MAX_BODY = int(os.environ.get("DSPORT_MAX_BODY", str(220 * 1024 * 1024)))          # 上传保护
_RATE: dict = {}   # (slot, window_start) -> count（内存态，单 worker；重启即清零）


def _compadmin(request: Request):
    """R54 赛事管理员：会话角色为 admin 且绑定 users.role='compadmin' 的账号。
    返回账号行（含 comp_id）；非赛事管理员返回 None。总管理员（环境口令）不建账号、永不受限。"""
    s = _session(request)
    if not s or not s.get("user_id"):
        return None
    u = db.rowdict(db.get_db().execute(
        "SELECT * FROM users WHERE id=? AND role='compadmin' AND active=1", (s["user_id"],)).fetchone())
    return u or None


_COMPCID_RE = re.compile(r"^/(api/)?events/(\d+)")
_COMPCID_DENY_PREFIXES = ("/api/users", "/api/import/json", "/api/import/db",
                          "/api/export/json", "/api/export/db")


@app.middleware("http")
async def compadmin_scope(request: Request, call_next):
    """R54 赛事管理员作用域中间件：全局能力拒绝；带 competition_id 的路径仅放行自己的赛事；
    /events 列表页与 /users、/files 页重定向到自己的赛程编排页。"""
    ca = _compadmin(request)
    if not ca:
        return await call_next(request)
    cid = ca["comp_id"]
    p = request.url.path
    method = request.method

    def deny(msg="赛事管理员无此权限"):
        if p.startswith("/api"):
            return JSONResponse({"detail": msg}, status_code=403)
        return PlainTextResponse(msg, status_code=403)

    if p.rstrip("/") in ("/events", "/users", "/files"):
        return RedirectResponse(f"/events/{cid}/schedule", status_code=302)
    if p == "/api/users" and method in ("GET", "POST"):
        pass  # R56 筹备向导：赛事管理员可创建/查看工作人员（host/marshal），handler 内钳制角色
    elif p.startswith(_COMPCID_DENY_PREFIXES):
        return deny("赛事管理员不可执行全局操作")
    if p == "/api/events" and method == "POST":
        return deny("赛事管理员不可创建赛事")
    if p == "/api/screen-control" and method == "POST":
        return deny("赛事管理员不可修改全局大屏设置")
    m = _COMPCID_RE.match(p)
    if m and int(m.group(2)) != cid:
        return deny("赛事管理员仅可操作自己的赛事")
    return await call_next(request)


@app.middleware("http")
async def guard(request: Request, call_next):
    """R53 基础防护：请求体大小上限 + 按 IP 固定窗口限速（常规 / 登录两档）+ 429。
    无 client 信息（测试直连/内部调用）不参与限速。"""
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY:
        return JSONResponse({"detail": "请求体过大"}, status_code=413)
    cli = request.client
    # 环回豁免：本机健康检查/测试不走限速（DDoS 只可能来自外部，TCP 源无法伪装环回）
    if cli is None or not cli.host or cli.host in ("127.0.0.1", "::1", "testclient"):
        return await call_next(request)
    is_login = request.method == "POST" and request.url.path == "/api/login"
    n, w = RATE_LOGIN if is_login else RATE_GENERAL
    now = int(time.time())
    key = (("L" if is_login else "G") + cli.host, now // w)
    cnt = _RATE.get(key, 0) + 1
    _RATE[key] = cnt
    if len(_RATE) > 20000:          # 防膨胀：直接重置（窗口粒度，影响可忽略）
        _RATE.clear()
        _RATE[key] = cnt
    if cnt > n:
        retry = w - (now % w)
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "请求过于频繁，请稍后再试"}, status_code=429,
                                headers={"Retry-After": str(retry)})
        return PlainTextResponse("请求过于频繁，请稍后再试", status_code=429,
                                 headers={"Retry-After": str(retry)})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """R53 基础安全响应头（HTTPS 就绪后再补 HSTS）。
    R54b：HTML 页面一律 no-cache——登录页等模板更新后浏览器不得使用旧缓存。"""
    resp = await call_next(request)
    if resp.headers.get("content-type", "").startswith("text/html"):
        resp.headers["Cache-Control"] = "no-cache"
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


@app.middleware("http")
async def visit_count(request: Request, call_next):
    """R53 访问统计：GET 且 200 且 text/html 的页面按工具桶计一次（接口/静态/下载不计）。"""
    resp = await call_next(request)
    try:
        if request.method == "GET" and resp.status_code == 200                 and resp.headers.get("content-type", "").startswith("text/html"):
            slug = _visit_slug(request.url.path)
            if slug:
                conn = db.get_db()
                conn.execute(
                    "INSERT INTO visit_stats(slug, day, n) VALUES(?, ?, 1) "
                    "ON CONFLICT(slug, day) DO UPDATE SET n = n + 1",
                    (slug, time.strftime("%Y-%m-%d")))
                conn.commit()
    except Exception:
        pass
    return resp


@app.middleware("http")
async def static_cache_control(request: Request, call_next):
    """静态资源长缓存（R41 压测：300 并发观众突发首访资源级联 P95 14.7s，
    根因是 softReload 周期对 /static 的重复条件请求挤占单 worker 事件循环）。
    静态引用均带 ?v= 版本参数，改版即换 URL，长缓存安全。"""
    resp = await call_next(request)
    if request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1024)   # R70：公开 JSON/HTML 压缩（观众流量大头）
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))


# ------------------------------------------------------------------ auth
def _session(request: Request):
    token = request.cookies.get("session")
    if not token:
        return None
    s = db.rowdict(db.get_db().execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone())
    if not s:
        return None
    # 员工角色（host/marshal）只接受账号制会话：迁移前的无 user_id 会话一律失效
    if s["role"] in ("host", "marshal") and not s.get("user_id"):
        return None
    if s.get("user_id"):
        # 账号制会话：联查账号，停用即失效
        u = db.rowdict(db.get_db().execute(
            "SELECT username, display_name, active FROM users WHERE id=?", (s["user_id"],)).fetchone())
        if not u or not u["active"]:
            return None
        s["username"] = u["username"]
        s["display_name"] = u["display_name"] or u["username"]
    return s


def require_admin(request: Request):
    s = _session(request)
    if not s or s["role"] != "admin":
        raise HTTPException(status_code=401, detail="需要管理员登录")
    return s




@app.exception_handler(HTTPException)
async def html_auth_redirect(request: Request, exc: HTTPException):
    """页面路由的登录/权限异常改为跳转登录页（API 路由维持 JSON），避免用户看到裸错误。"""
    if not request.url.path.startswith("/api/") and exc.status_code in (401, 403):
        return RedirectResponse("/login", status_code=302)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def require_judge(request: Request):
    s = _session(request)
    if not s or s["role"] != "judge":
        raise HTTPException(status_code=401, detail="需要裁判登录")
    return s


def require_staff(request: Request, competition_id: int = None):
    """主持人 / 检录长·检录员 共用权限（检录与播报台）。
    R57：绑定本赛事的赛事管理员亦可担任检录/播报（小型赛事一人多角）。"""
    s = _session(request)
    if s and s["role"] == "admin":
        ca = _compadmin(request)
        if ca and (competition_id is None or ca["comp_id"] == competition_id):
            return s
    if not s or s["role"] not in ("host", "marshal"):
        raise HTTPException(status_code=401, detail="需要主持人或检录员登录")
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
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体须为 JSON")
    role = body.get("role")
    ip = request.client.host if request.client else "?"
    if login_blocked(ip):
        raise HTTPException(status_code=429, detail="失败次数过多，请稍后再试")
    token = secrets.token_urlsafe(32)
    conn = db.get_db()
    bind_cid = body.get("competition_id")
    if bind_cid is not None:
        try:
            bind_cid = int(bind_cid)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="competition_id 须为整数")

    if role == "admin":
        demo_username = str(body.get("username") or "").strip()
        password = str(body.get("password") or "")
        if demo_username:
            # R54 赛事管理员：账号制登录；会话角色记 admin（页面通行），
            # 能力由 compadmin_scope 中间件按 users.comp_id 钳制。总管理员走环境口令、不建账号。
            urow = db.rowdict(conn.execute(
                "SELECT * FROM users WHERE username=? AND role='compadmin'", (demo_username,)).fetchone())
            if not urow or not _verify_pw(password, urow["pw_hash"]):
                _hash_pw(password)
                login_failures_window(ip).append(time.time())
                raise HTTPException(status_code=403, detail="用户名或口令错误")
            if not urow["active"]:
                login_failures_window(ip).append(time.time())
                raise HTTPException(status_code=403, detail="用户名或口令错误")
            if bind_cid is not None and urow["comp_id"] != bind_cid:
                raise HTTPException(status_code=403, detail="该赛事管理员不属于此赛事")
            conn.execute("INSERT INTO sessions(token, role, user_id, comp_id) VALUES(?, 'admin', ?, ?)",
                         (token, urow["id"], urow["comp_id"]))
        else:
            if body.get("password") != ADMIN_PASSWORD:
                login_failures_window(ip).append(time.time())
                raise HTTPException(status_code=403, detail="口令错误")
            conn.execute("INSERT INTO sessions(token, role) VALUES(?, 'admin')", (token,))
    elif role in ("host", "marshal"):
        # 分角色账号制：用户名 + 口令，账号由管理员在「用户管理」页创建/停用
        username = str(body.get("username") or "").strip() or role   # 留空 = 默认账号（host/marshal）
        password = str(body.get("password") or "")
        urow = db.rowdict(conn.execute(
            "SELECT * FROM users WHERE username=? AND role=?", (username, role)).fetchone())
        if not urow or not _verify_pw(password, urow["pw_hash"]):
            _hash_pw(password)   # 时序抹平：不存在的用户名也执行一次等价哈希
            login_failures_window(ip).append(time.time())
            raise HTTPException(status_code=403, detail="用户名或口令错误")
        if not urow["active"]:
            login_failures_window(ip).append(time.time())
            raise HTTPException(status_code=403, detail="用户名或口令错误")
        conn.execute("INSERT INTO sessions(token, role, user_id, comp_id) VALUES(?,?,?,?)",
                     (token, role, urow["id"], bind_cid))
    elif role == "judge":
        code = str(body.get("judge_id") or "")
        row = conn.execute("SELECT * FROM judges WHERE code=? ", (code,)).fetchone()
        # 需限定赛事：任一赛事存在该裁判即可（单激活赛事语义）
        if not row:
            login_failures_window(ip).append(time.time())
            raise HTTPException(status_code=403, detail="裁判 ID 不存在")
        if bind_cid is not None:
            # R55 赛事专属登录：裁判必须属于所登录的赛事
            member = conn.execute("SELECT 1 FROM judges WHERE competition_id=? AND code=?",
                                  (bind_cid, code)).fetchone()
            if not member:
                raise HTTPException(status_code=403, detail="该裁判不属于此赛事")
        conn.execute("INSERT INTO sessions(token, role, judge_code, comp_id) VALUES(?, 'judge', ?, ?)",
                     (token, code, bind_cid))
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
    """兜底：最新激活赛事（仅管理端兜底用；公开页请走 _viewer_competition）。"""
    return db.rowdict(db.get_db().execute("SELECT * FROM competitions WHERE active=1 ORDER BY id DESC").fetchone())


def _viewer_competition(request: Request):
    """R71e 公开页赛事解析（用户拍板：无默认入口概念，观众自选赛事）——
    ?comp=ID 显式指定优先；无参数且仅一个激活赛事时用之；多个激活且未指定 → None（路由重定向列表）。
    演示赛/压测赛 active=0 对观众隐藏，不出现在候选。"""
    try:
        qid = int(request.query_params.get("comp", "") or 0)
    except (TypeError, ValueError):
        qid = 0
    if qid:
        return db.rowdict(db.get_db().execute(
            "SELECT * FROM competitions WHERE id=? AND active=1", (qid,)).fetchone())
    actives = db.rows(db.get_db().execute(
        "SELECT * FROM competitions WHERE active=1 ORDER BY id DESC"))
    if len(actives) == 1:
        return actives[0]
    return None


def _current_competition(request: Request):
    """R49 多赛事模型：管理员按会话切换赛事；未选择时回落全局激活赛事。"""
    s = _session(request)
    if s and s.get("comp_id"):
        c = db.rowdict(db.get_db().execute(
            "SELECT * FROM competitions WHERE id=?", (s["comp_id"],)).fetchone())
        if c:
            return c
    return _active_competition()


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
    """R55b 工具箱门户：/ 恒为工具箱首页（备案名「体育舞蹈工具箱」落地面）。
    R56c：登录用户不再被重定向——左上角品牌点击必须能回到首页；
    门户页首为已登录角色提供「我的工作台」链接防迷路。"""
    conn = db.get_db()
    stats = {r["slug"]: r["n"] for r in db.rows(
        conn.execute("SELECT slug, SUM(n) AS n FROM visit_stats GROUP BY slug"))}
    player_dl = conn.execute(
        "SELECT COALESCE(SUM(f.downloads), 0) AS d FROM file_objects f "
        "JOIN file_tiers t ON t.id = f.tier_id WHERE t.name = 'party-player'").fetchone()["d"]
    s = _session(request)
    role_home = {("judge"): ("/judge", "我的评分台"),
                 ("marshal"): ("/staff", "检录台"),
                 ("host"): ("/staff", "主持台"),
                 ("admin"): ("/events", "赛事管理")}.get(s["role"]) if s else None
    return templates.TemplateResponse(request, "portal.html", {
        "request": request, "stats": stats, "player_dl": player_dl,
        "role_home": role_home})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """R55：/login 不再服务评分系统——只保留总管理员登录页；
    裁判旧书签（/login?role=judge&judge=J1）302 到其所属赛事的专属登录页；
    其余情况跳公开赛事列表。"""
    q = request.query_params
    if q.get("role") == "judge":
        code = (q.get("judge") or "").strip()
        if code:
            conn = db.get_db()
            rows = db.rows(conn.execute(
                "SELECT j.competition_id, c.active FROM judges j "
                "JOIN competitions c ON c.id=j.competition_id "
                "WHERE j.code=? AND c.active=1 ORDER BY j.competition_id DESC", (code,)))
            if rows:
                return RedirectResponse(
                    f"/competitions/{rows[0]['competition_id']}/login?role=judge&judge={urllib.parse.quote(code)}",
                    status_code=302)
        return RedirectResponse("/competitions", status_code=302)
    if q.get("role"):
        return RedirectResponse("/competitions", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"request": request})


# ---- R55 公开赛事中心 ----
@app.put("/api/competitions/{competition_id}")
async def api_competition_update(competition_id: int, request: Request = None):
    """R58 赛事信息编辑：名称/日期/地点。总管理员或绑定本赛事的赛事管理员。"""
    require_admin(request)
    ca = _compadmin(request)
    if ca and ca["comp_id"] != competition_id:
        raise HTTPException(status_code=403, detail="赛事管理员仅可编辑自己的赛事")
    comp = _comp_or_404(competition_id)
    body = await request.json()
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="赛事名称必填")
    if len(name) > 120:
        raise HTTPException(status_code=400, detail="赛事名称过长")
    date = str(body.get("date") or "").strip()[:10]
    location = str(body.get("location") or "").strip()[:120]
    conn = db.get_db()
    conn.execute("UPDATE competitions SET name=?, date=?, location=? WHERE id=?",
                 (name, date, location, competition_id))
    conn.commit()
    return {"ok": True}


@app.get("/competitions", response_class=HTMLResponse)
async def competitions_page(request: Request):
    """公开赛事列表：卡片展示全部激活中的赛事。"""
    conn = db.get_db()
    comps = db.rows(conn.execute(
        "SELECT id, name, date, location FROM competitions WHERE active=1 ORDER BY id DESC"))
    cards = []
    for c in comps:
        evs = db.rows(conn.execute(
            "SELECT status, published FROM events WHERE competition_id=?", (c["id"],)))
        cards.append({**c, "n_events": len(evs),
                      "n_published": sum(1 for e in evs if e["published"]),
                      "n_scoring": sum(1 for e in evs if e["status"] == "scoring")})
    return templates.TemplateResponse(request, "competitions.html", {
        "request": request, "cards": cards})


@app.get("/competitions/{competition_id}", response_class=HTMLResponse)
async def competition_home(request: Request, competition_id: int):
    """赛事专属首页：公开详情（赛程/成绩公告/团体总分）+ 各角色登录入口。
    仅展示激活中的赛事。"""
    conn = db.get_db()
    comp = db.rowdict(conn.execute(
        "SELECT * FROM competitions WHERE id=? AND active=1", (competition_id,)).fetchone())
    if not comp:
        raise HTTPException(status_code=404, detail="赛事尚未开放（未激活或不存在）")
    payload = _public_payload(comp) or {"events": [], "published_results": [],
                                        "team_standings": {"standings": []}}
    ca = _compadmin(request)
    return templates.TemplateResponse(request, "competition_home.html", {
        "request": request, "comp": comp, "events": payload["events"],
        "published": payload["published_results"],
        "standings": payload["team_standings"].get("standings", []),
        "is_comp_admin": bool(ca and ca["comp_id"] == competition_id)})


@app.get("/events/{competition_id}/setup", response_class=HTMLResponse)
async def setup_wizard_page(request: Request, competition_id: int):
    """R56 筹备向导：赛事管理员建赛后的多步引导。筹备完成后访问自动跳赛程编排。"""
    s = require_admin(request)
    comp = _comp_or_404(competition_id)
    ca = _compadmin(request)
    if ca and ca["comp_id"] != competition_id:
        raise HTTPException(status_code=403, detail="赛事管理员仅可操作自己的赛事")
    if comp["setup_done"]:
        return RedirectResponse(f"/events/{competition_id}/schedule", status_code=302)
    return templates.TemplateResponse(request, "setup.html", {"request": request, "comp": comp})


@app.get("/api/events/{competition_id}/setup/status")
async def api_setup_status(competition_id: int, request: Request = None):
    """筹备向导状态：各步骤当前数量。"""
    require_admin(request)
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    staff = db.rows(conn.execute(
        "SELECT username, display_name, role FROM users WHERE role IN ('host','marshal') ORDER BY role, username"))
    evs = db.rows(conn.execute(
        "SELECT status, published FROM events WHERE competition_id=?", (competition_id,)))
    first_ev = db.rowdict(conn.execute(
        "SELECT id, code FROM events WHERE competition_id=? AND status IN ('pending','scoring') "
        "ORDER BY run_seq IS NULL, run_seq, code LIMIT 1", (competition_id,)))
    return {
        "competitors": conn.execute(
            "SELECT COUNT(*) c FROM competitors WHERE competition_id=?", (competition_id,)).fetchone()["c"],
        "judges": conn.execute(
            "SELECT COUNT(*) c FROM judges WHERE competition_id=?", (competition_id,)).fetchone()["c"],
        "events": len(evs),
        "events_published": sum(1 for e in evs if e["published"]),
        "staff": staff,
        "setup_done": bool(comp["setup_done"]),
        "auto_publish": bool(comp["auto_publish"]),
        "first_event": first_ev,
    }


@app.post("/events/{competition_id}/setup/complete")
async def setup_complete(competition_id: int, request: Request = None):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    ca = _compadmin(request)
    if ca and ca["comp_id"] != competition_id:
        raise HTTPException(status_code=403, detail="赛事管理员仅可操作自己的赛事")
    db.get_db().execute("UPDATE competitions SET setup_done=1 WHERE id=?", (competition_id,))
    db.get_db().commit()
    return {"ok": True}


@app.get("/competitions/{competition_id}/login", response_class=HTMLResponse)
async def competition_login_page(request: Request, competition_id: int):
    """赛事专属登录页：登录成功即把会话绑定到本赛事（sessions.comp_id）。"""
    conn = db.get_db()
    comp = db.rowdict(conn.execute(
        "SELECT id, name FROM competitions WHERE id=? AND active=1", (competition_id,)).fetchone())
    if not comp:
        raise HTTPException(status_code=404, detail="赛事尚未开放（未激活或不存在）")
    q = request.query_params
    return templates.TemplateResponse(request, "competition_login.html", {
        "request": request, "comp": comp,
        "role": q.get("role") or "", "judge": q.get("judge") or ""})


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
    conn = db.get_db()
    events = db.rows(conn.execute(
        "SELECT * FROM events WHERE competition_id=? ORDER BY project_code, round, code", (competition_id,)))
    tree = {}
    for ev in events:
        dances = [r["name"] for r in db.rows(conn.execute(
            "SELECT name FROM event_dances WHERE event_id=? ORDER BY ord", (ev["id"],)))]
        n = conn.execute("SELECT COUNT(*) c FROM event_competitors WHERE event_id=?", (ev["id"],)).fetchone()["c"]
        tree.setdefault(ev["project_code"], {"rounds": {}})
        rr = tree[ev["project_code"]]["rounds"].setdefault(ev["round"], [])
        rr.append({"id": ev["id"], "code": ev["code"], "name": ev["name"], "round": ev["round"],
                   "dances": dances, "scoring_type": ev["scoring_type"],
                   "advancement_count": ev["advancement_count"], "status": ev["status"],
                   "published": ev["published"], "run_seq": ev["run_seq"],
                   "roster": [str(x) for x in range(n)] or [], "roster_n": n})
    # 序列化友好的结构：{proj: [{round, count, all_done, events:[...]}]}
    tree2 = {}
    for proj, info in tree.items():
        lst = []
        for rnd in sorted(info["rounds"]):
            evs = info["rounds"][rnd]
            for e in evs:
                e["roster"] = []
            all_done = all(e["status"] in ("calculated", "published") for e in evs)
            lst.append({"round": rnd, "count": len(evs), "all_done": all_done, "events": evs})
        tree2[proj] = lst
    import json as _json
    return templates.TemplateResponse(request, "schedule.html", {
        "request": request, "comp": comp, "tree": tree2,
        "tree_json": _json.dumps(tree2, ensure_ascii=False),
        "events": events})


@app.get("/events/{competition_id}/console/{ceid}", response_class=HTMLResponse)
async def console_page(request: Request, competition_id: int, ceid: int):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    ev = _event_or_404(ceid)
    all_competitors = db.rows(db.get_db().execute(
        "SELECT DISTINCT number, name, unit FROM competitors WHERE competition_id=? ORDER BY number", (competition_id,)))
    checked = set(checked_roster(ev["id"]))
    # 同项目下一场（P2 快赢）：优先同项目仍在评分中的最近一场，其次任一未开场场次，供控制台一键跳转
    _conn = db.get_db()
    next_ev = db.rowdict(_conn.execute(
        "SELECT id, code FROM events WHERE competition_id=? AND project_code=? AND id!=? AND status='scoring' "
        "ORDER BY round, id LIMIT 1",
        (competition_id, ev["project_code"], ceid)).fetchone())
    if not next_ev:
        next_ev = db.rowdict(_conn.execute(
            "SELECT id, code FROM events WHERE competition_id=? AND project_code=? AND id!=? AND status='pending' "
            "ORDER BY round, id LIMIT 1",
            (competition_id, ev["project_code"], ceid)).fetchone())
    return templates.TemplateResponse(request, "console.html", {
        "comp": comp, "ev": ev,
        "dances": dances_of(ev["id"]), "roster": roster(ev["id"]),
        "all_competitors": all_competitors, "checked": checked,
        "checked_n": len(checked), "total": len(roster(ev["id"])),
        "judges": judges_of(competition_id), "result": load_results(ev["id"]),
        "next_ev": next_ev,
    })


@app.get("/events/{competition_id}/results", response_class=HTMLResponse)
async def results_page(request: Request, competition_id: int):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    evs = db.rows(db.get_db().execute(
        "SELECT * FROM events WHERE competition_id=? AND status IN ('calculated','published') ORDER BY project_code, round, code",
        (competition_id,)))
    payload = []
    adv_hints = []
    for ev in evs:
        res = load_results(ev["id"])
        if res:
            payload.append({"ev": ev, "results": res})
        if (ev["status"] == "published" and ev["round"] == 1 and ev["advancement_count"]):
            has_next = db.get_db().execute(
                "SELECT 1 FROM events WHERE competition_id=? AND project_code=? AND round=?",
                (competition_id, ev["project_code"], ev["round"] + 1)).fetchone()
            if has_next:
                adv_hints.append({"code": ev["code"], "round": ev["round"], "project": ev["project_code"]})
    # R67 突出重点：待发布（已计算）场次置顶，已发布按场次序殿后
    payload.sort(key=lambda p: (0 if p["ev"]["status"] == "calculated" else 1, p["ev"]["run_seq"] or 0))
    return templates.TemplateResponse(request, "results.html", {"request": request, "comp": comp,
        "payload": payload, "adv_hints": adv_hints})


@app.get("/judge", response_class=HTMLResponse)
async def judge_home(request: Request):
    s = require_judge(request)
    comp = _current_competition(request)
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
    # 盲评公平性：评分页不向裁判提供背番号以外的任何选手信息（姓名/单位不出库）
    # 检录门禁：未检录选手置灰且不可评分
    checked = set(checked_roster(ceid))
    return templates.TemplateResponse(request, "judge_sheet.html", {
        "ev": ev, "comp": comp, "dance": dance,
        "roster": roster_list, "rows": rows, "checked": checked,
        "is_skating": scoring_kind(ev) == "skating",
        "is_mark": scoring_kind(ev) == "mark",
        "is_score": scoring_kind(ev) == "score",
        "n": len(roster_list),
    })


# ------------------------------------------------------------------ 用户与角色管理（管理员）
@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    require_admin(request)
    return templates.TemplateResponse(request, "users.html", {"request": request})


@app.get("/api/users")
async def api_users_list(request: Request = None):
    require_admin(request)
    rows = db.rows(db.get_db().execute(
        "SELECT id, username, role, display_name, active, created_at FROM users "
        "WHERE role IN ('host','marshal') ORDER BY role, username"))
    return {"users": rows}


@app.post("/api/users")
async def api_users_create(request: Request = None):
    require_admin(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体须为 JSON")
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    role = str(body.get("role") or "").strip()
    display_name = str(body.get("display_name") or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名与口令必填")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="口令至少 6 位")
    if len(username) > 64 or len(display_name) > 64:
        raise HTTPException(status_code=400, detail="用户名/显示名最长 64 字符")
    comp_id = body.get("competition_id")
    if role not in ("host", "marshal", "compadmin"):
        raise HTTPException(status_code=400, detail="角色须为 host / marshal / compadmin")
    if _compadmin(request) and role == "compadmin":
        raise HTTPException(status_code=403, detail="赛事管理员不可创建赛事管理员账号")
    if role == "compadmin":
        # R54 赛事管理员：必须绑定赛事
        try:
            comp_id = int(comp_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="赛事管理员必须绑定 competition_id")
        if not db.rowdict(db.get_db().execute(
                "SELECT id FROM competitions WHERE id=?", (comp_id,)).fetchone()):
            raise HTTPException(status_code=400, detail="绑定的赛事不存在")
    else:
        comp_id = None
    conn = db.get_db()
    dup = db.rowdict(conn.execute(
        "SELECT id, role, active FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone())
    if dup and dup["role"] == "compadmin" and role == "compadmin":
        # R57：同名赛事管理员 → 改绑/重置（总管理员重建演示赛时的固定动作）
        conn.execute("UPDATE users SET pw_hash=?, comp_id=?, active=1, display_name=? WHERE id=?",
                     (_hash_pw(password), comp_id, display_name or username, dup["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (dup["id"],))
        conn.commit()
        return {"ok": True, "username": username, "role": role, "comp_id": comp_id, "rebound": True}
    if dup:
        if not dup["active"]:
            raise HTTPException(status_code=400,
                                detail="用户名已存在（该同名账号当前为停用状态，可在列表中启用或改用其他用户名）")
        raise HTTPException(status_code=400, detail="用户名已存在（不区分大小写）")
    conn.execute(
        "INSERT INTO users(username, pw_hash, role, display_name, comp_id) VALUES(?,?,?,?,?)",
        (username, _hash_pw(password), role, display_name or username, comp_id))
    conn.commit()
    return {"ok": True, "username": username, "role": role, "comp_id": comp_id}


@app.post("/api/users/{user_id}/password")
async def api_users_password(user_id: int, request: Request = None):
    s = require_admin(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体须为 JSON")
    password = str(body.get("password") or "")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="口令至少 6 位")
    conn = db.get_db()
    cur = conn.execute("UPDATE users SET pw_hash=? WHERE id=? AND role IN ('host','marshal')",
                       (_hash_pw(password), user_id))
    conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))   # 重置口令即踢下线
    conn.commit()
    if not cur.rowcount:
        raise HTTPException(status_code=404, detail="账号不存在")
    urow = conn.execute("SELECT username, display_name FROM users WHERE id=?", (user_id,)).fetchone()
    _audit(_actor_name(s), "user_password", f"user:{user_id}",
           "重置 {0}（{1}）口令".format((urow["display_name"] or urow["username"]) if urow else "?",
                                       urow["username"] if urow else "?"),
           _client_ip(request))
    return {"ok": True}


@app.post("/api/users/{user_id}/active")
async def api_users_active(user_id: int, request: Request = None):
    s = require_admin(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体须为 JSON")
    state = 1 if body.get("active") else 0
    conn = db.get_db()
    cur = conn.execute("UPDATE users SET active=? WHERE id=? AND role IN ('host','marshal')",
                       (state, user_id))
    if not cur.rowcount:
        raise HTTPException(status_code=404, detail="账号不存在")
    if not state:
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))   # 停用即踢下线
    conn.commit()
    urow = conn.execute("SELECT username, display_name FROM users WHERE id=?", (user_id,)).fetchone()
    _audit(_actor_name(s), "user_active", f"user:{user_id}",
           "{0} → {1}".format((urow["display_name"] or urow["username"]) if urow else "?",
                              "启用" if state else "停用"),
           _client_ip(request))
    return {"ok": True, "active": bool(state)}


@app.get("/api/stats")
async def api_stats(request: Request = None):
    """R53 访问统计（admin）：各工具桶 累计/今日/近7天。"""
    require_admin(request)
    conn = db.get_db()
    today = time.strftime("%Y-%m-%d")
    d7 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 6 * 86400))
    totals = db.rows(conn.execute(
        "SELECT slug, SUM(n) AS n FROM visit_stats GROUP BY slug ORDER BY n DESC"))
    today_m = {r["slug"]: r["n"] for r in db.rows(
        conn.execute("SELECT slug, n FROM visit_stats WHERE day = ?", (today,)))}
    d7_m = {r["slug"]: r["n"] for r in db.rows(
        conn.execute("SELECT slug, SUM(n) AS n FROM visit_stats WHERE day >= ? GROUP BY slug", (d7,)))}
    return {"items": [{"slug": r["slug"], "total": r["n"],
                       "today": today_m.get(r["slug"], 0),
                       "d7": d7_m.get(r["slug"], 0)} for r in totals]}


_ROBOTS = """User-agent: *
Disallow: /api/
Disallow: /events
Disallow: /judge
Disallow: /staff
Disallow: /users
Disallow: /files/
Allow: /
Allow: /public/
Allow: /manual
Allow: /apps/
"""


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """私有工作区不索引；门户/公开页/手册/应用可索引。"""
    return PlainTextResponse(_ROBOTS, media_type="text/plain")


@app.get("/api/audit")
async def api_audit(request: Request = None, limit: int = 200):
    """敏感操作审计查询（管理员）：最新 limit 条，倒序。"""
    require_admin(request)
    limit = max(1, min(int(limit), 500))
    rows = db.rows(db.get_db().execute(
        "SELECT id, actor, action, target, detail, ip, created_at FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,)))
    return {"items": rows}


@app.get("/manual", response_class=HTMLResponse)
async def manual_page(request: Request):
    """操作手册（赛事完整周期各角色动线，实机截图说明）。"""
    return templates.TemplateResponse(request, "manual.html", {"request": request})


def _public_fingerprint(competition_id):
    """公开页变更指纹（R41）：发布门数 + 场次数 + 最大场次 id。
    廉价索引聚合（<1ms），覆盖发布/撤回/建场/删场四类变更。"""
    row = db.get_db().execute(
        "SELECT (SELECT COUNT(*) FROM results r JOIN events e ON e.id=r.event_id "
        " WHERE e.competition_id=?) AS pub, "
        "(SELECT COUNT(*) FROM events WHERE competition_id=?) AS n, "
        "(SELECT COALESCE(MAX(id),0) FROM events WHERE competition_id=?) AS m",
        (competition_id, competition_id, competition_id)).fetchone()
    return f'W/"{row["pub"]}-{row["n"]}-{row["m"]}"'


_PUBLIC_PAGE_CACHE = {}   # (cid, page) -> (fingerprint, html_bytes)；单 worker 内存态


def _etag_page(request: Request, cid: int, page: str, fingerprint: str, render):
    """公开页条件请求 + 渲染缓存（R41 压测优化）：观众页内容只随指纹变化——
    1) If-None-Match 命中指纹 → 304（免渲染免传输）；
    2) 指纹未变但无条件头 → 直发上次渲染的 HTML（免渲染免查询，300 并发同指纹只渲染一次）；
    3) 指纹变化 → 渲染一次并更新缓存。压测背景：单 worker 下每请求全量渲染 Jinja 是
       300 观众突发期 HTML P95 5s 的 CPU 瓶颈。"""
    inm = request.headers.get("if-none-match")
    if inm and inm.strip() == fingerprint:
        return Response(status_code=304, headers={"ETag": fingerprint, "Cache-Control": "no-cache"})
    entry = _PUBLIC_PAGE_CACHE.get((cid, page))
    if entry and entry[0] == fingerprint:
        html = entry[1]
    else:
        resp = render()
        html = resp.body if isinstance(resp.body, bytes) else str(resp.body).encode()
        _PUBLIC_PAGE_CACHE[(cid, page)] = (fingerprint, html)
    return HTMLResponse(html, headers={"ETag": fingerprint, "Cache-Control": "no-cache"})


@app.api_route("/public/schedule", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def public_schedule(request: Request):
    comp = _viewer_competition(request)
    if comp is None:
        return RedirectResponse("/competitions", status_code=302)
    evs = []
    if comp:
        evs = db.rows(db.get_db().execute(
            "SELECT code,name,project_code,round,status FROM events WHERE competition_id=? "
            "ORDER BY COALESCE(run_seq, 9999), project_code, round, code",
            (comp["id"],)))
    fp = _public_fingerprint(comp["id"]) if comp else 'W/"0-0-0"'
    return _etag_page(request, comp["id"] if comp else 0, "schedule", fp, lambda: templates.TemplateResponse(
        request, "public_schedule.html", {"request": request, "comp": comp, "events": evs}))


@app.api_route("/public/results", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def public_results(request: Request):
    comp = _viewer_competition(request)
    if comp is None:
        return RedirectResponse("/competitions", status_code=302)
    payload = []
    if comp:
        evs = db.rows(db.get_db().execute(
            "SELECT * FROM events WHERE competition_id=? AND published=1 ORDER BY project_code, round, code", (comp["id"],)))
        for ev in evs:
            name_by_number = _display_names(db.get_db(), comp["id"], ev["project_code"])
            res = load_results(ev["id"])
            if res:
                payload.append({"ev": ev, "results": res, "names": name_by_number})
    standings = _team_standings(comp["id"], published_only=True) if comp else {"standings": []}
    fp = _public_fingerprint(comp["id"]) if comp else 'W/"0-0-0"'
    return _etag_page(request, comp["id"] if comp else 0, "results", fp, lambda: templates.TemplateResponse(
        request, "public_results.html",
        {"request": request, "comp": comp, "payload": payload, "standings": standings}))


@app.get("/screen", response_class=HTMLResponse)
async def screen_page(request: Request):
    comp = _viewer_competition(request)
    if comp is None:
        return RedirectResponse("/competitions", status_code=302)
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
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    # R49 多赛事模型：多赛事可同时 active，不再互斥
    conn.execute("UPDATE competitions SET active=1 WHERE id=?", (competition_id,))
    conn.commit()
    # 同步操作人的会话赛事选择
    _session(request)  # 确保 session 存在
    return {"ok": True}


@app.post("/api/events/{competition_id}/deactivate")
async def api_deactivate(competition_id: int, request: Request = None):
    """R71d：停用赛事（从公开赛事列表与全局公开入口移除；数据保留，可再激活）。"""
    require_admin(request)
    _comp_or_404(competition_id)
    conn = db.get_db()
    conn.execute("UPDATE competitions SET active=0 WHERE id=?", (competition_id,))
    conn.commit()
    return {"ok": True}


@app.delete("/api/events/{competition_id}")
async def api_delete_event(competition_id: int, request: Request = None):
    s = require_admin(request)
    comp = db.rowdict(db.get_db().execute(
        "SELECT name FROM competitions WHERE id=?", (competition_id,)).fetchone())
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
    _audit(_actor_name(s), "event_delete", f"event:{competition_id}",
           comp["name"] if comp else "", _client_ip(request))
    return {"ok": True}


def _display_names(conn, competition_id: int, project_code=None):
    """背番号→显示名：双人项目「张三 / 李四」（partner 为 R71 组合搭档列，纯展示），
    单人项目即本人。计分/检录/晋级仍按背番号一人一号。
    R71b：搭档按场次语义——同号在不同项目可配不同搭档，传 project_code 过滤该项目的行；
    不传则跨项目聚合（仅限与场次无关的展示）。"""
    q = "SELECT number, name, partner FROM competitors WHERE competition_id=?"
    args = [competition_id]
    if project_code is not None:
        q += " AND project_code=?"
        args.append(project_code)
    out = {}
    for r in db.rows(conn.execute(q, args)):
        n = (r["name"] or "").strip()
        pt = (r["partner"] or "").strip()
        disp = (n + (" / " + pt if pt else "")) if n else pt
        if r["number"] in out:
            continue   # 同号同项目多行（历史数据）取首行
        out[r["number"]] = disp
    return out




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
        i_partner = _col(h, "搭档姓名", "搭档", "partner")
        i_punit = _col(h, "搭档单位", "搭档学校", "partner_unit")
        i_role = _col(h, "选手身份", "身份", "role")
        i_prole = _col(h, "搭档身份", "partner_role")
        if i_num is None:
            raise HTTPException(status_code=400, detail="缺少列：背番号")
        no_partner = {}   # R71c：未填搭档的行——双人项目漏填预警（单人项目可忽略）；
        for r in data_rows:   # 补全后同背番号重导即覆盖恢复（REPLACE 幂等）
            num = r[i_num].strip()
            if not num:
                continue
            nm = r[i_name].strip() if i_name is not None and i_name < len(r) else ""
            pt = r[i_partner].strip() if i_partner is not None and i_partner < len(r) else ""
            pu = r[i_punit].strip() if i_punit is not None and i_punit < len(r) else ""
            rl = r[i_role].strip() if i_role is not None and i_role < len(r) else ""
            prl = r[i_prole].strip() if i_prole is not None and i_prole < len(r) else ""
            conn.execute(
                "INSERT OR REPLACE INTO competitors(competition_id, number, project_code, name, partner, partner_unit, unit, role, partner_role) VALUES(?,?,?,?,?,?,?,?,?)",
                (competition_id, num, (r[i_proj].strip() if i_proj is not None and i_proj < len(r) else ""),
                 nm, pt, pu,
                 r[i_unit].strip() if i_unit is not None and i_unit < len(r) else "", rl, prl))
            if not pt:
                no_partner[num] = nm
            count += 1
        if no_partner:
            preview = "、".join("{0} {1}".format(n, m) for n, m in list(no_partner.items())[:8])
            more = " 等 {0} 行".format(len(no_partner)) if len(no_partner) > 8 else ""
            problems.append("未填搭档（单人项目可忽略；双人项目请补齐后重新导入，背号不变即可覆盖）：{0}{1}".format(preview, more))
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
        # R71 一致性：参赛选手列引用的背号必须已在选手库——坏号不入上场名单（防幽灵号），
        # 场次仍创建，problems 逐行提示（补导选手后重传赛程即可）
        known_numbers = {r["number"] for r in db.rows(conn.execute(
            "SELECT number FROM competitors WHERE competition_id=?", (competition_id,)))}
        i_code = _col(h, "场次编号", "code")
        i_name, i_proj = _col(h, "场次名称", "name"), _col(h, "项目编号", "project")
        i_round, i_dance = _col(h, "轮次", "round"), _col(h, "舞种", "dances")
        i_type = _col(h, "评分类型", "scoring_type")
        i_adv = _col(h, "晋级人数", "advancement_count")
        i_tmode = _col(h, "团体计分", "team_mode")
        i_comps = _col(h, "参赛选手", "competitors")
        if i_code is None or i_round is None:
            raise HTTPException(status_code=400, detail="缺少列：场次编号/轮次")
        for r in data_rows:
            code = r[i_code].strip()
            if not code:
                continue
            rnd = int(r[i_round].strip() or 1)
            proj = r[i_proj].strip() if i_proj is not None and i_proj < len(r) else ""
            # R57 结构化解析：轮次之后的多值区（舞种… 评分类型 晋级人数 参赛选手…）
            # 在 Excel 导出的未加引号 CSV 里会各自溢出成多列，无法按列号取值——
            # 以「评分类型枚举值」为锚点切分：锚点前=舞种（可多个），锚点=评分类型，
            # 其后依次为 晋级人数、参赛选手（可多个）。
            tail = [x.strip() for x in ",".join(r[i_dance:]).replace("，", ",").split(",") if x.strip()] \
                if i_dance is not None and i_dance < len(r) else []
            stype_idx = next((k for k, v in enumerate(tail)
                              if v.upper() in ("SKATING", "MARK", "SCORE")), None)
            tmode_raw = (r[i_tmode].strip() if i_tmode is not None and i_tmode < len(r) else "")
            if stype_idx is not None:
                # 结构化切分（多值列溢出场景）：锚点后依次 晋级人数、团体计分（可选）、参赛选手…
                dances = tail[:stype_idx]
                styp = {"SKATING": "顺位法", "MARK": "Mark制", "SCORE": "评分制"}[tail[stype_idx].upper()]
                rest = tail[stype_idx + 1:]
                adv = int(rest[0]) if rest and rest[0].isdigit() else 0
                rest = rest[1:]
                if rest and rest[0] and not rest[0].isdigit():
                    tmode_raw = rest[0]   # 团体计分列溢出到多值区（标准/老带新）
                    rest = rest[1:]
                comps = rest
            else:
                # 无锚点：未溢出的行按列位置解析（兼容旧口径：中文/未知评分类型落 Mark制）
                styp = (r[i_type].strip().upper() if i_type is not None and i_type < len(r) else "SKATING")
                styp = {"SKATING": "顺位法", "MARK": "Mark制", "SCORE": "评分制"}.get(styp, "Mark制")
                dances = ([r[i_dance].strip()] if r[i_dance].strip() else []) \
                    if i_dance is not None and i_dance < len(r) else []
                adv = int(r[i_adv].strip()) if i_adv is not None and i_adv < len(r) and r[i_adv].strip().isdigit() else 0
                comps = [x.strip() for x in (r[i_comps] if i_comps is not None and i_comps < len(r) else "")
                         .replace("，", ",").split(",") if x.strip()]
            conn.execute("INSERT OR IGNORE INTO projects(competition_id, code, name) VALUES(?,?,?)",
                         (competition_id, proj, proj))
            # R73：tmode_raw 已在多值区解析时确定（团体计分列或溢出吞出）——此处不得重复赋值覆盖
            tmode = "freshman_half" if ("老带新" in tmode_raw or tmode_raw == "freshman_half") else "standard"
            cur = conn.execute(
                "INSERT OR IGNORE INTO events(competition_id, code, name, project_code, round, scoring_type, advancement_count, team_mode)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (competition_id, code,
                 r[i_name].strip() if i_name is not None and i_name < len(r) else code,
                 proj, rnd, styp, adv, tmode))
            # R71：INSERT OR IGNORE 被忽略（重传同场次）时 lastrowid 是连接上一次插入的 rowid
            # （可能是 judges/competitors 的），不能信任——显式回查为准（重导幂等的正确路径）
            row = conn.execute("SELECT id FROM events WHERE competition_id=? AND code=?",
                               (competition_id, code)).fetchone()
            ev_id = row["id"] if row else cur.lastrowid
            if row:
                conn.execute("UPDATE events SET team_mode=? WHERE id=?", (tmode, ev_id))   # 重导同步计分模式
            for k, dname in enumerate(dances):
                conn.execute("INSERT INTO event_dances(event_id, name, ord) VALUES(?,?,?)", (ev_id, dname, k))
            if rnd == 1:
                conn.execute("DELETE FROM event_competitors WHERE event_id=?", (ev_id,))
                ghost = [n for n in comps if n not in known_numbers]
                if ghost:
                    problems.append("场次 {0}：参赛选手背号不在选手库，已跳过：{1}".format(code, ",".join(ghost)))
                for num in comps:
                    if num in known_numbers:
                        conn.execute("INSERT OR IGNORE INTO event_competitors(event_id, competitor_number) VALUES(?,?)",
                                     (ev_id, num))
            count += 1
    else:
        raise HTTPException(status_code=400, detail="未知导入类型")
    conn.commit()
    sse.bus.publish(competition_id, "schedule_changed")
    return {"ok": True, "imported": count, "problems": problems}


_CSV_TEMPLATES = {
    # 表头与 api_import 解析列一致（FR 导入列名），各带 2 行示例
    "competitors": [["背番号", "项目编号", "姓名", "搭档姓名", "搭档单位", "选手身份", "搭档身份", "学校/单位"],
                    ["101", "S-CHA", "张三", "李四", "", "新生", "新生", "北京舞蹈学院"],
                    ["101", "S-JSW", "张三", "王五", "", "新生", "新生", "北京舞蹈学院"],
                    ["102", "S-JSW", "李四", "", "", "新生", "", "上海体育大学"]],
    "judges": [["裁判ID", "姓名"],
               ["J1", "王裁判"],
               ["J2", "李裁判"]],
    "schedule": [["场次编号", "场次名称", "项目编号", "轮次", "舞种", "评分类型", "晋级人数", "团体计分", "参赛选手"],
                 ["S-CHA-R1", "恰恰初赛", "S-CHA", "1", "恰恰", "SKATING", "12", "标准", "101,102,103"],
                 ["S-CHA-R2", "恰恰决赛", "S-CHA", "2", "恰恰", "SKATING", "0", "标准", "101,102"]],
}


@app.get("/api/templates/{kind}")
async def api_template(kind: str):
    """CSV 导入模板下载（P2 快赢）：competitors/judges/schedule，
    表头与 api_import 解析列一致，含 2 行示例，Content-Disposition 触发下载。"""
    rows = _CSV_TEMPLATES.get(kind)
    if not rows:
        raise HTTPException(status_code=404, detail="未知模板类型")
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    return PlainTextResponse(
        buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="template-{0}.csv"'.format(kind)})


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
    # roster 兼容数组与逗号字符串两种形态（A5：字符串此前被按字符拆分入库）
    raw_roster = body.get("roster") or []
    if isinstance(raw_roster, str):
        raw_roster = raw_roster.replace("，", ",").split(",")
    if not isinstance(raw_roster, list):
        raise HTTPException(status_code=422, detail="roster 须为背号数组或逗号分隔字符串")
    roster_list = [str(n).strip() for n in raw_roster if str(n).strip()]
    if not roster_list:
        raise HTTPException(status_code=400, detail="上场选手名单不能为空")
    known = {c["number"] for c in db.rows(db.get_db().execute(
        "SELECT number FROM competitors WHERE competition_id=?", (comp["id"],)))}
    unknown = [n for n in roster_list if n not in known]
    if unknown:
        raise HTTPException(status_code=400, detail="背号不在选手库中: " + ",".join(unknown[:5]))
    if dances_of(ev["id"]) == []:
        raise HTTPException(status_code=400, detail="场次未配置舞种，请检查赛程导入")
    had_scores = bool(db.get_db().execute(
        "SELECT 1 FROM score_records WHERE event_id=? LIMIT 1", (ceid,)).fetchone())
    conn = db.get_db()
    if had_scores or body.get("reset"):
        # 重开（清空评分）= 全部重来，检录状态一并重置
        conn.execute("DELETE FROM event_competitors WHERE event_id=?", (ceid,))
        conn.execute("DELETE FROM score_records WHERE event_id=?", (ceid,))
        conn.execute("DELETE FROM results WHERE event_id=?", (ceid,))
    else:
        # 普通开启保留已有检录（检录员的确认不因主持人开场而作废），仅移除出名单者
        ph = ",".join("?" * len(roster_list))
        conn.execute(f"DELETE FROM event_competitors WHERE event_id=? AND competitor_number NOT IN ({ph})",
                     [ceid] + roster_list)
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


# ----------------------------------------------- schedule editing (FR-C1/J2)
@app.post("/api/events/{competition_id}/schedule/add")
async def api_schedule_add(competition_id: int, request: Request = None):
    """单场新增（FR-J2 低复杂度动线）：任意轮次可挂新场次。"""
    require_admin(request)
    comp = _comp_or_404(competition_id)
    body = await request.json()
    code = str(body.get("code") or "").strip()
    proj = str(body.get("project") or "").strip()
    try:
        rnd = int(body.get("round") or 1)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="轮次必须为整数")
    if not code or not proj:
        raise HTTPException(status_code=400, detail="场次编号与项目编号必填")
    typ = str(body.get("type") or "SKATING").strip().upper()
    typ_map = {"SKATING": "顺位法", "MARK": "Mark制", "SCORE": "评分制"}
    if typ not in typ_map:
        raise HTTPException(status_code=400, detail="评分类型须为 SKATING/MARK/SCORE")
    conn = db.get_db()
    if conn.execute("SELECT 1 FROM events WHERE competition_id=? AND code=?", (competition_id, code)).fetchone():
        raise HTTPException(status_code=400, detail="场次编号已存在")
    # 全部校验前置：roster 校验失败时不得留下任何已插入的行（R39 复审 P2：幽灵场次）
    roster = [x.strip() for x in str(body.get("roster") or "").replace("，", ",").split(",") if x.strip()]
    # 任意轮次均可预填上场名单（晋级轮回填场景同样需要）；开场(open)前可随时调整
    if roster:
        known = {c["number"] for c in db.rows(conn.execute(
            "SELECT number FROM competitors WHERE competition_id=?", (competition_id,)))}
        unknown = [n for n in roster if n not in known]
        if unknown:
            raise HTTPException(status_code=400,
                                detail="背号不在选手库中: " + ",".join(unknown[:5]))
    cur = conn.execute(
        "INSERT INTO events(competition_id, code, name, project_code, round, scoring_type, advancement_count, status) "
        "VALUES(?,?,?,?,?,?,?,'pending')",
        (competition_id, code, str(body.get("name") or code), proj, rnd, typ_map[typ],
         int(body.get("adv") or 0)))
    ev_id = cur.lastrowid
    dances = [x.strip() for x in str(body.get("dances") or "华尔兹").replace("，", ",").split(",") if x.strip()]
    for k, dname in enumerate(dances):
        conn.execute("INSERT INTO event_dances(event_id, name, ord) VALUES(?,?,?)", (ev_id, dname, k))
    for num in roster:
        conn.execute("INSERT OR IGNORE INTO event_competitors(event_id, competitor_number) VALUES(?,?)", (ev_id, num))
    conn.commit()
    sse.bus.publish(comp["id"], "schedule_changed", {"added": code})
    return {"ok": True, "event_id": ev_id, "code": code}


@app.put("/api/competition-events/{ceid}")
async def api_event_edit(ceid: int, request: Request = None):
    """编辑场次（仅 pending：未开场才可改结构，避免破坏评分一致性）。"""
    require_admin(request)
    ev = _event_or_404(ceid)
    if ev["status"] != "pending":
        raise HTTPException(status_code=400, detail="仅未开场的场次可编辑")
    conn = db.get_db()
    body = await request.json()
    fields, vals = [], []
    for key, col in (("name", "name"), ("type", "scoring_type"), ("adv", "advancement_count")):
        if key in body:
            v = body[key]
            if key == "type":
                typ_map = {"SKATING": "顺位法", "MARK": "Mark制", "SCORE": "评分制"}
                v = typ_map.get(str(v).strip().upper())
                if not v:
                    raise HTTPException(status_code=400, detail="评分类型须为 SKATING/MARK/SCORE")
            vals.append(v); fields.append(f"{col}=?")
    if fields:
        vals.append(ceid)
        conn.execute(f"UPDATE events SET {', '.join(fields)} WHERE id=?", vals)
    if "dances" in body:
        dances = [x.strip() for x in str(body["dances"]).replace("，", ",").split(",") if x.strip()]
        if dances:
            conn.execute("DELETE FROM event_dances WHERE event_id=?", (ceid,))
            for k, dname in enumerate(dances):
                conn.execute("INSERT INTO event_dances(event_id, name, ord) VALUES(?,?,?)", (ceid, dname, k))
    conn.commit()
    sse.bus.publish(ev["competition_id"], "schedule_changed", {"edited": ev["code"]})
    return {"ok": True}


@app.delete("/api/competition-events/{ceid}")
async def api_event_delete(ceid: int, request: Request = None):
    """删除场次（仅 pending）。"""
    s = require_admin(request)
    ev = _event_or_404(ceid)
    if ev["status"] != "pending":
        raise HTTPException(status_code=400, detail="仅未开场的场次可删除（先退回或关闭后清理）")
    comp_id = ev["competition_id"]
    conn = db.get_db()
    conn.execute("DELETE FROM event_dances WHERE event_id=?", (ceid,))
    conn.execute("DELETE FROM event_competitors WHERE event_id=?", (ceid,))
    conn.execute("DELETE FROM events WHERE id=?", (ceid,))
    conn.commit()
    _audit(_actor_name(s), "ce_delete", f"event:{ceid}",
           f"{ev['code']} {ev['name']}", _client_ip(request))
    sse.bus.publish(comp_id, "schedule_changed", {"deleted": ev["code"]})
    return {"ok": True}


@app.put("/api/events/{competition_id}")
async def api_event_settings(competition_id: int, request: Request = None):
    """赛事设置：名称/日期/地点（FR-A3）。"""
    require_admin(request)
    comp = _comp_or_404(competition_id)
    body = await request.json()
    fields, vals = [], []
    for key in ("name", "date", "location"):
        if key in body and str(body[key]).strip():
            fields.append(f"{key}=?"); vals.append(str(body[key]).strip())
    if fields:
        vals.append(competition_id)
        db.get_db().execute(f"UPDATE competitions SET {', '.join(fields)} WHERE id=?", vals)
        db.get_db().commit()
    return {"ok": True}


@app.post("/api/competition-events/{ceid}/return-scores")
async def api_return_scores(ceid: int, request: Request = None):
    """FR-G5 评分退回：清空本场评分与结果，状态回到评分中，裁判重新提交。"""
    s = require_admin(request)
    ev, comp = _require_active_event(ceid)
    if ev["status"] not in ("scoring", "calculated", "published"):
        raise HTTPException(status_code=400, detail="当前状态不可退回")
    conn = db.get_db()
    cleared = conn.execute("SELECT COUNT(*) c FROM score_records WHERE event_id=?", (ceid,)).fetchone()["c"]
    conn.execute("DELETE FROM score_records WHERE event_id=?", (ceid,))
    conn.execute("DELETE FROM results WHERE event_id=?", (ceid,))
    conn.execute("UPDATE events SET status='scoring', published=0 WHERE id=?", (ceid,))
    conn.commit()
    _audit(_actor_name(s), "return_scores", f"event:{ceid}",
           f"{ev['code']} {ev['name']}：清空评分 {cleared} 条，状态回到评分中", _client_ip(request))
    sse.bus.publish(comp["id"], "score_returned", {"event_id": ceid})
    return {"ok": True, "event_id": ceid}


@app.post("/api/competition-events/{ceid}/calculate")
async def api_calculate(ceid: int, request: Request = None):
    require_admin(request)
    ev, comp = _require_active_event(ceid)
    if not checked_roster(ceid):
        raise HTTPException(status_code=400, detail="本场尚无已检录选手，无法计算（请先完成检录）")
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
    comp = _current_competition(request)
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
    checked = set(checked_roster(ceid))
    values = body.get("values") or {}
    kind = scoring_kind(ev)
    skating = kind == "skating"

    # 服务端复验（不信任客户端）
    if kind == "score":
        if set(values.keys()) != checked:
            raise HTTPException(status_code=400, detail="必须为全部已检录队伍提交评分")
        for v in values.values():
            try:
                fv = float(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="评分必须为 0~10 的数值")
            if isinstance(v, bool):
                raise HTTPException(status_code=400, detail="评分必须为数值（布尔标记不属于评分制）")
            if not (0 <= fv <= 10) or round(fv, 1) != fv:
                raise HTTPException(status_code=400, detail="评分须为 0~10 且最多一位小数")
    elif skating:
        if set(values.keys()) != checked:
            raise HTTPException(status_code=400, detail="必须为全部已检录选手提交名次")
        placements = []
        for num, v in values.items():
            try:
                p = int(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="名次必须为 1~N 的整数")
            if not (1 <= p <= len(checked)):
                raise HTTPException(status_code=400, detail="名次超出范围 1~N")
            placements.append(p)
        if len(set(placements)) != len(checked):
            raise HTTPException(status_code=400, detail="名次必须为 1~N 且互不重复")
    elif kind == "mark":
        # Mark制（滑冰制预赛）：裁判**只对选中的选手**给 mark（core 语义：mark is True 计票，
        # 未选中选手无记录、票数 0）。提交即整体替换该裁判该舞种的全部标记。
        # 检录门禁：只能给已检录选手 mark。
        if not set(values.keys()) <= checked:
            raise HTTPException(status_code=400, detail="标记对象必须为已检录选手")
        for v in values.values():
            if not isinstance(v, bool):
                raise HTTPException(status_code=400, detail="Mark制为布尔标记（true/false）")
        if not any(values.values()):
            raise HTTPException(status_code=400, detail="至少需勾选一名给予 Mark 的选手")

    conn = db.get_db()
    # R48 评分变更日志：捕获旧值 → 写入后记入 score_change_log（追加式历史）
    old_records = {}
    if kind != "mark":
        for r in conn.execute(
                "SELECT competitor_number, mark, placement FROM score_records "
                "WHERE event_id=? AND judge_code=? AND dance_name=?",
                (ceid, s["judge_code"], dance)).fetchall():
            old_records[r["competitor_number"]] = (r["mark"], r["placement"])
    if kind == "mark":
        # 整体替换：清除该裁判该舞种旧记录，仅保留本次勾选（给予 mark）的选手
        conn.execute("DELETE FROM score_records WHERE event_id=? AND judge_code=? AND dance_name=?",
                     (ceid, s["judge_code"], dance))
        for num, v in values.items():
            if v:
                conn.execute(
                    "INSERT INTO score_records(event_id, judge_code, competitor_number, dance_name, mark, placement) "
                    "VALUES(?,?,?,?,?,?)",
                    (ceid, s["judge_code"], str(num), dance, 1, None))
    else:
        for num, v in values.items():
            conn.execute(
                "INSERT INTO score_records(event_id, judge_code, competitor_number, dance_name, mark, placement) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(event_id, dance_name, judge_code, competitor_number) "
                "DO UPDATE SET mark=excluded.mark, placement=excluded.placement, timestamp=datetime('now','localtime')",
                (ceid, s["judge_code"], str(num), dance,
                 _sheet_mark_value(kind, v),
                 _sheet_placement_value(kind, v)))
    conn.commit()
    # R48 评分变更日志（追加式）
    for num in values:
        old_m, old_p = old_records.get(str(num), (None, None))
        new_m = _sheet_mark_value(kind, values[num]) if kind == "mark" else None
        new_p = _sheet_placement_value(kind, values[num]) if kind != "mark" else None
        if kind == "mark":
            new_m = 1 if values[num] else None
            new_p = None
        if (old_m, old_p) != (new_m, new_p):
            conn.execute(
                "INSERT INTO score_change_log(event_id, judge_code, competitor_number, dance_name,"
                " old_mark, new_mark, old_placement, new_placement, changed_by)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (ceid, s["judge_code"], str(num), dance, old_m, new_m, old_p, new_p,
                 s.get("display_name") or s.get("judge_code") or s["role"]))
    conn.commit()
    sse.bus.publish(comp["id"], "score_submitted",
                    {"event_id": ceid, "dance": dance, "judge": s["judge_code"]})
    auto = _auto_calculate_if_ready(_event_or_404(ceid), comp)
    auto_pub = False
    if auto and comp.get("auto_publish"):
        # R57 自动发布开关：收齐自动算分后直接发布进大屏（按赛事配置，默认关）
        db.get_db().execute("UPDATE events SET published=1, status='published' WHERE id=?", (ceid,))
        db.get_db().commit()
        sse.bus.publish(comp["id"], "results_published", {"event_id": ceid})
        auto_pub = True
    return {"ok": True, "auto_calculated": auto, "auto_published": auto_pub}


# ---------------------------------------------- R48 数据持久化与容灾
# 设计原则：
#   1. JSON 导出 = 可读、可跨版本、可编辑后导入
#   2. SQLite 二进制备份 = 秒级、原子、可直接替换恢复
#   3. score_change_log = 追加式历史（每个分值变化一行，可回溯任意时点）
#   4. 导入 = 单事务原子写入，失败自动回滚
_BACKUP_TABLES = [
    "competitors", "judges", "events", "event_dances", "event_competitors",
    "score_records", "results", "audit_log", "score_change_log", "file_tiers",
]

_EXPORT_SCHEMA_VERSION = 1


@app.get("/api/export/json")
async def export_json(request: Request = None):
    """全量 JSON 结构化导出（admin）。"""
    require_admin(request)
    conn = db.get_db()
    tables = {}
    for tbl in _BACKUP_TABLES:
        rows = db.rows(conn.execute(f"SELECT * FROM {tbl}").fetchall())
        tables[tbl] = rows
    comp = _active_competition()
    payload = {
        "format": "dancesport-backup",
        "version": _EXPORT_SCHEMA_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "competition": dict(comp) if comp else None,
        "tables": tables,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=None, separators=(",", ":"))
    return Response(content=text.encode(), media_type="application/gzip",
                    headers={"Content-Disposition": 'attachment; filename="dancesport-export.json.gz"',
                             "Content-Encoding": "gzip"})


@app.post("/api/import/json")
async def import_json(request: Request = None):
    """从 JSON 结构化备份原子导入（admin）。单事务，失败全回滚。"""
    require_admin(request)
    body = await request.body()
    try:
        import gzip as _gz
        raw = _gz.decompress(body) if body[:2] == b"\x1f\x8b" else body
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="无法解析备份文件")
    if payload.get("format") != "dancesport-backup" or payload.get("version") != _EXPORT_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="备份格式或版本不匹配")
    tables = payload.get("tables", {})
    conn = db.get_db()
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN TRANSACTION")
        for tbl in reversed(_BACKUP_TABLES):
            conn.execute(f"DELETE FROM {tbl}")
        # 按依赖顺序正向插入
        for tbl in _BACKUP_TABLES:
            rows = tables.get(tbl, [])
            if not rows:
                continue
            cols = list(rows[0].keys())
            ph = ",".join("?" for _ in cols)
            conn.executemany(
                f"INSERT INTO {tbl} ({','.join(cols)}) VALUES ({ph})",
                [[r.get(c) for c in cols] for r in rows])
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        raise HTTPException(status_code=500, detail=f"导入失败已回滚: {e}")
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
    return {"ok": True, "tables": {t: len(tables.get(t, [])) for t in tables}}


@app.get("/api/export/db")
async def export_sqlite(request: Request = None):
    """SQLite 二进制原份导出（admin）。秒级完成，可直接替换恢复。"""
    require_admin(request)
    conn = db.get_db()
    dst = "/tmp/dancesport-export.db"
    if os.path.exists(dst):
        os.remove(dst)
    dst_conn = sqlite3.connect(dst)
    conn.backup(dst_conn)
    dst_conn.close()
    return FileResponse(dst, media_type="application/x-sqlite3",
                        filename=f"dancesport-{time.strftime('%Y%m%d-%H%M%S')}.db")


@app.post("/api/import/db")
async def import_sqlite(request: Request = None):
    """从 SQLite 二进制文件替换整个数据库（admin）。原子替换，失败保留原库。"""
    require_admin(request)
    body = await request.body()
    if len(body) < 100:
        raise HTTPException(status_code=400, detail="文件过小")
    dst_path = DEFAULT_DB
    tmp_path = dst_path + ".import-tmp"
    with open(tmp_path, "wb") as f:
        f.write(body)
    # 验证完整性
    test_conn = sqlite3.connect(tmp_path)
    qc = test_conn.execute("PRAGMA integrity_check").fetchone()[0]
    test_conn.close()
    if qc != "ok":
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail="导入文件完整性校验失败")
    # 关闭现有连接 → 替换文件 → 重启
    # 注意：这会终止所有活动会话，调用方需确认
    os.replace(tmp_path, dst_path)
    for suffix in ("-wal", "-shm"):
        p = dst_path + suffix
        if os.path.exists(p):
            os.remove(p)
    raise HTTPException(status_code=503, detail="数据库已替换，服务即将重启以加载新数据。请稍后刷新页面。")


# ---------------------------------------------- 检录/播报台（主持人 · 检录长/检录员）
@app.get("/staff", response_class=HTMLResponse)
async def staff_page(request: Request):
    """主持台/检录台共用页：赛程 + 逐场检录 + 已完成场次成绩与播报标记。"""
    s = require_staff(request, _current_competition(request).get("id") if _current_competition(request) else None)
    who = s.get("display_name") or s.get("username") or s["role"]
    comp = _current_competition(request)
    conn = db.get_db()
    items = []
    name_by_number = {}
    if comp:
        events = db.rows(conn.execute(
            "SELECT id,code,name,project_code,round,status,announced FROM events "
            "WHERE competition_id=? ORDER BY COALESCE(run_seq, 9999), project_code, round, code",
            (comp["id"],)))
        for ev in events:
            name_by_number = _display_names(conn, comp["id"], ev["project_code"])
            rows = db.rows(conn.execute(
                "SELECT competitor_number, checked_in, checked_by FROM event_competitors "
                "WHERE event_id=? ORDER BY CAST(competitor_number AS INTEGER), competitor_number",
                (ev["id"],)))
            roster = [{"number": r["competitor_number"], "checked": bool(r["checked_in"]),
                       "by": r["checked_by"] or ""} for r in rows]
            item = {"id": ev["id"], "code": ev["code"], "name": ev["name"],
                    "project": ev["project_code"], "round": ev["round"], "status": ev["status"],
                    "announced": bool(ev["announced"]), "roster": roster,
                    "checked_n": sum(1 for x in roster if x["checked"]),
                    "total": len(roster)}
            if ev["status"] in ("calculated", "published"):
                res = load_results(ev["id"])
                item["results"] = (res or {}).get("overall_results", [])
                item["names"] = name_by_number
                item["is_done"] = True
            item["competition_id"] = comp["id"]
            items.append(item)
    return templates.TemplateResponse(request, "staff.html", {
        "request": request, "comp": comp, "items": items, "role": s["role"],
        "who": who})


@app.get("/api/competition-events/{ceid}/checkin")
async def api_checkin_state(ceid: int, request: Request = None):
    """检录状态快照（staff/judge/admin 只读）。供检录台、裁判评分页、控制台做轻量局部
    刷新，避免为一次检录变动整页重载。"""
    s = _session(request)
    if not s or s["role"] not in ("host", "marshal", "judge", "admin"):
        raise HTTPException(status_code=401, detail="需要工作人员或裁判登录")
    ev, comp = _require_active_event(ceid)
    checked = checked_roster(ceid)
    return {"event_id": ceid, "checked": checked,
            "checked_n": len(checked), "total": len(roster(ceid))}


@app.post("/api/competition-events/{ceid}/checkin")
async def api_checkin(ceid: int, request: Request = None):
    """批量检录/撤销检录（主持人或检录长·检录员）。仅接受本场上场名单内的背号。
    已完成计算的场次不再接受检录变动（补录需先由管理员退回）。"""
    s = require_staff(request, _event_or_404(ceid)["competition_id"])
    ev, comp = _require_active_event(ceid)
    if ev["status"] in ("calculated", "published"):
        raise HTTPException(status_code=400, detail="场次已完成计算，检录变动不再生效（如需补录请先退回评分）")
    body = await request.json()
    numbers = [str(x).strip() for x in (body.get("numbers") or [])]
    state = 1 if body.get("state") else 0
    if not numbers:
        raise HTTPException(status_code=400, detail="未提供背号")
    roster_set = set(roster(ceid))
    bad = [n for n in numbers if n not in roster_set]
    if bad:
        raise HTTPException(status_code=400, detail="背号不在本场上场名单内: " + ",".join(bad[:5]))
    conn = db.get_db()
    who = s.get("display_name") or s.get("username") or s["role"]
    for num in numbers:
        conn.execute(
            "UPDATE event_competitors SET checked_in=?, checked_by=?, checked_at=? "
            "WHERE event_id=? AND competitor_number=?",
            (state, who if state else None,
             time.strftime("%Y-%m-%d %H:%M:%S") if state else None, ceid, num))
        # 撤销检录 = 该选手本场退出：其已有评分记录一并作废，保证结果与到场名单一致
        if not state:
            conn.execute(
                "DELETE FROM score_records WHERE event_id=? AND competitor_number=?",
                (ceid, num))
    conn.commit()
    if not state:
        # 撤销检录属敏感操作（连带作废该选手评分），逐次留痕；检录（state=true）量大不记
        _audit(who, "uncheckin", f"event:{ceid}",
               f"{ev['code']} 撤销检录：{','.join(numbers)}", _client_ip(request))
    sse.bus.publish(comp["id"], "checkin_changed",
                    {"event_id": ceid, "count": len(numbers), "state": bool(state)})
    return {"ok": True, "updated": len(numbers),
            "checked_n": len(checked_roster(ceid)), "total": len(roster_set)}


@app.post("/api/competition-events/{ceid}/announce")
async def api_announce(ceid: int, request: Request = None):
    """播报标记（备忘位，可标/可取消，仅 calculated/published 场次，不影响赛程逻辑）。"""
    s = require_staff(request, _event_or_404(ceid)["competition_id"])
    ev, comp = _require_active_event(ceid)
    if ev["status"] not in ("calculated", "published"):
        raise HTTPException(status_code=400, detail="仅已完成计算的场次可标记播报")
    body = await request.json()
    state = 1 if body.get("announced") else 0
    db.get_db().execute("UPDATE events SET announced=? WHERE id=?", (state, ceid))
    db.get_db().commit()
    return {"ok": True, "announced": bool(state)}


# ------------------------------------------------------------------ advancement
@app.get("/api/projects/{project_code}/rounds/{round_no}/advancement-proposal")
async def api_proposal(project_code: str, round_no: int, request: Request = None, competition_id: int = None):
    ca = _compadmin(request)
    if ca:
        comp = _current_competition(request)
        if not comp or comp["id"] != ca["comp_id"]:
            raise HTTPException(status_code=403, detail="赛事管理员仅可操作自己的赛事")
    require_admin(request)
    comp = _current_competition(request)
    cid = competition_id or (comp or {}).get("id")
    if not cid:
        raise HTTPException(status_code=400, detail="无激活赛事")
    return {"proposal": advancement_proposal(cid, project_code, round_no)}


@app.post("/api/projects/{project_code}/rounds/{round_no}/advancement-confirm")
async def api_confirm(project_code: str, round_no: int, request: Request = None):
    ca = _compadmin(request)
    if ca:
        comp = _current_competition(request)
        if not comp or comp["id"] != ca["comp_id"]:
            raise HTTPException(status_code=403, detail="赛事管理员仅可操作自己的赛事")
    require_admin(request)
    comp = _current_competition(request)
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
    # R73 成员信息：每组合行含主报成员与搭档的 (单位, 身份)。身份含「老」=老生（老带新项目老生不计分）。
    comp_rows = db.rows(conn.execute(
        "SELECT number, project_code, unit, partner_unit, role, partner_role FROM competitors WHERE competition_id=?",
        (competition_id,)))
    member_by_key = {}
    for c in comp_rows:
        member_by_key[(c["project_code"], c["number"])] = c
    unit_by_number = {c["number"]: (c["unit"] or "") for c in comp_rows}
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
        pr = ev["project_code"]
        mode = ev["team_mode"] if "team_mode" in ev.keys() else "standard"
        for r in data.get("overall_results") or []:
            num = str(r["competitor_number"])
            m = member_by_key.get((pr, num))
            u1 = (m["unit"] or "").strip() if m else unit_by_number.get(num, "")
            u2 = (m["partner_unit"] or "").strip() if m else ""
            r1 = (m["role"] or "").strip() if m else ""
            r2 = (m["partner_role"] or "").strip() if m else ""
            if mode == "freshman_half":
                # 老带新：均分只在新生成员间进行（各 0.5），老生权重 0；身份未填按新生处理
                parts = []
                if not ("老" in r1):
                    parts.append((u1, 0.5))
                if u2 and not ("老" in r2):
                    parts.append((u2 if u2 else u1, 0.5))
                if not parts:
                    continue   # 全老生组合：不计分
                # 同单位聚合（两新生同院 → 该院 1.0）
                agg = {}
                for u, sh in parts:
                    agg[u] = agg.get(u, 0.0) + sh
                for u, sh in agg.items():
                    entries.append({"project": pr, "number": num, "unit": u, "rank": r["rank"], "share": sh})
            else:
                # 标准（含跨学院平分）：组合总分均分给成员——同学院聚合=全额，跨学院各 0.5
                agg = {u1: 1.0}
                if u2 and u2 != u1:
                    agg = {u1: 0.5, u2: 0.5}
                for u, sh in agg.items():
                    entries.append({"project": pr, "number": num, "unit": u, "rank": r["rank"], "share": sh})
    from core.team_standing import compute_team_standings
    return compute_team_standings(entries)


@app.get("/api/events/{competition_id}/team-standings")
async def api_team_standings_admin(competition_id: int, request: Request = None):
    require_admin(request)
    return _team_standings(competition_id, published_only=False)


# ------------------------------------------------------------------ webui v1 pages
@app.get("/events/{competition_id}/advancement", response_class=HTMLResponse)
async def advancement_page(request: Request, competition_id: int):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    projects = [r["project_code"] for r in db.rows(conn.execute(
        "SELECT DISTINCT project_code FROM events WHERE competition_id=? ORDER BY project_code", (competition_id,)))]
    project = request.query_params.get("project") or (projects[0] if projects else "")
    rounds = [r["round"] for r in db.rows(conn.execute(
        "SELECT DISTINCT round FROM events WHERE competition_id=? AND project_code=? ORDER BY round", (competition_id, project)))]
    try: rnd = int(request.query_params.get("round") or (rounds[-1] if rounds else 1))
    except ValueError: rnd = rounds[-1] if rounds else 1
    proposal = []
    status = ""
    try:
        proposal = advancement_proposal(competition_id, project, rnd)
    except Exception:
        pass
    next_exists = bool(conn.execute(
        "SELECT 1 FROM events WHERE competition_id=? AND project_code=? AND round=? LIMIT 1",
        (competition_id, project, rnd + 1)).fetchone())
    return templates.TemplateResponse(request, "advancement.html", {
        "request": request, "comp": comp, "projects": projects, "project": project,
        "rounds": rounds, "round": rnd, "proposal": proposal,
        "adv": conn.execute("SELECT COALESCE(MAX(advancement_count),0) a FROM events WHERE competition_id=? AND project_code=? AND round=?",
                            (competition_id, project, rnd)).fetchone()["a"],
        "next_exists": next_exists,
    })


@app.get("/events/{competition_id}/teams", response_class=HTMLResponse)
async def teams_page(request: Request, competition_id: int):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    teams = db.rows(conn.execute(
        "SELECT number, name, unit, project_code FROM competitors WHERE competition_id=? AND number LIKE 'T%' ORDER BY number",
        (competition_id,)))
    unit_stats = db.rows(conn.execute(
        "SELECT unit, COUNT(*) AS pairs FROM competitors WHERE competition_id=? AND number NOT LIKE 'T%' AND unit<>'' GROUP BY unit ORDER BY pairs DESC",
        (competition_id,)))
    return templates.TemplateResponse(request, "teams.html", {
        "request": request, "comp": comp, "teams": teams, "unit_stats": unit_stats})


@app.get("/events/{competition_id}/screen-control", response_class=HTMLResponse)
async def screen_control_page(request: Request, competition_id: int):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    return templates.TemplateResponse(request, "screen_control.html", {
        "request": request, "comp": comp, "mode": SCREEN_CONTROL.get("mode", "auto")})


@app.get("/events/{competition_id}/team-standings", response_class=HTMLResponse)
async def team_standings_admin_page(request: Request, competition_id: int, best: str = ""):
    require_admin(request)
    comp = _comp_or_404(competition_id)
    best_n = int(best) if best.isdigit() and int(best) > 0 else None
    conn = db.get_db()
    from core.team_standing import compute_team_standings
    events = db.rows(conn.execute(
        "SELECT * FROM events WHERE competition_id=? AND status IN ('calculated','published') ORDER BY project_code, round, code",
        (competition_id,)))
    # R73 成员信息：每组合行含主报成员与搭档的 (单位, 身份)。身份含「老」=老生（老带新项目老生不计分）。
    comp_rows = db.rows(conn.execute(
        "SELECT number, project_code, unit, partner_unit, role, partner_role FROM competitors WHERE competition_id=?",
        (competition_id,)))
    member_by_key = {}
    for c in comp_rows:
        member_by_key[(c["project_code"], c["number"])] = c
    unit_by_number = {c["number"]: (c["unit"] or "") for c in comp_rows}
    entries = []
    last_round = {}
    with_results = []
    for ev in events:
        data = load_results(ev["id"])
        if data and data.get("overall_results"):
            with_results.append((ev, data))
            if ev["project_code"] not in last_round or ev["round"] > last_round[ev["project_code"]]:
                last_round[ev["project_code"]] = ev["round"]
    for ev, data in with_results:
        if ev["round"] != last_round[ev["project_code"]]:
            continue
        for r in data["overall_results"]:
            num = str(r["competitor_number"])
            entries.append({"project": ev["project_code"], "number": num,
                            "unit": unit_by_number.get(num, ""), "rank": r["rank"]})
    standings = compute_team_standings(entries, best_n=best_n)
    return templates.TemplateResponse(request, "team_standings.html", {
        "request": request, "comp": comp, "standings": standings, "best_n": best_n})


@app.api_route("/public/team-standings", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def team_standings_public_page(request: Request):
    comp = _current_competition(request)
    fp = _public_fingerprint(comp["id"]) if comp else 'W/"0-0-0"'
    if not comp:
        return _etag_page(request, 0, "standings", fp, lambda: templates.TemplateResponse(
            request, "public_team_standings.html",
            {"request": request, "comp": None, "standings": {"standings": []}}))
    return _etag_page(request, comp["id"], "standings", fp, lambda: templates.TemplateResponse(
        request, "public_team_standings.html", {
        "request": request, "comp": comp,
        "standings": _team_standings(comp["id"], published_only=True)}))


@app.get("/api/screen-control")
async def api_screen_control_get(request: Request = None):
    return {"mode": SCREEN_CONTROL.get("mode", "auto")}


@app.post("/api/events/{competition_id}/auto-publish")
async def api_auto_publish(competition_id: int, request: Request = None):
    """R57 自动发布开关：收齐自动算分后直接发布（按赛事配置）。"""
    require_admin(request)
    comp = _comp_or_404(competition_id)
    ca = _compadmin(request)
    if ca and ca["comp_id"] != competition_id:
        raise HTTPException(status_code=403, detail="赛事管理员仅可操作自己的赛事")
    body = await request.json()
    val = 1 if body.get("auto_publish") else 0
    db.get_db().execute("UPDATE competitions SET auto_publish=? WHERE id=?", (val, competition_id))
    db.get_db().commit()
    return {"ok": True, "auto_publish": bool(val)}


@app.post("/api/screen-control")
async def api_screen_control_set(request: Request = None):
    require_admin(request)
    body = await request.json()
    mode = body.get("mode")
    if mode not in ("auto", "scoring", "results", "standings", "welcome"):
        raise HTTPException(status_code=400, detail="未知大屏模式")
    SCREEN_CONTROL["mode"] = mode
    if SCREEN_CONTROL.get("comp_id"):
        sse.bus.publish(SCREEN_CONTROL["comp_id"], "screen_state_changed", {"mode": mode})
    return {"ok": True, "mode": mode}


@app.get("/api/competition-events/{ceid}/skating-table")
async def api_skating_table(ceid: int, request: Request = None):
    """滑冰法判定明细表（桌面版核心功能移植，FR-E1/E4）：分舞种
    各裁判名次 → 1~N 票数 → 累计票 → 序和 → 多数裁决名次 → 最终名次。仅管理端。"""
    require_admin(request)
    ev = _event_or_404(ceid)
    res = load_results(ceid)
    if not res:
        raise HTTPException(status_code=404, detail="尚未计算")
    if scoring_kind(ev) != "skating":
        raise HTTPException(status_code=400, detail="滑冰法判定明细仅顺位法场次生成（Mark制/评分制无此表）")
    details = res.get("score_details") or {}
    if not details:
        raise HTTPException(status_code=400, detail="该场次无滑冰法判定明细")
    names = _display_names(db.get_db(), ev["competition_id"], ev["project_code"])
    dances = {}
    for dance, comp_map in details.items():
        judges = []
        for d in comp_map.values():
            judges = sorted((d.get("judge_placements") or {}).keys())
            if judges:
                break
        rows = []
        for number, d in sorted(comp_map.items(), key=lambda kv: kv[1].get("final_rank", 99)):
            rows.append({
                "number": str(number), "name": names.get(str(number), ""),
                "placements": d.get("judge_placements") or {},
                "counts": {str(k): v for k, v in (d.get("placement_counts") or {}).items()},
                "cum": {str(k): v for k, v in (d.get("cumulative_votes") or {}).items()},
                "sum": d.get("sum_placement", 0),
                "majority": d.get("majority_rank"),
                "rank": d.get("final_rank", 0),
            })
        dances[dance] = {"judges": judges, "rows": rows}
    overall = None
    od = res.get("overall_score_details") or {}
    if od:
        overall = {str(num): {"total_sum": d.get("total_sum_placement", 0),
                              "rank": d.get("final_rank", 0)} for num, d in od.items()}
    return {"event": ev["code"], "name": ev["name"], "dances": dances, "overall": overall}


def _render_detail_markdown(competition_id, published_only):
    """明细表导出（Markdown）：已发布/全部已计算场次的滑冰法判定表。"""
    conn = db.get_db()
    q = "SELECT * FROM events WHERE competition_id=? AND status IN ('calculated','published')"
    if published_only:
        q += " AND published=1"
    evs = db.rows(conn.execute(q + " ORDER BY project_code, round, code", (competition_id,)))
    comp = _comp_or_404(competition_id)
    lines = [f"# {comp['name']} 判定明细表", ""]
    for ev in evs:
        names = _display_names(conn, competition_id, ev["project_code"])
        if scoring_kind(ev) != "skating":
            continue
        res = load_results(ev["id"])
        details = (res or {}).get("score_details") or {}
        if not details:
            continue
        lines.append(f"## {ev['name']}（{ev['project_code']} 第{ev['round']}轮 · {ev['scoring_type']}）")
        lines.append("")
        for dance, comp_map in details.items():
            judges = sorted({j for d in comp_map.values() for j in (d.get("judge_placements") or {})})
            positions = sorted({str(p) for d in comp_map.values() for p in (d.get("placement_counts") or {})},
                               key=lambda x: int(x))
            head = "| 名次 | 背番号 | 姓名 | " + " | ".join(judges) + " | " + " | ".join(f"{p}票" for p in positions) + " | 序和 | 多数 |"
            lines += [head, "|" + "---|" * (4 + len(judges) + len(positions) + 2)]
            for number, d in sorted(comp_map.items(), key=lambda kv: kv[1].get("final_rank", 99)):
                pl = d.get("judge_placements") or {}
                cnt = d.get("placement_counts") or {}
                cells = [str(pl.get(j, "-")) for j in judges] + [str(cnt.get(p, 0)) for p in positions]
                lines.append("| " + " | ".join([str(d.get("final_rank", "")), str(number), names.get(str(number), "")] + cells + [str(d.get("sum_placement", 0)), str(d.get("majority_rank") or "-")]) + " |")
            lines.append("")
    return chr(10).join(lines)


@app.get("/api/events/{competition_id}/detail-exports")
async def api_detail_exports(competition_id: int, request: Request = None, format: str = "markdown"):
    """判定明细表导出（桌面版核心功能）：markdown / csv。"""
    require_admin(request)
    md = _render_detail_markdown(competition_id, published_only=False)
    if format == "markdown":
        return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")
    if format == "csv":
        import csv as _csv, io as _io
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["场次", "舞种", "名次", "背番号", "姓名", "序和", "多数裁决"] +
                   [f"裁判{j}" for j in range(1, 16)])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8")
    raise HTTPException(status_code=400, detail="未知格式")


@app.get("/api/competition-events/{ceid}/detail-scores")
async def api_detail_scores(ceid: int, request: Request = None):
    """FR-E4 评分明细：仅管理端。返回每裁判×每选手原始打分。"""
    require_admin(request)
    ev = _event_or_404(ceid)
    rows = db.rows(db.get_db().execute(
        "SELECT judge_code, competitor_number, dance_name, mark, placement FROM score_records WHERE event_id=? ORDER BY dance_name, competitor_number, judge_code",
        (ceid,)))
    names = _display_names(db.get_db(), ev["competition_id"], ev["project_code"])
    return {"event": ev["code"], "records": [
        {"judge": r["judge_code"], "number": r["competitor_number"],
         "name": names.get(r["competitor_number"], ""), "dance": r["dance_name"],
         "mark": r["mark"], "placement": r["placement"]} for r in rows]}


# ------------------------------------------------------------------ public API
def _public_payload(comp=None):
    """公开数据载荷。comp 缺省时回落全局激活赛事；
    调用方持有明确赛事（如按 id 的公开端点）时必须显式传入。"""
    comp = comp or _active_competition()
    if not comp:
        return None
    events = db.rows(db.get_db().execute(
        "SELECT code,name,project_code,round,status,published,id FROM events WHERE competition_id=? "
        "ORDER BY COALESCE(run_seq, 9999), project_code, round, code",
        (comp["id"],)))
    published = []
    for ev in events:
        name_by_number = _display_names(db.get_db(), comp["id"], ev["project_code"])
        if ev["published"]:
            res = load_results(ev["id"])
            if res:
                rows = []
                for r in res["overall_results"]:
                    r = dict(r)
                    r["competitor_name"] = name_by_number.get(str(r["competitor_number"]), "")
                    rows.append(r)
                published.append({"code": ev["code"], "name": ev["name"], "project": ev["project_code"],
                                  "round": ev["round"], "results": rows})
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
    comp = _current_competition(request)
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
    payload = _public_payload(comp) or {"published_results": [], "events": []}
    if payload.get("competition"):
        SCREEN_CONTROL["comp_id"] = payload["competition"]["id"]
    return {"competition": payload["competition"], "scoring_now": scoring,
            "published_results": payload["published_results"],
            "team_standings": _team_standings(comp["id"], published_only=True),
            "forced_mode": SCREEN_CONTROL.get("mode", "auto"),
            "updated_at": int(time.time())}


# ------------------------------------------------- run order（防连场编排，FR-J 系增强）
def _roster_set(ceid):
    return {r["competitor_number"] for r in db.rows(db.get_db().execute(
        "SELECT competitor_number FROM event_competitors WHERE event_id=?", (ceid,)))}


def _pending_events(competition_id):
    return db.rows(db.get_db().execute(
        "SELECT id,code,name,project_code,round,run_seq FROM events "
        "WHERE competition_id=? AND status='pending' "
        "ORDER BY COALESCE(run_seq, 9999), project_code, round, code",
        (competition_id,)))


@app.get("/api/events/{competition_id}/run-order")
async def api_run_order_get(competition_id: int, request: Request = None):
    """当前已保存的比赛顺序（仅待赛场次）；roster 供前端重排时自算连场数。"""
    require_admin(request)
    _comp_or_404(competition_id)
    items = []
    for e in _pending_events(competition_id):
        rs = _roster_set(e["id"])
        items.append({"ceid": e["id"], "code": e["code"], "name": e["name"],
                      "project": e["project_code"], "round": e["round"],
                      "run_seq": e["run_seq"], "roster": sorted(rs)})
    return {"order": items}


@app.get("/api/events/{competition_id}/run-order/proposal")
async def api_run_order_proposal(competition_id: int, request: Request = None):
    """防连场自动排序建议：尊重同项目轮次依赖（轮次未齐不得跳轮），
    贪心选择与上一场选手重叠最小的场次；首场取人数最少者降低开场压力。"""
    require_admin(request)
    _comp_or_404(competition_id)
    pending = _pending_events(competition_id)
    rosters = {e["id"]: _roster_set(e["id"]) for e in pending}
    pending_pr = {}
    for e in pending:
        pending_pr[(e["project_code"], e["round"])] = pending_pr.get((e["project_code"], e["round"]), 0) + 1
    order, overlaps = [], []
    last = set()
    remaining = {e["id"]: e for e in pending}
    while remaining:
        ready = [e for e in remaining.values()
                 if all(pending_pr.get((e["project_code"], r), 0) == 0
                        for r in range(1, e["round"]))]
        if not ready:
            ready = list(remaining.values())   # 依赖兜底（不应发生）
        if last:
            best = min(ready, key=lambda e: (len(rosters[e["id"]] & last), e["round"], e["project_code"], e["code"]))
        else:
            best = min(ready, key=lambda e: (e["round"], len(rosters[e["id"]]), e["project_code"], e["code"]))
        order.append(best)
        overlaps.append(len(rosters[best["id"]] & last) if last else 0)
        last = rosters[best["id"]]
        pr = (best["project_code"], best["round"])
        pending_pr[pr] -= 1
        del remaining[best["id"]]
    items = [{"ceid": e["id"], "code": e["code"], "name": e["name"], "project": e["project_code"],
              "round": e["round"], "roster": sorted(rosters[e["id"]])} for e in order]
    return {"order": items, "overlaps": overlaps}


@app.post("/api/events/{competition_id}/run-order")
async def api_run_order_save(competition_id: int, request: Request = None):
    """保存（或清空）比赛顺序；仅接受本赛事 pending 场次。"""
    require_admin(request)
    comp = _comp_or_404(competition_id)
    body = await request.json()
    order = [int(x) for x in (body.get("order") or [])]
    conn = db.get_db()
    conn.execute("UPDATE events SET run_seq=NULL WHERE competition_id=?", (comp["id"],))
    for pos, ceid in enumerate(order, 1):
        conn.execute("UPDATE events SET run_seq=? WHERE id=? AND competition_id=? AND status='pending'",
                     (pos, ceid, comp["id"]))
    conn.commit()
    return {"ok": True, "saved": len(order)}


@app.get("/api/public/events/{competition_id}/exports/runsheet")
async def api_runsheet_export(competition_id: int, request: Request = None, format: str = "html", seed: str = ""):
    """R72 赛程总表（出场单）：所有能确认参赛选手的场次（预赛/单轮决赛；待回填决赛无名单不列），
    每场含全部参赛选手。打乱机制：出场顺序按 seed 随机抽签——同 seed 可复现（公平可审计），
    换 seed 即重抽；每场用 seed+场次码 派生独立流，场间互不影响。"""
    import random
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    seed = (seed or "").strip() or time.strftime("%Y%m%d")
    evs = db.rows(conn.execute(
        "SELECT * FROM events WHERE competition_id=? "
        "ORDER BY COALESCE(run_seq, 9999), project_code, round, code", (competition_id,)))
    blocks = []
    for ev in evs:
        roster = db.rows(conn.execute(
            "SELECT competitor_number FROM event_competitors WHERE event_id=? ORDER BY id", (ev["id"],)))
        if not roster:
            continue   # 待回填决赛等无名单场次不列
        names = _display_names(conn, competition_id, ev["project_code"])
        unit_by_number = {c["number"]: (c["unit"] or "") for c in db.rows(conn.execute(
            "SELECT number, unit FROM competitors WHERE competition_id=?", (competition_id,)))}
        rng = random.Random("{0}:{1}".format(seed, ev["code"]))
        nums = [r["competitor_number"] for r in roster]
        rng.shuffle(nums)
        dancers = "; ".join(sorted({(ev["dances"] or "") for _ in [0]})) if False else None
        blocks.append({"ev": ev, "nums": nums, "names": names, "units": unit_by_number})

    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["出场序", "场次编号", "场次名称", "背番号", "选手 / 组合", "单位"])
        for bi, b in enumerate(blocks, 1):
            ev = b["ev"]
            for oi, num in enumerate(b["nums"], 1):
                w.writerow([oi, ev["code"], ev["name"], num,
                            b["names"].get(num, ""), b["units"].get(num, "")])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": 'attachment; filename="runsheet-{0}-{1}.csv"'.format(competition_id, seed)})

    # html：每场一块出场单（打印友好）
    body = []
    for bi, b in enumerate(blocks, 1):
        ev = b["ev"]
        rows = "".join("<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
            oi, num, b["names"].get(num, ""), b["units"].get(num, "")) for oi, num in enumerate(b["nums"], 1))
        body.append("<h2>{0}. {1}（{2} · {3}）</h2>"
                    "<p class='muted'>出场序抽签 seed：{4}（同 seed 可复现）</p>"
                    "<table><tr><th>出场</th><th>背番号</th><th>选手 / 组合</th><th>单位</th></tr>{5}</table>".format(
                        bi, ev["name"], ev["code"], ev["scoring_type"], seed, rows))
    css = ("body{font-family:sans-serif;margin:2em}"
           "table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:5px 10px;text-align:left}"
           "th{background:#f5f3ef}h2{margin-top:1.6em}"
           ".muted{color:#6b7280;font-size:.85em}")
    html = ("<!doctype html><html><head><meta charset='utf-8'><title>" + comp["name"] + " 赛程总表</title>"
            "<style>" + css + "</style></head><body>"
            "<h1>" + comp["name"] + " 赛程总表（出场序抽签）</h1>"
            "<p class='muted'>抽签 seed：" + seed + " · 打印日期：" + time.strftime("%Y-%m-%d %H:%M") + " · dancetkt.com</p>"
            + "".join(body) + "</body></html>")
    return HTMLResponse(html)


@app.get("/api/events/{competition_id}/exports/competitors")
async def api_competitors_export(competition_id: int, request: Request = None, format: str = "csv"):
    """R71f 选手信息导出（管理端）：与导入模板同列序，可直接回导（导出→修改→再导入闭环）。"""
    require_admin(request)
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    rows = db.rows(conn.execute(
        "SELECT number, project_code, name, partner, partner_unit, unit FROM competitors WHERE competition_id=? "
        "ORDER BY project_code, CAST(number AS INTEGER), number", (competition_id,)))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["背番号", "项目编号", "姓名", "搭档姓名", "搭档单位", "学校/单位"])
    for r in rows:
        w.writerow([r["number"], r["project_code"], r["name"], r["partner"] or "",
                    r["partner_unit"] or "", r["unit"] or ""])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="competitors-{0}.csv"'.format(competition_id)})


@app.get("/api/public/events/{competition_id}/exports/schedule")
async def api_public_schedule_export(competition_id: int, format: str = "html", unit: str = ""):
    """R70 材料生产：赛程表导出（秩序册）。全场或按单位过滤；HTML 打印友好，Markdown 供再编辑。
    公开口径：只含赛程信息（场次/项目/舞种/制式/上场名单），不含成绩。"""
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    unit = (unit or "").strip()
    evs = db.rows(conn.execute(
        "SELECT * FROM events WHERE competition_id=? ORDER BY (run_seq IS NULL), run_seq, code",
        (competition_id,)))
    # 团体分/秩序册单位归属 = 主报单位（背番号持有者的单位；跨单位搭档整对归一处）
    unit_by_number = {c["number"]: c["unit"] for c in db.rows(conn.execute(
        "SELECT number, unit FROM competitors WHERE competition_id=?", (competition_id,)))}

    def _roster_line(ev):
        name_by_number = _display_names(conn, competition_id, ev["project_code"])
        nums = [r["competitor_number"] for r in db.rows(conn.execute(
            "SELECT competitor_number FROM event_competitors WHERE event_id=? ORDER BY id", (ev["id"],)))]
        pairs = []
        for n in nums:
            if unit and unit_by_number.get(n, "") != unit:
                continue
            pairs.append("{0} {1}".format(n, name_by_number.get(n, "")))
        return "、".join(pairs) if pairs else ""

    blocks = []
    for i, ev in enumerate(evs, 1):
        line = _roster_line(ev)
        if unit and not line:
            continue   # 按单位过滤：本单位无选手的场次不列
        ev = dict(ev)
        ev["dances"] = " / ".join(dances_of(ev["id"]))   # events 表无 dances 列，取自 event_dances
        blocks.append({"seq": i, "ev": ev, "roster": line})

    if format == "markdown":
        lines = ["# {0} 赛程表{1}".format(comp["name"], (" · " + unit) if unit else ""), ""]
        for b in blocks:
            ev = b["ev"]
            lines.append("## {0}. {1}（{2} 第{3}轮 · {4} · {5}）".format(
                b["seq"], ev["name"], ev["project_code"], ev["round"], ev["dances"], ev["scoring_type"]))
            lines.append("上场名单：{0}".format(b["roster"] or "—"))
            lines.append("")
        return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8")
    elif format == "html":
        body = []
        for b in blocks:
            ev = b["ev"]
            body.append(
                "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3} 第{4}轮</td><td>{5}</td><td>{6}</td><td>{7}</td></tr>".format(
                    b["seq"], ev["code"], ev["name"], ev["project_code"], ev["round"],
                    ev["dances"], ev["scoring_type"], b["roster"] or "—"))
        css = ("body{font-family:sans-serif;margin:2em}"
               "table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:6px 10px;text-align:left}"
               "th{background:#f5f3ef}")
        html = ("<!doctype html><html><head><meta charset='utf-8'><title>" + comp["name"] + " 赛程表"
                + (" · " + unit if unit else "") + "</title><style>" + css + "</style></head><body>"
                "<h1>" + comp["name"] + " 赛程表" + (" · " + unit if unit else "") + "</h1>"
                "<table><tr><th>序</th><th>场次</th><th>名称</th><th>项目/轮次</th><th>舞种</th><th>评分制式</th><th>上场名单</th></tr>"
                + "".join(body) + "</table>"
                "<p class=\"muted\" style=\"color:#6b7280\">打印日期：" + time.strftime("%Y-%m-%d %H:%M") + " · dancetkt.com</p>"
                "</body></html>")
        return HTMLResponse(html)
    raise HTTPException(status_code=400, detail="未知格式")


@app.get("/api/public/events/{competition_id}/lookup")
async def api_public_lookup(competition_id: int, num: str = ""):
    """按背番号查询公示信息（姓名/单位/参赛项目/已发布成绩）。"""
    comp = _comp_or_404(competition_id)
    num = (num or "").strip()
    if not num:
        raise HTTPException(status_code=400, detail="请输入背番号")
    conn = db.get_db()
    c = db.rowdict(conn.execute(
        "SELECT number,name,partner,unit FROM competitors WHERE competition_id=? AND number=?",
        (comp["id"], num)).fetchone())
    if not c:
        raise HTTPException(status_code=404, detail="未找到该背番号")
    partner = (c["partner"] or "").strip()
    display_name = ((c["name"] or "").strip() + (" / " + partner if partner else ""))
    projects = sorted({r["project_code"] for r in db.rows(conn.execute(
        "SELECT DISTINCT e.project_code AS project_code FROM event_competitors ec "
        "JOIN events e ON e.id=ec.event_id WHERE e.competition_id=? AND ec.competitor_number=?",
        (comp["id"], num)))})
    results = []
    for p in (_public_payload(comp) or {}).get("published_results", []):
        for r in p["results"]:
            if str(r["competitor_number"]) == num:
                results.append({"code": p["code"], "name": p["name"], "round": p["round"],
                                "rank": r["rank"], "total_score": r["total_score"]})
    # R70 选手自助赛程：全部参赛场次按出场序，状态公开口径（未发布成绩只示状态不示名次）
    st_names = {"pending": "待开赛", "scoring": "评分中", "calculated": "成绩整理中", "published": "已发布"}
    ev_rows = db.rows(conn.execute(
        "SELECT e.id, e.code, e.name, e.project_code, e.round, e.scoring_type, e.status, e.run_seq, "
        "(SELECT group_concat(name, ' / ') FROM (SELECT name FROM event_dances WHERE event_id=e.id ORDER BY ord)) AS dances "
        "FROM event_competitors ec JOIN events e ON e.id=ec.event_id "
        "WHERE e.competition_id=? AND ec.competitor_number=? "
        "ORDER BY (e.run_seq IS NULL), e.run_seq, e.code", (comp["id"], num)))
    schedule = []
    for ev in ev_rows:
        # 晋级判定：本场为预赛轮且同项目存在下一轮、且选手在下一轮上场名单中
        adv = None
        if ev["round"] == 1 and ev["status"] == "published":
            nxt = db.rowdict(conn.execute(
                "SELECT id FROM events WHERE competition_id=? AND project_code=? AND round=2",
                (comp["id"], ev["project_code"])).fetchone())
            if nxt:
                in_next = conn.execute(
                    "SELECT 1 FROM event_competitors WHERE event_id=? AND competitor_number=?",
                    (nxt["id"], num)).fetchone()
                adv = bool(in_next)
        schedule.append({"code": ev["code"], "name": ev["name"], "round": ev["round"],
                         "dance": ev["dances"], "scoring_type": ev["scoring_type"],
                         "status": ev["status"], "status_label": st_names.get(ev["status"], ev["status"]),
                         "advancement": adv})
    return {"number": c["number"], "name": display_name, "partner": partner, "unit": c["unit"],
            "projects": projects, "published_results": results, "schedule": schedule,
            "note": "公示口径：仅姓名、单位、赛程状态与已发布成绩"}


# ------------------------------------------------------------------ SSE
@app.get("/api/events/{competition_id}/stream")
async def api_stream(competition_id: int, request: Request = None):
    _comp_or_404(competition_id)
    q = sse.bus.subscribe(competition_id)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            # 连接/重连即推状态同步事件：重连客户端若错过离线期间的一次性变更，
            # 依赖此快照触发各自 refresh()（base 页不监听此事件，避免重载循环）
            yield "event: state_sync\ndata: {\"ts\": 1}\n\n"
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
async def api_export(competition_id: int, request: Request = None, format: str = "markdown", code: str = ""):
    """成绩单导出（markdown/html）。管理员=全部已发布；主持/检录角色可下载，
    带 code 参数可导出单场（含未发布但已计算的场次，供成绩播报使用）。"""
    s = _session(request)
    if not s or s["role"] not in ("admin", "host", "marshal"):
        raise HTTPException(status_code=401, detail="需要登录")
    comp = _comp_or_404(competition_id)
    conn = db.get_db()
    code = (code or "").strip()
    if code:
        evs = db.rows(conn.execute(
            "SELECT * FROM events WHERE competition_id=? AND code=? AND status IN ('calculated','published')",
            (competition_id, code)))
        if not evs:
            raise HTTPException(status_code=404, detail="场次不存在或未完成计算")
    else:
        evs = db.rows(conn.execute(
            "SELECT * FROM events WHERE competition_id=? AND published=1 ORDER BY project_code, round, code",
            (competition_id,)))

    def _rows(res):
        out = []
        for r in res["overall_results"]:
            nm = name_by_number.get(str(r["competitor_number"]), "")
            out.append((r["rank"], r["competitor_number"], nm, r["total_score"]))
        return out

    if format == "markdown":
        lines = ["# {0} 成绩".format(comp["name"]), ""]
        for ev in evs:
            name_by_number = _display_names(conn, competition_id, ev["project_code"])
            res = load_results(ev["id"])
            if not res:
                continue
            lines.append("## {0}（{1} 第{2}轮）".format(ev["name"], ev["project_code"], ev["round"]))
            lines.append("| 名次 | 背番号 | 选手 / 队伍 | 总分 |")
            lines.append("|---|---|---|---|")
            for rank, num, nm, total in _rows(res):
                lines.append("| {0} | {1} | {2} | {3} |".format(rank, num, nm, total))
            lines.append("")
        return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8")
    elif format == "html":
        rows_html = []
        for ev in evs:
            name_by_number = _display_names(conn, competition_id, ev["project_code"])
            res = load_results(ev["id"])
            if not res:
                continue
            body = "".join("<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
                rank, num, nm, total) for rank, num, nm, total in _rows(res))
            rows_html.append("<h2>{0}（{1} 第{2}轮）</h2><table><tr><th>名次</th><th>背番号</th><th>选手 / 队伍</th><th>总分</th></tr>{3}</table>".format(
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
def _hash_pw(pw: str, salt: str = None) -> str:
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), 600_000)
    return salt + "$" + h.hex()


def _verify_pw(pw: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
        return hmac.compare_digest(_hash_pw(pw, salt), stored)
    except ValueError:
        return False


def _actor_name(s):
    """审计操作人：账号制会话取显示名/用户名，其余回落到角色（admin 无账号表）。"""
    if not s:
        return "?"
    return s.get("display_name") or s.get("username") or s.get("role") or "?"


def _client_ip(request: Request):
    return request.client.host if request.client else "?"


def _audit(actor, action, target="", detail="", ip=""):
    """敏感操作留痕（R47）。审计失败不阻塞业务操作。"""
    try:
        db.get_db().execute(
            "INSERT INTO audit_log(actor, action, target, detail, ip) VALUES(?,?,?,?,?)",
            (str(actor)[:80], str(action)[:40], str(target)[:120], str(detail)[:300], str(ip)[:64]))
        db.get_db().commit()
    except Exception:
        pass


def _seed_default_accounts():
    """首次启动播种：host/marshal 角色至少各有一个默认账号（口令取环境变量），
    使旧部署在切换到账号制后仍可登录。管理员保持环境变量超管口令，不入表。"""
    conn = db.get_db()
    for role, username, env_key, default in (
        ("host", "host", "DSPORT_HOST_PASSWORD", "host123"),
        ("marshal", "marshal", "DSPORT_MARSHAL_PASSWORD", "marshal123"),
    ):
        if not conn.execute("SELECT 1 FROM users WHERE role=? LIMIT 1", (role,)).fetchone():
            conn.execute(
                "INSERT OR IGNORE INTO users(username, pw_hash, role, display_name) VALUES(?,?,?,?)",
                (username, _hash_pw(os.environ.get(env_key, default)), role,
                 "主持人（默认）" if role == "host" else "检录长（默认）"))
    conn.commit()


# ================================================================
# R43 文件分层托管：分层（tier）+ 权限（public 公开 / token 凭证 / admin 管理员）
# 上传走 API（admin 会话或层 Bearer 凭证），下载链接可直接分发。
# 文件落盘 webapp/data/files/<tier>/<filename>（data/ 已不入库不入 git）。
# ================================================================
FILES_ROOT = os.environ.get("DSPORT_FILES_DIR", os.path.join(BASE, "..", "data", "files"))
FILES_ROOT = os.path.abspath(FILES_ROOT)
MAX_UPLOAD = int(os.environ.get("DSPORT_MAX_UPLOAD_MB", "200")) * 1024 * 1024
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def _slug_ok(s: str) -> bool:
    return bool(_SLUG_RE.match(s or "")) and ".." not in s


def _tier_by_name(name: str):
    return db.rowdict(db.get_db().execute(
        "SELECT * FROM file_tiers WHERE name=?", (name,)).fetchone())


def _tier_token_ok(request: Request, tier) -> bool:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    raw = auth[7:].strip()
    return bool(tier["token_hash"]) and _verify_pw(raw, tier["token_hash"])


def _file_write_ok(request: Request, tier) -> bool:
    s = _session(request)
    if s and s["role"] == "admin":
        return True
    return tier["perm"] in ("public", "token") and _tier_token_ok(request, tier)


@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    """文件分发管理页（管理员）。"""
    require_admin(request)
    tiers = db.rows(db.get_db().execute("SELECT * FROM file_tiers ORDER BY id"))
    out = []
    for tr in tiers:
        fs = db.rows(db.get_db().execute(
            "SELECT filename, size, downloads, updated_at FROM file_objects WHERE tier_id=? ORDER BY updated_at DESC",
            (tr["id"],)))
        out.append({"tier": tr, "files": fs})
    return templates.TemplateResponse(request, "files.html",
                                      {"request": request, "tiers": out})


@app.post("/api/files/tiers")
async def files_tier_create(request: Request):
    """创建分层。body: {name, perm: public|token|admin, token?, note?}
    perm=token 时若未提供 token 则自动生成并【一次性】返回明文（服务端只存哈希）。"""
    require_admin(request)
    body = await request.json()
    name = str(body.get("name") or "").strip()
    perm = str(body.get("perm") or "public").strip()
    note = str(body.get("note") or "")[:200]
    token = str(body.get("token") or "")
    if not _slug_ok(name):
        raise HTTPException(status_code=400, detail="层名须为字母/数字/._- 开头字母或数字，≤80 字符")
    if perm not in ("public", "token", "admin"):
        raise HTTPException(status_code=400, detail="perm 须为 public/token/admin")
    if _tier_by_name(name):
        raise HTTPException(status_code=400, detail="层名已存在")
    token_hash = ""
    gen_token = ""
    if perm == "token":
        gen_token = token or secrets.token_urlsafe(18)
        if len(gen_token) < 8:
            raise HTTPException(status_code=400, detail="token 至少 8 位")
        token_hash = _hash_pw(gen_token)
    elif token:
        token_hash = _hash_pw(token)
    conn = db.get_db()
    conn.execute("INSERT INTO file_tiers(name, perm, token_hash, note) VALUES(?,?,?,?)",
                 (name, perm, token_hash, note))
    conn.commit()
    os.makedirs(os.path.join(FILES_ROOT, name), exist_ok=True)
    out = {"ok": True, "name": name, "perm": perm, "note": note}
    if gen_token:
        out["token"] = gen_token   # 仅此一次返回明文
    return out


@app.get("/api/files/tiers")
async def files_tier_list(request: Request):
    require_admin(request)
    rows = db.rows(db.get_db().execute(
        "SELECT t.id, t.name, t.perm, t.note, t.created_at, "
        " COUNT(f.id) AS files, COALESCE(SUM(f.size),0) AS bytes, "
        " COALESCE(SUM(f.downloads),0) AS downloads "
        "FROM file_tiers t LEFT JOIN file_objects f ON f.tier_id=t.id GROUP BY t.id ORDER BY t.id"))
    return {"tiers": rows}


@app.put("/api/files/tiers/{name}/token")
async def files_tier_reset_token(name: str, request: Request):
    """重置层凭证（旧凭证立即失效），返回一次性新明文。"""
    require_admin(request)
    tier = _tier_by_name(name)
    if not tier:
        raise HTTPException(status_code=404, detail="层不存在")
    new_token = secrets.token_urlsafe(18)
    db.get_db().execute("UPDATE file_tiers SET token_hash=? WHERE id=?",
                        (_hash_pw(new_token), tier["id"]))
    db.get_db().commit()
    return {"ok": True, "token": new_token}


@app.delete("/api/files/tiers/{name}")
async def files_tier_delete(name: str, request: Request):
    """删除分层及其全部文件（不可恢复）。"""
    s = require_admin(request)
    tier = _tier_by_name(name)
    if not tier:
        raise HTTPException(status_code=404, detail="层不存在")
    n_files = db.get_db().execute("SELECT COUNT(*) c FROM file_objects WHERE tier_id=?",
                                  (tier["id"],)).fetchone()["c"]
    shutil.rmtree(os.path.join(FILES_ROOT, name), ignore_errors=True)
    conn = db.get_db()
    conn.execute("DELETE FROM file_objects WHERE tier_id=?", (tier["id"],))
    conn.execute("DELETE FROM file_tiers WHERE id=?", (tier["id"],))
    conn.commit()
    _audit(_actor_name(s), "tier_delete", f"tier:{name}",
           f"perm={tier['perm']}，删除文件 {n_files} 个", _client_ip(request))
    return {"ok": True}


@app.get("/api/files/{name}")
async def files_list(name: str, request: Request):
    """列出层内文件（含可直接分发的下载链接）。凭证同上传。"""
    tier = _tier_by_name(name)
    if not tier:
        raise HTTPException(status_code=404, detail="层不存在")
    if not (_session(request) and _session(request)["role"] == "admin") and not _tier_token_ok(request, tier) \
            and tier["perm"] != "public":
        raise HTTPException(status_code=401, detail="需要管理员会话或层凭证")
    fs = db.rows(db.get_db().execute(
        "SELECT filename, size, sha256, downloads, updated_at FROM file_objects WHERE tier_id=? ORDER BY updated_at DESC",
        (tier["id"],)))
    for f in fs:
        f["url"] = f"/files/{name}/{f['filename']}" + ("?token=" + request.query_params.get("token", "") if tier["perm"] == "token" and request.query_params.get("token") else "")
    return {"tier": name, "perm": tier["perm"], "files": fs}


@app.put("/api/files/{name}/{filename:path}")
async def files_upload(name: str, filename: str, request: Request):
    """上传/覆盖文件（admin 会话或层 Bearer 凭证）。body = 文件原始字节。"""
    tier = _tier_by_name(name)
    if not tier:
        raise HTTPException(status_code=404, detail="层不存在")
    if not _slug_ok(filename):
        raise HTTPException(status_code=400, detail="文件名仅允许字母/数字/._- 且不含路径分隔符")
    if not _file_write_ok(request, tier):
        raise HTTPException(status_code=401, detail="需要管理员会话或层 Bearer 凭证")
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail=f"超过上传上限 {MAX_UPLOAD // 1024 // 1024}MB")
    tdir = os.path.join(FILES_ROOT, name)
    os.makedirs(tdir, exist_ok=True)
    fpath = os.path.join(tdir, filename)
    with open(fpath, "wb") as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    conn = db.get_db()
    existed = conn.execute("SELECT 1 FROM file_objects WHERE tier_id=? AND filename=?",
                           (tier["id"], filename)).fetchone()
    if existed:
        conn.execute("UPDATE file_objects SET size=?, sha256=?, content_type=?, updated_at=datetime('now','localtime') "
                     "WHERE tier_id=? AND filename=?",
                     (len(data), sha, ctype, tier["id"], filename))
    else:
        conn.execute("INSERT INTO file_objects(tier_id, filename, size, sha256, content_type) VALUES(?,?,?,?,?)",
                     (tier["id"], filename, len(data), sha, ctype))
    conn.commit()
    return {"ok": True, "tier": name, "filename": filename, "size": len(data), "sha256": sha,
            "overwritten": bool(existed), "url": f"/files/{name}/{filename}"}


@app.delete("/api/files/{name}/{filename:path}")
async def files_delete(name: str, filename: str, request: Request):
    tier = _tier_by_name(name)
    if not tier:
        raise HTTPException(status_code=404, detail="层不存在")
    if not _file_write_ok(request, tier):
        raise HTTPException(status_code=401, detail="需要管理员会话或层 Bearer 凭证")
    row = db.get_db().execute("SELECT id FROM file_objects WHERE tier_id=? AND filename=?",
                              (tier["id"], filename)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        os.remove(os.path.join(FILES_ROOT, name, filename))
    except OSError:
        pass
    db.get_db().execute("DELETE FROM file_objects WHERE tier_id=? AND filename=?", (tier["id"], filename))
    db.get_db().commit()
    # 删除者可能是层 Bearer 凭证（非账号会话），actor 回落为 token:<层名>
    _audit(_actor_name(_session(request)), "file_delete", f"tier:{name}/file:{filename}",
           "", _client_ip(request))
    return {"ok": True}


# ---- R43b /apps 静态 inline 直出：把 public 层文件作为「在线使用」入口（无 attachment）。
# 典型用途：纯前端单文件应用 + Service Worker（scope=同目录）。仅 public 层可直出；
# 只读分发（无上传、无后端执行），更新走 /files API 同名覆盖。----
_APPS_CT = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
            ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}


APP_ALIASES = {"wuzhen": "wuzhen-release"}   # /apps/<别名> → 托管层名（方案 A 指定路径 /apps/wuzhen/）


def _apps_serve(tier_name: str, filename: str):
    tier_name = APP_ALIASES.get(tier_name, tier_name)
    tier = _tier_by_name(tier_name)
    if not tier or tier["perm"] != "public":
        raise HTTPException(status_code=404, detail="应用不存在")
    if not _slug_ok(filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    row = db.get_db().execute("SELECT * FROM file_objects WHERE tier_id=? AND filename=?",
                              (tier["id"], filename)).fetchone()
    fpath = os.path.join(FILES_ROOT, tier_name, filename)
    if not row or not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(filename)[1].lower()
    resp = FileResponse(fpath, media_type=_APPS_CT.get(ext, "application/octet-stream"))
    resp.headers["Content-Disposition"] = "inline"
    resp.headers["Cache-Control"] = "no-cache"          # 更新走同名覆盖，确保拿到新版
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@app.get("/apps", response_class=HTMLResponse)
async def apps_shelf(request: Request):
    """R52 应用货架：列出全部 public 托管层（在线应用 + 可下载工具）。
    新工具上传到 public 层即自动出现在此页与门户卡片，无需改代码。"""
    conn = db.get_db()
    tiers = db.rows(conn.execute(
        "SELECT * FROM file_tiers WHERE perm='public' AND name != 'release' ORDER BY id"))
    items = []
    for t in tiers:
        files = db.rows(conn.execute(
            "SELECT filename, size, updated_at FROM file_objects WHERE tier_id=? "
            "ORDER BY updated_at DESC, filename DESC", (t["id"],)))
        items.append({"tier": t, "files": files,
                      "has_index": any(f["filename"] == "index.html" for f in files)})
    return templates.TemplateResponse(request, "apps.html", {"request": request, "items": items})


@app.api_route("/apps/{tier_name}", methods=["GET", "HEAD"])
@app.api_route("/apps/{tier_name}/", methods=["GET", "HEAD"])
async def apps_index(tier_name: str, request: Request):
    return _apps_serve(tier_name, "index.html")


@app.api_route("/apps/{tier_name}/{filename:path}", methods=["GET", "HEAD"])
async def apps_file(tier_name: str, filename: str, request: Request):
    if "/" in filename:
        raise HTTPException(status_code=400, detail="仅支持单级文件名")
    return _apps_serve(tier_name, filename)


@app.api_route("/files/{name}/{filename:path}", methods=["GET", "HEAD"])
async def files_download(name: str, filename: str, request: Request):
    """分发下载（可直接分享的链接）。public 直接下载；token 层需 ?token=<凭证>；
    admin 层需管理员会话。支持 Range 断点（FileResponse 内建）。"""
    tier = _tier_by_name(name)
    if not tier:
        raise HTTPException(status_code=404, detail="层不存在")
    row = db.get_db().execute("SELECT * FROM file_objects WHERE tier_id=? AND filename=?",
                              (tier["id"], filename)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")
    fpath = os.path.join(FILES_ROOT, name, filename)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="文件已丢失，请重新上传")
    if tier["perm"] == "token":
        tok = request.query_params.get("token", "")
        auth_ok = (tok and _verify_pw(tok, tier["token_hash"])) or _tier_token_ok(request, tier)
        if not auth_ok:
            raise HTTPException(status_code=401, detail="需要下载凭证（?token=）")
    elif tier["perm"] == "admin":
        s = _session(request)
        if not s or s["role"] != "admin":
            raise HTTPException(status_code=401, detail="需要管理员登录")
    resp = FileResponse(fpath, media_type=row["content_type"], filename=filename)
    resp.headers["ETag"] = '"' + row["sha256"] + '"'
    resp.headers["Cache-Control"] = "public, max-age=300"
    if request.method == "GET":   # HEAD（探活/链接预览）不计入下载
        db.get_db().execute("UPDATE file_objects SET downloads=downloads+1 WHERE id=?", (row["id"],))
        db.get_db().commit()
    return resp


@app.on_event("startup")
async def _startup():
    db.init_db()
    _seed_default_accounts()
    db.get_db().execute(
        "DELETE FROM sessions WHERE created_at < datetime('now','localtime','-30 days')")
    db.get_db().commit()
