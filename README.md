# YouTubeTranscriber v3

A **native macOS desktop application** for transcribing YouTube videos, built with **py2app** into a proper `.app` bundle with a real Mach-O binary. Double-click to launch from Finder, Spotlight, or the Dock — no terminal needed.

This is v3 of [YouTubeTranscriber](https://github.com/llmspace/YouTubeTranscriber), using py2app to produce a genuine macOS application that Finder and Gatekeeper recognize natively.

## What's New in v3

| Feature | v1 | v2 | v3 |
|---------|----|----|-----|
| Launch method | `python3 main.py` | Shell-script .app | **py2app native .app** |
| Binary type | Python script | Bash script | **Mach-O binary** |
| Finder/Gatekeeper | N/A | Blocked (error -54) | **Works natively** |
| Terminal required | Yes | Partially | **No** |
| Self-contained | No | No | **Yes (bundles Python)** |
| Build system | None | Manual .app folder | **py2app** |

## Features

- **Native macOS .app** — real Mach-O binary, no Gatekeeper issues
- **Self-contained** — bundles Python and all dependencies
- **Paste URLs** or **load .txt/.csv files** containing YouTube URLs
- **Creator captions-first**: uses creator-provided English captions when available
- **Deepgram fallback**: when no captions exist, downloads audio and transcribes via Deepgram Nova-3
- **Sequential processing** with full queue management
- **Duplicate detection**: skips videos already transcribed
- **Auto-retry** on transient failures; manual retry/remove from UI
- **Adaptive timeout chunking**: splits audio on Deepgram timeouts
- **Security hardened**: no listening ports, path traversal protection, Keychain storage
- **Browser extension**: exports YouTube-only cookies for restricted content

## Requirements

### System
- **macOS 10.15+** (Intel or Apple Silicon)
- **Python 3.10+** (for building only — the built app is self-contained)

### External Tools (required at runtime)
```bash
brew install yt-dlp ffmpeg
```

### API Key
- A **Deepgram API key** is needed for the speech-to-text fallback
- Sign up at [deepgram.com](https://deepgram.com)
- The key is stored securely in **macOS Keychain**

## Quick Start

### 1. Clone and Build

```bash
git clone https://github.com/llmspace/transcriberv3.git
cd transcriberv3
pip3 install -r requirements.txt
./build.sh
```

The build script will:
1. Check that Python 3, py2app, and requests are available
2. Build the native `.app` bundle into `dist/YouTubeTranscriber.app`
3. Remove quarantine flags automatically

### 2. Install

```bash
./install.sh
```

This copies the built app to `/Applications` and verifies `yt-dlp` and `ffmpeg` are installed.

### 3. Launch

- **Finder** → Applications → YouTubeTranscriber
- **Spotlight** → type "YouTubeTranscriber"
- **Dock** → drag from Applications to Dock for quick access
- Or **double-click** `dist/YouTubeTranscriber.app`

### Development Mode (Optional)

For development, use alias mode which links to your source files (changes take effect immediately):

```bash
./build.sh --dev
open dist/YouTubeTranscriber.app
```

## Usage

### Adding Videos

1. **Paste URLs**: Type or paste YouTube URLs into the text box (one per line)
2. **Load file**: Click "Load File..." to select a `.txt` or `.csv` file
3. Click **Start** to begin processing

### Output
Transcripts are saved as plain text files:
```
~/Downloads/YouTube Transcripts/
  └── Video Title/
      └── dQw4w9WgXcQ.txt
```

### Processing Pipeline

For each video:

1. **Validate URL** → extract `video_id`
2. **Check duplicates** → skip if already transcribed
3. **Fetch metadata** → get title, duration, formats
4. **Try creator captions** → download creator-provided English captions (VTT)
5. If captions found → **parse VTT to plain text** → write output
6. If no captions → **Deepgram fallback**:
   - Select optimal audio stream (64–128 kbps, prefer 96)
   - Download audio → Normalize (mono, 16kHz, MP3 96kbps)
   - Chunk if duration > 2 hours
   - Transcribe via Deepgram Nova-3
   - Merge chunks → write output
7. **Cleanup** → delete audio artifacts

## Browser Extension (Cookies Export)

For age-restricted or login-required videos:

1. Open Chrome → `chrome://extensions/` → Enable Developer mode
2. Click **Load unpacked** → select `app/extension/`
3. Log in to YouTube → click extension icon → **Export Cookies**
4. In app Settings, set Cookies mode to **Use cookies.txt file**

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Output folder | `~/Downloads/YouTube Transcripts/` | Where transcripts are saved |
| Cookies mode | Off | Enable to use exported cookies.txt |
| Keep debug artifacts | Off | Preserve metadata and Deepgram JSON after jobs |
| Deepgram API key | (Keychain) | Stored securely in macOS Keychain |

## Logs and Troubleshooting

### Log Location
```
~/Library/Logs/YouTubeTranscriber/app.log
```

### Crash Dialogs
If the app crashes, a native macOS alert will show the error message and point to the log file.

### Common Issues

| Issue | Solution |
|-------|----------|
| Build fails with "py2app not found" | `pip3 install py2app` |
| "yt-dlp Not Found" alert on launch | `brew install yt-dlp` |
| "ffmpeg Not Found" alert on launch | `brew install ffmpeg` |
| Transcription timeout on long videos | Automatic — app splits into smaller chunks |
| "Restricted content" error | Export cookies with the browser extension |

## Uninstall

```bash
cd transcriberv3
./uninstall.sh
```

This removes the app from `/Applications` and optionally deletes app data. Your transcripts are **never** deleted.

## Architecture

```
/transcriberv3
  build.sh                        ← Build script (runs py2app)
  install.sh                      ← Install to /Applications
  uninstall.sh                    ← Clean uninstaller
  setup.py                        ← py2app configuration
  main.py                         ← Python entry point
  requirements.txt                ← Python dependencies
  /app
    /desktop                      ← UI layer (tkinter)
      ui_main.py                  ← Main window, tabs, event handling
      ui_components.py            ← Reusable widgets (DropZone, JobsList)
      ui_settings.py              ← Settings, Diagnostics, API key dialogs
    /core                         ← Business logic
      constants.py, config.py, db_sqlite.py, models_sqlite.py,
      job_queue.py, url_parse.py, yt_metadata.py, captions_fetch.py,
      captions_parse.py, audio_select.py, download_audio.py,
      normalize.py, chunking_timebased.py, transcribe_deepgram.py,
      merge.py, output_writer.py, cleanup.py, security_utils.py,
      error_codes.py, diagnostics.py
    /extension                    ← Chrome extension for cookies export
  /tests
    test_core.py                  ← Unit tests (43 tests)
  /dist                           ← Built .app bundle (after ./build.sh)
    YouTubeTranscriber.app        ← Native macOS app with Mach-O binary
```

## Security

- **No incoming connections**: never binds/listens on any TCP port
- **Least-privilege filesystem**: only accesses output root, app support, and cookies
- **Path traversal protection**: all output paths validated with `realpath()` checks
- **Subprocess safety**: all `yt-dlp`/`ffmpeg` calls use argument arrays (no `shell=True`)
- **Secrets in Keychain**: Deepgram API key stored in macOS Keychain, never in plaintext
- **No secret logging**: API keys and cookie contents are never logged

## Privacy

- All processing happens **locally** on your Mac
- Audio files are downloaded temporarily and deleted after transcription
- The only outbound connections are to YouTube (via yt-dlp) and Deepgram API
- No data is sent to any other service

## License

This project is for personal/local use.
