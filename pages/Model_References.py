# pages/Model_References.py
#
# Thin click-out to the parameter & data provenance page. The full reference —
# evidence-tier tables, sourced citations, and the interactive data -> parameter
# calculators — lives in the shareable HTML artifact; this page just links to it.
# Source of truth for the content: docs/parameter-references.md.

import streamlit as st

from layout.header import show_dashboard_header
from layout.sidebar import render_sidebar
from layout.logos import show_logos

st.set_page_config(
    page_title="Model References",
    page_icon="assets/epydemix-icon.svg",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    "<style>.block-container{padding-top:2rem;padding-bottom:5rem;}</style>",
    unsafe_allow_html=True,
)

show_dashboard_header()
render_sidebar()

st.markdown("## Model References & Provenance")
st.caption(
    "Where every default value, plausible range, prior bound, and data input in the "
    "pertussis model comes from — each tagged by evidence tier (Literature · "
    "Lit-informed · Assumption · Data-derived) — plus a calculator for each parameter "
    "that converts local surveillance data into a value."
)

ARTIFACT_URL = "https://claude.ai/code/artifact/e82c6144-6f92-4aa8-ae4f-8ab3bbc5f6b2"
st.link_button("🧬 Open the provenance page & calculators ↗", ARTIFACT_URL,
               type="primary", use_container_width=False)
st.caption(
    "Opens the shareable HTML in a new tab. It is a private page — use its Share menu "
    "to grant your team access. The written source of truth is `docs/parameter-references.md` "
    "in the repository."
)

show_logos()
