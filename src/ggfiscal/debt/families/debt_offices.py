"""Family 'debt_offices' — the three debt management offices (DEBT_KICKOFF.md
§13: UK_DMO_GILTS, UK_DMO_BILLS, FRA_AFT_*, DEU_FINANZAGENTUR).

All three hosts are denied by the egress policy (OQ-8). The pull definitions
are nevertheless complete so that `ggfiscal debt fetch` records the denial
per part in the failure list (and `debt_source_verification.md` names what
is missing), and so that the same definitions run unchanged the day the
hosts are allowlisted. Files hand-retrieved meanwhile enter the store via
`ggfiscal ingest-file --source-id <id> --part <part>` using exactly these
part names, so the readers do not care which route the bytes took.

Part naming is stable and documented here because the committee may be
typing it by hand:
  UK_DMO_GILTS/{D1A,D1C,D1D,D2.1E,D2.1A,D2.1PROF7,D2.1PROF9,D10A,D4L,D8B,
                D5I,D10C,D9C}            one report each (Excel export)
  UK_DMO_GILTS/D1A_xml                   the XML form of D1A (schema-stable)
  UK_DMO_GILTS/D1A_cob_{YYYYMMDD}        month-end D1A snapshots (see cob_pulls)
  UK_DMO_GILTS/{yldeqns,igcalc}          convention PDFs
  UK_DMO_BILLS/{D2.2A,D2.2D,D2.2E,D2.2G}
  FRA_AFT_ENCOURS/{oat,btf,oatei}        the encours détaillé pages (HTML; the
                                         xlsx behind them: part suffix _xlsx)
  FRA_AFT_ADJUDICATIONS/{hist_btf,hist_oat,archives}
  FRA_AFT_INDEXATION/{oati_current,oati_hist_1998,oatei_current,oatei_hist_2005}
  FRA_AFT_FINANCEMENT/{rapports,plf_{year}}
  DEU_FINANZAGENTUR/{downloadcenter,einzelaufstellung_seit_1995,
                     umlaufende_monatsultimo,emissionshistorie,
                     emissionsergebnisse_aktuell,index_ratios_2015,
                     index_ratios_2025}
"""

from __future__ import annotations

import datetime as dt

from ggfiscal.ingest.endpoints import BROWSER_HEADERS, Pull

DMO = "https://www.dmo.gov.uk"
AFT = "https://www.aft.gouv.fr"
FA = "https://www.deutsche-finanzagentur.de"

DMO_GILT_REPORTS = ("D1A", "D1C", "D1D", "D2.1E", "D2.1A", "D2.1PROF7",
                    "D2.1PROF9", "D10A", "D4L", "D8B", "D5I", "D10C", "D9C")
DMO_BILL_REPORTS = ("D2.2A", "D2.2D", "D2.2E", "D2.2G")


# Presentation type each report is exported in. Verified live 2026-09-10
# through the browser session: the export handler serves each report in
# exactly one of xml / xls, and answers every other pair with the 35-byte
# stub "Unable to fulfil the report request" (STUB_MARKERS). The xls of
# D10A is an HTML table under an .xls name (sniffed at store time).
DMO_FORMATS = {
    "D1A": "xml", "D10C": "xml", "D4L": "xml", "D2.1E": "xml", "D2.2D": "xml",
    "D1C": "xls", "D2.1A": "xls", "D2.1PROF7": "xls", "D2.1PROF9": "xls", "D10A": "xls",
    "D8B": "xls", "D2.2E": "xls", "D2.2G": "xls",
}


def dmo_export_url(code: str, fmt: str | None = None) -> str:
    """The URL behind the DMO pages' export buttons. `ExportReport?reportCode=`
    alone answers "Report X is not available in this presentation type":
    the presentation type is `exportFormatValue`; see DMO_FORMATS for the
    one each report accepts. COBDate blank = latest close of business."""
    fmt = fmt or DMO_FORMATS.get(code, "xls")
    return (f"{DMO}/umbraco/surface/DataExport/GetDataExport?reportCode={code}"
            f"&exportFormatValue={fmt}&parameters=&COBDate=")


def dmo_xml_url(code: str) -> str:
    return f"{DMO}/data/XmlDataReport?reportCode={code}"


def dmo_cob_url(code: str, cob: dt.date) -> str:
    return (f"{DMO}/umbraco/surface/DataExport/GetDataExport?reportCode={code}"
            f"&exportFormatValue=xls&parameters=&COBDate={cob:%d}%2F{cob:%m}%2F{cob:%Y}")


def month_ends(start: dt.date, end: dt.date) -> list[dt.date]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append(dt.date(ny, nm, 1) - dt.timedelta(days=1))
        y, m = ny, nm
    return out


