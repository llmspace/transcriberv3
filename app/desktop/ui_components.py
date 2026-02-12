"""
Reusable UI components for YouTubeTranscriber.
Built with tkinter (ships with macOS Python).
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class DropZone(ttk.LabelFrame):
    """
    Drop zone widget that accepts .txt/.csv files via drag-and-drop
    and paste of URLs via a text box.
    """

    def __init__(self, parent, on_urls_pasted: Callable[[str], None] = None,
                 on_files_dropped: Callable[[list[str]], None] = None, **kwargs):
        super().__init__(parent, text="  Add YouTube URLs  ", padding=10, **kwargs)
        self.on_urls_pasted = on_urls_pasted
        self.on_files_dropped = on_files_dropped
        self._build()

    def _build(self):
        # Instructions
        instructions = ttk.Label(
            self,
            text="Paste YouTube URLs below (one per line) or drop .txt/.csv files onto this window",
            wraplength=500,
        )
        instructions.pack(fill=tk.X, pady=(0, 5))

        # Text area for pasting URLs
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.text_area = tk.Text(
            text_frame,
            height=8,
            wrap=tk.WORD,
            font=("Menlo", 12),
            relief=tk.SUNKEN,
            borderwidth=1,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL,
                                  command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=scrollbar.set)

        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Drop zone label (visual indicator)
        self.drop_label = ttk.Label(
            self,
            text="Drop .txt or .csv files here",
            foreground="gray",
            font=("Helvetica", 11, "italic"),
        )
        self.drop_label.pack(pady=(5, 0))

    def get_text(self) -> str:
        return self.text_area.get("1.0", tk.END).strip()

    def clear(self):
        self.text_area.delete("1.0", tk.END)


class JobRow(ttk.Frame):
    """Single job row in the jobs list."""

    def __init__(self, parent, job_data: dict,
                 on_retry: Callable[[str], None] = None,
                 on_remove: Callable[[str], None] = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.job_id = job_data.get('id', '')
        self.on_retry = on_retry
        self.on_remove = on_remove
        self._build(job_data)

    def _build(self, data: dict):
        # Title/ID
        title = data.get('title') or data.get('video_id') or 'Unknown'
        if len(title) > 60:
            title = title[:57] + "..."
        self.title_label = ttk.Label(self, text=title, width=45, anchor=tk.W)
        self.title_label.grid(row=0, column=0, sticky=tk.W, padx=(5, 10))

        # Status + Stage
        status = data.get('status', 'QUEUED')
        stage = data.get('stage', '')
        status_text = f"{status}"
        if stage and status == 'RUNNING':
            status_text += f" - {stage}"
        self.status_label = ttk.Label(self, text=status_text, width=30, anchor=tk.W)
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))

        # Progress
        progress = data.get('progress_pct', 0)
        self.progress_var = tk.IntVar(value=progress)
        self.progress_bar = ttk.Progressbar(
            self, variable=self.progress_var, maximum=100, length=120,
        )
        self.progress_bar.grid(row=0, column=2, padx=(0, 5))

        self.progress_label = ttk.Label(self, text=f"{progress}%", width=5)
        self.progress_label.grid(row=0, column=3, padx=(0, 10))

        # Action buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=0, column=4, sticky=tk.E)

        if status == 'FAILED':
            retry_btn = ttk.Button(btn_frame, text="Retry",
                                   command=lambda: self._do_retry(), width=6)
            retry_btn.pack(side=tk.LEFT, padx=2)

        if status in ('QUEUED', 'FAILED', 'SKIPPED', 'COMPLETED'):
            remove_btn = ttk.Button(btn_frame, text="Remove",
                                    command=lambda: self._do_remove(), width=7)
            remove_btn.pack(side=tk.LEFT, padx=2)

        # Error message (if any)
        error_msg = data.get('error_message')
        if error_msg and status == 'FAILED':
            err_label = ttk.Label(
                self, text=f"Error: {error_msg[:80]}",
                foreground="red", wraplength=500,
            )
            err_label.grid(row=1, column=0, columnspan=5, sticky=tk.W, padx=5)

    def _do_retry(self):
        if self.on_retry:
            self.on_retry(self.job_id)

    def _do_remove(self):
        if self.on_remove:
            self.on_remove(self.job_id)

    def update_data(self, data: dict):
        """Update display with new job data."""
        title = data.get('title') or data.get('video_id') or 'Unknown'
        if len(title) > 60:
            title = title[:57] + "..."
        self.title_label.configure(text=title)

        status = data.get('status', 'QUEUED')
        stage = data.get('stage', '')
        status_text = f"{status}"
        if stage and status == 'RUNNING':
            status_text += f" - {stage}"
        self.status_label.configure(text=status_text)

        progress = data.get('progress_pct', 0)
        self.progress_var.set(progress)
        self.progress_label.configure(text=f"{progress}%")


class JobsList(ttk.LabelFrame):
    """Scrollable list of job rows."""

    def __init__(self, parent, on_retry=None, on_remove=None, **kwargs):
        super().__init__(parent, text="  Jobs Queue  ", padding=5, **kwargs)
        self.on_retry = on_retry
        self.on_remove = on_remove
        self._rows: dict[str, JobRow] = {}
        self._build()

    def _build(self):
        # Canvas + scrollbar for scrolling
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL,
                                       command=self.canvas.yview)
        self.inner_frame = ttk.Frame(self.canvas)

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.inner_frame, anchor=tk.NW,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind canvas resize
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Empty label
        self.empty_label = ttk.Label(
            self.inner_frame, text="No jobs in queue",
            foreground="gray", font=("Helvetica", 12, "italic"),
        )
        self.empty_label.pack(pady=20)

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def update_jobs(self, jobs: list[dict]):
        """Refresh the entire jobs list."""
        # Clear existing
        for widget in self.inner_frame.winfo_children():
            widget.destroy()
        self._rows.clear()

        if not jobs:
            self.empty_label = ttk.Label(
                self.inner_frame, text="No jobs in queue",
                foreground="gray", font=("Helvetica", 12, "italic"),
            )
            self.empty_label.pack(pady=20)
            return

        for job_data in jobs:
            row = JobRow(
                self.inner_frame, job_data,
                on_retry=self.on_retry,
                on_remove=self.on_remove,
            )
            row.pack(fill=tk.X, padx=5, pady=2)
            sep = ttk.Separator(self.inner_frame, orient=tk.HORIZONTAL)
            sep.pack(fill=tk.X, padx=5)
            self._rows[job_data['id']] = row

    def update_single_job(self, job_data: dict):
        """Update a single job row."""
        job_id = job_data.get('id')
        if job_id in self._rows:
            self._rows[job_id].update_data(job_data)
