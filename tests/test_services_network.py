"""
Unit tests for the two Open-Meteo clients that the rest of the suite fakes:
`services/weather.fetch_daily` and `services/geocoding.search`.

The parse/build/cache logic is covered in `test_weather.py`. What is left —
and what this file covers — is the HTTP boundary itself: which URL is called,
which parameters are sent, and how every failure mode is translated into the
service's own exception so callers can degrade gracefully.
"""

from __future__ import annotations

import httpx
import pytest

from backend.services import geocoding, weather

# `tests/conftest.py` replaces `weather.fetch_daily` and `geocoding.search` for
# every test so nothing touches the network. This file tests THOSE functions, so
# it keeps its own references to the real ones, captured before any fixture runs.
real_fetch_daily = weather.fetch_daily
real_search = geocoding.search


class FakeResponse:
    def __init__(self, status_code=200, payload=None, raise_for_status=None):
        self.status_code = status_code
        self._payload = payload
        self._raise = raise_for_status

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture
def get_calls(monkeypatch):
    """Replaces httpx.get once — both services import the same httpx module."""
    calls = []
    replies = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return replies.pop(0) if replies else FakeResponse(200, {})

    monkeypatch.setattr(httpx, "get", fake_get)
    return {"calls": calls, "replies": replies}


# ---------------------------------------------------------------------------
# weather.fetch_daily
# ---------------------------------------------------------------------------


def test_the_forecast_request_asks_for_three_past_and_four_forecast_days(get_calls):
    get_calls["replies"].append(FakeResponse(200, {"daily": {}}))
    real_fetch_daily(28.99, 77.02)
    call = get_calls["calls"][0]
    assert call["url"] == weather.FORECAST_URL
    params = call["params"]
    assert params["latitude"] == 28.99 and params["longitude"] == 77.02
    assert params["past_days"] == 3
    assert params["forecast_days"] == 4          # today + next 3
    assert params["timezone"] == "auto"          # the farmer's own calendar
    assert "precipitation_sum" in params["daily"]
    assert "precipitation_probability_max" in params["daily"]


def test_the_four_daily_variables_are_requested(get_calls):
    get_calls["replies"].append(FakeResponse(200, {"daily": {}}))
    real_fetch_daily(1.0, 1.0)
    assert set(get_calls["calls"][0]["params"]["daily"].split(",")) == {
        "precipitation_sum", "relative_humidity_2m_mean",
        "temperature_2m_mean", "precipitation_probability_max",
    }


@pytest.mark.parametrize("error", [
    httpx.ConnectError("no route"),
    httpx.ReadTimeout("slow"),
    httpx.HTTPStatusError("500", request=None, response=None),
])
def test_any_transport_failure_becomes_weather_unavailable(get_calls, error):
    get_calls["replies"].append(FakeResponse(raise_for_status=error))
    with pytest.raises(weather.WeatherUnavailable):
        real_fetch_daily(1.0, 1.0)


def test_a_non_json_body_is_not_swallowed_here(get_calls):
    # fetch_daily returns resp.json(); get_weather catches the ValueError.
    get_calls["replies"].append(FakeResponse(200, ValueError("not json")))
    with pytest.raises(ValueError):
        real_fetch_daily(1.0, 1.0)


def test_a_timeout_is_configured_so_a_hung_request_cannot_block_forever():
    assert weather.TIMEOUT.read is not None
    assert weather.TIMEOUT.connect is not None


# ---------------------------------------------------------------------------
# geocoding.search
# ---------------------------------------------------------------------------


def test_the_search_is_limited_to_india(get_calls):
    get_calls["replies"].append(FakeResponse(200, {"results": []}))
    real_search("Karnal")
    params = get_calls["calls"][0]["params"]
    assert call_url(get_calls) == geocoding.GEOCODING_URL
    assert params["name"] == "Karnal"
    assert params["countryCode"] == "IN"


def call_url(calls):
    return calls["calls"][0]["url"]


def test_a_result_list_is_returned_as_is(get_calls):
    results = [{"name": "Karnal", "latitude": 29.69, "longitude": 76.98}]
    get_calls["replies"].append(FakeResponse(200, {"results": results}))
    assert real_search("Karnal") == results


@pytest.mark.parametrize("payload", [{}, {"results": None}, {"results": []}])
def test_an_empty_response_is_an_empty_list(get_calls, payload):
    get_calls["replies"].append(FakeResponse(200, payload))
    assert real_search("Nowhere") == []


