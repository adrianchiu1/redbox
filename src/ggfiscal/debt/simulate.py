"""Yield-path simulation through the register onto the interest line (France).

`DEBT_KICKOFF.md` §1 closes with "out of scope now, but shaped for:
simulating alternative yield-curve paths through the register onto the
interest line". This module is that simulation, for France, built for the
AFT briefing of September 2026 (D-S12-001).

It reads only the flat files in `deliverables/` — the per-security register
at the AFT's latest snapshot, the reference rates, the ledger and the strict
matrix — and rolls the stock forward year by year under a **declared**
scenario: a primary-balance path, an OAT–Bund spread path, a Bund curve, an
issuance mix and a bill-stock path. Every parameter is a number in
`BASELINE` or in one of the `SCENARIOS`; nothing is estimated, fitted or
calibrated silently. Where a calibration is used (the share of the
general-government deficit the État's negotiable debt absorbs, the wedge
between the register's interest and `GF01_7`) it is computed from the
deliverables and printed by `calibration()`.

What it is: an arithmetic of the existing coupons rolling off and being
replaced at scenario yields, with the deficit feeding back through the
interest bill (the wrong-way loop the briefing is about). What it is not: a
forecast of yields, growth or politics. The scenarios are the four
2027 configurations the committee asked for (Le Pen / Philippe × majority /
hung) plus the current path and one rupture stress, each stated in the
`SCENARIOS` table so it can be argued with line by line.

Conventions: calendar years; EUR bn unless a name says otherwise; interest
on the accrual basis (D.41 concept: coupons pro rata, bill discount
accreted, indexation uplift accrued as it arises — DD3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
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

    # Nominal GDP, EUR bn: 2025 ledger outturn, 2026–2027 the strict matrix
    # (EC AMECO spring 2026), then a declared 3.0% a year (1% real, 2% deflator).
    gdp: dict = field(default_factory=lambda: {2025: 2979.1, 2026: 3055.8, 2027: 3150.7})
    gdp_growth_after: float = 0.030

    # Primary balance, % of GDP (negative = primary deficit). 2025: NLB −5.1
    # less net interest ≈ 2.0 → −3.1. Thereafter 0.4 pp a year — slower than
    # the EDP path (0.5 pp structural) because the 2026 budget already
    # slipped from 4.6 to 5.0 and 2027 is an election year.
    primary_balance: dict = field(default_factory=lambda: {
        2025: -3.1, 2026: -2.7, 2027: -2.5, 2028: -2.1, 2029: -1.7,
        2030: -1.3, 2031: -0.9, 2032: -0.6, 2033: -0.5, 2034: -0.5, 2035: -0.5})

    # Interest receivable (R07), % of GDP, held constant.
    interest_receivable_pct: float = 0.2

    # Maastricht debt at end-2025 (INSEE, 27 March 2026: 115.6% of GDP).
    debt_2025_pct: float = 115.6

    # Bund curve, % — flat through the horizon (declared). 3m and 10y are the
    # register's own reference series at the snapshot (EA 3m money-market
    # 2.51% Aug 2026; Bundesbank 10y 3.41% on 7 Sep 2026); 2y/5y/30y declared.
    bund_curve: dict = field(default_factory=lambda: {
        0.25: 2.50, 2: 2.90, 5: 3.15, 10: 3.40, 30: 3.75})

    # OAT–Bund spread term structure as a fraction of the 10y spread.
    spread_shape: dict = field(default_factory=lambda: {
        0.25: 0.15, 2: 0.45, 5: 0.75, 10: 1.00, 30: 1.15})

    # Inflation for indexation uplift (FR CPI ex-tobacco / EA HICP ex-tobacco).
    inflation: float = 0.020
    # Real yield spread of linkers over the fixed curve: coupon at issue
    # = nominal yield − expected inflation (breakeven = inflation).
    linker_share_of_mlt: float = 0.07

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
    # security interest, non-negotiable debt, consolidation). 2025: 65.2 −
    # 55.2 = 10.0 EUR bn = 0.34% of GDP. Held constant as a share of GDP.
    gg_wedge_pct: float = 0.34

    # Feedback: spread rises with the debt ratio's deviation from the
    # current path, bp per pp of GDP. Declared, small.
    spread_feedback_bp_per_pp: float = 3.0


@dataclass
class Scenario:
    name: str
    label: str
    # Primary-balance deviation from the baseline path, pp of GDP, by year
    # (level deviation, not cumulative); missing years = last value.
    pb_deviation: dict
    # 10y OAT–Bund spread, bp, by year; missing years = last value.
    spread_bp: dict
    # Bill (BTF) stock path, EUR bn, by year end; missing = last value.
    btf_stock: dict
    # Issuance-mix tilt: bucket shares × exp(−lambda × tenor), renormalised.
    # 0 = the AFT's 2025 mix; positive = shorter.
    maturity_tilt: float = 0.0
    note: str = ""


BASELINE = Baseline()

_BTF_FLAT = {2026: 215.0}

SCENARIOS = [
    Scenario(
        "current", "Current path",
        pb_deviation={2026: 0.0},
        spread_bp={2026: 85, 2027: 85, 2028: 80, 2029: 75, 2030: 70},
        btf_stock=_BTF_FLAT,
        note="Minority governments continue to pass budgets by 49.3 with concessions; "
             "consolidation at 0.4 pp a year; spread drifts back towards its 2025 average."),
    Scenario(
        "philippe_majority", "Philippe, majority",
        pb_deviation={2027: 0.0, 2028: 0.3, 2029: 0.6, 2030: 0.9, 2031: 1.0},
        spread_bp={2026: 85, 2027: 80, 2028: 60, 2029: 50, 2030: 45},
        btf_stock=_BTF_FLAT,
        note="Pension age towards 65 phased from 2028, spending review, EDP path met by 2030; "
             "spread compresses towards the 2015–2021 range (35–50 bp)."),
    Scenario(
        "philippe_hung", "Philippe, hung Assembly",
        pb_deviation={2027: 0.0, 2028: -0.1, 2029: -0.2, 2030: -0.3, 2031: -0.4},
        spread_bp={2026: 85, 2027: 85, 2028: 80, 2029: 80, 2030: 75},
        btf_stock=_BTF_FLAT,
        note="A president without a majority: budgets by 49.3, consolidation slower than the "
             "current path; spread stays where 2025–2026 put it."),
    Scenario(
        "lepen_majority", "Le Pen, majority",
        pb_deviation={2027: 0.0, 2028: -1.2, 2029: -1.5, 2030: -1.5},
        spread_bp={2026: 85, 2027: 110, 2028: 150, 2029: 140, 2030: 130},
        btf_stock={2026: 215.0, 2027: 230.0, 2028: 260.0, 2029: 270.0},
        maturity_tilt=0.04,
        note="RN programme enacted: VAT on energy to 5.5% (≈0.5% of GDP), 2023 pension reform "
             "rolled back (≈0.5–0.8% of GDP by 2030), partial offsets; spread re-prices to "
             "the 2012 peak and stays; AFT leans on bills and shorter tenors."),
    Scenario(
        "lepen_hung", "Le Pen, hung Assembly",
        pb_deviation={2027: 0.0, 2028: -0.6, 2029: -0.8, 2030: -1.0},
        spread_bp={2026: 85, 2027: 100, 2028: 120, 2029: 120, 2030: 115},
        btf_stock={2026: 215.0, 2027: 225.0, 2028: 240.0},
        maturity_tilt=0.02,
        note="RN president, no majority: paralysis rather than programme; no consolidation, "
             "partial giveaways; spread above the current path but short of the 2012 peak."),
    Scenario(
        "lepen_rupture", "Le Pen, majority, rupture (stress)",
        pb_deviation={2027: 0.0, 2028: -1.5, 2029: -2.0, 2030: -2.0},
        spread_bp={2026: 85, 2027: 130, 2028: 250, 2029: 220, 2030: 200},
        btf_stock={2026: 215.0, 2027: 240.0, 2028: 300.0, 2029: 320.0},
        maturity_tilt=0.08,
        note="Stress, not a central case: open conflict with the Commission over the EDP, TPI "
             "eligibility in doubt, spread at 250 bp; the AFT funds a growing share at the short end."),
]


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
    ibs = _load("debt_interest_by_security").query("iso3 == @ISO and basis == 'cash'")
    reg_int = ibs.groupby("year").total_lcu_mn.sum() / 1000
    strict = pd.read_csv(DELIV / "strict_FRA.csv").set_index("year")
    gf = strict["GF01_7 - Public debt transactions (interest)"] / 1000
    return {"net_issuance_over_deficit_2015_2025": round(float(ratio), 3),
            "register_cash_interest_2025_bn": round(float(reg_int.loc[2025]), 1),
            "gf01_7_2025_bn": round(float(gf.loc[2025]), 1),
            "wedge_2025_bn": round(float(gf.loc[2025] - reg_int.loc[2025]), 1),
            "wedge_2025_pct_gdp": round(100 * float(gf.loc[2025] - reg_int.loc[2025])
                                        / BASELINE.gdp[2025], 2)}


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
                 baseline_debt_pct: pd.Series | None = None) -> pd.DataFrame:
    """Roll the register forward under one scenario. One row per year."""
    reg = (register if register is not None else load_register()).copy()
    mix = mix if mix is not None else issuance_mix()
    tenor_of = {b: mix.attrs.get("tenor", {}).get(b, BUCKET_TENOR[b]) for b in mix.index}
    tenors = np.array([tenor_of[b] for b in mix.index])
    w = mix.values * np.exp(-sc.maturity_tilt * tenors)
    w = w / w.sum()
    mlt_avg_maturity_at_issue = float((w * tenors).sum())

    # Existing stock split: bills are re-rolled as a stock, bonds tranche by tranche.
    bonds = reg[reg.instrument_class != "bill"].copy()
    bonds["issue_year"] = 0
    btf_2025 = float(reg.loc[reg.instrument_class == "bill", "nominal"].sum())
    new = []                                   # tranches issued in the simulation
    debt = base.debt_2025_pct / 100 * base.gdp[2025]
    gdp_prev = base.gdp[2025]
    rows = []
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        gdp = base.gdp.get(year, gdp_prev * (1 + base.gdp_growth_after))
        pb = _path(base.primary_balance, year) + _path(sc.pb_deviation, year, 0.0)
        spread = float(_path(sc.spread_bp, year))
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
        btf_target = float(_path(sc.btf_stock, year))
        btf_prev = btf_2025 if year == FIRST_YEAR else rows[-1]["btf_stock"]
        bill_rate = oat_yield(0.25, spread, base) / 100
        bill_interest = 0.5 * (btf_prev + btf_target) * bill_rate

        # --- the deficit and the financing need ----------------------------
        register_interest = coupon_fixed + coupon_link + uplift_accr + bill_interest
        # Issuance within the year also pays interest: half a year on average.
        # Solve the small fixed point for gross MLT issuance and its coupon.
        y_new = {b: oat_yield(tenor_of[b], spread, base) / 100 for b in mix.index}
        avg_new_yield = float(sum(w[i] * y_new[b] for i, b in enumerate(mix.index)))
        # linker share of new issuance carries real coupon + inflation accrual = nominal yield
        wedge = base.gg_wedge_pct / 100 * gdp
        recv = base.interest_receivable_pct / 100 * gdp
        deficit_ex_new = -pb / 100 * gdp + register_interest + wedge - recv
        year_share = 1.0
        if year == FIRST_YEAR:   # bridge year: the register holds the issuance to the snapshot
            year_share = (pd.Timestamp(year=year + 1, month=1, day=1) - pd.Timestamp(SNAPSHOT)).days / 365
            deficit_ex_new = -pb / 100 * gdp + base.gg_interest_2026_bn - recv
        net_issuance = base.deficit_to_net_issuance * deficit_ex_new * year_share
        d_btf = btf_target - btf_prev
        mlt_gross = redemptions + net_issuance - d_btf
        # interest on this year's issuance (half-year) adds to the deficit, which
        # adds to issuance: geometric fixed point
        k = 0.5 * avg_new_yield
        mlt_gross = mlt_gross / (1 - k * base.deficit_to_net_issuance) if mlt_gross > 0 else mlt_gross
        new_year_interest = max(mlt_gross, 0.0) * k
        register_interest += new_year_interest
        deficit = deficit_ex_new + new_year_interest
        net_issuance = base.deficit_to_net_issuance * deficit * year_share
        gg_interest = register_interest + wedge
        if year == FIRST_YEAR:
            gg_interest = base.gg_interest_2026_bn
            register_interest = gg_interest - wedge

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
            "primary_balance_pct": pb, "spread_bp": spread,
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
        gdp_prev = gdp
    return pd.DataFrame(rows)


def run_all(scenarios=SCENARIOS, base: Baseline = BASELINE, feedback: bool = True) -> pd.DataFrame:
    """All scenarios; the current path is run first so the feedback term has a reference."""
    reg = load_register()
    mix = issuance_mix()
    current = run_scenario(scenarios[0], base, reg, mix, feedback=False)
    ref = current.set_index("year").debt_pct_gdp
    out = [current]
    for sc in scenarios[1:]:
        out.append(run_scenario(sc, base, reg, mix, feedback=feedback, baseline_debt_pct=ref))
    return pd.concat(out, ignore_index=True)


def decompose_gap(sc: Scenario, base: Baseline = BASELINE, years=(2030, 2035)) -> pd.DataFrame:
    """Split a scenario's extra interest over the current path into the part
    due to the spread (price), the part due to the primary balance and
    issuance strategy (volume), and their interaction — by re-running the
    scenario with one lever at a time. Feedback off so the split is clean."""
    reg, mix = load_register(), issuance_mix()
    cur = SCENARIOS[0]
    full = run_scenario(sc, base, reg, mix, feedback=False).set_index("year")
    base_run = run_scenario(cur, base, reg, mix, feedback=False).set_index("year")
    price_only = Scenario(sc.name + "_price", sc.label, cur.pb_deviation, sc.spread_bp,
                          cur.btf_stock, 0.0)
    volume_only = Scenario(sc.name + "_volume", sc.label, sc.pb_deviation, cur.spread_bp,
                           sc.btf_stock, sc.maturity_tilt)
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


# --------------------------------------------------------------------------
# Mark-to-market sensitivity of the stock (for the holders section)
# --------------------------------------------------------------------------

def duration_table(spread10_bp: float = 90.0, base: Baseline = BASELINE,
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
                     "modified_duration": mod, "value_per_bp_mn": mv * mod * 1e3 / 1e4 * 1e3 / 1e3})
    out = pd.DataFrame(rows)
    out["value_per_bp_mn"] = out.market_value_bn * out.modified_duration / 10_000 * 1000
    return out


def duration_summary(spread10_bp: float = 90.0) -> dict:
    d = duration_table(spread10_bp)
    mv = d.market_value_bn.sum()
    dur = (d.market_value_bn * d.modified_duration).sum() / mv
    return {"market_value_bn": round(mv, 0), "nominal_bn": round(d.nominal_bn.sum(), 0),
            "modified_duration_years": round(dur, 2),
            "loss_per_100bp_bn": round(mv * dur / 100, 0),
            "loss_per_100bp_pct_gdp": round(100 * mv * dur / 100 / BASELINE.gdp[2026], 2)}


if __name__ == "__main__":       # pragma: no cover
    pd.set_option("display.width", 200)
    print(calibration())
    res = run_all()
    cols = ["label", "year", "spread_bp", "gg_interest_bn", "gg_interest_pct_gdp",
            "deficit_pct_gdp", "debt_pct_gdp", "mlt_gross_issuance_bn", "avg_coupon_fixed_pct"]
    print(res[res.year.isin([2026, 2027, 2028, 2030, 2032, 2035])][cols].round(2).to_string())
    print(duration_summary())
