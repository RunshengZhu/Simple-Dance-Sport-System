import os
print("DIAG DSPORT_DB:", os.environ.get("DSPORT_DB"))
import tempfile
_TMP = tempfile.mkdtemp(prefix="dsh-diag-")
os.environ["DSPORT_DB"] = os.path.join(_TMP, "t.db")
os.environ["DSPORT_FILES_DIR"] = os.path.join(_TMP, "f")
import asyncio, httpx
from server import app as app_module, db as db_module
db_module.init_db()

def test_diag():
    async def one(method, path, **kw):
        tr = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=tr, base_url="http://t") as c:
            return await c.request(method, path, **kw)
    r = asyncio.run(one("POST", "/api/login", json={"role": "admin", "password": "admin123"}))
    print("DIAG login:", r.status_code, r.text[:60])
    assert r.status_code == 200
    tok = r.headers["set-cookie"].split("session=")[1].split(";")[0]
    r2 = asyncio.run(one("GET", "/api/files/tiers", headers={"Cookie": "session=" + tok}))
    print("DIAG tiers:", r2.status_code, r2.text[:60])
    assert r2.status_code == 200
