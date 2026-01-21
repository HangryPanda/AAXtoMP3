#!/bin/zsh
set -x  # Enable debugging

echo "🔹 Running setup_env.sh..."

# Define script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📂 Script directory: $SCRIPT_DIR"

# Check if Homebrew is installed
if ! command -v brew &>/dev/null; then
    echo "🍺 Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "✅ Homebrew is already installed."
fi

# Ensure Python 3 is installed
if ! command -v python3 &>/dev/null; then
    echo "🐍 Python 3 not found. Installing Python..."
    brew install python
else
    echo "✅ Python 3 is already installed."
fi

# Ensure pip is installed and upgraded
echo "📦 Upgrading pip..."
python3 -m ensurepip --default-pip
python3 -m pip install --upgrade pip

# Create and activate a virtual environment
VENV_DIR="$SCRIPT_DIR/env"
if [ ! -d "$VENV_DIR" ]; then
    echo "🔹 Creating a virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

echo "🔹 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install required Python packages
echo "📦 Installing required Python dependencies..."
pip install --upgrade audible-cli

# Verify Audible CLI installation
if ! command -v audible &>/dev/null; then
    echo "❌ Audible CLI installation failed. Please check your environment."
    exit 1
else
    echo "✅ Audible CLI installed successfully."
fi

# Authenticate with Audible
echo "🔑 Checking Audible authentication..."
if [ ! -f "$HOME/.audible/audibleAuth" ]; then
    echo "🔐 Running Audible CLI Quickstart..."
    audible quickstart
else
    echo "✅ Audible CLI is already authenticated."
fi

# Ensure tmp directory exists
TMP_DIR="$SCRIPT_DIR/tmp"
mkdir -p "$TMP_DIR"
echo "✅ Ensured tmp directory exists: $TMP_DIR"

echo "✅ Environment setup complete!"
echo "You can now run: python sync_audible_library_cli.py"

set +x  # Disable debugging