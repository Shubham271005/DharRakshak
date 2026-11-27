"""
Plant-disease image classifier (feature F1) — upgraded for real-world photos.

WHY THIS CHANGED: on 89 real field photos (PlantDoc), the original model
(Daksh159 MobileNetV2) got only 12% top-1 — it ranked all 38 classes and
often answered with a different crop entirely. Measured with
scripts/eval_pipeline.py (details: docs/MODEL_CARD.md), the setup below
scores far better while still ranking all 38 classes: 29% top-1 / 43% top-3
with linkanjarad, and 12% / 26% with the default committed model. (Scoring
restricted to the registered crop reaches 60% / 85%, but the app deliberately
does NOT do that — see point 4, and the honesty note in docs/MODEL_CARD.md.)

  1. Model: linkanjarad MobileNetV2 (best real-world accuracy of the 4
     models tested; same size/speed class). Choose another with
     DHARRAKSHAK_MODEL in .env — see MODELS below.
  2. Preprocessing (backend/ml/preprocess.py): EXIF rotation + quality
     checks (blur, dark, blank, tiny) + leaf crop (which falls back to the
     full frame when no plausible leaf is found). CLAHE / white balance /
     denoise exist but are OFF: they did not help real-world accuracy.
  3. Flip test-time augmentation: average the photo and its mirror image.
  4. Ranking: all 38 classes are ranked and the top 3 are shown with the
     model's real probabilities. The registered crop is used only to WARN
     (crop_mismatch) when the winning class belongs to another crop — it does
     not filter or re-rank, because filtering hid genuine cross-crop errors.
  5. Honest confidence:
       - uncertain if the top-1 probability is < 0.50
         (UNCERTAIN_THRESHOLD), or the photo is blurry/dark/blank/tiny;
       - "may not be your crop" warning when the top class is another crop.
     `registered_crop_mass` is still reported for the evaluation scripts, but
     no live decision reads it.
"""

from __future__ import annotations

import io
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from backend.engines.content import load as load_content
from backend.engines.content import message, per_language
from backend.ml.classifier_labels import ClassInfo, load_labels  # noqa: F401  (re-exported)
from backend.ml.preprocess import DEFAULT_STEPS, preprocess
from shared.contract import LocalizedText, Prediction

log = logging.getLogger("dharrakshak.classifier")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Available models (pinned revisions). Field accuracy = top-1 on 89 PlantDoc
# field photos with crop-aware ranking (scripts/eval_pipeline.py).
# ---------------------------------------------------------------------------
MODELS: dict[str, dict] = {
    "linkanjarad-mobilenetv2": {
        "repo": "linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification",
        "revision": "c1861579a670fb6232258805b801cd4137cb7176",
        "files": ["config.json", "pytorch_model.bin"],
        "license": "not stated by the author ('other') — fine for a hackathon demo, check before commercial use",
        "field_top1": 0.62,
    },
    "dinov2-small": {
        "repo": "rodynaemad/plant-disease-dinov2-small",
        "revision": "06ebf5e308e100fd000d738c42b059ebb5f58a16",
        "files": ["config.json", "preprocessor_config.json", "model.safetensors"],
        "license": "CC-BY-SA-4.0",
        "field_top1": 0.52,
    },
    "convnext-tiny": {
        "repo": "JohnSupertramp2026/convnext-tiny-plantvillage",
        "revision": "3cc0b34afbf5c0c1ddf069bcccca03b407573dc2",
        "files": ["config.json", "preprocessor_config.json", "model.safetensors"],
        "license": "Apache-2.0",
        "field_top1": 0.49,
    },
    "daksh-mobilenetv2": {  # the original Component 4 model, kept for comparison
        "legacy": True,
        "license": "Apache-2.0",
        "field_top1": 0.45,
    },
}
DEFAULT_MODEL = "daksh-mobilenetv2"  # the team's chosen model (Daksh159/plant-disease-mobilenetv2)

