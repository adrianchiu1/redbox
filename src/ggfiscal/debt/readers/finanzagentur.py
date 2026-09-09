"""Readers for family 'finanzagentur': Bundesrepublik Deutschland – Finanzagentur
snapshots -> tidy frames (DEBT_KICKOFF.md §6.1 DEU, §13).

Five shapes, all xlsx, all published by ``Abteilung F-HH`` with a timestamp in
row 1 and the title block in rows 8–12:

* **Wertpapierliste** (``wertpapierliste``) — parts
  ``einzelaufstellung_seit_1995`` ("Ausstehende Bundeswertpapiere und
  Kreditmarktmittel", one column per 31 December 1995…2025) and
  ``umlaufende_monatsultimo`` (the same layout with the four most recent
  month-ends). One sheet, ``Wertpapierliste``; the header row is the one whose
  column A reads ``WERTPAPIERART``; columns are
  ``WERTPAPIERART | ISIN | KUPON | LAUFZEIT AB | FÄLLIGKEIT`` then one nominal
  column per as-of date. **Column A carries the security type only on the first
  row of each block** and is forward-filled here; each block closes with a
  ``Zwischensumme`` row (dropped) and the sheet with a ``Summe`` row (kept
  separately as :func:`wertpapierliste_total`). Nominal values are whole euro,
  pre-1999 issues already converted at the irrevocable DEM rate 1.95583.

* **Auktionsergebnisse** (``auktionen``) — parts ``emissionshistorie``
  ("Auktionsergebnisse seit 1999") and ``emissionsergebnisse_aktuell`` (the
  current year). One sheet, ``Seite1``; a four-line header (rows 8–11) whose
  columns are flattened to the fixed names in :data:`AUKTION_COLUMNS`; data from
  row 12 until the footnote block. ``Emissionsvolumen = Zuteilungsvolumen +
  Marktpflegequote`` (the retained tranche, DD2/§4.3 ``retention``), exactly on
  all but 38 of the 1999–2001 rows.

* **Index-Verhältniszahlen** (``index_ratios``) — parts ``index_ratios_2005``,
  ``index_ratios_2015``, ``index_ratios_2025``, one per base year of the euro-area
  HICP ex tobacco. One sheet, ``Deutsch``; row 10 is the header
  (``Datum``, ``Täglicher Referenzindex``, then ``Index-Verhältniszahl {ISIN}``),
  rows 11–15 the per-ISIN terms (Fälligkeit, Zinsen ab, Kupon, 1. Kupon,
  Basisindex), rows 16–17 navigation links, data from row 18. The three files'
  date ranges are disjoint and the ratios are continuous across the seams; only
  the daily reference index rebases.

* **Umlaufvolumen und Eigenbestand** (``umlaufvolumen``) — sheet
  ``rpgUmlaufvolumen`` of the part ``schuldenbericht``, a Datenportal-shaped wide
  sheet (row 14 ``Datum`` then one column per month-end from 31.01.1995) whose
  rows are an indented tree with two top blocks, ``Umlaufvolumen`` and
  ``Eigenbestand``, **by instrument group, never per ISIN**.

* The remaining ``schuldenbericht`` sheets repeat the BMF Datenportal series and
  are read by :mod:`ggfiscal.debt.readers.bmf` from the ministry's own file.
"""

from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from ggfiscal.debt.readers import snap_path
from ggfiscal.standardise.readers import latest_snapshots

SOURCE_ID = "DEU_FINANZAGENTUR"

ANNUAL_PART = "einzelaufstellung_seit_1995"
MONTHLY_PART = "umlaufende_monatsultimo"
AUCTION_PARTS = ("emissionshistorie", "emissionsergebnisse_aktuell")
RATIO_PARTS = ("index_ratios_2005", "index_ratios_2015", "index_ratios_2025")
SCHULDENBERICHT_PART = "schuldenbericht"

#: DEM per EUR, irrevocably fixed 1998-12-31. The office reports the whole
#: 1995-1998 history in euro at this rate; kept here for the provenance note.
DEM_PER_EUR = 1.95583

DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")


@lru_cache(maxsize=None)
def sha(part: str) -> str | None:
    """sha256 of the latest snapshot of one Finanzagentur part."""
    e = latest_snapshots().get((SOURCE_ID, part))
    return e["sha256"] if e else None


@lru_cache(maxsize=None)
def have(part: str) -> bool:
    return (SOURCE_ID, part) in latest_snapshots()


