import numpy as np
import pytest

from conftest import DATA
from fixtures.synth import synth_clip
from raaga.config import CombineParams, TheoryParams
from raaga.engine import EngineContext, analyze
from raaga.fingerprint.v0 import fingerprint_v0
from raaga.match.index import FingerprintIndex
from raaga.melody.extract import melody_line_from_audio
from raaga.store.base import ExampleMeta
from raaga.store.local import LocalExampleStore
from raaga.theory.ragas import Raga, RagaTable

DATA_TABLE = DATA / "ragas.json"
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
    return EngineContext(table, TheoryParams(), CombineParams(confident_enabled=True),
                         FingerprintIndex.build(st, "v0"), fingerprint_v0)


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


def test_wrong_detected_shruti_is_flagged(ctx_examples, mohanam_clip):
    # Simulate a detection error: re-reference the melody to F (not one of the clip's swaras
    # relative to the true Sa D), so Sa goes missing. (Pa-as-Sa would be graha bhedam.)
    from raaga.engine import analyze_line
    line = melody_line_from_audio(mohanam_clip, tonic_hz=146.83).with_tonic(174.61)
    r = analyze_line(line, ctx_examples)
    assert r.kind == "shortlist" and r.shruti_suspect is not None
    # Synthetic clips give every swara equal weight, so any of the clip's own swaras is a
    # valid Sa (graha bhedam); Sa-vs-Pa prominence tie-breaking is unit-tested in test_matcher.
    assert r.shruti_suspect.suggested_note in {"D", "E", "F#", "A", "B"}


def test_user_chosen_shruti_is_not_second_guessed(ctx_examples, mohanam_clip):
    """I7: after the user picks the shruti, don't nag with 'Check the shruti?' again."""
    r = analyze(mohanam_clip, ctx_examples, shruti="F")
    assert r.shruti_suspect is None and r.tonic_note == "F"


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


def test_raga_without_examples_can_win_on_theory(table):
    """No examples = neutral (median) example evidence, not zero: swaras decide."""
    from raaga.engine import Evidence, decide
    from raaga.theory.matcher import TheoryScore
    mo, ha, hi, ka = (table.resolve(n).id for n in ("Mohanam", "Hamsadhwani", "Hindolam", "Kalyani"))
    theory = {r: TheoryScore(r, 0.0, (), (), 1.0) for r in table.ragas}
    theory[mo] = TheoryScore(mo, 1.0, (), (), 1.0)    # perfect fit, but no examples
    theory[ha] = TheoryScore(ha, 0.4, (9,), (), 1.0)  # has examples, poor fit
    knn = {ha: 0.86, hi: 0.80, ka: 0.82}               # real-audio similarities are all high
    ev = Evidence(strengths=[0.0] * 12, theory=theory, knn=knn, suspect=None)
    kind, chosen, _ = decide(ev, table, CombineParams(w_theory=0.3, w_knn=0.7, knn_margin=1.0))
    assert kind == "shortlist" and chosen[0] == mo


def test_store_without_params_never_claims_confidence(table, tmp_path, mohanam_clip):
    """C1: a seeded store with no calibration must fail closed (shortlists only)."""
    from raaga.engine import EngineContext
    st = LocalExampleStore(tmp_path)
    mo = table.resolve("Mohanam").id
    for i, tonic in enumerate((146.8, 174.6, 130.8)):
        st.put_example(_meta(i, mo), melody_line_from_audio(synth_clip(MOHANAM, tonic, 20, seed=50 + i), tonic_hz=tonic))
    ctx = EngineContext.load(st, DATA_TABLE, None)
    assert ctx.combine.confident_enabled is False
    assert analyze(mohanam_clip, ctx).kind == "shortlist"


def test_params_are_loaded_from_the_store(table, tmp_path):
    """C1: calibration written to <store>/models/v0/params.json is used without RAAGA_PARAMS."""
    import json
    from raaga.engine import EngineContext
    st = LocalExampleStore(tmp_path)
    st.write_blob("models/v0/params.json", json.dumps(
        {"theory": {"presence_threshold": 0.33}, "combine": {"knn_margin": 0.07, "confident_enabled": True}}).encode())
    ctx = EngineContext.load(st, DATA_TABLE, None)
    assert ctx.theory.presence_threshold == 0.33
    assert ctx.combine.knn_margin == 0.07 and ctx.combine.confident_enabled is True


def test_confidence_switch_off_blocks_confident(ctx_examples, mohanam_clip):
    from dataclasses import replace
    from raaga.engine import EngineContext
    off = EngineContext(ctx_examples.table, ctx_examples.theory, replace(ctx_examples.combine, confident_enabled=False),
                        ctx_examples.index, ctx_examples.fingerprint)
    assert analyze(mohanam_clip, off).kind == "shortlist"



@pytest.mark.parametrize("kind", ["drone", "mridangam", "applause"])
def test_no_melody_for_drone_percussion_applause(ctx_empty, kind):
    """I1: tanpura-only, tani avartanam and applause must say 'keep listening', not guess."""
    from fixtures.synth import synth_applause, synth_mridangam
    audio = {"drone": lambda: synth_clip(MOHANAM, 146.8, 40, melody=False),
             "mridangam": lambda: synth_mridangam(146.8, 40),
             "applause": lambda: synth_applause(40)}[kind]()
    r = analyze(audio, ctx_empty)
    assert r.kind == "no_melody" and r.candidates == []