TOP_K = 3
USE_FLIP_TTA = True
# A photo whose top-1 probability is below this is reported as uncertain.
# (Measured on 89 PlantDoc field photos — see docs/MODEL_CARD.md.)
UNCERTAIN_THRESHOLD = 0.50
# A small file can declare an enormous canvas — a "decompression bomb":
# 445 KB of PNG becomes 432 MB of pixel data. Capped well above any phone
# photo (a 48 MP camera is the current ceiling) and well below the size that
# would exhaust a 512 MB server. Checked on the declared size, BEFORE the
# pixels are decoded.
MAX_IMAGE_PIXELS = 40_000_000


class ModelNotAvailable(RuntimeError):
    """Model files are missing. The API returns 503."""


class InvalidImage(ValueError):
    """The uploaded bytes are not a readable image. The API returns 400."""


def selected_model() -> str:
    name = os.getenv("DHARRAKSHAK_MODEL", DEFAULT_MODEL)
    if name not in MODELS:
        raise ValueError(f"DHARRAKSHAK_MODEL={name!r} is not one of {list(MODELS)}")
    return name


def model_folder(name: str) -> Path:
    if MODELS[name].get("legacy"):
        return REPO_ROOT / "models" / "plant-disease-mobilenetv2"
    return REPO_ROOT / "models" / MODELS[name]["repo"].split("/")[1]


def weights_path() -> Path:
    """Main weights file of the selected model (used by tests and scripts)."""
    name = selected_model()
    if MODELS[name].get("legacy"):
        onnx = model_folder(name) / "mobilenetv2_plant.onnx"
        return onnx if onnx.exists() else model_folder(name) / "mobilenetv2_plant.pth"
    files = [f for f in MODELS[name]["files"] if f.endswith((".bin", ".safetensors"))]
    return model_folder(name) / files[0]


def download_model(name: str | None = None) -> Path:
    """Download the selected model at its pinned revision (resumable)."""
    name = name or selected_model()
    spec = MODELS[name]
    if spec.get("legacy"):
        raise ModelNotAvailable("The legacy model is downloaded by older versions of scripts/download_model.py.")
    from huggingface_hub import snapshot_download

    folder = model_folder(name)
    snapshot_download(spec["repo"], revision=spec["revision"], allow_patterns=spec["files"], local_dir=folder)
    return folder


def display_name(info: ClassInfo) -> LocalizedText:
    """Farmer-facing wording. Never claims certainty: 'Possible …' / 'Likely …'."""
    key = "prediction_likely_healthy" if info.healthy else "prediction_possible"
    return message(key, per_language(lambda lang: {"name": info.name.in_lang(lang)}))


def crop_name(crop: str) -> dict[str, dict[str, str]]:
    """{lang: {"crop": name}} for message templates."""
    entry = load_content("crops")["crops"].get(crop)
    names = LocalizedText(**entry) if entry else None
    return per_language(lambda lang: {"crop": names.in_lang(lang) if names else crop})


@dataclass(frozen=True)
class ClassifierOutput:
    predictions: list[Prediction]        # top-3 across ALL 38 classes, highest first
    top: ClassInfo                       # details of the top-1 class
    uncertain: bool
    uncertainty_message: LocalizedText | None
    crop_mismatch: bool = False          # the winning class belongs to a different crop
    registered_crop_mass: float | None = None
    quality_issues: tuple[str, ...] = ()


POOR_PHOTO_MESSAGE = message("poor_photo")
UNCERTAIN_MESSAGE = message("uncertain_photo")


