/*
 * Language state for the whole app (F6).
 *
 * Any component can do:
 *   const { lang, setLang, t, tr } = useLanguage()
 *   t('nav_profile')   -> UI label in the current language
 *   tr(card.title)     -> picks the right language from a backend
 *                         LocalizedText object like {en: "...", hi: "...", mr: "..."}
 *
 * Missing texts follow the fallback chain in languages.js
 * (e.g. Bhojpuri → Hindi → English), the same as the backend.
 * The chosen language is remembered in the browser (localStorage).
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { LANGUAGES, languageChain } from './languages.js'
import { UI_TEXT } from './uiText.js'

export { LANGUAGES }

const STORAGE_KEY = 'dharrakshak.lang'
const LanguageContext = createContext(null)

function readSavedLanguage() {
  // A `?lang=mr` link opens the app in that language (handy for demos).
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
    document.documentElement.lang = lang === 'bgc' || lang === 'bho' ? 'hi' : lang // browsers know hi, not bgc/bho
    try {
      localStorage.setItem(STORAGE_KEY, lang)
    } catch {
      /* ignore */
    }
  }, [lang])

  const value = useMemo(() => {
    const chain = languageChain(lang)
    // UI label: current language → fallback chain → the key itself
    // (a raw key on screen makes missing translations easy to spot).
    const t = (key) => {
      for (const code of chain) {
        const text = UI_TEXT[code]?.[key]
        if (text) return text
      }
      return key
    }
    // Backend text (LocalizedText objects).
    const tr = (localized) => {
      if (!localized) return ''
      for (const code of chain) if (localized[code]) return localized[code]
      return localized.en ?? ''
    }
    return { lang, setLang, t, tr, speechLang: LANGUAGES[lang].speech, sttLang: LANGUAGES[lang].stt }
  }, [lang])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used inside <LanguageProvider>')
  return ctx
}
