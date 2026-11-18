import type { AnalysisResult, RagaDetail, RagaSummary } from './types'

export class ApiError extends Error {
  constructor(public status: number, public code: string) {
    super(code)
  }
}

export const ERROR_COPY: Record<string, string> = {
  too_short: 'That was too short — record at least 10 seconds.',
  youtube_blocked: "YouTube didn't let us fetch that video. Please upload the file instead.",
  bad_url: "That doesn't look like a YouTube link.",
  too_large: 'That file is too big (max 50 MB).',
  undecodable: "We couldn't read that file.",
  rate_limited: 'Too many tries — wait a minute.',
  network: "Couldn't reach the server.",
  bad_shruti: "That shruti isn't a note we know.",
}

export function errorCopy(e: unknown): string {
  const code = e instanceof ApiError ? e.code : 'network'
  return ERROR_COPY[code] ?? 'Something went wrong. Please try again.'
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError(0, 'network')
  }
  let body: any = null
  try {
    body = await res.json()
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) throw new ApiError(res.status, body?.error ?? 'network')
  return body as T
}

export function analyzeFile(file: Blob, filename: string, shruti?: string): Promise<AnalysisResult> {
  const fd = new FormData()
  fd.append('file', file, filename)
  if (shruti) fd.append('shruti', shruti)
  return request('/api/analyze', { method: 'POST', body: fd })
}

export function analyzeYouTube(url: string, start?: number, shruti?: string): Promise<AnalysisResult> {
  const body: Record<string, unknown> = { url }
  if (start !== undefined) body.start = start
  if (shruti) body.shruti = shruti
  return request('/api/analyze/youtube', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function searchRagas(q: string): Promise<RagaSummary[]> {
  return request(`/api/ragas?q=${encodeURIComponent(q)}`)
}

export function getRaga(id: string): Promise<RagaDetail> {
  return request(`/api/ragas/${encodeURIComponent(id)}`)
}

/** Poll /api/health until the server answers (Cloud Run cold starts take a few seconds). */
export function waitForServer(onSlow: () => void, slowAfterMs = 2000, timeoutMs = 90000): Promise<void> {
  return new Promise((resolve, reject) => {
    let finished = false
    const slow = setTimeout(() => !finished && onSlow(), slowAfterMs)
    const giveUp = setTimeout(() => finish(new ApiError(0, 'network')), timeoutMs)
    function finish(err?: ApiError) {
      if (finished) return
      finished = true
      clearTimeout(slow)
      clearTimeout(giveUp)
      if (err) reject(err)
      else resolve()
    }
    async function attempt() {
      if (finished) return
      try {
        const res = await fetch('/api/health', { cache: 'no-store' })
        if (res.ok) return finish()
      } catch {
        /* not up yet */
      }
      if (!finished) setTimeout(attempt, 1500)
    }
    void attempt()
  })
}
