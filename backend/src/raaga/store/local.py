"""Filesystem ExampleStore; layout mirrors the Cloud Storage bucket (spec §5.6)."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from raaga.melody.line import MelodyLine
from raaga.store.base import ExampleMeta

_SAFE = re.compile(r"^[A-Za-z0-9._:-]+$")


class LocalExampleStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        (self.root / "examples").mkdir(parents=True, exist_ok=True)

    def _dir(self, example_id: str) -> Path:
        if not _SAFE.match(example_id):
            raise ValueError(f"bad example id {example_id!r}")
        return self.root / "examples" / example_id

    def list_examples(self) -> list[ExampleMeta]:
        metas = []
        for p in sorted((self.root / "examples").glob("*/meta.json")):
            metas.append(ExampleMeta.from_json(p.read_text(encoding="utf-8")))
        return metas

    def load_melody(self, example_id: str) -> MelodyLine:
        return MelodyLine.from_npz_bytes((self._dir(example_id) / "melody.npz").read_bytes())

    def put_example(self, meta: ExampleMeta, melody: MelodyLine,
                    audio: bytes | None = None, audio_ext: str = "") -> None:
        d = self._dir(meta.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "melody.npz").write_bytes(melody.to_npz_bytes())
        if audio is not None:
            ext = re.sub(r"[^a-z0-9]", "", audio_ext.lower()) or "bin"
            (d / f"audio.{ext}").write_bytes(audio)
        (d / "meta.json").write_text(meta.to_json(), encoding="utf-8")  # last: marks complete

    def delete_example(self, example_id: str) -> None:
        shutil.rmtree(self._dir(example_id), ignore_errors=True)

    def _blob_path(self, path: str) -> Path:
        p = (self.root / path).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError(f"blob path escapes store: {path!r}")
        return p

    def read_blob(self, path: str) -> bytes | None:
        p = self._blob_path(path)
        return p.read_bytes() if p.is_file() else None

    def write_blob(self, path: str, data: bytes) -> None:
        p = self._blob_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
