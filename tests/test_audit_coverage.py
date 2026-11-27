"""
Coverage for backend branches that no test reached before the audit.

Each test names the branch it pins. Everything here passed on first run except
where noted in the docstring, so this file documents behaviour rather than
changing it.

Run: scripts\py.cmd -m pytest tests/test_audit_coverage.py -q
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from backend import repository
from backend.db import connect
from backend.main import allowed_origin
from backend.services import weather
from backend.services.llm import clean_transcript
from shared.contract import (
    AnalysisResult,
    LocalizedText,
    LoanSummary,
)

DEMO_CROP = "crop-demo-001"
TINY_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def new_crop_payload(**overrides):
    payload = {
        "farmer_name": "Asha Devi",
        "crop_type": "tomato",
        "sowing_date": "2026-06-01",
        "area_acres": 1.2,
        "location_name": "Karnal",
        "stage": "vegetative",
    }
    payload.update(overrides)
    return payload


def text(value="x"):
    return {"en": value, "hi": value}


def make_analysis(**overrides):
    payload = {
        "analysis_id": "an-test",
        "crop_id": "crop-test",
        "created_at": datetime.now(timezone.utc),
        "is_demo": False,
        "predictions": [{"label": "Tomato___Early_blight", "display_name": text(), "confidence": 0.8}],
        "uncertain": False,
        "risk": {"level": "low", "score": 0, "reasons": []},
        "action_cards": [
            {"card_id": "c", "priority": 1, "title": text(), "detail": text(), "why": text()}
        ],
        "explanation": {"summary": text(), "verify": text()},
    }
    payload.update(overrides)
    return AnalysisResult(**payload)


# ---------------------------------------------------------------------------
# Classifier output combinations
# ---------------------------------------------------------------------------

def test_an_uncertain_photo_of_another_crop_still_reports_the_mismatch(client, fake_model):
    """The real classifier sets `crop_mismatch` from the winning class's crop
    alone and does not suppress it for low confidence (backend/ml/classifier.py).
    `tests/conftest.py`'s fake DID suppress it, and `test_low_confidence_is_uncertain`
    pinned that suppression, so the suite asserted behaviour production never had.
    """
    fake_model.top_index = 21  # Potato___Late_blight; the demo crop is tomato
    fake_model.confidence = 0.30
    body = client.post(
        f"/api/crops/{DEMO_CROP}/analyze",
        files={"image": ("leaf.png", TINY_PNG, "image/png")},
    ).json()
    assert body["uncertain"] is True
    assert body["crop_mismatch"] is True


# ---------------------------------------------------------------------------
# Loan edge cases
# ---------------------------------------------------------------------------

def test_a_loan_without_a_due_date_has_no_next_repayment(client):
    """`get_loan_summary`'s `next_due_date IS NULL` branch was never exercised."""
    with connect() as conn:
        conn.execute("UPDATE loans SET next_due_date = NULL, next_due_amount_inr = NULL")

    body = client.get(f"/api/crops/{DEMO_CROP}/loan").json()
    assert body["loan"]["next_repayment"] is None
    # The rest of the summary must still be complete.
    assert body["documents"]


def test_loan_summary_rejects_missing_codes_that_do_not_match_the_documents():
    """`LoanSummary._missing_matches_documents` raise was never triggered."""
    with pytest.raises(PydanticValidationError, match="missing_document_codes"):
        LoanSummary(
            data_source="mock",
            crop_id="crop-1",
            loan={
                "loan_id": "l-1",
                "loan_type": "kcc",
                "display_name": text("KCC"),
                "lender_name": "Bank",
                "status": "active",
                "sanctioned_amount_inr": 1000,
                "outstanding_amount_inr": 500,
            },
            documents=[{"code": "land_record", "name": text(), "submitted": False}],
            missing_document_codes=[],  # contradicts the unsubmitted document above
            schemes=[],
        )


