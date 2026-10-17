"""
Plant-disease image classifier (feature F1) — upgraded for real-world photos.

WHY THIS CHANGED: on 89 real field photos (PlantDoc), the original model
(Daksh159 MobileNetV2) got only 12% top-1 — it ranked all 38 classes and
often answered with a different crop entirely. Measured with
scripts/eval_pipeline.py (details: docs/MODEL_CARD.md), the setup below
reaches 62% top-1 / 85% top-3 on the same photos:

  1. Model: linkanjarad MobileNetV2 (best real-world accuracy of the 4
     models tested; same size/speed class). Choose another with
     DHARRAKSHAK_MODEL in .env — see MODELS below.
  2. Preprocessing (backend/ml/preprocess.py): EXIF rotation + quality
     checks (blur, dark, blank, tiny). Leaf crop / CLAHE / white balance /
     denoise exist but are OFF: they did not help real-world accuracy.
  3. Flip test-time augmentation: average the photo and its mirror image.
  4. Crop-aware ranking: the farmer registered their crop, so only that
     crop's classes are ranked (the single biggest improvement).
  5. Honest confidence:
       - uncertain if the top-2 gap (within the crop) is < 0.3,
         or the photo is blurry/dark/blank/tiny;
       - "may not be your crop" warning if the photo puts < 0.1% of its
         probability on the registered crop (calibrated for few false alarms);
       - crops the model knows only ONE class for (e.g. healthy blueberry)
         are always flagged as limited support.
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
DEFAULT_MODEL = "linkanjarad-mobilenetv2"

TOP_K = 3
USE_FLIP_TTA = True
# Calibrated on 89 PlantDoc field photos (scripts/eval_model.py):
# gap < 0.3 → 43% accurate vs 65% otherwise, so the flag is informative.
MARGIN_THRESHOLD = 0.30          # top-1 minus top-2 (within the crop); below = uncertain
UNCERTAIN_THRESHOLD = 0.50       # used only when no crop is registered
# Probability the photo puts on the registered crop; below = "may not be your
# crop". At 0.02 it falsely warned on 30% of genuine photos; 0.001 keeps false
# alarms at ~4.5% but only catches ~31% of wrong-crop photos (crop identity is
# the model's weak spot on field photos — see docs/MODEL_CARD.md).
CROP_MASS_THRESHOLD = 0.001


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
        return model_folder(name) / "mobilenetv2_plant.pth"
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
    predictions: list[Prediction]        # top-3 (within the registered crop if known), highest first
    top: ClassInfo                       # details of the top-1 class
    uncertain: bool
    uncertainty_message: LocalizedText | None
    crop_mismatch: bool = False          # photo puts almost no weight on the registered crop
    registered_crop_mass: float | None = None
    quality_issues: tuple[str, ...] = ()


POOR_PHOTO_MESSAGE = message("poor_photo")
UNCERTAIN_MESSAGE = message("uncertain_photo")


class PlantDiseaseClassifier:
    """Loads the selected model once and classifies leaf photos. Thread-safe."""

    def __init__(self, model_name: str | None = None) -> None:
        import torch

        from backend.ml.models import DakshMobileNetV2, HuggingFaceBackend

        self.model_name = model_name or selected_model()
        folder = model_folder(self.model_name)
        legacy = MODELS[self.model_name].get("legacy")
        main_file = folder / ("mobilenetv2_plant.pth" if legacy else
                              [f for f in MODELS[self.model_name]["files"] if f.endswith((".bin", ".safetensors"))][0])
        if not main_file.exists():
            raise ModelNotAvailable(f"Model files not found in {folder}. Run: python scripts/download_model.py")
        self.backend = DakshMobileNetV2(main_file) if legacy else HuggingFaceBackend(folder)
        self.labels = load_labels()
        self._crop_of = np.array([c.crop for c in self.labels])
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        log.info("Image model ready: %s", self.model_name)

    @staticmethod
    def _decode(image_bytes: bytes):
        from PIL import Image, UnidentifiedImageError

        try:
            image = Image.open(io.BytesIO(image_bytes))
            image.load()
        except (UnidentifiedImageError, OSError) as err:
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

        crop_classes = self._crop_of == registered_crop
        mass = None
        if registered_crop and crop_classes.any():
            mass = float(probs[crop_classes].sum())
            ranked_probs = np.where(crop_classes, probs, 0.0) / max(mass, 1e-9)  # renormalise within the crop
        else:
            ranked_probs = probs
        order = [int(i) for i in np.argsort(-ranked_probs) if ranked_probs[i] > 0][:TOP_K]
        predictions = [
            Prediction(label=self.labels[i].label, display_name=display_name(self.labels[i]),
                       confidence=round(float(ranked_probs[i]), 4))
            for i in order
        ]
        top_p = ranked_probs[order[0]]
        second = ranked_probs[order[1]] if len(order) > 1 else 0.0

        crop_mismatch = mass is not None and mass < CROP_MASS_THRESHOLD
        single_class_crop = registered_crop is not None and int(crop_classes.sum()) == 1
        if prepared.poor_quality:
            msg = POOR_PHOTO_MESSAGE
        elif crop_mismatch:
            msg = message("not_registered_crop", crop_name(registered_crop))
        elif single_class_crop:
            msg = message("limited_crop_support", crop_name(registered_crop))
        elif (top_p - second) < MARGIN_THRESHOLD or (mass is None and top_p < UNCERTAIN_THRESHOLD):
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
