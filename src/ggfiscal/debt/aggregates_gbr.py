"""GBR aggregate class-level layer (DD8): the UK's own official instrument-type
totals, in the `aggregates.COLUMNS` shape, one row per
(iso3='GBR', year, instrument_class, sub_type, measure), calendar years (DD6),
£ millions.

Sources, all official and all read through the family readers — nothing here
re-parses a snapshot and nothing is hand-keyed:

| measure | source | table / series |
|---|---|---|
| `stock_year_end` | ONS_PSF_APPENDIX_A | PSA8A_1 CG gross debt at nominal value, end of period, December month-end |
| `stock_year_end` | ONS_PSF_TIMESERIES | BKPM before the PSA block (end-**March** only: see below) |
| `stock_year_end`, `own_holdings` | HMT_DMR | table A.1 composition of CG wholesale and retail debt at end-December |
| `net_issuance` | ONS_PSF_APPENDIX_S | table 1.2A financing of the CGNCR, 12 calendar months summed |
| `gross_issuance`, `redemptions` | HMT_DMR | table A.2 (financial years, converted per §7.10) |
| `gross_issuance` by class | HMT_DMR | table 3.A gilt sales split (financial years, §7.10) |
| `interest` | HMT_NLF | note 2 finance costs of borrowing (financial years, §7.10) |
| `uplift_accrued` | ONS_PSF_TIMESERIES | MW7L CG gross index-linked gilt capital uplift, calendar year |
| `own_holdings` | BOE_APF | operation results (cumulative net) and the maturity-profile table |

Grades (§9, DD8), applied consistently across the module:

* **A** — a calendar-year, exactly published figure whose own label maps 1:1
  onto one DD2 class or one named bridge line (ONS BKPJ Treasury bills, the
  ONS bridge lines, MW7L).
* **B** — published exactly but either without the DD2 class split (`mixed`
  gilts: ONS does not split conventional from index-linked) or converted from
  a financial year per §7.10 (DMR A.2, NLF note 2), or on a perimeter that
  differs from the calendar-year national-accounts one (DMR A.1).
* **C** — the period basis departs from 31 December / the calendar year, or a
  component of the value is the publisher's own forecast (DMR 3.A remit years,
  the pre-1997 end-March BKPM block, the APF cumulative-operations series
  which has no redemption deduction).

Three wedges are deliberately left open rather than closed with an estimate
(DD13, "decompose, never force"); each is stated in every affected row's
`notes` and in `reports/debt_sources/aggregates_gbr.md`:

1. **Uplifted vs unindexed nominal.** DMR A.1 prints index-linked gilts at
   unindexed nominal with the accrued inflation uplift on a separate line
   ("Nominal uplifted values" per the chart A.1 footnote); both are emitted,
   the uplift as its own `sub_type`.
2. **APF redemptions.** The APF publishes purchases and sales per ISIN but not
   redemptions, so cumulative purchases − sales is *not* a holding. It is
   emitted as such, named `boe_apf_net_operations`, grade C, and never netted
   against a maturity schedule.
3. **FY→CY.** DMR A.2/3.A and the NLF account are financial-year; §7.10
   (`intermediates.fy_to_cy`) converts them and the row records which two
   financial years (and which two editions) were used.
"""

from __future__ import annotations

import re

import pandas as pd

from ggfiscal.debt.aggregates import COLUMNS, row, sha
from ggfiscal.debt.intermediates import fy_to_cy
from ggfiscal.standardise.readers import latest_snapshots

ISO = "GBR"
BN = 1000.0                     # DMR tables are £ billion; the table is £ million

# ---------------------------------------------------------------------------
# ONS PSA8A_1 — CG gross debt at nominal value, end of period
# ---------------------------------------------------------------------------

# instrument label (readers.ons_hmt.CG_DEBT_INSTRUMENTS) ->
#   (cdid, instrument_class, sub_type, in_register, grade)
ONS_STOCK = {
    "gilts": ("BKPM", "mixed", "gilts_all", True, "B"),
    "treasury_bills": ("BKPJ", "bill", "treasury_bills", True, "A"),
    "national_savings": ("ACUA", "out_of_register", "national_savings", False, "A"),
    "tax_instruments": ("ACRV", "out_of_register", "tax_instruments", False, "A"),
    "other_sterling_and_foreign_currency": (
        "KW6Q", "out_of_register", "other_sterling_and_foreign_currency", False, "A"),
    "nram_and_bb": ("KW6R", "out_of_register", "nram_and_bb", False, "A"),
    "network_rail": ("MDL3", "out_of_register", "network_rail", False, "A"),
}


