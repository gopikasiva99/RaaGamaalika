"""Evaluation (spec §7 metrics) and v0 calibration of CombineParams."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace

import numpy as np

from raaga.config import CombineParams, TheoryParams
from raaga.engine import EngineContext, Evidence, decide, gather_evidence, has_melody
from raaga.eval.split import group_split
from raaga.fingerprint.v0 import FINGERPRINTS
from raaga.match.index import FingerprintIndex
from raaga.store.base import ExampleMeta, ExampleStore
from raaga.theory.matcher import _masks, _score_arrays, shruti_check
from raaga.theory.ragas import RagaTable
from raaga.theory.swaras import swara_profile, transitions

MIN_PRECISION = 0.90
MIN_CONFIDENT_SAMPLES = 20  # a precision measured on fewer confident answers is noise
MARGINS = [round(0.01 * i, 2) for i in range(31)]
W_THEORY = [0.3, 0.5, 0.7]
SHRUTI_MARGINS = [round(0.05 * i, 2) for i in range(1, 21)] + [1.01]  # 1.01 = never fires
MAX_SHRUTI_FALSE_ALARMS = 0.02
THEORY_GRID = {
    "presence_threshold": [0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75],
    "extra_penalty": [1.0, 4.0],
    "missing_penalty": [0.5, 1.0],
    "direction_weight": [0.0, 0.3],
}


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
    n_trained: int = 0
    n_fewshot: int = 0
    n_noexample: int = 0

    def format(self) -> str:
        lines = [
            f"test recording groups : {self.n_test_groups}",
            f"trained top-1         : {self.trained_top1:.1%}  (n={self.n_trained} windows)",
            f"trained top-3         : {self.trained_top3:.1%}",
            f"few-shot top-3        : {f'{self.fewshot_top3:.1%}' if self.n_fewshot else 'n/a'}  (n={self.n_fewshot})",
            f"no-example top-5      : {self.noexample_top5:.1%}  (n={self.n_noexample})",
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
        if has_melody(line, theory):
            out.append((m, gather_evidence(line, ctx)))
    return out


def _trained_scores(evs, table, cp) -> tuple[float, float, float, float, dict, int]:
    if not evs:
        return 0.0, 0.0, 1.0, 0.0, {}, 0
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
    return top1 / n, top3 / n, (conf_ok / conf if conf else 1.0), conf / n, per, conf


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
     rep.confident_coverage, rep.per_raga, _) = _trained_scores(evs, table, cp)
    rep.n_trained = len(evs)

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
    rep.n_fewshot, rep.n_noexample = few_n, none_n
    rep.fewshot_top3 = few_hits / few_n if few_n else 0.0
    rep.noexample_top5 = none_hits / none_n if none_n else 0.0
    return rep


def _theory_rows(store: ExampleStore, params: TheoryParams, split: str):
    rows = []
    for m in store.list_examples():
        if group_split(m.recording_group) != split:
            continue
        line = store.load_melody(m.id)
        if has_melody(line, params):
            rows.append((m.raga_id, swara_profile(line, params).strengths, transitions(line, params)))
    return rows


def _rank_stats(rows, table: RagaTable, params: TheoryParams) -> tuple[float, float]:
    if not rows:
        return 0.0, 0.0
    m = _masks(table)
    idx = {r: i for i, r in enumerate(m.ids)}
    ranks = []
    for raga_id, strengths, tr in rows:
        sc = _score_arrays(strengths, tr.up, tr.down, m, params)[0]
        # Pessimistic rank: ragas tied with the true one count against it (the app's
        # tie order is arbitrary), so tuning cannot "win" by making everything tie.
        ranks.append(int((sc >= sc[idx[raga_id]]).sum()))
    r = np.array(ranks)
    return float(np.mean(r == 1)), float(np.mean(r <= 5))


def theory_rank_stats(store: ExampleStore, table: RagaTable, params: TheoryParams,
                      split: str = "train") -> tuple[float, float]:
    """Theory-matcher-only (top-1, top-5) accuracy over one split's windows."""
    return _rank_stats(_theory_rows(store, params, split), table, params)