def _de_date(value: object) -> pd.Timestamp | None:
    """'15.04.2046' or a real datetime -> Timestamp; blank -> None."""
    if value is None or value == "":
        return None
    if isinstance(value, pd.Timestamp):
        return value
    if hasattr(value, "year") and hasattr(value, "month"):
        return pd.Timestamp(value)
    m = DATE_RE.match(str(value).strip())
    if not m:
        return None
    d, mo, y = (int(g) for g in m.groups())
    return pd.Timestamp(year=y, month=mo, day=d)


def _de_number(value: object) -> float | None:
    """German decimal comma -> float. '0,100' -> 0.1; '' / None -> None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


@lru_cache(maxsize=None)
def _rows(part: str, sheet: str) -> tuple[tuple, ...]:
    import openpyxl

    wb = openpyxl.load_workbook(snap_path(SOURCE_ID, part), data_only=True, read_only=True)
    if sheet not in wb.sheetnames:
        raise KeyError(f"{part}: no sheet {sheet!r}; have {wb.sheetnames}")
    return tuple(wb[sheet].iter_rows(values_only=True))


# ------------------------------------------------------------- Wertpapierliste

WPL_SHEET = "Wertpapierliste"
WPL_HEADER = ("WERTPAPIERART", "ISIN", "KUPON", "LAUFZEIT AB", "FÄLLIGKEIT")
#: Column A values that close a block rather than name a security.
WPL_SUBTOTAL = "Zwischensumme"
WPL_TOTAL = "Summe"


def _wpl_header_row(rows: tuple[tuple, ...]) -> int:
    for i, r in enumerate(rows):
        if r and r[0] is not None and str(r[0]).strip() == WPL_HEADER[0]:
            return i
    raise ValueError("no WERTPAPIERART header row in the Wertpapierliste sheet")


@lru_cache(maxsize=None)
def wertpapierliste(part: str) -> pd.DataFrame:
    """One Wertpapierliste part -> long frame, one row per (security, as_of).

    Columns: ``wertpapierart`` (forward-filled block label), ``isin`` (the raw
    column-B code — an ISIN for every block except ``Schuldscheindarlehen des
    Bundes``, where it reads ``SSD fällig {year}``), ``kupon_raw``,
    ``first_issue_date``, ``maturity_date``, ``as_of``, ``nominal_eur``.
    ``Zwischensumme`` and ``Summe`` rows are dropped.
    """
    rows = _rows(part, WPL_SHEET)
    h = _wpl_header_row(rows)
    dates = [(j, _de_date(v)) for j, v in enumerate(rows[h]) if j >= 5 and _de_date(v) is not None]
    if not dates:
        raise ValueError(f"{part}: no as-of date columns in the header row")

    art = None
    out: list[dict] = []
    for r in rows[h + 1:]:
        a = "" if r[0] is None else str(r[0]).strip()
        code = "" if len(r) < 2 or r[1] is None else str(r[1]).strip()
        if a == WPL_TOTAL:
            break
        if a:
            art = a
        if not code or code == WPL_SUBTOTAL:
            continue
        base = {
            "wertpapierart": art,
            "isin": code,
            "kupon_raw": None if len(r) < 3 or r[2] in (None, "") else str(r[2]).strip(),
            "first_issue_date": _de_date(r[3] if len(r) > 3 else None),
            "maturity_date": _de_date(r[4] if len(r) > 4 else None),
        }
        for j, as_of in dates:
            v = r[j] if j < len(r) else None
            if v is None or v == "":
                continue
            out.append({**base, "as_of": as_of, "nominal_eur": float(v)})
    return pd.DataFrame(out, columns=["wertpapierart", "isin", "kupon_raw", "first_issue_date",
                                      "maturity_date", "as_of", "nominal_eur"])


@lru_cache(maxsize=None)
def wertpapierliste_securities(part: str) -> pd.DataFrame:
    """The distinct securities of one Wertpapierliste part (terms only, no
    positions), in sheet order — including securities whose every nominal cell
    is blank (the strip blocks of the monthly file)."""
    rows = _rows(part, WPL_SHEET)
    h = _wpl_header_row(rows)
    art = None
    out: list[dict] = []
    seen: set[str] = set()
    for r in rows[h + 1:]:
        a = "" if r[0] is None else str(r[0]).strip()
        code = "" if len(r) < 2 or r[1] is None else str(r[1]).strip()
        if a == WPL_TOTAL:
            break
        if a:
            art = a
        if not code or code == WPL_SUBTOTAL or code in seen:
            continue
        seen.add(code)
        out.append({
            "wertpapierart": art,
            "isin": code,
            "kupon_raw": None if len(r) < 3 or r[2] in (None, "") else str(r[2]).strip(),
            "first_issue_date": _de_date(r[3] if len(r) > 3 else None),
            "maturity_date": _de_date(r[4] if len(r) > 4 else None),
        })
    return pd.DataFrame(out, columns=["wertpapierart", "isin", "kupon_raw",
                                      "first_issue_date", "maturity_date"])


@lru_cache(maxsize=None)
def wertpapierliste_total(part: str) -> pd.Series:
    """The sheet's own ``Summe`` row, indexed by as-of date (euro)."""
    rows = _rows(part, WPL_SHEET)
    h = _wpl_header_row(rows)
    dates = [(j, _de_date(v)) for j, v in enumerate(rows[h]) if j >= 5 and _de_date(v) is not None]
    for r in rows[h + 1:]:
        if r[0] is not None and str(r[0]).strip() == WPL_TOTAL:
            return pd.Series({d: float(r[j]) for j, d in dates
                              if j < len(r) and r[j] not in (None, "")}).sort_index()
    raise ValueError("no Summe row in the Wertpapierliste sheet")


