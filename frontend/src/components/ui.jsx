/*
 * Small shared building blocks. Use these in every screen so the app looks
 * consistent:
 *
 *   <Card>…</Card>                         white rounded panel
 *   <Pill tone="rust">ELEVATED</Pill>      rounded label (tones below)
 *   <MockTag />  /  <MockTag labelKey="demo_example" />   gold sample-data tag
 *   <ScreenHeader title="…" subtitle="…" />
 *   <Loading />   <ErrorBox error={error} onRetry={reload} />
 *   <StubBanner owner="Teammate 1" />      remove when your screen is done
 *   <RawData data={obj} />                 collapsible JSON preview while building
 */
import { useLanguage } from '../i18n/LanguageContext.jsx'

export function Card({ className = '', children }) {
  return (
    <div className={`rounded-2xl border border-tint bg-white p-5 shadow-sm ${className}`}>
      {children}
    </div>
  )
}

const PILL_TONES = {
  forest: 'bg-forest text-white',
  moss: 'bg-moss text-white',
  leaf: 'bg-leaf text-white',
  gold: 'bg-gold text-forest',
  rust: 'bg-rust text-white',
  tint: 'bg-tint text-moss',
  muted: 'bg-muted/15 text-muted',
}

export function Pill({ tone = 'moss', className = '', children }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-0.5 text-xs font-bold tracking-wide ${PILL_TONES[tone] ?? PILL_TONES.moss} ${className}`}
    >
      {children}
    </span>
  )
}

/** Required wherever sample or mock data is shown. */
export function MockTag({ labelKey = 'mock_data' }) {
  const { t } = useLanguage()
  return <Pill tone="gold">{t(labelKey)}</Pill>
}

export function ScreenHeader({ title, subtitle, children }) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-3xl font-bold text-forest">{title}</h1>
        {subtitle && <p className="mt-1 text-muted">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </header>
  )
}

export function Loading() {
  const { t } = useLanguage()
  return (
    <div className="flex items-center gap-3 py-10 text-muted" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-tint border-t-moss" />
      {t('loading')}
    </div>
  )
}

export function ErrorBox({ error, onRetry }) {
  const { t } = useLanguage()
  return (
    <div className="rounded-2xl border border-rust/30 bg-rust/10 p-4 text-rust" role="alert">
      <p className="font-bold">{t('error_title')}</p>
      <p className="mt-1 text-sm">{error?.message ?? String(error)}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-full bg-rust px-4 py-1.5 text-sm font-semibold text-white hover:opacity-90"
        >
          {t('retry')}
        </button>
      )}
    </div>
  )
}

/** Temporary banner on unfinished screens. Delete it when your screen is done. */
export function StubBanner({ owner }) {
  const { t } = useLanguage()
  return (
    <div className="mb-6 rounded-2xl border border-gold/40 bg-goldtint px-4 py-3 text-sm text-forest">
      🚧 {t('under_construction')} <strong>{owner}</strong>
    </div>
  )
}

/** Temporary JSON preview of what a screen receives. Delete when done. */
export function RawData({ data }) {
  const { t } = useLanguage()
  return (
    <details className="rounded-2xl border border-tint bg-white p-4">
      <summary className="cursor-pointer font-semibold text-moss">{t('raw_data')}</summary>
      <pre className="mt-3 max-h-[28rem] overflow-auto rounded-xl bg-cream p-3 text-xs leading-relaxed">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  )
}
