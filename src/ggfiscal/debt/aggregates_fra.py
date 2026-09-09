"""FRA aggregate class-level layer (DD8, `debt_class_aggregates` per
`ggfiscal.debt.aggregates`): the État's negotiable-debt totals by instrument
class, from the two reachable official aggregate sources.

AFT itself (`www.aft.gouv.fr`), the Banque de France web-stat service and
`www.budget.gouv.fr` are outside the allowlist (§15 Q-D1), so the AFT
"encours de la dette négociable" figures arrive here through INSEE's
redistribution of them (BDM `serie/ajax`, source `INSEE_AFT_AGG`, monthly
2009-01 onward) and the ESA instrument split arrives through Eurostat's
quarterly government debt table (`gov_10q_ggdebt`, source
`EUROSTAT_GOV10DD`, 2000-Q1 onward).

Two perimeter facts govern everything below and are documented in
`reports/debt_sources/aggregates_fra.md`:

* **S13111 is not published for France.** `gov_10q_ggdebt` carries only
  `S13`, `S1311`, `S1312`, `S1313`, `S1314` for `geo=FR` (and for `DE`);
  the budgetary-central-government sub-subsector `S13111` is absent from
  the dataflow for both countries. The tightest reachable Eurostat
  perimeter is therefore `S1311` (central government *including* ODAC —
  CADES, SNCF Réseau, ... — the §14 FRA trap), which is what the
  unsuffixed `f31_*`/`f32_*` rows carry. The `_s13` rows are general
  government, the wider step-B/step-C perimeter cross-check.
* **The État's own perimeter is the INSEE/AFT series**, which is
  négociable debt of the État alone: 1.6-2.1% *below* Eurostat `S1311`
  F3 at each year-end 2012-2025 (11.5% below in 2009), the difference
  being ODAC securities plus the non-négociable/valuation content of the
  Maastricht measure.

No `interest` rows are emitted: programme 117 (charge de la dette) is on
`www.budget.gouv.fr`/`www.performance-publique.budget.gouv.fr`, both
blocked, and no reachable source splits French interest by instrument
class. No `uplift_accrued` rows: the AFT coefficients d'indexation and the
programme 117 "charge d'indexation" line are on the same blocked hosts.
No `own_holdings` rows: `gov_10dd_ggd` carries no `S121` holder rows for
issuing sector `S1311` (see the report for the `S13`-issuer series that
does exist).
"""

from __future__ import annotations

import pandas as pd

from ggfiscal.debt.aggregates import COLUMNS, row, sha

INSEE_SOURCE = "INSEE_AFT_AGG"
EUROSTAT_SOURCE = "EUROSTAT_GOV10DD"
EUROSTAT_PART = "gov_10q_ggdebt_FR"

# INSEE/AFT idbank -> (instrument_class, sub_type, in_register). The titles
# are the exact `series[0].titre` of the BDM JSON payload, checked at build
# time by `_aft_december()` so that a re-pull that re-labels or re-numbers a
# series fails loudly rather than silently re-classifying it.
AFT_STOCK: dict[str, tuple[str, str, bool, str]] = {
    "001711531": ("mixed", "dette_negociable_total", True,
                  "Encours de la dette négociable totale de l'État en euros"),
    "001711532": ("bill", "btf", True,
                  "Encours de la dette négociable de l'État à court terme "
                  "(maturité d'un an et moins) en euros"),
    "001711533": ("mixed", "oat_btan_all", True,
                  "Encours de la dette négociable de l'État à moyen et long terme "
                  "(maturité de plus d'un an) en euros"),
    "001738853": ("mixed", "taux_fixe", True,
                  "Encours de la dette négociable de l'État à taux fixe"),
    "001738854": ("inflation_linked", "oati_oatei", True,
                  "Encours de la dette négociable de l'État indexée sur l'inflation"),
}

# Foreign-currency counterparts. Emitted as `out_of_register` rows only for
# year-ends where the series is non-zero; they are identically 0.0 at every
# December 2009-2025 in the harvested vintage (the État has issued no
# foreign-currency négociable debt over the period).
AFT_FX: dict[str, tuple[str, str, bool, str]] = {
    "001719708": ("out_of_register", "dette_negociable_total_devises", False,
                  "Encours de la dette négociable totale de l'État en devises"),
    "001719709": ("out_of_register", "dette_negociable_ct_devises", False,
                  "Encours de la dette négociable de l'État à court terme "
                  "(maturité d'un an et moins) en devises"),
    "001719710": ("out_of_register", "dette_negociable_mlt_devises", False,
                  "Encours de la dette négociable de l'État à moyen et long terme "
                  "(maturité de plus d'un an) en devises"),
}