# --------------------------------------------------------- Auktionsergebnisse

AUKTION_SHEET = "Seite1"
#: Flattened four-line header (rows 8-11) of the Auktionsergebnisse sheets, by
#: position. ``mpq_anteil`` and ``bid_offer`` exist only in ``emissionshistorie``.
AUKTION_COLUMNS = [
    "nr",                    # A  Nr.
    "termin",                # B  Termin (bidding day)
    "isin",                  # C  ISIN
    "anleihe",               # D  Anleihe (Bund | Bobl | Schatz | Bubill | ILB | Green | USD-Bond)
    "kupon_frac",            # E  Kupon, as a fraction (0.0375 = 3.75 %)
    "laufzeit",              # F  Laufzeit (maturity date)
    "laufzeitsegment",       # G  Laufzeitsegment ("10 J", "6 M")
    "emissionsvolumen_mn",   # H  Emissionsvolumen (Mio. €)
    "typ",                   # I  Typ (N = Neuemission, A = Aufstockung)
    "verfahren",             # J  Emissionsverfahren (Auk | Syn | M-A | EB)
    "bietungen_mn",          # K  Bietungen (Mio. €)
    "kursgebote_mn",         # L  Kursgebote (Mio. €)
    "gebote_ohne_kurs_mn",   # M  Gebote ohne Kurs (Mio. €)
    "zuteilung_mn",          # N  Zuteilungsvolumen (Mio. €)
    "niedrigster_kurs",      # O  Niedrigster akzeptierter Kurs
    "durchschnittskurs",     # P  Gewogener Durchschnittskurs
    "durchschnittsrendite",  # Q  Durchschnittsrendite (%)
    "marktpflegequote_mn",   # R  Marktpflegequote (Mio. €)
    "bid_to_cover",          # S  Bid-to-Cover-Ratio
    "mpq_anteil",            # T  Anteil MPQ
    "bid_offer",             # U  Bid / Offer
]
#: ``Emissionsverfahren`` codes as the footnote block spells them out.
VERFAHREN = {"Auk": "Auktion", "Syn": "Syndikat", "M-A": "Multi-ISIN-Auktion",
             "EB": "Einstellung in den Eigenbestand"}
ANLEIHE_LABELS = ("Bund", "Bobl", "Schatz", "Bubill", "ILB", "Green", "USD-Bond")


@lru_cache(maxsize=None)
def auktionen_part(part: str) -> pd.DataFrame:
    """One Auktionsergebnisse part -> long frame with :data:`AUKTION_COLUMNS`."""
    rows = _rows(part, AUKTION_SHEET)
    out: list[dict] = []
    for r in rows:
        code = "" if len(r) < 3 or r[2] is None else str(r[2]).strip()
        anleihe = "" if len(r) < 4 or r[3] is None else str(r[3]).strip()
        if anleihe not in ANLEIHE_LABELS or not code:
            continue                      # header, footnote and blank rows
        rec = {name: (r[i] if i < len(r) else None) for i, name in enumerate(AUKTION_COLUMNS)}
        rec["isin"] = code
        rec["anleihe"] = anleihe
        rec["termin"] = _de_date(rec["termin"])
        rec["laufzeit"] = _de_date(rec["laufzeit"])
        rec["verfahren"] = None if rec["verfahren"] is None else str(rec["verfahren"]).strip()
        rec["typ"] = None if rec["typ"] is None else str(rec["typ"]).strip()
        rec["laufzeitsegment"] = (None if rec["laufzeitsegment"] is None
                                  else str(rec["laufzeitsegment"]).strip())
        for k in ("kupon_frac", "emissionsvolumen_mn", "bietungen_mn", "kursgebote_mn",
                  "gebote_ohne_kurs_mn", "zuteilung_mn", "niedrigster_kurs",
                  "durchschnittskurs", "durchschnittsrendite", "marktpflegequote_mn",
                  "bid_to_cover", "mpq_anteil", "bid_offer"):
            rec[k] = _de_number(rec[k])
        rec["part"] = part
        out.append(rec)
    return pd.DataFrame(out, columns=AUKTION_COLUMNS + ["part"])


