# DharRakshak — Team Dynaminds (HackShift)

*From crop symptoms to smarter farming decisions.*

**🌐 Live demo: https://dharrakshak.vercel.app**  ·  API: https://dharrakshak-api.onrender.com/docs

> The free backend sleeps after 15 minutes idle — the first load can take 30–60 seconds.

DharRakshak is an AI crop assistant for Indian farmers. A farmer photographs a leaf. The app identifies **possible** problems with an image model tuned for real field photos, combines that with **real local weather** and the crop's growth stage, and gives a **risk estimate**, **ranked next steps** and a plain-language **"Why?"**. It works in **English, Hindi, Marathi, Punjabi, Haryanvi and Bhojpuri**. It also tracks **loan documents** (sample data) and has a **multilingual chatbot you can talk to**.

## Features

| | Feature | How |
|---|---|---|
| F1 | Leaf symptom analysis | MobileNetV2 chosen by evaluation on **real field photos** (60% top-1 / 85% top-3, against 12% before), crop-aware ranking, quality checks, honest uncertainty. See the [model card](docs/MODEL_CARD.md). |
| F2 | Crop profile + action cards | Saved profile, 3 ranked safe next steps |
| F3 | Context-aware risk | Rules combining the photo, Open-Meteo weather and crop stage → low / moderate / elevated (estimate) |
| F4 | Explainability | Every point in the risk score has a reason sentence, plus a "verify" line |
| F5 | Finance & loans | Loan status, repayments, document checklist you can tick, schemes. **Mock data, no bank integration** |
| F6 | Languages | English, हिंदी, मराठी, ਪੰਜਾਬੀ, हरियाणवी, भोजपुरी everywhere: UI, predictions, risk, cards, explanations, finance, chat. Fixed text is translated into reviewable JSON, and the chatbot answers live in the chosen language. |
| F7 | Chatbot + voice | Groq LLM grounded in the farmer's data. Push-to-talk: Groq Whisper speech-to-text (en/hi/mr/pa; Haryanvi and Bhojpuri via Hindi), answers read aloud with the device's voice for that language |

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLite, PyTorch (CPU)
- **Frontend:** React 19, Vite, Tailwind CSS v4
- **AI:** MobileNetV2 plant-disease classifier via Hugging Face `transformers` + OpenCV preprocessing ([model card](docs/MODEL_CARD.md)), transparent decision rules ([rules](docs/DECISION_RULES.md)), Groq `openai/gpt-oss-120b` (fallback `qwen/qwen3.8-27b`) for chat and translation, `whisper-large-v3` for speech-to-text
- **Data:** Open-Meteo weather and geocoding (free, no key). Loan data is sample data only.

---

## First-time setup (once per laptop)

You need **Python 3.11+**, **Node.js 20+** and internet for the first setup.

```bash
git clone <repo-url> && cd Dynaminds-IIITD

# 1. Python environment
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
# Linux only: small CPU-only PyTorch first (avoids a ~2 GB GPU download)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 2. Image model weights (~9 MB, checksum-verified)
python scripts/download_model.py

# 3. API key for the chatbot + voice
cp .env.example .env                      # then open .env and paste your Groq key
#   GROQ_API_KEY=gsk_...                  (get one at https://console.groq.com/keys)

# 4. Frontend packages
cd frontend && npm install && cd ..
```

## Run the app

**macOS / Linux, one command:**
```bash
./scripts/run_demo.sh
```
Then open **http://localhost:5173**. Press **Ctrl+C** to stop.

**Windows, or if you prefer two terminals:**
```bash
# Terminal 1: backend (API docs at http://localhost:8000/docs)
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
uvicorn backend.main:app --port 8000

# Terminal 2: frontend
cd frontend
echo VITE_API_MODE=api > .env             # use the real backend (delete .env for sample-data mode)
npm run dev                               # opens http://localhost:5173
```

The sidebar shows **Connected to server** when the frontend can reach the backend.

## Useful commands

| Command | What it does |
|---|---|
| `pytest` | Runs all backend tests (500+). No network or API key needed. |
| `python scripts/reset_db.py` | Wipes the database back to the demo farmer. Do this before the demo. |
| `python scripts/try_model.py photo.jpg` | Tries the image model on photos |
| `python scripts/fetch_field_images.py` + `python scripts/eval_model.py` | Measures accuracy on real field photos (PlantDoc), exactly as the app runs |
| `python scripts/eval_pipeline.py` | Compares models × preprocessing settings |
| `python scripts/translate_content.py` | Fills in Marathi, Punjabi, Haryanvi and Bhojpuri for any new text (uses Groq) |
| `python scripts/fetch_eval_images.py` + `python scripts/eval_model.py` | Measures model accuracy on labelled test photos |
| `python scripts/check_sample_data.py` | Checks the sample data matches the data contract |

## Before the demo

1. Run `python scripts/reset_db.py`.
2. Test your demo leaf photos with `scripts/try_model.py`. Use clear photos of a single leaf.
3. Open the app in **Chrome**, allow the microphone, and ask one question by voice.
4. Read [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## Project layout

```
backend/        FastAPI app: routes (main.py), database, image model (ml/),
                decision engines (engines/), weather, geocoding, chat and voice (services/)
frontend/       React app: screens/, components/, api/client.js (all data access)
shared/         Data contract (contract.py), sample data, rule content (content/),
                UI translations (i18n/)
docs/           Contract, model card, decision rules, demo script
scripts/        Setup, run, evaluation and maintenance scripts
tests/          Backend tests
```

See [ROADMAP.md](ROADMAP.md) for how the project was built, component by component.

## Honesty rules

- Model outputs are *possible* conditions, never confirmed diagnoses.
- Risk is always an *estimate*.
- Weather is real (Open-Meteo), and shown as unavailable rather than made up.
- Loan data is **sample data**. There is no bank integration.
- No pesticide names or doses anywhere. The chatbot refuses, and a filter blocks dose-like replies.

## Team notes

this is the second component draft for our prototype

this is the fifth component draft for our prototype at hackShift IIITD

##5th commit
##6th commit
## Deploy (free): backend on Render, frontend on Vercel

**1. Backend on Render** (free plan; the model runs with ONNX Runtime and uses about 120 MB of RAM):
1. Open **https://render.com/deploy?repo=https://github.com/Shubham271005/Dynaminds-IIITD** and sign in with GitHub.
2. Render reads `render.yaml`. Paste your **GROQ_API_KEY** when asked, then click **Apply**.
3. Wait for the build (about 3–5 minutes). Your API is at `https://dharrakshak-api.onrender.com`; check `/api/health`.

The free plan sleeps after 15 minutes idle, so the first request then takes 30–60 seconds. Data resets on restart (the demo farmer is re-created).

**2. Frontend on Vercel:**
1. Go to **vercel.com → Add New → Project → Import** `Dynaminds-IIITD` → **Deploy**. `vercel.json` already sets the build.
2. If Render's address differs from the one above, set `VITE_API_BASE` in Vercel → Settings → Environment Variables, then redeploy.

Optional: `deploy/hf-space/` + `scripts/deploy_hf_space.py` deploy the full PyTorch backend to a Hugging Face Docker Space (requires HF PRO).
