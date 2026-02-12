"""
Diagnostics: tool version detection and system checks.
"""

import os
import logging
from pathlib import Path

from app.core.security_utils import run_subprocess_capture
from app.core.constants import DEFAULT_COOKIES_PATH

logger = logging.getLogger(__name__)


def get_ytdlp_version() -> str:
    """Return yt-dlp version string, or error message."""
    try:
        result = run_subprocess_capture(["yt-dlp", "--version"], timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        return f"Error (rc={result.returncode})"
    except FileNotFoundError:
        return "Not installed"
    except Exception as e:
        return f"Error: {e}"


def get_ffmpeg_version() -> str:
    """Return ffmpeg version string, or error message."""
    try:
        result = run_subprocess_capture(["ffmpeg", "-version"], timeout=10)
        if result.returncode == 0:
            first_line = result.stdout.strip().splitlines()[0]
            return first_line
        return f"Error (rc={result.returncode})"
    except FileNotFoundError:
        return "Not installed"
    except Exception as e:
        return f"Error: {e}"


def check_cookies_file(cookies_path: Path | None = None) -> dict:
    """Check if cookies.txt exists and return info."""
    path = cookies_path or DEFAULT_COOKIES_PATH
    info = {"detected": False, "path": str(path), "last_modified": None}
    if path.exists():
        info["detected"] = True
        stat = path.stat()
        from datetime import datetime, timezone
        info["last_modified"] = datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat()
    return info


def get_diagnostics(cookies_path: Path | None = None) -> dict:
    """Gather all diagnostic information."""
    return {
        "ytdlp_version": get_ytdlp_version(),
        "ffmpeg_version": get_ffmpeg_version(),
        "cookies": check_cookies_file(cookies_path),
    }
