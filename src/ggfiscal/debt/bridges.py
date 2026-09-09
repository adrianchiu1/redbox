"""DEBT_KICKOFF.md §8 (DD4/DD5): the **official** bridge items of step B —
and, where a publisher provides one, step C — of the two reconciliation
chains.

`bridge_items(iso3, chain, year)` returns `ChainItem`s in millions of
national currency, all `item_type="official"`, signed so that

    carried + Σ items ≈ official_total

at the step they name. Nothing here is adjusted, netted or balanced: every
value is one published cell, and the sign applied to it is stated in the
item's `basis`. Whatever the published items do not explain stays in the
step's residual (D16) — `assemble` computes it.

Sign conventions of the two chains (`chains.py`):

* interest  — everything in D.41-payable sign (+ = interest expenditure);
* financing — everything in **net-borrowing** sign (+ = borrowing), so the
  step-B official total is −B.9 of S.1311 and the step-C total is −NLB.

What each country contributes
-----------------------------

**GBR, financing, step B** (carried = M98R central-government net cash
requirement, official = CG net borrowing −NMFJ). ONS PSF Appendix A
publishes the identity twice over. REC2 ("Reconciliation of central
government net borrowing and net cash requirement", note 74) states

    RUUX = −NMFJ + ANRH + ANRS + ANRU + ANRT + ANRV

i.e. *net cash requirement on own account = net borrowing + the five
reconciling columns*; PSA7C ("Central government net cash requirement",
notes 83–86) states the coverage difference between that RUUX and the
Appendix S carried value M98R:

    RUUX = M98R + M98W + MUI2 − ABEC − ABEI

(M98R excludes NRAM/B&B and Network Rail and RUUX is "own account", i.e.
net of central government's payments to local government and to public
corporations). Substituting gives the nine items emitted here, and the
identity closes to ≤ £2 m — ONS rounding — for every calendar year 1998
to 2025.

**GBR, interest, step B**: none. Carried is the National Loans Fund's
accrued finance costs of borrowing (which include the index-linked
uplift, NS&I and the other NLF costs) and the official total is ONS NMFX
(S.1311 D.41 payable). Neither ONS nor HM Treasury publishes a
reconciliation between the two, so no item is emitted and the whole wedge
stays in the residual.

**GBR, step C** (S.1311 → S.13). UK general government is central plus
local government, so one published subsector column closes each chain:
PSA6J_1 `NUGW` local-government interest payable, and PSA2 `-NMOE` local
government net borrowing (already published in + = borrowing sign, so the
sub-sector columns add: −NMFJ + −NMOE = −NNBK, the Maastricht deficit,
exactly). Appendix A publishes **no** intra-general-government interest
consolidation line — PSA6I `ANPZ` is local government's *net receipt* of
interest and dividends from the whole public sector, not the D.41 flow
consolidated out of general government — so none is emitted.

**FRA / DEU, financing, step B**: Eurostat `gov_10dd_edpt3` (the EDP
stock-flow adjustment, `sfa_components(iso3)`), sector S1311, in MIO_NAC.
Eurostat's published identity is

    GD_CH = B9_T3 + F_ASS + ORADJ + YA3

with `B9_T3` already in net-borrowing sign ("net lending (−)/net
borrowing (+), reversed sign"), `F_ASS = ΣF*_ASS`, `ORADJ = ORINV + ORRNV
+ ORFCD + ORD41A_ADJ + F8_ADJ_LIAB + F71_ADJ_LIAB + FV_ADJ_LIAB + KX +
K61`, and `GD_CH` the change in the subsector's consolidated gross debt.
The chain runs from **net issuance of securities** (the register) to net
borrowing, so the change in gross debt is split by instrument using
`gov_10q_ggdebt` end-of-Q4 stocks (same vintage, same MIO_NAC face value;
`ΔF2 + ΔF3 + ΔF4 = GD_CH` to ≤ 0.3 EUR mn), the two **non**-securities
legs are emitted as items, and every asset/adjustment/discrepancy item is
emitted with its sign reversed:

    B9_T3 = ΔF3 + [ΔF2 + ΔF4 − F_ASS-components − ORADJ-components − YA3]

so the residual left at step B is exactly `ΔF3 − carried`: the wedge
between the change in the subsector's Maastricht debt securities and the
chain's carried value. For FRA (step A blocked, carried = the register
itself) that is the register-vs-Maastricht coverage difference. For DEU
the carried value is the core-budget Nettokreditaufnahme, which excludes
the Sondervermögen that *are* inside S.1311's debt, so the DEU residual
also carries that scope difference — see reports/debt_sources/bridges.md.

**DEU, interest, step B**: `gov_10dd_edpt3` `ORD41A_ADJ` — "difference
between interest expenditure (D.41) accrued (−) and paid (+)" — is
published for DE/S1311, so `accrued = paid − ORD41A_ADJ` and the item is
emitted with the sign reversed. It is the only official accrued-vs-paid
interest item for the subsector; it does not (and cannot) explain the
agio/disagio timing of Kap. 3205, which stays in the residual.

**FRA, interest, step B**: none — step A is blocked (no carried value).

Steps C for FRA and DEU are already assembled by `chains.py` from
`gov_10a_main` subsector D41PAY / B9 and are not repeated here.
"""

