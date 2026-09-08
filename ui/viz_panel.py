# ui/viz_panel.py

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from copy import deepcopy
from .plots import plot_contact_matrix, plot_population
from helpers import contact_matrix_df
from schemas import MODEL_COMPS
from constants import DEFAULT_AGE_GROUPS
from collections import OrderedDict
from engine.hospitalization import (
    HOSP_AGE_GROUPS, HOSP_DEFAULTS, hospitalizations_from_trans, hospitalization_summary,
)

ages_to_idx = {ag: i for i, ag in enumerate(DEFAULT_AGE_GROUPS)}


def compute_metrics_with_deltas(selected_ids, reference_id, scenarios, results):
    base = compute_summary_metrics(selected_ids, scenarios, results)
    if base.empty:
        return base

    ref_name = scenarios[reference_id].get("name", reference_id)

    ref = base[base["scenario"] == ref_name][
        ["age_group", "peak_day", "peak_amplitude", "attack_rate", "total_infections", "hospitalizations", "hospitalization_rate"]
    ].rename(
        columns={
            "peak_day": "peak_day_ref",
            "peak_amplitude": "peak_amplitude_ref",
            "attack_rate": "attack_rate_ref",
            "total_infections": "total_infections_ref",
            "hospitalizations": "hospitalizations_ref",
            "hospitalization_rate": "hospitalization_rate_ref",
        }
    )

    out = base.merge(ref, on="age_group", how="left")

    # deltas
    for m in ["peak_day", "peak_amplitude", "attack_rate", "total_infections", "hospitalizations", "hospitalization_rate"]:
        out[f"{m}_delta"] = out[m] - out[f"{m}_ref"]

        denom = out[f"{m}_ref"].replace({0.0: pd.NA})
        out[f"{m}_pct_delta"] = (out[f"{m}_delta"] / denom) * 100.0

    out["reference"] = ref_name
    return out


def compute_summary_metrics(selected_ids, scenarios, results):
    rows = []

    for sid in selected_ids:
        df_comp, df_trans = results[sid]["compartments"], results[sid]["transitions"]
        name = scenarios[sid].get("name", sid)
        cfg = scenarios[sid].get("config", {})
        population = cfg.get("population", {})
        model = cfg.get("model", "")
        geo = cfg.get("geography", "")

        t = df_comp["t"].to_numpy()

        for ag in DEFAULT_AGE_GROUPS + ["total"]:
            i_col = f"I_{ag}"
            r_col = f"R_{ag}"
            h_col = f"H_{ag}"

            e_to_i_col = f"E_to_I_{ag}"

            I = df_comp[i_col].to_numpy()
            R = df_comp[r_col].to_numpy()
            E_to_I = df_trans[e_to_i_col].to_numpy()

            # Pertussis has a parallel partial-immunity track (Ip). Include it in
            # prevalence and new-infection metrics so the "silent" partial cases
            # are not undercounted.
            if model == "SEIRS (Pertussis)":
                ip_col = f"Ip_{ag}"
                ep_to_ip_col = f"Ep_to_Ip_{ag}"
                if ip_col in df_comp.columns:
                    I = I + df_comp[ip_col].to_numpy()
                if ep_to_ip_col in df_trans.columns:
                    E_to_I = E_to_I + df_trans[ep_to_ip_col].to_numpy()

            peak_idx = int(I.argmax())
            peak_day = int(t[peak_idx])
            peak_amp = float(I[peak_idx])
            total_infections = float(np.sum(E_to_I))

            if ag == "total":
                attack_rate = 100.0 * float(np.sum(E_to_I) / population.Nk.sum())
            else:
                attack_rate = 100.0 * float(np.sum(E_to_I) / population.Nk[ages_to_idx[ag]])

            if model == "SEIHR (COVID-19)":
                H = df_comp[h_col].to_numpy()
                hospitalizations = float(np.sum(H))
                if ag == "total":
                    hospitalization_rate = 100.0 * float(np.sum(H) / population.Nk.sum())
                else:
                    hospitalization_rate = 100.0 * float(np.sum(H) / population.Nk[ages_to_idx[ag]])
            else:
                hospitalizations = None
                hospitalization_rate = None
            
            rows.append(
                {
                    "scenario": name,
                    "model": model,
                    "geography": geo,
                    "age_group": ag,
                    "peak_day": peak_day,
                    "peak_amplitude": peak_amp,
                    "attack_rate": attack_rate,
                    "total_infections": total_infections,
                    "hospitalizations": hospitalizations,
                    "hospitalization_rate": hospitalization_rate,
                }
            )

    out = pd.DataFrame(rows)

    # Nice ordering for display
    if not out.empty:
        out = out.sort_values(["scenario", "age_group"]).reset_index(drop=True)

    return out


def _get_run_scenarios():
    scenarios = st.session_state.get("scenarios", {})
    results = st.session_state.get("results", {})
    # only scenarios that have results
    run_ids = [sid for sid in scenarios.keys() if sid in results]
    return run_ids, scenarios, results


