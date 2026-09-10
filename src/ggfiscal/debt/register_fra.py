"""FRA per-security register (DEBT_KICKOFF.md §3–§5, §14 FRA) from the Agence
France Trésor pages (readers.aft).

``build(run_id)`` returns the four canonical frames for iso3 ``FRA``:

===================== ===================================================
``debt_securities``   every line of the encours détaillé pages (OAT, OATi,
                      OAT€i, BTF) plus every line an adjudications page names
``debt_positions``    the encours at the pages' retrieval date
                      (``office_snapshot``); 31 December positions once the
                      auction history is in the store (rolled back from the
                      snapshot through the flows, as the UK register does)
``debt_flows``        every auction on the adjudications pages in the store
                      (``auction``; total issued = competitive + ONC), plus a
                      ``retention``-free ``redemption`` per matured line
``debt_index_ratios`` recomputed from ``FR_CPI_XT`` / ``EA_HICP_XT`` once the
                      base indices (the AFT coefficient files) are in the store
===================== ===================================================

All amounts are EUR millions. Status 2026-09-10: the encours pages and the
current month's auctions are in the store; the auction history, the OATi
page and the coefficient files are on the committee's list (OQ-8), so this
register is a snapshot register — positions at one date — until they arrive.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ggfiscal.debt.model import FLOWS, INDEX_RATIOS, POSITIONS, SECURITIES
from ggfiscal.debt.readers import aft as A

ISO3 = "FRA"
KIND = {
    "OAT": ("fixed_bullet", "oat"), "BTAN": ("fixed_bullet", "btan"),
    "OATi": ("inflation_linked", "oati"), "OAT€i": ("inflation_linked", "oatei"),
    "BTF": ("bill", "btf"),
}
INDEX_REFERENCE = {"OATi": "FR_CPI_XT", "OAT€i": "EA_HICP_XT"}


def _prov(run_id: str, source_id: str, part: str, grade: str, notes: str | None) -> dict:
    return {"run_id": run_id, "source_id": source_id, "snapshot_sha256": A.sha(source_id, part),
            "quality_grade": grade, "notes": notes}


def master() -> pd.DataFrame:
    """One row per ISIN: the encours line (terms from the libellé) and, for
    lines only seen at auction, the auction page's name and maturity."""
    enc = A.encours_all()
    au = A.auctions_all()
    rows = []
    seen = set()
    for r in enc.itertuples(index=False):
        seen.add(r.isin)
        rows.append({"isin": r.isin, "name": r.libelle, "kind": r.kind, "coupon_pct": r.coupon_pct,
                     "maturity_date": r.maturity_date, "is_green": bool(r.is_green),
                     "outstanding_mn": r.outstanding_eur / 1e6 if pd.notna(r.outstanding_eur) else np.nan,
                     "as_of": r.as_of, "part": r.part, "in_encours": True})
    if len(au):
        for r in au.drop_duplicates("isin").itertuples(index=False):
            if r.isin in seen:
                continue
            p = A.parse_libelle(r.line_name) if r.family == "OAT" else {"kind": "BTF", "coupon_pct": None,
                                                                      "maturity_date": r.maturity_date, "is_green": False}
            rows.append({"isin": r.isin, "name": r.line_name, "kind": p["kind"] or r.family,
                         "coupon_pct": p["coupon_pct"],
                         "maturity_date": p["maturity_date"] if pd.notna(p["maturity_date"]) else r.maturity_date,
                         "is_green": bool(p["is_green"]), "outstanding_mn": np.nan, "as_of": pd.NaT,
                         "part": r.part, "in_encours": False})
    return pd.DataFrame(rows)


