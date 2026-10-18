"""
Explanation builder (F4): Risk reasons → the "Why?" text.

No extra AI: the summary is the risk level plus the reason sentences the
risk engine collected, so every word can be traced to a rule. The
"verify" line tells the farmer what to check before acting.
"""

from __future__ import annotations

from backend.engines.content import fill, load
from backend.engines.facts import Facts
from shared.contract import SUPPORTED_LANGUAGES, Explanation, LocalizedText, Risk

MAX_REASONS = 3  # keep it short enough to read on a phone


def build_explanation(facts: Facts, risk: Risk) -> Explanation:
    templates = load("action_cards")["explanation"]
    level_names = load("risk_rules")["levels"]["names"][risk.level.value]

    # Keep the rule order (photo → crop check → weather → stage) because it
    # reads naturally. If there are too many reasons, drop the weakest ones
    # (fewest points) but never reorder the ones that stay.
    keep = sorted(range(len(risk.reasons)), key=lambda i: risk.reasons[i].points, reverse=True)[:MAX_REASONS]
    ordered = [risk.reasons[i] for i in sorted(keep)]
    level = LocalizedText(**level_names)
    values = {
        lang: {"level": level.in_lang(lang), "reasons": " ".join(r.text.in_lang(lang) for r in ordered)}
        for lang in SUPPORTED_LANGUAGES
    }
    summary = fill(templates["summary"], values)

    if facts.uncertain:
        verify = templates["verify"]["uncertain"]
    elif facts.looks_healthy:
        verify = templates["verify"]["healthy"]
    else:
        verify = templates["verify"]["disease"]
    # Disease-specific background (what it is, what to look for) so the
    # explanation is about THIS disease, not only the generic risk reasons.
    advice = load("disease_advice")["advice"].get(facts.top.label) if facts.disease_detected else None
    return Explanation(
        summary=summary,
        verify=LocalizedText(**verify),
        about=LocalizedText(**advice["about"]) if advice else None,
        look_for=LocalizedText(**advice["look_for"]) if advice else None,
    )
