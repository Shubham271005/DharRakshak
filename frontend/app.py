"""
DharRakshak — Streamlit entry point (Component 1).

Run from the repository root:
    streamlit run frontend/app.py

What this file does:
1. Sets up the page and the shared theme.
2. Draws the sidebar: app name, language selector, navigation, mode badge.
3. Calls the selected screen's `render(lang, crop_id)` function.

Each screen lives in frontend/screens/ and is owned by one teammate.
A screen must ONLY:
- read data through `api_client` (never files or URLs directly),
- show farmer-facing text through `theme.t()` or the LocalizedText fields,
- accept `lang` and `crop_id` as arguments.
"""

from __future__ import annotations

import streamlit as st

import api_client
import theme
from screens import analysis, chat, finance, profile

st.set_page_config(
    page_title="DharRakshak",
    page_icon="🌱",
    layout="wide",
)
theme.inject_css()

# Languages offered in the selector. Add a regional language here ONLY when
# its translations exist everywhere (see ROADMAP.md, Component 8).
LANGUAGES = {"en": "English", "hi": "हिंदी"}

# Navigation: (UI_TEXT key, screen module). Order = order in the sidebar.
SCREENS = [
    ("nav_profile", profile),
    ("nav_analysis", analysis),
    ("nav_finance", finance),
    ("nav_chat", chat),
]

# Remember the chosen language across reruns (Streamlit reruns this script
# from the top on every click).
if "lang" not in st.session_state:
    st.session_state.lang = "en"

with st.sidebar:
    st.markdown("## 🌱 DharRakshak")
    st.caption(theme.t("app_tagline", st.session_state.lang))

    lang = st.radio(
        theme.t("language", st.session_state.lang),
        options=list(LANGUAGES),
        format_func=lambda code: LANGUAGES[code],
        horizontal=True,
        key="lang",
    )

    st.divider()
    screen_index = st.radio(
        "Navigation",
        options=range(len(SCREENS)),
        format_func=lambda i: theme.t(SCREENS[i][0], lang),
        label_visibility="collapsed",
    )

    st.divider()
    if api_client.is_mock_mode():
        theme.mock_tag(lang, key="mock_mode")

crop_id = api_client.demo_crop_id()

# Show the chosen screen. Any unexpected error is shown on that screen only,
# so one unfinished screen can't break the whole app during development.
_, screen_module = SCREENS[screen_index]
try:
    screen_module.render(lang=lang, crop_id=crop_id)
except api_client.ApiError as err:
    st.error(f"Could not reach the DharRakshak server. {err}")
