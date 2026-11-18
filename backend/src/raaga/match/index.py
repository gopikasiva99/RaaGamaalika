"""In-memory fingerprint index with per-raga nearest-neighbour scoring."""
from __future__ import annotations

import io

import numpy as np

from raaga.config import KNN_TOP_PER_RAGA
from raaga.fingerprint.v0 import FINGERPRINTS
from raaga.store.base import ExampleMeta, ExampleStore


class FingerprintIndex:
    def __init__(self, model_version: str, ids: list[str], raga_ids: list[str], matrix: np.ndarray):
        self.model_version = model_version
        self.ids = list(ids)
        self.raga_ids = list(raga_ids)
        self.matrix = np.asarray(matrix, dtype=np.float32).reshape(len(self.ids), -1) \
            if self.ids else np.zeros((0, 0), np.float32)
        self._regroup()

    def _regroup(self) -> None:
        groups: dict[str, list[int]] = {}
        for i, r in enumerate(self.raga_ids):
            groups.setdefault(r, []).append(i)
        self._groups = {r: np.array(ix) for r, ix in groups.items()}

    @classmethod
    def build(cls, store: ExampleStore, model_version: str, use_cache: bool = True) -> "FingerprintIndex":
        fp_fn = FINGERPRINTS[model_version]
        metas = store.list_examples()
        cache_path = f"models/{model_version}/fingerprints.npz"
        cached: dict[str, np.ndarray] = {}
        blob = store.read_blob(cache_path) if use_cache else None
        if blob:
            z = np.load(io.BytesIO(blob), allow_pickle=False)
            cached = {i: row for i, row in zip(z["ids"].tolist(), z["matrix"])}
        rows, changed = [], len(cached) != len(metas)
        for m in metas:
            row = cached.get(m.id)
            if row is None:
                row = fp_fn(store.load_melody(m.id))
                changed = True
            rows.append(row)
        matrix = np.stack(rows) if rows else np.zeros((0, 0), np.float32)
        idx = cls(model_version, [m.id for m in metas], [m.raga_id for m in metas], matrix)
        if use_cache and changed:
            buf = io.BytesIO()
            np.savez_compressed(buf, ids=np.array(idx.ids, dtype=str),
                                raga_ids=np.array(idx.raga_ids, dtype=str), matrix=idx.matrix)
            store.write_blob(cache_path, buf.getvalue())
        return idx

    def __len__(self) -> int:
        return len(self.ids)

    def count(self, raga_id: str) -> int:
        g = self._groups.get(raga_id)
        return 0 if g is None else len(g)

    def raga_ids_with_examples(self) -> set[str]:
        return set(self._groups)

    def add(self, meta: ExampleMeta, fp: np.ndarray) -> None:
        fp = np.asarray(fp, dtype=np.float32)[None, :]
        self.matrix = fp if not self.ids else np.vstack([self.matrix, fp])
        self.ids.append(meta.id)
        self.raga_ids.append(meta.raga_id)
        self._regroup()

    def remove(self, example_id: str) -> None:
        if example_id not in self.ids:
            return
        i = self.ids.index(example_id)
        self.matrix = np.delete(self.matrix, i, axis=0)
        del self.ids[i], self.raga_ids[i]
        self._regroup()

    def match(self, fp: np.ndarray, top_per_raga: int = KNN_TOP_PER_RAGA) -> dict[str, float]:
        if not self.ids:
            return {}
        sims = self.matrix @ np.asarray(fp, dtype=np.float32)
        out = {}
        for r, ix in self._groups.items():
            s = sims[ix]
            k = min(top_per_raga, len(s))
            top = np.partition(s, len(s) - k)[len(s) - k:]
            out[r] = float(np.clip(top.mean(), 0.0, 1.0))
        return out
