"""Family 'bmf' — Bundesministerium der Finanzen (DEBT_KICKOFF.md §13, §6.3 DEU).

Four registered sources:

* ``BMF_DATENPORTAL`` — the open-data "Kreditbestand, Bruttokreditaufnahme,
  Tilgungen und Zinsen des Bundes" workbook (one xlsx, four sheets, monthly
  from 1995-12 / 1996-01, whole euro) plus the three sibling CSV time series
  (UTF-16LE, tab-separated, wide).
* ``BMF_KREDITAUFNAHMEBERICHT`` — the annual Kreditaufnahmebericht des Bundes
  (PDF), one part per edition; annex 4.5 (Verzinsung incl. Epl. 32 Kap. 3205)
  and annex 4.10 (Abrechnung des Kreditfinanzierungsplans) are the §6.3 step-A
  intermediates for DEU.
* ``BMF_MONATSBERICHT`` — the monthly article "Kreditaufnahme des Bundes und
  seiner Sondervermögen". Its section number moves between issues (3.5 in
  2025-11, 4.5 in 2021-02), so the series cannot be enumerated from a URL
  pattern: only the one verified article is registered here, and a later stage
  crawls the issue index (:func:`monatsbericht_issue_index_url`) for the rest.
* ``BMF_HAUSHALTSRECHNUNG`` — Haushaltsrechnung des Bundes, Band 2 (Epl. 32
  outturn). The index page is pulled; the per-year Band-2 PDFs live behind
  ``__blob=publicationFile`` links whose ``v=`` differs by year, so they are
  resolved from the index page at pull time.

**Bot manager.** www.bundesfinanzministerium.de sits behind a Radware bot
manager: roughly every other request is answered with a redirect to
``validate.perfdrive.com``, which the egress proxy refuses (CONNECT 403). The
family therefore supplies its own :func:`get`, which the debt fetch layer
prefers over ``ingest.fetch._get``: a fresh cookie jar per attempt, full
browser headers with a German Accept-Language and a bundesfinanzministerium.de
Referer, redirects followed manually and only within the host, and up to
``ATTEMPTS`` tries with a 1–3 s randomised backoff. A run in which *every*
attempt was a proxy CONNECT denial is reported as :class:`FetchBlocked`;
anything else as :class:`FetchError`.
"""

from __future__ import annotations

import random
import re
import time
from urllib.parse import urljoin, urlsplit

import requests

from ggfiscal.ingest.endpoints import Pull
from ggfiscal.ingest.fetch import FetchBlocked, FetchError

BMF_BASE = "https://www.bundesfinanzministerium.de"
DATENPORTAL_BASE = (f"{BMF_BASE}/Datenportal/Daten/offene-daten/"
                    "haushalt-oeffentliche-finanzen")

TIMEOUT = 180
ATTEMPTS = 8
MAX_REDIRECTS = 6

#: Full browser header set. The Radware manager 403s / bounces bare clients and
#: is markedly more tolerant of a German-locale browser arriving from the site's
#: own home page. ``Accept-Encoding`` deliberately omits ``br``: requests only
#: decodes brotli when the optional dependency is present.
BMF_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Referer": f"{BMF_BASE}/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ---------------------------------------------------------------- BMF_DATENPORTAL

#: Datenportal parts: part -> (path below DATENPORTAL_BASE, landing page).
#: ``v=`` is the publisher's file version; when the recorded one 404s the
#: landing page is scraped for the current link (see :func:`_resolve`).
DATENPORTAL_FILES = {
    "kredit_brutto_tilgung_zinsen_xlsx": (
        "Zeitreihe-Kredit-Bruttokredit-Tilgung-Zinsen/datensaetze/"
        "xlsx-Kreditbestand-Bruttokredit-Tilgung-Zinsen.xlsx?__blob=publicationFile&v=36",
        "Zeitreihe-Kredit-Bruttokredit-Tilgung-Zinsen/"
        "Kreditbestand-Bruttokredit-Tilgung-Zinsen.html"),
    "bruttokreditaufnahme_csv": (
        "Zeitreihe-Bruttokreditaufnahme-des-Bundes/datensaetze/"
        "csv_ZR-Bruttokreditaufnahme-des-Bundes.csv?__blob=publicationFile&v=31",
        "Zeitreihe-Bruttokreditaufnahme-des-Bundes/"
        "Bruttokreditaufnahme-des-Bundes.html"),
    "tilgungen_csv": (
        "Zeitreihe-Tilgung-des-Bundeshaushalts-und-Sondervermoegen-ab-1996/datensaetze/"
        "CSV_ZR-Tilgung-des-Bundeshaushalts-und-Sondervermoegen.csv?__blob=publicationFile&v=30",
        "Zeitreihe-Tilgung-des-Bundeshaushalts-und-Sondervermoegen-ab-1996/"
        "Tilgung-des-Bundeshaushalts-und-Sondervermoegen.html"),
    "kreditbestand_csv": (
        "Zeitreihe-Kreditbestand-seit-1996/datensaetze/"
        "csv-Kreditbestand.csv?__blob=publicationFile&v=32",
        "Zeitreihe-Kreditbestand-seit-1996/Kreditbestand-seit-1996.html"),
}

