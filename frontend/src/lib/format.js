// Formatting helpers shared by every screen.

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

/** 120000 -> "₹1,20,000" (Indian digit grouping). */
export function formatINR(amount) {
  return inrFormatter.format(amount)
}

/** 0.68 -> "68%". */
export function formatPercent(confidence) {
  return `${Math.round(confidence * 100)}%`
}

/** "2026-12-15" -> "15 Dec 2026" (en) / "15 दिस॰ 2026" (hi). Returns "—" for null. */
export function formatDate(isoDate, lang) {
  if (!isoDate) return '—'
  // Parse date-only strings as local dates so the day doesn't shift by timezone.
  const [y, m, d] = isoDate.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(lang === 'hi' ? 'hi-IN' : 'en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** Today's date as "YYYY-MM-DD" — handy for <input type="date" max={...}>. */
export function todayISO() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}
