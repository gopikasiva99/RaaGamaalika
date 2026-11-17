# RaaGamaalika — Carnatic Raga Recognizer — Design

Date: 2026-11-17
Status: Core design approved; revised to add admin examples and kritis (§5.7, §5.8)

## 1. Intent

A personal project: a web app, usable on phones and desktop, that tells a
**rasika** which raga is being performed, either live in a concert hall or
from a concert recording. It also shows **famous kritis** in that raga. The
owner will share it with other rasikas (friends, WhatsApp groups), so it
must be reachable by link, reasonably responsive and cheap to run.

The owner wants **all ragas covered**. Labelled recordings exist for only
about 40 ragas, so the app combines three things:

1. **Example matching:** clips are compared against a store of labelled
   example recordings ("fingerprints"). The store is seeded from open
   datasets.
2. **Owner-taught ragas:** the owner, as the only **admin**, can add more
   examples (1–5 per raga, their own singing or concert clips). New ragas
   become recognizable the moment examples are saved, with no retraining.
3. **Theory matching:** a theory-based matcher gives ranked shortlists for
   every raga in a reference table (all 72 melakartas plus several hundred
   janya ragas), including ragas with no examples at all.

The app always says whether it is giving a **confident answer** or a **shortlist**.

## 2. Goals, non-goals, anti-goals

### Goals (Phase 1)
- Recognize the raga of a single clip from:
  - **Live recording** in the browser or phone (default ~45 s, with an option to keep listening).
  - **File upload** (common audio/video formats).
  - **YouTube link**, with an optional start time.
- Return a **confident answer** (raga, confidence, runners-up) or a
  **shortlist** ("Likely one of…" with 2–5 ranked candidates).
- Show raga details: melakarta number/parent, arohana/avarohana, detected
  shruti, and a simple visual of which swaras were heard.
- Show **famous kritis** for the raga: name, composer, tala, and a
  "Find on YouTube" link. Kritis are searchable by name, composer or raga.
- **Admin (owner only):**
  - Add example recordings by recording, upload or YouTube segment.
  - Add new ragas to the reference table.
  - "Save as example" on any result.
  - See coverage per raga, and listen to or delete examples.
  - Add and edit kritis.
- Installable to the phone home screen (PWA). No app store.
- Keep recent results on the device. No user accounts; the admin is the
  only login.
- Run on a free tier at launch. Move to a ~$5–15/month host with no code
  changes when usage warrants it.

### Phase 2 (designed for, not built in Phase 1)
- **Full-concert timeline.** Split a long recording (2–3 h) into items,
  label each with its raga, and mark percussion solos (tani avartanam),
  applause and talking. Handle ragamalikas, where the raga changes
  mid-piece. Phase 1's engine must be callable on arbitrary windows of a
  long recording so that Phase 2 builds on it.

### Non-goals
- Native iOS/Android apps.
- Accounts for anyone but the admin. No social features, and no
  contributions from the public.
- Identifying the specific song, composer, artist or tala *from audio*.
  Kritis are listed by raga, not detected.
- Kriti lyrics or meanings.
- Feedback for singers on swara accuracy.
- Commercial use. The training datasets are licensed non-commercial.

### Anti-goals (failures even if it "works")
- **Presenting a guess as a certainty.** A wrong answer shown as "Thodi 92%"
  is worse than an honest shortlist. This matters more now that some ragas
  have only one example.
- Answering confidently on percussion-only, applause or silence. It should
  say "no melody detected, keep listening".
- Storing *users'* recordings. Their audio is processed and discarded. Only
  admin-saved examples are kept.
- Losing the admin's examples when the free host restarts.
- Running costs before anyone is using it.

## 3. Constraints
- **Budget:** free hosting to start (e.g. Hugging Face Spaces, Docker, CPU).
  Must tolerate cold starts. The frontend shows a "waking up the server…"
  state rather than appearing broken.
