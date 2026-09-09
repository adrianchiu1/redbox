"""DEBT_KICKOFF.md §7 — interest by security, both bases (DD3).

Pure functions over the canonical frames plus daily reference/index-ratio
series. No I/O. Conventions:

- 7.1 daily nominal path: latest office snapshot on or before the day,
  rolled forward by recorded flows (settlement date); a later snapshot that
  disagrees with the rolled value produces an `implied` flow (grade B) on
  the snapshot date, returned to the caller for logging (V30).
- 7.2 accrued coupon: actual/actual ICMA — each coupon period accrues
  coupon/frequency × nominal, spread evenly over the days of that period;
  a calendar year collects the days that fall in it. Short/long first
  periods accrue at the regular daily rate of a full period (documented
  simplification; the office's published cash coupon governs `cash`).
- 7.3 cash coupon: on each dividend date, coupon/frequency × nominal on
  that date × index ratio on that date (linkers).
- 7.4 uplift: accrued = Σ_d N(d−1)·(IR(d) − IR(d−1)); cash = (IR(maturity)
  − 1)·N at redemption.
- 7.5 bills: discount (nominal − cash) accreted linearly over the life.
- 7.6 floaters: coupon per period = (fixing at the period's reset date +
  spread) / frequency × nominal; fixing from the reference series named
  on the security; missing fixing → `not_computable` (DD10).
- 7.7 premium/discount: per issuance flow with a price, (price − 100)/100
  × nominal, amortised straight-line to maturity, reported separately.
"""

from __future__ import annotations

import dataclasses
import re

import numpy as np
import pandas as pd

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# ---------------------------------------------------------------- schedules

def parse_dividend_dates(text: str | None, maturity: pd.Timestamp | None,
                         frequency: int) -> list[tuple[int, int]]:
    """'22 Apr/Oct' -> [(22, 4), (22, 10)]; '25 Jul' -> [(25, 7)]. Falls back
    to the maturity anniversary spread by 12/frequency months."""
    if text:
        m = re.match(r"\s*(\d{1,2})\s+([A-Za-z]{3})(?:/([A-Za-z]{3}))*", text)
        if m:
            day = int(m.group(1))
            months = [MONTHS[x.lower()] for x in re.findall(r"[A-Za-z]{3}", text)]
            return sorted((day, mo) for mo in months)
    if maturity is None or pd.isna(maturity):
        raise ValueError("dividend dates unknown and no maturity to derive them from")
    step = 12 // frequency
    months = sorted(((maturity.month - 1 - k * step) % 12) + 1 for k in range(frequency))
    return [(maturity.day, mo) for mo in months]


