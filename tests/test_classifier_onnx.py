"""
End-to-end test of the model the app actually ships.

`tests/test_classifier.py` is skipped unless PyTorch AND transformers are
installed, but the committed model is `mobilenetv2_plant.onnx` and
`classifier.py` selects the ONNX backend whenever that file exists — i.e. by
default, on every machine and in production. So before this file the default
inference path had no test that runs on a normal install.

Needs only `onnxruntime`, which requirements.txt now lists. Skipped cleanly
when it or the model file is absent, so it never blocks a torch-only setup.

Run: scripts\py.cmd -m pytest tests/test_classifier_onnx.py -q
"""

import io

import pytest

from backend.ml import classifier as clf

onnxruntime = pytest.importorskip("onnxruntime")

MODEL_DIR = clf.REPO_ROOT / "models" / "plant-disease-mobilenetv2"
pytestmark = pytest.mark.skipif(
    not (MODEL_DIR / "mobilenetv2_plant.onnx").exists(),
    reason="the committed ONNX model is not present",
)


@pytest.fixture(scope="module")
def model():
    """The real classifier, built from the committed weights."""
    clf._instance = None  # bypass the process-wide singleton
    instance = clf.PlantDiseaseClassifier(model_name="daksh-mobilenetv2")
    yield instance
    clf._instance = None


def leaf_png(seed: int = 0, size: int = 300) -> bytes:
    """A deterministic, textured green image — enough to exercise inference."""
    from PIL import Image

    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            # A couple of gradients plus per-pixel noise: not a flat colour, so
            # the quality checks do not flag it as blank.
            noise = (x * 7 + y * 13 + seed * 31) % 40
            pixels[x, y] = (
                40 + noise,
                110 + (x * 255 // size + noise) % 80,
                30 + (y * 255 // size + noise) % 50,
            )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_the_shipped_model_loads_with_onnxruntime(model):
    assert model.backend.name == "mobilenetv2-daksh-onnx"
    assert len(model.labels) == 38


def test_probabilities_are_a_full_distribution(model):
    probs = model.probabilities(leaf_png())
    assert len(probs) == 38
    assert all(0.0 <= p <= 1.0 for p in probs)
    assert abs(sum(probs) - 1.0) < 1e-3


def test_classify_returns_three_ranked_predictions(model):
    out = model.classify(leaf_png(), registered_crop="tomato")
    assert len(out.predictions) == 3
    confidences = [p.confidence for p in out.predictions]
    assert confidences == sorted(confidences, reverse=True)
    assert out.top.label == out.predictions[0].label
    # Every prediction is one of the model's own classes, not an invented name.
    assert all(p.label in {label.label for label in model.labels} for p in out.predictions)


def test_the_same_photo_gives_the_same_answer(model):
    """Inference must be deterministic: no dropout, no sampling."""
    first = model.classify(leaf_png(seed=3))
    second = model.classify(leaf_png(seed=3))
    assert [p.label for p in first.predictions] == [p.label for p in second.predictions]


def test_junk_bytes_are_rejected_not_scored(model):
    with pytest.raises(clf.InvalidImage):
        model.classify(b"this is not an image")
