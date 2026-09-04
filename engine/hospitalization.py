# engine/hospitalization.py
#
# Hospitalization observation model: relate hospitalizations to infections as a
# post-processing lens on a completed run, WITHOUT changing the transmission
# dynamics. Hospitalizations are incidence x an age- and vaccination-status-
# specific hospitalization ratio (IHR):
#
#     Hosp_a(t) = h_naive,a * (E->I)_a(t) + h_partial,a * (Ep->Ip)_a(t)
#
# with h_partial = partial_ratio * h_naive (vaccinated/partial cases are milder).
#
# Pertussis hospitalization is concentrated in infants (<1 yr), but the model's
# youngest band is 0-4. Rather than restructure the model's age bands (which are
# tied to the epydemix-data 5x5 contact matrices), the *output* splits 0-4 into
# <1 and 1-4 using an infant fraction of the 0-4 incidence, so the infant signal
# is not washed out. An onset-to-hospitalization delay shifts the curve.
#
# Default IHRs reflect published pertussis patterns (CDC Pink Book / provisional
# surveillance): ~1/3 of infants <1 yr hospitalized, dropping steeply with age;
# they are user-editable and should be calibrated locally.

from __future__ import annotations
import numpy as np
import pandas as pd

from constants import DEFAULT_AGE_GROUPS  # ["0-4","5-19","20-49","50-64","65+"]

# Output age bands (0-4 resolved into <1 and 1-4 for the hospitalization view).
HOSP_AGE_GROUPS = ["<1", "1-4", "5-19", "20-49", "50-64", "65+"]

HOSP_DEFAULTS = {
    # Per-case hospitalization probability (naive/unvaccinated track), by output band.
    "ihr_infant": 0.30,   # <1 yr  (~1 in 3 infants; CDC)
    "ihr_toddler": 0.03,  # 1-4 yr
    "ihr_5_19": 0.01,
    "ihr_20_49": 0.01,
    "ihr_50_64": 0.02,
    "ihr_65p": 0.04,
    # Partial (vaccinated) cases are milder: h_partial = partial_ratio * h_naive.
    "partial_ratio": 0.20,
    # Fraction of 0-4 incidence attributed to infants (<1). ~1/5 single-year cohorts.
    "infant_fraction": 0.20,
    # Onset-to-hospitalization delay (days); shifts the hospitalization curve later.
    "delay_days": 10,
}

# Map an output band to its naive-IHR key in the params dict.
_IHR_KEY = {
    "<1": "ihr_infant",
    "1-4": "ihr_toddler",
    "5-19": "ihr_5_19",
    "20-49": "ihr_20_49",
    "50-64": "ihr_50_64",
    "65+": "ihr_65p",
}


def _delay_shift(arr: np.ndarray, days: int) -> np.ndarray:
    """Shift a daily series forward by `days` (hospitalizations lag infection)."""
    days = int(max(0, days))
    if days == 0:
        return arr
    out = np.zeros_like(arr, dtype=float)
    if days < len(arr):
        out[days:] = arr[:-days]
    return out


def hospitalizations_from_trans(df_trans, params: dict | None = None,
                                model: str = "SEIRS (Pertussis)") -> pd.DataFrame:
    """Daily hospitalizations per output age band from a run's transitions.

    Returns a tidy DataFrame [t, age_group, hosp] over HOSP_AGE_GROUPS. Naive
    incidence is E->I; for pertussis, partial incidence Ep->Ip is added at the
    reduced partial IHR."""
    p = dict(HOSP_DEFAULTS)
    if params:
        p.update(params)
    ratio = float(p["partial_ratio"])
    f_inf = float(p["infant_fraction"])
    delay = int(p.get("delay_days", 0))
    is_pert = (model == "SEIRS (Pertussis)")

    t = df_trans["t"].to_numpy()

    def incidence(model_band: str):
        ei = (df_trans[f"E_to_I_{model_band}"].to_numpy(dtype=float)
              if f"E_to_I_{model_band}" in df_trans.columns else np.zeros(len(t)))
        epi = np.zeros(len(t))
        if is_pert and f"Ep_to_Ip_{model_band}" in df_trans.columns:
            epi = df_trans[f"Ep_to_Ip_{model_band}"].to_numpy(dtype=float)
        return ei, epi

    # Precompute the 0-4 incidence split into infant / toddler shares.
    ei04, epi04 = incidence("0-4")

    rows = []
    for out_band in HOSP_AGE_GROUPS:
        h_naive = float(p[_IHR_KEY[out_band]])
        h_part = ratio * h_naive
        if out_band == "<1":
            ei, epi = f_inf * ei04, f_inf * epi04
        elif out_band == "1-4":
            ei, epi = (1.0 - f_inf) * ei04, (1.0 - f_inf) * epi04
        else:
            ei, epi = incidence(out_band)  # model band == output band here
        daily = _delay_shift(h_naive * ei + h_part * epi, delay)
        for ti, hi in zip(t, daily):
            rows.append({"t": int(ti), "age_group": out_band, "hosp": float(hi)})

    return pd.DataFrame(rows)


def weekly_hosp_total_from_trans(df_trans, params: dict | None = None,
                                 model: str = "SEIRS (Pertussis)") -> np.ndarray:
    """Modeled weekly total hospitalizations (all output age bands), for use as a
    calibration curve target."""
    daily = hospitalizations_from_trans(df_trans, params, model)
    daily["week"] = (daily["t"] - 1) // 7
    wk = daily.groupby("week", as_index=False)["hosp"].sum().sort_values("week")
    return wk["hosp"].to_numpy(dtype=float)


def hospitalization_summary(df_trans, params: dict | None = None,
                            model: str = "SEIRS (Pertussis)") -> pd.DataFrame:
    """Total hospitalizations per output age band (+ a 'total' row)."""
    daily = hospitalizations_from_trans(df_trans, params, model)
    by_age = daily.groupby("age_group", as_index=False)["hosp"].sum()
    by_age = by_age.set_index("age_group").reindex(HOSP_AGE_GROUPS).reset_index()
    total = pd.DataFrame([{"age_group": "total", "hosp": float(by_age["hosp"].sum())}])
    return pd.concat([by_age, total], ignore_index=True)
