import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { Recorder } from '../src/lib/recorder'
import Listen from '../src/routes/Listen.svelte'
import { result } from './fixtures'

let secs = 0
let fetchFn: ReturnType<typeof vi.fn>

function fakeRecorder(): Recorder {
  return {
    start: vi.fn(), pause: vi.fn(), close: vi.fn(),
    level: () => 0.3,
    seconds: () => secs,
    toWav: () => new Blob(['RIFF'], { type: 'audio/wav' }),
  }
}

beforeEach(() => {
  secs = 0
  vi.useFakeTimers()
  fetchFn = vi.fn().mockImplementation(async () => new Response(JSON.stringify(result())))
  vi.stubGlobal('fetch', fetchFn)
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('explains before asking for the microphone', () => {
  render(Listen, { createRecorder: async () => fakeRecorder(), onResult: () => {} })
  expect(screen.getByText("We'll listen for about 45 seconds. Audio is analysed and never stored.")).toBeInTheDocument()
})

test('stopping before 10s shows too-short message and does not call the API', async () => {
  render(Listen, { createRecorder: async () => fakeRecorder(), onResult: () => {} })
  await fireEvent.click(screen.getByRole('button', { name: 'Start listening' }))
  secs = 6
  await vi.advanceTimersByTimeAsync(500)
  await fireEvent.click(screen.getByRole('button', { name: 'Stop & identify' }))
  expect(screen.getByText('That was too short — record at least 10 seconds.')).toBeInTheDocument()
  expect(fetchFn).not.toHaveBeenCalled()
})

test('auto-stops at 45s and posts live.wav', async () => {
  const onResult = vi.fn()
  render(Listen, { createRecorder: async () => fakeRecorder(), onResult })
  await fireEvent.click(screen.getByRole('button', { name: 'Start listening' }))
  secs = 45
  await vi.advanceTimersByTimeAsync(500)
  const analyzeCall = () => fetchFn.mock.calls.find((c) => c[0] === '/api/analyze')
  await waitFor(() => expect(analyzeCall()).toBeDefined())
  const fd = analyzeCall()![1].body as FormData
  expect((fd.get('file') as File).name).toBe('live.wav')
  await waitFor(() => expect(onResult).toHaveBeenCalled())
})

test('permission denied shows upload fallback', async () => {
  const denied = Object.assign(new Error('denied'), { name: 'NotAllowedError' })
  render(Listen, { createRecorder: () => Promise.reject(denied), onResult: () => {} })
  await fireEvent.click(screen.getByRole('button', { name: 'Start listening' }))
  await waitFor(() =>
    expect(screen.getByText('Microphone access is needed to listen. You can upload a recording instead.')).toBeInTheDocument())
  expect(screen.getByRole('link', { name: 'Upload a recording' })).toHaveAttribute('href', '#/')
})

test('keep listening resumes the same recorder for 30 more seconds', async () => {
  const rec = fakeRecorder()
  secs = 45
  render(Listen, { createRecorder: async () => rec, onResult: () => {}, resume: rec })
  expect(rec.start).toHaveBeenCalled()
  secs = 60
  await vi.advanceTimersByTimeAsync(500)
  expect(fetchFn).not.toHaveBeenCalled()
  secs = 75
  await vi.advanceTimersByTimeAsync(500)
  await waitFor(() => expect(fetchFn).toHaveBeenCalled())
})
