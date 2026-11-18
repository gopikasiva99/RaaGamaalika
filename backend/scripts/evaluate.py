"""Evaluate the engine on an example store; optionally calibrate v0 combine params.

    uv run python scripts/evaluate.py --store ../.store [--calibrate --out ../.store/models/v0/params.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from raaga.config import CombineParams, TheoryParams
from raaga.eval.metrics import calibrate, evaluate
from raaga.store.local import LocalExampleStore
from raaga.theory.ragas import load_raga_table

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--out", type=Path, help="where to write calibrated params JSON")
    args = ap.parse_args()
    store, table = LocalExampleStore(args.store), load_raga_table(DATA / "ragas.json")
    if args.calibrate:
        theory, combine, rep = calibrate(store, table)
        print(f"calibrated: knn_margin={combine.knn_margin} w_theory={combine.w_theory} w_knn={combine.w_knn}")
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps({"theory": theory.to_json(), "combine": combine.to_json()}, indent=2))
            print(f"wrote {args.out}")
    else:
        rep = evaluate(store, table, (TheoryParams(), CombineParams()))
    print(rep.format())
    print("\nper raga (test windows, top-1 hits):")
    for r, d in sorted(rep.per_raga.items(), key=lambda kv: -kv[1]["n_test"]):
        print(f"  {table.get(r).name:28} {d['top1']}/{d['n_test']}")


if __name__ == "__main__":
    main()
