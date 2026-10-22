"""Retirement-age sensitivity of the general-government lines (France).

What a year of legal retirement age does to each Redbox line, and when
(D-S20-001, serves the France fiscal brief). The question the committee put:
if a 2027 government moves the age (62 for everyone, 60 for those who
started work before 20, or the 64 of the 2023 law resumed), how much does
each category of expenditure and revenue move, in which year, and how far
do the published methods disagree?

Design. Everything is a product of two things:

    impact(line, year) = Σ_groups  exposure(group, year, policy)  ×  unit(line, group, year, method)

* **Exposure** is demographic and legal, and depends on the policy: the
  number of person-years in `year` spent in retirement under the policy
  that would have been spent before the pension age under the law as it
  stands (the LFSS 2026 path: 62 years 9 months frozen for the 1964 and
  Q1-1965 cohorts, 64 from the 1969 cohort). It is computed month by
  month from Eurostat population by single year of age
  (`data/manual/FRA_population_by_age.csv`), in "cohort-person-years":
  one cohort-year = a whole birth cohort retiring one year earlier.
* **Units** are the cost per cohort-person-year on each line, and are
  where the methods differ. They are, by construction, the same whatever
  the plan: the plan only changes the exposure. That is the linearity the
  committee asked for, and its limits are in the assumptions register
  (asymmetry, the durée, pension levels, the macro loop).

Methods, as the brief's section numbers them:
  1. top-down elasticities: the DG Trésor decomposition for the COR
     (Jan 2022) with the Mésange time path; the Cour des comptes' one-year
     figure (Feb 2025); the DREES costing of the 2026 suspension (COR 2026)
     used as a calibration of the unit;
  2. bottom-up cohort arithmetic: cohort × share bound by the floor ×
     pension, wage, contribution and tax rates, with the DREES spillover
     to other benefits;
  3. published costings (RN, OFCE, CNAV, Zemmour, Montaigne) converted
     to the common unit and re-applied to the same exposures;
  4. the growth channel: GDP per cohort-year from Mésange / OFCE /
     Rexecode, revenue at unit elasticity;
  5. the central matrix expressed on the strict file's forward paths.

Every parameter is an `Assumption` in `ASSUMPTIONS` with its source and a
status (sourced / inferred / declared / missing). `register()` prints the
lot; the brief carries it in full. Nothing is fitted.

Conventions: calendar years; EUR bn; a positive expenditure impact is more
spending, a positive revenue impact is more revenue; `balance_bn` is the
effect on the primary balance (revenue less expenditure), negative = worse.
Prices: unit costs are at 2024 prices and indexed at the engine's 2%
deflator; GDP is the engine's reference path (`simulate.gdp_path`).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from ggfiscal.debt import simulate as sim

ROOT, DELIV = sim.ROOT, sim.DELIV
POP_FILE = ROOT / "data" / "manual" / "FRA_population_by_age.csv"
FIRST_YEAR, LAST_YEAR = 2026, 2040
BASE_PRICE_YEAR = 2024
DEFLATOR = 0.02

LINES = ["GF10_2", "GF10_X", "GF10_5", "R06", "R03", "R01", "R02", "R04"]
LINE_LABEL = {"GF10_2": "Old age (pensions)", "GF10_X": "Social protection ex old age and unemployment",
              "GF10_5": "Unemployment", "R06": "Net social contributions", "R03": "Taxes on household income",
              "R01": "Value added tax", "R02": "Other taxes on production and imports", "R04": "Taxes on corporate income"}
EXPENDITURE = {"GF10_2", "GF10_X", "GF10_5"}


# --------------------------------------------------------------------------- assumptions
@dataclass(frozen=True)
class Assumption:
    id: str
    name: str
    value: object
    unit: str
    low: object = None
    high: object = None
    source: str = ""
    status: str = "declared"        # sourced | inferred | declared | missing
    note: str = ""


ASSUMPTIONS: list[Assumption] = [
    # --- demography and law
    Assumption("D1", "Population by single year of age", "Eurostat", "persons",
               source="Eurostat demo_pjan (1 Jan 2024, 2025) and proj_23np baseline (2027–2045), retrieved 22 Oct 2026; data/manual/FRA_population_by_age.csv",
               status="sourced", note="2026 is the 2025 population aged one year (no 2026 vintage yet). Cohort size = people at age 60 in the year the cohort turns 60; mortality between 60 and 64 ignored (≈1% a year)."),
    Assumption("L1", "Age of entitlement (AOD) by cohort, law as it stands", "COR Table 1.4", "years",
               source="COR, Rapport annuel June 2026, Tableau 1.4 (LFSS 2026 suspension): 1960–61 62; Sep–Dec 1961 62.25; 1962 62.5; 1963–64 62.75; Jan–Mar 1965 62.75; Apr–Dec 1965 63; 1966 63.25; 1967 63.5; 1968 63.75; 1969+ 64",
               status="sourced"),
    Assumption("L2", "Age of entitlement by cohort, 2023 law before suspension", "COR Table 1.4", "years",
               source="same table, 'après réforme' column: 1964 63; 1965 63.25; 1966 63.5; 1967 63.75; 1968+ 64", status="sourced",
               note="Used only to cost the suspension (calibration M5) and to read published repeal costings (M6)."),
    Assumption("L3", "Early-career (carrière longue, started before 20) age = AOD − 2, floor 60", 2.0, "years",
               source="Law of 14 April 2023: departure two years before the AOD for a start before 20 (four before 18, six before 16)", status="inferred",
               note="The before-16 and before-18 tiers (58, 60) are folded into the before-20 tier; the durée condition (all quarters) is not modelled."),
    Assumption("L4", "Required insurance duration (durée) 172 quarters from the 1966 cohort", 172, "quarters",
               source="COR Table 1.4", status="sourced",
               note="Not modelled as a separate lever. The RN's 42 annuités (168) would also lower the age for people bound by the durée rather than the floor: omitted, direction = more cost (see U10)."),
    # --- policies
    Assumption("P0", "Policy start date", "2028-01-01", "date", low="2028-09-01", high="2028-01-01",
               source="committee: scenario policy starts in 2028 (D-S18-001 rule 3); a LFSS would take effect 1 September", status="declared",
               note="Applies to pensions liquidated from that date; no retroactivity for people already past the new age (they retire at once)."),
    Assumption("P1", "'62 for all': AOD 62 for every cohort whose AOD under the law exceeds 62", 62.0, "years",
               source="Le Pen, 14–17 Oct 2026 (franceinfo, Europe 1/CNEWS)", status="sourced"),
    Assumption("P2", "'60 for early starters': 60 with 40 annuités for a start before 20; 62 for the others", 60.0, "years",
               source="Le Pen, 17 Oct 2026; Chenu, RTL 18 Oct 2026; full plan promised 17 Nov 2026", status="sourced",
               note="The 40-annuité test is assumed met at 60 by everyone who started before 20 (they have 40+ years by 60 by construction, bar career gaps: see B2)."),
    Assumption("P3", "'64 resumed': the 2023 path without the suspension", 64.0, "years",
               source="Attal/Retailleau positions, Capital 24 Sep 2026", status="sourced",
               note="Shown as the negative exposure (a saving) for symmetry; the Cour's asymmetry (M4) applies."),
    # --- behaviour
    Assumption("B1", "Share of a cohort bound by the age floor (others)", 0.45, "share", low=0.35, high=0.55,
               source="INSEE/FIPECO: at 62 in 2021 (AOD 62) 51% retired, 33% employed, 14% inactive, 3% unemployed; ≈11% had left before 62 (carrière longue)",
               status="inferred", note="People who liquidate at the AOD itself ≈ 40% of a cohort; the 42-annuité durée adds some. These are the people who move when the floor moves."),
    Assumption("B2", "Share bound among early starters", 0.80, "share", low=0.65, high=0.90,
               source="long careers have the durée by 60; DREES: 15% of men and 7% of women liquidate in the year of their 60th birthday", status="inferred"),
    Assumption("B3", "Share of a cohort that started work before 20", 0.35, "share", low=0.25, high=0.45,
               source="no DREES/CNAV series found for the 1965–75 cohorts; Terra Nova (13 Oct 2026) 'concerne encore tellement de monde sur les dernières cohortes des années 1960'; Montaigne 2024 low case (early starters only) €31.5bn of €34.7bn",
               status="missing", note="The single most consequential missing number. Needs the DREES EIC age at first validated quarter by cohort."),
    Assumption("B4", "Of which already eligible to carrière longue under current rules", 0.17, "share of cohort",
               source="CNAV rapport statistique 2024: 114k RACL departures of 658k new retirees (17%); 1 man in 4, 1 woman in 10", status="sourced",
               note="These leave at AOD − 2 already; '62 for all' does not move them, '60' moves them by AOD − 2 − 60 (0.75 → 2 years as the AOD rises)."),
    Assumption("B5", "Status of the bound before they retire: employed / unemployed / inactive-sick-invalid", (0.65, 0.07, 0.28), "shares",
               low=(0.55, 0.10, 0.35), high=(0.75, 0.05, 0.20),
               source="FIPECO on INSEE 2021: among the non-retired at 62, 66% employed, 6% unemployed, 28% inactive", status="inferred",
               note="The bound are likelier to be in work than the average non-retired (those who wait for the full rate are employed); the high case reflects that."),
    # --- unit costs (2024 prices)
    Assumption("U1", "Gross pension at liquidation", 1600.0, "EUR a month", low=1500.0, high=1700.0,
               source="DREES, Les retraités et les retraites 2025: new retirees 2023, residents, €1,557 gross droit direct; +2.4% to 2024", status="sourced",
               note="All compulsory schemes incl. Agirc-Arrco (in S.13). Survivors' pensions excluded."),
    Assumption("U2", "Early starters' pension relative to the average", 0.95, "ratio", low=0.85, high=1.05,
               source="none", status="missing", note="Long careers at lower wages: full rate but lower SAM. Direction unknown within ±10%."),
    Assumption("U3", "Gross wage of the bound who are employed", 36700.0, "EUR a year", low=33000.0, high=40000.0,
               source="INSEE 2024: €3,602 gross a month per full-time equivalent, private sector; × 0.85 for part-time at 60–63 (declared)", status="inferred"),
    Assumption("U4", "Actual social contributions (D.611 + D.613) as a share of gross wage", 0.50, "share", low=0.45, high=0.55,
               source="employer ≈ 39% after the réduction générale at 1.5 SMIC, employee 11.3% (CSG/CRDS excluded: a tax)", status="inferred"),
    Assumption("U5", "Taxes on income (CSG/CRDS + IR) on wages / pensions / unemployment benefit", (0.155, 0.11, 0.08), "shares",
               source="CSG/CRDS 9.7% on 98.25% of the wage + IR ≈ 6%; pensions CSG at the average effective 7% (reduced rates) + CRDS/CASA 0.8% + IR ≈ 3%; ARE 6.2% + IR", status="inferred"),
    Assumption("U6", "Unemployment benefit (ARE) of the bound who are unemployed", 16000.0, "EUR a year",
               source="Unédic average ARE ≈ €1,300–1,350 gross a month", status="inferred"),
    Assumption("U7", "Other benefits (invalidity, sickness, AT-MP, minima) per cohort-person-year", 2250.0, "EUR, 2019 prices",
               source="DREES for the COR, 27 Jan 2022: a two-year rise in the AOD = +€3.6bn (0.14% GDP) in 2019 on ≈1.6M cohort-person-years; invalidity 1.8bn, minima 0.83bn", status="sourced",
               note="Applied to the whole cohort's exposure (it embeds the share concerned). Unemployment insurance and prime d'activité are not in it (GF10_5 is costed separately)."),
    Assumption("U8", "Indexation of unit costs", DEFLATOR, "a year", source="engine deflator (D-S18-001 rule 4)", status="declared",
               note="Pensions index on prices, wages on prices + productivity: a wage-pension gap of ~0.7% a year is ignored to 2040."),
    Assumption("U9", "Lower pension for life from an earlier liquidation", 0.0, "EUR", source="COR 2025: the 2023 reform −0.2 pt GDP in 2030 but +0.2 pt in 2070",
               status="declared", note="Omitted to 2040; direction = less cost over time, reversing after ~2050."),
    Assumption("U10", "Durée 43 → 42 annuités", 0.0, "EUR", source="RN programme", status="missing",
               note="Omitted. Would lower the effective age for people bound by the durée (not the floor). Direction = more cost; high case adds 10% to GF10_2."),
    # --- method 1: top-down
    Assumption("M1", "DG Trésor long-run effect of a two-year AOD rise, % GDP", {"GF10_2": -0.4, "R06": 0.1, "other_benefits": 0.2, "other_revenue": 0.6}, "% GDP",
               source="DG Trésor note to the COR, 27 Jan 2022, as tabulated by FIPECO (19 Oct 2022): pensions −0.4, pension contributions +0.1, other benefits +0.2, other compulsory levies +0.6, total +0.9 (≈€22bn 2022)", status="sourced",
               note="Read per cohort-year as half of each (2 cohort-years at steady state). Signs as a saving; the engine flips them for a cut."),
    Assumption("M2", "Time path of the public-balance effect (Mésange) and the OFCE alternative", {"5": 0.1, "10": 0.4, "15": 0.7, "20": 0.9, "ofce_10": 0.15}, "% GDP",
               source="same notes: Mésange 5/10/15/20 years; OFCE e-mod.fr 0.15 at 10 years, +110k jobs", status="sourced"),
    Assumption("M3", "Ramp of the second-round revenue channel (other_revenue) after exposure begins", {1: 0.15, 5: 0.45, 10: 0.75, 15: 1.0}, "share of long run",
               low={1: 0.05, 5: 0.2, 10: 0.4, 15: 0.5}, high={1: 0.3, 5: 0.7, 10: 1.0, 15: 1.0},
               source="M2 with the eight-year phase-in of the simulated reform stripped out (inferred); low ≈ OFCE", status="inferred",
               note="Spending channels follow exposure at once (people retire on the day); pension contributions too; only the GDP-type revenue lags."),
    Assumption("M4", "Cour des comptes: one year of AOD (63 vs 64) on the pension-system balance", 5.8, "EUR bn, 2035", low=5.8, high=8.4,
               source="Cour des comptes, 20 Feb 2025: 63 → +€5.8bn of spending in 2035; 65 → up to −€8.4bn", status="sourced",
               note="Asymmetric: a lower floor binds fewer people than a higher one. Deflated to each year at 2%."),
    Assumption("M5", "DREES/COR cost of the 2026 suspension", 1.8, "EUR bn a year, 2026–2032",
               source="COR June 2026, p.105 and Tableau 2.5 (DREES Trajectoire); government lettre rectificative €0.1bn 2026 / €1.4bn 2027", status="sourced",
               note="Used as a calibration: € per cohort-year = 1.8 / the suspension's own exposure computed here."),
    # --- method 3: published costings
    Assumption("M6", "Published costings", {"RN (Oct 2026)": (9.0, 2031, "p60", "pension"), "OFCE (2024)": (15.6, 2030, "repeal", "gg"),
                                             "CNAV (Nov 2024)": (16.0, 2032, "repeal", "pension"), "Zemmour (2024)": (21.0, 2030, "repeal", "gg"),
                                             "Montaigne (2024)": (34.7, 2030, "repeal60", "pension")}, "EUR bn a year",
               source="RN €9bn cruising, €1.9bn 2027 → €9.5bn 2031 (Terra Nova reading of the counter-budget); OFCE 'minimal cost of repeal' €9.5bn 2027, €15.6bn 2030; CNAV via AN amendments €16bn 2032; M. Zemmour €20–22bn 2030; Institut Montaigne €34.7bn 'à l'horizon 2027' for repeal + 60 with 40 annuités for pre-20 starters",
               status="sourced", note="Each is converted to € per cohort-year on the exposure of the measure it costs (repeal = 2023 path → 62), then re-applied to P1/P2. Montaigne's 2027 is read as a steady-state figure and placed at 2030."),
    # --- method 4: growth
    Assumption("G1", "GDP level effect per cohort-year of lower age, after 10 years", -0.35, "% of GDP", low=-0.15, high=-0.55,
               source="Mésange: +260k jobs for two cohort-years at 10 years → 130k per cohort-year ≈ 0.43% of employment × 0.8 relative productivity; OFCE +110k (−0.15%); Rexecode +1.1% GDP for the 2023 reform in 2030 (−0.55%)", status="inferred"),
    Assumption("G2", "Ramp of the GDP effect", 10, "years to full effect, linear", source="declared, from the M2 path", status="declared"),
    Assumption("G3", "Elasticity of R01, R02, R03, R04, R06 to GDP", 1.0, "ratio", source="declared", status="declared",
               note="Expenditure fixed in euros, so the ratios also move. Revenue shares of GDP from the 2024 strict file."),
    Assumption("G4", "GDP path for the ratios", "simulate.gdp_path(philippe_hung)", "EUR bn", source="engine reference scenario (0.5% real, 2% deflator)", status="declared"),
    # --- scope
    Assumption("X1", "Scope", "general government, S.13, all compulsory schemes", "", source="committee, 20 Oct 2026", status="declared",
               note="COFOG GF10_2 carries CNAV, the régimes spéciaux, the fonction publique and Agirc-Arrco; Agirc-Arrco follows the legal age with a lag (its own board) — assumed to follow."),
    Assumption("X2", "Horizon", f"{FIRST_YEAR}–{LAST_YEAR}", "years", status="declared"),
]
A = {a.id: a for a in ASSUMPTIONS}


def register() -> pd.DataFrame:
    rows = []
    for a in ASSUMPTIONS:
        rows.append({"id": a.id, "name": a.name, "value": _fmt(a.value), "unit": a.unit, "low": _fmt(a.low), "high": _fmt(a.high),
                     "status": a.status, "source": a.source, "note": a.note})
    return pd.DataFrame(rows)


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (tuple, list)):
        return " / ".join(_fmt(x) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_fmt(x)}" for k, x in v.items())
    return str(v)


# --------------------------------------------------------------------------- population
def population() -> pd.DataFrame:
    """Population by (year, age), persons; 2026 = 2025 aged one year (D1)."""
    p = pd.read_csv(POP_FILE)
    piv = p.pivot_table(index="year", columns="age", values="population")
    if 2026 not in piv.index and 2025 in piv.index:
        aged = piv.loc[2025].shift(1)
        aged.name = 2026
        piv = pd.concat([piv, aged.to_frame().T]).sort_index()
    return piv


def cohort_size(birth_year: int, pop: pd.DataFrame | None = None) -> float:
    """People of the cohort at age 60 (persons), from the year it turns 60 (D1)."""
    pop = population() if pop is None else pop
    y = birth_year + 60
    y = min(max(y, pop.index.min()), pop.index.max())
    age = 60 + (birth_year + 60 - y)
    return float(pop.loc[y, age])


# --------------------------------------------------------------------------- the law
def aod_current(by: int, bm: int) -> float:
    """Age of entitlement under the LFSS 2026 path (L1), years."""
    if by <= 1960 or (by == 1961 and bm <= 8):
        return 62.0
    if by == 1961:
        return 62.25
    return {1962: 62.5, 1963: 62.75, 1964: 62.75}.get(by, 62.75 if (by == 1965 and bm <= 3) else
            {1965: 63.0, 1966: 63.25, 1967: 63.5, 1968: 63.75}.get(by, 64.0))


def aod_reform(by: int, bm: int) -> float:
    """Age of entitlement under the 2023 law before the suspension (L2)."""
    if by <= 1960 or (by == 1961 and bm <= 8):
        return 62.0
    if by == 1961:
        return 62.25
    return {1962: 62.5, 1963: 62.75, 1964: 63.0, 1965: 63.25, 1966: 63.5, 1967: 63.75}.get(by, 64.0)


def aod_racl(base: float) -> float:
    return max(60.0, base - A["L3"].value)


# Groups of a cohort: (name, share-of-cohort callable, baseline age fn, policy age fn)
def groups(policy: str, v: dict) -> list[tuple[str, float, callable, callable]]:
    """The cohort split into the three groups and, per policy, the baseline and
    policy ages of each. Shares: others 1 − B3; early starters already on
    carrière longue B4; early starters not on it B3 − B4."""
    s_es, r = v["B3"], v["B4"]
    cur, ref = aod_current, aod_reform
    if policy == "p62":                       # 62 for all (P1)
        return [("others", 1 - s_es, cur, lambda by, bm: min(cur(by, bm), 62.0)),
                ("early_other", s_es - r, cur, lambda by, bm: min(cur(by, bm), 62.0)),
                ("early_racl", r, lambda by, bm: aod_racl(cur(by, bm)), lambda by, bm: aod_racl(cur(by, bm)))]
    if policy == "p60":                       # 62 for all, 60 for early starters (P2)
        return [("others", 1 - s_es, cur, lambda by, bm: min(cur(by, bm), 62.0)),
                ("early_other", s_es - r, cur, lambda by, bm: 60.0),
                ("early_racl", r, lambda by, bm: aod_racl(cur(by, bm)), lambda by, bm: 60.0)]
    if policy == "p64":                       # the 2023 path resumed (P3): negative exposure
        return [("others", 1 - s_es, cur, ref),
                ("early_other", s_es - r, cur, ref),
                ("early_racl", r, lambda by, bm: aod_racl(cur(by, bm)), lambda by, bm: aod_racl(ref(by, bm)))]
    if policy == "suspension":                # what the LFSS 2026 did: 2023 path → current path, from Sep 2026
        return [("others", 1 - s_es, ref, cur),
                ("early_other", s_es - r, ref, cur),
                ("early_racl", r, lambda by, bm: aod_racl(ref(by, bm)), lambda by, bm: aod_racl(cur(by, bm)))]
    if policy == "repeal":                    # the 2023 path → 62 for all (what OFCE / CNAV / Zemmour cost)
        return [("others", 1 - s_es, ref, lambda by, bm: 62.0),
                ("early_other", s_es - r, ref, lambda by, bm: 62.0),
                ("early_racl", r, lambda by, bm: aod_racl(ref(by, bm)), lambda by, bm: aod_racl(ref(by, bm)))]
    if policy == "repeal60":                  # the 2023 path → 62 for all, 60 for early starters (Montaigne 2024)
        return [("others", 1 - s_es, ref, lambda by, bm: 62.0),
                ("early_other", s_es - r, ref, lambda by, bm: 60.0),
                ("early_racl", r, lambda by, bm: aod_racl(ref(by, bm)), lambda by, bm: 60.0)]
    raise KeyError(policy)


POLICIES = {"p62": "62 for all", "p60": "62 for all, 60 for early starters", "p64": "64 resumed (2023 law)",
            "suspension": "the LFSS 2026 suspension", "repeal": "repeal of the 2023 law (64 → 62)",
            "repeal60": "repeal + 60 for early starters"}
START = {"suspension": "2026-09-01", "repeal": "2024-01-01", "repeal60": "2024-01-01"}


# --------------------------------------------------------------------------- exposure
def variant_values(variant: str = "central") -> dict:
    """Every assumption's value for a variant: central, low (less cost) or high (more cost)."""
    v = {}
    for a in ASSUMPTIONS:
        x = a.value
        if variant == "low" and a.low is not None:
            x = a.low
        elif variant == "high" and a.high is not None:
            x = a.high
        v[a.id] = x
    if variant == "low":                        # low = less cost: fewer early starters, fewer bound
        v["P0"] = A["P0"].low
    elif variant == "high":
        v["P0"] = A["P0"].high
    return v


