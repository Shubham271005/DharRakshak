/*
 * App navigation: brand, language switcher (F6), screen links and a
 * data-mode badge. On phones it becomes a top bar with scrollable tabs.
 */
import { getHealth, isMockMode } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { LANGUAGES, useLanguage } from '../i18n/LanguageContext.jsx'

function ModeBadge() {
  const { t } = useLanguage()
  // In api mode, ping /api/health to show whether the backend is reachable.
  const { error, loading } = useApiData(getHealth, [])

  if (isMockMode()) {
    return <span className="rounded-full bg-gold px-3 py-1 text-xs font-bold text-forest">{t('mock_mode')}</span>
  }
  if (loading) return null
  return (
    <span className="flex items-center gap-2 text-xs text-cream/90">
      <span className={`h-2.5 w-2.5 rounded-full ${error ? 'bg-rust' : 'bg-leaf'}`} />
      {error ? t('server_down') : t('server_ok')}
    </span>
  )
}

export default function Sidebar({ screens, current, onSelect }) {
  const { lang, setLang, t } = useLanguage()

  return (
    <aside className="bg-forest text-cream md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0 md:flex-col">
      <div className="px-5 pt-5 md:pt-7">
        <p className="text-xl font-bold">🌱 {t('app_name')}</p>
        <p className="mt-1 hidden text-sm text-cream/70 md:block">{t('app_tagline')}</p>
      </div>

      {/* Language switcher */}
      <div className="px-5 pt-4" role="group" aria-label={t('language')}>
        <p className="mb-2 hidden text-xs font-semibold uppercase tracking-widest text-leaf md:block">{t('language')}</p>
        <div className="inline-flex rounded-full bg-white/10 p-1">
          {Object.entries(LANGUAGES).map(([code, label]) => (
            <button
              key={code}
              onClick={() => setLang(code)}
              aria-pressed={lang === code}
              className={`rounded-full px-4 py-1 text-sm font-semibold transition ${
                lang === code ? 'bg-cream text-forest' : 'text-cream/80 hover:text-cream'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Screen navigation: tabs on phones, list on desktop */}
      <nav className="mt-4 flex gap-1 overflow-x-auto px-3 pb-3 md:mt-6 md:flex-col md:overflow-visible">
        {screens.map((screen) => (
          <button
            key={screen.id}
            onClick={() => onSelect(screen.id)}
            aria-current={current === screen.id ? 'page' : undefined}
            className={`flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-semibold transition ${
              current === screen.id ? 'bg-moss text-white' : 'text-cream/80 hover:bg-white/10 hover:text-cream'
            }`}
          >
            <span aria-hidden>{screen.icon}</span>
            {t(screen.labelKey)}
          </button>
        ))}
      </nav>

      <div className="hidden px-5 pb-6 md:mt-auto md:block">
        <ModeBadge />
      </div>
    </aside>
  )
}
