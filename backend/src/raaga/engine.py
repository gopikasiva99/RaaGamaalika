"""Recognition engine: melody line -> confident answer, shortlist, or no-melody."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from raaga.config import MIN_VOICED_S, SHORTLIST_SIZE, CombineParams, TheoryParams
from raaga.fingerprint.v0 import FINGERPRINTS
from raaga.match.index import FingerprintIndex
from raaga.melody.extract import detect_tonic, melody_line_from_audio
from raaga.melody.line import MelodyLine
from raaga.notes import hz_to_note, note_to_hz_near
from raaga.store.base import ExampleStore
from raaga.theory.matcher import score_ragas, shruti_check
from raaga.theory.ragas import RagaTable, load_raga_table
from raaga.theory.swaras import swara_profile, transitions

DEFAULT_TONIC_HZ = 146.83  # D3, used only when tonic detection fails on silence


@dataclass
class EngineContext:
    table: RagaTable
    theory: TheoryParams
    combine: CombineParams
    index: FingerprintIndex
    fingerprint: Callable[[MelodyLine], np.ndarray]

    @classmethod
    def load(cls, store: ExampleStore, table_path: Path, params_path: Path | None) -> "EngineContext":
        theory, combine = TheoryParams(), CombineParams()
        if params_path is not None and Path(params_path).is_file():
            data = json.loads(Path(params_path).read_text(encoding="utf-8"))
            theory = TheoryParams.from_json(data.get("theory"))
            combine = CombineParams.from_json(data.get("combine"))
        index = FingerprintIndex.build(store, combine.model_version)
        return cls(load_raga_table(table_path), theory, combine, index, FINGERPRINTS[combine.model_version])


@dataclass
class Candidate:
    raga_id: str
    name: str
    melakarta: int | None
    parent: int
    arohana: list[str]
    avarohana: list[str]
    score: float
    percent: int
    group: int | None


@dataclass
class ShrutiSuspect:
    suggested_tonic_hz: float
    suggested_note: str
    shift_semitones: int


@dataclass
class AnalysisResult:
    kind: Literal["confident", "shortlist", "no_melody"]
    candidates: list[Candidate]
    tonic_hz: float | None
    tonic_note: str | None
    shruti_suspect: ShrutiSuspect | None
    swara_strengths: list[float]
    voiced_seconds: float
    model_version: str
    processing_ms: int

    def to_json(self) -> dict:
        return asdict(self)


def _percents(values: list[float]) -> list[int]:
    total = sum(values)
    if total <= 0:
        return [round(100 / len(values))] * len(values) if values else []
    return [int(round(100 * v / total)) for v in values]


def analyze_line(line: MelodyLine, ctx: EngineContext) -> AnalysisResult:
    t0 = time.perf_counter()
    profile = swara_profile(line, ctx.theory)
    strengths = [float(x) for x in profile.strengths]
    base = dict(tonic_hz=float(line.tonic_hz), tonic_note=hz_to_note(line.tonic_hz),
                swara_strengths=strengths, voiced_seconds=round(line.voiced_seconds, 2),
                model_version=ctx.combine.model_version)
    if line.voiced_seconds < MIN_VOICED_S:
        return AnalysisResult(kind="no_melody", candidates=[], shruti_suspect=None,
                              processing_ms=int(1000 * (time.perf_counter() - t0)), **base)
    trans = transitions(line, ctx.theory)
    theory = score_ragas(profile, trans, ctx.table, ctx.theory)
    knn = ctx.index.match(ctx.fingerprint(line)) if len(ctx.index) else {}
    cp = ctx.combine
    combined = {r: cp.w_theory * theory[r].score + cp.w_knn * knn.get(r, 0.0) for r in theory}

    def order(r: str):
        return (-combined[r], -theory[r].score, "(mela" in ctx.table.ragas[r].name, ctx.table.ragas[r].name)

    ranked = sorted(combined, key=order)
    suspect = shruti_check(profile, trans, ctx.table, ctx.theory, line.tonic_hz)

    kind: Literal["confident", "shortlist"] = "shortlist"
    chosen = ranked[:SHORTLIST_SIZE]
    if knn and suspect is None:
        ordered_knn = sorted(knn.values(), reverse=True)
        top = max(knn, key=knn.get)
        margin = ordered_knn[0] - (ordered_knn[1] if len(ordered_knn) > 1 else 0.0)
        t = theory.get(top)
        if (t is not None and margin >= cp.knn_margin and t.score >= cp.theory_agree_min
                and t.extra == ()):
            kind = "confident"
            chosen = [top] + [r for r in ranked if r != top][: SHORTLIST_SIZE - 1]

    scale_key = {r: (ctx.table.ragas[r].aro_positions, ctx.table.ragas[r].avaro_positions) for r in chosen}
    counts: dict = {}
    for k in scale_key.values():
        counts[k] = counts.get(k, 0) + 1
    group_ids: dict = {}
    for r in chosen:
        if counts[scale_key[r]] > 1 and scale_key[r] not in group_ids:
            group_ids[scale_key[r]] = len(group_ids) + 1
    percents = _percents([combined[r] for r in chosen])
    candidates = []
    for r, pct in zip(chosen, percents):
        raga = ctx.table.ragas[r]
        candidates.append(Candidate(
            raga_id=r, name=raga.name, melakarta=raga.melakarta, parent=raga.parent,
            arohana=list(raga.arohana), avarohana=list(raga.avarohana),
            score=round(float(combined[r]), 4), percent=pct, group=group_ids.get(scale_key[r])))
    sus = None
    if suspect is not None:
        sus = ShrutiSuspect(suspect.suggested_tonic_hz, hz_to_note(suspect.suggested_tonic_hz),
                            suspect.shift_semitones)
    return AnalysisResult(kind=kind, candidates=candidates, shruti_suspect=sus,
                          processing_ms=int(1000 * (time.perf_counter() - t0)), **base)


def analyze(audio: np.ndarray, ctx: EngineContext, shruti: str | None = None) -> AnalysisResult:
    t0 = time.perf_counter()
    if shruti:
        note_to_hz_near(shruti, 440.0)  # validate early: raises ValueError
    try:
        tonic = detect_tonic(audio)
    except RuntimeError:  # Essentia finds no spectral peaks (silence); the gate decides
        tonic = DEFAULT_TONIC_HZ
    if shruti:
        tonic = note_to_hz_near(shruti, tonic)
    result = analyze_line(melody_line_from_audio(audio, tonic_hz=tonic), ctx)
    result.processing_ms = int(1000 * (time.perf_counter() - t0))
    return result
