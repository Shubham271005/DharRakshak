"""
DharRakshak — FastAPI backend (Components 2–9).

Run from the repository root:
    uvicorn backend.main:app --reload --port 8000

Then open http://localhost:8000/docs to try every endpoint in the browser.

All routes live under /api so the React dev server can forward /api/* to
this server (see frontend/vite.config.js) without CORS problems.

Every response body is a model from shared/contract.py via `response_model=`
(the one exception is the small `/api/health` dict), so FastAPI refuses to
send anything that doesn't match the contract.

Completeness: every feature this module serves (routing, validation, upload
checks, error codes, contract enforcement, CORS, rate limiting, SQLite
storage, image model, weather, rule engines, loans, chat and voice) is
implemented — nothing in the request path is a placeholder. The only mock
data is the loan records, which is labelled as such in the API
(`data_source: "mock"`) and in the UI.
"""

from __future__ import annotations

import logging
import os
import re

from backend import config  # noqa: F401  (loads .env before anything reads keys)
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend import repository
from backend.db import init_db
from backend.ml import classifier as clf
from backend.pipeline import run_analysis
from backend.services import chat as chat_service
from backend.services import geocoding, llm, ratelimit, weather

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

# Routes that accept an uploaded file, with the largest body they may accept.
# Checked from Content-Length BEFORE the body is read: without this the whole
# upload is buffered before the endpoint can reject it, which lets a client
# fill the disk with a single oversized request.
_UPLOAD_LIMITS = (
    (re.compile(r"^/api/crops/[^/]+/analyze$"), 8 * 1024 * 1024),
    (re.compile(r"^/api/voice/transcribe$"), 10 * 1024 * 1024),
)
# Room for the multipart boundaries and part headers around the file itself.
_MULTIPART_OVERHEAD = 64 * 1024


@app.middleware("http")
async def reject_oversized_uploads(request: Request, call_next):
    """Refuse an oversized upload before it is buffered into memory or disk.

    Registered before CORSMiddleware on purpose, so CORS ends up outermost and
    the browser can still read this 413. Requests without a Content-Length
    (chunked uploads) fall through to the per-endpoint size check.
    """
    if request.method == "POST":
        declared = request.headers.get("content-length")
        if declared and declared.isdigit():
            size = int(declared)
            for pattern, limit in _UPLOAD_LIMITS:
                if pattern.match(request.url.path) and size > limit + _MULTIPART_OVERHEAD:
                    return JSONResponse(
                        status_code=413,  # plain int: the named constant is
                        # deprecated in newer Starlette and absent in older ones.
                        content={"detail": "The uploaded file is too large."},
                    )
    return await call_next(request)


# Which websites may call this API from the browser: the local dev server,
# any Vercel deployment (*.vercel.app), plus extra origins listed in
# DHARRAKSHAK_CORS_ORIGINS (comma-separated, e.g. a custom domain).
# `allowed_origin()` is reused by the catch-all handler below, which has to add
# the header itself (see its docstring).
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173",
                *[o.strip() for o in os.getenv("DHARRAKSHAK_CORS_ORIGINS", "").split(",") if o.strip()]]
CORS_ORIGIN_REGEX = r"https://[a-z0-9-]+\.vercel\.app"
_cors_origin_re = re.compile(CORS_ORIGIN_REGEX)


def allowed_origin(origin: str | None) -> str | None:
    """The Origin to echo back, or None if this site may not call the API."""
    if not origin:
        return None
    if origin in CORS_ORIGINS or _cors_origin_re.fullmatch(origin):
        return origin
    return None


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, err: Exception) -> JSONResponse:
    """Last-resort handler: log the reason, return a generic message.

    Keeps every failure as JSON (the frontend reads `detail`) and never sends
    a stack trace or internal state to the browser.

    Starlette's own ServerErrorMiddleware runs OUTSIDE CORSMiddleware, so a
    response raised from here would reach the browser without an
    Access-Control-Allow-Origin header — the fetch would then look like a
    network failure and the frontend could not read `detail`. The header is
    therefore added here as well, using the same allow-list.
    """
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    headers = {}
    origin = allowed_origin(request.headers.get("origin"))
    if origin:
        headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Something went wrong on the server. Please try again."},
        headers=headers,
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


def _rate_limit(request: Request, bucket: str) -> None:
    """Count this call against the bucket's per-client and global limits.

    The three expensive routes (analyze, chat, transcribe) are reachable by
    anyone, and two of them spend Groq credits, so each caller gets a budget
    per minute. See backend/services/ratelimit.py.
    """
    client = ratelimit.client_key(
        request.client.host if request.client else None,
        request.headers.get("x-forwarded-for"),
    )
    try:
        ratelimit.check(bucket, client)
    except ratelimit.RateLimited as err:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(max(1, int(err.retry_after + 0.5)))},
        ) from err


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", tags=["system"])
def health() -> dict:
    """Quick check that the server is running. `stage` is the most recent
    completed ROADMAP milestone; `model` says whether the image model is
    loaded ("loaded") or will load on the first analysis ("not_loaded")."""
    return {
        "status": "ok",
        "stage": "upgrade-1-field-accuracy",
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
async def analyze(
    crop_id: str,
    request: Request,
    image: UploadFile = File(..., description="Leaf photo (JPEG/PNG/WebP)"),
) -> AnalysisResult:
    """Upload a leaf photo and get predictions, real weather, a risk estimate,
    ranked action cards and a "Why?" explanation."""
    _rate_limit(request, "analyze")
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
        # Plain 413 rather than a named constant: the old name
        # (HTTP_413_REQUEST_ENTITY_TOO_LARGE) is deprecated in newer
        # Starlette and its replacement is absent in older ones.
        raise HTTPException(413, "Photo is larger than 8 MB.")

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
def chat(request: Request, body: ChatRequest) -> ChatReply:
    """Ask a question about the crop or loan, in any supported language. The
    answer is grounded in this farmer's saved data. If the LLM is unavailable,
    a saved demo answer is returned with `is_fallback: true`."""
    _rate_limit(request, "chat")
    crop = _require_crop(body.crop_id)
    return chat_service.answer(body, crop)


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
    request: Request,
    audio: UploadFile = File(..., description="Recorded question (webm/ogg/wav/mp3/m4a)"),
    lang: str = Form("hi", description="Expected language: en, hi, mr or pa (use 'hi' for Haryanvi/Bhojpuri)"),
) -> VoiceTranscript:
    """Speech-to-text for the voice assistant (Groq Whisper). The frontend
    sends the text to /api/chat and reads the reply aloud with the browser's
    built-in voice."""
    _rate_limit(request, "transcribe")
    content_type = (audio.content_type or "").split(";")[0].strip()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported audio type: {content_type or 'unknown'}")
    data = await audio.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The recording is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording is too long.")
    try:
        text = await run_in_threadpool(llm.transcribe, data, audio.filename or "question.webm", content_type, lang)
    except llm.LLMUnavailable as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Voice input is unavailable right now. Please type your question.") from err
    if not text:
        raise HTTPException(422, "Couldn't hear any speech. Please try again, a little closer to the microphone.")
    return VoiceTranscript(text=text, lang=lang if lang in STT_LANGUAGES else "hi")


app.include_router(router)
