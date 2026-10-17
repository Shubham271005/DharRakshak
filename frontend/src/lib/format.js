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

// Locale for dates in each app language (Haryanvi/Bhojpuri use Hindi dates).
const DATE_LOCALES = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN', pa: 'pa-IN', bgc: 'hi-IN', bho: 'hi-IN' }

/**
 * "2026-12-15" -> "15 Dec 2026" (en) / "15 दिस॰ 2026" (hi). Returns "—" for null.
 * Date-only strings are read as local dates; full timestamps
 * ("2026-10-17T21:20:26+00:00") are converted to the device's local time,
 * so an upload at 2:50 am IST shows today's date, not yesterday's (UTC).
 */
export function formatDate(iso, lang) {
  if (!iso) return '—'
  const date = iso.length > 10 ? new Date(iso) : (() => {
    const [y, m, d] = iso.split('-').map(Number)
    return new Date(y, m - 1, d)
  })()
  return date.toLocaleDateString(DATE_LOCALES[lang] ?? 'en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

/** Today's date as "YYYY-MM-DD" — handy for <input type="date" max={...}>. */
export function todayISO() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}
