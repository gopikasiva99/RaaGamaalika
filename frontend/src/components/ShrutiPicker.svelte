<script lang="ts">
  import { NOTE_NAMES } from '../lib/notes'
  let { current, onPick }: { current: string | null; onPick: (note: string) => void } = $props()
</script>

<div class="picker" role="group" aria-label="Choose shruti">
  {#each NOTE_NAMES as note}
    <button class:current={note === current} onclick={() => onPick(note)}>{note}</button>
  {/each}
</div>

<style>
  .picker { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.4rem; margin-top: 0.6rem; }
  button { padding: 0.55rem 0; border-radius: 0.5rem; border: 1px solid var(--line); background: var(--card); font-weight: 600; }
  .current { background: var(--accent); color: white; border-color: var(--accent); }
</style>
