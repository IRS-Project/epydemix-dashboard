# engine/calibration.py
#
# Compare the pertussis partial-immunity model against an observed case dataset
# (cases by age band and vaccination status) and support three workflows:
#   1. Overlay / compare  -> observed_targets() + modeled_case_summary() + fit_error()
#   2. Seed & project      -> seed_ic_from_observed()
#   3. Auto-calibrate      -> calibrate_to_observed()
#
# Track proxy: "No" (not up to date) -> naive track (I / E_to_I),
#              "Yes" (up to date)    -> partial track (Ip / Ep_to_Ip).

from __future__ import annotations
import numpy as np
import pandas as pd

from constants import DEFAULT_AGE_GROUPS
from data.observed_datasets import aggregate_to_bands


# ----------------------------------------------------------------------------
# Observed targets
# ----------------------------------------------------------------------------
def observed_targets(raw: dict) -> dict:
    """Summarise an observed dataset into comparison targets."""
    bands = aggregate_to_bands(raw)
    counts = np.array([bands[a]["total"] for a in DEFAULT_AGE_GROUPS], dtype=float)
    naive = np.array([bands[a]["naive"] for a in DEFAULT_AGE_GROUPS], dtype=float)
    partial = np.array([bands[a]["partial"] for a in DEFAULT_AGE_GROUPS], dtype=float)

    total = counts.sum()
    known = naive + partial
    with np.errstate(invalid="ignore", divide="ignore"):
        share_by_band = np.where(known > 0, partial / known, np.nan)

    known_total = float((naive + partial).sum())
    return {
        "age_counts": counts,
        "age_dist": counts / total if total > 0 else counts,
        "naive_by_band": naive,
        "partial_by_band": partial,
        "partial_share_by_band": share_by_band,
        "overall_partial_share": (float(partial.sum()) / known_total) if known_total > 0 else np.nan,
        "total_cases": total,
    }


# ----------------------------------------------------------------------------
# Modeled case summary (from a completed run)
# ----------------------------------------------------------------------------
def modeled_case_summary(df_trans) -> dict:
    """
    Cumulative new infections per age band and track from a run's transitions.
    Naive new cases   = sum_t E_to_I_<band>
    Partial new cases = sum_t Ep_to_Ip_<band>
    """
    def col_sum(col):
        return float(df_trans[col].sum()) if col in df_trans.columns else 0.0

    naive = np.array([col_sum(f"E_to_I_{a}") for a in DEFAULT_AGE_GROUPS], dtype=float)
    partial = np.array([col_sum(f"Ep_to_Ip_{a}") for a in DEFAULT_AGE_GROUPS], dtype=float)
    total = naive + partial
    tsum = total.sum()

    with np.errstate(invalid="ignore", divide="ignore"):
        share_by_band = np.where(total > 0, partial / total, np.nan)

    return {
        "age_counts": total,
        "age_dist": total / tsum if tsum > 0 else total,
        "naive_by_band": naive,
        "partial_by_band": partial,
        "partial_share_by_band": share_by_band,
        "overall_partial_share": (float(partial.sum()) / tsum) if tsum > 0 else np.nan,
        "total_cases": float(tsum),
    }


# ----------------------------------------------------------------------------
# Fit error between observed and modeled
# ----------------------------------------------------------------------------
def fit_error(obs: dict, mod: dict) -> dict:
    """
    Scalar fit diagnostics comparing shape (age distribution) and the
    vaccinated (partial) share of cases. Both are scale-free so they compare
    a case count (observed) against a modeled incidence (different magnitude).
    """
    age_rmse = float(np.sqrt(np.nanmean((obs["age_dist"] - mod["age_dist"]) ** 2)))

    o_s = obs["overall_partial_share"]
    m_s = mod["overall_partial_share"]
    share_err = float(abs(o_s - m_s)) if np.isfinite(o_s) and np.isfinite(m_s) else np.nan

    # combined score: age-distribution shape + vaccinated-share match
    score = age_rmse + (share_err if np.isfinite(share_err) else 1.0)
    return {"age_dist_rmse": age_rmse, "partial_share_err": share_err, "score": score}