def render_spectral_radius_timeseries(dfs_dict: dict) -> None:
    """
    Render spectral radius timeseries comparison across scenarios.
    
    Args:
        dfs_dict: Dictionary of {scenario_name: spectral_radius_df}
                 Each df has columns: t, rho, rho_perc, layer
    """
    if not dfs_dict:
        st.warning("No spectral radius data available.")
        return

    st.caption("Compare contact matrix spectral radius across scenarios.")

    # Prepare combined dataframe
    all_data = []
    layers_set = set()
    
    for scenario_name, df in dfs_dict.items():
        if not isinstance(df, pd.DataFrame) or "t" not in df.columns:
            continue
        
        required_cols = ["t", "rho", "rho_perc", "layer"]
        if not all(col in df.columns for col in required_cols):
            continue
        
        layers_set.update(df["layer"].unique())
        df_copy = df.copy()
        df_copy["scenario"] = scenario_name
        all_data.append(df_copy)
    
    if not all_data:
        st.warning("No valid spectral radius data to display.")
        return
    
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Get available layers in desired order
    layer_order = ["overall", "home", "school", "work", "community"]
    available_layers = [layer for layer in layer_order if layer in layers_set]
    
    # Controls
    col1, col2 = st.columns(2)
    
    with col1:
        mode = st.radio(
            "View",
            options=["Percentage change", "Absolute value"],
            horizontal=True,
            key="spectral_radius_mode",
        )
    
    with col2:
        selected_layer = st.selectbox(
            "Contact layer",
            options=available_layers,
            index=0,  # Default to first available (typically "overall")
            key="spectral_radius_layer"
        )
    
    # Filter data for selected layer
    plot_data = combined_df[combined_df["layer"] == selected_layer]
    
    # Determine which column to plot
    y_col = "rho_perc" if mode == "Percentage change" else "rho"
    y_title = "Spectral radius (% change)" if mode == "Percentage change" else "Spectral radius"
    
    # Create chart with all scenarios as different colored lines
    chart = (
        alt.Chart(plot_data)
        .mark_line(strokeWidth=2, point=True)
        .encode(
            x=alt.X("t:Q", title="Day"),
            y=alt.Y(
                f"{y_col}:Q", 
                title=y_title
            ),
            color=alt.Color(
                "scenario:N", 
                title="Scenario",
                scale=alt.Scale(scheme="set2")
            ),
            tooltip=[
                alt.Tooltip("scenario:N", title="Scenario"),
                alt.Tooltip("t:Q", title="Day"),
                alt.Tooltip(f"{y_col}:Q", title=y_title, format=".3f"),
            ],
        )
        .interactive()
    )
    
    st.altair_chart(chart, use_container_width=True)
    

def render_vaccination_timeseries(dfs_dict: dict) -> None:
    """
    Render vaccination timeseries comparison across scenarios.
    
    Args:
        dfs_dict: Dictionary of {scenario_name: vaccination_df}
    """
    if not dfs_dict:
        st.warning("No vaccination schedules available.")
        return

    st.caption("Compare vaccination rollout across scenarios.")

    # Controls
    col1, col2 = st.columns(2)
    
    with col1:
        mode = st.radio(
            "View",
            options=["Daily doses", "Cumulative doses"],
            horizontal=True,
            key="vax_plot_mode",
        )
    
    # Prepare combined long dataframe
    all_data = []
    age_groups_set = set()
    
    for scenario_name, df in dfs_dict.items():
        if not isinstance(df, pd.DataFrame) or "t" not in df.columns:
            continue
        
        age_cols = [c for c in df.columns if c != "t"]
        if not age_cols:
            continue
        
        age_groups_set.update(age_cols)
        plot_df_vax = df[["t"] + age_cols].copy()

        if mode == "Cumulative doses":
            plot_df_vax[age_cols] = plot_df_vax[age_cols].cumsum()

        long_df = plot_df_vax.melt(
            id_vars="t", 
            value_vars=age_cols, 
            var_name="age_group", 
            value_name="doses"
        )
        long_df["scenario"] = scenario_name
        all_data.append(long_df)
    
    if not all_data:
        st.warning("No valid vaccination schedules to display.")
        return
    
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Age group selector
    with col2:
        selected_age = st.selectbox(
            "Age group",
            options=DEFAULT_AGE_GROUPS + ["total"],
            key="vax_age_selector"
        )
    
    # Filter data for selected age group
    plot_data = combined_df[combined_df["age_group"] == selected_age]
    
    # Create chart with all scenarios as different colored lines
    chart = (
        alt.Chart(plot_data)
        .mark_line(strokeWidth=2., point=False)
        .encode(
            x=alt.X("t:Q", title="Day"),
            y=alt.Y(
                "doses:Q", 
                title="Doses" if mode == "Daily doses" else "Cumulative doses"
            ),
            color=alt.Color(
                "scenario:N", 
                title="Scenario", 
                scale=alt.Scale(scheme="set2")
            ),
            tooltip=[
                alt.Tooltip("scenario:N", title="Scenario"),
                alt.Tooltip("t:Q", title="Day"),
                alt.Tooltip("doses:Q", title="Doses", format=","),
            ],
        )
        .interactive()
    )
    
    st.altair_chart(chart, use_container_width=True)
    

