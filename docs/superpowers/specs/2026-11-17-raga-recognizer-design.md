# Carnatic Raga Recognizer — Design

Date: 2026-11-17
Status: Draft for approval

## 1. Intent

A personal project: a web app, usable on phones and desktop, that tells a
**rasika** which raga is being performed, either live in a concert hall or
from a concert recording. The owner will share it with other rasikas
(friends, WhatsApp groups), so it must be reachable by link, reasonably
responsive and cheap to run.

The owner wants **all ragas covered**. Labelled recordings exist for only
about 40 ragas, so the app combines two methods:

1. A **trained model** gives confident answers for ragas that have training data.
2. A **theory-based matcher** gives ranked shortlists for every raga in a
   reference table (all 72 melakartas plus several hundred janya ragas).

The app always says which kind of answer it is giving.

## 2. Goals, non-goals, anti-goals

### Goals (Phase 1)
- Recognize the raga of a single clip from:
  - **Live recording** in the browser or phone (default ~45 s, with an option to keep listening).
  - **File upload** (common audio/video formats).
  - **YouTube link**, with an optional start time.
- Return either:
  - A **confident answer**: raga, confidence, and runners-up.
  - A **shortlist**: "Likely one of…" with 2–5 ranked candidates.
- Show raga details: melakarta number/parent, arohana/avarohana, detected
  shruti, and a simple visual of which swaras were heard.
- Installable to the phone home screen (PWA). No app store.
- Keep recent results on the device. No accounts.
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
- User accounts, social features, sharing results to a feed.
- Identifying the song, composer, artist or tala.
- Feedback for singers on swara accuracy (a different product).
- Commercial use. The training datasets are licensed non-commercial.

### Anti-goals (failures even if it "works")
- **Presenting a guess as a certainty.** A wrong answer shown as "Thodi 92%"
  is worse than an honest shortlist.
- Answering confidently on percussion-only, applause or silence. It should
  say "no melody detected, keep listening".
- Storing users' recordings. Audio is processed and discarded.
- Running costs before anyone is using it.

## 3. Constraints
- **Budget:** free hosting to start (e.g. Hugging Face Spaces, Docker, CPU).
  Must tolerate cold starts. The frontend shows a "waking up the server…"
  state rather than appearing broken.
- **Hardware:** CPU-only inference. The model must analyze a 60 s clip in a
  few seconds on ~2 vCPUs.
- **Data licensing:** CompMusic / Saraga Carnatic datasets are
  CC BY-NC(-SA) and must be credited in the app. The non-commercial terms
  apply.
- **Real-world audio:** phone microphones, hall reverb and noise, and an
  ensemble of vocal/instrument lead, violin, mridangam, ghatam and tanpura.
  The pipeline must extract the **predominant melody**, not just any pitch.
- **YouTube:** server-side downloads from cloud IPs are often blocked. When
  that happens, the app tells the user to upload the file instead. Fetch
  only the needed segment, never the whole video.

## 4. Approaches considered

| | Approach | Trade-offs | Decision |
|---|---|---|---|
| **A** | **Python recognition server + installable web app (PWA)** | Best audio/MIR tooling, fastest path to accuracy. One server also handles YouTube. Free hosting possible. Downside: every request hits the server, with cold starts on the free tier. | **Chosen** |
| B | Everything on-device (models in the browser) | Instant, free, private. Much harder to build and debug, struggles on older phones, still needs a server for YouTube, and every model update means reconversion. | Rejected for now. A may later move melody extraction onto the device. |
| C | Native mobile apps + backend | App store fees ($99/yr Apple, $25 Google), two codebases, little gain over a PWA for this use. | Rejected |

Within the recognition engine, the **hybrid** (trained model plus theory
matcher) was chosen over "trained model only" (accurate but only ~40
ragas) and "theory matcher only" (covers everything but can't separate
ragas that share swaras).

## 5. How it works

### 5.1 Recognition pipeline (server)
1. **Decode** the input to mono 44.1 kHz (ffmpeg). Trim or limit to the
   analysis window (Phase 1 default: first 2 min of the supplied clip or
   segment).
