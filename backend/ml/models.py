"""
Image-model backends behind one interface (accuracy upgrade).

Every backend returns probabilities for OUR 38 classes, in the order of
shared/content/labels.json, whatever order/naming the model itself uses.
That lets the app (and scripts/eval_pipeline.py) swap models freely.

Backends:
  "mobilenetv2-daksh"  original model (torchvision MobileNetV2 .pth, C4)
  "hf:<folder>"        any Hugging Face image-classification model saved
                       under models/ (DINOv2, ConvNeXt, MobileNetV2 …),
                       run with its OWN image processor (resize/normalise
                       exactly as in its training)

Class-name mapping is done by crop + disease words and must be a perfect
one-to-one match, otherwise loading fails loudly — a silent mismatch would
mislabel every prediction.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image

from backend.ml.classifier_labels import ClassInfo, load_labels

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Words that mean the same crop in different label sets.
CROP_ALIASES = {"maize": "corn", "bell": "pepper", "citrus": "orange", "sour": "cherry"}
# Different names for the same disease across label sets.
DISEASE_SYNONYMS = {
    "isariopsis": "blight",        # grape leaf blight is caused by Isariopsis
    "greening": "haunglongbing",   # citrus greening = huanglongbing (PlantVillage spells it "haunglongbing")
    "huanglongbing": "haunglongbing",
}
# Words to ignore when matching disease names.
STOP_WORDS = {"with", "and", "leaf", "the", "of", "including", "two", "spotted", "gray",
              "spot", "black", "measles", "plant", "citrus"}


def _tokens(name: str) -> tuple[str, set[str]]:
    """'Corn_(maize)___Common_rust_' -> ('corn', {'common', 'rust'})."""
    words = [w for w in re.split(r"[^a-z]+", name.lower()) if w]
    words = [DISEASE_SYNONYMS.get(w, CROP_ALIASES.get(w, w)) for w in words]
    crops = {"apple", "blueberry", "cherry", "corn", "grape", "orange", "peach", "pepper", "potato",
             "raspberry", "soybean", "squash", "strawberry", "tomato"}
    crop = next((w for w in words if w in crops), "")
    rest = {w for w in words if w not in crops and w not in STOP_WORDS}
    return crop, rest


def map_labels(model_labels: list[str], ours: tuple[ClassInfo, ...]) -> list[int]:
    """For each model class index, the matching index in OUR labels."""
    our_tokens = [_tokens(c.label) for c in ours]
    mapping = []
    for name in model_labels:
        crop, words = _tokens(name)
        best, best_score = None, -1.0
        for i, (our_crop, our_words) in enumerate(our_tokens):
            if crop != our_crop:
                continue
            if not words and not our_words:
                score = 1.0
            elif "healthy" in words or "healthy" in our_words:
                score = 1.0 if ("healthy" in words) == ("healthy" in our_words) else 0.0
            else:
                score = len(words & our_words) / max(1, len(words | our_words))
            if score > best_score:
                best, best_score = i, score
        if best is None or best_score <= 0:
            raise ValueError(f"Can't map model class {name!r} onto our labels")
        mapping.append(best)
    if sorted(mapping) != list(range(len(ours))):
        raise ValueError(f"Label mapping is not one-to-one: {mapping}")
    return mapping


class Backend:
    """Common interface: probs(image) -> np.ndarray[38] in OUR label order."""

    name: str

    def probs(self, image: Image.Image) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class DakshMobileNetV2(Backend):
    """The original model (Component 4): torchvision MobileNetV2 weights."""

    name = "mobilenetv2-daksh"

    def __init__(self, weights: Path):
        import torch
        from torch import nn
        from torchvision import models, transforms

        model = models.mobilenet_v2(weights=None)
        model.classifier[1] = nn.Sequential(nn.Dropout(0.2), nn.Linear(model.last_channel, 38))
        state = torch.load(weights, map_location="cpu", weights_only=True)
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        model.load_state_dict(state, strict=True)
        self._model = model.eval()
        self._torch = torch
        self._tf = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        # Its class order is already ours (alphabetical PlantVillage).

    def probs(self, image: Image.Image) -> np.ndarray:
        with self._torch.inference_mode():
            out = self._model(self._tf(image).unsqueeze(0))
            return self._torch.softmax(out, 1)[0].numpy()


class DakshOnnx(Backend):
    """The same Daksh model exported to ONNX (scripts/export_onnx.py).

    Runs with onnxruntime (~15 MB) instead of PyTorch (~770 MB), so the backend
    fits small free servers (Render, 512 MB). Preprocessing mirrors the PyTorch
    version: resize to 224×224, scale to 0–1, ImageNet mean/std.
    """

    name = "mobilenetv2-daksh-onnx"
    MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, onnx_path: Path):
        import os

        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = int(os.getenv("DHARRAKSHAK_THREADS", "2"))
        self._sess = ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])
        self._input = self._sess.get_inputs()[0].name

    def probs(self, image: Image.Image) -> np.ndarray:
        rgb = image.convert("RGB").resize((224, 224), Image.BILINEAR)
        x = (np.asarray(rgb, dtype=np.float32) / 255.0 - self.MEAN) / self.STD
        x = x.transpose(2, 0, 1)[None].astype(np.float32)  # HWC -> 1×CHW
        logits = self._sess.run(None, {self._input: x})[0][0]
        e = np.exp(logits - logits.max())
        return e / e.sum()  # class order is already ours (alphabetical PlantVillage)


class HuggingFaceBackend(Backend):
    """Any transformers image-classification model saved in a local folder."""

    def __init__(self, folder: Path):
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        self.name = f"hf:{folder.name}"
        self._torch = torch
        self._model = AutoModelForImageClassification.from_pretrained(folder).eval()
        try:
            self._processor = AutoImageProcessor.from_pretrained(folder)
        except (ValueError, OSError):
            # Some repos omit preprocessor_config.json; use the architecture's
            # standard settings (what its base checkpoint was trained with).
            import transformers
            fallback = {"mobilenet_v2": "MobileNetV2ImageProcessor"}  # extend if another repo needs it
            model_type = self._model.config.model_type
            if model_type not in fallback:
                raise
            self._processor = getattr(transformers, fallback[model_type])()
        id2label = self._model.config.id2label
        model_labels = [id2label[i] for i in range(len(id2label))]
        self._order = np.array(map_labels(model_labels, load_labels()))

    def probs(self, image: Image.Image) -> np.ndarray:
        inputs = self._processor(images=image, return_tensors="pt")
        with self._torch.inference_mode():
            logits = self._model(**inputs).logits
            p = self._torch.softmax(logits, 1)[0].numpy()
        ours = np.zeros(len(p), dtype=np.float32)
        ours[self._order] = p  # reorder into OUR label order
        return ours


def load_backend(spec: str) -> Backend:
    """'mobilenetv2-daksh' or 'hf:<folder under models/>'."""
    if spec == "mobilenetv2-daksh":
        return DakshMobileNetV2(REPO_ROOT / "models" / "plant-disease-mobilenetv2" / "mobilenetv2_plant.pth")
    if spec.startswith("hf:"):
        folder = Path(spec[3:])
        if not folder.is_absolute():
            folder = REPO_ROOT / "models" / folder
        return HuggingFaceBackend(folder)
    raise ValueError(f"unknown model spec {spec!r}")
