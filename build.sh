#!/bin/bash
# video-to-text-transcriber v1.0.0 — Build Script
# Builds a native macOS .app bundle using PyInstaller.
#
# Usage:
#   ./build.sh           # Full standalone build
#
# Prerequisites:
#   pip3 install pyinstaller requests

set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   video-to-text-transcriber — Build Script      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Check Python 3 ───────────────────────────────────────────────────
echo "Checking Python 3..."
PYTHON=""
for candidate in python3 python3.12 python3.11 python3.13 python3.14 python3.10; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ Python 3 not found."
    echo "   Install with:  brew install python@3.12"
    exit 1
fi
echo "✅ Python 3 found: $PYTHON ($($PYTHON --version))"

# ── Check PyInstaller ────────────────────────────────────────────────
echo "Checking PyInstaller..."
if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "   Installing PyInstaller..."
    "$PYTHON" -m pip install --user pyinstaller
fi
echo "✅ PyInstaller available"

# ── Check requests ───────────────────────────────────────────────────
echo "Checking requests..."
if ! "$PYTHON" -c "import requests" 2>/dev/null; then
    echo "   Installing requests..."
    "$PYTHON" -m pip install --user requests
fi
echo "✅ requests available"

# ── Check yt-dlp ─────────────────────────────────────────────────────
echo "Checking yt-dlp..."
if command -v yt-dlp &>/dev/null; then
    echo "✅ yt-dlp found: $(yt-dlp --version)"
else
    echo "⚠️  yt-dlp not found. Install with: brew install yt-dlp"
    echo "   (Not required for building, but required at runtime)"
fi

# ── Check ffmpeg ─────────────────────────────────────────────────────
echo "Checking ffmpeg..."
if command -v ffmpeg &>/dev/null; then
    echo "✅ ffmpeg found"
else
    echo "⚠️  ffmpeg not found. Install with: brew install ffmpeg"
    echo "   (Not required for building, but required at runtime)"
fi

# ── Clean previous builds ────────────────────────────────────────────
echo ""
echo "Cleaning previous builds..."
rm -rf build dist

# ── Build ────────────────────────────────────────────────────────────
echo ""
echo "Building STANDALONE app with PyInstaller..."
"$PYTHON" -m PyInstaller VideoToTextTranscriber.spec --noconfirm

# ── Remove quarantine ────────────────────────────────────────────────
if [ -d "dist/VideoToTextTranscriber.app" ]; then
    xattr -cr "dist/VideoToTextTranscriber.app" 2>/dev/null || true
fi

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     ✅ Build complete!                            ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  App location:                                   ║"
echo "║    dist/VideoToTextTranscriber.app               ║"
echo "║                                                  ║"
echo "║  To install:                                     ║"
echo "║    ./install.sh                                  ║"
echo "║                                                  ║"
echo "║  Or just double-click the .app in dist/          ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
