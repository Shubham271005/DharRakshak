"""
Analysis pipeline: one leaf photo → one AnalysisResult.

    photo ─► [C4] image model ─► [C5] weather ─► [C6] risk ─► action cards ─► explanation

Status after Component 4:
- REAL: predictions, uncertainty check, crop-mismatch check (image model).
- PLACEHOLDER: weather, risk, action cards and explanation still come from
  the sample analysis, so `is_demo` stays True and the UI keeps showing the
  DEMO EXAMPLE tag. Components 5 and 6 replace these, then `is_demo` becomes
  False.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.ml.classifier import ClassifierOutput, PlantDiseaseClassifier
from backend.sample_store import sample
from shared.contract import AnalysisResult, CropProfile


def build_analysis(crop: CropProfile, output: ClassifierOutput) -> AnalysisResult:
    """Combine the model output with the (for now placeholder) later stages."""
    placeholder = sample().analysis

    # The photo looks like a different crop than the farmer registered.
    # Only flagged when the model is reasonably confident, otherwise the
    # "uncertain" message already covers it.
    crop_mismatch = (not output.uncertain) and output.top.crop != crop.crop_type

    return AnalysisResult(
        analysis_id=f"an-{uuid.uuid4().hex[:8]}",
        crop_id=crop.crop_id,
        created_at=datetime.now(timezone.utc),
        is_demo=True,  # becomes False once weather/risk/cards are real (C5, C6)
        predictions=output.predictions,
        uncertain=output.uncertain,
        uncertainty_message=output.uncertainty_message,
        crop_mismatch=crop_mismatch,
        # ---- placeholders until Components 5–6 ----
        weather=placeholder.weather,
        risk=placeholder.risk,
        action_cards=placeholder.action_cards,
        explanation=placeholder.explanation,
    )


def run_analysis(crop: CropProfile, image_bytes: bytes, classifier: PlantDiseaseClassifier) -> AnalysisResult:
    """Full pipeline for one photo. Raises InvalidImage for unreadable files."""
    return build_analysis(crop, classifier.classify(image_bytes))