def exposure(policy: str, variant: str = "central", start: str | None = None,
             first: int = FIRST_YEAR, last: int = LAST_YEAR) -> pd.DataFrame:
    return _exposure(policy, variant, start, first, last).copy()


@lru_cache(maxsize=256)
def _exposure(policy, variant, start, first, last) -> pd.DataFrame:
    """Person-years of extra retirement by year and group, whole-cohort basis
    (`cohort_person_years`) and after the bound shares (`bound_person_years`),
    plus the extra retirees at year end (`people_end_year`). Negative for a
    rise in the age. Month by month on birth months from 1960 to 1985."""
    v = variant_values(variant)
    start = pd.Timestamp(start or START.get(policy) or v["P0"])
    pop = population()
    m0 = (first - 2000) * 12                              # month index: months since Jan 2000
    months = np.arange(m0, (last + 1 - 2000) * 12)        # calendar months in the horizon
    out = []
    for name, share, base_fn, pol_fn in groups(policy, v):
        bound = v["B2"] if name.startswith("early") else v["B1"]
        for by in range(1960, 1986):
            n = cohort_size(by, pop) / 12 * share           # people in one birth month of this group
            for bm in range(1, 13):
                birth = (by - 2000) * 12 + (bm - 1) + 0.5     # mid-month
                rb = birth + base_fn(by, bm) * 12
                rp = birth + pol_fn(by, bm) * 12
                st = (start.year - 2000) * 12 + (start.month - 1)
                lo, hi = max(min(rb, rp), st), max(rb, rp)
                if hi <= lo:
                    continue
                sign = 1.0 if rp < rb else -1.0            # earlier retirement = positive exposure
                # fraction of each calendar month spent in the window [lo, hi)
                frac = np.clip(np.minimum(months + 1, hi) - np.maximum(months, lo), 0, 1)
                if frac.sum() == 0:
                    continue
                for y in range(first, last + 1):
                    sl = slice((y - first) * 12, (y - first + 1) * 12)
                    py = frac[sl].sum() / 12 * n * sign
                    if py != 0:
                        dec = months[sl][-1]
                        end = n * sign if (lo <= dec < hi) else 0.0
                        out.append((y, name, py, py * bound, end * bound))
    e = pd.DataFrame(out, columns=["year", "group", "cohort_person_years", "bound_person_years", "people_end_year"])
    e = e.groupby(["year", "group"], as_index=False).sum()
    e["policy"], e["variant"] = policy, variant
    return e


