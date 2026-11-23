#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R141 证书 v2（背景+文本框）与公示打印台回归。"""
import os
import sys
import tempfile

# 合并运行时（pytest 多模块共享 server.app）沿用首个模块的隔离库；单跑本模块时独立建库
if "server.app" not in sys.modules:
    _TMP = tempfile.mkdtemp(prefix="dsh-certv2-")
    os.environ["DSPORT_DB"] = os.path.join(_TMP, "test.db")
    os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "files")

import asyncio  # noqa: E402
import base64  # noqa: E402
import io  # noqa: E402
import zipfile  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from PIL import Image as PILImage  # noqa: E402
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


CSV_COMPETITORS = (
    "背番号,姓名,学校/单位,项目编号\n"
    + "".join("%d,选手%d,院%d,P01Z01\n" % (n, n, n % 2 + 1) for n in (101, 102, 103, 104))
).encode("utf-8")
CSV_JUDGES = "裁判ID,姓名\nJ1,甲\nJ2,乙\nJ3,丙\n".encode("utf-8")
CSV_SCHEDULE = ('场次编号,场次名称,项目编号,轮次,舞种,评分类型,晋级人数,参赛选手\n'
                'P01-R1,平四决赛,P01Z01,1,平四,SKATING,4,"101,102,103,104"\n').encode("utf-8")


@pytest.fixture(scope="module", autouse=True)
def env():
    _login("admin", {"role": "admin", "password": "admin123"})
    r = req("POST", "/api/events", json={"name": "证书v2赛", "date": "2026-06-01", "location": "馆"}, role="admin")
    cid = r.json()["id"]
    req("POST", "/api/events/%d/activate" % cid, role="admin")
    for kind, body in (("competitors", CSV_COMPETITORS), ("judges", CSV_JUDGES), ("schedule", CSV_SCHEDULE)):
        assert req("POST", "/api/events/%d/imports/%s" % (cid, kind), content=body, role="admin").status_code == 200
    for j in ("J1", "J2", "J3"):
        _login(j, {"role": "judge", "judge_id": j})
    ceid = req("GET", "/api/public/events/%d/schedule" % cid).json()["events"][0]["id"]
    assert req("POST", "/api/competition-events/%d/open" % ceid,
               json={"roster": ["101", "102", "103", "104"]}, role="admin").status_code == 200
    req("POST", "/api/competition-events/%d/checkin" % ceid,
        json={"numbers": ["101", "102", "103", "104"], "state": True}, role="admin")
    for j in ("J1", "J2", "J3"):
        r = req("PUT", "/api/judge/competition-events/%d/dances/平四/sheet" % ceid,
                json={"values": {"101": "1", "102": "2", "103": "3", "104": "4"}}, role=j)
        assert r.status_code == 200
    assert req("POST", "/api/competition-events/%d/publish" % ceid, json={}, role="admin").status_code == 200
    return {"cid": cid, "ceid": ceid}


def _png_b64():
    buf = io.BytesIO()
    PILImage.new("RGB", (595, 842), "white").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()



@pytest.fixture(scope="module", autouse=True)
def _need_cjk_font():
    """生成 PDF 内嵌中文文本断言依赖 CJK 字体（生产必装 wqy-zenhei，macOS 有 PingFang）；
    CI 等无字体环境 _reportlab_font() 回退 Helvetica，中文必变豆腐块——跳过而非误报。"""
    from server.app import _reportlab_font
    if _reportlab_font() == "Helvetica":
        pytest.skip("无 CJK 字体（wqy-zenhei/PingFang）——中文 PDF 文本断言在此环境无意义")

def test_printer_role_and_desk(env):
    r = req("POST", "/api/users", json={"username": "printer1", "password": "print123",
                                        "role": "printer", "display_name": "打印员"}, role="admin")
    assert r.status_code == 200
    _login("printer", {"role": "printer", "username": "printer1", "password": "print123", "competition_id": env["cid"]})
    r = req("GET", "/print", role="printer")
    assert r.status_code == 200 and "公示打印台" in r.text and "平四决赛" in r.text
    r = req("GET", "/events/%d/print/view/%d" % (env["cid"], env["ceid"]), role="printer")
    assert r.status_code == 200 and "决赛名次表" in r.text and "选手101" in r.text
    # 打印员无权开赛
    r = req("POST", "/api/competition-events/1/open", json={"roster": ["101"]}, role="printer")
    assert r.status_code == 403


def test_cert_design_and_generate_v2(env):
    cid = env["cid"]
    fields = [
        {"type": "comp", "x": 10, "y": 12, "size": 14, "align": "left", "bold": False},
        {"type": "name", "x": 40, "y": 40, "size": 18, "align": "left", "bold": True},
        {"type": "project", "x": 40, "y": 47, "size": 14, "align": "left", "bold": False},
        {"type": "rank_cn", "x": 40, "y": 54, "size": 14, "align": "left", "bold": False},
    ]
    buf = io.BytesIO()
    PILImage.new("RGB", (595, 842), "white").save(buf, "PNG")
    r = req("POST", "/api/events/%d/certs/designs" % cid,
            json={"name": "标准四行", "bg_type": "image", "bg_b64": base64.b64encode(buf.getvalue()).decode(),
                  "fields": fields}, role="admin")
    assert r.status_code == 200
    did = r.json()["id"]
    r = req("GET", "/api/events/%d/certs/designs/%d/bg" % (cid, did), role="admin")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    # 旧版 .doc 拒绝
    r = req("POST", "/api/events/%d/certs/designs" % cid,
            json={"name": "旧版", "bg_type": "image", "bg_b64": base64.b64encode(b"\xd0\xcf\x11\xe0fake").decode(),
                  "fields": fields}, role="admin")
    assert r.status_code == 400
    # 生成：4 名选手 4 页，逐页名次/姓名断言
    r = req("POST", "/api/events/%d/certs/%d/generate-v2" % (cid, env["ceid"]), json={"design_id": did}, role="admin")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    rd = PdfReader(io.BytesIO(r.content))
    assert len(rd.pages) == 4
    texts = [(p.extract_text() or "") for p in rd.pages]
    assert "第一名" in texts[0] and "选手101" in texts[0]
    assert "第二名" in texts[1] and "选手102" in texts[1]
    assert "第四名" in texts[3] and "选手104" in texts[3]
    # 生成即标记已打印
    d = req("GET", "/api/events/%d/runboard" % cid, role="admin").json()
    ev0 = [e for e in d["events"] if e["id"] == env["ceid"]][0]
    assert ev0["cert_printed"] is True
    # 证书页渲染（设计器）
    html = req("GET", "/events/%d/certs/%d" % (cid, env["ceid"]), role="admin").text
    assert "选择证书设计" in html
    html2 = req("GET", "/events/%d/cert-design" % cid, role="admin").text
    assert "ed-canvas" in html2 and "ed-layer" in html2 and "interact.min.js" in html2
