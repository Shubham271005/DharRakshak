"""
Translate all fixed farmer-facing text into Marathi, Punjabi, Haryanvi and
Bhojpuri, using the Groq LLM (same key as the chatbot).

Run from the repository root:
    python scripts/translate_content.py              # fill in missing translations
    python scripts/translate_content.py --force      # redo everything
    python scripts/translate_content.py --langs pa   # one language

What it translates:
  shared/i18n/en.json            → shared/i18n/{mr,pa,bgc,bho}.json   (UI labels)
  shared/content/*.json, shared/sample_data.json
                                 → adds "mr"/"pa"/"bgc"/"bho" next to every
                                   {"en": …, "hi": …} text (names, risk reasons,
                                   action cards, schemes, messages …)

Every batch is validated: same keys, {placeholders} unchanged, correct
script (Devanagari / Gurmukhi), nothing empty — otherwise it is retried.

IMPORTANT: these are machine translations. They are a good starting point,
but a native speaker should review them (especially Haryanvi and Bhojpuri,
which are mostly spoken and have little standard written form).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend import config  # noqa: E402,F401  (loads GROQ_API_KEY)
from backend.services import llm  # noqa: E402

LANGS = {
    "mr": ("Marathi", "Devanagari", "standard, simple Marathi as spoken by farmers in rural Maharashtra"),
    "pa": ("Punjabi", "Gurmukhi", "simple Punjabi in Gurmukhi script as spoken by farmers in rural Punjab"),
    "bgc": ("Haryanvi", "Devanagari",
            "Haryanvi as spoken by farmers in rural Haryana (use natural Haryanvi words and grammar such as "
            "थारा/म्हारा, सै, कोनी where they sound natural), written in Devanagari"),
    "bho": ("Bhojpuri", "Devanagari",
            "Bhojpuri as spoken by farmers in Bihar and eastern Uttar Pradesh (natural Bhojpuri grammar such as "
            "बा, बानी, रउआ, हमनी where they sound natural), written in Devanagari"),
}
SCRIPT_RANGES = {"Devanagari": r"[ऀ-ॿ]", "Gurmukhi": r"[਀-੿]"}
# Groq free tier: 8,000 tokens/minute per model, 1,000 requests/day. Small
# batches + pauses stay under the per-minute limit and leave most of the
# daily requests for the chatbot.
BATCH = 12
MAX_TOKENS = 3000
PAUSE_SECONDS = 8

CONTENT_FILES = [
    "shared/content/labels.json", "shared/content/risk_rules.json", "shared/content/action_cards.json",
    "shared/content/crops.json", "shared/content/loan_documents.json", "shared/content/schemes.json",
    "shared/content/messages.json", "shared/sample_data.json",
]

SYSTEM = """You translate text for DharRakshak, a farming app for small farmers in India.
Translate each value into {style}.
Rules:
- Use simple, everyday words a farmer understands; keep agricultural meaning exact.
- Keep every {{placeholder}} in curly braces EXACTLY as it is (do not translate or remove it).
- Keep these unchanged: numbers, units (mm, %, °C, kg, ₹), scheme acronyms (KCC, MISS, PMFBY, PM-KISAN),
  website addresses, "Open-Meteo". Write the app name as "DharRakshak" transliterated into the target script.
