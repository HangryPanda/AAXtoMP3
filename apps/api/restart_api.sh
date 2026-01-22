#!/usr/bin/env bash
# Restart the local FastAPI dev server (uvicorn) in a consistent way.
#
# Safe-by-default behavior:
# - Prefer a PID file managed by this script.
# - If port 8000 is in use, only kill listeners that look like *this* API
#   (uvicorn + main:app) to avoid killing unrelated services.
#
# Usage:
#   bash apps/api/restart_api.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
HEALTH_URL="${HEALTH_URL:-http://$HOST:$PORT/health}"

TMP_DIR="$REPO_ROOT/tmp"
LOG_FILE="$TMP_DIR/api-uvicorn.log"
PID_FILE="$TMP_DIR/api-uvicorn.pid"

mkdir -p "$TMP_DIR"

is_our_api_pid() {
  local pid="$1"
  local cmd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$cmd" == *"uvicorn"* ]] && [[ "$cmd" == *"main:app"* ]]
}

stop_pid() {
  local pid="$1"
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi

  if ! is_our_api_pid "$pid"; then
    echo "Refusing to kill PID $pid (doesn't look like this API):" >&2
    echo "  $(ps -p "$pid" -o command= 2>/dev/null || true)" >&2
    return 0
  fi

  echo "Stopping API PID $pid..."
  kill "$pid" 2>/dev/null || true

  local i
  for i in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.2
  done

  echo "API PID $pid didn't stop; force killing..." >&2
  kill -9 "$pid" 2>/dev/null || true
}

echo "Restarting API on $HOST:$PORT"

# 1) Stop previous PID if we started it.
if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "${old_pid:-}" =~ ^[0-9]+$ ]]; then
    stop_pid "$old_pid"
  fi
  rm -f "$PID_FILE"
fi

# 2) If something is still listening on the port, try to stop only "our" uvicorn.
if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids:-}" ]]; then
    for pid in $pids; do
      stop_pid "$pid"
    done
  fi
fi

# 3) Start via the venv-based runner.
echo "Starting API (log: $LOG_FILE)"
nohup "$ROOT_DIR/run_dev.sh" > "$LOG_FILE" 2>&1 &
new_pid="$!"
echo "$new_pid" > "$PID_FILE"

# 4) Wait for health.
echo "Waiting for health: $HEALTH_URL"
for _ in $(seq 1 60); do
  if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    echo "API is up (pid=$new_pid)."
    exit 0
  fi
  sleep 0.25
done

echo "API did not become healthy in time. Check logs: $LOG_FILE" >&2
exit 1

