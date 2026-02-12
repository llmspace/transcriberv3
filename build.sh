#!/bin/bash
# YouTubeTranscriber v3 — Build Script
# Builds a native macOS .app bundle using py2app.
#
# Usage:
#   ./build.sh           # Full standalone build
#   ./build.sh --dev     # Development alias build (faster, links to source)
#
# Prerequisites:
#   pip3 install py2app requests

set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     YouTubeTranscriber v3 — Build Script        ║"
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

# ── Check setuptools (provides pkg_resources, required by py2app) ──────
echo "Checking setuptools..."
if ! "$PYTHON" -c "import pkg_resources" 2>/dev/null; then
    echo "   Installing setuptools..."
    "$PYTHON" -m pip install --user 'setuptools>=70.0'
fi
echo "✅ setuptools available"

# ── Check py2app ─────────────────────────────────────────────
echo "Checking py2app..."
if ! "$PYTHON" -c "import py2app" 2>/dev/null; then
    echo "   Installing py2app..."
    "$PYTHON" -m pip install --user py2app
fi
echo "✅ py2app available"

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
rm -rf build dist .eggs *.egg-info

# ── Build ────────────────────────────────────────────────────────────
echo ""
if [ "${1:-}" = "--dev" ]; then
    echo "Building in DEVELOPMENT mode (alias)..."
    "$PYTHON" setup.py py2app -A
    echo ""
    echo "⚠️  Development build: the app links to your source files."
    echo "   Changes to source code take effect immediately."
else
    echo "Building STANDALONE app..."
    "$PYTHON" setup.py py2app
fi

# ── Remove quarantine ────────────────────────────────────────────────
if [ -d "dist/YouTubeTranscriber.app" ]; then
    xattr -cr "dist/YouTubeTranscriber.app" 2>/dev/null || true
fi

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     ✅ Build complete!                            ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  App location:                                   ║"
echo "║    dist/YouTubeTranscriber.app                   ║"
echo "║                                                  ║"
echo "║  To install:                                     ║"
echo "║    cp -r dist/YouTubeTranscriber.app             ║"
echo "║       /Applications/                             ║"
echo "║                                                  ║"
echo "║  Or just double-click the .app in dist/          ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
