#!/usr/bin/env python3
"""
video-to-text-transcriber v1.0.0 — Main entry point.
Designed to be bundled with PyInstaller into a native macOS .app.
"""

import sys
import os
import logging
import traceback
from pathlib import Path
from datetime import datetime

# ── Ensure Homebrew paths are in PATH ────────────────────────────────
# When launched as a .app bundle, macOS does NOT source ~/.zshrc or
# ~/.bash_profile, so Homebrew's bin directories are missing from PATH.
# We add all common Homebrew locations so yt-dlp and ffmpeg are found.
HOMEBREW_PATHS = [
    "/opt/homebrew/bin",          # Apple Silicon default
    "/opt/homebrew/sbin",
    "/usr/local/bin",             # Intel Mac default
    "/usr/local/sbin",
    os.path.expanduser("~/Library/Python/3.12/bin"),
    os.path.expanduser("~/Library/Python/3.11/bin"),
    os.path.expanduser("~/Library/Python/3.13/bin"),
    "/Library/Frameworks/Python.framework/Versions/3.12/bin",
    "/Library/Frameworks/Python.framework/Versions/3.11/bin",
]

current_path = os.environ.get("PATH", "")
for p in HOMEBREW_PATHS:
    if os.path.isdir(p) and p not in current_path:
        current_path = p + ":" + current_path
os.environ["PATH"] = current_path

# ── Determine project root ────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # Running inside a PyInstaller bundle
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    # Running from source
    PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Logging setup (writes to ~/Library/Logs/video-to-text-transcriber/) ─────
LOG_DIR = Path.home() / "Library" / "Logs" / "video-to-text-transcriber"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("video-to-text-transcriber")


def show_crash_dialog(error_msg: str):
    """Show a native macOS alert on crash (no terminal needed)."""
    try:
        import subprocess
        safe_msg = error_msg.replace('"', '\\"').replace("'", "\\'")[:500]
        subprocess.run([
            "osascript", "-e",
            f'display alert "video-to-text-transcriber Error" '
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
        logger.error("Missing tools. PATH = %s", os.environ.get("PATH", ""))
        msg = "Missing required tools:\\n\\n" + "\\n".join(missing)
        show_crash_dialog(msg)
        sys.exit(1)

    # Log found paths for debugging
    logger.info("yt-dlp found at: %s", shutil.which("yt-dlp"))
    logger.info("ffmpeg found at: %s", shutil.which("ffmpeg"))


def main():
    logger.info("=" * 60)
    logger.info("video-to-text-transcriber v1.0.0 starting at %s", datetime.now().isoformat())
    logger.info("Python: %s", sys.executable)
    logger.info("Project root: %s", PROJECT_ROOT)
    logger.info("Frozen: %s", getattr(sys, 'frozen', False))
    logger.info("PATH: %s", os.environ.get("PATH", ""))
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
