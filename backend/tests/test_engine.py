import numpy as np
import pytest

from fixtures.synth import synth_clip
from raaga.config import CombineParams, TheoryParams
from raaga.engine import EngineContext, analyze
from raaga.fingerprint.v0 import fingerprint_v0
from raaga.match.index import FingerprintIndex
from raaga.melody.extract import melody_line_from_audio
from raaga.store.base import ExampleMeta
from raaga.store.local import LocalExampleStore
from raaga.theory.ragas import Raga, RagaTable

MOHANAM = ["S", "R2", "G3", "P", "D2"]
HINDOLAM = ["S", "G2", "M1", "D1", "N2"]


def _meta(i, raga):
    return ExampleMeta(id=f"e{i}", raga_id=raga, kind="concert", artist=f"A{i}", recording_group=f"g{i}",
                       tonic_hz=146.8, duration_s=20.0, source="dataset")


def _ctx(table, store_dir, examples):
    st = LocalExampleStore(store_dir)
    for i, (swaras, raga_id, tonic) in enumerate(examples):
        st.put_example(_meta(i, raga_id),
                       melody_line_from_audio(synth_clip(swaras, tonic, 20, seed=50 + i), tonic_hz=tonic))
    return EngineContext(table, TheoryParams(), CombineParams(), FingerprintIndex.build(st, "v0"), fingerprint_v0)


@pytest.fixture(scope="module")
def mohanam_clip():
    return synth_clip(MOHANAM, 146.8, 40, seed=7)


@pytest.fixture(scope="module")
def ctx_empty(table, tmp_path_factory):
    return _ctx(table, tmp_path_factory.mktemp("empty"), [])


@pytest.fixture(scope="module")
def ctx_examples(table, tmp_path_factory):
    mo, hi = table.resolve("Mohanam").id, table.resolve("Hindolam").id
    return _ctx(table, tmp_path_factory.mktemp("ex"),
                [(MOHANAM, mo, 146.8), (MOHANAM, mo, 174.6), (MOHANAM, mo, 130.8),
                 (HINDOLAM, hi, 146.8), (HINDOLAM, hi, 174.6), (HINDOLAM, hi, 130.8)])


@pytest.fixture(scope="module")
def ctx_mislabelled(table, tmp_path_factory):
    ha = table.resolve("Hamsadhwani").id
    return _ctx(table, tmp_path_factory.mktemp("mis"),
                [(MOHANAM, ha, 146.8), (MOHANAM, ha, 174.6), (HINDOLAM, table.resolve("Hindolam").id, 146.8)])


def test_no_melody_on_silence(ctx_empty):
    r = analyze(np.zeros(44100 * 20, np.float32), ctx_empty)
    assert r.kind == "no_melody" and r.candidates == []


def test_empty_store_theory_only_shortlist(ctx_empty, mohanam_clip, table):  # Review Focus 5
    r = analyze(mohanam_clip, ctx_empty)
    assert r.kind == "shortlist" and 1 <= len(r.candidates) <= 5
    mohanam = table.resolve("Mohanam")
    assert mohanam.id in [c.raga_id for c in r.candidates]
    assert table.get(r.candidates[0].raga_id).allowed == mohanam.allowed
    assert r.model_version == "v0" and len(r.swara_strengths) == 12


def test_confident_with_matching_examples(ctx_examples, mohanam_clip):
    r = analyze(mohanam_clip, ctx_examples)
    assert r.kind == "confident"
    assert r.candidates[0].name == "Mohanam"
    assert sum(c.percent for c in r.candidates) in (99, 100, 101)


def test_theory_veto_blocks_confidence(ctx_mislabelled, mohanam_clip):
    r = analyze(mohanam_clip, ctx_mislabelled)
    assert r.kind == "shortlist"


def test_shruti_override_used(ctx_empty, mohanam_clip):
    r = analyze(mohanam_clip, ctx_empty, shruti="D")
    assert r.tonic_note == "D"
    assert abs(r.tonic_hz - 146.83) < 0.5


def test_bad_shruti_raises(ctx_empty, mohanam_clip):
    with pytest.raises(ValueError):
        analyze(mohanam_clip, ctx_empty, shruti="H#")


def test_wrong_shruti_is_flagged(ctx_examples, mohanam_clip):
    # F is not one of the clip's swaras relative to the true Sa (D), so Sa goes missing.
    # (Giving Pa as Sa would turn Mohanam into another valid raga - graha bhedam - not flaggable.)
    r = analyze(mohanam_clip, ctx_examples, shruti="F")
    assert r.kind == "shortlist" and r.shruti_suspect is not None
    # The synthetic clip gives every swara equal weight, so any of its own swaras is a
    # valid Sa (graha bhedam); Sa-vs-Pa prominence tie-breaking is unit-tested in test_matcher.
    assert r.shruti_suspect.suggested_note in {"D", "E", "F#", "A", "B"}


def test_groups_marked_for_identical_scales(tmp_path, mohanam_clip):
    def raga(name):
        return Raga(id=name.lower(), name=name, aliases=(), melakarta=None, parent=28,
                    arohana=("S", "R2", "G3", "P", "D2", "S"), avarohana=("S", "D2", "P", "G3", "R2", "S"),
                    vakra=False, bhashanga=False)
    tiny = RagaTable([raga("Mohanam"), raga("Twin")])
    r = analyze(mohanam_clip, _ctx(tiny, tmp_path, []))
    assert r.candidates[0].group is not None and r.candidates[0].group == r.candidates[1].group


def test_result_json_shape(ctx_empty, mohanam_clip):
    j = analyze(mohanam_clip, ctx_empty).to_json()
    assert set(j) == {"kind", "candidates", "tonic_hz", "tonic_note", "shruti_suspect", "swara_strengths",
                      "voiced_seconds", "model_version", "processing_ms"}
    assert set(j["candidates"][0]) == {"raga_id", "name", "melakarta", "parent", "arohana", "avarohana",
                                       "score", "percent", "group"}