# Eurostat gov_10q_ggdebt na_item -> (instrument_class, sub_type, in_register)
# for the S1311 (unsuffixed) rows.
EUROSTAT_ITEMS: dict[str, tuple[str, str, bool]] = {
    "F31": ("bill", "f31_short_term_securities", True),
    "F32": ("mixed", "f32_long_term_securities", True),
    "F4": ("out_of_register", "f4_loans", False),
    "F2": ("out_of_register", "f2_currency_deposits", False),
}
# The wider-perimeter cross-check rows (S13, general government): securities
# only, never in register.
EUROSTAT_S13_ITEMS: dict[str, tuple[str, str, bool]] = {
    "F31": ("bill", "f31_short_term_securities_s13", False),
    "F32": ("mixed", "f32_long_term_securities_s13", False),
}

_ESA_NOTE = ("ESA 2010 instrument class, Maastricht gross debt at face value, "
             "Eurostat gov_10q_ggdebt, Q4 observation")
_PERIMETER_NOTE = ("sector S1311 central government incl. ODAC (CADES, ...); "
                   "S13111 budgetary central government is not published for FR")
_S13_NOTE = ("sector S13 general government — wider-perimeter cross-check, "
             "not the register perimeter")
_DELTA_NOTE = ("Δ year-end stock; buy-backs, indexation of principal and FX "
               "effects not separated")


# ---------------------------------------------------------------- INSEE/AFT

def _aft_december() -> pd.DataFrame:
    """December observations of every INSEE_AFT_AGG stock idbank used here,
    as a (year x idbank) frame in EUR millions. Raises if an idbank is
    missing from the snapshot store or its BDM title has changed."""
    from ggfiscal.debt.readers.eurostat_insee_oecd import aft_aggregates

    a = aft_aggregates()
    if a.empty:
        return pd.DataFrame()
    titles = dict(zip(a["idbank"], a["label"]))
    expected = {k: v[3] for k, v in {**AFT_STOCK, **AFT_FX}.items()}
    wrong = {k: titles.get(k) for k, t in expected.items() if titles.get(k) != t}
    if wrong:
        raise KeyError(
            "INSEE_AFT_AGG idbank titles differ from the verified 2026-09-09 "
            f"vintage (expected/found): {[(k, expected[k], v) for k, v in wrong.items()]}")
    d = a[(a["period"].dt.month == 12) & (a["idbank"].isin(expected))].copy()
    d["year"] = d["period"].dt.year
    return d.pivot_table(index="year", columns="idbank", values="value_eur_mn")