def render_compartment_timeseries(compartments, selected_ids, scenarios, results):

    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        comp_idx = np.where(np.array(compartments) == "I")[0][0]
        comp = st.selectbox("Compartment", options=compartments, index=int(comp_idx))

    with col2:
        total_ages = ["total"] + DEFAULT_AGE_GROUPS
        age = st.selectbox("Age group", options=total_ages, index=0)

    band_choice = st.radio(
        "Uncertainty band",
        options=["None", "50%", "90%", "95%"],
        index=2,
        horizontal=True,
        help="Shaded percentile band around the median across the stochastic replicates: "
             "50% = 25th–75th, 90% = 5th–95th, 95% = 2.5th–97.5th.",
    )
    _BANDS = {"50%": (0.25, 0.75), "90%": (0.05, 0.95), "95%": (0.025, 0.975)}

    # ---- Prepare long dataframe for plotting
    series_col = f"{comp}_{age}" if age != "" else comp

    rows = []
    band_rows = []
    for sid in selected_ids:
        df = results[sid]["compartments"]
        if series_col not in df.columns:
            continue  # should not happen due to intersection logic
        label = scenarios[sid].get("name", sid)

        tmp = df[["t", series_col]].copy()
        tmp.rename(columns={series_col: "value"}, inplace=True)
        tmp["scenario"] = label
        rows.append(tmp)

        # Single shaded band (selected level) around the median
        ci = results[sid].get("compartments_ci")
        if band_choice != "None" and ci is not None and series_col in ci.columns and "quantile" in ci.columns:
            qlo, qhi = _BANDS[band_choice]
            lo = ci[np.isclose(ci["quantile"], qlo)][["t", series_col]].rename(columns={series_col: "lo"})
            hi = ci[np.isclose(ci["quantile"], qhi)][["t", series_col]].rename(columns={series_col: "hi"})
            bnd = lo.merge(hi, on="t")
            bnd["scenario"] = label
            band_rows.append(bnd)

    plot_df = pd.concat(rows, ignore_index=True)

    series_col_label = series_col.replace("_", " (") + ")"

    # ---- Posterior-predictive (parameter-uncertainty) from an ABC-SMC run.
    # Distinct orange style; can be shown as a band, individual per-draw traces, or both.
    pp = st.session_state.get("_abc_ppc")
    pp_area = pp_med = pp_traces = None
    pp_caption = ""
    if pp is not None and isinstance(pp.get("compartments_pp"), pd.DataFrame):
        cpp = pp["compartments_pp"]
        draws = pp.get("compartments_draws")
        has_draws = isinstance(draws, pd.DataFrame) and series_col in getattr(draws, "columns", [])
        modes = ["Off", "Band"] + (["Individual traces", "Band + traces"] if has_draws else [])
        pcols = st.columns([0.6, 0.4])
        with pcols[0]:
            pp_mode = st.radio(
                "ABC posterior-predictive", modes, index=1, horizontal=True, key="_pp_mode",
                help="Parameter-uncertainty from the ABC-SMC posterior (parameter sets "
                     "resampled and each simulated). Band = shaded percentile band + median; "
                     "Individual traces = one line per posterior draw (spaghetti); Both = overlay.",
            )
        with pcols[1]:
            pp_level = st.radio(
                "Posterior band level", ["50%", "90%", "95%"], index=2,
                horizontal=True, key="_pp_band_level", label_visibility="collapsed",
            )
        want_band = pp_mode in ("Band", "Band + traces")
        want_traces = pp_mode in ("Individual traces", "Band + traces")

        if want_band and series_col in cpp.columns and "quantile" in cpp.columns:
            qlo, qhi = _BANDS[pp_level]
            plo = cpp[np.isclose(cpp["quantile"], qlo)][["t", series_col]].rename(columns={series_col: "lo"})
            phi = cpp[np.isclose(cpp["quantile"], qhi)][["t", series_col]].rename(columns={series_col: "hi"})
            pmed = cpp[np.isclose(cpp["quantile"], 0.5)][["t", series_col]].rename(columns={series_col: "med"})
            pband = plo.merge(phi, on="t")
            pp_area = (
                alt.Chart(pband)
                .mark_area(opacity=0.18, color="#e8833a")
                .encode(
                    x=alt.X("t:Q", title="Day"),
                    y=alt.Y("lo:Q", title=series_col_label),
                    y2="hi:Q",
                    tooltip=[alt.Tooltip("lo:Q", title="Posterior lo"),
                             alt.Tooltip("hi:Q", title="Posterior hi")],
                )
            )
            pp_med = (
                alt.Chart(pmed)
                .mark_line(strokeDash=[5, 3], color="#e8833a", strokeWidth=2)
                .encode(x="t:Q", y="med:Q",
                        tooltip=[alt.Tooltip("med:Q", title="Posterior median")])
            )
            pp_caption += f"  ·  dashed orange = posterior {pp_level} band"

        if want_traces and has_draws:
            dtr = draws[["t", "draw", series_col]].rename(columns={series_col: "value"})
            pp_traces = (
                alt.Chart(dtr)
                .mark_line(color="#e8833a", opacity=0.16, strokeWidth=1)
                .encode(
                    x=alt.X("t:Q", title="Day"),
                    y=alt.Y("value:Q", title=series_col_label),
                    detail="draw:N",
                    tooltip=[alt.Tooltip("draw:N", title="Draw"), "t:Q",
                             alt.Tooltip("value:Q", title="Value")],
                )
            )
            pp_caption += f"  ·  {pp['n_draws']} posterior traces"

    st.caption(f"Showing: {series_col_label} (median line)"
               + (f"  ·  shaded = {band_choice} band" if band_rows else "")
               + pp_caption)

    line = (
        alt.Chart(plot_df)
        .mark_line()
        .encode(
            x=alt.X("t:Q", title="Day"),
            y=alt.Y("value:Q", title=series_col_label),
            color=alt.Color("scenario:N", title="Scenario", scale=alt.Scale(scheme="set2")),
            tooltip=["scenario:N", "t:Q", "value:Q"],
        )
    )

    layers = []
    # Posterior-predictive underneath (parameter uncertainty): band, then traces
    if pp_area is not None:
        layers.append(pp_area)
    if pp_traces is not None:
        layers.append(pp_traces)
    if band_rows:
        band_df = pd.concat(band_rows, ignore_index=True)
        area = (
            alt.Chart(band_df)
            .mark_area(opacity=0.22)
            .encode(
                x=alt.X("t:Q", title="Day"),
                y=alt.Y("lo:Q", title=series_col_label),
                y2="hi:Q",
                color=alt.Color("scenario:N", title="Scenario", scale=alt.Scale(scheme="set2"), legend=None),
                tooltip=["scenario:N", "t:Q", alt.Tooltip("lo:Q", title="Lower"), alt.Tooltip("hi:Q", title="Upper")],
            )
        )
        layers.append(area)
    layers.append(line)
    # Posterior-predictive median (dashed) on top
    if pp_med is not None:
        layers.append(pp_med)

    chart = alt.layer(*layers).interactive()
    st.altair_chart(chart, use_container_width=True)


