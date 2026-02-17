"""
Main application window for YouTubeTranscriber.
Built with tkinter — no external UI dependencies.
Supports paste, drag-and-drop (.txt/.csv), folder picker, job queue display.
"""

import sys
import os
import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional
from dataclasses import asdict

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.constants import (
    APP_NAME, APP_DISPLAY_NAME, APP_VERSION, JobStatus, DEFAULT_OUTPUT_ROOT,
    APP_SUPPORT_DIR, APP_CACHE_DIR,
)
from app.core.config import AppConfig
from app.core.db_sqlite import Database
from app.core.job_queue import JobQueueManager
from app.core.url_parse import parse_input_lines, parse_input_file
from app.core.security_utils import keychain_get_api_key
from app.core.models_sqlite import Job
from app.desktop.ui_components import DropZone, JobsList
from app.desktop.ui_settings import SettingsPanel, DiagnosticsPanel, APIKeyDialog

logger = logging.getLogger(__name__)


class MainWindow:
    """Main application window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_DISPLAY_NAME} v{APP_VERSION}")
        self.root.geometry("800x700")
        self.root.minsize(700, 550)

        # Initialize backend
        self._init_backend()

        # Build UI
        self._build_ui()

        # Setup drag-and-drop (tkdnd if available, else file dialog fallback)
        self._setup_dnd()

        # Check for API key on first run
        self.root.after(500, self._check_first_run)

        # Periodic UI refresh
        self._schedule_refresh()

    def _init_backend(self):
        """Initialize config, database, and job queue."""
        APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        APP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self.config = AppConfig()
        self.db = Database()
        self.queue_manager = JobQueueManager(self.db, self.config.as_dict())

        # Set callbacks
        self.queue_manager.on_job_updated = self._on_job_updated_callback
        self.queue_manager.on_queue_empty = self._on_queue_empty_callback
        self.queue_manager.on_api_key_needed = self._on_api_key_needed_callback

    def _build_ui(self):
        """Build the main UI layout."""
        # Style
        style = ttk.Style()
        try:
            style.theme_use('aqua')  # macOS native look
        except tk.TclError:
            try:
                style.theme_use('clam')
            except tk.TclError:
                pass

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ── Tab 1: Main ──
        main_tab = ttk.Frame(self.notebook)
        self.notebook.add(main_tab, text="  Main  ")

        # Top: Drop zone
        self.drop_zone = DropZone(main_tab)
        self.drop_zone.pack(fill=tk.X, padx=10, pady=(10, 5))

        # Control buttons
        btn_frame = ttk.Frame(main_tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        self.start_btn = ttk.Button(btn_frame, text="Start",
                                    command=self._on_start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(btn_frame, text="Stop After Current",
                                   command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.clear_btn = ttk.Button(btn_frame, text="Clear Queue",
                                    command=self._on_clear_queue)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 5))

        # File drop button (fallback for systems without tkdnd)
        self.file_btn = ttk.Button(btn_frame, text="Load File...",
                                   command=self._on_load_file)
        self.file_btn.pack(side=tk.RIGHT)

        # Output folder display
        output_frame = ttk.Frame(main_tab)
        output_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        ttk.Label(output_frame, text="Output:").pack(side=tk.LEFT)
        self.output_label = ttk.Label(
            output_frame, text=self.config.output_root,
            foreground="blue", cursor="hand2",
        )
        self.output_label.pack(side=tk.LEFT, padx=5)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_tab, textvariable=self.status_var,
                               relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 5))

        # Jobs list
        self.jobs_list = JobsList(
            main_tab,
            on_retry=self._on_retry_job,
            on_remove=self._on_remove_job,
        )
        self.jobs_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ── Tab 2: Settings ──
        settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(settings_tab, text="  Settings  ")
        self.settings_panel = SettingsPanel(
            settings_tab, self.config,
            on_config_changed=self._on_config_changed,
        )
        self.settings_panel.pack(fill=tk.BOTH, expand=True)

        # ── Tab 3: Diagnostics ──
        diag_tab = ttk.Frame(self.notebook)
        self.notebook.add(diag_tab, text="  Diagnostics  ")
        self.diag_panel = DiagnosticsPanel(diag_tab, self.config)
        self.diag_panel.pack(fill=tk.BOTH, expand=True)

    def _setup_dnd(self):
        """Setup drag-and-drop support."""
        # Try to use tkdnd if available (macOS may have it)
        try:
            self.root.tk.eval('package require tkdnd')
            self._has_tkdnd = True
            # Register drop target
            self.root.tk.eval('''
                tkdnd::drop_target register . DND_Files
            ''')
            self.root.tk.eval('''
                bind . <<Drop:DND_Files>> {
                    event generate . <<FileDrop>> -data %D
                }
            ''')
            self.root.bind("<<FileDrop>>", self._on_file_drop)
        except tk.TclError:
            self._has_tkdnd = False
            # Fallback: use the Load File button

    def _check_first_run(self):
        """Check if Deepgram API key is set; prompt if not."""
        key = keychain_get_api_key()
        if not key:
            dialog = APIKeyDialog(
                self.root,
                title_text="Deepgram API Key Required",
                allow_cancel_quit=True,
            )
            if not dialog.result_key:
                # User chose to continue without key — that's OK
                # Deepgram fallback will prompt again when needed
                self.status_var.set("Warning: Deepgram API key not set (captions-only mode)")

    # ── Event handlers ────────────────────────────────────────────────

    def _on_start(self):
        """Add pasted URLs to queue and start processing."""
        text = self.drop_zone.get_text()
        urls = parse_input_lines(text)

        if urls:
            jobs = self.queue_manager.add_urls(urls)
            self.drop_zone.clear()
            self.status_var.set(f"Added {len(jobs)} job(s) to queue")
        elif not self.db.get_queued_jobs():
            self.status_var.set("No valid YouTube URLs found")
            return

        # Update config in queue manager
        self.queue_manager.config = self.config.as_dict()

        # Start processing
        self.queue_manager.start_processing()
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.status_var.set("Processing...")
        self._refresh_jobs_list()

    def _on_stop(self):
        """Stop after current job."""
        self.queue_manager.stop_after_current()
        self.status_var.set("Stopping after current job...")
        self.stop_btn.configure(state=tk.DISABLED)

    def _on_clear_queue(self):
        """Clear all queued jobs."""
        self.queue_manager.clear_queue()
        self.status_var.set("Queue cleared")
        self._refresh_jobs_list()

    def _on_load_file(self):
        """Open file dialog to load .txt/.csv file."""
        filetypes = [
            ("Text files", "*.txt"),
            ("CSV files", "*.csv"),
            ("All files", "*.*"),
        ]
        filepath = filedialog.askopenfilename(
            title="Select URL file",
            filetypes=filetypes,
        )
        if filepath:
            urls = parse_input_file(filepath)
            if urls:
                jobs = self.queue_manager.add_urls(urls)
                self.status_var.set(f"Loaded {len(jobs)} URL(s) from file")
                self._refresh_jobs_list()
            else:
                self.status_var.set("No valid YouTube URLs found in file")

    def _on_file_drop(self, event):
        """Handle file drop event (tkdnd)."""
        files = self.root.tk.splitlist(event.data if hasattr(event, 'data') else '')
        all_urls = []
        for f in files:
            f = f.strip('{}')  # tkdnd wraps paths in braces
            if f.lower().endswith(('.txt', '.csv')):
                urls = parse_input_file(f)
                all_urls.extend(urls)

        if all_urls:
            jobs = self.queue_manager.add_urls(all_urls)
            self.status_var.set(f"Loaded {len(jobs)} URL(s) from dropped file(s)")
            self._refresh_jobs_list()

    def _on_retry_job(self, job_id: str):
        """Retry a failed job."""
        self.queue_manager.retry_job(job_id)
        self._refresh_jobs_list()
        # Auto-start if not running
        if not self.queue_manager.is_running():
            self.queue_manager.config = self.config.as_dict()
            self.queue_manager.start_processing()
            self.start_btn.configure(state=tk.DISABLED)
            self.stop_btn.configure(state=tk.NORMAL)

    def _on_remove_job(self, job_id: str):
        """Remove a job."""
        self.queue_manager.remove_job(job_id)
        self._refresh_jobs_list()

    def _on_config_changed(self):
        """Config was changed in settings."""
        self.output_label.configure(text=self.config.output_root)
        self.queue_manager.config = self.config.as_dict()

    # ── Callbacks from worker thread ──────────────────────────────────

    def _on_job_updated_callback(self, job: Job):
        """Called from worker thread — schedule UI update."""
        self.root.after(0, self._refresh_jobs_list)

    def _on_queue_empty_callback(self):
        """Called when queue is empty."""
        self.root.after(0, self._on_processing_done)

    def _on_api_key_needed_callback(self) -> Optional[str]:
        """Called from worker when API key is needed."""
        # This runs in worker thread — need to use thread-safe dialog
        result = [None]
        event = threading.Event()

        def show_dialog():
            dialog = APIKeyDialog(self.root, title_text="Deepgram API Key Required")
            result[0] = dialog.result_key
            event.set()

        self.root.after(0, show_dialog)
        event.wait(timeout=300)  # Wait up to 5 minutes
        return result[0]

    def _on_processing_done(self):
        """Processing finished."""
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.status_var.set("Processing complete")
        self._refresh_jobs_list()

    # ── UI refresh ────────────────────────────────────────────────────

    def _refresh_jobs_list(self):
        """Refresh the jobs list display."""
        try:
            jobs = self.db.get_all_jobs()
            job_dicts = []
            for j in jobs:
                d = {
                    'id': j.id,
                    'title': j.title,
                    'video_id': j.video_id,
                    'status': j.status,
                    'stage': j.stage,
                    'progress_pct': j.progress_pct,
                    'error_code': j.error_code,
                    'error_message': j.error_message,
                }
                job_dicts.append(d)
            self.jobs_list.update_jobs(job_dicts)
        except Exception as e:
            logger.error("Error refreshing jobs list: %s", e)

    def _schedule_refresh(self):
        """Schedule periodic UI refresh."""
        if self.queue_manager.is_running():
            self._refresh_jobs_list()
        self.root.after(1000, self._schedule_refresh)  # Every 1 second

    # ── Run ───────────────────────────────────────────────────────────

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()

    def cleanup(self):
        """Cleanup on exit."""
        self.queue_manager.stop_processing()
        self.db.close()


def main():
    """Application entry point."""
    # Configure logging (only add file handler if not already configured)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        log_dir = Path.home() / "Library" / "Logs" / "video-to-text-transcriber"
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "app.log"),
            ],
        )

    # Ensure output root exists
    DEFAULT_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    app = MainWindow()
    try:
        app.run()
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()
