"""
Application configuration manager.
Stores settings in a JSON file under Application Support.
"""

import json
import logging
from pathlib import Path

from app.core.constants import (
    CONFIG_PATH, DEFAULT_OUTPUT_ROOT, CookiesMode, DEFAULT_COOKIES_PATH,
    CHUNK_THRESHOLD_HOURS, BASE_CHUNK_SEC, CHUNK_OVERLAP_SEC,
)

# Validation bounds
_CHUNK_THRESHOLD_MIN = 0.25   # 15 minutes
_CHUNK_THRESHOLD_MAX = 12     # 12 hours
_BASE_CHUNK_MIN = 300         # 5 minutes
_BASE_CHUNK_MAX = 7200        # 2 hours

logger = logging.getLogger(__name__)

_DEFAULTS = {
    'output_root': str(DEFAULT_OUTPUT_ROOT),
    'cookies_mode': CookiesMode.OFF,
    'cookies_path': str(DEFAULT_COOKIES_PATH),
    'chunk_threshold_hours': CHUNK_THRESHOLD_HOURS,
    'base_chunk_sec': BASE_CHUNK_SEC,
    'chunk_overlap_sec': CHUNK_OVERLAP_SEC,
    'keep_debug_artifacts': False,
}


class AppConfig:
    """Manages application configuration stored as JSON."""

    def __init__(self, config_path: Path | None = None):
        self.path = config_path or CONFIG_PATH
        self._data: dict = {}
        self.load()

    def load(self):
        """Load config from disk, merging with defaults."""
        self._data = dict(_DEFAULTS)
        if self.path.exists():
            try:
                with open(self.path, 'r') as f:
                    saved = json.load(f)
                self._data.update(saved)
            except Exception as e:
                logger.warning("Failed to load config: %s", e)

    def save(self):
        """Persist config to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        value = self._validate(key, value)
        self._data[key] = value
        self.save()

    def _validate(self, key: str, value):
        """Validate and coerce config values to safe ranges."""
        if key == 'chunk_threshold_hours':
            try:
                value = float(value)
            except (TypeError, ValueError):
                logger.warning("Invalid chunk_threshold_hours %r — using default", value)
                return CHUNK_THRESHOLD_HOURS
            return max(_CHUNK_THRESHOLD_MIN, min(_CHUNK_THRESHOLD_MAX, value))

        if key == 'base_chunk_sec':
            try:
                value = int(value)
            except (TypeError, ValueError):
                logger.warning("Invalid base_chunk_sec %r — using default", value)
                return BASE_CHUNK_SEC
            return max(_BASE_CHUNK_MIN, min(_BASE_CHUNK_MAX, value))

        if key == 'cookies_mode':
            if value not in (CookiesMode.OFF, CookiesMode.USE_FILE):
                logger.warning("Invalid cookies_mode %r — using OFF", value)
                return CookiesMode.OFF

        if key == 'keep_debug_artifacts':
            return bool(value)

        return value

    def as_dict(self) -> dict:
        return dict(self._data)

    @property
    def output_root(self) -> str:
        return self._data.get('output_root', str(DEFAULT_OUTPUT_ROOT))

    @output_root.setter
    def output_root(self, value: str):
        self._data['output_root'] = value
        self.save()

    @property
    def cookies_mode(self) -> str:
        return self._data.get('cookies_mode', CookiesMode.OFF)

    @cookies_mode.setter
    def cookies_mode(self, value: str):
        self._data['cookies_mode'] = value
        self.save()

    @property
    def keep_debug_artifacts(self) -> bool:
        return self._data.get('keep_debug_artifacts', False)

    @keep_debug_artifacts.setter
    def keep_debug_artifacts(self, value: bool):
        self._data['keep_debug_artifacts'] = value
        self.save()