def exposure_total(policy: str, variant: str = "central", **kw) -> pd.Series:
    """Cohort-person-years by year, all groups (whole-cohort basis), indexed by year."""
    e = exposure(policy, variant, **kw)
    return e.groupby("year").cohort_person_years.sum().reindex(range(FIRST_YEAR, LAST_YEAR + 1), fill_value=0.0)


# --------------------------------------------------------------------------- helpers
def price_index(year: int, base: int = BASE_PRICE_YEAR) -> float:
    return (1 + DEFLATOR) ** (year - base)


def gdp(year: int) -> float:
    g = sim.gdp_path(sim.scenario(sim.REFERENCE))
    if year in g:
        return g[year]
    last = max(g)
    return g[last] * ((1 + sim.scenario(sim.REFERENCE).real_growth) * (1 + DEFLATOR)) ** (year - last)


def revenue_shares_2024() -> dict:
    """Revenue lines as a share of GDP, France 2024, strict file."""
    r = pd.read_csv(DELIV / "revenue_esa.csv", low_memory=False).query("iso3 == 'FRA' and variant == 'strict' and year == 2024")
    return {k: float(r.loc[r.line_code == k, "pct_gdp"].iloc[0]) / 100 for k in ["R01", "R02", "R03", "R04", "R06"]}


