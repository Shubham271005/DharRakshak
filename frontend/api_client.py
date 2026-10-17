"""
The ONLY place the frontend gets data from (Component 1).

Screens never read files or call the backend directly — they call these
functions and get back validated objects from shared/contract.py, e.g.:

    profile = api_client.get_crop_profile(crop_id)
    profile.crop_type            -> "tomato"
    card.title.in_lang("hi")     -> "आस-पास के पौधे जाँचें"

Two modes, chosen with the DHARRAKSHAK_MODE environment variable:
- "mock" (default): reads shared/sample_data.json. Works with no backend,
  so teammates can build screens right away.
- "api": calls the FastAPI backend at DHARRAKSHAK_API_URL
  (default http://localhost:8000). Endpoints arrive in Component 2.

Switching modes never changes the screens, because both modes return the
same contract objects.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

import requests

# Make `import shared...` work when Streamlit runs frontend/app.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.contract import (  # noqa: E402
    AnalysisResult,
    ChatReply,
    ChatRequest,
    CropProfile,
    CropProfileCreate,
    LoanSummary,
    Location,
    SampleData,
)

MODE = os.getenv("DHARRAKSHAK_MODE", "mock").lower()
API_BASE_URL = os.getenv("DHARRAKSHAK_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_SECONDS = 30  # image analysis can be slow on a CPU

SAMPLE_PATH = REPO_ROOT / "shared" / "sample_data.json"

# In mock mode, a profile saved through the form is kept here so the profile
# card can show it. This is shared by everyone using the running app, which
# is fine for a single-laptop demo. Real storage arrives in Component 3.
_mock_saved_profile: CropProfile | None = None


class ApiError(Exception):
    """Raised when the backend can't be reached or returns an error.

    Screens should catch this and show a friendly message with st.error().
    """


def is_mock_mode() -> bool:
    return MODE != "api"


@lru_cache(maxsize=1)
def _sample() -> SampleData:
    """Load and validate the sample file once."""
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return SampleData.model_validate(raw)


def demo_crop_id() -> str:
    """The crop id used throughout the demo."""
    return _sample().crop_profile.crop_id


# ---------------------------------------------------------------------------
# Internal helpers for API mode
# ---------------------------------------------------------------------------

def _get(path: str) -> dict:
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as err:
        raise ApiError(f"Could not load {path}: {err}") from err


def _post(path: str, **kwargs) -> dict:
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", timeout=TIMEOUT_SECONDS, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as err:
        raise ApiError(f"Request to {path} failed: {err}") from err


# ---------------------------------------------------------------------------
# F2 — crop profile (Teammate 1)
# ---------------------------------------------------------------------------

def get_crop_profile(crop_id: str) -> CropProfile:
    if is_mock_mode():
        return _mock_saved_profile or _sample().crop_profile
    return CropProfile.model_validate(_get(f"/crops/{crop_id}"))


def save_crop_profile(new_profile: CropProfileCreate) -> CropProfile:
    """Save what the farmer typed in the form and return the full profile."""
    global _mock_saved_profile
    if is_mock_mode():
        sample = _sample().crop_profile
        _mock_saved_profile = CropProfile(
            crop_id=sample.crop_id,  # mock mode keeps a single demo crop
            farmer_name=new_profile.farmer_name,
            preferred_language=new_profile.preferred_language,
            crop_type=new_profile.crop_type,
            variety=new_profile.variety or None,
            sowing_date=new_profile.sowing_date,
            days_since_sowing=(date.today() - new_profile.sowing_date).days,
            area_acres=new_profile.area_acres,
            # Real coordinates come from geocoding in Component 5.
            location=Location(
                name=new_profile.location_name,
                latitude=sample.location.latitude,
                longitude=sample.location.longitude,
            ),
            stage=new_profile.stage,
        )
        return _mock_saved_profile
    data = _post("/crops", json=new_profile.model_dump(mode="json"))
    return CropProfile.model_validate(data)


# ---------------------------------------------------------------------------
# F1 + F3 + F2 + F4 — leaf analysis (Teammate 2)
# ---------------------------------------------------------------------------

def analyze_image(crop_id: str, image_bytes: bytes, filename: str) -> AnalysisResult:
    """Send a leaf photo and get predictions, risk, action cards and explanation.

    In mock mode the photo is ignored and the sample analysis is returned
    (it has is_demo=True so the screen can show the DEMO EXAMPLE tag).
    """
    if is_mock_mode():
        return _sample().analysis
    files = {"image": (filename, image_bytes)}
    return AnalysisResult.model_validate(_post(f"/crops/{crop_id}/analyze", files=files))


def get_latest_analysis(crop_id: str) -> AnalysisResult | None:
    """Most recent analysis for the crop, or None if there isn't one yet."""
    if is_mock_mode():
        return _sample().analysis
    history = _get(f"/crops/{crop_id}/history")
    return AnalysisResult.model_validate(history[0]) if history else None


# ---------------------------------------------------------------------------
# F5 — finance & loans (Teammate 3)
# ---------------------------------------------------------------------------

def get_loan_summary(crop_id: str) -> LoanSummary:
    if is_mock_mode():
        return _sample().loan_summary
    return LoanSummary.model_validate(_get(f"/crops/{crop_id}/loan"))


# ---------------------------------------------------------------------------
# F7 — chatbot (Teammate 4)
# ---------------------------------------------------------------------------

# Simple keyword routing so mock mode feels alive during frontend work.
# The real, grounded chatbot arrives in Component 9.
_MOCK_KEYWORDS = [
    (("कागज", "कागज़", "दस्तावेज", "document", "loan", "लोन"), 0),
    (("why", "क्यों", "inspect", "जाँच"), 1),
    (("pesticide", "spray", "dose", "दवा", "कीटनाशक", "छिड़काव"), 2),
]

_MOCK_UNKNOWN = {
    "en": "(Demo mode) I'll be able to answer this once the chatbot is connected.",
    "hi": "(डेमो मोड) चैटबॉट जुड़ने के बाद मैं इसका जवाब दे पाऊँगा।",
}


def send_chat(crop_id: str, message: str, lang: str) -> ChatReply:
    request = ChatRequest(crop_id=crop_id, message=message, lang=lang)
    if is_mock_mode():
        examples = _sample().chat_examples
        lowered = message.lower()
        for words, example_index in _MOCK_KEYWORDS:
            if any(w in lowered for w in words):
                return examples[example_index].reply
        return ChatReply(reply=_MOCK_UNKNOWN.get(lang, _MOCK_UNKNOWN["en"]), lang=lang, is_fallback=True)
    return ChatReply.model_validate(_post("/chat", json=request.model_dump()))
