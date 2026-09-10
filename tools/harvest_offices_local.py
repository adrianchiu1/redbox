#!/usr/bin/env python3
"""Download the DMO and AFT files on a normal desktop, with a visible browser.

Both offices sit behind bot management (Radware ShieldSquare, Cloudflare)
that lets a person through and stops headless automation. This script
drives a VISIBLE Chromium on your own machine: you may be asked to tick a
box or solve a captcha once per site; the script waits for you, then saves
every file in DOWNLOAD_LIST.md into data/incoming/{SOURCE_ID}/{part}.{ext}
with the names `ggfiscal debt ingest-incoming` expects.

Setup (once):   pip install playwright && playwright install chromium
Run:            python tools/harvest_offices_local.py [--only dmo|aft] [--skip-cob]
Afterwards:     git add data/incoming && git commit -m "DMO/AFT files" && git push
                (or copy data/incoming/ to the build box), then
                ggfiscal debt ingest-incoming

Polite by design: one browser, one tab per file, a pause between requests.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "data" / "incoming"
DMO = "https://www.dmo.gov.uk"
AFT = "https://www.aft.gouv.fr"

GILT_REPORTS = ["D1A", "D1C", "D1D", "D2.1E", "D2.1A", "D2.1PROF7", "D2.1PROF9", "D10A",
                "D4L", "D8B", "D5I", "D10C", "D9C"]
BILL_REPORTS = ["D2.2A", "D2.2D", "D2.2E", "D2.2G"]

CHALLENGE = ("ShieldSquare Captcha", "<title>Just a moment...</title>", "perfdrive.com/aperture")


def export_url(code: str, fmt: str = "xls", cob: str = "") -> str:
    """The URL behind the DMO pages' export buttons (the presentation type is
    `exportFormatValue`; without it the site says the report "is not
    available in this presentation type")."""
    return (f"{DMO}/umbraco/surface/DataExport/GetDataExport?reportCode={code}"
            f"&exportFormatValue={fmt}&parameters=&COBDate={cob}")


def dmo_jobs(skip_cob: bool) -> list[tuple[str, str, str]]:
    jobs = [("UK_DMO_GILTS", "D1A_xml", export_url("D1A", "xml"))]
    jobs += [("UK_DMO_GILTS", c, export_url(c)) for c in GILT_REPORTS]
    jobs += [("UK_DMO_BILLS", c, export_url(c)) for c in BILL_REPORTS]
    if not skip_cob:
        for y in range(1998, dt.date.today().year):
            d = dt.date(y, 12, 31)
            jobs.append(("UK_DMO_GILTS", f"D1A_cob_{d:%Y%m%d}",
                         export_url("D1A", "xls", f"{d:%d}%2F{d:%m}%2F{d:%Y}")))
    return jobs


# AFT pages: (source, part, page URL, regex the wanted link's href or text must match)
AFT_PAGES = [
    ("FRA_AFT_ENCOURS", "oat_xlsx", f"{AFT}/fr/encours-detaille-oat", r"\.xlsx?$"),
    ("FRA_AFT_ENCOURS", "btf_xlsx", f"{AFT}/fr/encours-detaille-btf", r"\.xlsx?$"),
    ("FRA_AFT_ENCOURS", "oatei_xlsx", f"{AFT}/en/encours-detaille-oatei", r"\.xlsx?$"),
    ("FRA_AFT_ADJUDICATIONS", "hist_oat", f"{AFT}/fr/dernieres-adjudications", r"hist.*oat.*\.xlsx?$"),
    ("FRA_AFT_ADJUDICATIONS", "hist_btf", f"{AFT}/fr/dernieres-adjudications", r"hist.*btf.*\.xlsx?$"),
    ("FRA_AFT_ADJUDICATIONS", "archives_oat", f"{AFT}/fr/dernieres-adjudications-archives", r"(oat|btan).*\.xlsx?$"),
    ("FRA_AFT_ADJUDICATIONS", "archives_btf", f"{AFT}/fr/dernieres-adjudications-archives", r"btf.*\.xlsx?$"),
    ("FRA_AFT_INDEXATION", "oati_current", f"{AFT}/fr/oati-principaux-chiffres", r"^(?!.*1998).*\.xlsx?$"),
    ("FRA_AFT_INDEXATION", "oati_hist_1998", f"{AFT}/fr/oati-principaux-chiffres", r"1998.*\.xlsx?$"),
    ("FRA_AFT_INDEXATION", "oatei_current", f"{AFT}/en/oateuroi-key-figures", r"^(?!.*2005).*\.xlsx?$"),
    ("FRA_AFT_INDEXATION", "oatei_hist_2005", f"{AFT}/en/oateuroi-key-figures", r"2005.*\.xlsx?$"),
    ("FRA_AFT_FINANCEMENT", "rapport_2024", f"{AFT}/fr/rapports-activite", r"2024.*\.pdf$"),
    ("FRA_AFT_FINANCEMENT", "rapport_2023", f"{AFT}/fr/rapports-activite", r"2023.*\.pdf$"),
]


