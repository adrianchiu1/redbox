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

All amounts are EUR millions.

How the positions are obtained (DD13: no scaling, no plugging) — the UK
method (register_gbr) on the AFT's files: the anchor is the encours détaillé
(every line in issue at the pages' retrieval date); the operations are the
AFT's auction histories (``hist_mlt`` 1999→, ``hist_btf`` 1999→, the
syndication history 1999→, plus the adjudications pages in the store for
the months after the files end). A line's history is the anchor walked back
through its operations; where Σ operations falls short of the anchor
(issues before 1999, buybacks the AFT does not publish per line) the
difference is one ``implied`` flow at 1999-01-01 (grade C), never spread.
Lines matured since 1999 have no anchor: their positions are Σ operations
(grade B: the AFT publishes no per-line buyback file, so a line bought
back before maturity is overstated in its last years) and they are redeemed
at that amount. BTF tendered after the history file's last month carry the
snapshot amount from the retrieval date only.
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
    "BTANi": ("inflation_linked", "btani"), "BTAN€i": ("inflation_linked", "btanei"),
    "BTF": ("bill", "btf"),
}
INDEX_REFERENCE = {"OATi": "FR_CPI_XT", "BTANi": "FR_CPI_XT", "OAT€i": "EA_HICP_XT", "BTAN€i": "EA_HICP_XT"}
#: The AFT auction histories start in January 1999.
REGISTER_START = pd.Timestamp("1999-01-01")
STUB_TOL_MN = 0.5
SIGN = {"auction": 1, "syndication": 1, "tap": 1, "tender": 1, "conversion_in": 1, "switch_in": 1,
        "redemption": -1, "buyback": -1, "conversion_out": -1, "switch_out": -1, "implied": 1,
        "retention": 0, "own_book_sale": 0, "own_book_purchase": 0}


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
            seen.add(r.isin)
            p = A.parse_libelle(r.line_name) if r.family == "OAT" else {"kind": "BTF", "coupon_pct": None,
                                                                      "maturity_date": r.maturity_date, "is_green": False}
            rows.append({"isin": r.isin, "name": r.line_name, "kind": p["kind"] or r.family,
                         "coupon_pct": p["coupon_pct"],
                         "maturity_date": p["maturity_date"] if pd.notna(p["maturity_date"]) else r.maturity_date,
                         "is_green": bool(p["is_green"]), "outstanding_mn": np.nan, "as_of": pd.NaT,
                         "part": r.part, "in_encours": False})
    # lines that appear only in the auction histories (matured since 1999)
    if A.have(A.SOURCE_ADJUDICATIONS, A.HIST_MLT_PART):
        h = A.history_mlt()
        sy = A.history_syndications() if A.have(A.SOURCE_ADJUDICATIONS, A.HIST_SYND_PART) else pd.DataFrame()
        lines = pd.concat([h[["isin", "line", "part"]], sy[["isin", "line", "part"]]] if len(sy) else [h[["isin", "line", "part"]]])
        for r in lines.drop_duplicates("isin").itertuples(index=False):
            if r.isin in seen:
                continue
            seen.add(r.isin)
            p = A.parse_libelle(r.line)
            rows.append({"isin": r.isin, "name": r.line, "kind": p["kind"] or "OAT", "coupon_pct": p["coupon_pct"],
                         "maturity_date": p["maturity_date"], "is_green": bool(p["is_green"]),
                         "outstanding_mn": np.nan, "as_of": pd.NaT, "part": r.part, "in_encours": False})
    if A.have(A.SOURCE_ADJUDICATIONS, A.HIST_BTF_PART):
        b = A.history_btf()
        for r in b.drop_duplicates("isin").itertuples(index=False):
            if not isinstance(r.isin, str) or r.isin in seen:
                continue
            seen.add(r.isin)
            rows.append({"isin": r.isin, "name": f"BTF {pd.Timestamp(r.maturity_date):%d %B %Y}", "kind": "BTF",
                         "coupon_pct": None, "maturity_date": r.maturity_date, "is_green": False,
                         "outstanding_mn": np.nan, "as_of": pd.NaT, "part": r.part, "in_encours": False})
    return pd.DataFrame(rows)


