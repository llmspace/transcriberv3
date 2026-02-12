"""
Time-based audio chunking using ffmpeg.
Chunks only when duration > 2 hours, or when adaptive timeout forces it.
"""

import json
import math
import logging
from pathlib import Path

from app.core.security_utils import run_subprocess_capture
from app.core.error_codes import JobError
from app.core.constants import (
    ErrorCode, BASE_CHUNK_SEC, CHUNK_OVERLAP_SEC, CHUNK_THRESHOLD_SEC,
)
from app.core.models_sqlite import JobChunk

logger = logging.getLogger(__name__)


def needs_chunking(duration_sec: float) -> bool:
    """Check if audio needs chunking based on duration."""
    return duration_sec > CHUNK_THRESHOLD_SEC


def create_chunk_manifest(duration_sec: float,
                          chunk_duration_sec: int = BASE_CHUNK_SEC,
                          overlap_sec: int = CHUNK_OVERLAP_SEC) -> list[dict]:
    """
    Create chunk manifest entries based on duration.
    Returns list of dicts with idx, start_sec, end_sec.
    """
    chunks = []
    idx = 0
    start = 0.0

    while start < duration_sec:
        end = min(start + chunk_duration_sec, duration_sec)
        chunks.append({
            'idx': idx,
            'start_sec': start,
            'end_sec': end,
        })
        idx += 1
        # Next chunk starts at (end - overlap) to create overlap
        start = end - overlap_sec if end < duration_sec else duration_sec

    return chunks


def split_audio_into_chunks(normalized_path: Path, chunks_dir: Path,
                            manifest_entries: list[dict]) -> list[Path]:
    """
    Split normalized audio into chunks using ffmpeg.
    Returns list of chunk file paths.
    """
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths = []

    for entry in manifest_entries:
        idx = entry['idx']
        start = entry['start_sec']
        end = entry['end_sec']
        duration = end - start

        chunk_file = chunks_dir / f"chunk_{idx:03d}.mp3"

        args = [
            "ffmpeg",
            "-y",
            "-i", str(normalized_path),
            "-ss", str(start),
            "-t", str(duration),
            "-codec:a", "copy",  # No re-encoding needed, already normalized
            str(chunk_file),
        ]

        try:
            result = run_subprocess_capture(args, timeout=120)
        except Exception as e:
            raise JobError(ErrorCode.CHUNKING, f"Chunk {idx} creation failed: {e}")

        if result.returncode != 0:
            raise JobError(ErrorCode.CHUNKING,
                           f"ffmpeg chunk {idx} failed: {result.stderr[:200] if result.stderr else 'unknown error'}")

        if not chunk_file.exists():
            raise JobError(ErrorCode.CHUNKING, f"Chunk file {idx} not created")

        chunk_paths.append(chunk_file)

    # Write manifest
    manifest = {
        'chunking_mode': 'time_based',
        'base_chunk_sec': manifest_entries[0]['end_sec'] - manifest_entries[0]['start_sec'] if manifest_entries else BASE_CHUNK_SEC,
        'overlap_sec': CHUNK_OVERLAP_SEC,
        'chunks': [
            {
                'idx': e['idx'],
                'file': f"chunk_{e['idx']:03d}.mp3",
                'start_sec': e['start_sec'],
                'end_sec': e['end_sec'],
            }
            for e in manifest_entries
        ],
    }

    with open(chunks_dir / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)

    logger.info("Created %d chunks in %s", len(chunk_paths), chunks_dir)
    return chunk_paths


def create_job_chunks(job_id: str, manifest_entries: list[dict]) -> list[JobChunk]:
    """Create JobChunk objects from manifest entries."""
    return [
        JobChunk(
            job_id=job_id,
            idx=e['idx'],
            start_sec=e['start_sec'],
            end_sec=e['end_sec'],
        )
        for e in manifest_entries
    ]


def split_chunk_in_half(start_sec: float, end_sec: float) -> list[dict]:
    """
    Split a time interval in half for adaptive timeout retry.
    Returns two manifest entries.
    """
    mid = (start_sec + end_sec) / 2.0
    return [
        {'start_sec': start_sec, 'end_sec': mid},
        {'start_sec': mid - CHUNK_OVERLAP_SEC, 'end_sec': end_sec},
    ]
