"""
DharRakshak — FastAPI backend (Components 2–9).

Run from the repository root:
    uvicorn backend.main:app --reload --port 8000

Then open http://localhost:8000/docs to try every endpoint in the browser.

All routes live under /api so the React dev server can forward /api/* to
this server (see frontend/vite.config.js) without CORS problems.

Every response uses a model from shared/contract.py (`response_model=`),
so FastAPI refuses to send anything that doesn't match the contract.

What's real vs. placeholder so far:
- Real: routing, input validation, upload checks, error codes, contract
  enforcement, CORS, and SQLite storage (crops, analyses, loans survive
  restarts). On first start the demo farmer is seeded automatically.
- Real (C4): the uploaded photo is classified by the pretrained
  MobileNetV2 model (top-3 predictions, uncertainty, crop mismatch).
- Real (C5): crop locations are geocoded with Open-Meteo (or taken from the
  phone's GPS), and each analysis includes real recent + forecast weather.
- Real (C6): risk, action cards and explanation from transparent rules.
- Real (C7): loan document checklist you can tick off (loan data is MOCK).
- Real (C9): grounded multilingual chatbot (Groq LLM) and voice input
  (Groq Whisper). Falls back to saved answers if Groq is unavailable.
"""

from __future__ import annotations

import logging
import os

from backend import config  # noqa: F401  (loads .env before anything reads keys)
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from backend import repository
from backend.db import init_db
from backend.ml import classifier as clf
from backend.pipeline import run_analysis
from backend.services import chat as chat_service
from backend.services import geocoding, llm, weather

log = logging.getLogger("dharrakshak")
from shared.contract import (
    AnalysisResult,
    ChatReply,
    ChatRequest,
    CropListItem,
    CropProfile,
    CropProfileCreate,
    DocumentUpdate,
    LoanSummary,
    VoiceTranscript,
    Weather,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Runs once when the server starts: create tables, seed the demo farmer,
    and load the image model so the first analysis is fast.
    Set DHARRAKSHAK_PRELOAD_MODEL=0 to skip loading (the tests do this)."""
    init_db()
    repository.seed_demo_if_empty()
    if os.getenv("DHARRAKSHAK_PRELOAD_MODEL", "1") != "0":
        try:
            await run_in_threadpool(clf.get_classifier)
            log.info("Image model loaded.")
        except clf.ModelNotAvailable as err:
            # The API still starts; /analyze returns 503 until the model exists.
            log.warning("Image model not available: %s", err)
    yield


app = FastAPI(
    title="DharRakshak API",
    version="0.9.0",
    lifespan=lifespan,
    description="Crop intelligence backend for the DharRakshak hackathon MVP. "
    "Loan data is MOCK — there is no bank integration.",
)

# Allow the React dev server to call the API directly too (useful if the
# Vite proxy isn't used, e.g. when opening a production build).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api")

# Upload rules for leaf photos.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB is plenty for a phone photo


def _require_crop(crop_id: str) -> CropProfile:
    """Return the crop or stop the request with a 404."""
    crop = repository.get_crop(crop_id)
    if crop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Crop '{crop_id}' not found")
    return crop


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", tags=["system"])
def health() -> dict:
    """Quick check that the server is running. `stage` tells you which
    roadmap component the backend is at; `model` whether the image model is
    loaded ("loaded") or will load on the first analysis ("not_loaded")."""
    return {
        "status": "ok",
        "stage": "component-9-chat-voice",
        "model": "loaded" if clf.is_loaded() else "not_loaded",
        "chat": "configured" if config.groq_api_key() else "no_api_key",
    }


# ---------------------------------------------------------------------------
# F2 — crop profiles
# ---------------------------------------------------------------------------

def _resolve_coordinates(form: CropProfileCreate, current: CropProfile | None = None) -> tuple[float, float]:
    """Where is this farm? In order of preference:
    1. coordinates sent by the app (phone GPS),
    2. unchanged location name → keep the stored coordinates,
    3. look the name up with Open-Meteo geocoding."""
    if form.latitude is not None and form.longitude is not None:
        return form.latitude, form.longitude
    if current is not None and current.location.name.strip().casefold() == form.location_name.strip().casefold():
        return current.location.latitude, current.location.longitude
    try:
        place = geocoding.geocode(form.location_name)
    except geocoding.LocationNotFound as err:
        raise HTTPException(422, str(err)) from err
    except geocoding.GeocodingUnavailable as err:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Location lookup is unavailable right now. Try again, or allow location access in the app.",
        ) from err
    return place.latitude, place.longitude


@router.post("/crops", response_model=CropProfile, status_code=status.HTTP_201_CREATED, tags=["crops"])
def create_crop(new_crop: CropProfileCreate) -> CropProfile:
    """Register a new farmer + crop from the registration form. The location
    is geocoded unless the app sends GPS coordinates."""
    lat, lon = _resolve_coordinates(new_crop)
    try:
        return repository.create_crop(new_crop, lat, lon)
    except repository.UnknownFarmer as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Farmer '{err}' not found") from err


@router.get("/crops", response_model=list[CropListItem], tags=["crops"])
def list_crops() -> list[CropListItem]:
    """All crops on this device (newest first) with a summary of their leaf
    checks — powers the "My crops" list and the crop switcher."""
    return repository.list_crops()


@router.get("/crops/{crop_id}", response_model=CropProfile, tags=["crops"])
def get_crop(crop_id: str) -> CropProfile:
    return _require_crop(crop_id)


@router.put("/crops/{crop_id}", response_model=CropProfile, tags=["crops"])
def update_crop(crop_id: str, changes: CropProfileCreate) -> CropProfile:
    """Edit an existing crop profile (keeps the same crop_id and history).
    The location is only looked up again if its name changed."""
    current = _require_crop(crop_id)
    lat, lon = _resolve_coordinates(changes, current)
    updated = repository.update_crop(crop_id, changes, lat, lon)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Crop '{crop_id}' not found")
    return updated


@router.get("/crops/{crop_id}/weather", response_model=Weather, tags=["crops"])
def crop_weather(crop_id: str) -> Weather:
    """Real recent + forecast weather at the crop's location (Open-Meteo).
    503 if the weather service can't be reached — never made-up numbers."""
    crop = _require_crop(crop_id)
    result = weather.get_weather(crop.location.latitude, crop.location.longitude)
    if result is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Weather is unavailable right now. Please try again.")
    return result


# ---------------------------------------------------------------------------
# F1 + F3 + F2 + F4 — leaf analysis
# ---------------------------------------------------------------------------

@router.post("/crops/{crop_id}/analyze", response_model=AnalysisResult, tags=["analysis"])
async def analyze(crop_id: str, image: UploadFile = File(..., description="Leaf photo (JPEG/PNG/WebP)")) -> AnalysisResult:
    """Upload a leaf photo and get predictions, risk, action cards and an
    explanation. Predictions (C4) and weather (C5) are real; risk, cards and
    explanation are still placeholders (Component 6)."""
    crop = _require_crop(crop_id)

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Please upload a JPEG, PNG or WebP photo (got {image.content_type}).",
        )
    data = await image.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo is larger than 8 MB.")

    try:
        classifier = await run_in_threadpool(clf.get_classifier)
    except clf.ModelNotAvailable as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(err)) from err
    try:
        # Inference is CPU-bound, so it runs in a worker thread and doesn't
        # block other requests.
        result = await run_in_threadpool(run_analysis, crop, data, classifier)
    except clf.InvalidImage as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err
    return repository.save_analysis(result)