def securities(run_id: str, m: pd.DataFrame, first_issue: pd.Series) -> pd.DataFrame:
    T, _ = coefficient_terms()
    terms = T.set_index("key") if len(T) else pd.DataFrame()
    rows = []
    for r in m.itertuples(index=False):
        klass, sub = KIND.get(r.kind, ("fixed_bullet", "oat"))
        linker = klass == "inflation_linked"
        notes = ["terms from the libellé of the encours page" if r.in_encours else
                 "line seen only on an adjudications page; not in the encours pages in the store"]
        base_index, base_date = np.nan, pd.NaT
        if linker:
            key = _term_key(r.kind, r.coupon_pct, r.maturity_date)
            if key in terms.index:
                base_index, base_date = float(terms.loc[key, "base_index"]), terms.loc[key, "base_date"]
                notes.append(f"indexed on {INDEX_REFERENCE[r.kind]} with a 3-month lag; base index "
                             f"{base_index:.5f} at {pd.Timestamp(base_date):%Y-%m-%d} (AFT coefficient file, "
                             "current CPI base)")
            else:
                notes.append(f"indexed on {INDEX_REFERENCE[r.kind]} with a 3-month lag; no AFT coefficient "
                             "column for this line (ratios not computable)")
        fi = first_issue.get(r.isin, pd.NaT)
        if pd.isna(fi) and pd.notna(base_date):
            fi = pd.Timestamp(base_date)
            notes.append("first_issue_date = the line's base (jouissance) date from the coefficient file")
        elif pd.isna(fi):
            notes.append("first issue date unknown until the auction history is in the store")
        rows.append({
            "iso3": ISO3, "security_id": r.isin, "isin": r.isin, "name": r.name,
            "instrument_class": klass, "sub_type": sub, "currency": "EUR",
            "coupon_pct": None if klass == "bill" else r.coupon_pct,
            "coupon_frequency": 1, "day_count": "ACT/360" if klass == "bill" else "ACT/ACT",
            "first_issue_date": fi, "maturity_date": r.maturity_date,
            "first_call_date": pd.NaT,
            "dividend_dates": (f"{r.maturity_date.day:02d} {r.maturity_date.strftime('%b')}"
                               if pd.notna(r.maturity_date) and klass != "bill" else None),
            "index_reference": INDEX_REFERENCE.get(r.kind) if linker else None,
            "index_lag_months": 3.0 if linker else np.nan, "base_index": base_index if linker else np.nan,
            "floating_reference": None, "spread_bp": np.nan, "is_green": bool(r.is_green), "issuer_unit": "state",
            **_prov(run_id, A.SOURCE_ENCOURS if r.in_encours else A.SOURCE_ADJUDICATIONS, r.part, "A",
                    "; ".join(notes)),
        })
    return SECURITIES.validate(pd.DataFrame(rows).sort_values("security_id").reset_index(drop=True))


def positions(run_id: str, m: pd.DataFrame) -> pd.DataFrame:
    e = m[m["in_encours"] & m["outstanding_mn"].notna()]
    out = pd.DataFrame({
        "iso3": ISO3, "security_id": e["isin"], "as_of": pd.to_datetime(e["as_of"]),
        "nominal_lcu_mn": e["outstanding_mn"], "nominal_uplifted_lcu_mn": np.nan,
        "nominal_issue_ccy_mn": np.nan, "official_holdings_lcu_mn": np.nan, "market_hands_lcu_mn": np.nan,
        "position_type": "office_snapshot", "fx_rate": np.nan, "fx_source_id": None,
        "run_id": run_id, "source_id": A.SOURCE_ENCOURS,
        "snapshot_sha256": [A.sha(A.SOURCE_ENCOURS, p) for p in e["part"]],
        "quality_grade": "A",
        "notes": "encours détaillé as published; the page states no date, the as_of is the snapshot's retrieval "
                 "date; index-linked lines at unindexed nominal",
    })
    return POSITIONS.validate(out.sort_values(["security_id", "as_of"]).reset_index(drop=True))


def flows(run_id: str, m: pd.DataFrame) -> pd.DataFrame:
    au = A.auctions_all()
    rows = []
    if len(au):
        for r in au.itertuples(index=False):
            if pd.isna(r.settlement_date) or pd.isna(r.total_issued_mn):
                continue
            price = r.avg_price_pct if pd.notna(r.avg_price_pct) else None
            rows.append({
                "security_id": r.isin, "settlement_date": r.settlement_date, "operation_date": r.auction_date,
                "flow_type": "auction", "nominal_lcu_mn": float(r.total_issued_mn),
                "cash_lcu_mn": float(r.total_issued_mn) * price / 100.0 if price else None,
                "price_pct": price, "yield_pct": r.avg_yield_pct if pd.notna(r.avg_yield_pct) else None,
                "method": f"adjudication ({r.family}); volume total émis = adjugé {r.allotted_mn:,.0f} + ONC "
                          f"{(r.onc_mn if pd.notna(r.onc_mn) else 0):,.0f}",
                "part": r.part,
                "notes": "AFT adjudications page: total issued incl. the non-competitive tranche (ONC); "
                         "price = weighted average price" if price else
                         "AFT adjudications page: total issued incl. ONC; BTF sold at a yield, no price published",
            })
    if not rows:
        return pd.DataFrame(columns=list(FLOWS.columns))
    df = pd.DataFrame(rows)
    df["seq"] = df.groupby(["security_id", "settlement_date", "flow_type"]).cumcount()
    out = pd.DataFrame({
        "iso3": ISO3, "security_id": df["security_id"], "settlement_date": pd.to_datetime(df["settlement_date"]),
        "flow_type": df["flow_type"], "seq": df["seq"], "operation_date": pd.to_datetime(df["operation_date"]),
        "nominal_lcu_mn": df["nominal_lcu_mn"], "cash_lcu_mn": df["cash_lcu_mn"], "price_pct": df["price_pct"],
        "yield_pct": df["yield_pct"], "method": df["method"], "counter_security_id": None,
        "run_id": run_id, "source_id": A.SOURCE_ADJUDICATIONS,
        "snapshot_sha256": [A.sha(A.SOURCE_ADJUDICATIONS, p) for p in df["part"]],
        "quality_grade": "A", "notes": df["notes"],
    })
    return FLOWS.validate(out.sort_values(["settlement_date", "security_id", "seq"]).reset_index(drop=True))


