"""
Analysis pipeline: one leaf photo → one AnalysisResult.

    photo ─► image model (C4) ─► weather (C5) ─► risk ─► action cards ─► explanation (C6)

Everything is real after Component 6:
- predictions, uncertainty and crop-mismatch checks come from the model,
- weather comes from Open-Meteo (None if unreachable — never made up),
- risk, cards and explanation come from the transparent rule engines in
  backend/engines/ using the content in shared/content/.

So `is_demo` is False for every real analysis. (Only the seeded sample
analysis from shared/sample_data.json keeps is_demo=True.)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.engines.actions import choose_cards
from backend.engines.explain import build_explanation
from backend.engines.facts import Facts
from backend.engines.risk import assess_risk
from backend.ml.classifier import ClassifierOutput, PlantDiseaseClassifier
from backend.services.weather import get_weather
from shared.contract import AnalysisResult, CropProfile, Weather


def build_analysis(crop: CropProfile, output: ClassifierOutput, weather: Weather | None) -> AnalysisResult:
    """Combine model output, weather and crop profile into one result."""
    # The classifier ranks only the registered crop's classes and flags a
    # mismatch when the photo puts almost no weight on that crop.
    crop_mismatch = output.crop_mismatch

    facts = Facts(
        crop=crop,
        top=output.top,
        confidence=output.predictions[0].confidence,
        uncertain=output.uncertain,
        crop_mismatch=crop_mismatch,
        weather=weather,
    )
    risk = assess_risk(facts)

    return AnalysisResult(
        analysis_id=f"an-{uuid.uuid4().hex[:8]}",
        crop_id=crop.crop_id,
        created_at=datetime.now(timezone.utc),
        is_demo=False,
        predictions=output.predictions,
        uncertain=output.uncertain,
        uncertainty_message=output.uncertainty_message,
        crop_mismatch=crop_mismatch,
        weather=weather,
        risk=risk,
        action_cards=choose_cards(facts),
        explanation=build_explanation(facts, risk),
    )


def run_analysis(crop: CropProfile, image_bytes: bytes, classifier: PlantDiseaseClassifier) -> AnalysisResult:
    """Full pipeline for one photo. Raises InvalidImage for unreadable files."""
    output = classifier.classify(image_bytes, registered_crop=crop.crop_type)
    weather = get_weather(crop.location.latitude, crop.location.longitude)
    return build_analysis(crop, output, weather)
