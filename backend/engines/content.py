"""Load rule content from shared/content/ and fill {placeholders} per language."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from shared.contract import REQUIRED_LANGUAGES, LocalizedText

CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "shared" / "content"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    """Parsed JSON file from shared/content/, e.g. load("risk_rules")."""
    return json.loads((CONTENT_DIR / f"{name}.json").read_text(encoding="utf-8"))


class _KeepMissing(dict):
    """Leaves unknown {placeholders} visible instead of crashing — easy to spot."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def fill(template: dict, values: dict[str, dict[str, str]]) -> LocalizedText:
    """Fill a {"en": ..., "hi": ...} template.

    `values` maps language -> {placeholder: text}, e.g.
        {"en": {"disease": "tomato early blight"}, "hi": {"disease": "टमाटर का अगेती झुलसा"}}
    """
    filled = {lang: template[lang].format_map(_KeepMissing(values.get(lang, {}))) for lang in REQUIRED_LANGUAGES}
    return LocalizedText(**filled)
