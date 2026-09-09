"""DEBT_KICKOFF.md §6.3 / §8: the official intermediate totals of the two
reconciliation chains, per country and calendar year — never adjusted.

Interest chain (DD4):   A_cg_cash      finance-ministry central-government interest
                        B_s1311_d41    S.1311 D.41 payable, national accounts
                        C_s13_gf01_7   the package's GF01_7 (strict)
Financing chain (DD5):  A_cg_cash_requirement  CG net cash requirement /
                                       besoin de financement / Nettokreditaufnahme
                        B_s1311_b9     S.1311 net lending/borrowing
                        C_s13_nlb      the package's NLB (strict)

Each row records where the value came from, its native basis, and — for
GBR financial-year sources — the §7.10 conversion applied (DD6). Where a
source is blocked (OQ-8) the row is present with a null value and the
source named, so the chain publishes a null residual rather than a
fabricated total.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.standardise.readers import latest_snapshots

COLUMNS = ["iso3", "year", "chain", "step", "value_lcu_mn", "item_source_id", "basis",
           "period_basis", "period_conversion_method", "snapshot_sha256", "quality_grade", "notes"]


def _sha(source_id: str, part: str) -> str | None:
    e = latest_snapshots().get((source_id, part))
    return e["sha256"] if e else None


def fy_to_cy(fy: pd.Series) -> pd.Series:
    """§7.10: CY_t = 0.25 × FY_{t−1/t} + 0.75 × FY_{t/t+1}, FY indexed by its
    starting calendar year. Consumes one year at the end."""
    fy = fy.sort_index().astype(float)
    out = {}
    for t in fy.index:
        if (t - 1) in fy.index:
            out[t] = 0.25 * fy[t - 1] + 0.75 * fy[t]
    return pd.Series(out, dtype=float)


def _row(iso3, year, chain, step, value, source, basis, period_basis="CY",
         conversion=None, sha=None, grade="A", notes=None) -> dict:
    return {"iso3": iso3, "year": int(year), "chain": chain, "step": step,
            "value_lcu_mn": None if value is None or pd.isna(value) else float(value),
            "item_source_id": source, "basis": basis, "period_basis": period_basis,
            "period_conversion_method": conversion, "snapshot_sha256": sha,
            "quality_grade": grade, "notes": notes}


def _blocked_rows(iso3, chain, step, source, basis, years) -> list[dict]:
    return [_row(iso3, y, chain, step, None, source, basis, grade="D",
                 notes=f"{source} unreachable (OQ-8): no official total") for y in years]


# ------------------------------------------------------------- package legs

def package_gf01_7(iso3: str) -> pd.Series:
    from ggfiscal.build import load_canonical
    df = load_canonical("COFOG", "strict")
    s = df[(df["iso3"] == iso3) & (df["line_code"] == "GF01_7") & (~df["is_forecast"].astype(bool))]
    return s.set_index("year")["value_lcu_mn"].sort_index()


def package_nlb(iso3: str) -> pd.Series:
    from ggfiscal.build import load_ledger
    df = load_ledger()
    df.columns = [c.lower() for c in df.columns]
    var = df["series_variant"] if "series_variant" in df.columns else df["variant"]
    s = df[(df["iso3"] == iso3) & (var == "strict")]
    col = "nlb_lcu_mn" if "nlb_lcu_mn" in s.columns else "nlb"
    return s.set_index("year")[col].sort_index()


# ------------------------------------------------------------------ GBR

def _gbr_interest(years) -> list[dict]:
    from ggfiscal.debt.readers import ons_hmt as O
    rows = []
    # step A: HM Treasury National Loans Fund Account — finance costs of
    # borrowing (accruals) per financial year; the cash-flow "interest paid"
    # is carried in notes. Converted to calendar year per §7.10.
    fy_total, fy_cash, editions = {}, {}, {}
    for (sid, part), e in latest_snapshots().items():
        if sid != "HMT_NLF":
            continue
        try:
            n = O.nlf_interest_summary(part)
        except Exception:      # unreadable edition: documented in the family report
            continue
        if n.empty:
            continue
        start = int(part[:4])
        tot = n[n["item"] == "total"]["value"]
        cash = n[n["item"] == "interest_paid_cash"]["value"]
        if not tot.empty:
            fy_total[start] = float(tot.iloc[0])
            fy_cash[start] = float(cash.iloc[0]) if not cash.empty else None
            editions[start] = (part, e["sha256"])
    cy = fy_to_cy(pd.Series(fy_total)) if fy_total else pd.Series(dtype=float)
    for y in years:
        if y in cy.index:
            rows.append(_row("GBR", y, "interest", "A_cg_cash", cy[y], "HMT_NLF", "accrued_nlf_finance_costs",
                             "FY", "0.25*FY(t-1/t)+0.75*FY(t/t+1) (§7.10)", editions[y][1],
                             notes=f"NLF total finance costs of borrowing; FY {editions[y-1][0]} and {editions[y][0]}; "
                                   f"cash interest paid FY{editions[y][0]}: {fy_cash.get(y)}"))
        else:
            rows.append(_row("GBR", y, "interest", "A_cg_cash", None, "HMT_NLF", "accrued_nlf_finance_costs",
                             "FY", None, None, grade="D", notes="no NLF edition pair for this year"))
    # step B: ONS PSA6B_2 CG interest payable (NMFX), calendar-year block
    ci = O.cg_interest()
    nmfx = ci[(ci["cdid"] == "NMFX") & (ci["period_type"] == "CY")].set_index(ci[(ci["cdid"] == "NMFX") & (ci["period_type"] == "CY")]["period_start"].dt.year)["value"]
    for y in years:
        rows.append(_row("GBR", y, "interest", "B_s1311_d41", nmfx.get(y), "ONS_PSF_APPENDIX_A", "accrued",
                         sha=_sha("ONS_PSF_APPENDIX_A", "appendix_a"),
                         notes="PSA6B_2 central government interest payable (D.41), calendar year"))
    return rows


def _gbr_financing(years) -> list[dict]:
    from ggfiscal.debt.readers import ons_hmt as O
    rows = []
    fin = O.cgncr_financing()
    m = fin[(fin["cdid"] == "M98R") & (fin["period_type"] == "M")]
    cy = m.groupby(m["period_start"].dt.year)["value"].sum()
    nmonths = m.groupby(m["period_start"].dt.year)["value"].size()
    for y in years:
        v = cy.get(y) if nmonths.get(y, 0) == 12 else None
        rows.append(_row("GBR", y, "financing", "A_cg_cash_requirement", v, "ONS_PSF_APPENDIX_S", "cash",
                         "M", "sum of 12 calendar months", _sha("ONS_PSF_APPENDIX_S", "appendix_s"),
                         notes="M98R CGNCR excl. NRAM/B&B/Network Rail; sign: + = borrowing"))
    ci = O.cg_interest()
    nb = ci[(ci["cdid"] == "-NMFJ") & (ci["period_type"] == "CY")]
    nb = nb.set_index(nb["period_start"].dt.year)["value"]
    for y in years:
        v = nb.get(y)
        rows.append(_row("GBR", y, "financing", "B_s1311_b9", None if v is None or pd.isna(v) else -float(v),
                         "ONS_PSF_APPENDIX_A", "accrued", sha=_sha("ONS_PSF_APPENDIX_A", "appendix_a"),
                         notes="PSA6B_2 central government net borrowing (NMFJ) with sign flipped to B.9 net lending"))
    return rows


# ------------------------------------------------------------- FRA / DEU

def _eurostat_rows(iso3: str, years, chain: str, step: str, item: str) -> list[dict]:
    from ggfiscal.debt.readers import eurostat_insee_oecd as E
    s = E.d41pay(iso3, "S1311") if item == "D41PAY" else E.b9(iso3, "S1311")
    geo = {"FRA": "FR", "DEU": "DE"}[iso3]
    sha = _sha("EUROSTAT_GOV10A_MAIN_S1311", f"gov_10a_main_S1311_{item}_{geo}") or _sha("EUROSTAT_GOV10A_MAIN_S1311", f"gov_10a_main_{geo}")
    return [_row(iso3, y, chain, step, s.get(y), "EUROSTAT_GOV10A_MAIN_S1311", "accrued", sha=sha,
                 notes=f"gov_10a_main S1311 {item}") for y in years]


def _deu_step_a(years, chain: str) -> list[dict]:
    """BMF Datenportal / Kreditaufnahmebericht (reachable). Filled by the
    BMF family reader; until it exposes annual totals the rows are null."""
    try:
        from ggfiscal.debt.readers import bmf as BMF
        fn = getattr(BMF, "bund_interest_annual" if chain == "interest" else "bund_net_borrowing_annual", None)
    except Exception:
        fn = None
    step = "A_cg_cash" if chain == "interest" else "A_cg_cash_requirement"
    if fn is None:
        return [_row("DEU", y, chain, step, None, "BMF_DATENPORTAL", "cash", grade="D",
                     notes="BMF reader does not yet expose an annual total") for y in years]
    s = fn()
    sha = _sha("BMF_DATENPORTAL", "kredit_brutto_tilgung_zinsen_xlsx")
    return [_row("DEU", y, chain, step, s.get(y), "BMF_DATENPORTAL", "cash", sha=sha,
                 notes=s.attrs.get("note")) for y in years]


# ---------------------------------------------------------------- public

def official_totals(run_id: str, first_year: int = 1990) -> pd.DataFrame:
    rows: list[dict] = []
    for iso3 in config.COUNTRIES:
        g = package_gf01_7(iso3)
        n = package_nlb(iso3)
        years = list(range(first_year, int(max(g.index.max(), n.index.max())) + 1))
        # step C: the package
        rows += [_row(iso3, y, "interest", "C_s13_gf01_7", g.get(y), "package_GF01_7", "accrued",
                      notes="expenditure_long_strict GF01_7, actuals only") for y in years]
        rows += [_row(iso3, y, "financing", "C_s13_nlb", n.get(y), "package_NLB", "accrued",
                      notes="balance_ledger strict NLB") for y in years]
        if iso3 == "GBR":
            rows += _gbr_interest(years)
            rows += _gbr_financing(years)
        elif iso3 == "FRA":
            rows += _blocked_rows("FRA", "interest", "A_cg_cash", "FRA_PLF_P117", "cash_budgetaire", years)
            rows += _eurostat_rows("FRA", years, "interest", "B_s1311_d41", "D41PAY")
            rows += _blocked_rows("FRA", "financing", "A_cg_cash_requirement", "FRA_AFT_FINANCEMENT", "cash", years)
            rows += _eurostat_rows("FRA", years, "financing", "B_s1311_b9", "B9")
        else:
            rows += _deu_step_a(years, "interest")
            rows += _eurostat_rows("DEU", years, "interest", "B_s1311_d41", "D41PAY")
            rows += _deu_step_a(years, "financing")
            rows += _eurostat_rows("DEU", years, "financing", "B_s1311_b9", "B9")
    out = pd.DataFrame(rows, columns=COLUMNS)
    out.insert(0, "run_id", run_id)
    return out.sort_values(["iso3", "chain", "year", "step"]).reset_index(drop=True)
