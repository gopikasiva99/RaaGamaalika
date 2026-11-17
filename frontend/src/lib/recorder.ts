import workletUrl from './recorder-worklet.js?url'
import { downsample, encodeWav } from './wav'

export const MAX_SECONDS = 120
export const UPLOAD_RATE = 22050

export interface Recorder {
  start(): void
  pause(): void
  level(): number // 0..1 RMS of the latest batch
  seconds(): number // captured audio so far
  toWav(): Blob
  close(): void
}

const CONSTRAINTS: MediaStreamConstraints = {
  audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
}

/**
 * Captures mono PCM across start()/pause() cycles. The microphone is released
 * on pause() (so the mic indicator turns off while the result is shown) and
 * re-acquired on the next start(); captured audio keeps accumulating.
 */
export async function createRecorder(): Promise<Recorder> {
  let stream: MediaStream | null = await navigator.mediaDevices.getUserMedia(CONSTRAINTS)
  const ctx = new AudioContext()
  await ctx.audioWorklet.addModule(workletUrl)
  const node = new AudioWorkletNode(ctx, 'pcm-capture')
  const mute = ctx.createGain()
  mute.gain.value = 0
  node.connect(mute).connect(ctx.destination) // keeps the worklet running in all browsers
  let source: MediaStreamAudioSourceNode | null = ctx.createMediaStreamSource(stream)
  source.connect(node)

  const chunks: Float32Array[] = []
  let total = 0
  let recording = false
  let lastLevel = 0
  const cap = MAX_SECONDS * ctx.sampleRate

  node.port.onmessage = (e: MessageEvent<Float32Array>) => {
    const b = e.data
    let sq = 0
    for (let i = 0; i < b.length; i++) sq += b[i] * b[i]
    lastLevel = Math.min(1, Math.sqrt(sq / b.length) * 4)
    if (recording && total < cap) {
      chunks.push(b)
      total += b.length
    }
  }

  function release() {
    source?.disconnect()
    source = null
    stream?.getTracks().forEach((t) => t.stop())
    stream = null
  }

  return {
    start() {
      recording = true
      void ctx.resume()
      if (!stream) {
        void navigator.mediaDevices.getUserMedia(CONSTRAINTS).then((s) => {
          stream = s
          source = ctx.createMediaStreamSource(s)
          source.connect(node)
        })
      }
    },
    pause() {
      recording = false
      release()
    },
    level: () => lastLevel,
    seconds: () => total / ctx.sampleRate,
    toWav() {
      const all = new Float32Array(total)
      let o = 0
      for (const c of chunks) {
        all.set(c.subarray(0, Math.min(c.length, total - o)), o)
        o += c.length
        if (o >= total) break
      }
      return encodeWav(downsample(all, ctx.sampleRate, UPLOAD_RATE), UPLOAD_RATE)
    },
    close() {
      recording = false
      release()
      void ctx.close()
    },
  }
}
