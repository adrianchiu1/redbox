#!/usr/bin/env python3
"""Download the DMO and AFT files on a normal desktop, with a visible browser.

Both offices sit behind bot management (Radware ShieldSquare, Cloudflare)
that lets a person through and stops headless automation. This script
drives a VISIBLE Chromium on your own machine: you may be asked to tick a
box or solve a captcha once per site; the script waits for you, then saves
every file in DOWNLOAD_LIST.md into data/incoming/{SOURCE_ID}/{part}.{ext}
with the names `ggfiscal debt ingest-incoming` expects.

Setup (once):   pip install playwright && playwright install chromium
Run:            python tools/harvest_offices_local.py [--only dmo|aft] [--cob] [--dmo-format TOKEN]
Afterwards:     git add data/incoming && git commit -m "DMO/AFT files" && git push
                (or copy data/incoming/ to the build box), then
                ggfiscal debt ingest-incoming

Polite by design: one browser, one tab per file, a pause between requests.
Keep the browser window open until the script prints "done": the script
drives it, and a closed window ends the run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONLY_PART = None
INCOMING = ROOT / "data" / "incoming"
DMO = "https://www.dmo.gov.uk"
AFT = "https://www.aft.gouv.fr"

GILT_REPORTS = ["D1A", "D1C", "D1D", "D2.1E", "D2.1A", "D2.1PROF7", "D2.1PROF9", "D10A",
                "D4L", "D8B", "D5I", "D10C", "D9C"]
BILL_REPORTS = ["D2.2A", "D2.2D", "D2.2E", "D2.2G"]

CHALLENGE = ("ShieldSquare Captcha", "<title>Just a moment...</title>", "perfdrive.com/aperture")
# Short text bodies the DMO's export handler returns instead of a file; a
# download that carries one of these is a failure, not data.
STUBS = ("Unable to fulfil the report request", "is not available in this presentation type")
# Presentation type each DMO report exports in (verified 2026-09-10: each
# report answers exactly one of xml / xls; the other pairs return a stub).
# Reports not listed are tried in DMO_FORMATS order.
KNOWN_FORMAT = {
    "D1A": "xml", "D10C": "xml", "D4L": "xml", "D2.1E": "xml", "D2.2D": "xml",
    "D1C": "xls", "D2.1A": "xls", "D2.1PROF7": "xls", "D2.1PROF9": "xls", "D10A": "xls",
    "D8B": "xls", "D2.2E": "xls", "D2.2G": "xls",
}
DMO_FORMATS = ["xls", "xml", "pdf", "csv"]


def export_url(code: str, fmt: str = "xls", cob: str = "") -> str:
    """The URL behind the DMO pages' export buttons (the presentation type is
    `exportFormatValue`; without it the site says the report "is not
    available in this presentation type")."""
    return (f"{DMO}/umbraco/surface/DataExport/GetDataExport?reportCode={code}"
            f"&exportFormatValue={fmt}&parameters=&COBDate={cob}")


def dmo_jobs(skip_cob: bool) -> list[tuple[str, str, str, str]]:
    """(source, part, report code, COBDate) — the format token is chosen at run time."""
    jobs = [("UK_DMO_GILTS", "D1A_xml", "D1A", "xml")]
    jobs += [("UK_DMO_GILTS", c, c, "") for c in GILT_REPORTS]
    jobs += [("UK_DMO_BILLS", c, c, "") for c in BILL_REPORTS]
    if not skip_cob:
        for y in range(1998, dt.date.today().year):
            d = dt.date(y, 12, 31)
            jobs.append(("UK_DMO_GILTS", f"D1A_cob_{d:%Y%m%d}", "D1A", f"{d:%d}%2F{d:%m}%2F{d:%Y}"))
    return jobs


