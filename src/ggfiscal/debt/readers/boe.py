"""Readers for family 'boe' (DEBT_KICKOFF.md §4.2, §5.4, §5.11, §13).

Three snapshot groups feed five functions:

- `BOE_APF` (six xlsx workbooks) -> `apf_operations()` (per-ISIN purchase and
  sale operations, unified across the core APF programme and the two 2022
  financial-stability side-portfolios) and `apf_maturity_profile()` (the
  current stock of APF gilt holdings by maturity).
- `BOE_YIELD_CURVES` (nine zips of xlsx workbooks) -> `yield_curve()`, the
  zero-coupon ("spot") government liability curve, long format.
- `BOE_IADB` (two IADB CSV/HTML exports plus `baserate.xls`) ->
  `iadb_series()` and `bank_rate_history()`.

Nothing here fabricates a value: unparseable rows are dropped and the drop
count is logged (module logger `ggfiscal.debt.readers.boe`), never silently
absorbed and never imputed.
"""

from __future__ import annotations

import io
import logging
import zipfile

import pandas as pd

from ggfiscal.debt.readers import snap_path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BOE_APF — operations (purchases and sales) and the maturity profile
# ---------------------------------------------------------------------------

# (part, sheet, programme, direction) for every operations workbook. The
# maturity-profile workbook is handled separately (`apf_maturity_profile`).
_APF_OPERATIONS = (
    ("gilt_purchases", "APF Gilts", "apf", 1),
    ("gilt_sales", "APF gilt sales", "apf", -1),
    ("fs_long_dated_purchases", "UK Government Bonds", "fs_long_dated", 1),
    ("fs_index_linked_purchases", "Web report", "fs_index_linked", 1),
    ("fs_gilt_sales", "APF FS portfolio gilt sales", "fs_sales", -1),
)

# BoE spells the column headers a little differently release to release
# (a stray "\n", "Bond" vs "Bond\n", "of which non-competitive" only on the
# purchases sheet) -> normalise on the way in.
_COLUMN_RENAME = {
    "Operation date": "operation_date",
    "Settlement date": "settlement_date",
    "ISIN": "isin",
    "Bond": "bond_label",
    "Bond\n": "bond_label",
    "Total allocation (nominal £mn)": "nominal_gbp_mn",
    "Total allocation (proceeds £mn)": "proceeds_gbp_mn",
    "Weighted Average Accepted Yield (%)": "wa_yield_pct",
    "Weighted Average Accepted Price": "wa_price",
}

_OPS_COLUMNS = [
    "operation_date", "settlement_date", "isin", "bond_label",
    "direction", "nominal_gbp_mn", "proceeds_gbp_mn", "wa_yield_pct",
    "wa_price", "programme", "part",
]


def _read_apf_sheet(path, sheet: str, programme: str, direction: int, part: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, header=1)
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]
    df = df.rename(columns=_COLUMN_RENAME)
    wanted = list(dict.fromkeys(_COLUMN_RENAME.values()))  # de-dup, keep order
    df = df[[c for c in wanted if c in df.columns]].copy()

    n_before = len(df)
    df["operation_date"] = pd.to_datetime(df["operation_date"], errors="coerce")
    df["settlement_date"] = pd.to_datetime(df.get("settlement_date"), errors="coerce")
    # A footer/comment row (fs_gilt_sales carries a trailing asterisked note)
    # fails both operation_date and isin parsing -> drop, log the count.
    keep = df["operation_date"].notna() & df["isin"].notna()
    dropped = int((~keep).sum())
    if dropped:
        log.info("BOE_APF/%s (%s): dropped %d unparseable row(s) of %d",
                 part, sheet, dropped, n_before)
    df = df[keep].copy()

    for col in ("nominal_gbp_mn", "proceeds_gbp_mn", "wa_yield_pct", "wa_price"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = pd.NA
    df["direction"] = direction
    df["programme"] = programme
    df["part"] = part
    return df[_OPS_COLUMNS]


def apf_operations() -> pd.DataFrame:
    """Every APF gilt-purchase and gilt-sale operation, per ISIN, across the
    core Asset Purchase Facility and the two 2022 financial-stability
    side-portfolios (long-dated and index-linked purchases; their combined
    sales file). `nominal_gbp_mn` and `proceeds_gbp_mn` are in GBP millions
    as published (zero-allocation lines — a gilt was offered into the
    operation but none was accepted — are kept: they are real, published
    operation rows, not gaps). `direction` is +1 for a purchase, -1 for a
    sale. `programme` in {apf, fs_long_dated, fs_index_linked, fs_sales}.
    """
    frames = []
    for part, sheet, programme, direction in _APF_OPERATIONS:
        path = snap_path("BOE_APF", part)
        frames.append(_read_apf_sheet(path, sheet, programme, direction, part))
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["operation_date", "isin"]).reset_index(drop=True)


