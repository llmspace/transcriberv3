"""
Security utilities for YouTubeTranscriber.
- Path traversal protection
- Filename sanitization
- Safe subprocess execution (argument arrays only)
- Keychain integration (macOS)
"""

import os
import re
import subprocess
import pathlib
import logging

from app.core.constants import (
    UNSAFE_FILENAME_CHARS,
    MAX_FOLDER_NAME_LEN,
    KEYCHAIN_SERVICE,
    KEYCHAIN_ACCOUNT,
)

logger = logging.getLogger(__name__)


# ── Filename / path safety ────────────────────────────────────────────

def sanitize_title(title: str) -> str:
    """Sanitize a YouTube title for use as a folder name."""
    if not title:
        return ""
    # Replace unsafe characters with underscore
    safe = re.sub(UNSAFE_FILENAME_CHARS, '_', title)
    # Remove path traversal sequences
    safe = safe.replace('..', '')
    # Remove path separators
    safe = safe.replace('/', '_').replace('\\', '_')
    # Collapse multiple underscores/spaces
    safe = re.sub(r'[_\s]+', ' ', safe).strip()
    # Truncate
    if len(safe) > MAX_FOLDER_NAME_LEN:
        safe = safe[:MAX_FOLDER_NAME_LEN].rstrip()
    # Remove leading/trailing dots (hidden files on macOS)
    safe = safe.strip('.')
    return safe if safe else ""


def safe_output_path(output_root: pathlib.Path, title: str, video_id: str) -> pathlib.Path:
    """
    Build a safe output folder path.  Enforces that realpath(result) starts
    with realpath(output_root).  Falls back to 'video_<video_id>' on failure.
    """
    sanitized = sanitize_title(title)
    if not sanitized:
        sanitized = f"video_{video_id}"

    candidate = output_root / sanitized
    try:
        real_root = output_root.resolve(strict=False)
        real_candidate = candidate.resolve(strict=False)
        if not str(real_candidate).startswith(str(real_root)):
            raise ValueError("Path traversal detected")
    except Exception:
        candidate = output_root / f"video_{video_id}"

    return candidate


# ── Subprocess safety ─────────────────────────────────────────────────

def run_subprocess(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Execute a subprocess using argument arrays only.
    shell=True is explicitly forbidden.
    """
    if not isinstance(args, (list, tuple)):
        raise TypeError("Subprocess args must be a list/tuple, not a string")

    # Force shell=False — remove any caller-supplied value, then set it once
    kwargs.pop('shell', None)

    logger.debug("Running subprocess: %s", ' '.join(str(a) for a in args))
    return subprocess.run(args, shell=False, **kwargs)


def run_subprocess_capture(args: list[str], timeout: int = 300, **kwargs) -> subprocess.CompletedProcess:
    """Run subprocess and capture stdout/stderr."""
    return run_subprocess(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        **kwargs,
    )


# ── Keychain integration (macOS) ──────────────────────────────────────

def keychain_get_api_key() -> str | None:
    """Retrieve the Deepgram API key from macOS Keychain."""
    try:
        result = run_subprocess_capture([
            "security", "find-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
            "-w",  # print password only
        ], timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    except Exception as e:
        logger.warning("Keychain read failed: %s", type(e).__name__)
    return None


def keychain_set_api_key(api_key: str) -> bool:
    """Store or update the Deepgram API key in macOS Keychain."""
    try:
        # Try to delete existing entry first (ignore errors)
        run_subprocess_capture([
            "security", "delete-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
        ], timeout=10)
    except Exception:
        pass

    try:
        result = run_subprocess_capture([
            "security", "add-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
            "-w", api_key,
            "-U",  # update if exists
        ], timeout=10)
        return result.returncode == 0
    except Exception as e:
        logger.error("Keychain write failed: %s", type(e).__name__)
        return False


def keychain_delete_api_key() -> bool:
    """Delete the Deepgram API key from macOS Keychain."""
    try:
        result = run_subprocess_capture([
            "security", "delete-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
        ], timeout=10)
        return result.returncode == 0
    except Exception:
        return False
