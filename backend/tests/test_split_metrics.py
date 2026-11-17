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
    assert 0.0 <= rep.confident_coverage <= 1.0
    assert set(rep.per_raga) <= {table.resolve(n).id for n in RAGAS}


def test_calibrate_meets_precision(synth_store, table):
    tp, cp, rep = calibrate(synth_store, table)
    assert rep.confident_precision >= 0.9
    assert 0.0 <= cp.knn_margin <= 0.30 and cp.w_theory in (0.3, 0.5, 0.7)
    assert cp.w_knn == pytest.approx(1 - cp.w_theory)