def tune_theory(store: ExampleStore, table: RagaTable, base: TheoryParams | None = None) -> TheoryParams:
    """Grid-search the theory matcher's dials on the train split (it needs no examples).

    Real concert audio spreads mass onto passing tones (gamakas), so the synthetic-audio
    defaults are far too strict; this is the v0 stand-in for Plan 4's trained tuning.
    """
    base = base or TheoryParams()
    rows = _theory_rows(store, base, "train")  # profiles depend only on tolerance_cents
    if not rows:
        return base
    best_key, best = None, base
    keys = list(THEORY_GRID)
    for values in itertools.product(*(THEORY_GRID[k] for k in keys)):
        p = replace(base, **dict(zip(keys, values)))
        top1, top5 = _rank_stats(rows, table, p)
        key = (top5, top1)
        if best_key is None or key > best_key:
            best_key, best = key, p
    return best


def _shruti_gains(rows, table: RagaTable, params: TheoryParams) -> list[float]:
    """Gain the shruti check would see on each window (rows use the true tonic)."""
    from raaga.theory.swaras import SwaraProfile
    probe = replace(params, shruti_margin=-1.0)  # report every positive gain
    gains = []
    for _raga, strengths, tr in rows:
        s = shruti_check(SwaraProfile(np.zeros(120), strengths), tr, table, probe, 146.8)
        gains.append(s.gain if s is not None else 0.0)
    return gains


def shruti_false_alarm_rate(store: ExampleStore, table: RagaTable, params: TheoryParams,
                            split: str = "train") -> float:
    """Share of windows (whose stored tonic is correct) on which the shruti check would fire."""
    gains = _shruti_gains(_theory_rows(store, params, split), table, params)
    return float(np.mean([g > 0 and g >= params.shruti_margin for g in gains])) if gains else 0.0


def tune_shruti_margin(store: ExampleStore, table: RagaTable, theory: TheoryParams) -> TheoryParams:
    """Smallest margin whose false-alarm rate on correct tonics is <= MAX_SHRUTI_FALSE_ALARMS."""
    gains = np.array(_shruti_gains(_theory_rows(store, theory, "train"), table, theory))
    if len(gains) == 0:
        return theory
    for margin in SHRUTI_MARGINS:
        if np.mean((gains > 0) & (gains >= margin)) <= MAX_SHRUTI_FALSE_ALARMS:
            return replace(theory, shruti_margin=margin)
    return replace(theory, shruti_margin=SHRUTI_MARGINS[-1])


def calibrate(store: ExampleStore, table: RagaTable, theory: TheoryParams | None = None, *,
              min_confident: int = MIN_CONFIDENT_SAMPLES) -> tuple[TheoryParams, CombineParams, EvalReport]:
    """Tune the theory matcher (train), then knn_margin and w_theory (val); report on test.

    Confidence is only enabled (confident_enabled=True) if, on val, at least `min_confident`
    confident answers were observed with precision >= MIN_PRECISION.
    """
    theory = theory or tune_shruti_margin(store, table, tune_theory(store, table))
    base = CombineParams()
    data = _Data(store, base.model_version)
    train = [m for m in data.metas if data.split[m.id] == "train"]
    trained_ragas = {m.raga_id for m in train}
    val = [m for m in data.metas if data.split[m.id] == "val" and m.raga_id in trained_ragas]
    evs = _evidence(data, table, theory, base, data.index(train), val)
    best_key, best_cp = None, None
    for w in W_THEORY:
        for margin in MARGINS:
            cp = replace(base, w_theory=w, w_knn=round(1 - w, 2), knn_margin=margin, confident_enabled=True)
            top1, _t3, precision, coverage, _, n_conf = _trained_scores(evs, table, cp)
            if precision < MIN_PRECISION or n_conf < min_confident:
                continue
            key = (top1, coverage, -margin)
            if best_key is None or key > best_key:
                best_key, best_cp = key, cp
    if best_cp is None:  # not enough evidence for honest confidence: shortlists only
        top1_by_w = {}
        for w in W_THEORY:
            cp = replace(base, w_theory=w, w_knn=round(1 - w, 2), confident_enabled=False)
            top1_by_w[w] = _trained_scores(evs, table, cp)[0]
        w = max(W_THEORY, key=lambda x: (top1_by_w[x], x))
        best_cp = replace(base, w_theory=w, w_knn=round(1 - w, 2), confident_enabled=False)
    return theory, best_cp, evaluate(store, table, (theory, best_cp), _data=data)