# ----------------------------------------------------------- index ratios

def _term_key(kind: str, coupon: float | None, maturity) -> str | None:
    if coupon is None or pd.isna(coupon) or maturity is None or pd.isna(maturity):
        return None
    return f"{kind}|{round(float(coupon), 3)}|{pd.Timestamp(maturity):%Y-%m-%d}"


def coefficient_terms() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every line of every coefficient file in the store: terms (with a
    term key) and the daily coefficients keyed the same way. The current
    files take precedence over the 2016 history files for the same line."""
    terms, dailies = [], []
    for kind, parts in A.COEF_PARTS.items():
        for part in parts:
            if not A.have(A.SOURCE_INDEXATION, part):
                continue
            t, d = A.coefficient_file(part)
            t["key"] = [_term_key(k, c, m) for k, c, m in zip(t["kind"], t["coupon_pct"], t["maturity_date"])]
            d = d.merge(t[["column", "key"]], on="column")
            d["part"] = part
            terms.append(t)
            dailies.append(d)
    if not terms:
        return pd.DataFrame(), pd.DataFrame()
    T = pd.concat(terms, ignore_index=True).drop_duplicates("key", keep="first")
    D = pd.concat(dailies, ignore_index=True)
    D = D.sort_values(["key", "date", "part"]).drop_duplicates(["key", "date"], keep="first")
    return T, D


def reference_index_3m(day: pd.Timestamp, monthly: pd.Series) -> float:
    """AFT daily reference index: index(m−3) + (d−1)/days(m) × (index(m−2) −
    index(m−3)); `monthly` is indexed by the first of the month."""
    day = pd.Timestamp(day)
    m3 = (day - pd.DateOffset(months=3)).to_period("M").to_timestamp()
    m2 = (day - pd.DateOffset(months=2)).to_period("M").to_timestamp()
    if m3 not in monthly.index or m2 not in monthly.index:
        return np.nan
    return float(monthly[m3] + (day.day - 1) / day.days_in_month * (monthly[m2] - monthly[m3]))


def _monthly_index(kind: str) -> pd.Series:
    px = A.price_index(kind)
    s = px.set_index(px["month"].dt.to_period("M").dt.to_timestamp()).iloc[:, 1]
    return pd.to_numeric(s, errors="coerce").dropna().sort_index()


def index_ratios(run_id: str, secs: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    linkers = secs[secs["instrument_class"] == "inflation_linked"]
    if linkers.empty or not any(A.have(A.SOURCE_INDEXATION, p) for ps in A.COEF_PARTS.values() for p in ps):
        return pd.DataFrame(columns=list(INDEX_RATIOS.columns))
    T, D = coefficient_terms()
    kinds = {"oati": "OATi", "oatei": "OAT€i"}
    frames = []
    for s_ in linkers.itertuples(index=False):
        kind = kinds.get(s_.sub_type)
        key = _term_key(kind, s_.coupon_pct, s_.maturity_date)
        office = D[D["key"] == key] if key else D.iloc[0:0]
        if len(office):
            frames.append(pd.DataFrame({
                "security_id": s_.security_id, "date": office["date"].values,
                "reference_index": office["reference_index"].values, "index_ratio": office["coefficient"].values,
                "ratio_source": "office", "source_id": A.SOURCE_INDEXATION, "part": office["part"].values,
                "notes": "AFT coefficient file: daily reference index and indexation coefficient as published",
            }))
        # recomputed monthly points beyond the office series (lines matured
        # after the 2016 history files) from the monthly index, base = the
        # reference index at the line's base date
        term = T[T["key"] == key] if key else T.iloc[0:0]
        stop = min(end, s_.maturity_date) if pd.notna(s_.maturity_date) else end
        if len(term) and (office.empty or office["date"].max() < stop - pd.Timedelta(days=45)):
            monthly = _monthly_index(kind)
            base_date = term["base_date"].iloc[0]
            base = reference_index_3m(base_date, monthly) if pd.notna(base_date) else np.nan
            start = office["date"].max() + pd.offsets.MonthBegin(1) if len(office) else pd.Timestamp(base_date)
            if pd.notna(base) and base > 0:
                dates = pd.date_range(start.normalize(), stop, freq="MS")
                refs = np.array([reference_index_3m(d, monthly) for d in dates])
                ok = ~np.isnan(refs)
                frames.append(pd.DataFrame({
                    "security_id": s_.security_id, "date": dates[ok], "reference_index": refs[ok],
                    "index_ratio": refs[ok] / base, "ratio_source": "recomputed",
                    "source_id": A.SOURCE_INDEXATION, "part": A.INDEX_PARTS[kind],
                    "notes": "recomputed: AFT 3-month-lag formula on the AFT monthly index (base 2025) / the "
                             "reference index at the line's base date; monthly points, linear within the month",
                }))
    if not frames:
        return pd.DataFrame(columns=list(INDEX_RATIOS.columns))
    df = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame({
        "iso3": ISO3, "security_id": df["security_id"], "date": pd.to_datetime(df["date"]),
        "reference_index": df["reference_index"], "index_ratio": df["index_ratio"],
        "ratio_source": df["ratio_source"], "run_id": run_id, "source_id": df["source_id"],
        "snapshot_sha256": [A.sha(A.SOURCE_INDEXATION, p) for p in df["part"]],
        "quality_grade": "A", "notes": df["notes"],
    }).drop_duplicates(["security_id", "date", "ratio_source"])
    return INDEX_RATIOS.validate(out.sort_values(["security_id", "date", "ratio_source"]).reset_index(drop=True))


def build(run_id: str) -> dict[str, pd.DataFrame]:
    if not any(A.have(A.SOURCE_ENCOURS, p) for p in A.ENCOURS_PARTS):
        raise FileNotFoundError("no AFT encours snapshot")
    m = master()
    fl = flows(run_id, m)
    first = (fl[fl["flow_type"] == "auction"].groupby("security_id")["settlement_date"].min()
             if len(fl) else pd.Series(dtype="datetime64[ns]"))
    secs = securities(run_id, m, first)
    pos = positions(run_id, m)
    end = pd.Timestamp(pos["as_of"].max()) if len(pos) else pd.Timestamp.today().normalize()
    ratios = index_ratios(run_id, secs, end)
    return {"debt_securities": secs, "debt_positions": pos, "debt_flows": fl, "debt_index_ratios": ratios}


def reconciliation(run_id: str, tables: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Σ encours by class at the snapshot date next to every in-register
    aggregate row of the latest year (V31): the aggregate layer carries
    alternative measures of the same stock side by side, so they are listed,
    never summed (config/debt.yaml `register_selection` picks a set)."""
    from ggfiscal import config
    t = tables or build(run_id)
    pos, secs = t["debt_positions"], t["debt_securities"]
    klass = secs.set_index("security_id")["instrument_class"]
    reg = pos.assign(klass=pos["security_id"].map(klass)).groupby("klass")["nominal_lcu_mn"].sum()
    rows = [{"instrument_class": k, "sub_type": "register (encours détaillé)", "year": int(pos["as_of"].max().year),
             "value_lcu_mn": float(v)} for k, v in reg.items()]
    path = config.repo_root() / "data" / "canonical" / "debt_class_aggregates.csv"
    if path.exists():
        agg = pd.read_csv(path)
        agg = agg[(agg["iso3"] == ISO3) & (agg["measure"] == "stock_year_end") & agg["in_register"]]
        if len(agg):
            latest = agg[agg["year"] == agg["year"].max()]
            for r in latest.itertuples(index=False):
                rows.append({"instrument_class": r.instrument_class, "sub_type": f"official: {r.sub_type}",
                             "year": int(r.year), "value_lcu_mn": float(r.value_lcu_mn)})
    return pd.DataFrame(rows).sort_values(["instrument_class", "sub_type"]).reset_index(drop=True)