def _metric_ci_bounds(selected_ids, scenarios, results, metric, model, qlo, qhi):
    """Per-(scenario, age band) lower/upper bounds for a metric at the requested
    quantiles, computed from the stored compartment/transition quantile frames.
    Returns a DataFrame [scenario, age_group, ci_lo, ci_hi] (empty if unavailable).
    Timing metrics (peak_day) are not supported and yield no rows."""
    ages = DEFAULT_AGE_GROUPS
    idx = {a: i for i, a in enumerate(ages)}
    out = []

    def q_series(df, col, q):
        if df is None or "quantile" not in df.columns or col not in df.columns:
            return None
        return df[np.isclose(df["quantile"], q)][col].to_numpy()

    for sid in selected_ids:
        name = scenarios[sid].get("name", sid)
        cfg = scenarios[sid].get("config", {})
        pop = cfg.get("population")
        comp_ci = results[sid].get("compartments_ci")
        trans_ci = results[sid].get("transitions_ci")
        if pop is None:
            continue
        Nk = pop.Nk
        for ag in ages + ["total"]:
            n = float(Nk.sum()) if ag == "total" else float(Nk[idx[ag]])

            def peak(q):
                I = q_series(comp_ci, f"I_{ag}", q)
                if I is None:
                    return None
                Ip = q_series(comp_ci, f"Ip_{ag}", q) if model == "SEIRS (Pertussis)" else None
                base = (I + Ip) if Ip is not None else I
                return float(base.max())

            def new_infections(q):
                E = q_series(trans_ci, f"E_to_I_{ag}", q)
                if E is None:
                    return None
                Ep = q_series(trans_ci, f"Ep_to_Ip_{ag}", q) if model == "SEIRS (Pertussis)" else None
                s = (E + Ep) if Ep is not None else E
                return float(s.sum())

            def h_sum(q):
                H = q_series(comp_ci, f"H_{ag}", q)
                return float(H.sum()) if H is not None else None

            lo = hi = None
            if metric == "peak_amplitude":
                lo, hi = peak(qlo), peak(qhi)
            elif metric == "total_infections":
                lo, hi = new_infections(qlo), new_infections(qhi)
            elif metric == "attack_rate":
                a, b = new_infections(qlo), new_infections(qhi)
                if a is not None and n > 0:
                    lo, hi = 100.0 * a / n, 100.0 * b / n
            elif metric == "hospitalizations":
                lo, hi = h_sum(qlo), h_sum(qhi)
            elif metric == "hospitalization_rate":
                a, b = h_sum(qlo), h_sum(qhi)
                if a is not None and n > 0:
                    lo, hi = 100.0 * a / n, 100.0 * b / n

            if lo is not None and hi is not None:
                if lo > hi:
                    lo, hi = hi, lo
                out.append({"scenario": name, "age_group": ag, "ci_lo": lo, "ci_hi": hi})

    return pd.DataFrame(out)


def render_metrics_tab(primary_id, selected_ids, scenarios, results):
    """
    Render the summary metrics tab with comparison to reference scenario.
    
    Args:
        primary_id: ID of the primary/reference scenario
        selected_ids: List of scenario IDs to include (primary + comparisons)
        scenarios: Dictionary of all scenarios
        results: Dictionary of all results
    """
    if not selected_ids:
        st.info("Select at least one scenario to compute summary metrics.")
        return
    
    metrics = compute_metrics_with_deltas(selected_ids, primary_id, scenarios, results)
    if metrics.empty:
        st.warning("No metrics available for the selected scenarios.")
        return
    
    model = scenarios[primary_id]["config"]["model"]
    if model == "SEIHR (COVID-19)":
        metrics_labels = {
            "attack_rate": "Final Attack Rate (%)",
            "total_infections": "Total Infections",
            "peak_day": "Peak Prevalence Day",
            "peak_amplitude": "Peak Prevalence Amplitude",
            "hospitalizations": "Total Hospitalizations",
            "hospitalization_rate": "Hospitalization Rate (%)",
        }
    else:
        metrics_labels = {
            "attack_rate": "Final Attack Rate (%)",
            "total_infections": "Total Infections",
            "peak_day": "Peak Prevalence Day",
            "peak_amplitude": "Peak Prevalence Amplitude",
        }

    metric = st.selectbox("Metric", options=metrics_labels.keys(), format_func=lambda x: metrics_labels[x])

    view = st.radio(
        "Display",
        options=["Absolute", "Δ vs reference", "Relative Δ vs reference"],
        horizontal=True,
    )

    if view == "Absolute":
        value_col = metric
        y_title = metrics_labels[metric]
    elif view == "Δ vs reference":
        value_col = f"{metric}_delta"
        y_title = f"{metrics_labels[metric]} (Δ)"
    else:
        value_col = f"{metric}_pct_delta"
        y_title = f"{metrics_labels[metric]} (Relative Δ)"

    ref_name = scenarios[primary_id].get("name", primary_id)
    st.caption(f"Reference: {ref_name}")

    # Ensure consistent scenario labels in chart
    metrics = metrics.copy()
    metrics["scenario_label"] = metrics["scenario"].astype(str)

    # Optional percentile error bars (Absolute view; count/rate metrics only)
    _QMAP = {"50%": (0.25, 0.75), "90%": (0.05, 0.95), "95%": (0.025, 0.975)}
    _CI_METRICS = {"attack_rate", "total_infections", "peak_amplitude",
                   "hospitalizations", "hospitalization_rate"}
    ci_level = st.radio(
        "Uncertainty interval (error bars)",
        options=["None", "50%", "90%", "95%"],
        index=2,
        horizontal=True,
        help="Adds percentile error bars to each bar (Absolute view only). 50% = 25th–75th, "
             "90% = 5th–95th, 95% = 2.5th–97.5th, across the stochastic replicates. Not available "
             "for Peak Prevalence Day.",
    )
    show_err = (view == "Absolute" and ci_level != "None" and metric in _CI_METRICS)
    if show_err:
        qlo, qhi = _QMAP[ci_level]
        ci_bounds = _metric_ci_bounds(selected_ids, scenarios, results, metric, model, qlo, qhi)
        if ci_bounds is not None and not ci_bounds.empty:
            metrics = metrics.merge(ci_bounds, on=["scenario", "age_group"], how="left")
        else:
            show_err = False

    bar = (
        alt.Chart(metrics)
        .mark_bar()
        .encode(
            x=alt.X("age_group:N", title="Age group", sort=DEFAULT_AGE_GROUPS + ["total"]),
            y=alt.Y(f"{value_col}:Q", title=y_title),
            color=alt.Color("scenario:N", title="Scenario", scale=alt.Scale(scheme="set2")),
            xOffset="scenario:N",
            tooltip=[
                "scenario:N",
                "age_group:N",
                alt.Tooltip(f"{value_col}:Q", title=y_title),
            ],
        )
    )

    chart = bar
    if show_err and "ci_lo" in metrics.columns:
        err = (
            alt.Chart(metrics)
            .mark_rule(strokeWidth=1.6, color="#5f6b7a")
            .encode(
                x=alt.X("age_group:N", sort=DEFAULT_AGE_GROUPS + ["total"]),
                xOffset="scenario:N",
                y=alt.Y("ci_lo:Q"),
                y2="ci_hi:Q",
                tooltip=["scenario:N", "age_group:N",
                         alt.Tooltip("ci_lo:Q", title="Lower"), alt.Tooltip("ci_hi:Q", title="Upper")],
            )
        )
        chart = alt.layer(bar, err)
        st.caption(f"Error bars: {ci_level} interval across stochastic replicates.")

    st.altair_chart(chart, use_container_width=True)

    # Download button
    csv = metrics.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download metrics (CSV)",
        data=csv,
        file_name="scenario_metrics_with_deltas.csv",
        mime="text/csv",
    )


