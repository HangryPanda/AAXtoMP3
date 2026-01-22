#!/bin/bash

# Stop the Audible Library Manager

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping Audible Library Manager..."
docker compose down

echo "Stopped."
