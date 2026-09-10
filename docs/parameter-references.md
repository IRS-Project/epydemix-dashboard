# EpyScenario Pertussis Model — Parameter & Data Provenance

This page documents where every default value, plausible range, prior bound, and
data input in the pertussis model comes from. It is the single reference for
"why is this number what it is."

**How to read the _Basis_ column** — values are not all equal in pedigree, and this
is stated honestly:

| Tag | Meaning |
|---|---|
| **Literature** | Value/range taken directly from a cited source. |
| **Lit‑informed** | A default chosen to sit inside a published range, but not a single quoted figure. |
| **Assumption** | An analyst placeholder with no direct source — **calibrate to local data before relying on it.** |
| **Data‑derived** | Computed from a loaded dataset (Lane County line‑list or CDC NNDSS). |

Every parameter's in‑app tooltip ("How to derive" / "Tactical") gives the operational
recipe for replacing the default with a locally‑measured value. Numbered sources `[n]`
are listed at the bottom.

---

## 1. Model parameters — SEIRS (Pertussis)

Defaults and ranges as configured in `schemas.py` (`MODEL_PARAM_SCHEMAS["SEIRS (Pertussis)"]`).

| Parameter (symbol) | Default | Range (UI) | Basis | Source |
|---|---|---|---|---|
| Basic reproduction number **R₀** | 12 | 6 – 18 | Lit‑informed | Classic pertussis R₀ 12–17 `[6]`; note the 12–17 figure derives from 1908–1917 data `[7]`. Fit locally via early growth rate. |
| Incubation period (1/ε) | 9 d | 0.5 – 30 | Literature | Pertussis incubation ≈ 7–10 d, CDC Pink Book `[6]` |
| Infectious period — naive **I** (1/γ) | 21 d | 0.5 – 40 | Literature | Catarrhal→paroxysmal communicability ≈ 14–21 d `[6]` |
| Infectious period — partial **Iₚ** (1/γₚ) | 10 d | 0.5 – 40 | Lit‑informed | Milder/shorter breakthrough illness (≈7–14 d); set as a fraction of naive `[1][6]` |
| Relative infectiousness of Iₚ (**σ**) | 0.2 | 0 – 1 | Lit‑informed / Assumption | Vaccinated index cases less infectious (≈0.1–0.3 from secondary‑attack studies) `[1]` — **calibrate** |
| Relative susceptibility of Sₚ (**δ**) | 0.3 | 0 – 1 | Lit‑informed / Assumption | δ ≈ 1 − VE (≈0.1–0.5) `[1][6]` — **calibrate** |
| Waning R→Sₚ (**ω₁**) | 4 y | 0.5 – 30 | Literature | Post‑infection immunity wanes to partial ≈ 3–5 y `[1]` |
| Waning Rₚ→S (**ω₂**) | 15 y | 1 – 50 | Lit‑informed | Residual immunity fully wanes ≈ 10–20 y, slower than ω₁ `[1][2]` |
| Waning vaccine Sₚ→S (**ω₃**) | 10 y | 1 – 50 | Literature | DTaP protection wanes ≈ 5–10 y; drives adolescent resurgence / Tdap‑at‑11 rationale `[6]` |
| Seasonality peak day | 240 (late Aug) | 1 – 365 | Lit‑informed / Data‑derived | Pertussis peaks late summer–early autumn `[3]`; can be estimated from multi‑year NNDSS in‑app `[8]` |
| Seasonality amplitude | "Low" | Strong…None | Lit‑informed | Pertussis seasonal forcing is weak `[2][3]` |

> **ω₃ note:** without vaccine waning, anyone vaccinated into Sₚ would stay at reduced
> susceptibility indefinitely — biologically wrong for acellular pertussis. ω₃ is the
> mechanism reproducing waning‑driven adolescent resurgence.

---

## 2. Initial conditions — SEIRS (Pertussis)

From `INITIAL_CONDITION_DEFAULTS` (`schemas.py`).

