// Mirrors backend AnalysisResult.to_json() and /api/ragas responses (snake_case on purpose).
export type Kind = 'confident' | 'shortlist' | 'no_melody'

export interface Candidate {
  raga_id: string
  name: string
  melakarta: number | null
  parent: number
  arohana: string[]
  avarohana: string[]
  score: number
  percent: number
  group: number | null
}

export interface ShrutiSuspect {
  suggested_tonic_hz: number
  suggested_note: string
  shift_semitones: number
}

export interface AnalysisResult {
  kind: Kind
  candidates: Candidate[]
  tonic_hz: number | null
  tonic_note: string | null
  shruti_suspect: ShrutiSuspect | null
  swara_strengths: number[]
  voiced_seconds: number
  model_version: string
  processing_ms: number
}

export interface RagaSummary {
  id: string
  name: string
  melakarta: number | null
  parent: number
}

export interface RagaDetail extends RagaSummary {
  aliases: string[]
  arohana: string[]
  avarohana: string[]
  vakra: boolean
  bhashanga: boolean
  example_count: number
}
