"""
SCREEN: Leaf check — upload + analysis results (F1, F3, F2, F4)
OWNER:  Teammate 2
DATA:   api_client.analyze_image(crop_id, image_bytes, filename) -> AnalysisResult
        api_client.get_latest_analysis(crop_id) -> AnalysisResult | None
        Field list: docs/CONTRACT.md, row "Analysis results"

==========================================================================
YOUR TASK — step by step (delete each TODO line once it's done)
==========================================================================
Work only in this file. Run the app with:  streamlit run frontend/app.py

TODO 1  Upload. st.file_uploader(type=["jpg", "jpeg", "png"]). When a file
        is uploaded, show it with st.image and a button "Analyze". On click,
        call api_client.analyze_image(crop_id, file.getvalue(), file.name)
        inside `with st.spinner(...)`, and store the result in
        st.session_state.analysis so it survives reruns.
        If nothing has been uploaded yet, show get_latest_analysis().

TODO 2  Tags. If result.is_demo: theme.mock_tag(lang, key="demo_example").
        If result.weather and result.weather.source == "mock": theme.mock_tag(lang).

TODO 3  Uncertain result. If result.uncertain, show
        st.warning(result.uncertainty_message.in_lang(lang)) ABOVE the
        predictions. If result.crop_mismatch, warn that the photo may be
        of a different crop than the profile.

TODO 4  Predictions (F1). For each item in result.predictions show
        display_name.in_lang(lang), theme.format_percent(confidence) and a
        bar (st.progress(confidence)). Never write "confirmed".

TODO 5  Risk (F3). A coloured badge with result.risk.level:
          low -> COLORS["leaf"], moderate -> COLORS["gold"], elevated -> COLORS["rust"]
        Use theme.pill(...) inside st.markdown(..., unsafe_allow_html=True)
        and ALWAYS add the word theme.t("estimate", lang) next to it.
        Below it, list each reason: reason.text.in_lang(lang).
        Also show result.weather.summary if weather is present.

TODO 6  Action cards (F2). Sort result.action_cards by priority and show
        them side by side with st.columns(len(cards)). Each card: priority
        number, title, detail, and an st.expander("Why?") with card.why.

TODO 7  Explanation (F4). A highlighted box (st.info or a tinted
        st.markdown block) with explanation.summary, then
        explanation.verify in bold.

DONE WHEN
  [ ] The demo result matches the slide 4 mockup (3 bars, ELEVATED +
      "estimate", 3 action cards, Why box).
  [ ] DEMO EXAMPLE / MOCK DATA tags show when the data is sample data.
  [ ] Editing sample_data.json to "uncertain": true (with a message)
      shows the warning — then put it back.
  [ ] Everything reads correctly in English AND Hindi.
"""

from __future__ import annotations

import streamlit as st

import api_client
import theme


def render(lang: str, crop_id: str) -> None:
    st.title(theme.t("nav_analysis", lang))
    st.info(theme.t("under_construction", lang) + " (Teammate 2)")

    result = api_client.get_latest_analysis(crop_id)

    # Temporary preview so you can see the data while building.
    # Remove this expander when TODO 4–7 are finished.
    with st.expander(theme.t("raw_data", lang)):
        if result is None:
            st.write("No analysis yet.")
        else:
            st.json(result.model_dump(mode="json"))
