"""
Unit tests for the Groq HTTP client (backend/services/llm.py).

No network: `httpx.post` is replaced, so every status code and body shape can
be exercised — especially the ones that used to leak a 500 to the farmer.
"""

from __future__ import annotations

import httpx
import pytest

from backend import config
from backend.services import llm

# `tests/conftest.py` replaces `llm.chat_complete` and `llm.transcribe` with a
# fake for every test, so that no test touches the network. This file is the
# one that tests THOSE functions, so it holds its own references to the real
# implementations — captured at import, before any fixture patches anything.
real_chat_complete = llm.chat_complete
real_transcribe = llm.transcribe


class FakeResponse:
    def __init__(self, status_code=200, payload=None, raise_on_json=False, text="{}"):
        self.status_code = status_code
        self._payload = payload
        self._raise_on_json = raise_on_json
        self.text = text

    def json(self):
        if self._raise_on_json:
            raise ValueError("not json")
        return self._payload


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(config, "groq_api_key", lambda: "test-key")
    monkeypatch.setattr(config, "GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(config, "GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b")
    monkeypatch.setattr(config, "GROQ_STT_MODEL", "whisper-large-v3")


@pytest.fixture
def post_calls(monkeypatch):
    """Records every httpx.post and replies with a queued FakeResponse."""
    calls = []
    replies = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        reply = replies.pop(0) if replies else FakeResponse(200, chat_body("default"))
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    return {"calls": calls, "replies": replies}


def chat_body(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


# ---------------------------------------------------------------------------
# Headers / configuration
# ---------------------------------------------------------------------------


def test_a_missing_key_raises_before_any_request(monkeypatch, post_calls):
    monkeypatch.setattr(config, "groq_api_key", lambda: None)
    with pytest.raises(llm.LLMUnavailable, match="GROQ_API_KEY"):
        real_chat_complete([{"role": "user", "content": "hi"}])
    assert post_calls["calls"] == []


def test_the_key_is_sent_as_a_bearer_token(post_calls):
    real_chat_complete([{"role": "user", "content": "hi"}])
    assert post_calls["calls"][0]["headers"] == {"Authorization": "Bearer test-key"}


def test_the_key_is_never_logged(post_calls, caplog):
    post_calls["replies"].append(FakeResponse(401, text="unauthorized"))
    with pytest.raises(llm.LLMUnavailable):
        real_chat_complete([{"role": "user", "content": "hi"}])
    assert "test-key" not in caplog.text


# ---------------------------------------------------------------------------
# chat_complete
# ---------------------------------------------------------------------------


def test_a_good_reply_is_returned_with_the_model_name(post_calls):
    post_calls["replies"].append(FakeResponse(200, chat_body("  Namaste  ")))
    text, model = real_chat_complete([{"role": "user", "content": "hi"}])
    assert text == "Namaste"
    assert model == "openai/gpt-oss-120b"


def test_gpt_oss_asks_for_low_reasoning_effort(post_calls):
    real_chat_complete([{"role": "user", "content": "hi"}])
    body = post_calls["calls"][0]["json"]
    assert body["reasoning_effort"] == "low"
    assert "reasoning_format" not in body


def test_other_models_hide_their_reasoning(post_calls, monkeypatch):
    monkeypatch.setattr(config, "GROQ_CHAT_MODEL", "qwen/qwen3.8-27b")
    real_chat_complete([{"role": "user", "content": "hi"}])
    body = post_calls["calls"][0]["json"]
    assert body["reasoning_format"] == "hidden"
    assert "reasoning_effort" not in body


def test_the_main_model_is_tried_first(post_calls):
    real_chat_complete([{"role": "user", "content": "hi"}])
    assert post_calls["calls"][0]["json"]["model"] == "openai/gpt-oss-120b"


@pytest.mark.parametrize("status", sorted(llm.RETRYABLE_STATUS))
def test_a_retryable_status_falls_through_to_the_fallback_model(post_calls, status):
    post_calls["replies"] += [FakeResponse(status, text="busy"),
                              FakeResponse(200, chat_body("from fallback"))]
    text, model = real_chat_complete([{"role": "user", "content": "hi"}])
    assert text == "from fallback"
    assert model == "qwen/qwen3.8-27b"
    assert [c["json"]["model"] for c in post_calls["calls"]] == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]


def test_a_transport_error_falls_through_to_the_fallback_model(post_calls):
    post_calls["replies"] += [httpx.ConnectError("no route"),
                              FakeResponse(200, chat_body("recovered"))]
    assert real_chat_complete([{"role": "user", "content": "hi"}]) == ("recovered", "qwen/qwen3.8-27b")


def test_a_client_error_is_not_retried(post_calls):
    # 401/400 mean a bad key or a bad request: retrying wastes time and hides it.
    post_calls["replies"].append(FakeResponse(401, text="bad key"))
    with pytest.raises(llm.LLMUnavailable, match="HTTP 401"):
        real_chat_complete([{"role": "user", "content": "hi"}])
    assert len(post_calls["calls"]) == 1


def test_both_models_failing_raises_with_the_last_error(post_calls):
    post_calls["replies"] += [FakeResponse(503, text="a"), FakeResponse(503, text="b")]
    with pytest.raises(llm.LLMUnavailable):
        real_chat_complete([{"role": "user", "content": "hi"}])


def test_an_empty_reply_falls_through_to_the_fallback(post_calls):
    post_calls["replies"] += [FakeResponse(200, chat_body("   ")),
                              FakeResponse(200, chat_body("real answer"))]
    assert real_chat_complete([{"role": "user", "content": "hi"}])[0] == "real answer"


def test_a_null_content_reply_falls_through(post_calls):
    post_calls["replies"] += [FakeResponse(200, {"choices": [{"message": {"content": None}}]}),
                              FakeResponse(200, chat_body("real answer"))]
    assert real_chat_complete([{"role": "user", "content": "hi"}])[0] == "real answer"


# --- the shape of a bad 200 must never become a 500 (Phase 1 finding #5) -----


@pytest.mark.parametrize("body", [
    {},                                                    # no choices
    {"choices": []},                                       # empty choices
    {"choices": [{}]},                                     # no message
    {"choices": [{"message": {}}]},                         # no content
    {"error": {"message": "upstream proxy error"}},        # a proxy error page
    {"choices": [{"text": "wrong key"}]},                   # an older, different shape
])
def test_an_unexpected_200_body_degrades_to_the_fallback(post_calls, body):
    post_calls["replies"] += [FakeResponse(200, body),
                              FakeResponse(200, chat_body("real answer"))]
    assert real_chat_complete([{"role": "user", "content": "hi"}])[0] == "real answer"


def test_non_json_200_becomes_llm_unavailable_not_a_crash(post_calls):
    post_calls["replies"] += [FakeResponse(200, raise_on_json=True),
                              FakeResponse(200, raise_on_json=True)]
    with pytest.raises(llm.LLMUnavailable):
        real_chat_complete([{"role": "user", "content": "hi"}])


def test_max_tokens_and_temperature_are_forwarded(post_calls):
    real_chat_complete([{"role": "user", "content": "hi"}], max_tokens=123, temperature=0.9)
    body = post_calls["calls"][0]["json"]
    assert body["max_completion_tokens"] == 123
    assert body["temperature"] == 0.9


def test_the_question_and_history_are_forwarded(post_calls):
    messages = [{"role": "system", "content": "rules"}, {"role": "user", "content": "q"}]
    real_chat_complete(messages)
    assert post_calls["calls"][0]["json"]["messages"] == messages


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------


def test_speech_is_returned_as_text(post_calls):
    post_calls["replies"].append(FakeResponse(200, {"text": "meri fasal kaisi hai"}))
    assert real_transcribe(b"audio", "q.webm", "audio/webm", "hi") == "meri fasal kaisi hai"


def test_the_audio_and_filename_are_uploaded(post_calls):
    real_transcribe(b"audio-bytes", "question.webm", "audio/webm", "hi")
    call = post_calls["calls"][0]
    assert call["files"]["file"] == ("question.webm", b"audio-bytes", "audio/webm")
    assert call["data"]["model"] == "whisper-large-v3"
    assert call["data"]["response_format"] == "verbose_json"


@pytest.mark.parametrize("lang", ["en", "hi", "mr", "pa"])
def test_supported_languages_are_passed_to_whisper(post_calls, lang):
    real_transcribe(b"audio", "q.webm", "audio/webm", lang)
    assert post_calls["calls"][0]["data"]["language"] == lang


@pytest.mark.parametrize("lang", ["bgc", "bho", "ta", None])
def test_unsupported_languages_are_omitted_and_whisper_autodetects(post_calls, lang):
    real_transcribe(b"audio", "q.webm", "audio/webm", lang)
    assert "language" not in post_calls["calls"][0]["data"]


def test_a_transcription_failure_raises_llm_unavailable(post_calls):
    post_calls["replies"].append(FakeResponse(500, text="boom"))
    with pytest.raises(llm.LLMUnavailable, match="HTTP 500"):
        real_transcribe(b"audio", "q.webm", "audio/webm")


def test_a_transcription_transport_error_raises_llm_unavailable(post_calls):
    post_calls["replies"].append(httpx.ConnectTimeout("timeout"))
    with pytest.raises(llm.LLMUnavailable):
        real_transcribe(b"audio", "q.webm", "audio/webm")


def test_a_non_json_transcription_raises_llm_unavailable(post_calls):
    post_calls["replies"].append(FakeResponse(200, raise_on_json=True))
    with pytest.raises(llm.LLMUnavailable):
        real_transcribe(b"audio", "q.webm", "audio/webm")


@pytest.mark.parametrize("payload", [[], "text", 42, None])
def test_a_wrong_shaped_transcription_raises_llm_unavailable(post_calls, payload):
    post_calls["replies"].append(FakeResponse(200, payload))
    with pytest.raises(llm.LLMUnavailable):
        real_transcribe(b"audio", "q.webm", "audio/webm")


def test_segments_marked_as_non_speech_are_dropped(post_calls):
    post_calls["replies"].append(FakeResponse(200, {"segments": [
        {"text": "(beep)", "no_speech_prob": 0.95},
        {"text": "meri fasal", "no_speech_prob": 0.05},
    ]}))
    assert real_transcribe(b"audio", "q.webm", "audio/webm") == "meri fasal"


def test_a_hallucinated_repeat_becomes_empty(post_calls):
    post_calls["replies"].append(FakeResponse(200, {"text": "प्रस्तुति प्रस्तुति प्रस्तुति"}))
    assert real_transcribe(b"audio", "q.webm", "audio/webm") == ""
