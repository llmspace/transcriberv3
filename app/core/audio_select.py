"""
Audio stream selection policy (speech-first).
Selects the best audio-only stream for speech transcription.
"""

import json
import logging
from pathlib import Path

from app.core.constants import PREFERRED_ABR_KBPS, MIN_ABR_KBPS, MAX_ABR_KBPS

logger = logging.getLogger(__name__)


def select_audio_stream(metadata: dict, meta_dir: Path | None = None) -> dict:
    """
    Select the best audio-only stream for speech transcription.

    Policy:
    1. Filter formats to audio-only (vcodec == "none")
    2. Prefer abr 64–128 kbps
    3. Choose abr closest to 96 kbps
    4. If 96 not available but 128 available, choose 128 (preferred over 64)
    5. Enforce floor: if any stream ≥64 exists, never choose <64 intentionally
    6. If abr missing/unreliable or none meet floor: fallback to best available audio-only

    Returns dict with format_id, abr, ext, and selection_reason.
    """
    formats = metadata.get('formats', [])

    # Filter audio-only streams
    audio_streams = []
    for fmt in formats:
        vcodec = fmt.get('vcodec', '')
        acodec = fmt.get('acodec', '')
        if vcodec in ('none', None, '') and acodec not in ('none', None, ''):
            abr = fmt.get('abr')
            if abr is not None:
                try:
                    abr = float(abr)
                except (ValueError, TypeError):
                    abr = None
            audio_streams.append({
                'format_id': fmt.get('format_id', ''),
                'abr': abr,
                'ext': fmt.get('ext', ''),
                'acodec': acodec,
                'filesize': fmt.get('filesize'),
                'format_note': fmt.get('format_note', ''),
            })

    if not audio_streams:
        return {
            'format_id': 'bestaudio',
            'abr': None,
            'ext': None,
            'selection_reason': 'No audio-only streams found; using bestaudio fallback',
        }

    # Separate streams with valid ABR
    with_abr = [s for s in audio_streams if s['abr'] is not None and s['abr'] > 0]
    without_abr = [s for s in audio_streams if s['abr'] is None or s['abr'] <= 0]

    selected = None
    reason = ""

    if with_abr:
        # Streams meeting the floor (≥64 kbps)
        above_floor = [s for s in with_abr if s['abr'] >= MIN_ABR_KBPS]

        if above_floor:
            # Prefer range 64–128
            in_range = [s for s in above_floor if s['abr'] <= MAX_ABR_KBPS]

            if in_range:
                # Sort by distance to 96, with tie-breaking favoring higher abr
                in_range.sort(key=lambda s: (abs(s['abr'] - PREFERRED_ABR_KBPS), -s['abr']))
                selected = in_range[0]
                reason = f"Closest to {PREFERRED_ABR_KBPS}kbps in [{MIN_ABR_KBPS}-{MAX_ABR_KBPS}] range"
            else:
                # All above 128 — choose lowest above floor
                above_floor.sort(key=lambda s: s['abr'])
                selected = above_floor[0]
                reason = f"No stream in [{MIN_ABR_KBPS}-{MAX_ABR_KBPS}] range; chose lowest above floor"
        else:
            # All below 64 — fallback to highest available
            with_abr.sort(key=lambda s: -s['abr'])
            selected = with_abr[0]
            reason = f"No stream >= {MIN_ABR_KBPS}kbps; chose highest available"
    else:
        # No reliable ABR info — pick first audio stream
        selected = audio_streams[0]
        reason = "No reliable ABR data; chose first audio-only stream"

    result = {
        'format_id': selected['format_id'],
        'abr': selected.get('abr'),
        'ext': selected.get('ext'),
        'acodec': selected.get('acodec'),
        'selection_reason': reason,
    }

    # Save selection metadata
    if meta_dir:
        meta_dir.mkdir(parents=True, exist_ok=True)
        with open(meta_dir / "selected_format.json", 'w') as f:
            json.dump(result, f, indent=2)

    logger.info("Selected audio stream: format_id=%s abr=%s reason=%s",
                result['format_id'], result.get('abr'), reason)

    return result
