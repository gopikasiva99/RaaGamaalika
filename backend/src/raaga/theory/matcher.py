"""Theory matcher: score every raga in the table from swaras heard and direction."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from raaga.config import TheoryParams
from raaga.theory.ragas import RagaTable
from raaga.theory.swaras import SwaraProfile, Transitions, roll_profile, roll_transitions

TIE_EPS = 0.05  # alternatives within this of the best are tie-broken by Sa/Pa prominence


@dataclass
class TheoryScore:
    raga_id: str
    score: float
    extra: tuple[int, ...]
    missing: tuple[int, ...]
    direction: float


@dataclass
class ShrutiSuggestion:
    shift_semitones: int  # true Sa is this many semitones above the detected Sa (-5..6)
    suggested_tonic_hz: float
    gain: float


@dataclass
class _Masks:
    ids: list[str]
    allowed: np.ndarray  # (n, 12) bool
    aro: np.ndarray
    avaro: np.ndarray
    n_non_sa: np.ndarray  # (n,) allowed swaras excluding Sa


def _masks(table: RagaTable) -> _Masks:
    cached = getattr(table, "_theory_masks", None)
    if cached is not None:
        return cached
    ids = list(table.ragas)
    n = len(ids)
    allowed, aro, avaro = (np.zeros((n, 12), bool) for _ in range(3))
    for i, rid in enumerate(ids):
        r = table.ragas[rid]
        allowed[i, list(r.allowed)] = True
        aro[i, list(r.aro_positions)] = True
        avaro[i, list(r.avaro_positions)] = True
    m = _Masks(ids, allowed, aro, avaro, np.maximum(1, allowed.sum(1) - 1))
    table._theory_masks = m  # type: ignore[attr-defined]
    return m


def _score_arrays(s: np.ndarray, up: np.ndarray, down: np.ndarray, m: _Masks, p: TheoryParams):
    heard = s >= p.presence_threshold
    extra = heard[None, :] & ~m.allowed
    missing = m.allowed & ~heard[None, :]
    missing[:, 0] = False
    penalty = (p.extra_penalty * (extra * s[None, :]).sum(1)
               + p.missing_penalty * missing.sum(1) / m.n_non_sa)
    if not heard[0]:
        penalty = penalty + p.sa_missing_penalty
    set_score = np.exp(-penalty)
    up_to, down_to = up.sum(0), down.sum(0)
    tot_up, tot_down = up_to.sum(), down_to.sum()
    viol_up = (~m.aro * up_to[None, :]).sum(1) / tot_up if tot_up > 0 else np.zeros(len(m.ids))
    viol_down = (~m.avaro * down_to[None, :]).sum(1) / tot_down if tot_down > 0 else np.zeros(len(m.ids))
    direction = 1.0 - 0.5 * (viol_up + viol_down)
    score = set_score * (1.0 - p.direction_weight + p.direction_weight * direction)
    return score, extra, missing, direction


def score_ragas(profile: SwaraProfile, trans: Transitions, table: RagaTable,
                params: TheoryParams) -> dict[str, TheoryScore]:
    m = _masks(table)
    score, extra, missing, direction = _score_arrays(profile.strengths, trans.up, trans.down, m, params)
    return {
        rid: TheoryScore(rid, float(score[i]), tuple(int(j) for j in np.flatnonzero(extra[i])),
                         tuple(int(j) for j in np.flatnonzero(missing[i])), float(direction[i]))
        for i, rid in enumerate(m.ids)
    }


def shruti_check(profile: SwaraProfile, trans: Transitions, table: RagaTable,
                 params: TheoryParams, tonic_hz: float) -> ShrutiSuggestion | None:
    """Suggest a different Sa if the swaras fit the raga table far better there.

    Rotations that keep Sa present (graha bhedam, e.g. Mohanam vs Madhyamavati)
    fit equally well and are not flagged: swaras alone cannot decide them.
    """
    m = _masks(table)
    base = float(_score_arrays(profile.strengths, trans.up, trans.down, m, params)[0].max())
    alts = []
    for k in range(1, 12):
        p, t = roll_profile(profile, k), roll_transitions(trans, k)
        best = float(_score_arrays(p.strengths, t.up, t.down, m, params)[0].max())
        shift = k - 12 if k > 6 else k
        alts.append((best, float(p.strengths[0] + p.strengths[7]), -abs(shift), shift))
    top = max(a[0] for a in alts)
    near = [a for a in alts if a[0] >= top - TIE_EPS]
    best, _sa_pa, _closeness, shift = max(near, key=lambda a: (a[1], a[2]))
    gain = best - base
    if gain < params.shruti_margin:
        return None
    return ShrutiSuggestion(shift, float(tonic_hz * 2 ** (shift / 12)), gain)
