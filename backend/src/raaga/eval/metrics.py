"""Evaluation (spec §7 metrics) and v0 calibration of CombineParams."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from raaga.config import MIN_VOICED_S, CombineParams, TheoryParams
from raaga.engine import EngineContext, Evidence, decide, gather_evidence
from raaga.eval.split import group_split
from raaga.fingerprint.v0 import FINGERPRINTS
from raaga.match.index import FingerprintIndex
from raaga.store.base import ExampleMeta, ExampleStore
from raaga.theory.ragas import RagaTable

MIN_PRECISION = 0.90
MARGINS = [round(0.01 * i, 2) for i in range(31)]
W_THEORY = [0.3, 0.5, 0.7]


@dataclass
class EvalReport:
    trained_top1: float = 0.0
    trained_top3: float = 0.0
    fewshot_top3: float = 0.0
    noexample_top5: float = 0.0
    confident_precision: float = 1.0
    confident_coverage: float = 0.0
    per_raga: dict[str, dict] = field(default_factory=dict)
    n_test_groups: int = 0

    def format(self) -> str:
        lines = [
            f"test recording groups : {self.n_test_groups}",
            f"trained top-1         : {self.trained_top1:.1%}",
            f"trained top-3         : {self.trained_top3:.1%}",
            f"few-shot top-3        : {self.fewshot_top3:.1%}",
            f"no-example top-5      : {self.noexample_top5:.1%}",
            f"confident precision   : {self.confident_precision:.1%}",
            f"confident coverage    : {self.confident_coverage:.1%}",
        ]
        return "\n".join(lines)


class _Data:
    """Melody lines and fingerprints loaded once per evaluation."""

    def __init__(self, store: ExampleStore, model_version: str):
        fp = FINGERPRINTS[model_version]
        self.metas: list[ExampleMeta] = store.list_examples()
        self.lines = {m.id: store.load_melody(m.id) for m in self.metas}
        self.fps = {m.id: fp(self.lines[m.id]) for m in self.metas}
        self.split = {m.id: group_split(m.recording_group) for m in self.metas}
        self.by_obj = {id(line): mid for mid, line in self.lines.items()}
        self.model_version = model_version

    def index(self, metas: list[ExampleMeta]) -> FingerprintIndex:
        if not metas:
            return FingerprintIndex(self.model_version, [], [], np.zeros((0, 0), np.float32))
        return FingerprintIndex(self.model_version, [m.id for m in metas], [m.raga_id for m in metas],
                                np.stack([self.fps[m.id] for m in metas]))


def _ctx(table, theory, combine, index, data) -> EngineContext:
    return EngineContext(table, theory, combine, index, lambda line: data.fps[data.by_obj[id(line)]])


def _evidence(data, table, theory, combine, index, metas) -> list[tuple[ExampleMeta, Evidence]]:
    ctx = _ctx(table, theory, combine, index, data)
    out = []
    for m in metas:
        line = data.lines[m.id]
        if line.voiced_seconds >= MIN_VOICED_S:
            out.append((m, gather_evidence(line, ctx)))
    return out


def _trained_scores(evs, table, cp) -> tuple[float, float, float, float, dict]:
    if not evs:
        return 0.0, 0.0, 1.0, 0.0, {}
    top1 = top3 = conf = conf_ok = 0
    per: dict[str, dict] = {}
    for m, ev in evs:
        kind, chosen, _ = decide(ev, table, cp)
        hit1, hit3 = chosen[:1] == [m.raga_id], m.raga_id in chosen[:3]
        top1 += hit1
        top3 += hit3
        if kind == "confident":
            conf += 1
            conf_ok += hit1
        d = per.setdefault(m.raga_id, {"n_test": 0, "top1": 0})
        d["n_test"] += 1
        d["top1"] += int(hit1)
    n = len(evs)
    return top1 / n, top3 / n, (conf_ok / conf if conf else 1.0), conf / n, per


def evaluate(store: ExampleStore, table: RagaTable, params: tuple[TheoryParams, CombineParams], *,
             split: str = "test", fewshot_k: int = 3, _data: _Data | None = None) -> EvalReport:
    theory, cp = params
    data = _data or _Data(store, cp.model_version)
    train = [m for m in data.metas if data.split[m.id] == "train"]
    target = [m for m in data.metas if data.split[m.id] == split]
    trained_ragas = {m.raga_id for m in train}
    rep = EvalReport(n_test_groups=len({m.recording_group for m in target}))

    evs = _evidence(data, table, theory, cp, data.index(train), [m for m in target if m.raga_id in trained_ragas])
    (rep.trained_top1, rep.trained_top3, rep.confident_precision,
     rep.confident_coverage, rep.per_raga) = _trained_scores(evs, table, cp)

    few_hits = few_n = none_hits = none_n = 0
    for raga in sorted({m.raga_id for m in target}):
        r_target = [m for m in target if m.raga_id == raga]
        others = [m for m in train if m.raga_id != raga]
        groups = sorted({m.recording_group for m in train if m.raga_id == raga})
        if len(groups) >= fewshot_k + 1:
            keep = set(groups[:fewshot_k])
            few_index = data.index(others + [m for m in train if m.raga_id == raga and m.recording_group in keep])
            for m, ev in _evidence(data, table, theory, cp, few_index, r_target):
                few_n += 1
                few_hits += raga in decide(ev, table, cp)[1][:3]
        for m, ev in _evidence(data, table, theory, cp, data.index(others), r_target):
            none_n += 1
            none_hits += raga in decide(ev, table, cp)[1][:5]
    rep.fewshot_top3 = few_hits / few_n if few_n else 0.0
    rep.noexample_top5 = none_hits / none_n if none_n else 0.0
    return rep


def calibrate(store: ExampleStore, table: RagaTable,
              theory: TheoryParams | None = None) -> tuple[TheoryParams, CombineParams, EvalReport]:
    """Pick knn_margin and w_theory on the val split; report on test."""
    theory = theory or TheoryParams()
    base = CombineParams()
    data = _Data(store, base.model_version)
    train = [m for m in data.metas if data.split[m.id] == "train"]
    trained_ragas = {m.raga_id for m in train}
    val = [m for m in data.metas if data.split[m.id] == "val" and m.raga_id in trained_ragas]
    evs = _evidence(data, table, theory, base, data.index(train), val)
    best_key, best_cp = None, base
    for w in W_THEORY:
        for margin in MARGINS:
            cp = replace(base, w_theory=w, w_knn=round(1 - w, 2), knn_margin=margin)
            top1, _t3, precision, coverage, _ = _trained_scores(evs, table, cp)
            if precision < MIN_PRECISION:
                continue
            key = (top1, coverage, -margin)
            if best_key is None or key > best_key:
                best_key, best_cp = key, cp
    if best_key is None:  # nothing reached the precision target: never claim confidence
        best_cp = replace(base, knn_margin=1.0)
    return theory, best_cp, evaluate(store, table, (theory, best_cp), _data=data)
