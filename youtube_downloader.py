import sys
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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


class YouTubeDownloaderApp:
    DEFAULT_FOLDER = r"C:\Users\mglas\Documents\Drum Tutorials"

    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Video Downloader")
        self.root.geometry("560x420")
        self.root.minsize(480, 400)
        self.root.resizable(True, False)

        self._cancel_event = threading.Event()
        self._downloading = False
        self._last_progress_update = 0.0
        self._download_phase = 0
        self._current_video_id = None

        self.url_var = tk.StringVar()
        self.quality_var = tk.StringVar(value="720")
        self.folder_var = tk.StringVar(value=self.DEFAULT_FOLDER)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── GUI construction ─────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 14, "pady": (6, 0)}

        # URL
        tk.Label(self.root, text="YouTube URL", font=("Segoe UI", 10, "bold")).pack(anchor="w", **pad)
        tk.Entry(self.root, textvariable=self.url_var, font=("Segoe UI", 10)).pack(
            fill="x", padx=14, pady=(2, 0)
        )
        tk.Label(self.root, text="Supports single videos and playlists", font=("Segoe UI", 8), fg="#666").pack(
            anchor="w", padx=14
        )

        # Quality
        tk.Label(self.root, text="Quality", font=("Segoe UI", 10, "bold")).pack(anchor="w", **pad)
        qframe = tk.Frame(self.root)
        qframe.pack(anchor="w", padx=14)
        for label, val in [("480p", "480"), ("720p", "720"), ("1080p", "1080")]:
            tk.Radiobutton(qframe, text=label, variable=self.quality_var, value=val, font=("Segoe UI", 10)).pack(
                side="left", padx=(0, 16)
            )

        # Output folder
        tk.Label(self.root, text="Save To", font=("Segoe UI", 10, "bold")).pack(anchor="w", **pad)
        fframe = tk.Frame(self.root)
        fframe.pack(fill="x", padx=14, pady=(2, 0))
        self.folder_entry = tk.Entry(fframe, textvariable=self.folder_var, font=("Segoe UI", 10))
        self.folder_entry.pack(side="left", fill="x", expand=True)
        self.browse_btn = tk.Button(fframe, text="Browse", command=self._browse_folder, font=("Segoe UI", 9))
        self.browse_btn.pack(side="left", padx=(6, 0))

        # Progress
        tk.Label(self.root, text="").pack()  # spacer
        self.progress_bar = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.progress_bar.pack(fill="x", padx=14)
        self.status_label = tk.Label(self.root, text="Ready", font=("Segoe UI", 9), anchor="w")
        self.status_label.pack(fill="x", padx=14)
        self.speed_label = tk.Label(self.root, text="", font=("Segoe UI", 9), fg="#555", anchor="w")
        self.speed_label.pack(fill="x", padx=14)

        # Buttons
        bframe = tk.Frame(self.root)
        bframe.pack(pady=(12, 14))
        self.download_btn = tk.Button(
            bframe, text="Download", command=self._start_download,
            font=("Segoe UI", 10, "bold"), width=12
        )
        self.download_btn.pack(side="left", padx=6)
        self.cancel_btn = tk.Button(
            bframe, text="Cancel", command=self._cancel_download,
            font=("Segoe UI", 10), width=12, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=6)

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
        self.progress_bar["value"] = 0
        self.status_label.config(text="Starting download...")
        self.speed_label.config(text="")

        thread = threading.Thread(target=self._download_thread, args=(url, output_dir), daemon=True)
        thread.start()

    def _cancel_download(self):
        if self._downloading:
            self._cancel_event.set()
            self.status_label.config(text="Cancelling...")

    def _on_close(self):
        if self._downloading:
            if messagebox.askokcancel("Download in Progress", "A download is running. Cancel and exit?"):
                self._cancel_event.set()
                self.root.after(500, self.root.destroy)
        else:
            self.root.destroy()

    # ── Download logic (background thread) ────────────────────

    def _download_thread(self, url, output_dir):
        quality = self.quality_var.get()
        opts = {
            "format": (
                f"bestvideo[height<={quality}][vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
                f"bestvideo[height<={quality}]+bestaudio/"
                f"best[height<={quality}]/best"
            ),
            "format_sort": [f"res:{quality}", "vcodec:h264", "acodec:m4a"],
            "merge_output_format": "mp4",
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [self._progress_hook],
            "overwrites": True,
            "windowsfilenames": True,
            "trim_file_name": 200,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": False,
        }

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

        if status == "downloading":
            now = time.monotonic()
            if now - self._last_progress_update < 0.1:
                return
            self._last_progress_update = now

            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            stream_percent = (downloaded / total * 100) if total > 0 else 0

            # Unify video (85%) + audio (15%) into one bar
            if self._download_phase == 0:
                unified_percent = stream_percent * 0.85
            else:
                unified_percent = 85 + stream_percent * 0.15

            speed = d.get("_speed_str", "N/A").strip()
            eta = d.get("_eta_str", "N/A").strip()
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
            if self._download_phase < 2:
                self.root.after(0, self._update_progress, 85, self.status_label.cget("text"), "Merging streams...")

    # ── UI updates (main thread) ──────────────────────────────

    def _update_progress(self, percent, status_text, speed_text):
        self.progress_bar["value"] = percent
        self.status_label.config(text=status_text)
        self.speed_label.config(text=speed_text)

    def _on_download_complete(self, success, message):
        self._downloading = False
        self._set_ui_state(True)
        self.progress_bar["value"] = 100 if success else 0
        self.speed_label.config(text="")

        if success:
            self.status_label.config(text="Download complete!")
        else:
            self.status_label.config(text="Ready")
            if "cancelled" not in message.lower():
                messagebox.showerror("Download Failed", message)

    def _set_ui_state(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in (self.folder_entry, self.browse_btn, self.download_btn):
            widget.config(state=state)
        self.cancel_btn.config(state="disabled" if enabled else "normal")


if __name__ == "__main__":
    root = tk.Tk()
    YouTubeDownloaderApp(root)
    root.mainloop()
