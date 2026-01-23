#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Missing venv python at: $VENV_PY" >&2
  echo "Create it with:" >&2
  echo "  bash \"$ROOT_DIR/bootstrap_venv.sh\"" >&2
  exit 1
fi

cd "$ROOT_DIR"
exec "$VENV_PY" -m uvicorn main:app --host 0.0.0.0 --port 8000
