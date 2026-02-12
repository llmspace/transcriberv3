"""
Captions fetching: creator-provided English captions only.
Uses yt-dlp with --write-subs (NO --write-auto-subs).
"""

import os
import glob
import logging
import tempfile
from pathlib import Path

from app.core.security_utils import run_subprocess_capture
from app.core.constants import CookiesMode, DEFAULT_COOKIES_PATH

logger = logging.getLogger(__name__)


def fetch_creator_captions(video_url: str, video_id: str,
                           work_dir: Path,
                           cookies_mode: str = CookiesMode.OFF,
                           cookies_path: Path | None = None) -> Path | None:
    """
    Attempt to download creator-provided English captions (VTT format).
    Returns path to the VTT file, or None if no creator captions found.

    MUST NOT use --write-auto-subs.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    def _try_fetch(use_cookies: bool) -> Path | None:
        args = [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--sub-langs", "en.*",
            "--sub-format", "vtt",
            "--no-playlist",
            "-o", str(work_dir / "%(id)s.%(ext)s"),
        ]

        # Explicitly do NOT add --write-auto-subs
        if use_cookies:
            cp = cookies_path or DEFAULT_COOKIES_PATH
            if cp.exists():
                args.extend(["--cookies", str(cp)])
            else:
                return None  # No cookies file, skip retry

        args.append(video_url)

        try:
            result = run_subprocess_capture(args, timeout=60)
        except Exception as e:
            logger.warning("Captions fetch error: %s", e)
            return None

        # Look for downloaded VTT files
        vtt_files = list(work_dir.glob(f"{video_id}*.vtt"))
        if not vtt_files:
            # Also check for .en.vtt pattern
            vtt_files = list(work_dir.glob(f"*.en*.vtt"))

        if vtt_files:
            # Filter to English captions only
            for vtt in vtt_files:
                name_lower = vtt.name.lower()
                # Accept files with .en. in name (creator captions)
                if '.en.' in name_lower or '.en-' in name_lower:
                    return vtt
            # If only one VTT and it matches video_id, accept it
            if len(vtt_files) == 1:
                return vtt_files[0]

        return None

    # First attempt: without cookies
    result = _try_fetch(use_cookies=False)
    if result:
        return result

    # Second attempt: with cookies (if enabled)
    if cookies_mode == CookiesMode.USE_FILE:
        logger.info("Retrying captions fetch with cookies...")
        result = _try_fetch(use_cookies=True)
        if result:
            return result

    return None