def _hosp_params_editor():
    """Editable hospitalization-model parameters (persisted in session_state)."""
    st.session_state.setdefault("hosp_params", dict(HOSP_DEFAULTS))
    p = st.session_state["hosp_params"]
    with st.expander("Hospitalization model parameters", expanded=False):
        st.caption(
            "Hospitalizations = incidence × per-case hospitalization ratio (IHR), by "
            "age and vaccination status. Naive (unvaccinated) IHR per output band; "
            "partial (vaccinated) cases use partial ratio × the naive IHR. Defaults "
            "reflect published pertussis patterns (CDC) — calibrate locally."
        )
        c = st.columns(3)
        p["ihr_infant"] = c[0].number_input("IHR <1 yr", 0.0, 1.0, float(p["ihr_infant"]), 0.01,
                                            help="Per-case hospitalization prob. for infants <1 yr (naive). CDC: ~1/3.")
        p["ihr_toddler"] = c[1].number_input("IHR 1-4", 0.0, 1.0, float(p["ihr_toddler"]), 0.01)
        p["ihr_5_19"] = c[2].number_input("IHR 5-19", 0.0, 1.0, float(p["ihr_5_19"]), 0.005, format="%.3f")
        c = st.columns(3)
        p["ihr_20_49"] = c[0].number_input("IHR 20-49", 0.0, 1.0, float(p["ihr_20_49"]), 0.005, format="%.3f")
        p["ihr_50_64"] = c[1].number_input("IHR 50-64", 0.0, 1.0, float(p["ihr_50_64"]), 0.005, format="%.3f")
        p["ihr_65p"] = c[2].number_input("IHR 65+", 0.0, 1.0, float(p["ihr_65p"]), 0.005, format="%.3f")
        c = st.columns(3)
        p["partial_ratio"] = c[0].number_input("Partial ratio", 0.0, 1.0, float(p["partial_ratio"]), 0.05,
                                               help="Vaccinated/partial IHR as a fraction of the naive IHR (milder disease).")
        p["infant_fraction"] = c[1].number_input("Infant share of 0-4", 0.0, 1.0, float(p["infant_fraction"]), 0.05,
                                                 help="Fraction of 0-4 incidence attributed to infants <1 (for the <1 vs 1-4 split).")
        p["delay_days"] = c[2].number_input("Onset→hosp delay (days)", 0, 60, int(p["delay_days"]), 1,
                                            help="Lag applied to the hospitalization curve. Pertussis ~1-2 weeks.")
    return p


