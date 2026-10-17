"""
Real weather for the crop's location (Component 5).

Uses the free Open-Meteo Forecast API (no API key). One call returns daily
values for the 3 days before today, today, and the next 3 days:

    precipitation_sum               mm of rain per day
    relative_humidity_2m_mean       average humidity, %
    temperature_2m_mean             average temperature, °C
    precipitation_probability_max   highest chance of rain that day, %

From that we build the contract's `Weather`:
- last 3 days: total rain, average humidity, average temperature
- next 3 days: total expected rain, highest chance of rain
- a short EN/HI summary for the farmer

Honesty rule: if Open-Meteo can't be reached, `get_weather` returns None
(the analysis says weather is unavailable). It never invents numbers.
Results are cached for 30 minutes per location.
"""

from __future__ import annotations

import logging
import threading
import time

import httpx

from backend.engines.content import message, per_language
from shared.contract import LocalizedText, Weather, WeatherSource

log = logging.getLogger("dharrakshak.weather")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_VARIABLES = "precipitation_sum,relative_humidity_2m_mean,temperature_2m_mean,precipitation_probability_max"
PAST_DAYS = 3
FORECAST_DAYS = 4  # today + next 3 days
TIMEOUT = httpx.Timeout(8.0, connect=5.0)
CACHE_SECONDS = 30 * 60

_cache: dict[tuple[float, float], tuple[float, Weather]] = {}
_cache_lock = threading.Lock()


class WeatherUnavailable(RuntimeError):
    """Open-Meteo couldn't be reached or returned unusable data."""


def fetch_daily(latitude: float, longitude: float) -> dict:
    """Raw Open-Meteo response. Kept separate so tests can replace it."""
    try:
        resp = httpx.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": DAILY_VARIABLES,
                "past_days": PAST_DAYS,
                "forecast_days": FORECAST_DAYS,
                "timezone": "auto",  # days follow the farmer's local calendar
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPError as err:
        raise WeatherUnavailable(f"Weather request failed: {err}") from err
    return resp.json()


def _values(daily: dict, key: str, start: int, end: int) -> list[float]:
    """Non-missing values of one daily variable for days [start, end)."""
    return [v for v in (daily.get(key) or [])[start:end] if v is not None]


def build_summary(rain_past: float, humidity: float, temp: float,
                  rain_next: float | None, chance_next: float | None) -> LocalizedText:
    """Farmer-friendly summary in every language (sentences: shared/content/messages.json)."""
    numbers = {
        "rain": f"{rain_past:.1f}", "humidity": f"{humidity:.0f}", "temp": f"{temp:.0f}",
        "rain_next": f"{(rain_next or 0):.0f}", "chance": f"{(chance_next or 0):.0f}",
    }
    parts = [message("weather_past", per_language(lambda lang: numbers))]
    if rain_next is not None:
        if rain_next < 1 and (chance_next or 0) < 30:
            parts.append(message("weather_next_dry"))
        elif rain_next < 1:
            parts.append(message("weather_next_light", per_language(lambda lang: numbers)))  # showers possible
        else:
            parts.append(message("weather_next_rain", per_language(lambda lang: numbers)))
    parts.append(message("weather_source"))
    langs = set.intersection(*(set(p.model_dump()) for p in parts))
    return LocalizedText(**{lang: " ".join(p.in_lang(lang) for p in parts) for lang in langs})


def parse_weather(payload: dict) -> Weather:
    """Turn an Open-Meteo response into the contract's Weather (pure function)."""
    daily = payload.get("daily") or {}
    days = len(daily.get("time") or [])
    if days < PAST_DAYS + 1:
        raise WeatherUnavailable("Weather response had too few days.")
    today = PAST_DAYS  # index of today: past days come first

    rain_past = _values(daily, "precipitation_sum", 0, today)
    humidity = _values(daily, "relative_humidity_2m_mean", 0, today)
    temps = _values(daily, "temperature_2m_mean", 0, today)
    if not (rain_past and humidity and temps):
        raise WeatherUnavailable("Weather response was missing recent values.")

    rain_next_vals = _values(daily, "precipitation_sum", today + 1, today + 4)
    chance_vals = _values(daily, "precipitation_probability_max", today + 1, today + 4)
    rain_next = round(sum(rain_next_vals), 1) if rain_next_vals else None
    chance_next = max(chance_vals) if chance_vals else None

    rain_total = round(sum(rain_past), 1)
    avg_humidity = round(sum(humidity) / len(humidity), 1)
    avg_temp = round(sum(temps) / len(temps), 1)
    return Weather(
        source=WeatherSource.open_meteo,
        rain_last_3_days_mm=rain_total,
        avg_humidity_pct=avg_humidity,
        avg_temp_c=avg_temp,
        rain_next_3_days_mm=rain_next,
        max_rain_chance_next_3_days_pct=chance_next,
        summary=build_summary(rain_total, avg_humidity, avg_temp, rain_next, chance_next),
    )


def get_weather(latitude: float, longitude: float) -> Weather | None:
    """Weather for a location, or None if it can't be fetched right now."""
    key = (round(latitude, 2), round(longitude, 2))  # ~1 km grid: nearby farms share a cache entry
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < CACHE_SECONDS:
            return cached[1]
    try:
        weather = parse_weather(fetch_daily(*key))
    except (WeatherUnavailable, ValueError) as err:
        log.warning("Weather unavailable for %s: %s", key, err)
        return None
    with _cache_lock:
        _cache[key] = (now, weather)
    return weather


def clear_cache() -> None:
    """Used by tests."""
    with _cache_lock:
        _cache.clear()
