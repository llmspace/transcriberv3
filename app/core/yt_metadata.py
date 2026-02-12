"""
YouTube metadata fetching via yt-dlp.
"""

import json
import logging
from pathlib import Path

from app.core.security_utils import run_subprocess_capture
from app.core.error_codes import JobError
from app.core.constants import ErrorCode, CookiesMode, DEFAULT_COOKIES_PATH

logger = logging.getLogger(__name__)


def fetch_metadata(video_url: str, cookies_mode: str = CookiesMode.OFF,
                   cookies_path: Path | None = None) -> dict:
    """
    Fetch video metadata using yt-dlp --dump-json.
    Returns dict with at least 'id', 'title', 'duration', 'formats'.
    """
    args = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--skip-download",
    ]

    if cookies_mode == CookiesMode.USE_FILE:
        cp = cookies_path or DEFAULT_COOKIES_PATH
        if cp.exists():
            args.extend(["--cookies", str(cp)])

    args.append(video_url)

    try:
        result = run_subprocess_capture(args, timeout=60)
    except Exception as e:
        raise JobError(ErrorCode.NETWORK_TRANSIENT, f"yt-dlp metadata fetch failed: {e}")

    if result.returncode != 0:
        stderr = result.stderr or ""
        if "Video unavailable" in stderr or "is not available" in stderr:
            raise JobError(ErrorCode.VIDEO_UNAVAILABLE, f"Video unavailable: {stderr[:200]}")
        if "geo" in stderr.lower() or "country" in stderr.lower():
            raise JobError(ErrorCode.GEO_BLOCKED, f"Geo-blocked: {stderr[:200]}")
        if "Sign in" in stderr or "age" in stderr.lower() or "consent" in stderr.lower():
            raise JobError(ErrorCode.RESTRICTED_CONTENT,
                           f"Restricted content (login/age required): {stderr[:200]}")
        raise JobError(ErrorCode.NETWORK_TRANSIENT, f"yt-dlp failed (rc={result.returncode}): {stderr[:300]}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise JobError(ErrorCode.NETWORK_TRANSIENT, f"Failed to parse yt-dlp JSON: {e}")

    return data


def get_video_duration(metadata: dict) -> float:
    """Get video duration in seconds from metadata."""
    return float(metadata.get('duration', 0))