2. **Tonic (shruti) detection**, e.g. Essentia `TonicIndianArtMusic`. The
   user may optionally override the shruti in the UI (useful for short
   live clips).
3. **Predominant melody extraction** (pitch contour of the lead voice or
   instrument), e.g. Essentia Melodia or a CREPE-family model. The builder
   picks one based on accuracy vs CPU time on Carnatic test clips.
4. **Melody gate:** if too little voiced melody is found (percussion, applause,
   silence), return "no melody detected — keep listening" instead of a guess.
5. **Normalize** the pitch to cents relative to the tonic, folded to one octave.
6. **Two recognizers run in parallel:**
   - **Trained model:** tonic-normalized pitch features (e.g. fine-grained
     pitch distributions and time-delayed melody surfaces, from the
     raga-recognition literature) feed a classifier over the ragas with
     training data. It outputs a probability per raga. Model family is
     the builder's call, provided it meets §7 on CPU.
   - **Theory matcher:** finds which of the 12 swarasthanas are present
     (pitch-histogram peaks) and the dominant ascending/descending note
     transitions. It scores every raga in the reference table by:
     - the swara set matching (missing or extra swaras penalized), and
     - consistency with the arohana/avarohana, including vakra (zig-zag) ragas.

     Shared pitch positions (R2=G1, R3=G2, D2=N1, D3=N2) are resolved by
     the raga's own naming.
7. **Combine:**
   - **Confident** when the trained model's top raga is above a
     calibrated threshold *and* its swara set agrees with what the theory
     matcher heard.
   - **Shortlist** otherwise: the theory matcher's top candidates,
     re-ranked using model probabilities where available. Ragas with
     identical swara sets that the model can't separate stay grouped.
8. **Response:** answer type (confident/shortlist/no-melody), ranked
   candidates with scores, detected shruti, swara-presence profile, and
   processing time.

The engine is exposed as a function `analyze(audio, start, end)`, so Phase
2 can slide it over a long recording.

### 5.2 Raga reference table
- A JSON/CSV in the repo with:
  - All **72 melakartas** plus **several hundred janya ragas** (target:
    ragas commonly heard in concerts, at least ~300).
  - For each raga: canonical name, **alternate spellings** (Thodi/Todi,
    Sankarabharanam/Shankarabharanam), melakarta number/parent, arohana
    and avarohana in swarasthanas, and a vakra flag.
- Compiled from public raga lists. Scale definitions are facts, but the
  source is credited.
- Search by any spelling.

### 5.3 Training data and model training
- Primary: the CompMusic Indian Art Music Raga Recognition dataset
  (Carnatic, ~40 ragas, ~480 recordings) and Saraga Carnatic (via
  `mirdata`). The builder confirms exact coverage and access, since some
  audio requires a request on Zenodo.
- Train offline (laptop CPU, or free Colab/Kaggle). The shipped artifact is
  small and CPU-loadable.
- Train on random 30–120 s excerpts with augmentation to mimic phone
  conditions: added noise and reverb, low-quality compression, and level changes.
- **Split by recording and artist, not by clip**, so no excerpt from a test
  concert leaks into training.

### 5.4 Server API
- `POST /analyze` with a multipart audio file, optional `shruti` override and
  optional `start`/`end`.
- `POST /analyze/youtube` with `{url, start?}`. It fetches only the needed
  segment (yt-dlp). If blocked, it returns a clear error code that the UI
  turns into "Please upload the file instead".
- `GET /ragas`, `GET /ragas/{id}` for the reference table.
- `GET /health` for the frontend to wake the server and show a "waking up" state.
- Limits: max upload size and duration, simple per-IP rate limiting. Audio
  is deleted right after analysis and never logged.

### 5.5 Web app (PWA)
- Screens:
  - **Home**, with three actions: **Listen**, **Upload**, **YouTube link**.
  - **Listening**, with a timer, a level meter and "Stop & identify". It
    offers "keep listening" when the answer is weak or no melody was found.
  - **Result**, sketched below.
  - **Raga detail.**
  - **History**, stored on the device.
  - **About**, with dataset credits and an explanation of confident vs shortlist.