def _ons_stock_rows(run_id: str) -> list[dict]:
    """PSA8A_1 December month-end stocks. The sheet's own annual block is the
    *financial* year (`Apr 1997 to Mar 1998`), so the calendar-year position is
    taken from the monthly block at period_start month 12 — never from the
    annual block."""
    from ggfiscal.debt.readers import ons_hmt as O

    sha256 = sha("ONS_PSF_APPENDIX_A", "appendix_a")
    d = O.cg_debt_by_instrument(("M",))
    d = d[d["period_start"].dt.month == 12]
    rows: list[dict] = []
    for label, (cdid, klass, sub, in_reg, grade) in ONS_STOCK.items():
        s = d[d["instrument"] == label]
        for _, r in s.iterrows():
            rows.append(row(
                run_id, ISO, r["period_start"].year, klass, sub, "stock_year_end",
                r["value"], "ONS_PSF_APPENDIX_A", basis="nominal", in_register=in_reg,
                sha256=sha256, grade=grade,
                notes=f"ONS PSA8A_1 {cdid} ({label}), CG gross debt at nominal value, "
                      f"December month-end (the sheet's annual block is the financial year)"))
    return rows


def _pusf_gilts_rows(run_id: str) -> list[dict]:
    """BKPM from the PUSF time series for the years before the PSA8A_1 block.

    The brief expected a calendar-year annual block from 1975. It is not there:
    in this vintage BKPM's `years` array is **blank before 1997** and the only
    pre-1997 observations are end-March (published as `1975 MAR` … `1996 MAR`,
    and repeated in the quarterly array as `1975 Q1` …). They are financial-
    year-end stocks, not 31 December stocks, so they are emitted under their own
    `sub_type` (`gilts_all_march`), basis `nominal_end_march`, grade C — never
    as a 31 December position (DD6). From 1997 the PUSF annual block is
    identical to the PSA8A_1 December month-end and adds nothing.
    """
    from ggfiscal.debt.readers import ons_hmt as O

    sha256 = sha("ONS_PSF_TIMESERIES", "BKPM")
    ts = O.ons_timeseries("BKPM", "pusf")
    ann = ts[ts["period_type"] == "A"]
    first_cy = int(ann["period_start"].dt.year.min()) if not ann.empty else 1997
    mar = ts[(ts["period_type"] == "M") & (ts["period_start"].dt.month == 3)]
    mar = mar[mar["period_start"].dt.year < first_cy]
    return [row(run_id, ISO, r["period_start"].year, "mixed", "gilts_all_march",
                "stock_year_end", r["value"], "ONS_PSF_TIMESERIES",
                basis="nominal_end_march", sha256=sha256, grade="C",
                notes="ONS PUSF BKPM 'CG: British government stock (gilts)'; the PUSF "
                      f"calendar-year block is blank before {first_cy}, so this is the "
                      "end-MARCH (financial-year-end) observation of the stated year, "
                      "not a 31 December position (DD6 departure)")
            for _, r in mar.iterrows()]


# ---------------------------------------------------------------------------
# HMT Debt Management Report — table A.1 (composition at end-December)
# ---------------------------------------------------------------------------

DMR_HTML_EDITIONS = ("2025-26", "2026-27")     # the only editions with an
                                               # accessible HTML rendering
_END_DEC = re.compile(r"end-?december\s*(\d{4})", re.IGNORECASE)
_FY_LABEL = re.compile(r"^(\d{4})-(\d{2})")


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _dmr_rows_in_order(frame: pd.DataFrame) -> list[tuple[str, dict[str, float]]]:
    """[(label_key, {column: value})] in the table's own row order."""
    out = []
    for i, g in frame.groupby("row_index", sort=True):
        out.append((_key(g["row"].iloc[0]),
                    dict(zip(g["column"], g["value"], strict=False))))
    return out