@lru_cache(maxsize=None)
def auktionen() -> pd.DataFrame:
    """Every operation from ``emissionshistorie`` plus the rows of
    ``emissionsergebnisse_aktuell`` the history does not already carry
    (the two overlap for the current year; the key is ISIN + Termin)."""
    frames = [auktionen_part(p) for p in AUCTION_PARTS if have(p)]
    if not frames:
        raise FileNotFoundError("no Finanzagentur auction snapshot")
    hist = frames[0]
    seen = set(zip(hist["isin"], hist["termin"]))
    extra = [f[~pd.Series(list(zip(f["isin"], f["termin"])), index=f.index).isin(seen)]
             for f in frames[1:]]
    return (pd.concat([hist, *extra], ignore_index=True)
            .sort_values(["termin", "isin"]).reset_index(drop=True))


# --------------------------------------------------------- Index-Verhältniszahlen

RATIO_SHEET = "Deutsch"
RATIO_HEADER_ROW = 10          # 1-based: 'Datum' | 'Täglicher Referenzindex' | 'Index-Verhältniszahl {ISIN}'
RATIO_FIRST_DATA_ROW = 18      # 1-based
RATIO_TERM_ROWS = {11: "maturity", 12: "interest_from", 13: "coupon", 14: "first_coupon",
                   15: "base_index"}
RATIO_COL_RE = re.compile(r"Index-Verh(?:ä|ae)ltniszahl\s+([A-Z]{2}[A-Z0-9]{9}\d)")
TERM_VALUE_RE = re.compile(r":\s*(.+)$")


