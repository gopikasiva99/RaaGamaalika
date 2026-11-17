<script lang="ts">
  import { clearHistory, listHistory } from '../lib/history'
  import type { AnalysisResult } from '../lib/types'

  let { onOpen }: { onOpen: (r: AnalysisResult) => void } = $props()
  let entries = $state(listHistory())

  function summary(r: AnalysisResult): string {
    if (r.kind === 'no_melody') return 'No melody detected'
    const names = r.candidates.slice(0, r.kind === 'confident' ? 1 : 3).map((c) => c.name)
    return r.kind === 'confident' ? names[0] : `Likely one of ${names.join(', ')}`
  }
  const when = (iso: string) => new Date(iso).toLocaleString()
</script>

<section>
  <h1>Recent</h1>
  {#if entries.length === 0}
    <p class="muted">Nothing yet. Results you get are kept on this device only.</p>
  {:else}
    <ul>
      {#each entries as e}
        <li>
          <button onclick={() => onOpen(e.result)}>
            <strong>{summary(e.result)}</strong>
            <small>{when(e.at)} · {e.source} · {e.label}</small>
          </button>
        </li>
      {/each}
    </ul>
    <button class="link" onclick={() => { clearHistory(); entries = [] }}>Clear history</button>
  {/if}
</section>

<style>
  h1 { margin: 0 0 0.6rem; }
  ul { list-style: none; padding: 0; display: grid; gap: 0.5rem; }
  li button { width: 100%; text-align: left; display: grid; gap: 0.2rem; }
  small, .muted { color: var(--muted); }
</style>
