"""Readers for family `eurostat_insee_oecd` (DEBT_KICKOFF.md §6.3, §13).

Snapshot -> tidy frame conventions:

* `eurostat(part)` is the one generic loader for every Eurostat SDMX-3.0
  CSV pull in this family (`gov_10a_main`, `gov_10dd_*`, `gov_10q_ggdebt`,
  `prc_hicp_*`, `irt_*`): dimension columns lower-cased as-is, `TIME_PERIOD`
  kept verbatim as `time_period` (the raw Eurostat period string — annual
  `"1995"`, monthly `"1999-12"`, quarterly `"2000-Q1"`) plus a parsed
  `period_start` date (first day of the period — 31 December is never
  substituted for an annual observation), `OBS_VALUE` -> float `value`,
  `OBS_FLAG` -> `obs_flag`. `STRUCTURE`/`STRUCTURE_ID`/`CONF_STATUS` are
  dropped (constant/uninformative for a single-dataflow pull).
* `insee_series(idbank)` parses the `html` field of the `serie/ajax` JSON
  payload (the `tableau-series` table carries the full history; the JSON's
  own `observations` field is null) into a monthly float Series. French
  thousands separators (narrow no-break space, U+202F) and decimal commas
  are normalised before parsing.
* `oecd_psd` / `oecd_rate` read OECD's `csvfilewithlabels` output, which
  pairs every code column with a same-row label column (`SECTOR`,
  `"Institutional sector"`, ...); only the all-caps code columns are kept
  (selected by name shape, not position, since OECD's column order is
  stable but the label columns are not needed for computation).

Key-order correction (documented in full in
`reports/debt_sources/eurostat_insee_oecd.md`): `gov_10dd_ggd`'s SDMX key
order is `freq.na_item.sector2.sector.maturity.unit.geo` — `sector2` (the
debt *holder*, codelist includes `S1_S2` "holders total", `S121` central
bank, etc.) precedes `sector` (the *issuing* subsector) — confirmed against
the dataflow's SDMX 2.1 content-constraint and a live key probe.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ggfiscal.debt.families.eurostat_insee_oecd import (
    EUROSTAT_GEO,
    INSEE_AFT_AGG_IDBANKS,
)
from ggfiscal.debt.readers import snap_path

# ---------- shared period parsing ----------

_ANNUAL_RE = re.compile(r"^\d{4}$")
_MONTHLY_RE = re.compile(r"^(\d{4})-(\d{2})$")
_QUARTERLY_RE = re.compile(r"^(\d{4})-Q([1-4])$")


def _period_start(time_period: str) -> pd.Timestamp:
    """First day of the raw Eurostat/OECD period string — the period string
    itself is preserved separately (`time_period`); this is never a
    period-end substitute (no 31 December for annual observations)."""
    tp = str(time_period)
    if _ANNUAL_RE.match(tp):
        return pd.Timestamp(int(tp), 1, 1)
    m = _MONTHLY_RE.match(tp)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
    m = _QUARTERLY_RE.match(tp)
    if m:
        return pd.Timestamp(int(m.group(1)), 3 * (int(m.group(2)) - 1) + 1, 1)
    return pd.NaT


# ---------- Eurostat SDMX-CSV ----------

_EUROSTAT_PART_PREFIXES = (
    ("gov_10a_main", "EUROSTAT_GOV10A_MAIN_S1311"),
    ("gov_10dd_", "EUROSTAT_GOV10DD"),
    ("gov_10q_ggdebt", "EUROSTAT_GOV10DD"),
    ("prc_hicp_", "EUROSTAT_PRC_HICP"),
    ("irt_", "EUROSTAT_IRT"),
)


def _eurostat_source_id(part: str) -> str:
    for prefix, source_id in _EUROSTAT_PART_PREFIXES:
        if part.startswith(prefix):
            return source_id
    raise ValueError(f"unrecognised eurostat_insee_oecd part {part!r}")


@lru_cache(maxsize=None)
def eurostat(part: str) -> pd.DataFrame:
    """Tidy frame for one Eurostat SDMX-3.0 CSV pull: every dimension column
    lower-cased, `time_period` (raw string) + `period_start` (date), `value`
    (float), `obs_flag`. Empty frame (same shape) if the snapshot is missing."""
    cols = ["time_period", "period_start", "value", "obs_flag"]
    try:
        path = snap_path(_eurostat_source_id(part), part)
    except FileNotFoundError:
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.lower() for c in df.columns]
    df = df.drop(columns=[c for c in ("structure", "structure_id", "conf_status")
                           if c in df.columns])
    df["value"] = pd.to_numeric(df.pop("obs_value"), errors="coerce")
    df["period_start"] = df["time_period"].map(_period_start)
    if "obs_flag" not in df.columns:
        df["obs_flag"] = pd.NA
    return df


def _annual_series(df: pd.DataFrame) -> pd.Series:
    """A eurostat() frame already filtered to one series -> int-year Series."""
    sel = df.dropna(subset=["value"])
    s = pd.Series(sel["value"].to_numpy(), index=sel["time_period"].astype(int))
    return s[~s.index.duplicated(keep="last")].sort_index()


def _monthly_series(df: pd.DataFrame) -> pd.Series:
    sel = df.dropna(subset=["value"])
    s = pd.Series(sel["value"].to_numpy(), index=pd.to_datetime(sel["time_period"], format="%Y-%m"))
    return s[~s.index.duplicated(keep="last")].sort_index()


# ---------- gov_10a_main: D41PAY, B9 by subsector (§6.3 step-B intermediate) ----------

def d41pay(iso3: str, sector: str) -> pd.Series:
    """gov_10a_main D41PAY (interest, expenditure), MIO_NAC, one subsector,
    annual (int-year index)."""
    geo = EUROSTAT_GEO[iso3]
    df = eurostat(f"gov_10a_main_D41PAY_{geo}")
    return _annual_series(df[df["sector"] == sector])


def b9(iso3: str, sector: str) -> pd.Series:
    """gov_10a_main B9 (net lending(+)/borrowing(-)), MIO_NAC, one subsector,
    annual (int-year index)."""
    geo = EUROSTAT_GEO[iso3]
    df = eurostat(f"gov_10a_main_B9_{geo}")
    return _annual_series(df[df["sector"] == sector])


# ---------- gov_10dd_rmd / gov_10dd_ggd / gov_10q_ggdebt / edpt2+3 ----------

def debt_by_maturity(iso3: str, sector: str = "S1311") -> pd.DataFrame:
    """gov_10dd_rmd: gross debt (`GD`) and average residual maturity
    (`GD_VAR`, unit `YR`) by the 7 maturity bands (TOTAL, Y_LE1 <=1y, Y1-5,
    Y_GT1 >1y, Y5-10, Y10-30, Y_GT30 >30y), one subsector, all units."""
    geo = EUROSTAT_GEO[iso3]
    df = eurostat(f"gov_10dd_rmd_{geo}")
    sel = df[df["sector"] == sector]
    return sel.sort_values(["na_item", "unit", "maturity", "time_period"]).reset_index(drop=True)


def debt_by_instrument(iso3: str, sector: str) -> pd.DataFrame:
    """gov_10dd_ggd: gross debt by instrument (`na_item`: GD, GD_F2/F21/F22/
    F29 currency+deposits, GD_F3 debt securities, GD_F4 loans) and by holder
    (`sector2`: `S1_S2` = holders total, `S1` = resident total economy, `S2`
    = rest of world, `S121` = national central bank, `S1311..S1314` = the GG
    subsectors as holders of each other's debt, ...), unit MIO_NAC. `sector`
    is the *issuing* subsector (fixed at pull time to S1311 or S13 — see
    module docstring on the sector/sector2 key-order correction). Callers
    select the holders-total view with `df[df.sector2 == "S1_S2"]` or break
    out by holder by grouping on `sector2`."""
    geo = EUROSTAT_GEO[iso3]
    df = eurostat(f"gov_10dd_ggd_{sector}_{geo}")
    return df.sort_values(["na_item", "sector2", "maturity", "time_period"]).reset_index(drop=True)


def quarterly_debt(iso3: str, sector: str) -> pd.DataFrame:
    """gov_10q_ggdebt: quarterly gross debt (`GD`) and instrument components
    (F2/F21/F22_F29/F3/F31/F32/F4/F41/F42), unit MIO_NAC, one subsector
    (S13, S1311, S13111, S13112, ... as available for the country)."""
    geo = EUROSTAT_GEO[iso3]
    df = eurostat(f"gov_10q_ggdebt_{geo}")
    sel = df[df["sector"] == sector]
    return sel.sort_values(["na_item", "time_period"]).reset_index(drop=True)


# Stock-flow-adjustment na_item labels (gov_10dd_edpt2, gov_10dd_edpt3),
# fetched from the ESTAT NA_ITEM codelist 2026-09-09 — see the report for
# the full discovery method. edpt2 items reconcile net lending/borrowing
# from the "working balance" (cash-based budgetary aggregate) to B.9;
# edpt3 items are the stock-flow adjustment proper, bridging B.9 to the
# change in Maastricht debt (GD).
NA_ITEM_LABELS: dict[str, str] = {
    # gov_10a_main / gov_10dd_ggd core items
    "D41PAY": "Interest, expenditure",
    "B9": "Net lending (+)/net borrowing (-)",
    "GD": "Government consolidated gross debt",
    "GD_F2": "Government consolidated gross debt at face value - currency and deposits",
    "GD_F21": "Government consolidated gross debt at face value - currency",
    "GD_F22": "Government consolidated gross debt at face value - transferable deposits",
    "GD_F29": "Government consolidated gross debt at face value - other deposits",
    "GD_F3": "Government consolidated gross debt at face value - debt securities",
    "GD_F32Z": "Government consolidated gross debt at face value - long-term debt securities, of which: zero-coupon bonds",
    "GD_F4": "Government consolidated gross debt at face value - loans",
    "GD_VAR": "Government consolidated gross debt at face value - at variable interest",
    "F_GD": "Transactions in Maastricht debt instruments at market value",
    "F4": "Loans",
    # gov_10dd_edpt2 (working-balance -> B.9 reconciliation)
    "B9_OB": "Net lending(+)/net borrowing(-) of other bodies of the subsector included in the working balance",
    "ORWB": "Working balance",
    "ORWB_E": "Working balance (+/-) of entities not part of the subsector",
    "OROA_ORWB": "Other adjustments (+/-) included in the working balance",
    "FT": "Financial transactions included in the working balance",
    "F4_ORWB": "Financial transactions included in the working balance - loans (+/-)",
    "F5_ORWB": "Financial transactions included in the working balance - equity and investment fund shares (+/-)",
    "F4_ACQ_ORWB": "Financial transactions included in the working balance - loans; acquisition/increase (+)",
    "F4_DIS_ORWB": "Financial transactions included in the working balance - loans; disposal/reduction (-)",
    "F5_ACQ_ORWB": "Financial transactions included in the working balance - equity and investment fund shares; acquisition/increase (+)",
    "F5_DIS_ORWB": "Financial transactions included in the working balance - equity and investment fund shares; disposal/reduction (-)",
    "FNDX_ORWB": "Financial transactions included in the working balance - other financial transactions (+/-)",
    "FNDL_ORWB": "Financial transactions included in the working balance - other financial transactions (+/-), of which: transactions in debt liabilities (+/-)",
    "F71K_ORWB": "Financial transactions included in the working balance - other financial transactions (+/-), of which: net settlements under swap contracts (+/-)",
    "ORNF_ORWB": "Non-financial transactions not included in the working balance",
    "ORD41A_ORWB": "Difference between interest (D.41) paid (+) and accrued (-) included in the working balance",
    "F8_ASS_ORWB": "Other accounts receivable (+) included in the working balance",
    "F8_LIAB_ORWB": "Other accounts payable (-) included in the working balance",
    # gov_10dd_edpt3 (B.9 -> change in Maastricht debt: the stock-flow adjustment)
    "B9_T3": "Net lending (-)/net borrowing (+) (reversed sign)",
    "B9FX9": "Discrepancy with the financial net lending/net borrowing (B9F-B9)",
    "YA3": "Total statistical discrepancies",
    "YA3O": "Statistical discrepancies: other statistical discrepancies (+/-)",
    "KX": "Adjustments: other volume changes in financial liabilities (-)",
    "K61": "Changes in sector classification and structure (+/-)",
    "GD_CH": "Change in consolidated gross debt",
    "GD_CTB": "Subsector contribution to general government gross debt",
    "GD_HOLD": "Holdings of other subsectors' debt",
    "F_ASS": "Net acquisition (+) of financial assets",
    "F2_ASS": "Net acquisition (+) of financial assets - currency and deposits",
    "F3_ASS": "Net acquisition (+) of financial assets - debt securities",
    "F4_ASS": "Net acquisition (+) of financial assets - loans",
    "F4_ACQ_ASS": "Net acquisition (+) of financial assets - loans - acquisition/increase (+)",
    "F4_DIS_ASS": "Net acquisition (+) of financial assets - loans; disposal/reduction (-)",
    "F41_ASS": "Net acquisition (+) of financial assets - short-term - loans",
    "F42_ASS": "Net acquisition (+) of financial assets - long-term - loans",
    "F42_ACQ_ASS": "Net acquisition (+) of financial assets - long-term loans; acquisition/increase (+)",
    "F42_DIS_ASS": "Net acquisition (+) of financial assets - long-term loans; disposal/reduction (-)",
    "F5_ASS": "Net acquisition (+) of financial assets - equity and investment fund shares/units",
    "F5PN_ASS": "Net acquisition (+) of financial assets - equity and investment fund shares/units - portfolio investments, net",
    "F5OP_ASS": "Net acquisition (+) of financial assets - equity and investment fund shares/units other than portfolio investments",
    "F5OP_ACQ_ASS": "Net acquisition (+) of financial assets - equity and investment fund shares/units other than portfolio investments; acquisition/increase (+)",
    "F5OP_DIS_ASS": "Net acquisition (+) of financial assets - equity and investment fund shares/units other than portfolio investments; disposal/reduction (-)",
    "F71_ASS": "Net acquisition (+) of financial assets - financial derivatives",
    "F8_ASS": "Net acquisition (+) of financial assets - other accounts receivable (+)",
    "FN_ASS": "Net acquisition (+) of financial assets - other financial assets (F.1, F.6)",
    "ORADJ": "Total adjustments",
    "F71_ADJ_LIAB": "Adjustments: net incurrence (-) of liabilities in financial derivatives",
    "F8_ADJ_LIAB": "Adjustments: net incurrence (-) of other accounts payable",
    "FV_ADJ_LIAB": "Adjustments: net incurrence (-) of other liabilities (F.1, F.5, F.6 and F.72)",
    "ORINV": "Adjustments: issuances above (-)/below (+) nominal value",
    "ORD41A_ADJ": "Adjustments: difference between interest expenditure (D.41) accrued (-) and paid (+)",
    "ORRNV": "Adjustments: redemptions/repurchase of debt above (+)/below (-) nominal value",
    "ORFCD": "Adjustments: appreciation (+)/depreciation (-) of foreign currency debt",
}


def sfa_components(iso3: str) -> pd.DataFrame:
    """gov_10dd_edpt2 (working-balance -> B.9) and gov_10dd_edpt3 (B.9 ->
    change in gross debt, the stock-flow adjustment proper) concatenated,
    unit MIO_NAC, with `table` (`edpt2`/`edpt3`) and `na_item_label` (from
    `NA_ITEM_LABELS`) added. This is the §8 financing-chain step-B source:
    edpt3's `KX`/`ORINV`/`ORRNV`/`ORFCD`/`ORADJ` items are the
    `sfa_financial_transactions`/`sfa_accrual_adjustments`/`sfa_other`
    bridge items of `debt_financing_reconciliation`."""
    geo = EUROSTAT_GEO[iso3]
    d2 = eurostat(f"gov_10dd_edpt2_{geo}")
    d2 = d2[d2["unit"] == "MIO_NAC"].assign(table="edpt2")
    d3 = eurostat(f"gov_10dd_edpt3_{geo}")
    d3 = d3[d3["unit"] == "MIO_NAC"].assign(table="edpt3")
    out = pd.concat([d2, d3], ignore_index=True)
    out["na_item_label"] = out["na_item"].map(NA_ITEM_LABELS).fillna("")
    return out.sort_values(["table", "na_item", "sector", "time_period"]).reset_index(drop=True)


# ---------- prc_hicp: HICP excluding tobacco ----------

def hicp_ex_tobacco(geo: str = "EA", base: str = "I25") -> pd.Series:
    """prc_hicp_minr (base I25/2025, from 1999-12) if `base == "I25"`, else
    prc_hicp_midx (archive, base I15/2015, FR/DE from 1996-01, EA from
    2000-12, to 2025-12). Monthly, DatetimeIndex."""
    dataset = "prc_hicp_minr" if base == "I25" else "prc_hicp_midx"
    df = eurostat(f"{dataset}_{geo}")
    return _monthly_series(df)


def hicp_ex_tobacco_chained(geo: str = "EA") -> pd.Series:
    """I15 (archive) chained to I25 (current) on the 2025 base: the archive
    is rescaled by the mean I25/I15 ratio over their overlap months, then
    concatenated with I25 from its first observation. The chain factor is
    attached as `.attrs["chain_factor"]` and reported in
    `reports/debt_sources/eurostat_insee_oecd.md`."""
    old = hicp_ex_tobacco(geo, base="I15")
    new = hicp_ex_tobacco(geo, base="I25")
    overlap = old.index.intersection(new.index)
    factor = float((new[overlap] / old[overlap]).mean())
    rescaled_old = old * factor
    combined = pd.concat([rescaled_old[rescaled_old.index < new.index.min()], new]).sort_index()
    combined.attrs["chain_factor"] = factor
    combined.attrs["overlap_months"] = int(len(overlap))
    return combined


# ---------- irt_st_m / irt_lt_mcby_m ----------

def ea_money_market(tenor: str = "3M") -> pd.Series:
    """irt_st_m: euro-area money-market rate, IRT_M3 (3-month) or IRT_M6
    (6-month), monthly."""
    code = {"3M": "IRT_M3", "6M": "IRT_M6"}[tenor]
    df = eurostat(f"irt_st_m_{code}")
    return _monthly_series(df)


def long_term_yield(geo: str) -> pd.Series:
    """irt_lt_mcby_m: long-term government bond yield (Maastricht
    convergence criterion series), monthly, geo in {FR, DE, EA}."""
    df = eurostat(f"irt_lt_mcby_m_{geo}")
    return _monthly_series(df)


# ---------- INSEE serie/ajax ----------

_INSEE_ROW_RE = re.compile(
    r'<tr>\s*<td>(\d{4})</td>\s*'
    r'<td><span data-i18n="series\.mois\.(\d{2})">[^<]*</span></td>\s*'
    r'<td class="nombre">([^<]*)</td>'
)


def _insee_snap_path(idbank: str) -> Path:
    for source_id in ("INSEE_IPC", "INSEE_AFT_AGG"):
        try:
            return snap_path(source_id, idbank)
        except FileNotFoundError:
            continue
    raise FileNotFoundError(f"no snapshot for INSEE idbank {idbank} — run `ggfiscal debt fetch`")


def _insee_payload(idbank: str) -> dict:
    return json.loads(_insee_snap_path(idbank).read_text(encoding="utf-8"))


def _insee_number(raw: str) -> float | None:
    # French formatting: narrow no-break space (U+202F) / plain space as the
    # thousands separator, comma as the decimal point.
    cleaned = raw.strip().replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


@lru_cache(maxsize=None)
def insee_series(idbank: str) -> pd.Series:
    """One INSEE `serie/ajax` idbank as a monthly float Series (DatetimeIndex),
    parsed from the `tableau-series` HTML table (the JSON's own
    `observations` field is null; `html` carries the full history)."""
    html = _insee_payload(idbank).get("html", "")
    data: dict[pd.Timestamp, float] = {}
    for y, m, v in _INSEE_ROW_RE.findall(html):
        val = _insee_number(v)
        if val is not None:
            data[pd.Timestamp(int(y), int(m), 1)] = val
    return pd.Series(data, dtype=float).sort_index()


def fr_cpi_ex_tobacco_chained() -> pd.Series:
    """France entière IPC ex-tobacco, idbank 001763852 (base 2015, 1990-01
    to 2025-12, stopped) chained to 011814056 (base 2025, from 1996-01) on
    the 2025 base, using the full 1996-01..2025-12 overlap. The ratio is
    constant to 4 decimal places over the overlap (reported in
    `reports/debt_sources/eurostat_insee_oecd.md`); the mean is used as the
    chain factor and attached as `.attrs["chain_factor"]`."""
    old = insee_series("001763852")
    new = insee_series("011814056")
    overlap = old.index.intersection(new.index)
    factor = float((new[overlap] / old[overlap]).mean())
    rescaled_old = old * factor
    combined = pd.concat([rescaled_old[rescaled_old.index < new.index.min()], new]).sort_index()
    combined.attrs["chain_factor"] = factor
    combined.attrs["overlap_months"] = int(len(overlap))
    return combined


def aft_aggregates() -> pd.DataFrame:
    """Long frame of every INSEE_AFT_AGG idbank: idbank, label (from the
    JSON `series[0]` title), period (Timestamp), value_eur_mn (already
    expressed in EUR millions per the series' own unit label)."""
    rows = []
    for idbank in INSEE_AFT_AGG_IDBANKS:
        payload = _insee_payload(idbank)
        label = payload["series"][0]["titre"] if payload.get("series") else ""
        s = insee_series(idbank)
        for period, value in s.items():
            rows.append({"idbank": idbank, "label": label, "period": period,
                         "value_eur_mn": value})
    return pd.DataFrame(rows, columns=["idbank", "label", "period", "value_eur_mn"])


# ---------- OECD SDMX-CSV (csvfilewithlabels: code + label column pairs) ----------

_OECD_CODE_COL_RE = re.compile(r"^[A-Z0-9_]+$")
_OECD_DROP_COLS = ("STRUCTURE", "STRUCTURE_ID", "STRUCTURE_NAME", "ACTION")


def _oecd_code_frame(source_id: str, part: str) -> pd.DataFrame:
    """Keep only the all-caps code columns from an OECD `csvfilewithlabels`
    export (label columns carry human-readable text in the same row and are
    dropped); lower-case the remaining column names."""
    path = snap_path(source_id, part)
    df = pd.read_csv(path, dtype=str)
    code_cols = [c for c in df.columns if _OECD_CODE_COL_RE.match(c) and c not in _OECD_DROP_COLS]
    out = df[code_cols].copy()
    out.columns = [c.lower() for c in out.columns]
    return out


def oecd_psd(iso3: str) -> pd.DataFrame:
    """OECD DF_T7PSD_Q: tidy frame keeping every dimension column (`sector`
    — S1311 central government, S13 general government, S1ZS public sector,
    ...; `instr_asset` — F2/F3/F4/F6/F8 plus FD4/FLE/FLD total-debt
    aggregates; `maturity` — S/L/T/LS/LL original/residual bands;
    `unit_measure`, `debt_breakdown`, ...), `time_period`, `period_start`
    (quarterly), `value` (float)."""
    df = _oecd_code_frame("OECD_T7PSD", f"T7PSD_{iso3}")
    df["value"] = pd.to_numeric(df.pop("obs_value"), errors="coerce")
    df["period_start"] = df["time_period"].map(_period_start)
    return df


def oecd_rate(iso3: str, measure: str) -> pd.Series:
    """OECD DF_FINMARK: IR3TIB (3-month interbank) or IRLT (long-term
    government bond yield) reference rate, percent per annum, monthly."""
    df = _oecd_code_frame("OECD_FINMARK", f"FINMARK_{measure}_{iso3}")
    idx = pd.to_datetime(df["time_period"], format="%Y-%m")
    s = pd.Series(pd.to_numeric(df["obs_value"], errors="coerce").to_numpy(), index=idx)
    return s[~s.index.duplicated(keep="last")].sort_index()
