import { afterEach, expect, test, vi } from 'vitest'
import { reanalyze, session, startAnalysis } from '../src/lib/session.svelte'
import { result } from './fixtures'

afterEach(() => vi.unstubAllGlobals())

test('reanalyze re-sends the last file with the chosen shruti', async () => {
  const fn = vi.fn().mockImplementation(async () => new Response(JSON.stringify(result())))
  vi.stubGlobal('fetch', fn)
  await startAnalysis({ kind: 'file', blob: new Blob(['x']), filename: 'clip.m4a', source: 'upload' })
  expect(session.lastResult?.candidates[0].name).toBe('Mohanam')
  await reanalyze('C#')
  const analyzeCalls = fn.mock.calls.filter((c) => c[0] === '/api/analyze')
  expect(analyzeCalls).toHaveLength(2)
  expect(fn.mock.calls[0][0]).toBe('/api/health') // waits for the server first (cold starts)
  const fd = analyzeCalls[1][1].body as FormData
  expect(fd.get('shruti')).toBe('C#')
  expect((fd.get('file') as File).name).toBe('clip.m4a')
})

test('errors are exposed as friendly copy', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: 'youtube_blocked' }), { status: 502 })))
  await startAnalysis({ kind: 'youtube', url: 'https://youtu.be/x', start: 0 })
  expect(session.error).toBe("YouTube didn't let us fetch that video. Please upload the file instead.")
})
