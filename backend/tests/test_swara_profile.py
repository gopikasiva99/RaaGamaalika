import numpy as np
import pytest

from fixtures.synth import synth_clip
from raaga.config import TheoryParams
from raaga.melody.extract import melody_line_from_audio
from raaga.theory.swaras import roll_profile, roll_transitions, swara_profile, transitions

MOHANAM = ["S", "R2", "G3", "P", "D2"]


@pytest.fixture(scope="module")
def mohanam_line():
    return melody_line_from_audio(synth_clip(MOHANAM, 146.8, 40, drone=False), tonic_hz=146.8)


def test_mohanam_profile(mohanam_line):
    p = swara_profile(mohanam_line, TheoryParams())
    assert set(np.where(p.strengths >= 0.15)[0]) == {0, 2, 4, 7, 9}
    assert p.strengths.max() == pytest.approx(1.0)
    assert p.histogram.shape == (120,) and p.histogram.sum() == pytest.approx(1.0)


def test_octave_error_gives_same_profile(mohanam_line):  # Review Focus 2
    a = swara_profile(mohanam_line, TheoryParams()).strengths
    b = swara_profile(mohanam_line.with_tonic(mohanam_line.tonic_hz * 2), TheoryParams()).strengths
    assert np.allclose(a, b, atol=1e-6)


def test_direction_detected(mohanam_line):
    t = transitions(mohanam_line, TheoryParams())
    assert t.up[4, 7] > 0 and t.down[7, 4] > 0 and t.up[7, 4] == 0


def test_roll_profile(mohanam_line):
    p = swara_profile(mohanam_line, TheoryParams())
    assert set(np.where(roll_profile(p, 7).strengths >= 0.15)[0]) == {0, 2, 5, 7, 9}


def test_roll_transitions(mohanam_line):
    t = transitions(mohanam_line, TheoryParams())
    r = roll_transitions(t, 7)
    assert r.up[(4 - 7) % 12, 0] == t.up[4, 7]


def test_silence_profile_is_zero():
    from raaga.melody.line import MelodyLine
    line = MelodyLine(146.8, 0.01, np.full(100, np.nan, dtype=np.float32))
    p = swara_profile(line, TheoryParams())
    assert not p.strengths.any()
    assert not transitions(line, TheoryParams()).up.any()