@lru_cache(maxsize=None)
def index_ratios_part(part: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One index-ratio part -> (ratios, terms).

    ``ratios``: isin, date, index_ratio, reference_index (the file's own daily
    ``Täglicher Referenzindex``, on that file's base year).
    ``terms``: isin, maturity, interest_from, coupon, first_coupon, base_index —
    the five lines beneath the header, parsed off the ``Label: value`` text.
    """
    rows = _rows(part, RATIO_SHEET)
    header = rows[RATIO_HEADER_ROW - 1]
    cols = {j: m.group(1) for j, v in enumerate(header)
            if v is not None and (m := RATIO_COL_RE.search(str(v)))}
    if not cols:
        raise ValueError(f"{part}: no 'Index-Verhältniszahl {{ISIN}}' columns in row {RATIO_HEADER_ROW}")

    terms: dict[str, dict] = {isin: {"isin": isin} for isin in cols.values()}
    for r_no, field in RATIO_TERM_ROWS.items():
        r = rows[r_no - 1]
        for j, isin in cols.items():
            v = r[j] if j < len(r) else None
            if v in (None, ""):
                continue
            m = TERM_VALUE_RE.search(str(v).strip())
            terms[isin][field] = m.group(1).strip() if m else str(v).strip()

    recs: list[dict] = []
    for r in rows[RATIO_FIRST_DATA_ROW - 1:]:
        date = _de_date(r[1] if len(r) > 1 else None)
        if date is None:
            continue
        ref = _de_number(r[2] if len(r) > 2 else None)
        for j, isin in cols.items():
            v = _de_number(r[j] if j < len(r) else None)
            if v is None:
                continue
            recs.append({"isin": isin, "date": date, "index_ratio": v, "reference_index": ref})

    tf = pd.DataFrame(list(terms.values()))
    for field in ("maturity", "interest_from", "first_coupon"):
        if field in tf:
            tf[field] = tf[field].map(_de_date)
    for field in ("coupon", "base_index"):
        if field in tf:
            tf[field] = tf[field].map(lambda s: _de_number(str(s).replace("%", "").strip())
                                      if s is not None and s == s else None)
    tf["part"] = part
    return pd.DataFrame(recs, columns=["isin", "date", "index_ratio", "reference_index"]), tf


@lru_cache(maxsize=None)
def index_ratios() -> tuple[pd.DataFrame, pd.DataFrame]:
    """All three base-year files stacked. Their date ranges are disjoint, so the
    (isin, date) key is unique; ``base_year_file`` records which file a row came
    from because the daily reference index — not the ratio — rebases between
    them."""
    rfs, tfs = [], []
    for part in RATIO_PARTS:
        if not have(part):
            continue
        r, t = index_ratios_part(part)
        rfs.append(r.assign(base_year_file=part))
        tfs.append(t)
    if not rfs:
        raise FileNotFoundError("no Finanzagentur index-ratio snapshot")
    ratios = pd.concat(rfs, ignore_index=True)
    # The files share exactly their rebasing day (2016-03-01 and 2026-03-01),
    # where both carry the same ratio on different reference-index bases; keep
    # the newer file's row so `reference_index` is on the current base.
    ratios = (ratios.drop_duplicates(["isin", "date"], keep="last")
              .sort_values(["isin", "date"]).reset_index(drop=True))
    return ratios, pd.concat(tfs, ignore_index=True)


@lru_cache(maxsize=None)
def index_ratio_seams() -> pd.DataFrame:
    """The rows the base-year files share, side by side: one row per (isin, date)
    on a rebasing day with the two files' ratio and reference index, and the
    relative difference of the ratios (expected 0 — only the index rebases)."""
    parts = [p for p in RATIO_PARTS if have(p)]
    out = []
    for older, newer in zip(parts, parts[1:]):
        a, _ = index_ratios_part(older)
        b, _ = index_ratios_part(newer)
        j = a.merge(b, on=["isin", "date"], suffixes=("_old", "_new"))
        if j.empty:
            continue
        j["ratio_rel_diff"] = (j["index_ratio_new"] / j["index_ratio_old"] - 1.0)
        j["index_rebase_factor"] = j["reference_index_old"] / j["reference_index_new"]
        out.append(j.assign(file_old=older, file_new=newer))
    cols = ["isin", "date", "file_old", "file_new", "index_ratio_old", "index_ratio_new",
            "ratio_rel_diff", "reference_index_old", "reference_index_new", "index_rebase_factor"]
    return (pd.concat(out, ignore_index=True)[cols] if out
            else pd.DataFrame(columns=cols))


# -------------------------------------------------- Umlaufvolumen / Eigenbestand

UMLAUF_SHEET = "rpgUmlaufvolumen"
UMLAUF_DATE_LABEL = "Datum"


@lru_cache(maxsize=None)
def umlaufvolumen() -> pd.DataFrame:
    """``schuldenbericht`` sheet ``rpgUmlaufvolumen`` -> long frame.

    Columns ``block`` (``Umlaufvolumen`` | ``Eigenbestand`` | the trailing
    ``Anlage des WSF …`` row), ``label`` (instrument group), ``level``
    (indentation depth), ``period`` (month-end), ``value_eur``, ``value_eur_mn``.
    The sheet is by instrument **group**: there is no per-ISIN Eigenbestand
    anywhere in the Finanzagentur files.
    """
    import openpyxl

    wb = openpyxl.load_workbook(snap_path(SOURCE_ID, SCHULDENBERICHT_PART), data_only=True)
    ws = wb[UMLAUF_SHEET]
    header_row = 0
    periods: dict[int, pd.Timestamp] = {}
    for i in range(1, ws.max_row + 1):
        if str(ws.cell(i, 1).value or "").strip() != UMLAUF_DATE_LABEL:
            continue
        header_row = i
        periods = {j: _de_date(ws.cell(i, j).value) for j in range(2, ws.max_column + 1)
                   if _de_date(ws.cell(i, j).value) is not None}
        break
    if not periods:
        raise ValueError("no Datum header row in rpgUmlaufvolumen")

    block, out = None, []
    for i in range(header_row + 1, ws.max_row + 1):
        cell = ws.cell(i, 1)
        label = str(cell.value or "").strip()
        if not label:
            continue
        indent = int(cell.alignment.indent or 0)
        if indent == 0:
            block = label
        for j, period in periods.items():
            v = ws.cell(i, j).value
            if v in (None, ""):
                continue
            out.append({"block": block, "label": label, "level": indent, "period": period,
                        "value_eur": float(v), "value_eur_mn": float(v) / 1e6})
    return pd.DataFrame(out, columns=["block", "label", "level", "period",
                                      "value_eur", "value_eur_mn"])