| Field | Default | Basis | Source / rationale |
|---|---|---|---|
| Initial infected % | 0.1 % | Assumption | Small outbreak seed |
| Background immunity % | 85 % | Lit‑informed | High‑vaccination endemic setting; consistent with US DTaP/Tdap coverage `[6]` |
| Partial‑infection share (Eₚ/Iₚ of seed) | 33 % | Assumption | Split of seeded cases into the partial track — **calibrate** |
| Sₚ share of immune pool | 71 % | Data‑informed | Chosen so the vaccinated share of cases (~66 %) is reproduced from the Lane County line‑list `[5]`; remainder split Rₚ:R ≈ 0.24:0.05 `[1]` |

---

## 3. Bayesian calibration (ABC‑SMC) — prior bounds

Uniform prior bounds from `engine/calibration.py` (`ABC_PARAMS`). These are analyst‑set to
**bracket** the literature ranges above, not themselves measurements.

| Parameter | Prior (uniform) | Basis |
|---|---|---|
| R₀ | 6 – 18 | Brackets classic 12–17 `[6]` |
| σ (rel. infectiousness partial) | 0.05 – 0.40 | Brackets secondary‑attack range `[1]` |
| δ (rel. susceptibility partial) | 0.10 – 0.60 | Brackets 1 − VE `[1][6]` |
| Sₚ share (%) | 40 – 90 | Analyst‑set span around the endemic default |

Method: ABC‑SMC with adaptive tolerance, Gaussian perturbation kernel, importance weights `[4]`.
Targets: observed age distribution + vaccinated share (cross‑tab `[5]`) and, optionally, the
CDC NNDSS weekly case‑curve shape `[8]`.

---

## 4. Hospitalization observation model

Per‑case hospitalization ratios (naive track) from `engine/hospitalization.py` (`_DEFAULT_IHR`).
Applied as a post‑processing lens (does not alter transmission).

| Age band | Default IHR | Basis |
|---|---|---|
| 0‑1 (infants <1) | 0.30 | Literature — ~1 in 3 infants <1 hospitalized `[6][9]` |
| 1‑6 | 0.03 | Lit‑informed — steep drop after infancy `[6]` |
| 7‑10 | 0.01 | Assumption |
| 11‑19 | 0.01 | Assumption |
| 20‑49 | 0.01 | Assumption |
| 50‑64 | 0.02 | Assumption |
| 65+ | 0.04 | Lit‑informed |
| Partial (vaccinated) IHR ratio | 0.20 × naive | Assumption — milder vaccinated disease |
| Onset→hospitalization delay | 10 d | Lit‑informed — pertussis ≈ 1–2 wk |

> Provisional 2023 NNDSS: <6 mo ≈ 21 %, 6–11 mo ≈ 8 % hospitalized `[9]`. IHRs are
> user‑editable and **should be calibrated to local records.**

---

## 5. Vaccination defaults (DTaP / Tdap)

Vaccination Planner grid (`pages/Vaccination_Planner.py`) and the seeded campaign set
(`data/campaign_store.py`).

| Group | Coverage | VE (against infection) | Basis |
|---|---|---|---|
| 0‑1, 1‑6 (DTaP primary series) | 92 % | 80 % | Lit‑informed — US childhood DTaP coverage & VE `[6]` |
| 7‑10, 11‑19 (school‑entry / Tdap adolescent) | 90 % | 80 % | Lit‑informed `[6]` |
| 20‑49, 50‑64, 65+ (Td/Tdap decennial) | ~7 % (≈10 %/yr, capped) | 70 % | Lit‑informed / Assumption — low adult booster uptake `[6]` |

Schedule structure (5‑dose DTaP by age ~6; Tdap at 11–12; decennial adult boosters)
follows the CDC immunization schedule `[6]`.

---

## 6. Age structure & contact matrices

