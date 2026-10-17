// UI labels in every supported language.
//
// The text lives in shared/i18n/<lang>.json. To add a label: add the key to
// en.json and hi.json, then run `python scripts/translate_content.py` to
// fill in Marathi, Punjabi, Haryanvi and Bhojpuri. tests/test_i18n.py checks
// that every language has every key the frontend uses.
//
// Files are discovered automatically, so a language file that doesn't exist
// yet simply falls back (see languages.js) instead of breaking the build.
const files = import.meta.glob('../../../shared/i18n/*.json', { eager: true, import: 'default' })

/** { en: {key: text}, hi: {...}, mr: {...}, ... } */
export const UI_TEXT = Object.fromEntries(
  Object.entries(files).map(([path, texts]) => [path.split('/').pop().replace('.json', ''), texts]),
)
