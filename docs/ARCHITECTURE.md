# DharRakshak — System Architecture

This page describes how the app is actually wired. Every statement below is derived from the
source files named in each section — not from the pitch, and not from other docs. Where an
existing document disagrees with the code, the code wins; those disagreements are listed in
[Appendix: where docs and code differ](#appendix-where-docs-and-code-differ).

Verified against commit `3d6702f`.

## Contents

1. [Layers at a glance](#1-layers-at-a-glance)
2. [Repository layout](#2-repository-layout)
3. [Frontend ↔ backend communication](#3-frontend--backend-communication)
4. [Image classification workflow](#4-image-classification-workflow)
5. [Weather workflow](#5-weather-workflow)
6. [Risk, action cards and explanation](#6-risk-action-cards-and-explanation)
7. [Database structure and data flow](#7-database-structure-and-data-flow)
8. [Chatbot and voice workflow](#8-chatbot-and-voice-workflow)
9. [Error handling and fallbacks](#9-error-handling-and-fallbacks)
10. [Configuration reference](#10-configuration-reference)

---

## 1. Layers at a glance

| Layer | Technology | Entry point |
|---|---|---|
| Frontend | React 19, Vite 7, Tailwind CSS v4, Lucide icons | `frontend/src/main.jsx` → `App.jsx` |
| HTTP API | FastAPI + uvicorn, all routes under `/api` | `backend/main.py` |
| Data access | SQLite (stdlib `sqlite3`) | `backend/db.py`, `backend/repository.py` |
| Image model | PyTorch **or** ONNX Runtime, behind one interface | `backend/ml/` |
| Decision engines | Pure Python + JSON content | `backend/engines/` |
| Weather / geocoding | Open-Meteo (free, no key) | `backend/services/weather.py`, `geocoding.py` |
| Chat / speech-to-text | Groq API (OpenAI-compatible) | `backend/services/llm.py`, `chat.py` |
| Text-to-speech | The browser's own speech synthesis | `frontend/src/lib/speech.js` |
| Shared contract | Pydantic models — the single source of truth | `shared/contract.py` |

The rule that holds the design together: **the backend never returns a payload that does not
match `shared/contract.py`**, because every route declares `response_model=`. The frontend never
invents its own data shapes; `frontend/src/api/client.js` is the only module that talks to the API.

## 2. Repository layout

| Path | Role |
|---|---|
| `backend/main.py` | FastAPI app, lifespan, CORS, all 12 routes |
| `backend/db.py` | Connection helper + SQL schema |
| `backend/repository.py` | The **only** module that reads or writes SQL |
| `backend/pipeline.py` | One photo → one `AnalysisResult` |
| `backend/sample_store.py` | Loads `shared/sample_data.json`; chat fallback answers |
| `backend/ml/classifier.py` | Model registry, download, ranking, uncertainty |
| `backend/ml/models.py` | `DakshMobileNetV2`, `DakshOnnx`, `HuggingFaceBackend` |
| `backend/ml/preprocess.py` | EXIF fix, quality checks, leaf segmentation (OpenCV) |
| `backend/ml/classifier_labels.py` | The 38 `ClassInfo` entries |
| `backend/engines/` | `facts.py`, `risk.py`, `actions.py`, `explain.py`, `content.py` |
| `backend/services/` | `weather.py`, `geocoding.py`, `llm.py`, `chat.py` |
| `shared/contract.py` | Pydantic models + language constants |
| `shared/content/` | Rules and farmer-facing text as JSON |
| `shared/i18n/` | UI labels, one file per language |
| `frontend/src/api/client.js` | Every network call, both mock and api mode |
| `frontend/src/screens/` | One file per screen |
| `tests/` | Backend tests (model, engines, weather, i18n, LLM, API) |

## 3. Frontend ↔ backend communication

### Two data modes

`frontend/src/api/client.js` is the single data boundary. It picks a mode at **build time**
(Vite inlines `import.meta.env`):

| Mode | Selected by | Behaviour |
|---|---|---|
| `mock` | default (anything other than `api`) | Returns data from `shared/sample_data.json` after a 300 ms delay, so loading states are visible. No backend needed. |
| `api` | `VITE_API_MODE=api` | Calls the FastAPI backend. |

Screens are identical in both modes — they import functions, never `fetch()` and never the
sample JSON directly.

### Where the API lives

- `VITE_API_BASE` (optional) — absolute origin. Empty means same-origin.
- In development, Vite proxies `/api` to `http://localhost:8000`
  (`frontend/vite.config.js`, override with `DHARRAKSHAK_API_PROXY`), so the browser never
  makes a cross-origin request.
- `frontend/.env.production` sets `VITE_API_MODE=api` and
  `VITE_API_BASE=https://dharrakshak-api.onrender.com` for the deployed build.
- Requests are built as `${API_BASE}/api${path}`. On failure the client reads FastAPI's
  `detail` field (a string, or a list of `{msg}` for 422) and throws `ApiError(message, status)`,
  where `status: 0` means the network itself failed.

### CORS

`backend/main.py` allows `http://localhost:5173`, `http://127.0.0.1:5173`, any
`https://*.vercel.app` origin, plus anything listed in `DHARRAKSHAK_CORS_ORIGINS`
(comma-separated).

### The API surface

12 routes, all mounted under `/api` (`main.py`, `@router.<verb>`):

| Method | Path | Purpose | Errors |
|---|---|---|---|
| GET | `/health` | `status`, `stage`, whether the model is `loaded`/`not_loaded`, whether chat is `configured` | — |
| POST | `/crops` | Register a farmer + crop → `201` | 404 unknown `farmer_id`, 422 validation |
| GET | `/crops` | All crops, newest first, with check summaries | — |
| GET | `/crops/{crop_id}` | One crop | 404 |
| PUT | `/crops/{crop_id}` | Edit a crop, same ID, history kept | 404, 422 |
| GET | `/crops/{crop_id}/weather` | Real weather | 404, 503 weather down |
| POST | `/crops/{crop_id}/analyze` | Upload a leaf photo → analysis | 400, 404, 413, 415, 503 |
| GET | `/crops/{crop_id}/history` | Analyses, newest first | 404 |
| GET | `/crops/{crop_id}/loan` | Mock loan summary | 404 (crop or no loan) |
| PUT | `/crops/{crop_id}/loan/documents/{code}` | Tick/untick a document | 404 |
| POST | `/chat` | Grounded chatbot reply | 404 |
| POST | `/voice/transcribe` | Speech → text | 400, 413, 415, 422, 503 |

### The app shell

`frontend/src/App.jsx` holds two pieces of state and passes both to every screen:

- `screenId` — one of `dashboard`, `analysis`, `profile`, `finance`, `chat`. Kept in the URL
  hash (`#finance`), so refresh and browser Back/Forward work.
- `cropId` — the active crop, persisted in `localStorage` under `dharrakshak.crop`.

Each screen gets `cropId`, `onCropChange` and `onNavigate`, and is wrapped in its own
`ErrorBoundary keyed on the screen id`, so one broken screen cannot take down the others.
If the remembered crop returns 404 (for example after `python scripts/reset_db.py`), the shell
silently falls back to the demo crop.

## 4. Image classification workflow

`POST /api/crops/{crop_id}/analyze` takes a multipart body with one field, `image`.

```
validate upload → load classifier → threadpool → preprocess → model → flip TTA
      → rank top 3 → uncertainty flags → weather → risk → cards → explanation → save
```

**Step 1 — upload checks** (`main.py`). Content type must be one of `image/jpeg`,
`image/png`, `image/webp` (else `415`); the body must be non-empty (`400`); at most
8 MB (`413`).

**Step 2 — load the classifier.** `clf.get_classifier()` runs in a worker thread and returns a
process-wide singleton (`_instance` guarded by a `_lock`). If weights are missing,
`ModelNotAvailable` becomes a `503`. The model is normally loaded during the lifespan startup
unless `DHARRAKSHAK_PRELOAD_MODEL=0`.

**Step 3 — decode and preprocess.** `classifier._decode` uses Pillow and raises `InvalidImage`
if the bytes are not an image (`400`). `preprocess()` then applies `DEFAULT_STEPS`:

| Step | Default | What it does |
|---|---|---|
| `exif` | **on** | Rotates phone photos using EXIF orientation |
| `quality` | **on** | Flags blurry, dark, flat and tiny photos |
| `leaf_crop` | **on** | HSV segmentation (green + yellow/brown lesions), crops with an 8% margin, falls back to the full frame |
| `background` | off | Greys out pixels far from the leaf |
| `white_bal` | off | Grey-world white balance |
| `clahe` | off | Local contrast on the lightness channel |
| `denoise` | off | Bilateral filter |

Quality thresholds (`preprocess.py`): blur = Laplacian variance `< 40`, dark = mean grey
`< 25`, flat = grey std `< 12`, tiny = shortest side `< 64` px.

**Step 4 — infer.** `classifier._probs` calls the backend on the image **and on its mirror
image**, and averages the two (flip test-time augmentation, `USE_FLIP_TTA = True`).

**Step 5 — rank.** `classify()` sorts all 38 class probabilities and takes the top 3
(`TOP_K = 3`). Each `Prediction` carries the **true** probability — it is not renormalised
within a crop, because rescaling made single-class crops always report 100%.

**Step 6 — honest flags.** Two independent signals:

- `crop_mismatch` — true when the top-1 class belongs to a different crop than
  `crop.crop_type`. It only adds a warning and a "check the crop in the photo" card; it does
  not change the prediction.
- `uncertain` + `uncertainty_message` — a poor-quality photo gets the retake message;
  otherwise a top-1 probability below `UNCERTAIN_THRESHOLD = 0.50` gets the uncertain message.
  (The constant's own comment calls this the no-crop path, but `classify()` applies it the same
  way whether or not a crop is registered.)

> Note: `MARGIN_THRESHOLD = 0.30` is declared in `classifier.py` but not read by any code path.
> The gap-based rule described in `docs/MODEL_CARD.md` is therefore not what the running code
> does — see the appendix.

### The model registry

`classifier.MODELS` holds four entries. `DHARRAKSHAK_MODEL` picks one; the default is
`DakshMobileNetV2`'s entry.

| Key | Repo | Field top-1 | Notes |
|---|---|---|---|
| `linkanjarad-mobilenetv2` | `linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification` | 0.62 | Highest field accuracy; license not stated |
| `dinov2-small` | `rodynaemad/plant-disease-dinov2-small` | 0.52 | CC-BY-SA-4.0 |
| `convnext-tiny` | `JohnSupertramp2026/convnext-tiny-plantvillage` | 0.49 | Apache-2.0 |
| `daksh-mobilenetv2` | — (`legacy: True`) | 0.45 | **The default.** Has no `repo`/`revision`, so `download_model.py` cannot fetch it |

### The three backends

| Class | Runtime | Weights | Label handling |
|---|---|---|---|
| `DakshMobileNetV2` | PyTorch | `mobilenetv2_plant.pth`, `strict=True` | Class order is already ours |
| `DakshOnnx` | ONNX Runtime | `mobilenetv2_plant.onnx` | Class order is already ours |
| `HuggingFaceBackend` | PyTorch + `transformers` | HF snapshot folder | Its own `id2label` is mapped onto our labels by `map_labels()`, which **raises** unless the mapping is a perfect one-to-one |

`DakshOnnx` is chosen automatically for the legacy model when the `.onnx` file exists and
`DHARRAKSHAK_RUNTIME` is `onnx` (the default). That is how the free Render deploy runs
PyTorch-free. Thread count comes from `DHARRAKSHAK_THREADS`.

All three return probabilities in the order of `shared/content/labels.json`, which is why the
file's `_about` warns that **order matters**.

## 5. Weather workflow

`backend/services/weather.py` wraps Open-Meteo's forecast API. No API key.

1. `fetch_daily(lat, lon)` requests four daily variables — `precipitation_sum`,
   `relative_humidity_2m_mean`, `temperature_2m_mean`, `precipitation_probability_max` — with
   `past_days=3`, `forecast_days=4` (today + next 3) and `timezone=auto`, so days follow the
   farmer's own calendar. Timeout 8 s.
2. `parse_weather()` treats index 3 as today. The past window is days 0–2; the forecast window
   is days 4–6. It computes total rain, mean humidity and mean temperature for the past,
   total expected rain and the highest rain chance for the forecast. Missing values are
   skipped, never treated as zero. Too few days, or no usable recent values, raises
   `WeatherUnavailable`.
3. A farmer-facing summary is assembled from `shared/content/messages.json`
   (`weather_past`, then one of `weather_next_dry` / `weather_next_light` / `weather_next_rain`,
   then `weather_source`) and filled in every supported language.

**Caching.** `get_weather()` caches successful results for 30 minutes
(`CACHE_SECONDS = 30*60`) keyed on `round(lat, 2), round(lon, 2)` — roughly a 1 km cell, so
neighbouring farms share an entry. Failures are **not** cached, so a retry after an outage can
succeed.

**Honesty rule.** On `WeatherUnavailable` or a `ValueError` from parsing, `get_weather()`
returns `None` and logs a warning. It never fabricates numbers. An analysis with
`weather: null` is valid — the risk engine emits a zero-point "weather unavailable" reason
instead.

**Geocoding** (`backend/services/geocoding.py`) is the sibling service. It splits the typed
place on commas, searches each part against Open-Meteo's search API restricted to
`countryCode=IN`, prefers a result whose `admin1`/`admin2`/`admin3` matches one of the other
parts (so "Aurangabad, Bihar" resolves to Bihar, not Maharashtra), and otherwise takes the most
populous match. Results are memoised with `lru_cache(maxsize=256)` on the accent- and
case-normalised query; failures are not cached.

## 6. Risk, action cards and explanation

`backend/engines/` turns the model output plus weather plus crop stage into three parts of the
`AnalysisResult`. The rules and all wording live in `shared/content/*.json`, so they can change
without touching Python.

### Facts

`facts.Facts` is a frozen dataclass that answers yes/no questions, keeping the engines away from
raw model or weather objects. Thresholds come from `shared/content/risk_rules.json`:

| Threshold | Value | Used by |
|---|---|---|
| `high_confidence` | 0.8 | `disease_high_confidence` |
| `wet_recent_rain_mm` | 10 | `wet_recently` |
| `wet_recent_humidity_pct` | 80 | `wet_recently` |
| `rain_forecast_mm` | 5 | `rain_expected` |
| `rain_forecast_chance_pct` | 60 | `rain_expected` |
| `hot_dry_temp_c` | 28 | `hot_and_dry` |
| `hot_dry_humidity_pct` | 60 | `hot_and_dry` |
| `sensitive_stages` | `flowering`, `fruiting` | `sensitive_stage` |

`WEATHER_SENSITIVE_TYPES = {"fungal", "bacterial"}` — only those two spread types react to wet
weather. Each of the 38 classes carries a `type` in `labels.json` (19 fungal, 12 healthy,
3 bacterial, 2 insect-spread, 1 pest, 1 viral).

### Risk score

`assess_risk()` evaluates rules in a fixed order, and **every rule that fires adds both points
and a reason sentence**, which is what makes the "Why?" traceable:

1. **Photo** — `unclear_photo`, `looks_healthy`, `disease_high_confidence` or `disease_possible`
2. **Photo vs profile** — `crop_mismatch` (0 points, information only)
3. **Weather**, matched to spread type — `wet_recent_disease` / `rain_forecast_disease` for
   fungal and bacterial, `hot_dry_pest` for pests, `wet_recent_healthy` for a healthy leaf, or
   `weather_unavailable` (0 points)
4. **Stage** — `sensitive_stage`, only when a problem was actually detected

`level_for(score)`: `>= 5` → `elevated`, `>= 3` → `moderate`, else `low`. Every `Risk` is
constructed with `is_estimate=True`, which the contract types as `Literal[True]`.

### Action cards

`choose_cards()` builds the shortlist from an `ELIGIBLE` dict of 11 card IDs, each with a
condition over `Facts`, and sorts by the `weight` in `action_cards.json`. When a disease is
detected, that disease's own steps from `disease_advice.json` join the list at weights 90 and 89
and **replace** the generic `inspect_nearby` card. The top `max_cards` (3) are kept and numbered
1…N; `AnalysisResult._check_consistency` rejects gaps or duplicates.

Cards only ever suggest checking, verifying, monitoring and basic hygiene. `tests/test_engines.py`
enforces the absence of pesticide and dose vocabulary.

### Explanation

`build_explanation()` keeps at most 3 reasons (`MAX_REASONS`), preserving the rule order and
dropping the lowest-scoring entries first. It picks one `verify` sentence — `uncertain`,
`healthy`, or `disease` — and, when a disease was detected, attaches `about` and `look_for` text
from `disease_advice.json` so the explanation is about that specific disease.

## 7. Database structure and data flow

SQLite in a single file. Default `data/dharrakshak.sqlite3`, overridden by `DHARRAKSHAK_DB`.
`connect()` is a context manager that commits on success, rolls back on error, always closes,
and sets `PRAGMA foreign_keys = ON` on every connection.

| Table | Key columns | Purpose |
|---|---|---|
| `farmers` | `farmer_id`, `name`, `preferred_language` | One row per farmer |
| `crops` | `crop_id`, `farmer_id` → farmers, `sowing_date`, `area_acres`, `location_name`, `latitude`, `longitude`, `stage`, yield range | A crop profile (F2) |
| `analyses` | `analysis_id`, `crop_id` → crops, `created_at`, `top_label`, `risk_level`, `is_demo`, **`result_json`** | Every leaf check |
| `loans` | `loan_id`, `farmer_id` → farmers, amounts, `next_due_*`, `data_source` | Mock loan (F5) |
| `loan_documents` | `(loan_id, code)`, `name_json`, `submitted`, `position` | Document checklist |

Design points worth knowing:

- **`analyses` stores the whole `AnalysisResult` as JSON** (`result_json`), which is already
  validated by the contract. Only `top_label`, `risk_level` and `is_demo` are copied into
  columns for querying. There is an index on `(crop_id, created_at)`.
- **`days_since_sowing` is computed on every read**, never stored, so it is always current
  (`repository._row_to_crop`).
- **`missing_document_codes` is derived** from the checklist on read, and the contract
  re-validates that it matches the unsubmitted documents.
- **Schemes come from `shared/content/schemes.json`**, selected by loan type, not from the DB.
- "My crops" is every crop in the database — there is no login yet.

### Startup

`lifespan` runs three steps: `init_db()` creates any missing tables, `seed_demo_if_empty()` inserts
the demo farmer, crop, loan and sample analysis from `shared/sample_data.json` **if and only
if** no crop exists, then the image model is preloaded. The seed is what gives the demo an
`is_demo: true` analysis; every analysis produced by the pipeline sets `is_demo=False`.

### The photo round trip

```
React AnalysisScreen
  └─ analyzeImage(cropId, file)              client.js → multipart POST
     └─ /api/crops/{id}/analyze              main.py: validate, 415/400/413
        └─ run_in_threadpool(run_analysis)   main.py: CPU work off the event loop
           ├─ classifier.classify(...)       top-3 + uncertainty + crop_mismatch
           ├─ weather.get_weather(lat, lon)  Open-Meteo, or None
           ├─ assess_risk(facts)             points + reason sentences
           ├─ choose_cards(facts)            top 3 ranked next steps
           └─ build_explanation(facts, risk) summary + verify + disease notes
        └─ repository.save_analysis(result)  inserts result_json
     └─ AnalysisResult (JSON)                contract-validated by response_model
  └─ screen renders predictions, risk, cards, "Why?"
```

## 8. Chatbot and voice workflow

### Chat

`POST /api/chat` accepts `ChatRequest`: `crop_id`, `message` (≤ 1000 chars), `lang`, and up to
20 earlier `history` turns. The frontend sends the last 20 (`history.slice(-20)`); the backend
forwards only the last 8 (`HISTORY_TURNS`).

`chat.build_context(crop)` assembles this farmer's saved data into one JSON block and reports
which parts it used:

- `crop_profile` — always
- `latest_leaf_check` — the newest analysis: possibilities, risk level and reasons, action cards
- `weather` — the summary from that analysis, when present
- `loan` — status, outstanding amount, next repayment, submitted/missing documents, schemes

That list becomes `ChatReply.used_context`. The messages sent to Groq are: the `SYSTEM_RULES`
prompt (role, safety rules, reply language, plain text only because replies may be read aloud),
a second system message holding the context JSON, the history turns, then the question.

`llm.chat_complete()` tries `GROQ_CHAT_MODEL`, then `GROQ_FALLBACK_MODEL`, but only for errors
worth retrying (`408`, `429`, `500`, `502`, `503`, `504`, or a transport error). `gpt-oss` models
get `reasoning_effort=low`; others get `reasoning_format=hidden`, so neither leaks its thinking
into the reply.

### Two safety layers

1. **The prompt** forbids naming pesticides, fungicides, insecticides or chemicals, giving doses
   or spray schedules, promising loan approval, inventing amounts or dates, and repeating
   personal ID or account numbers. Treatment questions are redirected to the local agriculture
   extension office or Krishi Vigyan Kendra.
2. **A regex guard.** `_guard()` scans every reply for dose-like patterns — a number followed by
   `ml`/`g`/`kg`/`litre`/`%` and `/`/`per`/`प्रति`, in English or Devanagari. A match is
   discarded and replaced with `messages.json → chat_safe_referral` in the farmer's language.

### Voice

There is no server-side speech synthesis. The loop is:

```
useRecorder()  →  POST /api/voice/transcribe  →  text  →  /api/chat  →  useSpeaker()
```

- `POST /api/voice/transcribe` accepts multipart `audio` plus a `lang` form field. Allowed
  types include `audio/webm`, `ogg`, `wav`, `mpeg`, `mp4`/`m4a`, `flac` and `video/webm` (some
  browsers label recordings that way). Empty → `400`, over 10 MB → `413`, unsupported → `415`.
- `llm.transcribe()` posts to Groq with `whisper-large-v3`, `response_format=verbose_json`,
  `temperature=0`, and passes the language only for `en`, `hi`, `mr`, `pa`. Haryanvi and
  Bhojpuri have no Whisper model, so the frontend sends `hi`.
- `clean_transcript()` drops segments Whisper rates as probably-not-speech
  (`no_speech_prob >= 0.6`) and returns `""` when the transcript is a single word repeated —
  that was a real failure where a beep became "प्रस्तुति प्रस्तुति प्रस्तुति". An empty result
  becomes a `422` asking the farmer to try again.
- The reply is spoken by the browser. `useSpeaker()` picks the voice for the language and tells
  the user when the device has none installed.

### When Groq is unavailable

`LLMUnavailable` is caught in `chat.answer()`, which returns `mock_chat_reply(request)` — the
saved answers from `shared/sample_data.json` — with `is_fallback=True`. The UI labels these so
the farmer is never told a canned answer is live model output.

## 9. Error handling and fallbacks

### HTTP status codes

| Code | Raised when | Where |
|---|---|---|
| `400` | Upload empty; bytes not a readable image; recording empty | `main.py`, `classifier.InvalidImage` |
| `404` | Unknown crop; unknown document code; no loan records; unknown `farmer_id` | `main.py`, `repository.UnknownFarmer` |
| `413` | Photo > 8 MB; recording > 10 MB | `main.py` |
| `415` | Image not JPEG/PNG/WebP; unsupported audio type | `main.py` |
| `422` | Pydantic validation (future sowing date, `area_acres > 1000`, latitude without longitude); place name not found; no speech heard | `contract.py`, `geocoding.LocationNotFound` |
| `503` | Model weights missing; geocoding or weather unreachable; voice unreachable | `clf.ModelNotAvailable`, `GeocodingUnavailable`, `WeatherUnavailable`, `LLMUnavailable` |

### Graceful degradation

| Failure | Consequence |
|---|---|
| Weather service down | `weather` is `null`; the analysis still succeeds and the risk engine records a 0-point "weather unavailable" reason. `GET /weather` alone returns `503`. |
| Geocoding down | Crop create/edit returns `503` with a message suggesting device location. An unknown name returns `422` with a suggestion. Unchanged names reuse stored coordinates. |
| Image model missing | The API still starts; `/analyze` returns `503` until weights exist. `/health` reports `model: not_loaded`. |
| Groq unreachable or no key | Chat falls back to saved answers marked `is_fallback: true`; voice returns `503` with "please type your question". |
| Backend unreachable | The client throws `ApiError` with `status: 0`; screens show `ErrorBox` with a retry. |
| One screen crashes | Its `ErrorBoundary` catches it; the rest of the app keeps working. |
| Remembered crop deleted | The shell falls back to the demo crop on `404`. |
| No backend at all | `mock` mode serves `shared/sample_data.json`, so the UI is fully explorable. |

## 10. Configuration reference

| Variable | Default | Effect |
|---|---|---|
| `GROQ_API_KEY` | — | Chat + speech-to-text. Without it, chat uses saved answers and voice is unavailable. |
| `GROQ_CHAT_MODEL` | `openai/gpt-oss-120b` | Primary chat model |
| `GROQ_FALLBACK_MODEL` | `qwen/qwen3.8-27b` | Tried when the primary is rate-limited or down |
| `GROQ_STT_MODEL` | `whisper-large-v3` | Speech-to-text model |
| `DHARRAKSHAK_MODEL` | `daksh-mobilenetv2` | Which entry of `classifier.MODELS` to use |
| `DHARRAKSHAK_RUNTIME` | `onnx` | `onnx` runs the legacy model without PyTorch |
| `DHARRAKSHAK_THREADS` | `2` | ONNX Runtime intra-op threads |
| `DHARRAKSHAK_DB` | `data/dharrakshak.sqlite3` | Database file |
| `DHARRAKSHAK_PRELOAD_MODEL` | `1` | `0` skips loading the model at startup (tests do this) |
| `DHARRAKSHAK_CORS_ORIGINS` | — | Extra allowed browser origins, comma-separated |
| `DHARRAKSHAK_API_PROXY` | `http://localhost:8000` | Vite dev proxy target |
| `VITE_API_MODE` | `mock` | `api` talks to the backend |
| `VITE_API_BASE` | same origin | Absolute backend origin for builds |

`.env` is git-ignored; `.env.example` documents the keys.

---

## Appendix: where docs and code differ

These are known drifts between the current documentation and the current source. They are
recorded here rather than silently "fixed", because the code is out of scope for this document.

| Document | Says | Code does |
|---|---|---|
| `docs/MODEL_CARD.md` | Ranking is crop-aware: only the registered crop's classes are ranked | `classifier.classify()` ranks all 38 and only *warns* via `crop_mismatch` |
| `docs/MODEL_CARD.md` | Uncertain when the within-crop top-2 gap is under 0.30 | `MARGIN_THRESHOLD` is unused; the live check is top-1 `< 0.50` |
| `backend/ml/classifier.py` header | Leaf crop is off because it did not help | `DEFAULT_STEPS` includes `leaf_crop`, so it is on |
| `docs/MODEL_CARD.md` | Default model is linkanjarad (60% field top-1) | `DEFAULT_MODEL` is `daksh-mobilenetv2` (45%) |
| `backend/main.py` `/analyze` docstring | Risk, cards and explanation are still placeholders | `pipeline.py` produces all three for real |
| `README.md` setup | `python scripts/download_model.py` downloads the weights | The legacy default has no `repo`, so that call cannot succeed; the `.onnx` weights are already committed |

The last row is the one that affects a fresh clone: weights ship in the repository, so nothing
needs downloading for the app to run.
