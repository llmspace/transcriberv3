#!/bin/bash
# YouTubeTranscriber v3 — Install Script
# Copies the built .app to /Applications.
#
# Usage:
#   ./install.sh
#
# Run ./build.sh first to create the .app bundle.

set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     YouTubeTranscriber v3 — Installer           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BUNDLE="$SCRIPT_DIR/dist/YouTubeTranscriber.app"

# ── Check the .app exists ────────────────────────────────────────────
if [ ! -d "$APP_BUNDLE" ]; then
    echo "❌ dist/YouTubeTranscriber.app not found."
    echo "   Run ./build.sh first to build the app."
    exit 1
fi

# ── Check runtime dependencies ───────────────────────────────────────
echo "Checking runtime dependencies..."

if command -v yt-dlp &>/dev/null; then
    echo "✅ yt-dlp found: $(yt-dlp --version)"
else
    echo "❌ yt-dlp not found."
    echo "   Install with:  brew install yt-dlp"
    exit 1
fi

if command -v ffmpeg &>/dev/null; then
    echo "✅ ffmpeg found"
else
    echo "❌ ffmpeg not found."
    echo "   Install with:  brew install ffmpeg"
    exit 1
fi

# ── Remove quarantine flag ───────────────────────────────────────────
echo "Removing quarantine flag..."
xattr -cr "$APP_BUNDLE" 2>/dev/null || true
echo "✅ Quarantine flag removed"

# ── Copy to /Applications ────────────────────────────────────────────
echo ""
echo "Installing to /Applications..."
DEST="/Applications/YouTubeTranscriber.app"

if [ -d "$DEST" ] || [ -L "$DEST" ]; then
    echo "   Removing existing installation..."
    rm -rf "$DEST"
fi

cp -R "$APP_BUNDLE" "$DEST"
echo "✅ Installed to /Applications/YouTubeTranscriber.app"

# ── Create output directory ──────────────────────────────────────────
mkdir -p "$HOME/Downloads/YouTube Transcripts"

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     ✅ Installation complete!                    ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  Launch from:                                    ║"
echo "║    • Finder → Applications → YouTubeTranscriber  ║"
echo "║    • Spotlight → type 'YouTubeTranscriber'       ║"
echo "║    • Or double-click in /Applications            ║"
echo "║                                                  ║"
echo "║  No terminal needed! 🎉                          ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Tip: Drag YouTubeTranscriber from /Applications to your Dock."
echo ""
