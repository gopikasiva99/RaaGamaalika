# RaaGamaalika

Identify the Carnatic raga being performed — live in the concert hall, from an
uploaded recording, or from a YouTube link. A personal project for rasikas.

The app gives a **confident answer** only when its example recordings clearly
point to one raga *and* the swaras it heard fit that raga's arohana/avarohana;
otherwise it gives an honest **"Likely one of…"** shortlist. Design:
[`docs/superpowers/specs/2026-11-17-raga-recognizer-design.md`](docs/superpowers/specs/2026-11-17-raga-recognizer-design.md).
Build roadmap: [`docs/superpowers/plans/2026-11-17-roadmap.md`](docs/superpowers/plans/2026-11-17-roadmap.md).

## Layout

- `backend/` — Python 3.13 package `raaga`: audio decoding (ffmpeg), shruti and
  predominant-melody extraction (Essentia), the theory matcher and shruti check,
  example fingerprints, the recognition engine, the FastAPI app, evaluation tools.
  Raga reference table: `backend/data/ragas.json` (see `backend/data/SOURCES.md`).
- `frontend/` — Svelte 5 + Vite installable web app (PWA).
- `Dockerfile` — one image serving the API (`/api/...`) and the web app.

## Run locally

```bash
docker build -t raagamaalika .
docker run -p 8080:8080 -v "$PWD/.store:/data/store" raagamaalika
```

Open <http://localhost:8080>. Without example recordings the app still works,
using the theory matcher only (shortlists). To add the Saraga Carnatic seed
examples (reads ~1 GB remotely, stores melody lines only — no audio):

```bash
cd backend
uv run --extra scripts python scripts/import_seed.py --store ../.store
uv run python scripts/evaluate.py --store ../.store --calibrate --out ../.store/models/v0/params.json
```

then run the container with `-e RAAGA_PARAMS=/data/store/models/v0/params.json`.
Results are recorded in [`docs/evaluation.md`](docs/evaluation.md).

## Develop

```bash
cd backend && uv sync && uv run pytest
cd frontend && npm ci && npm test -- --run && npm run dev   # dev server proxies /api to :8080
cd frontend && npm run e2e                                  # against a running server on :8080
```

## Credits and licence

- Example recordings: Saraga Carnatic dataset — CompMusic, Universitat Pompeu Fabra — CC BY-NC-SA 4.0 (non-commercial).
- Raga scales: Wikipedia, "List of Janya ragas" (CC BY-SA 4.0).
- Audio analysis: [Essentia](https://essentia.upf.edu) (AGPL-3.0).

RaaGamaalika is licensed under the **GNU AGPL-3.0** (see `LICENSE`).
