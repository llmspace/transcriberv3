"""
Audio download via yt-dlp.
"""

import logging
from pathlib import Path

from app.core.security_utils import run_subprocess_capture
from app.core.error_codes import JobError
from app.core.constants import ErrorCode, CookiesMode, DEFAULT_COOKIES_PATH

logger = logging.getLogger(__name__)


def download_audio(video_url: str, format_id: str,
                   output_dir: Path,
                   cookies_mode: str = CookiesMode.OFF,
                   cookies_path: Path | None = None) -> Path:
    """
    Download audio-only stream using yt-dlp.
    Returns path to the downloaded file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "source.%(ext)s")

    args = [
        "yt-dlp",
        "--no-playlist",
        "-f", format_id,
        "-o", output_template,
    ]

    if cookies_mode == CookiesMode.USE_FILE:
        cp = cookies_path or DEFAULT_COOKIES_PATH
        if cp.exists():
            args.extend(["--cookies", str(cp)])

    args.append(video_url)

    try:
        result = run_subprocess_capture(args, timeout=600)
    except Exception as e:
        raise JobError(ErrorCode.DOWNLOAD_FAILED, f"Audio download failed: {e}")

    if result.returncode != 0:
        stderr = result.stderr or ""
        raise JobError(ErrorCode.DOWNLOAD_FAILED,
                       f"yt-dlp download failed (rc={result.returncode}): {stderr[:300]}")

    # Find the downloaded file
    source_files = list(output_dir.glob("source.*"))
    if not source_files:
        raise JobError(ErrorCode.DOWNLOAD_FAILED, "No audio file found after download")

    downloaded = source_files[0]
    logger.info("Downloaded audio: %s", downloaded)
    return downloaded