def _dmr_years(frame: pd.DataFrame) -> dict[str, int]:
    """{'End-December 2024': 2024} for the A.1 columns."""
    years = {}
    for col in frame["column"].unique():
        m = _END_DEC.search(str(col))
        if m:
            years[col] = int(m.group(1))
    return years


def _a1_blocks(rows: list[tuple[str, dict]], edition: str) -> dict[str, dict]:
    """Pull the A.1 lines the layer needs out of the table's row sequence.

    Conventional and index-linked each print as a small block whose net line
    has an *empty* label, so the block is read positionally from its heading:

        Conventional gilts            1,996.9
        Less government holdings        164.0
        (blank)                       1,832.9   <- net
        Index-linked gilts              393.5
        less government holdings          2.1
        plus accrued inflation uplift   227.6
        (blank)                         619.0   <- net, uplifted

    Raises if that shape is gone, rather than silently emitting a wrong line.
    """
    keys = [k for k, _ in rows]

    def at(i):
        return rows[i][1]

    def find(key):
        try:
            return keys.index(key)
        except ValueError as e:
            raise ValueError(f"DMR {edition} table A.1: no {key!r} row "
                             f"(rows: {keys})") from e

    i = find("conventionalgilts")
    if keys[i + 1] != "lessgovernmentholdings" or keys[i + 2] != "":
        raise ValueError(f"DMR {edition} table A.1: unexpected conventional-gilt "
                         f"block {keys[i:i + 3]}")
    j = find("indexlinkedgilts")
    if (keys[j + 1] != "lessgovernmentholdings"
            or keys[j + 2] != "plusaccruedinflationuplift" or keys[j + 3] != ""):
        raise ValueError(f"DMR {edition} table A.1: unexpected index-linked block "
                         f"{keys[j:j + 4]}")
    out = {
        "conventional_gross": at(i), "conventional_holdings": at(i + 1),
        "conventional_net": at(i + 2),
        "linked_gross": at(j), "linked_holdings": at(j + 1),
        "linked_uplift": at(j + 2), "linked_net": at(j + 3),
    }
    for key, want in (("treasurybillsfordebtmanagement", "treasury_bills"),
                      ("nsi", "national_savings"),
                      ("balanceonwaysandmeansadvance", "ways_and_means"),
                      ("sovereignsukuk", "sovereign_sukuk")):
        out[want] = at(find(key))
    return out


# what each A.1 line becomes: (block key, class, sub_type, measure, in_register,
#                              basis, note tail)
A1_EMIT = (
    ("conventional_net", "fixed_bullet", "gilts_conventional", "stock_year_end", True,
     "nominal",
     "'Conventional gilts' less 'Less government holdings'; the table's own net line"),
    ("linked_net", "inflation_linked", "gilts_index_linked", "stock_year_end", True,
     "uplifted_nominal",
     "'Index-linked gilts' less government holdings plus accrued inflation uplift; "
     "the table's own net line — uplifted, not unindexed, nominal"),
    ("linked_gross", "inflation_linked", "gilts_index_linked_unindexed", "stock_year_end",
     True, "unindexed_nominal",
     "'Index-linked gilts' as printed, i.e. unindexed nominal before the uplift line "
     "and before government holdings"),
    ("linked_uplift", "inflation_linked", "gilts_index_linked_accrued_uplift",
     "stock_year_end", True, "accrued_uplift_stock",
     "'plus accrued inflation uplift' — the stock of uplift accrued to date, the "
     "uplifted/unindexed wedge"),
    ("treasury_bills", "bill", "treasury_bills_debt_management", "stock_year_end", True,
     "nominal",
     "'Treasury bills for debt management' — narrower than ONS BKPJ, which also "
     "carries bills issued for cash management"),
    ("national_savings", "out_of_register", "national_savings_dmr", "stock_year_end",
     False, "nominal", "'NS&I' retail debt"),
    ("ways_and_means", "out_of_register", "ways_and_means", "stock_year_end", False,
     "nominal", "'Balance on Ways and Means Advance'"),
    ("sovereign_sukuk", "out_of_register", "sovereign_sukuk", "stock_year_end", False,
     "nominal", "'Sovereign Sukuk' — a CG security but outside the DD1 GBR perimeter"),
    ("conventional_holdings", "fixed_bullet", "gilts_conventional", "own_holdings", True,
     "nominal", "'Less government holdings' against conventional gilts"),
    ("linked_holdings", "inflation_linked", "gilts_index_linked", "own_holdings", True,
     "unindexed_nominal",
     "'less government holdings' against index-linked gilts, on the unindexed nominal "
     "the line above it is printed on"),
)

