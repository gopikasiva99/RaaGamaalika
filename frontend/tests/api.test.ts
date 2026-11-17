import { afterEach, describe, expect, test, vi } from 'vitest'
import { analyzeFile, analyzeYouTube, ApiError, getRaga, searchRagas } from '../src/lib/api'
import { result } from './fixtures'

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  test('analyzeFile posts multipart and returns result', async () => {
    const fn = mockFetch(200, result())
    const r = await analyzeFile(new Blob(['x']), 'a.wav', 'C#')
    expect(r.candidates[0].name).toBe('Mohanam')
    const [url, init] = fn.mock.calls[0]
    expect(url).toBe('/api/analyze')
    expect(init.method).toBe('POST')
    const fd = init.body as FormData
    expect(fd.get('shruti')).toBe('C#')
    expect((fd.get('file') as File).name).toBe('a.wav')
  })

  test('error codes become ApiError with code', async () => {
    mockFetch(422, { error: 'too_short' })
    await expect(analyzeFile(new Blob(['x']), 'a.wav')).rejects.toMatchObject({ status: 422, code: 'too_short' })
  })

  test('network failure becomes ApiError network', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const err = await analyzeFile(new Blob(['x']), 'a.wav').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.code).toBe('network')
  })

  test('analyzeYouTube posts JSON', async () => {
    const fn = mockFetch(200, result())
    await analyzeYouTube('https://youtu.be/x', 90)
    const [url, init] = fn.mock.calls[0]
    expect(url).toBe('/api/analyze/youtube')
    expect(JSON.parse(init.body)).toEqual({ url: 'https://youtu.be/x', start: 90 })
  })

  test('searchRagas and getRaga', async () => {
    const fn = mockFetch(200, [{ id: 'mohanam', name: 'Mohanam', melakarta: null, parent: 28 }])
    expect((await searchRagas('moh'))[0].id).toBe('mohanam')
    expect(fn.mock.calls[0][0]).toBe('/api/ragas?q=moh')
    mockFetch(404, { error: 'not_found' })
    await expect(getRaga('zzz')).rejects.toMatchObject({ code: 'not_found' })
  })
})
