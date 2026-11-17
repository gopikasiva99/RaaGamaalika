/** Box-filter downsampling (good enough for 44.1/48 kHz → 22.05 kHz speech/music analysis). */
export function downsample(pcm: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return pcm
  const ratio = fromRate / toRate
  const n = Math.floor(pcm.length / ratio)
  const out = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * ratio)
    const b = Math.min(pcm.length, Math.max(a + 1, Math.floor((i + 1) * ratio)))
    let sum = 0
    for (let j = a; j < b; j++) sum += pcm[j]
    out[i] = sum / (b - a)
  }
  return out
}

/** 16-bit PCM mono WAV. */
export function encodeWav(pcm: Float32Array, sampleRate: number): Blob {
  const buf = new ArrayBuffer(44 + pcm.length * 2)
  const v = new DataView(buf)
  const str = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)))
  str(0, 'RIFF')
  v.setUint32(4, 36 + pcm.length * 2, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  v.setUint32(16, 16, true)
  v.setUint16(20, 1, true) // PCM
  v.setUint16(22, 1, true) // mono
  v.setUint32(24, sampleRate, true)
  v.setUint32(28, sampleRate * 2, true)
  v.setUint16(32, 2, true)
  v.setUint16(34, 16, true)
  str(36, 'data')
  v.setUint32(40, pcm.length * 2, true)
  for (let i = 0; i < pcm.length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]))
    v.setInt16(44 + i * 2, s < 0 ? Math.round(s * 32768) : Math.round(s * 32767), true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}
