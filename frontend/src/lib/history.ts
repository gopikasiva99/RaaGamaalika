import type { AnalysisResult } from './types'

export const HISTORY_KEY = 'raaga.history.v1'
export const HISTORY_MAX = 50

export interface HistoryEntry {
  at: string
  source: 'live' | 'upload' | 'youtube'
  label: string
  result: AnalysisResult
}

export function listHistory(): HistoryEntry[] {
  try {
    const v = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

export function addToHistory(e: HistoryEntry): void {
  const next = [e, ...listHistory()].slice(0, HISTORY_MAX)
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
  } catch {
    /* storage full or unavailable: history is best-effort */
  }
}

export function clearHistory(): void {
  localStorage.removeItem(HISTORY_KEY)
}
