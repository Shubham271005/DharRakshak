"""
Regression tests written during the backend engineering audit.

Every test here asserts behaviour the API SHOULD have. Several of them failed
when first written; the fix for each is recorded in docs/AUDIT.md and in the
docstring of the test itself.

Run: scripts\py.cmd -m pytest tests/test_audit_regressions.py -q
"""

import sqlite3

from backend import db

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


# ---------------------------------------------------------------------------
# Upload Content-Type parsing
# ---------------------------------------------------------------------------

def test_analyze_accepts_a_content_type_with_parameters(client):
    """A real browser may append parameters to the Content-Type.

    `transcribe()` already splits on ';' before comparing, but `analyze()`
    compared the raw header, so `image/png; charset=binary` was rejected as
    "not a JPEG, PNG or WebP" even though it is a PNG. Two endpoints, two
    different answers to the same header shape.
    """
    resp = client.post(
        f"/api/crops/{DEMO_CROP}/analyze",
        files={"image": ("leaf.png", TINY_PNG, "image/png; charset=binary")},
    )
    assert resp.status_code == 200, resp.text


def test_transcribe_accepts_a_content_type_with_parameters(client, fake_llm):
    """The counterpart that already worked — kept so the two cannot drift again."""
    fake_llm.transcript = "mere tamatar me dhabbe hain"
    resp = client.post(
        "/api/voice/transcribe",
        files={"audio": ("q.webm", b"\x00" * 64, "audio/webm;codecs=opus")},
        data={"lang": "hi"},
    )
    assert resp.status_code == 200, resp.text


def test_analyze_still_rejects_a_genuinely_wrong_type(client):
    """Widening the parse must not open the door to arbitrary uploads."""
    resp = client.post(
        f"/api/crops/{DEMO_CROP}/analyze",
        files={"image": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415


# ---------------------------------------------------------------------------
# Chat validation
# ---------------------------------------------------------------------------

def test_chat_rejects_a_whitespace_only_message(client, fake_llm):
    """`min_length=1` does not stop "   ".

    An empty message costs a Groq call and produces a reply to nothing. The
    existing test only covers "", not whitespace.
    """
    fake_llm.reply = "should never be called"
    resp = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": "   \t \n ", "lang": "en"})
    assert resp.status_code == 422
    assert fake_llm.messages is None, "a blank question must not reach the LLM"


def test_chat_still_accepts_a_normal_question(client, fake_llm):
    fake_llm.reply = "ok"
    resp = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": "keeda hai?", "lang": "hi"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Unbounded free-text fields
# ---------------------------------------------------------------------------

def test_location_name_is_length_bounded(client):
    """`location_name` has no max_length while `farmer_name` is capped at 100.

    An unbounded string is stored verbatim and also forwarded as a geocoding
    query parameter. GPS coordinates are sent so the geocoder is not involved:
    this test is about the length limit, not about place lookup.
    """
    resp = client.post(
        "/api/crops",
        json=new_crop_payload(location_name="K" * 5000, latitude=28.99, longitude=77.02),
    )
    assert resp.status_code == 422


def test_variety_is_length_bounded(client):
    resp = client.post(
        "/api/crops",
        json=new_crop_payload(variety="V" * 5000, latitude=28.99, longitude=77.02),
    )
    assert resp.status_code == 422


def test_a_long_but_sensible_location_still_works(client):
    """The new limit must not reject a real, descriptive Indian address."""
    resp = client.post(
        "/api/crops",
        json=new_crop_payload(
            location_name="Village Rampur, Tehsil Gohana, District Sonipat, Haryana",
            latitude=28.99,
            longitude=77.02,
        ),
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Data integrity: one corrupt row must not take out a whole screen
# ---------------------------------------------------------------------------

def test_a_corrupt_sowing_date_does_not_break_the_crop_list(client):
    """A single unreadable `sowing_date` used to 500 the app's start screen.

    `date.fromisoformat` was called with no guard, and `GET /api/crops` builds
    an item for every crop, so one bad row broke the list for all of them.
    """
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO crops (crop_id, farmer_id, crop_type, sowing_date, area_acres,
                                  location_name, latitude, longitude, stage)
               VALUES ('crop-bad-date', 'farmer-demo-001', 'tomato', 'not-a-date', 1.0,
                       'Karnal', 29.69, 76.98, 'vegetative')"""
        )

    resp = client.get("/api/crops")
    assert resp.status_code == 200
    ids = [item["profile"]["crop_id"] for item in resp.json()]
    assert DEMO_CROP in ids, "the healthy crop must still be listed"
    assert "crop-bad-date" not in ids, "an unreadable row is skipped, not served"


def test_a_corrupt_date_does_not_break_a_single_crop_read(client):
    """GET /api/crops/{id} for the bad row is a 404, not a 500."""
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO crops (crop_id, farmer_id, crop_type, sowing_date, area_acres,
                                  location_name, latitude, longitude, stage)
               VALUES ('crop-bad-date2', 'farmer-demo-001', 'tomato', '', 1.0,
                       'Karnal', 29.69, 76.98, 'vegetative')"""
        )
    resp = client.get("/api/crops/crop-bad-date2")
    assert resp.status_code == 404