def _aft_rows(run_id: str, piv: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for idbank, (klass, sub, in_reg, title) in AFT_STOCK.items():
        if idbank not in piv.columns:
            continue
        note = f'INSEE/AFT idbank {idbank} "{title}"'
        if idbank == "001738853":
            note += ("; includes BTF (short-term discount bills) — the AFT "
                     "taux fixe aggregate is fixed-rate incl. bills, not "
                     "fixed-rate bonds alone (see sub_type oat_btan_fixed)")
        for year, value in piv[idbank].dropna().items():
            rows.append(row(run_id, "FRA", year, klass, sub, "stock_year_end", value,
                            INSEE_SOURCE, basis="nominal", in_register=in_reg,
                            sha256=sha(INSEE_SOURCE, idbank), grade="B", notes=note))
    # derived: fixed-rate OAT/BTAN = taux fixe − BTF
    if {"001738853", "001711532"} <= set(piv.columns):
        derived = (piv["001738853"] - piv["001711532"]).dropna()
        for year, value in derived.items():
            rows.append(row(run_id, "FRA", year, "fixed_bullet", "oat_btan_fixed",
                            "stock_year_end", value, INSEE_SOURCE, basis="nominal",
                            in_register=True, sha256=sha(INSEE_SOURCE, "001738853"),
                            grade="B",
                            notes=("derived = INSEE/AFT 001738853 (encours à taux fixe, "
                                   "which includes BTF) − 001711532 (encours à court terme, "
                                   "i.e. BTF); fixed-rate OAT/BTAN alone. Not an AFT-published "
                                   "aggregate. Identity checked: 001738853 + 001738854 = "
                                   "001711531 exactly at every December 2009-2025. "
                                   "snapshot_sha256 is that of idbank 001738853; the "
                                   "subtracted BTF series is snapshot 001711532")))
    # foreign-currency négociable debt: emitted only where non-zero
    for idbank, (klass, sub, in_reg, title) in AFT_FX.items():
        if idbank not in piv.columns:
            continue
        nz = piv[idbank].dropna()
        nz = nz[nz != 0.0]
        for year, value in nz.items():
            rows.append(row(run_id, "FRA", year, klass, sub, "stock_year_end", value,
                            INSEE_SOURCE, basis="nominal", in_register=in_reg,
                            sha256=sha(INSEE_SOURCE, idbank), grade="B",
                            notes=f'INSEE/AFT idbank {idbank} "{title}"'))
    return rows


def _aft_net_issuance(run_id: str, piv: pd.DataFrame) -> list[dict]:
    """Δ December stock of the CT (BTF) and MLT (OAT/BTAN) aggregates."""
    rows: list[dict] = []
    for idbank in ("001711532", "001711533"):
        if idbank not in piv.columns:
            continue
        klass, sub, in_reg, title = AFT_STOCK[idbank]
        for year, value in piv[idbank].dropna().diff().dropna().items():
            rows.append(row(run_id, "FRA", year, klass, sub, "net_issuance", value,
                            INSEE_SOURCE, basis="nominal_change", in_register=in_reg,
                            sha256=sha(INSEE_SOURCE, idbank), grade="B",
                            notes=f'{_DELTA_NOTE}; INSEE/AFT idbank {idbank} "{title}"'))
    return rows


# ---------------------------------------------------------------- Eurostat

def _q4_stocks(sector: str) -> pd.DataFrame:
    """Q4 observations of gov_10q_ggdebt for one issuing subsector, as a
    (year x na_item) frame in EUR millions."""
    from ggfiscal.debt.readers.eurostat_insee_oecd import quarterly_debt

    q = quarterly_debt("FRA", sector)
    if q.empty:
        return pd.DataFrame()
    q4 = q[q["time_period"].str.endswith("-Q4")].copy()
    q4["year"] = q4["time_period"].str[:4].astype(int)
    return q4.pivot_table(index="year", columns="na_item", values="value")


def _eurostat_rows(run_id: str, sha256: str | None) -> list[dict]:
    rows: list[dict] = []
    specs = (("S1311", EUROSTAT_ITEMS, _PERIMETER_NOTE),
             ("S13", EUROSTAT_S13_ITEMS, _S13_NOTE))
    for sector, items, perimeter in specs:
        piv = _q4_stocks(sector)
        if piv.empty:
            continue
        for na_item, (klass, sub, in_reg) in items.items():
            if na_item not in piv.columns:
                continue
            s = piv[na_item].dropna()
            note = f"{na_item}, {_ESA_NOTE}; {perimeter}"
            for year, value in s.items():
                rows.append(row(run_id, "FRA", year, klass, sub, "stock_year_end", value,
                                EUROSTAT_SOURCE, basis="nominal", in_register=in_reg,
                                sha256=sha256, grade="B", notes=note))
            # net issuance from the securities lines of the register perimeter only
            if sector == "S1311" and na_item in ("F31", "F32"):
                for year, value in s.diff().dropna().items():
                    rows.append(row(run_id, "FRA", year, klass, sub, "net_issuance", value,
                                    EUROSTAT_SOURCE, basis="nominal_change",
                                    in_register=in_reg, sha256=sha256, grade="B",
                                    notes=f"{_DELTA_NOTE}; {na_item} Q4 stock, {perimeter}"))
    return rows


# ---------------------------------------------------------------- entry point

def class_aggregates(run_id: str) -> pd.DataFrame:
    piv = _aft_december()
    rows: list[dict] = []
    if not piv.empty:
        rows += _aft_rows(run_id, piv)
        rows += _aft_net_issuance(run_id, piv)
    rows += _eurostat_rows(run_id, sha(EUROSTAT_SOURCE, EUROSTAT_PART))
    return pd.DataFrame(rows, columns=COLUMNS)
