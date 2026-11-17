"""Seed examples from the Saraga Carnatic dataset (CompMusic, CC BY-NC-SA).

Reads only what is needed from the dataset zip — per-track metadata, the
annotated tonic and the precomputed predominant pitch of the *mixture* — so the
14 GB archive never has to be downloaded (HttpRangeFile reads it remotely).
No dataset audio is stored.
"""
from __future__ import annotations

import io
import json
import posixpath
import urllib.request
import zipfile
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from raaga.melody.line import MelodyLine
from raaga.store.base import ExampleMeta, ExampleStore
from raaga.theory.ragas import Raga, RagaTable, normalize_name

SARAGA_URL = "https://zenodo.org/records/4301737/files/saraga1.5_carnatic.zip?download=1"
_RAGAMALIKA = normalize_name("ragamalika")


class HttpRangeFile(io.RawIOBase):
    """Read-only seekable view of a remote file using HTTP Range requests."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
            self.size = int(r.headers["Content-Length"])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, b) -> int:
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def open_remote_zip(url: str = SARAGA_URL) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BufferedReader(HttpRangeFile(url), buffer_size=1 << 20))


@dataclass
class SaragaTrack:
    mbid: str
    title: str
    raga_names: list[str]
    artist: str
    pitch_member: str
    tonic_member: str


@dataclass
class ImportReport:
    n_tracks_used: int = 0
    n_examples: int = 0
    skipped_no_raga: int = 0
    skipped_ragamalika: int = 0
    skipped_missing_files: int = 0
    unmatched: Counter = field(default_factory=Counter)


def parse_pitch_txt(data: bytes) -> tuple[np.ndarray, float]:
    arr = np.loadtxt(io.BytesIO(data), dtype=np.float64, ndmin=2)
    hop = float(np.median(np.diff(arr[:, 0]))) if len(arr) > 1 else 128 / 44100
    return arr[:, 1].astype(np.float32), hop


def pitch_to_line(hz: np.ndarray, hop_s: float, tonic_hz: float) -> MelodyLine:
    cents = np.full(hz.shape, np.nan, dtype=np.float32)
    v = hz > 0
    cents[v] = 1200.0 * np.log2(hz[v] / tonic_hz)
    return MelodyLine(float(tonic_hz), hop_s, cents)


def window_line(line: MelodyLine, window_s: float, hop_s: float,
                min_voiced_s: float) -> list[tuple[float, MelodyLine]]:
    out = []
    start = 0.0
    while start + window_s <= line.duration_s + 1e-6:
        w = line.slice(start, start + window_s)
        if w.voiced_seconds >= min_voiced_s:
            out.append((start, w))
        start += hop_s
    return out


def list_saraga_tracks(z: zipfile.ZipFile) -> list[SaragaTrack]:
    names = [n for n in z.namelist() if not n.startswith("__MACOSX/")]
    by_dir: dict[str, list[str]] = {}
    for n in names:
        by_dir.setdefault(posixpath.dirname(n), []).append(n)
    tracks = []
    for d, files in by_dir.items():
        meta = [f for f in files if f.endswith(".json")]
        pitch = [f for f in files if f.endswith(".pitch.txt")]
        tonic = [f for f in files if f.endswith(".ctonic.txt")]
        if not meta:
            continue
        m = json.loads(z.read(meta[0]))
        lead = [a for a in m.get("artists", []) if a.get("lead")]
        artist = (lead[0]["artist"]["name"] if lead
                  else (m.get("album_artists") or [{"name": "unknown"}])[0]["name"])
        raga_names = []
        for r in m.get("raaga") or []:
            raga_names.append(r.get("name") or r.get("common_name") or "")
        tracks.append(SaragaTrack(
            mbid=m.get("mbid") or posixpath.basename(d), title=m.get("title") or posixpath.basename(d),
            raga_names=[n for n in raga_names if n], artist=artist,
            pitch_member=pitch[0] if pitch else "", tonic_member=tonic[0] if tonic else ""))
    return sorted(tracks, key=lambda t: t.mbid)


def _is_ragamalika(names: list[str]) -> bool:
    return any(normalize_name(n) == _RAGAMALIKA for n in names)


def resolve_raga(names: list[str], table: RagaTable) -> Raga | None:
    if len(names) != 1 or _is_ragamalika(names):
        return None
    for candidate in [names[0], *names[0].split("/")]:
        r = table.resolve(candidate.strip())
        if r is not None:
            return r
    return None


def import_saraga(z: zipfile.ZipFile, store: ExampleStore, table: RagaTable, *, window_s: float = 60.0,
                  hop_s: float = 60.0, min_voiced_s: float = 20.0, limit: int | None = None,
                  log=lambda msg: None) -> ImportReport:
    rep = ImportReport()
    tracks = list_saraga_tracks(z)
    for i, t in enumerate(tracks[:limit] if limit else tracks):
        if not t.raga_names:
            rep.skipped_no_raga += 1
            continue
        if _is_ragamalika(t.raga_names) or len(t.raga_names) > 1:
            rep.skipped_ragamalika += 1
            continue
        raga = resolve_raga(t.raga_names, table)
        if raga is None:
            rep.unmatched[t.raga_names[0]] += 1
            continue
        if not t.pitch_member or not t.tonic_member:
            rep.skipped_missing_files += 1
            continue
        tonic = float(z.read(t.tonic_member).decode().split()[0])
        hz, hop = parse_pitch_txt(z.read(t.pitch_member))
        line = pitch_to_line(hz, hop, tonic)
        added = 0
        for k, (start, w) in enumerate(window_line(line, window_s, hop_s, min_voiced_s)):
            store.put_example(ExampleMeta(
                id=f"saraga-{t.mbid[:8]}-{k:03d}", raga_id=raga.id, kind="concert", artist=t.artist,
                recording_group=f"saraga:{t.mbid}", tonic_hz=tonic, duration_s=w.duration_s,
                source="dataset", note=f"{t.title} @ {start:.0f}s"), w)
            added += 1
        if added:
            rep.n_tracks_used += 1
            rep.n_examples += added
        log(f"[{i + 1}/{len(tracks)}] {t.title} — {raga.name}: {added} windows")
    return rep
