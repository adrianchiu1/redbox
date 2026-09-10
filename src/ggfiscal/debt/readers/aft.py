"""Readers for the Agence France Trésor pages (DEBT_KICKOFF.md §6.1 FRA, §13:
sources ``FRA_AFT_ENCOURS``, ``FRA_AFT_ADJUDICATIONS``, ``FRA_AFT_INDEXATION``).

The AFT publishes its register as HTML pages behind a Cloudflare challenge;
they are saved by the committee (DOWNLOAD_LIST.md, ``ggfiscal debt
ingest-incoming``) and read here from the snapshot store. Shapes:

* **Encours détaillé** (parts ``oat``, ``oati``, ``oatei``, ``btf`` of
  ``FRA_AFT_ENCOURS``) — one table per maturity year, rows ``Code ISIN |
  Libellé | Encours (€)`` (BTF: ``Code ISIN | Échéance | Encours (€)``), a
  header row per group carrying the year and the group total. The libellé
  names the line: ``OAT 2,50 % 24 septembre 2026``, ``OAT€i 1.85% 25 July
  2027``, ``OATi 0,10 % 1 mars 2029``. Amounts are whole euros (French
  thousands separators, or English ``22,162,000,000.00`` on the English page).
  The page states no as-of date; the snapshot's retrieval date is used.
* **Adjudications** (``dernieres`` and the monthly history pages of
  ``FRA_AFT_ADJUDICATIONS``) — one table per auction day and family (OAT /
  BTF): the first row names the lines, then one row per attribute (dates,
  volumes in EUR mn, limit and weighted-average price / yield, the ISIN row
  last). ``Volume total émis`` = ``Volume adjugé`` + ``ONC après
  adjudication`` (the non-competitive tranche).
"""

from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from ggfiscal.debt.readers import snap_path
from ggfiscal.standardise.readers import latest_snapshots

SOURCE_ENCOURS = "FRA_AFT_ENCOURS"
SOURCE_ADJUDICATIONS = "FRA_AFT_ADJUDICATIONS"
SOURCE_INDEXATION = "FRA_AFT_INDEXATION"

ENCOURS_PARTS = ("oat", "oati", "oatei", "btf")

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "decembre": 12, "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "sept": 9, "janv": 1, "févr": 2, "déc": 12, "oct": 10, "nov": 11, "juil": 7,
}
ISIN_RE = re.compile(r"^FR[0-9A-Z]{10}$")
DATE_TEXT_RE = re.compile(r"(\d{1,2})(?:er)?\s+([A-Za-zéûÉ\.]+)\s+(\d{4})")
DATE_NUM_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
NAME_RE = re.compile(
    r"^(?P<green>GREEN\s+)?(?P<kind>OAT€I|OAT€i|OATi|OAT\$?i|BTANi|BTAN€i|BTAN|OAT|BTF)\s*(?P<green2>verte\s+|VERTE\s+)?"
    r"(?:(?P<zero>z[ée]ro\s+coupon)|(?P<coupon>[\d,\.]+)\s*%)\s*(?P<rest>.*)$", re.IGNORECASE)


@lru_cache(maxsize=None)
def sha(source_id: str, part: str) -> str | None:
    e = latest_snapshots().get((source_id, part))
    return e["sha256"] if e else None


@lru_cache(maxsize=None)
def have(source_id: str, part: str) -> bool:
    return (source_id, part) in latest_snapshots()


def retrieved_at(source_id: str, part: str) -> pd.Timestamp | None:
    e = latest_snapshots().get((source_id, part))
    return pd.Timestamp(e["retrieved_at"][:8]) if e else None


# ------------------------------------------------------------------ helpers

def eur(text: str) -> float | None:
    """'24 030 000 000' / '22,162,000,000.00' / '3 300' -> float (as printed)."""
    t = str(text).replace("\xa0", " ").strip()
    if not t or t in ("-", "–"):
        return None
    if re.search(r"\d,\d{3},\d{3}", t) or re.search(r"\d,\d{3}\.\d+$", t):   # English thousands
        t = t.replace(",", "")
    else:                                           # French: spaces thousands, comma decimal
        t = t.replace(" ", "").replace(",", ".")
    t = re.sub(r"[^\d.\-]", "", t)
    try:
        return float(t) if t not in ("", "-", ".") else None
    except ValueError:
        return None


