"""
SCREEN: Loans & documents (F5) — MOCK DATA ONLY, no bank integration
OWNER:  Teammate 3
DATA:   api_client.get_loan_summary(crop_id) -> LoanSummary
        Field list: docs/CONTRACT.md, row "Finance & loans"

==========================================================================
YOUR TASK — step by step (delete each TODO line once it's done)
==========================================================================
Work only in this file. Run the app with:  streamlit run frontend/app.py

TODO 1  Mock label. If summary.data_source == "mock", call
        theme.mock_tag(lang) at the very top, plus a one-line caption that
        this is sample data and not connected to any bank
        (add the text to UI_TEXT in theme.py in both languages).

TODO 2  Loan card. Show loan.display_name.in_lang(lang) as a heading and
        loan.status as a pill (active -> green, overdue -> rust,
        applied -> gold, closed -> muted). Then st.columns(3) with
        st.metric for: sanctioned amount, outstanding amount, next
        repayment (amount + date). Use theme.format_inr(...) for money.
        If next_repayment is None, show "—".

TODO 3  Documents checklist. Show "3 of 5 submitted" and a progress bar
        (submitted / total). Then one line per document:
          ✅ name   when submitted
          ❌ name   when missing — in COLORS["rust"] so it stands out
        Use document.name.in_lang(lang).

TODO 4  Schemes to check. For each scheme: name (bold), summary, and
        verify_note in italics. If official_url is set, show it as a link
        (st.link_button or a markdown link).

TODO 5  Language. All labels via theme.t(...); check in हिंदी.

DONE WHEN
  [ ] Matches the finance panel on slide 4 (KCC sample, ₹48,000
      outstanding, ₹12,000 due 15 Dec, 3 of 5 documents).
  [ ] Land record + passport photo appear in red as missing.
  [ ] MOCK DATA tag is clearly visible.
  [ ] Everything reads correctly in English AND Hindi.
"""

from __future__ import annotations

import streamlit as st

import api_client
import theme


def render(lang: str, crop_id: str) -> None:
    st.title(theme.t("nav_finance", lang))
    st.info(theme.t("under_construction", lang) + " (Teammate 3)")

    summary = api_client.get_loan_summary(crop_id)

    # Temporary preview so you can see the data while building.
    # Remove this expander when TODO 2–4 are finished.
    with st.expander(theme.t("raw_data", lang)):
        st.json(summary.model_dump(mode="json"))
