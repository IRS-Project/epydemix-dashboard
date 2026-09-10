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
# The model's youngest band is now 0-1 (infants <1), where pertussis
# hospitalization is concentrated, so no infant sub-split is needed — each model
# age band maps directly to one hospitalization output band. An onset-to-
# hospitalization delay shifts the curve.
#
# Default IHRs reflect published pertussis patterns (CDC Pink Book / provisional
# surveillance): ~1/3 of infants <1 yr hospitalized, dropping steeply with age;
# they are user-editable and should be calibrated locally.

from __future__ import annotations
import numpy as np
import pandas as pd

from constants import DEFAULT_AGE_GROUPS

# Hospitalization output bands = the model's age bands (0-1 is already infants).
HOSP_AGE_GROUPS = list(DEFAULT_AGE_GROUPS)

# Per-case hospitalization probability (naive/unvaccinated track), by band.
_DEFAULT_IHR = {
    "0-1": 0.30,   # infants <1 yr (~1 in 3; CDC)
    "1-6": 0.03,
    "7-10": 0.01,
    "11-19": 0.01,
    "20-49": 0.01,
    "50-64": 0.02,
    "65+": 0.04,
}

HOSP_DEFAULTS = {
    "ihr": dict(_DEFAULT_IHR),
    # Partial (vaccinated) cases are milder: h_partial = partial_ratio * h_naive.
    "partial_ratio": 0.20,
    # Onset-to-hospitalization delay (days); shifts the hospitalization curve later.
    "delay_days": 10,
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
    """Daily hospitalizations per age band from a run's transitions.

    Returns a tidy DataFrame [t, age_group, hosp] over HOSP_AGE_GROUPS. Naive
    incidence is E->I; for pertussis, partial incidence Ep->Ip is added at the
    reduced partial IHR."""
    p = dict(HOSP_DEFAULTS)
    if params:
        p.update(params)
    ihr = p.get("ihr", _DEFAULT_IHR)
    ratio = float(p["partial_ratio"])
    delay = int(p.get("delay_days", 0))
    is_pert = (model == "SEIRS (Pertussis)")

    t = df_trans["t"].to_numpy()
    n = len(t)

    rows = []
    for band in HOSP_AGE_GROUPS:
        ei = (df_trans[f"E_to_I_{band}"].to_numpy(dtype=float)
              if f"E_to_I_{band}" in df_trans.columns else np.zeros(n))
        epi = np.zeros(n)
        if is_pert and f"Ep_to_Ip_{band}" in df_trans.columns:
            epi = df_trans[f"Ep_to_Ip_{band}"].to_numpy(dtype=float)
        h_naive = float(ihr.get(band, 0.0))
        h_part = ratio * h_naive
        daily = _delay_shift(h_naive * ei + h_part * epi, delay)
        for ti, hi in zip(t, daily):
            rows.append({"t": int(ti), "age_group": band, "hosp": float(hi)})

    return pd.DataFrame(rows)


def weekly_hosp_total_from_trans(df_trans, params: dict | None = None,
                                 model: str = "SEIRS (Pertussis)") -> np.ndarray:
    """Modeled weekly total hospitalizations (all bands), for a curve target."""
    daily = hospitalizations_from_trans(df_trans, params, model)
    daily["week"] = (daily["t"] - 1) // 7
    wk = daily.groupby("week", as_index=False)["hosp"].sum().sort_values("week")
    return wk["hosp"].to_numpy(dtype=float)


def hospitalization_summary(df_trans, params: dict | None = None,
                            model: str = "SEIRS (Pertussis)") -> pd.DataFrame:
    """Total hospitalizations per age band (+ a 'total' row)."""
    daily = hospitalizations_from_trans(df_trans, params, model)
    by_age = daily.groupby("age_group", as_index=False)["hosp"].sum()
    by_age = by_age.set_index("age_group").reindex(HOSP_AGE_GROUPS).reset_index()
    total = pd.DataFrame([{"age_group": "total", "hosp": float(by_age["hosp"].sum())}])
    return pd.concat([by_age, total], ignore_index=True)
