import { fireEvent, render, screen } from '@testing-library/svelte'
import { expect, test, vi } from 'vitest'
import Result from '../src/routes/Result.svelte'
import { cand, result } from './fixtures'

const noop = () => {}

test('confident result shows name, a Best match label and Also possible', () => {
  render(Result, { result: result(), onShruti: noop, onRetry: noop })
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Mohanam')
  expect(screen.getByText('Best match')).toBeInTheDocument()
  expect(screen.getByText(/Also possible/)).toBeInTheDocument()
  expect(screen.getByText('Bilahari')).toBeInTheDocument()
})

test("shortlist shows 'Likely one of…' and the same-swaras note for grouped candidates", () => {
  const r = result({
    kind: 'shortlist',
    candidates: [cand('Mohanam', { group: 1 }), cand('Bhoopali', { group: 1 }), cand('Hamsadhwani')],
  })
  render(Result, { result: r, onShruti: noop, onRetry: noop })
  expect(screen.getByText('Likely one of…')).toBeInTheDocument()
  expect(screen.getByText('These ragas share the same swaras')).toBeInTheDocument()
})

test("no_melody shows 'No melody detected — keep listening'", async () => {
  const onRetry = vi.fn()
  render(Result, { result: result({ kind: 'no_melody', candidates: [] }), onShruti: noop, onRetry })
  expect(screen.getByText('No melody detected — keep listening')).toBeInTheDocument()
  await fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(onRetry).toHaveBeenCalled()
})

test('shruti suspect banner re-sends with suggested note', async () => {
  const onShruti = vi.fn()
  const r = result({
    kind: 'shortlist',
    shruti_suspect: { suggested_tonic_hz: 138.6, suggested_note: 'C#', shift_semitones: -2 },
  })
  render(Result, { result: r, onShruti, onRetry: noop })
  expect(screen.getByText('Check the shruti?')).toBeInTheDocument()
  await fireEvent.click(screen.getByRole('button', { name: 'Use C#' }))
  expect(onShruti).toHaveBeenCalledWith('C#')
})

test('editing the shruti offers 12 notes and re-sends the chosen one', async () => {
  const onShruti = vi.fn()
  render(Result, { result: result(), onShruti, onRetry: noop })
  await fireEvent.click(screen.getByRole('button', { name: /edit shruti/i }))
  expect(screen.getAllByRole('button', { name: /^[A-G]#?$/ })).toHaveLength(12)
  await fireEvent.click(screen.getByRole('button', { name: 'D' }))
  expect(onShruti).toHaveBeenCalledWith('D')
})

test('swara bars label shared positions with the top raga’s own swara names', () => {
  render(Result, { result: result(), onShruti: noop, onRetry: noop })
  expect(screen.getByLabelText('R2 strength')).toBeInTheDocument()
  expect(screen.getByLabelText('G3 strength')).toBeInTheDocument()
})


test('no uncalibrated percentages are shown (confident or shortlist)', () => {
  const { container, unmount } = render(Result, { result: result(), onShruti: noop, onRetry: noop })
  expect(container.textContent).not.toMatch(/\d+%/)
  unmount()
  const short = render(Result, { result: result({ kind: 'shortlist' }), onShruti: noop, onRetry: noop })
  expect(short.container.textContent).not.toMatch(/\d+%/)
})
