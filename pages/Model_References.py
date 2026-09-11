# pages/Model_References.py
#
# In-app parameter & data provenance reference: native "derive from your data"
# calculators (the same tactical formulas as the app tooltips), plus the full
# provenance document rendered from docs/parameter-references.md (source of
# truth, kept in git), and a link to the shareable interactive artifact.

import math
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


# ---------------------------------------------------------------------------
# Calculators — derive a parameter value from locally-monitored data
# ---------------------------------------------------------------------------
def _metric(col, label, value, formula, sub=""):
    with col:
        col.metric(label, value, help=formula)
        if sub:
            col.caption(sub)


def render_calculators():
    st.markdown("### Derive parameters from your data")
    st.caption(
        "Plug in locally-monitored quantities — each result updates live. These are the "
        "same tactical formulas carried in the app's parameter tooltips. Fields are "
        "pre-filled with **example values**; replace them with your own. For "
        "transmissibility and immunity, a full ABC-SMC calibration is preferred over any "
        "single point estimate."
    )

    # ---- Transmission & clinical course ----
    st.markdown("**Transmission & clinical course**")
    r = st.columns(3)
    with r[0].container(border=True):
        st.markdown("**R₀** · early case growth")
        c1 = st.number_input("Early weekly cases C₁", 0.0, value=10.0, step=1.0, key="r0_c1")
        c2 = st.number_input("Later weekly cases C₂", 0.0, value=22.0, step=1.0, key="r0_c2")
        dt = st.number_input("Days between", 1.0, value=7.0, step=1.0, key="r0_dt")
        D = st.number_input("Generation interval (d)", 1.0, value=30.0, step=1.0, key="r0_D")
        if c1 > 0 and c2 > 0 and dt > 0:
            gr = math.log(c2 / c1) / dt
            st.metric("R₀ ≈", f"{1 + gr * D:.1f}", help="r = ln(C₂/C₁)/Δt · R₀ = 1 + r·D")
            st.caption(f"growth r = {gr:.3f}/day")
        else:
            st.metric("R₀ ≈", "—")
    with r[1].container(border=True):
        st.markdown("**Incubation** · 1/ε")
        s = st.text_input("Onset−exposure intervals (d), comma-sep", "8, 9, 11, 7", key="inc_s")
        vals = [float(x) for x in s.replace(",", " ").split() if x.replace(".", "", 1).isdigit()]
        st.metric("Incubation ≈", f"{sum(vals)/len(vals):.1f} d" if vals else "—",
                  help="mean of the listed intervals")
    with r[2].container(border=True):
        st.markdown("**Infectious — naive** · 1/γ")
        m = st.number_input("Median onset→treatment (d)", 0.0, value=16.0, step=1.0, key="infN_m")
        st.metric("Infectious ≈", f"{min(21.0, m + 5):.1f} d", help="min(21, m + 5)")
    r = st.columns(3)
    with r[0].container(border=True):
        st.markdown("**Infectious — partial** · 1/γₚ")
        m = st.number_input("Median onset→treatment (d), vaccinated", 0.0, value=7.0, step=1.0, key="infP_m")
        st.metric("Infectious ≈", f"{min(21.0, m + 5):.1f} d", help="min(21, m + 5)")
    with r[1].container(border=True):
        st.markdown("**σ** · rel. infectiousness of Iₚ")
        sv = st.number_input("SAR, vaccinated index", 0.0, value=0.05, step=0.01, key="sig_sv")
        su = st.number_input("SAR, unvaccinated index", 0.0, value=0.25, step=0.01, key="sig_su")
        st.metric("σ ≈", f"{max(0.0, min(1.0, sv/su)):.2f}" if su > 0 else "—",
                  help="σ = SAR(vax) / SAR(unvax)")
    r[2].empty()

    # ---- Immunity & waning ----
    st.markdown("**Immunity & waning**")
    r = st.columns(3)
    with r[0].container(border=True):
        st.markdown("**δ** · rel. susceptibility of Sₚ")
        pcv = st.number_input("% of cases vaccinated (PCV)", 0.0, 100.0, 66.0, 1.0, key="del_pcv")
        ppv = st.number_input("Population coverage % (PPV)", 0.0, 100.0, 90.0, 1.0, key="del_ppv")
        p, q = pcv / 100.0, ppv / 100.0
        if 0 < p < 1 and 0 < q < 1:
            d = max(0.0, min(1.0, (p / (1 - p)) * ((1 - q) / q)))
            st.metric("δ ≈", f"{d:.2f}", help="δ = [PCV/(1−PCV)]·[(1−PPV)/PPV] = 1 − VE")
            st.caption(f"VE = {1 - d:.2f}")
        else:
            st.metric("δ ≈", "—")
    with r[1].container(border=True):
        st.markdown("**ω₁** · waning R→Sₚ")
        y = st.number_input("Years between surges", 0.5, value=4.0, step=0.5, key="om1_y")
        st.metric("ω₁ ≈", f"{y:.1f} y", help="ω₁ = mean inter-episode interval")
    with r[2].container(border=True):
        st.markdown("**ω₂** · waning Rₚ→S")
        T = st.number_input("Total immunity (y)", 1.0, value=20.0, step=1.0, key="om2_T")
        w1 = st.number_input("ω₁ (y)", 0.0, value=4.0, step=0.5, key="om2_w1")
        st.metric("ω₂ ≈", f"{T - w1:.1f} y", help="ω₂ = T − ω₁",
                  )
        if T - w1 <= 0:
            st.caption("total must exceed ω₁")
    r = st.columns(3)
    with r[0].container(border=True):
        st.markdown("**ω₃** · vaccine waning Sₚ→S")
        ve0 = st.number_input("Initial VE (0–1)", 0.0, 1.0, 0.80, 0.01, key="om3_ve0")
        vet = st.number_input("Later VE (0–1)", 0.0, 1.0, 0.50, 0.01, key="om3_vet")
        t = st.number_input("Years elapsed", 0.5, value=5.0, step=0.5, key="om3_t")
        if ve0 > vet > 0 and t > 0:
            st.metric("ω₃ ≈", f"{t * math.log(2) / math.log(ve0 / vet):.1f} y",
                      help="t½ = t · ln2 / ln(VE₀/VEₜ)")
        else:
            st.metric("ω₃ ≈", "—", help="need VE₀ > VEₜ > 0")
    r[1].empty(); r[2].empty()

    # ---- Seasonality ----
    st.markdown("**Seasonality**")
    r = st.columns(3)
    with r[0].container(border=True):
        st.markdown("**Seasonality peak day**")
        mon = st.number_input("Peak month (1–12)", 1, 12, 9, 1, key="pk_mon")
        st.metric("Day of year ≈", f"{int((mon - 1) * 30 + 15)}", help="day = (month − 1) × 30 + 15")
    with r[1].container(border=True):
        st.markdown("**Seasonality amplitude**")
        pk = st.number_input("Peak-month cases", 0.0, value=30.0, step=1.0, key="amp_pk")
        tr = st.number_input("Trough-month cases", 0.0, value=6.0, step=1.0, key="amp_tr")
        mn = st.number_input("Mean monthly cases", 0.0, value=12.0, step=1.0, key="amp_mn")
        if mn > 0:
            ratio = (pk - tr) / mn
            cat = "Low" if ratio < 0.5 else "Medium" if ratio < 1.0 else "Moderate" if ratio < 1.5 else "Strong"
            st.metric("Suggested →", cat, help="ratio = (peak − trough)/mean")
            st.caption(f"ratio = {ratio:.2f}")
        else:
            st.metric("Suggested →", "—")
    r[2].empty()

    # ---- From observed case counts ----
    st.markdown("**From observed case counts**")
    r = st.columns(3)
    with r[0].container(border=True):
        st.markdown("**Vaccinated share** · → Sₚ seed & target")
        yes = st.number_input("Cases up-to-date (Yes)", 0.0, value=311.0, step=1.0, key="vax_yes")
        no = st.number_input("Cases not up-to-date (No)", 0.0, value=160.0, step=1.0, key="vax_no")
        st.metric("Vaccinated share ≈", f"{100*yes/(yes+no):.1f}%" if (yes + no) > 0 else "—",
                  help="Yes / (Yes + No)")
    with r[1].container(border=True):
        st.markdown("**Hospitalization ratio** · IHR, per band")
        hosp = st.number_input("Hospitalized (band)", 0.0, value=30.0, step=1.0, key="ihr_h")
        cases = st.number_input("Total cases (band)", 0.0, value=100.0, step=1.0, key="ihr_c")
        st.metric("IHR ≈", f"{hosp/cases:.3f}" if cases > 0 else "—", help="IHR = hospitalized / cases")
    r[2].empty()


render_calculators()

st.divider()

# ---------------------------------------------------------------------------
# Full provenance document + link to the shareable interactive version
# ---------------------------------------------------------------------------
st.markdown("### Full provenance reference")
ARTIFACT_URL = "https://claude.ai/code/artifact/e82c6144-6f92-4aa8-ae4f-8ab3bbc5f6b2"
st.link_button("🧬 Open the shareable version (same calculators + tables)",
               ARTIFACT_URL, use_container_width=False)
st.caption("The shareable page is a private artifact — use its Share menu to grant your team access.")

_DOC = Path(__file__).resolve().parent.parent / "docs" / "parameter-references.md"
try:
    text = _DOC.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    st.markdown('<div class="ref-doc">', unsafe_allow_html=True)
    st.markdown("\n".join(lines))
    st.markdown("</div>", unsafe_allow_html=True)
except FileNotFoundError:
    st.error(f"Provenance document not found at {_DOC}. Expected docs/parameter-references.md.")

show_logos()
