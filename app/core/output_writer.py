"""
Output writer: writes final transcript TXT files.
"""

import logging
from pathlib import Path

from app.core.security_utils import safe_output_path

logger = logging.getLogger(__name__)


def write_transcript(text: str, output_root: Path, title: str, video_id: str) -> Path:
    """
    Write transcript to <OutputRoot>/<SanitizedTitle>/<video_id>.txt
    Returns the path to the written file.
    """
    folder = safe_output_path(output_root, title, video_id)
    folder.mkdir(parents=True, exist_ok=True)

    output_file = folder / f"{video_id}.txt"
    output_file.write_text(text, encoding='utf-8')

    logger.info("Wrote transcript: %s", output_file)
    return output_file


def transcript_exists(output_root: Path, video_id: str) -> bool:
    """
    Check if a transcript file already exists for this video_id.
    Searches <OutputRoot>/**/<video_id>.txt
    """
    pattern = f"**/{video_id}.txt"
    matches = list(output_root.glob(pattern))
    return len(matches) > 0