A1_NOTE = ("HMT DMR {ed} table A.1 'Composition of central government wholesale and "
           "retail debt', end-December {year}, £bn as published × 1000. Chart A.1's "
           "footnote reads \"Figures may not sum due to rounding. Nominal uplifted "
           "values.\" and table A.1's own footnote (1) reads \"Figures may not sum due "
           "to rounding.\": index-linked gilts are printed at unindexed nominal with "
           "the accrued inflation uplift on its own line. {tail}")


def _dmr_a1_rows(run_id: str) -> list[dict]:
    from ggfiscal.debt.readers import ons_hmt as O

    picked: dict[tuple, dict] = {}          # (year, class, sub, measure) -> row
    for edition in DMR_HTML_EDITIONS:       # ascending: the later edition wins
        try:
            a1 = O.dmr_tables(edition, ("A.1",)).get("A.1")
        except FileNotFoundError:
            continue
        if a1 is None or a1.empty:
            continue
        blocks = _a1_blocks(_dmr_rows_in_order(a1), edition)
        sha256 = sha("HMT_DMR", f"{edition}_html")
        for col, year in _dmr_years(a1).items():
            # the table's own arithmetic, checked rather than assumed
            for gross, hold, net, extra in (
                    ("conventional_gross", "conventional_holdings", "conventional_net", None),
                    ("linked_gross", "linked_holdings", "linked_net", "linked_uplift")):
                g, h, n = (blocks[gross].get(col), blocks[hold].get(col),
                           blocks[net].get(col))
                u = blocks[extra].get(col) if extra else 0.0
                if pd.notna(g) and pd.notna(h) and pd.notna(n) and pd.notna(u):
                    if abs(g - h + u - n) > 0.2:
                        raise ValueError(
                            f"DMR {edition} A.1 {col}: {gross} − {hold} (+ uplift) "
                            f"= {g - h + u} does not match the printed net {n}")
            for key, klass, sub, measure, in_reg, basis, tail in A1_EMIT:
                v = blocks[key].get(col)
                if v is None or pd.isna(v):
                    continue
                picked[(year, klass, sub, measure)] = row(
                    run_id, ISO, year, klass, sub, measure, v * BN, "HMT_DMR",
                    basis=basis, in_register=in_reg, sha256=sha256, grade="B",
                    notes=A1_NOTE.format(ed=edition, year=year, tail=tail))
    return list(picked.values())


# ---------------------------------------------------------------------------
# ONS Appendix S table 1.2A — financing of the CGNCR, net issuance
# ---------------------------------------------------------------------------

# cdid -> (instrument_class, sub_type, in_register, grade, description)
APPENDIX_S_ROWS = {
    "ANTA": ("mixed", "gilts_all", True, "B",
             "British government securities (F.332) — ONS does not split conventional "
             "from index-linked"),
    "NAVG": ("bill", "treasury_bills", True, "A", "sterling Treasury bills (F.331)"),
    "-AACE": ("out_of_register", "national_savings", False, "A", "national savings (F.29)"),
    "-AACF": ("out_of_register", "tax_instruments", False, "A", "tax instruments (F.29)"),
    "-EYMW": ("out_of_register", "coin", False, "A", "coin (F.21)"),
    "ANTB": ("out_of_register", "loans_from_mfis", False, "A",
             "loans from monetary financial institutions (F.4)"),
    "-AACH": ("out_of_register", "northern_ireland_cg_debt", False, "A",
              "Northern Ireland central government debt (F.332, F.411, F.424)"),
    "-AACI": ("out_of_register", "exchange_cover_scheme", False, "A",
              "Exchange Cover Scheme liabilities"),
    "ANTC": ("out_of_register", "deposits_from_other_sectors", False, "A",
             "deposits with central government from other sectors (F.29)"),
    "-AACL": ("out_of_register", "government_foreign_currency_debt", False, "A",
              "government foreign currency debt (F.332, F.411, F.424)"),
    "-AACM": ("out_of_register", "other_overseas_financing", False, "A",
              "other government overseas financing (F.4)"),
    "ANTD": ("out_of_register", "nilo_lending_asset", False, "A",
             "ASSET row: non-marketable bonds (NILO) lending except PWLB (F.4)"),
    "AIPA": ("out_of_register", "official_reserves_asset", False, "A",
             "ASSET row: net change in official reserves and other foreign currency assets"),
    "ANSZ": ("out_of_register", "sterling_deposits_asset", False, "A",
             "ASSET row: sterling deposits with financial institutions"),
}


