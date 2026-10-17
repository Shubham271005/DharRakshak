"""
Backend API tests (Components 2–3). Run from the repository root:
    pytest

Each test calls the API exactly like the React app would, against a fresh
temporary database (see conftest.py), and checks both happy paths and
error cases.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.sample_store import sample

DEMO_CROP = sample().crop_profile.crop_id

# A real (1×1 pixel) PNG so upload tests send genuine image bytes.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def new_crop_payload(**overrides):
    payload = {
        "farmer_name": "Asha", "crop_type": "potato",
        "sowing_date": (date.today() - timedelta(days=30)).isoformat(),
        "area_acres": 1.2, "location_name": "Karnal", "stage": "vegetative",
    }
    payload.update(overrides)
    return payload


# ----- system ---------------------------------------------------------------

def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ----- crops (F2) -----------------------------------------------------------

def test_demo_crop_is_seeded(client):
    resp = client.get(f"/api/crops/{DEMO_CROP}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["crop_type"] == "tomato"
    # days_since_sowing is computed from today, not copied from the sample.
    expected = (date.today() - date.fromisoformat(body["sowing_date"])).days
    assert body["days_since_sowing"] == expected


def test_unknown_crop_is_404(client):
    assert client.get("/api/crops/does-not-exist").status_code == 404


def test_create_crop(client):
    resp = client.post("/api/crops", json=new_crop_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["days_since_sowing"] == 30
    assert body["location"]["name"] == "Karnal"
    assert client.get(f"/api/crops/{body['crop_id']}").json()["farmer_name"] == "Asha"


def test_create_crop_rejects_future_sowing_date(client):
    future = (date.today() + timedelta(days=3)).isoformat()
    assert client.post("/api/crops", json=new_crop_payload(sowing_date=future)).status_code == 422


def test_update_crop_keeps_id(client):
    crop_id = client.post("/api/crops", json=new_crop_payload()).json()["crop_id"]
    resp = client.put(f"/api/crops/{crop_id}", json=new_crop_payload(stage="flowering", farmer_name="Asha Devi"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["crop_id"] == crop_id
    assert body["stage"] == "flowering"
    assert body["farmer_name"] == "Asha Devi"


def test_update_unknown_crop_is_404(client):
    assert client.put("/api/crops/nope", json=new_crop_payload()).status_code == 404


def test_data_survives_restart(db_file):
    """Two separate app starts on the same file = a server restart."""
    with TestClient(app) as first:
        crop_id = first.post("/api/crops", json=new_crop_payload()).json()["crop_id"]
    with TestClient(app) as second:
        assert second.get(f"/api/crops/{crop_id}").status_code == 200
        # The demo seed must not be duplicated on the second start.
        assert len(second.get(f"/api/crops/{DEMO_CROP}/history").json()) == 1


# ----- analysis (F1–F4) -----------------------------------------------------

def test_analyze_saves_to_history(client):
    assert len(client.get(f"/api/crops/{DEMO_CROP}/history").json()) == 1  # seeded
    resp = client.post(f"/api/crops/{DEMO_CROP}/analyze", files={"image": ("leaf.png", TINY_PNG, "image/png")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_demo"] is True
    assert body["risk"]["is_estimate"] is True
    history = client.get(f"/api/crops/{DEMO_CROP}/history").json()
    assert len(history) == 2
    assert history[0]["analysis_id"] == body["analysis_id"]  # newest first


def test_new_crop_has_empty_history(client):
    crop_id = client.post("/api/crops", json=new_crop_payload()).json()["crop_id"]
    assert client.get(f"/api/crops/{crop_id}/history").json() == []


@pytest.mark.parametrize("filename,content,ctype,expected", [
    ("notes.txt", b"hello", "text/plain", 415),
    ("empty.png", b"", "image/png", 400),
])
def test_analyze_rejects_bad_uploads(client, filename, content, ctype, expected):
    resp = client.post(f"/api/crops/{DEMO_CROP}/analyze", files={"image": (filename, content, ctype)})
    assert resp.status_code == expected


# ----- loans (F5, mock) -----------------------------------------------------

def test_demo_loan_is_mock_with_missing_documents(client):
    resp = client.get(f"/api/crops/{DEMO_CROP}/loan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_source"] == "mock"
    assert body["loan"]["outstanding_amount_inr"] == 48000
    assert sorted(body["missing_document_codes"]) == ["land_record", "passport_photo"]


def test_new_farmer_has_no_loan(client):
    crop_id = client.post("/api/crops", json=new_crop_payload()).json()["crop_id"]
    resp = client.get(f"/api/crops/{crop_id}/loan")
    assert resp.status_code == 404
    assert "No loan records" in resp.json()["detail"]


# ----- chat (F7, placeholder) -----------------------------------------------

@pytest.mark.parametrize("message,lang,expected_snippet,fallback", [
    ("लोन के लिए कौन से कागज़ बाकी हैं?", "hi", "ज़मीन के रिकॉर्ड", False),
    ("Why should I inspect nearby plants?", "en", "not a confirmed diagnosis", False),
    ("Which pesticide should I spray and how much?", "en", "can't recommend", False),
    ("hello", "hi", "डेमो मोड", True),
])
def test_chat_placeholder(client, message, lang, expected_snippet, fallback):
    resp = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": message, "lang": lang})
    assert resp.status_code == 200
    body = resp.json()
    assert expected_snippet in body["reply"]
    assert body["is_fallback"] is fallback


def test_chat_for_unknown_crop_is_404(client):
    resp = client.post("/api/chat", json={"crop_id": "nope", "message": "hi", "lang": "en"})
    assert resp.status_code == 404