# AFT pages: (source, part the page's HTML is saved as, page URL, regex of
# file links to download from it, or None). The encours pages ARE the data (an
# HTML table of ISIN / libellé / encours by maturity year) and link to one page
# per ISIN, which is saved too.
AFT_PAGES = [
    ("FRA_AFT_ENCOURS", "oat", f"{AFT}/fr/encours-detaille-oat", None),
    ("FRA_AFT_ENCOURS", "btf", f"{AFT}/fr/encours-detaille-btf", None),
    ("FRA_AFT_ENCOURS", "oatei", f"{AFT}/en/encours-detaille-oatei", None),
    ("FRA_AFT_ADJUDICATIONS", "dernieres", f"{AFT}/fr/dernieres-adjudications", r"\.(xlsx?|csv)$"),
    ("FRA_AFT_ADJUDICATIONS", "archives", f"{AFT}/fr/dernieres-adjudications-archives", r"\.(xlsx?|csv)$"),
    ("FRA_AFT_INDEXATION", "oati_page", f"{AFT}/fr/oati-principaux-chiffres", r"\.(xlsx?|csv)$"),
    ("FRA_AFT_INDEXATION", "oatei_page", f"{AFT}/en/oateuroi-key-figures", r"\.(xlsx?|csv)$"),
    ("FRA_AFT_FINANCEMENT", "rapports", f"{AFT}/fr/rapports-activite", None),
    ("FRA_AFT_FINANCEMENT", "bulletins_index", f"{AFT}/fr/bulletins-mensuels", None),
    ("FRA_AFT_ENCOURS", "dette_negociable", f"{AFT}/fr/dette-negociable", None),
]
ISIN_LINK_RE = re.compile(r"(FR[0-9A-Z]{10})")


def is_challenge(html: str) -> bool:
    return any(m in html for m in CHALLENGE)


def is_stub(body: bytes) -> bool:
    return len(body) < 400 and any(m in body.decode("utf-8", "ignore") for m in STUBS)


def wait_human(page, what: str, limit_s: int = 600) -> bool:
    """Block until the interstitial is gone; the person at the screen solves it.
    Returns True when a challenge had to be cleared. A page that is mid-reload
    (the challenge redirecting) cannot be read for a moment; that is retried,
    not treated as an error."""
    t0, seen, warned = time.time(), False, 0
    while time.time() - t0 < limit_s:
        try:
            html = page.content()
        except Exception:
            page.wait_for_timeout(700)
            continue
        if not is_challenge(html):
            return seen
        seen = True
        if time.time() - t0 > 20 * (warned + 1):
            warned += 1
            print(f"   ... waiting for you to clear the challenge on {what}", flush=True)
        page.wait_for_timeout(1500)
    raise RuntimeError("challenge not cleared in time")


def ext_for(name: str, body: bytes) -> str:
    n = (name or "").lower()
    if body[:2] == b"PK" or n.endswith(".xlsx"):
        return "xlsx"
    if body[:8] == bytes.fromhex("d0cf11e0a1b11ae1") or n.endswith(".xls"):
        return "xls"
    if body[:5] == b"%PDF-" or n.endswith(".pdf"):
        return "pdf"
    if body.lstrip()[:5] in (b"<?xml", b"<Data") or n.endswith(".xml"):
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
    if is_stub(body):
        raise RuntimeError("stub: " + body.decode("utf-8", "ignore").strip()[:80])
    save(source, part, body, hint)


class _Done(Exception):
    pass


