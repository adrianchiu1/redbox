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
    register     = coupons + uplift + bill discount − premium amortisation + in-year issuance
    debt_t       = debt_{t−1} + deficit_t                 (no stock-flow adjustment)
    MLT gross    = redemptions + 0.90 × deficit − uplift accrual − Δbills
    Δ negotiable stock = 0.90 × deficit                   (from 2027; exact)
    linker index = snapshot ratio × (1+π)^(years since the snapshot date)
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
AMORT_YEAR = 2026                # register year whose premium amortisation is carried forward
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
    # as a share of GDP. Calibrated on the register's accrued (D.41) total,
    # which the roll reproduces in concept: coupon pro rata, uplift accrued,
    # bill discount accreted, less the straight-line amortisation of the
    # premiums at which lines in the stock were reopened. 2025: 65.2 − 51.8 =
    # 13.4 EUR bn = 0.45% of GDP (`calibration()["wedge_2025_accrued_pct_gdp"]`).
    # The first version took the register's CASH total (55.2, 0.34%) against
    # an accrual roll; the second the roll without the amortisation (55.8,
    # 0.32%), and both were measured against an accrued total that counted
    # every bill's discount twice (fixed in interest.py, D-S18-005).
    gg_wedge_pct: float = 0.45

    # Feedback: spread rises with the debt ratio's deviation from the
    # reference scenario, bp per pp of GDP. Off (D-S18-001): each scenario's
    # spread path is declared in full, so the engine does not move it.
    spread_feedback_bp_per_pp: float = 0.0

    # Issuance rule (D-S18-006). "constant_profile": the maturity profile of
    # the negotiable stock at the snapshot — bills as a share of the stock,
    # bonds by residual-maturity bucket (`profile_weights`) — is held
    # constant: each year the AFT issues into bills and into every bucket
    # exactly what restores its weight after a year of ageing and the year's
    # redemptions; a bucket already above its weight gets nothing (no
    # buybacks) and the shortfall is reported as `profile_deviation_bn`.
    # "constant_mix": D-S18-001 rule 5 — the AFT's 2025 issuance shares by
    # bucket every year and a bill stock held at `btf_stock` EUR bn.
    issuance_rule: str = "constant_profile"
    # The date the held profile is measured at: the snapshot stock's residual
    # maturities seen from this date (`profile_weights`). The year end the
    # roll starts from, not the September snapshot: the engine books by
    # calendar year, so the 0–1 bucket at any year end holds a whole year of
    # maturities, which a mid-September view does not (it would put the
    # target at 5.8% against 7.4%, and the overshoot the ageing stock then
    # carries in the two shortest buckets is twice as large).
    profile_as_of: str = "2026-12-31"
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

CLASSES = ("bill", "fixed_bullet", "inflation_linked")
BUCKETS = list(BUCKET_TENOR)                       # DD7 buckets, in order
BUCKET_EDGES = [0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0, np.inf]


def _load(name):
    return pd.read_csv(DELIV / f"{name}.csv", low_memory=False)


