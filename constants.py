# constants.py

from datetime import datetime

LAYER_NAMES = ["home", "school", "work", "community"]

START_DATE = datetime(2026, 1, 1)

N_SIM = 25

# Model age bands. Boundaries are pertussis/vaccination-schedule oriented
# (infants <1, pre-school 1-6, school-age 7-10, adolescents 11-19, then adults).
# Each entry is (label, lower_inclusive, upper_exclusive) in single years.
AGE_BANDS = [
    ("0-1", 0, 1),
    ("1-6", 1, 7),
    ("7-10", 7, 11),
    ("11-19", 11, 20),
    ("20-49", 20, 50),
    ("50-64", 50, 65),
    ("65+", 65, 999),
]
DEFAULT_AGE_GROUPS = [label for label, _lo, _hi in AGE_BANDS]


def build_age_group_mapping(group_names) -> dict:
    """Map a location's single-year demographic group names (e.g. '0','1',…,'84+')
    onto AGE_BANDS. Built per-location so the top open-ended group ('84+', '85+', …)
    is assigned correctly rather than hard-coded. Returns {band_label: [group_name,…]}
    for the bands that have members, in AGE_BANDS order."""
    mapping = {label: [] for label, _lo, _hi in AGE_BANDS}
    for g in group_names:
        digits = "".join(ch for ch in str(g) if ch.isdigit())
        if digits == "":
            continue
        lo = int(digits)
        for label, a, b in AGE_BANDS:
            if a <= lo < b:
                mapping[label].append(str(g))
                break
    return {k: v for k, v in mapping.items() if v}


