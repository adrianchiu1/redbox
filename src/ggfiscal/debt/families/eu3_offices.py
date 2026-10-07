"""Debt sources of the Stage ED countries (EU3_KICKOFF.md §4 ED0, DE1/DE4):
the Italian Treasury (MEF Dipartimento del Tesoro), the Belgian Debt Agency
and the Banco de España. Every host here answered 200 to this
environment on 2026-10-07; `www.tesoro.es` (Spain's Treasury) fails TLS
verification and is replaced by the Banco de España (DE4).

* ``ITA_MEF_COMPOSIZIONE`` — "Composizione dei Titoli di Stato in
  circolazione" (CSV, EUR mn by instrument class, at a month end). The page
  lists the latest editions only; each is snapshotted as its own part
  (``composizione_{yyyy}_{mm}``), so year-end stocks accumulate from the
  December editions onward as the store grows.
* ``ITA_MEF_SCADENZE`` — maturities by year and class (CSV), same cadence.
* ``BEL_BDA`` — the OLO lines with net outstanding per ISIN (HTML table,
  the agency's own "Lines and outstanding at" page), the maturity schedule
  and the debt indicators (xlsx).
* ``ESP_BDE_BE`` — the Boletín Estadístico bulk zip (``be.zip``); the
  reader takes chapter 11 (Administraciones Públicas): monthly PDE debt of
  the Estado and of the AAPP by instrument (thousand EUR).

The listing pages are read at pull time so that a new month's file is a
new part, never an overwrite of an older one.
"""

from __future__ import annotations

import re

from ggfiscal.ingest.endpoints import BROWSER_HEADERS, Pull

MEF_BASE = "https://www.dt.mef.gov.it"
MEF_STAT = f"{MEF_BASE}/it/debito_pubblico/dati_statistici"
BDA_BASE = "https://www.debtagency.be"
BDE_ZIP = "https://www.bde.es/webbe/es/estadisticas/compartido/datos/zip/be.zip"

_MONTHS_IT = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
              "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11,
              "dicembre": 12}
_DATE_IT = re.compile(r"al-(\d{1,2})-([a-z]+)-(\d{4})\.csv$")


def _mef_csv_links(page: str) -> list[str]:
    """The CSV editions a MEF statistics page links (absolute URLs)."""
    import requests

    r = requests.get(f"{MEF_STAT}/{page}/", headers=dict(BROWSER_HEADERS), timeout=60)
    r.raise_for_status()
    hrefs = re.findall(r'href="([^"]+\.csv)"', r.text)
    return sorted({h if h.startswith("http") else MEF_BASE + h for h in hrefs})


def mef_part(prefix: str, url: str) -> str | None:
    """`{prefix}_{yyyy}_{mm}` from a MEF file name ending `al-31-agosto-2026.csv`."""
    m = _DATE_IT.search(url)
    if not m or m.group(2) not in _MONTHS_IT:
        return None
    return f"{prefix}_{m.group(3)}_{_MONTHS_IT[m.group(2)]:02d}"


def pulls() -> list[Pull]:
    out: list[Pull] = []
    for source_id, page, prefix in (
        ("ITA_MEF_COMPOSIZIONE", "composizione_titoli_stato", "composizione"),
        ("ITA_MEF_SCADENZE", "scadenze_titoli_suddivise_anno", "scadenze"),
    ):
        try:
            links = _mef_csv_links(page)
        except Exception:          # listing unreachable: the fetch records nothing new
            links = []
        for url in links:
            part = mef_part(prefix, url)
            if part:
                out.append(Pull(source_id, part, url, headers=BROWSER_HEADERS))
    out += [
        Pull("BEL_BDA", "olo_outstanding_html", f"{BDA_BASE}/en/datafederalstateoutstanding",
             headers=BROWSER_HEADERS),
        Pull("BEL_BDA", "maturity_schedule_xlsx",
             f"{BDA_BASE}/sites/default/files/content/download/Accesibility_excel/data_maturityschedule.xlsx",
             headers=BROWSER_HEADERS),
        Pull("BEL_BDA", "indicators_xlsx",
             f"{BDA_BASE}/sites/default/files/content/download/Accesibility_excel/data_indicators.xlsx",
             headers=BROWSER_HEADERS),
        Pull("BEL_BDA", "implicit_yield_xlsx",
             f"{BDA_BASE}/sites/default/files/content/download/Accesibility_excel/data_implicit_yield.xlsx",
             headers=BROWSER_HEADERS),
        Pull("ESP_BDE_BE", "be_zip", BDE_ZIP, headers=BROWSER_HEADERS),
    ]
    return out