@router.get("/crops/{crop_id}/history", response_model=list[AnalysisResult], tags=["analysis"])
def history(crop_id: str) -> list[AnalysisResult]:
    """All analyses for this crop, newest first (powers 'track progress')."""
    _require_crop(crop_id)
    return repository.list_analyses(crop_id)


# ---------------------------------------------------------------------------
# F5 — finance & loans (MOCK)
# ---------------------------------------------------------------------------

@router.get("/crops/{crop_id}/loan", response_model=LoanSummary, tags=["finance"])
def loan(crop_id: str) -> LoanSummary:
    """Loan status, dues, missing documents and schemes. Always mock data.
    404 when the farmer has no loan records (e.g. a newly registered farmer)."""
    _require_crop(crop_id)
    summary = repository.get_loan_summary(crop_id)
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No loan records for this farmer yet.")
    return summary


@router.put("/crops/{crop_id}/loan/documents/{code}", response_model=LoanSummary, tags=["finance"])
def update_document(crop_id: str, code: str, update: DocumentUpdate) -> LoanSummary:
    """Tick or untick a checklist document. Returns the updated summary, so
    the missing list and progress refresh immediately. (Mock data — this
    records what the farmer has handed to the bank; it is not sent anywhere.)"""
    _require_crop(crop_id)
    summary = repository.set_document_submitted(crop_id, code, update.submitted)
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No document '{code}' on this farmer's loan checklist.")
    return summary


# ---------------------------------------------------------------------------
# F7 — chatbot
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatReply, tags=["chat"])
def chat(request: ChatRequest) -> ChatReply:
    """Ask a question about the crop or loan, in English or Hindi. The answer
    is grounded in this farmer's saved data. If the LLM is unavailable, a
    saved demo answer is returned with `is_fallback: true`."""
    crop = _require_crop(request.crop_id)
    return chat_service.answer(request, crop)


# ---------------------------------------------------------------------------
# F7 — voice assistant (speech-to-text; replies are spoken by the browser)
# ---------------------------------------------------------------------------

ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3",
    "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/flac", "video/webm",  # some browsers label recordings video/webm
}
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # ~10 minutes of compressed speech; plenty for a question
# Whisper languages we pass through. Haryanvi and Bhojpuri have no Whisper
# model, so the frontend sends "hi" (closest) for them.
STT_LANGUAGES = {"en", "hi", "mr", "pa"}


@router.post("/voice/transcribe", response_model=VoiceTranscript, tags=["chat"])
async def transcribe(
    audio: UploadFile = File(..., description="Recorded question (webm/ogg/wav/mp3/m4a)"),
    lang: str = Form("hi", description="Expected language: en, hi, mr or pa (use 'hi' for Haryanvi/Bhojpuri)"),
) -> VoiceTranscript:
    """Speech-to-text for the voice assistant (Groq Whisper). The frontend
    sends the text to /api/chat and reads the reply aloud with the browser's
    built-in voice."""
    content_type = (audio.content_type or "").split(";")[0].strip()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported audio type: {content_type or 'unknown'}")
    data = await audio.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The recording is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Recording is too long.")
    try:
        text = await run_in_threadpool(llm.transcribe, data, audio.filename or "question.webm", content_type, lang)
    except llm.LLMUnavailable as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Voice input is unavailable right now. Please type your question.") from err
    if not text:
        raise HTTPException(422, "Couldn't hear any speech. Please try again, a little closer to the microphone.")
    return VoiceTranscript(text=text, lang=lang if lang in STT_LANGUAGES else "hi")


app.include_router(router)
