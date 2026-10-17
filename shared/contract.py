"""
DharRakshak — Data Contract (Component 0)
==========================================
###project begins
This file is the SINGLE SOURCE OF TRUTH for the shape of every piece of data
that moves between the backend and the frontend.

Why it matters
--------------
- The backend (FastAPI) uses these models as response types, so it can never
  return a malformed payload.
- The frontend (Streamlit) screens are built against `shared/sample_data.json`,
  which is validated against these same models. That lets the 4 frontend
  teammates build their screens before the real backend exists.
- If you need a new field, add it HERE first, update `sample_data.json`,
  run `python scripts/check_sample_data.py`, and only then touch backend or
  frontend code.

Conventions
-----------
- Any text shown to the farmer is a `LocalizedText` object holding every
  supported language (`{"en": "...", "hi": "..."}`). The frontend picks the
  language with `.in_lang(lang)`. Adding a regional language later means
  adding one more key (e.g. "mr" for Marathi) — no schema change needed.
- Money is always in whole Indian rupees (int), field names end in `_inr`.
- Probabilities/confidences are floats between 0.0 and 1.0.
- Risk is ALWAYS an estimate (`is_estimate` is fixed to True) — the product
  never claims a confirmed diagnosis.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Languages that MUST be present in every LocalizedText.
REQUIRED_LANGUAGES: tuple[str, ...] = ("en", "hi")

# All languages the app offers. Codes: ISO 639 (bgc = Haryanvi, bho = Bhojpuri).
# Text for mr/pa/bgc/bho is stored as extra keys on LocalizedText
# (shared/content/*.json, shared/i18n/*.json — see scripts/translate_content.py).
SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "hi", "mr", "pa", "bgc", "bho")
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "hi": "Hindi", "mr": "Marathi", "pa": "Punjabi", "bgc": "Haryanvi", "bho": "Bhojpuri",
}
# If a text is missing in a language, show the closest one the farmer can read.
LANGUAGE_FALLBACK: dict[str, str] = {"mr": "hi", "pa": "hi", "bgc": "hi", "bho": "hi", "hi": "en"}


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

class LocalizedText(BaseModel):
    """A piece of farmer-facing text in every supported language.

    `extra="allow"` lets us add optional regional languages (e.g. "mr", "ta")
    without changing this class.
    """

    model_config = ConfigDict(extra="allow")

    en: str
    hi: str

    def in_lang(self, lang: str) -> str:
        """Return the text in `lang`, following LANGUAGE_FALLBACK (e.g.
        Bhojpuri → Hindi → English) when a translation is missing."""
        seen = set()
        while lang and lang not in seen:
            seen.add(lang)
            if lang == "en":
                return self.en
            if lang == "hi":
                return self.hi
            text = (self.model_extra or {}).get(lang)
            if text:
                return text
            lang = LANGUAGE_FALLBACK.get(lang, "en")
        return self.en


class CropStage(str, Enum):
    """Growth stage of the crop. Drives stage-specific risk rules (Component 6)."""

    seedling = "seedling"
    vegetative = "vegetative"
    flowering = "flowering"
    fruiting = "fruiting"
    maturity = "maturity"


class RiskLevel(str, Enum):
    """Estimated inspection priority. Never presented as a certainty."""

    low = "low"
    moderate = "moderate"
    elevated = "elevated"


class WeatherSource(str, Enum):
    """Where weather data came from. The UI must label `mock` data clearly."""

    open_meteo = "open_meteo"
    mock = "mock"


class LoanStatus(str, Enum):
    applied = "applied"
    active = "active"
    overdue = "overdue"
    closed = "closed"


# ---------------------------------------------------------------------------
# F2 — Personal crop management: the farmer's crop profile
# ---------------------------------------------------------------------------

class Location(BaseModel):
    name: str = Field(..., description="Village / district name as typed by the farmer")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class YieldRange(BaseModel):
    """Estimated yield range. Always a range, never a single promised number."""

    min_kg: float = Field(..., ge=0)
    max_kg: float = Field(..., ge=0)


class CropProfile(BaseModel):
    crop_id: str
    farmer_name: str
    preferred_language: str = Field("en", description="Language code, e.g. 'en' or 'hi'")
    crop_type: str = Field(..., description="Lower-case crop key, e.g. 'tomato'")
    variety: Optional[str] = Field(None, description="None when the farmer doesn't know it")
    sowing_date: date
    days_since_sowing: int = Field(..., ge=0, description="Computed by the backend")
    area_acres: float = Field(..., gt=0)
    location: Location
    stage: CropStage
    expected_harvest_start: Optional[date] = None
    expected_harvest_end: Optional[date] = None
    yield_estimate: Optional[YieldRange] = Field(None, description="None = 'range pending'")


class CropProfileCreate(BaseModel):
    """What the farmer types into the registration form (Teammate 1's screen).

    The backend turns this into a full `CropProfile`: it assigns `crop_id`,
    computes `days_since_sowing`, and looks up latitude/longitude from
    `location_name` (Open-Meteo geocoding) unless coordinates are supplied.
    """

    farmer_name: str = Field(..., min_length=1, max_length=100)
    preferred_language: str = "en"
    crop_type: str = Field(..., description="Key from the supported-crops list, e.g. 'tomato'")
    variety: Optional[str] = None
    sowing_date: date
    area_acres: float = Field(..., gt=0, le=1000)
    location_name: str = Field(..., min_length=1)
    stage: CropStage
    # Optional exact position (e.g. from the phone's GPS). When given, the
    # backend skips looking up `location_name`. Send both or neither.
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def _sowing_not_in_future(self) -> "CropProfileCreate":
        if self.sowing_date > date.today():
            raise ValueError("sowing_date cannot be in the future")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("send both latitude and longitude, or neither")
        return self


# ---------------------------------------------------------------------------
# F1 + F3 + F2 + F4 — One analysis of one uploaded leaf photo
# ---------------------------------------------------------------------------

class Prediction(BaseModel):
    """One ranked possibility from the image model (F1)."""

    label: str = Field(..., description="Raw class name from the model, e.g. 'Tomato___Early_blight'")
    display_name: LocalizedText
    confidence: float = Field(..., ge=0.0, le=1.0)


class Weather(BaseModel):
    """Context used by the risk engine (F3)."""

    source: WeatherSource
    rain_last_3_days_mm: float = Field(..., ge=0)
    avg_humidity_pct: float = Field(..., ge=0, le=100, description="Average over the last 3 days")
    avg_temp_c: float = Field(..., description="Average over the last 3 days")
    # Forecast (Component 5). Optional so older saved analyses still load.
    rain_next_3_days_mm: Optional[float] = Field(None, ge=0)
    max_rain_chance_next_3_days_pct: Optional[float] = Field(None, ge=0, le=100)
    summary: LocalizedText


class RiskReason(BaseModel):
    """One rule that fired in the risk engine. Feeds the explanation (F4)."""

    code: str = Field(..., description="Stable rule id, e.g. 'wet_weather'")
    points: int
    text: LocalizedText


class Risk(BaseModel):
    level: RiskLevel
    score: int = Field(..., ge=0)
    is_estimate: Literal[True] = True
    reasons: list[RiskReason]


class ActionCard(BaseModel):
    """One prioritized next step (F2). Must never contain pesticide names or doses."""

    card_id: str
    priority: int = Field(..., ge=1, description="1 = do this first")
    title: LocalizedText
    detail: LocalizedText
    why: LocalizedText


class Explanation(BaseModel):
    """Overall 'Why?' text for the analysis (F4)."""

    summary: LocalizedText
    verify: LocalizedText = Field(..., description="What the farmer should check before acting")


class AnalysisResult(BaseModel):
    analysis_id: str
    crop_id: str
    created_at: datetime
    is_demo: bool = Field(..., description="True when values are illustrative, not real model output")
    predictions: list[Prediction] = Field(..., min_length=1, max_length=3)
    uncertain: bool = Field(..., description="True when top confidence is below the threshold")
    uncertainty_message: Optional[LocalizedText] = None
    crop_mismatch: bool = Field(False, description="Model's crop differs from the profile's crop")
    weather: Optional[Weather] = None
    risk: Risk
    action_cards: list[ActionCard]
    explanation: Explanation

    @model_validator(mode="after")
    def _check_consistency(self) -> "AnalysisResult":
        # Predictions must be ranked highest-confidence first.
        confs = [p.confidence for p in self.predictions]
        if confs != sorted(confs, reverse=True):
            raise ValueError("predictions must be sorted by confidence, highest first")
        # An uncertain result must tell the farmer why.
        if self.uncertain and self.uncertainty_message is None:
            raise ValueError("uncertain results need an uncertainty_message")
        # Action-card priorities must be 1..N with no gaps or duplicates.
        prios = sorted(c.priority for c in self.action_cards)
        if prios != list(range(1, len(prios) + 1)):
            raise ValueError("action card priorities must be 1..N without gaps")
        return self


# ---------------------------------------------------------------------------
# F5 — Finance & loans (MOCK DATA in the MVP — no bank integration)
# ---------------------------------------------------------------------------

class RepaymentDue(BaseModel):
    due_date: date
    amount_inr: int = Field(..., ge=0)


class Loan(BaseModel):
    loan_id: str
    loan_type: str = Field(..., description="Short key, e.g. 'kcc' for Kisan Credit Card")
    display_name: LocalizedText
    lender_name: str
    status: LoanStatus
    sanctioned_amount_inr: int = Field(..., ge=0)
    outstanding_amount_inr: int = Field(..., ge=0)
    next_repayment: Optional[RepaymentDue] = None


class DocumentItem(BaseModel):
    code: str = Field(..., description="Stable id, e.g. 'land_record'")
    name: LocalizedText
    submitted: bool


class DocumentUpdate(BaseModel):
    """Body of PUT /api/crops/{crop_id}/loan/documents/{code}."""

    submitted: bool


class Scheme(BaseModel):
    """A government scheme worth checking. Eligibility must be verified officially."""

    code: str
    name: LocalizedText
    summary: LocalizedText
    official_url: Optional[str] = None
    verify_note: LocalizedText


class LoanSummary(BaseModel):
    # 'mock' for the hackathon. 'farmer_entered' is the planned next step
    # (farmer types/uploads their own details). Real bank data would come via
    # India's consent-based Account Aggregator framework — NOT built.
    data_source: Literal["mock", "farmer_entered"]
    crop_id: str
    loan: Loan
    documents: list[DocumentItem]
    missing_document_codes: list[str]
    schemes: list[Scheme]

    @model_validator(mode="after")
    def _missing_matches_documents(self) -> "LoanSummary":
        # The missing list must be exactly the documents not yet submitted.
        expected = [d.code for d in self.documents if not d.submitted]
        if sorted(expected) != sorted(self.missing_document_codes):
            raise ValueError(
                f"missing_document_codes {self.missing_document_codes} "
                f"does not match unsubmitted documents {expected}"
            )
        return self


# ---------------------------------------------------------------------------
# F7 — Multilingual chatbot
# ---------------------------------------------------------------------------

class ChatTurn(BaseModel):
    """One earlier message in the conversation, sent back for context."""

    role: Literal["user", "assistant"]
    text: str = Field(..., max_length=2000)


class ChatRequest(BaseModel):
    crop_id: str
    message: str = Field(..., min_length=1, max_length=1000)
    lang: str = Field("en", description="Language the reply should be in")
    history: list[ChatTurn] = Field(
        default_factory=list, max_length=20,
        description="Earlier turns, oldest first (the backend uses the last few)",
    )


class ChatReply(BaseModel):
    reply: str
    lang: str
    used_context: list[str] = Field(
        default_factory=list,
        description="Which saved data grounded the answer, e.g. ['crop_profile', 'loan_summary']",
    )
    is_fallback: bool = Field(
        False, description="True when the LLM was unavailable and a canned answer was used"
    )


class VoiceTranscript(BaseModel):
    """Result of POST /api/voice/transcribe (speech-to-text)."""

    text: str
    lang: str


class ChatExample(BaseModel):
    """A request/reply pair. Used for frontend mocks and as demo fallbacks."""

    request: ChatRequest
    reply: ChatReply


# ---------------------------------------------------------------------------
# The whole sample file
# ---------------------------------------------------------------------------

class SampleData(BaseModel):
    """Shape of `shared/sample_data.json`."""

    crop_profile: CropProfile
    analysis: AnalysisResult
    loan_summary: LoanSummary
    chat_examples: list[ChatExample]
