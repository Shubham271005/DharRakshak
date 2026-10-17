/*
 * Shared building blocks — use these in every screen so the app looks like
 * one product (compact spacing, same radius, same type scale).
 *
 *   <Card title="…" icon={Leaf} action={…}>…</Card>   white panel, optional header
 *   <Pill tone="rust">ELEVATED</Pill>                   rounded label
 *   <MockTag /> / <MockTag labelKey="demo_example" />   gold sample-data tag
 *   <ScreenHeader title="…" subtitle="…">…</ScreenHeader>
 *   <Loading />  <ErrorBox error={e} onRetry={fn} />  <Notice tone="gold">…</Notice>
 *   <Button variant="primary|secondary|ghost|danger" icon={Send}>
 *   <Field label="…" hint="…" error="…">…</Field> + INPUT_CLASS
 *   <ProgressBar value={0.6} />  <RiskBadge level="elevated" />
 *   <Stat icon={CloudRain} label="…" value="…" />      compact metric tile
 *   <SectionTitle>…</SectionTitle>  <RawData data={obj} />
 */
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export function Card({ title, icon: Icon, action, className = '', bodyClassName = '', children }) {
  return (
    <section className={`rounded-2xl border border-black/5 bg-white shadow-[0_1px_2px_rgba(16,40,24,0.06)] ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-2 border-b border-tint/80 px-4 py-2.5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-forest">
            {Icon && <Icon className="h-4 w-4 text-moss" aria-hidden />}
            {title}
          </h2>
          {action}
        </header>
      )}
      <div className={`p-4 ${bodyClassName}`}>{children}</div>
    </section>
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
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide ${PILL_TONES[tone] ?? PILL_TONES.moss} ${className}`}>
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
    <header className="mb-4 flex flex-wrap items-end justify-between gap-2">
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-forest sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  )
}

export function Loading() {
  const { t } = useLanguage()
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-muted" role="status">
      <Loader2 className="h-4 w-4 animate-spin text-moss" aria-hidden />
      {t('loading')}
    </div>
  )
}

export function ErrorBox({ error, onRetry }) {
  const { t } = useLanguage()
  return (
    <div className="flex items-start gap-3 rounded-xl border border-rust/25 bg-rust/5 p-3 text-sm text-rust" role="alert">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{t('error_title')}</p>
        <p className="mt-0.5 break-words">{error?.message ?? String(error)}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="inline-flex shrink-0 items-center gap-1 rounded-full bg-rust px-3 py-1 text-xs font-semibold text-white hover:opacity-90">
          <RefreshCw className="h-3 w-3" aria-hidden /> {t('retry')}
        </button>
      )}
    </div>
  )
}

const BUTTON_STYLES = {
  primary: 'bg-moss text-white hover:bg-forest shadow-sm',
  secondary: 'border border-moss/40 bg-white text-moss hover:bg-tint',
  ghost: 'text-moss hover:bg-tint',
  danger: 'bg-rust text-white hover:opacity-90',
}

export function Button({ variant = 'primary', icon: Icon, className = '', type = 'button', children, ...props }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_STYLES[variant] ?? BUTTON_STYLES.primary} ${className}`}
      {...props}
    >
      {Icon && <Icon className="h-4 w-4" aria-hidden />}
      {children}
    </button>
  )
}

/** Shared look for <input> and <select>. */
export const INPUT_CLASS =
  'w-full rounded-xl border border-black/10 bg-cream/60 px-3 py-2 text-sm text-ink outline-none transition focus:border-moss focus:bg-white focus:ring-2 focus:ring-moss/15'

export function Field({ label, hint, error, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">{label}</span>
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
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-tint" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className={`h-full rounded-full ${BAR_TONES[tone] ?? BAR_TONES.moss} transition-all duration-500`} style={{ width: `${pct}%` }} />
    </div>
  )
}

const RISK_TONES = { low: 'leaf', moderate: 'gold', elevated: 'rust' }

export function RiskBadge({ level, size = 'md' }) {
  const { t } = useLanguage()
  return (
    <span className="inline-flex items-center gap-1.5">
      <Pill tone={RISK_TONES[level] ?? 'muted'} className={size === 'lg' ? 'px-3 py-1 text-xs' : ''}>{t(`risk_${level}`)}</Pill>
      <span className="text-xs italic text-muted">{t('estimate')}</span>
    </span>
  )
}

export function Stat({ icon: Icon, label, value, sub }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-cream/70 px-3 py-2.5">
      {Icon && (
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-moss shadow-sm">
          <Icon className="h-4 w-4" aria-hidden />
        </span>
      )}
      <div className="min-w-0">
        <p className="truncate text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</p>
        <p className="truncate text-sm font-bold text-forest">{value}</p>
        {sub && <p className="truncate text-[11px] text-muted">{sub}</p>}
      </div>
    </div>
  )
}

export function SectionTitle({ children }) {
  return <h2 className="mb-2 text-[11px] font-bold uppercase tracking-widest text-muted">{children}</h2>
}

const NOTICE_TONES = {
  gold: 'border-gold/40 bg-goldtint text-forest',
  rust: 'border-rust/25 bg-rust/5 text-rust',
  tint: 'border-leaf/30 bg-tint/70 text-forest',
}

export function Notice({ tone = 'gold', icon: Icon, className = '', children }) {
  return (
    <div className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-sm ${NOTICE_TONES[tone] ?? NOTICE_TONES.gold} ${className}`}>
      {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}
      <div className="min-w-0">{children}</div>
    </div>
  )
}

/** Collapsible JSON preview of a value (handy while debugging). */
export function RawData({ data }) {
  const { t } = useLanguage()
  return (
    <details className="rounded-xl border border-tint bg-white p-3 text-sm">
      <summary className="cursor-pointer font-semibold text-moss">{t('raw_data')}</summary>
      <pre className="mt-2 max-h-[28rem] overflow-auto rounded-lg bg-cream p-3 text-xs leading-relaxed">{JSON.stringify(data, null, 2)}</pre>
    </details>
  )
}

/** Three compact weather tiles: icon on top, value, small label. */
export function WeatherTiles({ items }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {items.map(({ icon: Icon, label, value }) => (
        <div key={label} className="flex flex-col items-center rounded-xl bg-cream/70 px-1 py-2 text-center">
          <Icon className="h-4 w-4 text-moss" aria-hidden />
          <span className="mt-1 text-sm font-bold text-forest">{value}</span>
          <span className="text-[10px] leading-tight text-muted">{label}</span>
        </div>
      ))}
    </div>
  )
}