def is_challenge(html: str) -> bool:
    return any(m in html for m in CHALLENGE)


def wait_human(page, what: str) -> None:
    """Block until the interstitial is gone; the person at the screen solves it."""
    t0 = time.time()
    while is_challenge(page.content()):
        if time.time() - t0 > 20 and int(time.time() - t0) % 20 == 0:
            print(f"   ... waiting for you to clear the challenge on {what}", flush=True)
        page.wait_for_timeout(1500)


def ext_for(name: str, body: bytes) -> str:
    n = (name or "").lower()
    if body[:2] == b"PK" or n.endswith(".xlsx"):
        return "xlsx"
    if body[:8] == bytes.fromhex("d0cf11e0a1b11ae1") or n.endswith(".xls"):
        return "xls"
    if body[:5] == b"%PDF-" or n.endswith(".pdf"):
        return "pdf"
    if body.lstrip()[:5] == b"<?xml" or n.endswith(".xml"):
        return "xml"
    if body.lstrip()[:1] == b"<":
        return "html"
    return "bin"


def save(source: str, part: str, body: bytes, name_hint: str) -> Path:
    dest = INCOMING / source / f"{part}.{ext_for(name_hint, body)}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    print(f"OK   {dest.relative_to(ROOT)}  {len(body):,} B", flush=True)
    return dest


def grab(page, url: str, source: str, part: str) -> None:
    """Navigate; take the document body, or the download the site triggers."""
    body, hint = b"", ""
    try:
        with page.expect_download(timeout=90000) as dl:
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=90000)
            except Exception as e:
                if "Download is starting" not in str(e) and "ERR_ABORTED" not in str(e):
                    raise
                resp = None
            if resp is not None:
                wait_human(page, url)
                body = resp.body() if not is_challenge(resp.text()) else page.content().encode()
                # a report page that is really data (XML / HTML table)
                raise _Done()
        d = dl.value
        body, hint = Path(d.path()).read_bytes(), d.suggested_filename
    except _Done:
        pass
    if not body or is_challenge(body.decode("utf-8", "ignore")[:20000]):
        raise RuntimeError("still a challenge page")
    save(source, part, body, hint)


class _Done(Exception):
    pass


def run_dmo(ctx, skip_cob: bool) -> list[str]:
    failed = []
    page = ctx.new_page()
    print("\n== DMO: a browser window will open; if you see a captcha, solve it and the script continues.")
    for source, part, url in dmo_jobs(skip_cob):
        try:
            grab(page, url, source, part)
        except Exception as e:
            print(f"FAIL {source}/{part}: {str(e)[:120]}", flush=True)
            failed.append(f"{source}/{part}")
        page.wait_for_timeout(1500)
    page.close()
    return failed


def run_aft(ctx) -> list[str]:
    failed = []
    page = ctx.new_page()
    print("\n== AFT: same again; the page's Excel links are picked up automatically.")
    for source, part, page_url, pattern in AFT_PAGES:
        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=90000)
            wait_human(page, page_url)
            links = page.eval_on_selector_all("a[href]", "els => els.map(e => [e.href, e.textContent.trim()])")
            rx = re.compile(pattern, re.I)
            cands = [h for h, t in links if rx.search(h.split("?")[0]) or rx.search(t)]
            if not cands:
                raise RuntimeError(f"no link matching /{pattern}/ on the page; download by hand into "
                                   f"data/incoming/{source}/{part}.xlsx")
            with page.expect_download(timeout=90000) as dl:
                page.evaluate("u => { const a = document.createElement('a'); a.href = u; a.download = ''; "
                              "document.body.appendChild(a); a.click(); }", cands[0])
            d = dl.value
            save(source, part, Path(d.path()).read_bytes(), d.suggested_filename)
        except Exception as e:
            print(f"FAIL {source}/{part}: {str(e)[:160]}", flush=True)
            failed.append(f"{source}/{part}")
        page.wait_for_timeout(1500)
    page.close()
    return failed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["dmo", "aft"])
    ap.add_argument("--skip-cob", action="store_true", help="skip the 28 UK year-end position snapshots")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium", file=sys.stderr)
        return 2
    failed: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(accept_downloads=True)
        if a.only in (None, "dmo"):
            failed += run_dmo(ctx, a.skip_cob)
        if a.only in (None, "aft"):
            failed += run_aft(ctx)
        browser.close()
    print(f"\ndone; {len(failed)} failed: {failed}" if failed else "\ndone; all files saved under data/incoming/")
    print("next: git add data/incoming && git commit -m 'DMO/AFT files' && git push   (then: ggfiscal debt ingest-incoming)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
