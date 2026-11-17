"""Fast synthetic MelodyLines (no audio) for matching tests."""
from __future__ import annotations

import numpy as np

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
    cents = order * 100.0 + rng.normal(0, noise_cents, n)
    cents[rng.random(n) < 0.1] = np.nan
    return MelodyLine(tonic_hz, HOP, cents.astype(np.float32))
