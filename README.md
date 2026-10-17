# DharRakshak — Team Dynaminds (HackShift)

*From crop symptoms to smarter farming decisions.*

DharRakshak is an AI crop assistant. It turns a leaf photo, the farmer's crop profile and local context into prioritized, explainable next steps in the farmer's own language. It also offers loan and document guidance (mock data) and a multilingual chatbot.

> **Status:** hackathon MVP, under construction. See [ROADMAP.md](ROADMAP.md) for progress and the order components are built in.
## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLite
- **AI:** pretrained MobileNetV2 plant-disease classifier ([model card](docs/MODEL_CARD.md)), rules-based risk and action engines, an LLM API for the chatbot
- **Frontend:** React 19 + Vite + Tailwind CSS v4
- **Data:** Open-Meteo weather (with mock fallback). Loan data is **mock only**, with no bank integration.

## Quick start (so far)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
# Linux only: get the small CPU build of PyTorch first (avoids a ~2 GB GPU download)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python scripts/download_model.py    # image model weights, ~9 MB (once per laptop)
python scripts/check_sample_data.py

# Backend (terminal 1) — API docs at http://localhost:8000/docs
uvicorn backend.main:app --reload --port 8000
pytest                              # run the backend tests
python scripts/reset_db.py          # wipe the database back to the demo data

# Frontend (terminal 2) — opens at http://localhost:5173
cd frontend
npm install                         # first time only (needs Node.js 20+)
npm run dev
```

The frontend starts in **mock mode** (sample data, no backend needed). To use the real backend, create `frontend/.env` containing `VITE_API_MODE=api` and restart `npm run dev`.

## For teammates

Read [docs/CONTRACT.md](docs/CONTRACT.md) first. It explains the data your screen receives and which part of `shared/sample_data.json` is yours.

## Honesty rules

- Model outputs are *possible* conditions, never confirmed diagnoses.
- Risk is always an *estimate*.
- Loan data is mock. There is no live bank integration.
- No pesticide names or doses anywhere in the app.


this is the second component draft for our prototype 

this is the fifth component draft for our prototype at hackShift IIITD

##5th commit 
##6th commit

