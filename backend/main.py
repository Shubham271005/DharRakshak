"""
DharRakshak — FastAPI backend (Component 2: skeleton).

Run from the repository root:
    uvicorn backend.main:app --reload --port 8000

Then open http://localhost:8000/docs to try every endpoint in the browser.

All routes live under /api so the React dev server can forward /api/* to
this server (see frontend/vite.config.js) without CORS problems.

Every response uses a model from shared/contract.py (`response_model=`),
so FastAPI refuses to send anything that doesn't match the contract.

What's real vs. placeholder in this component:
- Real: routing, input validation, upload checks, error codes, contract
  enforcement, CORS.
- Placeholder: storage is in memory (sample_store.py); analysis ignores the
  photo and returns the sample result; chat uses keyword matching.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from backend.sample_store import mock_chat_reply, store
from shared.contract import (
    AnalysisResult,
    ChatReply,
    ChatRequest,
    CropProfile,
    CropProfileCreate,
    LoanSummary,
)

app = FastAPI(
    title="DharRakshak API",
    version="0.2.0",
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
    crop = store.get_crop(crop_id)
    if crop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Crop '{crop_id}' not found")
    return crop


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", tags=["system"])
def health() -> dict:
    """Quick check that the server is running. `stage` tells you which
    roadmap component the backend is at."""
    return {"status": "ok", "stage": "component-2-skeleton"}


# ---------------------------------------------------------------------------
# F2 — crop profiles
# ---------------------------------------------------------------------------

@router.post("/crops", response_model=CropProfile, status_code=status.HTTP_201_CREATED, tags=["crops"])
def create_crop(new_crop: CropProfileCreate) -> CropProfile:
    """Register a crop from the farmer's form input."""
    return store.create_crop(new_crop)


@router.get("/crops/{crop_id}", response_model=CropProfile, tags=["crops"])
def get_crop(crop_id: str) -> CropProfile:
    return _require_crop(crop_id)


# ---------------------------------------------------------------------------
# F1 + F3 + F2 + F4 — leaf analysis
# ---------------------------------------------------------------------------

@router.post("/crops/{crop_id}/analyze", response_model=AnalysisResult, tags=["analysis"])
async def analyze(crop_id: str, image: UploadFile = File(..., description="Leaf photo (JPEG/PNG/WebP)")) -> AnalysisResult:
    """Upload a leaf photo and get predictions, risk, action cards and an
    explanation. SKELETON: the photo is validated but not analyzed yet."""
    _require_crop(crop_id)

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

    # Component 4 replaces this line with: model → weather → risk → actions → explanation.
    return store.mock_analysis(crop_id)


@router.get("/crops/{crop_id}/history", response_model=list[AnalysisResult], tags=["analysis"])
def history(crop_id: str) -> list[AnalysisResult]:
    """All analyses for this crop, newest first (powers 'track progress')."""
    _require_crop(crop_id)
    return store.history(crop_id)


# ---------------------------------------------------------------------------
# F5 — finance & loans (MOCK)
# ---------------------------------------------------------------------------

@router.get("/crops/{crop_id}/loan", response_model=LoanSummary, tags=["finance"])
def loan(crop_id: str) -> LoanSummary:
    """Loan status, dues, missing documents and schemes. Always mock data."""
    _require_crop(crop_id)
    return store.get_loan(crop_id)


# ---------------------------------------------------------------------------
# F7 — chatbot
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatReply, tags=["chat"])
def chat(request: ChatRequest) -> ChatReply:
    """Ask a question about the crop or loan. SKELETON: keyword-matched
    sample answers; the grounded LLM arrives in Component 9."""
    _require_crop(request.crop_id)
    return mock_chat_reply(request)


app.include_router(router)
