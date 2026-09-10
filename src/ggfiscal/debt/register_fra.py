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
    rows = []
    for r in m.itertuples(index=False):
        klass, sub = KIND.get(r.kind, ("fixed_bullet", "oat"))
        linker = klass == "inflation_linked"
        notes = ["terms from the libellé of the encours page" if r.in_encours else
                 "line seen only on an adjudications page; not in the encours pages in the store"]
        if linker:
            notes.append(f"indexed on {INDEX_REFERENCE[r.kind]} with a 3-month lag; base index pending the AFT "
                         "coefficient files (OQ-8), ratios not yet recomputed")
        if pd.isna(first_issue.get(r.isin, pd.NaT)):
            notes.append("first issue date unknown until the auction history is in the store")
        rows.append({
            "iso3": ISO3, "security_id": r.isin, "isin": r.isin, "name": r.name,
            "instrument_class": klass, "sub_type": sub, "currency": "EUR",
            "coupon_pct": None if klass == "bill" else r.coupon_pct,
            "coupon_frequency": 1, "day_count": "ACT/360" if klass == "bill" else "ACT/ACT",
            "first_issue_date": first_issue.get(r.isin, pd.NaT), "maturity_date": r.maturity_date,
            "first_call_date": pd.NaT,
            "dividend_dates": (f"{r.maturity_date.day:02d} {r.maturity_date.strftime('%b')}"
                               if pd.notna(r.maturity_date) and klass != "bill" else None),
            "index_reference": INDEX_REFERENCE.get(r.kind) if linker else None,
            "index_lag_months": 3.0 if linker else np.nan, "base_index": np.nan,
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


def build(run_id: str) -> dict[str, pd.DataFrame]:
    if not any(A.have(A.SOURCE_ENCOURS, p) for p in A.ENCOURS_PARTS):
        raise FileNotFoundError("no AFT encours snapshot")
    m = master()
    fl = flows(run_id, m)
    first = (fl[fl["flow_type"] == "auction"].groupby("security_id")["settlement_date"].min()
             if len(fl) else pd.Series(dtype="datetime64[ns]"))
    secs = securities(run_id, m, first)
    pos = positions(run_id, m)
    ratios = pd.DataFrame(columns=list(INDEX_RATIOS.columns))
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
