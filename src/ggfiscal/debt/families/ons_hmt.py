"""Family 'ons_hmt' — ONS public sector finances, ONS RPI, HM Treasury on
gov.uk (DEBT_KICKOFF.md §6.3 GBR column, §13, §14 GBR).

Six register entries, 41 pulls:

  ONS_PSF_APPENDIX_A   1 xlsx  PSA1–PSA10, REC1–REC3, PSNFL (step A/B stock and
                               reconciliation intermediates)
  ONS_PSF_APPENDIX_S   1 xls   table 1.2A financing of the CGNCR by instrument
  ONS_PSF_TIMESERIES  10 json  BKPM BKPJ NMFX MW7L M98R ANTA AACE L6BD ANSK ANLO
  ONS_RPI              3 json  CHAW CDKO CZBH (the `UK_RPI` reference series, §4.2)
  HMT_DMR              6       4 edition PDFs + 2 accessible-HTML editions
  HMT_NLF             20 pdf   National Loans Fund Account 2005-06 … 2024-25

Resolution rules (all verified live 2026-09-09):

* ONS dataset files sit at `/file?uri={dataset_uri}/current/{filename}`. The
  filename is stable but not guaranteed, so `_ons_current_file` HEADs the
  known name and, on 404, reads `{dataset_uri}/current/data` whose
  `downloads[0].file` names the current workbook. A network failure at
  resolution time falls back to the known name rather than killing `pulls()`
  for every other family — the fetch itself then records the failure.
  NOTE the PSF datasets live under `/publicsectorfinance/datasets`, not the
  `/publicspending/datasets` prefix hard-coded in
  `ingest.endpoints.ONS_DATASETS`, so the builders here are local.

* gov.uk attachments have opaque `assets.publishing.service.gov.uk/media/...`
  URLs that only the content API knows. Those lookups happen lazily inside
  `pulls()` and are cached in module scope; a failed lookup raises
  `GovUkResolutionError` (a clear error, per Stage D0) rather than silently
  dropping the HMT pulls.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from ggfiscal.ingest.endpoints import BROWSER_HEADERS, Pull

ONS_BASE = "https://www.ons.gov.uk"
PSF_DATASETS = "/economy/governmentpublicsectorandtaxes/publicsectorfinance/datasets"
PSF_TIMESERIES = "/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries"
RPI_TIMESERIES = "/economy/inflationandpriceindices/timeseries"
GOVUK_BASE = "https://www.gov.uk"
GOVUK_CONTENT = "https://www.gov.uk/api/content"

# (part, dataset slug, published filename)
PSF_FILES = (
    ("appendix_a", "publicsectorfinancesappendixatables110",
     "publicsectorfinancessummarytablesappendixafinal.xlsx"),
    ("appendix_s", "financialstatisticsforpublicsector",
     "publicsectornetcashrequirementappendixsfinal.xls"),
)
PSF_SOURCE_ID = {"appendix_a": "ONS_PSF_APPENDIX_A", "appendix_s": "ONS_PSF_APPENDIX_S"}

# PUSF single series (§13). BKPM/BKPJ stocks; NMFX accrued CG net interest;
# MW7L index-linked capital uplift; M98R CGNCR excl. NRAM/B&B/Network Rail;
# ANTA/AACE financing flows; L6BD APF interest receivable; ANSK gilt-interest
# adjustment; ANLO PS interest paid to the private sector.
PSF_CDIDS = ("BKPM", "BKPJ", "NMFX", "MW7L", "M98R",
             "ANTA", "AACE", "L6BD", "ANSK", "ANLO")
# CHAW Jan 1987 = 100 (1987–); CDKO long run Jan 1974 = 100 (1947–);
# CZBH RPI 12-month percentage change.
RPI_CDIDS = ("CHAW", "CDKO", "CZBH")

DMR_EDITIONS = ("2026-27", "2025-26", "2024-25", "2023-24")
NLF_COLLECTION = "/government/collections/hmt-central-funds"

TIMEOUT = 120


class GovUkResolutionError(RuntimeError):
    """A gov.uk content-API lookup needed to define a pull did not succeed."""


# ---------- ONS URL builders ----------

def psf_file_url(slug: str, filename: str) -> str:
    return f"{ONS_BASE}/file?uri={PSF_DATASETS}/{slug}/current/{filename}"


def psf_current_meta_url(slug: str) -> str:
    """`current` page JSON: `downloads[0].file` is the workbook served today."""
    return f"{ONS_BASE}{PSF_DATASETS}/{slug}/current/data"


def psf_timeseries_url(cdid: str) -> str:
    return f"{ONS_BASE}{PSF_TIMESERIES}/{cdid.lower()}/pusf/data"


def psf_timeseries_csv_url(cdid: str) -> str:
    """CSV-generator fallback for a CDID that 404s under /pusf/data."""
    return (f"{ONS_BASE}/generator?format=csv&uri="
            f"{PSF_TIMESERIES}/{cdid.lower()}/pusf")


def rpi_timeseries_url(cdid: str) -> str:
    return f"{ONS_BASE}{RPI_TIMESERIES}/{cdid.lower()}/mm23/data"


# ---------- HTTP helpers (stdlib: pulls() must not depend on the fetch layer) ----------

def _request(url: str, method: str = "GET") -> bytes:
    req = urllib.request.Request(url, method=method,
                                 headers=dict(BROWSER_HEADERS))
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _json(url: str) -> dict:
    return json.loads(_request(url).decode("utf-8"))


_ONS_FILE_CACHE: dict[str, str] = {}


def _ons_current_file(slug: str, filename: str) -> str:
    """Filename ONS serves for `slug` today. Known name if it still resolves."""
    if slug in _ONS_FILE_CACHE:
        return _ONS_FILE_CACHE[slug]
    resolved = filename
    try:
        _request(psf_file_url(slug, filename), method="HEAD")
    except urllib.error.HTTPError:
        try:
            downloads = _json(psf_current_meta_url(slug)).get("downloads") or []
        except (urllib.error.URLError, ValueError) as e:  # pragma: no cover
            raise RuntimeError(
                f"ONS dataset {slug}: {filename} is gone and "
                f"{psf_current_meta_url(slug)} could not be read ({e})") from e
        if not downloads:
            raise RuntimeError(f"ONS dataset {slug}: no downloads listed")
        resolved = str(downloads[0]["file"])
    except urllib.error.URLError:
        pass  # offline: keep the published name, let the fetch record the failure
    _ONS_FILE_CACHE[slug] = resolved
    return resolved


# ---------- gov.uk content API ----------

_GOVUK_CACHE: dict[str, dict] = {}


def govuk_content(base_path: str) -> dict:
    """Content-API document for a gov.uk base path, cached in module scope."""
    if base_path not in _GOVUK_CACHE:
        url = GOVUK_CONTENT + base_path
        try:
            _GOVUK_CACHE[base_path] = _json(url)
        except (urllib.error.URLError, ValueError) as e:
            raise GovUkResolutionError(f"gov.uk content API failed for {url}: {e}") from e
    return _GOVUK_CACHE[base_path]


def _attachments(base_path: str) -> list[dict]:
    return list(govuk_content(base_path).get("details", {}).get("attachments", []))


def _absolute(url: str) -> str:
    return url if url.startswith("http") else urllib.parse.urljoin(GOVUK_BASE, url)


def dmr_urls(edition: str) -> tuple[str, str | None]:
    """(PDF url, accessible-HTML url or None) for one Debt Management Report.

    The HTML edition is published as an attachment with no content type and a
    relative gov.uk path; only 2025-26 and 2026-27 have one (2025-26 calls it
    "… (Accessible)"), so the slug cannot be guessed and is read from the API.
    """
    base_path = f"/government/publications/debt-management-report-{edition}"
    pdf, html = None, None
    for a in _attachments(base_path):
        url = str(a.get("url") or "")
        if not url:
            continue
        if a.get("content_type") == "application/pdf" or url.lower().endswith(".pdf"):
            pdf = pdf or _absolute(url)
        elif url.startswith("/government/"):
            html = html or _absolute(url)
    if pdf is None:
        raise GovUkResolutionError(f"no PDF attachment on {base_path}")
    return pdf, html


_NLF_TITLE = re.compile(r"^national loans fund account\s+(\d{4})\s*(?:to|-|–)\s*(\d{2,4})",
                        re.IGNORECASE)


def _financial_year(y1: str, y2: str) -> str:
    """('2007', '2008') and ('2007', '08') both -> '2007-08'."""
    return f"{int(y1)}-{int(y2) % 100:02d}"


def nlf_editions() -> dict[str, str]:
    """{financial year: PDF url} for every National Loans Fund Account in the
    HMT central funds collection (2005-06 onward; earlier years are published
    as combined Consolidated Fund and NLF accounts and are not taken here)."""
    coll = govuk_content(NLF_COLLECTION)
    out: dict[str, str] = {}
    for doc in coll.get("links", {}).get("documents", []):
        m = _NLF_TITLE.match(str(doc.get("title", "")).strip())
        if not m:
            continue
        fy = _financial_year(*m.groups())
        pdfs = [str(a["url"]) for a in _attachments(str(doc["base_path"]))
                if a.get("content_type") == "application/pdf" and a.get("url")]
        if not pdfs:
            raise GovUkResolutionError(f"NLF {fy}: no PDF attachment on {doc['base_path']}")
        # 2015-16 … 2017-18 publish a web and a print rendering; take the web one.
        web = [u for u in pdfs if "print" not in u.lower()]
        out[fy] = _absolute((web or pdfs)[0])
    if not out:
        raise GovUkResolutionError(
            f"no 'National Loans Fund account' publications found in {NLF_COLLECTION}")
    return dict(sorted(out.items()))


# ---------- pulls ----------

def pulls() -> list[Pull]:
    out: list[Pull] = []

    for part, slug, filename in PSF_FILES:
        url = psf_file_url(slug, _ons_current_file(slug, filename))
        out.append(Pull(PSF_SOURCE_ID[part], part, url, headers=BROWSER_HEADERS))

    for cdid in PSF_CDIDS:
        out.append(Pull("ONS_PSF_TIMESERIES", cdid, psf_timeseries_url(cdid),
                        "application/json", BROWSER_HEADERS))

    for cdid in RPI_CDIDS:
        out.append(Pull("ONS_RPI", cdid, rpi_timeseries_url(cdid),
                        "application/json", BROWSER_HEADERS))

    for edition in DMR_EDITIONS:
        pdf, html = dmr_urls(edition)
        out.append(Pull("HMT_DMR", edition, pdf, headers=BROWSER_HEADERS))
        if html:
            out.append(Pull("HMT_DMR", f"{edition}_html", html, headers=BROWSER_HEADERS))

    for fy, url in nlf_editions().items():
        out.append(Pull("HMT_NLF", fy, url, headers=BROWSER_HEADERS))

    return out
