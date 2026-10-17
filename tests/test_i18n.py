"""
Language coverage checks (Component 8).

- en.json and hi.json have exactly the same keys, none empty.
- Placeholders like {done} match between languages.
- Hindi labels are actually in Hindi (contain Devanagari), except a few
  intentional exceptions such as "DharRakshak" brand text.
- Every label the React app asks for with t('key') exists.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "shared" / "i18n"
FRONTEND_SRC = ROOT / "frontend" / "src"


def load(lang: str) -> dict:
    data = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


EN, HI = load("en"), load("hi")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def test_same_keys_in_both_languages():
    assert set(EN) == set(HI), f"only in en: {set(EN) - set(HI)}; only in hi: {set(HI) - set(EN)}"


@pytest.mark.parametrize("key", sorted(EN))
def test_label_is_complete(key):
    assert EN[key].strip() and HI[key].strip()
    assert re.findall(r"\{\w+\}", EN[key]) == re.findall(r"\{\w+\}", HI[key]) or \
        sorted(re.findall(r"\{\w+\}", EN[key])) == sorted(re.findall(r"\{\w+\}", HI[key]))
    assert DEVANAGARI.search(HI[key]), f"hi label for {key!r} has no Hindi text: {HI[key]!r}"


def keys_used_by_frontend() -> set[str]:
    used: set[str] = set()
    for path in FRONTEND_SRC.rglob("*.jsx"):
        source = path.read_text(encoding="utf-8")
        # t('key'), t("key"), t(cond ? 'a' : 'b')
        for call in re.findall(r"\bt\(([^()]*)\)", source):
            used.update(re.findall(r"""['"]([a-z][a-z0-9_]*)['"]""", call))
        # labelKey: 'nav_profile'  /  labelKey="demo_example"  /  key="mock_mode" on MockTag
        used.update(re.findall(r"""labelKey[=:]\s*['"]([a-z0-9_]+)['"]""", source))
        used.update(re.findall(r"""<MockTag[^>]*\bkey=['"]([a-z0-9_]+)['"]""", source))
    # Keys built at runtime from data values.
    used.update(f"risk_{level}" for level in ("low", "moderate", "elevated"))
    used.update(f"loan_status_{s}" for s in ("active", "overdue", "applied", "closed"))
    return used


def test_every_label_used_in_the_frontend_exists():
    missing = keys_used_by_frontend() - set(EN)
    assert not missing, f"frontend uses labels missing from shared/i18n: {sorted(missing)}"
