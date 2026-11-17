# RaaGamaalika — Carnatic Raga Recognizer — Design

Date: 2026-11-17
Status: **Approved** (2026-11-17), including admin examples and kritis (§5.7, §5.8), GCP hosting (§5.6), a trained model with retraining (§5.9) and the shruti check (§5.1)

## 1. Intent

A personal project: a web app, usable on phones and desktop, that tells a
**rasika** which raga is being performed, either live in a concert hall or
from a concert recording. It also shows **famous kritis** in that raga. The
owner will share it with other rasikas (friends, WhatsApp groups), so it
must be reachable by link, reasonably responsive and cheap to run.

The owner wants **all ragas covered**. Labelled recordings exist for only
about 40 ragas, so the app combines four things:

1. **A trained model, used two ways:**
   - It gives high-accuracy answers for ragas with enough varied examples
     ("trained" ragas).
   - Its learned representation is the **fingerprint** used to compare clips
     against every stored example, so ragas with only a few examples work too.
2. **Owner-taught ragas:** the owner, as the only **admin**, adds examples.
   These are their own singing or concert clips, starting with 1–5 per raga
   and as many as needed over time. A new example counts **immediately**
   via fingerprint matching. Ragas that collect enough varied examples
   **graduate** into the classifier at the next retrain.
3. **Retraining on demand:** the admin presses "Retrain". The model is
   retrained on everything collected so far and only replaces the current
   one if it scores at least as well on held-out recordings.
4. **Theory matching:** a theory-based matcher gives ranked shortlists for
   every raga in a reference table (all 72 melakartas plus several hundred
   janya ragas), including ragas with no examples at all. Its thresholds
   and weights are tuned on the labelled data during training.

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
  - **Retrain** the model, see how it compares with the current one, and
    roll back to an earlier model.
  - See each raga's progress toward graduating into the classifier.
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
- **Budget:** the owner's GCP account, staying within free tiers to start.
  Cloud Run scales to zero, so cold starts (a few seconds) must be
  tolerated. The frontend shows a "waking up the server…" state rather
  than appearing broken. A GCP budget alert and a Cloud Run max-instances
  cap bound the worst-case cost.
- **Persistence and multiple instances:** Cloud Run containers have no
  lasting disk, and there may be several at once. The example store,
  admin-added ragas and kritis live in a **private Cloud Storage bucket**
  with object versioning on, which acts as a backup and a way to roll back.
  Every instance must see admin changes promptly (§5.6). There is no
  server-side state kept between requests.
- **Deploy access:** the GCP account is under a different Google ID from
  this development setup. Deploys run only from GitHub Actions, trusted by
  GCP through Workload Identity Federation. No GCP keys exist in GitHub,
  the repo or development sessions.
- **Hardware:** CPU-only.
  - Analyzing a 60 s clip and matching it against the whole example store
    must take a few seconds on ~2 vCPUs.
  - Training runs as a **Cloud Run Job** on CPU and should finish in under
    ~1 hour, staying mostly within the free tier.
  - No GPU is planned. The model works on melody lines (pitch over time),
    which are tiny compared with audio, so CPU training is realistic.
- **Data licensing:** CompMusic / Saraga Carnatic datasets are
  CC BY-NC(-SA) and must be credited in the app. The non-commercial terms
  apply. Admin-saved concert clips stay private (admin-only playback)
  and are used only for matching and training. Dataset-derived melody
  lines are kept privately in the bucket for training; dataset audio is
  not.
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
| 3 | Example matching (hand-crafted fingerprints) + theory matcher | Works with 1–5 examples, and additions count immediately. But fingerprints never improve with more data, and accuracy on well-covered ragas is below a trained classifier. | Superseded by 5 |
| 4 | Three separate recognizers (classifier + hand-crafted fingerprints + theory) | Simple to reason about, but training improves only the classifier; few-example ragas never get better. | Rejected |
| **5** | **One trained model with two jobs (classifier + learned fingerprint) + trained theory matcher** | Best accuracy on trained ragas. Few-example ragas still work instantly and improve with each retrain. Cost: retraining machinery, model versioning, and re-fingerprinting all examples after each retrain (cheap, since melody lines are stored). | **Chosen** |

