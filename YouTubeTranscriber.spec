# -*- mode: python ; coding: utf-8 -*-
"""
YouTubeTranscriber v3 — PyInstaller spec file.

Builds a native macOS .app bundle with a real Mach-O binary.

Usage:
    pyinstaller YouTubeTranscriber.spec
"""

import os
import sys

block_cipher = None

# Collect all app source files
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('app/extension', 'app/extension'),
    ],
    hiddenimports=[
        'app',
        'app.core',
        'app.core.constants',
        'app.core.config',
        'app.core.db_sqlite',
        'app.core.models_sqlite',
        'app.core.job_queue',
        'app.core.url_parse',
        'app.core.yt_metadata',
        'app.core.captions_fetch',
        'app.core.captions_parse',
        'app.core.audio_select',
        'app.core.download_audio',
        'app.core.normalize',
        'app.core.chunking_timebased',
        'app.core.transcribe_deepgram',
        'app.core.merge',
        'app.core.output_writer',
        'app.core.cleanup',
        'app.core.security_utils',
        'app.core.error_codes',
        'app.core.diagnostics',
        'app.desktop',
        'app.desktop.ui_main',
        'app.desktop.ui_components',
        'app.desktop.ui_settings',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'sqlite3',
        'requests',
        'json',
        'csv',
        'pathlib',
        'threading',
        'subprocess',
        'logging',
        'hashlib',
        'shutil',
        'tempfile',
        'urllib.parse',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'PIL', 'cv2', 'torch', 'tensorflow',
        'pytest', 'unittest', 'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YouTubeTranscriber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # Build for current architecture
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YouTubeTranscriber',
)

# Check if icon file exists
icon_file = 'AppIcon.icns' if os.path.exists('AppIcon.icns') else None

app = BUNDLE(
    coll,
    name='YouTubeTranscriber.app',
    icon=icon_file,
    bundle_identifier='com.local.youtubetranscriber',
    version='3.0.0',
    info_plist={
        'CFBundleName': 'YouTubeTranscriber',
        'CFBundleDisplayName': 'YouTube Transcriber',
        'CFBundleVersion': '3.0.0',
        'CFBundleShortVersionString': '3.0.0',
        'LSMinimumSystemVersion': '10.15',
        'NSHumanReadableCopyright': 'Local use only',
        'NSHighResolutionCapable': True,
        'LSEnvironment': {
            'PYTHONDONTWRITEBYTECODE': '1',
        },
    },
)
