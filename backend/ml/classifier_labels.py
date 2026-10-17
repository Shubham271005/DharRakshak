"""
The model's 38 classes as described in shared/content/labels.json
(raw label, crop, healthy flag, disease type, EN/HI names).

Kept separate from classifier.py so both the classifier and the model
backends (models.py) can use it without importing each other.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from shared.contract import LocalizedText

LABELS_PATH = Path(__file__).resolve().parent.parent.parent / "shared" / "content" / "labels.json"
NUM_CLASSES = 38


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