History: the core design chose 1 + 2. That moved to 3 when the owner asked
to teach ragas with a few examples, then to 5 when the owner asked for a
trained classifier and committed to adding as many examples as needed.
Approach 5 keeps 3's guarantee that new examples count without retraining.
Approach 3's hand-crafted fingerprint remains as **model v0**, so the app
works before the first training run.

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
6. **Model:** the active model version (§5.9) takes the tonic-normalized
   melody line and outputs two things:
   - **class probabilities** over the trained ragas, and
   - a **fingerprint** (embedding vector).

   Model v0 has no classifier: its fingerprint is a hand-crafted feature
   such as fine-grained pitch distribution plus time-delayed melody
   surfaces, from the raga-recognition literature.
7. **Three scores per raga:**
   - **Classifier:** probability, for trained ragas only.
   - **Example matching:** find the nearest example fingerprints in the
     store and aggregate them per raga, so that one raga with many examples
     doesn't swamp others. This produces a score per raga. It covers every
     raga with at least one example, trained or not.
   - **Theory matcher:** finds which of the 12 swarasthanas are present
     (pitch-histogram peaks) and the dominant ascending/descending note
     transitions. It scores every raga in the reference table by:
     - the swara set matching (missing or extra swaras penalized), and
     - consistency with the arohana/avarohana, including vakra ragas.

     Shared pitch positions (R2=G1, R3=G2, D2=N1, D3=N2) are resolved by
     the raga's own naming. Thresholds and penalty weights come from the
     active model version, where training tuned them.
   - **Shruti check:** the theory matcher also re-scores the swara profile
     as if Sa were at each of the other 11 positions.
     - If some other Sa fits the raga table far better (by a calibrated
       margin) than the detected one, the response includes a
       `shruti_suspect` flag with the suggested shruti.
     - The answer is then downgraded to a shortlist, and the UI shows
       "Check the shruti?" with a one-tap retry using the suggestion or a
       manual pick.
     - The same check runs when the admin saves an example.
8. **Combine** (the combination weights and thresholds are fitted during
   training and stored with the model version):
   - **Confident** when the theory matcher agrees with the top raga's swara
     set, *and* either:
     - the classifier is above its calibrated threshold for a trained raga, or
     - example matching has the top raga clearly ahead by its calibrated
       margin.
   - **Shortlist** otherwise: candidates ranked by the combined score.
     Ragas with identical swara sets that the evidence can't separate stay
     grouped.
9. **Response:** answer type (confident/shortlist/no-melody), ranked
   candidates with scores, detected shruti, swara-presence profile, top
   kritis for the top raga(s), and processing time.

The engine is exposed as `analyze(audio, start, end)` so Phase 2 can slide
it over a long recording.
- Steps 1–5 produce a **melody line** (tonic plus normalized pitch
  contour). It is stored with every example, so retraining and
  re-fingerprinting never re-process audio.
- Step 6 is a separate function, so adding an example reuses exactly the
  same steps.

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
- A one-off script extracts melody lines for every dataset recording and
  uploads them to the bucket as seed examples, tagged `source=dataset` with
  artist and recording IDs. The dataset may already ship precomputed tonic
  and pitch, which the builder can use. Dataset audio itself is not stored
  in the app.
- These seed examples are the initial training data. They are the reason
  ~40 ragas can be "trained" from day one.

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
  - `POST /admin/training` starts a training run (the Cloud Run Job).
    `GET /admin/training` returns the status of the current run and the
    history of model versions with their metrics.
  - `POST /admin/models/{version}/activate` promotes a model or rolls back
    to it.
- **"Save as example" on a result:** the server holds nothing. The admin's
  own browser still has the clip it just recorded or uploaded, or the
  YouTube URL and segment, and re-sends it to `POST /admin/examples`. This
  works with scale-to-zero and multiple instances, and keeps the "never
  store users' audio" rule absolute.
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
  - **Coverage:** for each raga, the example count and graduation progress,
    e.g. "7/10 recordings · 2/3 artists". Ragas with zero or one example
    are highlighted, and you can listen to or delete examples.
  - **Training**, sketched below.
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
 Artist:  [ Sanjay Subrahmanyan ▾ ]   (or "Me")
 Recording/concert: [ Music Academy 2025 ▾ ]   ← clips from one concert group together
 Note:    [ ]
 [ ▶ preview ]        [ Save ]
```

Admin "Training" screen:
```
Training ──────────────────────────────────────
 Active model: v3 (12 Nov) · 46 trained ragas
 Since v3: 38 new examples · 2 ragas ready to graduate
           (Kanada, Begada)
 [ Retrain now ]
 Last run: v4 · NOT promoted
   trained-raga top-1  79%  (v3: 82%)
   few-shot top-3      74%  (v3: 71%)      [details]
   [ Promote anyway ]
 History:  v3 ✓ active · v2 [roll back] · v1 · v0 (no classifier)
