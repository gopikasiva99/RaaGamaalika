"""MelodyLine: tonic-relative pitch contour of the lead melody."""
from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np


@dataclass
class MelodyLine:
    tonic_hz: float
    hop_s: float
    cents: np.ndarray  # float32, relative to tonic, unfolded, NaN = unvoiced

    def __post_init__(self) -> None:
        self.cents = np.asarray(self.cents, dtype=np.float32)

    @property
    def voiced_seconds(self) -> float:
        return float(np.count_nonzero(~np.isnan(self.cents)) * self.hop_s)

    @property
    def duration_s(self) -> float:
        return float(len(self.cents) * self.hop_s)

    def folded(self) -> np.ndarray:
        v = self.cents[~np.isnan(self.cents)]
        return np.mod(v, 1200.0).astype(np.float32)

    def slice(self, start_s: float, end_s: float) -> "MelodyLine":
        a = max(0, int(round(start_s / self.hop_s)))
        b = max(a, int(round(end_s / self.hop_s)))
        return MelodyLine(self.tonic_hz, self.hop_s, self.cents[a:b].copy())

    def with_tonic(self, new_tonic_hz: float) -> "MelodyLine":
        shift = 1200.0 * np.log2(new_tonic_hz / self.tonic_hz)
        return MelodyLine(new_tonic_hz, self.hop_s, self.cents - np.float32(shift))

    def to_npz_bytes(self) -> bytes:
        buf = io.BytesIO()
        np.savez_compressed(buf, tonic_hz=np.float64(self.tonic_hz),
                            hop_s=np.float64(self.hop_s), cents=self.cents)
        return buf.getvalue()

    @classmethod
    def from_npz_bytes(cls, data: bytes) -> "MelodyLine":
        z = np.load(io.BytesIO(data))
        return cls(float(z["tonic_hz"]), float(z["hop_s"]), z["cents"])