# ----------------------------------------------------------------------------
# Seed initial conditions directly from observed counts
# ----------------------------------------------------------------------------
def seed_ic_from_observed(Nk, raw: dict, immune_pct: float,
                          partial_immune_pct: float = 71.0,
                          immune_pct_by_age=None) -> dict:
    """
    Build an 8-compartment initial-conditions dict where the seeded infections
    reproduce the observed age x vaccination distribution:
      No  -> naive track  (split E/I)
      Yes -> partial track (split Ep/Ip)
      Unknown -> allocated within band by the known naive:partial ratio.
    Background immunity fills Sp/Rp/R from the immune_pct slider.
    """
    Nk = np.asarray(Nk, dtype=float)
    bands = aggregate_to_bands(raw)
    ic = {c: np.zeros(len(Nk)) for c in ["S", "E", "I", "R", "Sp", "Ep", "Ip", "Rp"]}

    for i, a in enumerate(DEFAULT_AGE_GROUPS):
        naive = float(bands[a]["naive"])
        partial = float(bands[a]["partial"])
        unk = float(bands[a]["Unknown"])
        known = naive + partial
        if known > 0:
            naive += unk * naive / known
            partial += unk * partial / known
        else:
            naive += unk  # no known status -> assume naive

        ic["E"][i] = naive / 2.0
        ic["I"][i] = naive / 2.0
        ic["Ep"][i] = partial / 2.0
        ic["Ip"][i] = partial / 2.0

    # background immunity pool -> Sp / Rp / R. A per-age immunity vector (e.g. real
    # vaccination coverage by band) overrides the uniform immune_pct when supplied.
    if immune_pct_by_age is not None:
        immune = Nk * (np.asarray(immune_pct_by_age, dtype=float) / 100.0)
    else:
        immune = Nk * (immune_pct / 100.0)
    sp = partial_immune_pct / 100.0
    rem = max(0.0, 1.0 - sp)
    ic["Sp"] = immune * sp
    ic["Rp"] = immune * rem * (0.24 / 0.29)
    ic["R"] = immune * rem * (0.05 / 0.29)

    # Floor every non-S compartment to integers, then let S absorb the remainder
    # so the compartments sum exactly to Nk (per age group).
    for c in ["E", "I", "Ep", "Ip", "Sp", "Rp", "R"]:
        ic[c] = np.maximum(0, ic[c]).astype(int)
    seeded = ic["E"] + ic["I"] + ic["Ep"] + ic["Ip"] + ic["Sp"] + ic["Rp"] + ic["R"]
    ic["S"] = np.maximum(0, Nk - seeded)

    return ic


# ----------------------------------------------------------------------------
# Coarse auto-calibration
# ----------------------------------------------------------------------------
def calibrate_to_observed(base_scenario: dict, raw: dict, run_fn,
                          r0_grid=None, partial_immune_grid=None,
                          sigma_grid=None) -> dict:
    """
    Coarse grid search over the most identifiable knobs for this data
    (R0, initial Sp share of the immune pool, and sigma) minimising fit_error.

    `run_fn(scenario) -> (df_comp, df_trans)` runs one model evaluation.
    `base_scenario` is a full scenario config; this function copies it and
    overrides model_params / initial_conditions per grid point.

    Returns best params, best error, and the full evaluation trace.
    """
    import copy

    obs = observed_targets(raw)
    r0_grid = r0_grid if r0_grid is not None else [8.0, 12.0, 16.0]
    partial_immune_grid = partial_immune_grid if partial_immune_grid is not None else [50.0, 71.0, 90.0]
    sigma_grid = sigma_grid if sigma_grid is not None else [0.1, 0.2, 0.3]

    trace = []
    best = None
    for r0 in r0_grid:
        for pi in partial_immune_grid:
            for sig in sigma_grid:
                sc = copy.deepcopy(base_scenario)
                sc["model_params"]["R0"] = float(r0)
                sc["model_params"]["rel_infectiousness_partial"] = float(sig)
                sc["initial_conditions"]["partial_immune_pct"] = float(pi)
                df_comp, df_trans, *_ = run_fn(sc)
                mod = modeled_case_summary(df_trans)
                err = fit_error(obs, mod)
                point = {"R0": r0, "partial_immune_pct": pi,
                         "rel_infectiousness_partial": sig, **err,
                         "modeled_partial_share": mod["overall_partial_share"]}
                trace.append(point)
                if best is None or err["score"] < best["score"]:
                    best = point

    return {"best": best, "trace": trace, "observed": {
        "overall_partial_share": obs["overall_partial_share"],
        "age_dist": obs["age_dist"].tolist(),
    }}