def run_dmo(ctx, skip_cob: bool, formats: list[str]) -> list[str]:
    failed = []
    page = ctx.new_page()
    print("\n== DMO: a browser window will open; if you see a captcha, solve it and the script continues.")
    formats = list(formats)
    for source, part, code, cob in dmo_jobs(skip_cob):
        if ONLY_PART and part != ONLY_PART:
            continue
        if part == "D1A_xml":
            tries = ["xml"]
        elif code in KNOWN_FORMAT:
            tries = [KNOWN_FORMAT[code]] + [f for f in formats if f != KNOWN_FORMAT[code]]
        else:
            tries = formats
        err = None
        for fmt in tries:
            try:
                grab(page, export_url(code, fmt, cob), source, part)
                err = None
                if fmt != tries[0] and code not in KNOWN_FORMAT and part != "D1A_xml":
                    print(f"     (format token {fmt!r} works for {code})", flush=True)
                break
            except Exception as e:
                err = e
                if not str(e).startswith("stub"):
                    break
            page.wait_for_timeout(1000)
        if err is not None:
            print(f"FAIL {source}/{part}: {str(err)[:120]}", flush=True)
            failed.append(f"{source}/{part}")
        page.wait_for_timeout(1500)
    page.close()
    return failed


LINK_TEXT_HINTS = ("xls", "excel", "télécharger", "telecharger", "download", "fichier", "tableau")


def page_links(page) -> list[tuple[str, str]]:
    """Every anchor's (href, text) plus download attributes, after the page has
    settled (the AFT lists its files from scripts on some pages)."""
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    return page.eval_on_selector_all(
        "a[href]", "els => els.map(e => [e.href, (e.textContent || '').trim() + ' ' + (e.getAttribute('download') || '') "
                   "+ ' ' + (e.getAttribute('title') || '')])")


def match_links(links, pattern: str) -> list[str]:
    rx = re.compile(pattern, re.I)
    strict = [h for h, t in links if rx.search(h.split("?")[0]) or rx.search(t)]
    if strict:
        return strict
    # broader: anything that looks like a spreadsheet download, by href or text
    return [h for h, t in links
            if re.search(r"xlsx?|\.csv|/download|/dl/|/files?/", h, re.I) or any(k in t.lower() for k in LINK_TEXT_HINTS)]


def capture_click(page, source: str, part: str, seconds: int = 180) -> bool:
    """Fallback: the person clicks the file link in the visible window; the
    script captures whatever download that starts and saves it under the
    right name."""
    print(f"   >> In the browser window, click the Excel link for {source}/{part} "
          f"(you have {seconds} s; press nothing here).", flush=True)
    try:
        with page.expect_download(timeout=seconds * 1000) as dl:
            pass
        d = dl.value
        save(source, part, Path(d.path()).read_bytes(), d.suggested_filename)
        return True
    except Exception as e:
        print(f"   .. no download captured ({str(e)[:60]})", flush=True)
        return False


