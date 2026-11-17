<script lang="ts">
  import { swaraLabel } from '../lib/notes'
  let { strengths, raga }: { strengths: number[]; raga?: { arohana: string[]; avarohana: string[] } } = $props()
</script>

<div class="bars" aria-label="Swaras heard">
  {#each strengths as s, i}
    {@const label = swaraLabel(i, raga)}
    <div class="bar">
      <div class="track"><div class="fill" style="height: {Math.round(Math.max(0, Math.min(1, s)) * 100)}%" aria-label="{label} strength" role="img"></div></div>
      <span>{label}</span>
    </div>
  {/each}
</div>

<style>
  .bars { display: grid; grid-template-columns: repeat(12, 1fr); gap: 0.25rem; align-items: end; }
  .bar { display: flex; flex-direction: column; align-items: center; gap: 0.2rem; }
  .track { height: 3.5rem; width: 100%; background: var(--soft); border-radius: 0.3rem; display: flex; align-items: flex-end; overflow: hidden; }
  .fill { width: 100%; background: var(--accent); border-radius: 0.3rem; }
  span { font-size: 0.65rem; color: var(--muted); }
</style>