def validate_register(reg: pd.DataFrame, snapshot: str = SNAPSHOT) -> pd.DataFrame:
    """The checks every register goes through before any arithmetic
    (D-S18-006): one row per security, supported classes only, a dated
    maturity after the snapshot, a finite positive nominal, a finite coupon
    on every bond (bills carry none), a finite positive index ratio on every
    linker and exactly one on everything else. A missing value raises; it is
    never read as zero or dropped from a sum. Returns a copy with the
    `premium_amort` column present (zero where the caller gave none)."""
    required = ["security_id", "instrument_class", "coupon", "maturity", "nominal", "uplift_ratio"]
    missing = [c for c in required if c not in reg.columns]
    if missing:
        raise ValueError(f"register lacks columns {missing}")
    reg = reg.copy()
    if "premium_amort" not in reg.columns:
        reg["premium_amort"] = 0.0
    if "name" not in reg.columns:
        reg["name"] = reg.security_id
    dup = reg.security_id[reg.security_id.duplicated()].tolist()
    if dup:
        raise ValueError(f"duplicate security ids in the register: {dup[:5]}")
    unknown = sorted(set(reg.instrument_class) - set(CLASSES))
    if unknown:
        raise ValueError(f"unsupported instrument classes {unknown}; supported: {list(CLASSES)}")
    reg["maturity"] = pd.to_datetime(reg.maturity, errors="coerce")
    if reg.maturity.isna().any():
        raise ValueError(f"missing or unparseable maturity on {reg.security_id[reg.maturity.isna()].tolist()[:5]}")
    t0 = pd.Timestamp(snapshot)
    early = reg.security_id[reg.maturity <= t0].tolist()
    if early:
        raise ValueError(f"securities matured on or before the snapshot {snapshot}: {early[:5]}")
    for col in ("nominal", "coupon", "uplift_ratio", "premium_amort"):
        reg[col] = pd.to_numeric(reg[col], errors="coerce")
    bad = reg.security_id[~np.isfinite(reg.nominal) | (reg.nominal <= 0)].tolist()
    if bad:
        raise ValueError(f"nominal must be finite and positive: {bad[:5]}")
    bond = reg.instrument_class != "bill"
    bad = reg.security_id[bond & ~np.isfinite(reg.coupon)].tolist()
    if bad:
        raise ValueError(f"missing or non-finite coupon on bonds {bad[:5]} (a bond's unknown coupon is not zero)")
    reg.loc[~bond, "coupon"] = reg.loc[~bond, "coupon"].fillna(0.0)
    link = reg.instrument_class == "inflation_linked"
    bad = reg.security_id[link & (~np.isfinite(reg.uplift_ratio) | (reg.uplift_ratio <= 0))].tolist()
    if bad:
        raise ValueError(f"missing or non-finite index ratio (uplift) on linkers {bad[:5]}")
    bad = reg.security_id[~link & ~np.isclose(reg.uplift_ratio.fillna(1.0), 1.0)].tolist()
    if bad:
        raise ValueError(f"index ratio must be exactly 1 on non-linkers: {bad[:5]}")
    reg.loc[~link, "uplift_ratio"] = 1.0
    bad = reg.security_id[~np.isfinite(reg.premium_amort)].tolist()
    if bad:
        raise ValueError(f"non-finite premium amortisation on {bad[:5]}")
    return reg[["security_id", "name", "instrument_class", "coupon", "maturity",
                "nominal", "uplift_ratio", "premium_amort"]].reset_index(drop=True)


def load_register(snapshot: str = SNAPSHOT) -> pd.DataFrame:
    """Every French security outstanding at the snapshot with its terms,
    validated (`validate_register`)."""
    sec = _load("debt_securities").query("iso3 == @ISO")
    pos = _load("debt_positions").query("iso3 == @ISO and as_of == @snapshot")
    if pos.empty:
        raise ValueError(f"no {ISO} positions at {snapshot} in debt_positions.csv")
    dup = sec.security_id[sec.security_id.duplicated()].tolist()
    if dup:
        raise ValueError(f"duplicate security metadata in debt_securities.csv: {dup[:5]}")
    dup = pos.security_id[pos.security_id.duplicated()].tolist()
    if dup:
        raise ValueError(f"duplicate positions at {snapshot}: {dup[:5]}")
    reg = pos.merge(sec[["security_id", "name", "instrument_class", "sub_type",
                         "coupon_pct", "maturity_date", "first_issue_date"]],
                    on="security_id", how="left", validate="one_to_one")
    unmatched = reg.security_id[reg.instrument_class.isna()].tolist()
    if unmatched:
        raise ValueError(f"positions without security metadata: {unmatched[:5]}")
    neg = reg.security_id[reg.nominal_lcu_mn < 0].tolist()
    if neg:
        raise ValueError(f"negative positions at {snapshot}: {neg[:5]}")
    reg = reg[reg.nominal_lcu_mn > 0].copy()           # redeemed lines carry zero
    reg["maturity"] = pd.to_datetime(reg.maturity_date)
    reg["nominal"] = reg.nominal_lcu_mn / 1000.0                       # EUR bn
    link = reg.instrument_class == "inflation_linked"
    reg["uplift_ratio"] = np.where(link, reg.nominal_uplifted_lcu_mn / reg.nominal_lcu_mn, 1.0)
    reg["coupon"] = reg.coupon_pct / 100.0            # NaN on a bond is rejected below
    # Premium/discount amortisation on the lines in the stock (§7.7 of the
    # register, EUR bn a year, positive = premium, reduces D.41): the latest
    # full register year's figure, carried at that annual rate to maturity.
    # Lines reopened within that year carry a part-year figure (settlement to
    # 31 December), so the rate is slightly understated for them.
    amort = (_load("debt_interest_by_security")
             .query("iso3 == @ISO and basis == 'accrued' and year == @AMORT_YEAR")
             .groupby("security_id").premium_discount_amort_lcu_mn.sum() / 1000.0)
    reg["premium_amort"] = reg.security_id.map(amort).fillna(0.0)
    return validate_register(reg, snapshot)


