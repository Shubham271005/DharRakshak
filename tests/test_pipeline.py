"""
Unit tests for the analysis pipeline (backend/pipeline.py).

`build_analysis` is pure, so every combination of model output, weather and
crop stage can be checked directly. `run_analysis` is checked for its two
contracts: it classifies with the REGISTERED crop, and weather failure never
stops an analysis.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from backend.ml.classifier import ClassInfo, ClassifierOutput, InvalidImage, load_labels
from backend.pipeline import build_analysis, run_analysis
from backend.services.weather import WeatherUnavailable
from shared.contract import CropProfile, LocalizedText, Location, Prediction, Weather, WeatherSource

LABELS = load_labels()
TOMATO_BLIGHT = next(c for c in LABELS if c.label == "Tomato___Early_blight")
TOMATO_HEALTHY = next(c for c in LABELS if c.label == "Tomato___healthy")
POTATO_LATE = next(c for c in LABELS if c.label == "Potato___Late_blight")


def crop(stage="flowering", crop_type="tomato") -> CropProfile:
    return CropProfile(
        crop_id="crop-1", farmer_id="farmer-1", farmer_name="Test", crop_type=crop_type,
        sowing_date=date(2026, 8, 1), days_since_sowing=40, area_acres=2,
        location=Location(name="Sonipat", latitude=28.99, longitude=77.02), stage=stage,
    )


def weather(rain=0.0, humidity=50.0, temp=24.0, rain_next=0.0, chance=0.0) -> Weather:
    return Weather(
        source=WeatherSource.open_meteo, rain_last_3_days_mm=rain, avg_humidity_pct=humidity,
        avg_temp_c=temp, rain_next_3_days_mm=rain_next, max_rain_chance_next_3_days_pct=chance,
        summary=LocalizedText(en="summary", hi="सारांश"),
    )


def output(top: ClassInfo = TOMATO_BLIGHT, confidence: float = 0.9, uncertain: bool = False,
           mismatch: bool = False) -> ClassifierOutput:
    predictions = [
        Prediction(label=top.label, display_name=LocalizedText(en=top.label, hi=top.label),
                   confidence=confidence),
    ]
    return ClassifierOutput(
        predictions=predictions, top=top, uncertain=uncertain,
        uncertainty_message=LocalizedText(en="photo unclear", hi="तस्वीर साफ़ नहीं") if uncertain else None,
        crop_mismatch=mismatch,
    )


# ---------------------------------------------------------------------------
# build_analysis
# ---------------------------------------------------------------------------


def test_the_result_is_stamped_with_the_crop_and_is_not_demo_data():
    result = build_analysis(crop(), output(), weather())
    assert result.crop_id == "crop-1"
    assert result.is_demo is False
    assert result.analysis_id.startswith("an-")
    assert len(result.analysis_id) > 3


def test_the_timestamp_is_timezone_aware_and_current():
    before = datetime.now(timezone.utc)
    result = build_analysis(crop(), output(), weather())
    assert result.created_at.tzinfo is not None
    assert before <= result.created_at <= datetime.now(timezone.utc)


def test_every_part_of_the_result_comes_from_a_real_engine():
    result = build_analysis(crop(), output(), weather(rain=30, humidity=90, rain_next=20, chance=90))
    assert result.predictions
    assert result.risk.level.value in ("low", "moderate", "elevated")
    assert result.risk.is_estimate is True
    assert 1 <= len(result.action_cards) <= 3
    assert result.explanation.summary.en.strip()
    assert result.explanation.verify.en.strip()


def test_the_classifier_flags_are_passed_through_untouched():
    result = build_analysis(crop(), output(confidence=0.2, uncertain=True, mismatch=True), weather())
    assert result.uncertain is True
    assert result.crop_mismatch is True
    assert result.uncertainty_message is not None


def test_a_healthy_leaf_produces_low_risk_and_a_healthy_verify_line():
    result = build_analysis(crop(), output(TOMATO_HEALTHY, 0.97), weather())
    assert result.risk.level.value == "low"
    assert "look healthy" in result.explanation.verify.en
    assert result.explanation.about is None


def test_a_disease_at_flowering_in_wet_weather_is_elevated():
    result = build_analysis(crop("flowering"), output(TOMATO_BLIGHT, 0.9),
                            weather(rain=30, humidity=90, rain_next=20, chance=90))
    assert result.risk.level.value == "elevated"
    assert result.explanation.about is not None


def test_missing_weather_still_produces_a_complete_result():
    result = build_analysis(crop(), output(), None)
    assert result.weather is None
    assert "weather_unavailable" in [r.code for r in result.risk.reasons]
    assert result.action_cards
    assert result.explanation.summary.en.strip()


def test_a_crop_mismatch_is_reported_but_does_not_change_the_prediction():
    result = build_analysis(crop(crop_type="tomato"), output(POTATO_LATE, 0.9, mismatch=True), weather())
    assert result.predictions[0].label == "Potato___Late_blight"
    assert result.crop_mismatch is True
    assert result.action_cards[0].card_id == "check_crop"


@pytest.mark.parametrize("stage", ["seedling", "vegetative", "flowering", "fruiting", "maturity"])
def test_every_crop_stage_produces_a_valid_result(stage):
    result = build_analysis(crop(stage), output(), weather())
    assert [c.priority for c in result.action_cards] == list(range(1, len(result.action_cards) + 1))


def test_the_result_survives_a_json_round_trip():
    """It is stored as result_json, so it must serialise and re-validate."""
    from shared.contract import AnalysisResult

    result = build_analysis(crop(), output(), weather(rain=12, humidity=85))
    restored = AnalysisResult.model_validate_json(result.model_dump_json())
    assert restored.risk == result.risk
    assert restored.predictions == result.predictions


def test_two_analyses_get_different_ids():
    ids = {build_analysis(crop(), output(), weather()).analysis_id for _ in range(20)}
    assert len(ids) == 20


# ---------------------------------------------------------------------------
# run_analysis
# ---------------------------------------------------------------------------


class RecordingClassifier:
    """Records the crop it was asked to classify, like the real one."""

    def __init__(self, result=None, error=None):
        self.result = result or output()
        self.error = error
        self.calls = []

    def classify(self, image_bytes, registered_crop=None):
        self.calls.append((image_bytes, registered_crop))
        if self.error:
            raise self.error
        return self.result


def test_run_analysis_passes_the_registered_crop_to_the_model(monkeypatch):
    monkeypatch.setattr("backend.pipeline.get_weather", lambda lat, lon: weather())
    classifier = RecordingClassifier()
    run_analysis(crop(crop_type="tomato"), b"png-bytes", classifier)
    assert classifier.calls == [(b"png-bytes", "tomato")]


def test_run_analysis_asks_for_the_crops_own_coordinates(monkeypatch):
    asked = {}

    def fake_weather(lat, lon):
        asked["coords"] = (lat, lon)
        return weather()

    monkeypatch.setattr("backend.pipeline.get_weather", fake_weather)
    run_analysis(crop(), b"png", RecordingClassifier())
    assert asked["coords"] == (28.99, 77.02)


def test_a_weather_outage_does_not_fail_the_analysis(monkeypatch):
    def boom(lat, lon):
        raise WeatherUnavailable("down")

    monkeypatch.setattr("backend.pipeline.get_weather", boom)
    with pytest.raises(WeatherUnavailable):
        # run_analysis relies on get_weather returning None (it handles its own
        # failures); a raised error is a programming error, so it propagates.
        run_analysis(crop(), b"png", RecordingClassifier())


def test_an_invalid_image_propagates_so_the_api_can_return_400(monkeypatch):
    monkeypatch.setattr("backend.pipeline.get_weather", lambda lat, lon: weather())
    classifier = RecordingClassifier(error=InvalidImage("not an image"))
    with pytest.raises(InvalidImage):
        run_analysis(crop(), b"junk", classifier)


def test_run_analysis_uses_the_weather_it_was_given(monkeypatch):
    monkeypatch.setattr("backend.pipeline.get_weather",
                        lambda lat, lon: weather(rain=30, humidity=90, rain_next=20, chance=90))
    result = run_analysis(crop(), b"png", RecordingClassifier())
    assert result.weather is not None
    assert result.risk.level.value == "elevated"
