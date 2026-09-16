# ui/setup_panel.py

import streamlit as st
import numpy as np
from ui.initial_conditions import render_initial_conditions
from ui.model_params import render_model_params
from ui.interventions import render_contact_interventions
from ui.scenarios import render_save_run_controls, render_saved_scenarios_list
from ui.vaccinations import render_vaccination_campaigns
from schemas import INITIAL_CONDITION_DEFAULTS, MODEL_PARAM_SCHEMAS
from state import reset_model_params_to_defaults, reset_initial_conditions_to_defaults, reset_workspace
from data.observed_datasets import OBSERVED_DATASETS, aggregate_to_bands, summary
from constants import DEFAULT_AGE_GROUPS


@st.dialog("Seasonality basis: multi-year NNDSS", width="large")
def _show_seasonality_dialog(est: dict) -> None:
    """Modal illustrating why a seasonal peak period was selected: overlay each
    year's normalised weekly curve, the multi-year average, and the chosen peak."""
    import altair as alt
    import pandas as pd

    st.markdown(f"**{est['area']}** · years {', '.join(str(y) for y in est['years'])} · {est['source']}")
    c = st.columns(4)
    c[0].metric("Peak week", f"{est['peak_week']}")
    c[1].metric("Peak day-of-year", f"{est['peak_day']}")
    c[2].metric("Amplitude", est["amplitude_label"])
    c[3].metric("Cross-year spread", f"±{est['peak_week_spread']:.0f} wk",
                help="Std. dev. of each year's own peak week. Large spread ⇒ the seasonal "
                     "timing is inconsistent across years (epidemic-dominated), so treat the "
                     "auto peak with caution.")

    per = est["per_year"].copy()
    per["year"] = per["year"].astype(str)
    avg = est["avg"]
    year_lines = (
        alt.Chart(per).mark_line(opacity=0.45, strokeWidth=1.5)
        .encode(
            x=alt.X("week:Q", title="MMWR week of year"),
            y=alt.Y("norm:Q", title="Weekly cases ÷ that year's mean"),
            color=alt.Color("year:N", title="Year", scale=alt.Scale(scheme="set2")),
            tooltip=["year:N", "week:Q", alt.Tooltip("norm:Q", format=".2f")],
        )
    )
    avg_line = (
        alt.Chart(avg).mark_line(color="#e8833a", strokeWidth=3)
        .encode(x="week:Q", y=alt.Y("smooth:Q", title="Weekly cases ÷ that year's mean"))
    )
    peak_rule = (
        alt.Chart(pd.DataFrame({"week": [est["peak_week"]]}))
        .mark_rule(color="#e8833a", strokeDash=[5, 3], strokeWidth=2)
        .encode(x="week:Q")
    )
    st.altair_chart(alt.layer(year_lines, avg_line, peak_rule).interactive(),
                    use_container_width=True)

    st.caption(
        "Each thin line is one year's weekly counts normalised by that year's own mean "
        "(so an epidemic year doesn't dominate the *shape*). The thick orange line is the "
        "multi-year average cycle; the dashed rule marks its peak week, which sets the "
        "model's seasonality peak day. Amplitude is the average cycle's robust trough/peak "
        "(10th/90th percentile) mapped to the nearest category."
    )
    if est["peak_week_spread"] >= 8:
        st.warning(
            f"Year-to-year peak timing varies by ±{est['peak_week_spread']:.0f} weeks — the "
            "multi-year signal here is closer to epidemic timing than a stable seasonal cycle. "
            "Sanity-check against the classic pertussis pattern (late summer / early autumn, "
            "≈ week 30–40) and override the seasonality peak manually if needed."
        )


