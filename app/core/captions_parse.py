"""
VTT captions parsing → plain text.
Removes timestamps, cue numbers, styling/markup.
Collapses whitespace, preserves paragraph breaks.
"""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Regex patterns for VTT cleanup
_TIMESTAMP_RE = re.compile(
    r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}.*$',
    re.MULTILINE,
)
_CUE_ID_RE = re.compile(r'^\d+\s*$', re.MULTILINE)
_WEBVTT_HEADER_RE = re.compile(r'^WEBVTT.*$', re.MULTILINE)
_KIND_RE = re.compile(r'^Kind:.*$', re.MULTILINE)
_LANGUAGE_RE = re.compile(r'^Language:.*$', re.MULTILINE)
_NOTE_RE = re.compile(r'^NOTE\s.*$', re.MULTILINE)
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_POSITION_RE = re.compile(r'\b(?:position|align|size|line):\S+', re.IGNORECASE)


def parse_vtt_to_text(vtt_path: Path) -> str:
    """
    Convert a VTT subtitle file to clean plain text.
    """
    content = vtt_path.read_text(encoding='utf-8', errors='replace')

    # Remove WEBVTT header and metadata
    content = _WEBVTT_HEADER_RE.sub('', content)
    content = _KIND_RE.sub('', content)
    content = _LANGUAGE_RE.sub('', content)
    content = _NOTE_RE.sub('', content)

    # Remove timestamps
    content = _TIMESTAMP_RE.sub('', content)

    # Remove cue IDs (standalone numbers)
    content = _CUE_ID_RE.sub('', content)

    # Remove positioning metadata
    content = _POSITION_RE.sub('', content)

    # Remove HTML/VTT styling tags
    content = _HTML_TAG_RE.sub('', content)

    # Process lines: deduplicate consecutive identical lines
    lines = content.splitlines()
    cleaned_lines = []
    prev_line = None
    blank_count = 0

    for line in lines:
        stripped = line.strip()

        if not stripped:
            blank_count += 1
            if blank_count <= 1 and cleaned_lines:
                # Preserve single blank line as paragraph break
                cleaned_lines.append('')
            continue

        blank_count = 0

        # Skip if identical to previous non-empty line (VTT often repeats)
        if stripped == prev_line:
            continue

        cleaned_lines.append(stripped)
        prev_line = stripped

    # Join and collapse excessive whitespace
    text = '\n'.join(cleaned_lines)

    # Collapse multiple blank lines to single
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Collapse multiple spaces within lines
    text = re.sub(r'[ \t]+', ' ', text)

    return text.strip()
