"""
Sample data + temporary placeholders.

Since Component 3, real storage lives in SQLite (backend/db.py and
backend/repository.py). What's left here is:

- `sample()`: loads shared/sample_data.json. Used to seed the demo farmer,
  to supply the placeholder weather/risk/cards in backend/pipeline.py until
  Components 5–6, and scheme notes until Component 7.
- `mock_chat_reply(request)`: saved demo answers, used by the real chatbot
  (backend/services/chat.py) as its FALLBACK when Groq is unavailable.

When those components land, the matching function here is deleted.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from shared.contract import ChatReply, ChatRequest, SampleData

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "shared" / "sample_data.json"


@lru_cache(maxsize=1)
def sample() -> SampleData:
    """Load and validate the sample file once (fails loudly if it's broken)."""
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return SampleData.model_validate(raw)


# Keyword routing to the sample chat answers, so the frontend chat works now.
# (keywords, index into sample().chat_examples). Safety (pesticide) first.
_CHAT_KEYWORDS: list[tuple[tuple[str, ...], int]] = [
    (("pesticide", "spray", "dose", "दवा", "कीटनाशक", "छिड़काव"), 2),
    (("कागज", "कागज़", "दस्तावेज", "document", "loan", "लोन"), 0),
    (("why", "क्यों", "inspect", "जाँच"), 1),
]

_UNKNOWN_REPLY = {
    "en": "The chatbot is offline right now, so I can only give saved answers. Please try again in a moment.",
    "hi": "चैटबॉट अभी ऑफ़लाइन है, इसलिए मैं केवल सहेजे गए जवाब दे सकता हूँ। कृपया थोड़ी देर बाद फिर कोशिश करें।",
}


def mock_chat_reply(request: ChatRequest) -> ChatReply:
    """Saved demo answers (fallback when the LLM is unavailable). Safety first:
    pesticide questions are matched before anything else."""
    text = request.message.lower()
    for words, example_index in _CHAT_KEYWORDS:
        if any(word in text for word in words):
            return sample().chat_examples[example_index].reply
    return ChatReply(
        reply=_UNKNOWN_REPLY.get(request.lang, _UNKNOWN_REPLY["en"]),
        lang=request.lang,
        is_fallback=True,
    )
