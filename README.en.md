# Simple Dance Sport System · DanceSport Competition Scoring

Two editions of the same DanceSport competition scoring system, sharing one algorithm core in
[`core/`](core/) (pure standard library; both editions produce bit-identical results):

| Directory | Edition | Best for | Stack |
|------|------|----------|--------|
| [`desktop/`](desktop/) | Local scoring app (single-machine desktop) | Single-station judging, offline venues, double-click to run on Windows/macOS | Python Tkinter + pandas |
| [`webapp/`](webapp/) | Online scoring system (multi-device web service) | Judges scoring from mobile devices, check-in / MC desk, spectator queries, big-screen rotation | FastAPI + Jinja2 + SQLite WAL + SSE |

## Directory Layout

```
Simple-Dance-Sport-System/
├── core/        # Shared algorithm core: Skating system / Mark scoring, advancement, team standings (pure standard library)
├── tests/       # Core tests: verified bit-for-bit against the desktop src/ implementation (run pytest from the repo root)
├── desktop/     # Local edition: launch with main.py; desktop UI and algorithms in src/, packaged via build_app.py
└── webapp/      # Server edition: launch with run.py; web app in server/, E2E and screenshot scripts in tools/, design docs in docs/
```

## Quick Start

### Desktop app (desktop/)

```bash
cd desktop
pip install -r requirements.txt
python main.py            # launch the desktop app
python build_app.py       # package with PyInstaller (see build_readme.md)
```

See [desktop/README.md](desktop/README.md) for details.

### Online scoring system (webapp/)

```bash
cd webapp
python -m server.seed     # optional: load the demo seed competition
python run.py             # listens on 0.0.0.0:8321 (override with DSPORT_PORT)
```

- Open `http://<host>:8321/login`: admin (password, defaults to `admin123` — in production always override it
  via environment variables such as `DSPORT_ADMIN_PASSWORD`), judges (judge ID), MC / check-in staff (username + password)
- Public pages require no login: `/public/schedule`, `/public/results`, `/screen` (auto-rotating big screen)
- Data file: `webapp/data/dancesport.db` (SQLite WAL)

See [webapp/README.md](webapp/README.md) and [webapp/docs/](webapp/docs/) (design / requirements / walkthrough manuals).

### Running tests (repo root)

```bash
python -m pytest          # core tests (core/ is the system under test, desktop/src is the reference baseline)
```

## Deployment Notes

- For production deployments of the server edition, override the default passwords via the
  `DSPORT_ADMIN_PASSWORD` / `DSPORT_HOST_PASSWORD` / `DSPORT_MARSHAL_PASSWORD` environment variables;
  tools such as `webapp/tools/manual_shots.py` read credentials from the same environment variables.
- `core/` lives at the repo root: the webapp `server` package automatically prepends the repo root to
  `sys.path` on import, so all three launch methods — `run.py`, `python -m server.seed`,
  and `uvicorn server.app:app` — work without setting PYTHONPATH manually.

## Deployment

The server edition supports two deployment options: **A) Run directly** — from the `webapp/` directory,
run `python -m server.seed` first (optional, loads the demo seed competition), then `python run.py` to
start the service; inject production passwords via the `DSPORT_ADMIN_PASSWORD` /
`DSPORT_HOST_PASSWORD` / `DSPORT_MARSHAL_PASSWORD` environment variables. **B) Docker Compose + Caddy
automatic HTTPS** — containerized deployment templates and steps are in
[`docs/DEPLOY.md`](docs/DEPLOY.md); note that the service must run a single worker
(a constraint of SQLite WAL and SSE).

## Security

- Production passwords are always injected via the `DSPORT_ADMIN_PASSWORD` / `DSPORT_HOST_PASSWORD` /
  `DSPORT_MARSHAL_PASSWORD` environment variables; no valid credentials are stored in the repository or code.
- Please do not report security vulnerabilities through public GitHub issues; see [SECURITY.md](SECURITY.md)
  for the reporting channel and known security design.
- Supported versions: the latest `main` branch only.

---

For the Chinese documentation, see [README.md](README.md).