| Item | Value | Basis | Source |
|---|---|---|---|
| Age bands | 0‑1, 1‑6, 7‑10, 11‑19, 20‑49, 50‑64, 65+ | Assumption (design choice) | Pertussis/vaccination‑schedule oriented (infant, pre‑school, school‑age, adolescent, adults) |
| Population by age | Single‑year, aggregated to the 7 bands | Data | US Census age distributions via epydemix‑data `[10]` |
| Contact matrices (home/school/work/community) | Single‑year, aggregated to 7×7 | Literature | Mistry et al. high‑resolution mixing `[3]`, distributed via epydemix‑data `[10]` |

---

## 7. Simulation settings

| Setting | Default | Basis |
|---|---|---|
| Stochastic replicates (N_SIM) | 25 | Analyst — ensemble size for quantile bands |
| Simulation length | 250 d | Assumption — single outbreak season |
| Time step (Δt) | 0.2 d | Analyst — accuracy/speed trade‑off |
| Start date | 2026‑01‑01 | Analyst — day‑of‑year anchor for seasonality |
| Engine | epydemix stochastic compartmental | Software `[10]` |
| Model structure | 8‑compartment SEIRS partial‑immunity | Literature `[1]` |

---

## 8. Observed & calibration data sources

| Dataset | Use | Provenance |
|---|---|---|
| Observed case cross‑tab — age band × vaccination‑up‑to‑date status (example: Lane County, 489 cases) | Age‑distribution + vaccinated‑share calibration targets; seeds the Sₚ share | Local surveillance line‑list aggregated to the model's bands `[5]` — required form in **Appendix A**. Example CSV: `data/observed/lane_county_pertussis.csv` |
| CDC NNDSS weekly pertussis (Socrata `x9gk-5huc`) | Weekly case‑curve shape target (R₀/seasonality); multi‑year seasonality estimate | CDC NNDSS provisional weekly data `[8]`; **provisional — undercounts vs finalized annual** |
| Small‑numbers suppression | Data‑handling constraint | OHA "Guidelines for Reporting Small Numbers to Protect Confidentiality," v2 (2015): denominator ≥ 50 primary rule; program count thresholds (e.g. ≥5) `[11]` |

---

## References

1. Wearing HJ, Rohani P. Estimating the duration of pertussis immunity using epidemiological signatures. *PLoS Pathog.* 2009;5(10):e1000647. doi:10.1371/journal.ppat.1000647
2. Lavine JS, King AA, Bjørnstad ON. Natural immune boosting in pertussis dynamics and the potential for long‑term vaccine failure. *Proc Natl Acad Sci USA.* 2011;108(17):7259–7264. doi:10.1073/pnas.1014394108
3. Mistry D, Litvinova M, Pastore y Piontti A, et al. Inferring high‑resolution human mixing patterns for disease modeling. *Nat Commun.* 2021;12:323. doi:10.1038/s41467-020-20544-y
4. Toni T, Welch D, Strelkowa N, Ipsen A, Stumpf MPH. Approximate Bayesian computation scheme for parameter inference and model selection in dynamical systems. *J R Soc Interface.* 2009;6(31):187–202. doi:10.1098/rsif.2008.0172
5. Observed case cross‑tabulation by age band × vaccination‑up‑to‑date status — a local surveillance line‑list aggregated to the model's age bands. **Required form, file format, and small‑cell handling: see Appendix A.** Example instance: Lane County, Oregon pertussis line‑list, provided by the SOAR / International Responder Systems team (489 cases; not independently published; see also System Description §13.1).
6. Havers FP, Moro PL, Hariri S, et al. Pertussis. In: *Epidemiology and Prevention of Vaccine‑Preventable Diseases* (Pink Book). 14th ed. Atlanta, GA: CDC; 2021. Ch. 16.
7. Delamater PL, Street EJ, Leslie TF, Yang YT, Jacobsen KH. Complexity of the Basic Reproduction Number (R₀). *Emerg Infect Dis.* 2019;25(1):1–4. doi:10.3201/eid2501.171901 (Notes the pertussis R₀ 12–17 origin in 1908–1917 data.)
8. CDC National Notifiable Diseases Surveillance System (NNDSS) — Weekly Data. data.cdc.gov dataset `x9gk-5huc`. (Provisional weekly counts; see also cdc.gov/pertussis surveillance.)
9. CDC. 2023 Provisional Pertussis Surveillance Report (age‑specific hospitalization percentages). cdc.gov/pertussis.
10. Gozzi N, Chinazzi M, Davis JT, Gioannini C, Rossi L, Ajelli M, Perra N, Vespignani A. Epydemix: an open‑source Python package for epidemic modeling with integrated approximate Bayesian calibration. *PLoS Comput Biol.* 2025;21(11):e1013735. doi:10.1371/journal.pcbi.1013735  ·  Contact/population data: epydemix‑data (github.com/epistorm/epydemix-data).
11. Oregon Public Health Division. Guidelines for Reporting Small Numbers to Protect Confidentiality, Version 2. March 2015.