```

Mobile-first; the desktop layout comes second.

### 5.6 Hosting, storage and deploys (GCP)
- **Runtime:** one Docker image (API plus built static frontend) on
  **Cloud Run**.
  - Min instances 0 (free, with a few-second cold start).
  - A max-instances cap (e.g. 3).
  - CPU and memory sized so a 60 s clip analyzes in a few seconds.
  - Region `us-central1` (my call): it keeps Cloud Run and Cloud Storage
    inside GCP's always-free tiers. The extra network latency for India is
    small next to the analysis time.
- **Storage:** a private **Cloud Storage** bucket, with object versioning,
  holding the following. The Cloud Run service account is the only thing
  with access.
  - `examples/{id}/audio.*`
  - `examples/{id}/meta.json` (including the fingerprint)
  - `ragas/admin.json` and `kritis/admin.json`
  - `examples/{id}/melody.*` (tonic plus pitch contour, used for training)
  - `seed/…` (dataset melody lines)
  - `models/{version}/`: model weights, the tuned theory-matcher and
    combination parameters, `metrics.json`, and `fingerprints.*`
    (fingerprints for every example under this model)
  - a small `manifest.json` with the **active model version** and a
    **generation number** that changes on every admin write or model switch.
- **Keeping instances in sync:** on startup an instance loads the active
  model, its fingerprints and the admin tables into memory. Before each analysis it
  checks the manifest's generation (one tiny metadata read) and reloads
  only if it changed. An example added on one instance is therefore used by
  the very next analysis on any instance.
- **Training job:** a **Cloud Run Job** using the same Docker image with a
  training entrypoint. It is started by the API when the admin presses
  "Retrain", with a generous CPU and memory size and a timeout of about
  1 hour. Only the API's service account may start it.
- **Secrets:**
  - The admin password hash and the cookie-signing key live in **Secret
    Manager**, mounted into Cloud Run.
  - The bucket is reached through the service account's identity, with no
    key.
- **Deploys (GitHub Actions):**
  - On every push to `main`: run the tests, build the image, push it to
    **Artifact Registry**, and deploy it to both the Cloud Run service and
    the training job.
  - GitHub authenticates to GCP via **Workload Identity Federation**,
    limited to this repo and its `main` branch. A dedicated deployer
    service account has only the roles it needs.
  - Pull requests run the tests only.
  - An Artifact Registry cleanup policy keeps the last few images, so
    image storage stays at pennies.
- **One-time setup by the owner:** a short script plus instructions in
  `docs/deploy.md`, run in **Cloud Shell** while signed in with the GCP
  Google ID. It:
  - enables the APIs;
  - creates the bucket, Artifact Registry repo, training job, service
    accounts, Workload Identity pool/provider and secrets;
  - sets a budget alert (e.g. $5/month).

  The owner then adds the non-secret identifiers it prints (project ID,
  provider name, service account email) as GitHub repository variables.
- **Upgrade path:** set Cloud Run min instances to 1 for no cold starts
  (roughly $10–15/month at the chosen size), or raise CPU/memory. Only
  configuration changes, no code changes.
- Code in the `gopikasiva99/RaaGamaalika` GitHub repo.

### 5.7 Admin: teaching new ragas
- **Single admin:**
  - A password, stored as a hash in Secret Manager, giving a signed,
    HTTP-only session cookie. It is stateless, so it works across instances.
  - Login rate-limited.
  - No user management.
- **Each example stores:**
  - Original audio, kept private for playback and for re-extraction if the
    melody method changes.
  - Melody line (tonic plus pitch contour).
  - Fingerprint under the active model.
  - Raga ID, kind (singing/concert), **artist** ("Me" for the owner's
    singing), **recording group** (clips from one concert or session share
    it), detected shruti, duration, source
    (record/upload/YouTube/saved-result), note, and date added.
  - Artist and recording group drive graduation and the held-out test
    split (§5.9).
- **Effect is immediate:** the example is written to Cloud Storage,
  fingerprinted with the active model, and the manifest generation is
  bumped. The next analysis on any instance picks it up (§5.6). Retraining
  is never needed for an example to count.
- **Guardrails:**
  - When saving, show the detected swaras next to the chosen raga's
    arohana/avarohana, and warn if they disagree. This catches mislabels
    and bad shruti detection.
  - Melody gate applies: no example is saved from percussion or silence.
  - A suggested length of 30 s–3 min.
- **Re-extract all:** an admin action that rebuilds every melody line from
  stored audio if the melody-extraction method changes. A retrain follows.
  Re-fingerprinting after a retrain is automatic (§5.9).

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

### 5.9 Training and model lifecycle
- **What is trained** (one run produces one model version):
  - **The network:** a small model over tonic-normalized melody lines (or
    features derived from them), with two outputs:
    - a **classification head** over the trained ragas, and
    - an **embedding** used as the fingerprint.

    It is trained so that the embedding also separates ragas it has no
    classification head for. For example, classification loss is combined
    with a metric-learning loss, so few-example ragas benefit. The
    architecture is the builder's call, within the CPU limits in §3.
  - **The theory matcher's parameters:** swara-presence thresholds,
    penalties for missing or extra swaras, and the arohana/avarohana weight.
    These are fitted on the training split.
  - **The combination:** weights, the classifier threshold and the
    fingerprint margin, calibrated on a validation split so that the
    "confident ≥ 90% right" target (§7) holds.
- **Which ragas are "trained" (graduation):** a raga gets a classifier
  output once it has **≥ 10 recording groups from ≥ 3 different artists**.
  - These are my proposed defaults, configurable.
  - Clips from the same concert or session count as one recording group.
  - The owner's own singing counts as one artist, however many sessions
    there are.
  - All other ragas with examples are still recognized through fingerprint
    matching.
- **Data splits:** by recording group, never by clip.
  - A stable, deterministic assignment (e.g. a hash of the group ID) puts
    roughly 20% of groups into a held-out **test set**, for ragas with
    enough groups.
  - Test groups are never trained on, so scores stay comparable across
    versions.
  - Few-shot behaviour is measured by simulation: hold some trained ragas
    out of the classifier and score them through fingerprints only.
- **Running:**
  - The admin presses "Retrain", which starts the Cloud Run Job.
  - The job loads all melody lines (seed plus admin), trains, tunes the
    theory matcher and combination, and evaluates.
  - It then computes fingerprints for **every** example under the new
    model and writes everything to `models/{new_version}/`.
  - Progress is reported to the Training screen.
- **Promotion gate:** the new version is evaluated against the active one
  **on the same current test set**. It is auto-promoted only if it is
  no worse on:
  - trained-raga top-1,
  - few-shot top-3, and
  - confidence honesty.

  Otherwise it is kept but not promoted, and the admin can inspect the
  metrics and promote it anyway. Promotion and rollback just switch
  `manifest.json`; instances reload on their next request.
- **Model v0:** hand-crafted fingerprints with no classifier, plus
  default theory-matcher parameters. It ships with the first deploy so the
  app works immediately. The first training run (seed data only) produces
  v1.

## 6. Decisions

### Made with the owner
- Audience: rasikas identifying ragas from concerts, on phone and web.
- Personal project, shared with other rasikas.
- Cover all ragas: confident answers where examples allow, honest
  shortlists elsewhere.
- Input: both live recording and upload/YouTube.
- Full-concert timeline is Phase 2. Phase 1 is a single clip.
- Free hosting to start, upgrade if needed.
- Host on the owner's GCP account (a different Google ID), with **automatic deploys from GitHub** on merge to `main`.
- Approach A: Python server plus installable web app.
- Owner is the sole admin. Adds 1–5 examples per raga, both their own
  singing and concert clips, so that new ragas become recognizable.
- Kritis: names, composer, tala, and YouTube links. No lyrics.
- **Train a classifier and the theory matcher.** The owner will add as
  many examples as needed. Recognition engine **approach 5**: one trained
  model serving as classifier and fingerprint, plus a trained theory
  matcher, with admin-triggered retraining.

### Calls made in this design (owner can override)
- Graduation rule: ≥ 10 recording groups from ≥ 3 artists. Splits by
  recording group; ~20% held out for testing.
- Training as a CPU Cloud Run Job, ≤ ~1 h, started from the admin screen
  (not on a schedule).
- Auto-promotion only if no worse on the same test set, with manual
  override and rollback.
- Artist and recording-group fields on every example.
- "Save as example" from any result: the admin's browser re-sends the clip, and the server holds nothing.
- Cloud Run + private Cloud Storage bucket (versioned) + Secret Manager, region `us-central1`, max-instances cap, $5 budget alert.
- Workload Identity Federation for GitHub → GCP (no keys anywhere), with a one-time Cloud Shell setup script for the owner.
- Swara-mismatch warning when saving examples.
- Admin can add new ragas and edit kritis.
- No accounts, with history on the device.
- Users' audio is never stored.
- Manual shruti override, plus the automatic "Check the shruti?" prompt.
- Default live listening time ~45 s.
- Reference table target of ≥300 ragas.
- Success targets in §7.
- **Repo public on GitHub (open source).** This keeps Essentia (AGPL)
  usable. Secrets and admin audio are never in the repo.

## 7. Success criteria (Phase 1)
These are proposed targets, to be revised once real numbers exist.

- **Trained ragas, clean recordings** (held-out recording groups, 60 s
  clips), starting with the dataset ragas after the first training run (v1):
  - top-1 accuracy ≥ 80%
  - top-3 accuracy ≥ 95%
- **Few-shot ragas** (simulate admin use: for ragas held out of the
  classifier, keep 3 examples and test on other recordings): the true raga
  is in the top 3 ≥ 70% of the time. v1 should beat v0 here; if it doesn't,
  the learned fingerprint isn't working.
- **No-example ragas:** the true raga appears in the shortlist (top 5)
  ≥ 70% of the time.
- **Confidence honesty:** when the app says "confident", it is right ≥ 90%
  of the time on the test set. This is used to set the margin.
- **Admin flow:** an example added through the UI affects the very next
  analysis on any instance, and it survives instances scaling to zero.
- **Training flow:**
  - "Retrain" from the admin screen produces a new version with metrics in
    ≤ ~1 h.
  - A deliberately worse model is **not** auto-promoted.
  - Rolling back restores the previous version's results exactly.
  - A raga that crosses the graduation rule becomes a trained raga after
    the next retrain.
- **Real phone recordings:** a small personal test set of live hall clips,
  scored and reported separately. It is not gated in Phase 1, but it drives
  what to improve next.
- **Speed:** ≤ 10 s from upload to result for a 60 s clip on a warm free-tier
  server, with the full example store loaded.

## 8. Left to the builder
- Specific pitch and tonic tools, v0 fingerprint features, model
  architecture and losses, distance measure, per-raga aggregation, and the
  fitting method for theory and combination parameters, as long as §7 is
  met on CPU.
- Training hyperparameters, augmentation, and job CPU/memory sizing.
- Frontend framework, and visual design within the screens above.
- Source compilation for the raga and kriti seed tables.
- Exact Cloud Run CPU/memory sizing and cold-start optimisation (e.g. image size, lazy loading).
- Exact rate limits, upload caps and error copy.
- Test strategy and project layout.

## 9. Risks
- **Tonic errors on short or noisy clips** cascade into wrong answers and
  bad examples. Mitigations: the shruti check (§5.1), manual override, the
  swara-mismatch warning when saving, and the confidence gate.
- **Solo singing vs concert mismatch:** an example of the owner singing may
  match concert audio less well. Mitigations: predominant-melody extraction
  for both, the `kind` tag to compare, and coverage view nudges to add a
  concert clip per raga.
- **One example per raga** can make a raga look confident too easily.
  Mitigation: the confidence margin is calibrated with few-shot
  simulations, and it requires agreement from the theory matcher.
- **Mislabelled examples** silently poison results, and now training too.
  Mitigations: the mismatch warning, listen/delete in the coverage view,
  bucket version history, and the promotion gate.
- **Overfitting to artists or recording conditions**, which is very likely
  with a single owner's voice and a few favourite concerts. Mitigations:
  the ≥ 3-artist graduation rule, group-based splits, augmentation, and the
  owner's singing counting as one artist.
- **The test set shifts as examples are added**, so old metrics aren't
  comparable. Mitigation: always compare the candidate and active models on
  the *current* test set at promotion time.
- **Training cost or time grows** with the data. Mitigations: training on
  melody lines (not audio), a job timeout, and a budget alert. If the data
  outgrows CPU, a GPU job is a later configuration change, not a redesign.
- **Kriti data quality** (spellings, raga attributions vary between
  sources). Mitigations: alternate spellings, admin editing, and credited
  sources.
- **Violin shadowing and gamaka-heavy passages** can confuse swara
  detection. Mitigation: evaluate on real ensemble audio.
- **YouTube blocking** on cloud hosts. Mitigation: a graceful fallback to upload.
- **Cold starts** (scale to zero, plus a heavy audio image). Mitigations:
  a health-ping "waking up" UI, a lean image, and min-instances=1 as the
  upgrade path.
- **Surprise GCP bills.** Mitigations: a max-instances cap, a budget
  alert, rate limits, and an image cleanup policy.
- **Owner-only setup steps** (Cloud Shell, GitHub variables) can be done
  wrong and are hard to debug remotely. Mitigations: an idempotent setup
  script that prints exactly what to paste, and a smoke-test deploy as its
  own early milestone.
