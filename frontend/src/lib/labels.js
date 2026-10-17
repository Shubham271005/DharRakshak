// Display names for crops and growth stages in every language.
// Crop keys MUST match the "crop" field in shared/content/labels.json —
// these are exactly the 14 crops the image model (Component 4) recognises.
// Most common crops for the demo are listed first.

export const CROP_OPTIONS = {
  tomato: { en: 'Tomato', hi: 'टमाटर' },
  potato: { en: 'Potato', hi: 'आलू' },
  corn: { en: 'Maize (corn)', hi: 'मक्का' },
  pepper_bell: { en: 'Bell pepper', hi: 'शिमला मिर्च' },
  soybean: { en: 'Soybean', hi: 'सोयाबीन' },
  grape: { en: 'Grape', hi: 'अंगूर' },
  apple: { en: 'Apple', hi: 'सेब' },
  orange: { en: 'Orange (citrus)', hi: 'संतरा' },
  peach: { en: 'Peach', hi: 'आड़ू' },
  cherry: { en: 'Cherry', hi: 'चेरी' },
  strawberry: { en: 'Strawberry', hi: 'स्ट्रॉबेरी' },
  squash: { en: 'Squash', hi: 'स्क्वैश' },
  blueberry: { en: 'Blueberry', hi: 'ब्लूबेरी' },
  raspberry: { en: 'Raspberry', hi: 'रास्पबेरी' },
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