# ----------------------------------------------------------------------------
# Weekly incidence curve (shape) target
# ----------------------------------------------------------------------------
def weekly_incidence_from_trans(df_trans, model: str) -> np.ndarray:
    """Modeled weekly new-infection incidence (all ages) from a run's daily
    transitions. Naive E→I plus, for pertussis, partial Eₚ→Iₚ. Days are binned
    in 7s (t is a daily index)."""
    n = len(df_trans)
    daily = np.zeros(n, dtype=float)
    for a in DEFAULT_AGE_GROUPS:
        c = f"E_to_I_{a}"
        if c in df_trans.columns:
            daily += df_trans[c].to_numpy(dtype=float)
        if model == "SEIRS (Pertussis)":
            cp = f"Ep_to_Ip_{a}"
            if cp in df_trans.columns:
                daily += df_trans[cp].to_numpy(dtype=float)
    n_weeks = int(np.ceil(n / 7.0)) if n else 0
    return np.array([daily[i * 7:(i + 1) * 7].sum() for i in range(n_weeks)], dtype=float)


def _normalize_peak(a) -> np.ndarray:
    a = np.clip(np.asarray(a, dtype=float), 0.0, None)
    m = a.max() if a.size else 0.0
    return a / m if m > 0 else a


def curve_shape_distance(obs_weekly, df_trans, model: str, mode: str = "weekly") -> float:
    """Scale-free distance between an observed weekly case series and the modeled
    incidence *shape*, over their overlapping window. This is what a time series
    adds over a cross-tab: it constrains growth rate, peak timing and seasonality
    (hence R₀), which shares/age-distributions cannot.

    mode="weekly": peak-normalise the weekly curves; score = RMSE + peak-week
        timing penalty (rewards matching the epidemic peak).
    mode="cumulative": cumulate then normalise each curve to its final total
        (a 0→1 S-curve); score = RMSE of the normalised cumulatives (rewards
        matching *when* incidence accrues; smoother/less noise-sensitive, no peak
        penalty since a cumulative's maximum is always its last point)."""
    obs = np.clip(np.asarray(obs_weekly, dtype=float), 0.0, None)
    mod = weekly_incidence_from_trans(df_trans, model)
    if obs.size == 0 or mod.size == 0 or obs.max() <= 0 or mod.max() <= 0:
        return 1.0
    L = min(len(obs), len(mod))
    o, m = obs[:L], mod[:L]

    if mode == "cumulative":
        oc, mc = np.cumsum(o), np.cumsum(m)
        on = oc / oc[-1] if oc[-1] > 0 else oc
        mn = mc / mc[-1] if mc[-1] > 0 else mc
        return float(np.sqrt(np.mean((on - mn) ** 2)))

    o, m = _normalize_peak(o), _normalize_peak(m)
    rmse = float(np.sqrt(np.mean((o - m) ** 2)))
    peak_pen = abs(int(np.argmax(o)) - int(np.argmax(m))) / max(1, L - 1)
    return rmse + 0.5 * peak_pen


# ----------------------------------------------------------------------------
# Bayesian calibration — Approximate Bayesian Computation, Sequential Monte Carlo
# ----------------------------------------------------------------------------
# Parameters calibrated (name, target dict, prior low, prior high):
#   R0, sigma (rel_infectiousness_partial), delta (rel_susceptibility_partial)
#   live in model_params; partial_immune_pct is an initial condition.
ABC_PARAMS = [
    ("R0", "model", 6.0, 18.0),
    ("rel_infectiousness_partial", "model", 0.05, 0.40),
    ("rel_susceptibility_partial", "model", 0.10, 0.60),
    ("partial_immune_pct", "ic", 40.0, 90.0),
]
ABC_PARAM_LABELS = {
    "R0": "R₀",
    "rel_infectiousness_partial": "σ (partial infectiousness)",
    "rel_susceptibility_partial": "δ (partial susceptibility)",
    "partial_immune_pct": "Sₚ share of immune pool (%)",
}


def _apply_abc_params(base_scenario, x):
    """Shallow-copy the scenario (avoids deep-copying the population) and overlay
    the calibrated parameter vector. Calibration always runs the parametric
    initial conditions (no observed-seeding / age-immunity override)."""
    sc = dict(base_scenario)
    mp = dict(base_scenario.get("model_params", {}))
    ic = dict(base_scenario.get("initial_conditions", {}))
    for val, (name, kind, _lo, _hi) in zip(x, ABC_PARAMS):
        if kind == "model":
            mp[name] = float(val)
        else:
            ic[name] = float(val)
    sc["model_params"] = mp
    sc["initial_conditions"] = ic
    sc["observed_mode"] = "Off"          # use the parametric IC, not observed-seeding
    sc["use_age_immunity"] = False
    return sc


