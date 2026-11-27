# Data Contract: what each screen receives

This page is for the frontend teammates. The real definitions are in `shared/contract.py`, and a full example is in `shared/sample_data.json`. **Build your screen by reading from `sample_data.json`.** The real backend will send exactly the same shape later, so your screen won't need to change.

## Rules everyone follows

1. **Text is localised.** Any text shown to the farmer looks like `{"en": "...", "hi": "...", "mr": "...", "pa": "...", "bgc": "...", "bho": "..."}`. Show the version for the language the farmer picked. Never hard-code farmer-facing English in a screen. `en` and `hi` are the only *required* keys (`REQUIRED_LANGUAGES` in `shared/contract.py`); the other four may be absent, and `LocalizedText.in_lang()` falls back to `en`.
2. **Confidence is 0–1.** Show `0.68` as `68%` or as a bar. Always say "possible", never "confirmed".
3. **Risk is an estimate.** Always show the word *estimate* next to the risk level.
4. **Money is whole rupees.** Show `48000` as `₹48,000`.
5. **Weather can be missing.** `weather` is `null` when the weather service can't be reached. Show "Weather unavailable" and never invent numbers.
6. **Mock data is labelled.** If `data_source` is `"mock"` or the weather `source` is `"mock"`, show a visible **MOCK DATA** tag.
7. **Never show pesticide names or doses.** The backend rejects dose-like wording with a filter before it reaches you. Product *names* are prevented only by the system prompt, so treat any named product with suspicion and do not add one yourself.

## Which part of the sample file belongs to whom

| Screen | Owner | Key in `sample_data.json` | Fields you'll use |
|---|---|---|---|
| Crop registration + profile card | Teammate 1 | `crop_profile` (the form saves a `CropProfileCreate`) | `crop_type`, `variety`, `sowing_date`, `days_since_sowing`, `area_acres`, `location.name`, `stage`, `expected_harvest_start/end`, `yield_estimate` (null = "range pending") |
| Analysis results | Teammate 2 | `analysis` | `predictions[]` (`display_name`, `confidence`), `uncertain` + `uncertainty_message`, `weather.summary` + `weather.source`, `risk.level`, `risk.reasons[]`, `action_cards[]` (`priority`, `title`, `detail`, `why`), `explanation.summary`, `explanation.verify`, `is_demo` |
| Finance & loans | Teammate 3 | `loan_summary` | `data_source`, `loan.display_name`, `loan.status`, `loan.outstanding_amount_inr`, `loan.next_repayment`, `documents[]` (`name`, `submitted`), `missing_document_codes`, `schemes[]` (`name`, `summary`, `official_url`, `verify_note`) |
| Chatbot + language + theme | Teammate 4 | `chat_examples` | `request.message`, `reply.reply`, `reply.lang`, `reply.is_fallback` |

## How screens get data

Never open `sample_data.json` or call `fetch()` directly. Use the functions in `frontend/src/api/client.js`: `getHealth`, `listCrops`, `getCropProfile`, `saveCropProfile`, `getWeather`, `getCurrentPosition`, `analyzeImage`, `getHistory`, `getLatestAnalysis`, `getLoanSummary`, `setDocumentSubmitted`, `sendChat` (with conversation history), `transcribeAudio` (voice → text). They read the sample file in mock mode and the real backend in api mode.

The easiest way to load data in a screen:

```jsx
const { data, loading, error, reload } = useApiData(() => getLoanSummary(cropId), [cropId])
```

Text helpers from `useLanguage()`:
- `t('key')` returns a UI label. The labels live in `shared/i18n/*.json` — **six files**, one per language: `en`, `hi`, `mr`, `pa`, `bgc` (Haryanvi), `bho` (Bhojpuri). Each currently has the same 180 keys. Add a new key to **all six** (`pytest tests/test_i18n.py` checks that every file has every key and that no key is missing a script).
- `tr(obj)` picks the right language from backend text like `{en, hi}`.

## Colours (everyone uses these)

In React, use the Tailwind class names (`bg-forest`, `text-rust`, `bg-tint`, `bg-gold/20`, …), defined in `frontend/src/index.css`. The table below gives the matching `--color-*` token name as well, because the hex alone does not tell you what to type.

| Use | Token / class suffix | Hex |
|---|---|---|
| Deep forest green (headers, sidebar) | `forest` | `#1F3D2B` |
| Green (buttons, main bars, active state) | `moss` | `#2E6B3F` |
| Leaf green (secondary bars, low risk) | `leaf` | `#7FA65A` |
| Gold (highlights, MOCK tags, moderate risk) | `gold` | `#C9A227` |
| Rust red (risk *elevated*, missing documents) | `rust` | `#B5502F` |
| Warm off-white (page background) | `cream` | `#F7F5EF` |
| Pale leaf tint (card backgrounds) | `tint` | `#E8EFE0` |
| Soft highlight background | `goldtint` | `#FBF3DC` |
| Body text | `ink` | `#1B2A20` |
| Secondary text | `muted` | `#5E6B60` |

## Changing the contract

Need a new field? Don't add it only in your screen. Ask the backend owner to:

1. Add it in `shared/contract.py`.
2. Add a sample value in `shared/sample_data.json`.
3. Run `python scripts/check_sample_data.py`. It must print `OK`.