---

## Appendix A — Observed case data: required form & example

**Required form.** Calibration and outbreak‑seeding need an observed **case
cross‑tabulation**: confirmed case counts broken down by **age** and
**vaccination‑up‑to‑date status**. The status maps onto the model's two tracks:

| Status column | Meaning | Model track |
|---|---|---|
| **No** | not up to date on vaccination | naive (I / E→I) |
| **Yes** | up to date | partial (Iₚ / Eₚ→Iₚ) |
| **Unknown** | status not established | allocated within band by the known No:Yes ratio |

**File format.** A CSV in `data/observed/` with an optional metadata header and one
row per age label:

```
# name: <dataset name shown in the app>
# geography_hint: <epydemix location, e.g. United_States__Oregon__Lane_County>
# note: <one-line description>
# source: <provenance statement>
age_label,No,Unknown,Yes
0,16,0,13
1-6,45,3,44
50+,9,1,8
```

`age_label` accepts single years, `lo-hi` bands, or an open `50+`; all are
auto‑aggregated to the model's seven bands. Any CSV in `data/observed/` appears
automatically in the app's dataset dropdown.

**How it's used.** It supplies two *scale‑free* calibration targets — the case
**age distribution** and the **vaccinated (partial) share** = Yes ÷ (Yes + No) — and
seeds the Sₚ share of the immune pool. It is **not** a time series; the weekly
epidemic‑curve target is drawn separately from CDC NNDSS `[8]`.

**Small‑cell suppression.** Health departments commonly suppress cells with counts
below a threshold (often < 5) and require a denominator ≥ 50 (OHA rule `[11]`). To
avoid suppression, request the data **pre‑aggregated to the model's seven bands ×
{up‑to‑date, not up‑to‑date}** — at that granularity band totals are well above both
thresholds. Where a cell is still suppressed, treat it as the interval **[1, 4]**,
never as 0.

**Example instance — Lane County, Oregon.** The bundled dataset
(`data/observed/lane_county_pertussis.csv`) is a Lane County pertussis line‑list
provided by the SOAR/IRS team: **489 cases (160 No / 18 Unknown / 311 Yes)**, an
overall **~66 % vaccinated share**. Its single‑year rows start at age 1 and fold 65+
into "50+", so the model's 0‑1 and 65+ bands show zero observed cases for this source.

**Caveat.** The vaccinated share of *cases* is **not** population vaccination
*coverage* — in a highly vaccinated population many cases are breakthroughs. Use it
as a structural calibration target, not as a coverage estimate; substitute registry
coverage (e.g. Oregon ALERT IIS) where a true denominator is available.

---

*Generated as a companion to the System Description. Values reflect the code at time of
writing (`constants.py`, `schemas.py`, `engine/calibration.py`, `engine/hospitalization.py`,
`pages/Vaccination_Planner.py`, `data/`). Re‑verify against the source files after parameter
changes.*
