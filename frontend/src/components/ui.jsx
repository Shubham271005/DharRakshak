/*
 * Small shared building blocks. Use these in every screen so the app looks
 * consistent:
 *
 *   <Card>…</Card>                         white rounded panel
 *   <Pill tone="rust">ELEVATED</Pill>      rounded label (tones below)
 *   <MockTag />  /  <MockTag labelKey="demo_example" />   gold sample-data tag
 *   <ScreenHeader title="…" subtitle="…" />
 *   <Loading />   <ErrorBox error={error} onRetry={reload} />
 *   <Button variant="primary|secondary|ghost">  rounded button
 *   <Field label="…" error="…">…</Field>   label + input + error, use INPUT_CLASS
 *   <ProgressBar value={0.6} tone="moss" /> thin bar, value 0–1
 *   <RiskBadge level="elevated" />         coloured risk level + "estimate"
 *   <SectionTitle>…</SectionTitle>         small uppercase heading
 *   <Notice tone="gold|rust|tint">…</Notice> soft message box
 *   <RawData data={obj} />                 collapsible JSON preview (debugging)
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

/** Collapsible JSON preview of a value (handy while debugging). */
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

const BUTTON_STYLES = {
  primary: 'bg-moss text-white hover:bg-forest',
  secondary: 'border border-moss text-moss hover:bg-tint',
  ghost: 'text-moss hover:bg-tint',
  danger: 'bg-rust text-white hover:opacity-90',
}

export function Button({ variant = 'primary', className = '', type = 'button', ...props }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_STYLES[variant] ?? BUTTON_STYLES.primary} ${className}`}
      {...props}
    />
  )
}

/** Shared look for <input> and <select>. */
export const INPUT_CLASS =
  'w-full rounded-xl border border-tint bg-cream px-3 py-2 text-ink outline-none transition focus:border-moss focus:ring-2 focus:ring-moss/20'

export function Field({ label, hint, error, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-forest">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs font-semibold text-rust">{error}</span>}
    </label>
  )
}

const BAR_TONES = { moss: 'bg-moss', leaf: 'bg-leaf', gold: 'bg-gold', rust: 'bg-rust' }

export function ProgressBar({ value, tone = 'moss', label }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  return (
    <div className="h-2 w-full rounded-full bg-tint" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className={`h-2 rounded-full ${BAR_TONES[tone] ?? BAR_TONES.moss} transition-all`} style={{ width: `${pct}%` }} />
    </div>
  )
}

const RISK_TONES = { low: 'leaf', moderate: 'gold', elevated: 'rust' }

export function RiskBadge({ level }) {
  const { t } = useLanguage()
  return (
    <span className="inline-flex items-center gap-2">
      <Pill tone={RISK_TONES[level] ?? 'muted'} className="px-4 py-1 text-sm">{t(`risk_${level}`)}</Pill>
      <span className="text-sm italic text-muted">{t('estimate')}</span>
    </span>
  )
}

export function SectionTitle({ children }) {
  return <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-muted">{children}</h2>
}

const NOTICE_TONES = {
  gold: 'border-gold/40 bg-goldtint text-forest',
  rust: 'border-rust/30 bg-rust/10 text-rust',
  tint: 'border-tint bg-tint text-forest',
}

export function Notice({ tone = 'gold', className = '', children }) {
  return <div className={`rounded-2xl border px-4 py-3 text-sm ${NOTICE_TONES[tone] ?? NOTICE_TONES.gold} ${className}`}>{children}</div>
}