def pct(text: str) -> float | None:
    """'76,96 %' / '2,540 %' / '4.19%' -> float; the comma is always a decimal."""
    t = str(text).replace("%", "").replace("\xa0", " ").strip().replace(" ", "").replace(",", ".")
    t = re.sub(r"[^\d.\-]", "", t)
    try:
        return float(t) if t not in ("", "-", ".") else None
    except ValueError:
        return None


def date_text(text: str) -> pd.Timestamp | None:
    """'24 septembre 2026', '25 July 2027', '1er mars 2029', '07/09/2026'."""
    t = str(text).strip()
    m = DATE_NUM_RE.match(t)
    if m:
        return pd.Timestamp(year=int(m.group(3)), month=int(m.group(2)), day=int(m.group(1)))
    m = DATE_TEXT_RE.search(t)
    if not m:
        return None
    mon = MONTHS.get(m.group(2).lower().rstrip("."))
    if mon is None:
        return None
    return pd.Timestamp(year=int(m.group(3)), month=mon, day=int(m.group(1)))


def parse_libelle(name: str) -> dict:
    """'OAT€i 1.85% 25 July 2027' -> kind OAT€i, coupon 1.85, maturity 2027-07-25."""
    t = str(name).replace("\xa0", " ").strip()
    m = NAME_RE.match(t)
    if not m:
        return {"kind": None, "coupon_pct": None, "maturity_date": date_text(t), "is_green": False}
    kind = m.group("kind").replace("$", "")
    kind = {"OAT€I": "OAT€i", "OATI": "OATi", "BTANI": "BTANi", "BTAN€I": "BTAN€i"}.get(kind.upper(), kind)
    if kind.upper() == "OAT":
        kind = "OAT"
    return {"kind": kind, "coupon_pct": 0.0 if m.group("zero") else eur(m.group("coupon")),
            "maturity_date": date_text(m.group("rest")),
            "is_green": bool(m.group("green") or m.group("green2"))}


@lru_cache(maxsize=None)
def _soup(source_id: str, part: str):
    from bs4 import BeautifulSoup
    html = open(snap_path(source_id, part), "rb").read().decode("utf-8", "ignore")
    return BeautifulSoup(html, "html.parser")


def _rows(table) -> list[list[str]]:
    return [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]


# ------------------------------------------------------------------ encours

def encours(part: str) -> pd.DataFrame:
    """All lines of one encours page: isin, libellé, kind, coupon, maturity,
    outstanding_eur, group_year, group_total_eur, as_of."""
    soup = _soup(SOURCE_ENCOURS, part)
    as_of = retrieved_at(SOURCE_ENCOURS, part)
    out, seen = [], set()
    for table in soup.find_all("table"):
        year, total = None, None
        for r in _rows(table):
            if not r:
                continue
            if len(r) >= 2 and re.fullmatch(r"(Échéance|Maturity)\s+\d{4}", r[0]):
                year, total = int(r[0][-4:]), eur(r[-1])
                continue
            if len(r) == 1 and re.fullmatch(r"\d{4}", r[0]):
                year = int(r[0])
                continue
            if len(r) == 3 and ISIN_RE.match(r[0]) and r[0] not in seen:
                seen.add(r[0])
                lib = r[1]
                p = parse_libelle(lib) if part != "btf" else {"kind": "BTF", "coupon_pct": None,
                                                              "maturity_date": date_text(lib), "is_green": False}
                out.append({"isin": r[0], "libelle": lib, "kind": p["kind"], "coupon_pct": p["coupon_pct"],
                            "is_green": p["is_green"],
                            "maturity_date": p["maturity_date"], "outstanding_eur": eur(r[2]),
                            "group_year": year, "group_total_eur": total, "as_of": as_of, "part": part})
    df = pd.DataFrame(out)
    # the group header sometimes sits in a separate table before the lines:
    # fill the year from the maturity date where it was not captured
    if len(df):
        df["group_year"] = df["group_year"].where(df["group_year"].notna(),
                                                  df["maturity_date"].map(lambda d: d.year if pd.notna(d) else None))
    return df


def encours_all() -> pd.DataFrame:
    frames = [encours(p) for p in ENCOURS_PARTS if have(SOURCE_ENCOURS, p)]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    # a line listed on two pages (OATi also on the OAT page) keeps its first
    return df.drop_duplicates("isin", keep="first").reset_index(drop=True)


# ------------------------------------------------------------ adjudications

