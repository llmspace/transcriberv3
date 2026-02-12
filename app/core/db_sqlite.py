"""
SQLite database layer for YouTubeTranscriber.
Thread-safe via check_same_thread=False + explicit locking.
"""

import sqlite3
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from app.core.constants import DB_PATH, APP_SUPPORT_DIR, JobStatus
from app.core.models_sqlite import Job, JobChunk

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    youtube_url TEXT NOT NULL,
    video_id TEXT,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    stage TEXT,
    progress_pct INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    retryable INTEGER DEFAULT 0,
    used_creator_captions INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_video_id ON jobs(video_id);

CREATE TABLE IF NOT EXISTS job_chunks (
    job_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    start_sec REAL,
    end_sec REAL,
    status TEXT DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    PRIMARY KEY (job_id, idx),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_job_chunks_job_idx ON job_chunks(job_id, idx);
"""


class Database:
    """SQLite database wrapper for YouTubeTranscriber."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self._ensure_dirs()
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _ensure_dirs(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _migrate(self):
        cur = self.conn.cursor()
        cur.executescript(_CREATE_TABLES)
        # Set schema version
        cur.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (_SCHEMA_VERSION,),
        )
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(**dict(row))

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> JobChunk:
        return JobChunk(**dict(row))

    # ── Job CRUD ──────────────────────────────────────────────────────

    def create_job(self, youtube_url: str, video_id: str | None = None) -> Job:
        job_id = str(uuid.uuid4())
        now = self._now()
        job = Job(
            id=job_id,
            youtube_url=youtube_url,
            video_id=video_id,
            created_at=now,
            updated_at=now,
        )
        self.conn.execute(
            """INSERT INTO jobs
               (id, youtube_url, video_id, status, progress_pct,
                retry_count, retryable, used_creator_captions,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job.id, job.youtube_url, job.video_id, job.status,
             job.progress_pct, job.retry_count, job.retryable,
             job.used_creator_captions, job.created_at, job.updated_at),
        )
        self.conn.commit()
        return job

    def get_job(self, job_id: str) -> Job | None:
        row = self.conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return self._row_to_job(row) if row else None

    def get_all_jobs(self) -> list[Job]:
        rows = self.conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_queued_jobs(self) -> list[Job]:
        rows = self.conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC",
            (JobStatus.QUEUED,),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def update_job(self, job_id: str, **kwargs):
        kwargs['updated_at'] = self._now()
        sets = ', '.join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [job_id]
        self.conn.execute(
            f"UPDATE jobs SET {sets} WHERE id = ?", vals
        )
        self.conn.commit()

    def update_job_status(self, job_id: str, status: str, stage: str | None = None,
                          progress_pct: int | None = None, **extra):
        fields = {'status': status}
        if stage is not None:
            fields['stage'] = stage
        if progress_pct is not None:
            fields['progress_pct'] = progress_pct
        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.SKIPPED):
            fields['completed_at'] = self._now()
        fields.update(extra)
        self.update_job(job_id, **fields)

    def has_completed_video(self, video_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM jobs WHERE video_id = ? AND status = ? LIMIT 1",
            (video_id, JobStatus.COMPLETED),
        ).fetchone()
        return row is not None

    def delete_job(self, job_id: str):
        self.conn.execute("DELETE FROM job_chunks WHERE job_id = ?", (job_id,))
        self.conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        self.conn.commit()

    def clear_queued_jobs(self):
        self.conn.execute(
            "DELETE FROM jobs WHERE status = ?", (JobStatus.QUEUED,)
        )
        self.conn.commit()

    # ── Chunk CRUD ────────────────────────────────────────────────────

    def create_chunk(self, chunk: JobChunk):
        self.conn.execute(
            """INSERT INTO job_chunks
               (job_id, idx, start_sec, end_sec, status, attempts)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (chunk.job_id, chunk.idx, chunk.start_sec, chunk.end_sec,
             chunk.status, chunk.attempts),
        )
        self.conn.commit()

    def create_chunks(self, chunks: list[JobChunk]):
        self.conn.executemany(
            """INSERT INTO job_chunks
               (job_id, idx, start_sec, end_sec, status, attempts)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(c.job_id, c.idx, c.start_sec, c.end_sec, c.status, c.attempts)
             for c in chunks],
        )
        self.conn.commit()

    def get_chunks(self, job_id: str) -> list[JobChunk]:
        rows = self.conn.execute(
            "SELECT * FROM job_chunks WHERE job_id = ? ORDER BY idx",
            (job_id,),
        ).fetchall()
        return [self._row_to_chunk(r) for r in rows]

    def update_chunk(self, job_id: str, idx: int, **kwargs):
        sets = ', '.join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [job_id, idx]
        self.conn.execute(
            f"UPDATE job_chunks SET {sets} WHERE job_id = ? AND idx = ?", vals
        )
        self.conn.commit()

    def delete_chunks(self, job_id: str):
        self.conn.execute("DELETE FROM job_chunks WHERE job_id = ?", (job_id,))
        self.conn.commit()
