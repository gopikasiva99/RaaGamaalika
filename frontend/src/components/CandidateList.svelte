<script lang="ts">
  import type { Candidate } from '../lib/types'
  import { formatScale } from '../lib/notes'
  let { candidates }: { candidates: Candidate[] } = $props()
  const grouped = $derived(candidates.some((c) => c.group !== null))
</script>

<ul class="list">
  {#each candidates as c}
    <li class:grouped={c.group !== null}>
      <a href="#/raga/{c.raga_id}">
        <span class="name">{c.name}</span>
        <span class="pct">{c.percent}%</span>
      </a>
      <span class="scale">{formatScale(c.arohana)} · {formatScale(c.avarohana)}</span>
    </li>
  {/each}
</ul>
{#if grouped}
  <p class="note">These ragas share the same swaras</p>
{/if}

<style>
  .list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.5rem; }
  li { background: var(--card); border: 1px solid var(--line); border-radius: 0.75rem; padding: 0.7rem 0.9rem; }
  li.grouped { border-left: 4px solid var(--accent-soft); }
  a { display: flex; justify-content: space-between; text-decoration: none; color: inherit; }
  .name { font-weight: 600; }
  .pct { color: var(--muted); }
  .scale { display: block; font-size: 0.8rem; color: var(--muted); margin-top: 0.2rem; }
  .note { font-size: 0.85rem; color: var(--muted); margin: 0.4rem 0 0; }
</style>
