"""
Action-card engine (F2): Facts → ranked ActionCards.

1. Decide which cards are ELIGIBLE (conditions below).
2. Sort eligible cards by `weight` from shared/content/action_cards.json.
3. Keep the top `max_cards` (3) and number them 1, 2, 3.

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


def choose_cards(facts: Facts) -> list[ActionCard]:
    content = load("action_cards")
    templates = content["cards"]
    values = facts.template_values()

    eligible = [card_id for card_id, condition in ELIGIBLE.items() if condition(facts)]
    eligible.sort(key=lambda card_id: templates[card_id]["weight"], reverse=True)

    return [
        ActionCard(
            card_id=card_id,
            priority=position,
            title=fill(templates[card_id]["title"], values),
            detail=fill(templates[card_id]["detail"], values),
            why=fill(templates[card_id]["why"], values),
        )
        for position, card_id in enumerate(eligible[: content["max_cards"]], start=1)
    ]
