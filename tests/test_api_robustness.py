"""
Robustness tests: request-size guards, input validation and JSON error shapes.

These complement tests/test_api.py (which covers the happy paths and the
business rules). Everything here uses the shared fixtures in conftest.py, so no
network, no real model and no API key are needed.
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, repository
from backend.main import app

DEMO_CROP = "crop-demo-001"
# The fake classifier only needs a valid PNG signature; 64 bytes is plenty.
TINY_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MB = 1024 * 1024

# Message returned by the early Content-Length guard in backend/main.py. It
# differs from the per-endpoint message ("Photo is larger than 8 MB."), which is
# how these tests know the oversized body was refused before being buffered.
GUARD_DETAIL = "The uploaded file is too large."


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


# ----- oversized uploads -----------------------------------------------------

def test_oversized_photo_is_refused_before_it_is_buffered(client):
    """A 9 MB photo is rejected from Content-Length, before the body is read."""
    resp = client.post(
        f"/api/crops/{DEMO_CROP}/analyze",
        files={"image": ("big.png", TINY_PNG + b"\x00" * (9 * MB), "image/png")},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == GUARD_DETAIL


def test_oversized_recording_is_refused_before_it_is_buffered(client):
    """The audio limit (10 MB) is enforced the same way."""
    resp = client.post(
        "/api/voice/transcribe",
        files={"audio": ("q.webm", b"\x00" * (11 * MB), "audio/webm")},
        data={"lang": "hi"},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == GUARD_DETAIL


def test_normal_photo_still_reaches_the_endpoint(client):
    """The guard must not reject legitimate uploads."""
    resp = client.post(
        f"/api/crops/{DEMO_CROP}/analyze",
        files={"image": ("leaf.png", TINY_PNG, "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["crop_id"] == DEMO_CROP


# ----- request validation ----------------------------------------------------

def test_chat_rejects_a_blank_message(client):
    resp = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": "", "lang": "en"})
    assert resp.status_code == 422


def test_chat_rejects_an_overlong_message(client):
    resp = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": "x" * 1001, "lang": "en"})
    assert resp.status_code == 422


def test_chat_rejects_too_much_history(client):
    history = [{"role": "user", "text": "hi"}] * 21
    resp = client.post(
        "/api/chat",
        json={"crop_id": DEMO_CROP, "message": "hello", "lang": "en", "history": history},
    )
    assert resp.status_code == 422


def test_document_update_requires_a_boolean(client):
    resp = client.put(
        f"/api/crops/{DEMO_CROP}/loan/documents/land_record",
        json={"submitted": "definitely"},
    )
    assert resp.status_code == 422


def test_crop_area_must_be_positive(client):
    resp = client.post("/api/crops", json=new_crop_payload(area_acres=0))
    assert resp.status_code == 422


def test_analyze_for_unknown_crop_is_404(client):
    resp = client.post("/api/crops/does-not-exist/analyze", files={"image": ("leaf.png", TINY_PNG, "image/png")})
    assert resp.status_code == 404


def test_weather_for_unknown_crop_is_404(client):
    assert client.get("/api/crops/does-not-exist/weather").status_code == 404


# ----- health ----------------------------------------------------------------

def test_health_reports_chat_as_configured_when_a_key_exists(client, monkeypatch):
    monkeypatch.setattr(config, "groq_api_key", lambda: "gsk_test")
    body = client.get("/api/health").json()
    assert body["chat"] == "configured"
    assert body["status"] == "ok"


def test_health_reports_missing_api_key(client, monkeypatch):
    monkeypatch.setattr(config, "groq_api_key", lambda: None)
    assert client.get("/api/health").json()["chat"] == "no_api_key"


# ----- error shape -----------------------------------------------------------

def test_unexpected_error_returns_json_without_internal_details(db_file, fake_model, monkeypatch):
    """An unhandled exception becomes a generic JSON 500, never a traceback."""

    def boom(_crop_id):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(repository, "get_crop", boom)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        resp = test_client.get(f"/api/crops/{DEMO_CROP}")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Something went wrong on the server. Please try again."
    assert "secret internal detail" not in resp.text
