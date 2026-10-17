"""
Scenario tests for the risk / action-card / explanation engines (Component 6).

Each test builds one realistic situation and checks the risk level, the
reasons, the cards and the explanation — exactly what a farmer would see.
"""

import json
import re
from datetime import date

import pytest

from backend.engines.actions import ELIGIBLE, choose_cards
from backend.engines.content import CONTENT_DIR, load
from backend.engines.explain import build_explanation
from backend.engines.facts import Facts
from backend.engines.risk import assess_risk
from backend.ml.classifier import load_labels
from shared.contract import CropProfile, LocalizedText, Location, Weather, WeatherSource

LABELS = {c.label: c for c in load_labels()}


def crop(stage="flowering", crop_type="tomato") -> CropProfile:
    return CropProfile(
        crop_id="c1", farmer_name="Test", crop_type=crop_type, sowing_date=date(2026, 8, 26),
        days_since_sowing=50, area_acres=1, stage=stage,
        location=Location(name="Sonipat", latitude=28.99, longitude=77.02),
    )


def weather(rain=0.0, humidity=50.0, temp=24.0, rain_next=0.0, chance=0.0) -> Weather:
    return Weather(
        source=WeatherSource.open_meteo, rain_last_3_days_mm=rain, avg_humidity_pct=humidity,
        avg_temp_c=temp, rain_next_3_days_mm=rain_next, max_rain_chance_next_3_days_pct=chance,
        summary=LocalizedText(en="test", hi="परीक्षण"),
    )


WET = dict(rain=27.7, humidity=85, rain_next=8, chance=70)
DRY = dict(rain=0, humidity=45, rain_next=0, chance=5)


def analyse(label, confidence=0.9, uncertain=False, mismatch=False, wx=None, stage="flowering"):
    facts = Facts(crop=crop(stage), top=LABELS[label], confidence=confidence, uncertain=uncertain,
                  crop_mismatch=mismatch, weather=wx)
    risk = assess_risk(facts)
    return risk, choose_cards(facts), build_explanation(facts, risk)


def codes(risk):
    return [r.code for r in risk.reasons]


def card_ids(cards):
    return [c.card_id for c in cards]


# ----- scenarios -----------------------------------------------------------------


def test_fungal_disease_in_wet_weather_at_flowering_is_elevated():
    risk, cards, expl = analyse("Tomato___Early_blight", 0.9, wx=weather(**WET))
    assert risk.level.value == "elevated"
    assert codes(risk) == ["disease_high_confidence", "wet_recent_disease", "rain_forecast_disease", "sensitive_stage"]
    assert risk.score == 3 + 2 + 1 + 1
    assert card_ids(cards) == ["inspect_nearby", "check_local_guidance", "keep_leaves_dry"]
    assert "27.7 mm rain" in risk.reasons[1].text.en
    assert "not a confirmed diagnosis" in expl.verify.en


def test_same_disease_in_dry_weather_at_vegetative_stage_is_moderate():
    risk, cards, _ = analyse("Tomato___Early_blight", 0.9, wx=weather(**DRY), stage="vegetative")
    assert risk.level.value == "moderate"          # 3 points: photo only
    assert "keep_leaves_dry" not in card_ids(cards)


def test_low_confidence_disease_uses_softer_wording():
    risk, _, _ = analyse("Tomato___Early_blight", 0.62, wx=weather(**DRY), stage="vegetative")
    assert codes(risk) == ["disease_possible"]
    assert "may match" in risk.reasons[0].text.en
    assert risk.level.value == "low"


def test_healthy_leaf_in_dry_weather_is_low():
    risk, cards, expl = analyse("Tomato___healthy", 0.97, wx=weather(**DRY))
    assert risk.level.value == "low" and risk.score == 0
    assert card_ids(cards) == ["keep_monitoring", "recheck_photo"]
    assert "look healthy early in an infection" in expl.verify.en


def test_healthy_leaf_in_wet_weather_gets_preventive_advice():
    risk, cards, _ = analyse("Tomato___healthy", 0.97, wx=weather(**WET))
    assert codes(risk) == ["looks_healthy", "wet_recent_healthy"]
    assert risk.level.value == "low"
    assert card_ids(cards) == ["keep_monitoring", "keep_leaves_dry", "recheck_photo"]
    # Reasons keep the natural order: what the photo shows first, then weather.
    summary = analyse("Tomato___healthy", 0.97, wx=weather(**WET))[2].summary.en
    assert summary.index("looks healthy") < summary.index("wet weather")


def test_unclear_photo_puts_retake_first():
    risk, cards, expl = analyse("Tomato___Early_blight", 0.3, uncertain=True, wx=weather(**WET))
    assert codes(risk) == ["unclear_photo"]        # no disease-specific weather points
    assert risk.level.value == "low"
    assert card_ids(cards)[0] == "retake_photo"
    assert "not reliable" in expl.verify.en


