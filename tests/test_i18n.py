"""
Language coverage checks (English, Hindi, Marathi, Punjabi, Haryanvi, Bhojpuri).

- Every UI label file has exactly the keys of en.json, none empty.
- {placeholders} match English in every language.
- Each language is written in its script (Devanagari / Gurmukhi).
- Every label the React app asks for exists.
- Every {"en", "hi"} text in shared/content and sample_data.json exists in
  all six languages, with the same placeholders.
"""

import json
import re
from pathlib import Path

import pytest

from shared.contract import SUPPORTED_LANGUAGES

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "shared" / "i18n"
FRONTEND_SRC = ROOT / "frontend" / "src"
SCRIPT = {"hi": r"[ऀ-ॿ]", "mr": r"[ऀ-ॿ]", "bgc": r"[ऀ-ॿ]",
          "bho": r"[ऀ-ॿ]", "pa": r"[਀-੿]"}
CONTENT_FILES = ["labels", "risk_rules", "action_cards", "crops", "loan_documents", "schemes", "messages"]


def load(lang: str) -> dict:
    path = I18N / f"{lang}.json"
    if not path.exists():
        return {}
    return {k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if not k.startswith("_")}


LABELS = {lang: load(lang) for lang in SUPPORTED_LANGUAGES}
EN = LABELS["en"]


def placeholders(text: str) -> list[str]:
    return sorted(re.findall(r"\{\w+\}", text))


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES[1:])
def test_language_file_has_every_key(lang):
    assert set(LABELS[lang]) == set(EN), (
        f"{lang}: missing {sorted(set(EN) - set(LABELS[lang]))[:10]}, extra {sorted(set(LABELS[lang]) - set(EN))[:10]}"
        " — run python scripts/translate_content.py"
    )


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES[1:])
def test_labels_are_complete_and_in_script(lang):
    bad = []
    for key, en_text in EN.items():
        text = LABELS[lang].get(key, "")
        if not text.strip():
            bad.append(f"{key}: empty")
        elif placeholders(text) != placeholders(en_text):
            bad.append(f"{key}: placeholders {placeholders(text)} != {placeholders(en_text)}")
        elif not re.search(SCRIPT[lang], text) and re.search(r"[A-Za-z]{3}", en_text):
            bad.append(f"{key}: not in the {lang} script: {text!r}")
    assert not bad, bad[:10]


def keys_used_by_frontend() -> set[str]:
    used: set[str] = set()
    for path in FRONTEND_SRC.rglob("*.jsx"):
        source = path.read_text(encoding="utf-8")
        for call in re.findall(r"\bt\(([^()]*)\)", source):  # t('key'), t(cond ? 'a' : 'b')
            used.update(re.findall(r"""['"]([a-z][a-z0-9_]*)['"]""", call))
        used.update(re.findall(r"""labelKey[=:]\s*['"]([a-z0-9_]+)['"]""", source))
        used.update(re.findall(r"""<MockTag[^>]*\bkey=['"]([a-z0-9_]+)['"]""", source))
        # QUICK_QUESTIONS / SUGGESTION_KEYS arrays of label keys
        for arr in re.findall(r"(?:QUICK_QUESTIONS|SUGGESTION_KEYS)\s*=\s*\[([^\]]*)\]", source):
            used.update(re.findall(r"""['"]([a-z0-9_]+)['"]""", arr))
    # Keys built at runtime from data values.
    used.update(f"risk_{level}" for level in ("low", "moderate", "elevated"))
    used.update(f"loan_status_{s}" for s in ("active", "overdue", "applied", "closed"))
    labels = json.loads((ROOT / "shared/content/labels.json").read_text(encoding="utf-8"))["classes"]
    used.update(f"crop_{c}" for c in {c["crop"] for c in labels})
    used.update(f"stage_{s}" for s in ("seedling", "vegetative", "flowering", "fruiting", "maturity"))
    return used


def test_every_label_used_in_the_frontend_exists():
    missing = keys_used_by_frontend() - set(EN)
    assert not missing, f"frontend uses labels missing from shared/i18n/en.json: {sorted(missing)}"


def collect(node, path=""):
    if isinstance(node, dict):
        if isinstance(node.get("en"), str) and isinstance(node.get("hi"), str):
            yield path, node
            return
        for k, v in node.items():
            if not k.startswith("_"):
                yield from collect(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from collect(v, f"{path}/{i}")


@pytest.mark.parametrize("name", CONTENT_FILES + ["sample_data"])
def test_content_texts_exist_in_every_language(name):
    path = ROOT / "shared" / ("sample_data.json" if name == "sample_data" else f"content/{name}.json")
    bad = []
    for where, text in collect(json.loads(path.read_text(encoding="utf-8"))):
        for lang in SUPPORTED_LANGUAGES:
            value = text.get(lang)
            if not value or not value.strip():
                bad.append(f"{where}: no {lang}")
            elif placeholders(value) != placeholders(text["en"]):
                bad.append(f"{where}: {lang} placeholders differ")
            elif lang in SCRIPT and not re.search(SCRIPT[lang], value) and re.search(r"[A-Za-z]{3}", text["en"]):
                bad.append(f"{where}: {lang} not in its script")
    assert not bad, f"{len(bad)} problems, e.g. {bad[:8]} — run python scripts/translate_content.py"


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES[1:])
def test_progress_counter_word_order(lang):
    # "3 of 5 submitted": Indian languages say "5 out of: 3" ("5 में से 3"),
    # so {total} must come before {done}. A machine translation once kept the
    # English order, which reads as "out of 3, 5 submitted".
    text = LABELS[lang].get("documents_progress", "")
    if not text:
        pytest.skip("not translated yet")
    assert text.index("{total}") < text.index("{done}"), text