def render_hospitalizations_tab(primary_id, selected_ids, scenarios, results):
    """Hospitalization observation model: incidence × age/status-specific IHR,
    with 0-4 resolved into <1 and 1-4. A lens on output; does not change dynamics."""
    model = scenarios[primary_id]["config"]["model"]
    st.caption(
        "Modeled hospitalizations derived from infection incidence (E→I, and Eₚ→Iₚ "
        "for pertussis) via age- and vaccination-status-specific hospitalization "
        "ratios. The 0–4 band is split into **<1** and **1–4** so the infant burden "
        "is visible. This is an observation layer — it does not alter transmission."
    )
    params = _hosp_params_editor()

    view = st.radio("View", ["Weekly", "Cumulative"], horizontal=True, key="_hosp_view")

    # Build a per-scenario, per-age hospitalization frame.
    frames = []
    for sid in selected_ids:
        daily = hospitalizations_from_trans(results[sid]["transitions"], params, model)
        daily["week"] = (daily["t"] - 1) // 7
        if view == "Weekly":
            agg = daily.groupby(["week", "age_group"], as_index=False)["hosp"].sum()
            agg = agg.rename(columns={"week": "x"})
        else:
            daily = daily.sort_values("t")
            daily["hosp"] = daily.groupby("age_group")["hosp"].cumsum()
            agg = daily.rename(columns={"t": "x"})[["x", "age_group", "hosp"]]
        agg["scenario"] = scenarios[sid].get("name", sid)
        frames.append(agg)
    plot_df = pd.concat(frames, ignore_index=True)

    x_title = "Week" if view == "Weekly" else "Day"
    y_title = "Hospitalizations (weekly)" if view == "Weekly" else "Cumulative hospitalizations"

    # For a single scenario colour by age band; for several, colour by scenario + facet age.
    if len(selected_ids) == 1:
        chart = (
            alt.Chart(plot_df)
            .mark_line()
            .encode(
                x=alt.X("x:Q", title=x_title),
                y=alt.Y("hosp:Q", title=y_title),
                color=alt.Color("age_group:N", title="Age band",
                                sort=HOSP_AGE_GROUPS, scale=alt.Scale(scheme="tableau10")),
                tooltip=["age_group:N", alt.Tooltip("x:Q", title=x_title),
                         alt.Tooltip("hosp:Q", title="Hospitalizations", format=".1f")],
            )
            .interactive()
        )
    else:
        chart = (
            alt.Chart(plot_df)
            .mark_line()
            .encode(
                x=alt.X("x:Q", title=x_title),
                y=alt.Y("hosp:Q", title=y_title),
                color=alt.Color("scenario:N", title="Scenario", scale=alt.Scale(scheme="set2")),
                facet=alt.Facet("age_group:N", columns=3, sort=HOSP_AGE_GROUPS, title=None),
                tooltip=["scenario:N", "age_group:N", alt.Tooltip("hosp:Q", format=".1f")],
            )
            .properties(width=200, height=140)
        )
    st.altair_chart(chart, use_container_width=True)

    # Totals table (primary scenario) + metric + download.
    summ = hospitalization_summary(results[primary_id]["transitions"], params, model)
    total = float(summ.loc[summ["age_group"] == "total", "hosp"].iloc[0])
    infants = float(summ.loc[summ["age_group"] == "<1", "hosp"].iloc[0])
    m1, m2 = st.columns(2)
    m1.metric("Total modeled hospitalizations", f"{total:,.0f}")
    m2.metric("Infant (<1) share", f"{(infants / total):.0%}" if total > 0 else "—",
              help="Share of modeled hospitalizations in infants <1 yr.")

    show = summ.copy()
    show["hosp"] = show["hosp"].round(1)
    show = show.rename(columns={"age_group": "Age band", "hosp": "Hospitalizations"})
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.download_button(
        "Download hospitalizations (CSV)",
        data=plot_df.to_csv(index=False).encode("utf-8"),
        file_name=f"hospitalizations_{view.lower()}_{model}.csv",
        mime="text/csv",
    )
    st.caption(
        "Note: infant hospitalization dominates but the 0–4 transmission band is coarse; "
        "the <1 vs 1–4 split here uses the 'Infant share of 0-4' parameter, not a separate "
        "infant contact structure. Treat the <1 series as an IHR-scaled view of 0–4 incidence."
    )


