<script lang="ts">
  let {
    busy,
    onFile,
    onYouTube,
  }: {
    busy: boolean
    onFile: (file: File) => void
    onYouTube: (url: string, start: number) => void
  } = $props()

  let url = $state('')
  let start = $state('')
  let fileInput: HTMLInputElement

  function parseStart(s: string): number {
    const parts = s.trim().split(':').map(Number)
    if (parts.some((n) => Number.isNaN(n))) return 0
    return parts.reduce((acc, n) => acc * 60 + n, 0)
  }
</script>

<section class="home">
  <p class="lead">Which raga is this? Listen live, upload a recording, or paste a YouTube link.</p>

  <a class="action primary" href="#/listen">
    <span class="icon" aria-hidden="true">🎙️</span>
    <span><strong>Listen</strong><br /><small>Hold your phone up in the hall</small></span>
  </a>

  <button class="action" disabled={busy} onclick={() => fileInput.click()}>
    <span class="icon" aria-hidden="true">📁</span>
    <span><strong>Upload</strong><br /><small>Audio or video file</small></span>
  </button>
  <input bind:this={fileInput} class="sr-only" type="file" accept="audio/*,video/*" aria-label="Upload a recording"
    onchange={(e) => { const f = (e.currentTarget as HTMLInputElement).files?.[0]; if (f) onFile(f) }} />

  <form class="action yt" onsubmit={(e) => { e.preventDefault(); if (url.trim()) onYouTube(url.trim(), parseStart(start)) }}>
    <span class="icon" aria-hidden="true">▶️</span>
    <div class="fields">
      <strong>YouTube link</strong>
      <input type="url" placeholder="https://youtu.be/…" bind:value={url} aria-label="YouTube link" required />
      <div class="row">
        <input type="text" inputmode="numeric" placeholder="Start at mm:ss (optional)" bind:value={start} aria-label="Start time" />
        <button class="primary" type="submit" disabled={busy}>Identify</button>
      </div>
    </div>
  </form>
</section>

<style>
  .home { display: grid; gap: 0.8rem; }
  .lead { color: var(--muted); margin: 0 0 0.4rem; }
  .action {
    display: flex; gap: 0.9rem; align-items: center; text-align: left; padding: 1rem;
    border-radius: 1rem; border: 1px solid var(--line); background: var(--card); text-decoration: none; color: inherit; width: 100%;
  }
  .action.primary { background: var(--accent); color: white; border-color: var(--accent); }
  .action small { opacity: 0.8; }
  .icon { font-size: 1.6rem; }
  .yt { align-items: flex-start; }
  .fields { display: grid; gap: 0.5rem; flex: 1; }
  .row { display: flex; gap: 0.5rem; }
</style>
