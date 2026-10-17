// Display names for crops and growth stages in every language.
// The crop list must match the image model's classes (chosen in Component 4).

export const CROP_OPTIONS = {
  tomato: { en: 'Tomato', hi: 'टमाटर' },
  potato: { en: 'Potato', hi: 'आलू' },
  pepper_bell: { en: 'Bell pepper', hi: 'शिमला मिर्च' },
  corn: { en: 'Maize (corn)', hi: 'मक्का' },
  apple: { en: 'Apple', hi: 'सेब' },
  grape: { en: 'Grape', hi: 'अंगूर' },
}

// Must match `CropStage` in shared/contract.py.
export const STAGE_LABELS = {
  seedling: { en: 'Seedling', hi: 'पौध' },
  vegetative: { en: 'Vegetative growth', hi: 'बढ़वार' },
  flowering: { en: 'Flowering', hi: 'फूल आना' },
  fruiting: { en: 'Fruiting', hi: 'फल लगना' },
  maturity: { en: 'Maturity', hi: 'पकना' },
}

export const cropLabel = (key, lang) => CROP_OPTIONS[key]?.[lang] ?? key
export const stageLabel = (key, lang) => STAGE_LABELS[key]?.[lang] ?? key
