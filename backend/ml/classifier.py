"""
Pretrained plant-disease image classifier (Component 4, feature F1).

Model: Daksh159/plant-disease-mobilenetv2 on Hugging Face (Apache-2.0).
MobileNetV2 trained on the PlantVillage dataset, 38 classes, 224×224 input.
Full details and limitations: docs/MODEL_CARD.md.

Pipeline for one photo:
    bytes ─► decode (Pillow) ─► RGB ─► resize 224×224 ─► tensor ─► ImageNet
    normalise ─► MobileNetV2 ─► softmax ─► top-3 ─► labels + EN/HI names
    ─► uncertainty + crop-mismatch checks

Safety choices:
- Weights are loaded with `torch.load(weights_only=True)`, which refuses
  to run arbitrary pickled code from the downloaded file.
- The file's SHA-256 is checked against the pinned value below.
- The model is built with the SAME head used in training and loaded with
  `strict=True`, so a mismatch fails loudly instead of silently giving
  random predictions.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from shared.contract import LocalizedText, Prediction

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LABELS_PATH = REPO_ROOT / "shared" / "content" / "labels.json"

# ---------------------------------------------------------------------------
# Model source — pinned to an exact Hugging Face revision for reproducibility
# ---------------------------------------------------------------------------
HF_REPO = "Daksh159/plant-disease-mobilenetv2"
HF_REVISION = "d3fb2afc90da83086eff06e9088a889b6c43d4a6"
WEIGHTS_FILENAME = "mobilenetv2_plant.pth"
WEIGHTS_URL = f"https://huggingface.co/{HF_REPO}/resolve/{HF_REVISION}/{WEIGHTS_FILENAME}"
WEIGHTS_SHA256 = "26c97b05ef2caf58bce6f901c725926546a887ee50f0a637a363b644ec17f96e"  # from the Hugging Face LFS record

NUM_CLASSES = 38
INPUT_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Below this top-1 confidence the result is shown as "uncertain" and the
# farmer is asked to retake the photo. 0.5 is a starting point — tune it
# after testing on real field photos (see docs/MODEL_CARD.md).
UNCERTAIN_THRESHOLD = 0.50
TOP_K = 3

# Basic photo-quality gate, applied BEFORE trusting the model. The model was
# trained only on leaf photos and is often confidently wrong on anything
# else (a plain green rectangle scored 92% "Septoria leaf spot" in testing).
# These cheap checks catch blank, flat, tiny or very dark photos; they do NOT
# detect every non-leaf photo (see docs/MODEL_CARD.md, "Known limitations").
MIN_SIDE_PX = 64          # smaller than this can't show leaf detail
MIN_DETAIL_STD = 12.0     # grey-level spread (0–255); below = flat/blank photo
MIN_BRIGHTNESS = 25.0     # mean grey level; below = far too dark


class ModelNotAvailable(RuntimeError):
    """Weights are missing or failed verification. The API returns 503."""


class InvalidImage(ValueError):
    """The uploaded bytes are not a readable image. The API returns 400."""


def model_dir() -> Path:
    return Path(os.getenv("DHARRAKSHAK_MODEL_DIR", str(REPO_ROOT / "models" / "plant-disease-mobilenetv2")))


def weights_path() -> Path:
    return model_dir() / WEIGHTS_FILENAME


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_weights(force: bool = False) -> Path:
    """Download the weights from Hugging Face (resumable) and verify them.

    Called by scripts/download_model.py — NOT at server startup, so a slow
    network can never block the API from starting.
    """
    path = weights_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force and sha256_of(path) == WEIGHTS_SHA256:
        return path

    partial = path.with_suffix(".part")
    if path.exists() and not partial.exists():
        path.replace(partial)  # unverified/incomplete file: resume it instead of starting over
    start = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(WEIGHTS_URL, headers={"Range": f"bytes={start}-"} if start else {})
    with urllib.request.urlopen(request, timeout=60) as resp, partial.open("ab" if start else "wb") as out:
        while chunk := resp.read(1 << 16):
            out.write(chunk)

    actual = sha256_of(partial)
    if actual != WEIGHTS_SHA256:
        partial.unlink(missing_ok=True)
        raise ModelNotAvailable(f"Downloaded weights failed the SHA-256 check (got {actual}). Try again.")
    partial.replace(path)
    return path


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassInfo:
    label: str          # raw class name, e.g. "Tomato___Early_blight"
    crop: str           # crop key, e.g. "tomato"
    healthy: bool
    disease_type: str   # fungal | bacterial | viral | insect_spread | pest | healthy
    name: LocalizedText  # plain name, e.g. {"en": "tomato early blight", ...}


@lru_cache(maxsize=1)
def load_labels() -> tuple[ClassInfo, ...]:
    raw = json.loads(LABELS_PATH.read_text(encoding="utf-8"))["classes"]
    if len(raw) != NUM_CLASSES:
        raise ValueError(f"labels.json has {len(raw)} classes, expected {NUM_CLASSES}")
    return tuple(
        ClassInfo(label=c["label"], crop=c["crop"], healthy=c["healthy"],
                  disease_type=c["type"], name=LocalizedText(**c["name"]))
        for c in raw
    )


def display_name(info: ClassInfo) -> LocalizedText:
    """Farmer-facing wording. Never claims certainty: 'Possible …' / 'Likely …'."""
    if info.healthy:
        return LocalizedText(en=f"Likely {info.name.en}", hi=f"संभवतः {info.name.hi}")
    return LocalizedText(en=f"Possible {info.name.en}", hi=f"संभावित {info.name.hi}")


# ---------------------------------------------------------------------------
# The classifier
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassifierOutput:
    predictions: list[Prediction]   # top-3, highest first
    top: ClassInfo                  # details of the top-1 class
    uncertain: bool
    uncertainty_message: LocalizedText | None


POOR_PHOTO_MESSAGE = LocalizedText(
    en="This photo looks blank, too dark or too small to check. Please take a clear, close photo "
       "of one leaf in daylight.",
    hi="यह तस्वीर खाली, बहुत अँधेरी या बहुत छोटी लग रही है। कृपया दिन की रोशनी में एक पत्ती की "
       "साफ़, नज़दीक से फोटो लें।",
)

UNCERTAIN_MESSAGE = LocalizedText(
    en="The model is not confident about this photo. Please retake it in daylight, "
       "with one leaf filling most of the frame, and check with a local expert.",
    hi="मॉडल इस तस्वीर को लेकर आश्वस्त नहीं है। कृपया दिन की रोशनी में, एक पत्ती को फ्रेम में "
       "बड़ा रखकर दोबारा फोटो लें, और स्थानीय विशेषज्ञ से जाँच कराएँ।",
)


class PlantDiseaseClassifier:
    """Loads the model once and classifies leaf photos. Thread-safe for inference."""

    def __init__(self, path: Path | None = None) -> None:
        # Imported here so the rest of the backend (and its tests) can start
        # even on a machine where PyTorch isn't installed yet.
        import torch
        from torch import nn
        from torchvision import models, transforms

        path = path or weights_path()
        if not path.exists():
            raise ModelNotAvailable(
                f"Model weights not found at {path}. Run: python scripts/download_model.py"
            )

        self._torch = torch
        model = models.mobilenet_v2(weights=None)
        # Same head as in training (see the model card): Dropout + Linear(1280 → 38).
        model.classifier[1] = nn.Sequential(nn.Dropout(0.2), nn.Linear(model.last_channel, NUM_CLASSES))

        state = torch.load(path, map_location="cpu", weights_only=True)
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        model.load_state_dict(state, strict=True)
        model.eval()
        self._model = model

        self._preprocess = transforms.Compose([
            transforms.Resize((INPUT_SIZE, INPUT_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
        self.labels = load_labels()
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))

    @staticmethod
    def _decode(image_bytes: bytes):
        from PIL import Image, UnidentifiedImageError

        try:
            image = Image.open(io.BytesIO(image_bytes))
            image.load()
        except (UnidentifiedImageError, OSError) as err:
            raise InvalidImage("The file could not be read as an image.") from err
        return image.convert("RGB")

    @staticmethod
    def is_poor_photo(image) -> bool:
        """True for blank/flat, tiny or very dark photos (see constants above)."""
        from PIL import ImageStat

        if min(image.size) < MIN_SIDE_PX:
            return True
        stats = ImageStat.Stat(image.convert("L"))
        return stats.stddev[0] < MIN_DETAIL_STD or stats.mean[0] < MIN_BRIGHTNESS

    def _probabilities_for(self, image) -> list[float]:
        tensor = self._preprocess(image).unsqueeze(0)
        with self._torch.inference_mode():
            probs = self._torch.softmax(self._model(tensor), dim=1)[0]
        return probs.tolist()

    def probabilities(self, image_bytes: bytes) -> list[float]:
        """All 38 class probabilities for one image (index order = labels.json)."""
        return self._probabilities_for(self._decode(image_bytes))

    def classify(self, image_bytes: bytes) -> ClassifierOutput:
        image = self._decode(image_bytes)
        poor_photo = self.is_poor_photo(image)
        probs = self._probabilities_for(image)
        ranked = sorted(range(NUM_CLASSES), key=lambda i: probs[i], reverse=True)[:TOP_K]
        predictions = [
            Prediction(
                label=self.labels[i].label,
                display_name=display_name(self.labels[i]),
                confidence=round(probs[i], 4),
            )
            for i in ranked
        ]
        if poor_photo:
            message = POOR_PHOTO_MESSAGE
        elif probs[ranked[0]] < UNCERTAIN_THRESHOLD:
            message = UNCERTAIN_MESSAGE
        else:
            message = None
        return ClassifierOutput(
            predictions=predictions,
            top=self.labels[ranked[0]],
            uncertain=message is not None,
            uncertainty_message=message,
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