def securities(run_id: str, m: pd.DataFrame, first_issue: pd.Series) -> pd.DataFrame:
    T, _ = coefficient_terms()
    terms = T.set_index("key") if len(T) else pd.DataFrame()
    rows = []
    for r in m.itertuples(index=False):
        klass, sub = KIND.get(r.kind, ("fixed_bullet", "oat"))
        linker = klass == "inflation_linked"
        notes = ["terms from the libellé of the encours page" if r.in_encours else
                 "line from the AFT auction histories, not in issue at the encours pages' date (matured, or "
                 "the BTF tendered after the history file's last month)"]
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
                             "column for this line (matured before the 2016 history files): ratios recomputed from the "
                             "AFT monthly index with the base at the coupon anniversary on or before the first settlement")
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


def _history_rows(known: set[str]) -> list[dict]:
    rows = []
    if A.have(A.SOURCE_ADJUDICATIONS, A.HIST_MLT_PART):
        for r in A.history_mlt().itertuples(index=False):
            if r.isin not in known or pd.isna(r.settlement_date) or pd.isna(r.total_issued_mn):
                continue
            price = r.avg_price * 100.0 if pd.notna(r.avg_price) else None
            rows.append({"security_id": r.isin, "settlement_date": r.settlement_date, "operation_date": r.auction_date,
                         "flow_type": "auction", "nominal_lcu_mn": float(r.total_issued_mn),
                         "cash_lcu_mn": float(r.total_issued_mn) * price / 100.0 if price else None,
                         "price_pct": price, "yield_pct": r.avg_yield * 100.0 if pd.notna(r.avg_yield) else None,
                         "method": f"adjudication {r.kind}: adjugé {r.allotted_mn:,.0f} + ONC "
                                   f"{(r.onc_mn if pd.notna(r.onc_mn) else 0):,.0f}",
                         "part": r.part, "grade": "A",
                         "notes": "AFT hist_mlt: total issued incl. the non-competitive tranche (ONC); price = weighted "
                                  "average price (fraction of par in the file, ×100 here); for linkers the price is "
                                  "real, cash = nominal × price (uplift not included)"})
    if A.have(A.SOURCE_ADJUDICATIONS, A.HIST_BTF_PART):
        for r in A.history_btf().itertuples(index=False):
            if not isinstance(r.isin, str) or r.isin not in known or pd.isna(r.settlement_date) or pd.isna(r.total_issued_mn):
                continue
            y = r.avg_yield if pd.notna(r.avg_yield) else None
            days = (r.maturity_date - r.settlement_date).days if pd.notna(r.maturity_date) else None
            price = 100.0 / (1.0 + y * days / 360.0) if y is not None and days else None
            rows.append({"security_id": r.isin, "settlement_date": r.settlement_date, "operation_date": r.auction_date,
                         "flow_type": "tender", "nominal_lcu_mn": float(r.total_issued_mn),
                         "cash_lcu_mn": float(r.total_issued_mn) * price / 100.0 if price else None,
                         "price_pct": price, "yield_pct": y * 100.0 if y is not None else None,
                         "method": f"BTF tender {int(r.weeks) if pd.notna(r.weeks) else '?'} weeks: adjugé "
                                   f"{r.allotted_mn:,.0f} + ONC {(r.onc_mn if pd.notna(r.onc_mn) else 0):,.0f}",
                         "part": r.part, "grade": "A",
                         "notes": "AFT hist_btf: total issued incl. ONC; the AFT publishes the money-market yield, the "
                                  "price is derived as 100 / (1 + yield × days/360) (BTF convention)"})
    if A.have(A.SOURCE_ADJUDICATIONS, A.HIST_SYND_PART):
        for r in A.history_syndications().itertuples(index=False):
            if r.isin not in known or pd.isna(r.settlement_date) or pd.isna(r.volume_mn):
                continue
            price = r.avg_price * 100.0 if pd.notna(r.avg_price) else None
            buyback = r.volume_mn < 0
            rows.append({"security_id": r.isin, "settlement_date": r.settlement_date, "operation_date": r.settlement_date,
                         "flow_type": "buyback" if buyback else "syndication", "nominal_lcu_mn": abs(float(r.volume_mn)),
                         "cash_lcu_mn": abs(float(r.volume_mn)) * price / 100.0 if price else None,
                         "price_pct": price, "yield_pct": r.avg_yield * 100.0 if pd.notna(r.avg_yield) else None,
                         "method": f"syndication {r.kind}" + (" (rachat: volume négatif)" if buyback else ""),
                         "part": r.part, "grade": "A",
                         "notes": "AFT syndication history: volume émis (+) ou racheté (−)"})
    return rows


