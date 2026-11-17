<script lang="ts">
  import Home from './routes/Home.svelte'
  import Listen from './routes/Listen.svelte'
  import { createRecorder, type Recorder } from './lib/recorder'
  import RagaDetail from './routes/RagaDetail.svelte'
  import Result from './routes/Result.svelte'
  import { reanalyze, session, startAnalysis } from './lib/session.svelte'

  let hash = $state(location.hash || '#/')
  addEventListener('hashchange', () => (hash = location.hash || '#/'))
  const go = (h: string) => (location.hash = h)

  const route = $derived(hash.replace(/^#/, '').split('/').filter(Boolean))

  let liveRecorder = $state<Recorder | null>(null)
  let resumeRecorder = $state<Recorder | null>(null)

  function dropLive() {
    liveRecorder?.close()
    liveRecorder = null
  }

  async function analyzeUpload(file: File) {
    dropLive()
    if (await startAnalysis({ kind: 'file', blob: file, filename: file.name || 'upload', source: 'upload' })) go('#/result')
  }
  async function analyzeLink(url: string, start: number) {
    dropLive()
    if (await startAnalysis({ kind: 'youtube', url, start })) go('#/result')
  }
</script>

<header>
  <a href="#/" class="brand">RaaGamaalika</a>
</header>

<main>
  {#if session.error}
    <div class="error" role="alert">{session.error}</div>
  {/if}
  {#if session.busy}
    <div class="busy" role="status">Identifying the raga…</div>
  {/if}

  {#if route[0] === 'listen'}
    {#key hash}
      <Listen
        {createRecorder}
        resume={route[1] === 'more' ? resumeRecorder : null}
        onResult={(_r, rec) => { liveRecorder = rec; resumeRecorder = null; go('#/result') }}
      />
    {/key}
  {:else if route[0] === 'result' && session.lastResult}
    <Result
      result={session.lastResult}
      onShruti={(n) => reanalyze(n)}
      onRetry={() => { dropLive(); go(session.lastInput?.kind === 'file' && session.lastInput.source === 'live' ? '#/listen' : '#/') }}
      onKeepListening={liveRecorder && session.lastInput?.kind === 'file' && session.lastInput.source === 'live'
        ? () => { resumeRecorder = liveRecorder; go('#/listen/more') }
        : undefined}
    />
  {:else if route[0] === 'raga' && route[1]}
    <RagaDetail id={decodeURIComponent(route[1])} />
  {:else}
    <Home busy={session.busy} onFile={analyzeUpload} onYouTube={analyzeLink} />
  {/if}
</main>

<style>
  header { padding: 0.9rem 1rem; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; }
  .brand { font-weight: 800; letter-spacing: 0.02em; text-decoration: none; color: var(--accent); font-size: 1.15rem; }
  main { max-width: 34rem; margin: 0 auto; padding: 1rem; display: grid; gap: 1rem; }
  .error { background: #fde8e4; color: #7a1f12; border-radius: 0.7rem; padding: 0.7rem 0.9rem; }
  .busy { background: var(--soft); border-radius: 0.7rem; padding: 0.7rem 0.9rem; }
</style>
