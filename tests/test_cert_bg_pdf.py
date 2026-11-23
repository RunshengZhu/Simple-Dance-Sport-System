#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R144 PDF 背景证书回归：上传 PDF 背景 → 预览栅格图 → 生成叠加 PDF（每选手一页、文本落位、互不串页）。"""
import os
import sys
import tempfile

if "server.app" not in sys.modules:
    _TMP = tempfile.mkdtemp(prefix="dsh-certbg-")
    os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
    os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import base64  # noqa: E402
import io  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from server import app as app_module, db as db_module  # noqa: E402

db_module.init_db()

_SESSIONS = {}


def req(method, path, json=None, content=None, role=None):
    headers = {}
    token = _SESSIONS.get(role)
    if token:
        headers["Cookie"] = "session=" + token

    async def _run():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(method, path, json=json, content=content, headers=headers)

    return asyncio.run(_run())


def _login(slot, payload):
    r = req("POST", "/api/login", json=payload)
    assert r.status_code == 200, r.text
    _SESSIONS[slot] = r.headers["set-cookie"].split("session=")[1].split(";")[0]


def _bg_pdf_bytes():
    """模拟证书背景 PDF：装饰边框 + 四栏下划线（无占位符文本）。"""
    from reportlab.pdfgen import canvas as rl
    buf = io.BytesIO()
    cv = rl.Canvas(buf, pagesize=(595, 842))
    cv.setStrokeColorRGB(0.5, 0.35, 0.1); cv.setLineWidth(6)
    cv.rect(20, 20, 555, 802)
    cv.setFont("Helvetica-Bold", 30)
    cv.drawCentredString(297, 640, "CERTIFICATE")
    for y, label in ((560, "Player"), (500, "Category"), (440, "Rank"), (380, "Date")):
        cv.setFont("Helvetica", 14)
        cv.drawString(120, y, label)
        cv.line(190, y - 2, 460, y - 2)
    cv.showPage(); cv.save()
    return buf.getvalue()


@pytest.fixture(scope="module", autouse=True)
def env():
    _login("admin", {"role": "admin", "password": "admin123"})
    r = req("POST", "/api/events", json={"name": "PDF背景赛", "date": "2026-06-01", "location": ""}, role="admin")
    cid = r.json()["id"]
    req("POST", "/api/events/%d/activate" % cid, role="admin")
    comp = "背番号,姓名,性别,学校/单位,项目编号\n" + "".join(
        "%d,选手%d,%s,P01Z01\n" % (n, n, "男" if n % 2 else "女") for n in (101, 102, 103, 104))
    req("POST", "/api/events/%d/imports/competitors" % cid, content=comp.encode("utf-8"), role="admin")
    req("POST", "/api/events/%d/imports/judges" % cid,
        content="裁判ID,姓名\nJ1,甲\nJ2,乙\nJ3,丙\n".encode("utf-8"), role="admin")
    sched = ('场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n'
             'P01-R1,平四决赛,P01Z01,1,平四,SKATING,4,"101,102,103,104"\n').encode("utf-8")
    req("POST", "/api/events/%d/imports/schedule" % cid, content=sched, role="admin")
    ceid = req("GET", "/api/public/events/%d/schedule" % cid).json()["events"][0]["id"]
    req("POST", "/api/competition-events/%d/open" % ceid,
        json={"roster": ["101", "102", "103", "104"]}, role="admin")
    req("POST", "/api/competition-events/%d/checkin" % ceid,
        json={"numbers": ["101", "102", "103", "104"], "state": True}, role="admin")
    for j in ("J1", "J2", "J3"):
        _login(j, {"role": "judge", "judge_id": j})   # 裁判登录（库导入后）
    for j in ("J1", "J2", "J3"):
        r = req("PUT", "/api/judge/competition-events/%d/dances/平四/sheet" % ceid,
                json={"values": {"101": "1", "102": "2", "103": "3", "104": "4"}}, role=j)
        assert r.status_code == 200
    assert req("POST", "/api/competition-events/%d/publish" % ceid, json={}, role="admin").status_code == 200
    return {"cid": cid, "ceid": ceid}



@pytest.fixture(scope="module", autouse=True)
def _need_cjk_font():
    """生成 PDF 内嵌中文文本断言依赖 CJK 字体（生产必装 wqy-zenhei，macOS 有 PingFang）；
    CI 等无字体环境 _reportlab_font() 回退 Helvetica，中文必变豆腐块——跳过而非误报。"""
    from server.app import _reportlab_font
    if _reportlab_font() == "Helvetica":
        pytest.skip("无 CJK 字体（wqy-zenhei/PingFang）——中文 PDF 文本断言在此环境无意义")

def test_pdf_background_upload_preview_and_generate(env):
    cid = env["cid"]
    bg_b64 = base64.b64encode(_bg_pdf_bytes()).decode()
    fields = [
        {"type": "name", "x": 32.5, "y": 33.5, "size": 15, "align": "left", "bold": False},
        {"type": "project", "x": 32.5, "y": 40.5, "size": 15, "align": "left", "bold": False},
        {"type": "rank_cn", "x": 32.5, "y": 47.5, "size": 15, "align": "left", "bold": False},
        {"type": "date", "x": 32.5, "y": 54.5, "size": 13, "align": "left", "bold": False},
    ]
    r = req("POST", "/api/events/%d/certs/designs" % cid,
            json={"name": "PDF 背景证书", "bg_type": "pdf", "bg_b64": bg_b64, "fields": fields}, role="admin")
    assert r.status_code == 200
    did = r.json()["id"]
    # 预览栅格图（PDF 背景 → PNG）
    r = req("GET", "/api/events/%d/certs/designs/%d/bg?preview=1" % (cid, did), role="admin")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    # 生成：4 名选手 4 页，页面尺寸继承背景，文本逐页轮转且互不串页
    r = req("POST", "/api/events/%d/certs/%d/generate-v2" % (cid, env["ceid"]), json={"design_id": did}, role="admin")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    rd = PdfReader(io.BytesIO(r.content))
    assert len(rd.pages) == 4
    assert abs(float(rd.pages[0].mediabox.width) - 595) < 1
    texts = [(p.extract_text() or "").replace("\n", " / ") for p in rd.pages]
    assert "选手101" in texts[0] and "第一名" in texts[0]
    assert "选手102" in texts[1] and "第二名" in texts[1]
    assert "选手103" in texts[2] and "第三名" in texts[2]
    assert "选手104" in texts[3] and "第四名" in texts[3]
    assert "选手101" not in texts[1]   # 无串页
    # 生成即标记已打印
    d = req("GET", "/api/events/%d/runboard" % cid, role="admin").json()
    assert [e for e in d["events"] if e["id"] == env["ceid"]][0]["cert_printed"] is True
