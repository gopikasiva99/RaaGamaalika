<script lang="ts">
  import { errorCopy, getRaga } from '../lib/api'
  import { formatScale } from '../lib/notes'
  import type { RagaDetail } from '../lib/types'

  let { id }: { id: string } = $props()
  let raga = $state<RagaDetail | null>(null)
  let error = $state<string | null>(null)

  $effect(() => {
    raga = null
    error = null
    getRaga(id).then((r) => (raga = r)).catch((e) => (error = e?.code === 'not_found' ? 'Raga not found.' : errorCopy(e)))
  })
</script>

{#if error}
  <p>{error}</p>
{:else if !raga}
  <p class="muted">Loading…</p>
{:else}
  <article class="raga">
    <h1>{raga.name}</h1>
    <p class="muted">
      {raga.melakarta !== null ? `Melakarta ${raga.melakarta}` : `Janya of melakarta ${raga.parent}`}
      {raga.vakra ? ' · vakra' : ''}{raga.bhashanga ? ' · bhashanga' : ''}
    </p>
    <dl>
      <dt>Arohana</dt><dd>{formatScale(raga.arohana)}</dd>
      <dt>Avarohana</dt><dd>{formatScale(raga.avarohana)}</dd>
      {#if raga.aliases.length}<dt>Also known as</dt><dd>{raga.aliases.join(', ')}</dd>{/if}
      <dt>Example recordings</dt><dd>{raga.example_count}</dd>
    </dl>
  </article>
{/if}

<style>
  h1 { margin: 0; }
  .muted { color: var(--muted); }
  dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.4rem 1rem; }
  dt { color: var(--muted); }
  dd { margin: 0; font-family: ui-monospace, monospace; }
</style>
