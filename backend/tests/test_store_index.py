import numpy as np
import pytest

from fixtures.lines import make_line
from raaga.fingerprint.v0 import fingerprint_v0
from raaga.match.index import FingerprintIndex
from raaga.store.base import ExampleMeta
from raaga.store.local import LocalExampleStore

MOHANAM = [0, 2, 4, 7, 9]
HINDOLAM = [0, 3, 5, 8, 10]


def meta(i, raga, group=None):
    return ExampleMeta(id=f"ex{i:03d}", raga_id=raga, kind="concert", artist="A",
                       recording_group=group or f"g{i}", tonic_hz=146.8, duration_s=30.0,
                       source="dataset", note="", added_at="2026-11-17T00:00:00Z")


@pytest.fixture
def store(tmp_path):
    st = LocalExampleStore(tmp_path)
    st.put_example(meta(0, "mohanam"), make_line(MOHANAM, seed=100, noise_cents=3))
    for i in range(1, 51):
        st.put_example(meta(i, "hindolam"), make_line(HINDOLAM, seed=i, noise_cents=25))
    return st


def test_store_roundtrip(tmp_path):
    st = LocalExampleStore(tmp_path)
    line = make_line(MOHANAM, 5)
    st.put_example(meta(1, "mohanam"), line, audio=b"RIFFxx", audio_ext="wav")
    [m] = st.list_examples()
    assert m == meta(1, "mohanam")
    assert np.allclose(st.load_melody("ex001").cents, line.cents, equal_nan=True)
    assert (tmp_path / "examples/ex001/audio.wav").read_bytes() == b"RIFFxx"
    st.write_blob("models/v0/x.bin", b"abc")
    assert st.read_blob("models/v0/x.bin") == b"abc" and st.read_blob("nope") is None
    st.delete_example("ex001")
    assert st.list_examples() == []


def test_meta_json_roundtrip():
    m = meta(3, "mohanam")
    assert ExampleMeta.from_json(m.to_json()) == m


def test_index_one_exact_beats_many(store, tmp_path):
    idx = FingerprintIndex.build(store, "v0")
    assert len(idx) == 51 and idx.count("hindolam") == 50 and idx.count("nothing") == 0
    m = idx.match(fingerprint_v0(make_line(MOHANAM, seed=7, noise_cents=5)))
    assert max(m, key=m.get) == "mohanam"
    assert all(0.0 <= v <= 1.0 for v in m.values())
    assert idx.raga_ids_with_examples() == {"mohanam", "hindolam"}
    assert (tmp_path / "models/v0/fingerprints.npz").exists()


def test_index_rebuild_after_delete_and_add(store):
    FingerprintIndex.build(store, "v0")
    store.delete_example("ex000")
    idx = FingerprintIndex.build(store, "v0")
    assert len(idx) == 50 and idx.count("mohanam") == 0
    line = make_line(MOHANAM, seed=3)
    idx.add(meta(99, "mohanam"), fingerprint_v0(line))
    assert idx.count("mohanam") == 1
    idx.remove("ex099")
    assert idx.count("mohanam") == 0


def test_empty_index_matches_nothing(tmp_path):
    idx = FingerprintIndex.build(LocalExampleStore(tmp_path), "v0")
    assert len(idx) == 0 and idx.match(np.ones(1720, np.float32) / np.sqrt(1720)) == {}
