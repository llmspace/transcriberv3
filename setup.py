"""
YouTubeTranscriber v3 — py2app build script.

Builds a native macOS .app bundle with a real Mach-O binary launcher.

Usage:
    # Development (alias mode — fast, links to source):
    python3 setup.py py2app -A

    # Distribution (standalone — fully self-contained):
    python3 setup.py py2app

The built app will be in the dist/ directory.
"""

import os
from setuptools import setup

APP = ["main.py"]
APP_NAME = "YouTubeTranscriber"

DATA_FILES = []

# Check if .icns icon exists (user builds it on macOS)
ICON_FILE = "AppIcon.icns" if os.path.exists("AppIcon.icns") else None

PY2APP_OPTIONS = {
    "argv_emulation": False,  # Don't use argv emulation with tkinter
    "plist": {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": "YouTube Transcriber",
        "CFBundleIdentifier": "com.local.youtubetranscriber",
        "CFBundleVersion": "3.0.0",
        "CFBundleShortVersionString": "3.0.0",
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "10.15",
        "NSHumanReadableCopyright": "Local use only",
        "LSUIElement": False,
        "NSHighResolutionCapable": True,
        "LSEnvironment": {
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    },
    "packages": [
        "app",
        "app.core",
        "app.desktop",
        "tkinter",
        "requests",
    ],
    "includes": [
        "app.core.constants",
        "app.core.config",
        "app.core.db_sqlite",
        "app.core.models_sqlite",
        "app.core.job_queue",
        "app.core.url_parse",
        "app.core.yt_metadata",
        "app.core.captions_fetch",
        "app.core.captions_parse",
        "app.core.audio_select",
        "app.core.download_audio",
        "app.core.normalize",
        "app.core.chunking_timebased",
        "app.core.transcribe_deepgram",
        "app.core.merge",
        "app.core.output_writer",
        "app.core.cleanup",
        "app.core.security_utils",
        "app.core.error_codes",
        "app.core.diagnostics",
        "app.desktop.ui_main",
        "app.desktop.ui_components",
        "app.desktop.ui_settings",
        "sqlite3",
    ],
    "excludes": [
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "matplotlib", "numpy", "scipy", "pandas",
        "PIL", "cv2", "torch", "tensorflow",
        "pytest", "unittest",
    ],
    "site_packages": True,
}

# Add icon if available
if ICON_FILE:
    PY2APP_OPTIONS["iconfile"] = ICON_FILE

setup(
    name=APP_NAME,
    version="3.0.0",
    description="Local macOS YouTube Transcription Tool",
    install_requires=[
        "requests>=2.28.0",
    ],
    python_requires=">=3.10",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": PY2APP_OPTIONS},
    setup_requires=["py2app"],
)
