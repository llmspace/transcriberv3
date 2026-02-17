"""
Deepgram Speech-to-Text integration.
Uses Nova-3 Monolingual (English), pre-recorded mode.
Includes exponential backoff for rate-limit (429) responses.
"""

import json
import logging
import time
import random
import requests
from pathlib import Path

from app.core.security_utils import keychain_get_api_key
from app.core.error_codes import JobError
from app.core.constants import (
    ErrorCode, DEEPGRAM_API_BASE, DEEPGRAM_MODEL, DEEPGRAM_LANGUAGE,
    MIN_CHUNK_SEC,
)

logger = logging.getLogger(__name__)

DEEPGRAM_PRERECORDED_URL = f"{DEEPGRAM_API_BASE}/listen"


def verify_api_key(api_key: str) -> tuple[bool, str]:
    """
    Verify a Deepgram API key with a lightweight request.
    Returns (success: bool, message: str).
    """
    try:
        resp = requests.get(
            f"{DEEPGRAM_API_BASE}/projects",
            headers={"Authorization": f"Token {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "Key verified"
        elif resp.status_code in (401, 403):
            return False, "Key invalid or rejected"
        else:
            return False, f"Unexpected response: {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Network error — could not reach Deepgram"
    except requests.exceptions.Timeout:
        return False, "Network error — request timed out"
    except Exception as e:
        return False, f"Network error: {e}"


_MAX_RATE_LIMIT_RETRIES = 4
_RATE_LIMIT_BASE_DELAY = 2.0   # seconds — doubles each retry with jitter


def transcribe_audio(audio_path: Path, api_key: str | None = None,
                     transcript_output_path: Path | None = None) -> dict:
    """
    Transcribe an audio file using Deepgram Nova-3 Monolingual (pre-recorded).
    Retries up to 4 times with exponential backoff on 429 rate-limit responses.
    Returns the Deepgram response dict.
    """
    if not api_key:
        api_key = keychain_get_api_key()
    if not api_key:
        raise JobError(ErrorCode.DEEPGRAM_TRANSCRIBE_FAILED,
                       "Deepgram API key not found in Keychain")

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/mpeg",
    }

    params = {
        "model": DEEPGRAM_MODEL,
        "language": DEEPGRAM_LANGUAGE,
        "smart_format": "true",
        "punctuate": "true",
        "paragraphs": "true",
    }

    file_size = audio_path.stat().st_size
    # Adaptive timeout: ~1 min per 10MB, minimum 120s
    timeout_sec = max(120, int(file_size / (10 * 1024 * 1024) * 60) + 60)

    for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
        try:
            with open(audio_path, 'rb') as f:
                resp = requests.post(
                    DEEPGRAM_PRERECORDED_URL,
                    headers=headers,
                    params=params,
                    data=f,
                    timeout=timeout_sec,
                )
        except requests.exceptions.Timeout:
            raise JobError(ErrorCode.DEEPGRAM_TIMEOUT,
                           "Deepgram request timed out", retryable=True)
        except requests.exceptions.ConnectionError:
            raise JobError(ErrorCode.NETWORK_TRANSIENT,
                           "Network error connecting to Deepgram", retryable=True)
        except Exception as e:
            raise JobError(ErrorCode.DEEPGRAM_TRANSCRIBE_FAILED,
                           f"Deepgram request failed: {e}", retryable=True)

        if resp.status_code == 504:
            raise JobError(ErrorCode.DEEPGRAM_TIMEOUT,
                           "Deepgram returned 504 Gateway Timeout", retryable=True)

        if resp.status_code == 429:
            if attempt < _MAX_RATE_LIMIT_RETRIES:
                # Exponential backoff with jitter: 2s, 4s, 8s, 16s (+/- 10%)
                delay = _RATE_LIMIT_BASE_DELAY * (2 ** attempt)
                delay *= 1 + random.uniform(-0.1, 0.1)
                logger.warning(
                    "Deepgram rate limited (429) — retrying in %.1fs (attempt %d/%d)",
                    delay, attempt + 1, _MAX_RATE_LIMIT_RETRIES,
                )
                time.sleep(delay)
                continue
            raise JobError(ErrorCode.NETWORK_TRANSIENT,
                           f"Deepgram rate limited (429) after {_MAX_RATE_LIMIT_RETRIES} retries",
                           retryable=True)

        if resp.status_code != 200:
            # Sanitize error message (never log API key)
            error_body = resp.text[:300] if resp.text else "No response body"
            raise JobError(ErrorCode.DEEPGRAM_TRANSCRIBE_FAILED,
                           f"Deepgram returned {resp.status_code}: {error_body}")

        try:
            result = resp.json()
        except json.JSONDecodeError:
            raise JobError(ErrorCode.DEEPGRAM_TRANSCRIBE_FAILED,
                           "Failed to parse Deepgram response JSON")

        # Save raw response if output path provided
        if transcript_output_path:
            transcript_output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(transcript_output_path, 'w') as f:
                json.dump(result, f, indent=2)

        return result

    # Should never reach here
    raise JobError(ErrorCode.NETWORK_TRANSIENT, "Deepgram request exhausted retries", retryable=True)


def extract_transcript_text(deepgram_response: dict) -> str:
    """
    Extract plain text transcript from Deepgram response.
    Uses paragraphs if available, falls back to channels/alternatives.
    """
    try:
        results = deepgram_response.get('results', {})

        # Try paragraphs first
        paragraphs = results.get('channels', [{}])[0].get('alternatives', [{}])[0].get('paragraphs', {})
        if paragraphs and paragraphs.get('paragraphs'):
            text_parts = []
            for para in paragraphs['paragraphs']:
                sentences = para.get('sentences', [])
                para_text = ' '.join(s.get('text', '') for s in sentences)
                if para_text.strip():
                    text_parts.append(para_text.strip())
            if text_parts:
                return '\n\n'.join(text_parts)

        # Fallback to transcript
        transcript = results.get('channels', [{}])[0].get('alternatives', [{}])[0].get('transcript', '')
        if transcript:
            return transcript.strip()

    except (IndexError, KeyError, TypeError) as e:
        logger.warning("Error extracting transcript: %s", e)

    return ""
