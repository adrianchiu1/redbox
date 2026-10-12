"""Yield-path simulation through the register onto the interest line (France).

`DEBT_KICKOFF.md` §1 closes with "out of scope now, but shaped for:
simulating alternative yield-curve paths through the register onto the
interest line". This module is that simulation, for France, built for the
AFT briefing of September 2026 (D-S12-001).

It reads only the flat files in `deliverables/` — the per-security register
at the AFT's latest snapshot, the reference rates, the ledger and the strict
matrix — and rolls the stock forward year by year under a **declared**
scenario: a primary-balance path in EUR bn, real growth, an OAT–Bund spread
path and a Bund curve (the issuance mix and the bill stock are common). Every parameter is a number in
`BASELINE` or in one of the `SCENARIOS`; nothing is estimated, fitted or
calibrated silently. Where a calibration is used (the share of the
general-government deficit the État's negotiable debt absorbs, the wedge
between the register's interest and `GF01_7`) it is computed from the
deliverables and printed by `calibration()`.

What it is: an arithmetic of the existing coupons rolling off and being
replaced at scenario yields, with the deficit feeding back through the
interest bill (the wrong-way loop the briefing is about). What it is not: a
forecast of yields, growth or politics. The scenarios are Redbox's
statistical benchmark (D-S18-002) and the five 2027 configurations the
committee asked for (Le Pen / Philippe × majority / hung, and Mélenchon;
D-S18-001), each stated in the `SCENARIOS` table so it can be
argued with line by line.

Conventions: calendar years; EUR bn unless a name says otherwise; interest
on the accrual basis (D.41 concept: coupons pro rata, bill discount
accreted, indexation uplift accrued as it arises — DD3). The identities the
engine keeps every year, and `tests/debt/test_simulate.py` checks:

    deficit      = −primary balance + GG interest − interest receivable
    GG interest  = register interest + wedge (a share of GDP)
    debt_t       = debt_{t−1} + deficit_t                 (no stock-flow adjustment)
    MLT gross    = redemptions + 0.90 × deficit − uplift accrual − Δbills
    Δ negotiable stock = 0.90 × deficit                   (from 2027)
    nominal GDP  = ledger 2025 level × AMECO growth to 2027 × (1+g)(1+π) after

What feeds back into what: the interest bill enters the deficit, the deficit
the issuance, the issuance the next year's interest — that is the only
endogenous channel. The spread path, real growth and the primary-balance
changes are declared per scenario and do not respond to the debt ratio,
to each other or to the interest bill (the debt-ratio spread feedback
exists as a parameter and is set to zero, D-S18-001). In particular a
scenario's primary balance in EUR does not move with its growth: there are
no automatic stabilisers (see the briefing's assumptions table).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = next(p for p in [Path(__file__).resolve(), *Path(__file__).resolve().parents]
            if (p / "deliverables" / "debt_securities.csv").exists())
DELIV = ROOT / "deliverables"

ISO = "FRA"
SNAPSHOT = "2026-09-10"          # the AFT's latest office snapshot in the register
FIRST_YEAR, LAST_YEAR = 2026, 2035

BUCKET_TENOR = {                 # residual maturity at issue, years, midpoint of the DD7 bucket
    "0-1": 0.5, "1-2": 1.5, "2-3": 2.5, "3-5": 4.0, "5-7": 6.0, "7-10": 8.5,
    "10-15": 12.5, "15-20": 17.5, "20-30": 25.0, "30+": 35.0,
}


# --------------------------------------------------------------------------
# Declared assumptions
# --------------------------------------------------------------------------

@dataclass
class Baseline:
    """Everything the scenarios share. All numbers are declared, not fitted."""

    # Nominal GDP, EUR bn. The level is the ledger's 2025 outturn (Eurostat;
    # the denominator of INSEE's 115.6% debt ratio). 2026–2027 chain the EC
    # AMECO spring 2026 growth rates onto it — growth rates, never AMECO's
    # levels (D-S4-002, as `forecast.levels`): AMECO's own 2025 is 2991.1, 0.4%
    # above the ledger, so taking its 2026 level outright booked that 0.4% as
    # 2026 growth and took half a point off every debt ratio. From 2028 each
    # scenario declares its own real growth; the deflator is common.
    gdp: dict = field(default_factory=lambda: {2025: 2979.1})
    gdp_ameco: dict = field(default_factory=lambda: {2025: 2991.1, 2026: 3055.8, 2027: 3150.7})
    deflator_after: float = 0.020

    # Primary balance, % of GDP (negative = primary deficit), common to every
    # scenario to 2027: the 2027 budget is voted before the election. 2025:
    # NLB −5.1 less net interest ≈ 2.0 → −3.1. From 2028 each scenario moves
    # the primary balance by a declared number of EUR bn a year (outturn,
    # year on year), so growth acts on the ratio through the denominator only.
    primary_balance: dict = field(default_factory=lambda: {2025: -3.1, 2026: -2.7, 2027: -2.5})

    # Interest receivable (R07), % of GDP, held constant.
    interest_receivable_pct: float = 0.2

    # Maastricht debt at end-2025 (INSEE, 27 March 2026: 115.6% of GDP).
    debt_2025_pct: float = 115.6

    # Bund curve, % — flat through the horizon (declared). The 10-year is held
    # at 3.50% (DE_LT10 averaged 3.47% in September 2026); 2y/5y/30y keep the
    # previous vintage's slope to the 10-year, the 3-month stays at the ECB-
    # anchored 2.50% (EA 3m money-market 2.51% Aug 2026).
    bund_curve: dict = field(default_factory=lambda: {
        0.25: 2.50, 2: 3.00, 5: 3.25, 10: 3.50, 30: 3.85})

    # OAT–Bund spread term structure as a fraction of the 10y spread.
    spread_shape: dict = field(default_factory=lambda: {
        0.25: 0.15, 2: 0.45, 5: 0.75, 10: 1.00, 30: 1.15})

    # The 10y spread today (Bloomberg, 11 October 2026), used for the rest of
    # 2026 in every scenario and as the last point of the actual line. The
    # bundle's monthly OECD series ends in September 2026 (about 100 bp).
    spread_today_bp: float = 135.0
    spread_today_date: str = "2026-10-11"

    # Inflation for indexation uplift (FR CPI ex-tobacco / EA HICP ex-tobacco).
    # New linker issuance is not modelled separately: with breakeven =
    # inflation a linker's real coupon plus uplift accrual equals the nominal
    # yield, so every new tranche is booked at the nominal yield.
    inflation: float = 0.020

    # Share of the general-government deficit financed by the État's
    # negotiable debt: Δ(F.31+F.32) over −NLB summed over 2015–2025 is 0.90
    # (calibration()); local government, social security and CADES fund the
    # rest, and the État's own deficit is below the general-government one.
    deficit_to_net_issuance: float = 0.90

    # 2026 is a bridge year: the register already carries the issuance to
    # 10 September, so only the remainder of the year is financed here, and
    # the 2026 interest bill is taken from the strict matrix (EC AMECO,
    # 77.7 EUR bn) rather than from a partial-year roll.
    gg_interest_2026_bn: float = 77.66

    # Wedge GF01_7 − register interest, % of GDP (local government and social
    # security interest, non-negotiable debt, consolidation), held constant
    # as a share of GDP. Calibrated on the engine's own concept of register
    # interest — coupon accrued pro rata, uplift accrued, bill discount
    # accreted: 2025 65.2 − 55.8 = 9.5 EUR bn = 0.32% of GDP
    # (`calibration()["wedge_2025_engine_concept_pct_gdp"]`). The first
    # version took the register's CASH total (55.2, wedge 0.34) against an
    # accrual roll; the register's own accrued total (56.6, wedge 0.29) is not
    # used either, because its premium/discount amortisation component counts
    # the bill discount a second time (see `calibration()` and the note in
    # DECISIONS D-S18-005). What the roll still omits: the amortisation of
    # premiums/discounts on the bonds in the snapshot stock, which nets to
    # about −1.5 EUR bn a year in 2026 on the register's figures.
    gg_wedge_pct: float = 0.32

    # Feedback: spread rises with the debt ratio's deviation from the
    # reference scenario, bp per pp of GDP. Off (D-S18-001): each scenario's
    # spread path is declared in full, so the engine does not move it.
    spread_feedback_bp_per_pp: float = 0.0

    # Bill (BTF) stock, EUR bn, held flat in every scenario; the issuance mix
    # is the AFT's 2025 mix in every scenario.
    btf_stock: float = 215.0


@dataclass
class Scenario:
    name: str
    label: str
    # 10y OAT–Bund spread, bp, annual average: the 2027 level, a straight-line
    # fade to the 2029 level, flat thereafter (2026 is today's level).
    spread_2027_bp: float
    spread_2029_bp: float
    # Year-on-year improvement of the primary balance, EUR bn (negative = a
    # loosening), 2028–2031, then `consolidation_after_bn` a year.
    consolidation_bn: float
    real_growth: float
    consolidation_after_bn: float = 5.0
    consolidation_until: int = 2031
    note: str = ""
    # Optional overrides, used by decompose_gap to switch one lever at a time.
    spread_bp: dict | None = None
    pb_change_bn: dict | None = None
    # Alternative to the EUR bn rule: year-on-year change of the primary
    # balance in pp of GDP (missing years = no change in the ratio).
    pb_change_pp: dict | None = None

    def spread_path(self, base: "Baseline" = None) -> dict:
        if self.spread_bp is not None:
            return self.spread_bp
        base = base or BASELINE
        return {2026: base.spread_today_bp, 2027: self.spread_2027_bp,
                2028: (self.spread_2027_bp + self.spread_2029_bp) / 2, 2029: self.spread_2029_bp}

    def pb_changes(self) -> dict:
        """Year-on-year change of the primary balance, EUR bn (the EUR bn rule
        only; a pp-of-GDP scenario is resolved in primary_balance_path)."""
        if self.pb_change_bn is not None:
            return self.pb_change_bn
        return {y: (self.consolidation_bn if y <= self.consolidation_until else self.consolidation_after_bn)
                for y in range(2028, LAST_YEAR + 1)}


BASELINE = Baseline()


def benchmark_pb_changes(first: int = 2028) -> dict:
    """Year-on-year change of the primary balance, pp of GDP, in the Redbox
    statistical benchmark (`benchmark_balance.csv`, D-S11-002): primary
    balance = benchmark NLB + benchmark GF01_7 interest − interest receivable.
    The benchmark is anchored on 2024, so its level is not used, only its
    changes from `first` to its last year (2031)."""
    b = pd.read_csv(DELIV / "benchmark_balance.csv", low_memory=False).query("iso3 == @ISO")
    nlb = b[b.kind == "balance"].set_index("year").pct_gdp
    gi = b[(b.kind == "line") & (b.line_code == "GF01_7")].set_index("year").pct_gdp
    pb = (nlb + gi - BASELINE.interest_receivable_pct).dropna()
    d = pb.diff()
    return {int(y): float(v) for y, v in d.items() if y >= first}


# The statistical benchmark plus the five 2027 configurations (committee,
# 2026-10-11; D-S18-001, D-S18-002). The fiscal
# paths assume slippage against what each camp promises: the RN's
# counter-budget of 6 October 2026 promises EUR 140bn of net savings by 2032
# (against 2026) and a deficit below 3% in 2030; the Le Pen-majority path
# delivers EUR 25bn a year from 2028, about EUR 105bn by 2032.
SCENARIOS = [
    Scenario(
        "statistical", "Statistical benchmark", 175, 150, 0.0, 0.005,
        pb_change_pp=benchmark_pb_changes(),
        note="Redbox's statistics-based forecast of the primary balance (benchmark_balance.csv): "
             "its year-on-year changes 2028–2031, flat as a share of GDP after; spread and "
             "growth as Philippe, hung."),
    Scenario(
        "philippe_majority", "Philippe, majority", 150, 125, 10.0, 0.010,
        note="Pension age and spending review delivered in part: primary balance €10bn a year "
             "better to 2031; growth 1%; spread 150 → 125 bp."),
    Scenario(
        "philippe_hung", "Philippe, hung Assembly", 175, 150, 2.0, 0.005,
        note="The status quo: budgets by 49.3 with concessions, €2bn a year of consolidation; "
             "growth 0.5%; spread 175 → 150 bp."),
    Scenario(
        "lepen_majority", "Le Pen, majority", 190, 125, 25.0, 0.000,
        note="RN counter-budget enacted with slippage: €25bn a year against the €140bn by 2032 "
             "promised; growth 0% as the cuts bite; spread spikes to 190 bp, then 125 bp."),
    Scenario(
        "lepen_hung", "Le Pen, hung Assembly", 175, 125, 15.0, 0.005,
        note="RN president, no majority: part of the counter-budget passes, €15bn a year; "
             "growth 0.5%; spread 175 → 125 bp."),
    Scenario(
        "melenchon", "Mélenchon", 250, 300, -10.0, 0.000,
        note="LFI programme: spending ahead of revenue, primary balance €10bn a year worse to "
             "2031; growth 0%; spread 250 → 300 bp."),
]

# The status quo: the reference for decompose_gap and the spread feedback.
REFERENCE = "philippe_hung"


def scenario(name: str) -> Scenario:
    return next(sc for sc in SCENARIOS if sc.name == name)


def gdp_path(sc: Scenario, base: Baseline = BASELINE) -> dict:
    """Nominal GDP, EUR bn, by year: the ledger level, AMECO growth chained
    on to 2027 (common), then (1+g)(1+π)."""
    gdp = dict(base.gdp)
    for y in sorted(base.gdp_ameco):
        if y > max(gdp) and (y - 1) in base.gdp_ameco:
            gdp[y] = gdp[y - 1] * base.gdp_ameco[y] / base.gdp_ameco[y - 1]
    for y in range(max(gdp) + 1, LAST_YEAR + 1):
        gdp[y] = gdp[y - 1] * (1 + sc.real_growth) * (1 + base.deflator_after)
    return gdp


def primary_balance_path(sc: Scenario, base: Baseline = BASELINE) -> dict:
    """Primary balance, EUR bn, by year: common % of GDP to 2027, then the
    previous year's balance plus the scenario's declared change."""
    gdp = gdp_path(sc, base)
    pb = {y: v / 100 * gdp[y] for y, v in base.primary_balance.items()}
    if sc.pb_change_pp is not None:
        for y in range(max(pb) + 1, LAST_YEAR + 1):
            pb[y] = (pb[y - 1] / gdp[y - 1] + sc.pb_change_pp.get(y, 0.0) / 100) * gdp[y]
        return pb
    ch = sc.pb_changes()
    for y in range(max(pb) + 1, LAST_YEAR + 1):
        pb[y] = pb[y - 1] + ch.get(y, 0.0)
    return pb


# --------------------------------------------------------------------------
# Register
# --------------------------------------------------------------------------

def _load(name):
    return pd.read_csv(DELIV / f"{name}.csv", low_memory=False)


def load_register(snapshot: str = SNAPSHOT) -> pd.DataFrame:
    """Every French security outstanding at the snapshot with its terms."""
    sec = _load("debt_securities").query("iso3 == @ISO")
    pos = _load("debt_positions").query("iso3 == @ISO and as_of == @snapshot")
    reg = pos.merge(sec[["security_id", "name", "instrument_class", "sub_type",
                         "coupon_pct", "maturity_date", "first_issue_date"]],
                    on="security_id")
    reg = reg[reg.nominal_lcu_mn > 0].copy()
    reg["maturity"] = pd.to_datetime(reg.maturity_date)
    reg["nominal"] = reg.nominal_lcu_mn / 1000.0                       # EUR bn
    reg["uplift_ratio"] = np.where(reg.instrument_class == "inflation_linked",
                                   reg.nominal_uplifted_lcu_mn / reg.nominal_lcu_mn, 1.0)
    reg["coupon"] = reg.coupon_pct.fillna(0.0) / 100.0
    return reg[["security_id", "name", "instrument_class", "coupon", "maturity",
                "nominal", "uplift_ratio"]].reset_index(drop=True)


def issuance_mix(year: int = 2025) -> pd.Series:
    """Share of medium/long-term gross issuance by residual-maturity bucket
    in `year`, fixed and linkers together (the AFT's own choice of tenors).
    The tenor used for each bucket is the AFT's own nominal-weighted residual
    maturity at issue in that bucket and year (`weighted_residual_years_at_issue`),
    stored in the Series' attrs, not the bucket midpoint."""
    b = _load("debt_issuance_by_bucket").query(
        "iso3 == @ISO and year == @year and instrument_class != 'bill'")
    b = b.assign(w=b.gross_nominal_lcu_mn * b.weighted_residual_years_at_issue)
    g = b.groupby("bucket").agg(nominal=("gross_nominal_lcu_mn", "sum"), w=("w", "sum"))
    g = g.reindex([k for k in BUCKET_TENOR if k in g.index])
    s = g.nominal / g.nominal.sum()
    s.attrs["tenor"] = (g.w / g.nominal).to_dict()
    return s


def calibration() -> dict:
    """The two calibrations the engine relies on, computed from the bundle."""
    agg = _load("debt_class_aggregates").query("iso3 == @ISO and measure == 'net_issuance'")
    ni = agg[agg.sub_type.isin(["f31_short_term_securities", "f32_long_term_securities"])]
    ni = ni.groupby("year").value_lcu_mn.sum()
    led = _load("balance_ledger").query("iso3 == @ISO and variant == 'strict'").set_index("year")
    yrs = [y for y in range(2015, 2026) if y in ni.index and y in led.index]
    ratio = ni.loc[yrs].sum() / (-led.nlb_lcu_mn.loc[yrs]).sum()
    ibs = _load("debt_interest_by_security").query("iso3 == @ISO")
    sec = _load("debt_securities").query("iso3 == @ISO")
    by = ibs.groupby(["year", "basis"])[["coupon_lcu_mn", "uplift_lcu_mn", "discount_lcu_mn",
                                         "premium_discount_amort_lcu_mn", "total_lcu_mn"]].sum() / 1000
    cash = by.loc[(2025, "cash")]
    acc = by.loc[(2025, "accrued")]
    # what run_scenario computes for the register: coupon pro rata, uplift
    # accrued, bill discount accreted — the accrued basis without the
    # premium/discount amortisation (§7.7), which the roll does not carry
    engine_concept = float(acc.coupon_lcu_mn + acc.uplift_lcu_mn + acc.discount_lcu_mn)
    strict = pd.read_csv(DELIV / "strict_FRA.csv").set_index("year")
    gf = strict["GF01_7 - Public debt transactions (interest)"] / 1000
    g25 = BASELINE.gdp[2025]
    return {"net_issuance_over_deficit_2015_2025": round(float(ratio), 3),
            "register_cash_interest_2025_bn": round(float(cash.total_lcu_mn), 1),
            "register_accrued_interest_2025_bn": round(float(acc.total_lcu_mn), 1),
            "register_engine_concept_2025_bn": round(engine_concept, 1),
            "gf01_7_2025_bn": round(float(gf.loc[2025]), 1),
            "wedge_2025_bn": round(float(gf.loc[2025] - cash.total_lcu_mn), 1),
            "wedge_2025_pct_gdp": round(100 * float(gf.loc[2025] - cash.total_lcu_mn) / g25, 2),
            "wedge_2025_accrued_pct_gdp": round(100 * float(gf.loc[2025] - acc.total_lcu_mn) / g25, 2),
            "wedge_2025_engine_concept_pct_gdp": round(100 * (float(gf.loc[2025]) - engine_concept) / g25, 2),
            # D.41 the roll omits: the premium/discount amortisation on the
            # BONDS in the stock (positive = premium, reduces interest). Bills
            # are left out: the published file amortises their discount on top
            # of accreting it (fixed in interest.py, D-S18-005; the file is
            # regenerated by `ggfiscal debt build`).
            "bond_premium_amortisation_2026_bn": round(float(
                ibs.merge(sec[["security_id", "instrument_class"]], on="security_id")
                .query("year == 2026 and basis == 'accrued' and instrument_class != 'bill'")
                .premium_discount_amort_lcu_mn.sum()) / 1000, 1)}


# --------------------------------------------------------------------------
# Curves
# --------------------------------------------------------------------------

def _interp(points: dict, tenor: float) -> float:
    xs = np.array(sorted(points)); ys = np.array([points[x] for x in xs])
    return float(np.interp(np.log(max(tenor, 0.25)), np.log(xs), ys))


def oat_yield(tenor: float, spread10_bp: float, base: Baseline = BASELINE) -> float:
    """Nominal OAT yield (%) at `tenor` years for a given 10y spread."""
    return _interp(base.bund_curve, tenor) + _interp(base.spread_shape, tenor) * spread10_bp / 100


def _path(d: dict, year: int, default=None):
    """Value for `year` from a sparse {year: value} dict: nearest earlier year."""
    ks = [k for k in d if k <= year]
    if not ks:
        return default if default is not None else d[min(d)]
    return d[max(ks)]


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

def _year_fraction_outstanding(maturity: pd.Timestamp, year: int) -> float:
    """Fraction of calendar `year` a bullet maturing on `maturity` is outstanding."""
    start = pd.Timestamp(year=year, month=1, day=1)
    end = pd.Timestamp(year=year + 1, month=1, day=1)
    if maturity <= start:
        return 0.0
    if maturity >= end:
        return 1.0
    return (maturity - start).days / (end - start).days


def run_scenario(sc: Scenario, base: Baseline = BASELINE, register: pd.DataFrame | None = None,
                 mix: pd.Series | None = None, feedback: bool = True,
                 baseline_debt_pct: pd.Series | None = None,
                 financing_interest: pd.Series | None = None) -> pd.DataFrame:
    """Roll the register forward under one scenario. One row per year.

    `financing_interest` (EUR bn by year, general-government basis) is a
    diagnostic: when given, the issuance of each year from 2027 is sized on
    that interest bill instead of the scenario's own, while the deficit, the
    debt and the interest reported stay the scenario's. `loop_size` uses it
    with the status quo's bill to measure the arithmetic loop — the interest
    the extra interest itself ends up costing — directly.
    """
    reg = (register if register is not None else load_register()).copy()
    mix = mix if mix is not None else issuance_mix()
    tenor_of = {b: mix.attrs.get("tenor", {}).get(b, BUCKET_TENOR[b]) for b in mix.index}
    tenors = np.array([tenor_of[b] for b in mix.index])
    w = mix.values / mix.values.sum()
    mlt_avg_maturity_at_issue = float((w * tenors).sum())

    # Existing stock split: bills are re-rolled as a stock, bonds tranche by tranche.
    bonds = reg[reg.instrument_class != "bill"].copy()
    bonds["issue_year"] = 0
    btf_2025 = float(reg.loc[reg.instrument_class == "bill", "nominal"].sum())
    new = []                                   # tranches issued in the simulation
    debt = base.debt_2025_pct / 100 * base.gdp[2025]
    gdp_of, pb_of, spread_of = gdp_path(sc, base), primary_balance_path(sc, base), sc.spread_path(base)
    rows = []
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        gdp = gdp_of[year]
        pb = 100 * pb_of[year] / gdp
        spread = float(_path(spread_of, year))
        if feedback and baseline_debt_pct is not None and year > FIRST_YEAR:
            dev = rows[-1]["debt_pct_gdp"] - baseline_debt_pct.loc[year - 1]
            spread += base.spread_feedback_bp_per_pp * max(dev, 0.0)

        # --- interest on what exists at the start of the year -------------
        frac = bonds.maturity.map(lambda m: _year_fraction_outstanding(m, year)).values
        fixed_mask = (bonds.instrument_class == "fixed_bullet").values
        link_mask = ~fixed_mask
        coupon_fixed = float((bonds.nominal * bonds.coupon * frac)[fixed_mask].sum())
        # linkers: real coupon on the uplifted nominal, plus uplift accrual
        upl = bonds.uplift_ratio * (1 + base.inflation) ** max(0, year - 2026)
        coupon_link = float((bonds.nominal * upl * bonds.coupon * frac)[link_mask].sum())
        uplift_accr = float((bonds.nominal * upl * base.inflation * frac)[link_mask].sum())
        redemptions = float((bonds.nominal * np.where(link_mask, upl, 1.0))[
            (bonds.maturity.dt.year == year).values].sum())

        # new tranches from earlier simulation years
        for t in new:
            if t["maturity_year"] > year:
                coupon_fixed += t["nominal"] * t["coupon"]
            elif t["maturity_year"] == year:
                redemptions += t["nominal"]
                coupon_fixed += t["nominal"] * t["coupon"] * 0.5   # matures mid-year on average

        # --- bills ---------------------------------------------------------
        btf_target = base.btf_stock
        btf_prev = btf_2025 if year == FIRST_YEAR else rows[-1]["btf_stock"]
        bill_rate = oat_yield(0.25, spread, base) / 100
        bill_interest = 0.5 * (btf_prev + btf_target) * bill_rate

        # --- the deficit and the financing need ----------------------------
        register_interest = coupon_fixed + coupon_link + uplift_accr + bill_interest
        y_new = {b: oat_yield(tenor_of[b], spread, base) / 100 for b in mix.index}
        avg_new_yield = float(sum(w[i] * y_new[b] for i, b in enumerate(mix.index)))
        wedge = base.gg_wedge_pct / 100 * gdp
        recv = base.interest_receivable_pct / 100 * gdp
        d_btf = btf_target - btf_prev
        # The deficit is financed by negotiable debt at the calibrated share,
        # EXCEPT the indexation uplift: it is D.41 interest (in the deficit)
        # and raises the Maastricht stock through the indexed nominal, but it
        # is not paid until redemption, so it is not issued against. (In ESA
        # the uplift is a reinvestment in F.32, so the 0.90 calibration
        # already contains it; the cash issuance is 0.90 × deficit − uplift.)
        # Booking it as issuance as well grew the stock by the uplift twice.
        if year == FIRST_YEAR:
            # Bridge year: the register already holds the issuance to the
            # snapshot, so only the remainder of the year is financed here,
            # and the whole year's interest — including the in-year interest
            # on that remainder — is the strict matrix's figure (EC AMECO).
            # Nothing is added to it: adding the new-issuance half-year on
            # top counted the same interest twice (2.5 EUR bn in the first
            # version, carried in the debt of every later year).
            year_share = (pd.Timestamp(year=year + 1, month=1, day=1) - pd.Timestamp(SNAPSHOT)).days / 365
            gg_interest = base.gg_interest_2026_bn
            register_interest = gg_interest - wedge
            deficit = -pb / 100 * gdp + gg_interest - recv
            new_year_interest = 0.0
            net_issuance = base.deficit_to_net_issuance * deficit * year_share
            mlt_gross = redemptions + net_issuance - uplift_accr * year_share - d_btf
        else:
            deficit_ex_new = -pb / 100 * gdp + register_interest + wedge - recv
            k = 0.5 * avg_new_yield          # issuance within the year pays half a year
            if financing_interest is not None and year in financing_interest.index:
                fin_deficit = -pb / 100 * gdp + float(financing_interest.loc[year]) - recv
                mlt_gross = redemptions + base.deficit_to_net_issuance * fin_deficit - uplift_accr - d_btf
                new_year_interest = max(mlt_gross, 0.0) * k
            else:
                # the interest on this year's issuance adds to the deficit,
                # which adds to issuance: geometric fixed point
                mlt_gross = redemptions + base.deficit_to_net_issuance * deficit_ex_new - uplift_accr - d_btf
                mlt_gross = mlt_gross / (1 - k * base.deficit_to_net_issuance) if mlt_gross > 0 else mlt_gross
                new_year_interest = max(mlt_gross, 0.0) * k
            register_interest += new_year_interest
            deficit = deficit_ex_new + new_year_interest
            net_issuance = base.deficit_to_net_issuance * deficit
            gg_interest = register_interest + wedge

        # book the new tranches
        for i, b in enumerate(mix.index):
            nominal = max(mlt_gross, 0.0) * w[i]
            if nominal > 0:
                new.append({"issue_year": year, "nominal": nominal, "coupon": y_new[b],
                            "maturity_year": year + max(1, int(round(tenor_of[b])))})
        debt += deficit
        # stock statistics at year end
        stock_bonds = float((bonds.nominal * np.where(link_mask, upl, 1.0))[
            (bonds.maturity.dt.year > year).values].sum())
        stock_new = sum(t["nominal"] for t in new if t["maturity_year"] > year)
        stock = stock_bonds + stock_new + btf_target
        cpn_bonds = float((bonds.nominal * bonds.coupon)[fixed_mask & (bonds.maturity.dt.year > year).values].sum())
        nom_bonds = float(bonds.nominal[fixed_mask & (bonds.maturity.dt.year > year).values].sum())
        cpn_new = sum(t["nominal"] * t["coupon"] for t in new if t["maturity_year"] > year)
        avg_coupon_fixed = 100 * (cpn_bonds + cpn_new) / (nom_bonds + stock_new) if nom_bonds + stock_new else np.nan

        rows.append({
            "scenario": sc.name, "label": sc.label, "year": year, "gdp_bn": gdp,
            "primary_balance_pct": pb, "primary_balance_bn": pb_of[year], "spread_bp": spread,
            "oat_10y_pct": oat_yield(10, spread, base), "avg_new_yield_pct": 100 * avg_new_yield,
            "mlt_avg_maturity_at_issue": mlt_avg_maturity_at_issue,
            "redemptions_bn": redemptions, "net_issuance_bn": net_issuance,
            "mlt_gross_issuance_bn": max(mlt_gross, 0.0), "btf_stock": btf_target,
            "register_interest_bn": register_interest, "gg_interest_bn": gg_interest,
            "gg_interest_pct_gdp": 100 * gg_interest / gdp,
            "deficit_bn": deficit, "deficit_pct_gdp": 100 * deficit / gdp,
            "debt_bn": debt, "debt_pct_gdp": 100 * debt / gdp,
            "negotiable_stock_bn": stock, "avg_coupon_fixed_pct": avg_coupon_fixed,
            "coupon_fixed_bn": coupon_fixed, "coupon_linker_bn": coupon_link,
            "uplift_bn": uplift_accr, "bill_interest_bn": bill_interest,
            "new_issue_interest_bn": new_year_interest,
        })
    return pd.DataFrame(rows)


def run_all(scenarios=SCENARIOS, base: Baseline = BASELINE, feedback: bool = True) -> pd.DataFrame:
    """All scenarios; the reference (status quo) is run first so the feedback
    term has a path to deviate from (the feedback is zero by default)."""
    reg = load_register()
    mix = issuance_mix()
    ref_sc = next(sc for sc in scenarios if sc.name == REFERENCE)
    ref_run = run_scenario(ref_sc, base, reg, mix, feedback=False)
    ref = ref_run.set_index("year").debt_pct_gdp
    out = {REFERENCE: ref_run}
    for sc in scenarios:
        if sc.name != REFERENCE:
            out[sc.name] = run_scenario(sc, base, reg, mix, feedback=feedback, baseline_debt_pct=ref)
    return pd.concat([out[sc.name] for sc in scenarios], ignore_index=True)


def decompose_gap(sc: Scenario, base: Baseline = BASELINE, years=(2030, 2035)) -> pd.DataFrame:
    """Split a scenario's interest gap to the status quo (`REFERENCE`) into
    the part due to the spread (price), the part due to the primary balance
    and growth (volume), and their interaction — by re-running the scenario
    with one lever at a time. Feedback off so the split is clean."""
    reg, mix = load_register(), issuance_mix()
    ref = scenario(REFERENCE)
    full = run_scenario(sc, base, reg, mix, feedback=False).set_index("year")
    base_run = run_scenario(ref, base, reg, mix, feedback=False).set_index("year")
    price_only = replace(ref, name=sc.name + "_price", spread_bp=sc.spread_path(base))
    volume_only = replace(sc, name=sc.name + "_volume", spread_bp=ref.spread_path(base))
    p = run_scenario(price_only, base, reg, mix, feedback=False).set_index("year")
    v = run_scenario(volume_only, base, reg, mix, feedback=False).set_index("year")
    rows = []
    for y in years:
        gap = full.gg_interest_bn[y] - base_run.gg_interest_bn[y]
        price = p.gg_interest_bn[y] - base_run.gg_interest_bn[y]
        volume = v.gg_interest_bn[y] - base_run.gg_interest_bn[y]
        rows.append({"scenario": sc.name, "label": sc.label, "year": y, "gap_bn": gap,
                     "spread_effect_bn": price, "volume_effect_bn": volume,
                     "interaction_bn": gap - price - volume})
    return pd.DataFrame(rows)


def loop_size(sc: Scenario, base: Baseline = BASELINE, years=(2030, 2035)) -> pd.DataFrame:
    """The arithmetic loop, measured directly: a scenario's interest gap to
    the status quo, less the gap it would show if its issuance were sized on
    the status quo's interest bill (the extra interest not refinanced). What
    is left is the interest the extra interest itself costs — the loop that
    `decompose_gap`'s interaction term is often read as, but is not (that
    term is the price × volume cross-effect of the two-lever split)."""
    reg, mix = load_register(), issuance_mix()
    ref_run = run_scenario(scenario(REFERENCE), base, reg, mix, feedback=False).set_index("year")
    full = run_scenario(sc, base, reg, mix, feedback=False).set_index("year")
    frozen = run_scenario(sc, base, reg, mix, feedback=False,
                          financing_interest=ref_run.gg_interest_bn).set_index("year")
    rows = []
    for y in years:
        gap = full.gg_interest_bn[y] - ref_run.gg_interest_bn[y]
        no_loop = frozen.gg_interest_bn[y] - ref_run.gg_interest_bn[y]
        rows.append({"scenario": sc.name, "label": sc.label, "year": y, "gap_bn": gap,
                     "gap_without_loop_bn": no_loop, "loop_bn": gap - no_loop,
                     "loop_share": (gap - no_loop) / gap if gap else np.nan})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Mark-to-market sensitivity of the stock (for the holders section)
# --------------------------------------------------------------------------

def duration_table(spread10_bp: float = 135.0, base: Baseline = BASELINE,
                   register: pd.DataFrame | None = None, as_of: str = SNAPSHOT) -> pd.DataFrame:
    """Price, modified duration and value per basis point of every bond in
    the register at the current curve. Annual coupons, ACT/365 residual life."""
    reg = (register if register is not None else load_register()).copy()
    reg = reg[reg.instrument_class != "bill"].copy()
    t0 = pd.Timestamp(as_of)
    rows = []
    for r in reg.itertuples():
        T = max((r.maturity - t0).days / 365.25, 0.01)
        y = oat_yield(T, spread10_bp, base) / 100
        c = r.coupon
        if r.instrument_class == "inflation_linked":
            y = y - base.inflation                      # real yield on real cash-flows
        n = int(np.ceil(T)); times = np.array([T - (n - 1 - i) for i in range(n)])
        times = times[times > 0]
        cfs = np.full(len(times), c); cfs[-1] += 1.0
        df = (1 + y) ** (-times)
        price = float((cfs * df).sum())
        mac = float((times * cfs * df).sum() / price)
        mod = mac / (1 + y)
        mv = r.nominal * r.uplift_ratio * price
        rows.append({"security_id": r.security_id, "name": r.name, "class": r.instrument_class,
                     "nominal_bn": r.nominal * r.uplift_ratio, "years_to_maturity": T,
                     "yield_pct": 100 * y, "price": 100 * price, "market_value_bn": mv,
                     "modified_duration": mod,
                     # EUR mn per basis point: bn × duration / 10,000 × 1,000
                     "value_per_bp_mn": mv * mod / 10_000 * 1000})
    return pd.DataFrame(rows)


def duration_summary(spread10_bp: float = 135.0) -> dict:
    d = duration_table(spread10_bp)
    mv = d.market_value_bn.sum()
    dur = (d.market_value_bn * d.modified_duration).sum() / mv
    return {"market_value_bn": round(mv, 0), "nominal_bn": round(d.nominal_bn.sum(), 0),
            "modified_duration_years": round(dur, 2),
            "loss_per_100bp_bn": round(mv * dur / 100, 0),
            "loss_per_100bp_pct_gdp": round(100 * mv * dur / 100 / gdp_path(scenario(REFERENCE))[2026], 2)}


if __name__ == "__main__":       # pragma: no cover
    pd.set_option("display.width", 200)
    print(calibration())
    res = run_all()
    cols = ["label", "year", "spread_bp", "gg_interest_bn", "gg_interest_pct_gdp",
            "deficit_pct_gdp", "debt_pct_gdp", "mlt_gross_issuance_bn", "avg_coupon_fixed_pct"]
    print(res[res.year.isin([2026, 2027, 2028, 2030, 2032, 2035])][cols].round(2).to_string())
    print(duration_summary())
