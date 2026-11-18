"""Western note names for shruti display and override (A4 = 440 Hz)."""
from __future__ import annotations

import math

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_C0 = 440.0 * 2 ** (-57 / 12)  # C0 frequency


def hz_to_note(hz: float) -> str:
    n = round(12 * math.log2(hz / _C0))
    return NOTE_NAMES[n % 12]


def note_to_hz_near(note: str, near_hz: float) -> float:
    key = note.strip().upper().replace("♯", "#")
    if key not in NOTE_NAMES:
        raise ValueError(f"unknown note {note!r}")
    base = _C0 * 2 ** (NOTE_NAMES.index(key) / 12)
    octave = round(math.log2(near_hz / base))
    return base * 2 ** octave
