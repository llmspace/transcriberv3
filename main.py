#!/usr/bin/env python3
"""
YouTubeTranscriber v3 — Main entry point.
Designed to be bundled with py2app into a native macOS .app.
"""

import sys
import os
import logging
import traceback
from pathlib import Path
from datetime import datetime

# ── Determine project root ────────────────────────────────────────────
# When bundled by py2app, __file__ is inside the .app bundle.
# We need to find the actual resources directory.
if getattr(sys, 'frozen', False):
    # Running inside a py2app bundle
    PROJECT_ROOT = Path(os.environ.get('RESOURCEPATH', Path(__file__).resolve().parent))
else:
    # Running from source
    PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Logging setup (writes to ~/Library/Logs/YouTubeTranscriber/) ─────
LOG_DIR = Path.home() / "Library" / "Logs" / "YouTubeTranscriber"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("YouTubeTranscriber")


def show_crash_dialog(error_msg: str):
    """Show a native macOS alert on crash (no terminal needed)."""
    try:
        import subprocess
        safe_msg = error_msg.replace('"', '\\"').replace("'", "\\'")[:500]
        subprocess.run([
            "osascript", "-e",
            f'display alert "YouTubeTranscriber Error" '
            f'message "{safe_msg}\\n\\nCheck logs at:\\n{LOG_FILE}" '
            f'as critical buttons {{"OK"}}'
        ], timeout=30)
    except Exception:
        pass  # If even osascript fails, just exit


def check_prerequisites():
    """Check that yt-dlp and ffmpeg are available, show dialog if not."""
    import shutil
    missing = []
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp (install with: brew install yt-dlp)")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg (install with: brew install ffmpeg)")
    if missing:
        msg = "Missing required tools:\\n\\n" + "\\n".join(missing)
        show_crash_dialog(msg)
        sys.exit(1)


def main():
    logger.info("=" * 60)
    logger.info("YouTubeTranscriber v3 starting at %s", datetime.now().isoformat())
    logger.info("Python: %s", sys.executable)
    logger.info("Project root: %s", PROJECT_ROOT)
    logger.info("Frozen: %s", getattr(sys, 'frozen', False))
    logger.info("=" * 60)

    try:
        check_prerequisites()
        from app.desktop.ui_main import main as run_app
        run_app()
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.critical("Fatal error: %s\n%s", error_msg, traceback.format_exc())
        show_crash_dialog(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