@st.dialog("Observed data feeding the calibration", width="large")
def _show_observed_dialog(choice: str) -> None:
    """Modal popup: the exact observed dataset (raw rows + aggregated bands +
    the shares the calibrator targets)."""
    import pandas as pd

    meta = OBSERVED_DATASETS[choice]
    raw = meta["raw"]

    st.markdown(f"**{choice}**")
    if meta.get("note"):
        st.caption(meta["note"])
    if meta.get("source"):
        st.caption(f"Source: {meta['source']}")

    s = summary(raw)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total cases", f"{s['total']:,}")
    c2.metric("Up-to-date (Yes)", f"{s['Yes']:,}")
    c3.metric(
        "Vaccinated share",
        f"{s['partial_share']:.0%}" if s["partial_share"] is not None else "—",
        help="Yes / (Yes + No), excluding Unknown — the vaccinated-share target the calibrator fits.",
    )

    st.markdown("**Aggregated to model age bands** (what the calibrator actually uses)")
    bands = aggregate_to_bands(raw)
    band_df = pd.DataFrame([
        {
            "Age band": ag,
            "Naive (No)": bands[ag]["naive"],
            "Unknown": bands[ag]["Unknown"],
            "Partial (Yes)": bands[ag]["partial"],
            "Total": bands[ag]["total"],
            "Vaccinated share": (
                f"{bands[ag]['partial'] / (bands[ag]['naive'] + bands[ag]['partial']):.0%}"
                if (bands[ag]["naive"] + bands[ag]["partial"]) > 0 else "—"
            ),
        }
        for ag in DEFAULT_AGE_GROUPS
    ])
    st.dataframe(band_df, hide_index=True, use_container_width=True)
    st.caption(
        "Track mapping: **No** (not up to date) → naive track (I), "
        "**Yes** (up to date) → partial track (Iₚ). Unknown is excluded from the "
        "vaccinated-share target. Note: source rows labelled “50+” are folded into 50-64."
    )

    with st.expander("Raw source rows (as loaded)", expanded=False):
        raw_df = pd.DataFrame([
            {"Age label": k, "No": v["No"], "Unknown": v["Unknown"], "Yes": v["Yes"]}
            for k, v in raw.items()
        ])
        st.dataframe(raw_df, hide_index=True, use_container_width=True)
        st.download_button(
            "Download observed data (CSV)",
            data=raw_df.to_csv(index=False).encode("utf-8"),
            file_name=f"observed_{choice.split(',')[0].strip().replace(' ', '_')}.csv",
            mime="text/csv",
        )
    if meta.get("source_path"):
        st.caption(f"File: `{meta['source_path']}`")


