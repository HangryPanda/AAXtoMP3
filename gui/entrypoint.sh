#!/bin/bash
set -euo pipefail

sync_audible_cli_credentials() {
  # audible-cli expects credentials under ~/.audible (in-container: /root/.audible).
  # We mount host credentials at /host_audible:ro, so bootstrap /root/.audible from it.
  if [ -d /host_audible ] && [ -e /host_audible ]; then
    mkdir -p /root/.audible

    # Copy known audible-cli files if they don't exist yet in /root/.audible.
    for f in config.toml audibleAuth; do
      if [ -f "/host_audible/$f" ] && [ ! -f "/root/.audible/$f" ]; then
        cp "/host_audible/$f" "/root/.audible/$f"
      fi
    done

    # Some setups store auth as JSON; copy those too (non-destructive).
    for f in /host_audible/*.json; do
      if [ -f "$f" ]; then
        base="$(basename "$f")"
        if [ ! -f "/root/.audible/$base" ]; then
          cp "$f" "/root/.audible/$base"
        fi
      fi
    done
  fi
}

sync_audible_cli_credentials

# Start ttyd in background
# -W: writable
# -p: port
# bash: shell to run
echo "Starting terminal..."
nohup ttyd -W -p 7681 bash > /var/log/ttyd.log 2>&1 &

# Start Streamlit
echo "Starting Streamlit..."
exec streamlit run app.py
