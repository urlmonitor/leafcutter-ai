#!/usr/bin/env bash
# run-mock-toggle-check.sh — UXP-553 regression: mock-mode runtime toggle.
#
# Proves, against a RUNNING server, that toggling ?mock=1 / ?mock=0 within a
# single process returns FIXTURE data vs REAL data correctly and that the
# per-root cache does not leak between the two modes.
#
# Three assertions (all run in one server process):
#
#   1. ?mock=1 (query param)
#      → middleware sets x-mock-active: 1
#      → isMockActive()=true → repoRoot()=FIXTURE_ROOT
#      → getFlows() cache bucket: FIXTURE_ROOT
#      → fixture-only flow "leafcutter/mock-mode-toggle" MUST be PRESENT
#      → expect HTTP 200
#
#   2. ?mock=0 (query param, fresh session — no cookies sent)
#      → middleware sets x-mock-active: 0 AND persists sticky cookie "mock"="0"
#      → isMockActive()=false → repoRoot()=realRoot
#      → getFlows() cache bucket: realRoot (separate from FIXTURE_ROOT bucket)
#      → fixture-only flow MUST be ABSENT
#      → expect HTTP 200
#      Guards bug B (cache-by-root): single-value cache would return stale
#      fixture flows → flow PRESENT → HTTP 500 → FAIL.
#
#   3. No ?mock param; "mock"="0" cookie replayed from assertion 2
#      → middleware reads cookie → sets x-mock-active: 0
#      → isMockActive()=false → real root → flow MUST be ABSENT
#      → expect HTTP 200
#      Guards bug A (sticky cookie): if middleware DELETED the cookie instead of
#      setting it to "0", the cookie jar from step 2 would be empty → no override
#      → LEAFCUTTER_MOCK=1 env takes over → fixture root → flow PRESENT → HTTP 500 → FAIL.
#
# Usage (from leafcutter-web/):
#   bash scripts/run-mock-toggle-check.sh
#
# Prerequisites:
#   - npm run build must have been run (server-side env vars are runtime; build
#     need not match the LEAFCUTTER_MOCK value used here)
#   - port 3002 must be free (default; override with MOCK_TOGGLE_CHECK_PORT)
#   - curl and python3 must be available on PATH
#
# Exit codes:
#   0 — all three assertions pass
#   1 — one or more assertions failed (toggle or cache-by-root regressed)
#   2 — server failed to start within the timeout

set -euo pipefail

PORT="${MOCK_TOGGLE_CHECK_PORT:-3002}"
TIMEOUT="${MOCK_TOGGLE_CHECK_TIMEOUT:-60}"
ENDPOINT="http://localhost:${PORT}/api/mock-toggle-check"

# Temp files for response bodies and cookie jar.
RESP_ON="/tmp/mtc-response-mock-on.json"
RESP_OFF="/tmp/mtc-response-mock-off.json"
RESP_STICKY="/tmp/mtc-response-sticky.json"
COOKIE_JAR="/tmp/mtc-cookie-jar.txt"

echo "=== UXP-553 Mock-mode toggle regression check ==="
echo "Endpoint: ${ENDPOINT}"
echo ""

# Pre-flight: ensure the port is free so we don't silently test an old server.
if curl -s --max-time 1 -o /dev/null "${ENDPOINT}" 2>/dev/null; then
  echo "ERROR: Port ${PORT} is already in use (old server still alive?)."
  echo "Kill the process on port ${PORT} before running this script."
  exit 2
fi

# Start the Next.js server with LEAFCUTTER_MOCK=1 so the env default is mock-on.
# This makes assertion 3 meaningful: if the sticky cookie "mock"="0" is NOT
# preserved, the env default (mock=1) kicks in and the fixture flow is wrongly served.
LEAFCUTTER_MOCK=1 npx next start -p "${PORT}" \
  >/tmp/next-mock-toggle.log 2>&1 &
SERVER_PID=$!
echo "Started Next.js server (PID ${SERVER_PID}) on port ${PORT} with LEAFCUTTER_MOCK=1"

# Kill the server on script exit regardless of success or failure.
# Order matters: kill direct children (next-server) BEFORE killing the parent (npx).
# If the parent dies first, children are re-parented to PID 1 and pkill -P can no
# longer find them — leaving orphan server processes that hold the port across runs.
cleanup() {
  echo ""
  echo "Stopping server (PID ${SERVER_PID}) and children..."
  pkill -P "${SERVER_PID}" 2>/dev/null || true   # kill next-server child first
  kill "${SERVER_PID}" 2>/dev/null || true        # then kill the npx parent
  rm -f "${COOKIE_JAR}"
}
trap cleanup EXIT

# Wait for the server to be ready (retry every 2 s, up to TIMEOUT s).
#
# Pattern: assign inside an `if` condition so that curl's non-zero exit (7 =
# connection refused) does NOT trigger `set -e`, yet the stdout (always "000"
# on failure, a real HTTP code on success) still lands in HTTP_STATUS.
# Give the server a moment to bind before probing.
sleep 5

# Probe the light home route until it returns 200 (a true readiness signal,
# distinct from the toggle assertions below). Requiring 200 avoids false-positive
# readiness from a spurious/partial response during startup.
READY_URL="http://localhost:${PORT}/"
echo "Waiting for server to be ready (timeout: ${TIMEOUT}s)..."
ELAPSED=0
READY=false
while [ "${ELAPSED}" -lt "${TIMEOUT}" ]; do
  READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${READY_URL}" 2>/dev/null || echo "000")
  if [ "${READY_STATUS}" = "200" ]; then
    READY=true
    break
  fi
  sleep 2
  ELAPSED=$(( ELAPSED + 2 ))