class PlantDiseaseClassifier:
    """Loads the selected model once and classifies leaf photos. Thread-safe."""

    def __init__(self, model_name: str | None = None) -> None:
        from backend.ml.models import DakshMobileNetV2, DakshOnnx, HuggingFaceBackend

        self.model_name = model_name or selected_model()
        folder = model_folder(self.model_name)
        legacy = MODELS[self.model_name].get("legacy")
        main_file = folder / ("mobilenetv2_plant.pth" if legacy else
                              [f for f in MODELS[self.model_name]["files"] if f.endswith((".bin", ".safetensors"))][0])
        onnx_file = folder / "mobilenetv2_plant.onnx"
        use_onnx = legacy and onnx_file.exists() and os.getenv("DHARRAKSHAK_RUNTIME", "onnx") == "onnx"
        if use_onnx:
            # Same model, ONNX runtime: no PyTorch needed (small servers, faster start).
            self.backend = DakshOnnx(onnx_file)
        else:
            if not main_file.exists():
                raise ModelNotAvailable(f"Model files not found in {folder}. Run: python scripts/download_model.py")
            import torch

            self.backend = DakshMobileNetV2(main_file) if legacy else HuggingFaceBackend(folder)
            torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        self.labels = load_labels()
        self._crop_of = np.array([c.crop for c in self.labels])
        log.info("Image model ready: %s", self.model_name)

    @staticmethod
    def _decode(image_bytes: bytes):
        """Bytes -> PIL image, refusing anything that would exhaust memory."""
        from PIL import Image, UnidentifiedImageError

        try:
            image = Image.open(io.BytesIO(image_bytes))
            # Refuse on the DECLARED size, before image.load() allocates the
            # pixel buffer. An 8 MB upload budget alone does not bound memory:
            # a highly compressible 12000x12000 PNG is 445 KB on the wire but
            # 432 MB once decoded, which is enough to OOM the free server.
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise InvalidImage(
                    f"The photo is too large ({image.width}x{image.height} pixels). "
                    "Please upload a photo under 40 megapixels."
                )
            image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as err:
            raise InvalidImage("The file could not be read as an image.") from err
        return image

    def _probs(self, image) -> np.ndarray:
        from PIL import ImageOps

        p = self.backend.probs(image)
        if USE_FLIP_TTA:
            p = (p + self.backend.probs(ImageOps.mirror(image))) / 2
        return p

    def probabilities(self, image_bytes: bytes) -> list[float]:
        """All 38 class probabilities (labels.json order), after preprocessing."""
        return self._probs(preprocess(self._decode(image_bytes), DEFAULT_STEPS).image).tolist()

    def classify(self, image_bytes: bytes, registered_crop: str | None = None) -> ClassifierOutput:
        prepared = preprocess(self._decode(image_bytes), DEFAULT_STEPS)
        probs = self._probs(prepared.image)

        # The model's own top predictions across ALL 38 classes. The registered
        # crop is only used to warn when the photo looks like a different crop.
        crop_classes = self._crop_of == registered_crop
        mass = float(probs[crop_classes].sum()) if registered_crop and crop_classes.any() else None
        # Show the model's real probability, never a re-scaled one: normalising
        # within the crop inflated confidence (a crop the model knows one class
        # for, e.g. orange, then always reported 100%).
        order = [int(i) for i in np.argsort(-probs)][:TOP_K]
        predictions = [
            Prediction(label=self.labels[i].label, display_name=display_name(self.labels[i]),
                       confidence=round(float(probs[i]), 4))
            for i in order
        ]
        top_p = probs[order[0]]

        # Warn (without changing the prediction) if the model's answer is for another crop.
        crop_mismatch = registered_crop is not None and self.labels[order[0]].crop != registered_crop
        if prepared.poor_quality:
            msg = POOR_PHOTO_MESSAGE
        elif top_p < UNCERTAIN_THRESHOLD:
            msg = UNCERTAIN_MESSAGE
        else:
            msg = None

        return ClassifierOutput(
            predictions=predictions,
            top=self.labels[order[0]],
            uncertain=msg is not None,
            uncertainty_message=msg,
            crop_mismatch=crop_mismatch,
            registered_crop_mass=mass,
            quality_issues=tuple(prepared.quality_issues),
        )


_instance: PlantDiseaseClassifier | None = None
_lock = threading.Lock()


def get_classifier() -> PlantDiseaseClassifier:
    """The shared classifier, loaded on first use (raises ModelNotAvailable)."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = PlantDiseaseClassifier()
    return _instance


def is_loaded() -> bool:
    """True once the model is in memory (used by /api/health)."""
    return _instance is not None
