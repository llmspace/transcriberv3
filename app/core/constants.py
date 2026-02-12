"""
Shared constants for YouTubeTranscriber.
Single source of truth — imported by every other module.
"""

import os
import pathlib

# ── Application identity ──────────────────────────────────────────────
APP_NAME = "YouTubeTranscriber"
APP_BUNDLE_ID = "com.local.youtubetranscriber"
APP_VERSION = "3.0.0"

# ── Filesystem paths ─────────────────────────────────────────────────
HOME = pathlib.Path.home()

DEFAULT_OUTPUT_ROOT = HOME / "Downloads" / "YouTube Transcripts"
APP_SUPPORT_DIR = HOME / "Library" / "Application Support" / APP_NAME
APP_CACHE_DIR = HOME / "Library" / "Caches" / APP_NAME
JOBS_CACHE_DIR = APP_CACHE_DIR / "jobs"
DB_PATH = APP_SUPPORT_DIR / "app.db"
CONFIG_PATH = APP_SUPPORT_DIR / "config.json"

# Cookies
DEFAULT_COOKIES_DIR = HOME / "Downloads" / APP_NAME
DEFAULT_COOKIES_PATH = DEFAULT_COOKIES_DIR / "youtube_cookies.txt"

# ── Keychain identifiers ─────────────────────────────────────────────
KEYCHAIN_SERVICE = "YouTubeTranscriber:Deepgram"
KEYCHAIN_ACCOUNT = "default"

# ── Job status values ─────────────────────────────────────────────────
class JobStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

# ── Job stage values (ordered) ────────────────────────────────────────
class JobStage:
    VALIDATING_URL = "VALIDATING_URL"
    FETCHING_METADATA = "FETCHING_METADATA"
    TRYING_CREATOR_CAPTIONS = "TRYING_CREATOR_CAPTIONS"
    PARSING_CAPTIONS = "PARSING_CAPTIONS"
    WRITING_TXT = "WRITING_TXT"
    SELECTING_AUDIO_STREAM = "SELECTING_AUDIO_STREAM"
    DOWNLOADING_AUDIO = "DOWNLOADING_AUDIO"
    NORMALIZING_AUDIO = "NORMALIZING_AUDIO"
    CHUNKING_AUDIO = "CHUNKING_AUDIO"
    TRANSCRIBING_DEEPGRAM = "TRANSCRIBING_DEEPGRAM"
    MERGING_TRANSCRIPT = "MERGING_TRANSCRIPT"
    CLEANUP = "CLEANUP"

# ── Chunk status ──────────────────────────────────────────────────────
class ChunkStatus:
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"

# ── Error codes ───────────────────────────────────────────────────────
class ErrorCode:
    # Non-retryable
    INVALID_URL = "ERR_INVALID_URL"
    VIDEO_UNAVAILABLE = "ERR_VIDEO_UNAVAILABLE"
    GEO_BLOCKED = "ERR_GEO_BLOCKED"
    RESTRICTED_CONTENT = "ERR_RESTRICTED_CONTENT"
    CAPTIONS_NOT_FOUND = "ERR_CAPTIONS_NOT_FOUND_CREATOR_EN"
    FFMPEG_NORMALIZE = "ERR_FFMPEG_NORMALIZE"
    CHUNKING = "ERR_CHUNKING"

    # Retryable
    DOWNLOAD_FAILED = "ERR_DOWNLOAD_FAILED"
    DEEPGRAM_TRANSCRIBE_FAILED = "ERR_DEEPGRAM_TRANSCRIBE_FAILED"
    NETWORK_TRANSIENT = "ERR_NETWORK_TRANSIENT"
    DEEPGRAM_TIMEOUT = "ERR_DEEPGRAM_TIMEOUT"

    # Special (not failure)
    CREATOR_CAPTIONS_USED = "CREATOR_CAPTIONS_USED_EN"

RETRYABLE_ERRORS = {
    ErrorCode.DOWNLOAD_FAILED,
    ErrorCode.DEEPGRAM_TRANSCRIBE_FAILED,
    ErrorCode.NETWORK_TRANSIENT,
    ErrorCode.DEEPGRAM_TIMEOUT,
}

# ── Audio pipeline defaults ───────────────────────────────────────────
CHUNK_THRESHOLD_HOURS = 2
CHUNK_THRESHOLD_SEC = CHUNK_THRESHOLD_HOURS * 3600
BASE_CHUNK_SEC = 3600          # 60 minutes
CHUNK_OVERLAP_SEC = 2
MIN_CHUNK_SEC = 300            # 5 minutes — adaptive timeout floor

# Normalization target
NORM_CHANNELS = 1
NORM_SAMPLE_RATE = 16000
NORM_BITRATE = "96k"
NORM_FORMAT = "mp3"

# Audio stream selection
PREFERRED_ABR_KBPS = 96
MIN_ABR_KBPS = 64
MAX_ABR_KBPS = 128

# ── Progress mapping ─────────────────────────────────────────────────
PROGRESS_VALIDATE = 5
PROGRESS_METADATA = 10
PROGRESS_CAPTIONS_TRY = 15
PROGRESS_CAPTIONS_PARSE = 20
PROGRESS_CAPTIONS_WRITE = 25
PROGRESS_AUDIO_SELECT = 30
PROGRESS_AUDIO_DOWNLOAD = 45
PROGRESS_AUDIO_NORMALIZE = 55
PROGRESS_AUDIO_CHUNK = 60
PROGRESS_TRANSCRIBE_START = 60
PROGRESS_TRANSCRIBE_END = 95
PROGRESS_MERGE = 96
PROGRESS_WRITE = 98
PROGRESS_CLEANUP = 100

# ── Cookies ───────────────────────────────────────────────────────────
class CookiesMode:
    OFF = "OFF"
    USE_FILE = "USE_FILE"

# ── Deepgram ──────────────────────────────────────────────────────────
DEEPGRAM_API_BASE = "https://api.deepgram.com/v1"
DEEPGRAM_MODEL = "nova-3"
DEEPGRAM_LANGUAGE = "en"

# ── Misc ──────────────────────────────────────────────────────────────
MAX_AUTO_RETRIES = 1
YOUTUBE_URL_PATTERNS = [
    r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
]

# Characters forbidden in folder names (macOS + safety)
UNSAFE_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'
MAX_FOLDER_NAME_LEN = 200
