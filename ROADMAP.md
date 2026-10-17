# DharRakshak — Build Roadmap

This is the guided, step-by-step plan for building the prototype. We build **one component at a time**, check it works, and stop before starting the next. Each section lists the files that get created or changed, what the component does, and how to verify it.

**Legend:** ✅ done · 🔜 next · ⬜ not started

**Features:** F1 symptom analysis · F2 crop profile + action cards · F3 context risk · F4 explainability · F5 finance & loans · F6 regional languages · F7 multilingual chatbot + voice assistant

**Team decisions that shape the plan:**
- **Real APIs over mock data.** The team has API keys, so every component that has a real service uses it. Mock data stays only where no real source can be used: loans (no bank integration), plus clearly labelled fallbacks when a service is down.
- **Ask before choosing.** Before adding the pretrained image model (Component 4) or any keyed API (LLM, voice), Claude asks which model or provider to use and for the key. Keys go in `.env`, which is never committed.
- **Voice assistant** is part of the multilingual chatbot (Component 9).

## Target folder structure

```
Dynaminds-IIITD/
├── README.md, ROADMAP.md, requirements.txt, .gitignore, .env.example
├── docs/CONTRACT.md            ← plain-language data contract for teammates
├── docs/MODEL_CARD.md, docs/DECISION_RULES.md ← model + rules, for judges (C4, C6)
├── shared/
│   ├── contract.py             ← data shapes (single source of truth)
│   ├── sample_data.json        ← mock data matching the contract
│   ├── i18n/                   ← UI strings: en.json, hi.json        (C8)
│   └── content/                ← rules, card templates, schemes, docs (C6, C7)
├── backend/
│   ├── main.py                 ← FastAPI app + routes                (C2)
│   ├── db.py                   ← SQLite connection + schema          (C3)
│   ├── repository.py           ← all database reads/writes           (C3)
│   ├── ml/classifier.py        ← pretrained image model              (C4)
│   ├── services/geocoding.py   ← place name → coordinates (Open-Meteo) (C5)
│   ├── services/weather.py     ← real weather, honest when unavailable (C5)
│   ├── engines/                ← risk.py, actions.py, explain.py     (C6)
│   ├── services/loans.py       ← mock loans + document checker       (C7)
│   ├── services/chat.py        ← grounded LLM chatbot                (C9)
│   └── services/voice.py       ← speech-to-text + text-to-speech     (C9)
├── frontend/                   ← React + Vite + Tailwind CSS v4
│   ├── package.json, vite.config.js, index.html, .env.example
│   └── src/
│       ├── App.jsx             ← app shell: sidebar + current screen  (C1)
│       ├── index.css           ← Tailwind + theme colours             (C1)
│       ├── api/client.js       ← mock OR backend data, one function per call (C1)
│       ├── api/useApiData.js   ← loading/error hook for screens       (C1)
│       ├── i18n/               ← language context + UI labels         (C1, C8)
│       ├── components/         ← Sidebar, Card, Pill, MockTag, …      (C1)
│       ├── lib/                ← formatting, crop/stage labels        (C1)
│       └── screens/            ← one file per teammate                (C1 stubs → teammates)
├── tests/test_api.py           ← backend API tests                    (C2)
├── scripts/                    ← checks and helper scripts
├── models/                     ← downloaded model weights (git-ignored)  (C4)
└── data/eval/                  ← labelled test photos (git-ignored)      (C4)
```

---

## ✅ Component 0 — Data contract + project scaffold

**Goal:** agree on the exact shape of every piece of data before any feature is built, so backend and frontend can be built in parallel.

**Files created:**
- `shared/contract.py`: Pydantic models for crop profile, analysis result, loan summary and chat. Includes built-in consistency checks: predictions are sorted, priorities have no gaps, and the missing-documents list matches the document checklist.
- `shared/sample_data.json`: one complete, realistic demo scenario (tomato, flowering, possible early blight, mock KCC loan, three chat examples including a pesticide-refusal example).
- `scripts/check_sample_data.py`: validates the sample file against the contract.
- `docs/CONTRACT.md`: plain-language version for teammates, with field ownership and colours.
- `requirements.txt`, `.gitignore`, `README.md`, this roadmap.

