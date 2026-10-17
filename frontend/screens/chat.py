"""
SCREEN: Ask DharRakshak — multilingual chatbot (F7) + app-wide polish (F6)
OWNER:  Teammate 4
DATA:   api_client.send_chat(crop_id, message, lang) -> ChatReply
        Field list: docs/CONTRACT.md, row "Chatbot + language + theme"

In mock mode the reply comes from shared/sample_data.json "chat_examples"
(simple keyword matching). Try: "लोन के लिए कौन से कागज़ बाकी हैं?",
"Why should I inspect nearby plants?", "Which pesticide should I spray?".
The real, grounded chatbot arrives in Component 9 — this screen won't change.

==========================================================================
YOUR TASK — step by step (delete each TODO line once it's done)
==========================================================================
Work in this file AND frontend/theme.py. Run:  streamlit run frontend/app.py

TODO 1  Chat history. Keep a list in st.session_state.chat_history of
        dicts like {"role": "user" | "assistant", "text": "..."}.
        Create it if missing. Draw every message with
        `with st.chat_message(role): st.markdown(text)`.

TODO 2  Input. `message = st.chat_input(placeholder)` (placeholder text via
        theme.t, e.g. "Ask in English or हिंदी…"). When the farmer sends a
        message: append it, call api_client.send_chat(crop_id, message, lang)
        inside st.spinner, append the reply, then st.rerun().

TODO 3  Honesty cues. If reply.is_fallback, show a small st.caption under
        the answer saying the chatbot is offline and this is a saved answer.
        Add a "Clear chat" button that empties the history.

TODO 4  Suggested questions. Show 2–3 st.button chips with example
        questions (one Hindi, one English) that send the question when
        clicked — this makes the live demo smooth.

TODO 5  App polish (frontend/theme.py → inject_css). Make all four screens
        feel like one product: card styling for st.container(border=True),
        spacing, button colours. Coordinate with Teammates 1–3 so everyone
        uses theme.COLORS and theme.pill.

TODO 6  Language selector check. Switch EN ↔ हिंदी on every screen and
        list any untranslated text for the owner to fix.

DONE WHEN
  [ ] The three sample questions give the matching answers.
  [ ] History stays when you switch screens and come back.
  [ ] Fallback replies are clearly marked.
  [ ] All four screens share one consistent look.
"""

from __future__ import annotations

import streamlit as st

import api_client
import theme


def render(lang: str, crop_id: str) -> None:
    st.title(theme.t("nav_chat", lang))
    st.info(theme.t("under_construction", lang) + " (Teammate 4)")

    # Temporary preview: one real round-trip through api_client so you can
    # see what a reply looks like. Remove when TODO 1–2 are finished.
    with st.expander(theme.t("raw_data", lang)):
        sample_question = "लोन के लिए कौन से कागज़ बाकी हैं?" if lang == "hi" else "Why should I inspect nearby plants?"
        reply = api_client.send_chat(crop_id, sample_question, lang)
        st.write(f"**Q:** {sample_question}")
        st.json(reply.model_dump(mode="json"))