@pytest.mark.parametrize("error", [
    httpx.ConnectError("no route"),
    httpx.ReadTimeout("slow"),
    httpx.HTTPStatusError("503", request=None, response=None),
])
def test_any_transport_failure_becomes_geocoding_unavailable(get_calls, error):
    get_calls["replies"].append(FakeResponse(raise_for_status=error))
    with pytest.raises(geocoding.GeocodingUnavailable):
        real_search("Karnal")


# ---------------------------------------------------------------------------
# geocoding._pick / _normalise
# ---------------------------------------------------------------------------


def test_normalise_strips_accents_case_and_padding():
    assert geocoding._normalise("  Sonīpat ") == "sonipat"
    assert geocoding._normalise("KARNAL") == "karnal"


def test_a_matching_state_hint_wins_over_the_larger_population():
    results = [
        {"name": "Aurangabad", "admin1": "Maharashtra", "latitude": 19.88, "longitude": 75.34, "population": 1175116},
        {"name": "Aurangabad", "admin1": "Bihar", "latitude": 24.75, "longitude": 84.37, "population": 102244},
    ]
    assert geocoding._pick(results, ["Bihar"])["admin1"] == "Bihar"
    assert geocoding._pick(results, ["Maharashtra"])["admin1"] == "Maharashtra"


def test_without_a_usable_hint_the_most_populous_result_wins():
    results = [
        {"name": "A", "latitude": 1, "longitude": 1, "population": 10},
        {"name": "B", "latitude": 2, "longitude": 2, "population": 5000},
    ]
    assert geocoding._pick(results, ["Karnal"])["name"] == "B"


def test_a_result_with_no_population_field_is_still_usable():
    results = [{"name": "A", "latitude": 1, "longitude": 1},
               {"name": "B", "latitude": 2, "longitude": 2}]
    assert geocoding._pick(results, [])["name"] in ("A", "B")


def test_a_name_with_no_admin_fields_does_not_break_hint_matching():
    results = [{"name": "X", "latitude": 1, "longitude": 1, "population": 5}]
    assert geocoding._pick(results, ["Haryana"])["name"] == "X"


# ---------------------------------------------------------------------------
# Caching behaviour
# ---------------------------------------------------------------------------


def test_the_weather_cache_expires(monkeypatch):
    weather.clear_cache()
    calls = {"n": 0}

    def fake_fetch(lat, lon):
        calls["n"] += 1
        return {"daily": {
            "time": ["d"] * 7,
            "precipitation_sum": [0, 0, 0, 0, 0, 0, 0],
            "relative_humidity_2m_mean": [50] * 7,
            "temperature_2m_mean": [25] * 7,
            "precipitation_probability_max": [0] * 7,
        }}

    monkeypatch.setattr(weather, "fetch_daily", fake_fetch)
    weather.get_weather(28.99, 77.02)
    weather.get_weather(28.99, 77.02)
    assert calls["n"] == 1

    now = weather.time.monotonic()
    monkeypatch.setattr(weather.time, "monotonic", lambda: now + weather.CACHE_SECONDS + 1)
    weather.get_weather(28.99, 77.02)
    assert calls["n"] == 2
    weather.clear_cache()


def test_geocoding_successes_are_memoised(monkeypatch):
    geocoding._geocode_cached.cache_clear()
    calls = []

    def fake_search(name, count=5):
        calls.append(name)
        return [{"name": "Karnal", "admin1": "Haryana", "latitude": 29.69, "longitude": 76.98, "population": 1}]

    monkeypatch.setattr(geocoding, "search", fake_search)
    geocoding.geocode("Karnal")
    geocoding.geocode("KARNAL")
    geocoding.geocode("  Karnāl  ")
    assert calls == ["karnal"]
    geocoding._geocode_cached.cache_clear()


def test_an_empty_place_name_is_rejected_without_a_request(monkeypatch):
    geocoding._geocode_cached.cache_clear()
    calls = []
    monkeypatch.setattr(geocoding, "search", lambda name, count=5: calls.append(name) or [])
    with pytest.raises(geocoding.LocationNotFound, match="village"):
        geocoding.geocode("   ")
    assert calls == []


def test_a_failed_lookup_is_not_cached(monkeypatch):
    geocoding._geocode_cached.cache_clear()
    attempts = {"n": 0}

    def flaky(name, count=5):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise geocoding.GeocodingUnavailable("down")
        return [{"name": "Karnal", "latitude": 1.0, "longitude": 2.0, "population": 1}]

    monkeypatch.setattr(geocoding, "search", flaky)
    with pytest.raises(geocoding.GeocodingUnavailable):
        geocoding.geocode("Karnal")
    assert geocoding.geocode("Karnal").latitude == 1.0     # retry succeeds
    geocoding._geocode_cached.cache_clear()
