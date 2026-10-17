# DharRakshak — Build Roadmap

This is the guided, step-by-step plan for building the prototype. We build **one component at a time**, check it works, and stop before starting the next. Each section lists the files that get created or changed, what the component does, and how to verify it.

**Legend:** ✅ done · 🔜 next · ⬜ not started

**Features:** F1 symptom analysis · F2 crop profile + action cards · F3 context risk · F4 explainability · F5 finance & loans · F6 regional languages · F7 multilingual chatbot

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
│   ├── db.py                   ← SQLite tables + helpers             (C3)
│   ├── ml/classifier.py        ← pretrained image model              (C4)
│   ├── services/weather.py     ← Open-Meteo + mock fallback          (C5)
│   ├── engines/                ← risk.py, actions.py, explain.py     (C6)
│   ├── services/loans.py       ← mock loans + document checker       (C7)
│   └── services/chat.py        ← grounded LLM chatbot                (C9)
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
└── data/samples/               ← sample leaf photos for the demo     (C4)
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

## 🔜 Component 3 — Database (SQLite) + real crop profiles

**Goal:** crop profiles and analyses are saved and loaded for real.

**Files:** `backend/db.py` (tables: farmers, crops, analyses, loans, documents; uses Python's built-in `sqlite3`). `backend/main.py`: the `/crops` routes read and write the database, and `days_since_sowing` is computed. `scripts/seed_demo.py` inserts the demo farmer, crop and mock loan.

**Verify:** create a crop in `/docs`, restart the server, and the crop is still there.

---

## ⬜ Component 4 — Pretrained image model (F1)

**Goal:** a real photo goes in, and the real top-3 ranked possibilities come out.

**Steps:**
1. Choose a PlantVillage-trained model on Hugging Face. Check its classes, license and input size, and record the choice in `docs/MODEL_CARD.md`.
2. `backend/ml/classifier.py`: load the model once at startup, then preprocess (resize, normalize with the training values), run the model, apply softmax, take the top 3, map labels to EN/HI names, and apply the uncertainty threshold and crop-mismatch check.
3. `shared/content/labels.json`: raw class names mapped to friendly EN/HI names.
4. Add sample leaf photos to `data/samples/`.
5. `requirements.txt`: add `torch`, `torchvision` or `transformers`, and `pillow`.

**Verify:** `python scripts/try_model.py data/samples/<photo>` prints sensible top 3. A blurry or non-leaf photo shows *uncertain*.

---

## ⬜ Component 5 — Weather context

**Goal:** real recent and forecast weather for the crop's location, with a clearly labelled fallback.

**Files:** `backend/services/weather.py` (Open-Meteo: past 3 days of rain plus humidity and temperature, with a timeout). If the call fails, it returns mock weather with `source="mock"`. `requirements.txt`: `requests` is already added.

**Verify:** call it for the demo coordinates. With Wi-Fi off, it returns mock weather labelled "mock".

---

## ⬜ Component 6 — Risk, action-card and explanation engines (F3, F2, F4)

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

## ⬜ Component 9 — Multilingual chatbot (F7)

**Goal:** a chatbot that answers in the farmer's language, grounded in their saved data.

**Files:**
- `backend/services/chat.py`: builds the guardrail system prompt and a context package (profile, latest analysis, action cards, loan summary), calls the LLM, and returns a `ChatReply`. Falls back to canned answers from `chat_examples` if the API is unavailable.
- `.env.example`: `ANTHROPIC_API_KEY=` (the real `.env` is git-ignored).
- `requirements.txt`: add `anthropic`, `python-dotenv`.

**Verify:** the Hindi loan-documents question gets the correct missing documents. A pesticide-dose question gets a polite refusal. With the key removed, it returns the fallback with `is_fallback=true`.

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
| 4 | `frontend/src/screens/ChatScreen.jsx` + app polish | Chat bubbles, input box, language selector, consistent styling | `chat_examples` |

Everyone builds against mock mode first. In Component 10 we flip the switch to the real backend.

