"""Readers for the UK Debt Management Office reports (DEBT_KICKOFF.md §6.1 GBR,
§13: sources ``UK_DMO_GILTS`` and ``UK_DMO_BILLS``).

Every report is the DMO's own export (``GetDataExport?reportCode=…``), each in
the one presentation type the site serves it in (``families/debt_offices.py``
``DMO_FORMATS``). Shapes:

* **D1A** ``Gilts in issue`` (xml) — one ``View_GILTS_IN_ISSUE`` element per gilt
  at the latest close of business: ISIN, name, type (``Conventional`` /
  ``Index-linked 3 months`` / ``Index-linked 8 months``), redemption and first
  issue dates, dividend dates (``22 Apr/Oct``), nominal in issue and the
  nominal including index-linked uplift, £ million.
* **D2.1E** ``Gilt issuance history`` (xml) — one ``View_Gilt_Issuance_History``
  element per operation since 1981-03-27: ISIN, name, actual (settlement)
  date, issuance type (``Outright``, ``Syndication``, ``Cancellation``,
  ``Reverse Auction``, ``Conversion``, ``Switch Auction``, …), **signed**
  nominal (creations positive, cancellations negative), clean price and yield
  (``N/A`` on non-priced operations), indexation lag.
* **D1C** ``Gilt redemptions`` (xls) — one row per gilt redeemed since 1981:
  redemption date, name, nominal outstanding at redemption. No ISIN.
* **D10C** ``Index ratios`` (xml) — ``GILTS`` elements (ISIN, settlement date,
  index ratio) with a nested ``REFERENCE_RPI``; the current month only.
* **D2.2D** ``Treasury bill tender history`` (xml) — nested ``di`` (maturity
  type, maturity date) → ``dd`` (tender date) → ``sdd`` (issue date, size) →
  ``far`` (cover, average yield, average price, tail), since April 2000.
* **D2.2G** ``Treasury bill issuance`` (xls) — monthly issuance by tenor and
  the stock outstanding, financial-year blocks.
* **D2.1A / D2.1PROF7 / D2.1PROF9 / D10A / D8B / D2.2E** — auction, other-
  operation, tender, syndication, future-redemption and current-bill tables;
  cross-checks only (D2.1E is the operations master).

Names carry the coupon and maturity (``4¼% Treasury Gilt 2040``,
``0 1/8% Index-linked Treasury Gilt 2028``, ``12% Exchequer Stock 2013-2017``);
:func:`parse_name` reads them, and :func:`name_key` gives the join key between
the three gilt lists (D1C has no ISIN).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from functools import lru_cache

import numpy as np
import pandas as pd

from ggfiscal.debt.readers import snap_path
from ggfiscal.standardise.readers import latest_snapshots

SOURCE_GILTS = "UK_DMO_GILTS"
SOURCE_BILLS = "UK_DMO_BILLS"

PART_IN_ISSUE = "D1A"
PART_ISSUANCE = "D2.1E"
PART_REDEMPTIONS = "D1C"
PART_RATIOS = "D10C"
PART_AUCTIONS = "D2.1A"
PART_OTHER_OPS = "D2.1PROF7"
PART_TENDERS = "D2.1PROF9"
PART_SYNDICATIONS = "D10A"
PART_FUTURE_REDEMPTIONS = "D8B"
PART_BILL_TENDERS = "D2.2D"
PART_BILL_MONTHLY = "D2.2G"
PART_BILL_CURRENT = "D2.2E"

#: Register parts a GBR build needs (the rest are cross-checks).
REQUIRED = ((SOURCE_GILTS, PART_IN_ISSUE), (SOURCE_GILTS, PART_ISSUANCE),
            (SOURCE_GILTS, PART_REDEMPTIONS), (SOURCE_BILLS, PART_BILL_TENDERS))


@lru_cache(maxsize=None)
def sha(source_id: str, part: str) -> str | None:
    e = latest_snapshots().get((source_id, part))
    return e["sha256"] if e else None


@lru_cache(maxsize=None)
def have(source_id: str, part: str) -> bool:
    return (source_id, part) in latest_snapshots()


def have_register_parts() -> bool:
    return all(have(s, p) for s, p in REQUIRED)


# ------------------------------------------------------------------ helpers

def _num(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "N/A", "n/a", "-", "nan"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _date(value) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    if not text or text in ("N/A",):
        return None
    ts = pd.to_datetime(text, errors="coerce")
    return None if pd.isna(ts) else pd.Timestamp(ts).normalize()


@lru_cache(maxsize=None)
def _xml_root(source_id: str, part: str):
    return ET.parse(snap_path(source_id, part)).getroot()


def _xml_attrs(source_id: str, part: str, tag: str) -> pd.DataFrame:
    return pd.DataFrame([e.attrib for e in _xml_root(source_id, part).iter(tag)])


@lru_cache(maxsize=None)
def _xls(source_id: str, part: str) -> pd.DataFrame:
    """The report sheet as raw cells (header=None); the title block and the
    ``Page -1 of 1`` footer are left to the caller."""
    return pd.read_excel(snap_path(source_id, part), header=None)


# ------------------------------------------------------------- gilt names

FRACTIONS = {"½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅛": " 1/8", "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8"}
NAME_RE = re.compile(r"^(?P<whole>\d+)?\s*(?:(?P<num>\d)/(?P<den>\d))?\s*%\s*(?P<rest>.*)$")
TRANCHE_RE = re.compile(r"\s+(?P<tranche>[A-D])$")
YEARS_RE = re.compile(r"(\d{4})")


def parse_name(name: str) -> dict:
    """``'8½% Treasury Loan 2007 A'`` -> coupon 8.5, years ['2007'], tranche 'A',
    is_linker False, base name ``'8½% Treasury Loan 2007'``. Undated stock
    (``'3½% War Loan'``) has no years."""
    text = str(name).strip()
    tr = TRANCHE_RE.search(text)
    tranche = tr.group("tranche") if tr else None
    base = text[:tr.start()] if tr else text
    norm = base
    for k, v in FRACTIONS.items():
        norm = norm.replace(k, v)
    m = NAME_RE.match(norm)
    if not m:
        return {"name": text, "base_name": base, "coupon_pct": None, "years": [], "tranche": tranche,
                "is_linker": "index" in text.lower(), "is_floating": "floating" in text.lower()}
    coupon = float(m.group("whole") or 0)
    if m.group("num"):
        coupon += float(m.group("num")) / float(m.group("den"))
    rest = m.group("rest")
    return {"name": text, "base_name": base, "coupon_pct": coupon, "years": YEARS_RE.findall(rest),
            "tranche": tranche, "is_linker": "index" in rest.lower(), "is_floating": "floating" in rest.lower()}


def name_key(name: str) -> str:
    """Join key across D1A / D2.1E / D1C: ``'{coupon}|{IL|CV}|{YYYY[-YYYY]}'``;
    the tranche suffix is dropped so tranches fold into their parent. Undated
    stock has no years, so its normalised base name stands in for them."""
    p = parse_name(name)
    years = "-".join(p["years"]) or re.sub(r"\s+", " ", p["base_name"].lower())
    return f"{p['coupon_pct']}|{'IL' if p['is_linker'] else 'CV'}|{years}"


# ----------------------------------------------------------------- gilts

def gilts_in_issue() -> pd.DataFrame:
    df = _xml_attrs(SOURCE_GILTS, PART_IN_ISSUE, "View_GILTS_IN_ISSUE")
    out = pd.DataFrame({
        "isin": df["ISIN_CODE"].str.strip(),
        "name": df["INSTRUMENT_NAME"].str.strip(),
        "instrument_type": df["INSTRUMENT_TYPE"].str.strip(),
        "maturity_bracket": df.get("MATURITY_BRACKET", pd.Series([None] * len(df))).astype(str).str.strip(),
        "cob_date": df["CLOSE_OF_BUSINESS_DATE"].map(_date),
        "redemption_date": df["REDEMPTION_DATE"].map(_date),
        "first_issue_date": df["FIRST_ISSUE_DATE"].map(_date),
        "dividend_dates": df["DIVIDEND_DATES"].str.strip(),
        "current_ex_div_date": df.get("CURRENT_EX_DIV_DATE", pd.Series([None] * len(df))).map(_date),
        "amount_mn": df["TOTAL_AMOUNT_IN_ISSUE"].map(_num),
        "amount_uplifted_mn": df["TOTAL_AMOUNT_INCLUDING_IL_UPLIFT"].map(_num),
    })
    return out


def issuance_history() -> pd.DataFrame:
    """Every operation, signed nominal as published (£ mn)."""
    df = _xml_attrs(SOURCE_GILTS, PART_ISSUANCE, "View_Gilt_Issuance_History")
    out = pd.DataFrame({
        "isin": df["ISIN_CODE"].str.strip(),
        "name": df["INSTRUMENT_NAME"].str.strip(),
        "date": df["ACTUAL_DATE"].map(_date),
        "issuance_type": df["ISSUANCE_TYPE"].str.strip(),
        "nominal_mn": df["NOMINAL_ISSUED"].map(_num),
        "price_pct": df["ISSUE_CLEAN_PRICE"].map(_num),
        "yield_pct": df["ISSUE_YIELD"].map(_num),
        "indexation_lag": df["INDEXATION_LAG"].str.strip().replace("", None),
    })
    return out.sort_values(["isin", "date"]).reset_index(drop=True)


def redemptions() -> pd.DataFrame:
    """D1C rows: redemption date, name, nominal outstanding at redemption (£ mn)."""
    x = _xls(SOURCE_GILTS, PART_REDEMPTIONS)
    dates = pd.to_datetime(x[0], errors="coerce", format="mixed")
    body = x[dates.notna()]
    return pd.DataFrame({
        "redemption_date": pd.to_datetime(body[0]).dt.normalize(),
        "name": body[1].astype(str).str.strip(),
        "nominal_mn": body[2].map(_num),
    }).reset_index(drop=True)


def index_ratios() -> pd.DataFrame:
    rows = []
    for g in _xml_root(SOURCE_GILTS, PART_RATIOS).iter("GILTS"):
        ref = g.find("REFERENCE_RPI")
        rows.append({"isin": g.attrib["ISIN_CODE"].strip(), "name": g.attrib["INSTRUMENT_NAME"].strip(),
                     "date": _date(g.attrib["SETTLEMENT_DATE"]),
                     "index_ratio": _num(g.attrib["INDEX_RATIO_OR_RPI"]),
                     "reference_rpi": _num(ref.attrib.get("REFERENCE_RPI")) if ref is not None else None})
    return pd.DataFrame(rows).sort_values(["isin", "date"]).reset_index(drop=True)


def syndications() -> pd.DataFrame:
    """D10A (an HTML table under an .xls name): syndication date, name, amount
    sold (£ mn nominal), issue price, issue yield."""
    from bs4 import BeautifulSoup

    html = open(snap_path(SOURCE_GILTS, PART_SYNDICATIONS), "rb").read().decode("utf-8", "ignore")
    table = BeautifulSoup(html, "html.parser").find("table")
    rows = [[td.get_text(strip=True) for td in tr.find_all("td")] for tr in table.find_all("tr")]
    body = [r for r in rows[1:] if len(r) >= 5 and _date(r[0]) is not None]
    return pd.DataFrame({
        "date": [_date(r[0]) for r in body],
        "name": [r[1] for r in body],
        "nominal_mn": [_num(r[2]) for r in body],
        "price_pct": [_num(r[3]) for r in body],
        "yield_pct": [_num(r[4]) for r in body],
    })


# ----------------------------------------------------------------- bills

def bill_tenders() -> pd.DataFrame:
    rows = []
    for di in _xml_root(SOURCE_BILLS, PART_BILL_TENDERS).iter("di"):
        for dd in di.iter("dd"):
            for sdd in dd.iter("sdd"):
                far = sdd.find("far")
                a = {**di.attrib, **dd.attrib, **sdd.attrib, **(far.attrib if far is not None else {})}
                rows.append({
                    "maturity_type": a.get("TBILL_MATURITY_TYPE", "").strip(),
                    "maturity_date": _date(a.get("MATURITY_DATE")),
                    "tender_date": _date(a.get("TENDER_DATE")),
                    "issue_date": _date(a.get("ISSUE_DATE")),
                    "size_mn": _num(a.get("SIZE_MILLIONS")),
                    "cover": _num(a.get("COVER")),
                    "yield_pct": _num(a.get("AVERAGE_YIELD_PERCENT")),
                    "price": _num(a.get("AVERAGE_PRICE_GBP")),
                    "tail_bp": _num(a.get("YIELD_TAIL_BP")),
                })
    return pd.DataFrame(rows).sort_values(["maturity_date", "issue_date"]).reset_index(drop=True)


MONTHS = {m: i for i, m in enumerate(["Apr", "May", "Jun", "Jul", "Aug", "Sep",
                                      "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"])}
FY_RE = re.compile(r"^(\d{4})-(\d{2})$")


def bill_monthly() -> pd.DataFrame:
    """D2.2G: month-end issuance by tenor and stock outstanding (£ mn). The
    sheet is blocked by financial year (a ``2026-27`` row, then ``Aug``,
    ``Jul``, …); the month-end date is rebuilt from the block."""
    x = _xls(SOURCE_BILLS, PART_BILL_MONTHLY)
    header_row = next(i for i, v in x[0].items() if str(v).strip() == "Month End")
    cols = [str(c).replace("\n", " ").strip() for c in x.iloc[header_row]]
    rows, fy = [], None
    for _, r in x.iloc[header_row + 1:].iterrows():
        label = str(r[0]).strip()
        m = FY_RE.match(label)
        if m:
            fy = int(m.group(1))
            continue
        if label[:3] in MONTHS and fy is not None:
            month = MONTHS[label[:3]]
            year = fy if month < 9 else fy + 1
            cal_month = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3][month]
            end = (pd.Timestamp(year=year, month=cal_month, day=1) + pd.offsets.MonthEnd(0)).normalize()
            rows.append({"month_end": end, **{c: _num(v) for c, v in zip(cols[1:], r[1:])}})
    df = pd.DataFrame(rows).sort_values("month_end").reset_index(drop=True)
    rename = {}
    for c in df.columns:
        lc = c.lower()
        if lc.startswith("one month"):
            rename[c] = "one_month_mn"
        elif lc.startswith("three month"):
            rename[c] = "three_month_mn"
        elif lc.startswith("six month"):
            rename[c] = "six_month_mn"
        elif lc.startswith("ad hoc"):
            rename[c] = "ad_hoc_mn"
        elif lc.startswith("other issuance"):
            rename[c] = "other_mn"
        elif lc.startswith("total issuance"):
            rename[c] = "total_issuance_mn"
        elif lc.startswith("total stock"):
            rename[c] = "stock_mn"
        elif lc.startswith("t-bill stock for debt"):
            rename[c] = "stock_debt_financing_mn"
    return df.rename(columns=rename)


def bills_current() -> pd.DataFrame:
    """D2.2E: the bills in issue at the data date with their ISINs."""
    x = _xls(SOURCE_BILLS, PART_BILL_CURRENT)
    dates = pd.to_datetime(x[0], errors="coerce", format="mixed")
    body = x[dates.notna()]
    return pd.DataFrame({
        "maturity_date": pd.to_datetime(body[0]).dt.normalize(),
        "isin": body[1].astype(str).str.strip(),
        "original_issue_date": pd.to_datetime(body[2], errors="coerce").dt.normalize(),
        "original_nominal_mn": body[3].map(_num),
    }).reset_index(drop=True)
