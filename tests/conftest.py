"""
Shared test fixtures.

- Every test gets its own empty SQLite file in a temp folder, so tests never
  touch the real data/dharrakshak.sqlite3 and never affect each other.
- API tests use a FAKE image classifier (fast, deterministic, no 9 MB model
  needed). The real model is tested separately in test_classifier.py.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ml import classifier as clf
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
