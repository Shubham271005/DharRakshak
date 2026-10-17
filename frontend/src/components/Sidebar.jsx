/*
 * App navigation.
 *   <Sidebar>        desktop: brand, screen links, language, connection status
 *   <MobileHeader>   phones: brand + language picker at the top
 *   <BottomNav>      phones: icon tab bar at the bottom (thumb-friendly)
 *   <LanguageSelect> 6-language dropdown (F6), each name in its own script
 */
import { Languages, Sprout } from 'lucide-react'
import { getHealth, isMockMode } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { LANGUAGES, useLanguage } from '../i18n/LanguageContext.jsx'

export function LanguageSelect({ dark = false }) {
  const { lang, setLang, t } = useLanguage()
  return (
    <label className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm ${dark ? 'bg-white/10 text-cream' : 'bg-tint text-forest'}`}>
      <Languages className="h-4 w-4 shrink-0" aria-hidden />
      <span className="sr-only">{t('language')}</span>
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value)}
        className="cursor-pointer bg-transparent font-semibold outline-none [&>option]:text-ink"
        aria-label={t('language')}
      >
        {Object.entries(LANGUAGES).map(([code, { label }]) => (
          <option key={code} value={code}>{label}</option>
        ))}
      </select>
    </label>
  )
}

function ModeBadge() {
  const { t } = useLanguage()
  // In api mode, ping /api/health to show whether the backend is reachable.
  const { error, loading } = useApiData(getHealth, [])
  if (isMockMode()) {
    return <span className="rounded-full bg-gold px-2.5 py-0.5 text-[11px] font-bold text-forest">{t('mock_mode')}</span>
  }
  if (loading) return null
  return (
    <span className="flex items-center gap-1.5 text-xs text-cream/80">
      <span className={`h-2 w-2 rounded-full ${error ? 'bg-rust' : 'bg-leaf'}`} />
      {error ? t('server_down') : t('server_ok')}
    </span>
  )
}

function Brand({ compact = false }) {
  const { t } = useLanguage()
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-leaf/90 text-forest shadow-sm">
        <Sprout className="h-5 w-5" aria-hidden />
      </span>
      <div className="min-w-0 leading-tight">
        <p className="truncate font-bold text-cream">{t('app_name')}</p>
        {!compact && <p className="truncate text-[11px] text-cream/60">{t('app_tagline')}</p>}
      </div>
    </div>
  )
}

export function Sidebar({ screens, current, onSelect }) {
  const { t } = useLanguage()
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-forest px-3 py-5 text-cream md:flex">
      <div className="px-2"><Brand /></div>
      <nav className="mt-6 flex flex-col gap-0.5" aria-label="Main">
        {screens.map(({ id, labelKey, Icon }) => (
          <button
            key={id}
            onClick={() => onSelect(id)}
            aria-current={current === id ? 'page' : undefined}
            className={`flex items-center gap-3 rounded-xl px-3 py-2 text-left text-sm font-medium transition ${
              current === id ? 'bg-white/12 text-white shadow-inner' : 'text-cream/75 hover:bg-white/5 hover:text-cream'
            }`}
          >
            <Icon className={`h-4 w-4 ${current === id ? 'text-leaf' : ''}`} aria-hidden />
            {t(labelKey)}
          </button>
        ))}
      </nav>
      <div className="mt-auto space-y-3 px-2">
        <LanguageSelect dark />
        <ModeBadge />
      </div>
    </aside>
  )
}

export function MobileHeader() {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-2 bg-forest px-4 py-2.5 md:hidden">
      <Brand compact />
      <LanguageSelect dark />
    </header>
  )
}

export function BottomNav({ screens, current, onSelect }) {
  const { t } = useLanguage()
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-20 grid border-t border-black/10 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      style={{ gridTemplateColumns: `repeat(${screens.length}, minmax(0, 1fr))` }}
      aria-label="Main"
    >
      {screens.map(({ id, labelKey, Icon }) => (
        <button
          key={id}
          onClick={() => onSelect(id)}
          aria-current={current === id ? 'page' : undefined}
          className={`flex flex-col items-center gap-0.5 px-1 py-2 text-[10px] font-semibold ${current === id ? 'text-moss' : 'text-muted'}`}
        >
          <Icon className="h-5 w-5" aria-hidden />
          <span className="max-w-full truncate">{t(labelKey)}</span>
        </button>
      ))}
    </nav>
  )
}

export default Sidebar
