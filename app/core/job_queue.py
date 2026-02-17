"""
Job Queue Manager and Worker.
Processes one video at a time through the full pipeline.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from app.core.constants import (
    JobStatus, JobStage, ErrorCode, ChunkStatus,
    RETRYABLE_ERRORS, MAX_AUTO_RETRIES,
    JOBS_CACHE_DIR, DEFAULT_OUTPUT_ROOT,
    CookiesMode, DEFAULT_COOKIES_PATH,
    CHUNK_THRESHOLD_SEC, BASE_CHUNK_SEC, CHUNK_OVERLAP_SEC, MIN_CHUNK_SEC,
    PROGRESS_VALIDATE, PROGRESS_METADATA, PROGRESS_CAPTIONS_TRY,
    PROGRESS_CAPTIONS_PARSE, PROGRESS_CAPTIONS_WRITE,
    PROGRESS_AUDIO_SELECT, PROGRESS_AUDIO_DOWNLOAD,
    PROGRESS_AUDIO_NORMALIZE, PROGRESS_AUDIO_CHUNK,
    PROGRESS_TRANSCRIBE_START, PROGRESS_TRANSCRIBE_END,
    PROGRESS_MERGE, PROGRESS_WRITE, PROGRESS_CLEANUP,
)
from app.core.db_sqlite import Database
from app.core.models_sqlite import Job, JobChunk
from app.core.error_codes import JobError, is_retryable
from app.core.url_parse import validate_youtube_url
from app.core.yt_metadata import fetch_metadata, get_video_duration
from app.core.captions_fetch import fetch_creator_captions
from app.core.captions_parse import parse_vtt_to_text
from app.core.audio_select import select_audio_stream
from app.core.download_audio import download_audio
from app.core.normalize import normalize_audio, get_audio_duration
from app.core.chunking_timebased import (
    needs_chunking, create_chunk_manifest, split_audio_into_chunks,
    create_job_chunks, split_chunk_in_half,
)
from app.core.transcribe_deepgram import transcribe_audio, extract_transcript_text
from app.core.merge import merge_transcripts, merge_transcript_files
from app.core.output_writer import write_transcript, transcript_exists
from app.core.cleanup import cleanup_job_artifacts
from app.core.security_utils import keychain_get_api_key

logger = logging.getLogger(__name__)


class JobQueueManager:
    """
    Manages the job queue and processes jobs one at a time.
    Emits progress callbacks for UI updates.
    """

    def __init__(self, db: Database, config: dict | None = None):
        self.db = db
        self.config = config or {}
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stop_after_current = threading.Event()
        self._running = False
        self._current_job_id: Optional[str] = None

        # Callbacks
        self.on_job_updated: Optional[Callable[[Job], None]] = None
        self.on_queue_empty: Optional[Callable[[], None]] = None
        self.on_api_key_needed: Optional[Callable[[], str | None]] = None

    # ── Config helpers ────────────────────────────────────────────────

    @property
    def output_root(self) -> Path:
        return Path(self.config.get('output_root', str(DEFAULT_OUTPUT_ROOT)))

    @property
    def cookies_mode(self) -> str:
        return self.config.get('cookies_mode', CookiesMode.OFF)

    @property
    def cookies_path(self) -> Path:
        return Path(self.config.get('cookies_path', str(DEFAULT_COOKIES_PATH)))

    @property
    def keep_debug(self) -> bool:
        return self.config.get('keep_debug_artifacts', False)

    @property
    def chunk_threshold_sec(self) -> float:
        hours = self.config.get('chunk_threshold_hours', 2)
        return hours * 3600

    @property
    def base_chunk_sec(self) -> int:
        return self.config.get('base_chunk_sec', BASE_CHUNK_SEC)

    # ── Queue management ──────────────────────────────────────────────

    def add_urls(self, urls: list[str]) -> list[Job]:
        """Add URLs to the queue. Returns list of created jobs."""
        jobs = []
        for url in urls:
            try:
                video_id = validate_youtube_url(url)
            except JobError:
                continue  # Skip invalid URLs

            job = self.db.create_job(youtube_url=url, video_id=video_id)
            jobs.append(job)

        return jobs

    def start_processing(self):
        """Start the worker thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._stop_after_current.clear()
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def stop_processing(self):
        """Stop processing immediately."""
        self._stop_event.set()
        self._running = False

    def stop_after_current(self):
        """Stop after the current job finishes."""
        self._stop_after_current.set()

    def is_running(self) -> bool:
        return self._running

    def retry_job(self, job_id: str):
        """Reset a failed job to QUEUED for retry."""
        job = self.db.get_job(job_id)
        if job and job.status == JobStatus.FAILED:
            self.db.update_job(job_id,
                               status=JobStatus.QUEUED,
                               stage=None,
                               progress_pct=0,
                               error_code=None,
                               error_message=None,
                               retryable=0)
            self.db.delete_chunks(job_id)
            self._notify_job_updated(job_id)

    def remove_job(self, job_id: str):
        """Remove a job from the queue/list."""
        self.db.delete_job(job_id)

    def clear_queue(self):
        """Remove all QUEUED jobs."""
        self.db.clear_queued_jobs()

    # ── Worker loop ───────────────────────────────────────────────────

    def _worker_loop(self):
        """Main worker loop — processes one job at a time."""
        try:
            while not self._stop_event.is_set():
                if self._stop_after_current.is_set():
                    break

                queued = self.db.get_queued_jobs()
                if not queued:
                    if self.on_queue_empty:
                        self.on_queue_empty()
                    break

                job = queued[0]
                self._current_job_id = job.id
                self._process_job(job)
                self._current_job_id = None

        except Exception as e:
            logger.error("Worker loop error: %s", e, exc_info=True)
        finally:
            self._running = False
            self._current_job_id = None

    def _notify_job_updated(self, job_id: str):
        """Notify UI of job update."""
        if self.on_job_updated:
            job = self.db.get_job(job_id)
            if job:
                self.on_job_updated(job)

    def _update_progress(self, job_id: str, stage: str, progress: int, **extra):
        """Update job stage and progress."""
        self.db.update_job_status(job_id, JobStatus.RUNNING, stage=stage,
                                  progress_pct=progress, **extra)
        self._notify_job_updated(job_id)

    # ── Job processing pipeline ───────────────────────────────────────

    def _process_job(self, job: Job):
        """Process a single job through the full pipeline."""
        job_id = job.id
        workspace = JOBS_CACHE_DIR / job_id

        try:
            # Mark as RUNNING
            self.db.update_job_status(job_id, JobStatus.RUNNING,
                                      stage=JobStage.VALIDATING_URL,
                                      progress_pct=PROGRESS_VALIDATE)
            self._notify_job_updated(job_id)

            # ── Stage 1: Validate URL ──
            video_id = validate_youtube_url(job.youtube_url)
            self.db.update_job(job_id, video_id=video_id)

            # ── Duplicate check ──
            if self._check_duplicate(job_id, video_id):
                return

            # ── Stage 2: Fetch metadata ──
            self._update_progress(job_id, JobStage.FETCHING_METADATA, PROGRESS_METADATA)
            metadata = fetch_metadata(job.youtube_url, self.cookies_mode, self.cookies_path)
            title = metadata.get('title', f'video_{video_id}')
            self.db.update_job(job_id, title=title)

            # Save metadata
            meta_dir = workspace / "meta"
            meta_dir.mkdir(parents=True, exist_ok=True)
            with open(meta_dir / "ytinfo.json", 'w') as f:
                json.dump(metadata, f, indent=2)

            # ── Stage 3: Try creator captions ──
            self._update_progress(job_id, JobStage.TRYING_CREATOR_CAPTIONS, PROGRESS_CAPTIONS_TRY)

            captions_dir = workspace / "captions"
            vtt_path = fetch_creator_captions(
                job.youtube_url, video_id, captions_dir,
                self.cookies_mode, self.cookies_path,
            )

            if vtt_path:
                # ── Captions found → parse and write (with Deepgram fallback on empty) ──
                self._process_captions_path(job_id, vtt_path, title, video_id, workspace, metadata)
                return

            # ── No creator captions → Deepgram fallback ──
            self._process_deepgram_fallback(job_id, job.youtube_url, metadata,
                                            title, video_id, workspace)

        except JobError as e:
            self._handle_job_error(job_id, e, workspace)
        except Exception as e:
            logger.error("Unexpected error processing job %s: %s", job_id, e, exc_info=True)
            self.db.update_job_status(
                job_id, JobStatus.FAILED,
                error_code="ERR_UNEXPECTED",
                error_message=str(e)[:2000],
                retryable=1,
            )
            self._notify_job_updated(job_id)
            cleanup_job_artifacts(workspace, self.keep_debug)

    def _check_duplicate(self, job_id: str, video_id: str) -> bool:
        """
        Atomic duplicate check — queries DB and filesystem under a single
        lock acquisition so two jobs for the same video_id cannot both pass.
        Returns True if the job was skipped.
        """
        with self.db._lock:
            # DB check inside the lock
            already_done = self.db.conn.execute(
                "SELECT 1 FROM jobs WHERE video_id = ? AND status = ? AND id != ? LIMIT 1",
                (video_id, JobStatus.COMPLETED, job_id),
            ).fetchone()

            if already_done:
                # Mark skipped while still holding the lock
                now = self.db._now()
                self.db.conn.execute(
                    "UPDATE jobs SET status=?, stage=?, progress_pct=?, completed_at=?, updated_at=? WHERE id=?",
                    (JobStatus.SKIPPED, "DUPLICATE_IN_DB", 100, now, now, job_id),
                )
                self.db.conn.commit()
                self._notify_job_updated(job_id)
                return True

        # Filesystem check (outside lock — I/O shouldn't block DB)
        self.output_root.mkdir(parents=True, exist_ok=True)
        if transcript_exists(self.output_root, video_id):
            self.db.update_job_status(job_id, JobStatus.SKIPPED,
                                      stage="DUPLICATE_ON_DISK",
                                      progress_pct=100)
            self._notify_job_updated(job_id)
            return True

        return False

    def _process_captions_path(self, job_id: str, vtt_path: Path,
                               title: str, video_id: str, workspace: Path,
                               metadata: dict | None = None):
        """
        Process found captions: parse VTT → write TXT.
        Falls back to Deepgram if the VTT parses to empty text.
        """
        # Parse captions
        self._update_progress(job_id, JobStage.PARSING_CAPTIONS, PROGRESS_CAPTIONS_PARSE)
        try:
            text = parse_vtt_to_text(vtt_path)
        except Exception as e:
            logger.warning("VTT parse failed for job %s: %s — falling back to Deepgram", job_id, e)
            text = ""

        if not text.strip():
            # Empty or failed captions — fall back to Deepgram if metadata available
            if metadata is not None:
                logger.info("Empty captions for job %s — switching to Deepgram fallback", job_id)
                job = self.db.get_job(job_id)
                if job:
                    self._process_deepgram_fallback(
                        job_id, job.youtube_url, metadata, title, video_id, workspace
                    )
                return
            # No metadata to fall back with — write a placeholder
            text = "(No caption text could be extracted)"

        # Write output
        self._update_progress(job_id, JobStage.WRITING_TXT, PROGRESS_CAPTIONS_WRITE)
        write_transcript(text, self.output_root, title, video_id)

        # Cleanup
        self._update_progress(job_id, JobStage.CLEANUP, PROGRESS_CLEANUP)
        cleanup_job_artifacts(workspace, self.keep_debug)

        # Mark completed
        self.db.update_job_status(job_id, JobStatus.COMPLETED,
                                  stage=JobStage.CLEANUP,
                                  progress_pct=100,
                                  used_creator_captions=1,
                                  error_code=ErrorCode.CREATOR_CAPTIONS_USED)
        self._notify_job_updated(job_id)

    def _process_deepgram_fallback(self, job_id: str, video_url: str,
                                   metadata: dict, title: str, video_id: str,
                                   workspace: Path):
        """Full Deepgram fallback pipeline: select → download → normalize → chunk → transcribe → merge."""

        # Check for API key
        api_key = keychain_get_api_key()
        if not api_key:
            if self.on_api_key_needed:
                api_key = self.on_api_key_needed()
            if not api_key:
                raise JobError(ErrorCode.DEEPGRAM_TRANSCRIBE_FAILED,
                               "Deepgram API key not available")

        # ── Select audio stream ──
        self._update_progress(job_id, JobStage.SELECTING_AUDIO_STREAM, PROGRESS_AUDIO_SELECT)
        meta_dir = workspace / "meta"
        stream_info = select_audio_stream(metadata, meta_dir)
        format_id = stream_info['format_id']

        # ── Download audio ──
        self._update_progress(job_id, JobStage.DOWNLOADING_AUDIO, PROGRESS_AUDIO_DOWNLOAD)
        source_dir = workspace / "source"
        audio_path = download_audio(video_url, format_id, source_dir,
                                    self.cookies_mode, self.cookies_path)

        # ── Normalize audio ──
        self._update_progress(job_id, JobStage.NORMALIZING_AUDIO, PROGRESS_AUDIO_NORMALIZE)
        norm_dir = workspace / "normalized"
        normalized_path = normalize_audio(audio_path, norm_dir)

        # Get duration
        duration = get_audio_duration(normalized_path)
        if duration <= 0:
            duration = get_video_duration(metadata)

        # ── Chunk if needed ──
        transcripts_dir = workspace / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)

        if needs_chunking(duration):
            self._update_progress(job_id, JobStage.CHUNKING_AUDIO, PROGRESS_AUDIO_CHUNK)
            manifest = create_chunk_manifest(duration, self.base_chunk_sec, CHUNK_OVERLAP_SEC)
            chunks_dir = workspace / "chunks"
            chunk_paths = split_audio_into_chunks(normalized_path, chunks_dir, manifest)

            # Create DB chunk records
            job_chunks = create_job_chunks(job_id, manifest)
            self.db.create_chunks(job_chunks)

            # Transcribe chunks
            self._transcribe_chunks(job_id, chunk_paths, manifest, transcripts_dir,
                                    normalized_path, workspace, api_key)
        else:
            # Single file transcription
            self._update_progress(job_id, JobStage.TRANSCRIBING_DEEPGRAM, PROGRESS_TRANSCRIBE_START)
            result = self._transcribe_with_adaptive_retry(
                normalized_path, api_key,
                transcripts_dir / "chunk_000.json",
                0, duration, workspace, job_id,
            )
            text = extract_transcript_text(result)

            self._update_progress(job_id, JobStage.MERGING_TRANSCRIPT, PROGRESS_MERGE)
            # Save merged text
            with open(transcripts_dir / "merged.txt", 'w') as f:
                f.write(text)

            # Write output
            self._update_progress(job_id, JobStage.WRITING_TXT, PROGRESS_WRITE)
            write_transcript(text, self.output_root, title, video_id)

            # Cleanup
            self._update_progress(job_id, JobStage.CLEANUP, PROGRESS_CLEANUP)
            cleanup_job_artifacts(workspace, self.keep_debug)

            self.db.update_job_status(job_id, JobStatus.COMPLETED,
                                      stage=JobStage.CLEANUP,
                                      progress_pct=100)
            self._notify_job_updated(job_id)
            return

        # After chunked transcription — merge
        self._update_progress(job_id, JobStage.MERGING_TRANSCRIPT, PROGRESS_MERGE)
        chunks = self.db.get_chunks(job_id)
        chunk_count = len(chunks)
        merged_text = merge_transcript_files(transcripts_dir, chunk_count)

        with open(transcripts_dir / "merged.txt", 'w') as f:
            f.write(merged_text)

        # Write output
        self._update_progress(job_id, JobStage.WRITING_TXT, PROGRESS_WRITE)
        write_transcript(merged_text, self.output_root, title, video_id)

        # Cleanup
        self._update_progress(job_id, JobStage.CLEANUP, PROGRESS_CLEANUP)
        cleanup_job_artifacts(workspace, self.keep_debug)

        self.db.update_job_status(job_id, JobStatus.COMPLETED,
                                  stage=JobStage.CLEANUP,
                                  progress_pct=100)
        self._notify_job_updated(job_id)

    def _transcribe_chunks(self, job_id: str, chunk_paths: list[Path],
                           manifest: list[dict], transcripts_dir: Path,
                           normalized_path: Path, workspace: Path,
                           api_key: str):
        """Transcribe all chunks with progress tracking."""
        total = len(chunk_paths)
        progress_range = PROGRESS_TRANSCRIBE_END - PROGRESS_TRANSCRIBE_START

        for i, chunk_path in enumerate(chunk_paths):
            if self._stop_event.is_set():
                raise JobError(ErrorCode.NETWORK_TRANSIENT, "Processing stopped by user")

            progress = PROGRESS_TRANSCRIBE_START + int((i / total) * progress_range)
            self._update_progress(job_id, JobStage.TRANSCRIBING_DEEPGRAM, progress)

            entry = manifest[i]
            transcript_path = transcripts_dir / f"chunk_{i:03d}.json"

            try:
                self._transcribe_with_adaptive_retry(
                    chunk_path, api_key, transcript_path,
                    entry['start_sec'], entry['end_sec'],
                    workspace, job_id,
                )
                self.db.update_chunk(job_id, i, status=ChunkStatus.DONE)
            except JobError as e:
                self.db.update_chunk(job_id, i,
                                     status=ChunkStatus.FAILED,
                                     error_code=e.code,
                                     error_message=e.message[:2000])
                raise

    def _transcribe_with_adaptive_retry(self, audio_path: Path, api_key: str,
                                        output_path: Path,
                                        start_sec: float, end_sec: float,
                                        workspace: Path, job_id: str) -> dict:
        """
        Transcribe with adaptive timeout handling.
        On timeout: split in half and retry, until minimum chunk size reached.
        """
        duration = end_sec - start_sec

        try:
            return transcribe_audio(audio_path, api_key, output_path)
        except JobError as e:
            if e.code != ErrorCode.DEEPGRAM_TIMEOUT:
                # Auto-retry once for other retryable errors
                if e.retryable:
                    try:
                        return transcribe_audio(audio_path, api_key, output_path)
                    except JobError:
                        raise
                raise

        # Timeout — try adaptive chunking
        if duration <= MIN_CHUNK_SEC:
            raise JobError(ErrorCode.DEEPGRAM_TIMEOUT,
                           f"Timeout on minimum chunk size ({duration:.0f}s)")

        logger.info("Timeout on %.0fs chunk, splitting in half...", duration)

        # Split the audio file in half
        half_duration = duration / 2
        chunks_dir = workspace / "chunks" / "adaptive"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        from app.core.security_utils import run_subprocess_capture

        texts = []
        for part_idx, (s, e) in enumerate([(start_sec, start_sec + half_duration),
                                            (start_sec + half_duration - 2, end_sec)]):
            part_file = chunks_dir / f"adaptive_{start_sec:.0f}_{part_idx}.mp3"

            # Extract sub-chunk from normalized audio
            args = [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-ss", str(s - start_sec) if start_sec > 0 else "0",
                "-t", str(e - s),
                "-codec:a", "copy",
                str(part_file),
            ]
            run_subprocess_capture(args, timeout=60)

            if part_file.exists():
                part_output = output_path.parent / f"adaptive_{start_sec:.0f}_{part_idx}.json"
                result = self._transcribe_with_adaptive_retry(
                    part_file, api_key, part_output, s, e, workspace, job_id,
                )
                texts.append(extract_transcript_text(result))

        # Merge the two halves
        from app.core.merge import merge_transcripts
        merged = merge_transcripts(texts)

        # Create a synthetic response
        return {
            'results': {
                'channels': [{
                    'alternatives': [{
                        'transcript': merged,
                    }]
                }]
            }
        }

    def _handle_job_error(self, job_id: str, error: JobError, workspace: Path):
        """Handle a JobError: auto-retry or fail."""
        job = self.db.get_job(job_id)
        if not job:
            return

        if error.retryable and job.retry_count < MAX_AUTO_RETRIES:
            # Auto-retry
            logger.info("Auto-retrying job %s (attempt %d)", job_id, job.retry_count + 1)
            self.db.update_job(job_id,
                               retry_count=job.retry_count + 1,
                               status=JobStatus.QUEUED,
                               stage=None,
                               progress_pct=0,
                               error_code=None,
                               error_message=None)
            self._notify_job_updated(job_id)
        else:
            # Final failure
            self.db.update_job_status(
                job_id, JobStatus.FAILED,
                error_code=error.code,
                error_message=error.message[:2000],
                retryable=1 if error.retryable else 0,
            )
            self._notify_job_updated(job_id)
            cleanup_job_artifacts(workspace, self.keep_debug)
