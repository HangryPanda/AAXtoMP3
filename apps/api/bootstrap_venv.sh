#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"

VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
REQ_FILE="${REQ_FILE:-$ROOT_DIR/requirements.txt}"

if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python3.11}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

PIP_CACHE_DIR="${PIP_CACHE_DIR:-$REPO_ROOT/tmp/pip-cache}"

mkdir -p "$PIP_CACHE_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Configure pip to use a writable cache directory (avoids warnings when HOME cache isn't writable).
cat > "$VENV_DIR/pip.conf" <<EOF
[global]
cache-dir = $PIP_CACHE_DIR
EOF

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install -U pip setuptools wheel
pip install -r "$REQ_FILE"

echo "OK: venv ready at $VENV_DIR"