def _ramp(table: dict, t: float) -> float:
    """Piecewise-linear ramp from {years: share}; zero before the first key."""
    ks = sorted(table)
    if t <= 0:
        return 0.0
    if t <= ks[0]:
        return table[ks[0]] * t / ks[0]
    for a, b in zip(ks, ks[1:]):
        if t <= b:
            return table[a] + (table[b] - table[a]) * (t - a) / (b - a)
    return table[ks[-1]]


# --------------------------------------------------------------------------- method 2: bottom-up units
def bottom_up_units(variant: str = "central", year: int = BASE_PRICE_YEAR) -> pd.DataFrame:
    """EUR per person-year, by line and group, at `year` prices (method 2).
    Rows: line, group, eur_per_bound_person_year, eur_per_cohort_person_year."""
    v = variant_values(variant)
    idx = price_index(year)
    emp, unemp, inact = v["B5"]
    t_w, t_p, t_u = v["U5"]
    rows = []
    for name in ("others", "early_other", "early_racl"):
        bound = v["B2"] if name.startswith("early") else v["B1"]
        pension = v["U1"] * 12 * (v["U2"] if name.startswith("early") else 1.0) * idx
        wage = v["U3"] * idx
        are = v["U6"] * idx
        u = {"GF10_2": pension * (1.10 if (variant == "high" and name == "others") else 1.0),      # U10 in the high case
             "GF10_5": -unemp * are,
             "R06": -emp * wage * v["U4"],
             "R03": -emp * wage * t_w - unemp * are * t_u + pension * t_p,
             "R01": 0.0, "R02": 0.0, "R04": 0.0}
        for line, x in u.items():
            rows.append((line, name, x, x * bound))
        # other benefits: DREES per cohort-person-year (U7), 2019 prices → year
        ob = -v["U7"] * price_index(year, 2019)
        rows.append(("GF10_X", name, ob / bound, ob))
    return pd.DataFrame(rows, columns=["line_code", "group", "eur_per_bound_person_year", "eur_per_cohort_person_year"])


