"""
In-process rate limiting for the endpoints that cost money or CPU.

Three routes are expensive and reachable by anyone:

    POST /api/crops/{id}/analyze   saturates a CPU for a second or more
    POST /api/chat                 spends Groq credits on every call
    POST /api/voice/transcribe     spends Groq credits on every call

Without a limit, one client can drain the API key or make the free-tier server
unusable for every other farmer. Both limits are applied together:

- PER-CLIENT — N calls per window, keyed on the caller's address.
- GLOBAL — a backstop per bucket, so a spoofed ``X-Forwarded-For`` buys a
  bypass of the per-client limit but not unlimited calls.

This is deliberately in-process: a dict of timestamps behind one lock. It
resets on restart and is not shared between worker processes, so it is a cheap
guard against casual abuse and runaway clients — not an authentication or
security boundary. Real protection needs a shared store (Redis) and per-user
accounts, neither of which this MVP has.

Set ``DHARRAKSHAK_RATE_LIMIT=0`` to switch it off (tests do this).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque

log = logging.getLogger("dharrakshak.ratelimit")

WINDOW_SECONDS = 60.0

# bucket -> (calls per client per window, calls per window across all clients)
LIMITS: dict[str, tuple[int, int]] = {
    "analyze": (30, 200),
    "chat": (30, 200),
    "transcribe": (15, 100),
}

# Beyond this many tracked keys the table is cleared. Keeps a stream of
# invented X-Forwarded-For values from growing memory without bound.
MAX_KEYS = 4096

_hits: dict[tuple[str, str], deque[float]] = {}
_lock = threading.Lock()


class RateLimited(Exception):
    """The caller has used up its budget for this window. The API returns 429."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limited, retry in {retry_after:.0f}s")
        self.retry_after = retry_after


def enabled() -> bool:
    return os.getenv("DHARRAKSHAK_RATE_LIMIT", "1") != "0"


def client_key(host: str | None, forwarded_for: str | None) -> str:
    """Who is calling.

    ``X-Forwarded-For`` is read because the app runs behind Render's/Vercel's
    proxy, where ``request.client.host`` is the proxy's address for every
    farmer. The first entry is the original client. A client can forge this
    header, which is exactly why the global limit exists as well.
    """
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return host or "unknown"


def _take(key: tuple[str, str], limit: int, now: float) -> float | None:
    """Record one call. None if allowed, else seconds until a slot frees up."""
    cutoff = now - WINDOW_SECONDS
    queue = _hits.setdefault(key, deque())
    while queue and queue[0] <= cutoff:
        queue.popleft()
    if len(queue) >= limit:
        return max(0.0, queue[0] + WINDOW_SECONDS - now)
    queue.append(now)
    return None


def check(bucket: str, client: str, now: float | None = None) -> None:
    """Count one call against both limits. Raises RateLimited when over."""
    if not enabled():
        return
    per_client, overall = LIMITS[bucket]
    now = time.monotonic() if now is None else now
    with _lock:
        if len(_hits) > MAX_KEYS:
            # Oldest-first eviction is not worth tracking; start clean instead.
            _hits.clear()
        wait = _take((bucket, f"client:{client}"), per_client, now)
        if wait is None:
            wait = _take((bucket, "*"), overall, now)
    if wait is not None:
        log.warning("Rate limited %s on %s (retry in %.0fs)", client, bucket, wait)
        raise RateLimited(wait)


def reset() -> None:
    """Forget every counter. Used by tests."""
    with _lock:
        _hits.clear()
