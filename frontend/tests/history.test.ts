import { beforeEach, expect, test } from 'vitest'
import { addToHistory, clearHistory, HISTORY_KEY, listHistory } from '../src/lib/history'
import { result } from './fixtures'

beforeEach(() => localStorage.clear())

const entry = (i: number) => ({ at: new Date(2026, 0, 1, 0, i).toISOString(), source: 'upload' as const, label: `clip ${i}`, result: result() })

test('history keeps newest 50, newest first', () => {
  for (let i = 0; i < 55; i++) addToHistory(entry(i))
  const h = listHistory()
  expect(h).toHaveLength(50)
  expect(h[0].label).toBe('clip 54')
  expect(h[49].label).toBe('clip 5')
})

test('corrupt storage resets to empty', () => {
  localStorage.setItem(HISTORY_KEY, '{not json')
  expect(listHistory()).toEqual([])
  addToHistory(entry(1))
  expect(listHistory()).toHaveLength(1)
})

test('clearHistory empties it', () => {
  addToHistory(entry(1))
  clearHistory()
  expect(listHistory()).toEqual([])
})
