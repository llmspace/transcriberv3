# YouTubeTranscriber

A **native macOS desktop application** for transcribing YouTube videos. Built with **PyInstaller** into a genuine `.app` bundle with a Mach-O binary — double-click to launch from Finder, Spotlight, or the Dock with no terminal required.

YouTubeTranscriber takes a **captions-first approach**: it downloads creator-provided English captions whenever available, falling back to **Deepgram Nova-3** speech-to-text only when captions are absent. The result is fast, accurate transcripts saved as plain text files on your Mac.

## Features

YouTubeTranscriber is designed as a single-user, offline-first macOS application with no server component and no incoming network connections.

| Category | Details |
|----------|---------|
| **Native macOS app** | Real Mach-O binary, launches from Finder/Spotlight/Dock |
| **Self-contained** | Bundles Python and all dependencies via PyInstaller |
| **Captions-first** | Uses creator-provided English captions when available |
| **Deepgram fallback** | Nova-3 speech-to-text for videos without captions |
| **Batch processing** | Paste multiple URLs or load `.txt`/`.csv` files |
| **Duplicate detection** | Skips videos already transcribed |
| **Auto-retry** | Retries transient failures; manual retry/remove from UI |
| **Adaptive chunking** | Splits long audio on Deepgram timeouts automatically |
| **Security hardened** | No listening ports, path traversal protection, Keychain storage |
| **Cookies export** | Chrome extension for age-restricted or login-required videos |

## Requirements

### System

YouTubeTranscriber requires **macOS 10.15 or later** and runs on both Intel and Apple Silicon Macs. Python 3.10 or newer is needed only for building the app — the built `.app` is fully self-contained.

### External Tools

Two command-line tools must be installed via Homebrew. These are used at runtime for downloading and processing audio:

```bash
brew install yt-dlp ffmpeg
```

### Deepgram API Key

