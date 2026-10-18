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

/*
 * Each icon gets its own colour so cards are easy to tell apart at a glance.
 * Keyed by lucide's displayName; anything unlisted uses the brand green.
 */
const ICON_TONES = {
  CloudRain: 'from-sky-400 to-blue-600 shadow-sky-500/30',
  Droplets: 'from-cyan-400 to-teal-600 shadow-cyan-500/30',
  Thermometer: 'from-amber-400 to-orange-600 shadow-orange-500/30',
  FileCheck2: 'from-violet-400 to-indigo-600 shadow-indigo-500/30',
  Landmark: 'from-violet-400 to-indigo-600 shadow-indigo-500/30',
  MessageCircle: 'from-fuchsia-400 to-pink-600 shadow-pink-500/30',
  ShieldAlert: 'from-orange-400 to-red-600 shadow-red-500/30',
  Lightbulb: 'from-yellow-300 to-amber-500 shadow-amber-500/30',
  ListChecks: 'from-emerald-400 to-teal-600 shadow-emerald-500/30',
  CheckCircle2: 'from-emerald-400 to-green-600 shadow-emerald-500/30',
  History: 'from-slate-400 to-slate-600 shadow-slate-500/30',
  Info: 'from-sky-400 to-cyan-600 shadow-sky-500/30',
  ScanSearch: 'from-lime-400 to-green-600 shadow-lime-500/30',
  Calendar: 'from-rose-400 to-red-500 shadow-rose-500/30',
  MapPin: 'from-red-400 to-rose-600 shadow-rose-500/30',
  Ruler: 'from-amber-400 to-yellow-600 shadow-amber-500/30',
}
const DEFAULT_TONE = 'from-leaf to-moss shadow-moss/30'
export const iconTone = (Icon) => ICON_TONES[Icon?.displayName] ?? DEFAULT_TONE

/** Gradient icon chip: white glyph on a coloured tile, wiggles on card hover. */
export function IconChip({ icon: Icon, size = 'md' }) {
  const box = size === 'lg' ? 'h-11 w-11 rounded-2xl' : 'h-8 w-8 rounded-xl'
  const glyph = size === 'lg' ? 'h-5 w-5' : 'h-[18px] w-[18px]'
  return (
    <span className={`flex shrink-0 items-center justify-center bg-gradient-to-br text-white shadow-md transition duration-300 group-hover/card:-rotate-6 group-hover/card:scale-110 ${box} ${iconTone(Icon)}`}>
      <Icon className={glyph} strokeWidth={2.25} aria-hidden />
    </span>
  )
}

export function Card({ title, icon: Icon, action, className = '', bodyClassName = '', children }) {
  return (
    <section className={`group/card relative overflow-hidden rounded-2xl border border-black/[0.06] bg-white/90 shadow-[0_1px_2px_rgba(16,40,24,0.04),0_8px_24px_-12px_rgba(16,40,24,0.12)] backdrop-blur-sm transition duration-300 hover:shadow-[0_1px_2px_rgba(16,40,24,0.05),0_14px_32px_-14px_rgba(16,40,24,0.22)] ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-2 border-b border-black/[0.05] px-4 py-2.5">
          <h2 className="flex items-center gap-2.5 text-[15px] font-bold tracking-tight text-forest">
            {Icon && <IconChip icon={Icon} />}
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
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3 animate-fade">
      <div className="min-w-0">
        <h1 className="bg-gradient-to-r from-forest via-moss to-forest bg-clip-text text-2xl font-extrabold tracking-tight text-transparent sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
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
  primary: 'bg-gradient-to-b from-moss to-forest text-white shadow-md shadow-moss/25 hover:brightness-110 active:scale-[0.98]',
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
      <div className={`h-full origin-left animate-grow rounded-full ${BAR_TONES[tone] ?? BAR_TONES.moss}`} style={{ width: `${pct}%` }} />
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
    <div className="group/card flex items-center gap-3 rounded-xl border border-black/[0.04] bg-gradient-to-br from-white to-cream/80 px-3 py-2.5 transition hover:border-moss/20">
      {Icon && <IconChip icon={Icon} size="lg" />}
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
        <div key={label} className="group/card flex flex-col items-center rounded-2xl bg-gradient-to-b from-cream to-cream/40 px-1 py-4 text-center ring-1 ring-black/[0.03] transition hover:-translate-y-0.5 hover:shadow-md">
          <IconChip icon={Icon} size="lg" />
          <span className="mt-2 text-lg font-extrabold tracking-tight text-forest">{value}</span>
          <span className="text-[11px] leading-tight text-muted">{label}</span>
        </div>
      ))}
    </div>
  )
}
