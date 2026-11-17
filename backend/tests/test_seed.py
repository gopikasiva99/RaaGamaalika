import json
import zipfile

import numpy as np
import pytest

from fixtures.lines import make_line
from raaga.eval.seed import (import_saraga, list_saraga_tracks, parse_pitch_txt, pitch_to_line,
                             resolve_raga, window_line)
from raaga.store.local import LocalExampleStore

ROOT = "saraga1.5_carnatic/Concert X at Arkay by Artist A"


def _pitch_txt(line):
    hz = np.where(np.isnan(line.cents), 0.0, line.tonic_hz * 2 ** (np.nan_to_num(line.cents) / 1200))
    t = np.arange(len(hz)) * line.hop_s
    return "\n".join(f"{a:.18e}\t{b:.18e}" for a, b in zip(t, hz)).encode()


def _add_track(z, title, mbid, raaga, line, artist="Artist A"):
    d = f"{ROOT}/{title}"
    meta = {"mbid": mbid, "title": title, "raaga": raaga,
            "artists": [{"artist": {"name": artist}, "lead": True}],
            "album_artists": [{"name": artist}]}
    z.writestr(f"{d}/{title}.json", json.dumps(meta))
    z.writestr(f"__MACOSX/{d}/._{title}.json", b"junk")
    z.writestr(f"{d}/{artist} - {title}.pitch.txt", _pitch_txt(line))
    z.writestr(f"{d}/{artist} - {title}.pitch-vocal.txt", b"0\t0\n")
    z.writestr(f"{d}/{artist} - {title}.ctonic.txt", f"{line.tonic_hz}\n".encode())


@pytest.fixture
def saraga_zip(tmp_path):
    p = tmp_path / "s.zip"
    with zipfile.ZipFile(p, "w") as z:
        _add_track(z, "Song One", "11111111-aaaa", [{"name": "Mōhanaṁ"}], make_line([0, 2, 4, 7, 9], 150, seed=1))
        _add_track(z, "Song Two", "22222222-bbbb", [], make_line([0, 2, 4, 7, 9], 90, seed=2))
        _add_track(z, "Song Three", "33333333-cccc", [{"name": "Rāgamālika", "common_name": "ragamalika"}],
                   make_line([0, 2, 4, 7, 9], 90, seed=3))
        _add_track(z, "Song Four", "44444444-dddd", [{"name": "Unknownraga"}], make_line([0, 2, 4, 7, 9], 90))
    return zipfile.ZipFile(p)


def test_parse_pitch_and_line():
    hz, hop = parse_pitch_txt(b"0.0\t0.0\n0.0029024943\t146.8\n0.0058049886\t293.6\n")
    assert hop == pytest.approx(0.0029024943) and hz.tolist() == pytest.approx([0.0, 146.8, 293.6])
    line = pitch_to_line(hz, hop, 146.8)
    assert np.isnan(line.cents[0]) and line.cents[1:].tolist() == pytest.approx([0.0, 1200.0], abs=0.01)


def test_window_line():
    line = make_line([0, 7], 150)
    wins = window_line(line, 60, 60, 20)
    assert [s for s, _ in wins] == [0, 60]  # the 30 s tail is dropped
    assert all(abs(w.duration_s - 60) < 0.1 for _, w in wins)


def test_list_tracks_skips_macosx(saraga_zip):
    tracks = list_saraga_tracks(saraga_zip)
    assert sorted(t.title for t in tracks) == ["Song Four", "Song One", "Song Three", "Song Two"]
    one = next(t for t in tracks if t.title == "Song One")
    assert one.pitch_member.endswith(".pitch.txt") and "vocal" not in one.pitch_member
    assert one.artist == "Artist A" and one.raga_names == ["Mōhanaṁ"]


def test_resolve_raga(table):
    assert resolve_raga(["Mōhanaṁ"], table).name == "Mohanam"
    assert resolve_raga(["Kāmavardani/Pantuvarāḷi"], table).melakarta == 51
    assert resolve_raga(["Rāgamālika"], table) is None
    assert resolve_raga([], table) is None


def test_import(saraga_zip, table, tmp_path):
    store = LocalExampleStore(tmp_path / "store")
    rep = import_saraga(saraga_zip, store, table, window_s=60, hop_s=60, min_voiced_s=20)
    metas = store.list_examples()
    assert len(metas) == 2 and rep.n_examples == 2 and rep.n_tracks_used == 1
    assert {m.recording_group for m in metas} == {"saraga:11111111-aaaa"}
    assert all(m.source == "dataset" and m.kind == "concert" and m.artist == "Artist A" for m in metas)
    assert metas[0].raga_id == table.resolve("Mohanam").id
    assert rep.unmatched == {"Unknownraga": 1}
    assert rep.skipped_no_raga == 1 and rep.skipped_ragamalika == 1
    assert not list((tmp_path / "store").rglob("audio.*"))  # no dataset audio stored
