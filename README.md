# DharRakshak — Team Dynaminds (HackShift)

*From crop symptoms to smarter farming decisions.*

DharRakshak is an AI crop assistant. It turns a leaf photo, the farmer's crop profile and local context into prioritized, explainable next steps in the farmer's own language. It also offers loan and document guidance (mock data) and a multilingual chatbot.

> **Status:** hackathon MVP, under construction. See [ROADMAP.md](ROADMAP.md) for progress and the order components are built in.

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLite
- **AI:** pretrained plant-disease image classifier (PlantVillage-trained), rules-based risk and action engines, an LLM API for the chatbot
- **Frontend:** Streamlit
- **Data:** Open-Meteo weather (with mock fallback). Loan data is **mock only**, with no bank integration.

## Quick start (so far)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/check_sample_data.py

# Run the app (mock mode, no backend needed)
streamlit run frontend/app.py
```

The app opens at http://localhost:8501.

## For teammates

Read [docs/CONTRACT.md](docs/CONTRACT.md) first. It explains the data your screen receives and which part of `shared/sample_data.json` is yours.

## Honesty rules

- Model outputs are *possible* conditions, never confirmed diagnoses.
- Risk is always an *estimate*.
- Loan data is mock. There is no live bank integration.
- No pesticide names or doses anywhere in the app.

this is the second component draft for our prototype 