import sys
import os
import re
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing Dependency",
        "customtkinter is not installed.\n\n"
        "Please run:\n  pip install customtkinter\n\n"
        "Then restart this application."
    )
    sys.exit(1)

try:
    import yt_dlp
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing Dependency",
        "yt-dlp is not installed.\n\n"
        "Please run:\n  pip install yt-dlp\n\n"
        "Then restart this application."
    )
    sys.exit(1)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class YouTubeDownloaderApp:
    DEFAULT_FOLDER = r"C:\Users\mglas\Documents\Drum Tutorials"

    ALL_RESOLUTIONS = [480, 720, 1080, 1440, 2160]

    # Video bitrate targets in Mbps per (preset, resolution)
    BITRATE_MAP = {
        "Low":    {480: 1,   720: 2.5, 1080: 4,  1440: 8,  2160: 15},
        "Medium": {480: 2,   720: 5,   1080: 8,  1440: 15, 2160: 30},
        "High":   {480: 3,   720: 7.5, 1080: 12, 1440: 24, 2160: 45},
        "Best":   {480: 0,   720: 0,   1080: 0,  1440: 0,  2160: 0},
    }

    AUDIO_BITRATE_KBPS = 128

    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("600x720")
        self.root.minsize(520, 720)
        self.root.resizable(True, False)

        self._cancel_event = threading.Event()
        self._downloading = False
        self._fetching = False
        self._last_progress_update = 0.0
        self._download_phase = 0
        self._current_video_id = None
        self._video_duration = 0  # seconds
        self._available_resolutions = []
        self._formats = []  # raw format list from yt-dlp

        self.url_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="Video")
        self.quality_var = tk.StringVar(value="720")
        self.preset_var = tk.StringVar(value="Best")
        self.audio_format_var = tk.StringVar(value="mp3")
        self.folder_var = tk.StringVar(value=self.DEFAULT_FOLDER)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── GUI construction ─────────────────────────────────────

    def _build_ui(self):
        # Main card container
        card = ctk.CTkFrame(self.root, corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)
        self._card = card

        # Title
        ctk.CTkLabel(card, text="YouTube Downloader", font=("Segoe UI", 20, "bold")).pack(
            anchor="w", padx=20, pady=(20, 4)
        )
        ctk.CTkLabel(card, text="Download videos, playlists, or audio only", font=("Segoe UI", 12),
                      text_color="#888").pack(anchor="w", padx=20, pady=(0, 12))

        # URL + Fetch button
        ctk.CTkLabel(card, text="YouTube URL", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=20)
        url_frame = ctk.CTkFrame(card, fg_color="transparent")
        url_frame.pack(fill="x", padx=20, pady=(4, 12))
        self.url_entry = ctk.CTkEntry(url_frame, textvariable=self.url_var, placeholder_text="Paste YouTube URL here...",
                                       height=36, font=("Segoe UI", 12))
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.fetch_btn = ctk.CTkButton(url_frame, text="Fetch", command=self._fetch_info,
                                        width=80, height=36, font=("Segoe UI", 12),
                                        fg_color="#555", hover_color="#666")
        self.fetch_btn.pack(side="left", padx=(8, 0))

        # Video info label (hidden until fetch)
        self.info_label = ctk.CTkLabel(card, text="", font=("Segoe UI", 11), text_color="#aaa", anchor="w")

        # Mode (Video / Audio)
        self.mode_label = ctk.CTkLabel(card, text="Mode", font=("Segoe UI", 13, "bold"))
        self.mode_seg = ctk.CTkSegmentedButton(card, values=["Video", "Audio"],
                                                command=self._on_mode_change, font=("Segoe UI", 12))
        self.mode_seg.set("Video")

        # Resolution selector (dynamic, hidden until fetch)
        self.resolution_label = ctk.CTkLabel(card, text="Resolution", font=("Segoe UI", 13, "bold"))
        self.quality_seg = None  # built dynamically after fetch

        # Quality preset selector (hidden until fetch in Video mode)
        self.preset_label = ctk.CTkLabel(card, text="Quality", font=("Segoe UI", 13, "bold"))
        self.preset_seg = ctk.CTkSegmentedButton(card, values=["Low", "Medium", "High", "Best"],
                                                   command=self._on_preset_change, font=("Segoe UI", 12))
        self.preset_seg.set("Best")

        # Size estimate label
        self.size_label = ctk.CTkLabel(card, text="", font=("Segoe UI", 12, "bold"), text_color="#4a9eff", anchor="w")

        # Audio format selector (hidden until fetch in Audio mode)
        self.format_label = ctk.CTkLabel(card, text="Format", font=("Segoe UI", 13, "bold"))
        self.format_seg = ctk.CTkSegmentedButton(card, values=["MP3", "M4A", "WAV", "FLAC", "OGG"],
                                                  command=self._on_format_change, font=("Segoe UI", 12))
        self.format_seg.set("MP3")

        # Output folder (always visible)
        self.saveto_label = ctk.CTkLabel(card, text="Save To", font=("Segoe UI", 13, "bold"))
        self.saveto_label.pack(anchor="w", padx=20)
        fframe = ctk.CTkFrame(card, fg_color="transparent")
        fframe.pack(fill="x", padx=20, pady=(4, 12))
        self.folder_entry = ctk.CTkEntry(fframe, textvariable=self.folder_var, height=36, font=("Segoe UI", 12))
        self.folder_entry.pack(side="left", fill="x", expand=True)
        self.browse_btn = ctk.CTkButton(fframe, text="Browse", command=self._browse_folder, width=80, height=36,
                                         font=("Segoe UI", 12), fg_color="#555", hover_color="#666")
        self.browse_btn.pack(side="left", padx=(8, 0))
        self._folder_frame = fframe

        # Progress
        self.progress_bar = ctk.CTkProgressBar(card, height=14, corner_radius=7)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(8, 2))
        self.status_label = ctk.CTkLabel(card, text="Ready — paste a URL and click Fetch", font=("Segoe UI", 11), anchor="w")
        self.status_label.pack(fill="x", padx=20)
        self.speed_label = ctk.CTkLabel(card, text="", font=("Segoe UI", 11), text_color="#888", anchor="w")
        self.speed_label.pack(fill="x", padx=20)

        # Buttons
        bframe = ctk.CTkFrame(card, fg_color="transparent")
        bframe.pack(pady=(12, 20))
        self.download_btn = ctk.CTkButton(bframe, text="Download", command=self._start_download,
                                           width=150, height=40, font=("Segoe UI", 13, "bold"),
                                           state="disabled")
        self.download_btn.pack(side="left", padx=8)
        self.cancel_btn = ctk.CTkButton(bframe, text="Cancel", command=self._cancel_download,
                                         width=150, height=40, font=("Segoe UI", 13),
                                         fg_color="#555", hover_color="#666", state="disabled")
        self.cancel_btn.pack(side="left", padx=8)

    def _show_video_options(self):
        """Show resolution, preset, and size estimate controls for Video mode."""
        # Pack in order before the Save To label
        self.resolution_label.pack(anchor="w", padx=20, before=self.saveto_label)
        if self.quality_seg:
            self.quality_seg.pack(fill="x", padx=20, pady=(4, 12), before=self.saveto_label)
        self.preset_label.pack(anchor="w", padx=20, before=self.saveto_label)
        self.preset_seg.pack(fill="x", padx=20, pady=(4, 4), before=self.saveto_label)
        self.size_label.pack(fill="x", padx=20, pady=(0, 12), before=self.saveto_label)
        self._update_size_estimate()

    def _hide_video_options(self):
        """Hide resolution, preset, and size estimate controls."""
        self.resolution_label.pack_forget()
        if self.quality_seg:
            self.quality_seg.pack_forget()
        self.preset_label.pack_forget()
        self.preset_seg.pack_forget()
        self.size_label.pack_forget()

    def _show_audio_options(self):
        """Show audio format selector."""
        self.format_label.pack(anchor="w", padx=20, before=self.saveto_label)
        self.format_seg.pack(fill="x", padx=20, pady=(4, 12), before=self.saveto_label)

    def _hide_audio_options(self):
        """Hide audio format selector."""
        self.format_label.pack_forget()
        self.format_seg.pack_forget()

    def _show_options_for_mode(self):
        """Show the appropriate options panel based on current mode."""
        if not self._available_resolutions:
            return
        if self.mode_var.get() == "Video":
            self._hide_audio_options()
            self._show_video_options()
        else:
            self._hide_video_options()
            self._show_audio_options()

    def _on_mode_change(self, value):
        self.mode_var.set(value)
        self._show_options_for_mode()

    def _on_quality_change(self, value):
        self.quality_var.set(value.replace("p", ""))
        self._update_size_estimate()

    def _on_preset_change(self, value):
        self.preset_var.set(value)
        self._update_size_estimate()

    def _on_format_change(self, value):
        self.audio_format_var.set(value.lower())

    def _get_video_bitrate(self, fmt):
        """Get video-only bitrate in kbps, avoiding tbr which includes audio."""
        vbr = fmt.get("vbr")
        if vbr:
            return vbr
        # If tbr exists but abr also exists, subtract audio
        tbr = fmt.get("tbr") or 0
        abr = fmt.get("abr") or 0
        if tbr > abr:
            return tbr - abr
        return 0

    def _estimate_stream_size(self, fmt, bitrate_key="vbr"):
        """Estimate size in bytes from filesize fields or bitrate * duration."""
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        if size:
            return size
        if bitrate_key == "vbr":
            br = self._get_video_bitrate(fmt)
        else:
            br = fmt.get("abr") or 0
        return br * 1000 / 8 * self._video_duration

    def _update_size_estimate(self):
        """Calculate and display estimated file size using actual stream data."""
        if not self._video_duration or not self._available_resolutions or not self._formats:
            self.size_label.configure(text="")
            return

        preset = self.preset_var.get()
        resolution = int(self.quality_var.get())

        # Video-only streams at or below the target resolution
        video_only = [
            f for f in self._formats
            if f.get("vcodec", "none") != "none"
            and f.get("acodec", "none") == "none"  # video-only, not muxed
            and f.get("height") is not None
            and f.get("height") <= resolution
        ]

        # Prefer h264 streams (matching what the download format string selects)
        h264_streams = [f for f in video_only if "avc1" in (f.get("vcodec") or "")]
        preferred_video = h264_streams if h264_streams else video_only

        if preset != "Best":
            target_kbps = int(self.BITRATE_MAP[preset][resolution] * 1000)
            # Find streams under the bitrate cap
            capped = [f for f in preferred_video if self._get_video_bitrate(f) > 0
                       and self._get_video_bitrate(f) <= target_kbps]
            if capped:
                video_stream = max(capped, key=lambda f: (f.get("height", 0), self._get_video_bitrate(f)))
                video_size = self._estimate_stream_size(video_stream, "vbr")
            elif preferred_video:
                # No stream under cap; pick the lowest bitrate at target resolution
                at_res = [f for f in preferred_video if f.get("height") == resolution]
                pool = at_res if at_res else preferred_video
                video_stream = min(pool, key=lambda f: self._get_video_bitrate(f) or float("inf"))
                video_size = self._estimate_stream_size(video_stream, "vbr")
            else:
                self.size_label.configure(text="")
                return
        else:
            if not preferred_video:
                self.size_label.configure(text="")
                return
            video_stream = max(preferred_video, key=lambda f: (f.get("height", 0), self._get_video_bitrate(f)))
            video_size = self._estimate_stream_size(video_stream, "vbr")

        # Audio-only streams, prefer AAC (matching download preference)
        audio_only = [
            f for f in self._formats
            if f.get("acodec", "none") != "none"
            and f.get("vcodec", "none") == "none"
        ]
        aac_streams = [f for f in audio_only if "mp4a" in (f.get("acodec") or "")]
        preferred_audio = aac_streams if aac_streams else audio_only

        audio_size = 0
        if preferred_audio:
            audio_stream = max(preferred_audio, key=lambda f: f.get("abr") or 0)
            audio_size = self._estimate_stream_size(audio_stream, "abr")

        size_bytes = video_size + audio_size

        if size_bytes <= 0:
            self.size_label.configure(text="")
            return

        if size_bytes >= 1_073_741_824:
            size_str = f"{size_bytes / 1_073_741_824:.1f} GB"
        else:
            size_str = f"{size_bytes / 1_048_576:.0f} MB"

        self.size_label.configure(text=f"Estimated size: ~{size_str}")

    # ── Fetch video info ────────────────────────────────────────

    def _fetch_info(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Input Required", "Please enter a YouTube URL.")
            return
        if self._fetching:
            return

        self._fetching = True
        self.fetch_btn.configure(state="disabled", text="...")
        self.status_label.configure(text="Fetching video info...")
        self.download_btn.configure(state="disabled")

        # Hide any previous options
        self._hide_video_options()
        self._hide_audio_options()
        self.info_label.pack_forget()
        self.mode_label.pack_forget()
        self.mode_seg.pack_forget()

        thread = threading.Thread(target=self._fetch_thread, args=(url,), daemon=True)
        thread.start()

    def _fetch_thread(self, url):
        try:
            opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            duration = info.get("duration", 0) or 0
            title = info.get("title", "Unknown")
            formats = info.get("formats", [])

            # Find available resolutions
            available = set()
            for f in formats:
                h = f.get("height")
                if h and f.get("vcodec", "none") != "none":
                    for res in self.ALL_RESOLUTIONS:
                        if h >= res:
                            available.add(res)

            available = sorted(available) if available else [720]
            self.root.after(0, self._on_fetch_complete, True, title, duration, available, formats)
        except Exception as e:
            self.root.after(0, self._on_fetch_complete, False, str(e), 0, [], [])

    def _on_fetch_complete(self, success, title_or_error, duration, available_resolutions, formats):
        self._fetching = False
        self.fetch_btn.configure(state="normal", text="Fetch")

        if not success:
            self.status_label.configure(text="Ready")
            messagebox.showerror("Fetch Failed", title_or_error)
            return

        self._video_duration = duration
        self._available_resolutions = available_resolutions
        self._formats = formats

        # Format duration for display
        mins, secs = divmod(duration, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            dur_str = f"{int(hours)}h {int(mins)}m {int(secs)}s"
        else:
            dur_str = f"{int(mins)}m {int(secs)}s"

        # Show video info
        self.info_label.configure(text=f"{title_or_error}  ({dur_str})")
        self.info_label.pack(fill="x", padx=20, pady=(0, 8), before=self.saveto_label)

        # Show mode selector
        self.mode_label.pack(anchor="w", padx=20, before=self.saveto_label)
        self.mode_seg.pack(fill="x", padx=20, pady=(4, 12), before=self.saveto_label)

        # Build resolution segmented button with available options
        res_values = [f"{r}p" for r in available_resolutions]
        if self.quality_seg:
            self.quality_seg.destroy()
        self.quality_seg = ctk.CTkSegmentedButton(self._card, values=res_values,
                                                    command=self._on_quality_change, font=("Segoe UI", 12))
        # Default to highest available
        default_res = res_values[-1]
        self.quality_seg.set(default_res)
        self.quality_var.set(str(available_resolutions[-1]))
        self.preset_var.set("Best")
        self.preset_seg.set("Best")

        # Show options based on current mode
        self._show_options_for_mode()

        self.download_btn.configure(state="normal")
        self.status_label.configure(text="Ready to download")

    # ── Actions ───────────────────────────────────────────────

    def _browse_folder(self):
        current = self.folder_var.get()
        initial = current if os.path.isdir(current) else os.path.expanduser("~")
        chosen = filedialog.askdirectory(title="Select Download Folder", initialdir=initial)
        if chosen:
            self.folder_var.set(os.path.normpath(chosen))

    def _start_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Input Required", "Please enter a YouTube URL.")
            return

        output_dir = self.folder_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Input Required", "Please select a download folder.")
            return
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Invalid Folder", f"Cannot create folder:\n{output_dir}\n\n{e}")
            return

        self._set_ui_state(False)
        self._cancel_event.clear()
        self._downloading = True
        self._download_phase = 0
        self._current_video_id = None
        self.progress_bar.set(0)
        self.status_label.configure(text="Starting download...")
        self.speed_label.configure(text="")

        thread = threading.Thread(target=self._download_thread, args=(url, output_dir), daemon=True)
        thread.start()

    def _cancel_download(self):
        if self._downloading:
            self._cancel_event.set()
            self.status_label.configure(text="Cancelling...")

    def _on_close(self):
        if self._downloading:
            if messagebox.askokcancel("Download in Progress", "A download is running. Cancel and exit?"):
                self._cancel_event.set()
                self.root.after(500, self.root.destroy)
        else:
            self.root.destroy()

    # ── Download logic (background thread) ────────────────────

    def _download_thread(self, url, output_dir):
        is_audio = self.mode_var.get() == "Audio"

        opts = {
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [self._progress_hook],
            "overwrites": True,
            "windowsfilenames": True,
            "trim_file_name": 200,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": False,
        }

        if is_audio:
            audio_fmt = self.audio_format_var.get()
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_fmt,
                "preferredquality": "0",  # best quality
            }]
        else:
            quality = self.quality_var.get()
            preset = self.preset_var.get()

            if preset == "Best":
                opts["format"] = (
                    f"bestvideo[height<={quality}][vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
                    f"bestvideo[height<={quality}]+bestaudio/"
                    f"best[height<={quality}]/best"
                )
                opts["format_sort"] = [f"res:{quality}", "vcodec:h264", "acodec:m4a"]
            else:
                target_br = self.BITRATE_MAP[preset][int(quality)]
                target_kbps = int(target_br * 1000)
                opts["format"] = (
                    f"bestvideo[height<={quality}][vbr<={target_kbps}]+bestaudio/"
                    f"bestvideo[height<={quality}]+bestaudio/"
                    f"best[height<={quality}]/best"
                )
                opts["format_sort"] = [f"res:{quality}", f"tbr:{target_kbps}", "vcodec:h264", "acodec:m4a"]

            opts["merge_output_format"] = "mp4"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.root.after(0, self._on_download_complete, True, "Download complete!")
        except yt_dlp.utils.DownloadCancelled:
            self.root.after(0, self._on_download_complete, False, "Download cancelled.")
        except yt_dlp.utils.DownloadError as e:
            self.root.after(0, self._on_download_complete, False, str(e))
        except Exception as e:
            self.root.after(0, self._on_download_complete, False, f"Unexpected error:\n{e}")

    def _progress_hook(self, d):
        if self._cancel_event.is_set():
            raise yt_dlp.utils.DownloadCancelled("Download cancelled by user")

        status = d.get("status")
        info = d.get("info_dict") or {}
        video_id = info.get("id")

        # Reset phase when a new video starts (playlist support)
        if video_id and video_id != self._current_video_id:
            self._current_video_id = video_id
            self._download_phase = 0

        is_audio = self.mode_var.get() == "Audio"

        if status == "downloading":
            now = time.monotonic()
            if now - self._last_progress_update < 0.1:
                return
            self._last_progress_update = now

            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            stream_percent = (downloaded / total * 100) if total > 0 else 0

            if is_audio:
                # Audio: single stream → 90%, remaining 10% for conversion
                unified_percent = stream_percent * 0.90
            else:
                # Video: video stream (85%) + audio stream (15%)
                if self._download_phase == 0:
                    unified_percent = stream_percent * 0.85
                else:
                    unified_percent = 85 + stream_percent * 0.15

            speed = re.sub(r'\x1b\[[0-9;]*m', '', d.get("_speed_str", "N/A")).strip()
            eta = re.sub(r'\x1b\[[0-9;]*m', '', d.get("_eta_str", "N/A")).strip()
            title = info.get("title", os.path.basename(d.get("filename", "")))
            playlist_index = info.get("playlist_index")
            playlist_count = info.get("n_entries")

            if playlist_index and playlist_count:
                status_text = f"Video {playlist_index} of {playlist_count}: {title}"
            else:
                status_text = f"Downloading: {title}"

            speed_text = f"Speed: {speed}  |  ETA: {eta}  |  {unified_percent:.0f}%"
            self.root.after(0, self._update_progress, unified_percent, status_text, speed_text)

        elif status == "finished":
            self._download_phase += 1
            if is_audio:
                self.root.after(0, self._update_progress, 90, self.status_label.cget("text"),
                                f"Converting to {self.audio_format_var.get().upper()}...")
            elif self._download_phase < 2:
                self.root.after(0, self._update_progress, 85, self.status_label.cget("text"), "Merging streams...")

    # ── UI updates (main thread) ──────────────────────────────

    def _update_progress(self, percent, status_text, speed_text):
        self.progress_bar.set(percent / 100)
        self.status_label.configure(text=status_text)
        self.speed_label.configure(text=speed_text)

    def _on_download_complete(self, success, message):
        self._downloading = False
        self._set_ui_state(True)
        self.progress_bar.set(1.0 if success else 0.0)
        self.speed_label.configure(text="")

        if success:
            self.status_label.configure(text="Download complete!")
        else:
            self.status_label.configure(text="Ready")
            if "cancelled" not in message.lower():
                messagebox.showerror("Download Failed", message)

    def _set_ui_state(self, enabled):
        state = "normal" if enabled else "disabled"
        widgets = [self.url_entry, self.folder_entry, self.browse_btn, self.download_btn,
                   self.fetch_btn, self.format_seg, self.mode_seg, self.preset_seg]
        if self.quality_seg:
            widgets.append(self.quality_seg)
        for widget in widgets:
            widget.configure(state=state)
        self.cancel_btn.configure(state="disabled" if enabled else "normal")


if __name__ == "__main__":
    root = ctk.CTk()
    YouTubeDownloaderApp(root)
    root.mainloop()
