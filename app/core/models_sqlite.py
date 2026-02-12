"""
SQLite data models (plain dataclasses) for YouTubeTranscriber.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    id: str                          # UUID
    youtube_url: str
    video_id: Optional[str] = None
    title: Optional[str] = None
    status: str = "QUEUED"
    stage: Optional[str] = None
    progress_pct: int = 0
    retry_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: int = 0
    used_creator_captions: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class JobChunk:
    job_id: str
    idx: int
    start_sec: float
    end_sec: float
    status: str = "pending"
    attempts: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
