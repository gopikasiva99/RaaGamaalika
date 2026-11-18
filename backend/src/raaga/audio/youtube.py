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


_LIST_PATHS = ("/playlist", "/channel/", "/c/", "/user/", "/@")
SOCKET_TIMEOUT_S = 30


def validate_url(url: str) -> None:
    """Accept single-video URLs on YouTube hosts only (no playlists or channels)."""
    p = urlparse(url.strip())
    if p.scheme not in ("http", "https") or (p.hostname or "").lower() not in ALLOWED_HOSTS:
        raise YouTubeInvalid(url)
    if p.path.startswith(_LIST_PATHS):
        raise YouTubeInvalid(url)


def fetch_youtube_segment(url: str, start_s: float, dest_dir: Path,
                          duration_s: float = ANALYSIS_WINDOW_S) -> Path:
    validate_url(url)
    start = max(0.0, float(start_s))
    start = int(start) if start.is_integer() else start
    end = start + duration_s
    end = int(end) if float(end).is_integer() else end
    rejected: list[str] = []

    def only_finished_videos(info, *, incomplete=False):
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            rejected.append("live")
            return "live streams are not supported"
        return None

    opts = {
        "format": "bestaudio/best",
        "playlist_items": "1",  # a watch URL carrying &list= must not walk the playlist
        "allowed_extractors": ["youtube"],
        "match_filter": only_finished_videos,
        "socket_timeout": SOCKET_TIMEOUT_S,
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
    if not files and rejected:
        raise YouTubeInvalid(url)
    if not files:
        raise YouTubeBlocked("no file downloaded")
    return files[0]
