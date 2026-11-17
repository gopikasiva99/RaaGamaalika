"""Swara tokens and their positions (semitones above Sa)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter1d, median_filter

from raaga.config import BIN_CENTS, N_BINS, TheoryParams

TOKEN_POSITION: dict[str, int] = {
    "S": 0,
    "R1": 1, "R2": 2, "R3": 3,
    "G1": 2, "G2": 3, "G3": 4,
    "M1": 5, "M2": 6,
    "P": 7,
    "D1": 8, "D2": 9, "D3": 10,
    "N1": 9, "N2": 10, "N3": 11,
}


def positions(tokens: Iterable[str]) -> frozenset[int]:
    """Positions (0..11) used by a sequence of swara tokens."""
    try:
        return frozenset(TOKEN_POSITION[t] for t in tokens)
    except KeyError as e:
        raise ValueError(f"unknown swara token {e.args[0]!r}") from None


# --- Swara profile and directional transitions -------------------------------

STABLE_SLOPE_CENTS_PER_S = 300.0
SLOPE_HALF_WINDOW_S = 0.025
MIN_SEGMENT_S = 0.08
_POS_CENTS = np.arange(12) * 100.0


@dataclass
class SwaraProfile:
    histogram: np.ndarray  # (120,) sum 1 (or zeros)
    strengths: np.ndarray  # (12,) max 1 (or zeros)


@dataclass
class Transitions:
    up: np.ndarray  # (12, 12) counts [from, to]
    down: np.ndarray


def _circ_dist(folded: np.ndarray) -> np.ndarray:
    """(n, 12) circular distance in cents from each frame to each position."""
    d = np.abs(folded[:, None] - _POS_CENTS[None, :])
    return np.minimum(d, 1200.0 - d)


def _smoothed(cents: np.ndarray) -> np.ndarray:
    voiced = ~np.isnan(cents)
    out = cents.copy()
    if voiced.sum() >= 5:
        filled = np.interp(np.arange(len(cents)), np.flatnonzero(voiced), cents[voiced])
        out = np.where(voiced, median_filter(filled, size=5, mode="nearest"), np.nan)
    return out.astype(np.float32)


def _stable_mask(cents: np.ndarray, hop_s: float) -> np.ndarray:
    c = _smoothed(cents)
    k = max(1, int(round(SLOPE_HALF_WINDOW_S / hop_s)))
    slope = np.full(len(c), np.inf)
    if len(c) > 2 * k:
        slope[k:-k] = np.abs(c[2 * k:] - c[:-2 * k]) / (2 * k * hop_s)
    with np.errstate(invalid="ignore"):
        return np.nan_to_num(slope, nan=np.inf) < STABLE_SLOPE_CENTS_PER_S


def swara_profile(line, params: TheoryParams) -> SwaraProfile:
    voiced = ~np.isnan(line.cents)
    n_voiced = int(voiced.sum())
    if n_voiced == 0:
        return SwaraProfile(np.zeros(N_BINS), np.zeros(12))
    folded = np.mod(line.cents[voiced], 1200.0)
    bins = np.minimum((folded // BIN_CENTS).astype(int), N_BINS - 1)
    hist = np.bincount(bins, minlength=N_BINS).astype(np.float64)
    hist = gaussian_filter1d(hist, sigma=1.0, mode="wrap")
    hist /= hist.sum()
    near = _circ_dist(folded) <= params.tolerance_cents
    stable = _stable_mask(line.cents, line.hop_s)[voiced]
    mass_all = near.sum(axis=0) / n_voiced
    mass_stable = (near & stable[:, None]).sum(axis=0) / n_voiced
    s = 0.5 * mass_all + 0.5 * mass_stable
    peak = s.max()
    return SwaraProfile(hist, s / peak if peak > 0 else np.zeros(12))


def transitions(line, params: TheoryParams) -> Transitions:
    up = np.zeros((12, 12))
    down = np.zeros((12, 12))
    cents = line.cents
    voiced = ~np.isnan(cents)
    if not voiced.any():
        return Transitions(up, down)
    pos = np.full(len(cents), -1)
    folded = np.mod(np.where(voiced, cents, 0.0), 1200.0)
    dist = _circ_dist(folded)
    nearest = dist.argmin(axis=1) % 12
    ok = voiced & (dist.min(axis=1) <= params.tolerance_cents)
    pos[ok] = nearest[ok]
    min_len = max(1, int(round(MIN_SEGMENT_S / line.hop_s)))
    segments: list[tuple[int, float]] = []  # (position, mean unfolded cents)
    start = 0
    for i in range(1, len(pos) + 1):
        if i == len(pos) or pos[i] != pos[start]:
            if pos[start] >= 0 and i - start >= min_len:
                p, m = int(pos[start]), float(np.mean(cents[start:i]))
                if segments and segments[-1][0] == p:
                    segments[-1] = (p, m)
                else:
                    segments.append((p, m))
            start = i
    for (a, ma), (b, mb) in zip(segments, segments[1:]):
        (up if mb > ma else down)[a, b] += 1
    return Transitions(up, down)


def roll_profile(p: SwaraProfile, k: int) -> SwaraProfile:
    """Re-reference to a Sa k semitones above the current one."""
    return SwaraProfile(np.roll(p.histogram, -k * (N_BINS // 12)), np.roll(p.strengths, -k))


def roll_transitions(t: Transitions, k: int) -> Transitions:
    r = lambda m: np.roll(np.roll(m, -k, axis=0), -k, axis=1)  # noqa: E731
    return Transitions(r(t.up), r(t.down))


SMOOTH_STEP_CENTS = 40.0   # frame-to-frame change still counted as a continuous glide
MIN_SMOOTH_RUN_S = 0.2
MIN_POSITION_S = 0.5


def melodic_positions(line, params: TheoryParams) -> int:
    """How many swara positions the melody spends >= 0.5 s on, in continuous glides.

    A real melody visits several swaras (even through gamakas); a tanpura drone or
    a mridangam (tuned to Sa) sits on one or two, and applause/noise has no
    continuous pitch at all.
    """
    c = line.cents
    v = ~np.isnan(c)
    if v.sum() < 2:
        return 0
    with np.errstate(invalid="ignore"):
        ok = v[1:] & v[:-1] & (np.abs(np.diff(c)) < SMOOTH_STEP_CENTS)
    min_run = max(1, int(round(MIN_SMOOTH_RUN_S / line.hop_s)))
    smooth = np.zeros(len(c), bool)
    padded = np.concatenate([[False], ok, [False]]).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    for a, b in zip(edges[::2], edges[1::2]):  # runs of ok pairs [a, b)
        if b - a >= min_run:
            smooth[a:b + 1] = True
    folded = np.mod(c[smooth], 1200.0)
    pos = np.round(folded / 100.0).astype(int) % 12
    seconds = np.bincount(pos, minlength=12) * line.hop_s
    return int((seconds >= MIN_POSITION_S).sum())
