"""Readers for the 'ons_hmt' family: ONS public sector finances (Appendix A and
Appendix S), ONS PUSF/MM23 time series, HM Treasury Debt Management Reports and
National Loans Fund Accounts.

These are the GBR §6.3 reconciliation intermediates and the `UK_RPI` reference
series (§4.2). Nothing here adjusts a published number: every frame is the
publisher's own value, long-shaped, with the period label kept verbatim beside
the parsed period so a value can always be traced back to its cell.

Layouts verified against the 2026-08-20 vintage (snapshots of 2026-09-09).

Appendix A worksheets share one shape, but not one row offset:

    row 0..3   title / "This worksheet contains one table" / source / coverage
    row 4      "Time period" + one column heading per series
    row 5      "Transaction code"  (present on REC2, REC3, PSA6* — not on PSA8A_1)
    row 5|6    "Dataset identifier code" + one CDID per column
    then       data rows, in blocks: calendar years, financial years,
               quarters, months

so `psa_table` finds the header and CDID rows by their stub label rather than
by position. Period labels in this vintage are

    "1998"                  calendar year   -> CY, 1998-01-01
    "Apr 1997 to Mar 1998"  financial year  -> FY, 1997-04-01
    "Apr to Jun 1997"       quarter         -> Q,  1997-04-01
    "2026 Jul"              month           -> M,  2026-07-01

and `_parse_period` also accepts the "1998/99", "1998-99", "2026 Q1" and
"Jul 2026" spellings that other ONS workbooks use.

Appendix S "Table 1.2A" is one row earlier throughout (row 3 headings, row 4
transaction codes, row 5 CDIDs, data from row 6) and carries the ESA codes the
financing chain needs — gilts F.332 (ANTA), Treasury bills F.331 (NAVG).

HMT_DMR and HMT_NLF snapshots are stored with extension `.bin`: `ingest.fetch.
_ext_for` has no PDF or HTML branch. Readers address snapshots by manifest
path, so this is cosmetic — see reports/debt_sources/ons_hmt.md.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

from ggfiscal.debt.readers import snap_path

APPENDIX_A = ("ONS_PSF_APPENDIX_A", "appendix_a")
APPENDIX_S = ("ONS_PSF_APPENDIX_S", "appendix_s")
APPENDIX_S_SHEET = "Table 1.2A"

# dataset id -> register source_id for the ONS time-series JSON pulls
TIMESERIES_SOURCE = {"pusf": "ONS_PSF_TIMESERIES", "mm23": "ONS_RPI"}

# PSA8A_1: central government gross debt at nominal value, end of period, £mn
CG_DEBT_INSTRUMENTS = {
    "BKPM": "gilts",
    "BKPJ": "treasury_bills",
    "ACUA": "national_savings",
    "ACRV": "tax_instruments",
    "KW6Q": "other_sterling_and_foreign_currency",
    "KW6R": "nram_and_bb",
    "MDL3": "network_rail",
    "BKPW": "total_cg_gross_debt",
}

PERIOD_TYPES = ("FY", "CY", "Q", "M")

_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}


# ---------- period labels ----------

def _month_no(name: str) -> int | None:
    return _MONTHS.get(name.strip().lower()[:3])


def _ts(year: int, month: int) -> pd.Timestamp:
    return pd.Timestamp(dt.date(year, month, 1))


def _parse_period(label: str) -> tuple[str, pd.Timestamp]:
    """('FY'|'CY'|'Q'|'M', period start) for an ONS period label.

    Unrecognised labels return ('', NaT) so a stray stub row is dropped rather
    than silently mis-dated.
    """
    s = re.sub(r"\s+", " ", str(label)).strip()
    if not s:
        return "", pd.NaT

    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return "CY", _ts(int(m.group(1)), 1)

    # 1998/99, 1998/1999, 1998-99 — financial years starting in April
    m = re.fullmatch(r"(\d{4})\s*[/\-–]\s*(\d{2}|\d{4})", s)
    if m:
        return "FY", _ts(int(m.group(1)), 4)

    m = re.fullmatch(r"(\d{4})\s*Q([1-4])", s, re.IGNORECASE) or \
        re.fullmatch(r"Q([1-4])\s*(\d{4})", s, re.IGNORECASE)
    if m:
        a, b = m.groups()
        year, q = (int(a), int(b)) if len(a) == 4 else (int(b), int(a))
        return "Q", _ts(year, 3 * (q - 1) + 1)

    # "Apr 1997 to Mar 1998": a 12-month span is a financial year, 3 a quarter
    m = re.fullmatch(r"([A-Za-z]{3,9}) (\d{4}) to ([A-Za-z]{3,9}) (\d{4})", s)
    if m:
        m1, y1, m2, y2 = _month_no(m.group(1)), int(m.group(2)), \
            _month_no(m.group(3)), int(m.group(4))
        if m1 and m2:
            span = (y2 - y1) * 12 + (m2 - m1) + 1
            return ("FY" if span == 12 else "Q" if span == 3 else "CY"), _ts(y1, m1)

    # "Apr to Jun 1997": a quarter inside one calendar year
    m = re.fullmatch(r"([A-Za-z]{3,9}) to ([A-Za-z]{3,9}) (\d{4})", s)
    if m:
        m1, m2, y = _month_no(m.group(1)), _month_no(m.group(2)), int(m.group(3))
        if m1 and m2:
            return ("Q" if m2 - m1 == 2 else "FY" if m2 - m1 == 11 else "CY"), _ts(y, m1)

    m = re.fullmatch(r"(\d{4}) ([A-Za-z]{3,9})", s) or \
        re.fullmatch(r"([A-Za-z]{3,9}) (\d{4})", s)
    if m:
        a, b = m.groups()
        year, mon = (int(a), _month_no(b)) if a.isdigit() else (int(b), _month_no(a))
        if mon:
            return "M", _ts(year, mon)

    return "", pd.NaT


# ---------- Appendix A ----------

@lru_cache(maxsize=None)
def _sheet(source: tuple[str, str], sheet: str, engine: str) -> pd.DataFrame:
    return pd.read_excel(snap_path(*source), sheet_name=sheet,
                         header=None, engine=engine)


def _stub_row(df: pd.DataFrame, prefix: str, start: int = 0) -> int | None:
    """Index of the first row whose column-0 stub starts with `prefix`."""
    for i in range(start, len(df)):
        if str(df.iat[i, 0]).strip().lower().startswith(prefix):
            return i
    return None


def _long(df: pd.DataFrame, head: int, cdid_row: int, first_data: int,
          extra_rows: dict[str, int] | None = None) -> pd.DataFrame:
    """Melt a header/CDID/data block into the common long shape."""
    extra_rows = extra_rows or {}
    cols = []
    for c in range(1, df.shape[1]):
        cdid = str(df.iat[cdid_row, c]).strip()
        label = re.sub(r"\s+", " ", str(df.iat[head, c])).strip()
        if cdid in ("", "nan") and label in ("", "nan"):
            continue
        meta = {"cdid": "" if cdid == "nan" else cdid,
                "column_label": "" if label == "nan" else label}
        for name, r in extra_rows.items():
            v = str(df.iat[r, c]).strip()
            meta[name] = "" if v == "nan" else v
        cols.append((c, meta))

    rows = []
    for i in range(first_data, len(df)):
        label = str(df.iat[i, 0]).strip()
        ptype, start = _parse_period(label)
        if not ptype:
            continue
        for c, meta in cols:
            val = pd.to_numeric(df.iat[i, c], errors="coerce")
            if pd.isna(val):
                continue
            rows.append({"period_label": re.sub(r"\s+", " ", label),
                         "period_type": ptype, "period_start": start,
                         **meta, "value": float(val)})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    front = ["period_label", "period_type", "period_start", "cdid"]
    rest = [c for c in out.columns if c not in front and c != "value"]
    return out[front + rest + ["value"]]


def psa_table(sheet: str) -> pd.DataFrame:
    """One Appendix A worksheet, long: period_label, period_type, period_start,
    cdid, column_label, value. Values are as published (£ million unless the
    column heading says otherwise; PSA9A/PSA9B carry percentages)."""
    df = _sheet(APPENDIX_A, sheet, "openpyxl")
    head = _stub_row(df, "time period")
    if head is None:
        raise ValueError(f"Appendix A sheet {sheet!r}: no 'Time period' header row")
    cdid_row = _stub_row(df, "dataset identifier code", head + 1)
    if cdid_row is None:
        raise ValueError(f"Appendix A sheet {sheet!r}: no 'Dataset identifier code' row")
    return _long(df, head, cdid_row, cdid_row + 1)


def psa_table_columns(sheet: str) -> pd.DataFrame:
    """Column metadata of one Appendix A worksheet: cdid, column_label and, when
    the sheet publishes one, transaction_code (the ESA code, e.g. REC2 '-B.9g')."""
    df = _sheet(APPENDIX_A, sheet, "openpyxl")
    head = _stub_row(df, "time period")
    cdid_row = _stub_row(df, "dataset identifier code", head + 1)
    tcode_row = _stub_row(df, "transaction code", head + 1)
    rows = []
    for c in range(1, df.shape[1]):
        cdid = str(df.iat[cdid_row, c]).strip()
        label = re.sub(r"\s+", " ", str(df.iat[head, c])).strip()
        if cdid in ("", "nan") and label in ("", "nan"):
            continue
        code = ""
        if tcode_row is not None and tcode_row < cdid_row:
            code = str(df.iat[tcode_row, c]).strip()
        rows.append({"cdid": "" if cdid == "nan" else cdid,
                     "column_label": "" if label == "nan" else label,
                     "transaction_code": "" if code == "nan" else code})
    return pd.DataFrame(rows)


def cg_debt_by_instrument(period_types: tuple[str, ...] | None = None) -> pd.DataFrame:
    """PSA8A_1 — central government gross debt at nominal value, end of period,
    £ million, by instrument (gilts BKPM, Treasury bills BKPJ, NS&I ACUA, tax
    instruments ACRV, other sterling and foreign currency KW6Q, NRAM/B&B KW6R,
    Network Rail MDL3, total BKPW).

    Every period type is an end-of-period stock: CY = end-December, FY and Q =
    end-quarter, M = month end. `period_types=("M",)` gives the month-end
    series the register cross-check (§6.3) uses.
    """
    df = psa_table("PSA8A_1")
    df = df[df["cdid"].isin(CG_DEBT_INSTRUMENTS)].copy()
    df["instrument"] = df["cdid"].map(CG_DEBT_INSTRUMENTS)
    df["unit"] = "GBP_mn"
    if period_types:
        df = df[df["period_type"].isin(period_types)]
    return df.reset_index(drop=True)


def cgncr_reconciliation() -> pd.DataFrame:
    """REC2 (CG net borrowing -> CG net cash requirement) and REC3 (CGNCR
    excluding NRAM/B&B/Network Rail M98R -> the headline CGNCR), all columns,
    with a `sheet` column. REC3 carries the index-linked capital uplift MW7L
    and the net premia/discounts on gilt issuance LSIW (§14 GBR)."""
    frames = []
    for sheet in ("REC2", "REC3"):
        d = psa_table(sheet)
        d.insert(0, "sheet", sheet)
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def cg_interest() -> pd.DataFrame:
    """Central government interest, accrued, £ million: the whole of PSA6B_2
    (current expenditure, of which interest NMFX) plus the APF interest and
    dividends receivable column L6BD of PSA6B_1 (§14 GBR: APF income returns
    to central government through L6BD)."""
    exp = psa_table("PSA6B_2")
    exp.insert(0, "sheet", "PSA6B_2")
    rec = psa_table("PSA6B_1")
    rec = rec[rec["cdid"].str.strip("- ") == "L6BD"].copy()
    rec.insert(0, "sheet", "PSA6B_1")
    return pd.concat([exp, rec], ignore_index=True)


# ---------- Appendix S ----------

def cgncr_financing() -> pd.DataFrame:
    """Appendix S table 1.2A — financing of the central government net cash
    requirement by instrument, £ million, long: period_label, period_type,
    period_start, cdid, esa_code, label, value.

    Sign convention is the publisher's: a CDID printed as '-AACE' is published
    with the sign already applied so the row sums to the CGNCR (M98R). ESA
    codes: gilts F.332 (ANTA), Treasury bills F.331 (NAVG), coin F.21 (-EYMW),
    NS&I and tax instruments F.29, loans F.4.
    """
    df = _sheet(APPENDIX_S, APPENDIX_S_SHEET, "xlrd")
    head = _stub_row(df, "transaction")
    if head is None:
        raise ValueError("Appendix S table 1.2A: no 'Transaction' header row")
    tcode_row = _stub_row(df, "transaction code", head + 1)
    cdid_row = _stub_row(df, "dataset identifier code", head + 1)
    if cdid_row is None:
        raise ValueError("Appendix S table 1.2A: no 'Dataset identifier code' row")
    out = _long(df, head, cdid_row, cdid_row + 1,
                extra_rows={"esa_code": tcode_row} if tcode_row is not None else None)
    if out.empty:
        return out
    return out.rename(columns={"column_label": "label"})[
        ["period_label", "period_type", "period_start", "cdid",
         "esa_code", "label", "value"]]


# ---------- ONS time-series JSON ----------

_FREQ_KEY = {"years": "A", "quarters": "Q", "months": "M"}


def ons_timeseries(cdid: str, dataset: str) -> pd.DataFrame:
    """One ONS time-series JSON snapshot as period_type (A|Q|M), period_start,
    value — annual, quarterly and monthly stacked. Annual observations are
    calendar years on both PUSF and MM23."""
    dataset = dataset.lower()
    if dataset not in TIMESERIES_SOURCE:
        raise ValueError(f"unknown ONS dataset {dataset!r}; expected one of "
                         f"{sorted(TIMESERIES_SOURCE)}")
    path = snap_path(TIMESERIES_SOURCE[dataset], cdid.upper())
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for key, freq in _FREQ_KEY.items():
        for obs in doc.get(key) or []:
            value = pd.to_numeric(obs.get("value"), errors="coerce")
            if pd.isna(value):
                continue
            _, start = _parse_period(obs.get("date", ""))
            if pd.isna(start):
                continue
            rows.append({"period_type": freq, "period_start": start,
                         "value": float(value)})
    out = pd.DataFrame(rows, columns=["period_type", "period_start", "value"])
    return out.sort_values(["period_type", "period_start"]).reset_index(drop=True)


def _monthly(cdid: str) -> pd.Series:
    d = ons_timeseries(cdid, "mm23")
    d = d[d["period_type"] == "M"]
    return pd.Series(d["value"].to_numpy(), index=pd.DatetimeIndex(d["period_start"]),
                     name=cdid).sort_index()


RPI_SPLICE_DATE = pd.Timestamp("1987-01-01")


def rpi_index() -> pd.Series:
    """`UK_RPI` (§4.2): RPI all items, monthly, Jan 1987 = 100, DatetimeIndex.

    CHAW is the Jan 1987 = 100 index and starts 1987-01. Before that the only
    published monthly RPI is CDKO, the long-run series on Jan 1974 = 100
    (1947-06 onward). The splice rescales CDKO by

        factor = 100 / CDKO(1987-01)

    and uses it for every month before 1987-01; CHAW is used unchanged from
    1987-01 (§14 GBR: pre-1987 index-linked gilts carry base RPIs quoted on the
    Jan-1987 base, so the whole series must live on that base).

    The two series are the same index on different bases, so CHAW/CDKO is
    constant over the 1987-01– overlap; the ratio is checked to 4 dp and a
    departure raises rather than silently distorting the index ratios.
    """
    chaw, cdko = _monthly("CHAW"), _monthly("CDKO")
    if RPI_SPLICE_DATE not in cdko.index:
        raise ValueError("CDKO has no 1987-01 observation: cannot rescale onto CHAW")
    factor = 100.0 / float(cdko.loc[RPI_SPLICE_DATE])
    overlap = chaw.index.intersection(cdko.index)
    ratios = (chaw.loc[overlap] / cdko.loc[overlap]).round(4)
    distinct = sorted(set(ratios.dropna()))
    if len(distinct) != 1 or abs(distinct[0] - round(factor, 4)) > 1e-9:
        raise ValueError("CHAW/CDKO ratio is not constant to 4 dp over the "
                         f"overlap ({len(overlap)} months, ratios {distinct[:5]}): "
                         "the RPI splice would distort the index")
    back = (cdko[cdko.index < RPI_SPLICE_DATE] * factor)
    out = pd.concat([back, chaw]).sort_index()
    out.name = "UK_RPI"
    out.index.name = "date"
    return out


# ---------- HMT Debt Management Report (accessible HTML) ----------

class _TableParser(HTMLParser):
    """Collect every top-level <table> with the running document text that
    precedes it — gov.uk publishes the table number as a paragraph, not a
    <caption>, so the title has to come from the text before the element."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[tuple[str, list[list[str]]]] = []
        self._text: list[str] = []
        self._depth = 0
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._pre = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._rows, self._pre = [], "".join(self._text)[-600:]
        elif self._depth and tag == "tr":
            self._row = []
        elif self._depth and tag in ("td", "th"):
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag == "table" and self._depth:
            self._depth -= 1
            if self._depth == 0:
                self.tables.append((self._pre, self._rows or []))
                self._rows = None
        elif self._depth and tag == "tr" and self._row is not None:
            self._rows.append(self._row)
            self._row = None
        elif self._depth and tag in ("td", "th") and self._cell is not None:
            if self._row is None:
                self._row = []
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._depth == 0:
            self._text.append(data)


