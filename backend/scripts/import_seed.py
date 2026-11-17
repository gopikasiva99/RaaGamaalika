"""Import Saraga Carnatic seed examples into an example store.

Reads the dataset zip remotely (HTTP range requests) unless --zip points at a
local copy. Only metadata, tonic and precomputed mixture pitch are read.

    uv run python scripts/import_seed.py --store ../.store [--zip saraga1.5_carnatic.zip] [--limit 10]
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from raaga.eval.seed import SARAGA_URL, import_saraga, open_remote_zip
from raaga.store.local import LocalExampleStore
from raaga.theory.ragas import load_raga_table

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--zip", type=Path, help="local saraga1.5_carnatic.zip (default: read remotely)")
    ap.add_argument("--url", default=SARAGA_URL)
    ap.add_argument("--window", type=float, default=60.0)
    ap.add_argument("--hop", type=float, default=60.0)
    ap.add_argument("--min-voiced", type=float, default=20.0)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    z = zipfile.ZipFile(args.zip) if args.zip else open_remote_zip(args.url)
    table = load_raga_table(DATA / "ragas.json")
    rep = import_saraga(z, LocalExampleStore(args.store), table, window_s=args.window, hop_s=args.hop,
                        min_voiced_s=args.min_voiced, limit=args.limit, log=print)
    print(f"\ntracks used: {rep.n_tracks_used}, examples: {rep.n_examples}")
    print(f"skipped: no raga {rep.skipped_no_raga}, ragamalika/multi {rep.skipped_ragamalika}, "
          f"missing files {rep.skipped_missing_files}")
    if rep.unmatched:
        out = Path("seed_unmatched.txt")
        out.write_text("".join(f"{n}\t{c}\n" for n, c in rep.unmatched.most_common()), encoding="utf-8")
        print(f"unmatched raga names: {sum(rep.unmatched.values())} tracks -> {out}")


if __name__ == "__main__":
    main()