ATTR = {
    "date d'adjudication": "auction_date", "date de règlement": "settlement_date", "échéance": "maturity_date",
    "ligne": "line", "volume annoncé": "announced", "volume demandé": "bid_mn", "volume adjugé": "allotted_mn",
    "onc après adjudication": "onc_mn", "volume total émis": "total_issued_mn", "prix limite": "limit_price_pct",
    "taux limite": "limit_yield_pct", "pourcentage adjugé au prix limite": "pct_at_limit",
    "pourcentage adjugé au taux limite": "pct_at_limit", "taux de couverture": "cover",
    "prix moyen pondéré": "avg_price_pct", "taux moyen pondéré": "avg_yield_pct", "code isin": "isin",
}


def _attr(label: str) -> str | None:
    key = re.sub(r"[\*\s]+$", "", label.strip().lower())
    key = key.replace("’", "'")
    for k, v in ATTR.items():
        if key.startswith(k):
            return v
    return None


def auctions(source_id: str, part: str) -> pd.DataFrame:
    """Every line of every auction table on one page, one row per (auction
    date, ISIN): the attribute rows pivoted; volumes in EUR mn as printed."""
    soup = _soup(source_id, part)
    rows = []
    for table in soup.find_all("table"):
        rr = _rows(table)
        if len(rr) < 4 or not any(_attr(r[0]) == "isin" for r in rr if r):
            continue
        head = rr[0]
        family = "BTF" if any("BTF" in c for c in head) else "OAT"
        n = len(head) - 1
        cols = [{} for _ in range(n)]
        for r in rr[1:]:
            a = _attr(r[0]) if r else None
            if a is None:
                continue
            vals = r[1:]
            if len(vals) == 1 and n > 1:              # a merged cell (announced range)
                vals = vals * n
            for i in range(min(n, len(vals))):
                cols[i][a] = vals[i]
        for i, c in enumerate(cols):
            if not c.get("isin"):
                continue
            rows.append({
                "family": family, "line_name": head[i + 1], "isin": c["isin"].strip(),
                "auction_date": date_text(c.get("auction_date", "")),
                "settlement_date": date_text(c.get("settlement_date", "")),
                "maturity_date": date_text(c.get("maturity_date", "")),
                "announced": c.get("announced"), "bid_mn": eur(c.get("bid_mn", "")),
                "allotted_mn": eur(c.get("allotted_mn", "")), "onc_mn": eur(c.get("onc_mn", "")),
                "total_issued_mn": eur(c.get("total_issued_mn", "")),
                "avg_price_pct": pct(c.get("avg_price_pct", "")), "avg_yield_pct": pct(c.get("avg_yield_pct", "")),
                "limit_price_pct": pct(c.get("limit_price_pct", "")), "limit_yield_pct": pct(c.get("limit_yield_pct", "")),
                "cover": eur(c.get("cover", "")), "part": part,
            })
    return pd.DataFrame(rows)


def auctions_all() -> pd.DataFrame:
    """Every adjudications page in the store (the current month and any
    history pages saved as parts of FRA_AFT_ADJUDICATIONS)."""
    parts = sorted(p for (s, p) in latest_snapshots() if s == SOURCE_ADJUDICATIONS)
    frames = [auctions(SOURCE_ADJUDICATIONS, p) for p in parts]
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(["isin", "auction_date"], keep="first").reset_index(drop=True)


# -------------------------------------------------------------- indexation

#: The coefficient files' part names in the store (page part + file name).
COEF_PARTS = {
    "OATi": ("oati_page_file_2026-08_coef_oati-octobre26", "oati_page_file_coef_oati_histo_1998_2016"),
    "OAT€i": ("oati_page_file_2026-08_coef_oatei_octobre_2026", "oati_page_file_coef_oatEi_2001_2016"),
}
INDEX_PARTS = {"OATi": "oati_page_file_2026-08_IPC", "OAT€i": "oati_page_file_2026-08_IPCH"}


