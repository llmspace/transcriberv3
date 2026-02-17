#!/bin/bash
# video-to-text-transcriber v1.0.0 — Uninstall Script
# Removes the app from /Applications and optionally cleans up app data.
#
# Usage:  ./uninstall.sh

set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   video-to-text-transcriber — Uninstaller       ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Remove from /Applications ────────────────────────────────────────
DEST="/Applications/VideoToTextTranscriber.app"
if [ -d "$DEST" ] || [ -L "$DEST" ]; then
    rm -rf "$DEST"
    echo "✅ Removed /Applications/VideoToTextTranscriber.app"
else
    echo "ℹ️  App not found in /Applications (already removed?)"
fi

# ── Ask about app data ──────────────────────────────────────────────
echo ""
echo "Would you like to also remove app data?"
echo "  • ~/Library/Application Support/Video to Text Transcriber/"
echo "  • ~/Library/Caches/Video to Text Transcriber/"
echo "  • ~/Library/Logs/video-to-text-transcriber/"
echo ""
echo "⚠️  Your transcripts in ~/Downloads/Video Transcripts/ will NOT be deleted."
echo ""
read -p "Remove app data? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$HOME/Library/Application Support/Video to Text Transcriber"
    rm -rf "$HOME/Library/Caches/Video to Text Transcriber"
    rm -rf "$HOME/Library/Logs/video-to-text-transcriber"
    echo "✅ App data removed"
else
    echo "ℹ️  App data kept"
fi

echo ""
echo "✅ Uninstall complete."
echo ""
