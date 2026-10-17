// UI labels in every supported language (Component 8).
//
// The text lives in shared/i18n/en.json and shared/i18n/hi.json so it can
// be reviewed (and translated) in one place. To add a label: add the same
// key to BOTH files, then use t('your_key') via useLanguage().
// tests/test_i18n.py fails if a key is missing from either file or if the
// frontend uses a key that doesn't exist.
import en from '../../../shared/i18n/en.json'
import hi from '../../../shared/i18n/hi.json'

const SOURCES = { en, hi }

export const UI_TEXT = Object.fromEntries(
  Object.keys(en)
    .filter((key) => !key.startsWith('_'))
    .map((key) => [key, Object.fromEntries(Object.entries(SOURCES).map(([lang, texts]) => [lang, texts[key]]))]),
)
