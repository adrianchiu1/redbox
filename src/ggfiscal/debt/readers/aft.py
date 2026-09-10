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
    r"^(?P<green>GREEN\s+)?(?P<kind>OAT€I|OAT€i|OATi|OAT\$?i|OAT|BTAN|BTF)\s*(?P<green2>verte\s+|VERTE\s+)?"
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
    kind = {"OAT€I": "OAT€i", "OATI": "OATi"}.get(kind.upper() if kind.upper() in ("OAT€I", "OATI") else kind, kind)
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