#: Kreditaufnahmebericht editions: year -> (directory below /Content/DE/Downloads,
#: ``v=``). Editions up to 2024 sit in the Oeffentliche-Finanzen archive; the
#: current one is published in the Broschüren/Bestellservice tree and moves
#: there each spring (verified against the site search, 2026-09-09). §13 asks
#: for 2013-2025; 2010-2012 resolve on the same archive pattern with ``v=1``.
KAB_DIRS = {
    "archive": "Oeffentliche-Finanzen/Kreditaufnahmeberichte",
    "current": "Broschueren_Bestellservice",
}
KAB_EDITIONS = {
    2025: ("current", 2),
    2024: ("archive", 5), 2023: ("archive", 5), 2022: ("archive", 3),
    2021: ("archive", 1), 2020: ("archive", 1), 2019: ("archive", 1),
    2018: ("archive", 1), 2017: ("archive", 1), 2016: ("archive", 1),
    2015: ("archive", 1), 2014: ("archive", 1), 2013: ("archive", 1),
}

HAUSHALTSRECHNUNG_INDEX = (
    f"{BMF_BASE}/Web/DE/Themen/Oeffentliche_Finanzen/Bundeshaushalt/"
    "Haushalts_und_Vermoegensrechnungen_des_Bundes/"
    "haushalts_vermoegensrechnungen_des_bundes.html")

#: Haushaltsrechnung des Bundes, Band 2 (Epl. 32 / Kap. 3205 outturn). From
#: 2014 the report is split into Band 1 and Band 2; 2025 is only linked from
#: its Broschüren landing page (:data:`HAUSHALTSRECHNUNG_2025_LANDING`).
HAUSHALTSRECHNUNG_DIR = (f"{BMF_BASE}/Content/DE/Downloads/Oeffentliche-Finanzen/"
                         "Haushalts-und-Vermoegensrechnungen")
HAUSHALTSRECHNUNG_2025_LANDING = (
    f"{BMF_BASE}/Content/DE/Downloads/Broschueren_Bestellservice/"
    "haushaltsrechnung-des-bundes-2025.html")
HR_BAND2_VERSIONS = {2025: 6, 2024: 4, 2023: 5}

#: Verified Monatsbericht article (November 2025 issue). The issue index is
#: ``/Monatsberichte/Ausgabe/{yyyy}/{mm}/monatsbericht-{mm}-{yyyy}.html``.
MONATSBERICHT_2025_11 = (
    f"{BMF_BASE}/Monatsberichte/Ausgabe/2025/11/Inhalte/"
    "Kapitel-3-Wirtschafts-und-Finanzlage/3-5-kreditaufnahme-des-bundes.html")


def datenportal_url(part: str) -> str:
    return f"{DATENPORTAL_BASE}/{DATENPORTAL_FILES[part][0]}"


def datenportal_landing_url(part: str) -> str:
    return f"{DATENPORTAL_BASE}/{DATENPORTAL_FILES[part][1]}"


def kreditaufnahmebericht_url(year: int, version: int | None = None) -> str:
    where, v = KAB_EDITIONS.get(year, ("archive", 1))
    return (f"{BMF_BASE}/Content/DE/Downloads/{KAB_DIRS[where]}/"
            f"kreditaufnahmebericht-{year}.pdf?__blob=publicationFile"
            f"&v={v if version is None else version}")


def kreditaufnahmebericht_landing_url(year: int) -> str:
    where = KAB_EDITIONS.get(year, ("archive", 1))[0]
    return (f"{BMF_BASE}/Content/DE/Downloads/{KAB_DIRS[where]}/"
            f"kreditaufnahmebericht-{year}.html")


def haushaltsrechnung_band2_url(year: int) -> str:
    return (f"{HAUSHALTSRECHNUNG_DIR}/haushaltsrechnung-{year}-band2.pdf"
            f"?__blob=publicationFile&v={HR_BAND2_VERSIONS.get(year, 1)}")


def monatsbericht_issue_index_url(year: int, month: int) -> str:
    return (f"{BMF_BASE}/Monatsberichte/Ausgabe/{year}/{month:02d}/"
            f"monatsbericht-{month:02d}-{year}.html")


