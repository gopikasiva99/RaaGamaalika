"""Decode any audio/video file to mono float32 PCM with ffmpeg."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from raaga.config import ANALYSIS_WINDOW_S, SAMPLE_RATE


class AudioDecodeError(Exception):
    pass


def decode_audio(path: Path, start_s: float = 0.0, max_s: float = ANALYSIS_WINDOW_S) -> np.ndarray:
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error",
        "-ss", f"{max(0.0, start_s):.3f}", "-t", f"{max_s:.3f}",
        "-i", str(path),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise AudioDecodeError(str(e)) from None
    if proc.returncode != 0 or not proc.stdout:
        raise AudioDecodeError(proc.stderr.decode(errors="replace").strip()[:300] or "no audio")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()
