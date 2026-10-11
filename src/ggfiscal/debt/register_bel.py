"""BEL per-security register (EU3_KICKOFF.md Stage ED3, D-S17-016) from the
Belgian Debt Agency's "outstanding" page (`BEL_BDA/olo_outstanding_html`).

The page carries four tables, each with its own date:

=========================== ===================================== ============
OLO lines                   ISIN, maturity, coupon, net outstanding  trade date
                            (buy-backs in portfolio excluded), buy-backs
                            in portfolio, capital stripped
Treasury Certificates (TC)  ISIN, maturity, nominal, net amount paid
EMTN / other bonds          one row per tap (Nr 79, 79B ...): value date,
                            ISIN, currency, amount, coupon (fixed, Euribor
                            6M + spread, or "inflation coef. * c"),
                            EUR equivalent
Schuldscheine               loans without ISIN — outside DD1 (marketable
                            securities), not entered
=========================== ===================================== ============

``build(run_id)`` returns ``debt_securities`` and ``debt_positions``
(``office_snapshot`` at each table's own date; amounts EUR mn, the EMTN
lines at the agency's EUR equivalent, with the issue-currency amount
alongside). There are no flows (no auction history is published as a
file), so the register enters no chain year (``register.register_sums``
needs a 1 January anchor) and the maturity profile at the latest date
covers the lines dated that day (the OLOs).
"""

from __future__ import annotations

import io
import re

import pandas as pd

from ggfiscal.debt.model import POSITIONS, SECURITIES
from ggfiscal.debt.readers import snap_path
from ggfiscal.standardise.readers import latest_snapshots

ISO3 = "BEL"
SOURCE = "BEL_BDA"
PART = "olo_outstanding_html"
_DATE_RE = re.compile(r"[Oo]utstanding at\s+(\d{2})\.(\d{2})\.(\d{4})")
_FLOAT_RE = re.compile(r"Euribor(\d+)M\s*\+\s*([\d.]+)")
_INFL_RE = re.compile(r"inflation coef\.\s*\*\s*([\d.]+)")


def _sha() -> str | None:
    e = latest_snapshots().get((SOURCE, PART))
    return e["sha256"] if e else None


def _date(s) -> pd.Timestamp | None:
    return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce") if isinstance(s, str) else None


def page_tables() -> tuple[list[pd.DataFrame], list[pd.Timestamp]]:
    """The page's tables and the 'Outstanding at dd.mm.yyyy' dates, in page
    order (the HTML is UTF-8; pandas reads the four tables)."""
    html = snap_path(SOURCE, PART).read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S))
    text = re.sub(r"(&nbsp;|\s)+", " ", text)
    dates = [pd.Timestamp(int(y), int(m), int(d)) for d, m, y in _DATE_RE.findall(text)]
    return pd.read_html(io.StringIO(html)), dates


def _col(df: pd.DataFrame, start: str) -> str:
    hit = [c for c in df.columns if str(c).replace("\xa0", " ").strip().startswith(start)]
    if len(hit) != 1:
        raise KeyError(f"BDA table: expected one column starting {start!r}, got {list(df.columns)}")
    return hit[0]


def _sec(isin, name, klass, sub, maturity, *, coupon=None, freq=1, first=None,
         currency="EUR", floating=None, spread=None, index=None, notes=None, run_id="", sha=None):
    return {"iso3": ISO3, "security_id": isin, "isin": isin, "name": name,
            "instrument_class": klass, "sub_type": sub, "currency": currency,
            # the register_fra convention: frequency 1 for bills, ACT/360 on them
            "coupon_pct": coupon, "coupon_frequency": freq,
            "day_count": "ACT/360" if klass in ("bill", "floating") else "ACT/ACT",
            "first_issue_date": first, "maturity_date": maturity, "first_call_date": None,
            "dividend_dates": None, "index_reference": index, "index_lag_months": None,
            "base_index": None, "floating_reference": floating, "spread_bp": spread,
            "is_green": False, "issuer_unit": "Belgian federal State (BDA)",
            "run_id": run_id, "source_id": SOURCE, "snapshot_sha256": sha,
            "quality_grade": "A", "notes": notes}


def _pos(isin, as_of, nominal, *, issue_ccy=None, own=None, run_id="", sha=None, notes=None):
    return {"iso3": ISO3, "security_id": isin, "as_of": as_of, "nominal_lcu_mn": nominal,
            "nominal_uplifted_lcu_mn": None, "nominal_issue_ccy_mn": issue_ccy,
            "official_holdings_lcu_mn": own, "market_hands_lcu_mn": None,
            "position_type": "office_snapshot", "fx_rate": None, "fx_source_id": None,
            "run_id": run_id, "source_id": SOURCE, "snapshot_sha256": sha,
            "quality_grade": "A", "notes": notes}


