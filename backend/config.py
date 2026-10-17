"""
Settings loaded from the environment / the git-ignored `.env` file (Component 9).

Import this module early (backend/main.py does) so `.env` is read before
any service looks for its key. Values already set in the real environment
win over `.env`, so you can override a key per terminal.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env", override=False)


def groq_api_key() -> str | None:
    key = os.getenv("GROQ_API_KEY", "").strip()
    return key or None


GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b")
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
