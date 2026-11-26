"""
Unit tests for the in-process rate limiter (backend/services/ratelimit.py).

The limiter protects the two Groq-backed endpoints and the CPU-bound analysis
endpoint. Because the clock is passed in, the window can be tested exactly
rather than by sleeping.
"""

from __future__ import annotations

import pytest

from backend.services import ratelimit


@pytest.fixture(autouse=True)
def clean():
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_a_fresh_client_is_allowed():
    ratelimit.check("chat", "1.1.1.1")


def test_the_per_client_budget_is_enforced():
    limit = ratelimit.LIMITS["chat"][0]
    for _ in range(limit):
        ratelimit.check("chat", "1.1.1.1")
    with pytest.raises(ratelimit.RateLimited):
        ratelimit.check("chat", "1.1.1.1")


def test_one_client_does_not_consume_another_clients_budget():
    limit = ratelimit.LIMITS["chat"][0]
    for _ in range(limit):
        ratelimit.check("chat", "1.1.1.1")
    ratelimit.check("chat", "2.2.2.2")          # must not raise


def test_buckets_are_independent():
    limit = ratelimit.LIMITS["analyze"][0]
    for _ in range(limit):
        ratelimit.check("analyze", "1.1.1.1")
    ratelimit.check("chat", "1.1.1.1")          # a different bucket is unaffected


def test_the_window_slides():
    limit = ratelimit.LIMITS["chat"][0]
    start = 1000.0
    for i in range(limit):
        ratelimit.check("chat", "1.1.1.1", now=start + i * 0.1)
    with pytest.raises(ratelimit.RateLimited):
        ratelimit.check("chat", "1.1.1.1", now=start + 1.0)
    # One window after the FIRST call expires, a slot is free again.
    ratelimit.check("chat", "1.1.1.1", now=start + ratelimit.WINDOW_SECONDS + 0.01)


def test_retry_after_is_the_time_until_the_oldest_call_expires():
    start = 100.0
    ratelimit.check("analyze", "1.1.1.1", now=start)
    for _ in range(ratelimit.LIMITS["analyze"][0] - 1):
        ratelimit.check("analyze", "1.1.1.1", now=start)
    with pytest.raises(ratelimit.RateLimited) as err:
        ratelimit.check("analyze", "1.1.1.1", now=start + 10)
    assert err.value.retry_after == pytest.approx(ratelimit.WINDOW_SECONDS - 10)


def test_the_global_limit_stops_a_client_that_keeps_changing_its_address():
    """A forged X-Forwarded-For buys a bypass of the per-client limit only."""
    overall = ratelimit.LIMITS["transcribe"][1]
    with pytest.raises(ratelimit.RateLimited):
        for i in range(overall + 1):
            ratelimit.check("transcribe", f"10.0.0.{i}")


def test_a_rate_limited_attempt_still_raises_for_a_new_address_at_the_global_cap():
    overall = ratelimit.LIMITS["analyze"][1]
    for i in range(overall):
        ratelimit.check("analyze", f"10.0.{i // 250}.{i % 250}")
    with pytest.raises(ratelimit.RateLimited):
        ratelimit.check("analyze", "172.16.0.1")


# ---------------------------------------------------------------------------
# Client identification behind a proxy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host,forwarded,expected", [
    ("10.0.0.1", "203.0.113.5", "203.0.113.5"),            # real client behind the proxy
    ("10.0.0.1", "203.0.113.5, 70.41.3.18", "203.0.113.5"),  # first entry is the client
    ("10.0.0.1", None, "10.0.0.1"),
    ("10.0.0.1", "", "10.0.0.1"),
    ("10.0.0.1", "   ", "10.0.0.1"),
    (None, None, "unknown"),
])
def test_client_key(host, forwarded, expected):
    assert ratelimit.client_key(host, forwarded) == expected


# ---------------------------------------------------------------------------
# Switches and housekeeping
# ---------------------------------------------------------------------------


def test_the_limiter_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("DHARRAKSHAK_RATE_LIMIT", "0")
    assert ratelimit.enabled() is False
    for _ in range(ratelimit.LIMITS["chat"][0] * 3):
        ratelimit.check("chat", "1.1.1.1")       # never raises


def test_the_limiter_is_on_by_default(monkeypatch):
    monkeypatch.delenv("DHARRAKSHAK_RATE_LIMIT", raising=False)
    assert ratelimit.enabled() is True


def test_reset_clears_every_counter():
    for _ in range(ratelimit.LIMITS["chat"][0]):
        ratelimit.check("chat", "1.1.1.1")
    ratelimit.reset()
    ratelimit.check("chat", "1.1.1.1")


def test_the_table_is_cleared_rather_than_growing_without_bound(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_KEYS", 3)
    ratelimit.check("chat", "a")
    ratelimit.check("chat", "b")
    ratelimit.check("chat", "c")
    ratelimit.check("chat", "d")      # over the cap → table cleared first
    assert len(ratelimit._hits) <= 3


def test_measured_limits_match_the_documented_table():
    assert ratelimit.LIMITS["analyze"] == (30, 200)
    assert ratelimit.LIMITS["chat"] == (30, 200)
    assert ratelimit.LIMITS["transcribe"] == (15, 100)
    for per_client, overall in ratelimit.LIMITS.values():
        assert per_client <= overall, "a single client must never be able to use the whole budget"