- **Persistence:** free hosts have ephemeral disks. The example store,
  admin-added ragas and kritis must live in free persistent storage, for
  example a **private Hugging Face dataset repo**, which is also versioned
  and so acts as a backup. They are loaded on startup and written through
  on change.
- **Hardware:** CPU-only. Analyzing a 60 s clip and matching it against the
  whole example store must take a few seconds on ~2 vCPUs.
- **Data licensing:** CompMusic / Saraga Carnatic datasets are
  CC BY-NC(-SA) and must be credited in the app. The non-commercial terms
  apply. Admin-saved concert clips stay private (admin-only playback)
  and are used only for matching.
- **Real-world audio:** phone microphones, hall reverb and noise, and an
  ensemble of vocal/instrument lead, violin, mridangam, ghatam and tanpura.
  The pipeline must extract the **predominant melody**, not just any pitch.
  This applies equally to admin examples, so that solo singing and
  ensemble concert clips are comparable.
- **YouTube:** server-side downloads from cloud IPs are often blocked. When
  that happens, the app tells the user to upload the file instead. Fetch
  only the needed segment, never the whole video.

## 4. Approaches considered

### Platform
| | Approach | Trade-offs | Decision |
|---|---|---|---|
| **A** | **Python recognition server + installable web app (PWA)** | Best audio/MIR tooling, fastest path to accuracy. One server also handles YouTube and admin. Free hosting possible. Downside: cold starts on the free tier. | **Chosen** |
| B | Everything on-device (models in the browser) | Instant, free, private. Much harder to build, struggles on older phones, still needs a server for YouTube and admin. | Rejected for now. A may later move melody extraction onto the device. |
| C | Native mobile apps + backend | App store fees, two codebases, little gain over a PWA. | Rejected |

### Recognition engine
| | Approach | Trade-offs | Decision |
|---|---|---|---|
| 1 | Trained classifier only | Accurate on the ~40 dataset ragas. Can't learn from 1–5 examples, and every addition needs an offline retrain. | Rejected |
| 2 | Theory matcher only | Covers every raga in the table. Can't separate ragas sharing swaras, so mostly shortlists. | Rejected alone |
| **3** | **Example matching (fingerprints, nearest neighbours) + theory matcher** | Works with 1–5 examples, and admin additions count immediately. The theory matcher covers ragas with no examples and vetoes inconsistent matches. Raw accuracy on the 40 dataset ragas may be slightly below a dedicated classifier. | **Chosen** |

The core design originally chose approach 1 with approach 2. That changed
to approach 3 when the owner asked to teach new ragas with a few examples.
A learned fingerprint (a model trained on the dataset to produce better
fingerprints) is an allowed later improvement, as long as new examples
still take effect without retraining.

## 5. How it works

### 5.1 Recognition pipeline (server)
1. **Decode** the input to mono 44.1 kHz (ffmpeg). Limit it to the analysis
   window (Phase 1 default: first 2 min of the supplied clip or segment).
2. **Tonic (shruti) detection**, e.g. Essentia `TonicIndianArtMusic`. The
   user may optionally override the shruti in the UI.
3. **Predominant melody extraction**, e.g. Essentia Melodia or a CREPE-family
   model. The builder picks one based on accuracy vs CPU time on Carnatic
   test clips.
4. **Melody gate:** if too little voiced melody is found, return "no melody
   detected — keep listening".
5. **Normalize** the pitch to cents relative to the tonic, folded to one octave.
6. **Fingerprint:** compute tonic-independent melodic features, e.g.
   fine-grained pitch distribution plus time-delayed melody surfaces, as in
   the raga-recognition literature. The exact feature set and distance
   measure are the builder's call, subject to §7.
7. **Two recognizers run in parallel:**
   - **Example matching:** find the nearest example fingerprints in the
     store and aggregate them per raga, so that one raga with many examples
     doesn't swamp others. This produces a score per raga.
   - **Theory matcher:** finds which of the 12 swarasthanas are present
     (pitch-histogram peaks) and the dominant ascending/descending note
     transitions. It scores every raga in the reference table by:
     - the swara set matching (missing or extra swaras penalized), and
     - consistency with the arohana/avarohana, including vakra ragas.

     Shared pitch positions (R2=G1, R3=G2, D2=N1, D3=N2) are resolved by
     the raga's own naming.
