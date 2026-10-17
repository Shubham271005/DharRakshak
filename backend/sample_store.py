"""
Temporary in-memory data store (Component 2).

For now the backend keeps everything in Python dictionaries, seeded from
`shared/sample_data.json`. Data is lost when the server restarts.

This file is replaced step by step in later components:
- Component 3 (database): crops, analyses and loans move into SQLite.
- Component 4–6 (model + engines): `mock_analysis` is replaced by the real
  image model, risk engine, action cards and explanations.
- Component 7 (finance): `get_loan` reads real mock records per farmer.
- Component 9 (chatbot): `mock_chat_reply` is replaced by the grounded LLM.

The rest of the backend only talks to the functions below, so swapping the
storage later doesn't change `main.py`'s routes.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

from shared.contract import (
    AnalysisResult,
    ChatReply,
    ChatRequest,
    CropProfile,
    CropProfileCreate,
    LoanSummary,
    Location,
    SampleData,
)

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "shared" / "sample_data.json"


@lru_cache(maxsize=1)
def sample() -> SampleData:
    """Load and validate the sample file once (fails loudly if it's broken)."""
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return SampleData.model_validate(raw)


class InMemoryStore:
    """Holds crops, analyses and loans for the running server."""

    def __init__(self) -> None:
        demo = sample()
        self.crops: dict[str, CropProfile] = {demo.crop_profile.crop_id: demo.crop_profile}
        # Analyses per crop, oldest first. History returns them newest first.
        self.analyses: dict[str, list[AnalysisResult]] = {demo.crop_profile.crop_id: [demo.analysis]}
        self.loans: dict[str, LoanSummary] = {demo.crop_profile.crop_id: demo.loan_summary}

    # ----- F2: crop profiles ------------------------------------------------

    def create_crop(self, new: CropProfileCreate) -> CropProfile:
        """Turn the farmer's form input into a full profile and store it."""
        demo_location = sample().crop_profile.location
        profile = CropProfile(
            crop_id=f"crop-{uuid.uuid4().hex[:8]}",
            farmer_name=new.farmer_name,
            preferred_language=new.preferred_language,
            crop_type=new.crop_type,
            variety=new.variety or None,
            sowing_date=new.sowing_date,
            days_since_sowing=(date.today() - new.sowing_date).days,
            area_acres=new.area_acres,
            # Placeholder coordinates — real geocoding of `location_name`
            # arrives in Component 5 (Open-Meteo geocoding API).
            location=Location(
                name=new.location_name,
                latitude=demo_location.latitude,
                longitude=demo_location.longitude,
            ),
            stage=new.stage,
        )
        self.crops[profile.crop_id] = profile
        self.analyses[profile.crop_id] = []
        return profile

    def get_crop(self, crop_id: str) -> CropProfile | None:
        return self.crops.get(crop_id)

    # ----- F1 + F3 + F2 + F4: analyses --------------------------------------

    def mock_analysis(self, crop_id: str) -> AnalysisResult:
        """Return the sample analysis re-labelled for this crop.

        The uploaded photo is NOT looked at yet — the image model arrives in
        Component 4. `is_demo` stays True so the UI shows "DEMO EXAMPLE".
        """
        result = sample().analysis.model_copy(
            update={
                "analysis_id": f"an-{uuid.uuid4().hex[:8]}",
                "crop_id": crop_id,
                "created_at": datetime.now(timezone.utc),
                "is_demo": True,
            }
        )
        self.analyses.setdefault(crop_id, []).append(result)
        return result

    def history(self, crop_id: str) -> list[AnalysisResult]:
        """All analyses for a crop, newest first."""
        return list(reversed(self.analyses.get(crop_id, [])))

    # ----- F5: loans (MOCK) -------------------------------------------------

    def get_loan(self, crop_id: str) -> LoanSummary:
        """Mock loan summary. New crops get a copy of the sample loan for now."""
        if crop_id not in self.loans:
            self.loans[crop_id] = sample().loan_summary.model_copy(update={"crop_id": crop_id})
        return self.loans[crop_id]


# ----- F7: chatbot stub -----------------------------------------------------

# Keyword routing to the sample chat answers, so the frontend chat works now.
# (keywords, index into sample().chat_examples)
_CHAT_KEYWORDS: list[tuple[tuple[str, ...], int]] = [
    (("pesticide", "spray", "dose", "दवा", "कीटनाशक", "छिड़काव"), 2),
    (("कागज", "कागज़", "दस्तावेज", "document", "loan", "लोन"), 0),
    (("why", "क्यों", "inspect", "जाँच"), 1),
]

_UNKNOWN_REPLY = {
    "en": "(Demo mode) I'll be able to answer this once the chatbot is connected.",
    "hi": "(डेमो मोड) चैटबॉट जुड़ने के बाद मैं इसका जवाब दे पाऊँगा।",
}


def mock_chat_reply(request: ChatRequest) -> ChatReply:
    """Placeholder chatbot. Safety questions (pesticides) are checked first."""
    text = request.message.lower()
    for words, example_index in _CHAT_KEYWORDS:
        if any(word in text for word in words):
            return sample().chat_examples[example_index].reply
    return ChatReply(
        reply=_UNKNOWN_REPLY.get(request.lang, _UNKNOWN_REPLY["en"]),
        lang=request.lang,
        is_fallback=True,
    )


# One shared store for the whole running server.
store = InMemoryStore()