def _appendix_s_rows(run_id: str) -> list[dict]:
    """12 calendar months of Appendix S table 1.2A summed per year. The sheet
    has no calendar-year block, so the monthly rows are the only calendar-year
    route; a year with fewer than 12 published months is omitted."""
    from ggfiscal.debt.readers import ons_hmt as O

    sha256 = sha("ONS_PSF_APPENDIX_S", "appendix_s")
    f = O.cgncr_financing()
    m = f[f["period_type"] == "M"].copy()
    m["year"] = m["period_start"].dt.year
    rows: list[dict] = []
    for cdid, (klass, sub, in_reg, grade, desc) in APPENDIX_S_ROWS.items():
        s = m[m["cdid"] == cdid]
        for year, g in s.groupby("year"):
            if len(g) != 12:
                continue
            rows.append(row(
                run_id, ISO, year, klass, sub, "net_issuance", g["value"].sum(),
                "ONS_PSF_APPENDIX_S", basis="cash", in_register=in_reg, sha256=sha256,
                grade=grade,
                notes=f"ONS Appendix S table 1.2A {cdid} ({desc}), sum of the 12 "
                      f"calendar months of {year}; the publisher's own sign (a CDID "
                      f"printed with a leading minus is published already negated so "
                      f"the row sums to the CGNCR M98R)"))
    return rows


# ---------------------------------------------------------------------------
# HMT DMR tables A.2 and 3.A — gilt issuance and redemptions, FY -> CY
# ---------------------------------------------------------------------------

def _a2_by_fy() -> tuple[dict[str, dict[int, float]], dict[int, str], set[int]]:
    """({measure: {fy_start: £bn}}, {fy_start: edition}, outturn fy_starts).

    A financial year carried by more than one edition takes the latest edition's
    value. A row label with a footnote marker (`2025-26(3)`) is the publisher's
    forecast flag.
    """
    from ggfiscal.debt.readers import ons_hmt as O

    # column headings carry footnote markers ("Gross gilt sales(2)"), so the
    # heading is matched on the prefix of its letters-and-digits key
    want = {"redemptions": "redemptions", "grossgiltsales": "gross_issuance"}
    vals: dict[str, dict[int, float]] = {v: {} for v in want.values()}
    editions: dict[int, str] = {}
    outturn: set[int] = set()
    for edition in DMR_HTML_EDITIONS:               # ascending: later wins
        try:
            a2 = O.dmr_tables(edition, ("A.2",)).get("A.2")
        except FileNotFoundError:
            continue
        if a2 is None or a2.empty:
            continue
        cols = {}
        for c in a2["column"].unique():
            for prefix, measure in want.items():
                if _key(c).startswith(prefix):
                    cols[c] = measure
        if set(cols.values()) != set(want.values()):
            raise ValueError(f"DMR {edition} table A.2: expected a redemptions and a "
                             f"gross gilt sales column, found {list(a2['column'].unique())}")
        for _, g in a2.groupby("row_index", sort=True):
            label = str(g["row"].iloc[0])
            m = _FY_LABEL.match(label)
            if not m:
                continue
            fy = int(m.group(1))
            editions[fy] = edition
            (outturn.add if "(" not in label else outturn.discard)(fy)
            for col, measure in cols.items():
                v = g.loc[g["column"] == col, "value"]
                if not v.empty and pd.notna(v.iloc[0]):
                    vals[measure][fy] = float(v.iloc[0])
    return vals, editions, outturn