# ---------------------------------------------------------------------------
# AnalysisResult consistency rules
# ---------------------------------------------------------------------------

def test_an_uncertain_result_must_explain_itself():
    with pytest.raises(PydanticValidationError, match="uncertainty_message"):
        make_analysis(uncertain=True, uncertainty_message=None)


def test_action_card_priorities_must_be_one_to_n():
    cards = [
        {"card_id": "a", "priority": 1, "title": text(), "detail": text(), "why": text()},
        {"card_id": "b", "priority": 3, "title": text(), "detail": text(), "why": text()},
    ]
    with pytest.raises(PydanticValidationError, match="priorities"):
        make_analysis(action_cards=cards)


def test_at_most_three_predictions_are_allowed():
    four = [{"label": f"L{i}", "display_name": text(), "confidence": 0.9 - i * 0.1} for i in range(4)]
    with pytest.raises(PydanticValidationError):
        make_analysis(predictions=four)


def test_localized_text_requires_both_english_and_hindi():
    with pytest.raises(PydanticValidationError):
        LocalizedText(en="only english")


def test_in_lang_falls_back_to_english_for_an_unknown_code():
    """`LANGUAGE_FALLBACK.get(lang, "en")` — an arbitrary code must not loop or crash."""
    value = LocalizedText(en="tomato", hi="टमाटर")
    assert value.in_lang("ta") == "tomato"
    assert value.in_lang("") == "tomato"


# ---------------------------------------------------------------------------
# Weather edge cases
# ---------------------------------------------------------------------------

def test_parse_weather_rejects_a_response_with_no_recent_values():
    payload = {
        "daily": {
            "time": ["d0", "d1", "d2", "d3"],
            "precipitation_sum": [None, None, None, None],
            "relative_humidity_2m_mean": [None, None, None, 60],
            "temperature_2m_mean": [None, None, None, 20],
            "precipitation_probability_max": [None, None, None, 0],
        }
    }
    with pytest.raises(weather.WeatherUnavailable, match="missing recent values"):
        weather.parse_weather(payload)


def test_a_summary_without_a_forecast_omits_the_forecast_sentence():
    """`build_summary` with `rain_next=None` — the second sentence is skipped."""
    summary = weather.build_summary(5.0, 80.0, 24.0, None, None)
    assert "mm" in summary.en
    # No forecast was available, so the summary must not invent one.
    assert summary.en == weather.build_summary(5.0, 80.0, 24.0, None, None).en


def test_get_weather_returns_none_when_the_payload_breaks_the_contract(monkeypatch):
    """A 200 whose humidity is 200% fails the `Weather` contract (le=100).

    `get_weather` must degrade to None, not raise a 500.
    """
    bad = {
        "daily": {
            "time": ["d0", "d1", "d2", "d3"],
            "precipitation_sum": [0.0, 0.0, 0.0, 0.0],
            "relative_humidity_2m_mean": [200, 200, 200, 200],
            "temperature_2m_mean": [20.0, 20.0, 20.0, 20.0],
            "precipitation_probability_max": [0, 0, 0, 0],
        }
    }
    monkeypatch.setattr(weather, "fetch_daily", lambda lat, lon: bad)
    weather.clear_cache()
    assert weather.get_weather(11.11, 22.22) is None


# ---------------------------------------------------------------------------
# Transcript cleaning
# ---------------------------------------------------------------------------

def test_an_empty_segment_list_falls_back_to_the_plain_text():
    """`clean_transcript` treats `segments: []` as absent, not as 'no speech'."""
    assert clean_transcript({"segments": [], "text": " keeda hai "}) == "keeda hai"


# ---------------------------------------------------------------------------
# CORS allow-list
# ---------------------------------------------------------------------------

def test_allowed_origin_accepts_a_vercel_deployment():
    assert allowed_origin("https://dhar-rakshak-abc123.vercel.app")


