#!/usr/bin/env python3
"""生产方式启动入口：uvicorn server.app:app --host 0.0.0.0 --port ${DSPORT_PORT:-8321}"""
import uvicorn

from server.app import app  # noqa: F401

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(__import__("os").environ.get("DSPORT_PORT", "8321")), workers=1)
