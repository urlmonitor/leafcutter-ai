#!/usr/bin/env bash
# run-parse-through-check.sh — UXP-554 drift guard: Part 2 (parse-through check).
#
# Starts the Next.js app with LEAFCUTTER_MOCK=1, waits for it to be ready,
# then calls /api/drift-guard to verify all real loaders can parse the fixture
# tree and return populated results. Kills the server and exits with the check's
# exit code.
#
# Usage (from leafcutter-web/):
#   bash scripts/run-parse-through-check.sh
#
# Prerequisites:
#   - npm run build must have been run with LEAFCUTTER_MOCK=1 NEXT_PUBLIC_LEAFCUTTER_MOCK=1
#     (the built app already has the mock flag baked in for NEXT_PUBLIC)
#   - port 3001 must be free (uses 3001 to avoid conflicting with dev server on 3000)
#   - curl must be available on PATH
#
# Exit codes:
#   0 — all loader parse-through checks pass
#   1 — one or more checks failed (drift detected)
#   2 — server failed to start within the timeout

set -euo pipefail

PORT="${FIXTURE_CHECK_PORT:-3001}"
TIMEOUT="${FIXTURE_CHECK_TIMEOUT:-60}"
ENDPOINT="http://localhost:${PORT}/api/drift-guard"

echo "=== UXP-554 Fixture parse-through check ==="
echo "Endpoint: ${ENDPOINT}"
echo ""

# Start the Next.js production server in the background on a dedicated port.
# LEAFCUTTER_MOCK=1 is required so repoRoot() returns the fixture dir.
# NEXT_PUBLIC_LEAFCUTTER_MOCK=1 is optional here (already baked into the build).
LEAFCUTTER_MOCK=1 npx next start -p "${PORT}" \
  > /tmp/next-drift-guard.log 2>&1 &
SERVER_PID=$!
echo "Started Next.js server (PID ${SERVER_PID}) on port ${PORT}"

# Ensure the server is killed on script exit (success or failure).
cleanup() {
  echo ""
  echo "Stopping server (PID ${SERVER_PID})..."
  kill "${SERVER_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# Give the server a moment to bind before probing.
sleep 5

# Wait for the server to be ready — probe the light home route until it returns
# 200 (a readiness signal distinct from the drift-guard assertion below). A
# spurious/partial response is not 200, so this avoids false-positive readiness.
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
  echo "Last server log (tail -20):"
  tail -20 /tmp/next-drift-guard.log || true
  exit 2
fi

echo "Server ready after ~${ELAPSED}s."
echo ""

# Call the drift-guard endpoint and capture the response body + HTTP status.
# Guard against set -e: on a connection failure curl exits non-zero, so fall
# back to "000" and let the HTTP-code check below report it (never abort here).
HTTP_CODE=$(curl -s -o /tmp/drift-guard-response.json -w "%{http_code}" "${ENDPOINT}" 2>/dev/null || echo "000")

echo "HTTP ${HTTP_CODE} — response:"
# Pretty-print if python3 is available; fall back to raw.
python3 -m json.tool /tmp/drift-guard-response.json 2>/dev/null \
  || cat /tmp/drift-guard-response.json
echo ""

# HTTP 200 = ok, anything else = failure.
if [ "${HTTP_CODE}" = "200" ]; then
  echo "OK: all fixture parse-through checks passed."
  exit 0
else
  echo "FAIL: drift-guard returned HTTP ${HTTP_CODE} — fixture parse-through check failed."
  exit 1
fi
