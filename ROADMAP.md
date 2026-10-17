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
├── frontend/
│   ├── app.py                  ← Streamlit entry point + navigation  (C1)
│   ├── api_client.py           ← talks to backend OR reads mock data (C1)
│   ├── theme.py                ← shared colours / helpers            (C1)
│   └── screens/                ← one file per teammate               (C1 stubs → teammates)
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

## ✅ Component 1 — Frontend shell + teammate screen stubs

**Goal:** unblock the 4 teammates as early as possible. They need a running app with an empty screen each.

**Files to create:**
- `frontend/app.py`: Streamlit entry point. Page config, sidebar navigation between the 4 screens, and the language selector state.
- `frontend/api_client.py`: one function per backend call (`get_crop_profile`, `analyze_image`, `get_loan_summary`, `send_chat`). Has a **mock mode** that reads `shared/sample_data.json`, so screens work with no backend.
- `frontend/theme.py`: colour constants plus small helpers (format rupees, pick language text, render a "MOCK DATA" tag).
- `frontend/screens/profile.py` (Teammate 1), `analysis.py` (Teammate 2), `finance.py` (Teammate 3), `chat.py` (Teammate 4). Each is a **stub** with TODO comments describing exactly what to build.
- `.streamlit/config.toml`: green theme.
- `requirements.txt`: add `streamlit`, `requests`.

**Also added:** `CropProfileCreate` in `shared/contract.py`, the model for what the farmer types into the registration form (it rejects future sowing dates).

**Verify:** `streamlit run frontend/app.py` opens, you can switch between 4 placeholder screens, and the language selector works.
Mock mode is the default. `DHARRAKSHAK_MODE=api` switches to the backend once Component 2 exists.

**Hand-off:** each teammate gets their stub file and `docs/CONTRACT.md`.

---

## 🔜 Component 2 — Backend skeleton (FastAPI)

**Goal:** a running API that returns the sample data from every endpoint, so the frontend can switch from mock mode to "real server" mode early.

**Files to create:**
- `backend/__init__.py`, `backend/main.py`: FastAPI app, CORS, `/health`, and stub routes that return validated sample data:
  - `POST /crops` and `GET /crops/{crop_id}` (F2)
  - `POST /crops/{crop_id}/analyze` (photo upload; F1, F3, F2, F4)
  - `GET /crops/{crop_id}/history`
  - `GET /crops/{crop_id}/loan` (F5)
  - `POST /chat` (F7)
- `requirements.txt`: add `fastapi`, `uvicorn[standard]`, `python-multipart`.

**Verify:** `uvicorn backend.main:app --reload`, open `http://localhost:8000/docs`, and every endpoint returns the sample payload. Then set the frontend to real-server mode and the screens look identical.

---

## ⬜ Component 3 — Database (SQLite) + real crop profiles

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

**Files:** `shared/i18n/en.json` and `hi.json` (every UI label, keyed by id), a `t(key, lang)` helper in `frontend/theme.py`, and a language-coverage check script.

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
| 1 | `frontend/screens/profile.py` | Crop registration form + profile card | `crop_profile` |
| 2 | `frontend/screens/analysis.py` | Prediction bars, risk badge, action cards, "Why?" box | `analysis` |
| 3 | `frontend/screens/finance.py` | Loan card, documents checklist (missing in red), schemes, MOCK tag | `loan_summary` |
| 4 | `frontend/screens/chat.py` + theme polish | Chat bubbles, input box, language selector, consistent styling | `chat_examples` |

Everyone builds against mock mode first. In Component 10 we flip the switch to the real backend.

