export const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

// Default names for the 12 swarasthanas when no raga context is known.
const DEFAULT_LABELS = ['S', 'R1', 'R2', 'G2', 'G3', 'M1', 'M2', 'P', 'D1', 'D2', 'N2', 'N3']
const TOKEN_POSITION: Record<string, number> = {
  S: 0, R1: 1, R2: 2, R3: 3, G1: 2, G2: 3, G3: 4, M1: 5, M2: 6, P: 7,
  D1: 8, D2: 9, D3: 10, N1: 9, N2: 10, N3: 11,
}

/** Label for a swara position, using the raga's own token for shared positions (e.g. R2 vs G1). */
export function swaraLabel(position: number, raga?: { arohana: string[]; avarohana: string[] }): string {
  if (raga) {
    for (const t of [...raga.arohana, ...raga.avarohana]) {
      if (TOKEN_POSITION[t] === position) return t
    }
  }
  return DEFAULT_LABELS[position]
}

export function formatScale(tokens: string[]): string {
  return tokens.join(' ')
}