_TABLE_TITLE = re.compile(r"Table\s+([0-9A-Z]{1,2}\.[0-9A-Z]{1,2})\s*:?\s*", re.IGNORECASE)
_FOOTNOTE = re.compile(r"\(\d+\)")


def _dmr_value(text: str) -> float:
    """Cell text -> float. Strips footnote markers, thousands separators, '£',
    '%' and the word 'years'; '-' and '' are missing, not zero."""
    s = _FOOTNOTE.sub("", str(text)).replace(",", "").replace("£", "")
    s = s.replace("%", "").replace("years", "").replace("year", "").strip()
    if s in ("", "-", "–", "—", "n/a", "N/A"):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


@lru_cache(maxsize=None)
def _dmr_html_tables(edition: str) -> list[tuple[str, list[list[str]]]]:
    src = Path(snap_path("HMT_DMR", f"{edition}_html")).read_text(
        encoding="utf-8", errors="replace")
    p = _TableParser()
    p.feed(src)
    return p.tables


DMR_WANTED = ("3.A", "A.1", "A.2")


def dmr_tables(edition: str, wanted: tuple[str, ...] = DMR_WANTED
               ) -> dict[str, pd.DataFrame]:
    """Tidy frames for the numbered tables of one Debt Management Report,
    keyed by table id: 3.A the financing arithmetic, A.1 the debt composition,
    A.2 the CGNCR / redemptions / gross gilt sales history from 2008-09.

    Each frame is long: table, row_index, row, column, value_text, value
    (`value` NaN where the cell is a heading, a dash or non-numeric).

    Only editions published with an accessible HTML rendering can be read here
    (2025-26 and 2026-27 as of 2026-09-09); an edition that is PDF-only raises
    FileNotFoundError. gov.uk repeats the table number on the footnote table
    that follows each real table, so the first table with at least two columns
    under a title wins.
    """
    out: dict[str, pd.DataFrame] = {}
    for pre, rows in _dmr_html_tables(edition):
        titles = _TABLE_TITLE.findall(re.sub(r"\s+", " ", pre))
        if not titles:
            continue
        tid = titles[-1].upper()
        if tid not in wanted or tid in out or not rows or len(rows[0]) < 2:
            continue
        header = rows[0]
        recs = []
        for i, row in enumerate(rows[1:]):
            label = row[0] if row else ""
            for j, cell in enumerate(row[1:], start=1):
                col = header[j] if j < len(header) else f"col{j}"
                recs.append({"table": tid, "row_index": i, "row": label,
                             "column": col, "value_text": cell,
                             "value": _dmr_value(cell)})
        out[tid] = pd.DataFrame(recs)
    return out


