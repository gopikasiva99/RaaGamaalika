# Plan 1 — Recognition Engine v0 + Public Web App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally runnable RaaGamaalika. A user can record, upload or link a Carnatic clip and get a confident raga answer or an honest shortlist from model v0, through an installable web app packaged as one Docker image.

**Architecture:**
- A Python package `raaga` (under `backend/`) holds the pipeline:
  - audio decode;
  - tonic and predominant-melody extraction (Essentia);
  - melody line → swara profile and transitions;
  - the theory matcher and shruti check, against a JSON raga table;
  - v0 hand-crafted fingerprints with nearest-neighbour matching over an
    `ExampleStore` (local filesystem in this plan; Cloud Storage in Plan 2);
  - the combine step.
- FastAPI serves the API under `/api` plus the built frontend.
- The frontend (`frontend/`) is a Svelte + Vite PWA.
- A seed script fills the store from the Saraga Carnatic dataset. An
  evaluation script reports §7 baseline metrics and calibrates v0's
  combination parameters.

**Tech Stack:**
- Backend: Python 3.13, uv, numpy, scipy, essentia, FastAPI, uvicorn,
  yt-dlp, mirdata (scripts only), pytest, ffmpeg (system).
- Frontend: Svelte 5, Vite, TypeScript, vite-plugin-pwa, Vitest,
  @testing-library/svelte, Playwright.
- Packaging and CI: Docker, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-17-raga-recognizer-design.md`. Roadmap: `docs/superpowers/plans/2026-11-17-roadmap.md`.

## Global Constraints

- **Users' audio is never stored or logged.** Uploaded and recorded audio
  lives only in a per-request temp dir, deleted in a `finally`. Request
  bodies are never logged.
- **CPU only.** For a 60 s clip, analysis (decode → result) takes ≤ 10 s on
  2 vCPUs, with the store loaded.
- **Analysis window:** the first 120 s of the supplied clip or segment
  (`ANALYSIS_WINDOW_S = 120`).
- **Limits:**
  - Clips shorter than 10 s → `422 too_short`.
  - Uploads larger than 50 MB → `413`.
  - Below 8 s of voiced melody → answer kind `no_melody`.
- **Answer kinds** are exactly `confident`, `shortlist` and `no_melody`.
  The shortlist has at most 5 candidates.
- **The app never presents a guess as certain.** It says `confident` only
  via the rule in Task 8.
- **UI copy (verbatim):**
  - "Likely one of…"
  - "No melody detected — keep listening"
  - "Check the shruti?"
  - "Please upload the file instead"
  - "Waking up the server…"
- **Swara positions** (semitones above Sa):

  | Position | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | Swaras | S | R1 | R2, G1 | R3, G2 | G3 | M1 | M2 | P | D1 | D2, N1 | D3, N2 | N3 |
- **Licensing:**
  - The repo is licensed **AGPL-3.0**, because it uses Essentia (AGPL).
  - The Saraga/CompMusic data is CC BY-NC-SA. Credit it in About.
  - Never commit dataset audio, or any concert audio, to the repo.
- **Mobile-first UI.** Desktop is secondary.
- **No accounts and no admin** in this plan. The admin comes in Plan 3.
- **API prefix.** All API routes live under `/api` (e.g. `/api/analyze`), so
  the single-page app owns every other path. This is a deliberate
  refinement of spec §5.4's paths.

## Review Focus

1. **A clip that starts with silence, applause or a tani avartanam and then
   has melody** must still be analyzed. The gate counts voiced *seconds*,
   not the voiced ratio. Test is in Task 4.
2. **A tonic detected an octave off** (common across male, female and
   instrument ranges) must give an identical swara profile. Test is in
   Task 5.
3. **Phone formats:** iPhone `.m4a` (AAC), Android/Chrome `.webm` (Opus)
   and `.mp4` video uploads must decode. Test is in Task 3.
4. **Stopping too early** (under 10 s) must give a friendly "too short"
   message, not an error page. Tests are in Task 10 (API) and Task 13 (UI).
5. **An empty example store** (seed not imported yet) must still answer,
   with theory-only shortlists, and never crash or claim confidence. Test
   is in Task 8.

---

## File Structure

```
LICENSE                                  AGPL-3.0 text (Task 1)
backend/
  pyproject.toml, uv.lock
  src/raaga/
    config.py            constants + TheoryParams, CombineParams dataclasses
    theory/swaras.py     swara tokens ↔ positions, swara_profile(), transitions()
    theory/ragas.py      Raga, RagaTable, load_raga_table(), normalize_name(), melakarta_scale()
    theory/matcher.py    TheoryScore, score_ragas(), shruti_check()
    audio/decode.py      decode_audio()
    audio/youtube.py     fetch_youtube_segment(), YouTubeBlocked
    melody/line.py       MelodyLine
    melody/extract.py    detect_tonic(), extract_pitch(), melody_line_from_audio()
    fingerprint/v0.py    fingerprint_v0()
    store/base.py        ExampleMeta, ExampleStore protocol
    store/local.py       LocalExampleStore
    match/index.py       FingerprintIndex
    engine.py            EngineContext, AnalysisResult, analyze(), combine()
    notes.py             hz_to_note(), note_to_hz_near()
    eval/split.py        group_split()
    eval/metrics.py      evaluate(), calibrate()
    api/app.py           create_app(), app_from_env()
    api/ratelimit.py     RateLimiter
  data/ragas.json        reference table (Task 2)
  scripts/build_melakartas.py, scripts/import_seed.py, scripts/evaluate.py
  tests/…, tests/fixtures/synth.py