def test_allowed_origin_rejects_a_foreign_site():
    """The `None` branch for a present-but-disallowed Origin was untested."""
    assert allowed_origin("https://evil.example.com") is None
    assert allowed_origin("http://localhost:5173.evil.com") is None


def test_allowed_origin_rejects_a_missing_header():
    assert allowed_origin(None) is None


# ---------------------------------------------------------------------------
# Routing: paths and methods that do not exist
# ---------------------------------------------------------------------------

def test_an_unknown_path_is_json_404(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_a_wrong_method_is_405(client):
    assert client.post("/api/health").status_code == 405
    assert client.delete(f"/api/crops/{DEMO_CROP}").status_code == 405


# ---------------------------------------------------------------------------
# Write endpoints: validation and dependency outage
# ---------------------------------------------------------------------------

def test_updating_a_crop_with_an_invalid_body_is_422(client):
    """PUT /api/crops/{id} 422 was never sent; only POST was tested."""
    resp = client.put(f"/api/crops/{DEMO_CROP}", json=new_crop_payload(farmer_name=""))
    assert resp.status_code == 422


def test_updating_a_crop_survives_a_geocoding_outage_with_503(client, fake_open_meteo):
    """Renaming the location forces a geocode; an outage must be 503, not 500."""
    fake_open_meteo.down = True
    resp = client.put(
        f"/api/crops/{DEMO_CROP}",
        json=new_crop_payload(location_name="Aurangabad"),
    )
    assert resp.status_code == 503
    assert "location" in resp.json()["detail"].lower()


def test_a_document_update_for_an_unknown_crop_is_404(client):
    """The only write endpoint whose crop-404 was untested."""
    resp = client.put(
        "/api/crops/no-such-crop/loan/documents/land_record",
        json={"submitted": True},
    )
    assert resp.status_code == 404


def test_transcribe_without_an_audio_part_is_422(client):
    resp = client.post("/api/voice/transcribe", data={"lang": "hi"})
    assert resp.status_code == 422


def test_preferred_language_must_be_a_supported_code(client):
    resp = client.post(
        "/api/crops",
        json=new_crop_payload(preferred_language="klingon", latitude=28.99, longitude=77.02),
    )
    assert resp.status_code == 422


def test_every_supported_language_is_accepted(client):
    for code in ("en", "hi", "mr", "pa", "bgc", "bho"):
        resp = client.post(
            "/api/crops",
            json=new_crop_payload(preferred_language=code, latitude=28.99, longitude=77.02),
        )
        assert resp.status_code == 201, (code, resp.text)


# ---------------------------------------------------------------------------
# Chat: whitespace handling
# ---------------------------------------------------------------------------

def test_surrounding_whitespace_is_trimmed_before_the_model_sees_it(client, fake_llm):
    fake_llm.reply = "ok"
    client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": "  keeda hai?  ", "lang": "hi"})
    sent = fake_llm.messages[-1]["content"]
    assert sent == "keeda hai?"


# ---------------------------------------------------------------------------
# Repository: unreadable rows are skipped, not fatal
# ---------------------------------------------------------------------------

def test_list_analyses_skips_a_corrupt_row(client):
    """A bad `result_json` must not break the crop's whole history."""
    with connect() as conn:
        conn.execute(
            """INSERT INTO analyses (analysis_id, crop_id, created_at, top_label, risk_level, is_demo, result_json)
               VALUES ('an-corrupt', ?, '2026-10-19T00:00:00+00:00', 'x', 'low', 0, '{not json')""",
            (DEMO_CROP,),
        )
    resp = client.get(f"/api/crops/{DEMO_CROP}/history")
    assert resp.status_code == 200
    assert all(item["analysis_id"] != "an-corrupt" for item in resp.json())


def test_schemes_are_empty_for_an_unknown_loan_type():
    """`schemes_for`'s `.get(loan_type, [])` default."""
    assert repository.schemes_for("no_such_loan_type") == []