def coefficient_file(part: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One AFT coefficient workbook -> (terms, daily).

    Layout (sheet 1): column A the day, column B the daily reference index
    (``référence quotidienne d'inflation``), then one column per line with a
    header block in rows 2–8: kind (``OATi`` / ``OAT€i`` / ``BTANi``), coupon
    (as a fraction), maturity date, the date the index base refers to (the
    ``date de jouissance``), the base index; data from row 10. The current
    files run from the first line's issue (1998 / 2001) to the coming month;
    the ``histo`` files stop in 2016 and are on the earlier CPI base.
    ``terms`` has one row per column: kind, coupon_pct, maturity_date,
    base_date, base_index, column; ``daily`` is long: date, reference_index,
    column, coefficient.
    """
    x = pd.read_excel(snap_path(SOURCE_INDEXATION, part), header=None)
    terms = []
    for col in range(2, x.shape[1]):
        kind = x.iat[1, col]
        if not isinstance(kind, str) or not kind.strip():
            continue
        terms.append({"column": col, "kind": kind.strip().replace("OAT€I", "OAT€i"),
                      "coupon_pct": float(x.iat[2, col]) * 100.0 if pd.notna(x.iat[2, col]) else None,
                      "maturity_date": pd.Timestamp(x.iat[3, col]) if pd.notna(x.iat[3, col]) else None,
                      "base_date": pd.Timestamp(x.iat[5, col]) if pd.notna(x.iat[5, col]) else None,
                      "base_index": float(x.iat[7, col]) if pd.notna(x.iat[7, col]) else None, "part": part})
    terms = pd.DataFrame(terms)
    body = x.iloc[9:].copy()
    body = body[pd.to_datetime(body[0], errors="coerce").notna()]
    dates = pd.to_datetime(body[0])
    ref = pd.to_numeric(body[1], errors="coerce")
    frames = []
    for t in terms.itertuples(index=False):
        c = pd.to_numeric(body[t.column], errors="coerce")
        f = pd.DataFrame({"date": dates.values, "reference_index": ref.values, "column": t.column,
                          "coefficient": c.values})
        frames.append(f[f["coefficient"].notna()])
    daily = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["date", "reference_index", "column", "coefficient"])
    return terms, daily


def price_index(kind: str) -> pd.DataFrame:
    """The AFT's monthly reference price index (IPC ex-tobacco for OATi,
    euro-area HICP ex-tobacco for OAT€i), every published base side by
    side: month (the 15th), index (current base) and the older bases."""
    part = INDEX_PARTS[kind]
    x = pd.read_excel(snap_path(SOURCE_INDEXATION, part), header=None)
    header = [str(v).replace("\n", " ").strip() for v in x.iloc[1].tolist()]
    body = x.iloc[2:].copy()
    body = body[pd.to_datetime(body[0], errors="coerce").notna()]
    out = pd.DataFrame({"month": pd.to_datetime(body[0]).values})
    for i, h in enumerate(header[1:], start=1):
        out[h] = pd.to_numeric(body[i], errors="coerce").values
    return out[out.iloc[:, 1].notna()].reset_index(drop=True)


# ------------------------------------------------------- auction histories

HIST_MLT_PART = "historique_file_2026-08_hist_mlt"
HIST_BTF_PART = "historique_file_2026-08_hist_btf"
HIST_SYND_PART = "historique_file_1999-2026_historique_syndications"
HIST_MLT_2018_PART = "historique_file_26622_oat_btan_1999_2018"
HIST_BTF_2018_PART = "historique_file_26621_btf_1999_2018"


def _hist_frame(part: str) -> pd.DataFrame:
    x = pd.read_excel(snap_path(SOURCE_ADJUDICATIONS, part), header=None)
    head = [str(v).replace("\n", " ").strip().lower() for v in x.iloc[0].tolist()]
    body = x.iloc[1:].copy()
    body.columns = range(x.shape[1])
    return head, body


def _col(head: list[str], *needles: str) -> int | None:
    """Index of the first header containing every needle; the apostrophe in
    the AFT headers is typographic (’) in some files and plain (') in others."""
    alts = [tuple(n.replace("’", "'") for n in needles), tuple(n.replace("'", "’") for n in needles)]
    for i, h in enumerate(head):
        hh = h.replace("’", "'")
        if any(all(n.replace("’", "'") in hh for n in alt) for alt in alts):
            return i
    return None


def history_mlt(part: str = HIST_MLT_PART) -> pd.DataFrame:
    """The AFT medium/long-term auction history (``hist_mlt``, 1999→): one
    row per (auction, line): type (adju_LT / adju_MT / adju_I), auction and
    settlement dates, ISIN, line, bid, allotted, cover, ONC, total issued
    (EUR mn), weighted-average yield (fraction) and price (fraction of par),
    indexation coefficient at settlement for the linkers."""
    head, b = _hist_frame(part)
    c = {"kind": _col(head, "type"), "auction_date": _col(head, "date d'adjudication"),
         "settlement_date": _col(head, "règlement"), "isin": _col(head, "isin"), "line": _col(head, "ligne"),
         "bid_mn": _col(head, "soumission"), "allotted_mn": _col(head, "adjugé"), "cover": _col(head, "couverture"),
         "onc_mn": _col(head, "onc"), "total_issued_mn": _col(head, "total émis"), "avg_yield": _col(head, "taux moyen"),
         "avg_price": _col(head, "prix moyen"), "coefficient": _col(head, "coefficient")}
    out = pd.DataFrame({k: (b[v] if v is not None else None) for k, v in c.items()})
    out = out[pd.to_datetime(out["auction_date"], errors="coerce").notna() & out["isin"].astype(str).str.match(r"^FR")]
    for k in ("auction_date", "settlement_date"):
        out[k] = pd.to_datetime(out[k], errors="coerce")
    for k in ("bid_mn", "allotted_mn", "cover", "onc_mn", "total_issued_mn", "avg_yield", "avg_price", "coefficient"):
        out[k] = pd.to_numeric(out[k], errors="coerce")
    out["isin"] = out["isin"].astype(str).str.strip()
    out["line"] = out["line"].astype(str).str.replace("\xa0", " ").str.strip()
    out["part"] = part
    return out.reset_index(drop=True)


def history_btf(part: str = HIST_BTF_PART) -> pd.DataFrame:
    """The AFT BTF tender history (``hist_btf``, 1999→): auction and
    settlement dates, tenor in weeks, maturity date, ISIN (the 2018 archive
    has none), bid, allotted, cover, ONC, total issued (EUR mn), yield."""
    head, b = _hist_frame(part)
    c = {"auction_date": _col(head, "date d'adjudication"),
         "settlement_date": _col(head, "règlement"), "weeks": _col(head, "durée"), "maturity_date": _col(head, "échéance"),
         "isin": _col(head, "isin"), "bid_mn": _col(head, "soumission"), "allotted_mn": _col(head, "adjugé"),
         "cover": _col(head, "couverture"), "onc_mn": _col(head, "onc"), "total_issued_mn": _col(head, "total émis"),
         "avg_yield": _col(head, "taux moyen")}
    out = pd.DataFrame({k: (b[v] if v is not None else None) for k, v in c.items()})
    out = out[pd.to_datetime(out["auction_date"], errors="coerce").notna()]
    for k in ("auction_date", "settlement_date", "maturity_date"):
        out[k] = pd.to_datetime(out[k], errors="coerce")
    for k in ("weeks", "bid_mn", "allotted_mn", "cover", "onc_mn", "total_issued_mn", "avg_yield"):
        out[k] = pd.to_numeric(out[k], errors="coerce")
    if out["isin"].notna().any():
        out["isin"] = out["isin"].astype(str).str.strip()
    out["part"] = part
    return out.reset_index(drop=True)


def history_syndications(part: str = HIST_SYND_PART) -> pd.DataFrame:
    """The AFT syndication history (1999→): type (synd_LT / synd_I),
    settlement date, ISIN, line, volume issued (+) or bought back (−) in
    EUR mn, yield, price, coefficient."""
    head, b = _hist_frame(part)
    c = {"kind": _col(head, "type"), "settlement_date": _col(head, "règlement"), "isin": _col(head, "isin"),
         "line": _col(head, "ligne"), "volume_mn": _col(head, "volume"), "avg_yield": _col(head, "taux moyen"),
         "avg_price": _col(head, "prix moyen"), "coefficient": _col(head, "coefficient")}
    out = pd.DataFrame({k: (b[v] if v is not None else None) for k, v in c.items()})
    out = out[pd.to_datetime(out["settlement_date"], errors="coerce").notna() & out["isin"].astype(str).str.match(r"^FR")]
    out["settlement_date"] = pd.to_datetime(out["settlement_date"], errors="coerce")
    for k in ("volume_mn", "avg_yield", "avg_price", "coefficient"):
        out[k] = pd.to_numeric(out[k], errors="coerce")
    out["isin"] = out["isin"].astype(str).str.strip()
    out["line"] = out["line"].astype(str).str.replace("\xa0", " ").str.strip()
    out["part"] = part
    return out.reset_index(drop=True)
