// Crop and growth-stage names for the UI, in every language.
//
// The names live in shared/i18n/<lang>.json as crop_<key> / stage_<key>, so
// they are translated with everything else (scripts/translate_content.py).
// Crop keys MUST match the "crop" field in shared/content/labels.json —
// exactly the 14 crops the image model recognises. Order = order in the form.
import { languageChain } from '../i18n/languages.js'
import { UI_TEXT } from '../i18n/uiText.js'

export const CROP_OPTIONS = [
  'tomato', 'potato', 'corn', 'pepper_bell', 'soybean', 'grape', 'apple',
  'orange', 'peach', 'cherry', 'strawberry', 'squash', 'blueberry', 'raspberry',
].reduce((acc, key) => ({ ...acc, [key]: true }), {})

// Must match `CropStage` in shared/contract.py.
export const STAGE_LABELS = ['seedling', 'vegetative', 'flowering', 'fruiting', 'maturity']
  .reduce((acc, key) => ({ ...acc, [key]: true }), {})

function lookup(key, lang, fallback) {
  for (const code of languageChain(lang)) {
    const text = UI_TEXT[code]?.[key]
    if (text) return text
  }
  return fallback
}

export const cropLabel = (key, lang) => lookup(`crop_${key}`, lang, key)
export const stageLabel = (key, lang) => lookup(`stage_${key}`, lang, key)
