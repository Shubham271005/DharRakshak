# Data Contract: what each screen receives

This page is for the frontend teammates. The real definitions are in `shared/contract.py`, and a full example is in `shared/sample_data.json`. **Build your screen by reading from `sample_data.json`.** The real backend will send exactly the same shape later, so your screen won't need to change.

## Rules everyone follows

1. **Text is bilingual.** Any text shown to the farmer looks like `{"en": "...", "hi": "..."}`. Show the version for the language the farmer picked. Never hard-code farmer-facing English in a screen.
2. **Confidence is 0–1.** Show `0.68` as `68%` or as a bar. Always say "possible", never "confirmed".
3. **Risk is an estimate.** Always show the word *estimate* next to the risk level.
4. **Money is whole rupees.** Show `48000` as `₹48,000`.
5. **Mock data is labelled.** If `data_source` is `"mock"` or the weather `source` is `"mock"`, show a visible **MOCK DATA** tag.
6. **Never show pesticide names or doses.** The backend won't send any. Don't add any.

## Which part of the sample file belongs to whom

| Screen | Owner | Key in `sample_data.json` | Fields you'll use |
|---|---|---|---|
| Crop registration + profile card | Teammate 1 | `crop_profile` (the form saves a `CropProfileCreate`) | `crop_type`, `variety`, `sowing_date`, `days_since_sowing`, `area_acres`, `location.name`, `stage`, `expected_harvest_start/end`, `yield_estimate` (null = "range pending") |
| Analysis results | Teammate 2 | `analysis` | `predictions[]` (`display_name`, `confidence`), `uncertain` + `uncertainty_message`, `weather.summary` + `weather.source`, `risk.level`, `risk.reasons[]`, `action_cards[]` (`priority`, `title`, `detail`, `why`), `explanation.summary`, `explanation.verify`, `is_demo` |
| Finance & loans | Teammate 3 | `loan_summary` | `data_source`, `loan.display_name`, `loan.status`, `loan.outstanding_amount_inr`, `loan.next_repayment`, `documents[]` (`name`, `submitted`), `missing_document_codes`, `schemes[]` (`name`, `summary`, `official_url`, `verify_note`) |
| Chatbot + language + theme | Teammate 4 | `chat_examples` | `request.message`, `reply.reply`, `reply.lang`, `reply.is_fallback` |

## How screens get data

Never open `sample_data.json` or call `fetch()` directly. Use the functions in `frontend/src/api/client.js`: `getCropProfile`, `saveCropProfile`, `analyzeImage`, `getLatestAnalysis`, `getLoanSummary`, `sendChat`. They read the sample file in mock mode and the real backend in api mode.

The easiest way to load data in a screen:

```jsx
const { data, loading, error, reload } = useApiData(() => getLoanSummary(cropId), [cropId])
```

Text helpers from `useLanguage()`:
- `t('key')` returns a UI label from `src/i18n/uiText.js`.
- `tr(obj)` picks the right language from backend text like `{en, hi}`.

## Colours (everyone uses these)

In React, use the Tailwind class names (`bg-forest`, `text-rust`, `bg-tint`, `bg-gold/20`, …), defined in `frontend/src/index.css`.

| Use | Hex |
|---|---|
| Deep forest green (headers, sidebar) | `#1F3D2B` |
| Green (buttons, bars) | `#2E6B3F` |
| Leaf green (secondary bars) | `#7FA65A` |
| Gold (highlights, tags) | `#C9A227` |
| Rust red (risk *elevated*, missing documents) | `#B5502F` |
| Warm off-white (page background) | `#F7F5EF` |
| Pale leaf tint (card backgrounds) | `#E8EFE0` |

## Changing the contract

Need a new field? Don't add it only in your screen. Ask the backend owner to:

1. Add it in `shared/contract.py`.
2. Add a sample value in `shared/sample_data.json`.
3. Run `python scripts/check_sample_data.py`. It must print `OK`.