def apf_maturity_profile() -> pd.DataFrame:
    """Current stock of APF gilt holdings by maturity (`table-for-website.xlsx`,
    sheet "Maturity Profile of APF (Table)"). `total_nominal_gbp_bn` is the
    total amount of that gilt in issue; `remaining_stock_gbp_bn` is the
    running total of remaining APF gilt holdings as the table steps through
    gilts in maturity order (the workbook's own cumulative column, not
    recomputed here). The workbook's own summary row ("Current stock of
    holdings", no gilt name or maturity date) is dropped — it is a total,
    not a security."""
    path = snap_path("BOE_APF", "maturity_profile")
    raw = pd.read_excel(path, sheet_name="Maturity Profile of APF (Table)", header=1)
    raw = raw.rename(columns={
        "Gilt ": "gilt_name",
        "Gilt": "gilt_name",
        "Maturity Date": "maturity_date",
        "Total Nominal (£bn)": "total_nominal_gbp_bn",
        "Remaining Stock of APF": "remaining_stock_gbp_bn",
    })
    n_before = len(raw)
    raw["maturity_date"] = pd.to_datetime(raw["maturity_date"], errors="coerce")
    keep = raw["maturity_date"].notna()
    dropped = int((~keep).sum())
    if dropped:
        log.info("BOE_APF/maturity_profile: dropped %d non-security row(s) of %d "
                 "(units subheader, 'current stock of holdings' total)", dropped, n_before)
    out = raw[keep].copy()
    out["total_nominal_gbp_bn"] = pd.to_numeric(out["total_nominal_gbp_bn"], errors="coerce")
    out["remaining_stock_gbp_bn"] = pd.to_numeric(out["remaining_stock_gbp_bn"], errors="coerce")
    cols = ["gilt_name", "maturity_date", "total_nominal_gbp_bn", "remaining_stock_gbp_bn"]
    return out[cols].sort_values("maturity_date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# BOE_YIELD_CURVES — nominal, real, inflation, OIS spot curves
# ---------------------------------------------------------------------------

# kind -> (part suffix for the frequency-specific pull, substring to match
# the workbook filename inside the 'latest' bundle).
_YC_KIND_MATCH = {
    "nominal": "Nominal",
    "real": "Real",
    "inflation": "Inflation",
    "ois": "OIS",
}


def _spot_sheet_name(sheet_names: list[str]) -> str:
    """The zero-coupon ("spot") curve sheet: named '... spot curve' (e.g.
    '4. spot curve', '4. nominal spot curve', '2. spot curve' for OIS, which
    has no forward/par short-end sheets). Excludes the short-end sheets
    ('3. spot, short end') and the forward-curve sheets, which are par/
    forward, not zero-coupon."""
    candidates = [s for s in sheet_names
                 if s.strip().lower().endswith("spot curve")]
    if not candidates:
        raise ValueError(f"no spot-curve sheet among {sheet_names!r}")
    return candidates[0]


def _parse_spot_workbook(content: bytes, kind: str, part: str, workbook_name: str) -> pd.DataFrame:
    xf = pd.ExcelFile(io.BytesIO(content))
    sheet = _spot_sheet_name(xf.sheet_names)
    raw = xf.parse(sheet, header=None)

    years_row = None
    for i in range(min(10, len(raw))):
        if str(raw.iloc[i, 0]).strip().lower() == "years:":
            years_row = i
            break
    if years_row is None:
        raise ValueError(f"BOE_YIELD_CURVES/{part} ({workbook_name}, {sheet!r}): "
                         "'years:' maturity header row not found")

    maturities = pd.to_numeric(raw.iloc[years_row, 1:], errors="coerce")
    valid_cols = maturities.dropna()
    body = raw.iloc[years_row + 2:, :]
    dates = pd.to_datetime(body.iloc[:, 0], errors="coerce")
    vals = body.loc[:, valid_cols.index].apply(pd.to_numeric, errors="coerce")
    vals.columns = valid_cols.values
    vals.index = dates

    long = vals.stack().rename("value_pct").reset_index()
    long.columns = ["date", "maturity_years", "value_pct"]
    n_before = len(long)
    long = long.dropna(subset=["date", "maturity_years", "value_pct"])
    dropped = n_before - len(long)
    if dropped:
        log.info("BOE_YIELD_CURVES/%s (%s): dropped %d cell(s) with no date/"
                 "maturity/value of %d", part, workbook_name, dropped, n_before)
    long["kind"] = kind
    return long


def yield_curve(kind: str, frequency: str = "monthend") -> pd.DataFrame:
    """The BoE government liability zero-coupon ("spot") curve, long format:
    one row per (date, maturity_years), `value_pct` the annualised
    zero-coupon yield in per cent (nominal/real: %; OIS: % per annum; the
    published curves, not a re-derivation).

    `kind` in {nominal, real, inflation, ois}; `frequency` in {daily,
    monthend, latest} ('latest' is BoE's small current-month-only bundle,
    one workbook per kind, used for a quick freshness check rather than
    history). Each BoE zip holds two or three era-split workbooks (e.g.
    "...1970 to 2015.xlsx", "...2016 to 2024.xlsx", "...2025 to
    present.xlsx"); every workbook's spot-curve sheet is parsed and
    concatenated. The spot (zero-coupon) sheet is picked over the forward
    and par-yield sheets in the same workbook (see `_spot_sheet_name`);
    real/inflation curves are NaN (dropped) before their instrument's
    first observation even though the workbook nominally starts earlier."""
    if kind not in _YC_KIND_MATCH:
        raise ValueError(f"kind must be one of {sorted(_YC_KIND_MATCH)}, got {kind!r}")

    if frequency == "latest":
        part = "latest"
        path = snap_path("BOE_YIELD_CURVES", part)
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if _YC_KIND_MATCH[kind] in n]
            if not names:
                raise ValueError(f"no workbook matching kind={kind!r} in BOE_YIELD_CURVES/latest")
            frames = [_parse_spot_workbook(z.read(n), kind, part, n) for n in names]
    else:
        part = f"{kind}_{frequency}"
        path = snap_path("BOE_YIELD_CURVES", part)
        with zipfile.ZipFile(path) as z:
            frames = [_parse_spot_workbook(z.read(n), kind, part, n) for n in z.namelist()]

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["date", "maturity_years"], keep="last")
    return out.sort_values(["date", "maturity_years"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# BOE_IADB — IUDSOIA (SONIA), IUDBEDR (Bank Rate), and baserate.xls
# ---------------------------------------------------------------------------

def iadb_series(code: str) -> pd.Series:
    """One BoE Interactive Database series (e.g. `IUDSOIA` = SONIA,
    `IUDBEDR` = Bank Rate) as a float Series with a DatetimeIndex, in the
    series' native units (per cent per annum for both). The endpoint
    (`families.boe._iadb_url`) can answer either a plain two-column CSV
    (`DATE,<code>`, observed live 2026-09-09) or, per DEBT_KICKOFF.md §13,
    an HTML page carrying `<table id="stats-table">` — both are handled
    here; the raw bytes are stored as-is by the fetch layer regardless of
    which shape came back."""
    path = snap_path("BOE_IADB", code)
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")

    if "<table" in text.lower():
        try:
            tables = pd.read_html(io.StringIO(text), attrs={"id": "stats-table"})
        except ValueError:
            tables = []
        if not tables:
            tables = pd.read_html(io.StringIO(text))
        df = tables[0]
        df.columns = [str(c).strip() for c in df.columns]
    else:
        df = pd.read_csv(io.StringIO(text))
        df.columns = [str(c).strip() for c in df.columns]

    date_col = df.columns[0]
    val_col = code if code in df.columns else df.columns[1]
    dates = pd.to_datetime(df[date_col], format="%d %b %Y", errors="coerce")
    dates = dates.where(dates.notna(), pd.to_datetime(df[date_col], errors="coerce"))
    values = pd.to_numeric(df[val_col], errors="coerce")

    n_before = len(df)
    keep = dates.notna() & values.notna()
    dropped = int((~keep).sum())
    if dropped:
        log.info("BOE_IADB/%s: dropped %d unparseable row(s) of %d", code, dropped, n_before)

    s = pd.Series(values[keep].to_numpy(), index=pd.DatetimeIndex(dates[keep]), name=code)
    return s.sort_index()


def bank_rate_history() -> pd.DataFrame:
    """Bank Rate (and predecessor Bank/Minimum Lending/dealing/repo rate)
    changes since 1694, from `baserate.xls` sheet "HISTORICAL SINCE 1694".
    Columns: `date_changed` (the date the new rate took effect — day is
    unpublished before 1844 and is recorded as the 1st of the month in that
    case, since the source gives no finer resolution) and `rate_pct`."""
    path = snap_path("BOE_IADB", "baserate_xls")
    raw = pd.read_excel(path, sheet_name="HISTORICAL SINCE 1694", header=None)

    # Row 6 (0-based) is the last header row ("Bank Rate" in col A); data
    # runs from row 7. Columns: A=year (set only on a year's first entry),
    # B=day (blank before 1844), C=month (3-letter abbrev.), D=new rate (%).
    body = raw.iloc[7:, :4].copy()
    body.columns = ["year", "day", "month", "rate_pct"]
    body["year"] = body["year"].ffill()
    # Blank rows separate one year's entries from the next in the source
    # sheet — expected formatting, not a data-quality drop, so removed
    # before the unparseable-row count below is taken.
    body = body.dropna(subset=["month", "rate_pct"])

    n_before = len(body)
    body["day"] = body["day"].fillna(1).astype(int)
    body["rate_pct"] = pd.to_numeric(body["rate_pct"], errors="coerce")
    body["date_changed"] = pd.to_datetime(
        body["year"].astype(int).astype(str) + body["month"].astype(str) + body["day"].astype(str),
        format="%Y%b%d", errors="coerce")

    keep = body["date_changed"].notna() & body["rate_pct"].notna()
    dropped = n_before - int(keep.sum())
    if dropped:
        log.info("BOE_IADB/baserate_xls: dropped %d unparseable row(s) of %d", dropped, n_before)

    out = body[keep][["date_changed", "rate_pct"]]
    return out.sort_values("date_changed").reset_index(drop=True)