def _dmr_a2_rows(run_id: str) -> list[dict]:
    vals, editions, outturn = _a2_by_fy()
    rows: list[dict] = []
    for measure, fy in vals.items():
        fy_out = {k: v for k, v in fy.items() if k in outturn}
        cy = fy_to_cy(pd.Series(fy_out, dtype=float))
        for year, value in cy.items():
            ed = editions[year]
            line = ("gross gilt sales" if measure == "gross_issuance"
                    else "gilt redemptions")
            rows.append(row(
                run_id, ISO, year, "mixed", "gilts_all", measure, value * BN, "HMT_DMR",
                basis="cash", sha256=sha("HMT_DMR", f"{ed}_html"), grade="B",
                notes=f"HMT DMR table A.2 ({line}"
                      f", £bn, 'figures are in cash terms'); FY→CY per §7.10 from DMR "
                      f"A.2 {ed}: 0.25×FY{year - 1}-{str(year)[2:]} + 0.75×FY{year}-"
                      f"{str(year + 1)[2:]} (editions {editions[year - 1]} and {ed}); "
                      f"outturn financial years only, the DMR's forecast rows are omitted"))
    return rows


_3A_LINES = {
    "shortconventionalgilts": "conventional",
    "mediumconventionalgilts": "conventional",
    "longconventionalgilts": "conventional",
    "indexlinkedgilts": "index_linked",
    "unallocatedamountofgilts": "unallocated",
    "totalgiltsalesfordebtfinancing": "total",
}
_3A_EMIT = {
    "conventional": ("fixed_bullet", "gilts_conventional",
                     "short + medium + long conventional gilt sales (green gilts included "
                     "in those lines per the table's own footnote)"),
    "index_linked": ("inflation_linked", "gilts_index_linked", "index-linked gilt sales"),
    "unallocated": ("mixed", "gilts_unallocated",
                    "'Unallocated amount of gilts' — not yet split by class in the remit"),
}


def _3a_by_fy() -> tuple[dict[str, dict[int, float]], dict[int, str]]:
    from ggfiscal.debt.readers import ons_hmt as O

    vals: dict[str, dict[int, float]] = {k: {} for k in _3A_LINES.values()}
    editions: dict[int, str] = {}
    for edition in DMR_HTML_EDITIONS:               # ascending: later wins
        try:
            t = O.dmr_tables(edition, ("3.A",)).get("3.A")
        except FileNotFoundError:
            continue
        if t is None or t.empty:
            continue
        cols = {}
        for c in t["column"].unique():
            m = _FY_LABEL.match(str(c).strip())
            if m:
                cols[c] = int(m.group(1))
        seen = {fy: {} for fy in cols.values()}
        for _, g in t.groupby("row_index", sort=True):
            bucket = None
            k = _key(g["row"].iloc[0])
            for prefix, b in _3A_LINES.items():
                if k.startswith(prefix):
                    bucket = b
                    break
            if bucket is None:
                continue
            for col, fy in cols.items():
                v = g.loc[g["column"] == col, "value"]
                if not v.empty and pd.notna(v.iloc[0]):
                    seen[fy][bucket] = seen[fy].get(bucket, 0.0) + float(v.iloc[0])
        for fy, got in seen.items():
            if not got:
                continue
            editions[fy] = edition
            for bucket, value in got.items():
                vals[bucket][fy] = value
    return vals, editions


def _dmr_3a_rows(run_id: str) -> tuple[list[dict], list[str]]:
    """Class-split gross gilt sales. Table 3.A carries two financial years per
    edition (the estimate for the year ending and the remit for the year
    starting), so a calendar year needs two consecutive financial years. A
    calendar year whose *earlier* financial year is still a DMR forecast is
    skipped — it would be a projection for a year that has not happened. The
    skipped years are returned so the report can name them."""
    vals, editions = _3a_by_fy()
    _, _, outturn = _a2_by_fy()
    rows: list[dict] = []
    skipped: list[str] = []
    # the total line is a check, not an emitted row
    total = vals.pop("total", {})
    for fy, tot in total.items():
        parts = sum(vals[b].get(fy, 0.0) for b in ("conventional", "index_linked",
                                                   "unallocated"))
        if abs(parts - tot) > 0.15:
            raise ValueError(f"DMR 3.A FY{fy}: class lines sum to {parts} against the "
                             f"printed total gilt sales {tot}")
    for bucket, (klass, sub, desc) in _3A_EMIT.items():
        cy = fy_to_cy(pd.Series(vals[bucket], dtype=float))
        for year, value in cy.items():
            if (year - 1) not in outturn:
                skipped.append(f"CY {year} ({bucket})")
                continue
            ed = editions[year]
            forecast = year not in outturn
            rows.append(row(
                run_id, ISO, year, klass, sub, "gross_issuance", value * BN, "HMT_DMR",
                basis="cash", sha256=sha("HMT_DMR", f"{ed}_html"),
                grade="C" if forecast else "B",
                notes=f"HMT DMR table 3.A financing arithmetic ({desc}), £bn; FY→CY per "
                      f"§7.10: 0.25×FY{year - 1}-{str(year)[2:]} + 0.75×FY{year}-"
                      f"{str(year + 1)[2:]} (editions {editions[year - 1]} and {ed})"
                      + ("; FY" + f"{year}-{str(year + 1)[2:]} is the DMR's own remit "
                         "estimate, not outturn (grade C)" if forecast else "")))
    return rows, sorted(set(skipped))


