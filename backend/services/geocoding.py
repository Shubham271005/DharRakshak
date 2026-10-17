"""
Location name → coordinates (Component 5).

Uses the free Open-Meteo Geocoding API (no API key):
    https://geocoding-api.open-meteo.com/v1/search?name=Sonipat&countryCode=IN

How a farmer's text is matched, e.g. "Sonipat, Haryana":
1. Split on commas → ["Sonipat", "Haryana"].
2. Search the first part (then the next part, if nothing is found).
3. Prefer a result whose state/district matches one of the other parts,
   otherwise take the most populous result.

Searches are limited to India (countryCode=IN) because the app is built for
Indian farmers. Results are cached in memory, so typing the same village
twice doesn't call the API twice.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import httpx

log = logging.getLogger("dharrakshak.geocoding")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
COUNTRY_CODE = "IN"
TIMEOUT = httpx.Timeout(8.0, connect=5.0)


class LocationNotFound(ValueError):
    """No place matched the farmer's text. The API returns 422."""


class GeocodingUnavailable(RuntimeError):
    """The geocoding service couldn't be reached. The API returns 503."""


@dataclass(frozen=True)
class Place:
    latitude: float
    longitude: float
    label: str  # e.g. "Sonīpat, Sonipat, Haryana" — handy for logs/debugging


def search(name: str, count: int = 5) -> list[dict]:
    """Raw Open-Meteo search. Kept separate so tests can replace it."""
    try:
        resp = httpx.get(
            GEOCODING_URL,
            params={"name": name, "count": count, "language": "en", "format": "json", "countryCode": COUNTRY_CODE},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPError as err:
        raise GeocodingUnavailable(f"Location lookup failed: {err}") from err
    return resp.json().get("results") or []


def _normalise(text: str) -> str:
    """'Sonīpat' → 'sonipat' (drop accents and case) for fuzzy comparison."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def _pick(results: list[dict], hints: list[str]) -> dict:
    """Prefer a result whose state/district matches a hint; else most populous."""
    norm_hints = [_normalise(h) for h in hints]
    for result in results:
        regions = [_normalise(result.get(k) or "") for k in ("admin1", "admin2", "admin3")]
        if any(h and any(h in r or r in h for r in regions if r) for h in norm_hints):
            return result
    return max(results, key=lambda r: r.get("population") or 0)


@lru_cache(maxsize=256)
def _geocode_cached(normalised_query: str) -> Place:
    """Look up an already-normalised query. Only successes are cached
    (lru_cache never stores a call that raised)."""
    parts = [p.strip() for p in normalised_query.split(",") if p.strip()]
    for i, part in enumerate(parts):
        results = search(part)
        if results:
            best = _pick(results, parts[:i] + parts[i + 1:])
            label = ", ".join(x for x in (best.get("name"), best.get("admin2"), best.get("admin1")) if x)
            return Place(latitude=best["latitude"], longitude=best["longitude"], label=label)
    raise LocationNotFound(normalised_query)


def geocode(location_name: str) -> Place:
    """Coordinates for a farmer-typed place name in India.

    Raises LocationNotFound (bad name) or GeocodingUnavailable (network).
    "Karnal", "karnal " and "Karnāl" share one cache entry; failures are
    never cached, so a retry after a network error can succeed.
    """
    text = location_name.strip()
    if not text:
        raise LocationNotFound("Please enter your village, town or district.")
    try:
        return _geocode_cached(_normalise(text))
    except LocationNotFound:
        raise LocationNotFound(
            f"Couldn't find '{text}'. Try the nearest town or district name, e.g. 'Sonipat, Haryana'."
        ) from None
