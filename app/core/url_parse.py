"""
YouTube URL parsing and validation.
"""

import re
from urllib.parse import urlparse, parse_qs

from app.core.constants import YOUTUBE_URL_PATTERNS
from app.core.error_codes import JobError, ErrorCode


def extract_video_id(url: str) -> str | None:
    """
    Extract the 11-character video_id from a YouTube URL.
    Returns None if the URL is not a valid YouTube URL.
    """
    url = url.strip()
    if not url:
        return None

    # Try regex patterns
    for pattern in YOUTUBE_URL_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)

    # Fallback: parse query string for 'v' parameter
    try:
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
            qs = parse_qs(parsed.query)
            v = qs.get('v', [None])[0]
            if v and re.match(r'^[a-zA-Z0-9_-]{11}$', v):
                return v
    except Exception:
        pass

    return None


def validate_youtube_url(url: str) -> str:
    """
    Validate a YouTube URL and return the video_id.
    Raises JobError if invalid.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise JobError(ErrorCode.INVALID_URL, f"Not a valid YouTube URL: {url}")
    return video_id


def is_youtube_url(url: str) -> bool:
    """Quick check if a string looks like a YouTube URL."""
    return extract_video_id(url) is not None


def parse_input_lines(text: str) -> list[str]:
    """
    Parse pasted text into a list of YouTube URLs.
    - Trims whitespace
    - Ignores empty lines
    - Rejects non-YouTube URLs (silently skips)
    """
    urls = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if is_youtube_url(line):
            urls.append(line)
    return urls


def parse_csv_file(filepath: str) -> list[str]:
    """
    Parse a CSV file for YouTube URLs.
    - If header includes 'url' or 'youtube_url' (case-insensitive), use that column
    - Else use first column
    - Ignore rows without valid YouTube URLs
    """
    import csv

    urls = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return urls

    # Detect header
    header = rows[0]
    url_col_idx = 0
    for i, col in enumerate(header):
        col_lower = col.strip().lower()
        if col_lower in ('url', 'youtube_url'):
            url_col_idx = i
            rows = rows[1:]  # skip header
            break
    else:
        # No recognized header — check if first row is itself a URL
        if is_youtube_url(header[0].strip()):
            pass  # first row is data
        else:
            rows = rows[1:]  # assume header, skip

    for row in rows:
        if url_col_idx < len(row):
            cell = row[url_col_idx].strip()
            if is_youtube_url(cell):
                urls.append(cell)

    return urls


def parse_txt_file(filepath: str) -> list[str]:
    """Parse a .txt file containing one URL per line."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return parse_input_lines(f.read())


def parse_input_file(filepath: str) -> list[str]:
    """Parse a .txt or .csv file for YouTube URLs."""
    ext = filepath.lower().rsplit('.', 1)[-1] if '.' in filepath else ''
    if ext == 'csv':
        return parse_csv_file(filepath)
    else:
        return parse_txt_file(filepath)