done

if [ "${READY}" != "true" ]; then
  echo ""
  echo "ERROR: Server did not become ready within ${TIMEOUT}s"
  echo "Last 20 lines of server log:"
  tail -20 /tmp/next-mock-toggle.log 2>/dev/null || true
  exit 2
fi

echo "Server ready after ~${ELAPSED}s."
echo ""

PASS=true

# ── Assertion 1: ?mock=1 (query param → fixture mode) ──────────────────────────
echo "--- Assertion 1: ?mock=1 (fixture mode — fixture-only flow MUST be present) ---"
HTTP_1="000"
if HTTP_1=$(curl -s -o "${RESP_ON}" -w "%{http_code}" \
    "${ENDPOINT}?mock=1" 2>/dev/null); then
  : # curl succeeded — HTTP_1 holds the status code
else
  echo "ERROR [1]: curl failed (server dropped connection?) — treating as HTTP 000"
  HTTP_1="000"
fi
echo "HTTP ${HTTP_1} — response:"
python3 -m json.tool "${RESP_ON}" 2>/dev/null || cat "${RESP_ON}"
echo ""

if [ "${HTTP_1}" = "200" ]; then
  echo "PASS [1]: ?mock=1 → fixture-only flow is present (FIXTURE_ROOT cached in its own bucket)"
else
  echo "FAIL [1]: ?mock=1 returned HTTP ${HTTP_1} — fixture-only flow is absent (repoRoot() or getFlows() broken)"
  PASS=false
fi

echo ""

# ── Assertion 2: ?mock=0 (query param → real mode; captures sticky cookie) ─────
# --cookie-jar captures Set-Cookie headers so assertion 3 can replay them.
# No --cookie/-b flag: we send NO cookies from the client side — only the param.
echo "--- Assertion 2: ?mock=0 (real mode — fixture-only flow MUST be absent) ---"
HTTP_2="000"
if HTTP_2=$(curl -s -o "${RESP_OFF}" -w "%{http_code}" \
    --cookie-jar "${COOKIE_JAR}" \
    "${ENDPOINT}?mock=0" 2>/dev/null); then
  : # curl succeeded — HTTP_2 holds the status code
else
  echo "ERROR [2]: curl failed — treating as HTTP 000"
  HTTP_2="000"
fi
echo "HTTP ${HTTP_2} — response:"
python3 -m json.tool "${RESP_OFF}" 2>/dev/null || cat "${RESP_OFF}"
echo ""

if [ "${HTTP_2}" = "200" ]; then
  echo "PASS [2]: ?mock=0 → fixture-only flow is absent (real-root cache bucket correctly isolated from FIXTURE_ROOT bucket)"
else
  echo "FAIL [2]: ?mock=0 returned HTTP ${HTTP_2} — fixture-only flow is PRESENT (cache-by-root leaked: FIXTURE_ROOT data served under real-root key)"
  PASS=false
fi

echo ""

# ── Assertion 3: no ?mock param; replay cookie "mock"="0" from assertion 2 ─────
# If middleware persisted the cookie (fix), the jar contains mock=0 → override
# applies → real root → flow absent → HTTP 200 PASS.
# If middleware DELETED the cookie (bug A), jar is empty → no override →
# LEAFCUTTER_MOCK=1 env → fixture root → flow present → HTTP 500 FAIL.
echo "--- Assertion 3: sticky cookie (no ?mock param; cookie from assertion 2 replayed) ---"
if [ -f "${COOKIE_JAR}" ]; then
  echo "Cookie jar contents:"
  cat "${COOKIE_JAR}"
  echo ""
else
  echo "(no cookie jar written — middleware did not set a cookie in assertion 2)"
fi

HTTP_3="000"
if HTTP_3=$(curl -s -o "${RESP_STICKY}" -w "%{http_code}" \
    --cookie "${COOKIE_JAR}" \
    "${ENDPOINT}" 2>/dev/null); then
  : # curl succeeded — HTTP_3 holds the status code
else
  echo "ERROR [3]: curl failed — treating as HTTP 000"
  HTTP_3="000"
fi
echo "HTTP ${HTTP_3} — response:"
python3 -m json.tool "${RESP_STICKY}" 2>/dev/null || cat "${RESP_STICKY}"
echo ""

if [ "${HTTP_3}" = "200" ]; then
  echo "PASS [3]: sticky cookie → fixture-only flow is absent (middleware correctly persisted mock=0 cookie; cookie remembered real mode)"
else
  echo "FAIL [3]: sticky cookie → HTTP ${HTTP_3} (fixture-only flow is PRESENT — middleware deleted the cookie instead of persisting mock=0; env default LEAFCUTTER_MOCK=1 took over)"
  PASS=false
fi

echo ""

# ── Summary ─────────────────────────────────────────────────────────────────────
if [ "${PASS}" = "true" ]; then
  echo "OK: all mock-mode toggle assertions passed."
  exit 0
else
  echo "FAIL: one or more mock-mode toggle assertions failed."
  echo "  Assertion 1 guards: middleware → x-mock-active → repoRoot() → FIXTURE_ROOT seam"
  echo "  Assertion 2 guards: cache-by-root isolation (Map<repoRoot,T> fix)"
  echo "  Assertion 3 guards: sticky cookie persistence (middleware sets mock=0, not delete)"
  exit 1
fi
