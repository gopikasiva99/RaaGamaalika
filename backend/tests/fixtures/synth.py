"""Deterministic synthetic Carnatic-like clips for tests (no licensing issues)."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

from raaga.theory.swaras import TOKEN_POSITION

SR = 44100


def _note_sequence(swaras: list[str]) -> list[int]:
    """Semitone offsets cycling up two octaves and back down."""
    pos = sorted({TOKEN_POSITION[s] for s in swaras})
    up = [p for p in pos] + [p + 12 for p in pos] + [24]
    return up + up[-2:0:-1]


def synth_clip(swaras: list[str], tonic_hz: float, seconds: float, *, drone: bool = True,
               note_s: float = 0.5, seed: int = 0, leading_silence_s: float = 0.0,
               melody: bool = True) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(round(seconds * SR))
    lead = min(n, int(round(leading_silence_s * SR)))
    m = n - lead
    seq = _note_sequence(swaras)
    note_len = int(note_s * SR)
    idx = (np.arange(m) // note_len) % len(seq)
    semis = np.array(seq, dtype=np.float64)[idx]
    t = np.arange(m) / SR
    vib = 0.08 * np.sin(2 * np.pi * 5.5 * t + rng.uniform(0, 2 * np.pi))  # ~8 cents vibrato
    freq = tonic_hz * 2.0 ** ((semis + vib) / 12.0)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    tone = sum(np.sin(k * phase) / k for k in range(1, 6))
    # soft attack/release per note to avoid clicks
    pos_in_note = (np.arange(m) % note_len) / SR
    env = np.minimum(1.0, np.minimum(pos_in_note / 0.02, (note_s - pos_in_note) / 0.02))
    melody_sig = 0.35 * tone * np.clip(env, 0, 1) if melody else np.zeros(m)
    out = melody_sig
    if drone:
        tt = np.arange(m) / SR
        d = np.zeros(m)
        for f0 in (tonic_hz / 2, tonic_hz * 2 ** (7 / 12) / 2, tonic_hz, tonic_hz * 2):
            for k in range(1, 11):
                d += np.sin(2 * np.pi * f0 * k * tt + rng.uniform(0, 2 * np.pi)) / k
        pluck = np.exp(-((tt % 1.0) / 0.6))  # re-plucked every second
        out = out + 0.25 * 0.25 * d * (0.5 + 0.5 * pluck)
    out = out + 10 ** (-50 / 20) * rng.standard_normal(m)
    full = np.zeros(n, dtype=np.float32)
    full[lead:] = out.astype(np.float32)
    peak = float(np.max(np.abs(full))) or 1.0
    return (0.8 * full / peak).astype(np.float32)


def write_wav(path: Path, audio: np.ndarray, sr: int = SR) -> Path:
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return Path(path)


def encode(path_wav: Path, ext: str) -> Path:
    out = Path(path_wav).with_suffix("." + ext)
    if ext == "m4a":
        args = ["-i", str(path_wav), "-c:a", "aac", "-b:a", "128k"]
    elif ext == "webm":
        args = ["-i", str(path_wav), "-c:a", "libopus", "-b:a", "96k"]
    elif ext == "mp4":
        args = ["-f", "lavfi", "-i", "color=black:s=64x64:r=1", "-i", str(path_wav),
                "-map", "0:v", "-map", "1:a", "-c:v", "mpeg4", "-c:a", "aac", "-shortest"]
    else:
        raise ValueError(ext)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args, str(out)], check=True)
    return out


def synth_mridangam(tonic_hz: float, seconds: float, *, seed: int = 0) -> np.ndarray:
    """Percussive strokes: decaying tones near the tonic (mridangam is tuned to Sa) plus noisy hits."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = np.zeros(n)
    t = 0.0
    while t < seconds - 0.5:
        i = int(t * SR)
        L = int(0.35 * SR)
        tt = np.arange(L) / SR
        f = tonic_hz * rng.choice([1.0, 2.0])
        stroke = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt / 0.08)
        stroke += 0.6 * rng.standard_normal(L) * np.exp(-tt / 0.02)
        out[i:i + L] += stroke[: n - i]
        t += rng.choice([0.125, 0.25, 0.375])
    return (0.8 * out / np.max(np.abs(out))).astype(np.float32)


def synth_applause(seconds: float, *, seed: int = 0) -> np.ndarray:
    """Clapping: dense short noise bursts."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = 0.05 * rng.standard_normal(n)
    for _ in range(int(seconds * 25)):
        i = rng.integers(0, n - 2000)
        L = 1500
        out[i:i + L] += rng.standard_normal(L) * np.exp(-np.arange(L) / 200)
    return (0.8 * out / np.max(np.abs(out))).astype(np.float32)