def pulls() -> list[Pull]:
    """Every BMF pull (DEBT_KICKOFF.md §13).

    BMF_MONATSBERICHT carries only the one verified article: the section number
    of "Kreditaufnahme des Bundes und seiner Sondervermögen" moves between
    issues (3.5 in 2025-11, 3.4 and 3.6 in other years), so a crawl of the issue
    index — not a URL pattern — is the way to enumerate it, and that crawl is
    left to a later stage rather than guessed at here.
    """
    out = [Pull("BMF_DATENPORTAL", part, datenportal_url(part))
           for part in DATENPORTAL_FILES]
    out += [Pull("BMF_KREDITAUFNAHMEBERICHT", str(year),
                 kreditaufnahmebericht_url(year))
            for year in sorted(KAB_EDITIONS, reverse=True)]
    out.append(Pull("BMF_MONATSBERICHT", "2025-11_kreditaufnahme",
                    MONATSBERICHT_2025_11))
    out.append(Pull("BMF_HAUSHALTSRECHNUNG", "index", HAUSHALTSRECHNUNG_INDEX))
    out.append(Pull("BMF_HAUSHALTSRECHNUNG", "2025_band2",
                    haushaltsrechnung_band2_url(2025)))
    return out


# ------------------------------------------------------------------- HTTP client

class _Denied(Exception):
    """One attempt ended in a proxy CONNECT denial."""


def _attempt(url: str) -> requests.Response:
    """One attempt: fresh session, manual same-host redirect following."""
    session = requests.Session()
    try:
        current = url
        for _ in range(MAX_REDIRECTS):
            resp = session.get(current, headers=BMF_HEADERS, timeout=TIMEOUT,
                               allow_redirects=False)
            if resp.status_code in (301, 302, 303, 307, 308):
                target = urljoin(current, resp.headers.get("location", ""))
                if urlsplit(target).netloc != urlsplit(current).netloc:
                    # The bot manager's validate.perfdrive.com interstitial:
                    # the proxy refuses it, so drop the session and start over.
                    raise FetchError(f"bot-manager redirect to {target}")
                current = target
                continue
            if resp.status_code == 200:
                return resp
            raise FetchError(f"HTTP {resp.status_code} for {current}")
        raise FetchError(f"redirect loop for {url}")
    except requests.exceptions.ProxyError as exc:
        raise _Denied(str(exc)) from exc
    except requests.exceptions.RequestException as exc:
        raise FetchError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        session.close()


def _fetch(url: str, attempts: int = ATTEMPTS) -> requests.Response:
    """Retry :func:`_attempt`; classify a run of pure CONNECT denials as blocked."""
    errors: list[str] = []
    denials = 0
    for i in range(attempts):
        try:
            return _attempt(url)
        except _Denied as exc:
            denials += 1
            errors.append(f"proxy CONNECT denied: {exc}")
        except FetchError as exc:
            errors.append(str(exc))
        if i + 1 < attempts:
            time.sleep(random.uniform(1.0, 3.0))
    detail = f"{url} after {attempts} attempts: " + "; ".join(errors[-4:])
    if denials == attempts:
        raise FetchBlocked(f"egress policy denied every attempt for {detail}")
    raise FetchError(f"failed {detail}")


_HREF = re.compile(r'href="([^"]+?)"', re.I)


def _resolve(landing_url: str, pattern: str) -> str | None:
    """Scrape a landing page for the first href matching `pattern` (regex)."""
    try:
        html = _fetch(landing_url).text
    except (FetchBlocked, FetchError):
        return None
    rx = re.compile(pattern, re.I)
    for href in _HREF.findall(html):
        if rx.search(href):
            return urljoin(landing_url, href.replace("&amp;", "&"))
    return None


def _fallback_landing(pull: Pull) -> tuple[str, str] | None:
    """(landing url, href pattern) to re-resolve `pull` when its `v=` has moved."""
    if pull.source_id == "BMF_DATENPORTAL":
        stem = DATENPORTAL_FILES[pull.part][0].split("?")[0].rsplit("/", 1)[-1]
        return datenportal_landing_url(pull.part), re.escape(stem)
    if pull.source_id == "BMF_KREDITAUFNAHMEBERICHT":
        return (kreditaufnahmebericht_landing_url(int(pull.part)),
                rf"kreditaufnahmebericht-{int(pull.part)}\.pdf")
    if pull.source_id == "BMF_HAUSHALTSRECHNUNG" and pull.part.endswith("band2"):
        year = int(pull.part.split("_")[0])
        landing = (HAUSHALTSRECHNUNG_2025_LANDING if year == 2025
                   else HAUSHALTSRECHNUNG_INDEX)
        return landing, rf"haushaltsrechnung-{year}-band2\.pdf"
    return None


def get(pull: Pull) -> tuple[bytes, str, int]:
    """Family fetch hook (`debt.fetch.fetch_pull`): bytes, content-type, status.

    On a 404 (the publisher bumps ``v=`` whenever a file is refreshed) the
    landing page is scraped for the current link and the pull retried once.
    """
    try:
        resp = _fetch(pull.url)
    except FetchError as exc:
        if "HTTP 404" not in str(exc):
            raise
        fallback = _fallback_landing(pull)
        resolved = _resolve(*fallback) if fallback else None
        if not resolved or resolved == pull.url:
            raise
        resp = _fetch(resolved)
    return resp.content, resp.headers.get("content-type", ""), resp.status_code
