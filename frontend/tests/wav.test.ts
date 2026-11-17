import { expect, test } from 'vitest'
import { downsample, encodeWav } from '../src/lib/wav'

test('encodeWav writes a valid RIFF header and length', async () => {
  const pcm = new Float32Array([0, 0.5, -0.5, 1, -1])
  const blob = encodeWav(pcm, 22050)
  const buf = new DataView(await blob.arrayBuffer())
  const text = (o: number) => String.fromCharCode(...[0, 1, 2, 3].map((i) => buf.getUint8(o + i)))
  expect(text(0)).toBe('RIFF')
  expect(text(8)).toBe('WAVE')
  expect(buf.getUint16(22, true)).toBe(1) // mono
  expect(buf.getUint32(24, true)).toBe(22050)
  expect(buf.getUint16(34, true)).toBe(16)
  expect(text(36)).toBe('data')
  expect(buf.getUint32(40, true)).toBe(2 * pcm.length)
  expect(blob.size).toBe(44 + 2 * pcm.length)
  expect(buf.getInt16(44 + 2 * 3, true)).toBe(32767)
  expect(blob.type).toBe('audio/wav')
})

test('downsample 44100→22050 halves length and keeps a constant signal', () => {
  const out = downsample(new Float32Array(44100).fill(0.25), 44100, 22050)
  expect(out.length).toBe(22050)
  expect(out[100]).toBeCloseTo(0.25)
})

test('downsample is a no-op at the same rate', () => {
  const pcm = new Float32Array([1, 2, 3])
  expect(downsample(pcm, 22050, 22050)).toBe(pcm)
})