8. **Combine:**
   - **Confident** when the top raga from example matching is clearly
     ahead (by a calibrated margin) *and* its swara set agrees with what
     the theory matcher heard.
   - **Shortlist** otherwise: theory-matcher candidates re-ranked using
     example-matching scores where available. Ragas with identical swara
     sets that the examples can't separate stay grouped.
9. **Response:** answer type (confident/shortlist/no-melody), ranked
   candidates with scores, detected shruti, swara-presence profile, top
   kritis for the top raga(s), and processing time.

The engine is exposed as `analyze(audio, start, end)` so Phase 2 can slide
it over a long recording. Fingerprinting is a separate function, so that
adding an example reuses exactly the same steps 1–6.

### 5.2 Raga reference table
- Stored as JSON in the repo as the **seed**, plus admin additions in
  persistent storage, merged at startup.
- Contents:
  - All **72 melakartas** plus **several hundred janya ragas** (target:
    commonly performed ragas, at least ~300).
  - For each raga: canonical name, **alternate spellings**, melakarta
    number/parent, arohana and avarohana in swarasthanas, and a vakra flag.
- Compiled from public raga lists, with the source credited. Searchable by
  any spelling.

### 5.3 Seed examples from open datasets
- Sources: the CompMusic Indian Art Music Raga Recognition dataset
  (Carnatic, ~40 ragas, ~480 recordings) and Saraga Carnatic (via
  `mirdata`). The builder confirms exact coverage and access.
- A one-off offline script fingerprints excerpts (e.g. several 60 s windows
  per recording) and loads them into the example store, tagged
  `source=dataset`. The dataset audio itself is not stored in the app; only
  fingerprints are.
- Evaluation and threshold calibration hold out whole recordings and
  artists, so no excerpt of a test concert is also an example.

### 5.4 Server API
- **Public:**
  - `POST /analyze` with a multipart audio file, optional `shruti` override
    and optional `start`/`end`.
  - `POST /analyze/youtube` with `{url, start?}`. It fetches only the
    needed segment. If blocked, it returns a clear error code that the UI
    turns into "Please upload the file instead".
  - `GET /ragas`, `GET /ragas/{id}` for the reference table, including
    example count and kritis.
  - `GET /kritis?q=&raga=&composer=` to search kritis.
  - `GET /health` for the frontend to wake the server and show a "waking up" state.
- **Admin** (requires the admin session):
  - `POST /admin/login` and logout.
  - `POST /admin/examples`: audio (file, YouTube segment, or the reference
    of a just-analyzed clip for "save as example"), `raga_id`,
    `kind=singing|concert`, and an optional note.
  - `GET /admin/examples?raga=` and `DELETE /admin/examples/{id}`.
  - `GET /admin/examples/{id}/audio` (admin-only playback).
  - `POST /admin/ragas` and `PUT /admin/ragas/{id}` to add or correct ragas.
  - `POST/PUT/DELETE /admin/kritis`.
- **"Save as example" on a result:** analysis keeps the user's clip in
  memory for a short time (e.g. 15 min) under a random ID. Only the admin
  can turn that ID into a stored example. Otherwise it expires, so the
  "never store users' audio" rule holds.
- **Limits:** max upload size and duration, and simple per-IP rate
  limiting on public endpoints. Public audio is never logged.

### 5.5 Web app (PWA)
- **Public screens:**
  - **Home**, with three actions: **Listen**, **Upload**, **YouTube link**.
  - **Listening**, with a timer, a level meter and "Stop & identify". It
    offers "keep listening" when the answer is weak or no melody was found.
  - **Result**, sketched below.
  - **Raga detail**, with full kriti list.
  - **Kriti search.**
  - **History**, stored on the device.
  - **About**, with dataset credits and an explanation of confident vs shortlist.