def render_observed_panel(model: str, geography: str) -> None:
    """Pertussis: select an observed case dataset to overlay, seed from, or
    auto-calibrate against."""
    st.session_state.setdefault("observed_dataset", None)
    st.session_state.setdefault("observed_mode", "Off")

    names = ["None"] + list(OBSERVED_DATASETS.keys())
    current = st.session_state.get("observed_dataset") or "None"
    choice = st.selectbox(
        "Observed dataset",
        options=names,
        index=names.index(current) if current in names else 0,
        help="Real-world case data (by age and vaccination status) to compare against or seed from.",
    )
    st.session_state["observed_dataset"] = None if choice == "None" else choice

    if choice == "None":
        st.caption("Select a dataset to overlay it on results, seed the outbreak from it, or auto-calibrate.")
        return

    meta = OBSERVED_DATASETS[choice]
    st.caption(meta.get("note", ""))
    if meta.get("source"):
        st.caption(f"Source: {meta['source']}")
    if st.button("🔍 View observed data", use_container_width=True,
                 help="Show the exact case counts (raw rows and model-band aggregation) "
                      "that feed the calibration."):
        _show_observed_dialog(choice)
    hint = meta.get("geography_hint")
    if hint and hint != geography:
        st.info(f"This dataset is for **{hint}**. Set Geography to match for a like-for-like comparison.")

    st.radio(
        "Use the dataset as",
        options=["Off", "Overlay / compare", "Seed initial state"],
        key="observed_mode",
        help=(
            "Overlay / compare: show observed vs. modeled case age-distribution and "
            "vaccinated share after a run.  Seed initial state: start the outbreak "
            "from the observed counts (No→naive, Yes→partial), then project forward."
        ),
    )

    # ---- Auto-calibrate (coarse) --------------------------------------------
    st.markdown("**Auto-calibrate (coarse)**")
    st.caption(
        "Grid-search R₀, σ (partial infectiousness) and the Sₚ share of the immune "
        "pool to best match the observed vaccinated-share and age distribution. "
        "Uses a reduced number of stochastic runs for speed."
    )
    if st.button("Calibrate to observed", use_container_width=True):
        from state import build_current_config
        from engine.run import run_scenario
        from engine.calibration import calibrate_to_observed
        import engine.run as _runmod

        raw = meta["raw"]
        with st.spinner("Running coarse calibration (27 evaluations)…"):
            base = build_current_config(model, geography)
            old_nsim = _runmod.N_SIM
            _runmod.N_SIM = 5  # speed up the search
            try:
                res = calibrate_to_observed(base, raw, run_scenario)
            finally:
                _runmod.N_SIM = old_nsim

        best = res["best"]
        # Apply best params to the structured store and clear widget keys so the
        # inputs re-initialise to the calibrated values on rerun.
        mp_store = st.session_state["model_params"][model]
        mp_store["R0"] = float(best["R0"])
        mp_store["rel_infectiousness_partial"] = float(best["rel_infectiousness_partial"])
        st.session_state["initial_conditions"]["partial_immune_pct"] = float(best["partial_immune_pct"])
        for k in ("R0", "rel_infectiousness_partial"):
            st.session_state.pop(f"param_{model}_{k}", None)

        st.session_state["_calib_result"] = res
        st.rerun()

    res = st.session_state.get("_calib_result")
    if res:
        b = res["best"]
        st.success(
            f"Best fit → R₀={b['R0']}, σ={b['rel_infectiousness_partial']}, "
            f"Sₚ share={b['partial_immune_pct']}% · modeled vaccinated share "
            f"{b['modeled_partial_share']:.0%} vs observed "
            f"{res['observed']['overall_partial_share']:.0%} "
            f"(age-dist RMSE {b['age_dist_rmse']:.3f}). Applied — click Run to simulate."
        )

    # ---- Weekly incidence time series (shape target) ------------------------
    st.markdown("**Weekly incidence time series (shape target)**")
    st.caption(
        "Optional. Fit the *shape* of a weekly pertussis curve — growth rate, peak "
        "timing and seasonality — which the cross-tab cannot constrain and which is "
        "the main lever on R₀. Source: CDC NNDSS (every U.S. state, DC, and the "
        "national total)."
    )
    from data.weekly_sources import (WEEKLY_AREAS, load_weekly_pertussis,
                                      weekly_series_to_array, NATIONAL_LABEL)

    def _default_area() -> str:
        g = (geography or "").lower()
        for a in WEEKLY_AREAS:
            if a != NATIONAL_LABEL and a.lower().replace(" ", "_") in g:
                return a
        return WEEKLY_AREAS[0]

    wc = st.columns([0.55, 0.45])
    with wc[0]:
        _def = _default_area()
        w_area = st.selectbox("Reporting area", WEEKLY_AREAS,
                              index=WEEKLY_AREAS.index(_def), key="_weekly_area")
    with wc[1]:
        w_years = st.multiselect("MMWR years", [2022, 2023, 2024, 2025, 2026],
                                 default=[2024], key="_weekly_years")

    if st.button("Fetch weekly pertussis (CDC NNDSS)", use_container_width=True):
        try:
            with st.spinner(f"Fetching {w_area} weekly pertussis…"):
                wdf, wsrc = load_weekly_pertussis(w_area, years=w_years or None, refresh=True)
            if wdf is None or wdf.empty:
                st.warning("No weekly rows returned for that area/year selection.")
            else:
                st.session_state["_weekly_df"] = wdf
                st.session_state["_weekly_meta"] = {
                    "area": w_area, "years": list(w_years), "source": wsrc,
                    "series": weekly_series_to_array(wdf),
                }
                st.toast(f"Loaded {len(wdf)} weeks for {w_area}.")
        except Exception as exc:
            st.error(f"Could not fetch weekly data: {exc}")

    wmeta = st.session_state.get("_weekly_meta")
    if wmeta and st.session_state.get("_weekly_df") is not None:
        import pandas as pd
        import altair as alt
        wdf = st.session_state["_weekly_df"].copy()
        wdf["idx"] = range(len(wdf))
        wdf["cumulative"] = wdf["cases"].cumsum()
        st.caption(f"{wmeta['area']} · {len(wdf)} weeks · {wmeta['source']}")

        basis_label = st.radio(
            "Curve basis (chart & calibration fit)",
            options=["Cumulative totals", "Weekly totals"],
            index=0,
            horizontal=True,
            key="_weekly_basis",
            help="Cumulative: running total (a 0→1 S-curve when fitted). Weekly: "
                 "per-week new cases. This choice drives both the chart below and "
                 "the curve term used in ABC-SMC calibration.",
        )
        _cumulative = basis_label.startswith("Cumulative")
        y_col = "cumulative" if _cumulative else "cases"
        y_title = "Cumulative cases" if _cumulative else "Weekly cases"
        ch = (
            alt.Chart(wdf)
            .mark_line(color="#4c9be8")
            .encode(
                x=alt.X("idx:Q", title="Week index"),
                y=alt.Y(f"{y_col}:Q", title=y_title),
                tooltip=[alt.Tooltip("year:Q", title="Year"),
                         alt.Tooltip("week:Q", title="MMWR week"),
                         alt.Tooltip("cases:Q", title="Weekly"),
                         alt.Tooltip("cumulative:Q", title="Cumulative")],
            )
        )
        st.altair_chart(ch, use_container_width=True)
        st.checkbox("Use weekly curve in ABC-SMC calibration", value=True,
                    key="_weekly_fit_on",
                    help="Adds a peak-normalised curve-shape term (RMSE + peak-week "
                         "timing) to the ABC-SMC distance, alongside the age-distribution "
                         "and vaccinated-share terms.")
        st.slider("Weekly-fit weight", 0.0, 3.0, 1.0, 0.5, key="_weekly_weight",
                  help="Relative weight of the curve term vs the cross-tab terms.")
        _basis_txt = ("cumulative totals (normalised to the final total)" if _cumulative
                      else "weekly totals (peak-normalised)")
        st.caption(
            f"Calibration fits the **{_basis_txt}** by *shape* over the overlapping "
            "window from the simulation start, so choose a year window covering one "
            "outbreak season. Absolute magnitude is ignored (state counts vs a "
            "county-scaled model)."
        )

    # ---- Seasonality from multi-year NNDSS ----------------------------------
    st.markdown("**Seasonality (from multi-year NNDSS)**")
    st.caption(
        "Pin the seasonal peak timing and amplitude empirically from several years of "
        "NNDSS weekly cases, rather than free-fitting them (which lets R₀ absorb seasonal "
        "misfit). Applies to the model's seasonality peak-day and amplitude."
    )
    from data.weekly_sources import WEEKLY_AREAS, estimate_seasonality, NATIONAL_LABEL

    sc_ = st.columns([0.55, 0.45])
    with sc_[0]:
        _sdef = st.session_state.get("_weekly_area") or (
            _default_area() if "_default_area" in dir() else WEEKLY_AREAS[0])
        s_area = st.selectbox("Reporting area (seasonality)", WEEKLY_AREAS,
                              index=WEEKLY_AREAS.index(_sdef) if _sdef in WEEKLY_AREAS else 0,
                              key="_season_area")
    with sc_[1]:
        s_years = st.multiselect("Years (multi-year)", [2022, 2023, 2024, 2025, 2026],
                                 default=[2022, 2023, 2024, 2025, 2026], key="_season_years")

    sb = st.columns(2)
    with sb[0]:
        if st.button("Estimate & apply seasonality", use_container_width=True):
            try:
                with st.spinner(f"Estimating seasonality for {s_area}…"):
                    est = estimate_seasonality(s_area, years=s_years or None)
                if not est:
                    st.warning("No weekly data returned for that selection.")
                else:
                    st.session_state["_season_est"] = est
                    mp_store = st.session_state["model_params"][model]
                    mp_store["seasonality_peak_day"] = float(est["peak_day"])
                    mp_store["seasonality_amplitude"] = est["amplitude_label"]
                    for k in ("seasonality_peak_day", "seasonality_amplitude"):
                        st.session_state.pop(f"param_{model}_{k}", None)
                    st.toast(f"Applied: peak day {est['peak_day']} (week {est['peak_week']}), "
                             f"amplitude {est['amplitude_label']}.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not estimate seasonality: {exc}")
    with sb[1]:
        if st.button("Why this peak? (view traces)", use_container_width=True,
                     disabled=not st.session_state.get("_season_est")):
            _show_seasonality_dialog(st.session_state["_season_est"])

    _se = st.session_state.get("_season_est")
    if _se:
        _warn = " ⚠️ inconsistent across years" if _se["peak_week_spread"] >= 8 else ""
        st.success(
            f"Applied seasonality from {_se['area']} ({_se['n_years']} yrs): peak day "
            f"**{_se['peak_day']}** (week {_se['peak_week']}), amplitude **{_se['amplitude_label']}**"
            f"{_warn}. Adjust in Model parameters if needed."
        )

    # ---- Bayesian calibration (ABC-SMC) -------------------------------------
    st.markdown("**Calibrate (Bayesian · ABC-SMC)**")
    st.caption(
        "Approximate Bayesian Computation with Sequential Monte Carlo. Returns posterior medians "
        "and 95% credible intervals for R₀, σ, δ and the Sₚ share, fit to the observed "
        "vaccinated-share and age distribution. Heavier than the coarse search — expect a few minutes."
    )
    if st.session_state.get("_weekly_fit_on") and st.session_state.get("_weekly_meta"):
        _wm = st.session_state["_weekly_meta"]
        _basis = ("cumulative" if str(st.session_state.get("_weekly_basis", "")).startswith("Cumulative")
                  else "weekly")
        st.info(f"Curve fit **active** ({_basis} totals): {_wm['area']} "
                f"({', '.join(str(y) for y in _wm['years']) or 'all years'}) — "
                f"weight {st.session_state.get('_weekly_weight', 1.0):g}. This sharply "
                "tightens the R₀ posterior.")
    ac = st.columns(2)
    with ac[0]:
        abc_particles = st.slider("Particles", 20, 80, 40, 10,
                                  help="Posterior sample size. More = smoother posterior, longer runtime.")
    with ac[1]:
        abc_rounds = st.slider("SMC rounds", 2, 5, 3, 1,
                               help="Refinement rounds with a shrinking tolerance. More = tighter fit, longer runtime.")

    multi_trace = st.checkbox(
        "Average multiple simulated traces per evaluation", value=True, key="_abc_multi_trace",
        help="On: evaluate each candidate as an ensemble of stochastic replicates and use the "
             "median trace, so noise doesn't distort the distance (more robust, slower). "
             "Off: a single simulated trace per candidate (faster, noisier).",
    )
    abc_nsim = 1
    if multi_trace:
        abc_nsim = st.slider("Traces per evaluation", 2, 7, 3, 1, key="_abc_nsim",
                             help="Number of stochastic replicates averaged per candidate during the search.")
    if st.button("Run ABC-SMC calibration", use_container_width=True):
        from state import build_current_config
        from engine.run import run_scenario
        from engine.calibration import abc_smc_calibrate
        import engine.run as _runmod

        raw = meta["raw"]
        prog = st.progress(0.0, text="Starting ABC-SMC…")

        def _cb(frac, msg):
            prog.progress(min(1.0, float(frac)), text=msg)

        base = build_current_config(model, geography)
        # Attach the weekly-incidence shape target if the user enabled it.
        if st.session_state.get("_weekly_fit_on") and st.session_state.get("_weekly_meta"):
            base["weekly_target"] = st.session_state["_weekly_meta"]["series"]
            base["weekly_weight"] = float(st.session_state.get("_weekly_weight", 1.0))
            base["weekly_mode"] = ("cumulative"
                                   if str(st.session_state.get("_weekly_basis", "")).startswith("Cumulative")
                                   else "weekly")
        old_nsim = _runmod.N_SIM
        _runmod.N_SIM = int(abc_nsim)  # single trace, or an averaged ensemble per candidate
        try:
            abc = abc_smc_calibrate(base, raw, run_scenario,
                                    n_particles=int(abc_particles), n_rounds=int(abc_rounds), progress=_cb)
        finally:
            _runmod.N_SIM = old_nsim
        prog.progress(1.0, text="Done")

        # Apply posterior medians to the scenario
        s = abc["summary"]
        mp_store = st.session_state["model_params"][model]
        mp_store["R0"] = round(s["R0"]["median"], 2)
        mp_store["rel_infectiousness_partial"] = round(s["rel_infectiousness_partial"]["median"], 3)
        mp_store["rel_susceptibility_partial"] = round(s["rel_susceptibility_partial"]["median"], 3)
        st.session_state["initial_conditions"]["partial_immune_pct"] = round(s["partial_immune_pct"]["median"], 1)
        for k in ("R0", "rel_infectiousness_partial", "rel_susceptibility_partial"):
            st.session_state.pop(f"param_{model}_{k}", None)
        st.session_state["_abc_result"] = abc
        st.rerun()

    abc_res = st.session_state.get("_abc_result")
    if abc_res:
        import pandas as pd
        s = abc_res["summary"]
        st.success(
            f"Posterior applied (medians) — {abc_res['n_particles']} particles over "
            f"{abc_res['rounds_completed']} round(s). Click Run to simulate."
        )
        table = pd.DataFrame([
            {"Parameter": s[k]["label"],
             "Posterior median": f"{s[k]['median']:.3g}",
             "95% credible interval": f"{s[k]['lo']:.3g} – {s[k]['hi']:.3g}"}
            for k in abc_res["params"]
        ])
        st.dataframe(table, hide_index=True, use_container_width=True)

        # ---- Posterior-predictive projection --------------------------------
        st.markdown("**Posterior-predictive projection**")
        st.caption(
            "Propagate the calibrated parameter uncertainty into the outbreak "
            "trajectory: resample parameter sets from the posterior above, simulate "
            "each, and shade the resulting band. This band reflects uncertainty in "
            "the parameters themselves — distinct from the stochastic band, which "
            "fixes the parameters. Appears as a dashed orange band on the "
            "Trajectories chart."
        )
        pp_draws = st.slider(
            "Posterior draws", 20, 100, 30, 10, key="_abc_pp_draws",
            help="Parameter sets resampled from the posterior, each simulated. More = "
                 "smoother band, longer runtime.",
        )
        if st.button("Run posterior-predictive projection", use_container_width=True):
            from state import build_current_config
            from engine.run import run_scenario
            from engine.calibration import posterior_predictive
            import engine.run as _runmod

            prog = st.progress(0.0, text="Starting posterior-predictive…")

            def _cb_pp(frac, msg):
                prog.progress(min(1.0, float(frac)), text=msg)

            base = build_current_config(model, geography)
            old_nsim = _runmod.N_SIM
            _runmod.N_SIM = 3  # reduced replicates per draw
            try:
                pp = posterior_predictive(base, abc_res, run_scenario,
                                          n_draws=int(pp_draws), progress=_cb_pp)
            finally:
                _runmod.N_SIM = old_nsim
            prog.progress(1.0, text="Done")

            if pp is None:
                st.warning("Posterior-predictive projection produced no usable draws.")
            else:
                st.session_state["_abc_ppc"] = pp
                st.toast(f"Posterior-predictive band ready ({pp['n_draws']} draws) — "
                         "see the Trajectories tab.")
                st.rerun()

        if st.session_state.get("_abc_ppc"):
            _pp = st.session_state["_abc_ppc"]
            st.success(
                f"Posterior-predictive band ready — {_pp['n_draws']} draws. "
                "Toggle it on the Trajectories chart's uncertainty controls."
            )


