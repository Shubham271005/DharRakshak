"""
Tests for the REAL image model (Component 4).

Skipped automatically when PyTorch isn't installed or the weights haven't
been downloaded (python scripts/download_model.py), so the rest of the
suite still runs on any laptop.
"""

import io

import pytest

from backend.ml import classifier as clf

torch = pytest.importorskip("torch")
pytestmark = pytest.mark.skipif(not clf.weights_path().exists(), reason="model weights not downloaded")


@pytest.fixture(scope="module")
def model():
    return clf.PlantDiseaseClassifier()


def make_png(color=(60, 140, 60), size=(300, 300)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_weights_match_pinned_checksum():
    assert clf.sha256_of(clf.weights_path()) == clf.WEIGHTS_SHA256


def test_labels_cover_38_classes_with_both_languages():
    labels = clf.load_labels()
    assert len(labels) == 38
    assert all(l.name.en and l.name.hi for l in labels)
    assert sum(1 for l in labels if l.crop == "tomato") == 10


def test_probabilities_are_a_distribution(model):
    probs = model.probabilities(make_png())
    assert len(probs) == 38
    assert abs(sum(probs) - 1.0) < 1e-4


def make_textured_png(size=(300, 300)) -> bytes:
    """Random noise: detailed enough to pass the photo-quality gate."""
    import random
    from PIL import Image

    random.seed(0)
    img = Image.new("RGB", size)
    img.putdata([(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for _ in range(size[0] * size[1])])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_detailed_photo_passes_quality_gate(model):
    from PIL import Image

    assert model.is_poor_photo(Image.open(io.BytesIO(make_textured_png())).convert("RGB")) is False


def test_classify_returns_sorted_top3(model):
    out = model.classify(make_png())
    confs = [p.confidence for p in out.predictions]
    assert len(confs) == 3 and confs == sorted(confs, reverse=True)
    assert out.predictions[0].label == out.top.label


def test_blank_photo_is_marked_uncertain(model):
    # A plain green image is not a leaf; the model alone is overconfident on it.
    out = model.classify(make_png(color=(70, 130, 60), size=(400, 300)))
    assert out.uncertain is True
    assert out.uncertainty_message == clf.POOR_PHOTO_MESSAGE


def test_tiny_and_dark_photos_are_marked_uncertain(model):
    assert model.classify(make_png(size=(40, 40))).uncertain is True
    assert model.classify(make_png(color=(5, 8, 5))).uncertain is True


def test_handles_odd_image_modes(model):
    from PIL import Image

    for mode in ("L", "RGBA", "P"):  # greyscale, transparent PNG, palette
        buf = io.BytesIO()
        Image.new(mode, (64, 64)).save(buf, format="PNG")
        assert len(model.classify(buf.getvalue()).predictions) == 3


def test_garbage_bytes_raise_invalid_image(model):
    with pytest.raises(clf.InvalidImage):
        model.classify(b"definitely not an image")