# ---------------------------------------------------------------------------
# HMT National Loans Fund Account — note 2, finance costs of borrowing
# ---------------------------------------------------------------------------

# NLF note-2 item -> (instrument_class, sub_type, in_register)
NLF_ITEMS = {
    "gilts": ("mixed", "gilts_all", True),
    "treasury_bills": ("bill", "treasury_bills", True),
    "national_savings": ("out_of_register", "national_savings", False),
    "other": ("out_of_register", "other_nlf_finance_costs", False),
}


def _nlf_by_fy() -> tuple[dict[str, dict[int, float]], dict[int, tuple[str, str]]]:
    from ggfiscal.debt.readers import ons_hmt as O

    vals: dict[str, dict[int, float]] = {k: {} for k in NLF_ITEMS}
    editions: dict[int, tuple[str, str]] = {}
    parts = sorted(p for (s, p) in latest_snapshots() if s == "HMT_NLF")
    for part in parts:
        try:
            n = O.nlf_interest_summary(part)
        except Exception:                  # unreadable edition (2006-07, 2007-08)
            continue
        if n.empty:
            continue
        fy = int(part[:4])
        editions[fy] = (part, sha("HMT_NLF", part))
        note = n[n["source"] == "note_2"]
        for item in NLF_ITEMS:
            g = note[note["item"] == item]
            if not g.empty:
                # an edition can print more than one line for an item (2012-13
                # and 2013-14 carry "Loss on cancellation of Royal Mail gilts"
                # under gilts; 2012-13 splits FLS and SLS Treasury bills) — the
                # note's own total is the sum of every line, so sum them.
                vals[item][fy] = float(g["value"].sum())
    return vals, editions


def _nlf_rows(run_id: str) -> list[dict]:
    vals, editions = _nlf_by_fy()
    rows: list[dict] = []
    for item, (klass, sub, in_reg) in NLF_ITEMS.items():
        cy = fy_to_cy(pd.Series(vals[item], dtype=float))
        for year, value in cy.items():
            prev_ed, _ = editions[year - 1]
            ed, sha256 = editions[year]
            rows.append(row(
                run_id, ISO, year, klass, sub, "interest", value, "HMT_NLF",
                basis="accrued_nlf_finance_costs", in_register=in_reg, sha256=sha256,
                grade="B",
                notes=f"HMT National Loans Fund Account note 2 'finance costs of "
                      f"borrowing', item '{item}'; FY→CY per §7.10: "
                      f"0.25×FY{year - 1}-{str(year)[2:]} + 0.75×FY{year}-"
                      f"{str(year + 1)[2:]}, from editions {prev_ed} and {ed}; "
                      f"the 2006-07 and 2007-08 accounts have no usable text layer so "
                      f"CY 2006-2008 cannot be built"))
    return rows


# ---------------------------------------------------------------------------
# ONS MW7L — index-linked gilt capital uplift accrued in the calendar year
# ---------------------------------------------------------------------------

def _mw7l_rows(run_id: str) -> list[dict]:
    from ggfiscal.debt.readers import ons_hmt as O

    sha256 = sha("ONS_PSF_TIMESERIES", "MW7L")
    ts = O.ons_timeseries("MW7L", "pusf")
    ann = ts[ts["period_type"] == "A"]
    return [row(run_id, ISO, r["period_start"].year, "inflation_linked",
                "gilts_index_linked", "uplift_accrued", r["value"],
                "ONS_PSF_TIMESERIES", basis="accrued", sha256=sha256, grade="A",
                notes="ONS PUSF MW7L 'CG: Gross Index-linked gilt capital uplift', "
                      "£m, annual block = calendar year, from 1981; no conversion")
            for _, r in ann.iterrows()]