def _on_model_change():
    m = st.session_state["selected_model"]
    reset_model_params_to_defaults(m, MODEL_PARAM_SCHEMAS)
    reset_initial_conditions_to_defaults(m, INITIAL_CONDITION_DEFAULTS)


def _us_only(locations):
    """Restrict the geography list to United States entries (national, state and
    county). All U.S. locations in epydemix-data are prefixed 'United_States',
    which excludes 'United_Kingdom' / 'United_Arab_Emirates'. Falls back to the
    full list if no U.S. entries are present."""
    us = [loc for loc in locations if str(loc).startswith("United_States")]
    return us or list(locations)


def render_setup_panel(load_locations_fn, model_param_schemas):
    st.subheader("Setup")

    # Initialize workspace early if scenarios/results exist but workspace doesn't
    scenarios_exist = bool(st.session_state.get("scenarios"))
    results_exist = bool(st.session_state.get("results"))

    # Geography menu is restricted to the United States (this is a US-focused
    # pertussis tool). Loaded once and reused for the default and the selectbox.
    locations = _us_only(load_locations_fn())

    # Get current selections early (before any UI elements)
    st.session_state.setdefault("selected_model", "SEIR (Measles)")
    st.session_state.setdefault("selected_geography", locations[0])
    
    # Initialize workspace if needed BEFORE checking workspace_active
    if st.session_state.get("workspace") is None and (scenarios_exist or results_exist):
        st.session_state["workspace"] = {
            "model": st.session_state["selected_model"],
            "geography": st.session_state["selected_geography"]
        }
    
    # Now get the workspace state
    workspace = st.session_state.get("workspace")
    workspace_active = (workspace is not None)

    # Show workspace info if active
    if workspace_active:
        with st.container(border=True):
            st.markdown("**Workspace**")
            st.caption(
                f"{workspace['model']} · {workspace['geography']} — scenario comparison is restricted to this context. Start a new session to change the model or geography."
            )

            if st.button("Start new session", type="primary", use_container_width=True):
                reset_workspace()
                st.rerun()

    # Model & geography
    c1, c2 = st.columns(2)
    with c1:
        model = st.selectbox(
            "Model",
            options=["SEIR (Measles)", "SEIRS (Influenza)", "SEIRS (Pertussis)", "SEIHR (COVID-19)"],
            key="selected_model",
            on_change=_on_model_change,
            disabled=workspace_active,
            help=("Disease model to simulate. 'SEIRS (Pertussis)' activates the 8-compartment "
                  "partial-immunity structure. Locked once a scenario is run — use 'Start new "
                  "session' to change it."),
        )
    
    with c2:
        geography = st.selectbox(
            "Geography",
            options=locations,
            key="selected_geography",
            help=("Location whose population age structure and home/school/work/community contact "
                  "matrices are used (from epydemix-data). Type to search. How to derive: pick the "
                  "administrative area matching your setting (e.g. a Lane County, Oregon entry)."),
            disabled=workspace_active,
        )

    # Simulation length and time step
    c1, c2 = st.columns(2)
    with c1:
        st.number_input(
            "Simulation length (days)",
            min_value=1,
            max_value=5000,
            value=250,
            step=10,
            help=("Total run duration in days. How to derive: match your analysis window — a single "
                  "outbreak season ≈ 150–365 days; multi-year endemic/booster studies need longer, "
                  "since waning and resurgence take years to appear."),
            key="sim_length",
        )
    
    with c2:
        st.number_input(
            "$\Delta t$ (days)",
            min_value=0.1,
            max_value=1.0,
            value=0.2,
            step=0.1,
            help="Time step for the simulation. Smaller values result in more accurate simulations but require more computational resources.",
            key="time_step",
        )

    # Scenario controls (use model/geography)
    render_save_run_controls(model, geography)

    st.caption("Change the settings below to create custom scenarios.")

    # Expanders
    with st.expander("Initial conditions", expanded=False):
        render_initial_conditions(model, INITIAL_CONDITION_DEFAULTS)

    with st.expander("Model parameters", expanded=False):
        render_model_params(model, model_param_schemas)
        st.page_link(
            "pages/Model_References.py",
            label="📖 Parameter provenance & references — where these values come from",
            help="Sources, ranges, priors and evidence tier for every parameter, plus "
                 "data → parameter calculators.",
        )

    with st.expander("Contact interventions", expanded=False):
        render_contact_interventions()

    with st.expander("Vaccination campaigns", expanded=False):
        render_vaccination_campaigns(model)

    if model == "SEIRS (Pertussis)":
        # Keep the panel open after a calibration so its results table stays visible
        # (a calibration triggers a rerun, which would otherwise collapse it).
        _obs_open = bool(st.session_state.get("_abc_result")
                         or st.session_state.get("_calib_result")
                         or st.session_state.get("_abc_ppc")
                         or st.session_state.get("_weekly_meta"))
        with st.expander("Observed data & calibration", expanded=_obs_open):
            render_observed_panel(model, geography)

    render_saved_scenarios_list()

    return model, geography