def _bottom_up_matrix(policy: str, variant: str) -> pd.DataFrame:
    e = exposure(policy, variant)
    rows = []
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        u = bottom_up_units(variant, y).set_index(["line_code", "group"]).eur_per_cohort_person_year
        ey = e[e.year == y].set_index("group").cohort_person_years
        for line in LINES:
            x = sum(u.get((line, g), 0.0) * ey.get(g, 0.0) for g in ey.index) / 1e9
            rows.append((y, line, x))
    return pd.DataFrame(rows, columns=["year", "line_code", "eur_bn"])


# --------------------------------------------------------------------------- method 1: top-down
def _split_other_revenue(x: float) -> dict:
    """The Trésor 'other compulsory levies' spread over the revenue lines by
    their 2024 weight (R03, R01, R02, R04; R06's non-pension part folded into R06)."""
    sh = revenue_shares_2024()
    w = {"R03": sh["R03"], "R01": sh["R01"], "R02": sh["R02"], "R04": sh["R04"], "R06": 0.35 * sh["R06"]}   # non-pension contributions ≈ 35% of R06
    tot = sum(w.values())
    return {k: x * v / tot for k, v in w.items()}


def _top_down_tresor(policy: str, variant: str) -> pd.DataFrame:
    """DG Trésor per cohort-year (half the two-year figures), spending at once,
    second-round revenue on the M3 ramp (method 1a)."""
    v = variant_values(variant)
    m1, ramp = A["M1"].value, v["M3"]
    E = exposure_total(policy, variant)
    first_exposed = next((y for y, x in E.items() if abs(x) > 1e-6), None)
    rows = []
    for y, ex in E.items():
        g = gdp(y)
        n_cohort = 850_000                                  # the Trésor figures are for whole cohorts of this size (2022)
        k = ex / n_cohort                                   # cohort-years
        t = (y - first_exposed + 1) if first_exposed else 0
        per = {"GF10_2": -m1["GF10_2"] / 2, "R06": -m1["R06"] / 2,                          # a cut: pensions up, contributions down
               "other_benefits": -m1["other_benefits"] / 2, "other_revenue": -m1["other_revenue"] / 2 * _ramp(ramp, t)}
        vals = {"GF10_2": per["GF10_2"], "R06": per["R06"],
                "GF10_X": per["other_benefits"] * 0.8, "GF10_5": per["other_benefits"] * 0.2}
        for line, x in _split_other_revenue(per["other_revenue"]).items():
            vals[line] = vals.get(line, 0.0) + x
        for line in LINES:
            rows.append((y, line, vals.get(line, 0.0) / 100 * g * k))
    return pd.DataFrame(rows, columns=["year", "line_code", "eur_bn"])