- **Admin screens** (hidden unless logged in; reached via a non-advertised
  `/admin` path):
  - **Add example**, sketched below.
  - **Coverage:** ragas with example counts. Ragas with zero or one
    example are highlighted, and you can listen to or delete examples.
  - **Raga editor.**
  - **Kriti editor.**
  - "Save as example" plus a raga picker appear on result screens only
    for the admin.

Result screen:
```
┌──────────────────────────────┐
│  Thodi                 87%   │  ← confident
│  Melakarta 8 · Hanumatodi    │
│  S R1 G2 M1 P D1 N2 S        │
│  ─────────────────────────── │
│  Also possible: Dhanyasi 9%  │
│  Detected shruti: C#  [edit] │
│  Swaras heard: ▇▇▅▁▇▆▃ ...   │
│  ─────────────────────────── │
│  Famous kritis               │
│  Kaddanuvariki · Tyagaraja · │
│    Adi            [▶ YouTube]│
│  Dasharathe · Tyagaraja ·    │
│    Adi            [▶ YouTube]│
│  See all 12 →                │
│  ─────────────────────────── │
│  (admin) [Save as example ▾] │
└──────────────────────────────┘
```

A shortlist result has a "Likely one of…" header, and each candidate
expands to show its kritis.

Admin "Add example" screen:
```
Add example ─────────────────────
 Source:  ● Record  ○ Upload  ○ YouTube (url, start, end)
 Raga:    [ Kanada            ▾ ]   [+ New raga]
 Type:    ○ My singing  ● Concert
 Note:    [ Sanjay S., Music Academy 2025 ]
 [ ▶ preview ]        [ Save ]
```

Mobile-first; the desktop layout comes second.

### 5.6 Hosting and upgrade path
- **Launch:** one Docker image (API plus built static frontend) on a free
  Hugging Face Space (CPU). The example store, admin ragas and kritis are
  kept in a private Hugging Face dataset repo, loaded on startup and
  written through on each admin change.
- **Upgrade:** the same image on a paid always-on instance or a small VPS
  (~$5–15/month). No code changes, only configuration.
- **Secrets** (admin password, storage token) come from host secrets, never
  the repo.
- Code in the `gopikasiva99/RaaGamaalika` GitHub repo.

### 5.7 Admin: teaching new ragas
- **Single admin:**
  - A password set as a host secret, giving a signed, HTTP-only session
    cookie.
  - Login rate-limited.
  - No user management.
- **Each example stores:**
  - Original audio, kept private for playback and re-fingerprinting if the
    feature method changes.
  - Fingerprint.
  - Raga ID, kind (singing/concert), detected shruti, duration, source
    (record/upload/YouTube/saved-result), note, and date added.
- **Effect is immediate:** the new fingerprint is added to the in-memory
  index and written through to storage. The next analysis uses it.
- **Guardrails:**
  - When saving, show the detected swaras next to the chosen raga's
    arohana/avarohana, and warn if they disagree. This catches mislabels
    and bad shruti detection.
  - Melody gate applies: no example is saved from percussion or silence.
  - A suggested length of 30 s–3 min.
- **Re-fingerprint all:** an admin action that rebuilds every fingerprint
  from stored audio after the feature method changes.

### 5.8 Kritis
- **Catalog:**
  - Name, alternate spellings, composer, raga ID, tala, language (optional),
    and a "famous" flag/rank.
  - Seeded as JSON in the repo from public composition lists (e.g. lists
    of works by Tyagaraja, Dikshitar, Syama Sastri, Papanasam Sivan and
    others), with sources credited. Admin additions and edits live in
    persistent storage.
- **On a result or raga page:** up to ~5 famous kritis, plus "see all". If
  none are flagged famous, show what exists.
