"""Raga model, reference table loading and name matching."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from raaga.theory.swaras import TOKEN_POSITION, positions

_RG = [("R1", "G1"), ("R1", "G2"), ("R1", "G3"), ("R2", "G2"), ("R2", "G3"), ("R3", "G3")]
_DN = [("D1", "N1"), ("D1", "N2"), ("D1", "N3"), ("D2", "N2"), ("D2", "N3"), ("D3", "N3")]


def melakarta_scale(n: int) -> tuple[str, ...]:
    """The seven swaras of melakarta number n (1..72)."""
    if not 1 <= n <= 72:
        raise ValueError(f"melakarta number out of range: {n}")
    i = (n - 1) % 36
    r, g = _RG[i // 6]
    d, ni = _DN[i % 6]
    m = "M1" if n <= 36 else "M2"
    return ("S", r, g, m, "P", d, ni)


def _ascii_lower(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def slugify(name: str) -> str:
    """Readable id: accents stripped, lowercase, a-z0-9 only."""
    return re.sub(r"[^a-z0-9]", "", _ascii_lower(name))


def normalize_name(s: str) -> str:
    """Aggressive spelling-tolerant form used only for matching names."""
    s = re.sub(r"[^a-z0-9]", "", _ascii_lower(s))
    for a, b in (("ee", "i"), ("oo", "u"), ("ow", "o"), ("ou", "o"), ("au", "o"),
                 ("sh", "s"), ("th", "t"), ("dh", "d"), ("bh", "b"), ("w", "v")):
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)


@dataclass(frozen=True)
class Raga:
    id: str
    name: str
    aliases: tuple[str, ...]
    melakarta: int | None
    parent: int
    arohana: tuple[str, ...]
    avarohana: tuple[str, ...]
    vakra: bool
    bhashanga: bool

    @cached_property
    def aro_positions(self) -> frozenset[int]:
        return positions(self.arohana)

    @cached_property
    def avaro_positions(self) -> frozenset[int]:
        return positions(self.avarohana)

    @cached_property
    def allowed(self) -> frozenset[int]:
        return self.aro_positions | self.avaro_positions

    def to_json(self) -> dict:
        return {
            "id": self.id, "name": self.name, "aliases": list(self.aliases),
            "melakarta": self.melakarta, "parent": self.parent,
            "arohana": list(self.arohana), "avarohana": list(self.avarohana),
            "vakra": self.vakra, "bhashanga": self.bhashanga,
        }

    @classmethod
    def from_json(cls, d: dict) -> "Raga":
        return cls(
            id=d.get("id") or slugify(d["name"]), name=d["name"],
            aliases=tuple(d.get("aliases", ())), melakarta=d.get("melakarta"),
            parent=int(d["parent"]), arohana=tuple(d["arohana"]),
            avarohana=tuple(d["avarohana"]), vakra=bool(d.get("vakra", False)),
            bhashanga=bool(d.get("bhashanga", False)),
        )


class RagaTable:
    def __init__(self, ragas: list[Raga]):
        self.ragas: dict[str, Raga] = {r.id: r for r in ragas}
        self._by_norm: dict[str, str] = {}
        for r in ragas:
            for key in (r.name, r.id, *r.aliases):
                self._by_norm.setdefault(normalize_name(key), r.id)

    def __len__(self) -> int:
        return len(self.ragas)

    def get(self, raga_id: str) -> Raga:
        return self.ragas[raga_id]

    def resolve(self, name: str) -> Raga | None:
        rid = self._by_norm.get(normalize_name(name))
        return self.ragas[rid] if rid else None

    def search(self, q: str, limit: int = 20) -> list[Raga]:
        nq = normalize_name(q)
        if not nq:
            return []
        prefix: list[str] = []
        contains: list[str] = []
        for key, rid in self._by_norm.items():
            if key.startswith(nq):
                prefix.append(rid)
            elif nq in key:
                contains.append(rid)
        seen: dict[str, None] = {}
        for rid in sorted(prefix, key=lambda i: self.ragas[i].name) + sorted(
            contains, key=lambda i: self.ragas[i].name
        ):
            seen.setdefault(rid, None)
        return [self.ragas[rid] for rid in list(seen)[:limit]]


def validate_raga(r: Raga) -> None:
    """Raise ValueError (naming the raga) if its definition is inconsistent."""
    try:
        for seq in (r.arohana, r.avarohana):
            if not seq or "S" not in seq:
                raise ValueError("arohana/avarohana must be non-empty and contain S")
            positions(seq)
        if not 1 <= r.parent <= 72:
            raise ValueError(f"parent out of range: {r.parent}")
        scale = positions(melakarta_scale(r.parent))
        if r.melakarta is not None:
            if r.melakarta != r.parent:
                raise ValueError("melakarta must equal parent")
            if r.allowed != scale:
                raise ValueError(f"swaras differ from melakarta {r.melakarta}")
        elif not r.bhashanga and not r.allowed <= scale:
            raise ValueError(f"swaras foreign to parent {r.parent} but not marked bhashanga")
    except ValueError as e:
        raise ValueError(f"raga {r.name!r}: {e}") from None


def load_raga_table(path: Path) -> RagaTable:
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    ragas = []
    for e in entries:
        try:
            r = Raga.from_json(e)
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(f"raga {e.get('name')!r}: {err}") from None
        validate_raga(r)
        ragas.append(r)
    table = RagaTable(ragas)
    if len(table.ragas) != len(ragas):
        raise ValueError("duplicate raga ids")
    return table
