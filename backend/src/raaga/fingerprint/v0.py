"""Model v0 fingerprint: folded pitch histogram + time-delayed melody surface (TDMS)."""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d

from raaga.config import BIN_CENTS, N_BINS
from raaga.melody.line import MelodyLine

TDMS_DELAY_S = 0.3
TDMS_BINS = 40
TDMS_BIN_CENTS = 1200 // TDMS_BINS  # 30
TDMS_POWER = 0.75
DIM = N_BINS + TDMS_BINS * TDMS_BINS  # 1720


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def fingerprint_v0(line: MelodyLine) -> np.ndarray:
    c = line.cents
    voiced = ~np.isnan(c)
    if not voiced.any():
        return np.zeros(DIM, dtype=np.float32)
    folded = np.mod(c[voiced], 1200.0)
    hist = np.bincount(np.minimum((folded // BIN_CENTS).astype(int), N_BINS - 1), minlength=N_BINS)
    hist = _unit(gaussian_filter1d(hist.astype(np.float64), 1.0, mode="wrap"))

    d = max(1, int(round(TDMS_DELAY_S / line.hop_s)))
    tdms = np.zeros((TDMS_BINS, TDMS_BINS))
    if len(c) > d:
        a, b = c[:-d], c[d:]
        ok = ~np.isnan(a) & ~np.isnan(b)
        if ok.any():
            ia = np.minimum((np.mod(a[ok], 1200.0) // TDMS_BIN_CENTS).astype(int), TDMS_BINS - 1)
            ib = np.minimum((np.mod(b[ok], 1200.0) // TDMS_BIN_CENTS).astype(int), TDMS_BINS - 1)
            np.add.at(tdms, (ia, ib), 1.0)
            tdms = gaussian_filter(tdms, 1.0, mode="wrap") ** TDMS_POWER
            tdms /= tdms.sum()
    tdms = _unit(tdms.ravel())
    return _unit(np.concatenate([0.5 * hist, 0.5 * tdms])).astype(np.float32)


FINGERPRINTS: dict[str, Callable[[MelodyLine], np.ndarray]] = {"v0": fingerprint_v0}
