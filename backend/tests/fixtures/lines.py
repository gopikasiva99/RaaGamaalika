"""Fast synthetic MelodyLines (no audio) for matching tests."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d

from raaga.melody.line import MelodyLine

HOP = 128 / 44100


def make_line(positions: list[int], seconds: float = 30.0, *, seed: int = 0, noise_cents: float = 5.0,
              note_s: float = 0.4, tonic_hz: float = 146.8) -> MelodyLine:
    rng = np.random.default_rng(seed)
    pos = sorted(positions)
    seq = pos + [p + 12 for p in pos] + [24]
    seq = seq + seq[-2:0:-1]
    n = int(seconds / HOP)
    per = max(1, int(note_s / HOP))
    order = np.array(seq)[(np.arange(n) // per) % len(seq)]
    jitter = rng.integers(0, len(seq))  # different phase per seed
    order = np.roll(order, jitter * per)
    # Pitch wanders smoothly (like intonation drift / gamaka), not white noise per frame.
    drift = gaussian_filter1d(rng.normal(0, 1, n), sigma=0.03 / HOP)
    drift *= noise_cents / (drift.std() or 1.0)
    cents = order * 100.0 + drift
    # Unvoiced stretches (breaths, rests) of ~50-300 ms covering ~10% of frames.
    k = 0
    while k < n:
        k += int(rng.integers(int(0.8 / HOP), int(3.0 / HOP)))
        cents[k:k + int(rng.integers(int(0.05 / HOP), int(0.3 / HOP)))] = np.nan
    return MelodyLine(tonic_hz, HOP, cents.astype(np.float32))
