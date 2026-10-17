"""
Risk engine (F3): Facts → Risk (level, score, reasons).

Every rule that fires adds its points AND a reason sentence, so the score
is fully traceable — the reasons become the "Why?" explanation (F4).
Rules, points and thresholds: shared/content/risk_rules.json.

Rule order (also the order reasons are shown):
1. What the photo shows   — unclear / healthy / possible / likely disease
2. Photo vs profile       — crop mismatch (information only, 0 points)
3. Weather                — matched to HOW the problem spreads:
                              fungal & bacterial ← wet recently, rain expected
                              spider mites       ← hot and dry
                              healthy leaf       ← wet recently (stay alert)
                            or "weather unavailable" (0 points) if missing
4. Crop stage             — flowering/fruiting raise the stakes
"""

from __future__ import annotations

from backend.engines.content import fill, load
from backend.engines.facts import Facts
from shared.contract import Risk, RiskLevel, RiskReason


def assess_risk(facts: Facts) -> Risk:
    rules = load("risk_rules")["rules"]
    values = facts.template_values()
    reasons: list[RiskReason] = []

    def add(code: str) -> None:
        rule = rules[code]
        reasons.append(RiskReason(code=code, points=rule["points"], text=fill(rule["text"], values)))

    # 1. What the photo shows
    if facts.uncertain:
        add("unclear_photo")
    elif facts.looks_healthy:
        add("looks_healthy")
    elif facts.high_confidence:
        add("disease_high_confidence")
    else:
        add("disease_possible")

    # 2. Photo vs profile
    if facts.crop_mismatch:
        add("crop_mismatch")

    # 3. Weather, matched to how the problem spreads
    if facts.weather is None:
        add("weather_unavailable")
    elif facts.weather_sensitive_disease:
        if facts.wet_recently:
            add("wet_recent_disease")
        if facts.rain_expected:
            add("rain_forecast_disease")
    elif facts.disease_detected and facts.disease_type == "pest":
        if facts.hot_and_dry:
            add("hot_dry_pest")
    elif facts.looks_healthy and facts.wet_recently:
        add("wet_recent_healthy")

    # 4. Crop stage (only matters when there is a problem)
    if facts.disease_detected and facts.sensitive_stage:
        add("sensitive_stage")

    score = sum(r.points for r in reasons)
    return Risk(level=level_for(score), score=score, is_estimate=True, reasons=reasons)


def level_for(score: int) -> RiskLevel:
    levels = load("risk_rules")["levels"]
    if score >= levels["elevated"]:
        return RiskLevel.elevated
    if score >= levels["moderate"]:
        return RiskLevel.moderate
    return RiskLevel.low