def cob_pulls(start: dt.date = dt.date(1998, 4, 30),
              end: dt.date | None = None) -> list[Pull]:
    """Month-end D1A snapshots — the positions panel (§5.2). Run separately
    (`--family debt_offices` pulls only the current reports). Verified
    2026-09-10: the export endpoint ignores COBDate in xml and returns the
    stub in xls, so these pulls fail until the page's own export link (which
    carries the date in `parameters=`) is captured; the positions panel is
    meanwhile rebuilt from the flows (D2.1E, D1C, D2.1PROF7)."""
    end = end or dt.date.today()
    return [Pull("UK_DMO_GILTS", f"D1A_cob_{d:%Y%m%d}", dmo_cob_url("D1A", d),
                 headers=BROWSER_HEADERS) for d in month_ends(start, end)]


CHALLENGE_MARKERS = ("ShieldSquare Captcha", "<title>Just a moment...</title>", "perfdrive.com/aperture")
# Short text bodies the DMO export handler returns instead of a file
STUB_MARKERS = ("Unable to fulfil the report request", "is not available in this presentation type")


BROWSER_HOSTS = ("www.dmo.gov.uk", "www.aft.gouv.fr")


def get(pull: Pull):
    """Plain GET first; the two bot-challenged hosts (DMO: Radware
    ShieldSquare; AFT: Cloudflare) go through the committee-authorised
    browser session (debt/browser.py) when the plain path returns a
    challenge page or a 403. A challenge page is never stored as data."""
    from urllib.parse import urlsplit

    from ggfiscal.ingest.fetch import FetchError, _get
    host = urlsplit(pull.url).netloc
    if host not in BROWSER_HOSTS:
        resp = _get(pull.url, pull.accept, pull.headers)
        return resp.content, resp.headers.get("content-type", ""), resp.status_code
    try:
        resp = _get(pull.url, pull.accept, pull.headers)
        ctype = resp.headers.get("content-type", "")
        if not ("text/html" in ctype and any(m in resp.content[:20000].decode("utf-8", "ignore")
                                            for m in CHALLENGE_MARKERS)):
            return resp.content, ctype, resp.status_code
    except FetchError:
        pass
    from ggfiscal.debt import browser
    body, ctype, status = browser.fetch(pull.url)
    if status >= 400:
        raise FetchError(f"HTTP {status} via browser for {pull.url}")
    if is_stub(body):
        raise FetchError(f"server stub instead of a file ({body.decode('utf-8', 'ignore').strip()[:60]!r}) for {pull.url}")
    return body, sniff_type(body, ctype), status


def sniff_type(body: bytes, declared: str) -> str:
    """The DMO labels every export with the type of the format requested
    (D10A's "xls" is an HTML table; an error is XML). Trust the bytes."""
    head = body.lstrip()[:8]
    if head[:2] == b"PK":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if body[:8] == bytes.fromhex("d0cf11e0a1b11ae1"):
        return "application/vnd.ms-excel"
    if head[:5] == b"%PDF-":
        return "application/pdf"
    if head[:5] == b"<?xml" or head[:5] == b"<Data" or head[:6] == b"<Error":
        return "application/xml"
    if head[:1] == b"<":
        return "text/html"
    return declared


def is_stub(body: bytes) -> bool:
    """The DMO export handler answers some (report, format) pairs with a
    35-byte sentence and a 200; that is a failed pull, never a snapshot."""
    return len(body) < 400 and any(m in body.decode("utf-8", "ignore") for m in STUB_MARKERS)


# Parts that are hand-downloaded from links the pages carry (versioned file
# names): (source_id, part, landing URL the file was taken from).
HAND_PARTS = [
    ("FRA_AFT_ENCOURS", "oat_xlsx", f"{AFT}/fr/encours-detaille-oat"),
    ("FRA_AFT_ENCOURS", "btf_xlsx", f"{AFT}/fr/encours-detaille-btf"),
    ("FRA_AFT_ENCOURS", "oatei_xlsx", f"{AFT}/en/encours-detaille-oatei"),
    ("FRA_AFT_ADJUDICATIONS", "hist_oat", f"{AFT}/fr/dernieres-adjudications"),
    ("FRA_AFT_ADJUDICATIONS", "hist_btf", f"{AFT}/fr/dernieres-adjudications"),
    ("FRA_AFT_ADJUDICATIONS", "archives_oat", f"{AFT}/fr/dernieres-adjudications-archives"),
    ("FRA_AFT_ADJUDICATIONS", "archives_btf", f"{AFT}/fr/dernieres-adjudications-archives"),
    ("FRA_AFT_INDEXATION", "oati_current", f"{AFT}/fr/oati-principaux-chiffres"),
    ("FRA_AFT_INDEXATION", "oati_hist_1998", f"{AFT}/fr/oati-principaux-chiffres"),
    ("FRA_AFT_INDEXATION", "oatei_current", f"{AFT}/en/oateuroi-key-figures"),
    ("FRA_AFT_INDEXATION", "oatei_hist_2005", f"{AFT}/en/oateuroi-key-figures"),
    ("FRA_AFT_FINANCEMENT", "rapport_2024", f"{AFT}/fr/rapports-activite"),
    ("FRA_AFT_FINANCEMENT", "rapport_2023", f"{AFT}/fr/rapports-activite"),
    ("UK_DMO_GILTS", "gross_net_issuance_annual", f"{DMO}/data/gilt-market/gross-and-net-issuance-data/"),
    ("UK_DMO_GILTS", "cash_sales_by_type_and_maturity", f"{DMO}/data/gilt-market/gross-and-net-issuance-data/"),
]