- **Search:** by kriti name (spelling-tolerant), composer or raga.
- **"Find on YouTube":** a plain YouTube search link (e.g. "<kriti> <raga>
  <composer>"). No API key, no embedding, no lyrics.

## 6. Decisions

### Made with the owner
- Audience: rasikas identifying ragas from concerts, on phone and web.
- Personal project, shared with other rasikas.
- Cover all ragas: confident answers where examples allow, honest
  shortlists elsewhere.
- Input: both live recording and upload/YouTube.
- Full-concert timeline is Phase 2. Phase 1 is a single clip.
- Free hosting to start, upgrade if needed.
- Approach A: Python server plus installable web app.
- Owner is the sole admin. Adds 1–5 examples per raga, both their own
  singing and concert clips, so that new ragas become recognizable.
- Kritis: names, composer, tala, and YouTube links. No lyrics.

### Calls made in this design (owner can override)
- **Recognition engine switched to example matching** (approach 3), so admin
  examples work immediately.
- "Save as example" from any result, using a 15-minute in-memory hold of
  the clip.
- Private Hugging Face dataset repo for persistent storage.
- Swara-mismatch warning when saving examples.
- Admin can add new ragas and edit kritis.
- No accounts, with history on the device.
- Users' audio is never stored.
- Manual shruti override.
- Default live listening time ~45 s.
- Reference table target of ≥300 ragas.
- Success targets in §7.
- **Repo public on GitHub (open source).** This keeps Essentia (AGPL)
  usable. Secrets and admin audio are never in the repo.

## 7. Success criteria (Phase 1)
These are proposed targets, to be revised once real numbers exist.

- **Dataset ragas, clean recordings** (held-out concerts, 60 s clips):
  - top-1 accuracy ≥ 80%
  - top-3 accuracy ≥ 95%
- **Few-shot ragas** (simulate admin use: for ragas held out of the seed
  store, add 3 examples and test on other recordings): the true raga is in
  the top 3 ≥ 70% of the time.
- **No-example ragas:** the true raga appears in the shortlist (top 5)
  ≥ 70% of the time.
- **Confidence honesty:** when the app says "confident", it is right ≥ 90%
  of the time on the test set. This is used to set the margin.
- **Admin flow:** an example added through the UI affects the very next
  analysis, and it survives a server restart.
- **Real phone recordings:** a small personal test set of live hall clips,
  scored and reported separately. It is not gated in Phase 1, but it drives
  what to improve next.
- **Speed:** ≤ 10 s from upload to result for a 60 s clip on a warm free-tier
  server, with the full example store loaded.

## 8. Left to the builder
- Specific pitch and tonic tools, fingerprint features, distance measure,
  per-raga aggregation and thresholds, as long as §7 is met on CPU.
- Frontend framework, and visual design within the screens above.
- Source compilation for the raga and kriti seed tables.
- Storage layout inside the dataset repo.
- Exact rate limits, upload caps and error copy.
- Test strategy and project layout.

## 9. Risks
- **Tonic errors on short or noisy clips** cascade into wrong answers and
  bad examples. Mitigations: manual override, the swara-mismatch warning
  when saving, and the confidence gate.
- **Solo singing vs concert mismatch:** an example of the owner singing may
  match concert audio less well. Mitigations: predominant-melody extraction
  for both, the `kind` tag to compare, and coverage view nudges to add a
  concert clip per raga.
- **One example per raga** can make a raga look confident too easily.
  Mitigation: the confidence margin is calibrated with few-shot
  simulations, and it requires agreement from the theory matcher.
- **Mislabelled examples** silently poison results. Mitigations: the
  mismatch warning, listen/delete in the coverage view, and dataset-repo
  version history to roll back.
- **Kriti data quality** (spellings, raga attributions vary between
  sources). Mitigations: alternate spellings, admin editing, and credited
  sources.
- **Violin shadowing and gamaka-heavy passages** can confuse swara
  detection. Mitigation: evaluate on real ensemble audio.
- **YouTube blocking** on cloud hosts. Mitigation: a graceful fallback to upload.
- **Free-tier sleep and cold starts.** Mitigations: a health-ping
  "waking up" UI, and the upgrade path.