**Verify:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/check_sample_data.py      # must print "OK"
```

---

## ✅ Component 1 — Frontend shell + teammate screen stubs (React + Tailwind)

**Goal:** unblock the 4 teammates as early as possible. They need a running app with an empty screen each.

*(First built in Streamlit, then rebuilt in React + Tailwind at the team's request. The Streamlit version is in git history, commit `f692de9`.)*

**Files created (in `frontend/`):**
- `package.json`, `vite.config.js`, `index.html`: Vite + React 19 + Tailwind CSS v4. Vite forwards `/api/*` to the backend on port 8000.
- `src/index.css`: theme colours as Tailwind classes (`bg-forest`, `text-rust`, `bg-tint`, …) and system fonts that handle Hindi.
- `src/App.jsx`: sidebar plus the current screen. Each screen is wrapped in an error boundary so one broken screen can't crash the app. The screen is kept in the URL (`#finance`).
- `src/api/client.js`: the only place data comes from: `getCropProfile`, `saveCropProfile`, `analyzeImage`, `getLatestAnalysis`, `getLoanSummary`, `sendChat`, `getHealth`. It has **mock mode** (reads `shared/sample_data.json`) and **api mode** (calls the backend), set by `VITE_API_MODE`.
- `src/api/useApiData.js`: a hook that gives screens `data`, `loading`, `error` and `reload`.
- `src/api/types.js`: JSDoc types mirroring the contract, for editor autocomplete.
- `src/i18n/`: `LanguageContext.jsx` (`t()` for UI labels, `tr()` for backend text, remembered choice, `?lang=hi` links) and `uiText.js` (EN + HI labels).
- `src/components/`: `Sidebar`, `ErrorBoundary`, and `ui.jsx` (Card, Pill, MockTag, ScreenHeader, Loading, ErrorBox, StubBanner, RawData).
- `src/lib/`: `format.js` (₹ with Indian grouping, %, dates in EN/HI), `labels.js` (crop and stage names), `useSessionState.js`.
- `src/screens/ProfileScreen.jsx` (Teammate 1), `AnalysisScreen.jsx` (Teammate 2), `FinanceScreen.jsx` (Teammate 3), `ChatScreen.jsx` (Teammate 4). Each is a working stub with numbered TODOs and a "done when" checklist.

**Also added:** `CropProfileCreate` in `shared/contract.py`, the model for what the farmer types into the registration form (it rejects future sowing dates).

**Verify:**
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (mock mode, no backend needed)
```
You can switch between 4 screens, the language switcher changes every label, and the phone-width layout shows top tabs.

**Hand-off:** each teammate gets their screen file and `docs/CONTRACT.md`.

---

## ✅ Component 2 — Backend skeleton (FastAPI)

**Goal:** a running API that returns the sample data from every endpoint, so the frontend can switch from mock mode to "real server" mode early.

**Files created:**
- `backend/main.py`: FastAPI app, CORS for the React dev server, and all routes under `/api`. Every response is checked against `shared/contract.py`:
  - `GET /api/health`
  - `POST /api/crops` and `GET /api/crops/{crop_id}` (F2)
  - `POST /api/crops/{crop_id}/analyze`: photo upload with real checks (JPEG/PNG/WebP only, not empty, max 8 MB). It returns the sample result for now (F1, F3, F2, F4).
  - `GET /api/crops/{crop_id}/history`, newest first
  - `GET /api/crops/{crop_id}/loan`, always `data_source: "mock"` (F5)
  - `POST /api/chat`, keyword-matched sample answers, pesticide questions checked first (F7)
  - Unknown crops return 404. Bad input returns 422.
- `backend/sample_store.py`: in-memory storage seeded from the sample file. Later components replace it piece by piece.
- `tests/test_api.py` + `pytest.ini`: 14 tests covering happy paths and error cases.
- `requirements.txt`: `fastapi`, `uvicorn[standard]`, `python-multipart`, `pytest`, `httpx` (Streamlit removed).

**Verify:**
```bash
uvicorn backend.main:app --reload --port 8000    # then open http://localhost:8000/docs
pytest                                           # 14 passed
# React app against the real backend (second terminal):
cd frontend && echo "VITE_API_MODE=api" > .env && npm run dev
```
The sidebar shows **Connected to server** and every screen loads its data from the backend.

---

## ✅ Component 3 — Database (SQLite) + real crop profiles

**Goal:** crop profiles, analyses and loan records are saved for real and survive a server restart.

**Files created / changed:**
- `backend/db.py`: connection helper (commits on success, rolls back on error, foreign keys on) and the schema. Tables: `farmers`, `crops`, `analyses` (full contract JSON plus a few query columns), `loans`, `loan_documents`. The file is `data/dharrakshak.sqlite3` (git-ignored), and `DHARRAKSHAK_DB` can point elsewhere.
- `backend/repository.py`: the only module that touches SQL. It converts rows to contract models, computes `days_since_sowing` on every read, computes missing documents from the checklist, and seeds the demo data.
- `backend/main.py`: on startup it creates the tables and seeds the demo farmer, crop, analysis and mock loan if the database is empty. Changes:
  - New `PUT /api/crops/{id}` to edit a crop while keeping the same id and history.
  - Analyses are saved to the database.
  - A farmer with no loan records gets a **404 "No loan records for this farmer yet"** instead of fake data.
- `backend/sample_store.py`: reduced to the sample loader plus the two placeholders (analysis, chat) that later components replace.
- `scripts/reset_db.py`: wipes and reseeds the database. Use it before rehearsals and the final demo.
- `tests/conftest.py` + `tests/test_api.py`: each test uses its own temporary database. 19 tests, including editing a crop, the new-farmer loan 404, and data surviving a restart.
- Frontend: `saveCropProfile(form, cropId)` now edits, while `saveCropProfile(form)` registers a new crop. The ProfileScreen and FinanceScreen TODOs are updated (two save buttons, and a friendly "no loan yet" card).

**Verify:**
```bash
pytest                                   # 19 passed
uvicorn backend.main:app --reload        # create a crop in /docs, stop, restart: it's still there
python scripts/reset_db.py               # back to a clean demo state
```

---

## ✅ Component 4 — Pretrained image model (F1)

**Goal:** a real photo goes in, and the real top-3 ranked possibilities come out.

**Model chosen by the team:** [`Daksh159/plant-disease-mobilenetv2`](https://huggingface.co/Daksh159/plant-disease-mobilenetv2). MobileNetV2, PlantVillage, 38 classes across 14 crops, Apache-2.0. Pinned to an exact revision. Full details and limitations are in `docs/MODEL_CARD.md`.

**Checks done before wiring it in:**
- License: Apache-2.0, fine for our use.
- The weights file holds weight data only, with no executable code. Its SHA-256 matches Hugging Face's record.
- The repo is missing the `class_names.json` its card mentions. We took the class order from a community Space, then confirmed it against a labelled PlantVillage dataset that uses the same order.
- That community Space loads the model with the wrong final layer and `strict=False`, which silently skips the trained weights. We match the training architecture (`Dropout → Linear`) and load with `strict=True`.

**Files created / changed:**
- `backend/ml/classifier.py`: download with resume and SHA-256 check, safe loading (`weights_only=True`), preprocessing (224×224 + ImageNet normalisation), top-3, "Possible …" / "Likely healthy …" wording in EN/HI, the uncertainty threshold (0.50) and the retake message. The model loads once and is thread-safe.
- `backend/pipeline.py`: photo → AnalysisResult. Predictions, uncertainty and crop mismatch are **real**. Weather, risk, cards and explanation are still placeholders, so `is_demo` stays `true` until Components 5–6.
- `backend/main.py`:
  - Loads the model at startup (the API still starts if the weights are missing).
  - Inference runs in a worker thread.
  - Unreadable images return 400. A missing model returns 503.
  - `/api/health` reports whether the model is loaded.
- `shared/content/labels.json`: the 38 classes in model order, with crop key, healthy flag, and EN/HI names.
- `frontend/src/lib/labels.js`: the crop list is now exactly the 14 crops the model knows.
- `scripts/download_model.py`, `scripts/try_model.py`, `scripts/fetch_eval_images.py`, `scripts/eval_model.py`.
- `tests/test_classifier.py` (real model, auto-skipped if not installed). The API tests use a fake classifier for uncertain, crop-mismatch, healthy, bad-image and missing-model cases.
- `requirements.txt`: `torch`, `torchvision`, `pillow`. On Linux, install the CPU build first (see the comment in the file).

**Verify:**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu   # Linux
pip install -r requirements.txt
python scripts/download_model.py          # about 9 MB, verified
python scripts/fetch_eval_images.py       # 76 labelled test images
python scripts/eval_model.py              # accuracy + mistakes + speed
pytest                                    # 31 passed
```

---

## ✅ Component 5 — Weather context + location lookup

**Goal:** real recent and forecast weather for the crop's location, and real coordinates for every farm.

**Service:** [Open-Meteo](https://open-meteo.com), free with **no API key**, for both geocoding and weather.

**Files created / changed:**
- `backend/services/geocoding.py`: turns a farmer-typed place ("Sonipat, Haryana") into coordinates.
  - Searches within India.
  - Uses the state or district as a hint ("Aurangabad, Bihar" vs Maharashtra).
  - Falls back from village to district, and ignores accents and case.
  - Caches successful lookups only.
  - An unknown place returns **422** with a helpful message. An outage returns **503**.
- `backend/services/weather.py`: one Open-Meteo call gives the **last 3 days** (total rain, average humidity and temperature) and the **next 3 days** (expected rain, highest chance of rain), plus an EN/HI summary that cites the source. Results are cached for 30 minutes per ~1 km cell.
  - **Honesty rule:** if Open-Meteo is unreachable, weather is `null` and the analysis still works. Numbers are never made up. (This replaces the earlier plan of a "mock" fallback, per the team's real-data decision.)
- `shared/contract.py`:
  - `Weather` gets `rain_next_3_days_mm` and `max_rain_chance_next_3_days_pct` (optional, so older analyses still load).
  - `CropProfileCreate` gets optional `latitude`/`longitude` from the phone's GPS. Both must be sent together, and when present the name lookup is skipped.
- `backend/main.py`:
  - Registering or editing a crop resolves coordinates: GPS first, then stored coordinates if the name is unchanged, then a lookup.
  - New `GET /api/crops/{id}/weather`.
  - Each analysis includes real weather.
- `backend/pipeline.py`: predictions + **real weather**. Risk, cards and explanation are still placeholders until Component 6.
- `backend/repository.py`: stores the coordinates it's given. The placeholder coordinates are removed.
- Frontend `src/api/client.js`: new `getWeather(cropId)` and `getCurrentPosition()` (browser GPS). The Profile and Analysis TODOs are updated (a "Use my location" button, a weather card, and "Weather unavailable" handling).
- `tests/test_weather.py` and new API tests. Open-Meteo is faked for every test (recorded real responses, with simulated outages).

**Verify:**
```bash
pytest                                   # 58 passed, no network needed
uvicorn backend.main:app --reload
# In /docs: POST /api/crops with location_name "Karnal, Haryana" gives real coordinates.
# GET /api/crops/{id}/weather gives a real Open-Meteo summary in EN + HI.
```

---

## ✅ Component 6 — Risk, action-card and explanation engines (F3, F2, F4)

**Goal:** turn predictions, weather and crop stage into a risk estimate, ranked action cards and a "Why?" text, all traceable to rules. After this, **every analysis is real** and the DEMO EXAMPLE tag only appears on the seeded sample.

**Plain-language rules for judges and experts:** `docs/DECISION_RULES.md`.

**Files created / changed:**
- `shared/content/labels.json`: each class gets a `type` (fungal, bacterial, viral, insect_spread, pest, healthy), which decides which weather matters.
- `shared/content/risk_rules.json`: thresholds, points, score-to-level mapping (0–2 low, 3–4 moderate, 5+ elevated), and every reason sentence in EN/HI.
- `shared/content/action_cards.json`: 11 safe card templates with weights (top 3 shown) and the explanation templates.
- `shared/content/crops.json`: crop and stage names in EN/HI for the templates.
- `backend/engines/`:
  - `facts.py`: one object answering simple questions (disease found? wet recently? rain expected? hot and dry? sensitive stage?).
  - `risk.py`: the scoring rules.
  - `actions.py`: card conditions.
  - `explain.py`: the summary and verify line.
  - `content.py`: JSON loading and `{placeholder}` filling.
- `backend/pipeline.py`: model → weather → risk → cards → explanation, with `is_demo=False`.
- `backend/ml/classifier.py`: `ClassInfo.disease_type`.
- `backend/services/weather.py`: a "light rain possible" wording when the chance of rain is notable but almost no rain is forecast.
- `tests/test_engines.py`: 12 realistic scenarios plus a sweep of every class × 4 weather situations × clear or unclear photo (all text filled in both languages, valid priorities). It also includes a **banned-words test** (no pesticide or dose terms, EN and HI) and a **Hindi grammar guard** (no disease name directly before a postposition).

**Found and fixed during live testing:** Hindi postposition agreement ("अंगूर का काला सड़न **से**" became "इस समस्या से …: अंगूर का काला सड़न"), and the explanation reason order.

**Verify:**
```bash
pytest                                   # 379 passed
uvicorn backend.main:app --reload        # upload a leaf photo in /docs → real risk, cards, Why
```

---

## ✅ Component 7 — Finance & loans (F5, mock data)

**Goal:** loan status, dues, a document checklist farmers can tick off, and relevant schemes. All of it is clearly labelled sample data.

**Files:**
- `shared/content/loan_documents.json`: general document checklist per loan type, with a note that requirements vary by bank.
- `shared/content/schemes.json`: MISS interest subvention, PMFBY crop insurance and PM-KISAN. Neutral summaries only (no amounts or rates that can go out of date), each with a "verify" note and official link.
- `backend/repository.py`: `set_document_submitted()`, and schemes now come from the content files.
- `PUT /api/crops/{id}/loan/documents/{code}` (body `{"submitted": true}`): ticks or unticks a document and returns the updated summary. Unknown documents and farmers with no loan return 404.
- Frontend `setDocumentSubmitted()`. The checkbox updates instantly and rolls back if saving fails.

## ✅ Component 8 — Regional languages (F6)

**Goal:** the whole interface works in English and Hindi.

**Files:**
- `shared/i18n/en.json` and `hi.json`: all 105 UI labels in one reviewable place. `frontend/src/i18n/uiText.js` builds the label table from them.
- Backend text (predictions, risk reasons, cards, explanations, weather summaries, schemes, chat) was already bilingual from Components 4–7.
- `tests/test_i18n.py`:
  - both files have the same keys and matching `{placeholders}`;
  - every Hindi label actually contains Hindi script;
  - every `t('key')` the React app uses exists.
- **Decision:** English + Hindi only for the MVP. A regional language is added by creating one more JSON file plus one entry in `LANGUAGES`, once a native speaker has checked it.

## ✅ Component 9 — Multilingual chatbot + voice assistant (F7)

**Goal:** a chatbot grounded in the farmer's own data that the farmer can also talk to.

**Provider (chosen by the team):** **Groq**, with one API key for both the LLM and speech-to-text. The key lives in the git-ignored `.env` (template: `.env.example`).
- **Chat model:** `openai/gpt-oss-120b`, falling back to `qwen/qwen3.8-27b`. We picked it after a head-to-head test of all three Groq chat models on a grounded Hindi loan question and a pesticide-dose question that must be refused. gpt-oss-120b gave the most precise answers. gpt-oss-20b hinted at a loan outcome. Qwen is the fastest, so it's the backup.
- **Speech-to-text:** `whisper-large-v3`.
- **Text-to-speech:** the browser's built-in voices. Groq has no Hindi TTS, so this needs no key.

**Files:**
- `backend/config.py`: loads `.env`.
- `backend/services/llm.py`: Groq chat (with model fallback) and Whisper. Whisper's "no speech" scores and a repeated-word check drop transcripts it invents from noise. In testing, a plain beep had become "प्रस्तुति प्रस्तुति प्रस्तुति".
- `backend/services/chat.py`: system rules and a **context package** (profile, latest analysis with risk reasons and cards, weather, mock loan with missing documents and schemes), plus the last 8 turns of history. **Two safety layers:** the model is told to refuse products, doses and loan promises, and a regex replaces any dose-like reply. If Groq is down, the saved answers come back with `is_fallback=true`.
- `shared/contract.py`: `ChatTurn` (history), `ChatRequest.history`, `VoiceTranscript`.
- `POST /api/chat` (real LLM) and `POST /api/voice/transcribe` (audio upload, webm/ogg/wav/mp3/m4a). Silence returns 422 and an outage returns 503, each with a friendly message.
- Frontend `lib/speech.js`: `useRecorder()` for the mic (picks a format each browser supports) and `useSpeaker()` for read-aloud. It detects whether the device has a Hindi voice.

**Live-tested with the real key:**
- Missing documents in Hindi: correct.
- Follow-up question about the next instalment: answered ₹12,000 due 15 Dec, using the earlier conversation.
- Fungicide dose: refused.
- "Will my loan be approved?": "can't guarantee… sample data".
- Spoken Hindi question: transcribed and answered.

## ✅ Component 10 — Screens, integration and demo prep

**Goal:** a complete, working app that anyone on the team can start and demo.

**Files:**
- **All four screens fully built:**
  - `ProfileScreen.jsx`: profile card, live weather card, edit or register form with "use my location".
  - `AnalysisScreen.jsx`: photo upload or camera, possibilities, risk with reasons and points, 3 action cards with "Why?", explanation, check history.
  - `FinanceScreen.jsx`: MOCK banner, loan metrics, tickable checklist with progress, schemes with official links.
  - `ChatScreen.jsx`: chat with history, suggested questions, 🎤 voice input, 🔊 spoken answers with mute, fallback labels.
- Each screen keeps a short **POLISH TASKS** list for its teammate in its header comment.
- `components/ui.jsx`: Button, Field, ProgressBar, RiskBadge, Notice and more.
- `scripts/run_demo.sh`: one command starts the backend and frontend, checks setup and ports, and stops both on Ctrl+C.
- `frontend/vite.config.js`: the proxy target can be set with `DHARRAKSHAK_API_PROXY`.
- `README.md` (full setup and run guide) and `docs/DEMO_SCRIPT.md` (4-minute demo with fallbacks).

**Verified:**
- `pytest`: 500+ tests.
- A browser end-to-end test (Playwright and Chrome, real backend, model, weather and Groq) covered: profile and weather load; upload gives a real result (tomato late blight, 73%, ELEVATED); ticking a document moves 3/5 to 4/5; the English and Hindi chat answer correctly; Hindi UI; phone layout; no console errors.
- The microphone was tested with Chrome's fake microphone: the recording uploads, and noise is rejected kindly in the farmer's language.

## Teammate tasks (polish, testing, demo)

All screens work. Each teammate owns their screen's finishing touches, testing and demo part. The full list is in each file's header comment.

| Teammate | Screen file | Owns |
|---|---|---|
| 1 | `frontend/src/screens/ProfileScreen.jsx` | Phone layout check, Hindi wording review, auto-hiding "Saved", registering a crop live in the demo |
| 2 | `frontend/src/screens/AnalysisScreen.jsx` | Choosing and testing demo photos, clickable history, bar animation, Hindi review |
| 3 | `frontend/src/screens/FinanceScreen.jsx` | Checking scheme text against official sites, repayment countdown, Hindi review, ticking a document live |
| 4 | `frontend/src/screens/ChatScreen.jsx` + app polish | Mic and voice testing on laptop and phone, copy-answer button, consistent styling, Hindi review |

---

## ✅ Upgrade 1 — Real-world accuracy, redesign, 6 languages, voice

**Why:** on real phone photos the original model often answered with the wrong crop (for example "apple black rot" on a tomato). Measured on 89 real field photos (PlantDoc), it scored **12% top-1**.

**Accuracy** (full details and tables in `docs/MODEL_CARD.md`):
- Evaluated 4 models × 8 preprocessing settings × 2 ranking methods on lab and field photos (`scripts/eval_pipeline.py`).
- New default model: **linkanjarad MobileNetV2**. The model can be switched in `.env` (`DHARRAKSHAK_MODEL`).
- **Crop-aware ranking** (only the registered crop's classes), plus flip-averaging.
- **Result on field photos: 12% → 60% top-1, 81% → 85% top-3, F1 0.43 → 0.60.**
- `backend/ml/preprocess.py` (OpenCV): EXIF rotation and quality checks (blur, dark, blank, tiny) are on. Leaf segmentation (keeps lesions, falls back safely), background removal, CLAHE, white balance and denoising are implemented but **off**, because they didn't help real-world accuracy.
- Uncertainty calibrated on field photos:
  - a top-2 gap under 0.3 is flagged (43% accurate vs 55% for unflagged results);
  - the "may not be your crop" warning was tuned to about 4.5% false alarms;
  - crops the model knows only one class for are flagged as limited support.
- New files: `backend/ml/models.py` (backends + strict label mapping), `backend/ml/classifier_labels.py`, `scripts/fetch_field_images.py`, `scripts/eval_pipeline.py`. Tests guard accuracy at ≥90% on lab and ≥55% on field photos.

**UI redesign:**
- New **Dashboard** home screen.
- Compact cards and type scale, Lucide icons, a 6-language dropdown, and a bottom tab bar on phones.
- Leaf check uses two columns (upload panel stays in view on desktop).
- Dates are shown in local time, which fixes a UTC off-by-one-day bug.

**Languages: English, Hindi, Marathi, Punjabi, Haryanvi, Bhojpuri:**
- All farmer-facing text that was in Python moved to `shared/content/messages.json`.
- `scripts/translate_content.py` (Groq) translates every UI label and content text, validates placeholders and script, and saves after every batch. It stays within Groq's 8,000 tokens/minute free tier.
- Fallback chain: regional language → Hindi → English (`LANGUAGE_FALLBACK` in `shared/contract.py`, mirrored in `frontend/src/i18n/languages.js`).
- The chatbot answers in all six languages.
- `tests/test_i18n.py` checks every language has every label and content text, with matching placeholders, in the right script.
- **These are machine translations. A native speaker should review them, especially Haryanvi and Bhojpuri.**

**Voice:**
- Push-to-talk in all six languages. Whisper handles en/hi/mr/pa directly; Haryanvi and Bhojpuri are transcribed as Hindi, the closest available.
- Replies are read aloud with the device's voice for the language, and the app says so when none is installed.
- **LiveKit real-time voice was not built:** it needs a LiveKit server or cloud plus a separate agent process, too fragile for a hackathon. Push-to-talk is the working fallback the brief allows.
- **BHASHINI TTS** is the recommended next step for natural Marathi, Punjabi and Bhojpuri voices. It needs a free BHASHINI API key.