- Disease names: use the common local name if one exists, otherwise transliterate the English name.
- Keep the same tone: careful, never claiming certainty ("possible", "estimate").
- Output ONLY a JSON object with exactly the same keys as the input, values translated."""


def placeholders(text: str) -> list[str]:
    return sorted(re.findall(r"\{\w+\}", text))


def translate_batch(items: dict[str, dict[str, str]], lang: str) -> dict[str, str]:
    """items: key -> {"en":…, "hi":…}. Returns key -> translation (validated)."""
    name, script, style = LANGS[lang]
    payload = {k: v["en"] for k, v in items.items()}
    hindi = {k: v.get("hi", "") for k, v in items.items()}
    messages = [
        {"role": "system", "content": SYSTEM.format(style=style)},
        {"role": "user", "content": "Translate the values of this JSON object into " + name +
         ". Hindi versions are given for reference only.\nENGLISH:\n" + json.dumps(payload, ensure_ascii=False) +
         "\nHINDI (reference):\n" + json.dumps(hindi, ensure_ascii=False)},
    ]
    for attempt in range(10):
        try:
            text, _ = llm.chat_complete(messages, max_tokens=MAX_TOKENS, temperature=0.2)
        except llm.LLMUnavailable as err:  # rate limited: wait for the minute window to reset
            print(f"    waiting 30 s ({err})", flush=True)
            time.sleep(30)
            continue
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            continue
        problems = []
        for k, src in payload.items():
            value = out.get(k)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{k}: missing")
            elif placeholders(value) != placeholders(src):
                problems.append(f"{k}: placeholders changed")
            elif not re.search(SCRIPT_RANGES[script], value) and re.search(r"[A-Za-z]{3}", src):
                problems.append(f"{k}: not in {script} script")
        if not problems:
            return {k: out[k].strip() for k in payload}
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": "Fix these problems and return the full JSON again: " + "; ".join(problems[:10])})
    raise RuntimeError(f"{name}: could not get a valid translation for batch starting {next(iter(payload))}")


def collect(node, path=()):
    """Yield (path, dict) for every {"en": str, "hi": str} text inside a JSON tree."""
    if isinstance(node, dict):
        if isinstance(node.get("en"), str) and isinstance(node.get("hi"), str):
            yield path, node
            return
        for k, v in node.items():
            if not k.startswith("_"):
                yield from collect(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from collect(v, path + (i,))


def run_batches(todo: dict[str, dict], lang: str, on_batch=None) -> dict[str, str]:
    """Translate in batches; `on_batch(results)` is called after each one so
    progress is saved even if the run stops part-way."""
    keys = list(todo)
    done: dict[str, str] = {}
    for i in range(0, len(keys), BATCH):
        chunk = {k: todo[k] for k in keys[i:i + BATCH]}
        result = translate_batch(chunk, lang)
        done.update(result)
        if on_batch:
            on_batch(result)
        print(f"    {min(i + BATCH, len(keys))}/{len(keys)}", flush=True)
        time.sleep(PAUSE_SECONDS)
    return done


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", nargs="*", default=list(LANGS))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    en = json.loads((REPO_ROOT / "shared/i18n/en.json").read_text(encoding="utf-8"))
    hi = json.loads((REPO_ROOT / "shared/i18n/hi.json").read_text(encoding="utf-8"))
    docs = {f: json.loads((REPO_ROOT / f).read_text(encoding="utf-8")) for f in CONTENT_FILES}

    for lang in args.langs:
        name = LANGS[lang][0]
        # 1. UI labels
        target_path = REPO_ROOT / f"shared/i18n/{lang}.json"
        existing = {} if args.force or not target_path.exists() else json.loads(target_path.read_text(encoding="utf-8"))
        todo = {k: {"en": v, "hi": hi.get(k, "")} for k, v in en.items() if not k.startswith("_") and k not in existing}
        print(f"{name}: {len(todo)} UI labels")

        def save_labels(result, existing=existing, target_path=target_path, name=name):
            existing.update(result)
            out = {"_about": f"UI labels ({name}). MACHINE-TRANSLATED with scripts/translate_content.py — please have a native speaker review."}
            out.update({k: existing[k] for k in en if not k.startswith("_") and k in existing})
            target_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if todo:
            run_batches(todo, lang, save_labels)

        # 2. Content texts (added next to en/hi)
        todo, refs = {}, {}
        for f, doc in docs.items():
            for path, node in collect(doc):
                if args.force or lang not in node:
                    key = f"{Path(f).stem}:{'/'.join(map(str, path))}"
                    todo[key], refs[key] = node, node
        print(f"{name}: {len(todo)} content texts")

        def save_content(result, refs=refs, lang=lang):
            for key, text in result.items():
                refs[key][lang] = text
            for f, doc in docs.items():
                (REPO_ROOT / f).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if todo:
            run_batches(todo, lang, save_content)
    print("Done. Run: pytest tests/test_i18n.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
