// Synthetic Mohanam clip (harmonic tones + tanpura-like drone) as a 16-bit mono WAV buffer.
const SR = 22050

export function mohanamWav(seconds = 30, tonic = 146.8): Buffer {
  const semis = [0, 2, 4, 7, 9]
  const up = [...semis, ...semis.map((s) => s + 12), 24]
  const seq = [...up, ...up.slice(1, -1).reverse()]
  const n = seconds * SR
  const note = Math.floor(0.5 * SR)
  const pcm = new Float32Array(n)
  let phase = 0
  for (let i = 0; i < n; i++) {
    const f = tonic * 2 ** (seq[Math.floor(i / note) % seq.length] / 12)
    phase += (2 * Math.PI * f) / SR
    let s = 0
    for (let k = 1; k <= 5; k++) s += Math.sin(k * phase) / k
    const t = i / SR
    let d = 0
    for (const f0 of [tonic / 2, (tonic * 2 ** (7 / 12)) / 2, tonic, tonic * 2])
      for (let k = 1; k <= 8; k++) d += Math.sin(2 * Math.PI * f0 * k * t) / k
    pcm[i] = 0.25 * s + 0.04 * d
  }
  let peak = 0
  for (const v of pcm) peak = Math.max(peak, Math.abs(v))
  const buf = Buffer.alloc(44 + n * 2)
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write('WAVE', 8); buf.write('fmt ', 12)
  buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(SR, 24)
  buf.writeUInt32LE(SR * 2, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36)
  buf.writeUInt32LE(n * 2, 40)
  for (let i = 0; i < n; i++) buf.writeInt16LE(Math.round((0.8 * pcm[i] / peak) * 32767), 44 + i * 2)
  return buf
}