A Deepgram API key is required for the speech-to-text fallback (used only when creator captions are unavailable). Sign up at [deepgram.com](https://deepgram.com) to obtain a key. The key is stored securely in the **macOS Keychain** and never written to disk in plaintext.

## Quick Start

### 1. Clone and Build

```bash
git clone https://github.com/llmspace/transcriberv3.git
cd transcriberv3
pip3 install -r requirements.txt
./build.sh
```

The build script checks that Python 3, PyInstaller, and requests are available, then produces a native `.app` bundle at `dist/YouTubeTranscriber.app` with quarantine flags automatically removed.

### 2. Install

```bash
./install.sh
```

This copies the built app to `/Applications` and verifies that `yt-dlp` and `ffmpeg` are installed.

### 3. Launch

Launch the application through any of the standard macOS methods: open **Finder** and navigate to Applications, use **Spotlight** and type "YouTubeTranscriber", or drag the app to the **Dock** for quick access. No terminal window is needed — the app runs as a native GUI application.

## Usage

### Adding Videos

The main window presents a drop zone where you can paste YouTube URLs (one per line) or click **Load File** to select a `.txt` or `.csv` file containing URLs. Click **Start** to begin processing the queue.

### Output

Transcripts are saved as plain text files organized by video title:

```
~/Downloads/YouTube Transcripts/
  └── Video Title/
      └── dQw4w9WgXcQ.txt
```

### Processing Pipeline

Each video passes through the following stages in sequence. The job state machine tracks progress through QUEUED, RUNNING, and terminal states (COMPLETED, FAILED, or SKIPPED).

| Stage | Description |
|-------|-------------|
| **Validate URL** | Extract `video_id` from the YouTube URL |
| **Check duplicates** | Skip if the video has already been transcribed |
| **Fetch metadata** | Retrieve title, duration, and available formats via yt-dlp |
| **Try creator captions** | Download creator-provided English captions in VTT format |
| **Parse VTT** | Convert VTT to clean plain text (if captions were found) |
| **Deepgram fallback** | If no captions: select audio stream, download, normalize, chunk, transcribe |
| **Merge chunks** | Combine transcript segments with overlap deduplication |
| **Write output** | Save the final transcript to the output directory |
| **Cleanup** | Delete temporary audio artifacts |

### Audio Pipeline (Deepgram Path)

When creator captions are unavailable, the app downloads and processes audio before sending it to Deepgram. The audio stream is selected targeting 96 kbps (accepting 64–128 kbps), then normalized to mono 16 kHz MP3 at 96 kbps using ffmpeg. Videos longer than two hours are split into overlapping chunks to stay within Deepgram's processing limits.

## Browser Extension (Cookies Export)

For age-restricted or login-required videos, a Chrome extension is included that exports YouTube-only cookies in Netscape format:

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** in the top-right corner
3. Click **Load unpacked** and select the `app/extension/` directory
4. Log in to YouTube, then click the extension icon and select **Export Cookies**
5. In the app's Settings tab, set Cookies mode to **Use cookies.txt file**

The extension only exports cookies scoped to `youtube.com` domains and never transmits data externally.

## Settings

The Settings tab provides configuration for output location, cookies, debug mode, and the Deepgram API key.

| Setting | Default | Description |
|---------|---------|-------------|
| Output folder | `~/Downloads/YouTube Transcripts/` | Directory where transcripts are saved |
| Cookies mode | Off | Enable to use an exported cookies.txt file for restricted content |
| Keep debug artifacts | Off | Preserve metadata JSON and Deepgram response files after jobs |
| Deepgram API key | *(Keychain)* | Stored securely in macOS Keychain via the Settings dialog |

## Logs and Troubleshooting

### Log Location

Application logs are written to `~/Library/Logs/YouTubeTranscriber/app.log` and include timestamped entries for every pipeline stage, tool paths, and error details.

### Common Issues

| Issue | Solution |
|-------|----------|
| Build fails with "PyInstaller not found" | Run `pip3 install pyinstaller` |
| "Missing required tools" alert on launch | Run `brew install yt-dlp ffmpeg` and rebuild the app |
| App can't find yt-dlp/ffmpeg after install | Rebuild with `./build.sh` — the app adds Homebrew paths to PATH at startup |
| Transcription timeout on long videos | Handled automatically — the app splits audio into smaller chunks and retries |
| "Restricted content" error | Export cookies using the included browser extension |
| Gatekeeper blocks the app | Run `xattr -cr dist/YouTubeTranscriber.app` or right-click → Open |

### PATH Handling

When macOS launches a `.app` bundle, it does not source shell profiles (`~/.zshrc`, `~/.bash_profile`), so Homebrew paths are not available by default. The application automatically adds `/opt/homebrew/bin`, `/usr/local/bin`, and common Python framework paths to `PATH` at startup, ensuring that `yt-dlp` and `ffmpeg` are found regardless of how the app is launched.

## Uninstall

```bash
cd transcriberv3
./uninstall.sh
```

This removes the app from `/Applications` and optionally deletes application support data. Transcripts in the output directory are never deleted.

## Architecture

```
transcriberv3/
├── main.py                         ← Python entry point (PATH setup, prereq checks)
├── YouTubeTranscriber.spec         ← PyInstaller build configuration
├── build.sh                        ← Build script (runs PyInstaller)
├── install.sh                      ← Install to /Applications
├── uninstall.sh                    ← Clean uninstaller
├── requirements.txt                ← Python dependencies
├── app/
│   ├── desktop/                    ← UI layer (tkinter)
│   │   ├── ui_main.py             ← Main window, tabs, event handling
│   │   ├── ui_components.py       ← Reusable widgets (DropZone, JobsList)
│   │   └── ui_settings.py         ← Settings, Diagnostics, API key dialogs
│   ├── core/                       ← Business logic
│   │   ├── constants.py           ← Shared configuration values
│   │   ├── config.py              ← JSON config manager
│   │   ├── db_sqlite.py           ← SQLite database with migrations
│   │   ├── models_sqlite.py       ← Data models
│   │   ├── job_queue.py           ← Job worker and pipeline orchestration
│   │   ├── url_parse.py           ← YouTube URL validation and parsing
│   │   ├── yt_metadata.py         ← Video metadata fetching via yt-dlp
│   │   ├── captions_fetch.py      ← Creator caption downloading
│   │   ├── captions_parse.py      ← VTT to plain text conversion
│   │   ├── audio_select.py        ← Audio stream selection
│   │   ├── download_audio.py      ← Audio downloading via yt-dlp
│   │   ├── normalize.py           ← Audio normalization via ffmpeg
│   │   ├── chunking_timebased.py  ← Time-based audio chunking
│   │   ├── transcribe_deepgram.py ← Deepgram Nova-3 transcription
│   │   ├── merge.py               ← Transcript chunk merging with deduplication
│   │   ├── output_writer.py       ← Transcript file writing
│   │   ├── cleanup.py             ← Temporary file cleanup
│   │   ├── security_utils.py      ← Path sanitization, subprocess safety
│   │   ├── error_codes.py         ← Standardized error codes
│   │   └── diagnostics.py         ← System diagnostics
│   └── extension/                  ← Chrome extension for cookies export
│       ├── manifest.json
│       ├── background.js
│       ├── popup.html
│       ├── popup.js
│       └── README.md
├── tests/
│   └── test_core.py               ← Unit tests (43 tests)
└── dist/                           ← Built .app bundle (after ./build.sh)
    └── YouTubeTranscriber.app
```

## Security

The application is designed with a strict security posture appropriate for a local desktop tool that handles API credentials and user content.

**No incoming connections** — the application never binds or listens on any TCP or UDP port. All network activity is outbound only (YouTube via yt-dlp, Deepgram API via HTTPS).

**Least-privilege filesystem access** — the app only reads and writes within the configured output directory, the Application Support folder, and the cookies file path. All output paths are validated with `realpath()` checks to prevent path traversal.

**Subprocess safety** — all calls to `yt-dlp` and `ffmpeg` use argument arrays with `shell=False`, preventing shell injection. No user input is ever interpolated into shell commands.

**Secrets in Keychain** — the Deepgram API key is stored in the macOS Keychain and retrieved at runtime. It is never written to configuration files, logged, or displayed in the UI after entry.

## Privacy

All processing happens locally on your Mac. Audio files are downloaded temporarily and deleted after transcription. The only outbound connections are to YouTube (via yt-dlp) and the Deepgram API (for speech-to-text when captions are unavailable). No data is sent to any other service.

## Disclaimer

This tool is intended for **personal, educational, and accessibility use only**. Users are responsible for ensuring their use complies with YouTube's Terms of Service and applicable laws in their jurisdiction.

YouTubeTranscriber does not host, redistribute, or monetize any YouTube content. It uses `yt-dlp` (an open-source tool) to access publicly available content for the purpose of generating text transcripts. The application does not circumvent digital rights management (DRM) or technological protection measures.

**By using this software, you acknowledge that:**
- You will only transcribe content you have the right to access
- You are responsible for compliance with YouTube's Terms of Service
- The developers are not liable for any misuse of this tool

## License

MIT License. See [LICENSE](LICENSE) for details.
