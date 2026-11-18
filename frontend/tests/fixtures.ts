import type { AnalysisResult, Candidate } from '../src/lib/types'

export function cand(name: string, over: Partial<Candidate> = {}): Candidate {
  return {
    raga_id: name.toLowerCase(), name, melakarta: null, parent: 28,
    arohana: ['S', 'R2', 'G3', 'P', 'D2', 'S'], avarohana: ['S', 'D2', 'P', 'G3', 'R2', 'S'],
    score: 0.5, percent: 20, group: null, ...over,
  }
}

export function result(over: Partial<AnalysisResult> = {}): AnalysisResult {
  return {
    kind: 'confident',
    candidates: [cand('Mohanam', { percent: 70 }), cand('Bilahari', { percent: 30, parent: 29 })],
    tonic_hz: 138.6, tonic_note: 'C#', shruti_suspect: null,
    swara_strengths: [1, 0, 0.8, 0, 0.7, 0, 0, 0.9, 0, 0.6, 0, 0],
    voiced_seconds: 30, model_version: 'v0', processing_ms: 1200, ...over,
  }
}
