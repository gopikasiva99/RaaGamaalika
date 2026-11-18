import numpy as np
import pytest

from fixtures.synth import synth_clip
from raaga.config import MIN_VOICED_S
from raaga.melody.extract import detect_tonic, extract_pitch, melody_line_from_audio
from raaga.melody.line import MelodyLine


def test_tonic_detected_within_50_cents():
    a = synth_clip(["S", "R2", "G3", "P", "D2"], 146.8, 30)
    assert abs(1200 * np.log2(detect_tonic(a) / 146.8)) < 50


def test_extract_pitch_shape():
    hz, hop = extract_pitch(synth_clip(["S", "P"], 146.8, 5, drone=False))
    assert hop == pytest.approx(128 / 44100)
    assert hz.ndim == 1 and abs(len(hz) * hop - 5) < 0.1


def test_melody_tracks_synth_notes():
    line = melody_line_from_audio(synth_clip(["S", "G3", "P"], 146.8, 20), tonic_hz=146.8)
    f = line.folded()
    targets = np.array([0, 400, 700, 1200])
    near = np.min(np.abs(f[:, None] - targets[None]), axis=1)
    assert np.mean(near < 30) > 0.85


def test_leading_silence_still_counts_voiced_seconds():  # Review Focus 1
    a = synth_clip(["S", "R2", "G3", "P", "D2"], 146.8, 60, leading_silence_s=30)
    assert melody_line_from_audio(a, tonic_hz=146.8).voiced_seconds >= MIN_VOICED_S


def test_npz_roundtrip_and_with_tonic():
    line = MelodyLine(146.8, 0.0029, np.array([0, 700, np.nan], dtype=np.float32))
    back = MelodyLine.from_npz_bytes(line.to_npz_bytes())
    assert np.allclose(back.cents, line.cents, equal_nan=True) and back.tonic_hz == 146.8
    assert np.allclose(line.with_tonic(146.8 * 2 ** (7 / 12)).cents[:2], [-700, 0], atol=0.01)


def test_folded_and_slice():
    line = MelodyLine(100.0, 0.5, np.array([1300, np.nan, -100, 50], dtype=np.float32))
    assert np.allclose(line.folded(), [100, 1100, 50])
    assert line.voiced_seconds == pytest.approx(1.5)
    assert np.allclose(line.slice(1.0, 2.0).cents, [-100, 50])
