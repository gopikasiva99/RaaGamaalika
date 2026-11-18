# Evaluation

How to reproduce (from `backend/`):

```bash
uv run --extra scripts python scripts/import_seed.py --store ../.store   # Saraga Carnatic, read remotely
uv run python scripts/evaluate.py --store ../.store --calibrate --out ../.store/models/v0/params.json
```

Splits are by recording (`group_split`, ~20% test, ~10% val), never by clip.
`calibrate` tunes the theory matcher on the train split, then the combine
weights on val, and reports on test. Confidence is only switched on if, on val,
at least 20 confident answers were ≥ 90% correct.

## v0 baseline — 2026-11-17

Data: Saraga Carnatic 1.5 — 169 single-raga recordings resolved to the raga
table (65 had no raga label, 8 were ragamalikas, 2 unmatched: Kalgada), cut into
2,179 sixty-second windows across 94 ragas. Melody lines come from the dataset's
precomputed mixture pitch and annotated tonic.

```
test recording groups : 34
trained top-1         : 25.0%  (n=204 windows)
trained top-3         : 62.7%
few-shot top-3        : n/a  (n=0)
no-example top-5      : 4.1%  (n=316)
confident precision   : 100.0%
confident coverage    : 0.0%
```

Calibrated parameters (`.store/models/v0/params.json`, loaded automatically from the store):
theory `presence_threshold=0.15, extra_penalty=1.0, missing_penalty=0.5, direction_weight=0.3,
shruti_margin=0.85`; combine `w_theory=0.3, w_knn=0.7, confident_enabled=false`.

The melody gate (≥ 8 s voiced and ≥ 3 swaras visited in continuous glides) rejects
drone-only, mridangam-like and applause clips and about 4% of real concert windows,
which get "keep listening". The shruti check's margin is set so that it fires on
≤ 2% of training windows whose (annotated) tonic is correct; on test windows it
fires on 1.3% (it was 7.6% before calibration).

"Confident precision 100%" with 0% coverage just means v0 never claims confidence.

Per raga (test windows, top-1 hits):

```
  Kamas                        3/52
  Mohanam                      29/42
  Begada                       3/29
  Gowla                        12/13
  Harikambhoji                 0/11
  Behag                        0/10
  Padi                         0/8
  Lalita                       0/7
  Sindhubhairavi               1/7
  Surutti                      3/6
  Jaunpuri                     0/5
  Shreeranjani                 0/5
  Sahana                       0/5
  Nadanamakriya                0/2
  Sowrashtram                  0/1
  Kanada                       0/1
```

### What this means

- **This is a baseline, not a gate.** The spec §7 targets apply from the first
  trained model (v1, Plan 4).
- **Confident answers are switched off.** No setting reached 90% precision on
  enough validation answers, so v0 always gives a shortlist rather than risk a
  confident wrong answer (the design's first anti-goal).
- **Saraga is thin per raga**: 94 ragas, mostly 1–7 recordings each, and a few
  ragas (Kamas, Mohanam, Begada) dominate the test windows. No raga has enough
  recordings for the few-shot simulation (n/a).
- **Theory-only recognition among 978 ragas is weak on real audio** (no-example
  top-5 4.1%): gamakas spread pitch over passing tones, and many ragas share or
  nearly share swaras. The admin examples (Plan 3) and the trained model and
  learned fingerprints (Plan 4) are where accuracy is expected to come from.

## Speed

60-second clip, Docker image limited to 2 CPUs (`docker run --cpus=2`), warm:
**~2.5 s** from upload to result (`processing_ms` 2518; 2.6–3.2 s wall time
including upload). Target: ≤ 10 s.
