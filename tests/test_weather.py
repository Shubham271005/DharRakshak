"""
Tests for weather + geocoding (Component 5). The network is faked by the
autouse `fake_open_meteo` fixture in conftest.py.
"""

import copy

import pytest

from backend.services import geocoding, weather
from tests.conftest import OPEN_METEO_DAILY

# ----- weather parsing -------------------------------------------------------


def test_parse_uses_three_past_days_and_three_forecast_days():
    w = weather.parse_weather(OPEN_METEO_DAILY)
    assert w.source.value == "open_meteo"
    assert w.rain_last_3_days_mm == 27.7                      # 27.0 + 0.7 + 0.0
    assert w.avg_humidity_pct == pytest.approx(80.3, abs=0.1)  # (87 + 81 + 73) / 3
    assert w.avg_temp_c == pytest.approx(23.3, abs=0.1)
    assert w.rain_next_3_days_mm == 6.5                        # 2.5 + 4.0 + 0.0 (today excluded)
    assert w.max_rain_chance_next_3_days_pct == 65


def test_summary_is_bilingual_and_cites_source():
    w = weather.parse_weather(OPEN_METEO_DAILY)
    assert "27.7 mm rain" in w.summary.en and "Open-Meteo" in w.summary.en
    assert "मिमी बारिश" in w.summary.hi
    assert "about 6 mm rain expected (up to 65% chance)" in w.summary.en


def test_summary_says_little_rain_when_dry_ahead():
    dry = copy.deepcopy(OPEN_METEO_DAILY)
    dry["daily"]["precipitation_sum"][4:] = [0.0, 0.0, 0.0]
    dry["daily"]["precipitation_probability_max"][4:] = [5, 10, 0]
    assert "little or no rain expected" in weather.parse_weather(dry).summary.en


def test_summary_light_rain_possible_when_chance_but_little_rain():
    showery = copy.deepcopy(OPEN_METEO_DAILY)
    showery["daily"]["precipitation_sum"][4:] = [0.2, 0.0, 0.3]
    showery["daily"]["precipitation_probability_max"][4:] = [39, 20, 10]
    summary = weather.parse_weather(showery).summary
    assert "light rain possible (up to 39% chance)" in summary.en
    assert "about 0 mm" not in summary.en
    assert "हल्की बारिश संभव" in summary.hi


def test_missing_values_are_skipped_not_treated_as_zero():
    gappy = copy.deepcopy(OPEN_METEO_DAILY)
    gappy["daily"]["relative_humidity_2m_mean"][0] = None
    assert weather.parse_weather(gappy).avg_humidity_pct == 77.0  # (81 + 73) / 2


def test_unusable_response_raises():
    with pytest.raises(weather.WeatherUnavailable):
        weather.parse_weather({"daily": {"time": ["2026-10-18"]}})


# ----- get_weather: caching and outages ----------------------------------------


def test_get_weather_caches_per_location(fake_open_meteo):
    weather.get_weather(28.99, 77.02)
    weather.get_weather(28.991, 77.019)   # same ~1 km grid cell
    assert fake_open_meteo.weather_calls == 1
    weather.get_weather(29.69, 76.98)     # different place
    assert fake_open_meteo.weather_calls == 2


def test_outage_returns_none_and_is_not_cached(fake_open_meteo):
    fake_open_meteo.down = True
    assert weather.get_weather(28.99, 77.02) is None
    fake_open_meteo.down = False
    assert weather.get_weather(28.99, 77.02) is not None  # recovers on retry


# ----- geocoding --------------------------------------------------------------


def test_geocode_simple_name():
    place = geocoding.geocode("Karnal")
    assert (place.latitude, place.longitude) == (29.69, 76.98)


def test_geocode_ignores_accents_and_uses_state_hint():
    # "Aurangabad" exists in Maharashtra (bigger) and Bihar; the hint picks Bihar.
    assert geocoding.geocode("Aurangabad, Bihar").latitude == 24.75
    assert geocoding.geocode("Aurangabad").latitude == 19.88  # no hint: most populous


def test_geocode_falls_back_to_next_part(fake_open_meteo):
    # Unknown village, known district → found via the second part.
    place = geocoding.geocode("Chhotagaon, Sonipat")
    assert place.latitude == 28.99
    assert fake_open_meteo.geocode_calls == ["chhotagaon", "sonipat"]


def test_geocode_unknown_place_raises_helpful_error():
    with pytest.raises(geocoding.LocationNotFound, match="nearest town or district"):
        geocoding.geocode("Atlantis")


def test_geocode_results_are_cached(fake_open_meteo):
    geocoding.geocode("Karnal")
    geocoding.geocode("karnal ")
    geocoding.geocode("Karnāl")
    assert fake_open_meteo.geocode_calls == ["karnal"]


def test_geocode_outage_is_not_cached(fake_open_meteo):
    fake_open_meteo.down = True
    with pytest.raises(geocoding.GeocodingUnavailable):
        geocoding.geocode("Karnal")
    fake_open_meteo.down = False
    assert geocoding.geocode("Karnal").latitude == 29.69
