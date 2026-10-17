"""
Backend API tests (Component 2). Run from the repository root:
    pytest

Each test calls the API exactly like the React app would, and checks both
the happy path and the error cases.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.sample_store import sample

client = TestClient(app)
DEMO_CROP = sample().crop_profile.crop_id

# A real (1×1 pixel) PNG so upload tests send genuine image bytes.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_get_demo_crop():
    resp = client.get(f"/api/crops/{DEMO_CROP}")
    assert resp.status_code == 200
    assert resp.json()["crop_type"] == "tomato"


def test_unknown_crop_is_404():
    assert client.get("/api/crops/does-not-exist").status_code == 404


def test_create_crop_computes_days_since_sowing():
    sown = date.today() - timedelta(days=30)
    resp = client.post("/api/crops", json={
        "farmer_name": "Asha", "crop_type": "potato", "sowing_date": sown.isoformat(),
        "area_acres": 1.2, "location_name": "Karnal", "stage": "vegetative",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["days_since_sowing"] == 30
    assert body["location"]["name"] == "Karnal"
    # The new crop can be fetched again.
    assert client.get(f"/api/crops/{body['crop_id']}").status_code == 200


def test_create_crop_rejects_future_sowing_date():
    resp = client.post("/api/crops", json={
        "farmer_name": "Asha", "crop_type": "tomato",
        "sowing_date": (date.today() + timedelta(days=3)).isoformat(),
        "area_acres": 1, "location_name": "Karnal", "stage": "flowering",
    })
    assert resp.status_code == 422


def test_analyze_returns_demo_result_and_adds_to_history():
    before = len(client.get(f"/api/crops/{DEMO_CROP}/history").json())
    resp = client.post(f"/api/crops/{DEMO_CROP}/analyze", files={"image": ("leaf.png", TINY_PNG, "image/png")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_demo"] is True
    assert body["risk"]["is_estimate"] is True
    history = client.get(f"/api/crops/{DEMO_CROP}/history").json()
    assert len(history) == before + 1
    assert history[0]["analysis_id"] == body["analysis_id"]  # newest first


@pytest.mark.parametrize("filename,content,ctype,expected", [
    ("notes.txt", b"hello", "text/plain", 415),
    ("empty.png", b"", "image/png", 400),
])
def test_analyze_rejects_bad_uploads(filename, content, ctype, expected):
    resp = client.post(f"/api/crops/{DEMO_CROP}/analyze", files={"image": (filename, content, ctype)})
    assert resp.status_code == expected


def test_loan_is_always_mock():
    resp = client.get(f"/api/crops/{DEMO_CROP}/loan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_source"] == "mock"
    assert sorted(body["missing_document_codes"]) == ["land_record", "passport_photo"]


@pytest.mark.parametrize("message,lang,expected_snippet,fallback", [
    ("लोन के लिए कौन से कागज़ बाकी हैं?", "hi", "ज़मीन के रिकॉर्ड", False),
    ("Why should I inspect nearby plants?", "en", "not a confirmed diagnosis", False),
    ("Which pesticide should I spray and how much?", "en", "can't recommend", False),
    ("hello", "hi", "डेमो मोड", True),
])
def test_chat_stub(message, lang, expected_snippet, fallback):
    resp = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": message, "lang": lang})
    assert resp.status_code == 200
    body = resp.json()
    assert expected_snippet in body["reply"]
    assert body["is_fallback"] is fallback


def test_chat_for_unknown_crop_is_404():
    resp = client.post("/api/chat", json={"crop_id": "nope", "message": "hi", "lang": "en"})
    assert resp.status_code == 404
