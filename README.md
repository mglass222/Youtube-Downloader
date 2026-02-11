# YouTube Video Downloader

A simple GUI application for downloading YouTube videos and playlists. Built for backing up drum tutorial content.

## Features

- Download single videos or entire playlists
- Quality selection: 480p, 720p, or 1080p
- Output format: MP4 container with H.264 video + AAC audio
- Browse for output folder or create a new one
- Progress bar with speed, ETA, and current video info
- Cancel downloads mid-progress

## Dependencies

| Dependency | Purpose | Install |
|---|---|---|
| **Python 3.10+** | Runtime | [python.org](https://www.python.org/downloads/) |
| **yt-dlp** | YouTube download backend | `pip install yt-dlp` |
| **customtkinter** | Modern dark-themed GUI | `pip install customtkinter` |
| **ffmpeg** | Merges video + audio streams into MP4 | `winget install Gyan.FFmpeg` |
| **tkinter** | GUI framework | Included with Python on Windows |

## Setup

1. Install Python 3.10 or later (make sure "Add to PATH" is checked during install).

2. Install ffmpeg:
   ```
   winget install Gyan.FFmpeg
   ```

3. Install Python packages:
   ```
   pip install yt-dlp customtkinter
   ```

4. Verify both are available:
   ```
   ffmpeg -version
   yt-dlp --version
   ```

## Usage

Run the application:

```
python youtube_downloader.py
```

1. Paste a YouTube video or playlist URL into the URL field.
2. Select your desired quality (480p, 720p, or 1080p).
3. Choose an output folder (defaults to `C:\Users\mglas\Documents\Drum Tutorials`).
4. Click **Download**.
5. Use **Cancel** to stop a download in progress.

## Updating yt-dlp

YouTube frequently changes its internals. If downloads start failing, update yt-dlp:

```
pip install --upgrade yt-dlp
```
