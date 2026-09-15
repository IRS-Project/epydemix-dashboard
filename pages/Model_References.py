# pages/Model_References.py
#
# Parameter & data provenance: rather than rebuild the reference as Streamlit
# widgets, embed the self-contained HTML page we generated (evidence-tier tables,
# full sourced reference, and the interactive data -> parameter calculators) via
# st.components.v1.html so its own CSS/JS run. A link to the shareable claude.ai
# artifact (the same page) is offered for hand-off.

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

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
st.markdown(
    f'<a href="{ARTIFACT_URL}" target="_blank" rel="noopener" '
    'style="color:#4cc9c6;font-weight:600;text-decoration:none;">'
    '🧬 Open the shareable version in a new tab ↗</a> '
    '<span style="color:#8a97a0;font-size:0.85rem;">— private artifact; use its Share menu for your team.</span>',
    unsafe_allow_html=True,
)

# Embed the generated HTML so its calculators and styling run in-app.
_HTML = Path(__file__).resolve().parent.parent / "static" / "parameter-references.html"
try:
    components.html(_HTML.read_text(encoding="utf-8"), height=1500, scrolling=True)
except FileNotFoundError:
    st.error(f"Provenance HTML not found at {_HTML}.")

show_logos()