def _page_rows(known: set[str], after: pd.Timestamp | None) -> list[dict]:
    """The adjudications pages in the store, for auctions after the history
    files' last settlement (the current month)."""
    au = A.auctions_all()
    rows = []
    if not len(au):
        return rows
    for r in au.itertuples(index=False):
        if r.isin not in known or pd.isna(r.settlement_date) or pd.isna(r.total_issued_mn):
            continue
        if after is not None and r.settlement_date <= after:
            continue
        price = r.avg_price_pct if pd.notna(r.avg_price_pct) else None
        if price is None and r.family == "BTF" and pd.notna(r.avg_yield_pct) and pd.notna(r.maturity_date):
            price = 100.0 / (1.0 + r.avg_yield_pct / 100.0 * (r.maturity_date - r.settlement_date).days / 360.0)
        rows.append({"security_id": r.isin, "settlement_date": r.settlement_date, "operation_date": r.auction_date,
                     "flow_type": "auction" if r.family == "OAT" else "tender", "nominal_lcu_mn": float(r.total_issued_mn),
                     "cash_lcu_mn": float(r.total_issued_mn) * price / 100.0 if price else None,
                     "price_pct": price, "yield_pct": r.avg_yield_pct if pd.notna(r.avg_yield_pct) else None,
                     "method": f"adjudication ({r.family}), from the monthly page; adjugé {r.allotted_mn:,.0f} + ONC "
                               f"{(r.onc_mn if pd.notna(r.onc_mn) else 0):,.0f}",
                     "part": r.part, "grade": "A",
                     "notes": "AFT adjudications page (the month after the history files end)"})
    return rows


