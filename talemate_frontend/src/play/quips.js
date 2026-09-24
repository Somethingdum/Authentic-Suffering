// The loading bar's line picking (10_UI §2.10; service/progress.py PROG-07). Pure functions.
export const QUIP_MS = 2500

export function quipLines(quips, kind, phase, sub) {
  const q = quips || {}
  for (const key of [`${kind}.${phase}.${sub}`, `${kind}.${phase}`, `${kind}`]) {
    const lines = q[key]
    if (Array.isArray(lines) && lines.length) return lines
  }
  return []
}

export function nextQuip(lines, recent, random = Math.random) {
  if (!lines || !lines.length) return null
  const k = Math.min(3, lines.length - 1)
  const barred = k > 0 ? recent.slice(-k) : []
  const candidates = lines.filter((l) => !barred.includes(l))
  return candidates[Math.floor(random() * candidates.length)]
}