def test_spider_mites_in_hot_dry_weather():
    risk, cards, _ = analyse("Tomato___Spider_mites", 0.85, wx=weather(temp=33, humidity=40))
    assert "hot_dry_pest" in codes(risk)
    assert risk.level.value == "elevated"          # 3 + 2 + 1 (flowering)
    assert "check_undersides" in card_ids(cards)


def test_spider_mites_not_boosted_by_rain():
    risk, _, _ = analyse("Tomato___Spider_mites", 0.85, wx=weather(**WET))
    assert "wet_recent_disease" not in codes(risk)


def test_insect_spread_virus_suggests_checking_insects():
    _, cards, _ = analyse("Tomato___Yellow_Leaf_Curl_Virus", 0.9, wx=weather(**DRY))
    assert "check_insects" in card_ids(cards)


def test_contact_virus_suggests_hygiene():
    # Mosaic: inspect (90) and guidance (80) outrank clean_tools (75) in a top-3 of 3.
    _, cards, _ = analyse("Tomato___Tomato_mosaic_virus", 0.9, wx=weather(**DRY))
    assert card_ids(cards) == ["inspect_nearby", "check_local_guidance", "clean_tools"]


def test_crop_mismatch_card_comes_first_and_names_the_crop():
    risk, cards, _ = analyse("Potato___Late_blight", 0.9, mismatch=True, wx=weather(**DRY))
    assert "crop_mismatch" in codes(risk)
    assert cards[0].card_id == "check_crop"
    assert "tomato" in cards[0].detail.en and "टमाटर" in cards[0].detail.hi


def test_missing_weather_is_said_out_loud():
    risk, cards, expl = analyse("Tomato___Early_blight", 0.9, wx=None)
    assert "weather_unavailable" in codes(risk)
    assert "keep_leaves_dry" not in card_ids(cards)
    assert "Weather data was unavailable" in expl.summary.en


# ----- invariants over every class and situation ----------------------------------


@pytest.mark.parametrize("label", sorted(LABELS))
@pytest.mark.parametrize("wx", [None, "wet", "dry", "hot"])
@pytest.mark.parametrize("uncertain", [False, True])
def test_every_class_produces_valid_bilingual_output(label, wx, uncertain):
    w = {None: None, "wet": weather(**WET), "dry": weather(**DRY), "hot": weather(temp=34, humidity=35)}[wx]
    risk, cards, expl = analyse(label, 0.4 if uncertain else 0.9, uncertain=uncertain, wx=w)
    assert 1 <= len(cards) <= load("action_cards")["max_cards"]
    assert [c.priority for c in cards] == list(range(1, len(cards) + 1))
    for text in [r.text for r in risk.reasons] + [c.title for c in cards] + [c.detail for c in cards] + \
                [c.why for c in cards] + [expl.summary, expl.verify]:
        for value in (text.en, text.hi):
            assert value.strip()
            assert not re.search(r"\{\w+\}", value), f"unfilled placeholder in: {value}"


def test_every_card_has_a_condition_and_vice_versa():
    assert set(ELIGIBLE) == set(load("action_cards")["cards"])


BANNED = [
    r"\bpesticide", r"\bfungicide", r"\binsecticide", r"\bspray", r"\bdose\b", r"\bdosage", r"\bml\b",
    r"\bgrams?\b", r"\bmancozeb", r"\bcopper\b", r"\bneem oil",
    "कीटनाशक", "फफूंदनाशक", "छिड़काव", "खुराक", "दवा",
]


@pytest.mark.parametrize("name", ["action_cards", "risk_rules"])
def test_no_treatment_or_dose_advice_anywhere(name):
    # Everything farmer-facing except the "_about"/"when" notes for developers.
    data = json.loads((CONTENT_DIR / f"{name}.json").read_text(encoding="utf-8"))

    def farmer_text(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key not in ("_about", "when"):
                    yield from farmer_text(value)
        elif isinstance(node, list):
            for item in node:
                yield from farmer_text(item)
        elif isinstance(node, str):
            yield node

    for text in farmer_text(data):
        for pattern in BANNED:
            assert not re.search(pattern, text, re.IGNORECASE), f"banned term {pattern!r} in: {text}"


def test_hindi_templates_never_put_a_disease_name_before_a_postposition():
    # "{disease}" expands to phrases like "अंगूर का काला सड़न"; directly before
    # से / को / के / में the "का" would need to change form ("के"), so templates
    # must phrase around it, e.g. "इस समस्या ({disease}) को".
    # Checks the Hindi ("hi") texts only — other languages have their own grammar.
    def hindi_texts(node):
        if isinstance(node, dict):
            if isinstance(node.get("hi"), str):
                yield node["hi"]
            for key, value in node.items():
                if key != "hi":
                    yield from hindi_texts(value)
        elif isinstance(node, list):
            for item in node:
                yield from hindi_texts(item)

    for name in ("action_cards", "risk_rules"):
        data = json.loads((CONTENT_DIR / f"{name}.json").read_text(encoding="utf-8"))
        for text in hindi_texts(data):
            assert not re.search(r"\{disease\}\s*(से|को|के|में|जैसे)", text), f"{name}: {text}"
