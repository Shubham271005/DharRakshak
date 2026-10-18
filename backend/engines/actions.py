"""
Action-card engine (F2): Facts → ranked ActionCards.

1. Decide which cards are ELIGIBLE (conditions below).
2. Sort eligible cards by `weight` from shared/content/action_cards.json.
3. When a disease is detected, its own steps from
   shared/content/disease_advice.json join the list (weights 90, 89), so the
   advice changes with the disease instead of always being generic.
4. Keep the top `max_cards` (3) and number them 1, 2, 3.

Cards only ever suggest checking, verifying, monitoring and basic field
hygiene — no pesticide names or doses (enforced by tests/test_engines.py).
"""

from __future__ import annotations

from collections.abc import Callable

from backend.engines.content import fill, load
from backend.engines.facts import Facts
from shared.contract import ActionCard

# card id -> condition. Keep in sync with the "when" notes in action_cards.json.
ELIGIBLE: dict[str, Callable[[Facts], bool]] = {
    "retake_photo": lambda f: f.uncertain,
    "check_crop": lambda f: f.crop_mismatch,
    "inspect_nearby": lambda f: f.disease_detected,
    "check_undersides": lambda f: f.disease_detected and f.disease_type == "pest",
    "check_insects": lambda f: f.disease_detected and f.disease_type == "insect_spread",
    "keep_monitoring": lambda f: f.looks_healthy,
    "check_local_guidance": lambda f: f.disease_detected or f.uncertain,
    "clean_tools": lambda f: f.disease_detected and f.disease_type == "viral",
    "keep_leaves_dry": lambda f: (f.weather_sensitive_disease or f.looks_healthy)
    and (f.wet_recently or f.rain_expected),
    "monitor_weather": lambda f: f.weather_sensitive_disease and f.rain_expected,
    "recheck_photo": lambda f: True,
}

DISEASE_STEP_WEIGHTS = (90, 89)  # below retake_photo / check_crop, above the generic cards


def disease_steps(facts: Facts) -> list[tuple[int, str, dict]]:
    """(weight, card_id, template) for the detected disease's own steps."""
    if not facts.disease_detected:
        return []
    steps = load("disease_advice")["advice"].get(facts.top.label, {}).get("steps", [])
    return [(w, f"{facts.top.label}:{i}", step) for i, (w, step) in enumerate(zip(DISEASE_STEP_WEIGHTS, steps), start=1)]


def choose_cards(facts: Facts) -> list[ActionCard]:
    content = load("action_cards")
    templates = content["cards"]
    values = facts.template_values()

    eligible = [(templates[card_id]["weight"], card_id, templates[card_id])
                for card_id, condition in ELIGIBLE.items() if condition(facts)]
    specific = disease_steps(facts)
    if specific:
        # The disease's own steps replace the generic "inspect nearby" card.
        eligible = [c for c in eligible if c[1] != "inspect_nearby"]
    eligible += specific
    eligible.sort(key=lambda c: c[0], reverse=True)

    return [
        ActionCard(
            card_id=card_id,
            priority=position,
            title=fill(template["title"], values),
            detail=fill(template["detail"], values),
            why=fill(template["why"], values),
        )
        for position, (_, card_id, template) in enumerate(eligible[: content["max_cards"]], start=1)
    ]