# ---------- HMT National Loans Fund Account (PDF) ----------

def _pypdf():
    try:
        import pypdf
    except Exception as e:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "pypdf is required to read the National Loans Fund Account PDFs "
            "(`pip install pypdf cffi`)") from e
    return pypdf


@lru_cache(maxsize=None)
def nlf_account_text(edition: str) -> str:
    """Extracted text of one National Loans Fund Account PDF (`edition` is the
    financial year, e.g. '2024-25'). The PDFs are machine-generated and carry a
    real text layer, so this is extraction, not OCR and not hand-keying."""
    reader = _pypdf().PdfReader(str(snap_path("HMT_NLF", edition)))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# Note 2 heading and the note that closes it. Print typefaces in these PDFs
# break words with stray spaces and ligatures ("Total fi nance costs",
# "3  Income  from  lending  oper ations"), so every line is matched on its
# letters-and-digits key rather than on its words.
_NOTE_START_KEY = re.compile(r"^\d?\.?financ(?:e|ing)costs(?:of|on)borrowing$")
_NOTE_END_KEY = re.compile(r"^\d?\.?incomefromlendingoperations")
# A figure cell: 1,234 / (1,234) / 12.3 / a dash for nil. Lines are read from
# the right — trailing figure tokens are the year columns, what is left is the
# label — because the labels themselves carry footnote digits ("FLS Treasury
# Bills1 74 -") and brackets ("Treasury Bills (FLS)").
_FIG = re.compile(r"\(?-?[\d,]+(?:\.\d+)?\)?|[-\u2013\u2014]")
_DASH = ("-", "\u2013", "\u2014")

