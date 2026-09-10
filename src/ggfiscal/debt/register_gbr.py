"""GBR per-security register (DEBT_KICKOFF.md §3–§5, §14 GBR) from the UK Debt
Management Office reports (readers.dmo).

``build(run_id)`` returns the four canonical frames for iso3 ``GBR``:

===================== ===================================================
``debt_securities``   every gilt in the DMO's three lists — in issue (D1A),
                      redeemed since 1981 (D1C), with an operation since 1981
                      (D2.1E) — plus one Treasury bill per maturity date in the
                      tender history (D2.2D, from April 2000)
``debt_positions``    the office's latest close of business for gilts in issue
                      (``office_snapshot``, D1A) and every 31 December from 1981
                      rolled from the flows (``rolled_from_flows``)
``debt_flows``        every operation of the issuance history (D2.1E), one
                      ``redemption`` per redeemed gilt at its D1C nominal, every
                      bill tender with its price and a ``redemption`` at par,
                      and — where the recorded operations do not add up to the
                      anchor — one ``implied`` opening flow at 1981-01-01
``debt_index_ratios`` the office's current-month ratios (D10C, ``office``) and
                      the ratios recomputed from the ONS RPI (``recomputed``)
                      for the life of every index-linked gilt
===================== ===================================================

All amounts are GBP millions nominal (uplift is carried separately).

How the positions are obtained (DD13: no scaling, no plugging):

* The DMO publishes no historical positions table by URL (its year-end
  snapshots ignore the date parameter), but it does publish the complete
  operations record since 1981 and two anchors — the nominal in issue today
  (D1A) and the nominal outstanding at redemption for every gilt redeemed
  since 1981 (D1C). A gilt's history is therefore the anchor walked back
  through its operations; verified live 2026-09-10: Σ operations reproduces
  the D1A amount for 102 of 104 gilts in issue within £1 mn.
* Where Σ operations falls short of the anchor the difference was created by
  an operation the history does not carry (a pre-1981 issue, or one of the
  early-1990s tenders the D2.1E extract omits). That difference is written as
  one ``implied`` flow dated 1981-01-01 — never allocated to a later date —
  and the security's positions are graded C until its first recorded
  operation and B after it.
* Gilts with no recorded operation at all (the older stocks) carry their D1C
  redemption nominal from 1981-01-01 to redemption (grade B: a gilt without
  an operation since 1981 has been constant since 1981).
* Tranches (``8½% Treasury Loan 2007 A``) are folded into their parent: the
  DMO lists them as separate ISINs while partly paid and assimilates them on
  the parent afterwards; D1C and D1A carry the parent only.

Index ratios: the DMO's 3-month-lag formula (reference RPI on day *d* =
RPI(m−3) + (d−1)/days(m) × (RPI(m−2) − RPI(m−3)); ratio = reference RPI /
reference RPI at first issue) is reproduced from the ONS RPI to 5 decimals
against every D10C row (verified 2026-09-10), so ``recomputed`` monthly points
(the formula is linear within the month, which is exactly how the engine
interpolates) cover each linker's whole life. 8-month-lag gilts use
RPI(m−8) / RPI(issue month − 8), a monthly step.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ggfiscal.debt.model import FLOWS, INDEX_RATIOS, POSITIONS, SECURITIES
from ggfiscal.debt.readers import dmo as D

ISO3 = "GBR"
SOURCE_GILTS = D.SOURCE_GILTS
SOURCE_BILLS = D.SOURCE_BILLS
INDEX_REFERENCE = "UK_RPI"
#: First date of the register window: the D1C redemption history starts
#: 1981-01-15 and the D2.1E operations record 1981-03-27.
REGISTER_START = pd.Timestamp("1981-01-01")
#: Tolerance (GBP mn) below which Σ operations counts as reproducing the anchor.
STUB_TOL_MN = 0.5

#: D2.1E issuance type -> flow_type (sign decides *_in / *_out where listed).
ISSUANCE_TYPE = {
    "Outright": ("auction", "auction"),
    "Syndication": ("syndication", "syndication"),
    "Cancellation": ("buyback", "buyback"),
    "Cancellation from 12-Oct-99 Switch Auction": ("switch_out", "switch_out"),
    "Reverse Auction": ("buyback", "buyback"),
    "Conversion": ("conversion_in", "conversion_out"),
    "Switch Auction": ("switch_in", "switch_out"),
    "Special Switch Facility": ("switch_in", "switch_out"),
    "Cancellation Adjustment": ("auction", "buyback"),
}
ISSUANCE_NOTE = {
    "Outright": "Outright issuance as published (auction, tap or post-auction option facility)",
    "Cancellation": "Cancellation as published (stock bought in and cancelled)",
}


# ------------------------------------------------------------- RPI / ratios

def _rpi() -> pd.Series:
    from ggfiscal.debt.readers import ons_hmt as O
    s = O.rpi_index().copy()
    s.index = pd.to_datetime(s.index).to_period("M").to_timestamp()
    return s.sort_index()


def reference_rpi_3m(day: pd.Timestamp, rpi: pd.Series) -> float:
    """DMO 3-month-lag reference RPI for a settlement day."""
    day = pd.Timestamp(day)
    m3 = (day - pd.DateOffset(months=3)).to_period("M").to_timestamp()
    m2 = (day - pd.DateOffset(months=2)).to_period("M").to_timestamp()
    if m3 not in rpi.index or m2 not in rpi.index:
        return np.nan
    return float(rpi[m3] + (day.day - 1) / day.days_in_month * (rpi[m2] - rpi[m3]))


def reference_rpi_8m(day: pd.Timestamp, rpi: pd.Series) -> float:
    m8 = (pd.Timestamp(day) - pd.DateOffset(months=8)).to_period("M").to_timestamp()
    return float(rpi[m8]) if m8 in rpi.index else np.nan


def _ratio_points(first_issue: pd.Timestamp, end: pd.Timestamp, lag: float,
                  rpi: pd.Series) -> pd.DataFrame:
    """Monthly (date, reference_index, index_ratio) points from first issue
    to `end`; the first point is the issue date itself (ratio 1)."""
    ref = reference_rpi_3m if lag == 3.0 else reference_rpi_8m
    base = ref(first_issue, rpi)
    if np.isnan(base):
        return pd.DataFrame(columns=["date", "reference_index", "index_ratio"])
    months = pd.date_range((first_issue + pd.offsets.MonthBegin(1)).normalize(), end, freq="MS")
    dates = [pd.Timestamp(first_issue)] + list(months)
    refs = [ref(d, rpi) for d in dates]
    out = pd.DataFrame({"date": dates, "reference_index": refs})
    out = out[out["reference_index"].notna()]
    out["index_ratio"] = out["reference_index"] / base
    return out.reset_index(drop=True)


# ------------------------------------------------------------- gilt master

def _slug(name: str) -> str:
    text = name
    for k, v in D.FRACTIONS.items():
        text = text.replace(k, v.strip().replace("/", "-"))
    text = text.replace("%", "pct")
    return "GBGILT-" + re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def gilt_master() -> pd.DataFrame:
    """One row per gilt (tranches folded): key, security_id, isin, name, class
    fields, anchors, and the ISINs whose operations belong to it."""
    g = D.gilts_in_issue()
    h = D.issuance_history()
    r = D.redemptions()
    g["key"] = g["name"].map(D.name_key)
    r["key"] = r["name"].map(D.name_key)
    h["key"] = h["name"].map(D.name_key)
    h["tranche"] = h["name"].map(lambda n: D.parse_name(n)["tranche"])

    # parent ISIN per key: the non-tranche ISIN in the operations record
    parents = (h[h["tranche"].isna()].drop_duplicates("isin")
               .groupby("key")["isin"].first())
    tranche_isins = (h[h["tranche"].notna()].drop_duplicates("isin")
                     .groupby("key")["isin"].apply(list))
    lag = h.groupby("key")["indexation_lag"].agg(lambda s: next((x for x in s if isinstance(x, str) and x), None))
    first_op = h.groupby("key")["date"].min()

    keys = list(dict.fromkeys(list(g["key"]) + list(r["key"]) + list(h["key"])))
    gi = g.set_index("key")
    ri = r.drop_duplicates("key").set_index("key")
    rows = []
    for k in keys:
        in_issue = k in gi.index
        redeemed = k in ri.index
        name = (gi.loc[k, "name"] if in_issue else ri.loc[k, "name"] if redeemed
                else h[h["key"] == k]["name"].map(lambda n: D.parse_name(n)["base_name"]).iloc[0])
        p = D.parse_name(name)
        isin = gi.loc[k, "isin"] if in_issue else parents.get(k)
        if isin is None and k in tranche_isins.index and not in_issue and not redeemed:
            isin = tranche_isins[k][0]
        itype = gi.loc[k, "instrument_type"] if in_issue else None
        lag_m = (3.0 if itype == "Index-linked 3 months" else 8.0 if itype == "Index-linked 8 months"
                 else 3.0 if lag.get(k) == "3 months" else 8.0 if lag.get(k) == "8 months"
                 else (8.0 if p["is_linker"] else np.nan))
        if p["is_linker"]:
            klass, sub = "inflation_linked", ("gilts_index_linked_3m" if lag_m == 3.0 else "gilts_index_linked_8m")
        elif p["is_floating"]:
            klass, sub = "floating", "gilts_floating"
        elif not p["years"]:
            klass, sub = "fixed_bullet", "gilts_undated"
        else:
            klass, sub = "fixed_bullet", "gilts_conventional"
        maturity = (gi.loc[k, "redemption_date"] if in_issue else ri.loc[k, "redemption_date"] if redeemed else None)
        rows.append({
            "key": k, "security_id": isin or _slug(name), "isin": isin, "name": name,
            "instrument_class": klass, "sub_type": sub, "coupon_pct": p["coupon_pct"],
            "index_lag_months": lag_m, "is_double_dated": len(p["years"]) == 2,
            "first_issue_date": (gi.loc[k, "first_issue_date"] if in_issue else first_op.get(k)),
            "maturity_date": maturity,
            "dividend_dates": gi.loc[k, "dividend_dates"] if in_issue else None,
            "in_issue": in_issue, "redeemed": redeemed,
            "anchor_date": (gi.loc[k, "cob_date"] if in_issue else ri.loc[k, "redemption_date"] if redeemed else None),
            "anchor_mn": (gi.loc[k, "amount_mn"] if in_issue else ri.loc[k, "nominal_mn"] if redeemed else None),
            "anchor_uplifted_mn": gi.loc[k, "amount_uplifted_mn"] if in_issue else None,
            "tranche_isins": tranche_isins.get(k, []),
            "has_operations": k in set(h["key"]),
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ flows

def _gilt_operation_rows(master: pd.DataFrame) -> list[dict]:
    h = D.issuance_history()
    h["key"] = h["name"].map(D.name_key)
    sid = master.set_index("key")["security_id"]
    parent_isin = master.set_index("key")["isin"]
    rows = []
    for r in h.itertuples(index=False):
        n = r.nominal_mn
        if n is None or pd.isna(n):
            continue
        if r.issuance_type not in ISSUANCE_TYPE:
            raise KeyError(f"unmapped D2.1E issuance type (extend ISSUANCE_TYPE): {r.issuance_type!r}")
        pos_type, neg_type = ISSUANCE_TYPE[r.issuance_type]
        if abs(n) < 1e-3:
            continue                                     # the two 'Cancellation Adjustment' rows of £400
        flow_type = pos_type if n > 0 else neg_type
        notes = [ISSUANCE_NOTE.get(r.issuance_type, f"{r.issuance_type} as published")]
        if parent_isin.get(r.key) != r.isin:
            notes.append(f"tranche {r.name!r} (ISIN {r.isin}) folded into the parent")
        cash = abs(n) * r.price_pct / 100.0 if r.price_pct is not None and pd.notna(r.price_pct) else None
        rows.append({
            "security_id": sid[r.key], "settlement_date": r.date, "operation_date": r.date,
            "flow_type": flow_type, "nominal_lcu_mn": abs(float(n)), "cash_lcu_mn": cash,
            "price_pct": r.price_pct if pd.notna(r.price_pct) else None,
            "yield_pct": r.yield_pct if pd.notna(r.yield_pct) else None,
            "method": r.issuance_type, "counter_security_id": None,
            "source_id": SOURCE_GILTS, "part": D.PART_ISSUANCE, "grade": "A",
            "notes": "; ".join(notes) + ("; cash = nominal × clean price (accrued interest not included)"
                                         if cash is not None else ""),
        })
    return rows


def _gilt_redemption_rows(master: pd.DataFrame) -> list[dict]:
    rows = []
    for m in master[master["redeemed"]].itertuples(index=False):
        rows.append({
            "security_id": m.security_id, "settlement_date": m.anchor_date, "operation_date": m.anchor_date,
            "flow_type": "redemption", "nominal_lcu_mn": float(m.anchor_mn), "cash_lcu_mn": None,
            "price_pct": None, "yield_pct": None, "method": "Redemption",
            "counter_security_id": None, "source_id": SOURCE_GILTS, "part": D.PART_REDEMPTIONS,
            "grade": "A", "notes": "D1C: nominal outstanding at redemption as published"
                                   + ("; double-dated stock redeemed on this date" if m.is_double_dated else ""),
        })
    return rows


SIGN = {"auction": 1, "syndication": 1, "tap": 1, "tender": 1, "conversion_in": 1, "switch_in": 1,
        "redemption": -1, "buyback": -1, "conversion_out": -1, "switch_out": -1, "implied": 1,
        "retention": 0, "own_book_sale": 0, "own_book_purchase": 0}


def _opening_rows(master: pd.DataFrame, ops: list[dict]) -> tuple[list[dict], dict]:
    """One `implied` flow at REGISTER_START per gilt whose recorded operations
    do not reproduce its anchor. Returns (rows, stub per security_id)."""
    df = pd.DataFrame(ops)
    # the anchor of a redeemed gilt is its redemption nominal, so the
    # redemption flow itself stays out of the sum that is compared to it
    df = df[df["flow_type"] != "redemption"]
    signed = (df["nominal_lcu_mn"] * df["flow_type"].map(SIGN)).groupby(df["security_id"]).sum() \
        if len(df) else pd.Series(dtype=float)
    rows, stubs = [], {}
    for m in master.itertuples(index=False):
        if m.anchor_mn is None or pd.isna(m.anchor_mn):
            continue
        stub = float(m.anchor_mn) - float(signed.get(m.security_id, 0.0))
        if abs(stub) <= STUB_TOL_MN:
            continue
        stubs[m.security_id] = stub
        why = ("no operation recorded in the DMO issuance history (from 1981): the D1C redemption "
               "nominal is carried from the register start" if not m.has_operations else
               f"Σ recorded operations ({float(signed.get(m.security_id, 0.0)):,.3f}) short of the anchor "
               f"({float(m.anchor_mn):,.3f} at {pd.Timestamp(m.anchor_date):%Y-%m-%d}) by {stub:,.3f}: "
               "created by an operation the history does not carry (pre-1981 or an omitted early tender)")
        rows.append({
            "security_id": m.security_id, "settlement_date": REGISTER_START, "operation_date": None,
            "flow_type": "implied", "nominal_lcu_mn": stub, "cash_lcu_mn": None, "price_pct": None,
            "yield_pct": None, "method": "opening stub", "counter_security_id": None,
            "source_id": SOURCE_GILTS, "part": D.PART_REDEMPTIONS if m.redeemed else D.PART_IN_ISSUE,
            "grade": "B" if not m.has_operations else "C",
            "notes": "opening amount at the register start, " + why + " (DD13: published, never allocated)",
        })
    return rows, stubs


# ------------------------------------------------------------------ bills

def bill_master() -> pd.DataFrame:
    t = D.bill_tenders()
    t = t[t["maturity_date"].notna() & t["issue_date"].notna() & t["size_mn"].notna()]
    g = t.groupby("maturity_date")
    out = pd.DataFrame({
        "maturity_date": g.size().index,
        "first_issue_date": g["issue_date"].min().values,
        "issued_mn": g["size_mn"].sum().values,
        "n_tenders": g.size().values,
        "types": g["maturity_type"].agg(lambda s: "/".join(sorted(set(s)))).values,
    })
    out["security_id"] = ["UKTB-" + pd.Timestamp(d).strftime("%Y%m%d") for d in out["maturity_date"]]
    isins = D.bills_current().set_index("maturity_date")["isin"] if D.have(SOURCE_BILLS, D.PART_BILL_CURRENT) \
        else pd.Series(dtype=str)
    out["isin"] = out["maturity_date"].map(isins)
    return out


def _bill_rows(bills: pd.DataFrame) -> list[dict]:
    t = D.bill_tenders()
    t = t[t["maturity_date"].notna() & t["issue_date"].notna() & t["size_mn"].notna()]
    sid = bills.set_index("maturity_date")["security_id"]
    rows = []
    for r in t.itertuples(index=False):
        rows.append({
            "security_id": sid[r.maturity_date], "settlement_date": r.issue_date, "operation_date": r.tender_date,
            "flow_type": "tender", "nominal_lcu_mn": float(r.size_mn),
            "cash_lcu_mn": float(r.size_mn) * r.price / 100.0 if r.price is not None and pd.notna(r.price) else None,
            "price_pct": r.price if pd.notna(r.price) else None, "yield_pct": r.yield_pct if pd.notna(r.yield_pct) else None,
            "method": f"Treasury bill tender ({r.maturity_type})", "counter_security_id": None,
            "source_id": SOURCE_BILLS, "part": D.PART_BILL_TENDERS, "grade": "A",
            "notes": "D2.2D: size and average accepted price as published; bills of one maturity date are fungible",
        })
    for b in bills.itertuples(index=False):
        rows.append({
            "security_id": b.security_id, "settlement_date": b.maturity_date, "operation_date": b.maturity_date,
            "flow_type": "redemption", "nominal_lcu_mn": float(b.issued_mn), "cash_lcu_mn": float(b.issued_mn),
            "price_pct": 100.0, "yield_pct": None, "method": "Redemption at par", "counter_security_id": None,
            "source_id": SOURCE_BILLS, "part": D.PART_BILL_TENDERS, "grade": "B",
            "notes": "derived: Σ tender sizes redeemed at par on the maturity date (the DMO publishes no "
                     "bill redemption file; bills are not bought back)",
        })
    return rows


# ------------------------------------------------------------- securities

def _provenance(run_id: str, source_id: str, part: str, grade: str, notes: str | None) -> dict:
    return {"run_id": run_id, "source_id": source_id, "snapshot_sha256": D.sha(source_id, part),
            "quality_grade": grade, "notes": notes}


def securities(run_id: str, master: pd.DataFrame, bills: pd.DataFrame, stubs: dict,
               rpi: pd.Series) -> pd.DataFrame:
    rows = []
    for m in master.itertuples(index=False):
        linker = m.instrument_class == "inflation_linked"
        base = np.nan
        if linker and m.first_issue_date is not None and pd.notna(m.first_issue_date):
            base = (reference_rpi_3m if m.index_lag_months == 3.0 else reference_rpi_8m)(m.first_issue_date, rpi)
        notes = []
        if m.tranche_isins:
            notes.append("tranches folded into this security: " + ", ".join(m.tranche_isins))
        if m.isin is None:
            notes.append("no ISIN published for this stock (D1C lists redeemed gilts by name only)")
        if m.security_id in stubs:
            notes.append(f"opening stub {stubs[m.security_id]:,.3f} at {REGISTER_START:%Y-%m-%d} (see the implied flow)")
        if m.sub_type == "gilts_undated":
            notes.append("undated stock; maturity_date is the redemption date the DMO called it on")
        if m.is_double_dated:
            notes.append("double-dated stock; maturity_date is the actual redemption date")
        if m.instrument_class == "floating":
            notes.append("floating-rate gilt (LIBID-linked); no fixing history in the reference set (DD10)")
        if linker:
            notes.append(f"{m.index_lag_months:g}-month indexation lag; base RPI = reference RPI at first issue "
                         "(Jan 1987 = 100)" + ("" if pd.notna(base) else "; first issue date unknown, no base"))
        if not m.in_issue and not m.redeemed:
            notes.append("neither in issue nor redeemed since 1981 per the DMO lists: converted or switched out in full")
        part = D.PART_IN_ISSUE if m.in_issue else D.PART_REDEMPTIONS if m.redeemed else D.PART_ISSUANCE
        rows.append({
            "iso3": ISO3, "security_id": m.security_id, "isin": m.isin, "name": m.name,
            "instrument_class": m.instrument_class, "sub_type": m.sub_type, "currency": "GBP",
            "coupon_pct": m.coupon_pct if m.instrument_class != "floating" else None,
            "coupon_frequency": 4 if "Consolidated" in m.name or m.instrument_class == "floating" else 2,
            "day_count": "ACT/ACT",
            "first_issue_date": m.first_issue_date, "maturity_date": m.maturity_date, "first_call_date": pd.NaT,
            "dividend_dates": m.dividend_dates if isinstance(m.dividend_dates, str) and m.dividend_dates else None,
            "index_reference": INDEX_REFERENCE if linker else None,
            "index_lag_months": m.index_lag_months if linker else np.nan,
            "base_index": base if linker else np.nan,
            "floating_reference": "UK_LIBID_3M" if m.instrument_class == "floating" else None,
            "spread_bp": np.nan, "is_green": False, "issuer_unit": "state",
            **_provenance(run_id, SOURCE_GILTS, part, "A" if m.isin else "B", "; ".join(notes) or None),
        })
    for b in bills.itertuples(index=False):
        rows.append({
            "iso3": ISO3, "security_id": b.security_id, "isin": b.isin if isinstance(b.isin, str) else None,
            "name": f"Treasury bill {pd.Timestamp(b.maturity_date):%d %b %Y}",
            "instrument_class": "bill", "sub_type": "treasury_bills", "currency": "GBP",
            "coupon_pct": None, "coupon_frequency": 1, "day_count": "ACT/365",
            "first_issue_date": b.first_issue_date, "maturity_date": b.maturity_date, "first_call_date": pd.NaT,
            "dividend_dates": None, "index_reference": None, "index_lag_months": np.nan, "base_index": np.nan,
            "floating_reference": None, "spread_bp": np.nan, "is_green": False, "issuer_unit": "state",
            **_provenance(run_id, SOURCE_BILLS, D.PART_BILL_TENDERS, "A",
                          f"one security per maturity date ({b.n_tenders} tender(s), tenors {b.types}); "
                          "ISIN from the current bills table where still in issue"),
        })
    df = pd.DataFrame(rows)
    return SECURITIES.validate(df.sort_values("security_id").reset_index(drop=True))


# --------------------------------------------------------------- positions

def positions(run_id: str, secs: pd.DataFrame, flows: pd.DataFrame, master: pd.DataFrame,
              ratios: pd.DataFrame, stubs: dict, end_year: int) -> pd.DataFrame:
    fl = flows.copy()
    fl["_v"] = fl["nominal_lcu_mn"] * fl["flow_type"].map(SIGN).fillna(0)
    year_ends = pd.date_range(f"{REGISTER_START.year}-12-31", f"{end_year}-12-31", freq="YE")
    terms = secs.set_index("security_id")
    first_op = fl[fl["flow_type"] != "implied"].groupby("security_id")["settlement_date"].min()
    ratio_lookup = _ratio_series(ratios)
    rows = []
    for sid, g in fl.groupby("security_id"):
        g = g.sort_values("settlement_date")
        cum = g.groupby("settlement_date")["_v"].sum().cumsum()
        mat = terms.loc[sid, "maturity_date"]
        klass = terms.loc[sid, "instrument_class"]
        start = cum.index.min()
        for d in year_ends:
            if d < start or (pd.notna(mat) and d >= mat):
                continue
            level = float(cum[cum.index <= d].iloc[-1])
            if abs(level) < 1e-6:
                continue
            grade, note = "A", "rolled from the recorded operations"
            if sid in stubs:
                fo = first_op.get(sid)
                if fo is None or pd.isna(fo):
                    grade, note = "B", "constant at the D1C redemption nominal: no operation recorded since 1981"
                elif d < fo:
                    grade, note = "C", "before the first recorded operation: the opening stub only"
                else:
                    grade, note = "B", "rolled from the recorded operations on top of the opening stub"
            ir = ratio_lookup(sid, d) if klass == "inflation_linked" else None
            rows.append({"security_id": sid, "as_of": d, "nominal_lcu_mn": level,
                         "nominal_uplifted_lcu_mn": level * ir if ir is not None else np.nan,
                         "position_type": "rolled_from_flows", "grade": grade, "notes": note,
                         "source_id": SOURCE_GILTS if not sid.startswith("UKTB-") else SOURCE_BILLS,
                         "part": D.PART_ISSUANCE if not sid.startswith("UKTB-") else D.PART_BILL_TENDERS})
    for m in master[master["in_issue"]].itertuples(index=False):
        rows.append({"security_id": m.security_id, "as_of": m.anchor_date, "nominal_lcu_mn": float(m.anchor_mn),
                     "nominal_uplifted_lcu_mn": (float(m.anchor_uplifted_mn)
                                                 if m.instrument_class == "inflation_linked" else np.nan),
                     "position_type": "office_snapshot", "grade": "A",
                     "notes": "D1A: nominal in issue at the close of business as published"
                              + ("; uplifted nominal as published" if m.instrument_class == "inflation_linked" else ""),
                     "source_id": SOURCE_GILTS, "part": D.PART_IN_ISSUE})
    df = pd.DataFrame(rows)
    out = pd.DataFrame({
        "iso3": ISO3, "security_id": df["security_id"], "as_of": pd.to_datetime(df["as_of"]),
        "nominal_lcu_mn": df["nominal_lcu_mn"], "nominal_uplifted_lcu_mn": df["nominal_uplifted_lcu_mn"],
        "nominal_issue_ccy_mn": np.nan, "official_holdings_lcu_mn": np.nan, "market_hands_lcu_mn": np.nan,
        "position_type": df["position_type"], "fx_rate": np.nan, "fx_source_id": None,
        "run_id": run_id, "source_id": df["source_id"],
        "snapshot_sha256": [D.sha(s, p) for s, p in zip(df["source_id"], df["part"])],
        "quality_grade": df["grade"], "notes": df["notes"],
    })
    return POSITIONS.validate(out.sort_values(["security_id", "as_of"]).reset_index(drop=True))


def _ratio_series(ratios: pd.DataFrame):
    by = {sid: g.sort_values("date").drop_duplicates("date", keep="first").set_index("date")["index_ratio"]
          for sid, g in ratios.groupby("security_id")} if len(ratios) else {}

    def lookup(sid: str, day: pd.Timestamp) -> float | None:
        s = by.get(sid)
        if s is None or s.empty or day < s.index.min():
            return None
        idx = s.index.searchsorted(day, side="right") - 1
        if idx + 1 < len(s):
            d0, d1 = s.index[idx], s.index[idx + 1]
            w = (day - d0).days / (d1 - d0).days
            return float(s.iloc[idx] + w * (s.iloc[idx + 1] - s.iloc[idx]))
        return float(s.iloc[idx])
    return lookup


# ----------------------------------------------------------- index ratios

def index_ratios(run_id: str, secs: pd.DataFrame, rpi: pd.Series, end: pd.Timestamp) -> pd.DataFrame:
    frames = []
    linkers = secs[secs["instrument_class"] == "inflation_linked"]
    for s in linkers.itertuples(index=False):
        if s.first_issue_date is None or pd.isna(s.first_issue_date):
            continue
        stop = min(end, s.maturity_date) if pd.notna(s.maturity_date) else end
        pts = _ratio_points(pd.Timestamp(s.first_issue_date), stop, float(s.index_lag_months), rpi)
        if pts.empty:
            continue
        pts["security_id"] = s.security_id
        pts["ratio_source"] = "recomputed"
        pts["notes"] = (f"DMO {s.index_lag_months:g}-month-lag formula on the ONS RPI (Jan 1987 = 100); "
                        + ("monthly points, linear within the month as the formula is"
                           if s.index_lag_months == 3.0 else "monthly step RPI(m−8) / RPI(issue month − 8)"))
        pts["source_id"] = "ONS_RPI"
        pts["part"] = "CHAW"
        frames.append(pts)
    if D.have(SOURCE_GILTS, D.PART_RATIOS):
        o = D.index_ratios()
        by_isin = secs.dropna(subset=["isin"]).set_index("isin")["security_id"]
        o = o[o["isin"].isin(by_isin.index)]
        frames.append(pd.DataFrame({
            "date": o["date"], "reference_index": o["reference_rpi"], "index_ratio": o["index_ratio"],
            "security_id": o["isin"].map(by_isin), "ratio_source": "office",
            "notes": "D10C: the office's daily index ratio and reference RPI for the current month",
            "source_id": SOURCE_GILTS, "part": D.PART_RATIOS,
        }))
    if not frames:
        return pd.DataFrame(columns=list(INDEX_RATIOS.columns))
    df = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame({
        "iso3": ISO3, "security_id": df["security_id"], "date": pd.to_datetime(df["date"]),
        "reference_index": df["reference_index"], "index_ratio": df["index_ratio"],
        "ratio_source": df["ratio_source"], "run_id": run_id, "source_id": df["source_id"],
        "snapshot_sha256": [_sha_any(s, p) for s, p in zip(df["source_id"], df["part"])],
        "quality_grade": "A", "notes": df["notes"],
    })
    out = out.drop_duplicates(["security_id", "date", "ratio_source"])
    return INDEX_RATIOS.validate(out.sort_values(["security_id", "date", "ratio_source"]).reset_index(drop=True))


def _sha_any(source_id: str, part: str) -> str | None:
    from ggfiscal.standardise.readers import latest_snapshots
    e = latest_snapshots().get((source_id, part))
    return e["sha256"] if e else None


# ------------------------------------------------------------------- build

def build(run_id: str) -> dict[str, pd.DataFrame]:
    if not D.have_register_parts():
        raise FileNotFoundError("DMO register parts missing (D1A, D2.1E, D1C, D2.2D)")
    rpi = _rpi()
    master = gilt_master()
    bills = bill_master()
    ops = _gilt_operation_rows(master) + _gilt_redemption_rows(master)
    opening, stubs = _opening_rows(master, ops)
    rows = ops + opening + _bill_rows(bills)
    secs = securities(run_id, master, bills, stubs, rpi)

    df = pd.DataFrame(rows)
    df["seq"] = df.groupby(["security_id", "settlement_date", "flow_type"]).cumcount()
    fl = pd.DataFrame({
        "iso3": ISO3, "security_id": df["security_id"], "settlement_date": pd.to_datetime(df["settlement_date"]),
        "flow_type": df["flow_type"], "seq": df["seq"], "operation_date": pd.to_datetime(df["operation_date"]),
        "nominal_lcu_mn": df["nominal_lcu_mn"], "cash_lcu_mn": df["cash_lcu_mn"], "price_pct": df["price_pct"],
        "yield_pct": df["yield_pct"], "method": df["method"], "counter_security_id": df["counter_security_id"],
        "run_id": run_id, "source_id": df["source_id"],
        "snapshot_sha256": [D.sha(s, p) for s, p in zip(df["source_id"], df["part"])],
        "quality_grade": df["grade"], "notes": df["notes"],
    })
    fl = FLOWS.validate(fl.sort_values(["settlement_date", "security_id", "flow_type", "seq"]).reset_index(drop=True))

    cob = pd.Timestamp(master.loc[master["in_issue"], "anchor_date"].max())
    ratios = index_ratios(run_id, secs, rpi, cob)
    pos = positions(run_id, secs, fl, master, ratios, stubs, end_year=cob.year - 1 if cob.month < 12 else cob.year)
    return {"debt_securities": secs, "debt_positions": pos, "debt_flows": fl, "debt_index_ratios": ratios}


# ------------------------------------------------------------ reconciliation

AGGREGATES_CSV = "data/canonical/debt_class_aggregates.csv"


def class_aggregates(run_id: str | None = None) -> pd.DataFrame:
    from ggfiscal import config
    path = config.repo_root() / AGGREGATES_CSV
    if path.exists():
        df = pd.read_csv(path)
        return df[df["iso3"] == ISO3].copy()
    from ggfiscal.debt.aggregates import class_aggregates as build_aggregates
    df = build_aggregates(run_id or "RECON")
    return df[df["iso3"] == ISO3].copy()


def reconciliation(run_id: str, tables: dict[str, pd.DataFrame] | None = None) -> dict[str, pd.DataFrame]:
    """Register vs the aggregate layer per year (V31, V39): Σ 31 December
    nominal of gilts against the ONS gilt stock (PSA8A_1 BKPM, nominal), bills
    against BKPJ, and Σ issuance against the DMO gross issuance."""
    t = tables or build(run_id)
    pos, fl, secs = t["debt_positions"], t["debt_flows"], t["debt_securities"]
    agg = class_aggregates(run_id)
    klass = secs.set_index("security_id")["instrument_class"]
    ye = pos[(pos["position_type"] == "rolled_from_flows")].copy()
    ye["year"] = ye["as_of"].dt.year
    ye["klass"] = ye["security_id"].map(klass)
    by_class = (ye.groupby(["year", "klass"], as_index=False)
                .agg(nominal_lcu_mn=("nominal_lcu_mn", "sum"),
                     uplifted_lcu_mn=("nominal_uplifted_lcu_mn", lambda s: s.sum(min_count=1)),
                     n_securities=("security_id", "nunique")))
    gilts = ye[ye["klass"] != "bill"].groupby("year").agg(
        register_gilts_nominal_lcu_mn=("nominal_lcu_mn", "sum"), n_gilts=("security_id", "nunique"))
    upl = ye[ye["klass"] == "inflation_linked"].groupby("year")["nominal_uplifted_lcu_mn"].sum(min_count=1)
    unind = ye[ye["klass"] == "inflation_linked"].groupby("year")["nominal_lcu_mn"].sum()
    gilts["register_gilts_uplifted_lcu_mn"] = gilts["register_gilts_nominal_lcu_mn"] + (upl - unind).reindex(gilts.index).fillna(0.0)
    bills = ye[ye["klass"] == "bill"].groupby("year")["nominal_lcu_mn"].sum().rename("register_bills_lcu_mn")
    st = agg[agg["measure"] == "stock_year_end"]
    ons_gilts = st[st["sub_type"] == "gilts_all"].set_index("year")["value_lcu_mn"]
    ons_bills = st[st["sub_type"] == "treasury_bills"].set_index("year")["value_lcu_mn"]
    stock = gilts.join(bills, how="outer")
    stock["official_gilts_lcu_mn"] = ons_gilts
    stock["ratio_gilts_uplifted_over_official"] = stock["register_gilts_uplifted_lcu_mn"] / ons_gilts
    stock["ratio_gilts_nominal_over_official"] = stock["register_gilts_nominal_lcu_mn"] / ons_gilts
    stock["official_bills_lcu_mn"] = ons_bills
    stock["ratio_bills_over_official"] = stock["register_bills_lcu_mn"] / ons_bills
    stock.index.name = "year"

    iss = fl[fl["flow_type"].isin(["auction", "syndication", "tap", "tender"]) & ~fl["security_id"].str.startswith("UKTB-")].copy()
    iss["year"] = iss["settlement_date"].dt.year
    gi = iss.groupby("year")["nominal_lcu_mn"].sum().rename("register_gross_issuance_lcu_mn")
    official = (agg[(agg["measure"] == "gross_issuance") & agg["in_register"]]
                .groupby("year")["value_lcu_mn"].sum().rename("official_gross_issuance_lcu_mn"))
    issuance = pd.concat([gi, official], axis=1)
    issuance["ratio"] = issuance["register_gross_issuance_lcu_mn"] / issuance["official_gross_issuance_lcu_mn"]
    issuance["n_operations"] = iss.groupby("year").size()
    issuance.index.name = "year"
    return {"stock": stock.reset_index(), "by_class": by_class, "issuance": issuance.reset_index()}
