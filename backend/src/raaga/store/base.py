"""Example metadata and the storage protocol (local now, Cloud Storage in Plan 2)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from raaga.melody.line import MelodyLine

Kind = Literal["singing", "concert"]
Source = Literal["dataset", "record", "upload", "youtube", "saved-result"]


@dataclass(frozen=True)
class ExampleMeta:
    id: str
    raga_id: str
    kind: Kind
    artist: str
    recording_group: str
    tonic_hz: float
    duration_s: float
    source: Source
    note: str = ""
    added_at: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str | bytes) -> "ExampleMeta":
        return cls(**json.loads(data))


class ExampleStore(Protocol):
    def list_examples(self) -> list[ExampleMeta]: ...
    def load_melody(self, example_id: str) -> MelodyLine: ...
    def put_example(self, meta: ExampleMeta, melody: MelodyLine,
                    audio: bytes | None = None, audio_ext: str = "") -> None: ...
    def delete_example(self, example_id: str) -> None: ...
    def read_blob(self, path: str) -> bytes | None: ...
    def write_blob(self, path: str, data: bytes) -> None: ...
