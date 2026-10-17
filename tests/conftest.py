"""
Shared test fixtures.

- Every test gets its own empty SQLite file in a temp folder, so tests never
  touch the real data/dharrakshak.sqlite3 and never affect each other.
- API tests use a FAKE image classifier (fast, deterministic, no 9 MB model
  needed). The real model is tested separately in test_classifier.py.
- Open-Meteo (weather + geocoding) is replaced by recorded responses for
  EVERY test (autouse), so tests never use the network. Set
  `fake_open_meteo.down = True` in a test to simulate an outage.
- Groq (chatbot LLM + Whisper) is replaced by `fake_llm` for EVERY test, so
  tests never use the network or the real API key. By default it is "down"
  (exercises the fallback); set `fake_llm.reply = "..."` to make it answer.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ml import classifier as clf
from backend.services import geocoding, llm, weather
from shared.contract import Prediction

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class FakeClassifier:
    """Stands in for PlantDiseaseClassifier. Returns `top_index` with
    `confidence`, and rejects anything that isn't a PNG as an invalid image."""

    def __init__(self, top_index: int = 29, confidence: float = 0.81):  # 29 = Tomato___Early_blight
        self.labels = clf.load_labels()
        self.top_index = top_index
        self.confidence = confidence

    def classify(self, image_bytes: bytes) -> clf.ClassifierOutput:
        if not image_bytes.startswith(PNG_SIGNATURE):
            raise clf.InvalidImage("The file could not be read as an image.")
        indices = [self.top_index, (self.top_index + 1) % 38, (self.top_index + 2) % 38]
        # Top-3 of a 38-way softmax: always descending, need not sum to 1.
        confs = [self.confidence, self.confidence * 0.2, self.confidence * 0.1]
        top = self.labels[self.top_index]
        uncertain = self.confidence < clf.UNCERTAIN_THRESHOLD
        return clf.ClassifierOutput(
            predictions=[
                Prediction(label=self.labels[i].label, display_name=clf.display_name(self.labels[i]), confidence=c)
                for i, c in zip(indices, confs)
            ],
            top=top,
            uncertain=uncertain,
            uncertainty_message=clf.UNCERTAIN_MESSAGE if uncertain else None,
        )


@pytest.fixture
def db_file(tmp_path, monkeypatch):
    """Point the backend at a fresh temporary database file."""
    path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("DHARRAKSHAK_DB", str(path))
    monkeypatch.setenv("DHARRAKSHAK_PRELOAD_MODEL", "0")  # don't load the real model in API tests
    return path


@pytest.fixture
def fake_model(monkeypatch):
    """Replace the real classifier with a FakeClassifier. Tests can tweak it:
    fake_model.top_index = 20; fake_model.confidence = 0.3"""
    fake = FakeClassifier()
    monkeypatch.setattr(clf, "get_classifier", lambda: fake)
    return fake


@pytest.fixture
def client(db_file, fake_model):
    """A test client. `with` runs the app's startup (create tables + seed demo)."""
    with TestClient(app) as test_client:
        yield test_client


# A real Open-Meteo response shape (Sonipat, 18 Oct 2026): 3 past days,
# today, 3 forecast days.
OPEN_METEO_DAILY = {
    "timezone": "Asia/Kolkata",
    "daily": {
        "time": ["2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21"],
        "precipitation_sum": [27.0, 0.7, 0.0, 0.0, 2.5, 4.0, 0.0],
        "relative_humidity_2m_mean": [87, 81, 73, 66, 65, 68, 69],
        "temperature_2m_mean": [22.3, 23.1, 24.4, 23.3, 23.1, 23.5, 24.1],
        "precipitation_probability_max": [100, 31, 0, 0, 40, 65, 10],
    },
}

KNOWN_PLACES = {
    "karnal": [{"name": "Karnāl", "admin1": "Haryana", "admin2": "Karnal", "latitude": 29.69, "longitude": 76.98, "population": 286827}],
    "sonipat": [{"name": "Sonīpat", "admin1": "Haryana", "admin2": "Sonipat", "latitude": 28.99, "longitude": 77.02, "population": 289333}],
    # Two places with the same name in different states, to test hint matching.
    "aurangabad": [
        {"name": "Aurangabad", "admin1": "Maharashtra", "latitude": 19.88, "longitude": 75.34, "population": 1175116},
        {"name": "Aurangabad", "admin1": "Bihar", "latitude": 24.75, "longitude": 84.37, "population": 102244},
    ],
}


class FakeOpenMeteo:
    """Records calls and serves canned data instead of the real APIs."""

    def __init__(self):
        self.down = False
        self.weather_calls = 0
        self.geocode_calls = []

    def fetch_daily(self, latitude, longitude):
        self.weather_calls += 1
        if self.down:
            raise weather.WeatherUnavailable("simulated outage")
        return OPEN_METEO_DAILY

    def search(self, name, count=5):
        self.geocode_calls.append(name)
        if self.down:
            raise geocoding.GeocodingUnavailable("simulated outage")
        return KNOWN_PLACES.get(geocoding._normalise(name), [])


@pytest.fixture(autouse=True)
def fake_open_meteo(monkeypatch):
    fake = FakeOpenMeteo()
    monkeypatch.setattr(weather, "fetch_daily", fake.fetch_daily)
    monkeypatch.setattr(geocoding, "search", fake.search)
    weather.clear_cache()
    geocoding._geocode_cached.cache_clear()
    yield fake
    weather.clear_cache()
    geocoding._geocode_cached.cache_clear()


class FakeLLM:
    """Stands in for backend.services.llm. Records what was sent."""

    def __init__(self):
        self.reply = None           # None = unavailable (fallback path)
        self.transcript = None      # None = speech-to-text unavailable
        self.messages = None
        self.stt_calls = []

    def chat_complete(self, messages, max_tokens=500, temperature=0.3):
        self.messages = messages
        if self.reply is None:
            raise llm.LLMUnavailable("fake: no LLM")
        return self.reply, "fake-model"

    def transcribe(self, audio, filename, content_type, lang=None):
        self.stt_calls.append((filename, content_type, lang, len(audio)))
        if self.transcript is None:
            raise llm.LLMUnavailable("fake: no STT")
        return self.transcript


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(llm, "chat_complete", fake.chat_complete)
    monkeypatch.setattr(llm, "transcribe", fake.transcribe)
    return fake