def pension_system_split(variant: str = "central") -> dict:
    """How a pension-system-only figure splits between GF10_2 and R06 (pension
    contributions), from the bottom-up units of the 'others' group."""
    u = bottom_up_units(variant).set_index(["line_code", "group"]).eur_per_cohort_person_year
    p, c = u[("GF10_2", "others")], -u[("R06", "others")] * 0.65          # 65% of contributions are pension contributions
    return {"GF10_2": p / (p + c), "R06": -c / (p + c)}


def _unit_matrix(policy: str, variant: str, eur_per_cohort_year: float, price_year: int, split: dict) -> pd.DataFrame:
    """A single € per cohort-year figure (at `price_year` prices) spread over
    lines by `split` and over years by exposure."""
    E = exposure_total(policy, variant)
    rows = []
    for y, ex in E.items():
        k = ex / 850_000
        tot = eur_per_cohort_year * price_index(y, price_year) * k
        for line in LINES:
            rows.append((y, line, tot * split.get(line, 0.0)))
    return pd.DataFrame(rows, columns=["year", "line_code", "eur_bn"])


def suspension_unit(variant: str = "central") -> dict:
    """€ bn per cohort-year implied by the DREES €1.8bn a year for the
    suspension (M5): 1.8 over the suspension's own average exposure 2027–2031."""
    E = exposure_total("suspension", variant)
    k = (E.loc[2027:2031] / 850_000).mean()
    return {"cohort_years_2027_2031_avg": float(k), "eur_bn_per_cohort_year": float(A["M5"].value / k) if k else float("nan")}