def _weighted_quantile(values, weights, q):
    order = np.argsort(values)
    v = np.asarray(values)[order]
    w = np.asarray(weights)[order]
    cw = np.cumsum(w) - 0.5 * w
    cw /= np.sum(w)
    return float(np.interp(q, cw, v))


def abc_smc_calibrate(base_scenario, raw, run_fn, *, n_particles=40, n_rounds=3,
                      quantile=0.5, max_attempts_factor=4, rng_seed=0, progress=None):
    """Approximate Bayesian Computation with Sequential Monte Carlo (Toni et al. 2009).

    Refines a population of weighted parameter 'particles' over `n_rounds` with an
    adaptive tolerance (the `quantile` of the previous round's distances) and a
    Gaussian perturbation kernel truncated to the uniform priors. `run_fn(scenario)`
    runs one model evaluation and returns (compartments, transitions, ci...).

    Returns a dict with per-parameter posterior summary (median + 95% credible
    interval), the raw particles/weights, and the observed target shares.
    """
    obs = observed_targets(raw)
    lo = np.array([p[2] for p in ABC_PARAMS], dtype=float)
    hi = np.array([p[3] for p in ABC_PARAMS], dtype=float)
    D = len(ABC_PARAMS)
    rng = np.random.default_rng(rng_seed)

    # Optional weekly-incidence shape target (adds growth-rate / peak-timing /
    # seasonality information the cross-tab lacks).
    weekly = base_scenario.get("weekly_target") or None
    weekly_weight = float(base_scenario.get("weekly_weight", 1.0))
    weekly_mode = base_scenario.get("weekly_mode", "weekly")
    model_name = base_scenario.get("model")

    def report(frac, msg):
        if progress is not None:
            try:
                progress(max(0.0, min(1.0, frac)), msg)
            except Exception:
                pass

    def distance(x):
        try:
            _comp, trans, *_ = run_fn(_apply_abc_params(base_scenario, x))
            d = fit_error(obs, modeled_case_summary(trans))["score"]
            if weekly:
                d += weekly_weight * curve_shape_distance(weekly, trans, model_name, mode=weekly_mode)
            return float(d) if np.isfinite(d) else 1e6
        except Exception:
            return 1e6

    # ---- Round 1: sample the prior, keep the best n_particles ----
    n_init = int(np.ceil(1.5 * n_particles))
    cand = rng.uniform(lo, hi, size=(n_init, D))
    dists = np.empty(n_init)
    for i, x in enumerate(cand):
        dists[i] = distance(x)
        report((i + 1) / n_init / n_rounds, f"Round 1/{n_rounds}: prior sampling ({i + 1}/{n_init})")
    keep = np.argsort(dists)[:n_particles]
    particles = cand[keep]
    pdist = dists[keep]
    weights = np.ones(n_particles) / n_particles
    eps = float(np.quantile(pdist, quantile))
    rounds_completed = 1

    # ---- Rounds 2..T: perturb + accept under a shrinking tolerance ----
    for t in range(2, n_rounds + 1):
        mean = np.average(particles, axis=0, weights=weights)
        var = np.average((particles - mean) ** 2, axis=0, weights=weights)
        kstd = np.maximum(np.sqrt(2.0 * var), 1e-6 * (hi - lo))  # Gaussian kernel std

        new_p, new_d = [], []
        max_attempts = max_attempts_factor * n_particles
        attempts = 0
        base_frac = (t - 1) / n_rounds
        while len(new_p) < n_particles and attempts < max_attempts:
            i = rng.choice(len(particles), p=weights)
            x = particles[i] + rng.normal(0.0, kstd)
            attempts += 1
            if np.any(x < lo) or np.any(x > hi):
                continue
            d = distance(x)
            if attempts % 5 == 0:
                report(base_frac + (attempts / max_attempts) / n_rounds,
                       f"Round {t}/{n_rounds}: accepted {len(new_p)}/{n_particles}")
            if d <= eps:
                new_p.append(x)
                new_d.append(d)

        if len(new_p) < max(5, n_particles // 4):
            break  # too few accepted at this tolerance; stop and keep the current population

        new_p = np.array(new_p)
        new_d = np.array(new_d)
        # Importance weights: uniform prior -> w_j ∝ 1 / Σ_k w_k K(x_j | x_k)
        w = np.zeros(len(new_p))
        norm = np.prod(kstd) * (2.0 * np.pi) ** (D / 2.0)
        for j, xj in enumerate(new_p):
            diff = (xj - particles) / kstd
            k = np.exp(-0.5 * np.sum(diff ** 2, axis=1)) / norm
            denom = np.sum(weights * k)
            w[j] = (1.0 / denom) if denom > 0 else 0.0
        if w.sum() <= 0:
            break
        w /= w.sum()
        particles, weights, pdist = new_p, w, new_d
        eps = float(np.quantile(pdist, quantile))
        rounds_completed = t

    report(1.0, "Done")

    summary = {}
    for idx, (name, _kind, _l, _h) in enumerate(ABC_PARAMS):
        vals = particles[:, idx]
        summary[name] = {
            "median": _weighted_quantile(vals, weights, 0.5),
            "lo": _weighted_quantile(vals, weights, 0.025),
            "hi": _weighted_quantile(vals, weights, 0.975),
            "label": ABC_PARAM_LABELS[name],
        }

    return {
        "summary": summary,
        "params": [p[0] for p in ABC_PARAMS],
        "particles": particles.tolist(),
        "weights": weights.tolist(),
        "final_eps": eps,
        "n_particles": int(len(particles)),
        "rounds_completed": rounds_completed,
        "observed": {"overall_partial_share": obs["overall_partial_share"]},
    }


# ----------------------------------------------------------------------------
# Posterior-predictive projection
# ----------------------------------------------------------------------------
def posterior_predictive(base_scenario, abc_result, run_fn, *, n_draws=30,
                         rng_seed=0, quants=None, progress=None):
    """Propagate ABC-SMC *parameter* uncertainty into the trajectory.

    Resamples `n_draws` parameter vectors from the weighted posterior particles
    (with replacement), runs the model for each, and returns per-day quantile
    bands of the compartment trajectories *across parameter draws*. This is the
    posterior-predictive band — it reflects uncertainty in the calibrated
    parameters, unlike the stochastic band which fixes the parameters and varies
    only the random seed. Each draw contributes its own median stochastic
    trajectory, so `run_fn` should be called with a small N_SIM for speed.

    `run_fn(scenario) -> (df_comp, df_trans, ci...)`.

    Returns {"compartments_pp": df[t, quantile, <series...>], "n_draws", "params"}
    or None if no draw produced a usable trajectory. The returned frame has the
    same shape as the stored `compartments_ci`, so the trajectory viz can reuse
    its band-drawing logic.
    """
    from engine.run import CI_QUANTILES
    quants = list(quants) if quants is not None else list(CI_QUANTILES)

    particles = np.asarray(abc_result["particles"], dtype=float)
    weights = np.asarray(abc_result["weights"], dtype=float)
    wsum = weights.sum()
    weights = weights / wsum if wsum > 0 else np.ones(len(particles)) / len(particles)
    rng = np.random.default_rng(rng_seed)

    idx = rng.choice(len(particles), size=int(n_draws), p=weights)
    draws = particles[idx]

    def report(frac, msg):
        if progress is not None:
            try:
                progress(max(0.0, min(1.0, frac)), msg)
            except Exception:
                pass

    frames = []
    for i, x in enumerate(draws):
        try:
            df_comp, _df_trans, *_ = run_fn(_apply_abc_params(base_scenario, x))
            frames.append(df_comp.reset_index(drop=True))
            report((i + 1) / len(draws), f"Posterior draw {i + 1}/{len(draws)}")
        except Exception:
            report((i + 1) / len(draws), f"Posterior draw {i + 1}/{len(draws)} (skipped)")

    if not frames:
        return None

    series_cols = [c for c in frames[0].columns if c != "t"]
    L = min(len(f) for f in frames)
    t = frames[0]["t"].to_numpy()[:L]
    stacks = {c: np.vstack([f[c].to_numpy()[:L] for f in frames]) for c in series_cols}

    out_rows = []
    for q in quants:
        row = {"t": t, "quantile": np.full(L, float(q))}
        for c in series_cols:
            row[c] = np.quantile(stacks[c], q, axis=0)
        out_rows.append(pd.DataFrame(row))
    pp_df = pd.concat(out_rows, ignore_index=True)

    report(1.0, "Done")
    return {
        "compartments_pp": pp_df,
        "n_draws": len(frames),
        "params": abc_result.get("params", [p[0] for p in ABC_PARAMS]),
    }
