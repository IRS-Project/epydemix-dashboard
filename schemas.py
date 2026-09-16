# schemas.py

MODEL_COMPS = {"SEIR (Measles)": ["S", "E", "I", "R", "V"],
               "SEIRS (Influenza)": ["S", "E", "I", "R", "R1", "V"],
               # Pertussis: 8-compartment SEIRS with a parallel partial-immunity
               # track (naive S->E->I->R and partial Sp->Ep->Ip->Rp). Vaccination
               # routes S->Sp, so no separate V compartment is used.
               "SEIRS (Pertussis)": ["S", "E", "I", "R", "Sp", "Ep", "Ip", "Rp"],
               "SEIHR (COVID-19)": ["S", "E", "I", "H", "R", "V"]}

# Seasonality-amplitude choices. The stored value is the plain label (the engine's
# SEASONALITY_OPTIONS maps it to a trough/peak ratio); the dropdown shows the
# peak-to-trough swing next to each so the strength is legible. Order runs from
# strongest to none, matching the engine mapping (Strong 0.50 … None 1.00).
SEASONALITY_AMPLITUDE_OPTIONS = ["Strong", "Moderate", "Medium", "Weak", "Low", "None"]
SEASONALITY_AMPLITUDE_LABELS = {
    "Strong": "Strong — 50% peak-to-trough",
    "Moderate": "Moderate — 35% peak-to-trough",
    "Medium": "Medium — 25% peak-to-trough",
    "Weak": "Weak — 15% peak-to-trough",
    "Low": "Low — 10% peak-to-trough",
    "None": "None — flat (0%)",
}

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
            "options": SEASONALITY_AMPLITUDE_OPTIONS,
            "option_labels": SEASONALITY_AMPLITUDE_LABELS,
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
            "min": 5.0,
            "max": 17.0,
            "step": 0.1,
            "default": 8.0,
            "help": ("**Description:** Average number of secondary cases from one infectious individual "
                     "in a fully susceptible population. One of the highest of any vaccine-preventable "
                     "disease.\n\n"
                     "**Default rationale:** Traditionally the reproduction number used for pertussis is "
                     "12–17 (Anderson & May). Delamater et al. show those historic values (1908–1917 U.S.; "
                     "1944–1979 England & Wales) are unlikely to match present-day epidemiology, and "
                     "Kretzschmar et al. (2010) estimate 5–6 using serology + POLYMOD contact matrices. "
                     "8 is chosen as a middle value between these disparate ranges."),
            "references": [
                "Anderson RM, May RM. Directly transmitted infectious diseases: control by vaccination. Science. 1982;215:1053–1060.",
                "Kretzschmar M, Teunis PFM, Pebody RG. Incidence and reproduction numbers of pertussis: estimates from serological and social contact data in five European countries. PLoS Med. 2010;7(6):e1000291.",
                "Delamater PL, Street EJ, Leslie TF, Yang YT, Jacobsen KH. Complexity of the basic reproduction number (R0). Emerg Infect Dis. 2019;25(1):1–4.",
            ],
        },
        {
            "key": "incubation_period",
            "label": "Incubation period (days)",
            "type": "float",
            "min": 3.0,
            "max": 30.0,
            "step": 0.5,
            "default": 9.0,
            "help": ("**Description:** Inverse of the rate at which exposed individuals become infectious "
                     "(the E→I rate, ε = 1/this). Mean incubation period ≈ 7–10 days.\n\n"
                     "**Default rationale:** The CDC Pink Book gives a typical incubation of 7–10 days; "
                     "9 sits at the centre of that modal window, and the 3–30 range accommodates the "
                     "documented tail."),
            "references": [
                "Havers FP, Pedro FML, Hariri S, Skoff T. Chapter 16: Pertussis. In: Epidemiology and Prevention of Vaccine-Preventable Diseases (Pink Book). 14th ed. CDC; 2021.",
            ],
        },
        {
            "key": "infectious_period",
            "label": "Infectious period — naive $I$ (days)",
            "type": "float",
            "min": 5.0,
            "max": 30.0,
            "step": 0.5,
            "default": 15.0,
            "help": ("**Description:** Days a fully infectious classic-pertussis case (symptomatic with "
                     "paroxysmal cough) is infectious — the primary driver of transmission. Sets the "
                     "recovery rate γ = 1/this.\n\n"
                     "**Default rationale:** Pink Book communicability runs up to ~21 days untreated but is "
                     "front-loaded in the catarrhal and early paroxysmal stages, and is shortened to ~5 days "
                     "by effective antibiotics. 15 days is a central 'effective' infectious period."),
            "references": [
                "Havers FP, Pedro FML, Hariri S, Skoff T. Chapter 16: Pertussis. In: Epidemiology and Prevention of Vaccine-Preventable Diseases (Pink Book). 14th ed. CDC; 2021.",
            ],
        },
        {
            "key": "infectious_period_partial",
            "label": "Infectious period — partial $I_p$ (days)",
            "type": "float",
            "min": 5.0,
            "max": 30.0,
            "step": 0.5,
            "default": 12.0,
            "help": ("**Description:** Days a partially-immune case is infectious — milder illness, shorter "
                     "duration, lower infectiousness; often undiagnosed, the 'silent' adult reservoir.\n\n"
                     "**Default rationale:** Vaccinated / previously-infected cases are clinically milder and "
                     "shorter (Tozzi 2003; McNamara 2017) yet still transmit (Warfel 2014). Set below the "
                     "naive period at 12 days (~80% of naive), and always ≤ the naive infectious period."),
            "references": [
                "Tozzi AE, Rava L, Ciofi degli Atti ML, Salmaso S. Clinical presentation of pertussis in unvaccinated and vaccinated children in the first six years of life. Pediatrics. 2003;112(5):1069–1075.",
                "Warfel JM, Zimmerman LI, Merkel TJ. Acellular pertussis vaccines protect against disease but fail to prevent infection and transmission in a nonhuman primate model. Proc Natl Acad Sci USA. 2014;111(2):787–792.",
                "McNamara LA, et al. Reduced severity of pertussis in persons with age-appropriate pertussis vaccination—United States, 2010–2012. Clin Infect Dis. 2017;65(5):811–818.",
            ],
        },
        {
            "key": "rel_infectiousness_partial",
            "label": r"Relative infectiousness of $I_p$ ($\sigma$)",
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "default": 0.5,
            "help": ("**Description:** Scales the contribution of Iₚ to the force of infection relative to I "
                     "(0–1). Reflects milder illness and shorter coughing episodes in partially-immune "
                     "individuals.\n\n"
                     "**Default rationale:** Warfel (2014) showed vaccinated hosts transmit efficiently "
                     "(σ well above 0), while milder cough and lower shedding argue for a reduction; 0.5 "
                     "(half a classic case's infectiousness) balances the two. A primary ABC-SMC "
                     "calibration target."),
            "references": [
                "Wearing HJ, Rohani P. Estimating the duration of pertussis immunity using epidemiological signatures. PLoS Pathog. 2009;5(10):e1000647.",
                "Warfel JM, Zimmerman LI, Merkel TJ. Acellular pertussis vaccines protect against disease but fail to prevent infection and transmission in a nonhuman primate model. Proc Natl Acad Sci USA. 2014;111(2):787–792.",
            ],
        },
        {
            "key": "rel_susceptibility_partial",
            "label": r"Relative susceptibility of $S_p$ ($\delta$)",
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "default": 0.3,
            "help": ("**Description:** Scales the infection rate of Sₚ relative to S (0–1). Reflects partial "
                     "protection from prior immunity; lower δ = stronger residual protection.\n\n"
                     "**Default rationale:** δ ≈ 1 − VE against infection. Using screening-method VE "
                     "(Orenstein 1985) and typical pertussis VE of ~70–85%, δ falls in ~0.15–0.30; 0.3 "
                     "(VE ≈ 70%) is a conservative centre for a pool mixing recently- and remotely-immunised "
                     "individuals."),
            "references": [
                "Orenstein WA, et al. Field evaluation of vaccine efficacy. Bull World Health Organ. 1985;63(6):1055–1068.",
            ],
        },
        {
            "key": "waning_full_to_partial_years",
            "label": r"Waning full$\rightarrow$partial ($\omega_1$, years)",
            "type": "float",
            "min": 0.5,
            "max": 30.0,
            "step": 0.5,
            "default": 4.0,
            "help": ("**Description:** Years over which R loses sterilizing immunity and transitions to Sₚ — "
                     "the gradual loss of full protection.\n\n"
                     "**Default rationale:** Wendelboe (2005) reviews immunity duration (~4–20 y after "
                     "natural infection, ~4–12 y after vaccination); the initial sterilizing phase is the "
                     "shorter one, ~4 years."),
            "references": [
                "Wendelboe AM, Van Rie A, Salmaso S, Englund JA. Duration of immunity against pertussis after natural infection or vaccination. Pediatr Infect Dis J. 2005;24(5 Suppl):S58–S61.",
            ],
        },
        {
            "key": "waning_partial_to_susceptible_years",
            "label": r"Waning partial$\rightarrow$susceptible ($\omega_2$, years)",
            "type": "float",
            "min": 1.0,
            "max": 50.0,
            "step": 1.0,
            "default": 12.0,
            "help": ("**Description:** Years over which Rₚ loses remaining partial immunity and returns to S. "
                     "Slower than ω₁ — partial immunity persists longer.\n\n"
                     "**Default rationale:** The residual, non-sterilizing phase outlasts ω₁ (Wendelboe 2005: "
                     "natural-infection immunity extends toward ~20 y). 12 years keeps the ordering ω₂ > ω₁ "
                     "and sits within the reviewed range."),
            "references": [
                "Wendelboe AM, Van Rie A, Salmaso S, Englund JA. Duration of immunity against pertussis after natural infection or vaccination. Pediatr Infect Dis J. 2005;24(5 Suppl):S58–S61.",
            ],
        },
        {
            "key": "waning_vaccine_to_susceptible_years",
            "label": r"Waning vaccine $S_p\rightarrow S$ ($\omega_3$, years)",
            "type": "float",
            "min": 2.0,
            "max": 12.0,
            "step": 1.0,
            "default": 7.0,
            "help": ("**Description:** Years over which vaccine-derived partial protection (Sₚ) is lost, "
                     "returning individuals to full susceptibility (S) — the acellular-vaccine waning behind "
                     "adolescent resurgence.\n\n"
                     "**Default rationale:** Klein (2012, NEJM) found the odds of pertussis rose ~42% per "
                     "year after the fifth DTaP dose — rapid waning of acellular protection over roughly five "
                     "years, the rationale for the Tdap booster at 11–12 y. 7 years is a central estimate "
                     "spanning rapid (~5 y) and more durable (~10 y) responses."),
            "references": [
                "Klein NP, Bartlett J, Rowhani-Rahbar A, Fireman B, Baxter R. Waning protection after fifth dose of acellular pertussis vaccine in children. N Engl J Med. 2012;367(11):1012–1019.",
            ],
        },
        {
            "key": "seasonality_peak_day",
            "label": "Seasonality peak day (day of the year)",
            "type": "float",
            "min": 1,
            "max": 365,
            "step": 1,
            "default": 240,
            "help": ("**Description:** Day of the year (1–365) at which the seasonal transmission multiplier "
                     "peaks. Pertussis often peaks in late summer / early autumn.\n\n"
                     "**Default rationale:** Fine & Clarkson (1986) documented summer–autumn pertussis "
                     "seasonality, and US surveillance (CDC NNDSS) shows late-summer/early-autumn peaks; "
                     "day 240 (late August) is a central value, best refined from local multi-year data."),
            "references": [
                "Fine PEM, Clarkson JA. Seasonal influences on pertussis. Int J Epidemiol. 1986;15(2):237–247.",
                "CDC National Notifiable Diseases Surveillance System (NNDSS) — Weekly Data. data.cdc.gov dataset x9gk-5huc.",
            ],
        },
        {
            "key": "seasonality_amplitude",
            "label": "Seasonality",
            "type": "discrete",
            "options": SEASONALITY_AMPLITUDE_OPTIONS,
            "option_labels": SEASONALITY_AMPLITUDE_LABELS,
            "default": "Low",
            "help": ("**Description:** Strength of the seasonal forcing on transmission (peak-to-trough), "
                     "from None to Strong.\n\n"
                     "**Default rationale:** Pertussis seasonal forcing is weak relative to strongly seasonal "
                     "childhood infections (Wearing & Rohani 2009; Fine & Clarkson 1986); 'Low' (~10% "
                     "peak-to-trough) is typical."),
            "references": [
                "Wearing HJ, Rohani P. Estimating the duration of pertussis immunity using epidemiological signatures. PLoS Pathog. 2009;5(10):e1000647.",
                "Fine PEM, Clarkson JA. Seasonal influences on pertussis. Int J Epidemiol. 1986;15(2):237–247.",
            ],
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