def _stub_and_redemption_rows(m: pd.DataFrame, ops: list[dict], snapshot_date: pd.Timestamp) -> tuple[list[dict], dict]:
    df = pd.DataFrame(ops)
    signed = ((df["nominal_lcu_mn"] * df["flow_type"].map(SIGN)).groupby(df["security_id"]).sum()
              if len(df) else pd.Series(dtype=float))
    first = df.groupby("security_id")["settlement_date"].min() if len(df) else pd.Series(dtype="datetime64[ns]")
    rows, stubs = [], {}
    for r in m.itertuples(index=False):
        total = float(signed.get(r.isin, 0.0))
        if r.in_encours and pd.notna(r.outstanding_mn):
            stub = float(r.outstanding_mn) - total
            if abs(stub) > STUB_TOL_MN:
                stubs[r.isin] = stub
                if r.kind == "BTF" and r.isin not in first.index:
                    when, grade, why = (snapshot_date, "C", "BTF tendered after the last month of the BTF history "
                                                          "file: only the encours at the retrieval date is known")
                elif r.kind == "BTF":
                    when, grade, why = (pd.Timestamp(first[r.isin]), "C", "Σ tenders in the store short of the encours "
                                                                         "(a tender after the history file's last month)")
                elif stub < 0 and r.isin in first.index and pd.Timestamp(first[r.isin]) > REGISTER_START:
                    # a line issued inside the history whose operations exceed
                    # its encours has been bought back (rachats, which the AFT
                    # publishes only in aggregate); the timing is unknown and the
                    # buybacks fall in the line's last years, so the stub is dated
                    # at the snapshot and the earlier year-ends stay gross of it
                    when, grade, why = (snapshot_date, "C", f"Σ recorded operations ({total:,.1f}) exceed the encours "
                                                            f"({float(r.outstanding_mn):,.1f}) by {-stub:,.1f}: bought back "
                                                            "before the snapshot on dates the AFT does not publish per line; "
                                                            "dated at the snapshot, so the year-ends before it are gross of "
                                                            "the buyback")
                elif stub > 0 and r.isin in first.index and pd.Timestamp(first[r.isin]) > REGISTER_START:
                    when, grade, why = (pd.Timestamp(first[r.isin]), "C", f"Σ recorded operations ({total:,.1f}) fall "
                                                                          f"short of the encours ({float(r.outstanding_mn):,.1f}) by {stub:,.1f} "
                                                                          "for a line issued inside the history: an operation the files do not "
                                                                          "carry, dated at the line's first recorded operation")
                else:
                    when, grade, why = (REGISTER_START, "C", f"Σ recorded operations since 1999 ({total:,.1f}) differ "
                                                            f"from the encours ({float(r.outstanding_mn):,.1f}) by {stub:,.1f}: "
                                                            "issued before 1999 (the history starts in January 1999)")
                rows.append({"security_id": r.isin, "settlement_date": when, "operation_date": None,
                             "flow_type": "implied", "nominal_lcu_mn": stub, "cash_lcu_mn": None, "price_pct": None,
                             "yield_pct": None, "method": "opening stub", "part": r.part, "grade": grade,
                             "notes": "opening amount, " + why + " (DD13: published, never allocated)"})
        elif pd.notna(r.maturity_date) and r.maturity_date <= snapshot_date and total > STUB_TOL_MN:
            rows.append({"security_id": r.isin, "settlement_date": pd.Timestamp(r.maturity_date),
                         "operation_date": pd.Timestamp(r.maturity_date), "flow_type": "redemption",
                         "nominal_lcu_mn": total, "cash_lcu_mn": total, "price_pct": 100.0, "yield_pct": None,
                         "method": "Redemption at par", "part": r.part, "grade": "B",
                         "notes": "derived: Σ recorded operations redeemed at maturity (the AFT publishes no "
                                  "redemption file and no per-line buybacks: a line bought back before maturity is "
                                  "overstated in its last years)"})
    return rows, stubs


