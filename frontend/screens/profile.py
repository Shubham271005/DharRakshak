"""
SCREEN: My crop — registration form + profile card (F2)
OWNER:  Teammate 1
DATA:   api_client.get_crop_profile()  -> CropProfile        (read)
        api_client.save_crop_profile() <- CropProfileCreate  (write)
        Field list: docs/CONTRACT.md, row "Crop registration + profile card"

==========================================================================
YOUR TASK — step by step (delete each TODO line once it's done)
==========================================================================
Work only in this file. Run the app with:  streamlit run frontend/app.py
Streamlit reloads the page automatically when you save this file.

TODO 1  Profile card (top of the screen).
        Use st.columns(3) and st.metric (or st.markdown) to show:
        crop (use theme.crop_label), stage (theme.stage_label), days since
        sowing, area in acres, location name, expected harvest window
        (show "—" if None), yield estimate ("Range pending" if None).
        Hint: profile.sowing_date.strftime("%d %b %Y") formats a date.

TODO 2  Registration form (below the card).
        Wrap inputs in `with st.form("crop_form"):` so the page only
        reloads when the farmer presses Save. Inputs:
          - farmer name ......... st.text_input
          - crop ................ st.selectbox(options=list(theme.CROP_OPTIONS),
                                  format_func=lambda k: theme.crop_label(k, lang))
          - variety (optional) .. st.text_input
          - sowing date ......... st.date_input (max_value=date.today())
          - area in acres ....... st.number_input(min_value=0.1, step=0.1)
          - village / district .. st.text_input
          - crop stage .......... st.selectbox over theme.STAGE_LABELS
        Pre-fill each input with the current profile's value.

TODO 3  On Save: build a CropProfileCreate(...) from the inputs and call
        api_client.save_crop_profile(...). Wrap it in try/except
        (pydantic.ValidationError, api_client.ApiError) and show
        st.error(...) on failure, st.success(...) on success, then
        st.rerun() so the card shows the new values.

TODO 4  Language. Every label must come from theme.t("key", lang).
        Add the keys you need (both "en" and "hi") to UI_TEXT in
        frontend/theme.py. Switch the sidebar to हिंदी and check.

DONE WHEN
  [ ] Card shows the demo profile (tomato, flowering, day 52, 0.5 acre).
  [ ] Saving the form updates the card.
  [ ] A future sowing date or empty name shows a friendly error.
  [ ] Everything reads correctly in English AND Hindi.
"""

from __future__ import annotations

import streamlit as st

import api_client
import theme


def render(lang: str, crop_id: str) -> None:
    st.title(theme.t("nav_profile", lang))
    st.info(theme.t("under_construction", lang) + " (Teammate 1)")

    profile = api_client.get_crop_profile(crop_id)

    # Temporary preview so you can see the data while building.
    # Remove this expander when TODO 1 is finished.
    with st.expander(theme.t("raw_data", lang)):
        st.json(profile.model_dump(mode="json"))
