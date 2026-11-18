import numpy as np
import pytest

from raaga.config import TheoryParams
from raaga.theory.matcher import score_ragas, shruti_check
from raaga.theory.swaras import SwaraProfile, Transitions

NO_T = Transitions(np.zeros((12, 12)), np.zeros((12, 12)))
MOHANAM = {0, 2, 4, 7, 9}


def prof(pos, strength=1.0, strong=()):
    s = np.zeros(12)
    s[list(pos)] = strength
    s[list(strong)] = 1.0
    return SwaraProfile(np.zeros(120), s)


def test_mohanam_ranking(table):
    rid = lambda n: table.resolve(n).id  # noqa: E731
    sc = score_ragas(prof(MOHANAM), NO_T, table, TheoryParams())
    assert sc[rid("Mohanam")].score > sc[rid("Bilahari")].score > sc[rid("Hamsadhwani")].score \
        > sc[rid("Hindolam")].score
    assert sc[rid("Mohanam")].score == pytest.approx(1.0)
    assert sc[rid("Hamsadhwani")].extra == (9,)
    assert sc[rid("Bilahari")].missing == (5, 11)


def test_extra_swara_hurts_more_than_missing(table):
    rid = lambda n: table.resolve(n).id  # noqa: E731
    sc = score_ragas(prof({0, 2, 4, 6, 7, 9, 11}), NO_T, table, TheoryParams())  # M2 heard
    assert sc[rid("Mechakalyani")].score > sc[rid("Dheerasankarabharanam")].score


def test_missing_sa_is_heavily_penalized(table):
    sc = score_ragas(prof({2, 4, 7, 9}), NO_T, table, TheoryParams())
    assert sc[table.resolve("Mohanam").id].score < 0.01


def test_direction_penalizes_descent_only_swara_in_ascent(table):
    up = np.zeros((12, 12))
    up[9, 11] = 5  # D2 -> N3 going up; Bilahari's N3 is descent-only
    sc = score_ragas(prof({0, 2, 4, 5, 7, 9, 11}), Transitions(up, np.zeros((12, 12))), table, TheoryParams())
    assert sc[table.resolve("Bilahari").id].direction < 1.0
    assert sc[table.resolve("Dheerasankarabharanam").id].direction == pytest.approx(1.0)


def test_shruti_check_finds_shift(table):
    # True Sa and Pa are the most prominent swaras (drone, nyasa), as in real concerts.
    true = prof(MOHANAM, strength=0.6, strong=(0, 7))
    detected = SwaraProfile(true.histogram, np.roll(true.strengths, 7))  # detected Sa is 7 below
    s = shruti_check(detected, NO_T, table, TheoryParams(), 146.8)
    assert s is not None and s.shift_semitones == -5
    assert s.suggested_tonic_hz == pytest.approx(146.8 * 2 ** (-5 / 12), rel=1e-3)
    assert s.gain >= TheoryParams().shruti_margin


def test_shruti_check_silent_when_correct(table):
    assert shruti_check(prof(MOHANAM, 0.6, strong=(0, 7)), NO_T, table, TheoryParams(), 146.8) is None


def test_graha_bhedam_rotation_not_flagged(table):
    # Madhyamavati is Mohanam re-referenced; Sa is present and fits perfectly: no flag.
    assert shruti_check(prof({0, 2, 5, 7, 10}, 0.6, strong=(0, 7)), NO_T, table, TheoryParams(), 146.8) is None