def published_units(variant: str = "central") -> pd.DataFrame:
    """Each published costing (M6) as € bn per cohort-year, on the exposure of
    the measure it costs in the year it quotes (method 3)."""
    rows = []
    for name, (bn, year, measure, scope) in A["M6"].value.items():
        E = exposure_total(measure, variant)
        k = E.get(year, np.nan) / 850_000
        rows.append({"source": name, "eur_bn": bn, "year": year, "measure": POLICIES[measure], "scope": scope,
                     "cohort_years": k, "eur_bn_per_cohort_year": bn / k if k else np.nan})
    c = A["M4"]
    rows.append({"source": "Cour des comptes (2025)", "eur_bn": c.value, "year": 2035, "measure": "one year of AOD (63 vs 64)", "scope": "pension",
                 "cohort_years": 1.0, "eur_bn_per_cohort_year": c.value})
    s = suspension_unit(variant)
    rows.append({"source": "COR/DREES suspension (2026)", "eur_bn": A["M5"].value, "year": 2029, "measure": POLICIES["suspension"], "scope": "pension",
                 "cohort_years": s["cohort_years_2027_2031_avg"], "eur_bn_per_cohort_year": s["eur_bn_per_cohort_year"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- method 4: growth
def gdp_channel(policy: str, variant: str = "central") -> pd.DataFrame:
    """GDP level effect (% and EUR bn) and the revenue it moves, by year (method 4)."""
    v = variant_values(variant)
    E = exposure_total(policy, variant)
    first_exposed = next((y for y, x in E.items() if abs(x) > 1e-6), None)
    sh = revenue_shares_2024()
    rows = []
    for y, ex in E.items():
        k = ex / 850_000
        t = (y - first_exposed + 1) if first_exposed else 0
        dg = v["G1"] * k * min(1.0, t / v["G2"]) if first_exposed else 0.0      # % of GDP
        g = gdp(y)
        rows.append({"year": y, "gdp_pct": dg, "gdp_bn": dg / 100 * g,
                     **{f"{line}_bn": dg / 100 * g * sh[line] * v["G3"] for line in ("R01", "R02", "R03", "R04", "R06")}})
    return pd.DataFrame(rows)


def growth_haircut(policy: str, variant: str = "central") -> dict:
    """Year-on-year change of the GDP level effect: the real-growth
    adjustment the engine would carry (pp a year, negative = slower)."""
    c = gdp_channel(policy, variant).set_index("year").gdp_pct
    return {int(y): float(x) for y, x in c.diff().fillna(c).items()}


# --------------------------------------------------------------------------- the matrix
METHODS = {
    "m1_tresor": "1a · top-down: DG Trésor / Mésange",
    "m1_cour": "1b · top-down: Cour des comptes one-year",
    "m1_cor": "1c · top-down: COR/DREES suspension unit",
    "m2_bottom_up": "2 · bottom-up cohort arithmetic",
    "m3_published": "3 · published costings (median; min/max in the variants)",
    "m4_growth": "4 · bottom-up spending + GDP channel revenue",
}


def matrix(policy: str = "p62", variant: str = "central") -> pd.DataFrame:
    """Impact by method × line × year, EUR bn and % GDP, for one policy and
    variant. Positive expenditure = more spending; positive revenue = more
    revenue; `balance_bn` = revenue − expenditure effect."""
    frames = []
    bu = _bottom_up_matrix(policy, variant); bu["method"] = "m2_bottom_up"; frames.append(bu)
    td = _top_down_tresor(policy, variant); td["method"] = "m1_tresor"; frames.append(td)
    split = pension_system_split(variant)
    cour = variant_values(variant)["M4"]                    # 5.8 (63 vs 64); the high case takes the 65 figure, 8.4
    cm = _unit_matrix(policy, variant, cour, 2035, split); cm["method"] = "m1_cour"; frames.append(cm)
    su = suspension_unit(variant)["eur_bn_per_cohort_year"]
    sm = _unit_matrix(policy, variant, su, 2029, split); sm["method"] = "m1_cor"; frames.append(sm)
    pu = published_units(variant)
    pub = pu[pu.source.str.contains("OFCE|Zemmour|Montaigne|CNAV|RN")]
    # general-government costings spread like the bottom-up lines; pension-only ones over GF10_2/R06
    bu_shares = _line_shares(bu)
    stat = {"low": "min", "central": "median", "high": "max"}[variant]
    unit3 = getattr(pub.eur_bn_per_cohort_year, stat)()
    pm = _unit_matrix(policy, variant, unit3, 2030, bu_shares); pm["method"] = "m3_published"; frames.append(pm)
    gc = gdp_channel(policy, variant).set_index("year")
    g4 = bu.copy()
    for line in ("R01", "R02", "R03", "R04", "R06"):
        g4.loc[g4.line_code == line, "eur_bn"] = g4.loc[g4.line_code == line, "year"].map(gc[f"{line}_bn"]).values
    g4["method"] = "m4_growth"; frames.append(g4)
    m = pd.concat(frames, ignore_index=True)
    m["pct_gdp"] = [100 * x / gdp(y) for x, y in zip(m.eur_bn, m.year)]
    m["policy"], m["variant"] = policy, variant
    m["side"] = np.where(m.line_code.isin(EXPENDITURE), "expenditure", "revenue")
    m["balance_bn"] = np.where(m.side == "expenditure", -m.eur_bn, m.eur_bn)
    return m[["policy", "variant", "method", "year", "line_code", "side", "eur_bn", "pct_gdp", "balance_bn"]]


def _line_shares(bu: pd.DataFrame) -> dict:
    """Shares of the bottom-up balance effect by line (2030), for spreading a
    general-government total over lines."""
    b = bu[bu.year == 2030].set_index("line_code").eur_bn
    cost = sum((b[k] if k in EXPENDITURE else -b[k]) for k in b.index)      # the balance worsening, positive
    return {k: float(b[k] / cost) for k in b.index}


def units_table(variant: str = "central", year: int = 2030) -> pd.DataFrame:
    """EUR bn per cohort-year by method and line at `year` prices and GDP: the
    plan-invariant unit the brief tabulates (the matrix divided by the exposure)."""
    m = matrix("p62", variant)
    k = exposure_total("p62", variant)[year] / 850_000
    t = m[m.year == year].pivot_table(index="method", columns="line_code", values="eur_bn")[LINES] / k
    t["total_cost"] = sum((t[l] if l in EXPENDITURE else -t[l]) for l in LINES)
    t.index = t.index.map(METHODS)
    return t


def matrix_all(policies=("p62", "p60", "p64"), variants=("low", "central", "high")) -> pd.DataFrame:
    return pd.concat([matrix(p, v) for p in policies for v in variants], ignore_index=True)


def balance_overlay(policy: str = "p62", method: str = "m2_bottom_up", variant: str = "central") -> dict:
    """Change of the primary balance by year, EUR bn (negative = worse): what
    the scenario engine would add to a declared path (`Scenario.pb_change_bn`
    is year-on-year, so take differences there)."""
    m = matrix(policy, variant)
    s = m[m.method == method].groupby("year").balance_bn.sum()
    return {int(y): float(x) for y, x in s.items()}


def summary(policy: str = "p62", variant: str = "central", years=(2028, 2029, 2030, 2032, 2035, 2040)) -> pd.DataFrame:
    """Balance effect by method and year, EUR bn, for the brief's table."""
    m = matrix(policy, variant)
    t = m.groupby(["method", "year"]).balance_bn.sum().unstack("year")[list(years)]
    t.index = t.index.map(METHODS)
    return t


if __name__ == "__main__":       # pragma: no cover
    pd.set_option("display.width", 200)
    print(register()[["id", "name", "value", "status"]].to_string())
    for p in ("suspension", "p62", "p60", "p64"):
        E = exposure(p)
        print(p, E.groupby("year")[["cohort_person_years", "bound_person_years", "people_end_year"]].sum().loc[2026:2036].round(0).to_string())
    print(suspension_unit())
    print(published_units().round(2).to_string())
    print(summary("p62").round(1).to_string())
    print(summary("p60").round(1).to_string())
