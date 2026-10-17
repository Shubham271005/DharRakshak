"""
Backend API tests (Components 2–6). Run from the repository root:
    pytest

Each test calls the API exactly like the React app would, against a fresh
temporary database (see conftest.py), and checks both happy paths and
error cases.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ml import classifier as clf
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


def test_create_crop_geocodes_location(client):
    body = client.post("/api/crops", json=new_crop_payload(location_name="Karnal")).json()
    assert (body["location"]["latitude"], body["location"]["longitude"]) == (29.69, 76.98)


def test_create_crop_with_gps_skips_lookup(client, fake_open_meteo):
    body = client.post("/api/crops", json=new_crop_payload(location_name="My farm", latitude=26.85, longitude=80.95)).json()
    assert body["location"]["latitude"] == 26.85
    assert fake_open_meteo.geocode_calls == []


def test_only_one_coordinate_is_rejected(client):
    assert client.post("/api/crops", json=new_crop_payload(latitude=26.85)).status_code == 422


def test_unknown_location_is_422_with_help(client):
    resp = client.post("/api/crops", json=new_crop_payload(location_name="Atlantis"))
    assert resp.status_code == 422
    assert "nearest town or district" in resp.json()["detail"]


def test_geocoding_outage_is_503(client, fake_open_meteo):
    fake_open_meteo.down = True
    resp = client.post("/api/crops", json=new_crop_payload())
    assert resp.status_code == 503
    assert "allow location access" in resp.json()["detail"]


def test_update_same_location_does_not_look_up_again(client, fake_open_meteo):
    crop_id = client.post("/api/crops", json=new_crop_payload()).json()["crop_id"]
    calls = len(fake_open_meteo.geocode_calls)
    client.put(f"/api/crops/{crop_id}", json=new_crop_payload(stage="flowering"))
    assert len(fake_open_meteo.geocode_calls) == calls


def test_update_new_location_moves_coordinates(client):
    crop_id = client.post("/api/crops", json=new_crop_payload()).json()["crop_id"]
    body = client.put(f"/api/crops/{crop_id}", json=new_crop_payload(location_name="Sonipat, Haryana")).json()
    assert body["location"]["latitude"] == 28.99


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


# ----- weather (C5) ------------------------------------------------------------

def test_weather_endpoint_returns_real_source(client):
    resp = client.get(f"/api/crops/{DEMO_CROP}/weather")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "open_meteo"
    assert body["rain_last_3_days_mm"] == 27.7


def test_weather_endpoint_outage_is_503(client, fake_open_meteo):
    fake_open_meteo.down = True
    assert client.get(f"/api/crops/{DEMO_CROP}/weather").status_code == 503


# ----- analysis (F1–F4) -----------------------------------------------------

def upload(client, crop_id=DEMO_CROP, content=TINY_PNG, filename="leaf.png", ctype="image/png"):
    return client.post(f"/api/crops/{crop_id}/analyze", files={"image": (filename, content, ctype)})


def test_analyze_uses_model_predictions(client):
    body = upload(client).json()
    top = body["predictions"][0]
    assert top["label"] == "Tomato___Early_blight"          # from the (fake) model
    assert top["display_name"]["en"] == "Possible tomato early blight"
    assert top["display_name"]["hi"].startswith("संभावित")
    assert body["uncertain"] is False
    assert body["crop_mismatch"] is False
    # Everything is real since Component 6, so the DEMO tag is gone.
    assert body["is_demo"] is False
    assert body["risk"]["is_estimate"] is True
    # Fake model: tomato early blight 81%; recorded weather: 27.7 mm recent rain,
    # rain expected; demo crop is flowering → elevated.
    assert body["risk"]["level"] == "elevated"
    assert [c["card_id"] for c in body["action_cards"]] == ["inspect_nearby", "check_local_guidance", "keep_leaves_dry"]
    assert body["explanation"]["summary"]["en"].startswith("Inspection priority is elevated")


def test_analysis_includes_real_weather(client):
    body = upload(client).json()
    assert body["weather"]["source"] == "open_meteo"
    assert body["weather"]["rain_next_3_days_mm"] == 6.5


def test_analysis_still_works_when_weather_is_down(client, fake_open_meteo):
    fake_open_meteo.down = True
    resp = upload(client)
    assert resp.status_code == 200
    assert resp.json()["weather"] is None  # honest: no made-up weather


def test_low_confidence_is_uncertain(client, fake_model):
    fake_model.confidence = 0.30
    body = upload(client).json()
    assert body["uncertain"] is True
    assert "retake" in body["uncertainty_message"]["en"]
    assert body["crop_mismatch"] is False  # not flagged when already uncertain


def test_photo_of_other_crop_is_flagged(client, fake_model):
    fake_model.top_index = 21  # Potato___Late_blight, but the demo crop is tomato
    body = upload(client).json()
    assert body["crop_mismatch"] is True


def test_healthy_leaf_wording(client, fake_model):
    fake_model.top_index = 37  # Tomato___healthy
    body = upload(client).json()
    assert body["predictions"][0]["display_name"]["en"] == "Likely healthy tomato leaf"


def test_unreadable_image_is_400(client):
    assert upload(client, content=b"not really a jpeg", filename="x.jpg", ctype="image/jpeg").status_code == 400


def test_missing_model_is_503(client, monkeypatch):
    def missing():
        raise clf.ModelNotAvailable("Model weights not found")
    monkeypatch.setattr(clf, "get_classifier", missing)
    assert upload(client).status_code == 503


def test_analyze_saves_to_history(client):
    assert len(client.get(f"/api/crops/{DEMO_CROP}/history").json()) == 1  # seeded
    resp = upload(client)
    assert resp.status_code == 200
    body = resp.json()
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


# ----- chat (F7) --------------------------------------------------------------

@pytest.mark.parametrize("message,lang,expected_snippet", [
    ("लोन के लिए कौन से कागज़ बाकी हैं?", "hi", "ज़मीन के रिकॉर्ड"),
    ("Why should I inspect nearby plants?", "en", "not a confirmed diagnosis"),
    ("Which pesticide should I spray and how much?", "en", "can't recommend"),
    ("hello", "hi", "ऑफ़लाइन"),
])
def test_chat_falls_back_to_saved_answers_when_llm_is_down(client, message, lang, expected_snippet):
    resp = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": message, "lang": lang})
    assert resp.status_code == 200
    body = resp.json()
    assert expected_snippet in body["reply"]
    assert body["is_fallback"] is True  # always marked when the LLM didn't answer


def test_chat_is_grounded_in_farmer_data(client, fake_llm):
    fake_llm.reply = "दो कागज़ बाकी हैं: ज़मीन के रिकॉर्ड की कॉपी और पासपोर्ट साइज़ फोटो।"
    resp = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": "लोन के कागज़?", "lang": "hi"})
    body = resp.json()
    assert body["is_fallback"] is False
    assert body["reply"] == fake_llm.reply
    assert body["used_context"] == ["crop_profile", "analysis", "weather", "loan_summary"]
    system, context = fake_llm.messages[0]["content"], fake_llm.messages[1]["content"]
    assert "Reply in Hindi" in system and "Never name any pesticide" in system
    assert "Land record copy" in context and "Passport-size photo" in context  # missing docs
    assert "sample data, not from a real bank" in context
    assert fake_llm.messages[-1] == {"role": "user", "content": "लोन के कागज़?"}


def test_chat_sends_recent_history(client, fake_llm):
    fake_llm.reply = "Yes."
    history = [{"role": "user", "text": f"q{i}"} if i % 2 == 0 else {"role": "assistant", "text": f"a{i}"} for i in range(12)]
    client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": "and now?", "lang": "en", "history": history})
    sent = [m["content"] for m in fake_llm.messages[2:-1]]
    assert sent == [t["text"] for t in history[-8:]]  # only the last 8 turns


def test_chat_blocks_dose_advice_from_the_model(client, fake_llm):
    fake_llm.reply = "Mix 2 ml per litre of water and apply weekly."
    body = client.post("/api/chat", json={"crop_id": DEMO_CROP, "message": "How much to use?", "lang": "en"}).json()
    assert "2 ml" not in body["reply"]
    assert "Krishi Vigyan Kendra" in body["reply"]


def test_chat_for_new_farmer_says_no_loan(client, fake_llm):
    fake_llm.reply = "OK"
    crop_id = client.post("/api/crops", json=new_crop_payload()).json()["crop_id"]
    body = client.post("/api/chat", json={"crop_id": crop_id, "message": "loan?", "lang": "en"}).json()
    assert body["used_context"] == ["crop_profile"]
    assert "No loan records" in fake_llm.messages[1]["content"]


# ----- voice (F7) -------------------------------------------------------------

def test_voice_transcribe(client, fake_llm):
    fake_llm.transcript = "लोन के लिए कौन से कागज़ बाकी हैं"
    resp = client.post("/api/voice/transcribe", files={"audio": ("q.webm", b"fake-audio", "audio/webm;codecs=opus")}, data={"lang": "hi"})
    assert resp.status_code == 200
    assert resp.json() == {"text": fake_llm.transcript, "lang": "hi"}
    assert fake_llm.stt_calls == [("q.webm", "audio/webm", "hi", 10)]


@pytest.mark.parametrize("files,expected", [
    ({"audio": ("x.txt", b"hello", "text/plain")}, 415),
    ({"audio": ("q.webm", b"", "audio/webm")}, 400),
])
def test_voice_rejects_bad_audio(client, files, expected):
    assert client.post("/api/voice/transcribe", files=files).status_code == expected


def test_voice_unavailable_is_503(client):
    resp = client.post("/api/voice/transcribe", files={"audio": ("q.webm", b"abc", "audio/webm")})
    assert resp.status_code == 503
    assert "type your question" in resp.json()["detail"]


def test_voice_silence_is_422(client, fake_llm):
    fake_llm.transcript = ""
    assert client.post("/api/voice/transcribe", files={"audio": ("q.webm", b"abc", "audio/webm")}).status_code == 422


def test_chat_for_unknown_crop_is_404(client):
    resp = client.post("/api/chat", json={"crop_id": "nope", "message": "hi", "lang": "en"})
    assert resp.status_code == 404


# ----- finance (C7) ----------------------------------------------------------

def test_loan_schemes_come_from_content(client):
    codes = [s["code"] for s in client.get(f"/api/crops/{DEMO_CROP}/loan").json()["schemes"]]
    assert codes == ["miss", "pmfby", "pm_kisan"]


def test_ticking_a_document_updates_missing_list(client):
    url = f"/api/crops/{DEMO_CROP}/loan/documents/land_record"
    body = client.put(url, json={"submitted": True}).json()
    assert body["missing_document_codes"] == ["passport_photo"]
    assert next(d for d in body["documents"] if d["code"] == "land_record")["submitted"] is True
    # Persisted: a fresh read agrees, and unticking brings it back.
    assert client.get(f"/api/crops/{DEMO_CROP}/loan").json()["missing_document_codes"] == ["passport_photo"]
    body = client.put(url, json={"submitted": False}).json()
    assert sorted(body["missing_document_codes"]) == ["land_record", "passport_photo"]


def test_unknown_document_is_404(client):
    resp = client.put(f"/api/crops/{DEMO_CROP}/loan/documents/nope", json={"submitted": True})
    assert resp.status_code == 404


def test_document_update_for_farmer_without_loan_is_404(client):
    crop_id = client.post("/api/crops", json=new_crop_payload()).json()["crop_id"]
    assert client.put(f"/api/crops/{crop_id}/loan/documents/land_record", json={"submitted": True}).status_code == 404