# ---------------------------------------------------------------------------
# BoE Asset Purchase Facility — the official-holdings overlay (DD11)
# ---------------------------------------------------------------------------

APF_PARTS = ("gilt_purchases", "gilt_sales", "fs_long_dated_purchases",
             "fs_index_linked_purchases", "fs_gilt_sales")


def _apf_rows(run_id: str) -> list[dict]:
    """Two honest rows, never one estimated one.

    `boe_apf_net_operations` is the cumulative nominal of every published APF
    gilt purchase less every published sale at each 31 December. It is **not**
    the APF's holding: gilts redeem out of the APF and the Bank does not publish
    those redemptions per ISIN, so the series overstates the holding by the
    nominal that has matured. No redemption schedule is invented for it
    (`apf_maturity_profile()` lists only gilts still held, which cannot recover
    what has already matured).

    `boe_apf_published_stock` is the Bank's own current holding from the
    maturity-profile table, for the latest year only.
    """
    from ggfiscal.debt.readers import boe as B

    ops = B.apf_operations().copy()
    ops["signed"] = ops["direction"] * ops["nominal_gbp_mn"]
    by_year = ops.groupby(ops["operation_date"].dt.year)["signed"].sum().sort_index()
    cum = by_year.cumsum()
    last_op_year = int(by_year.index.max())
    complete = [y for y in cum.index if y < last_op_year]   # last year is part-year
    sha_ops = sha("BOE_APF", "gilt_purchases")
    rows = [row(run_id, ISO, y, "mixed", "boe_apf_net_operations", "own_holdings",
                float(cum[y]), "BOE_APF", basis="nominal", sha256=sha_ops, grade="C",
                notes="BoE APF: cumulative nominal of published gilt purchases less "
                      "sales to 31 December, over BOE_APF parts "
                      + ", ".join(APF_PARTS) +
                      "; REDEMPTIONS OUT OF THE APF ARE NOT DEDUCTED — the Bank does "
                      "not publish them per ISIN — so this overstates the holding by "
                      "the nominal matured to date and is not the APF's stock (DD11 "
                      "overlay, DD13: no redemption schedule is inferred)")
            for y in complete]

    prof = B.apf_maturity_profile()
    if not prof.empty:
        total_mn = float(prof["total_nominal_gbp_bn"].sum()) * BN
        snap = latest_snapshots().get(("BOE_APF", "maturity_profile")) or {}
        asof = str(snap.get("retrieved_at", ""))[:8]
        year = int(asof[:4]) if asof[:4].isdigit() else last_op_year
        rows.append(row(
            run_id, ISO, year, "mixed", "boe_apf_published_stock", "own_holdings",
            total_mn, "BOE_APF", basis="nominal",
            sha256=sha("BOE_APF", "maturity_profile"), grade="B",
            notes=f"BoE APF 'Maturity Profile of the stock of gilts held in the APF' "
                  f"({len(prof)} gilts), sum of the published per-gilt 'Total Nominal "
                  f"(£bn)' column. Current stock as at the BOE_APF snapshot "
                  f"{asof or 'n/a'}, NOT a 31 December position. The workbook's own "
                  f"header total 'Current stock of holdings' is a cumulation of the "
                  f"'Total Purchase Proceeds' column (initial purchase price), not of "
                  f"nominal, and is dropped by apf_maturity_profile(); the nominal sum "
                  f"is used instead so the row is comparable with the operations row"))
    return rows


# ---------------------------------------------------------------------------

def class_aggregates(run_id: str) -> pd.DataFrame:
    rows: list[dict] = []
    rows += _ons_stock_rows(run_id)
    rows += _pusf_gilts_rows(run_id)
    rows += _dmr_a1_rows(run_id)
    rows += _appendix_s_rows(run_id)
    rows += _dmr_a2_rows(run_id)
    rows += _dmr_3a_rows(run_id)[0]
    rows += _nlf_rows(run_id)
    rows += _mw7l_rows(run_id)
    rows += _apf_rows(run_id)
    return pd.DataFrame(rows, columns=COLUMNS)
