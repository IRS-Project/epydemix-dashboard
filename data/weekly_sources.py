# data/weekly_sources.py
#
# Public weekly pertussis incidence time series, for use as a *shape* target in
# calibration (growth rate, peak timing, seasonality — the things a cumulative
# cross-tab cannot constrain).
#
# Source: CDC National Notifiable Diseases Surveillance System (NNDSS) "Weekly
# Data" table, Socrata dataset x9gk-5huc on data.cdc.gov. Fields used:
#   label   = disease name ("Pertussis")
#   states  = reporting area (state name; UPPERCASE in 2022-2024, Title Case in
#             2025-2026 — matched case-insensitively so both eras merge cleanly)
#   year    = MMWR year
#   week    = MMWR week
#   m1      = current-week case count (absent  => 0 that week; m3 is cumulative)
#
# Works for every U.S. state, DC, and the national total. Results are cached to
# data/observed/weekly_cache/<area>.csv so the app works offline after a first
# fetch and does not hit the network on every Streamlit rerun.

from __future__ import annotations
import json
import os
import re
import urllib.parse
import urllib.request

import pandas as pd

CDC_HOST = "https://data.cdc.gov"
CDC_DATASET = "x9gk-5huc"
CDC_LABEL = "Pertussis"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "observed", "weekly_cache")

# National total is stored under the reporting area "TOTAL" in this dataset.
NATIONAL_AREA = "TOTAL"
NATIONAL_LABEL = "United States (national total)"

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
    "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
]

# Selectable reporting areas: national total first, then the states + DC.
WEEKLY_AREAS = [NATIONAL_LABEL] + US_STATES


def _area_query_value(area: str) -> str:
    """Map a friendly area label to the dataset's `states` value (matched
    case-insensitively, so era-specific casing does not matter)."""
    if area == NATIONAL_LABEL:
        return NATIONAL_AREA
    return area


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _soql(params: dict, timeout: int = 30) -> list:
    query = urllib.parse.urlencode(params)
    url = f"{CDC_HOST}/resource/{CDC_DATASET}.json?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "epyscenario/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_cdc_weekly_pertussis(area: str, years=None, timeout: int = 30) -> pd.DataFrame:
    """Fetch the weekly pertussis series for a reporting area from CDC NNDSS.

    Returns a DataFrame [year, week, cases] sorted chronologically. A week with
    no `m1` value is a genuine zero. Raises on a network/HTTP error."""
    q_area = _area_query_value(area).replace("'", "''")
    where = f"label='{CDC_LABEL}' AND upper(states)=upper('{q_area}')"
    if years:
        yrs = ",".join(f"'{int(y)}'" for y in years)
        where += f" AND year in({yrs})"
    rows = _soql({
        "$select": "year,week,m1",
        "$where": where,
        "$order": "year,week",
        "$limit": "5000",
    }, timeout=timeout)

    recs = []
    for r in rows:
        try:
            y, w = int(r["year"]), int(r["week"])
        except (KeyError, TypeError, ValueError):
            continue
        raw = r.get("m1")
        try:
            cases = int(float(raw)) if raw not in (None, "", ".", "-") else 0
        except (TypeError, ValueError):
            cases = 0
        recs.append((y, w, cases))

    df = pd.DataFrame(recs, columns=["year", "week", "cases"])
    if not df.empty:
        # Eras do not overlap, but guard against any duplicate (year, week).
        df = (df.groupby(["year", "week"], as_index=False)["cases"].max()
                .sort_values(["year", "week"]).reset_index(drop=True))
    return df


def load_weekly_pertussis(area: str, years=None, refresh: bool = False):
    """Cached wrapper around fetch_cdc_weekly_pertussis.

    Returns (DataFrame[year, week, cases], source_str). Falls back to the cached
    CSV if the network fetch fails; raises only if there is no cache either."""
    slug = _slug(area)
    if years:
        slug += "_" + "_".join(str(int(y)) for y in sorted(years))
    path = os.path.join(CACHE_DIR, f"{slug}.csv")

    if not refresh and os.path.exists(path):
        return pd.read_csv(path), "cache"

    try:
        df = fetch_cdc_weekly_pertussis(area, years)
        os.makedirs(CACHE_DIR, exist_ok=True)
        df.to_csv(path, index=False)
        return df, "CDC NNDSS (network)"
    except Exception as exc:  # network/HTTP/parse failure
        if os.path.exists(path):
            return pd.read_csv(path), f"cache (refresh failed: {exc})"
        raise


def weekly_series_to_array(df: pd.DataFrame):
    """Flatten a [year, week, cases] frame to a chronological cases array."""
    if df is None or df.empty:
        return []
    d = df.sort_values(["year", "week"])
    return [float(c) for c in d["cases"].to_numpy()]
