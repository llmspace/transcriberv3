#!/bin/bash
# YouTubeTranscriber v3 — Uninstall Script
# Removes the app from /Applications and optionally cleans up app data.
#
# Usage:  ./uninstall.sh

set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     YouTubeTranscriber v3 — Uninstaller         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Remove from /Applications ────────────────────────────────────────
DEST="/Applications/YouTubeTranscriber.app"
if [ -d "$DEST" ] || [ -L "$DEST" ]; then
    rm -rf "$DEST"
    echo "✅ Removed /Applications/YouTubeTranscriber.app"
else
    echo "ℹ️  App not found in /Applications (already removed?)"
fi

# ── Ask about app data ──────────────────────────────────────────────
echo ""
echo "Would you like to also remove app data?"
echo "  • ~/Library/Application Support/YouTubeTranscriber/"
echo "  • ~/Library/Caches/YouTubeTranscriber/"
echo "  • ~/Library/Logs/YouTubeTranscriber/"
echo ""
echo "⚠️  Your transcripts in ~/Downloads/YouTube Transcripts/ will NOT be deleted."
echo ""
read -p "Remove app data? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$HOME/Library/Application Support/YouTubeTranscriber"
    rm -rf "$HOME/Library/Caches/YouTubeTranscriber"
    rm -rf "$HOME/Library/Logs/YouTubeTranscriber"
    echo "✅ App data removed"
else
    echo "ℹ️  App data kept"
fi

echo ""
echo "✅ Uninstall complete."
echo ""