def render_observed_comparison(primary_id, scenarios, results):
    """Compare the primary run against the selected observed case dataset."""
    from data.observed_datasets import OBSERVED_DATASETS
    from engine.calibration import observed_targets, modeled_case_summary, fit_error

    cfg = scenarios[primary_id]["config"]
    ds_name = cfg.get("observed_dataset")
    if not ds_name or ds_name not in OBSERVED_DATASETS:
        st.info("No observed dataset selected for the primary scenario.")
        return

    raw = OBSERVED_DATASETS[ds_name]["raw"]
    obs = observed_targets(raw)
    mod = modeled_case_summary(results[primary_id]["transitions"])
    err = fit_error(obs, mod)

    st.caption(
        f"Primary scenario **{scenarios[primary_id].get('name', primary_id)}** vs observed "
        f"**{ds_name}**. Model incidence is cumulative new infections "
        "(E→I naive, Eₚ→Iₚ partial); observed is cumulative cases."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Observed vaccinated share", f"{obs['overall_partial_share']:.0%}")
    c2.metric("Modeled vaccinated share", f"{mod['overall_partial_share']:.0%}")
    c3.metric("Age-dist RMSE (fit)", f"{err['age_dist_rmse']:.3f}")

    # --- Age distribution: observed vs modeled (normalised shares) ---
    rows = []
    for i, ag in enumerate(DEFAULT_AGE_GROUPS):
        rows.append({"age_group": ag, "source": "Observed", "share": float(obs["age_dist"][i])})
        rows.append({"age_group": ag, "source": "Modeled", "share": float(mod["age_dist"][i])})
    dist_df = pd.DataFrame(rows)

    st.markdown("**Case age distribution (share of total)**")
    chart = (
        alt.Chart(dist_df)
        .mark_bar()
        .encode(
            x=alt.X("age_group:N", title="Age group", sort=DEFAULT_AGE_GROUPS),
            y=alt.Y("share:Q", title="Share of cases", axis=alt.Axis(format="%")),
            color=alt.Color("source:N", title="", scale=alt.Scale(scheme="set2")),
            xOffset="source:N",
            tooltip=["age_group:N", "source:N", alt.Tooltip("share:Q", format=".1%")],
        )
    )
    st.altair_chart(chart, use_container_width=True)

    # --- Vaccinated (partial) share by band ---
    srows = []
    for i, ag in enumerate(DEFAULT_AGE_GROUPS):
        o = obs["partial_share_by_band"][i]
        m = mod["partial_share_by_band"][i]
        if np.isfinite(o):
            srows.append({"age_group": ag, "source": "Observed", "share": float(o)})
        if np.isfinite(m):
            srows.append({"age_group": ag, "source": "Modeled", "share": float(m)})
    if srows:
        share_df = pd.DataFrame(srows)
        st.markdown("**Vaccinated (partial-track) share of cases, by age band**")
        chart2 = (
            alt.Chart(share_df)
            .mark_bar()
            .encode(
                x=alt.X("age_group:N", title="Age group", sort=DEFAULT_AGE_GROUPS),
                y=alt.Y("share:Q", title="Vaccinated share", axis=alt.Axis(format="%")),
                color=alt.Color("source:N", title="", scale=alt.Scale(scheme="set2")),
                xOffset="source:N",
                tooltip=["age_group:N", "source:N", alt.Tooltip("share:Q", format=".1%")],
            )
        )
        st.altair_chart(chart2, use_container_width=True)

    # --- Raw comparison table + download ---
    table = pd.DataFrame({
        "age_group": DEFAULT_AGE_GROUPS,
        "observed_cases": obs["age_counts"].astype(int),
        "observed_naive(No)": obs["naive_by_band"].astype(int),
        "observed_partial(Yes)": obs["partial_by_band"].astype(int),
        "modeled_new_infections": np.round(mod["age_counts"]).astype(int),
        "modeled_naive": np.round(mod["naive_by_band"]).astype(int),
        "modeled_partial": np.round(mod["partial_by_band"]).astype(int),
    })
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.download_button(
        "Download observed-vs-modeled (CSV)",
        data=table.to_csv(index=False).encode("utf-8"),
        file_name=f"observed_vs_modeled_{ds_name}.csv",
        mime="text/csv",
    )
    st.caption(
        "Note: the modeled age distribution is driven by the geography's contact matrix and "
        "will not necessarily match reporting-skewed surveillance data (e.g. adolescent-heavy "
        "pertussis case counts). The vaccinated-share comparison is the more meaningful "
        "structural check for this model."
    )


def render_demographic_and_contacts_tab(
    population, 
    contact_matrices, 
    country_name, 
    sep_width=0.02
    ):
    """Render the population visualization tab."""

    view = st.radio(
            "Display",
            options=["Population", "Contact Matrix", "Contacts by setting"],
            horizontal=True,
        )

    if view == "Population":

        # Population Data Download
        population_data = pd.DataFrame({
            "Age Group": population.Nk_names,
            "Count": population.Nk,
            "Percentage": 100 * population.Nk / population.Nk.sum()
        })
        st.download_button(
            label="Download Population Data (CSV)",
            data=population_data.to_csv(index=False),
            file_name=f"{country_name}_population.csv",
            mime="text/csv",
            use_container_width=False,
            help="Download population by age group (counts and percentages)"
        )

        # Population Metrics
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Total Population", f"{population.Nk.sum():,}")
        with col2: st.metric("Most Populous Age Group", f"{population.Nk_names[population.Nk.argmax()]}")
        with col3: st.metric("Least Populous Age Group", f"{population.Nk_names[population.Nk.argmin()]}")

        # Population Donut Plot
        plot_population(
            population=population,
            facecolor="#0c1019",
        )

    # Contact Matrix Panel
    if view == "Contact Matrix":    
        layer = st.selectbox("Contact layer", 
                            options=["overall", "home", "school", "work", "community"], 
                            index=0, 
                            help="Choose which contact layer to visualize")

        # Contact Matrix Data Download
        contact_df = contact_matrix_df(layer, population.contact_matrices, population.Nk_names)
        st.download_button(
                label="Download Contact Matrix (CSV)",
                data=contact_df.round(3).to_csv(index=True),
                file_name=f"{country_name}_contacts_{layer}.csv",
                mime="text/csv",
                use_container_width=False,
                help="Download contact matrix data with age groups and contact rates"
            )

        # Contact Matrix Metrics
        if layer == "overall":
            matrix = sum(population.contact_matrices.values())
        else:
            matrix = population.contact_matrices[layer]
        matrix = np.array(matrix)

        col1, col2, col3, col4 = st.columns(4)    
        with col1: st.metric("Most Active Age Group", f"{population.Nk_names[matrix.sum(axis=1).argmax()]}")
        with col2: st.metric("Least Active Age Group", f"{population.Nk_names[matrix.sum(axis=1).argmin()]}")
        with col3: st.metric("Mean Contact Rate", f"{matrix.sum(axis=1).mean():.2f}")
        with col4: st.metric("Spectral Radius", f"{np.linalg.eigvals(matrix).max().real:.2f}")
        
        # Contact Matrix Plot
        plot_contact_matrix(
            layer=layer,
            matrices=contact_matrices,
            groups=population.Nk_names,
            facecolor="#0c1019",
            cmap=("#9fb6d4", "#e9e4dd", "#e8933f"),  # light blue -> neutral -> orange
        )

    # Contacts-by-setting summary (age-mixing story across home/school/work/community)
    if view == "Contacts by setting":
        st.caption(
            "Average daily contacts **made by** a person in each age band, split by "
            "setting (row sums of each layer's contact matrix). This is the age-mixing "
            "structure that drives transmission — e.g. school-age bands dominate the "
            "school setting while the youngest and oldest make no workplace contacts."
        )

        settings = ["home", "school", "work", "community"]
        groups = list(population.Nk_names)
        rows = []
        for layer_name in settings:
            if layer_name not in population.contact_matrices:
                continue
            made = np.asarray(population.contact_matrices[layer_name]).sum(axis=1)
            for i, ag in enumerate(groups):
                rows.append({"age_group": ag, "setting": layer_name, "contacts": float(made[i])})
        mix_df = pd.DataFrame(rows)

        chart = (
            alt.Chart(mix_df)
            .mark_bar()
            .encode(
                x=alt.X("age_group:N", title="Age group", sort=groups),
                y=alt.Y("contacts:Q", title="Contacts made per person / day"),
                color=alt.Color(
                    "setting:N", title="Setting",
                    scale=alt.Scale(domain=settings, scheme="set2"),
                    sort=settings,
                ),
                order=alt.Order("setting:N", sort="ascending"),
                tooltip=["age_group:N", "setting:N", alt.Tooltip("contacts:Q", format=".2f")],
            )
        )
        st.altair_chart(chart, use_container_width=True)

        # Table (age band x setting, with total) + download
        pivot = (
            mix_df.pivot(index="age_group", columns="setting", values="contacts")
            .reindex(index=groups, columns=settings)
        )
        pivot["total"] = pivot.sum(axis=1)
        st.dataframe(pivot.round(2), use_container_width=True)
        st.download_button(
            "Download contacts-by-setting (CSV)",
            data=pivot.round(3).to_csv(index=True).encode("utf-8"),
            file_name=f"{country_name}_contacts_by_setting.csv",
            mime="text/csv",
        )
        st.caption(
            "Note: bands are coarse (e.g. 5-19 averages kindergarten through college), "
            "and the community layer in this dataset depends only on the age contacted, "
            "not the contactor — so its bars are flat across age bands."
        )


def render_viz_panel(model: str, geography: str) -> None:
    st.subheader("Visualisation")

    run_ids, scenarios, results = _get_run_scenarios()
    if not run_ids:
        st.info("No run results yet. Click Run to generate output.")
        return

    # ---- SCENARIO SELECTION (shared across all tabs) ----
    st.markdown("**Scenario Selection**")
    
    last_run = st.session_state.get("last_run_scenario_id")
    default_primary = last_run if last_run in run_ids else run_ids[0]

    col1, col2 = st.columns([0.5, 0.5])
    
    with col1:
        primary_id = st.selectbox(
            "Primary scenario",
            options=run_ids,
            index=run_ids.index(default_primary),
            format_func=lambda sid: scenarios[sid].get("name", sid),
            key="viz_primary_scenario"
        )

    compare_pool = [sid for sid in run_ids if sid != primary_id]
    
    with col2:
        compare_ids = st.multiselect(
            "Compare with",
            options=compare_pool,
            default=[],
            format_func=lambda sid: scenarios[sid].get("name", sid),
            key="viz_compare_scenarios"
        )
    
    selected_ids = [primary_id] + compare_ids

    has_observed = bool(scenarios[primary_id]["config"].get("observed_dataset"))
    tab_labels = ["Trajectories", "Summary metrics", "Hospitalizations",
                  "Contact Interventions", "Vaccinations", "Population"]
    if has_observed:
        tab_labels.append("Observed vs modeled")
    _tabs = st.tabs(tab_labels)
    (tab_ts, tab_metrics, tab_hosp, tab_contact_interventions,
     tab_vaccinations, tab_population) = _tabs[:6]

    with tab_hosp:
        render_hospitalizations_tab(primary_id, selected_ids, scenarios, results)

    with tab_ts:
        render_compartment_timeseries(MODEL_COMPS[model], selected_ids, scenarios, results)
        # Download button of all timeseries
        complete_df = pd.DataFrame()
        for sid in selected_ids:
            df = results[sid]["compartments"]
            df["scenario"] = scenarios[sid].get("name", sid)
            complete_df = pd.concat([complete_df, df], ignore_index=True)

        # Download button
        country_name = scenarios[selected_ids[0]]["config"]["geography"]
        csv = complete_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download timeseries (CSV)",
            data=csv,
            file_name=f"{country_name}_{model}_all_timeseries.csv",
            mime="text/csv",
        )

    with tab_metrics:
        render_metrics_tab(primary_id, selected_ids, scenarios, results)

    with tab_contact_interventions:
        dfs_dict = {scenarios[sid].get("name", sid): scenarios[sid]["config"]["spectral_radius_df"] for sid in selected_ids}
        dfs_dict = OrderedDict(sorted(dfs_dict.items(), key=lambda item: item[0]))
        render_spectral_radius_timeseries(dfs_dict)

    with tab_vaccinations:
        dfs_dict = {scenarios[sid].get("name", sid): scenarios[sid]["config"]["daily_doses_by_age_daily"] for sid in selected_ids}
        dfs_dict = OrderedDict(sorted(dfs_dict.items(), key=lambda item: item[0]))
        render_vaccination_timeseries(dfs_dict)

        complete_vax_df = pd.DataFrame()
        for sid in selected_ids:
            df = scenarios[sid]["config"]["daily_doses_by_age_daily"]
            df["scenario"] = scenarios[sid].get("name", sid)
            complete_vax_df = pd.concat([complete_vax_df, df], ignore_index=True)

        country_name = scenarios[selected_ids[0]]["config"]["geography"]
        csv = complete_vax_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download vaccination timeseries (CSV)",
            data=csv,
            file_name=f"{country_name}_{model}_all_vaccinations.csv",
            mime="text/csv",
            use_container_width=False,
            help="Download vaccination timeseries data with age groups and daily doses"
        )

    with tab_population:
        render_demographic_and_contacts_tab(
            population=scenarios[primary_id]["config"]["population"],
            contact_matrices=scenarios[primary_id]["config"]["population"].contact_matrices,
            country_name=scenarios[primary_id]["config"]["geography"],
        )

    if has_observed:
        with _tabs[6]:
            render_observed_comparison(primary_id, scenarios, results)