from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from ggfiscal.debt.reconcile import ChainItem

STEP_B = {"interest": "B_s1311_d41", "financing": "B_s1311_b9"}
STEP_C = {"interest": "C_s13_gf01_7", "financing": "C_s13_nlb"}

ONS_APPENDIX_A = "ONS_PSF_APPENDIX_A"
EUROSTAT_DD = "EUROSTAT_GOV10DD"

# --- GBR, financing, step B -------------------------------------------------
# REC2 (note 74): net cash requirement RUUX = net borrowing (-NMFJ) + these.
GBR_REC2_ADJUSTMENTS = ("ANRH", "ANRS", "ANRU", "ANRT", "ANRV")
# PSA7C (notes 83-86): RUUX = M98R + M98W + MUI2 - ABEC - ABEI.
GBR_PSA7C_COVERAGE = (("M98W", +1, "nram_and_bb_net_cash_requirement"),
                      ("MUI2", +1, "network_rail_net_cash_requirement"),
                      ("ABEC", -1, "less_payments_to_local_government"),
                      ("ABEI", -1, "less_payments_to_public_corporations"))

# --- GBR, step C ------------------------------------------------------------
GBR_STEP_C = {"interest": ("PSA6J_1", "NUGW", "local_government_d41"),
              "financing": ("PSA2", "-NMOE", "local_government_net_borrowing")}

# --- FRA / DEU, financing, step B (gov_10dd_edpt3, sector S1311) ------------
EDPT3_ASSETS = ("F2_ASS", "F3_ASS", "F4_ASS", "F5_ASS", "F71_ASS", "F8_ASS", "FN_ASS")
EDPT3_ADJUSTMENTS = ("ORINV", "ORRNV", "ORFCD", "ORD41A_ADJ", "F8_ADJ_LIAB",
                     "F71_ADJ_LIAB", "FV_ADJ_LIAB", "KX", "K61")
EDPT3_DISCREPANCY = ("YA3",)
# short, stable item-name stems; the full Eurostat label goes in `basis`
EDPT3_STEM = {
    "F2_ASS": "currency_and_deposits", "F3_ASS": "debt_securities", "F4_ASS": "loans",
    "F5_ASS": "equity_and_investment_fund_shares", "F71_ASS": "financial_derivatives",
    "F8_ASS": "other_accounts_receivable", "FN_ASS": "other_financial_assets",
    "ORINV": "issuance_above_below_par", "ORRNV": "redemption_above_below_nominal",
    "ORFCD": "foreign_currency_debt_revaluation",
    "ORD41A_ADJ": "interest_accrued_less_paid", "F8_ADJ_LIAB": "other_accounts_payable",
    "F71_ADJ_LIAB": "derivative_liabilities", "FV_ADJ_LIAB": "other_liabilities",
    "KX": "other_volume_changes", "K61": "sector_reclassification",
    "YA3": "statistical_discrepancy",
}
EDPT3_OTHER_LIABILITIES = (("F2", "currency_and_deposits"), ("F4", "loans"))


# ---------------------------------------------------------------- public

def bridge_items(iso3: str, chain: str, year: int) -> list[ChainItem]:
    """Official bridge items for step B (and step C where a source exists)
    of one chain, one country, one calendar year. Empty where the
    publisher provides no bridge or the year is outside the source's
    coverage — never a fabricated or balancing item."""
    if chain not in STEP_B:
        raise ValueError(f"unknown chain {chain!r}; expected 'interest' or 'financing'")
    year = int(year)
    if iso3 == "GBR":
        items = _gbr_financing_b(year) if chain == "financing" else []
        return items + _gbr_step_c(chain, year)
    if iso3 in ("FRA", "DEU"):
        if chain == "financing":
            return _eu_financing_b(iso3, year)
        if iso3 == "DEU":
            return _deu_interest_b(year)
        return []
    return []


