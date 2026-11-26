"""
Unit tests for the classifier's registry, ranking and honest-flag logic
(backend/ml/classifier.py), without loading real model weights.

`tests/test_classifier.py` runs the genuine ONNX model and is skipped when the
runtime is absent. This file exercises everything around the model — the
registry, `classify()`'s ranking and uncertainty rules — with a stub backend,
so those rules stay covered on a machine without torch or onnxruntime.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from backend.ml import classifier as clf
from backend.ml.models import map_labels
from shared.contract import SUPPORTED_LANGUAGES


class StubBackend:
    """Returns a fixed probability vector instead of running a model."""

    name = "stub"

    def __init__(self, probs):
        self._probs = np.asarray(probs, dtype=np.float32)
        self.calls = 0

    def probs(self, image):
        self.calls += 1
        return self._probs


@pytest.fixture
def labels():
    return clf.load_labels()


def make_classifier(probs, labels):
    """A PlantDiseaseClassifier wired up without touching the filesystem."""
    instance = clf.PlantDiseaseClassifier.__new__(clf.PlantDiseaseClassifier)
    instance.model_name = "stub-model"
    instance.labels = labels
    instance._crop_of = np.array([c.crop for c in labels])
    instance.backend = StubBackend(probs)
    return instance


def peaked(index: int, peak: float = 0.9, labels=None) -> np.ndarray:
    """A 38-way distribution with `peak` on one class and the rest spread out."""
    labels = labels or clf.load_labels()
    probs = np.full(len(labels), (1 - peak) / (len(labels) - 1), dtype=np.float32)
    probs[index] = peak
    return probs


def png(size=(200, 200), colour=(40, 150, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def noisy_png(size=(200, 200)) -> bytes:
    rng = np.random.default_rng(3)
    image = Image.fromarray(rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


TOMATO_BLIGHT = next(i for i, c in enumerate(clf.load_labels()) if c.label == "Tomato___Early_blight")
TOMATO_HEALTHY = next(i for i, c in enumerate(clf.load_labels()) if c.label == "Tomato___healthy")
POTATO_LATE = next(i for i, c in enumerate(clf.load_labels()) if c.label == "Potato___Late_blight")


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------


def test_the_default_model_is_a_known_entry(monkeypatch):
    monkeypatch.delenv("DHARRAKSHAK_MODEL", raising=False)
    assert clf.selected_model() in clf.MODELS
    assert clf.selected_model() == clf.DEFAULT_MODEL


def test_the_model_can_be_chosen_by_environment(monkeypatch):
    monkeypatch.setenv("DHARRAKSHAK_MODEL", "dinov2-small")
    assert clf.selected_model() == "dinov2-small"


def test_an_unknown_model_name_is_rejected_loudly(monkeypatch):
    monkeypatch.setenv("DHARRAKSHAK_MODEL", "not-a-model")
    with pytest.raises(ValueError, match="not-a-model"):
        clf.selected_model()


def test_every_registry_entry_has_a_field_accuracy_and_licence():
    for name, spec in clf.MODELS.items():
        assert 0 < spec["field_top1"] <= 1, name
        assert spec["license"].strip(), name


def test_the_legacy_model_lives_in_the_repo_folder():
    folder = clf.model_folder("daksh-mobilenetv2")
    assert folder.name == "plant-disease-mobilenetv2"
    assert folder.is_dir()


def test_a_hugging_face_model_folder_is_named_after_its_repo():
    folder = clf.model_folder("dinov2-small")
    assert folder.name == "plant-disease-dinov2-small"


def test_the_legacy_weights_path_prefers_the_committed_onnx_file():
    path = clf.weights_path()
    assert path.exists(), "a fresh clone must be able to run without downloading"
    assert path.suffix == ".onnx"


def test_downloading_the_legacy_model_is_refused_with_a_clear_message():
    with pytest.raises(clf.ModelNotAvailable, match="legacy"):
        clf.download_model("daksh-mobilenetv2")


def test_the_classifier_singleton_is_cached_and_reported(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(clf, "_instance", None)
    monkeypatch.setattr(clf, "PlantDiseaseClassifier", lambda *a, **k: sentinel)
    assert clf.is_loaded() is False
    assert clf.get_classifier() is sentinel
    assert clf.is_loaded() is True
    assert clf.get_classifier() is sentinel          # second call reuses it


# ---------------------------------------------------------------------------
# Display text
# ---------------------------------------------------------------------------


def test_a_disease_is_never_named_as_a_certainty(labels):
    blight = next(c for c in labels if c.label == "Tomato___Early_blight")
    text = clf.display_name(blight)
    assert "possible" in text.en.lower() or "likely" in text.en.lower()
    for lang in SUPPORTED_LANGUAGES:
        assert text.in_lang(lang).strip()


def test_a_healthy_leaf_uses_its_own_wording(labels):
    healthy = next(c for c in labels if c.label == "Tomato___healthy")
    assert clf.display_name(healthy).en != clf.display_name(
        next(c for c in labels if c.label == "Tomato___Early_blight")).en


def test_crop_names_are_localised(labels):
    names = clf.crop_name("tomato")
    for lang in SUPPORTED_LANGUAGES:
        assert names[lang]["crop"].strip()
    assert names["en"]["crop"].lower() == "tomato"


def test_an_unknown_crop_name_falls_back_to_its_key():
    names = clf.crop_name("quinoa")
    assert names["en"]["crop"] == "quinoa"


# ---------------------------------------------------------------------------
# _decode
# ---------------------------------------------------------------------------


def test_decode_rejects_bytes_that_are_not_an_image():
    with pytest.raises(clf.InvalidImage, match="could not be read"):
        clf.PlantDiseaseClassifier._decode(b"just some text")


def test_decode_rejects_a_truncated_image():
    complete = png()
    with pytest.raises(clf.InvalidImage):
        clf.PlantDiseaseClassifier._decode(complete[: len(complete) // 3])


def test_decode_rejects_a_decompression_bomb():
    buffer = io.BytesIO()
    Image.new("RGB", (12000, 12000), (30, 120, 40)).save(buffer, format="PNG", optimize=True)
    payload = buffer.getvalue()
    assert len(payload) < 8 * 1024 * 1024           # it fits the upload limit
    with pytest.raises(clf.InvalidImage, match="too large"):
        clf.PlantDiseaseClassifier._decode(payload)


def test_decode_accepts_a_normal_photo():
    assert clf.PlantDiseaseClassifier._decode(png()).size == (200, 200)


def test_decode_accepts_an_animated_gif(labels):
    frames = [Image.new("P", (60, 60), i) for i in range(2)]
    buffer = io.BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:])
    assert clf.PlantDiseaseClassifier._decode(buffer.getvalue()) is not None


# ---------------------------------------------------------------------------
# classify() — ranking
# ---------------------------------------------------------------------------


def test_the_top_three_are_returned_in_descending_confidence(labels):
    instance = make_classifier(peaked(TOMATO_BLIGHT, 0.7, labels), labels)
    out = instance.classify(noisy_png(), registered_crop="tomato")
    assert len(out.predictions) == clf.TOP_K
    confidences = [p.confidence for p in out.predictions]
    assert confidences == sorted(confidences, reverse=True)
    assert out.predictions[0].label == "Tomato___Early_blight"


def test_probabilities_are_the_models_own_and_are_not_rescaled(labels):
    """Re-scaling within a crop used to make single-class crops report 100%."""
    probs = peaked(TOMATO_BLIGHT, 0.42, labels)
    instance = make_classifier(probs, labels)
    out = instance.classify(noisy_png(), registered_crop="tomato")
    assert out.predictions[0].confidence == pytest.approx(0.42, abs=0.001)


def test_flip_tta_averages_the_image_and_its_mirror(labels):
    instance = make_classifier(peaked(TOMATO_BLIGHT, 0.9, labels), labels)
    instance.classify(noisy_png())
    assert instance.backend.calls == 2          # original + mirror


def test_probabilities_method_returns_all_38(labels):
    instance = make_classifier(peaked(TOMATO_BLIGHT, 0.9, labels), labels)
    values = instance.probabilities(png())
    assert len(values) == len(labels)
    assert sum(values) == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# classify() — honest flags
# ---------------------------------------------------------------------------


def test_a_confident_answer_is_not_flagged_uncertain(labels):
    out = make_classifier(peaked(TOMATO_BLIGHT, 0.9, labels), labels).classify(noisy_png())
    assert out.uncertain is False
    assert out.uncertainty_message is None


def test_a_low_confidence_answer_is_flagged_uncertain(labels):
    out = make_classifier(peaked(TOMATO_BLIGHT, clf.UNCERTAIN_THRESHOLD - 0.01, labels),
                          labels).classify(noisy_png())
    assert out.uncertain is True
    assert out.uncertainty_message is not None


def test_the_confidence_threshold_is_inclusive(labels):
    at = make_classifier(peaked(TOMATO_BLIGHT, clf.UNCERTAIN_THRESHOLD, labels), labels)
    assert at.classify(noisy_png()).uncertain is False


def test_a_blank_photo_is_flagged_even_when_the_model_is_confident(labels):
    out = make_classifier(peaked(TOMATO_BLIGHT, 0.99, labels), labels).classify(
        png(colour=(128, 128, 128)))
    assert out.uncertain is True
    assert out.quality_issues
    assert "photo" in out.uncertainty_message.en.lower()


def test_a_tiny_photo_is_flagged(labels):
    out = make_classifier(peaked(TOMATO_BLIGHT, 0.99, labels), labels).classify(png(size=(30, 30)))
    assert "too_small" in out.quality_issues
    assert out.uncertain is True


def test_a_top_class_from_another_crop_is_a_mismatch(labels):
    out = make_classifier(peaked(POTATO_LATE, 0.9, labels), labels).classify(
        noisy_png(), registered_crop="tomato")
    assert out.crop_mismatch is True
    # …and the prediction is NOT changed to something in the registered crop.
    assert out.predictions[0].label == "Potato___Late_blight"


def test_the_same_crop_is_not_a_mismatch(labels):
    out = make_classifier(peaked(TOMATO_BLIGHT, 0.9, labels), labels).classify(
        noisy_png(), registered_crop="tomato")
    assert out.crop_mismatch is False


def test_without_a_registered_crop_there_is_no_mismatch(labels):
    out = make_classifier(peaked(POTATO_LATE, 0.9, labels), labels).classify(noisy_png())
    assert out.crop_mismatch is False
    assert out.registered_crop_mass is None


def test_the_registered_crop_mass_is_reported(labels):
    out = make_classifier(peaked(TOMATO_BLIGHT, 0.9, labels), labels).classify(
        noisy_png(), registered_crop="tomato")
    assert out.registered_crop_mass is not None
    assert 0.0 <= out.registered_crop_mass <= 1.0


def test_a_healthy_top_class_is_reported_as_healthy(labels):
    out = make_classifier(peaked(TOMATO_HEALTHY, 0.95, labels), labels).classify(noisy_png())
    assert out.top.healthy is True


def test_an_unreadable_photo_raises_invalid_image(labels):
    instance = make_classifier(peaked(TOMATO_BLIGHT, 0.9, labels), labels)
    with pytest.raises(clf.InvalidImage):
        instance.classify(b"nope")


# ---------------------------------------------------------------------------
# Label mapping (backend/ml/models.py) — pure functions, no torch needed
# ---------------------------------------------------------------------------


def test_label_tokens_split_crop_from_disease():
    from backend.ml.models import _tokens

    crop, words = _tokens("Corn_(maize)___Common_rust_")
    assert crop == "corn"
    assert "rust" in words and "common" in words
    assert "maize" not in words          # mapped to corn, then dropped as the crop


def test_label_tokens_recognise_a_healthy_class():
    from backend.ml.models import _tokens

    crop, words = _tokens("Apple___healthy")
    assert crop == "apple"
    assert "healthy" in words


def test_crop_aliases_are_applied():
    from backend.ml.models import _tokens

    assert _tokens("Pepper,_bell___Bacterial_spot")[0] == "pepper"
    assert _tokens("Orange___Haunglongbing_(Citrus_greening)")[0] == "orange"


def test_a_permutation_of_our_own_labels_maps_one_to_one():
    ours = clf.load_labels()
    mapping = map_labels([c.label for c in ours], ours)
    assert sorted(mapping) == list(range(len(ours)))


def test_a_duplicate_label_cannot_map_one_to_one():
    ours = clf.load_labels()
    duplicated = [c.label for c in ours]
    duplicated[1] = duplicated[0]
    with pytest.raises(ValueError, match="not one-to-one|Can't map"):
        map_labels(duplicated, ours)


def test_an_unmappable_label_is_rejected_loudly():
    ours = clf.load_labels()
    with pytest.raises(ValueError, match="Can't map"):
        map_labels(["Banana___Blue_mould"], ours)


def test_a_healthy_name_cannot_map_onto_a_disease():
    ours = clf.load_labels()
    model_labels = [c.label for c in ours]
    model_labels[model_labels.index("Tomato___healthy")] = "Tomato___Early_blight"
    with pytest.raises(ValueError):
        map_labels(model_labels, ours)


def test_loading_an_unknown_backend_spec_is_rejected():
    from backend.ml.models import load_backend

    with pytest.raises(ValueError, match="unknown model spec"):
        load_backend("something-else")