def _isin_rows(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Rows carrying an ISIN (drops the total and footnote rows)."""
    return df[df[col].astype(str).str.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d")]


def build(run_id: str) -> dict[str, pd.DataFrame]:
    tables, dates = page_tables()
    if len(tables) < 3 or len(dates) < 3:
        raise ValueError(f"BDA page: expected >= 3 tables and dates, got {len(tables)} / {len(dates)}")
    sha = _sha()
    secs, pos = [], []

    # --- OLO lines
    olo, d_olo = tables[0], dates[0]
    isin_c, mat_c, cpn_c = _col(olo, "ISIN"), _col(olo, "Maturity"), _col(olo, "Coupon")
    net_c, bb_c = _col(olo, "Net outstanding"), _col(olo, "Buy-backs")
    lines = _isin_rows(olo, isin_c)
    total = olo[olo[isin_c].isna()][net_c].dropna()
    if len(total) and abs(lines[net_c].sum() - total.iloc[-1]) > 1.0:
        raise ValueError(f"BDA OLO lines sum {lines[net_c].sum():,.0f} != page total {total.iloc[-1]:,.0f}")
    for _, r in lines.iterrows():
        isin, mat, cpn = r[isin_c], _date(r[mat_c]), float(r[cpn_c])
        secs.append(_sec(isin, f"OLO {cpn:g}% {mat:%d/%m/%Y}", "fixed_bullet", "olo", mat,
                         coupon=cpn, freq=1, run_id=run_id, sha=sha))
        own = float(r[bb_c]) / 1e6 if pd.notna(r[bb_c]) else None
        pos.append(_pos(isin, d_olo, float(r[net_c]) / 1e6, own=own, run_id=run_id, sha=sha,
                        notes="net outstanding excludes the buy-backs held in the Treasury's portfolio "
                              "(official_holdings_lcu_mn)"))

    # --- Treasury Certificates
    tc, d_tc = tables[1], dates[1]
    isin_c, mat_c, nom_c = _col(tc, "ISIN"), _col(tc, "Maturity"), _col(tc, "Nominal")
    for _, r in _isin_rows(tc, isin_c).iterrows():
        isin, mat = r[isin_c], _date(r[mat_c])
        secs.append(_sec(isin, f"TC {mat:%d/%m/%Y}", "bill", "treasury_certificates", mat,
                         run_id=run_id, sha=sha))
        pos.append(_pos(isin, d_tc, float(r[nom_c]) / 1e6, run_id=run_id, sha=sha))

    # --- EMTN / other bonds: one row per tap, aggregated per ISIN
    em, d_em = tables[2], dates[2]
    isin_c, mat_c, val_c = _col(em, "ISIN"), _col(em, "Maturity"), _col(em, "Value Date")
    ccy_c, amt_c, cpn_c, eur_c = _col(em, "Currency"), _col(em, "Amount"), _col(em, "Coupon"), _col(em, "EUR Equivalent")
    rows = _isin_rows(em, isin_c).copy()
    rows["_value"] = rows[val_c].map(_date)
    for isin, g in rows.groupby(isin_c, sort=False):
        r = g.iloc[0]
        if g[ccy_c].nunique() != 1 or g[cpn_c].nunique() != 1:
            raise ValueError(f"BDA EMTN {isin}: taps disagree on currency or coupon")
        mat, ccy, cpn = _date(r[mat_c]), str(r[ccy_c]), str(r[cpn_c]).strip()
        kw: dict = {"first": g["_value"].min(), "currency": ccy, "run_id": run_id, "sha": sha}
        # one ISIN has one maturity; the page shifts it by a day per tap on
        # BE6367588231 (16-22/08/2035) — the first tap's date is kept
        mat_note = ("" if g[mat_c].nunique() == 1 else
                    f"; the page lists {g[mat_c].nunique()} maturity dates across taps "
                    f"({g[mat_c].iloc[0]} .. {g[mat_c].iloc[-1]}), the first tap's is kept")
        if m := _FLOAT_RE.search(cpn):
            klass = "floating"
            kw.update(floating=f"EA_EURIBOR_{m.group(1)}M", spread=float(m.group(2)) * 100,
                      freq=12 // int(m.group(1)))
            name = f"EMTN Euribor{m.group(1)}M+{m.group(2)} {mat:%d/%m/%Y}"
        elif m := _INFL_RE.search(cpn):
            klass = "inflation_linked"
            kw.update(coupon=float(m.group(1)),
                      notes=f'coupon "{cpn}": the agency publishes no index reference for it')
            name = f"EMTN inflation-linked {m.group(1)} {mat:%d/%m/%Y}"
        else:
            klass = "fixed_bullet"
            kw.update(coupon=float(cpn), freq=1)
            name = f"EMTN {ccy} {float(cpn):g}% {mat:%d/%m/%Y}"
        if mat_note:
            kw["notes"] = (kw.get("notes") or "") + mat_note
        secs.append(_sec(isin, name, klass, "emtn", mat, **kw))
        pos.append(_pos(isin, d_em, float(g[eur_c].sum()) / 1e6,
                        issue_ccy=float(g[amt_c].sum()) / 1e6, run_id=run_id, sha=sha,
                        notes=f"{len(g)} tap(s); EUR equivalent as published by the agency"
                              + ("" if ccy == "EUR" else f"; issued in {ccy}")))

    sec_df = pd.DataFrame(secs)
    return {"debt_securities": SECURITIES.validate(sec_df),
            "debt_positions": POSITIONS.validate(pd.DataFrame(pos)),
            "debt_flows": pd.DataFrame(),
            "debt_index_ratios": pd.DataFrame()}
