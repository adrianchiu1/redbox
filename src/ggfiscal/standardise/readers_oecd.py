"""OECD SNA table readers — the `oecd_sna` anchor family's cells
(REPLICATION_KICKOFF.md D18, §11.2, §11.3; Stage U0, D-S16-002).

The national statistical office's own data as it re-presents them on the
SNA 2008 framework for the OECD (BEA for USA, ESRI for JPN), served by
`sdmx.oecd.org` as SDMX-CSV with a UNIT_MULT column:

  OECD_T12_{EXP,REV,BAL}  DSD_NASEC10@DF_TABLE12_{EXP,REV,BAL},1.1 — government
                          non-financial accounts (S13): payable items, receivable
                          items, balancing items; key A.{iso3}.S13..........
  OECD_T10                DSD_NASEC10@DF_TABLE10,1.1 — taxes and social
                          contributions receipts detail (D51M/D51O, D214A, D611/D613,
                          D59, D91); same key
  OECD_T11                DSD_NASEC10@DF_TABLE11,1.1 — expenditure by function
                          (readers.oecd_t11_cofog, unchanged; the transaction
                          reader here serves the D4-by-function cross-check)
  OECD_T1                 DSD_NAMAIN10@DF_TABLE1_EXPENDITURE,2.0 — GDP (B1GQ),
                          current prices, national currency; resolved live in U0
                          (the catalog carries no plain DF_TABLE1 GDP flow with an
                          XDC current-price series other than the expenditure
                          approach); 12-dim key A.{iso3}...B1GQ.......
  OECD_EO                 DSD_EO@DF_EO,1.5 — Economic Outlook general-government
                          measures (XDC in units, UNIT_MULT 0; ratios in PT_B1GQ)

Every reader is the `_oecd_frame` pattern of `standardise.readers`
(latest usable snapshot per (source_id, part=iso3), OBS_VALUE numeric) with
values scaled to LCU millions through UNIT_MULT. Readers of the three
existing families are untouched.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal.standardise.readers import _oecd_frame, _to_millions, _year_series

T12_FLOWS = ("EXP", "REV", "BAL")


def _empty() -> pd.Series:
    return pd.Series(dtype=float)


def oecd_t12(iso3: str, item: str, flow: str) -> pd.Series:
    """One TRANSACTION of DF_TABLE12_{flow} (S13, XDC), LCU millions.
    `flow` is EXP (payable / uses), REV (receivable / resources) or BAL
    (balancing items: B9, B8G, B2N, ...)."""
    flow = flow.upper()
    if flow not in T12_FLOWS:
        raise ValueError(f"OECD T12 flow must be one of {T12_FLOWS}, got {flow!r}")
    df = _oecd_frame(f"OECD_T12_{flow}", iso3)
    if df.empty:
        return _empty()
    return _to_millions(df[(df["TRANSACTION"] == item) & (df["UNIT_MEASURE"] == "XDC")])


def oecd_t10(iso3: str, code: str) -> pd.Series:
    """One TRANSACTION of DF_TABLE10 (taxes and social contributions detail,
    S13, XDC), LCU millions."""
    df = _oecd_frame("OECD_T10", iso3)
    if df.empty:
        return _empty()
    return _to_millions(df[(df["TRANSACTION"] == code) & (df["UNIT_MEASURE"] == "XDC")])


def oecd_t11_item(iso3: str, cofog: str, transaction: str) -> pd.Series:
    """DF_TABLE11: one transaction (D4, D1, P2, ...) of one function — the
    D4 × GF01 cross-check of kickoff §4.1 (OTE per function is
    readers.oecd_t11_cofog)."""
    df = _oecd_frame("OECD_T11", iso3)
    if df.empty:
        return _empty()
    return _to_millions(df[(df["EXPENDITURE"] == cofog) & (df["TRANSACTION"] == transaction)])


def oecd_t1_gdp(iso3: str) -> pd.Series:
    """DF_TABLE1_EXPENDITURE: B1GQ, current prices (PRICE_BASE V), national
    currency (XDC), LCU millions — the D18 denominator, same vintage as the
    government tables."""
    df = _oecd_frame("OECD_T1", iso3)
    if df.empty:
        return _empty()
    sel = df[(df["TRANSACTION"] == "B1GQ") & (df["UNIT_MEASURE"] == "XDC")
             & (df["PRICE_BASE"] == "V")]
    return _to_millions(sel)


def oecd_eo(iso3: str, measure: str) -> pd.Series:
    """DF_EO: one general-government measure. Currency measures (XDC) are
    scaled to LCU millions; ratio measures (PT_B1GQ: NLGQ, GGFLQ) are
    returned as published (% of GDP)."""
    df = _oecd_frame("OECD_EO", iso3)
    if df.empty:
        return _empty()
    sel = df[df["MEASURE"] == measure]
    if sel.empty:
        return _empty()
    if (sel["UNIT_MEASURE"] == "XDC").all():
        return _to_millions(sel)
    return _year_series(zip(sel["TIME_PERIOD"], sel["OBS_VALUE"]))
