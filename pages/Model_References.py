# pages/Model_References.py
#
# Thin link to the parameter & data provenance document. The full reference is a
# self-contained, portable HTML page (static/parameter-provenance-v2.html) served
# by Streamlit's static file server and opened via a RELATIVE url — no external or
# local-drive dependency. Written source of truth: docs/parameter-references.md;
# tactical derivation recipes: docs/tactical.txt.

import streamlit as st
import mime_fix  # noqa: F401  (serve the provenance HTML as a real page; see mime_fix.py)

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
    "Default value, plausible range, description, selection rationale, and citations "
    "for every pertussis-model parameter (v2)."
)

# Relative URL to the portable HTML served from ./static/; opens in a new tab.
PROVENANCE_URL = "app/static/parameter-provenance-v2.html"
st.markdown(
    f'<a href="{PROVENANCE_URL}" target="_blank" rel="noopener" '
    'style="display:inline-block;background:#0e6b64;color:#fff;text-decoration:none;'
    'font-weight:600;padding:0.55rem 1.1rem;border-radius:8px;font-size:0.95rem;">'
    '\U0001F4D6 Open parameter provenance (v2) ↗</a>',
    unsafe_allow_html=True,
)
st.caption(
    "Opens the provenance document in a new tab. It is a self-contained, portable HTML file "
    "in the repository (`static/parameter-provenance-v2.html`) — no external dependencies. "
    "Tactical “how to derive from data” recipes are in `docs/tactical.txt`."
)

show_logos()
