#!/usr/bin/env bash
# CI 发版门禁（R134）：临时库起服 → 全链路 API 套件（含 comp21 事故回归用例）
# → doctor 不变量体检 → 前端页面响应断言。
# 用法：bash webapp/tools/ci.sh    （pytest 单测走独立 workflow job，本脚本为真实 HTTP 层）
# 退出码 0 = 通过。
set -uo pipefail
cd "$(dirname "$0")/.."          # webapp/

PORT="${CI_PORT:-8399}"
BASE="http://127.0.0.1:${PORT}"
TMPDIR="$(mktemp -d /tmp/ci-dsport.XXXXXX)"
DB="${TMPDIR}/ci.db"
LOG="${TMPDIR}/server.log"
PY="${PYTHON:-python3}"

cleanup() {
  [[ -n "${SRV_PID:-}" ]] && kill "${SRV_PID}" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT

echo "== CI 发版门禁（临时库 ${DB}）=="

# 1) 静态：语法编译
"${PY}" -m py_compile server/app.py server/db.py server/scoring_service.py \
  ../core/*.py tools/ci_suite.py tools/doctor.py \
  || { echo "FAIL: py_compile"; exit 1; }
echo "PASS py_compile"

# 2) 起服（隔离临时库）
DSPORT_DB="${DB}" DSPORT_PORT="${PORT}" "${PY}" run.py >"${LOG}" 2>&1 &
SRV_PID=$!
for i in $(seq 1 40); do
  if curl -sf -o /dev/null "${BASE}/competitions"; then break; fi
  sleep 0.5
done
curl -sf -o /dev/null "${BASE}/competitions" || { echo "FAIL: 服务未就绪"; tail -20 "${LOG}"; exit 1; }
echo "PASS 服务就绪 (${BASE})"

# 3) 全链路 API 套件（含事故回归 + doctor + 前端响应）
CI_BASE="${BASE}" CI_DB="${DB}" "${PY}" tools/ci_suite.py
SUITE=$?
[[ ${SUITE} -eq 0 ]] || { echo "FAIL: ci_suite"; tail -30 "${LOG}"; exit 1; }

echo "== CI 全部通过 =="
