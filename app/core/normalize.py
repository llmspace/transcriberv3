"""
Audio normalization using ffmpeg.
Target: mono, 16kHz, MP3 CBR 96kbps.
"""

import logging
from pathlib import Path

from app.core.security_utils import run_subprocess_capture
from app.core.error_codes import JobError
from app.core.constants import (
    ErrorCode, NORM_CHANNELS, NORM_SAMPLE_RATE, NORM_BITRATE, NORM_FORMAT,
)

logger = logging.getLogger(__name__)


def normalize_audio(input_path: Path, output_dir: Path) -> Path:
    """
    Normalize audio to mono, 16kHz, MP3 CBR 96kbps.
    Uses explicit L+R downmix to preserve both channels.
    Returns path to normalized file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"normalized.{NORM_FORMAT}"

    args = [
        "ffmpeg",
        "-y",                           # overwrite
        "-i", str(input_path),
        # Explicit stereo→mono downmix preserving both channels
        "-af", "pan=mono|c0=0.5*c0+0.5*c1",
        "-ar", str(NORM_SAMPLE_RATE),   # 16kHz
        "-ac", str(NORM_CHANNELS),      # mono
        "-b:a", NORM_BITRATE,           # 96k CBR
        "-codec:a", "libmp3lame",
        str(output_path),
    ]

    try:
        result = run_subprocess_capture(args, timeout=600)
    except Exception as e:
        raise JobError(ErrorCode.FFMPEG_NORMALIZE, f"ffmpeg normalization failed: {e}")

    if result.returncode != 0:
        stderr = result.stderr or ""
        raise JobError(ErrorCode.FFMPEG_NORMALIZE,
                       f"ffmpeg failed (rc={result.returncode}): {stderr[:300]}")

    if not output_path.exists():
        raise JobError(ErrorCode.FFMPEG_NORMALIZE, "Normalized file not created")

    logger.info("Normalized audio: %s", output_path)
    return output_path


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    args = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]

    try:
        result = run_subprocess_capture(args, timeout=30)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass

    return 0.0
