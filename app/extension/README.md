# YouTube Cookies Exporter — Browser Extension

## Overview

This Chrome/Chromium extension exports YouTube-only cookies to a local file in Netscape `cookies.txt` format, compatible with `yt-dlp`. This allows YouTubeTranscriber to access age-restricted or login-required content.

## Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select the `extension/` folder from this repository

## Usage

1. Log in to YouTube in your browser
2. Click the extension icon in the toolbar
3. Click **Export Cookies**
4. The cookies file will be saved to: `~/Downloads/YouTubeTranscriber/youtube_cookies.txt`

## Cookie Domains

By default, only cookies from these domains are exported:
- `.youtube.com`
- `.googlevideo.com`
- `.ytimg.com`

Optionally, you can include `.google.com` cookies by checking the option in the popup.

## Security Notes

- The exported `cookies.txt` contains sensitive session data
- **Do not share** this file with anyone
- The file grants access to your YouTube/Google account
- YouTubeTranscriber reads this file in read-only mode
- Consider deleting the cookies file after your transcription session

## File Format

The exported file uses the standard Netscape cookies.txt format:
```
# Netscape HTTP Cookie File
# domain  include_subdomains  path  secure  expiry  name  value
```

## Permissions

This extension requires:
- `cookies` — to read browser cookies for allowed domains
- `downloads` — to save the cookies file to disk
- Host permissions for YouTube-related domains only
