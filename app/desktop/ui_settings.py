"""
Settings and Diagnostics UI panels for YouTubeTranscriber.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

from app.core.constants import CookiesMode, APP_VERSION
from app.core.diagnostics import get_diagnostics
from app.core.security_utils import keychain_get_api_key, keychain_set_api_key
from app.core.transcribe_deepgram import verify_api_key


class APIKeyDialog(tk.Toplevel):
    """Modal dialog for entering/changing the Deepgram API key."""

    def __init__(self, parent, title_text="Deepgram API Key Required",
                 body_text=None, allow_cancel_quit=False):
        super().__init__(parent)
        self.title(title_text)
        self.result_key: Optional[str] = None
        self._allow_cancel_quit = allow_cancel_quit
        self.transient(parent)
        self.grab_set()

        # Make modal
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.resizable(False, False)

        self._build(body_text or
                    "Paste your Deepgram API key to enable transcription fallback.\n"
                    "The key will be stored securely in macOS Keychain.")

        # Center on parent
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50,
                                  parent.winfo_rooty() + 50))
        self.wait_window()

    def _build(self, body_text: str):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Body text
        body = ttk.Label(frame, text=body_text, wraplength=400, justify=tk.LEFT)
        body.pack(fill=tk.X, pady=(0, 15))

        # API key entry (masked)
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(key_frame, text="API Key:").pack(side=tk.LEFT, padx=(0, 10))
        self.key_entry = ttk.Entry(key_frame, show="*", width=40)
        self.key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Status label
        self.status_label = ttk.Label(frame, text="", foreground="gray")
        self.status_label.pack(fill=tk.X, pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        self.save_btn = ttk.Button(btn_frame, text="Save", command=self._on_save)
        self.save_btn.pack(side=tk.RIGHT, padx=(5, 0))

        cancel_text = "Quit" if self._allow_cancel_quit else "Cancel"
        self.cancel_btn = ttk.Button(btn_frame, text=cancel_text,
                                     command=self._on_cancel)
        self.cancel_btn.pack(side=tk.RIGHT)

        # Network error: Save Anyway button (hidden initially)
        self.save_anyway_btn = ttk.Button(btn_frame, text="Save Anyway",
                                          command=self._on_save_anyway)

        self.key_entry.focus_set()

    def _on_save(self):
        key = self.key_entry.get().strip()
        if not key:
            self.status_label.configure(text="Please enter an API key", foreground="red")
            return

        self.status_label.configure(text="Verifying key...", foreground="gray")
        self.save_btn.configure(state=tk.DISABLED)
        self.update_idletasks()

        success, message = verify_api_key(key)

        if success:
            # Key verified — save to Keychain
            if keychain_set_api_key(key):
                self.status_label.configure(text="Key verified and saved", foreground="green")
                self.result_key = key
                self.after(800, self.destroy)
            else:
                self.status_label.configure(
                    text="Key verified but Keychain save failed", foreground="orange")
                self.result_key = key  # Still return it for in-memory use
                self.after(1200, self.destroy)
        elif "Network error" in message:
            # Network error — offer Save Anyway
            self.status_label.configure(
                text=f"Warning: {message}", foreground="orange")
            self.save_anyway_btn.pack(side=tk.RIGHT, padx=(5, 0))
            self.save_btn.configure(state=tk.NORMAL)
        else:
            # Invalid key
            self.status_label.configure(text=f"Key invalid: {message}", foreground="red")
            self.save_btn.configure(state=tk.NORMAL)

    def _on_save_anyway(self):
        key = self.key_entry.get().strip()
        if key:
            keychain_set_api_key(key)
            self.result_key = key
            self.destroy()

    def _on_cancel(self):
        self.result_key = None
        self.destroy()


class SettingsPanel(ttk.Frame):
    """Settings panel with output root, cookies mode, debug toggle, API key management."""

    def __init__(self, parent, config, on_config_changed=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.config = config
        self.on_config_changed = on_config_changed
        self._build()

    def _build(self):
        # ── Output Root ──
        output_frame = ttk.LabelFrame(self, text="  Output Folder  ", padding=10)
        output_frame.pack(fill=tk.X, padx=10, pady=5)

        self.output_var = tk.StringVar(value=self.config.output_root)
        ttk.Label(output_frame, textvariable=self.output_var, wraplength=400).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="Change...",
                   command=self._change_output).pack(side=tk.RIGHT)

        # ── Cookies Mode ──
        cookies_frame = ttk.LabelFrame(self, text="  Cookies  ", padding=10)
        cookies_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cookies_var = tk.StringVar(value=self.config.cookies_mode)
        ttk.Radiobutton(cookies_frame, text="Off", variable=self.cookies_var,
                        value=CookiesMode.OFF,
                        command=self._save_cookies_mode).pack(anchor=tk.W)
        ttk.Radiobutton(cookies_frame, text="Use cookies.txt file",
                        variable=self.cookies_var,
                        value=CookiesMode.USE_FILE,
                        command=self._save_cookies_mode).pack(anchor=tk.W)

        ttk.Label(cookies_frame,
                  text="Warning: cookies.txt contains sensitive session data",
                  foreground="orange", font=("Helvetica", 10, "italic")).pack(
            anchor=tk.W, pady=(5, 0))

        # ── Debug Artifacts ──
        debug_frame = ttk.LabelFrame(self, text="  Debug  ", padding=10)
        debug_frame.pack(fill=tk.X, padx=10, pady=5)

        self.debug_var = tk.BooleanVar(value=self.config.keep_debug_artifacts)
        ttk.Checkbutton(debug_frame, text="Keep debug artifacts after job completion",
                        variable=self.debug_var,
                        command=self._save_debug).pack(anchor=tk.W)

        # ── Deepgram API Key ──
        key_frame = ttk.LabelFrame(self, text="  Deepgram API Key  ", padding=10)
        key_frame.pack(fill=tk.X, padx=10, pady=5)

        key_status = "Key set" if keychain_get_api_key() else "Key not set"
        self.key_status_label = ttk.Label(key_frame, text=key_status)
        self.key_status_label.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(key_frame, text="Change Key...",
                   command=self._change_key).pack(side=tk.RIGHT)

        # ── App Version ──
        ttk.Label(self, text=f"YouTubeTranscriber v{APP_VERSION}",
                  foreground="gray").pack(pady=(10, 0))

    def _change_output(self):
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.config.output_root,
        )
        if folder:
            self.config.output_root = folder
            self.output_var.set(folder)
            if self.on_config_changed:
                self.on_config_changed()

    def _save_cookies_mode(self):
        self.config.cookies_mode = self.cookies_var.get()
        if self.on_config_changed:
            self.on_config_changed()

    def _save_debug(self):
        self.config.keep_debug_artifacts = self.debug_var.get()
        if self.on_config_changed:
            self.on_config_changed()

    def _change_key(self):
        dialog = APIKeyDialog(
            self.winfo_toplevel(),
            title_text="Change Deepgram API Key",
            body_text="Enter your new Deepgram API key.\n"
                      "The key will be stored securely in macOS Keychain.",
        )
        if dialog.result_key:
            self.key_status_label.configure(text="Key set")
        self._refresh_key_status()

    def _refresh_key_status(self):
        key = keychain_get_api_key()
        status = "Key set" if key else "Key not set"
        self.key_status_label.configure(text=status)


class DiagnosticsPanel(ttk.Frame):
    """Diagnostics panel showing tool versions and system info."""

    def __init__(self, parent, config=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.config = config
        self._build()

    def _build(self):
        frame = ttk.LabelFrame(self, text="  Diagnostics  ", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Info rows
        self.info_labels = {}
        fields = [
            ("yt-dlp Version", "ytdlp_version"),
            ("ffmpeg Version", "ffmpeg_version"),
            ("Cookies File", "cookies_detected"),
            ("Cookies Last Modified", "cookies_modified"),
        ]

        for i, (label, key) in enumerate(fields):
            ttk.Label(frame, text=f"{label}:", font=("Helvetica", 11, "bold")).grid(
                row=i, column=0, sticky=tk.W, padx=(0, 15), pady=3)
            val_label = ttk.Label(frame, text="...", wraplength=400)
            val_label.grid(row=i, column=1, sticky=tk.W, pady=3)
            self.info_labels[key] = val_label

        # Refresh button
        ttk.Button(frame, text="Refresh", command=self.refresh).grid(
            row=len(fields), column=0, columnspan=2, pady=(15, 0))

        # Auto-refresh on build
        self.after(100, self.refresh)

    def refresh(self):
        """Refresh diagnostic information."""
        from pathlib import Path
        cookies_path = None
        if self.config:
            cookies_path = Path(self.config.get('cookies_path', ''))

        diag = get_diagnostics(cookies_path)

        self.info_labels['ytdlp_version'].configure(text=diag['ytdlp_version'])
        self.info_labels['ffmpeg_version'].configure(text=diag['ffmpeg_version'])

        cookies = diag['cookies']
        self.info_labels['cookies_detected'].configure(
            text="Yes" if cookies['detected'] else "No")
        self.info_labels['cookies_modified'].configure(
            text=cookies.get('last_modified', 'N/A') or 'N/A')
