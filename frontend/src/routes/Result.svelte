<script lang="ts">
  import CandidateList from '../components/CandidateList.svelte'
  import ShrutiPicker from '../components/ShrutiPicker.svelte'
  import SwaraBars from '../components/SwaraBars.svelte'
  import { formatScale } from '../lib/notes'
  import type { AnalysisResult } from '../lib/types'

  let {
    result,
    onShruti,
    onRetry,
    onKeepListening,
  }: {
    result: AnalysisResult
    onShruti: (note: string) => void
    onRetry: () => void
    onKeepListening?: () => void
  } = $props()

  let editing = $state(false)
  const top = $derived(result.candidates[0])
  const rest = $derived(result.candidates.slice(1))
</script>

<section class="result">
  {#if result.kind === 'no_melody'}
    <h1 class="title">No melody detected — keep listening</h1>
    <p class="muted">We couldn't hear a clear lead melody. Try a passage with singing or a melodic instrument.</p>
    <div class="actions">
      {#if onKeepListening}<button class="primary" onclick={onKeepListening}>Keep listening</button>{/if}
      <button onclick={onRetry}>Try again</button>
    </div>
  {:else}
    {#if result.shruti_suspect}
      <div class="banner" role="alert">
        <strong>Check the shruti?</strong>
        <p>The swaras fit much better if Sa is {result.shruti_suspect.suggested_note}.</p>
        <div class="actions">
          <button class="primary" onclick={() => onShruti(result.shruti_suspect!.suggested_note)}>
            Use {result.shruti_suspect.suggested_note}
          </button>
          <button onclick={() => (editing = true)}>Pick manually</button>
        </div>
      </div>
    {/if}

    {#if result.kind === 'confident' && top}
      <div class="hero">
        <h1 class="title">{top.name}</h1>
        <span class="big">{top.percent}%</span>
      </div>
      <p class="muted">
        {top.melakarta !== null ? `Melakarta ${top.melakarta}` : `Janya of melakarta ${top.parent}`}
      </p>
      <p class="scale">{formatScale(top.arohana)}<br />{formatScale(top.avarohana)}</p>
      <p><a href="#/raga/{top.raga_id}">About this raga →</a></p>
      {#if rest.length}
        <h2>Also possible:</h2>
        <CandidateList candidates={rest} />
      {/if}
    {:else}
      <h1 class="title">Likely one of…</h1>
      <CandidateList candidates={result.candidates} />
    {/if}

    <div class="shruti">
      <span>Detected shruti: <strong>{result.tonic_note ?? '—'}</strong></span>
      <button class="link" aria-label="Edit shruti" onclick={() => (editing = !editing)}>[edit]</button>
    </div>
    {#if editing}
      <ShrutiPicker current={result.tonic_note} onPick={(n) => { editing = false; onShruti(n) }} />
    {/if}

    <h2>Swaras heard</h2>
    <SwaraBars strengths={result.swara_strengths} raga={top} />

    {#if onKeepListening && result.kind !== 'confident'}
      <div class="actions"><button class="primary" onclick={onKeepListening}>Keep listening</button></div>
    {/if}
  {/if}
</section>

<style>
  .result { display: grid; gap: 0.8rem; }
  .hero { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; }
  .title { margin: 0; font-size: 1.9rem; }
  .big { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
  .muted { color: var(--muted); margin: 0; }
  .scale { font-family: ui-monospace, monospace; margin: 0; line-height: 1.6; }
  h2 { font-size: 1rem; margin: 0.6rem 0 0; }
  .banner { background: var(--warn-bg); border: 1px solid var(--warn); border-radius: 0.75rem; padding: 0.8rem; }
  .banner p { margin: 0.3rem 0 0.6rem; }
  .shruti { display: flex; gap: 0.5rem; align-items: center; }
  .actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
</style>