# ------------------------------------------------------------------ GBR

@lru_cache(maxsize=None)
def _gbr_sheet(sheet: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """(calendar-year block, monthly sums, monthly counts, cdid -> label) for
    one Appendix A worksheet, wide by CDID."""
    from ggfiscal.debt.readers import ons_hmt as O
    if sheet in ("REC2", "REC3"):
        d = O.cgncr_reconciliation()
        d = d[d["sheet"] == sheet]
    else:
        d = O.psa_table(sheet)
    cy = d[d["period_type"] == "CY"]
    wide = cy.pivot_table(index=cy["period_start"].dt.year, columns="cdid", values="value")
    m = d[d["period_type"] == "M"]
    msum = m.pivot_table(index=m["period_start"].dt.year, columns="cdid",
                         values="value", aggfunc="sum")
    mcount = m.pivot_table(index=m["period_start"].dt.year, columns="cdid",
                           values="value", aggfunc="size")
    cols = O.psa_table_columns(sheet)
    labels = dict(zip(cols["cdid"], cols["column_label"]))
    return wide, msum, mcount, labels


def _gbr_cell(sheet: str, cdid: str, year: int) -> tuple[float | None, str]:
    """One Appendix A cell for a calendar year, with the period basis used.

    The calendar-year block is preferred; where a sheet publishes only
    financial years the 12 calendar months of the monthly block are summed
    instead and the basis says so (DD6: calendar year is canonical)."""
    wide, msum, mcount, _ = _gbr_sheet(sheet)
    if cdid in wide.columns and year in wide.index and pd.notna(wide.at[year, cdid]):
        return float(wide.at[year, cdid]), "calendar-year block"
    if cdid in mcount.columns and year in mcount.index and int(mcount.at[year, cdid]) == 12:
        return float(msum.at[year, cdid]), "sum of the 12 calendar months (no CY block)"
    return None, "not published for this year"


def _gbr_label(sheet: str, cdid: str) -> str:
    return _clean_label(_gbr_sheet(sheet)[3].get(cdid, cdid))


def _gbr_item(sheet: str, cdid: str, year: int, sign: int, step: str,
              name: str, basis: str, why: str) -> ChainItem | None:
    value, period = _gbr_cell(sheet, cdid, year)
    if value is None:
        return None
    label = _gbr_label(sheet, cdid)
    return ChainItem(step, name, sign * value, "official", ONS_APPENDIX_A,
                     f"{basis}; Appendix A {sheet} {cdid} '{label}', {period}; "
                     f"sign {'+' if sign > 0 else '-'}1 ({why})")


def _gbr_financing_b(year: int) -> list[ChainItem]:
    """M98R (carried) -> central government net borrowing (-NMFJ)."""
    step = STEP_B["financing"]
    out: list[ChainItem] = []
    for cdid, sign, name in GBR_PSA7C_COVERAGE:
        it = _gbr_item("PSA7C", cdid, year, sign, step, name, "cash",
                       "PSA7C notes 83-86: RUUX = M98R + M98W + MUI2 - ABEC - ABEI")
        if it is not None:
            out.append(it)
    for cdid in GBR_REC2_ADJUSTMENTS:
        name = _slug_name(_gbr_label("REC2", cdid), -1)
        it = _gbr_item("REC2", cdid, year, -1, step, name, "cash to accrued",
                       "REC2 note 74: RUUX = -NMFJ + ANRH + ANRS + ANRU + ANRT + ANRV")
        if it is not None:
            out.append(it)
    return out


def _gbr_step_c(chain: str, year: int) -> list[ChainItem]:
    """S.1311 -> S.13: UK general government is central + local government."""
    sheet, cdid, name = GBR_STEP_C[chain]
    basis = ("accrued" if chain == "interest" else "accrued, net borrowing = -B.9")
    it = _gbr_item(sheet, cdid, year, +1, STEP_C[chain], name, basis,
                   "S.13 = S.1311 + S.1313; UK has no state government or "
                   "social security funds subsector")
    return [] if it is None else [it]


# ------------------------------------------------------------- FRA / DEU

@lru_cache(maxsize=None)
def _edpt3(iso3: str) -> tuple[pd.DataFrame, dict, str]:
    """(gov_10dd_edpt3 wide by na_item x year, na_item -> label, sector used)."""
    from ggfiscal.debt.readers import eurostat_insee_oecd as E
    d = E.sfa_components(iso3)
    d = d[d["table"] == "edpt3"]
    sector = "S1311" if "S1311" in set(d["sector"]) else "S13"
    d = d[d["sector"] == sector].dropna(subset=["value"])
    if d.empty:
        return pd.DataFrame(), {}, sector
    wide = d.pivot_table(index=d["time_period"].astype(int), columns="na_item", values="value")
    labels = dict(zip(d["na_item"], d["na_item_label"]))
    return wide, labels, sector


@lru_cache(maxsize=None)
def _debt_stock(iso3: str, sector: str) -> pd.DataFrame:
    """gov_10q_ggdebt end-of-Q4 stocks by instrument, wide by na_item x year."""
    from ggfiscal.debt.readers import eurostat_insee_oecd as E
    q = E.quarterly_debt(iso3, sector)
    if q.empty:
        return pd.DataFrame()
    q = q[q["time_period"].str.endswith("Q4")].dropna(subset=["value"])
    return q.pivot_table(index=q["time_period"].str[:4].astype(int),
                         columns="na_item", values="value")


def _eu_financing_b(iso3: str, year: int) -> list[ChainItem]:
    wide, labels, sector = _edpt3(iso3)
    if wide.empty or year not in wide.index:
        return []
    stock = _debt_stock(iso3, sector)
    if stock.empty or year not in stock.index or (year - 1) not in stock.index:
        return []
    step = STEP_B["financing"]
    row = wide.loc[year]
    out: list[ChainItem] = []

    for code, stem in EDPT3_OTHER_LIABILITIES:
        if code not in stock.columns:
            continue
        d = stock.at[year, code] - stock.at[year - 1, code]
        if pd.isna(d):
            continue
        out.append(ChainItem(
            step, f"net_issuance_other_liabilities_{stem}", float(d), "official", EUROSTAT_DD,
            f"nominal (face value); gov_10q_ggdebt {sector} {code} end-Q4 stock, "
            f"{year} less {year - 1}; sign +1 (debt not issued as securities still "
            "adds to net borrowing)"))

    for group, codes, why in (
        ("less_net_acquisition", EDPT3_ASSETS,
         "gov_10dd_edpt3 identity GD_CH = B9_T3 + F_ASS + ORADJ + YA3, solved for B9_T3"),
        ("less_sfa_adjustment", EDPT3_ADJUSTMENTS,
         "component of ORADJ in GD_CH = B9_T3 + F_ASS + ORADJ + YA3, solved for B9_T3"),
        ("less", EDPT3_DISCREPANCY,
         "gov_10dd_edpt3 identity GD_CH = B9_T3 + F_ASS + ORADJ + YA3, solved for B9_T3"),
    ):
        for code in codes:
            if code not in wide.columns or pd.isna(row.get(code)):
                continue
            out.append(ChainItem(
                step, f"{group}_{EDPT3_STEM[code]}", -float(row[code]) + 0.0, "official", EUROSTAT_DD,
                f"accrual/valuation; gov_10dd_edpt3 {sector} {code} "
                f"'{labels.get(code, '')}', sign -1 ({why})"))
    return out


def _deu_interest_b(year: int) -> list[ChainItem]:
    """Kap. 3205 Verzinsung (cash-like) -> S.1311 D.41 payable (accrued)."""
    wide, labels, sector = _edpt3("DEU")
    if wide.empty or "ORD41A_ADJ" not in wide.columns or year not in wide.index:
        return []
    v = wide.at[year, "ORD41A_ADJ"]
    if pd.isna(v):
        return []
    return [ChainItem(
        STEP_B["interest"], "d41_accrued_less_paid_adjustment", -float(v) + 0.0, "official",
        EUROSTAT_DD,
        f"accrued less paid; gov_10dd_edpt3 {sector} ORD41A_ADJ "
        f"'{labels.get('ORD41A_ADJ', '')}' = paid - accrued, sign -1 "
        "(accrued = paid - ORD41A_ADJ)")]


# ---------------------------------------------------------------- naming

def _clean_label(label: str) -> str:
    t = re.sub(r"\[note[^\]]*\]", " ", str(label))
    t = re.sub(r"\(\s*£?\s*million[^)]*\)", " ", t)
    return re.sub(r"\s+", " ", t.replace("£", " ")).strip(" ,;")


def _slug_name(label: str, sign: int) -> str:
    from ggfiscal.debt.aggregates import _slug
    stem = _slug(_clean_label(label))
    return f"less_{stem}" if sign < 0 else stem