def run_aft(ctx, browser, click: bool = False, no_isin: bool = False) -> list[str]:
    failed = []
    print("\n== AFT: each page is saved as data; file links on it are downloaded; ISIN pages follow.")
    page = None
    log = INCOMING / "_aft_links.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    for source, part, page_url, pattern in AFT_PAGES:
        if ONLY_PART and part != ONLY_PART:
            continue
        if page is None or page.is_closed():
            page = ctx.new_page()
        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=90000)
            wait_human(page, page_url)
            links = page_links(page)
            html = page.content()
            if is_challenge(html):
                raise RuntimeError("still a challenge page")
            save(source, part, html.encode("utf-8"), f"{part}.html")
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n## {source}/{part}  {page_url}\n")
                for h, t in links:
                    f.write(f"{h}\t{t[:80]}\n")
            # files linked from the page (strict match only)
            if pattern:
                rx = re.compile(pattern, re.I)
                for i, u in enumerate([h for h, t in links if rx.search(h.split("?")[0])][:12]):
                    name = re.sub(r"[^A-Za-z0-9._-]+", "_", u.split("?")[0].rsplit("/", 1)[-1])[:60]
                    try:
                        with page.expect_download(timeout=60000) as dl:
                            page.evaluate("u => { const a = document.createElement('a'); a.href = u; "
                                          "a.download = ''; document.body.appendChild(a); a.click(); }", u)
                        d = dl.value
                        body = Path(d.path()).read_bytes()
                        if not is_challenge(body.decode("utf-8", "ignore")[:20000]) and len(body) >= 400:
                            save(source, f"{part}_file_{name}", body, d.suggested_filename)
                    except Exception as e:
                        print(f"   .. {u[-60:]}: {str(e)[:60]}", flush=True)
                    page.wait_for_timeout(1500)
                if click:
                    capture_click(page, source, f"{part}_clicked")
            # one page per ISIN on the encours pages — in the SAME tab (a new
            # tab is challenged again); after three challenges in a row the
            # crawl stops and the encours table already saved stands
            if source == "FRA_AFT_ENCOURS" and not no_isin:
                seen, streak, saved = set(), 0, 0
                isin_links = [(h, t) for h, t in links if (ISIN_LINK_RE.search(h) or ISIN_LINK_RE.search(t))
                              and not h.startswith("mailto")]
                for h, t in isin_links:
                    m = ISIN_LINK_RE.search(h) or ISIN_LINK_RE.search(t)
                    if m.group(1) in seen:
                        continue
                    seen.add(m.group(1))
                    dest = INCOMING / source / f"isin_{m.group(1)}.html"
                    if dest.exists():
                        continue
                    try:
                        page.goto(h, wait_until="domcontentloaded", timeout=90000)
                        challenged = wait_human(page, h, limit_s=120)
                        streak = streak + 1 if challenged else 0
                        sub_html = page.content()
                        if not is_challenge(sub_html):
                            save(source, f"isin_{m.group(1)}", sub_html.encode("utf-8"), "x.html")
                            saved += 1
                    except Exception as e:
                        print(f"   .. {h[-60:]}: {str(e)[:60]}", flush=True)
                        streak += 1
                    if streak >= 3:
                        print(f"   !! the site challenges every ISIN page; stopping the ISIN crawl after {saved} "
                              f"of {len(isin_links)} (rerun later with --part {part}, saved pages are skipped)", flush=True)
                        break
                    page.wait_for_timeout(2500)
        except Exception as e:
            print(f"FAIL {source}/{part}: {str(e)[:160]}", flush=True)
            failed.append(f"{source}/{part}")
            if "closed" in str(e).lower():
                page = None
        if page is not None and not page.is_closed():
            page.wait_for_timeout(1500)
    return failed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["dmo", "aft"])
    ap.add_argument("--part", help="run one part only, e.g. oat (AFT) or D1A (DMO)")
    ap.add_argument("--no-isin", action="store_true", help="AFT: skip the per-ISIN pages")
    ap.add_argument("--click", action="store_true",
                    help="AFT: after the automatic downloads, wait for you to click a file link on each page")
    ap.add_argument("--cob", action="store_true",
                    help="also try the 28 UK year-end D1A snapshots (COBDate=); off by default because the "
                         "export ignores the date in xml and returns a stub in xls (2026-09-10)")
    ap.add_argument("--dmo-format", default=None,
                    help="presentation-type token for the DMO Excel export, if known (default: try "
                         + ", ".join(DMO_FORMATS) + " in turn)")
    a = ap.parse_args()
    global ONLY_PART
    ONLY_PART = a.part
    formats = [a.dmo_format] + [f for f in DMO_FORMATS if f != a.dmo_format] if a.dmo_format else DMO_FORMATS
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium", file=sys.stderr)
        return 2
    failed: list[str] = []
    with sync_playwright() as p:
        # AutomationControlled off: Cloudflare re-challenges a browser that
        # advertises webdriver control on every navigation
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(accept_downloads=True)
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        if a.only in (None, "dmo"):
            failed += run_dmo(ctx, not a.cob, formats)
        if a.only in (None, "aft"):
            failed += run_aft(ctx, browser, a.click, a.no_isin)
        browser.close()
    print(f"\ndone; {len(failed)} failed: {failed}" if failed else "\ndone; all files saved under data/incoming/")
    print("next: git add data/incoming && git commit -m 'DMO/AFT files' && git push   (then: ggfiscal debt ingest-incoming)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