def flows(run_id: str, m: pd.DataFrame, snapshot_date: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    known = set(m["isin"])
    ops = _history_rows(known)
    last = max((r["settlement_date"] for r in ops), default=None)
    ops += _page_rows(known, last)
    extra, stubs = _stub_and_redemption_rows(m, ops, snapshot_date)
    rows = ops + extra
    if not rows:
        return pd.DataFrame(columns=list(FLOWS.columns)), {}
    df = pd.DataFrame(rows)
    df["seq"] = df.groupby(["security_id", "settlement_date", "flow_type"]).cumcount()
    out = pd.DataFrame({
        "iso3": ISO3, "security_id": df["security_id"], "settlement_date": pd.to_datetime(df["settlement_date"]),
        "flow_type": df["flow_type"], "seq": df["seq"], "operation_date": pd.to_datetime(df["operation_date"]),
        "nominal_lcu_mn": df["nominal_lcu_mn"], "cash_lcu_mn": df["cash_lcu_mn"], "price_pct": df["price_pct"],
        "yield_pct": df["yield_pct"], "method": df["method"], "counter_security_id": None,
        "run_id": run_id, "source_id": [A.SOURCE_ADJUDICATIONS if not str(p).startswith(("oat", "btf")) else A.SOURCE_ENCOURS
                                        for p in df["part"]],
        "snapshot_sha256": [A.sha(A.SOURCE_ADJUDICATIONS, p) or A.sha(A.SOURCE_ENCOURS, p) for p in df["part"]],
        "quality_grade": df["grade"], "notes": df["notes"],
    })
    return FLOWS.validate(out.sort_values(["settlement_date", "security_id", "flow_type", "seq"]).reset_index(drop=True)), stubs


def positions(run_id: str, m: pd.DataFrame, fl: pd.DataFrame, secs: pd.DataFrame, ratios: pd.DataFrame,
              stubs: dict, snapshot_date: pd.Timestamp) -> pd.DataFrame:
    rows = []
    e = m[m["in_encours"] & m["outstanding_mn"].notna()]
    ratio_lookup = _ratio_series(ratios)
    klass = secs.set_index("security_id")["instrument_class"]
    for r in e.itertuples(index=False):
        ir = ratio_lookup(r.isin, pd.Timestamp(r.as_of)) if klass.get(r.isin) == "inflation_linked" else None
        rows.append({"security_id": r.isin, "as_of": pd.Timestamp(r.as_of), "nominal_lcu_mn": float(r.outstanding_mn),
                     "nominal_uplifted_lcu_mn": float(r.outstanding_mn) * ir if ir is not None else np.nan,
                     "position_type": "office_snapshot", "grade": "A", "source_id": A.SOURCE_ENCOURS, "part": r.part,
                     "notes": "encours détaillé as published; the page states no date, the as_of is the snapshot's "
                              "retrieval date" + ("; uplifted at the AFT coefficient" if ir is not None else "")})
    if len(fl):
        f = fl.copy()
        f["_v"] = f["nominal_lcu_mn"] * f["flow_type"].map(SIGN).fillna(0)
        terms = secs.set_index("security_id")
        year_ends = pd.date_range(f"{REGISTER_START.year}-12-31", f"{snapshot_date.year - 1}-12-31", freq="YE")
        for sid, g in f.groupby("security_id"):
            cum = g.groupby("settlement_date")["_v"].sum().cumsum()
            mat = terms.loc[sid, "maturity_date"]
            for d in year_ends:
                if d < cum.index.min() or (pd.notna(mat) and d >= mat):
                    continue
                level = float(cum[cum.index <= d].iloc[-1])
                if abs(level) < 1e-6:
                    continue
                in_enc = bool(terms.loc[sid, "notes"] and "encours page" in str(terms.loc[sid, "notes"]))
                grade = "A" if (in_enc and sid not in stubs) else ("B" if in_enc else "B")
                note = ("rolled from the AFT auction histories back from the encours anchor" if in_enc and sid not in stubs
                        else "rolled from the AFT auction histories on top of an opening stub" if in_enc
                        else "Σ AFT auction histories (matured line: no anchor, buybacks unknown)")
                ir = ratio_lookup(sid, d) if klass.get(sid) == "inflation_linked" else None
                rows.append({"security_id": sid, "as_of": d, "nominal_lcu_mn": level,
                             "nominal_uplifted_lcu_mn": level * ir if ir is not None else np.nan,
                             "position_type": "rolled_from_flows", "grade": grade, "source_id": A.SOURCE_ADJUDICATIONS,
                             "part": A.HIST_MLT_PART if klass.get(sid) != "bill" else A.HIST_BTF_PART, "notes": note})
    df = pd.DataFrame(rows)
    out = pd.DataFrame({
        "iso3": ISO3, "security_id": df["security_id"], "as_of": pd.to_datetime(df["as_of"]),
        "nominal_lcu_mn": df["nominal_lcu_mn"], "nominal_uplifted_lcu_mn": df["nominal_uplifted_lcu_mn"],
        "nominal_issue_ccy_mn": np.nan, "official_holdings_lcu_mn": np.nan, "market_hands_lcu_mn": np.nan,
        "position_type": df["position_type"], "fx_rate": np.nan, "fx_source_id": None,
        "run_id": run_id, "source_id": df["source_id"],
        "snapshot_sha256": [A.sha(s_, p) for s_, p in zip(df["source_id"], df["part"])],
        "quality_grade": df["grade"], "notes": df["notes"],
    })
    return POSITIONS.validate(out.sort_values(["security_id", "as_of"]).reset_index(drop=True))


def _ratio_series(ratios: pd.DataFrame):
    by = ({sid: g.sort_values("date").drop_duplicates("date").set_index("date")["index_ratio"]
           for sid, g in ratios.groupby("security_id")} if len(ratios) else {})

    def lookup(sid: str, day: pd.Timestamp):
        s_ = by.get(sid)
        if s_ is None or s_.empty or day < s_.index.min():
            return None
        idx = s_.index.searchsorted(day, side="right") - 1
        if idx + 1 < len(s_):
            d0, d1 = s_.index[idx], s_.index[idx + 1]
            w = (day - d0).days / max((d1 - d0).days, 1)
            return float(s_.iloc[idx] + w * (s_.iloc[idx + 1] - s_.iloc[idx]))
        return float(s_.iloc[idx])
    return lookup


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
    kinds = {"oati": "OATi", "oatei": "OAT€i", "btani": "OATi", "btanei": "OAT€i"}
    frames = []
    for s_ in linkers.itertuples(index=False):
        kind = kinds.get(s_.sub_type)
        file_kind = {"btani": "BTANi", "btanei": "BTAN€i"}.get(s_.sub_type, kind)
        key = _term_key(file_kind, s_.coupon_pct, s_.maturity_date)
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
        if len(term):
            base_date = term["base_date"].iloc[0]
            how = "the reference index at the line's base date (coefficient file)"
        elif pd.notna(s_.first_issue_date) and pd.notna(s_.maturity_date):
            # no coefficient column (matured before the 2016 history files):
            # the base date is the coupon anniversary on or before the first
            # settlement — the AFT's date de jouissance convention
            fi, mat = pd.Timestamp(s_.first_issue_date), pd.Timestamp(s_.maturity_date)
            base_date = pd.Timestamp(year=fi.year, month=mat.month, day=mat.day)
            if base_date > fi:
                base_date = pd.Timestamp(year=fi.year - 1, month=mat.month, day=mat.day)
            how = ("the reference index at the coupon anniversary on or before the first settlement (no coefficient "
                   "column for this line: matured before the 2016 history files)")
        else:
            base_date = pd.NaT
            how = ""
        if pd.notna(base_date) and (office.empty or office["date"].max() < stop - pd.Timedelta(days=45)):
            monthly = _monthly_index(kind)
            base = reference_index_3m(base_date, monthly)
            start = office["date"].max() + pd.offsets.MonthBegin(1) if len(office) else pd.Timestamp(base_date)
            if pd.notna(base) and base > 0:
                dates = pd.date_range(start.normalize(), stop, freq="MS")
                refs = np.array([reference_index_3m(d, monthly) for d in dates])
                ok = ~np.isnan(refs)
                frames.append(pd.DataFrame({
                    "security_id": s_.security_id, "date": dates[ok], "reference_index": refs[ok],
                    "index_ratio": refs[ok] / base, "ratio_source": "recomputed",
                    "source_id": A.SOURCE_INDEXATION, "part": A.INDEX_PARTS[kind],
                    "notes": "recomputed: AFT 3-month-lag formula on the AFT monthly index (base 2025) / " + how
                             + "; monthly points, linear within the month",
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
    snapshot_date = pd.Timestamp(m.loc[m["in_encours"], "as_of"].max())
    fl, stubs = flows(run_id, m, snapshot_date)
    first = (fl[fl["flow_type"].isin(["auction", "tender", "syndication"])].groupby("security_id")["settlement_date"].min()
             if len(fl) else pd.Series(dtype="datetime64[ns]"))
    secs = securities(run_id, m, first)
    ratios = index_ratios(run_id, secs, snapshot_date)
    pos = positions(run_id, m, fl, secs, ratios, stubs, snapshot_date)
    return {"debt_securities": secs, "debt_positions": pos, "debt_flows": fl, "debt_index_ratios": ratios}


def class_aggregates_rows() -> pd.DataFrame:
    """The FRA rows of the aggregate layer (the canonical file)."""
    from ggfiscal import config
    path = config.repo_root() / "data" / "canonical" / "debt_class_aggregates.csv"
    if not path.exists():
        return pd.DataFrame(columns=["iso3", "year", "instrument_class", "sub_type", "measure", "value_lcu_mn"])
    df = pd.read_csv(path)
    return df[df["iso3"] == ISO3].copy()


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
