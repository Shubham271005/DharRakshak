// Languages the app offers (must match SUPPORTED_LANGUAGES in shared/contract.py).
//
//   label     — shown in the language picker, in its own script
//   fallback  — language to use when a text is missing (same chain as the backend)
//   speech    — BCP-47 tag for the browser's read-aloud voice
//   stt       — language sent to speech-to-text (Whisper has no Haryanvi or
//               Bhojpuri model, so those use Hindi, the closest it knows)
export const LANGUAGES = {
  en: { label: 'English', fallback: null, speech: 'en-IN', stt: 'en' },
  hi: { label: 'हिंदी', fallback: 'en', speech: 'hi-IN', stt: 'hi' },
  mr: { label: 'मराठी', fallback: 'hi', speech: 'mr-IN', stt: 'mr' },
  pa: { label: 'ਪੰਜਾਬੀ', fallback: 'hi', speech: 'pa-IN', stt: 'pa' },
  bgc: { label: 'हरियाणवी', fallback: 'hi', speech: 'hi-IN', stt: 'hi' },
  bho: { label: 'भोजपुरी', fallback: 'hi', speech: 'hi-IN', stt: 'hi' },
}

/** Fallback chain, e.g. 'bho' -> ['bho', 'hi', 'en']. */
export function languageChain(lang) {
  const chain = []
  let current = lang
  while (current && !chain.includes(current)) {
    chain.push(current)
    current = LANGUAGES[current]?.fallback ?? (current === 'en' ? null : 'en')
  }
  return chain
}
