"""
Boundary-value and all-language tests for the rule engines (F3/F2/F4).

`tests/test_engines.py` covers realistic scenarios. This file covers the parts
that a scenario suite tends to miss:

- every threshold at, just below and just above its cut-off;
- all six supported languages, for every piece of text the farmer reads
  (including a check that the text was actually translated);
- the content loader's own failure modes (`{placeholder}` handling, unknown
  crop/stage keys).
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from backend.engines.actions import DISEASE_STEP_WEIGHTS, choose_cards, disease_steps
from backend.engines.content import _KeepMissing, fill, load, message, per_language
from backend.engines.explain import MAX_REASONS, build_explanation
from backend.engines.facts import Facts, thresholds
from backend.engines.risk import assess_risk, level_for
from backend.ml.classifier import load_labels
from shared.contract import (
    SUPPORTED_LANGUAGES,
    CropProfile,
    LocalizedText,
    Location,
    Weather,
    WeatherSource,
)

LABELS = {c.label: c for c in load_labels()}
TOMATO_BLIGHT = "Tomato___Early_blight"
TOMATO_HEALTHY = "Tomato___healthy"
SPIDER_MITES = "Tomato___Spider_mites"


def crop(stage: str = "flowering", crop_type: str = "tomato") -> CropProfile:
    return CropProfile(
        crop_id="c1", farmer_name="Test", crop_type=crop_type, sowing_date=date(2026, 8, 26),
        days_since_sowing=50, area_acres=1, stage=stage,
        location=Location(name="Sonipat", latitude=28.99, longitude=77.02),
    )


def weather(rain: float = 0.0, humidity: float = 50.0, temp: float = 24.0,
            rain_next: float | None = 0.0, chance: float | None = 0.0) -> Weather:
    return Weather(
        source=WeatherSource.open_meteo, rain_last_3_days_mm=rain, avg_humidity_pct=humidity,
        avg_temp_c=temp, rain_next_3_days_mm=rain_next, max_rain_chance_next_3_days_pct=chance,
        summary=LocalizedText(en="test", hi="परीक्षण"),
    )


def facts(label: str = TOMATO_BLIGHT, confidence: float = 0.9, uncertain: bool = False,
          mismatch: bool = False, wx: Weather | None = None, stage: str = "flowering",
          crop_type: str = "tomato") -> Facts:
    return Facts(crop=crop(stage, crop_type), top=LABELS[label], confidence=confidence,
                 uncertain=uncertain, crop_mismatch=mismatch, weather=wx)


def codes(risk) -> list[str]:
    return [r.code for r in risk.reasons]


# ---------------------------------------------------------------------------
# Thresholds — exactly at the cut-off, and just either side of it
# ---------------------------------------------------------------------------

T = thresholds()


def test_confidence_threshold_is_inclusive():
    assert facts(confidence=T["high_confidence"]).high_confidence is True
    assert facts(confidence=T["high_confidence"] - 0.0001).high_confidence is False


def test_confidence_threshold_decides_which_rule_fires():
    # Vegetative stage keeps the stage rule out of the way, so only the photo
    # rule differs between the two cases.
    at = assess_risk(facts(confidence=T["high_confidence"], wx=weather(), stage="vegetative"))
    below = assess_risk(facts(confidence=T["high_confidence"] - 0.01, wx=weather(), stage="vegetative"))
    assert codes(at) == ["disease_high_confidence"]
    assert codes(below) == ["disease_possible"]
    assert at.score - below.score == 1  # 3 points vs 2


@pytest.mark.parametrize("rain,humidity,expected", [
    (T["wet_recent_rain_mm"], 0.0, True),          # rain exactly at the cut-off
    (T["wet_recent_rain_mm"] - 0.1, 0.0, False),
    (0.0, T["wet_recent_humidity_pct"], True),     # humidity exactly at the cut-off
    (0.0, T["wet_recent_humidity_pct"] - 0.1, False),
    (0.0, 0.0, False),
])
def test_wet_recently_boundaries(rain, humidity, expected):
    assert facts(wx=weather(rain=rain, humidity=humidity)).wet_recently is expected


@pytest.mark.parametrize("rain_next,chance,expected", [
    (T["rain_forecast_mm"], 0.0, True),
    (T["rain_forecast_mm"] - 0.1, 0.0, False),
    (0.0, T["rain_forecast_chance_pct"], True),
    (0.0, T["rain_forecast_chance_pct"] - 1, False),
    (0.0, 0.0, False),
])
def test_rain_expected_boundaries(rain_next, chance, expected):
    assert facts(wx=weather(rain_next=rain_next, chance=chance)).rain_expected is expected


def test_missing_forecast_is_not_treated_as_zero_rain_but_is_not_rain_either():
    # The contract allows either forecast field to be None (older saved analyses).
    # Unknown must never count as "rain expected".
    w = weather(rain_next=None, chance=None)
    assert facts(wx=w).rain_expected is False
    assert facts(wx=w).wet_recently is False


def test_forecast_of_zero_rain_with_high_chance_still_counts_as_rain_expected():
    assert facts(wx=weather(rain_next=0.0, chance=95)).rain_expected is True


def test_hot_and_dry_needs_both_conditions():
    assert facts(label=SPIDER_MITES, wx=weather(temp=T["hot_dry_temp_c"],
                                                humidity=T["hot_dry_humidity_pct"] - 0.1)).hot_and_dry is True
    assert facts(label=SPIDER_MITES, wx=weather(temp=T["hot_dry_temp_c"] - 0.1,
                                                humidity=10)).hot_and_dry is False
    # Hot but humid is not "hot and dry".
    assert facts(label=SPIDER_MITES, wx=weather(temp=40, humidity=T["hot_dry_humidity_pct"])).hot_and_dry is False


def test_no_weather_disables_every_weather_question():
    f = facts(wx=None)
    assert f.wet_recently is False
    assert f.rain_expected is False
    assert f.hot_and_dry is False


@pytest.mark.parametrize("stage,sensitive", [
    ("flowering", True), ("fruiting", True),
    ("seedling", False), ("vegetative", False), ("maturity", False),
])
def test_sensitive_stage_covers_every_stage(stage, sensitive):
    assert facts(stage=stage).sensitive_stage is sensitive


def test_sensitive_stages_config_matches_the_contract_enum():
    from shared.contract import CropStage
    for stage in thresholds()["sensitive_stages"]:
        assert stage in {s.value for s in CropStage}, f"{stage} is not a real CropStage"


@pytest.mark.parametrize("score,level", [
    (0, "low"), (1, "low"), (2, "low"),
    (3, "moderate"), (4, "moderate"),
    (5, "elevated"), (6, "elevated"), (99, "elevated"),
])
def test_level_boundaries(score, level):
    assert level_for(score).value == level


# ---------------------------------------------------------------------------
# Facts edge cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("uncertain,healthy,detected,looks_healthy", [
    (True, False, False, False),   # an unclear photo confirms nothing
    (True, True, False, False),    # …not even "healthy"
    (False, False, True, False),
    (False, True, False, True),
])
def test_detected_and_healthy_are_mutually_exclusive(uncertain, healthy, detected, looks_healthy):
    label = TOMATO_HEALTHY if healthy else TOMATO_BLIGHT
    f = facts(label=label, uncertain=uncertain)
    assert f.disease_detected is detected
    assert f.looks_healthy is looks_healthy


def test_only_fungal_and_bacterial_react_to_weather():
    assert facts(label=TOMATO_BLIGHT).weather_sensitive_disease is True      # fungal
    assert facts(label="Pepper___Bacterial_spot").weather_sensitive_disease is True
    assert facts(label=SPIDER_MITES).weather_sensitive_disease is False      # pest
    assert facts(label="Tomato___Tomato_mosaic_virus").weather_sensitive_disease is False
    assert facts(label="Tomato___Yellow_Leaf_Curl_Virus").weather_sensitive_disease is False


def test_template_values_exist_in_all_six_languages():
    values = facts(wx=weather(**{"rain": 12.5, "humidity": 83.0, "temp": 27.4,
                                 "rain_next": 6.4, "chance": 71.0})).template_values()
    assert set(values) == set(SUPPORTED_LANGUAGES)
    for lang, mapping in values.items():
        assert mapping["conf"] == "90%", lang            # 0.9 → 90%
        assert mapping["rain"] == "12.5"
        assert mapping["humidity"] == "83"
        assert mapping["temp"] == "27"
        assert mapping["rain_next"] == "6"
        assert mapping["chance"] == "71"
        assert mapping["disease"].strip() and mapping["crop"].strip() and mapping["stage"].strip()
        assert not re.search(r"\{\w+\}", mapping["disease"])


def test_template_values_are_empty_strings_without_weather():
    # Empty, not "0": a missing reading must never be rendered as a measurement.
    values = facts(wx=None).template_values()
    for lang in SUPPORTED_LANGUAGES:
        for key in ("rain", "humidity", "temp", "rain_next", "chance"):
            assert values[lang][key] == "", (lang, key)


def test_template_values_fall_back_to_the_raw_key_for_an_unknown_crop():
    values = facts(crop_type="quinoa").template_values()
    assert values["en"]["crop"] == "quinoa"
    assert values["hi"]["crop"] == "quinoa"


def test_crop_name_is_localised_in_every_language():
    values = facts(crop_type="tomato").template_values()
    assert values["en"]["crop"].lower() == "tomato"
    assert values["hi"]["crop"] == "टमाटर"
    assert values["mr"]["crop"] == "टोमॅटो"
    assert values["pa"]["crop"] == "ਟਮਾਟਰ"
    # Haryanvi and Bhojpuri are Devanagari dialects and share Hindi's word for
    # this crop, so the six values are not all distinct. Recorded here because
    # the counts are only four, which is correct rather than a missing entry.
    assert values["bgc"]["crop"] == "टमाटर"
    assert values["bho"]["crop"] == "टमाटर"
    assert len({values[lang]["crop"] for lang in SUPPORTED_LANGUAGES}) == 4


# ---------------------------------------------------------------------------
# Risk engine — reason ordering, points and untranslated output
# ---------------------------------------------------------------------------

def test_reason_bag_is_fully_traceable_to_the_score():
    risk = assess_risk(facts(wx=weather(rain=30, humidity=90, rain_next=20, chance=90)))
    assert risk.score == sum(r.points for r in risk.reasons)
    assert risk.is_estimate is True


def test_unclear_photo_suppresses_weather_and_stage_points():
    # An unreadable photo must not accrue disease points from wet weather.
    risk = assess_risk(facts(confidence=0.2, uncertain=True,
                             wx=weather(rain=40, humidity=95, rain_next=30, chance=100)))
    assert codes(risk) == ["unclear_photo"]
    assert risk.score == 1


def test_healthy_leaf_gets_no_stage_points():
    risk = assess_risk(facts(label=TOMATO_HEALTHY, wx=weather()))
    assert "sensitive_stage" not in codes(risk)


def test_weather_unavailable_is_recorded_but_scores_nothing():
    risk = assess_risk(facts(wx=None))
    assert "weather_unavailable" in codes(risk)
    assert next(r.points for r in risk.reasons if r.code == "weather_unavailable") == 0


def test_crop_mismatch_scores_nothing_but_is_reported():
    risk = assess_risk(facts(mismatch=True, wx=weather()))
    mismatch = next(r for r in risk.reasons if r.code == "crop_mismatch")
    assert mismatch.points == 0


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_every_reason_is_translated_in_every_language(lang):
    risk = assess_risk(facts(wx=weather(rain=30, humidity=90, rain_next=20, chance=90)))
    assert risk.reasons
    for reason in risk.reasons:
        text = reason.text.in_lang(lang)
        assert text.strip()
        assert not re.search(r"\{\w+\}", text), f"{lang}: unfilled placeholder in {text!r}"


@pytest.mark.parametrize("lang", [x for x in SUPPORTED_LANGUAGES if x != "en"])
def test_no_reason_sentence_is_left_in_english(lang):
    """A translation that silently fell back to English would look complete."""
    values = facts(wx=weather(rain=30, humidity=90, rain_next=20, chance=90)).template_values()
    risk = assess_risk(facts(wx=weather(rain=30, humidity=90, rain_next=20, chance=90)))
    translated = [r.text.in_lang(lang) for r in risk.reasons]
    english = [r.text.en for r in risk.reasons]
    for lang_text, en_text in zip(translated, english):
        # The digits are shared; strip them and require a different sentence.
        assert re.sub(r"\d", "", lang_text) != re.sub(r"\d", "", en_text), (
            f"reason left in English for {lang}: {en_text!r}")


# ---------------------------------------------------------------------------
# Action cards
# ---------------------------------------------------------------------------

def test_disease_steps_are_absent_when_no_disease_is_detected():
    assert disease_steps(facts(label=TOMATO_HEALTHY)) == []
    assert disease_steps(facts(uncertain=True)) == []


def test_disease_steps_use_the_configured_weights():
    steps = disease_steps(facts())
    assert [w for w, _, _ in steps] == list(DISEASE_STEP_WEIGHTS)
    assert [card_id for _, card_id, _ in steps] == [f"{TOMATO_BLIGHT}:1", f"{TOMATO_BLIGHT}:2"]


def test_cards_are_numbered_without_gaps_whatever_fires():
    for label in LABELS:
        for wx in (None, weather(rain=30, humidity=90), weather(temp=35, humidity=20)):
            cards = choose_cards(facts(label=label, wx=wx))
            assert [c.priority for c in cards] == list(range(1, len(cards) + 1))
            assert len(cards) <= load("action_cards")["max_cards"]


def test_no_duplicate_card_ids():
    cards = choose_cards(facts(mismatch=True, wx=weather(rain=30, humidity=90, rain_next=9, chance=90)))
    ids = [c.card_id for c in cards]
    assert len(ids) == len(set(ids))


def test_generic_inspect_card_is_replaced_by_disease_specific_steps():
    cards = choose_cards(facts(wx=weather()))
    assert "inspect_nearby" not in [c.card_id for c in cards]
    assert f"{TOMATO_BLIGHT}:1" in [c.card_id for c in cards]


def test_retake_photo_beats_everything_else():
    cards = choose_cards(facts(uncertain=True, mismatch=True, wx=weather(rain=30, humidity=90)))
    assert cards[0].card_id == "retake_photo"


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_every_card_is_translated_in_every_language(lang):
    cards = choose_cards(facts(mismatch=True, wx=weather(rain=30, humidity=90, rain_next=9, chance=90)))
    assert cards
    for card in cards:
        for text in (card.title, card.detail, card.why):
            value = text.in_lang(lang)
            assert value.strip()
            assert not re.search(r"\{\w+\}", value), f"{lang}: {value!r}"


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------

def build(wx=None, **kwargs):
    f = facts(wx=wx, **kwargs)
    return f, build_explanation(f, assess_risk(f))


def test_explanation_keeps_the_three_strongest_reasons_in_rule_order():
    # 3 + 2 + 1 + 1 points: the weakest (sensitive_stage, last) is dropped, and
    # the survivors keep photo → weather order rather than points order.
    f, expl = build(wx=weather(rain=30, humidity=90, rain_next=20, chance=90))
    risk = assess_risk(f)
    assert len(risk.reasons) == 4 > MAX_REASONS
    summary = expl.summary.en
    assert "can help" in summary and ("wet weather" in summary.lower())
    assert summary.index("closely match") < summary.index("can help")
    dropped = risk.reasons[-1]
    assert dropped.code == "sensitive_stage"
    assert dropped.text.en not in summary


def test_explanation_never_keeps_more_than_max_reasons():
    f = facts(wx=weather(rain=30, humidity=90, rain_next=20, chance=90))
    risk = assess_risk(f)
    expl = build_explanation(f, risk)
    kept = [r for r in risk.reasons if r.text.en in expl.summary.en]
    assert len(kept) <= MAX_REASONS


@pytest.mark.parametrize("label,uncertain,expected_key", [
    (TOMATO_BLIGHT, False, "disease"),
    (TOMATO_HEALTHY, False, "healthy"),
    (TOMATO_BLIGHT, True, "uncertain"),
])
def test_verify_line_matches_the_situation(label, uncertain, expected_key):
    templates = load("action_cards")["explanation"]["verify"]
    _, expl = build(wx=weather(), label=label, uncertain=uncertain)
    assert expl.verify.en == templates[expected_key]["en"]


def test_disease_advice_is_attached_only_for_a_detected_disease():
    _, with_disease = build(wx=weather())
    assert with_disease.about is not None and with_disease.look_for is not None
    _, healthy = build(wx=weather(), label=TOMATO_HEALTHY)
    assert healthy.about is None and healthy.look_for is None
    _, unclear = build(wx=weather(), uncertain=True)
    assert unclear.about is None


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_explanation_is_complete_in_every_language(lang):
    _, expl = build(wx=weather(rain=30, humidity=90))
    for text in (expl.summary, expl.verify, expl.about, expl.look_for):
        if text is None:
            continue
        value = text.in_lang(lang)
        assert value.strip()
        assert not re.search(r"\{\w+\}", value)


@pytest.mark.parametrize("lang", [x for x in SUPPORTED_LANGUAGES if x != "en"])
def test_explanation_summary_is_not_left_in_english(lang):
    _, expl = build(wx=weather(rain=30, humidity=90))
    assert re.sub(r"[\d.%]", "", expl.summary.in_lang(lang)) != re.sub(r"[\d.%]", "", expl.summary.en)


def test_level_name_is_localised_inside_the_summary():
    # The level word in the summary must be the translated one, not the enum,
    # and it must be the level the score actually earned.
    scenarios = [weather(rain=30, humidity=90, rain_next=20, chance=90), weather(), None]
    seen = set()
    names = load("risk_rules")["levels"]["names"]
    for wx in scenarios:
        f = facts(wx=wx)
        risk = assess_risk(f)
        expl = build_explanation(f, risk)
        seen.add(risk.level.value)
        for lang in SUPPORTED_LANGUAGES:
            assert names[risk.level.value][lang] in expl.summary.in_lang(lang), (
                f"{lang}/{risk.level.value} missing from summary")
    assert len(seen) >= 2, "the scenarios should exercise more than one level"


# ---------------------------------------------------------------------------
# Content loader
# ---------------------------------------------------------------------------


def test_unknown_placeholder_stays_visible_instead_of_crashing():
    text = fill({"en": "Hello {name}", "hi": "नमस्ते {name}"}, {"en": {}, "hi": {}})
    assert text.en == "Hello {name}"
    assert text.hi == "नमस्ते {name}"


def test_keep_missing_only_substitutes_known_keys():
    mapping = _KeepMissing({"a": "A"})
    assert mapping["a"] == "A"
    assert mapping["b"] == "{b}"


def test_fill_falls_back_to_english_values_for_a_language_without_its_own():
    text = fill({"en": "Rain {rain} mm", "hi": "बारिश {rain} मिमी"},
                {"en": {"rain": "5"}})
    assert text.en == "Rain 5 mm"
    assert text.hi == "बारिश 5 मिमी"   # hi has no entry, so the English value is used


def test_fill_only_returns_languages_present_in_the_template():
    text = fill({"en": "x", "hi": "y"}, {})
    assert text.in_lang("mr") == "y"      # mr is absent → mr falls back to hi


def test_per_language_builds_one_entry_per_language():
    built = per_language(lambda lang: {"lang": lang})
    assert set(built) == set(SUPPORTED_LANGUAGES)
    assert all(built[lang]["lang"] == lang for lang in SUPPORTED_LANGUAGES)


def test_message_reads_from_messages_json():
    text = message("weather_source")
    assert text.en.strip() and text.hi.strip()


def test_every_message_is_translated_in_all_six_languages():
    for key, template in load("messages").items():
        if key.startswith("_"):
            continue
        assert set(SUPPORTED_LANGUAGES) <= set(template), f"{key} is missing a language"
        for lang in SUPPORTED_LANGUAGES:
            assert template[lang].strip(), f"{key}/{lang} is empty"
