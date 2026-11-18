import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { waitForServer } from '../src/lib/api'

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('waitForServer calls onSlow once after 2s then resolves on ok', async () => {
  let up = false
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async () =>
    up ? new Response(JSON.stringify({ ok: true })) : Promise.reject(new TypeError('down'))))
  const onSlow = vi.fn()
  let done = false
  const p = waitForServer(onSlow).then(() => (done = true))
  await vi.advanceTimersByTimeAsync(1600)
  expect(onSlow).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1600)
  expect(onSlow).toHaveBeenCalledTimes(1)
  up = true
  await vi.advanceTimersByTimeAsync(1600)
  await p
  expect(done).toBe(true)
  expect(onSlow).toHaveBeenCalledTimes(1)
})

test('waitForServer resolves immediately when the server is up', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }))))
  const onSlow = vi.fn()
  await waitForServer(onSlow)
  expect(onSlow).not.toHaveBeenCalled()
})

test('waitForServer rejects with network after the timeout', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')))
  const p = waitForServer(() => {}, 2000, 6000).catch((e) => e)
  await vi.advanceTimersByTimeAsync(7000)
  expect(await p).toMatchObject({ code: 'network' })
})
