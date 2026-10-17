"""
Everything the engines need to know about one analysis, in one place.

The engines never look at raw model output or weather directly; they ask
simple yes/no questions of `Facts` (is a disease detected? was it wet
recently? is rain expected?). The thresholds come from
shared/content/risk_rules.json.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.engines.content import load
from backend.ml.classifier import ClassInfo
from shared.contract import SUPPORTED_LANGUAGES, CropProfile, LocalizedText, Weather

WEATHER_SENSITIVE_TYPES = {"fungal", "bacterial"}  # spread by wet leaves / rain splash


def thresholds() -> dict:
    return load("risk_rules")["thresholds"]


@dataclass(frozen=True)
class Facts:
    crop: CropProfile
    top: ClassInfo          # the model's top-1 class
    confidence: float       # its confidence, 0–1
    uncertain: bool         # low confidence or poor photo
    crop_mismatch: bool
    weather: Weather | None

    # ----- what the photo shows -------------------------------------------

    @property
    def disease_detected(self) -> bool:
        """A disease or pest, with enough confidence to act on."""
        return not self.uncertain and not self.top.healthy

    @property
    def looks_healthy(self) -> bool:
        return not self.uncertain and self.top.healthy

    @property
    def disease_type(self) -> str:
        return self.top.disease_type

    @property
    def weather_sensitive_disease(self) -> bool:
        return self.disease_detected and self.disease_type in WEATHER_SENSITIVE_TYPES

    @property
    def high_confidence(self) -> bool:
        return self.confidence >= thresholds()["high_confidence"]

    # ----- weather ----------------------------------------------------------

    @property
    def wet_recently(self) -> bool:
        w, t = self.weather, thresholds()
        return w is not None and (
            w.rain_last_3_days_mm >= t["wet_recent_rain_mm"] or w.avg_humidity_pct >= t["wet_recent_humidity_pct"]
        )

    @property
    def rain_expected(self) -> bool:
        w, t = self.weather, thresholds()
        if w is None:
            return False
        return (w.rain_next_3_days_mm or 0) >= t["rain_forecast_mm"] or (
            w.max_rain_chance_next_3_days_pct or 0
        ) >= t["rain_forecast_chance_pct"]

    @property
    def hot_and_dry(self) -> bool:
        w, t = self.weather, thresholds()
        return w is not None and w.avg_temp_c >= t["hot_dry_temp_c"] and w.avg_humidity_pct < t["hot_dry_humidity_pct"]

    # ----- crop -------------------------------------------------------------

    @property
    def sensitive_stage(self) -> bool:
        return self.crop.stage.value in thresholds()["sensitive_stages"]

    # ----- text for {placeholders} -----------------------------------------

    def template_values(self) -> dict[str, dict[str, str]]:
        """Placeholder values per language for the rule and card templates."""
        names = load("crops")
        w = self.weather
        numbers = {
            "conf": f"{round(self.confidence * 100)}%",
            "rain": f"{w.rain_last_3_days_mm:.1f}" if w else "",
            "humidity": f"{w.avg_humidity_pct:.0f}" if w else "",
            "temp": f"{w.avg_temp_c:.0f}" if w else "",
            "rain_next": f"{(w.rain_next_3_days_mm or 0):.0f}" if w else "",
            "chance": f"{(w.max_rain_chance_next_3_days_pct or 0):.0f}" if w else "",
        }
        def name_in(table: dict, key: str, lang: str) -> str:
            entry = table.get(key, {})
            return LocalizedText(**entry).in_lang(lang) if entry else key

        values = {}
        for lang in SUPPORTED_LANGUAGES:
            values[lang] = {
                **numbers,
                "disease": self.top.name.in_lang(lang),
                "crop": name_in(names["crops"], self.crop.crop_type, lang),
                "stage": name_in(names["stages"], self.crop.stage.value, lang),
            }
        return values
