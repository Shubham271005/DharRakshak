/*
 * Language state for the whole app (F6).
 *
 * Any component can do:
 *   const { lang, setLang, t, tr } = useLanguage()
 *   t('nav_profile')            -> UI label from uiText.js in the current language
 *   tr(card.title)              -> picks the right language from a backend
 *                                  LocalizedText object like {en: "...", hi: "..."}
 *
 * The chosen language is remembered in the browser (localStorage).
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { UI_TEXT } from './uiText.js'

// Languages shown in the switcher. Add a regional language ONLY when its
// translations exist everywhere (ROADMAP.md, Component 8).
export const LANGUAGES = { en: 'English', hi: 'हिंदी' }

const STORAGE_KEY = 'dharrakshak.lang'
const LanguageContext = createContext(null)

function readSavedLanguage() {
  // A `?lang=hi` link opens the app in that language (handy for demos).
  const fromUrl = new URLSearchParams(window.location.search).get('lang')
  if (fromUrl in LANGUAGES) return fromUrl
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved in LANGUAGES ? saved : 'en'
  } catch {
    return 'en' // private mode / storage blocked
  }
}

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(readSavedLanguage)

  useEffect(() => {
    document.documentElement.lang = lang // helps screen readers and fonts
    try {
      localStorage.setItem(STORAGE_KEY, lang)
    } catch {
      /* ignore */
    }
  }, [lang])

  const value = useMemo(() => {
    // UI label lookup: current language -> English -> the key itself
    // (a raw key on screen makes missing translations easy to spot).
    const t = (key) => UI_TEXT[key]?.[lang] ?? UI_TEXT[key]?.en ?? key
    // Backend text lookup for LocalizedText objects.
    const tr = (localized) => (localized ? (localized[lang] ?? localized.en ?? '') : '')
    return { lang, setLang, t, tr }
  }, [lang])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used inside <LanguageProvider>')
  return ctx
}
