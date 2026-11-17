import numpy as np

from fixtures.synth import synth_clip
from raaga.fingerprint.v0 import FINGERPRINTS, fingerprint_v0
from raaga.melody.extract import melody_line_from_audio
from raaga.melody.line import MelodyLine


def test_fp_shape_norm_and_tonic_invariance():
    l1 = melody_line_from_audio(synth_clip(["S", "R2", "G3", "P", "D2"], 146.8, 30, drone=False), tonic_hz=146.8)
    l2 = melody_line_from_audio(synth_clip(["S", "R2", "G3", "P", "D2"], 174.6, 30, drone=False, seed=1),
                                tonic_hz=174.6)
    a, b = fingerprint_v0(l1), fingerprint_v0(l2)
    assert a.shape == (1720,) and a.dtype == np.float32
    assert np.isclose(np.linalg.norm(a), 1, atol=1e-5)
    assert a @ b > 0.9


def test_different_ragas_less_similar():
    a = fingerprint_v0(melody_line_from_audio(
        synth_clip(["S", "R2", "G3", "P", "D2"], 146.8, 30, drone=False), tonic_hz=146.8))
    b = fingerprint_v0(melody_line_from_audio(
        synth_clip(["S", "G2", "M1", "D1", "N2"], 146.8, 30, drone=False), tonic_hz=146.8))
    assert a @ b < 0.6


def test_silent_line_gives_zero_vector():
    fp = fingerprint_v0(MelodyLine(146.8, 0.01, np.full(50, np.nan, dtype=np.float32)))
    assert fp.shape == (1720,) and not fp.any()


def test_registry():
    assert FINGERPRINTS["v0"] is fingerprint_v0
