"""Family 'boe' — pull definitions (DEBT_KICKOFF.md §13).

Three BoE sources:

- `BOE_APF` — Asset Purchase Facility gilt operations (purchase results by
  ISIN, sales time series, the maturity-profile workbook) plus the two
  financial-stability (non-APF) purchase/sale time series that live under
  `other-market-operations/` and the mislabelled "finanical-stability" gilt
  sales file (the typo is in BoE's own filename, not ours). All six are
  static `.xlsx` files under bankofengland.co.uk/-/media/... — a plain GET
  with a browser User-Agent is enough (BoE's media CDN 403s on a bare
  `requests` default UA).
- `BOE_YIELD_CURVES` — the government liability curve archives: nominal,
  real, inflation and OIS, each as a daily-since-inception zip and a
  month-end zip, plus the small `latest` zip. Same plain-GET path; the
  files are tens of MB so the shared `ingest.fetch` timeout (300s) applies.
- `BOE_IADB` — the Statistical Interactive Database CSV/HTML export for two
  series (IUDSOIA = SONIA, IUDBEDR = Bank Rate), each pulled from its own
  true start date (the endpoint returns an HTML error page, still HTTP 200,
  if `Datefrom` precedes the series' first observation — DEBT_KICKOFF.md
  §13), plus the `baserate.xls` "Bank Rate history since 1694" workbook.

No family `get()` override: the default plain GET in `ingest.fetch._get`
with `BROWSER_HEADERS` succeeds for every part here (verified live
2026-09-09). The IADB HTML-vs-CSV ambiguity is a *parsing* concern, handled
in `debt.readers.boe.iadb_series`, not a fetch-layer one — either shape
comes back as a normal 200 response.
"""

from __future__ import annotations

from ggfiscal.ingest.endpoints import BROWSER_HEADERS, Pull

APF_BASE = "https://www.bankofengland.co.uk/-/media/boe/files/markets"
YC_BASE = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves"
BASERATE_URL = ("https://www.bankofengland.co.uk/-/media/boe/files/monetary-policy/"
               "baserate.xls")
IADB_BASE = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"

# (part, url) — APF and the two financial-stability side series.
APF_FILES = (
    ("gilt_purchases",
     f"{APF_BASE}/asset-purchase-facility/gilt-purchase-operational-results.xlsx"),
    ("gilt_sales",
     f"{APF_BASE}/asset-purchase-facility/gilt-sales-time-series.xlsx"),
    ("maturity_profile",
     f"{APF_BASE}/asset-purchase-facility/table-for-website.xlsx"),
    ("fs_long_dated_purchases",
     f"{APF_BASE}/other-market-operations/"
     "long-dated-uk-government-bond-purchase-time-series.xlsx"),
    ("fs_index_linked_purchases",
     f"{APF_BASE}/other-market-operations/index-linked-gilt-purchase-results.xlsx"),
    # BoE's own filename typo ("finanical") — recorded verbatim, see report.
    ("fs_gilt_sales",
     f"{APF_BASE}/asset-purchase-facility/"
     "finanical-stability-gilt-sales-time-series.xlsx"),
)

# (part, filename) under YC_BASE.
YC_FILES = (
    ("nominal_daily", "glcnominalddata.zip"),
    ("real_daily", "glcrealddata.zip"),
    ("inflation_daily", "glcinflationddata.zip"),
    ("ois_daily", "oisddata.zip"),
    ("nominal_monthend", "glcnominalmonthedata.zip"),
    ("real_monthend", "glcrealmonthedata.zip"),
    ("inflation_monthend", "glcinflationmonthedata.zip"),
    ("ois_monthend", "oismonthedata.zip"),
    ("latest", "latest-yield-curve-data.zip"),
)

# IADB series code -> first observation date (DD/Mon/YYYY, as the endpoint expects).
# A Datefrom earlier than this returns an HTML error page (still HTTP 200).
IADB_SERIES_START = {
    "IUDSOIA": "01/Jan/1997",   # SONIA; first obs 1997-01-02
    "IUDBEDR": "01/Jan/1975",   # Bank Rate; first obs 1975-01-02
}


def _iadb_url(code: str, datefrom: str) -> str:
    return (f"{IADB_BASE}?csv.x=yes&Datefrom={datefrom}&Dateto=now"
            f"&SeriesCodes={code}&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")


def pulls() -> list[Pull]:
    out: list[Pull] = []
    for part, url in APF_FILES:
        out.append(Pull("BOE_APF", part, url, headers=BROWSER_HEADERS))
    for part, filename in YC_FILES:
        out.append(Pull("BOE_YIELD_CURVES", part, f"{YC_BASE}/{filename}",
                        headers=BROWSER_HEADERS))
    for code, datefrom in IADB_SERIES_START.items():
        out.append(Pull("BOE_IADB", code, _iadb_url(code, datefrom),
                        headers=BROWSER_HEADERS))
    out.append(Pull("BOE_IADB", "baserate_xls", BASERATE_URL, headers=BROWSER_HEADERS))
    return out
