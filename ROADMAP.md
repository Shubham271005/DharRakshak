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

## 🔜 Component 6 — Risk, action-card and explanation engines (F3, F2, F4)

**Goal:** turn predictions, weather and crop stage into a risk estimate, ranked action cards and a "Why?" text, all traceable to rules.

**Files:**
- `shared/content/risk_rules.json`: each rule has a condition, points and a reason text (EN/HI).
- `shared/content/action_cards.json`: card templates (EN/HI) and when each applies. No pesticide names or doses.
- `backend/engines/risk.py`, `actions.py`, `explain.py`: small, commented functions.
- `backend/main.py`: `/analyze` now runs model → weather → risk → actions → explanation and saves the result.
- `scripts/test_engines.py`: a few fixed scenarios with expected levels.

**Verify:** the demo photo with mock wet weather gives *elevated*. A healthy leaf in dry weather gives *low*. Every card has a "why".

---

## ⬜ Component 7 — Finance & loans (F5, mock data)

**Goal:** loan status, dues, missing documents and schemes from local mock data.

**Files:** `shared/content/loan_documents.json` (required documents per loan type), `shared/content/schemes.json` (short scheme notes with a "verify" line), `backend/services/loans.py` (missing = required − submitted), and the `/crops/{id}/loan` route reading from the database.

**Verify:** mark a document as submitted, and the missing list and progress update. The response always has `data_source="mock"`.

---

## ⬜ Component 8 — Regional languages (F6)

**Goal:** the whole interface switches between English and Hindi.

**Files:** `shared/i18n/en.json` and `hi.json` (every UI label, keyed by id), the `t()` helper in `frontend/src/i18n/LanguageContext.jsx` reading them, and a language-coverage check script.

**Verify:** switching to हिंदी changes all labels, cards, alerts and finance text. The coverage script reports no missing keys. Add a regional language only if its file is complete.

---

## ⬜ Component 9 — Multilingual chatbot + voice assistant (F7)

**Goal:** a chatbot that answers in the farmer's language, grounded in their saved data, that the farmer can also **speak to and hear answers from**.

**Before starting, ask the team:** which LLM provider and which speech provider to use, and for their API keys. Options for Hindi and Indian languages include Sarvam AI, Google Cloud Speech/TTS, Azure Speech, ElevenLabs, OpenAI Whisper, and Bhashini. The browser's built-in Web Speech API is a free fallback, but its Hindi support varies by browser.

**Files:**
- `backend/services/chat.py`: builds the guardrail system prompt (no pesticide names or doses, no loan-approval promises, say "I don't know", reply in the chosen language) and a context package (profile, latest analysis, action cards, loan summary). It calls the LLM and returns a `ChatReply`. If the API is unavailable, it falls back to the saved answers with `is_fallback=true`.
- `backend/services/voice.py`: speech-to-text (farmer's voice note to text in Hindi or English) and text-to-speech (reply text to audio in the same language).
- `backend/main.py`: `POST /api/chat` uses the real LLM. New `POST /api/voice/chat` takes an audio clip, transcribes it, gets the grounded reply, and returns text plus audio.
- `shared/contract.py`: voice request/response models (transcript, reply, audio).
- Frontend: a mic button in the chat (record, then send), a "listening…" state, and auto-play of the spoken reply with a mute toggle. Owned by Teammate 4 together with the chat screen.
- `.env.example`: placeholder names for the chosen keys (the real `.env` is git-ignored).
- `requirements.txt`: the provider SDKs and `python-dotenv`.

**Verify:**
- Typed or spoken in Hindi, "लोन के लिए कौन से कागज़ बाकी हैं?" gets the correct missing documents, spoken back in Hindi.
- A pesticide-dose question gets a polite refusal.
- With the keys removed, chat returns the fallback with `is_fallback=true`, and the mic button says voice is unavailable.

---

## ⬜ Component 10 — Integration, testing and demo prep

**Goal:** everything works end to end, reliably, on the demo laptop.

**Tasks:** switch the frontend to real-server mode, test the full demo script (from the pitch notes), write `scripts/run_demo.sh` (starts backend and frontend), cache the demo responses for offline backup, record a backup screen video, and update the README with run instructions.

**Verify:** a teammate who didn't write the code can run the whole demo from the README in under 5 minutes.

---

## Teammate frontend tasks (start after Component 1)

| Teammate | Screen file | Builds | Data |
|---|---|---|---|
| 1 | `frontend/src/screens/ProfileScreen.jsx` | Crop registration form + profile card | `crop_profile` |
| 2 | `frontend/src/screens/AnalysisScreen.jsx` | Prediction bars, risk badge, action cards, "Why?" box | `analysis` |
| 3 | `frontend/src/screens/FinanceScreen.jsx` | Loan card, documents checklist (missing in red), schemes, MOCK tag | `loan_summary` |
| 4 | `frontend/src/screens/ChatScreen.jsx` + app polish | Chat bubbles, input box, mic button and voice playback (after C9), language selector, consistent styling | `chat_examples` |

Everyone builds against mock mode first. In Component 10 we flip the switch to the real backend.

