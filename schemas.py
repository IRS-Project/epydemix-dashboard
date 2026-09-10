# schemas.py

MODEL_COMPS = {"SEIR (Measles)": ["S", "E", "I", "R", "V"],
               "SEIRS (Influenza)": ["S", "E", "I", "R", "R1", "V"],
               # Pertussis: 8-compartment SEIRS with a parallel partial-immunity
               # track (naive S->E->I->R and partial Sp->Ep->Ip->Rp). Vaccination
               # routes S->Sp, so no separate V compartment is used.
               "SEIRS (Pertussis)": ["S", "E", "I", "R", "Sp", "Ep", "Ip", "Rp"],
               "SEIHR (COVID-19)": ["S", "E", "I", "H", "R", "V"]}

MODEL_PARAM_SCHEMAS = {
    
    "SEIR (Measles)": [
        {
            "key": "R0",
            "label": "$R_0$",
            "type": "float",
            "min": 0.1,
            "max": 20.0,
            "step": 0.1,
            "default": 12.0,
        },
        {
            "key": "incubation_period",
            "label": "Incubation period (days)",
            "type": "float",
            "min": 0.5,
            "max": 30.0,
            "step": 0.5,
            "default": 11.0,
        },
        {
            "key": "infectious_period",
            "label": "Infectious period (days)",
            "type": "float",
            "min": 0.5,
            "max": 30.0,
            "step": 0.5,
            "default": 9.0,
        },
    ],
    "SEIRS (Influenza)": [
        {
            "key": "R0",
            "label": "$R_0$",
            "type": "float",
            "min": 0.1,
            "max": 20.0,
            "step": 0.1,
            "default": 1.5,
        },
        {
            "key": "incubation_period",
            "label": "Incubation period (days)",
            "type": "float",
            "min": 0.5,
            "max": 20.0,
            "step": 0.5,
            "default": 1.5,
        },
        {
            "key": "infectious_period",
            "label": "Infectious period (days)",
            "type": "float",
            "min": 0.5,
            "max": 20.0,
            "step": 0.5,
            "default": 1.5,
        }, 
        {
            "key": "waning_immunity_period",
            "label": "Waning immunity period (days)",
            "type": "float",
            "min": 5.0,
            "max": 1000.0,
            "step": 5.0,
            "default": 365.0,
        },
        {
            "key": "seasonality_peak_day",
            "label": "Seasonality peak day (day of the year)",
            "type": "float",
            "min": 1,
            "max": 365,
            "step": 1,
            "default": 125,
        },
        {
            "key": "seasonality_amplitude",
            "label": "Seasonality",
            "type": "discrete",
            "options": ["Strong", "Moderate", "Medium", "Low", "None"],
            "default": "Medium",
        }
    ],
    # 8-compartment SEIRS with partial-immunity track (Wearing & Rohani 2009).
    # R0 is defined on the naive track (beta / gamma_naive). The partial track
    # is governed by sigma (relative infectiousness of Ip) and delta (relative
    # susceptibility of Sp).
    "SEIRS (Pertussis)": [
        {
            "key": "R0",
            "label": "$R_0$",
            "type": "float",
            "min": 0.1,
            "max": 20.0,
            "step": 0.1,
            "default": 12.0,
            "help": ("Basic reproduction number — average secondary cases from one infection in a fully "
                     "susceptible population (defined here on the naive track). Pertussis is among the "
                     "highest, classically 12–17. How to derive: use published estimates for your "
                     "setting, or fit to the early exponential growth rate r of local case counts "
                     "(R₀ ≈ 1 + r·D, where D is the generation interval ≈ incubation + infectious period). "
                     "Tactical: from two early weekly case counts C₁ then C₂, r = ln(C₂/C₁)/7 per day, "
                     "so R₀ ≈ 1 + r×30 (≈30-day generation interval)."),
        },
        {
            "key": "incubation_period",
            "label": "Incubation period (days)",
            "type": "float",
            "min": 0.5,
            "max": 30.0,
            "step": 0.5,
            "default": 9.0,
            "help": ("Mean latent period (days) from infection to becoming infectious; determines the "
                     "E→I rate (ε = 1/this). Pertussis ≈ 7–10 days. How to derive: CDC/clinical "
                     "references, or contact-tracing data (mean exposure-to-symptom-onset interval). "
                     "Tactical: average of (cough-onset date − exposure date) across investigated cases."),
        },
        {
            "key": "infectious_period",
            "label": "Infectious period — naive $I$ (days)",
            "type": "float",
            "min": 0.5,
            "max": 40.0,
            "step": 0.5,
            "default": 21.0,
            "help": ("Mean days a naive (classic) case is infectious; sets the recovery rate (γ = 1/this) "
                     "and, with R₀, the transmission rate. Pertussis ≈ 14–21 days (catarrhal stage "
                     "through ~3 weeks of paroxysms; shorter with early antibiotics). How to derive: "
                     "communicability guidance, or the observed serial interval minus the latent period. "
                     "Tactical: median of (effective-treatment-start date − cough-onset date) + 5 days, "
                     "capped at ~21 days if untreated."),
        },
        {
            "key": "infectious_period_partial",
            "label": "Infectious period — partial $I_p$ (days)",
            "type": "float",
            "min": 0.5,
            "max": 40.0,
            "step": 0.5,
            "default": 10.0,
            "help": ("Mean infectious days for partially-immune (breakthrough) cases — milder and "
                     "shorter than naive, ≈ 7–14 days. How to derive: studies of vaccinated / "
                     "previously-infected cases, or set as a fraction of the naive infectious period. "
                     "Tactical: the same onset-to-treatment calculation, computed only over "
                     "up-to-date (vaccinated) cases in the line list."),
        },
        {
            "key": "rel_infectiousness_partial",
            "label": r"Relative infectiousness of $I_p$ ($\sigma$)",
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "default": 0.2,
            "help": ("How infectious partial-track cases (Iₚ) are relative to naive cases (I), on a 0–1 "
                     "scale. Lower means the vaccinated/waned 'silent reservoir' transmits less. "
                     "How to derive: secondary-attack-rate studies comparing vaccinated vs unvaccinated "
                     "index cases, or culture-positivity / viral-load ratios (typically 0.1–0.3). "
                     "Tactical: σ = (secondary cases per contact of vaccinated index cases) ÷ "
                     "(secondary cases per contact of unvaccinated index cases), from contact investigations."),
        },
        {
            "key": "rel_susceptibility_partial",
            "label": r"Relative susceptibility of $S_p$ ($\delta$)",
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "default": 0.3,
            "help": ("Susceptibility of partially-immune people (Sₚ) relative to fully susceptible (S), "
                     "0–1; equals 1 minus effectiveness against infection (δ ≈ 1 − VE). How to derive: "
                     "vaccine-effectiveness studies, or the infection hazard ratio in previously-immune "
                     "vs naive cohorts (typically 0.1–0.5). "
                     "Tactical: δ = 1 − VE, using the screening-method VE = 1 − [PCV/(1−PCV)]·[(1−PPV)/PPV], "
                     "where PCV = % of cases vaccinated (line list) and PPV = population coverage (IIS)."),
        },
        {
            "key": "waning_full_to_partial_years",
            "label": r"Waning full$\rightarrow$partial ($\omega_1$, years)",
            "type": "float",
            "min": 0.5,
            "max": 30.0,
            "step": 0.5,
            "default": 4.0,
            "help": ("Years for strong post-infection immunity to wane to partial (R→Sₚ) ≈ 3–5 y. "
                     "How to derive: cohort/serological reinfection-interval studies, or fit to the "
                     "inter-epidemic (surge-to-surge) period in local case series. "
                     "Tactical: 1/ω₁ ≈ the average number of years between successive pertussis episodes "
                     "in repeat patients, or the observed interval between local surges."),
        },
        {
            "key": "waning_partial_to_susceptible_years",
            "label": r"Waning partial$\rightarrow$susceptible ($\omega_2$, years)",
            "type": "float",
            "min": 1.0,
            "max": 50.0,
            "step": 1.0,
            "default": 15.0,
            "help": ("Years for residual partial immunity to fully wane (Rₚ→S) ≈ 10–20 y, slower than "
                     "ω₁. How to derive: long-term reinfection / serology studies; often set as the "
                     "estimated total duration of immunity minus the ω₁ phase. "
                     "Tactical: if no local reinfection data, set 1/ω₂ ≈ (assumed total years of immunity) "
                     "− (ω₁ years) — e.g. 20 − 4 ≈ 15 y."),
        },
        # Vaccine-derived protection decays too: without this, an individual
        # vaccinated into Sp stays at reduced susceptibility delta forever
        # unless infected, since Sp's only other exit is Sp -> Ep. DTaP
        # protection wanes materially within 5-10 years of the primary series,
        # which is the documented driver of adolescent resurgence and the
        # rationale for the 11-year Tdap booster. Set to the max (50 y) to
        # approximate the previous no-vaccine-waning behaviour.
        {
            "key": "waning_vaccine_to_susceptible_years",
            "label": r"Waning vaccine $S_p\rightarrow S$ ($\omega_3$, years)",
            "type": "float",
            "min": 1.0,
            "max": 50.0,
            "step": 1.0,
            "default": 10.0,
            "help": ("Years for vaccine-derived protection to wane (Sₚ→S) ≈ 5–10 y for acellular "
                     "pertussis (DTaP). This is the documented driver of adolescent resurgence and the "
                     "rationale for the 11-year Tdap booster. How to derive: vaccine-effectiveness-"
                     "over-time studies (the annual decline in VE after the primary series). "
                     "Tactical: stratify cases by years since last dose, compute screening-method VE in "
                     "each stratum, and read off the number of years for VE to fall to about half its "
                     "initial value."),
        },
        {
            "key": "seasonality_peak_day",
            "label": "Seasonality peak day (day of the year)",
            "type": "float",
            "min": 1,
            "max": 365,
            "step": 1,
            "default": 240,
            "help": ("Day of the year (1–365) when transmission peaks. Pertussis often peaks in late "
                     "summer / early autumn (≈ day 210–260). How to derive: the month-of-onset "
                     "distribution in local surveillance — take the peak month's mid-point as day-of-year. "
                     "Tactical: peak month of monthly case counts → day ≈ (month−1)×30 + 15."),
        },
        {
            "key": "seasonality_amplitude",
            "label": "Seasonality",
            "type": "discrete",
            "options": ["Strong", "Moderate", "Medium", "Low", "None"],
            "default": "Low",
            "help": ("Strength of seasonal forcing on the transmission rate (None → Strong). Pertussis "
                     "seasonality is weak, so 'Low' is typical. How to derive: the peak-to-trough "
                     "amplitude of de-trended (seasonally decomposed) local case counts. "
                     "Tactical: compute (peak-month − trough-month cases) ÷ mean monthly cases — a small "
                     "ratio maps to 'Low', a large one to 'Strong'."),
        }
    ],
    "SEIHR (COVID-19)": [
        {
            "key": "R0",
            "label": "$R_0$",
            "type": "float",
            "min": 0.1,
            "max": 20.0,
            "step": 0.1,
            "default": 2.5,
        },
        {
            "key": "incubation_period",
            "label": "Incubation period (days)",
            "type": "float",
            "min": 0.5,
            "max": 20.0,
            "step": 0.5,
            "default": 3.0,
        },
        {
            "key": "infectious_period",
            "label": "Infectious period (days)",
            "type": "float",
            "min": 0.5,
            "max": 20.0,
            "step": 0.5,
            "default": 2.5,
        },
        {
           "key": "hospital_stay",
           "label": "Hospital stay (days)",
           "type": "float",
           "min": 0.,
           "max": 25.0,
           "step": 1.0,
           "default": 5.0, 
        },  
        {
            "key": "ph",
            "label": "Probability of hospitalization (%)",
            "type": "by_age_float",
            "min": 0.,
            "max": 100.0,
            "step": 0.1,
            # One value per model age band (0-1, 1-6, 7-10, 11-19, 20-49, 50-64, 65+).
            "default": [0.2, 0.3, 0.4, 0.5, 1.5, 5., 18.],
        }
    ]
}


INITIAL_CONDITION_DEFAULTS = {
    "SEIR (Measles)": {"infected_pct": 0.1, "immune_pct": 85.0},
    "SEIRS (Influenza)": {"infected_pct": 0.1, "immune_pct": 25.0},
    # "Background immunity" seeds the partial-immunity pool (Sp/Rp/R). At an
    # endemic start most of a vaccinated population carries partial immunity.
    # partial_infection_pct: share of seeded infections in the partial track (Ep/Ip).
    # partial_immune_pct:    Sp share of the immunity pool (remainder split Rp/R).
    "SEIRS (Pertussis)": {
        "infected_pct": 0.1,
        "immune_pct": 85.0,
        "partial_infection_pct": 33.0,
        "partial_immune_pct": 71.0,
    },
    "SEIHR (COVID-19)": {"infected_pct": 0.1, "immune_pct": 25.0},
}
