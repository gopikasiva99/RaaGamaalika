from collections import Counter

import pytest

from fixtures.lines import make_line
from raaga.config import CombineParams, TheoryParams
from raaga.eval.metrics import calibrate, evaluate
from raaga.eval.split import group_split
from raaga.store.base import ExampleMeta
from raaga.store.local import LocalExampleStore

RAGAS = ["Mohanam", "Hindolam", "Hamsadhwani", "Mayamalavagowla", "Kalyani", "Kharaharapriya"]


@pytest.fixture(scope="module")
def synth_store(table, tmp_path_factory):
    st = LocalExampleStore(tmp_path_factory.mktemp("store"))
    i = 0
    for r_i, name in enumerate(RAGAS):
        raga = table.resolve(name)
        for g in range(10):
            for w in range(2):
                st.put_example(
                    ExampleMeta(id=f"x{i:04d}", raga_id=raga.id, kind="concert", artist=f"art{g % 4}",
                                recording_group=f"{raga.id}:rec{g}", tonic_hz=146.8, duration_s=30.0,
                                source="dataset"),
                    make_line(sorted(raga.allowed), 30, seed=1000 * r_i + 10 * g + w, noise_cents=12))
                i += 1
    return st


def test_split_stable_and_proportioned():
    assert group_split("saraga:abc") == group_split("saraga:abc")
    shares = Counter(group_split(f"g{i}") for i in range(5000))
    assert 0.17 < shares["test"] / 5000 < 0.23
    assert 0.07 < shares["val"] / 5000 < 0.13


def test_no_group_leaks_between_splits(synth_store):
    seen = {}
    for m in synth_store.list_examples():
        assert seen.setdefault(m.recording_group, group_split(m.recording_group)) == group_split(m.recording_group)


def test_evaluate_on_synthetic_store(synth_store, table):
    rep = evaluate(synth_store, table, (TheoryParams(), CombineParams()))
    assert rep.n_test_groups > 0
    assert rep.trained_top1 > 0.8
    assert rep.trained_top3 >= rep.trained_top1
    assert rep.noexample_top5 > 0.5
    assert rep.n_noexample > 0 and rep.n_trained > 0 and rep.n_fewshot >= 0
    assert 0.0 <= rep.confident_coverage <= 1.0
    assert set(rep.per_raga) <= {table.resolve(n).id for n in RAGAS}


def test_calibrate_meets_precision(synth_store, table):
    tp, cp, rep = calibrate(synth_store, table)
    assert rep.confident_precision >= 0.9
    assert 0.0 <= cp.knn_margin <= 0.30 and cp.w_theory in (0.3, 0.5, 0.7)
    assert cp.w_knn == pytest.approx(1 - cp.w_theory)


def _gamaka_store(table, root):
    """Mohanam/Hindolam windows with heavy passing-tone mass on non-scale swaras (like real gamakas)."""
    import numpy as np
    from raaga.melody.line import MelodyLine
    st = LocalExampleStore(root)
    for r_i, name in enumerate(["Mohanam", "Hindolam", "Kalyani"]):
        raga = table.resolve(name)
        outside = [p for p in range(12) if p not in raga.allowed][:2]
        for g in range(12):
            line = make_line(sorted(raga.allowed), 30, seed=100 * r_i + g, noise_cents=8)
            c = line.cents.copy()
            rng = np.random.default_rng(g)
            # ~12% of the time the melody glides through an outside swara (0.1 s passing tones)
            step = int(0.1 / line.hop_s)
            for start in range(0, len(c) - step, step):
                if rng.random() < 0.12:
                    c[start:start + step] = rng.choice(outside) * 100.0 + rng.normal(0, 3)
            st.put_example(ExampleMeta(id=f"y{r_i}{g:02d}", raga_id=raga.id, kind="concert", artist=f"a{g % 3}",
                                       recording_group=f"{raga.id}:{g}", tonic_hz=146.8, duration_s=30.0,
                                       source="dataset"), MelodyLine(line.tonic_hz, line.hop_s, c))
    return st


def test_tune_theory_beats_defaults_on_gamaka_audio(table, tmp_path):
    from raaga.eval.metrics import theory_rank_stats, tune_theory
    st = _gamaka_store(table, tmp_path)
    tuned = tune_theory(st, table)
    # top-5: identical-scale twins (e.g. Mohanam/Bhoopali) always tie, so top-1 is unreachable
    _, default_top5 = theory_rank_stats(st, table, TheoryParams())
    _, tuned_top5 = theory_rank_stats(st, table, tuned)
    assert tuned.presence_threshold > TheoryParams().presence_threshold
    assert tuned_top5 > default_top5


def test_calibrate_never_confident_without_enough_evidence(synth_store, table):
    _, cp, rep = calibrate(synth_store, table, min_confident=10_000)
    assert cp.confident_enabled is False and rep.confident_coverage == 0.0


def test_calibrate_allows_confidence_with_enough_evidence(synth_store, table):
    _, cp, _ = calibrate(synth_store, table, min_confident=3)
    assert cp.confident_enabled is True


def test_rank_stats_do_not_reward_ties(synth_store, table):
    """If nothing counts as heard, every raga ties: that must score as a miss, not a hit."""
    from dataclasses import replace
    from raaga.eval.metrics import theory_rank_stats
    all_tie = replace(TheoryParams(), presence_threshold=1.01, sa_missing_penalty=0.0, direction_weight=0.0)
    top1, top5 = theory_rank_stats(synth_store, table, all_tie)
    assert top1 == 0.0 and top5 == 0.0


def test_shruti_margin_calibrated_to_few_false_alarms(table, tmp_path):
    """I7: on windows whose tonic is correct, the check should rarely fire."""
    from raaga.eval.metrics import shruti_false_alarm_rate, tune_shruti_margin
    st = _gamaka_store(table, tmp_path)  # passing tones make wrong-Sa rotations look plausible
    theory = TheoryParams(shruti_margin=0.0)
    assert shruti_false_alarm_rate(st, table, theory) > 0.02  # uncalibrated: noisy
    tuned = tune_shruti_margin(st, table, theory)
    assert shruti_false_alarm_rate(st, table, tuned) <= 0.02
