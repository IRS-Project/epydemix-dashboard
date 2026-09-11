# pages/Model_References.py
#
# In-app parameter & data provenance reference: renders docs/parameter-references.md
# (the version-controlled source of truth) natively, and links out to the
# interactive artifact version, which adds the data-to-parameter calculators.

from pathlib import Path

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
    """
    <style>
        .block-container { padding-top: 2rem; padding-bottom: 5rem; }
        /* keep the reference tables readable and scrollable on narrow screens */
        .ref-doc table { font-size: 0.9rem; }
        .ref-doc { max-width: 1000px; }
    </style>
    """,
    unsafe_allow_html=True,
)

show_dashboard_header()
render_sidebar()

st.markdown("## Model References & Provenance")
st.caption(
    "Where every default value, plausible range, prior bound, and data input in the "
    "pertussis model comes from — each tagged by evidence tier (Literature · "
    "Lit-informed · Assumption · Data-derived)."
)

# Link to the interactive artifact (adds the data → parameter calculators).
ARTIFACT_URL = "https://claude.ai/code/artifact/e82c6144-6f92-4aa8-ae4f-8ab3bbc5f6b2"
st.link_button("🧬 Open the interactive version (with data → parameter calculators)",
               ARTIFACT_URL, use_container_width=False)
st.caption(
    "The interactive version adds a calculator for each parameter (e.g. R₀ from early "
    "case growth, δ from screening-method VE). It is a private page — use its Share "
    "menu to grant your team access."
)

st.divider()

# Render the provenance document (source of truth, kept in git).
_DOC = Path(__file__).resolve().parent.parent / "docs" / "parameter-references.md"
try:
    text = _DOC.read_text(encoding="utf-8")
    # Drop the leading H1 (the page already has its own title above).
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    st.markdown('<div class="ref-doc">', unsafe_allow_html=True)
    st.markdown("\n".join(lines))
    st.markdown("</div>", unsafe_allow_html=True)
except FileNotFoundError:
    st.error(f"Provenance document not found at {_DOC}. Expected docs/parameter-references.md.")

show_logos()