def issuance_mix(year: int = 2025) -> pd.Series:
    """Share of medium/long-term gross issuance by residual-maturity bucket
    in `year`, fixed and linkers together (the AFT's own choice of tenors).
    The tenor used for each bucket is the AFT's own nominal-weighted residual
    maturity at issue in that bucket and year (`weighted_residual_years_at_issue`),
    stored in the Series' attrs, not the bucket midpoint. The `constant_mix`
    issuance rule applies these shares every year; the `constant_profile`
    rule uses only the tenors."""
    b = _load("debt_issuance_by_bucket").query(
        "iso3 == @ISO and year == @year and instrument_class != 'bill'")
    b = b.assign(w=b.gross_nominal_lcu_mn * b.weighted_residual_years_at_issue)
    g = b.groupby("bucket").agg(nominal=("gross_nominal_lcu_mn", "sum"), w=("w", "sum"))
    g = g.reindex([k for k in BUCKET_TENOR if k in g.index])
    s = g.nominal / g.nominal.sum()
    s.attrs["tenor"] = (g.w / g.nominal).to_dict()
    return s


def _bucket_of(residual_years) -> pd.Categorical:
    """DD7 bucket of a residual maturity in years, [lo, hi)."""
    return pd.cut(np.asarray(residual_years, dtype=float), BUCKET_EDGES, labels=BUCKETS, right=False)


def profile_weights(register: pd.DataFrame, as_of: str = SNAPSHOT) -> pd.Series:
    """The maturity profile the `constant_profile` rule holds: the share of
    the negotiable stock in bills and in each residual-maturity bucket of
    bonds at `as_of`, bonds at their indexed nominal. Index "bill" then the
    DD7 buckets; sums to one."""
    t0 = pd.Timestamp(as_of)
    bonds = register[(register.instrument_class != "bill") & (register.maturity > t0)]
    value = bonds.nominal * bonds.uplift_ratio
    residual = (bonds.maturity - t0).dt.days / 365.25
    by_bucket = value.groupby(_bucket_of(residual), observed=False).sum().reindex(BUCKETS, fill_value=0.0)
    bills = float(register.loc[register.instrument_class == "bill", "nominal"].sum())
    w = pd.concat([pd.Series({"bill": bills}), by_bucket.astype(float)])
    return w / w.sum()


def tranche_years(bucket: str, tenor: float) -> int:
    """Whole years to maturity of a tranche issued mid-year into `bucket`, so
    that at the year end (residual T − 0.5) it sits in that bucket: the
    rounded tenor where that lands in the bucket, else the shortest that does."""
    T = max(1, int(round(tenor)))
    if str(_bucket_of([T - 0.5])[0]) == bucket:
        return T
    lo = BUCKET_EDGES[BUCKETS.index(bucket)]
    return max(1, int(np.ceil(lo + 0.5)))


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
    # coupon pro rata, uplift accrued, bill discount accreted — the accrued
    # basis before the premium/discount amortisation (§7.7), which the roll
    # carries separately (`premium_amort_bn`)
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
            # the premium/discount amortisation on the bonds in the stock
            # (positive = premium, reduces interest), which the roll carries
            # forward from AMORT_YEAR; bills have none (D-S18-005)
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

def index_factor(date, base: Baseline = BASELINE, snapshot: str = SNAPSHOT):
    """Growth of a linker's index ratio from the snapshot date to `date` at
    the declared inflation: (1+π)^(days/365.25). One for the snapshot itself;
    below one for dates before it. Vectorised over a DatetimeIndex/array."""
    days = (pd.DatetimeIndex(np.atleast_1d(np.asarray(date, dtype="datetime64[ns]")))
            - pd.Timestamp(snapshot)).days.to_numpy()
    out = (1.0 + base.inflation) ** (days / 365.25)
    return float(out[0]) if np.ndim(date) == 0 else out


def _year_fraction_outstanding(maturity: pd.Timestamp, year: int) -> float:
    """Fraction of calendar `year` a bullet maturing on `maturity` is outstanding."""
    start = pd.Timestamp(year=year, month=1, day=1)
    end = pd.Timestamp(year=year + 1, month=1, day=1)
    if maturity <= start:
        return 0.0
    if maturity >= end:
        return 1.0
    return (maturity - start).days / (end - start).days