_ITEM_KEYS = (
    ("totalfinancecosts", "total"),
    ("gilt", "gilts"),
    ("treasurybill", "treasury_bills"),
    ("nationalsavings", "national_savings"),
    ("otherfinancecosts", "other"),
)


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _split_figures(text: str) -> tuple[str, list[str]]:
    """('Gilt-edged stock', ['49,573', '48,085']) — the label and the year
    columns of one note line. Trailing footnote digits are dropped from the
    label ('FLS Treasury Bills1' -> 'FLS Treasury Bills')."""
    toks = text.split()
    figures: list[str] = []
    while toks and _FIG.fullmatch(toks[-1]):
        figures.insert(0, toks.pop())
    label = re.sub(r"\d+$", "", " ".join(toks)).strip(" .:")
    return label, figures


def _figure(cell: str) -> float:
    """A published figure. A dash is the publisher's nil, i.e. zero, not
    missing; brackets are the publisher's minus sign."""
    if cell in _DASH:
        return 0.0
    negative = cell.startswith("(")
    return (-1.0 if negative else 1.0) * float(cell.strip("()").replace(",", ""))


def _classify(label: str) -> str:
    k = _key(label)
    for key, item in _ITEM_KEYS:
        if key in k:
            return item
    return ""


def nlf_interest_summary(edition: str) -> pd.DataFrame:
    """Interest on the national debt as the NLF Account books it, £ million.

    Note 2 "Finance costs of borrowing" is the cash/effective-interest cost of
    the debt the National Loans Fund carries; it is the §6.3 step-A GBR
    intermediate. Extracted lines are returned as published, one row per line
    of the note:

        edition, source ('note_2' | 'cash_flow'), label, item, value

    `item` is the normalised bucket (gilts, treasury_bills, national_savings,
    other, total) where the line names one, else ''. Editions differ: 2005-06
    to 2010-11 split gilts into 'Marketable'/'Non-marketable' with a 'Total'
    line (classified as gilts by the section it sits in), only 2008-09 onward
    carries a Treasury bills line, and 2008-09/2009-10 print no sub-total under
    'Other finance costs' so its components stay unclassified. The Statement of
    Cash Flows 'Interest paid' line is appended as source 'cash_flow'.

    An edition whose PDF yields no usable text returns an empty frame with
    these columns — 2006-07 and 2007-08 are typeset with no usable ToUnicode
    map and extract as mojibake. No number here is ever hand-keyed.
    """
    cols = ["edition", "source", "label", "item", "value"]
    try:
        text = nlf_account_text(edition)
    except Exception:
        return pd.DataFrame(columns=cols)
    # PDF text carries the "fi"/"fl" ligatures of the print typeface; NFKC
    # folds them so "Other finance costs" matches in every edition.
    lines = [unicodedata.normalize("NFKC", ln).rstrip() for ln in text.split("\n")]

    rows: list[dict] = []
    # The same words head the note and label a line of the Statement of
    # Comprehensive Net Expenditure ("Financing costs of borrowing 2 86,949
    # 84,167"); the key of the heading line ends at "borrowing".
    start = next((i for i, ln in enumerate(lines) if _NOTE_START_KEY.match(_key(ln))),
                 None)
    if start is not None:
        window = lines[start + 1:start + 60]
        section = ""
        for n, ln in enumerate(window):
            if _NOTE_END_KEY.match(_key(ln)):
                break
            t = re.sub(r"\s+", " ", ln).strip()
            if not t:
                continue
            label, figures = _split_figures(t)
            if not label or not re.search(r"[A-Za-z]", label):
                continue
            item = _classify(label)
            if not figures:
                # a bare sub-heading ("Gilt-edged stock", "Other finance
                # costs"): its figure is either on the next line (2020-21) or
                # in a Marketable/Non-marketable block closed by "Total"
                if item:
                    following = next((x for x in window[n + 1:n + 3] if x.strip()), "")
                    lab2, figs2 = _split_figures(re.sub(r"\s+", " ", following).strip())
                    if figs2 and not lab2:
                        rows.append({"edition": edition, "source": "note_2",
                                     "label": label, "item": item,
                                     "value": _figure(figs2[0])})
                    else:
                        section = item
                continue
            if not item and _key(label).startswith("total") and section:
                item = section              # "Total" inside the gilts sub-block
            if item in ("gilts", "treasury_bills", "national_savings", "other"):
                section = item
            rows.append({"edition": edition, "source": "note_2", "label": label,
                         "item": item, "value": _figure(figures[0])})

    for ln in lines:
        s = re.sub(r"\s+", " ", ln).strip()
        m = re.match(r"^Interest paid\s+\((?P<v>[\d,]+)\)", s, re.IGNORECASE)
        if m:
            rows.append({"edition": edition, "source": "cash_flow",
                         "label": "Interest paid", "item": "interest_paid_cash",
                         "value": -float(m.group("v").replace(",", ""))})
            break

    return pd.DataFrame(rows, columns=cols)
