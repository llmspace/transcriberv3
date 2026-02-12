"""
Standardised error handling for YouTubeTranscriber.
"""

from app.core.constants import ErrorCode, RETRYABLE_ERRORS


class JobError(Exception):
    """Raised when a job encounters a known error condition."""

    def __init__(self, code: str, message: str, retryable: bool | None = None):
        self.code = code
        self.message = message
        # auto-detect retryable from code if not explicitly set
        self.retryable = retryable if retryable is not None else (code in RETRYABLE_ERRORS)
        super().__init__(f"[{code}] {message}")


def is_retryable(code: str) -> bool:
    return code in RETRYABLE_ERRORS