class FinancingSurplus(ValueError):
    """Gross issuance after redemptions would be negative: buybacks and cash
    balances are not modelled (D-S18-006)."""


def run_scenario(sc: Scenario, base: Baseline = BASELINE, register: pd.DataFrame | None = None,
                 mix: pd.Series | None = None, feedback: bool = True,
                 baseline_debt_pct: pd.Series | None = None,
                 financing_interest: pd.Series | None = None) -> pd.DataFrame:
    """Roll the register forward under one scenario. One row per year.

    Linkers (D-S18-006): the index ratio at the snapshot grows at the
    declared inflation from the snapshot DATE, so the opening index of a
    year is the snapshot ratio × (1+π)^(years since 10 Sep 2026). In a year a
    linker is outstanding from `start` (1 January, or the snapshot in 2026)
    to `stop` (31 December, or its maturity): uplift accrues on nominal ×
    (index(stop) − index(start)); the coupon accrues pro rata on the
    geometric mean of the two indexed nominals; a maturing linker redeems
    nominal × index(maturity); a surviving one closes at nominal ×
    index(31 December). So the stock, the uplift and the redemptions are the
    same path, and Δ(negotiable stock) = financed share × deficit exactly.

    Issuance (`base.issuance_rule`, D-S18-006): the year-end stock is the
    opening stock plus the financed share of the deficit (ESA: the uplift is
    reinvested, not issued against). Under `constant_profile` bills and each
    residual-maturity bucket are brought to their snapshot share of that
    stock; a bucket already above its share gets nothing (no buybacks) and
    the shortfall is `profile_deviation_bn`. Under `constant_mix` the bill
    stock is `base.btf_stock` and bond issuance follows the AFT's 2025
    shares. A negative gross requirement raises `FinancingSurplus`.

    `financing_interest` (EUR bn by year, general-government basis) is a
    diagnostic: when given, the issuance of each year from 2027 is sized on
    that interest bill instead of the scenario's own, while the deficit, the
    debt and the interest reported stay the scenario's. `loop_size` uses it
    with the status quo's bill to measure the arithmetic loop directly.
    """
    reg = validate_register(register if register is not None else load_register())
    mix = mix if mix is not None else issuance_mix()
    rule = base.issuance_rule
    if rule not in ("constant_profile", "constant_mix"):
        raise ValueError(f"unknown issuance_rule {rule!r}: constant_profile or constant_mix")
    a = base.deficit_to_net_issuance
    snap = pd.Timestamp(SNAPSHOT)
    tenor_of = {b: float(mix.attrs.get("tenor", {}).get(b, BUCKET_TENOR[b])) for b in BUCKETS}
    years_of = {b: tranche_years(b, tenor_of[b]) for b in BUCKETS}
    mix_w = pd.Series({b: float(mix.get(b, 0.0)) for b in BUCKETS})
    mix_w = mix_w / mix_w.sum()
    weights = profile_weights(reg, base.profile_as_of) if rule == "constant_profile" else None

    bonds = reg[reg.instrument_class != "bill"].reset_index(drop=True)
    link = (bonds.instrument_class == "inflation_linked").to_numpy()
    fixed = ~link
    nominal = bonds.nominal.to_numpy(float)
    coupon = bonds.coupon.to_numpy(float)
    ratio = bonds.uplift_ratio.to_numpy(float)
    amort = bonds.premium_amort.to_numpy(float)
    mat = bonds.maturity.to_numpy(dtype="datetime64[ns]")
    btf_prev = float(reg.loc[reg.instrument_class == "bill", "nominal"].sum())
    stock_prev = float((nominal * ratio).sum()) + btf_prev      # index factor 1 at the snapshot
    new: list[dict] = []                                        # tranches issued in the simulation
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
        bridge = year == FIRST_YEAR
        start = snap if bridge else pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year + 1, month=1, day=1)
        share = (end - start).days / 365 if bridge else 1.0      # of the year financed here

        # --- existing bonds over [start, stop) ----------------------------
        alive = mat > start.to_datetime64()
        stop = np.minimum(mat, end.to_datetime64())
        days_out = np.clip((stop - start.to_datetime64()).astype("timedelta64[D]").astype(float), 0, None)
        frac = days_out / (365.25 if bridge else (end - start).days)
        f_start = index_factor(start, base)
        f_stop = index_factor(stop, base)
        f_end = index_factor(end, base)
        idx_start = np.where(link, ratio * f_start, 1.0)
        idx_stop = np.where(link, ratio * f_stop, 1.0)
        coupon_fixed = float((nominal * coupon * frac)[fixed & alive].sum())
        coupon_link = float((nominal * coupon * frac * np.sqrt(idx_start * idx_stop))[link & alive].sum())
        uplift_accr = float((nominal * (idx_stop - idx_start))[link & alive].sum())
        prem_amort = float((amort * frac)[alive].sum())
        maturing = alive & (mat < end.to_datetime64())
        redemptions = float((nominal * idx_stop)[maturing].sum())
        surviving = alive & ~maturing
        # new tranches from earlier simulation years
        for t in new:
            if t["maturity_year"] > year:
                coupon_fixed += t["nominal"] * t["coupon"]
            elif t["maturity_year"] == year:
                redemptions += t["nominal"]
                coupon_fixed += t["nominal"] * t["coupon"] * 0.5   # matures mid-year on average
        existing_interest = coupon_fixed + coupon_link + uplift_accr - prem_amort

        # --- the stock that survives the year, by residual bucket at the year end
        value_end = np.where(link, nominal * ratio * f_end, nominal)[surviving]
        residual_end = ((mat[surviving] - end.to_datetime64()).astype("timedelta64[D]").astype(float)) / 365.25
        surv = pd.Series(value_end).groupby(_bucket_of(residual_end), observed=False).sum().reindex(BUCKETS, fill_value=0.0).astype(float)
        for t in new:
            if t["maturity_year"] > year:
                surv[str(_bucket_of([t["maturity_year"] - year - 0.5])[0])] += t["nominal"]
        surv_total = float(surv.sum())

        wedge = base.gg_wedge_pct / 100 * gdp
        recv = base.interest_receivable_pct / 100 * gdp
        y_new = {b: oat_yield(tenor_of[b], spread, base) / 100 for b in BUCKETS}
        bill_rate = oat_yield(0.25, spread, base) / 100

        def financing(d_fin: float):
            """Year-end stock, bills, gross bond issuance by bucket and the
            profile shortfall for a deficit `d_fin` financed this year."""
            s_end = stock_prev + a * d_fin * share
            if rule == "constant_profile":
                btf_end = float(weights["bill"] * s_end)
                target = weights[BUCKETS].astype(float) * s_end
            else:
                btf_end = float(base.btf_stock)
                target = None
            gross = s_end - btf_end - surv_total
            if gross < -1e-9:
                raise FinancingSurplus(
                    f"{sc.name} {year}: redemptions and the bill stock exceed the financing need by "
                    f"{-gross:.1f} EUR bn — buybacks and cash balances are not modelled")
            gross = max(gross, 0.0)
            if rule == "constant_profile":
                gap = target - surv
                positive = gap.clip(lower=0.0)
                deviation = float((-gap.clip(upper=0.0)).sum())
                issue = positive * (gross / positive.sum()) if positive.sum() > 0 else positive * 0.0
            else:
                deviation = 0.0
                issue = mix_w * gross
            return s_end, btf_end, gross, issue, deviation

        if bridge:
            # The register already holds the issuance to the snapshot, so only
            # the remainder of the year is financed here, and the whole year's
            # interest — including the in-year interest on that remainder — is
            # the strict matrix's figure (EC AMECO). Nothing is added to it
            # (D-S18-005: adding the new-issuance half-year counted it twice).
            gg_interest = base.gg_interest_2026_bn
            register_interest = gg_interest - wedge
            deficit = -pb / 100 * gdp + gg_interest - recv
            new_year_interest = 0.0
            d_fin = deficit
            s_end, btf_end, gross, issue, deviation = financing(d_fin)
            bill_interest = 0.5 * (btf_prev + btf_end) * bill_rate * share   # post-snapshot, informative
        else:
            d0 = -pb / 100 * gdp + existing_interest + wedge - recv
            fin_given = financing_interest is not None and year in financing_interest.index
            deficit = d0
            for _ in range(200):
                d_fin = (-pb / 100 * gdp + float(financing_interest.loc[year]) - recv) if fin_given else deficit
                s_end, btf_end, gross, issue, deviation = financing(d_fin)
                bill_interest = 0.5 * (btf_prev + btf_end) * bill_rate
                # issuance within the year pays half a year: the deficit it adds
                # to is the deficit it is sized on — a fixed point
                new_year_interest = float(sum(issue[b] * 0.5 * y_new[b] for b in BUCKETS))
                d_next = d0 + bill_interest + new_year_interest
                if abs(d_next - deficit) < 1e-10:
                    deficit = d_next
                    break
                deficit = d_next
            else:                                     # pragma: no cover
                raise RuntimeError(f"{sc.name} {year}: the financing fixed point did not converge")
            d_fin = (-pb / 100 * gdp + float(financing_interest.loc[year]) - recv) if fin_given else deficit
            s_end, btf_end, gross, issue, deviation = financing(d_fin)
            register_interest = existing_interest + bill_interest + new_year_interest
            gg_interest = register_interest + wedge
        net_issuance = a * d_fin * share

        # book the new tranches
        for b in BUCKETS:
            if issue[b] > 1e-12:
                new.append({"issue_year": year, "nominal": float(issue[b]), "coupon": y_new[b],
                            "maturity_year": year + years_of[b], "bucket": b})
        debt += deficit
        stock = s_end
        assert abs(stock - (surv_total + float(issue.sum()) + btf_end)) < 1e-6
        stock_bonds_fixed = float(nominal[fixed & surviving].sum())
        cpn_bonds = float((nominal * coupon)[fixed & surviving].sum())
        stock_new = sum(t["nominal"] for t in new if t["maturity_year"] > year)
        cpn_new = sum(t["nominal"] * t["coupon"] for t in new if t["maturity_year"] > year)
        avg_coupon_fixed = (100 * (cpn_bonds + cpn_new) / (stock_bonds_fixed + stock_new)
                            if stock_bonds_fixed + stock_new else np.nan)
        wam = float(sum(issue[b] * tenor_of[b] for b in BUCKETS) / gross) if gross > 0 else np.nan
        avg_yield = float(sum(issue[b] * y_new[b] for b in BUCKETS) / gross) if gross > 0 else np.nan
        profile_end = pd.concat([pd.Series({"bill": btf_end}), surv + issue]) / stock

        rows.append({
            "scenario": sc.name, "label": sc.label, "year": year, "gdp_bn": gdp,
            "primary_balance_pct": pb, "primary_balance_bn": pb_of[year], "spread_bp": spread,
            "oat_10y_pct": oat_yield(10, spread, base), "avg_new_yield_pct": 100 * avg_yield,
            "issuance_rule": rule, "mlt_avg_maturity_at_issue": wam,
            "redemptions_bn": redemptions, "net_issuance_bn": net_issuance,
            "mlt_gross_issuance_bn": gross, "btf_stock": btf_end,
            "bill_share_of_stock": btf_end / stock, "profile_deviation_bn": deviation,
            "linker_index_factor": f_end,
            "register_interest_bn": register_interest, "gg_interest_bn": gg_interest,
            "gg_interest_pct_gdp": 100 * gg_interest / gdp,
            "deficit_bn": deficit, "deficit_pct_gdp": 100 * deficit / gdp,
            "debt_bn": debt, "debt_pct_gdp": 100 * debt / gdp,
            "negotiable_stock_bn": stock, "avg_coupon_fixed_pct": avg_coupon_fixed,
            "coupon_fixed_bn": coupon_fixed, "coupon_linker_bn": coupon_link,
            "uplift_bn": uplift_accr, "bill_interest_bn": bill_interest,
            "premium_amort_bn": prem_amort, "new_issue_interest_bn": new_year_interest,
            **{f"profile_{b}": float(profile_end[b]) for b in ["bill", *BUCKETS]},
        })
        stock_prev, btf_prev = stock, btf_end
    return pd.DataFrame(rows)


def run_all(scenarios=SCENARIOS, base: Baseline = BASELINE, feedback: bool = True) -> pd.DataFrame:
    """The scenarios requested, in the order requested. The reference (status
    quo) path is resolved whenever the debt-ratio spread feedback is live,
    whether or not it is among the scenarios requested; with the feedback at
    zero (the default) nothing depends on it."""
    reg = load_register()
    mix = issuance_mix()
    ref = None
    if feedback and base.spread_feedback_bp_per_pp != 0.0:
        ref_sc = next((s for s in scenarios if s.name == REFERENCE), None) or scenario(REFERENCE)
        ref = run_scenario(ref_sc, base, reg, mix, feedback=False).set_index("year").debt_pct_gdp
    out = [run_scenario(sc, base, reg, mix, feedback=feedback and sc.name != REFERENCE,
                        baseline_debt_pct=ref) for sc in scenarios]
    return pd.concat(out, ignore_index=True)


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
