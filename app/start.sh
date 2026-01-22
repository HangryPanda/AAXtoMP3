#!/bin/bash

# Audible Library Manager - One-click launcher
# Just run: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}       Audible Library Manager - Setup & Launch${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Please install Docker first: https://docs.docker.com/engine/install/"
    exit 1
fi

# Check for docker compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not available.${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check for .env and offer to reconfigure
if [ -f ".env" ]; then
    echo -e "${YELLOW}Current configuration found in .env${NC}"
    echo -n "Do you want to reconfigure paths (e.g. to switch to NAS)? [y/N]: "
    read RECONFIGURE </dev/tty
    if [[ "$RECONFIGURE" =~ ^[Yy]$ ]]; then
        rm .env
        echo -e "${YELLOW}Reconfiguring...${NC}"
    fi
fi

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Setup - configuring paths...${NC}"
    echo ""

    # Ensure we can read from terminal
    if [ ! -t 0 ]; then
        echo -e "${RED}Error: Cannot read input. Please run this script interactively or create .env manually.${NC}"
        echo ""
        echo "Create .env with:"
        echo "  DOWNLOAD_PATH=/path/to/downloads"
        echo "  CONVERTED_PATH=/path/to/converted"
        echo "  COMPLETED_PATH=/path/to/completed"
        echo "  LIBRARY_BACKUPS_PATH=/path/to/backups"
        echo "  TZ=America/Los_Angeles"
        echo "  PORT=8501"
        echo "  TERMINAL_PORT=7681"
        exit 1
    fi

    # Ask for download path
    echo -n "Where should downloaded audiobooks be stored? [./downloads]: "
    read DOWNLOAD_PATH </dev/tty
    DOWNLOAD_PATH=${DOWNLOAD_PATH:-./downloads}

    # Ask for converted path
    echo -n "Where should converted M4B files be stored? [./converted]: "
    read CONVERTED_PATH </dev/tty
    CONVERTED_PATH=${CONVERTED_PATH:-./converted}

    # Ask for completed path (source files after conversion)
    echo -n "Where should processed source files be moved? [./completed]: "
    read COMPLETED_PATH </dev/tty
    COMPLETED_PATH=${COMPLETED_PATH:-./completed}

    # Ask for library backups path
    echo -n "Where are your old library.tsv backups located? (Optional) [./library_backups]: "
    read LIBRARY_BACKUPS_PATH </dev/tty
    LIBRARY_BACKUPS_PATH=${LIBRARY_BACKUPS_PATH:-./library_backups}

    # Ask for port
    echo -n "What port should the web UI use? [8501]: "
    read PORT </dev/tty
    PORT=${PORT:-8501}

    # Ask for terminal port
    echo -n "What port should the terminal use? [7681]: "
    read TERMINAL_PORT </dev/tty
    TERMINAL_PORT=${TERMINAL_PORT:-7681}

    # Detect timezone
    if [ -f /etc/timezone ]; then
        DEFAULT_TZ=$(cat /etc/timezone)
    elif [ -L /etc/localtime ]; then
        DEFAULT_TZ=$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')
    else
        DEFAULT_TZ="America/Los_Angeles"
    fi
    echo -n "Your timezone? [$DEFAULT_TZ]: "
    read TZ </dev/tty
    TZ=${TZ:-$DEFAULT_TZ}

    # Create .env file
    cat > .env << EOF
DOWNLOAD_PATH=$DOWNLOAD_PATH
CONVERTED_PATH=$CONVERTED_PATH
COMPLETED_PATH=$COMPLETED_PATH
LIBRARY_BACKUPS_PATH=$LIBRARY_BACKUPS_PATH
TZ=$TZ
PORT=$PORT
TERMINAL_PORT=$TERMINAL_PORT
EOF

    echo ""
    echo -e "${GREEN}Configuration saved to .env${NC}"
fi

# Load .env
source .env

# Create directories if they don't exist
mkdir -p "$DOWNLOAD_PATH" "$CONVERTED_PATH" "$COMPLETED_PATH"

# Get local IP for display
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")
fi

echo ""
echo -e "${YELLOW}Building and starting container...${NC}"
echo ""

# Build and start
docker compose up -d --build

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}                    Ready!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Open in your browser:"
echo -e "    Local:   ${GREEN}http://localhost:${PORT}${NC}"
echo -e "    Network: ${GREEN}http://${LOCAL_IP}:${PORT}${NC}"
echo ""
echo -e "  Commands:"
echo -e "    Stop:    ${YELLOW}./stop.sh${NC}"
echo -e "    Logs:    ${YELLOW}docker compose logs -f${NC}"
echo -e "    Restart: ${YELLOW}./start.sh${NC}"
echo ""
