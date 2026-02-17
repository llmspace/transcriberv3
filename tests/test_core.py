#!/usr/bin/env python3
"""
Unit tests for video-to-text-transcriber core modules.
Tests cover: URL parsing, security utils, database, captions parsing, audio selection, chunking.
"""

import sys
import os
import tempfile
import sqlite3
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import unittest

from app.core.constants import (
    JobStatus, JobStage, ErrorCode, RETRYABLE_ERRORS,
    CHUNK_THRESHOLD_SEC, BASE_CHUNK_SEC,
)
from app.core.url_parse import (
    extract_video_id, validate_youtube_url, is_youtube_url,
    parse_input_lines, parse_csv_file, parse_txt_file,
)
from app.core.security_utils import sanitize_title, safe_output_path
from app.core.error_codes import JobError, is_retryable
from app.core.captions_parse import parse_vtt_to_text
from app.core.audio_select import select_audio_stream
from app.core.chunking_timebased import (
    needs_chunking, create_chunk_manifest, split_chunk_in_half,
)
from app.core.merge import dedupe_overlap, merge_transcripts
from app.core.output_writer import transcript_exists


class TestURLParsing(unittest.TestCase):
    """Test YouTube URL parsing and validation."""

    def test_standard_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_short_url(self):
        self.assertEqual(
            extract_video_id("https://youtu.be/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_embed_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_shorts_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_mobile_url(self):
        self.assertEqual(
            extract_video_id("https://m.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_url_with_params(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120"),
            "dQw4w9WgXcQ",
        )

    def test_invalid_url(self):
        self.assertIsNone(extract_video_id("https://www.google.com"))
        self.assertIsNone(extract_video_id("not a url"))
        self.assertIsNone(extract_video_id(""))

    def test_is_youtube_url(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertFalse(is_youtube_url("https://www.google.com"))

    def test_validate_raises_on_invalid(self):
        with self.assertRaises(JobError) as ctx:
            validate_youtube_url("https://www.google.com")
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_URL)

    def test_parse_input_lines(self):
        text = """
        https://www.youtube.com/watch?v=dQw4w9WgXcQ
        https://youtu.be/abc123def45

        not a url
        https://www.youtube.com/watch?v=xyz789abc12
        """
        urls = parse_input_lines(text)
        self.assertEqual(len(urls), 3)

    def test_parse_input_lines_empty(self):
        self.assertEqual(parse_input_lines(""), [])
        self.assertEqual(parse_input_lines("   \n\n  "), [])


class TestSecurityUtils(unittest.TestCase):
    """Test security utilities."""

    def test_sanitize_title_basic(self):
        self.assertEqual(sanitize_title("Hello World"), "Hello World")

    def test_sanitize_title_special_chars(self):
        result = sanitize_title('Video: "Test" <script>alert(1)</script>')
        self.assertNotIn('"', result)
        self.assertNotIn('<', result)
        self.assertNotIn('>', result)

    def test_sanitize_title_path_traversal(self):
        result = sanitize_title("../../../etc/passwd")
        self.assertNotIn('..', result)

    def test_sanitize_title_empty(self):
        self.assertEqual(sanitize_title(""), "")
        self.assertEqual(sanitize_title("..."), "")

    def test_sanitize_title_long(self):
        long_title = "A" * 300
        result = sanitize_title(long_title)
        self.assertLessEqual(len(result), 200)

    def test_safe_output_path_normal(self):
        root = Path("/tmp/test_output")
        result = safe_output_path(root, "My Video Title", "abc123def45")
        self.assertTrue(str(result.resolve()).startswith(str(root.resolve())))

    def test_safe_output_path_traversal(self):
        root = Path("/tmp/test_output")
        result = safe_output_path(root, "../../etc/passwd", "abc123def45")
        self.assertTrue(str(result.resolve()).startswith(str(root.resolve())))

    def test_safe_output_path_empty_title(self):
        root = Path("/tmp/test_output")
        result = safe_output_path(root, "", "abc123def45")
        self.assertIn("video_abc123def45", str(result))


class TestErrorCodes(unittest.TestCase):
    """Test error code handling."""

    def test_retryable_errors(self):
        self.assertTrue(is_retryable(ErrorCode.DOWNLOAD_FAILED))
        self.assertTrue(is_retryable(ErrorCode.DEEPGRAM_TIMEOUT))
        self.assertTrue(is_retryable(ErrorCode.NETWORK_TRANSIENT))

    def test_non_retryable_errors(self):
        self.assertFalse(is_retryable(ErrorCode.INVALID_URL))
        self.assertFalse(is_retryable(ErrorCode.VIDEO_UNAVAILABLE))
        self.assertFalse(is_retryable(ErrorCode.FFMPEG_NORMALIZE))

    def test_job_error_auto_retryable(self):
        err = JobError(ErrorCode.DOWNLOAD_FAILED, "test")
        self.assertTrue(err.retryable)

        err2 = JobError(ErrorCode.INVALID_URL, "test")
        self.assertFalse(err2.retryable)


class TestCaptionsParsing(unittest.TestCase):
    """Test VTT caption parsing."""

    def test_parse_vtt_basic(self):
        vtt_content = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:05.000
Hello, welcome to this video.

00:00:05.000 --> 00:00:10.000
Today we'll be talking about Python.

00:00:10.000 --> 00:00:15.000
Let's get started.
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
            f.write(vtt_content)
            f.flush()
            result = parse_vtt_to_text(Path(f.name))

        self.assertIn("Hello, welcome to this video.", result)
        self.assertIn("Today we'll be talking about Python.", result)
        self.assertIn("Let's get started.", result)
        # Should not contain timestamps
        self.assertNotIn("00:00:00", result)
        self.assertNotIn("-->", result)
        os.unlink(f.name)

    def test_parse_vtt_removes_html(self):
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
<b>Bold text</b> and <i>italic</i> text.
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
            f.write(vtt_content)
            f.flush()
            result = parse_vtt_to_text(Path(f.name))

        self.assertIn("Bold text", result)
        self.assertNotIn("<b>", result)
        self.assertNotIn("<i>", result)
        os.unlink(f.name)


class TestAudioSelection(unittest.TestCase):
    """Test audio stream selection policy."""

    def test_prefer_96kbps(self):
        metadata = {
            'formats': [
                {'format_id': '1', 'vcodec': 'none', 'acodec': 'opus', 'abr': 64, 'ext': 'webm'},
                {'format_id': '2', 'vcodec': 'none', 'acodec': 'opus', 'abr': 96, 'ext': 'webm'},
                {'format_id': '3', 'vcodec': 'none', 'acodec': 'opus', 'abr': 128, 'ext': 'webm'},
            ]
        }
        result = select_audio_stream(metadata)
        self.assertEqual(result['format_id'], '2')

    def test_prefer_128_over_64(self):
        metadata = {
            'formats': [
                {'format_id': '1', 'vcodec': 'none', 'acodec': 'opus', 'abr': 64, 'ext': 'webm'},
                {'format_id': '3', 'vcodec': 'none', 'acodec': 'opus', 'abr': 128, 'ext': 'webm'},
            ]
        }
        result = select_audio_stream(metadata)
        # 128 is closer to 96 than 64 is (distance 32 vs 32, but 128 preferred)
        self.assertEqual(result['format_id'], '3')

    def test_no_audio_streams(self):
        metadata = {
            'formats': [
                {'format_id': '1', 'vcodec': 'h264', 'acodec': 'aac', 'abr': 128},
            ]
        }
        result = select_audio_stream(metadata)
        self.assertEqual(result['format_id'], 'bestaudio')

    def test_floor_enforcement(self):
        metadata = {
            'formats': [
                {'format_id': '1', 'vcodec': 'none', 'acodec': 'opus', 'abr': 32, 'ext': 'webm'},
                {'format_id': '2', 'vcodec': 'none', 'acodec': 'opus', 'abr': 64, 'ext': 'webm'},
            ]
        }
        result = select_audio_stream(metadata)
        self.assertEqual(result['format_id'], '2')  # Should pick 64, not 32


class TestChunking(unittest.TestCase):
    """Test time-based chunking logic."""

    def test_needs_chunking(self):
        self.assertFalse(needs_chunking(3600))       # 1 hour
        self.assertFalse(needs_chunking(7200))       # 2 hours exactly
        self.assertTrue(needs_chunking(7201))        # Just over 2 hours
        self.assertTrue(needs_chunking(14400))       # 4 hours

    def test_create_manifest(self):
        # 3 hour video with 1 hour chunks
        manifest = create_chunk_manifest(10800, chunk_duration_sec=3600, overlap_sec=2)
        self.assertGreaterEqual(len(manifest), 3)
        self.assertEqual(manifest[0]['start_sec'], 0.0)
        self.assertEqual(manifest[0]['end_sec'], 3600.0)
        # Second chunk should start at 3598 (3600 - 2 overlap)
        self.assertAlmostEqual(manifest[1]['start_sec'], 3598.0, places=0)
        # Last chunk should end at or near the total duration
        self.assertAlmostEqual(manifest[-1]['end_sec'], 10800.0, places=0)

    def test_split_chunk_in_half(self):
        halves = split_chunk_in_half(0.0, 3600.0)
        self.assertEqual(len(halves), 2)
        self.assertEqual(halves[0]['start_sec'], 0.0)
        self.assertAlmostEqual(halves[0]['end_sec'], 1800.0, places=0)


class TestMerge(unittest.TestCase):
    """Test transcript merging."""

    def test_merge_single(self):
        result = merge_transcripts(["Hello world"])
        self.assertEqual(result, "Hello world")

    def test_merge_multiple(self):
        result = merge_transcripts(["Part one.", "Part two.", "Part three."])
        self.assertIn("Part one.", result)
        self.assertIn("Part two.", result)
        self.assertIn("Part three.", result)

    def test_merge_empty(self):
        self.assertEqual(merge_transcripts([]), "")

    def test_dedupe_overlap(self):
        text_a = "The quick brown fox jumps over the lazy dog"
        text_b = "over the lazy dog and then runs away"
        result = dedupe_overlap(text_a, text_b, overlap_words=10)
        # Should not have "over the lazy dog" repeated
        count = result.count("over the lazy dog")
        self.assertEqual(count, 1)


class TestDatabase(unittest.TestCase):
    """Test SQLite database operations."""

    def setUp(self):
        self.db_path = Path(tempfile.mktemp(suffix='.db'))
        from app.core.db_sqlite import Database
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_create_job(self):
        job = self.db.create_job("https://www.youtube.com/watch?v=test123test1", "test123test1")
        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, JobStatus.QUEUED)
        self.assertEqual(job.video_id, "test123test1")

    def test_get_job(self):
        job = self.db.create_job("https://www.youtube.com/watch?v=test123test1", "test123test1")
        fetched = self.db.get_job(job.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.youtube_url, job.youtube_url)

    def test_update_job_status(self):
        job = self.db.create_job("https://www.youtube.com/watch?v=test123test1", "test123test1")
        self.db.update_job_status(job.id, JobStatus.RUNNING, stage=JobStage.FETCHING_METADATA)
        fetched = self.db.get_job(job.id)
        self.assertEqual(fetched.status, JobStatus.RUNNING)
        self.assertEqual(fetched.stage, JobStage.FETCHING_METADATA)

    def test_has_completed_video(self):
        job = self.db.create_job("https://www.youtube.com/watch?v=test123test1", "test123test1")
        self.assertFalse(self.db.has_completed_video("test123test1"))
        self.db.update_job_status(job.id, JobStatus.COMPLETED)
        self.assertTrue(self.db.has_completed_video("test123test1"))

    def test_delete_job(self):
        job = self.db.create_job("https://www.youtube.com/watch?v=test123test1", "test123test1")
        self.db.delete_job(job.id)
        self.assertIsNone(self.db.get_job(job.id))

    def test_clear_queued(self):
        self.db.create_job("https://www.youtube.com/watch?v=test1test1ab", "test1test1ab")
        self.db.create_job("https://www.youtube.com/watch?v=test2test2ab", "test2test2ab")
        self.assertEqual(len(self.db.get_queued_jobs()), 2)
        self.db.clear_queued_jobs()
        self.assertEqual(len(self.db.get_queued_jobs()), 0)

    def test_chunks(self):
        from app.core.models_sqlite import JobChunk
        job = self.db.create_job("https://www.youtube.com/watch?v=test123test1", "test123test1")
        chunks = [
            JobChunk(job_id=job.id, idx=0, start_sec=0, end_sec=3600),
            JobChunk(job_id=job.id, idx=1, start_sec=3598, end_sec=7200),
        ]
        self.db.create_chunks(chunks)
        fetched = self.db.get_chunks(job.id)
        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0].idx, 0)
        self.assertEqual(fetched[1].idx, 1)


class TestOutputWriter(unittest.TestCase):
    """Test output file operations."""

    def test_transcript_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create a transcript file
            folder = root / "Test Video"
            folder.mkdir()
            (folder / "abc123def45.txt").write_text("test")

            self.assertTrue(transcript_exists(root, "abc123def45"))
            self.assertFalse(transcript_exists(root, "xyz789abc12"))


if __name__ == "__main__":
    unittest.main()
