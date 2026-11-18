"""Build backend/data/ragas.json from Wikipedia's "List of Janya ragas" wikitext.

Usage:
    uv run python scripts/build_raga_table.py \
        --wikitext data/sources/wikipedia_list_of_janya_ragas.wikitext \
        --aliases data/raga_aliases.json --overrides data/raga_overrides.json \
        --out data/ragas.json

The wikitext lists all 72 melakartas (bold, numbered rows) each followed by its
janya ragas. Scale definitions are facts; the source is credited in data/SOURCES.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from raaga.theory.ragas import Raga, melakarta_scale, normalize_name, slugify, validate_raga
from raaga.theory.swaras import TOKEN_POSITION, positions

SVARA_RE = re.compile(r"\{\{svaraC\|([^}]*)\}\}")
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def _ascii(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _clean(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", s).strip(" ,.;")


def _outside_parens(s: str) -> str:
    """Drop parenthetical notes that are not inside a [[link]]."""
    out, depth, i = [], 0, 0
    while i < len(s):
        if s.startswith("[[", i):
            j = s.find("]]", i)
            j = len(s) if j < 0 else j + 2
            if depth == 0:
                out.append(s[i:j])
            i = j
            continue
        c = s[i]
        if c == "(":
            depth += 1
        elif c == ")" and depth:
            depth -= 1
        elif depth == 0:
            out.append(c)
        i += 1
    return "".join(out)


def _tokens(raw: str) -> list[str]:
    out = []
    for t in raw.split("|"):
        t = re.sub(r"^\d+=", "", t.strip()).strip("'")
        if t in TOKEN_POSITION:
            out.append(t)
    return out


def _is_vakra(aro: list[str], avaro: list[str]) -> bool:
    a = [TOKEN_POSITION[t] for t in aro]
    d = [TOKEN_POSITION[t] for t in avaro]
    a_core = a[1:-1] if len(a) > 2 and a[0] == 0 and a[-1] == 0 else a
    d_core = d[1:-1] if len(d) > 2 and d[0] == 0 and d[-1] == 0 else d
    inc = all(x < y for x, y in zip(a_core, a_core[1:])) and (not a_core or a_core[0] != 0 or len(a_core) == 1)
    dec = all(x > y for x, y in zip(d_core, d_core[1:]))
    return not (inc and dec)


def parse(wikitext: str) -> list[dict]:
    blocks = re.split(r"\n\|-[^\n]*", wikitext)
    entries: list[dict] = []
    parent = 0
    for block in blocks:
        block = block.strip()
        if "svaraC" not in block or not block.startswith("|"):
            continue
        cells = re.split(r"\|\||\n\|", block[1:])
        scale_cells = [c for c in cells[1:] if "svaraC" in c]
        if len(scale_cells) < 2:
            continue
        # First template of the arohana cell and of the avarohana cell; extra
        # variants (after <br />) and anya-swara notes are ignored.
        templates = [SVARA_RE.findall(scale_cells[0])[0], SVARA_RE.findall(scale_cells[1])[0]]
        name_cell = _outside_parens(cells[0].split("\n", 1)[0])
        name_cell = re.sub(r"\{[^{}]*\}", "", name_cell)
        mela = re.match(r"\s*'''\s*(\d+)\s", name_cell)
        link = LINK_RE.search(name_cell)
        if link:
            target, display = link.group(1), link.group(2) or link.group(1)
        else:
            target, display = "", name_cell
        display = _clean(display)
        target = _clean(target)
        if mela:
            parent = int(mela.group(1))
            display = re.sub(r"^\d+\s*", "", display)
        if not display or parent == 0:
            continue
        aro, avaro = _tokens(templates[0]), _tokens(templates[1])
        if not aro or not avaro:
            continue
        name = _ascii(display)
        aliases = {a for a in (display, target, _ascii(target)) if a and a != name}
        allowed = positions(aro) | positions(avaro)
        mela_pos = positions(melakarta_scale(parent))
        entries.append({
            "linked": bool(link),
            "name": name,
            "aliases": sorted(aliases),
            "melakarta": parent if mela else None,
            "parent": parent,
            "arohana": aro,
            "avarohana": avaro,
            "vakra": _is_vakra(aro, avaro),
            "bhashanga": ("Anya swara" in block) or not allowed <= mela_pos,
        })
    return entries


def dedupe(entries: list[dict], extra_aliases: dict[str, list[str]]) -> list[dict]:
    """Unique ids and unambiguous aliases.

    A name that appears under several melas keeps its plain name for the first
    (lowest-numbered) occurrence; later ones become "Name (mela N)".
    Aliases that would resolve to two different ragas are dropped.
    """
    # Pick which occurrence of a duplicated name keeps the plain name:
    # a melakarta first, then one with its own Wikipedia article, then the first.
    winner: dict[str, dict] = {}
    for e in entries:
        key = normalize_name(e["name"])
        cur = winner.get(key)
        rank = (e["melakarta"] is not None, e["linked"])
        if cur is None or rank > (cur["melakarta"] is not None, cur["linked"]):
            winner[key] = e
    for e in entries:
        if winner[normalize_name(e["name"])] is not e:
            e["name"] = f'{e["name"]} (mela {e["parent"]})'
    for e in entries:
        e["id"] = slugify(e["name"])
    by_name = {normalize_name(e["name"]): e for e in entries}
    # Hand-written aliases are deliberate: they win over any clash.
    forced: dict[str, str] = {}
    for target, alist in extra_aliases.items():
        e = by_name.get(normalize_name(target))
        if e is None:
            sys.exit(f"alias target not found: {target}")
        e["aliases"] = sorted(set(e["aliases"]) | set(alist))
        for a in alist:
            forced[normalize_name(a)] = e["id"]
    for e in entries:
        key = normalize_name(e["name"])
        if key in forced and forced[key] != e["id"]:
            e["name"] = f'{e["name"]} (mela {e["parent"]})'
            e["id"] = slugify(e["name"])
    owners: dict[str, set[str]] = {}
    for e in entries:
        for a in [e["name"], e["id"], *e["aliases"]]:
            owners.setdefault(normalize_name(a), set()).add(e["id"])
    for e in entries:
        own = normalize_name(e["name"])
        keep = []
        for a in e["aliases"]:
            k = normalize_name(a)
            if k == own or forced.get(k) == e["id"] or (k not in forced and len(owners[k]) == 1):
                keep.append(a)
        e["aliases"] = keep
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate ids after dedupe"
    return [{k: e[k] for k in ("id", "name", "aliases", "melakarta", "parent",
                               "arohana", "avarohana", "vakra", "bhashanga")} for e in entries]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wikitext", type=Path, required=True)
    ap.add_argument("--aliases", type=Path, required=True)
    ap.add_argument("--overrides", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    drop = {(normalize_name(n.rsplit("@", 1)[0]), int(n.rsplit("@", 1)[1])) for n in overrides["drop"]}
    fixes = {normalize_name(k): v for k, v in overrides["fix"].items()}
    entries = []
    for e in parse(args.wikitext.read_text(encoding="utf-8")):
        if (normalize_name(e["name"]), e["parent"]) in drop:
            continue
        e.update(fixes.get(normalize_name(e["name"]), {}))
        try:
            validate_raga(Raga.from_json({**e, "id": "x"}))
        except ValueError as err:
            print(f"skipped (invalid in source): {err}")
            continue
        entries.append(e)
    extra = json.loads(args.aliases.read_text(encoding="utf-8"))
    table = dedupe(entries, extra)
    args.out.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(table)} ragas ({sum(e['melakarta'] is not None for e in table)} melakartas)")


if __name__ == "__main__":
    main()
