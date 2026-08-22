#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Video Watermark Remover Pro v6.0 - Universal Launcher (macOS / Linux)
# ─────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  🎬 Video Watermark Remover Pro v6.0 (Instant 1000 FPS)    "
echo "============================================================"

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 is required. Please install Python 3.9+."
    exit 1
fi

# Check for FFmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "[WARNING] FFmpeg not found on PATH. Checking common locations..."
    if [ -f "/opt/homebrew/bin/ffmpeg" ]; then
        export PATH="/opt/homebrew/bin:$PATH"
    elif [ -f "/usr/local/bin/ffmpeg" ]; then
        export PATH="/usr/local/bin:$PATH"
    else
        echo "[ERROR] FFmpeg is not installed."
        echo "Install via Homebrew (macOS): brew install ffmpeg"
        echo "Install via APT (Ubuntu/Debian): sudo apt update && sudo apt install -y ffmpeg"
        exit 1
    fi
fi

# Setup Virtual Environment if missing
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Launch GUI
python3 gui_app.py "$@"