def pulls() -> list[Pull]:
    out: list[Pull] = []
    for code in DMO_GILT_REPORTS:
        out.append(Pull("UK_DMO_GILTS", code, dmo_export_url(code), headers=BROWSER_HEADERS))
    out.append(Pull("UK_DMO_GILTS", "D1A_xml", dmo_xml_url("D1A"), headers=BROWSER_HEADERS))
    out.append(Pull("UK_DMO_GILTS", "yldeqns", f"{DMO}/media/1sljygul/yldeqns.pdf", headers=BROWSER_HEADERS))
    out.append(Pull("UK_DMO_GILTS", "igcalc", f"{DMO}/media/0ltegugd/igcalc.pdf", headers=BROWSER_HEADERS))
    for code in DMO_BILL_REPORTS:
        out.append(Pull("UK_DMO_BILLS", code, dmo_export_url(code), headers=BROWSER_HEADERS))

    out += [
        Pull("FRA_AFT_ENCOURS", "oat", f"{AFT}/fr/encours-detaille-oat", headers=BROWSER_HEADERS),
        Pull("FRA_AFT_ENCOURS", "btf", f"{AFT}/fr/encours-detaille-btf", headers=BROWSER_HEADERS),
        Pull("FRA_AFT_ENCOURS", "oatei", f"{AFT}/en/encours-detaille-oatei", headers=BROWSER_HEADERS),
        Pull("FRA_AFT_ADJUDICATIONS", "dernieres", f"{AFT}/fr/dernieres-adjudications", headers=BROWSER_HEADERS),
        Pull("FRA_AFT_ADJUDICATIONS", "archives", f"{AFT}/fr/dernieres-adjudications-archives", headers=BROWSER_HEADERS),
        Pull("FRA_AFT_INDEXATION", "oati_page", f"{AFT}/fr/oati-principaux-chiffres", headers=BROWSER_HEADERS),
        Pull("FRA_AFT_INDEXATION", "oatei_page", f"{AFT}/en/oateuroi-key-figures", headers=BROWSER_HEADERS),
        Pull("FRA_AFT_FINANCEMENT", "rapports", f"{AFT}/fr/rapports-activite", headers=BROWSER_HEADERS),
        Pull("FRA_AFT_FINANCEMENT", "bulletins_index", f"{AFT}/fr/bulletins-mensuels", headers=BROWSER_HEADERS),
    ]
    # The xlsx links behind the AFT pages are versioned; they are resolved
    # from the page HTML by the reader once the pages are in the store.

    fa_files = {
        # resolved live 2026-09-09 from /downloadcenter and the ILB / Umlauf / Emissionen pages
        "einzelaufstellung_seit_1995": "berichtswesen/einzelaufstellung_jahre_dt.xlsx",
        "umlaufende_monatsultimo": "berichtswesen/einzelaufstellung_dt.xlsx",
        "schuldenbericht": "berichtswesen/schuldenbericht_dt.xlsx",
        "emissionshistorie": "auktionen/emissionshistorie_dt.xlsx",
        "emissionsergebnisse_aktuell": "auktionen/emissionsergebnisse_aktuell_dt.xlsx",
        "index_ratios_2005": "indexverhaeltnis/archiv_referenzindex_bj2005_dt.xlsx",
        "index_ratios_2015": "indexverhaeltnis/archiv_referenzindex_bj2015_dt.xlsx",
        "index_ratios_2025": "indexverhaeltnis/archiv_referenzindex_bj2025_dt.xlsx",
    }
    for part, rel in fa_files.items():
        out.append(Pull("DEU_FINANZAGENTUR", part,
                        f"{FA}/fileadmin/user_upload/Institutionelle-investoren/{rel}", headers=BROWSER_HEADERS))
    for year in range(2004, 2013):      # editions before the BMF-hosted 2013- set
        out.append(Pull("DEU_FINANZAGENTUR", f"kreditaufnahmebericht_{year}",
                        f"{FA}/fileadmin/user_upload/Finanzagentur/pdf/kreditaufnahmeberichte/Kreditaufnahmebericht_{year}.pdf",
                        headers=BROWSER_HEADERS))
    out += [
        Pull("DEU_FINANZAGENTUR", "downloadcenter", f"{FA}/downloadcenter", headers=BROWSER_HEADERS),
        Pull("DEU_FINANZAGENTUR", "umlaufende_page",
             f"{FA}/bundeswertpapiere/handel/umlaufende-bundeswertpapiere", headers=BROWSER_HEADERS),
        Pull("DEU_FINANZAGENTUR", "ilb_page",
             f"{FA}/bundeswertpapiere/bundeswertpapierarten/inflationsindexierte-bundeswertpapiere",
             headers=BROWSER_HEADERS),
    ]
    return out