def coupon_dates(security: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    """All dividend dates in [start, end] for the security."""
    freq = int(security["coupon_frequency"]) if pd.notna(security.get("coupon_frequency")) else 2
    pairs = parse_dividend_dates(security.get("dividend_dates"), security.get("maturity_date"), freq)
    out = []
    for year in range(start.year, end.year + 1):
        for day, month in pairs:
            try:
                d = pd.Timestamp(year=year, month=month, day=day)
            except ValueError:            # 29/30/31 in a short month
                d = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
            if start <= d <= end:
                out.append(d)
    mat = security.get("maturity_date")
    if pd.notna(mat) and start <= mat <= end and mat not in out:
        out.append(pd.Timestamp(mat))
    return sorted(out)


def coupon_period_bounds(security: pd.Series, day: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(previous dividend date, next dividend date] containing `day`."""
    freq = int(security["coupon_frequency"]) if pd.notna(security.get("coupon_frequency")) else 2
    pairs = parse_dividend_dates(security.get("dividend_dates"), security.get("maturity_date"), freq)
    cands = []
    for year in (day.year - 1, day.year, day.year + 1):
        for d_, mo in pairs:
            try:
                cands.append(pd.Timestamp(year=year, month=mo, day=d_))
            except ValueError:
                cands.append(pd.Timestamp(year=year, month=mo, day=1) + pd.offsets.MonthEnd(0))
    cands = sorted(cands)
    prev = max(c for c in cands if c <= day)
    nxt = min(c for c in cands if c > day)
    return prev, nxt


# ------------------------------------------------------------ nominal path

@dataclasses.dataclass
class ImpliedFlow:
    security_id: str
    date: pd.Timestamp
    nominal_lcu_mn: float
    rolled: float
    snapshot: float


def nominal_path(security_id: str, positions: pd.DataFrame, flows: pd.DataFrame,
                 start: pd.Timestamp, end: pd.Timestamp,
                 tolerance_mn: float = 0.5) -> tuple[pd.Series, list[ImpliedFlow]]:
    """Daily nominal outstanding on [start, end] (§7.1). Positions and flows
    are already filtered to one country. Returns (series, implied flows)."""
    pos = positions[positions["security_id"] == security_id].sort_values("as_of")
    fl = flows[(flows["security_id"] == security_id)
               & (~flows["flow_type"].isin(["retention", "own_book_sale", "own_book_purchase"]))]
    signed = fl.assign(_s=np.where(fl["flow_type"].isin(
        ["redemption", "buyback", "conversion_out", "switch_out"]), -1.0, 1.0))
    signed = signed.assign(_v=signed["nominal_lcu_mn"] * signed["_s"])
    daily_flow = signed.groupby("settlement_date")["_v"].sum()

    days = pd.date_range(start, end, freq="D")
    out = pd.Series(np.nan, index=days)
    implied: list[ImpliedFlow] = []

    if pos.empty:
        # no snapshot at all: build from flows only (first flow starts the path)
        level, prev = 0.0, None
        for d in days:
            level += float(daily_flow.get(d, 0.0))
            out[d] = level
        return out, implied

    anchor_rows = pos[pos["as_of"] <= start]
    if anchor_rows.empty:
        anchor_date, level = None, 0.0
    else:
        a = anchor_rows.iloc[-1]
        anchor_date, level = a["as_of"], float(a["nominal_lcu_mn"])
        # roll from the anchor date up to start-1
        for d, v in daily_flow.items():
            if anchor_date < d < start:
                level += float(v)
    snaps = pos[(pos["as_of"] >= start) & (pos["as_of"] <= end)].set_index("as_of")["nominal_lcu_mn"]
    for d in days:
        level += float(daily_flow.get(d, 0.0))
        if d in snaps.index:
            snap = float(snaps[d])
            if abs(snap - level) > tolerance_mn:
                implied.append(ImpliedFlow(security_id, d, snap - level, level, snap))
            level = snap
        out[d] = level
    return out, implied


# --------------------------------------------------------- daily references

def daily_index_ratio(ratios: pd.DataFrame, security_id: str,
                      start: pd.Timestamp, end: pd.Timestamp) -> pd.Series | None:
    """Daily index-ratio series for a linker from the ratio table (office
    values first, recomputed where the office has none), forward-filled."""
    r = ratios[ratios["security_id"] == security_id]
    if r.empty:
        return None
    office = r[r["ratio_source"] == "office"].set_index("date")["index_ratio"]
    recomp = r[r["ratio_source"] == "recomputed"].set_index("date")["index_ratio"]
    s = office.combine_first(recomp).sort_index()
    days = pd.date_range(min(start - pd.Timedelta(days=1), s.index.min()), end, freq="D")
    return s.reindex(days).interpolate(method="time").ffill().bfill()


# ------------------------------------------------------------ computations

def _year_bounds(year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    return pd.Timestamp(year=year, month=1, day=1), pd.Timestamp(year=year, month=12, day=31)


def accrued_coupon(security: pd.Series, path: pd.Series, year: int) -> float:
    """§7.2 actual/actual ICMA on the daily nominal path."""
    if security["instrument_class"] in ("bill",) or pd.isna(security.get("coupon_pct")):
        return 0.0
    c = float(security["coupon_pct"]) / 100.0
    f = int(security["coupon_frequency"]) if pd.notna(security.get("coupon_frequency")) else 2
    y0, y1 = _year_bounds(year)
    total = 0.0
    cache: dict[tuple, int] = {}
    for d in pd.date_range(y0, y1, freq="D"):
        n = float(path.get(d, 0.0))
        if n == 0.0:
            continue
        prev, nxt = coupon_period_bounds(security, d)
        key = (prev, nxt)
        if key not in cache:
            cache[key] = (nxt - prev).days
        total += c / f * n / cache[key]
    return total


def cash_coupon(security: pd.Series, path: pd.Series, year: int,
                ir: pd.Series | None = None) -> float:
    """§7.3 on each dividend date: coupon/frequency × nominal (× IR)."""
    if security["instrument_class"] == "bill" or pd.isna(security.get("coupon_pct")):
        return 0.0
    c = float(security["coupon_pct"]) / 100.0
    f = int(security["coupon_frequency"]) if pd.notna(security.get("coupon_frequency")) else 2
    y0, y1 = _year_bounds(year)
    total = 0.0
    for d in coupon_dates(security, y0, y1):
        # nominal on the day before payment (redemption flows settle on the date itself)
        n = float(path.get(d - pd.Timedelta(days=1), path.get(d, 0.0)))
        ratio = float(ir.get(d, np.nan)) if ir is not None else 1.0
        if ir is not None and np.isnan(ratio):
            ratio = float(ir.ffill().get(d, 1.0))
        total += c / f * n * ratio
    return total


def uplift(security: pd.Series, path: pd.Series, ir: pd.Series | None, year: int,
           basis: str) -> float | None:
    """§7.4. None when the security is a linker without ratios (→ not_computable)."""
    if security["instrument_class"] != "inflation_linked":
        return 0.0
    if ir is None:
        return None
    y0, y1 = _year_bounds(year)
    if basis == "accrued":
        total = 0.0
        prev = y0 - pd.Timedelta(days=1)
        for d in pd.date_range(y0, y1, freq="D"):
            n_prev = float(path.get(prev, 0.0))
            total += n_prev * (float(ir.get(d, np.nan)) - float(ir.get(prev, np.nan)))
            prev = d
        return 0.0 if np.isnan(total) else total
    mat = security.get("maturity_date")
    if pd.notna(mat) and y0 <= mat <= y1:
        n = float(path.get(mat - pd.Timedelta(days=1), 0.0))
        return n * (float(ir.ffill().get(mat, 1.0)) - 1.0)
    return 0.0


def bill_discount(security: pd.Series, flows: pd.DataFrame, year: int, basis: str) -> float:
    """§7.5: each issuance flow's discount (nominal − cash), accreted
    linearly from settlement to maturity (accrued) or at maturity (cash)."""
    if security["instrument_class"] != "bill":
        return 0.0
    fl = flows[(flows["security_id"] == security["security_id"])
               & (flows["flow_type"].isin(["auction", "tender", "tap", "syndication"]))
               & flows["cash_lcu_mn"].notna()]
    mat = security.get("maturity_date")
    if fl.empty or pd.isna(mat):
        return 0.0
    y0, y1 = _year_bounds(year)
    total = 0.0
    for _, r in fl.iterrows():
        disc = float(r["nominal_lcu_mn"]) - float(r["cash_lcu_mn"])
        s = pd.Timestamp(r["settlement_date"])
        life = (mat - s).days
        if life <= 0:
            continue
        if basis == "cash":
            total += disc if y0 <= mat <= y1 else 0.0
        else:
            overlap = (min(mat, y1) - max(s, y0 - pd.Timedelta(days=1))).days
            total += disc * max(0, min(overlap, life)) / life
    return total


def floating_coupon(security: pd.Series, path: pd.Series, year: int,
                    reference: pd.Series | None, basis: str) -> float | None:
    """§7.6: fixing at the start of each coupon period + spread. None when
    the reference series is missing for any period (DD10)."""
    if security["instrument_class"] != "floating":
        return 0.0
    if reference is None or reference.empty:
        return None
    f = int(security["coupon_frequency"]) if pd.notna(security.get("coupon_frequency")) else 4
    spread = float(security.get("spread_bp") or 0.0) / 10000.0
    y0, y1 = _year_bounds(year)
    ref = reference.sort_index()

    def fixing(on: pd.Timestamp) -> float | None:
        s = ref[ref.index <= on]
        if s.empty or (on - s.index[-1]).days > 45:
            return None
        return float(s.iloc[-1]) / 100.0

    total = 0.0
    if basis == "cash":
        for d in coupon_dates(security, y0, y1):
            prev, _ = coupon_period_bounds(security, d - pd.Timedelta(days=1))
            fx = fixing(prev)
            if fx is None:
                return None
            n = float(path.get(d - pd.Timedelta(days=1), 0.0))
            total += (fx + spread) / f * n
        return total
    cache: dict = {}
    for d in pd.date_range(y0, y1, freq="D"):
        n = float(path.get(d, 0.0))
        if n == 0.0:
            continue
        prev, nxt = coupon_period_bounds(security, d)
        if prev not in cache:
            cache[prev] = (fixing(prev), (nxt - prev).days)
        fx, days = cache[prev]
        if fx is None:
            return None
        total += (fx + spread) / f * n / days
    return total


def premium_discount_amortisation(security: pd.Series, flows: pd.DataFrame, year: int) -> float:
    """§7.7: Σ over priced issuance flows of (price − 100)/100 × nominal,
    straight-line from settlement to maturity; positive = premium (reduces
    ESA interest), reported as a separate component with that sign."""
    fl = flows[(flows["security_id"] == security["security_id"])
               & (flows["flow_type"].isin(["auction", "tender", "tap", "syndication"]))
               & flows["price_pct"].notna()]
    mat = security.get("maturity_date")
    if fl.empty or pd.isna(mat):
        return 0.0
    y0, y1 = _year_bounds(year)
    total = 0.0
    for _, r in fl.iterrows():
        prem = (float(r["price_pct"]) - 100.0) / 100.0 * float(r["nominal_lcu_mn"])
        s = pd.Timestamp(r["settlement_date"])
        life = (mat - s).days
        if life <= 0:
            continue
        overlap = (min(mat, y1) - max(s, y0 - pd.Timedelta(days=1))).days
        total += prem * max(0, min(overlap, life)) / life
    return total


def interest_for_security(security: pd.Series, positions: pd.DataFrame,
                          flows: pd.DataFrame, year: int,
                          ratios: pd.DataFrame | None = None,
                          reference: pd.Series | None = None) -> list[dict]:
    """Both bases for one security-year (§5.6 rows without provenance)."""
    y0, y1 = _year_bounds(year)
    sid = security["security_id"]
    path, implied = nominal_path(sid, positions, flows, y0 - pd.Timedelta(days=1), y1)
    ir = daily_index_ratio(ratios, sid, y0, y1) if (ratios is not None
                                                     and security["instrument_class"] == "inflation_linked") else None
    rows = []
    for basis in ("accrued", "cash"):
        coupon = accrued_coupon(security, path, year) if basis == "accrued" else cash_coupon(security, path, year, ir)
        up = uplift(security, path, ir, year, basis)
        disc = bill_discount(security, flows, year, basis)
        flo = floating_coupon(security, path, year, reference, basis)
        pd_amort = premium_discount_amortisation(security, flows, year) if basis == "accrued" else 0.0
        not_comp = up is None or flo is None
        if security["instrument_class"] == "floating":
            coupon = 0.0
        total = None if not_comp else coupon + (up or 0.0) + disc + (flo or 0.0) - pd_amort
        rows.append({
            "iso3": security["iso3"], "security_id": sid, "year": year, "basis": basis,
            "coupon_lcu_mn": coupon, "uplift_lcu_mn": up, "discount_lcu_mn": disc,
            "floating_lcu_mn": flo, "premium_discount_amort_lcu_mn": pd_amort,
            "total_lcu_mn": total,
            "computability": "not_computable" if not_comp else "computed",
            "reference_values_used": _refs_used(security, ir, reference, y0, y1),
            "derivation": _derivation(security, basis, coupon, up, disc, flo, pd_amort, path, y0, y1),
            "implied_flows": implied,
        })
    return rows


def _refs_used(security, ir, reference, y0, y1) -> str | None:
    parts = []
    if ir is not None:
        parts.append(f"index_ratio {ir.get(y0 - pd.Timedelta(days=1), np.nan):.5f}->{ir.get(y1, np.nan):.5f}")
    if reference is not None and security["instrument_class"] == "floating":
        parts.append(f"{security.get('floating_reference')} fixings")
    return "; ".join(parts) or None


def _derivation(security, basis, coupon, up, disc, flo, pd_amort, path, y0, y1) -> str:
    n0, n1 = float(path.get(y0, 0.0)), float(path.get(y1, 0.0))
    bits = [f"{basis}: nominal {n0:,.1f}->{n1:,.1f}"]
    if security["instrument_class"] == "floating":
        bits.append("floating coupon " + ("not computable" if flo is None else f"{flo:,.2f}"))
    elif security["instrument_class"] != "bill":
        bits.append(f"coupon {security.get('coupon_pct')}% x{security.get('coupon_frequency')} = {coupon:,.2f}")
    if security["instrument_class"] == "inflation_linked":
        bits.append("uplift " + ("not computable" if up is None else f"{up:,.2f}"))
    if security["instrument_class"] == "bill":
        bits.append(f"discount {disc:,.2f}")
    if pd_amort:
        bits.append(f"premium/discount amortisation {pd_amort:,.2f}")
    return "; ".join(bits)
