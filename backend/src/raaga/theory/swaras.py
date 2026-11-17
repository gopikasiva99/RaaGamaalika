"""Swara tokens and their positions (semitones above Sa)."""
from __future__ import annotations

from collections.abc import Iterable

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
