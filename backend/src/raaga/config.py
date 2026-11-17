"""Project-wide constants and tunable parameter sets."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

SAMPLE_RATE = 44100
ANALYSIS_WINDOW_S = 120.0
MIN_CLIP_S = 10.0
MIN_VOICED_S = 8.0
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
BIN_CENTS = 10
N_BINS = 120
SHORTLIST_SIZE = 5
KNN_TOP_PER_RAGA = 3


class _JsonMixin:
    def to_json(self) -> dict:
        return asdict(self)  # type: ignore[arg-type]

    @classmethod
    def from_json(cls, data: dict | str | None):
        if data is None:
            return cls()
        if isinstance(data, str):
            data = json.loads(data)
        known = {f.name for f in fields(cls)}  # type: ignore[arg-type]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class TheoryParams(_JsonMixin):
    presence_threshold: float = 0.15
    tolerance_cents: float = 35.0
    extra_penalty: float = 4.0
    missing_penalty: float = 0.5
    sa_missing_penalty: float = 6.0
    direction_weight: float = 0.3
    shruti_margin: float = 0.25


@dataclass
class CombineParams(_JsonMixin):
    knn_margin: float = 0.05
    theory_agree_min: float = 0.5
    w_theory: float = 0.5
    w_knn: float = 0.5
    model_version: str = "v0"
