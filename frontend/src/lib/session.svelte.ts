import { analyzeFile, analyzeYouTube, errorCopy } from './api'
import type { AnalysisResult } from './types'

export type Input =
  | { kind: 'file'; blob: Blob; filename: string; source: 'upload' | 'live' }
  | { kind: 'youtube'; url: string; start: number }

export const session = $state<{
  lastInput: Input | null
  lastResult: AnalysisResult | null
  busy: boolean
  error: string | null
}>({ lastInput: null, lastResult: null, busy: false, error: null })

type Listener = (r: AnalysisResult, input: Input) => void
const listeners: Listener[] = []
export function onResult(fn: Listener) {
  listeners.push(fn)
}

async function run(input: Input, shruti?: string): Promise<AnalysisResult | null> {
  session.busy = true
  session.error = null
  try {
    const r =
      input.kind === 'file'
        ? await analyzeFile(input.blob, input.filename, shruti)
        : await analyzeYouTube(input.url, input.start, shruti)
    session.lastInput = input
    session.lastResult = r
    listeners.forEach((fn) => fn(r, input))
    return r
  } catch (e) {
    session.error = errorCopy(e)
    return null
  } finally {
    session.busy = false
  }
}

export function startAnalysis(input: Input) {
  return run(input)
}

export function reanalyze(shruti?: string) {
  return session.lastInput ? run(session.lastInput, shruti) : Promise.resolve(null)
}