- Recording uses the browser's MediaRecorder. Microphone permission is
  explained before it is requested.
- Result screen sketch:

```
┌──────────────────────────────┐
│  Thodi                 87%   │  ← confident (trained model)
│  Melakarta 8 · Hanumatodi    │
│  S R1 G2 M1 P D1 N2 S        │
│  ─────────────────────────── │
│  Also possible: Dhanyasi 9%  │
│  Detected shruti: C#  [edit] │
│  Swaras heard: ▇▇▅▁▇▆▃ ...   │
└──────────────────────────────┘
```

  A shortlist result is visibly different: a header saying "Likely one of…",
  candidates of similar weight, and a one-line reason such as "these ragas
  share the same swaras".
- Works well on phone screens first. Desktop layout comes second.

### 5.6 Hosting and upgrade path
- **Launch:** one Docker image (API plus built static frontend) on a free
  Hugging Face Space (CPU).
- **Upgrade:** the same image on a paid always-on instance or a small VPS
  (~$5–15/month). No code changes, only configuration.
- Code in a GitHub repo.

## 6. Decisions

### Made with the owner
- Audience: rasikas identifying ragas from concerts, on phone and web.
- Personal project, shared with other rasikas.
- Cover all ragas: confident answers where data allows, honest shortlists elsewhere.
- Input: both live recording and upload/YouTube.
- Full-concert timeline is Phase 2. Phase 1 is a single clip.
- Free hosting to start, upgrade if needed.
- Approach A: Python server plus installable web app.

### Calls made in this design (owner can override)
- Result screen content and the confident/shortlist presentation (§5.5).
- No accounts, with history on the device.
- Audio never stored.
- Manual shruti override.
- Default live listening time ~45 s.
- Reference table target of ≥300 ragas.
- Success targets in §7.
- **Repo public on GitHub (open source).** This keeps tooling options open,
  since Essentia is AGPL, and suits a shared personal project. If the
  owner wants the code private, the builder must avoid AGPL libraries or
  accept their terms.

## 7. Success criteria (Phase 1)
These are proposed targets, to be revised once real numbers exist.

- **Trained ragas, clean recordings** (held-out concerts, 60 s clips):
  - top-1 accuracy ≥ 80%
  - top-3 accuracy ≥ 95%
- **Untrained ragas** (held-out recordings of ragas outside the training
  set): the true raga appears in the shortlist (top 5) ≥ 70% of the time.
- **Confidence honesty:** when the app says "confident", it is right ≥ 90%
  of the time on the test set. This is used to set the threshold.
- **Real phone recordings:** a small personal test set of live hall clips,
  scored separately and reported. It is not gated in Phase 1, but it
  drives what to improve next.
- **Speed:** ≤ 10 s from upload to result for a 60 s clip on a warm free-tier
  server. Cold-start time is measured and shown honestly in the UI.

## 8. Left to the builder
- Specific pitch and tonic tools, classifier family, feature details and
  thresholds, as long as §7 is met on CPU.
- Frontend framework, and visual design within the screens above.
- Source compilation for the raga reference table.
- Exact rate limits, upload caps and error copy.
- Test strategy and project layout.

## 9. Risks
- **Tonic errors on short or noisy live clips** cascade into wrong answers.
  Mitigations: manual override, longer listening, and the confidence gate.
- **Violin shadowing the vocalist and gamaka-heavy passages** can confuse
  swara detection. Mitigation: evaluate on real ensemble audio, not just
  isolated voice.
- **Training-set bias** toward particular artists or recording conditions.
  Mitigation: split by artist, augmentation, and the phone-recording test set.
- **YouTube blocking** on cloud hosts. Mitigation: a graceful fallback to upload.
- **Free-tier sleep and cold starts.** Mitigations: a health-ping "waking up"
  UI, and the upgrade path.
