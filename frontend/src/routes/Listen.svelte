<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import { ERROR_COPY } from '../lib/api'
  import { MAX_SECONDS, type Recorder } from '../lib/recorder'
  import { startAnalysis } from '../lib/session.svelte'
  import type { AnalysisResult } from '../lib/types'

  const FIRST_LISTEN_S = 45
  const KEEP_LISTENING_S = 30
  const MIN_S = 10

  let {
    createRecorder,
    onResult,
    resume,
  }: {
    createRecorder: () => Promise<Recorder>
    onResult: (r: AnalysisResult, rec: Recorder) => void
    resume?: Recorder | null
  } = $props()

  let phase = $state<'intro' | 'recording' | 'analysing' | 'denied'>('intro')
  let rec = $state<Recorder | null>(null)
  let elapsed = $state(0)
  let level = $state(0)
  let target = $state(FIRST_LISTEN_S)
  let message = $state<string | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null

  function tick() {
    if (!rec) return
    elapsed = rec.seconds()
    level = rec.level()
    if (elapsed >= target || elapsed >= MAX_SECONDS) void finish()
  }

  let handedOff = false

  async function record(r: Recorder, forSeconds: number) {
    rec = r
    target = Math.min(MAX_SECONDS, r.seconds() + forSeconds)
    message = null
    phase = 'recording'
    try {
      await r.start()
    } catch {
      phase = 'denied'
      return
    }
    timer ??= setInterval(tick, 250)
  }

  async function begin() {
    try {
      await record(await createRecorder(), FIRST_LISTEN_S)
    } catch (e) {
      phase = 'denied'
    }
  }

  async function finish() {
    if (!rec || phase !== 'recording') return
    rec.pause()
    if (timer) clearInterval(timer)
    timer = null
    if (rec.seconds() < MIN_S) {
      message = ERROR_COPY.too_short
      phase = 'intro'
      return
    }
    phase = 'analysing'
    const r = await startAnalysis({ kind: 'file', blob: rec.toWav(), filename: 'live.wav', source: 'live' })
    if (r) {
      handedOff = true // the result screen owns it now (for "Keep listening")
      onResult(r, rec)
    } else phase = 'intro'
  }

  onMount(() => {
    if (resume) void record(resume, KEEP_LISTENING_S)
  })

  onDestroy(() => {
    if (timer) clearInterval(timer)
    if (rec && !handedOff) rec.close() // leaving mid-recording: release the microphone
  })

  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
</script>

<section class="listen">
  {#if phase === 'denied'}
    <p>Microphone access is needed to listen. You can upload a recording instead.</p>
    <a class="button" href="#/">Upload a recording</a>
  {:else if phase === 'recording'}
    <p class="timer" aria-live="polite">{mmss(elapsed)} / {mmss(target)}</p>
    <div class="meter" aria-hidden="true"><div style="width: {Math.round(level * 100)}%"></div></div>
    <p class="muted">Listening… hold the phone towards the stage.</p>
    <button class="primary" onclick={finish}>Stop & identify</button>
  {:else if phase === 'analysing'}
    <p role="status">Identifying the raga…</p>
  {:else}
    <p>We'll listen for about 45 seconds. Audio is analysed and never stored.</p>
    {#if message}<p class="warn" role="alert">{message}</p>{/if}
    <button class="primary" onclick={() => (rec && message ? void record(rec, FIRST_LISTEN_S) : begin())}>
      {rec && message ? 'Keep recording' : 'Start listening'}
    </button>
  {/if}
</section>

<style>
  .listen { display: grid; gap: 0.9rem; text-align: center; padding-top: 1rem; }
  .timer { font-size: 2.6rem; font-weight: 700; margin: 0; font-variant-numeric: tabular-nums; }
  .meter { height: 0.6rem; background: var(--soft); border-radius: 1rem; overflow: hidden; }
  .meter div { height: 100%; background: var(--accent); transition: width 0.2s; }
  .muted { color: var(--muted); }
  .warn { color: var(--warn); }
  .button { display: inline-block; padding: 0.6rem 1rem; border-radius: 0.7rem; border: 1px solid var(--line); text-decoration: none; }
</style>
