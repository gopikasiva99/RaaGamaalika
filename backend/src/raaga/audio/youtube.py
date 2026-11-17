"""Fetch just the needed segment of a YouTube video's audio (yt-dlp)."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from yt_dlp.utils import DownloadError, download_range_func

from raaga.config import ANALYSIS_WINDOW_S

ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}
_INVALID_MARKERS = ("unsupported url", "incomplete youtube id", "is not a valid url")


class YouTubeBlocked(Exception):
    pass


class YouTubeInvalid(Exception):
    pass


def validate_url(url: str) -> None:
    p = urlparse(url.strip())
    if p.scheme not in ("http", "https") or (p.hostname or "").lower() not in ALLOWED_HOSTS:
        raise YouTubeInvalid(url)


def fetch_youtube_segment(url: str, start_s: float, dest_dir: Path,
                          duration_s: float = ANALYSIS_WINDOW_S) -> Path:
    validate_url(url)
    start = max(0.0, float(start_s))
    start = int(start) if start.is_integer() else start
    end = start + duration_s
    end = int(end) if float(end).is_integer() else end
    opts = {
        "format": "bestaudio/best",
        "outtmpl": {"default": str(Path(dest_dir) / "yt.%(ext)s")},
        "download_ranges": download_range_func(None, [(start, end)]),
        "force_keyframes_at_cuts": False,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except DownloadError as e:
        msg = str(e).lower()
        if any(m in msg for m in _INVALID_MARKERS):
            raise YouTubeInvalid(url) from None
        raise YouTubeBlocked(str(e)[:200]) from None
    files = [f for f in Path(dest_dir).glob("yt.*") if f.is_file()]
    if not files:
        raise YouTubeBlocked("no file downloaded")
    return files[0]
