"""
Shared look-and-feel helpers for every screen (Component 1).

Every teammate imports from here so the four screens look like ONE app:
    from theme import COLORS, t, format_inr, mock_tag, crop_label, stage_label

Rules:
- Never hard-code farmer-facing English in a screen. Put the text in UI_TEXT
  below (both "en" and "hi") and call t("key", lang).
  Component 8 moves UI_TEXT into shared/i18n/en.json and hi.json; screens
  keep calling t(), so they won't need to change.
- Use COLORS instead of typing hex codes in screens.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Colours — same palette as the pitch deck (see docs/CONTRACT.md)
# ---------------------------------------------------------------------------
COLORS = {
    "forest": "#1F3D2B",   # headers, sidebar
    "green": "#2E6B3F",    # buttons, main bars
    "leaf": "#7FA65A",     # secondary bars
    "gold": "#C9A227",     # highlights, tags
    "rust": "#B5502F",     # elevated risk, missing documents
    "offwhite": "#F7F5EF", # page background
    "tint": "#E8EFE0",     # card backgrounds
    "gold_tint": "#FBF3DC",# soft highlight background
    "ink": "#1B2A20",      # body text
    "muted": "#5E6B60",    # secondary text
}

# ---------------------------------------------------------------------------
# UI text in every supported language.
# Add a key here whenever a screen needs a new label.
# ---------------------------------------------------------------------------
UI_TEXT: dict[str, dict[str, str]] = {
    "app_tagline": {
        "en": "From crop symptoms to smarter farming decisions",
        "hi": "फसल के लक्षणों से बेहतर खेती के फैसलों तक",
    },
    "language": {"en": "Language", "hi": "भाषा"},
    "nav_profile": {"en": "My crop", "hi": "मेरी फसल"},
    "nav_analysis": {"en": "Leaf check", "hi": "पत्ती जाँच"},
    "nav_finance": {"en": "Loans & documents", "hi": "लोन और कागज़ात"},
    "nav_chat": {"en": "Ask DharRakshak", "hi": "धररक्षक से पूछें"},
    "mock_mode": {"en": "Demo mode: sample data", "hi": "डेमो मोड: नमूना डेटा"},
    "mock_data": {"en": "MOCK DATA", "hi": "नमूना डेटा"},
    "demo_example": {"en": "DEMO EXAMPLE", "hi": "डेमो उदाहरण"},
    "estimate": {"en": "estimate", "hi": "अनुमान"},
    "under_construction": {
        "en": "This screen is being built by a teammate.",
        "hi": "यह स्क्रीन एक साथी बना रहे हैं।",
    },
    "raw_data": {"en": "Data this screen receives", "hi": "इस स्क्रीन को मिलने वाला डेटा"},
}


def t(key: str, lang: str) -> str:
    """Return UI text for `key` in `lang` (falls back to English, then the key)."""
    entry = UI_TEXT.get(key)
    if entry is None:
        return key  # makes missing keys easy to spot on screen
    return entry.get(lang) or entry.get("en") or key


# ---------------------------------------------------------------------------
# Crop and stage display names (the final crop list depends on the image
# model chosen in Component 4 — keep these keys in sync with it).
# ---------------------------------------------------------------------------
CROP_OPTIONS: dict[str, dict[str, str]] = {
    "tomato": {"en": "Tomato", "hi": "टमाटर"},
    "potato": {"en": "Potato", "hi": "आलू"},
    "pepper_bell": {"en": "Bell pepper", "hi": "शिमला मिर्च"},
    "corn": {"en": "Maize (corn)", "hi": "मक्का"},
    "apple": {"en": "Apple", "hi": "सेब"},
    "grape": {"en": "Grape", "hi": "अंगूर"},
}

STAGE_LABELS: dict[str, dict[str, str]] = {
    "seedling": {"en": "Seedling", "hi": "पौध"},
    "vegetative": {"en": "Vegetative growth", "hi": "बढ़वार"},
    "flowering": {"en": "Flowering", "hi": "फूल आना"},
    "fruiting": {"en": "Fruiting", "hi": "फल लगना"},
    "maturity": {"en": "Maturity", "hi": "पकना"},
}


def crop_label(crop_key: str, lang: str) -> str:
    return CROP_OPTIONS.get(crop_key, {}).get(lang) or crop_key.title()


def stage_label(stage_key: str, lang: str) -> str:
    return STAGE_LABELS.get(stage_key, {}).get(lang) or stage_key.title()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_inr(amount: int) -> str:
    """Format rupees with Indian digit grouping: 120000 -> '₹1,20,000'."""
    sign = "-" if amount < 0 else ""
    digits = str(abs(int(amount)))
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    last3, rest = digits[-3:], digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return f"{sign}₹{','.join(groups)},{last3}"


def format_percent(confidence: float) -> str:
    """0.68 -> '68%'."""
    return f"{round(confidence * 100)}%"


# ---------------------------------------------------------------------------
# Small visual building blocks (HTML rendered with st.markdown)
# ---------------------------------------------------------------------------

def pill(text: str, bg: str, fg: str = "#FFFFFF") -> str:
    """Return HTML for a rounded label. Use inside st.markdown(..., unsafe_allow_html=True)."""
    return (
        f"<span style='background:{bg};color:{fg};padding:3px 10px;border-radius:999px;"
        f"font-size:0.78rem;font-weight:700;letter-spacing:0.02em'>{text}</span>"
    )


def mock_tag(lang: str, key: str = "mock_data") -> None:
    """Show the gold MOCK DATA tag. Required wherever sample/mock data is displayed."""
    st.markdown(pill(t(key, lang), COLORS["gold"], COLORS["forest"]), unsafe_allow_html=True)


def inject_css() -> None:
    """Global CSS tweaks. Called once from app.py. Teammate 4 owns polishing this."""
    st.markdown(
        f"""
        <style>
          /* Sidebar in deep forest green with light text */
          section[data-testid="stSidebar"] {{ background-color: {COLORS["forest"]}; }}
          section[data-testid="stSidebar"] * {{ color: {COLORS["offwhite"]}; }}
          /* Headings in forest green */
          h1, h2, h3 {{ color: {COLORS["forest"]}; }}
          /* Slightly rounder buttons */
          .stButton > button {{ border-radius: 999px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