frontend/
  package.json, vite.config.ts, index.html
  src/lib/{api,types,history,recorder,wav,notes,session}.ts
  src/routes/{Home,Listen,Result,RagaDetail,History,About}.svelte
  src/components/{CandidateList,SwaraBars,ShrutiPicker,WakingBanner}.svelte
  src/App.svelte (hash router), src/main.ts
  tests/*.test.ts, e2e/smoke.spec.ts
Dockerfile, .dockerignore, .github/workflows/ci.yml
```

Commands run from `backend/` (`uv run pytest …`) or `frontend/` (`npm run …`) as shown.

---

### Task 1: Backend skeleton, swara tokens, raga model and name matching

**Files:**
- Create:
  - `LICENSE` (AGPL-3.0)
  - `backend/pyproject.toml`
  - `backend/src/raaga/__init__.py`
  - `backend/src/raaga/config.py`
  - `backend/src/raaga/theory/__init__.py`
  - `backend/src/raaga/theory/swaras.py`
  - `backend/src/raaga/theory/ragas.py`
- Test:
  - `backend/tests/test_swaras_tokens.py`
  - `backend/tests/test_ragas.py`

**Interfaces:**
- Produces:
  - `swaras.TOKEN_POSITION: dict[str, int]`. It maps
    `S R1 R2 R3 G1 G2 G3 M1 M2 P D1 D2 D3 N1 N2 N3` to the positions in
    Global Constraints.
  - `swaras.positions(tokens: list[str]) -> frozenset[int]`
  - `@dataclass(frozen=True) Raga` with fields:
    - `id: str` (a slug)
    - `name: str`
    - `aliases: tuple[str, ...]`
    - `melakarta: int | None` (set when the raga *is* mela N)
    - `parent: int` (its parent mela number)
    - `arohana: tuple[str, ...]`
    - `avarohana: tuple[str, ...]`
    - `vakra: bool`
    - `bhashanga: bool`

    with properties:
    - `aro_positions: frozenset[int]`
    - `avaro_positions: frozenset[int]`
    - `allowed: frozenset[int]` (their union)
  - `RagaTable` with:
    - `ragas: dict[str, Raga]`
    - `get(id) -> Raga`
    - `search(q: str, limit=20) -> list[Raga]`, which matches names and
      aliases after `normalize_name`, with prefix matches first
    - `resolve(name: str) -> Raga | None`: an exact match of
      `normalize_name` against each raga's name, aliases and id
  - `load_raga_table(path: Path) -> RagaTable`, which validates (see Task 2)
  - `normalize_name(s: str) -> str`: the aggressive form, used only for
    matching
  - `slugify(name: str) -> str`: the readable id. NFKD, drop marks,
    lowercase, keep `a-z0-9` (e.g. "Hamsadhwani" → `hamsadhwani`).
  - `melakarta_scale(n: int) -> tuple[str, ...]`, 7 tokens S..N
  - `config`:
    - `SAMPLE_RATE=44100`, `ANALYSIS_WINDOW_S=120.0`, `MIN_CLIP_S=10.0`
    - `MIN_VOICED_S=8.0`, `MAX_UPLOAD_BYTES=50*1024*1024`
    - `BIN_CENTS=10`, `N_BINS=120`, `SHORTLIST_SIZE=5`, `KNN_TOP_PER_RAGA=3`
    - `@dataclass TheoryParams` with defaults:
      - `presence_threshold=0.15`, `tolerance_cents=35.0`
      - `extra_penalty=4.0`, `missing_penalty=0.5`, `sa_missing_penalty=6.0`
      - `direction_weight=0.3`, `shruti_margin=0.25`
    - `@dataclass CombineParams` with defaults:
      - `knn_margin=0.05`, `theory_agree_min=0.5`
      - `w_theory=0.5`, `w_knn=0.5`, `model_version="v0"`
    - Both dataclasses get `to_json()` / `from_json()`.

- [ ] **Step 1: Write failing tests**

```python
# test_swaras_tokens.py
def test_shared_positions():
    assert TOKEN_POSITION["R2"] == TOKEN_POSITION["G1"] == 2
    assert TOKEN_POSITION["D3"] == TOKEN_POSITION["N2"] == 10
def test_positions_of_mohanam():
    assert positions(["S","R2","G3","P","D2","S"]) == frozenset({0,2,4,7,9})

# test_ragas.py
@pytest.mark.parametrize("n,scale", [
  (8,  ("S","R1","G2","M1","P","D1","N2")),   # Hanumatodi
  (15, ("S","R1","G3","M1","P","D1","N3")),   # Mayamalavagowla
  (22, ("S","R2","G2","M1","P","D2","N2")),   # Kharaharapriya
  (29, ("S","R2","G3","M1","P","D2","N3")),   # Dheerasankarabharanam
  (65, ("S","R2","G3","M2","P","D2","N3")),   # Mechakalyani
])
def test_melakarta_scale(n, scale): assert melakarta_scale(n) == scale
@pytest.mark.parametrize("a,b", [("Thodi","Todi"), ("Tōḍi","Thodi"),
  ("Shankarabharanam","Śankarābharaṇaṁ"), ("Sankarabharanam","Shankarabharanam"),
  ("Mohanam","mohanam "), ("Kalyaani","Kalyani")])
def test_normalize_equivalent(a,b): assert normalize_name(a) == normalize_name(b)
def test_search_and_resolve(tiny_table):  # fixture: Mohanam, Bilahari, Hindolam
    assert tiny_table.resolve("mohanam").id == "mohanam"
    assert [r.id for r in tiny_table.search("bil")] == ["bilahari"]
```

- [ ] **Step 2: Run** `cd backend && uv run pytest tests/test_swaras_tokens.py tests/test_ragas.py -v`. Expected: FAIL (ImportError).

- [ ] **Step 3: Create `pyproject.toml`** (package `raaga`, src layout,
  `requires-python = ">=3.13,<3.14"`; dev group pytest; runtime deps
  numpy, scipy, essentia, fastapi, uvicorn[standard], python-multipart,
  yt-dlp; optional group `scripts` = mirdata). Then implement the
  modules above.

  - **`melakarta_scale(n)`:**
    - M is M1 for n ≤ 36, M2 otherwise.
    - With `i = (n-1) % 36`:
      - `RG = [R1G1,R1G2,R1G3,R2G2,R2G3,R3G3][i // 6]`
      - `DN = [D1N1,D1N2,D1N3,D2N2,D2N3,D3N3][i % 6]`
  - **`normalize_name`** applies these steps in order:
    1. NFKD, then drop combining marks.
    2. Lowercase.
    3. Keep only `a-z`.
    4. Replace `sh→s`, `th→t`, `dh→d`, `bh→b`, `w→v`.
    5. Collapse runs of the same letter to one.

- [ ] **Step 4: Run tests.** Expected: PASS.

- [ ] **Step 5: Commit** `feat(backend): package skeleton, swara tokens, raga model, name normalization`

---

### Task 2: Raga reference table (≥ 300 ragas)

**Files:**
- Create:
  - `backend/scripts/build_melakartas.py`, which writes the 72 melakarta
    entries with names
  - `backend/data/ragas.json`
  - `backend/data/SOURCES.md`, which credits the public raga lists used
- Test: `backend/tests/test_raga_table_data.py`

**Interfaces:**
- Consumes: `load_raga_table`, `melakarta_scale`, `normalize_name` (Task 1).
- Produces: `backend/data/ragas.json`. It is a JSON list of objects
  `{id, name, aliases[], melakarta|null, parent, arohana[], avarohana[], vakra, bhashanga}`.
  `id = slugify(name)`. Tests and code look ragas up with
  `table.resolve(name)` rather than hard-coding ids.

- [ ] **Step 1: Write the failing data test**

```python
def test_table_size_and_validity():
    t = load_raga_table(DATA / "ragas.json")      # raises on any invalid entry
    assert len(t.ragas) >= 300
    assert sum(r.melakarta is not None for r in t.ragas.values()) == 72
def test_known_scales():
    t = load_raga_table(DATA / "ragas.json")
    assert t.resolve("Mohanam").aro_positions == {0,2,4,7,9}
    assert t.resolve("Bilahari").aro_positions == {0,2,4,7,9}
    assert t.resolve("Bilahari").avaro_positions == {0,2,4,5,7,9,11}
    assert t.resolve("Hamsadhwani").allowed == {0,2,4,7,11}
    assert t.resolve("Hindolam").allowed == {0,3,5,8,10}
    for name in ["Kalyani","Thodi","Bhairavi","Kambhoji","Sahana","Darbar",
                 "Nayaki","Kanada","Begada","Madhyamavati","Saveri","Atana"]:
        assert t.resolve(name) is not None, name
def test_aliases_unique():  # no alias resolves to two different ragas
```

- [ ] **Step 2: Run** `uv run pytest tests/test_raga_table_data.py -v`. Expected: FAIL (file missing).

- [ ] **Step 3: Add validation to `load_raga_table`.** It raises
  `ValueError` naming the raga if any of these fail:
  - every token is valid;
  - arohana and avarohana each start and end with `S`;
  - for a `melakarta` entry, its swaras equal `melakarta_scale(n)`;
  - for a non-bhashanga janya, its swaras are a subset of the parent's
    scale;
  - ids and normalized aliases are unique.

- [ ] **Step 4: Build the data.**
  - Run `scripts/build_melakartas.py` for the 72 melakartas, with names
    from the standard list.
  - Hand-compile ≥ 228 janya ragas from public raga lists (e.g.
    Wikipedia's "List of Janya ragas"). Prioritise commonly performed
    ragas and every raga named in the Saraga Carnatic metadata.
  - Record each source in `SOURCES.md`.
  - Mark bhashanga ragas, e.g. Bhairavi, whose D2 is foreign to its parent
    Natabhairavi's D1.

- [ ] **Step 5: Run tests.** Expected: PASS.

- [ ] **Step 6: Commit** `feat(data): raga reference table with 72 melakartas and janya ragas`

---

### Task 3: Audio decoding and synthetic test fixtures

**Files:**
- Create:
  - `backend/src/raaga/audio/__init__.py`
  - `backend/src/raaga/audio/decode.py`
  - `backend/tests/fixtures/synth.py`
- Test: `backend/tests/test_decode.py`

**Interfaces:**
- Produces:
  - `decode_audio(path: Path, start_s: float = 0.0, max_s: float = ANALYSIS_WINDOW_S) -> np.ndarray`.
    It returns mono float32 at `SAMPLE_RATE`. It uses ffmpeg via
    subprocess (`-ss start -t max_s -ac 1 -ar 44100 -f f32le pipe:1`).
    On ffmpeg failure or empty output it raises `AudioDecodeError`.
  - `tests/fixtures/synth.py`:
    - `synth_clip(swaras: list[str], tonic_hz: float, seconds: float, *, drone=True, note_s=0.5, seed=0, leading_silence_s=0.0) -> np.ndarray`.
      It produces a harmonic tone sequence (5 partials) cycling up and down
      the given swaras across two octaves around the tonic. With
      `drone=True` it mixes in a tanpura-like drone (Sa, Pa, upper Sa,
      with harmonics) at −12 dB. It is deterministic for a given seed.
    - `write_wav(path, audio)`.
    - `encode(path_wav, ext) -> Path`, which uses ffmpeg to make
      `.m4a` (aac), `.webm` (libopus) or `.mp4` (aac audio plus a 1-frame
      black video).

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize("ext", ["wav","m4a","webm","mp4"])
def test_decodes_phone_formats(tmp_path, ext):           # Review Focus 3
    wav = write_wav(tmp_path/"c.wav", synth_clip(["S","R2","G3","P","D2"], 146.8, 12))
    a = decode_audio(wav if ext=="wav" else encode(wav, ext))
    assert a.dtype == np.float32 and abs(len(a)/44100 - 12) < 0.2
def test_window_and_offset(tmp_path):
    wav = write_wav(tmp_path/"c.wav", synth_clip(["S","P"], 146.8, 200))
    assert abs(len(decode_audio(wav, start_s=30, max_s=120))/44100 - 120) < 0.1
def test_garbage_raises(tmp_path):
    p = tmp_path/"x.mp3"; p.write_bytes(b"not audio")
    with pytest.raises(AudioDecodeError): decode_audio(p)
```

- [ ] **Step 2: Run** `uv run pytest tests/test_decode.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `decode.py` and `synth.py`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(audio): ffmpeg decoding and synthetic clip fixtures`

---

### Task 4: Tonic, predominant melody and the melody line (with gate)

**Files:**
- Create:
  - `backend/src/raaga/melody/__init__.py`
  - `backend/src/raaga/melody/line.py`
  - `backend/src/raaga/melody/extract.py`
  - `backend/src/raaga/notes.py`
- Test:
  - `backend/tests/test_melody.py`
  - `backend/tests/test_notes.py`

**Interfaces:**
- Consumes: `decode_audio` output, and `synth_clip` for tests.
- Produces:
  - `@dataclass MelodyLine` with fields:
    - `tonic_hz: float`
    - `hop_s: float`
    - `cents: np.ndarray`: float32 cents relative to the tonic, unfolded,
      with `NaN` for unvoiced frames

    and with:
    - property `voiced_seconds -> float`
    - method `folded() -> np.ndarray`: voiced frames only, mod 1200
    - method `slice(start_s, end_s) -> MelodyLine`
    - method `with_tonic(new_tonic_hz) -> MelodyLine`: re-references the
      cents
    - methods `to_npz_bytes() -> bytes` and `from_npz_bytes(b) -> MelodyLine`
  - `detect_tonic(audio) -> float`: Essentia `TonicIndianArtMusic`.
  - `extract_pitch(audio) -> tuple[np.ndarray, float]`: Hz per frame (0 =
    unvoiced) and hop_s. It uses Essentia `EqualLoudness` →
    `PredominantPitchMelodia(frameSize=2048, hopSize=128)`.
  - `melody_line_from_audio(audio, tonic_hz: float | None = None) -> MelodyLine`.
    When `tonic_hz` is None it detects the tonic.
  - `notes.hz_to_note(hz) -> str`: A4 = 440, names
    `C C# D D# E F F# G G# A A# B`.
  - `notes.note_to_hz_near(note: str, near_hz: float) -> float`: the
    octave of `note` closest to `near_hz`. It raises `ValueError` on an
    unknown note.

- [ ] **Step 1: Write failing tests**

```python
def test_tonic_detected_within_50_cents():
    a = synth_clip(["S","R2","G3","P","D2"], 146.8, 30)
    assert abs(1200*np.log2(detect_tonic(a)/146.8)) < 50
def test_melody_tracks_synth_notes():
    line = melody_line_from_audio(synth_clip(["S","G3","P"], 146.8, 20), tonic_hz=146.8)
    f = line.folded(); near = np.min(np.abs(f[:,None]-np.array([0,400,700,1200])[None]),axis=1)
    assert np.mean(near < 30) > 0.85
def test_leading_silence_still_counts_voiced_seconds():      # Review Focus 1
    a = synth_clip(["S","R2","G3","P","D2"], 146.8, 60, leading_silence_s=30)
    assert melody_line_from_audio(a, tonic_hz=146.8).voiced_seconds >= MIN_VOICED_S
def test_npz_roundtrip_and_with_tonic():
    l = MelodyLine(146.8, 0.0029, np.array([0, 700, np.nan], dtype=np.float32))
    assert np.allclose(MelodyLine.from_npz_bytes(l.to_npz_bytes()).cents, l.cents, equal_nan=True)
    assert np.allclose(l.with_tonic(146.8*2**(7/12)).cents[:2], [-700, 0], atol=0.01)
# test_notes.py
def test_notes(): assert hz_to_note(138.6)=="C#" and abs(note_to_hz_near("D",150)-146.83)<0.1
def test_bad_note():
    with pytest.raises(ValueError): note_to_hz_near("H#", 150)
```

- [ ] **Step 2: Run** `uv run pytest tests/test_melody.py tests/test_notes.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** as above. The gate itself lives in the engine
  (Task 8) and compares `voiced_seconds` with `MIN_VOICED_S`. Do not gate
  on the voiced ratio.
- [ ] **Step 4: Run.** Expected: PASS. If the tonic test is flaky on
  synthetic audio, strengthen the synthetic drone (more harmonics), not
  the tolerance.
- [ ] **Step 5: Commit** `feat(melody): tonic detection, predominant melody, MelodyLine`

---

### Task 5: Swara profile and directional transitions

**Files:**
- Modify: `backend/src/raaga/theory/swaras.py`
- Test: `backend/tests/test_swara_profile.py`

**Interfaces:**
- Consumes: `MelodyLine` (Task 4) and `TheoryParams` (Task 1).
- Produces:
  - `@dataclass SwaraProfile`:
    - `histogram: np.ndarray` of shape (120,), sum 1;
    - `strengths: np.ndarray` of shape (12,), with max = 1 (or all 0 if
      silent).
  - `swara_profile(line, params) -> SwaraProfile`.
  - `@dataclass Transitions`: `up: np.ndarray` and `down: np.ndarray`,
    each of shape (12, 12), float counts indexed `[from, to]`.
  - `transitions(line, params) -> Transitions`.
  - `roll_profile(p: SwaraProfile, k: int) -> SwaraProfile` and
    `roll_transitions(t, k) -> Transitions`. These re-reference the
    profile to a Sa that is `k` semitones above the current one
    (`np.roll(…, -k)` on every position axis).

**Algorithm (not fixed by the tests, so specified here):**
- **Histogram:**
  - Built from `line.folded()` in 10-cent bins.
  - Gaussian smoothing with σ = 1 bin, applied circularly.
- **Stable frames:** frames where `|Δcents/Δt| < 300 cents/s`, using a
  5-frame median-filtered contour.
- **Strength of position i:**
  `0.5 * mass_all(i) + 0.5 * mass_stable(i)`, where `mass` is the share of
  frames within ±`tolerance_cents` of `100*i`, measured circularly. The
  result is then max-normalized.
- **Transitions:**
  - Find stable segments: runs of at least 80 ms within ±tolerance of one
    position.
  - Collapse repeats to get a note sequence.
  - For each consecutive pair, add to `up[a, b]` if the second segment's
    *unfolded* mean cents is higher than the first's, else to `down[a, b]`.

- [ ] **Step 1: Write failing tests**

```python
def _line(swaras, secs=40, tonic=146.8):
    return melody_line_from_audio(synth_clip(swaras, tonic, secs, drone=False), tonic_hz=tonic)
def test_mohanam_profile():
    s = swara_profile(_line(["S","R2","G3","P","D2"]), TheoryParams()).strengths
    assert set(np.where(s >= 0.15)[0]) == {0,2,4,7,9}
def test_octave_error_gives_same_profile():                  # Review Focus 2
    l = _line(["S","R2","G3","P","D2"])
    a = swara_profile(l, TheoryParams()).strengths
    b = swara_profile(l.with_tonic(l.tonic_hz*2), TheoryParams()).strengths
    assert np.allclose(a, b, atol=1e-6)
def test_direction_detected():
    t = transitions(_line(["S","R2","G3","P","D2"]), TheoryParams())
    assert t.up[4,7] > 0 and t.down[7,4] > 0 and t.up[7,4] == 0
def test_roll_profile():
    p = swara_profile(_line(["S","R2","G3","P","D2"]), TheoryParams())
    assert set(np.where(roll_profile(p, 7).strengths >= .15)[0]) == {0,2,5,7,9}
```

- [ ] **Step 2: Run** `uv run pytest tests/test_swara_profile.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(theory): swara profile and directional transitions`

---

### Task 6: Theory matcher and shruti check

**Files:**
- Create: `backend/src/raaga/theory/matcher.py`
- Test: `backend/tests/test_matcher.py`

**Interfaces:**
- Consumes: `SwaraProfile`, `Transitions`, `roll_*` (Task 5);
  `RagaTable`, `Raga` (Task 1); `TheoryParams`.
- Produces:
  - `@dataclass TheoryScore` with fields:
    - `raga_id: str`
    - `score: float` in [0, 1]
    - `extra: tuple[int, ...]`
    - `missing: tuple[int, ...]`
    - `direction: float`
  - `score_ragas(profile, trans, table, params) -> dict[str, TheoryScore]`
  - `@dataclass ShrutiSuggestion`:
    - `shift_semitones: int` in −5..6;
    - `suggested_tonic_hz: float`;
    - `gain: float`.

    `shift_semitones = k` means the true Sa is k semitones above the
    detected one; values above 6 are expressed as k−12 so the suggestion
    stays within ±half an octave.
  - `shruti_check(profile, trans, table, params, tonic_hz) -> ShrutiSuggestion | None`

**Scoring algorithm:**

```
s = profile.strengths; heard = {i | s[i] >= presence_threshold}
extra   = heard - raga.allowed
missing = raga.allowed - heard - {0}
penalty = extra_penalty * sum(s[i] for i in extra)
        + missing_penalty * len(missing) / max(1, len(raga.allowed) - 1)
        + (sa_missing_penalty if s[0] < presence_threshold else 0)
set_score = exp(-penalty)
viol_up   = sum(up[:, j]   for j not in raga.aro_positions)   / max(sum(up), 1e-9)
viol_down = sum(down[:, j] for j not in raga.avaro_positions) / max(sum(down), 1e-9)
direction = 1 - 0.5 * (viol_up + viol_down)   # 1.0 when there are no transitions
score = set_score * (1 - direction_weight + direction_weight * direction)
```

**Shruti check:**
1. `base = max(score)` over the table.
2. For k = 1..11, compute `alt_k = max(score)` using the profile and
   transitions rolled by k.
3. Let `k*` be the k with the highest `alt_k`. If
   `alt_k* − base ≥ shruti_margin`, return a suggestion; otherwise return
   `None`.

Requiring Sa means a wrong tonic usually loses Sa, so a real shift is
noticed. Rotations that keep Sa, which is the graha bhedam case (e.g.
Mohanam ↔ Madhyamavati), score about the same both ways and are *not*
flagged. That is correct, because the swaras alone can't decide it.

- [ ] **Step 1: Write failing tests** (profiles built directly as arrays; fixture table from Task 2 data)

```python
def prof(pos, strength=1.0): s=np.zeros(12); s[list(pos)]=strength; return SwaraProfile(np.zeros(120), s)
NO_T = Transitions(np.zeros((12,12)), np.zeros((12,12)))
def test_mohanam_ranking(table):
    rid = lambda n: table.resolve(n).id
    sc = score_ragas(prof({0,2,4,7,9}), NO_T, table, TheoryParams())
    assert sc[rid("Mohanam")].score > sc[rid("Bilahari")].score > sc[rid("Hamsadhwani")].score > sc[rid("Hindolam")].score
    assert sc[rid("Mohanam")].score == pytest.approx(1.0)
    assert sc[rid("Hamsadhwani")].extra == (9,) and sc[rid("Bilahari")].missing == (5, 11)
def test_extra_swara_hurts_more_than_missing(table):
    rid = lambda n: table.resolve(n).id
    sc = score_ragas(prof({0,2,4,6,7,9,11}), NO_T, table, TheoryParams())   # M2 heard
    assert sc[rid("Mechakalyani")].score > sc[rid("Dheerasankarabharanam")].score
def test_direction_penalizes_descent_only_swara_in_ascent(table):
    up = np.zeros((12,12)); up[9,11] = 5   # D2→N3 going up
    sc = score_ragas(prof({0,2,4,5,7,9,11}), Transitions(up, np.zeros((12,12))), table, TheoryParams())
    assert sc[table.resolve("Bilahari").id].direction < 1.0
def test_shruti_check_finds_shift(table):
    s = shruti_check(prof({(p+7)%12 for p in {0,2,4,7,9}}), NO_T, table, TheoryParams(), 146.8)
    assert s is not None and s.shift_semitones == -5 \
       and s.suggested_tonic_hz == pytest.approx(146.8*2**(-5/12), rel=1e-3)
def test_shruti_check_silent_when_correct(table):
    assert shruti_check(prof({0,2,4,7,9}), NO_T, table, TheoryParams(), 146.8) is None
```

- [ ] **Step 2: Run** `uv run pytest tests/test_matcher.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Vectorize over the table by precomputing a
  (n_ragas, 12) allowed mask and aro/avaro masks once per `RagaTable`.
  That keeps the 12-fold shruti check fast.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(theory): raga scoring and shruti check`

---

### Task 7: v0 fingerprint, example store and fingerprint index

**Files:**
- Create:
  - `backend/src/raaga/fingerprint/v0.py`
  - `backend/src/raaga/store/base.py`
  - `backend/src/raaga/store/local.py`
  - `backend/src/raaga/match/index.py`
- Test:
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_store_index.py`

**Interfaces:**
- Consumes: `MelodyLine` (Task 4).
- Produces:
  - `fingerprint_v0(line: MelodyLine) -> np.ndarray`: float32, `D=1720`,
    L2-normalized. It concatenates:
    - the 120-bin folded pitch histogram (L2-normalized, weight 0.5);
    - a TDMS, weight 0.5. That is a 2-D histogram of (folded cents at t,
      folded cents at t+0.3 s) over voiced pairs, in 40×40 bins of 30
      cents, Gaussian-smoothed with σ = 1 bin circularly, raised to the
      power 0.75, L1- then L2-normalized, and flattened to 1600 values.
  - `FINGERPRINTS = {"v0": fingerprint_v0}`.
  - `@dataclass ExampleMeta` with fields:
    - `id`, `raga_id`
    - `kind: Literal["singing","concert"]`
    - `artist`, `recording_group`
    - `tonic_hz`, `duration_s`
    - `source: Literal["dataset","record","upload","youtube","saved-result"]`
    - `note=""`, `added_at` (ISO 8601 UTC)

    plus `to_json()` and `from_json()`.
  - `class ExampleStore(Protocol)` with methods:
    - `list_examples() -> list[ExampleMeta]`
    - `load_melody(id) -> MelodyLine`
    - `put_example(meta, melody, audio: bytes | None = None, audio_ext: str = "") -> None`
    - `delete_example(id) -> None`
    - `read_blob(path: str) -> bytes | None`
    - `write_blob(path: str, data: bytes) -> None`
  - `LocalExampleStore(root: Path)` with layout:
    - `examples/{id}/meta.json`
    - `examples/{id}/melody.npz`
    - `examples/{id}/audio.{ext}` (optional)
    - blobs at `root/{path}`

    This mirrors the Cloud Storage layout in spec §5.6.
  - `class FingerprintIndex` with:
    - `build(store, model_version: str, use_cache=True) -> FingerprintIndex`.
      The cache is the blob `models/{version}/fingerprints.npz` holding
      ids, raga_ids and the matrix. It is rebuilt if the ids differ from
      the store's.
    - `add(meta, fp)` and `remove(id)`.
    - `match(fp, top_per_raga=KNN_TOP_PER_RAGA) -> dict[str, float]`:
      cosine similarity, and per raga the mean of its top
      `min(top_per_raga, n)` similarities, clipped to [0, 1].
    - `raga_ids_with_examples() -> set[str]`.
    - `__len__`.

- [ ] **Step 1: Write failing tests**

```python
def test_fp_shape_norm_and_tonic_invariance():
    l = melody_line_from_audio(synth_clip(["S","R2","G3","P","D2"],146.8,30,drone=False), tonic_hz=146.8)
    l2 = melody_line_from_audio(synth_clip(["S","R2","G3","P","D2"],174.6,30,drone=False,seed=1), tonic_hz=174.6)
    a, b = fingerprint_v0(l), fingerprint_v0(l2)
    assert a.shape == (1720,) and np.isclose(np.linalg.norm(a), 1) and a @ b > 0.9
def test_different_ragas_less_similar(): ...  # Mohanam vs Hindolam synth: a @ b < 0.6
def test_store_roundtrip_and_index(tmp_path):
    st = LocalExampleStore(tmp_path); put Mohanam×1 (exact) and Hindolam×50 (noisy) examples
    idx = FingerprintIndex.build(st, "v0")
    m = idx.match(fp_of_new_mohanam_clip)
    assert max(m, key=m.get) == "mohanam"          # many examples don't swamp one exact match
    assert (tmp_path/"models/v0/fingerprints.npz").exists()
    st.delete_example(some_id); assert len(FingerprintIndex.build(st, "v0")) == 50
```

- [ ] **Step 2: Run** `uv run pytest tests/test_fingerprint.py tests/test_store_index.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(match): v0 fingerprints, local example store, fingerprint index`

---

### Task 8: Engine — analyze() and combine()

**Files:**
- Create: `backend/src/raaga/engine.py`
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces:
  - `@dataclass EngineContext` with fields:
    - `table: RagaTable`
    - `theory: TheoryParams`
    - `combine: CombineParams`
    - `index: FingerprintIndex`
    - `fingerprint: Callable[[MelodyLine], np.ndarray]`

    and `EngineContext.load(store, table_path, params_path: Path | None) -> EngineContext`.
    `params_path` is a JSON `{theory: {...}, combine: {...}}` written by
    Task 9's calibration. When it is missing, the defaults apply.
  - `@dataclass Candidate` with fields:
    - `raga_id`, `name`
    - `melakarta: int | None`, `parent: int`
    - `arohana: list[str]`, `avarohana: list[str]`
    - `score: float`
    - `percent: int`
    - `group: int | None`
  - `@dataclass ShrutiSuspect`: `suggested_tonic_hz`, `suggested_note`,
    `shift_semitones`.
  - `@dataclass AnalysisResult` with fields:
    - `kind: Literal["confident","shortlist","no_melody"]`
    - `candidates: list[Candidate]`
    - `tonic_hz: float | None`, `tonic_note: str | None`
    - `shruti_suspect: ShrutiSuspect | None`
    - `swara_strengths: list[float]` (12 values)
    - `voiced_seconds: float`
    - `model_version: str`
    - `processing_ms: int`

    and `to_json() -> dict`.
  - `analyze_line(line: MelodyLine, ctx) -> AnalysisResult`
  - `analyze(audio: np.ndarray, ctx, shruti: str | None = None) -> AnalysisResult`.
    It decodes the `shruti` note via `note_to_hz_near(shruti, detected_tonic)`,
    builds the melody line, then calls `analyze_line`.

**Combine rule** (spec §5.1 step 8, v0 has no classifier):
1. If `voiced_seconds < MIN_VOICED_S`, return
   `kind="no_melody", candidates=[]`.
2. Compute the theory scores `T`.
3. Compute `K = index.match(fp)` if the index is non-empty, else `{}`.
4. For every raga r in the table:
   `combined[r] = w_theory*T[r].score + w_knn*K.get(r, 0)`.
5. Let `top` = argmax K, and `margin` = K[top] − (second-best K, or 0).
6. The answer is **confident** only if *all* of these hold:
   - K is non-empty;
   - `margin ≥ knn_margin`;
   - `T[top].score ≥ theory_agree_min`;
   - `T[top].extra == ()`;
   - the shruti check returned None.

   Then the candidates are `[top]` plus the next 4 by `combined`.
7. Otherwise the answer is a **shortlist**: the top 5 by `combined`.
8. `percent`: the combined values of the returned candidates, normalized to
   sum to 100 and rounded.
9. `group`: candidates sharing identical `(aro_positions, avaro_positions)`
   get the same small int; unique ones get None.
10. If there is a shruti suspect, set `kind="shortlist"` and fill
    `shruti_suspect`.

- [ ] **Step 1: Write failing tests**

```python
def test_no_melody_on_silence(ctx): assert analyze(np.zeros(44100*20, np.float32), ctx).kind == "no_melody"
def test_empty_store_theory_only_shortlist(ctx_empty):          # Review Focus 5
    r = analyze(synth_clip(["S","R2","G3","P","D2"],146.8,40), ctx_empty)
    assert r.kind == "shortlist" and r.candidates[0].raga_id == ctx_empty.table.resolve("Mohanam").id and len(r.candidates) <= 5
def test_confident_with_matching_examples(ctx_with_mohanam_and_hindolam_examples):
    r = analyze(synth_clip(["S","R2","G3","P","D2"],146.8,40,seed=7), ctx_with_mohanam_and_hindolam_examples)
    assert r.kind == "confident" and r.candidates[0].name == "Mohanam" and sum(c.percent for c in r.candidates) in (99,100,101)
def test_theory_veto_blocks_confidence(ctx_with_mislabelled_examples):
    # examples labelled Hamsadhwani but sung as Mohanam → K says Hamsadhwani; T says extra D2 → shortlist
    assert analyze(mohanam_clip, ctx_with_mislabelled_examples).kind == "shortlist"
def test_shruti_override_used(ctx_empty):
    r = analyze(synth_clip(["S","R2","G3","P","D2"],146.8,40), ctx_empty, shruti="D")
    assert r.tonic_note == "D"
def test_groups_marked_for_identical_scales(ctx_empty): ...  # a profile fitting two identical-scale ragas → same group id
```

- [ ] **Step 2: Run** `uv run pytest tests/test_engine.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Measure `processing_ms` with `time.perf_counter`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(engine): analyze pipeline with confident/shortlist/no-melody combine rule`

---

### Task 9: Seed import (Saraga Carnatic), splits, evaluation and calibration

**Files:**
- Create:
  - `backend/src/raaga/eval/__init__.py`
  - `backend/src/raaga/eval/split.py`
  - `backend/src/raaga/eval/metrics.py`
  - `backend/scripts/import_seed.py`
  - `backend/scripts/evaluate.py`
  - `docs/evaluation.md`, which records how to run the scripts and the v0
    report
- Test: `backend/tests/test_split_metrics.py`

**Interfaces:**
- Consumes: `ExampleStore`, `FingerprintIndex`, `analyze_line`,
  `RagaTable.resolve`.
- Produces:
  - `group_split(group_id: str) -> Literal["train","val","test"]`. Let
    `b = sha1(group_id)[0] % 10`: `b ∈ {0,1}` → test, `b == 2` → val,
    else train. Plan 4 reuses this unchanged.
  - `@dataclass EvalReport` with fields:
    - `trained_top1`, `trained_top3`
    - `fewshot_top3`, `noexample_top5`
    - `confident_precision`, `confident_coverage`
    - `per_raga: dict[str, dict]`
    - `n_test_groups: int`
  - `evaluate(store, table, params: tuple[TheoryParams, CombineParams], *, split="test", fewshot_k=3) -> EvalReport`.
    It builds the index from train-split examples only, then:
    - **trained_\***: scores test windows of ragas that have train
      examples.
    - **fewshot_top3**: for each raga with ≥ 4 groups, rebuilds the index
      with only 3 of its train groups, then scores its test windows.
    - **noexample_top5**: removes the raga from the index entirely, then
      scores its test windows.
    - **confident_precision**: the share of `confident` answers whose top
      candidate is correct.
  - `calibrate(store, table) -> tuple[TheoryParams, CombineParams, EvalReport]`.
    It grid-searches `knn_margin ∈ {0.00, 0.01, …, 0.30}` and
    `w_theory ∈ {0.3, 0.5, 0.7}` (`w_knn = 1 − w_theory`) on the **val**
    split. It picks the setting that maximises `trained_top1` subject to
    `confident_precision ≥ 0.90`, then reports on **test**.
  - `scripts/import_seed.py --store DIR --data-home PATH [--jobs N] [--window 60]`:
    - Calls `mirdata.initialize("saraga_carnatic", data_home)`. The
      dataset must already be downloaded; the script prints the
      `dataset.download()` instructions if it is missing.
    - For each track with a raga label and a tonic annotation, it
      decodes the **mixture audio** and runs `melody_line_from_audio(audio, tonic_hz=annotated)`.
      Using the mixture means seed melody lines come from the same
      pipeline as live clips.
    - It splits the line into 60 s windows and keeps windows with
      voiced ≥ 20 s.
    - It calls `put_example` with `kind="concert"`, `source="dataset"`,
      `artist` = the lead artist, and `recording_group=f"saraga:{track_id}"`.
      It stores **no audio**.
    - It resolves raga names via `table.resolve()`. Unresolved names go
      to `seed_unmatched.txt`, with a count printed.
  - `scripts/evaluate.py --store DIR [--calibrate --out PATH]`. It prints
    the report as a table, and with `--calibrate` writes the params JSON
    used by `EngineContext.load`.

- [ ] **Step 1: Write failing tests** (on a small synthetic store: 6 ragas × 6 groups × 2 windows)

```python
def test_split_stable_and_proportioned():
    assert group_split("saraga:abc") == group_split("saraga:abc")
    shares = Counter(group_split(f"g{i}") for i in range(5000))
    assert 0.17 < shares["test"]/5000 < 0.23 and 0.07 < shares["val"]/5000 < 0.13
def test_no_group_leaks_between_splits(synth_store): # every window of a group lands in one split
def test_evaluate_on_synthetic_store(synth_store, table):
    rep = evaluate(synth_store, table, (TheoryParams(), CombineParams()))
    assert rep.trained_top1 > 0.8 and rep.noexample_top5 > 0.5
def test_calibrate_meets_precision(synth_store, table):
    _, cp, rep = calibrate(synth_store, table); assert rep.confident_precision >= 0.9
```

- [ ] **Step 2: Run** `uv run pytest tests/test_split_metrics.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the split, metrics, calibrate and both scripts.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real-data run (manual; needs network and disk).**
  1. Download Saraga Carnatic via mirdata.
  2. Run `uv run python scripts/import_seed.py --store ../.store --data-home ~/mir_datasets/saraga_carnatic --jobs 4`.
  3. Run `uv run python scripts/evaluate.py --store ../.store --calibrate --out ../.store/models/v0/params.json`.
  4. Paste the printed report into `docs/evaluation.md` under "v0 baseline".

  This is a **baseline, not a gate**: spec §7's targets apply to v1+
  (Plan 4). If the download is impossible in the execution environment,
  record that in `docs/evaluation.md` and leave the step for the owner.
- [ ] **Step 6: Commit** `feat(eval): seed import, group splits, evaluation and v0 calibration`

---

### Task 10: Public API

**Files:**
- Create:
  - `backend/src/raaga/api/__init__.py`
  - `backend/src/raaga/api/app.py`
  - `backend/src/raaga/api/ratelimit.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `EngineContext.load`, `analyze`, `decode_audio`, `RagaTable`.
- Produces:
  - `@dataclass Settings` with fields `store_dir: Path`, `raga_table: Path`,
    `params_path: Path | None`, `static_dir: Path | None`,
    `analyze_per_min: int = 10`.
  - `create_app(settings) -> FastAPI` and `app_from_env() -> FastAPI`.
    The env vars are `RAAGA_STORE_DIR`, `RAAGA_RAGA_TABLE` (default: the
    packaged `data/ragas.json`), `RAAGA_PARAMS` and `RAAGA_STATIC_DIR`.
  - `RateLimiter(per_min).check(key) -> bool`, an in-memory sliding
    window. The key is the first `X-Forwarded-For` hop, else the client host.
- Routes (all JSON):
  - `GET /api/health` → `{"ok": true, "model_version": "v0", "examples": N}`.
  - `POST /api/analyze` takes multipart `file` and an optional form field
    `shruti`. It returns `AnalysisResult.to_json()`. Errors:
    - `413 {"error":"too_large"}`
    - `415 {"error":"undecodable"}`
    - `422 {"error":"too_short"}` when the decoded audio is under 10 s
    - `422 {"error":"bad_shruti"}`
    - `429 {"error":"rate_limited"}`

    The upload is streamed to a `TemporaryDirectory` and deleted in
    `finally`. Analysis runs via `run_in_threadpool`.
  - `GET /api/ragas?q=` → `[{id, name, melakarta, parent}]`, max 20.
    `GET /api/ragas/{id}` → the full raga plus `example_count` (from the
    fingerprint index), or `404`.
  - When `static_dir` is set, the static files are mounted at `/`, with
    an SPA fallback to `index.html` for non-`/api` paths.

- [ ] **Step 1: Write failing tests** (TestClient; tiny store fixture; synthetic WAVs)

```python
def test_health(client): assert client.get("/api/health").json()["ok"] is True
def test_analyze_ok(client, mohanam_wav):
    r = client.post("/api/analyze", files={"file": mohanam_wav}); assert r.status_code == 200
    assert r.json()["kind"] in {"confident","shortlist"} and r.json()["candidates"][0]["name"] == "Mohanam"
def test_too_short(client, wav_5s):                                     # Review Focus 4
    r = client.post("/api/analyze", files={"file": wav_5s}); assert (r.status_code, r.json()["error"]) == (422, "too_short")
def test_bad_shruti(client, mohanam_wav):
    assert client.post("/api/analyze", files={"file": mohanam_wav}, data={"shruti": "H#"}).json()["error"] == "bad_shruti"
def test_undecodable(client): assert client.post("/api/analyze", files={"file": ("x.mp3", b"junk")}).status_code == 415
def test_too_large(client_small_limit, mohanam_wav): assert client_small_limit.post(...).status_code == 413
def test_rate_limit(client_limit_2, mohanam_wav): third request → 429
def test_no_temp_files_left(client, mohanam_wav, tmp_path, monkeypatch):  # TMPDIR → tmp_path; after request tmp_path is empty
def test_ragas_search_and_detail(client):
    ids = [r["id"] for r in client.get("/api/ragas", params={"q": "todi"}).json()]
    assert TABLE.resolve("Thodi").id in ids                      # spelling-tolerant search
    d = client.get(f"/api/ragas/{TABLE.resolve('Mohanam').id}").json()
    assert d["avarohana"][0] == "S" and "example_count" in d
    assert client.get("/api/ragas/nonexistent").status_code == 404
```

- [ ] **Step 2: Run** `uv run pytest tests/test_api.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Check the upload size limit while streaming;
  don't trust `Content-Length`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(api): analyze, ragas and health endpoints with limits`

---

### Task 11: YouTube segment analysis

**Files:**
- Create: `backend/src/raaga/audio/youtube.py`
- Modify: `backend/src/raaga/api/app.py` (add the route)
- Test: `backend/tests/test_youtube.py`

**Interfaces:**
- Produces:
  - `class YouTubeBlocked(Exception)` and `class YouTubeInvalid(Exception)`.
  - `fetch_youtube_segment(url: str, start_s: float, dest_dir: Path, duration_s: float = ANALYSIS_WINDOW_S) -> Path`.
    It validates the host (`youtube.com`, `www.youtube.com`,
    `m.youtube.com`, `youtu.be`, `music.youtube.com`), otherwise it raises
    `YouTubeInvalid`. It uses the `yt_dlp.YoutubeDL` Python API with:
    - `format=bestaudio`
    - `download_ranges=download_range_func(None, [(start, start+duration)])`
    - `force_keyframes_at_cuts=False`
    - `noplaylist=True`
    - output in `dest_dir`

    A `DownloadError` whose message mentions sign-in or bot confirmation,
    HTTP 403 or 429, or "unavailable" maps to `YouTubeBlocked`.
  - Route `POST /api/analyze/youtube` with JSON
    `{url: str, start?: float, shruti?: str}`. It returns the same result
    shape as `/api/analyze`. Errors:
    - `502 {"error":"youtube_blocked"}`
    - `422 {"error":"bad_url"}`

    It shares the rate limit and temp-dir cleanup with `/api/analyze`.

- [ ] **Step 1: Write failing tests** (monkeypatch `yt_dlp.YoutubeDL` — no network in tests)

```python
def test_rejects_non_youtube(client): assert client.post("/api/analyze/youtube", json={"url":"https://evil.example/x"}).json()["error"]=="bad_url"
def test_blocked_maps_to_502(client, fake_ytdl_raising("Sign in to confirm you're not a bot")):
    r = client.post("/api/analyze/youtube", json={"url":"https://youtu.be/abc"}); assert (r.status_code, r.json()["error"]) == (502,"youtube_blocked")
def test_segment_analyzed(client, fake_ytdl_writing(mohanam_wav)):
    r = client.post("/api/analyze/youtube", json={"url":"https://www.youtube.com/watch?v=abc","start":90})
    assert r.status_code == 200 and fake.last_ranges == [(90, 210)]
```

- [ ] **Step 2: Run** `uv run pytest tests/test_youtube.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(api): YouTube segment analysis with blocked fallback`

---

### Task 12: Frontend — scaffold, API client, upload/YouTube, result and raga detail

**Files:**
- Create:
  - `frontend/` (Vite + Svelte 5 + TS; `npm create vite@latest` with
    template `svelte-ts`, then trimmed)
  - `src/lib/types.ts`
  - `src/lib/api.ts`
  - `src/lib/notes.ts`
  - `src/lib/session.ts`
  - `src/App.svelte` (a hash router: `#/`, `#/listen`, `#/result`,
    `#/raga/:id`, `#/history`, `#/about`)
  - `src/routes/Home.svelte`
  - `src/routes/Result.svelte`
  - `src/routes/RagaDetail.svelte`
  - `src/components/CandidateList.svelte`
  - `src/components/SwaraBars.svelte`
  - `src/components/ShrutiPicker.svelte`
- Test:
  - `frontend/tests/api.test.ts`
  - `frontend/tests/Result.test.ts`

**Interfaces:**
- Consumes: the API in Tasks 10–11. `types.ts` mirrors
  `AnalysisResult.to_json()` exactly, with snake_case keys.
- Produces:
  - `api.ts`:
    - `analyzeFile(file: Blob, filename: string, shruti?: string): Promise<AnalysisResult>`
    - `analyzeYouTube(url: string, start?: number, shruti?: string): Promise<AnalysisResult>`
    - `searchRagas(q: string): Promise<RagaSummary[]>`
    - `getRaga(id: string): Promise<RagaDetail>`

    Non-2xx responses throw `ApiError {status, code}`, where `code` is the
    backend's `error` string.
  - `session.ts`: in-memory `lastInput: {kind:"file", blob, filename} | {kind:"youtube", url, start} | null`
    and `lastResult`. These let shruti edits and retries re-send without
    asking the user again.
  - `notes.ts`: `NOTE_NAMES` (`C`…`B`) and `swaraLabel(position, raga?)`.
    The label uses the raga's own token for shared positions, e.g. R2
    vs G1.
  - `ERROR_COPY: Record<string,string>` with exact strings:
    - `too_short` → "That was too short — record at least 10 seconds."
    - `youtube_blocked` → "YouTube didn't let us fetch that video. Please upload the file instead."
    - `bad_url` → "That doesn't look like a YouTube link."
    - `too_large` → "That file is too big (max 50 MB)."
    - `undecodable` → "We couldn't read that file."
    - `rate_limited` → "Too many tries — wait a minute."
    - `network` → "Couldn't reach the server."

**Result screen rules (spec §5.5):**
- `confident`: big name and percent, melakarta line, arohana/avarohana,
  then "Also possible:" for the rest.
- `shortlist`: header "Likely one of…". Candidates have equal visual
  weight, and those sharing a `group` get the note "These ragas share the
  same swaras".
- `no_melody`: "No melody detected — keep listening", plus a "Try again"
  button.
- Always show the detected shruti with an `[edit]` button. It opens
  `ShrutiPicker` (12 note buttons), then re-sends `lastInput` with
  `shruti`.
- If `shruti_suspect` is set, show the banner "Check the shruti?" with
  "Use {suggested_note}", which re-sends with that note, and "Pick
  manually".
- `SwaraBars` draws 12 bars from `swara_strengths`, labelled with
  `swaraLabel`.

- [ ] **Step 1: Write failing tests** (Vitest + @testing-library/svelte; `fetch` mocked)

```ts
test("analyzeFile posts multipart and returns result", ...)
test("error codes become ApiError with code", async () => { mock 422 {"error":"too_short"}; await expect(analyzeFile(b,"a.wav")).rejects.toMatchObject({code:"too_short"}) })
test("confident result shows name and Also possible", ...)
test("shortlist shows 'Likely one of…' and same-swaras note for grouped candidates", ...)
test("no_melody shows 'No melody detected — keep listening'", ...)
test("shruti suspect banner re-sends with suggested note", ...)  // asserts analyzeFile called with shruti "C#"
```

- [ ] **Step 2: Run** `cd frontend && npm test -- --run`. Expected: FAIL.
- [ ] **Step 3: Implement** the routes, components and api client. The
  Home screen has three actions:
  - **Listen** → `#/listen` (Task 13).
  - **Upload** → a file input accepting `audio/*,video/*`.
  - **YouTube link** → URL and optional start time (mm:ss).

  The dev server proxies `/api` to `localhost:8080`.
- [ ] **Step 4: Run.** Expected: PASS. `npm run build` succeeds.
- [ ] **Step 5: Commit** `feat(web): app shell, upload/YouTube flows, result and raga screens`

---

### Task 13: Frontend — live listening

**Files:**
- Create:
  - `frontend/src/lib/recorder.ts`
  - `frontend/src/lib/wav.ts`
  - `frontend/src/lib/recorder-worklet.js`
  - `frontend/src/routes/Listen.svelte`
- Modify: `frontend/src/routes/Result.svelte` (add "Keep listening")
- Test:
  - `frontend/tests/wav.test.ts`
  - `frontend/tests/Listen.test.ts`

**Interfaces:**
- Produces:
  - `wav.ts`:
    - `downsample(pcm: Float32Array, fromRate: number, toRate: number): Float32Array`
    - `encodeWav(pcm: Float32Array, sampleRate: number): Blob` (16-bit PCM mono)
  - `recorder.ts`: `createRecorder(): Promise<Recorder>`, where
    `Recorder = { start(): void; pause(): void; level(): number /*0..1 RMS*/; seconds(): number; toWav(): Blob; close(): void }`.
    - It uses `getUserMedia({audio:{echoCancellation:false, noiseSuppression:false, autoGainControl:false}})`,
      then an `AudioContext`, then an AudioWorklet that collects Float32
      frames.
    - `toWav()` downsamples to 22050 Hz.
    - Captured PCM accumulates across `pause()`/`start()`, so "keep
      listening" extends the same clip. It is capped at 120 s.
  - **Listen flow:**
    1. A one-line explanation is shown *before* the mic permission
       prompt: "We'll listen for about 45 seconds. Audio is analysed and
       never stored."
    2. A timer, a level meter, and "Stop & identify".
    3. Auto-stop at **45 s**.
    4. Then `analyzeFile(recorder.toWav(), "live.wav")`, and navigate to the
       result.
    5. On the Result screen, when `kind !== "confident"` and the input was
       live, show "Keep listening". It resumes the *same* recorder for 30
       more seconds (up to the 120 s cap) and re-analyzes.
    6. If stopped before 10 s, show `ERROR_COPY.too_short` inline and stay
       on the Listen screen (Review Focus 4).
    7. Microphone permission denied → "Microphone access is needed to listen. You can upload a recording instead." with an Upload button.

- [ ] **Step 1: Write failing tests**

```ts
test("encodeWav writes a valid RIFF header and length", ...)  // bytes 0..3 "RIFF", data size = 2*n
test("downsample 44100→22050 halves length", ...)
test("stopping before 10s shows too-short message and does not call the API", ...) // fake Recorder seconds()=6
test("auto-stops at 45s and posts live.wav", ...)  // fake timers
test("permission denied shows upload fallback", ...)
```

- [ ] **Step 2: Run** `npm test -- --run`. Expected: FAIL.
- [ ] **Step 3: Implement.** Inject the recorder factory as a prop, so tests
  pass a fake.
- [ ] **Step 4: Run.** Expected: PASS. Manual check with `npm run dev`: on
  a phone over the LAN (needs https; use `vite --host` with a tunnel, or
  test on desktop Chrome), a 45 s recording produces a result.
- [ ] **Step 5: Commit** `feat(web): live listening with keep-listening and 45s auto-stop`

---

### Task 14: Frontend — history, about, waking-up state, PWA

**Files:**
- Create:
  - `frontend/src/lib/history.ts`
  - `frontend/src/routes/History.svelte`
  - `frontend/src/routes/About.svelte`
  - `frontend/src/components/WakingBanner.svelte`
  - `frontend/public/icons/*`
- Modify:
  - `frontend/vite.config.ts` (vite-plugin-pwa)
  - `frontend/src/lib/api.ts` (`waitForServer`)
- Test:
  - `frontend/tests/history.test.ts`
  - `frontend/tests/waking.test.ts`

**Interfaces:**
- Produces:
  - `history.ts`:
    - `addToHistory(e: {at: string; source: "live"|"upload"|"youtube"; label: string; result: AnalysisResult}): void`
    - `listHistory(): HistoryEntry[]` (newest first)
    - `clearHistory(): void`

    It uses localStorage key `raaga.history.v1` and keeps at most **50**
    entries, dropping the oldest. Corrupt JSON resets the list to empty.
  - `api.ts`: `waitForServer(onSlow: () => void, slowAfterMs = 2000, timeoutMs = 90000): Promise<void>`.
    It polls `/api/health` every 1.5 s until it returns ok, calls `onSlow`
    once after `slowAfterMs`, and rejects with `ApiError{code:"network"}`
    at the timeout.
  - `WakingBanner` shows "Waking up the server…" while slow.
  - **About** includes:
    - an explanation of confident vs shortlist;
    - "Audio you record or upload is analysed and immediately discarded";
    - the dataset credit "Saraga Carnatic dataset — CompMusic, Universitat
      Pompeu Fabra — CC BY-NC-SA", with the exact licence version taken
      from the dataset's page;
    - a link to the GitHub repo and "Licensed AGPL-3.0".
  - **PWA:** name "RaaGamaalika", `display: standalone`, icons 192/512
    (a simple "R" monogram is fine). The service
    worker precaches the app shell only, and `/api/*` is never cached
    (`navigateFallbackDenylist: [/^\/api/]`).

- [ ] **Step 1: Write failing tests**

```ts
test("history keeps newest 50", ...); test("corrupt storage resets to empty", ...)
test("waitForServer calls onSlow once after 2s then resolves on ok", ...)  // fake timers + fetch mock
```

- [ ] **Step 2: Run** `npm test -- --run`. Expected: FAIL.
- [ ] **Step 3: Implement.** Call `waitForServer` on app load and before
  every analyze, and add results to history after each successful analyze.
- [ ] **Step 4: Run.** Expected: PASS. `npm run build` emits a manifest
  and `sw.js`.
- [ ] **Step 5: Commit** `feat(web): history, about, waking-up banner, installable PWA`

---

### Task 15: Docker image, end-to-end smoke test, CI

**Files:**
- Create:
  - `Dockerfile`
  - `.dockerignore`
  - `frontend/e2e/smoke.spec.ts`
  - `frontend/playwright.config.ts`
  - `.github/workflows/ci.yml`
  - `README.md` (replace the title-only file with: what it is, local run,
    tests, licence)

**Interfaces:**
- Consumes: `app_from_env` (Task 10) and the built frontend (Task 14).
- Produces:
  - **The Dockerfile**, multi-stage:
    1. `node:22-slim` runs `npm ci && npm run build` into `frontend/dist`.
    2. `python:3.13-slim` installs `ffmpeg` with apt, copies `backend/`,
       runs `uv sync --frozen --no-dev`, and copies `frontend/dist` to
       `/app/static`.

    Env: `RAAGA_STATIC_DIR=/app/static`, `RAAGA_STORE_DIR=/data/store`.
    Command: `uvicorn raaga.api.app:app_from_env --factory --host 0.0.0.0 --port ${PORT:-8080}`.
    Plan 2 deploys this image unchanged.
  - **The Playwright smoke test:**
    1. Start the backend with an empty store and the built static files.
    2. Open `/`.
    3. Upload `backend/tests/fixtures/mohanam_40s.wav`, generated by a
       pytest fixture script and committed (synthetic, so no licence
       issue).
    4. Expect the result screen to contain "Mohanam".
  - **CI** runs on `pull_request` and `push`:
    - Job **backend**: ubuntu, apt ffmpeg, `uv sync`, `uv run pytest`.
    - Job **frontend**: `npm ci`, `npm test -- --run`, `npm run build`.
    - Job **e2e**: needs both; builds the Docker image, runs it on port
      8080, then runs `npx playwright install --with-deps chromium` and
      `npx playwright test --trace off`.

- [ ] **Step 1: Write the smoke test** `e2e/smoke.spec.ts` as above.
- [ ] **Step 2: Run the image and the test locally:**
  `docker build -t raagamaalika . && docker run -d -p 8080:8080 raagamaalika`,
  then `cd frontend && npx playwright test --trace off`. Expected: the
  test FAILS before the Dockerfile is right, and PASSES after.
- [ ] **Step 3: Timing check.** Post a 60 s synthetic clip to
  `/api/analyze` on the container, limited to 2 CPUs
  (`docker run --cpus=2`). Expected `processing_ms` ≤ 10000. Record the
  number in `docs/evaluation.md`.
- [ ] **Step 4: Write `.github/workflows/ci.yml` and `README.md`.**
- [ ] **Step 5: Commit** `chore: Docker image, e2e smoke test, CI workflow, README`.
  Push, and confirm the CI run is green on GitHub.

---

## Done when

- All tests pass locally and in CI.
- The Docker image serves the PWA at `http://localhost:8080`, and live
  recording, upload and YouTube all reach a result screen.
- `docs/evaluation.md` holds the v0 baseline report, or a note that the
  dataset step was left to the owner, plus the 60 s timing number.
- Next: write **Plan 2 (GCP deploy)** from the roadmap.
