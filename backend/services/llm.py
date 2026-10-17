"""
Groq API client: chat completions (LLM) and Whisper speech-to-text (Component 9).

Groq's API is OpenAI-compatible, so plain HTTP with httpx is enough — no
extra SDK. The key comes from GROQ_API_KEY in `.env` (backend/config.py).

Models (chosen after a head-to-head test on grounded Hindi answers and
refusing a pesticide-dose question — see ROADMAP.md, Component 9):
- chat:     openai/gpt-oss-120b, falling back to qwen/qwen3.8-27b if the
            first is rate-limited or down
- speech:   whisper-large-v3 (good Hindi accuracy)
"""

from __future__ import annotations

import logging

import httpx

from backend import config

log = logging.getLogger("dharrakshak.llm")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
CHAT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
STT_TIMEOUT = httpx.Timeout(45.0, connect=5.0)
# Errors worth trying the fallback model for (rate limit, overload, server).
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class LLMUnavailable(RuntimeError):
    """No key configured, or Groq couldn't answer. Callers fall back gracefully."""


def _headers() -> dict[str, str]:
    key = config.groq_api_key()
    if not key:
        raise LLMUnavailable("GROQ_API_KEY is not set (add it to .env).")
    return {"Authorization": f"Bearer {key}"}


def chat_complete(messages: list[dict], max_tokens: int = 500, temperature: float = 0.3) -> tuple[str, str]:
    """Send a chat conversation and return (reply_text, model_used).

    Tries the main model, then the fallback model. Raises LLMUnavailable if
    neither answers.
    """
    headers = _headers()
    last_error = "no models tried"
    for model in dict.fromkeys([config.GROQ_CHAT_MODEL, config.GROQ_FALLBACK_MODEL]):  # unique, in order
        body = {"model": model, "messages": messages, "temperature": temperature, "max_completion_tokens": max_tokens}
        # Both models "think" before answering; keep that short and out of the reply.
        if model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        else:
            body["reasoning_format"] = "hidden"
        try:
            resp = httpx.post(f"{GROQ_BASE_URL}/chat/completions", json=body, headers=headers, timeout=CHAT_TIMEOUT)
        except httpx.HTTPError as err:
            last_error = f"{model}: {err}"
            log.warning("Chat request failed, trying fallback: %s", last_error)
            continue
        if resp.status_code in RETRYABLE_STATUS:
            last_error = f"{model}: HTTP {resp.status_code}"
            log.warning("Chat model busy/unavailable, trying fallback: %s", last_error)
            continue
        if resp.status_code != 200:
            raise LLMUnavailable(f"{model}: HTTP {resp.status_code} {resp.text[:200]}")
        text = (resp.json()["choices"][0]["message"].get("content") or "").strip()
        if text:
            return text, model
        last_error = f"{model}: empty reply"
    raise LLMUnavailable(last_error)


# Whisper sometimes "hears" words in noise or silence (e.g. a beep became
# "प्रस्तुति प्रस्तुति प्रस्तुति" in testing). Segments it rates as probably
# not speech are dropped, and a transcript that is one word repeated is
# treated as noise. An empty result makes the API answer "couldn't hear".
NO_SPEECH_THRESHOLD = 0.6


def clean_transcript(payload: dict) -> str:
    """Keep only segments Whisper believes contain speech (verbose_json)."""
    segments = payload.get("segments")
    if segments:
        text = " ".join(
            seg.get("text", "").strip()
            for seg in segments
            if (seg.get("no_speech_prob") or 0) < NO_SPEECH_THRESHOLD
        ).strip()
    else:
        text = (payload.get("text") or "").strip()
    words = [w.strip("।.,!?") for w in text.split()]
    if len(words) >= 2 and len({w.casefold() for w in words if w}) == 1:
        return ""  # the same word over and over = hallucination, not a question
    return text


def transcribe(audio: bytes, filename: str, content_type: str, lang: str | None = None) -> str:
    """Speech-to-text with Whisper. `lang` ("hi"/"en") improves accuracy.
    Returns "" when the recording seems to contain no real speech."""
    data = {"model": config.GROQ_STT_MODEL, "response_format": "verbose_json", "temperature": "0"}
    if lang in ("hi", "en"):
        data["language"] = lang
    try:
        resp = httpx.post(
            f"{GROQ_BASE_URL}/audio/transcriptions",
            headers=_headers(),
            data=data,
            files={"file": (filename, audio, content_type)},
            timeout=STT_TIMEOUT,
        )
    except httpx.HTTPError as err:
        raise LLMUnavailable(f"Speech-to-text request failed: {err}") from err
    if resp.status_code != 200:
        raise LLMUnavailable(f"Speech-to-text failed: HTTP {resp.status_code} {resp.text[:200]}")
    return clean_transcript(resp.json())
