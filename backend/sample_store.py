"""
Sample data + temporary placeholders.

Since Component 3, real storage lives in SQLite (backend/db.py and
backend/repository.py). What's left here is:

- `sample()`: loads shared/sample_data.json. Used to seed the demo farmer
  and, until Component 7, to supply scheme notes.
- `mock_analysis(crop_id)`: placeholder analysis result. Replaced by the
  real image model + engines in Components 4–6.
- `mock_chat_reply(request)`: placeholder chatbot. Replaced by the
  grounded LLM + voice assistant in Component 9.

When those components land, the matching function here is deleted.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from shared.contract import AnalysisResult, ChatReply, ChatRequest, SampleData

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "shared" / "sample_data.json"


@lru_cache(maxsize=1)
def sample() -> SampleData:
    """Load and validate the sample file once (fails loudly if it's broken)."""
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return SampleData.model_validate(raw)


def mock_analysis(crop_id: str) -> AnalysisResult:
    """Sample analysis re-labelled for this crop (the photo is not used yet).

    `is_demo` stays True so the UI shows "DEMO EXAMPLE" until the real
    model arrives in Component 4.
    """
    return sample().analysis.model_copy(
        update={
            "analysis_id": f"an-{uuid.uuid4().hex[:8]}",
            "crop_id": crop_id,
            "created_at": datetime.now(timezone.utc),
            "is_demo": True,
        }
    )


# Keyword routing to the sample chat answers, so the frontend chat works now.
# (keywords, index into sample().chat_examples). Safety (pesticide) first.
_CHAT_KEYWORDS: list[tuple[tuple[str, ...], int]] = [
    (("pesticide", "spray", "dose", "दवा", "कीटनाशक", "छिड़काव"), 2),
    (("कागज", "कागज़", "दस्तावेज", "document", "loan", "लोन"), 0),
    (("why", "क्यों", "inspect", "जाँच"), 1),
]

_UNKNOWN_REPLY = {
    "en": "(Demo mode) I'll be able to answer this once the chatbot is connected.",
    "hi": "(डेमो मोड) चैटबॉट जुड़ने के बाद मैं इसका जवाब दे पाऊँगा।",
}


def mock_chat_reply(request: ChatRequest) -> ChatReply:
    """Placeholder chatbot until Component 9."""
    text = request.message.lower()
    for words, example_index in _CHAT_KEYWORDS:
        if any(word in text for word in words):
            return sample().chat_examples[example_index].reply
    return ChatReply(
        reply=_UNKNOWN_REPLY.get(request.lang, _UNKNOWN_REPLY["en"]),
        lang=request.lang,
        is_fallback=True,
    )
