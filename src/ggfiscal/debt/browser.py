"""Browser-backed fetch for the two debt offices whose sites answer plain
HTTP with a JavaScript challenge (DMO: Radware ShieldSquare; AFT: Cloudflare).
Authorised by the committee 2026-09-09 (OQ-8 follow-up): public official
statistics, fetched from the committee's own environment, one session per
host, a polite delay between requests, and every byte stored as a D8
snapshot like any other pull.

Mechanics (verified live): Playwright's bundled Chromium through the agent
proxy needs TLS capped at 1.2 and QUIC / post-quantum key exchange off to
complete the tunnel handshake. The landing page is opened once so the
challenge script can set its cookie; report files are then fetched with the
context's request client, which shares those cookies and returns raw bytes.
TLS verification stays on.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from urllib.parse import urlsplit

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
ARGS = ["--no-sandbox", "--disable-quic",
        "--disable-features=PostQuantumKyber,UseMLKEM,EncryptedClientHello",
        "--ssl-version-max=tls1.2"]
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
# Only markers of the interstitial itself: a cleared Cloudflare page still
# references /cdn-cgi/challenge-platform/, so that string is NOT a marker.
CHALLENGE_MARKERS = ("ShieldSquare Captcha", "<title>Just a moment...</title>", "perfdrive.com/aperture")
# The page that is opened to clear the challenge: verified live 2026-09-09
# (the DMO's /data/ landing never clears it; the report URL itself does).
LANDING = {"www.dmo.gov.uk": "https://www.dmo.gov.uk/data/XmlDataReport?reportCode=D1A",
           "www.aft.gouv.fr": "https://www.aft.gouv.fr/fr/encours-detaille-oat"}
MIN_INTERVAL_S = 1.5


def is_challenge(content: bytes | str) -> bool:
    head = content[:30000].decode("utf-8", "ignore") if isinstance(content, bytes) else content[:30000]
    return any(m in head for m in CHALLENGE_MARKERS)


class BrowserSession:
    """One Chromium context per process, one solved challenge per host."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            executable_path=CHROME, headless=True, args=ARGS,
            proxy={"server": os.environ["HTTPS_PROXY"]} if os.environ.get("HTTPS_PROXY") else None)
        self._ctx = self._browser.new_context(user_agent=UA, ignore_https_errors=False,
                                              locale="en-GB")
        self._solved: set[str] = set()
        self._last: dict[str, float] = {}

    @classmethod
    def get(cls) -> "BrowserSession":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def close(self) -> None:
        try:
            self._ctx.close()
            self._browser.close()
            self._pw.stop()
        finally:
            type(self)._instance = None

    # ------------------------------------------------------------ challenge

    def solve(self, host: str, force: bool = False) -> None:
        if host in self._solved and not force:
            return
        url = LANDING.get(host, f"https://{host}/")
        page = self._ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            deadline = time.time() + 60
            while time.time() < deadline:
                page.wait_for_timeout(2000)
                if not is_challenge(page.content()):
                    break
            else:
                raise RuntimeError(f"challenge on {host} did not clear within 45 s")
        finally:
            page.close()
        self._solved.add(host)
        print(f"[browser] challenge cleared on {host}", file=sys.stderr)

    # ---------------------------------------------------------------- fetch

    def fetch(self, url: str, referer: str | None = None, retries: int = 2) -> tuple[bytes, str, int]:
        """Navigate a page to the URL (the challenge cookie alone does not
        satisfy the DMO's request-level checks; a real navigation does). A
        response that is a document comes back as its raw body; a response
        the browser treats as a download is read from the download file."""
        host = urlsplit(url).netloc
        self.solve(host)
        for attempt in range(retries + 1):
            wait = MIN_INTERVAL_S - (time.time() - self._last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            page = self._ctx.new_page()
            body, ctype, status = b"", "", 0
            try:
                try:
                    with page.expect_download(timeout=120000) as dl_info:
                        try:
                            resp = page.goto(url, wait_until="domcontentloaded", timeout=120000, referer=referer)
                        except Exception as e:      # "Download is starting" aborts the navigation
                            if "Download is starting" not in str(e) and "net::ERR_ABORTED" not in str(e):
                                raise
                            resp = None
                        if resp is not None:
                            body, ctype, status = resp.body(), resp.headers.get("content-type", ""), resp.status
                            if "text/html" in ctype and is_challenge(body):
                                page.wait_for_timeout(8000)
                                body = page.content().encode("utf-8")
                            raise _Done()
                    dl = dl_info.value
                    body = open(dl.path(), "rb").read()
                    ctype = _guess_type(dl.suggested_filename, body)
                    status = 200
                except _Done:
                    pass
            finally:
                page.close()
            self._last[host] = time.time()
            if "text/html" in ctype and is_challenge(body):
                print(f"[browser] challenge page on {url}; re-solving ({attempt + 1}/{retries + 1})", file=sys.stderr)
                self.solve(host, force=True)
                continue
            print(f"[browser] {status} {len(body):>9} B  {ctype.split(';')[0]:<40} {url}", file=sys.stderr)
            return body, ctype, status
        raise RuntimeError(f"still a challenge page after {retries + 1} attempts: {url}")


class _Done(Exception):
    pass


def _guess_type(name: str, body: bytes) -> str:
    n = (name or "").lower()
    if body[:2] == b"PK" or n.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if body[:8] == bytes.fromhex("d0cf11e0a1b11ae1") or n.endswith(".xls"):
        return "application/vnd.ms-excel"
    if body[:5] == b"%PDF-" or n.endswith(".pdf"):
        return "application/pdf"
    if body.lstrip()[:5] == b"<?xml" or n.endswith(".xml"):
        return "application/xml"
    if n.endswith(".csv"):
        return "text/csv"
    return "text/html" if body.lstrip()[:1] == b"<" else "application/octet-stream"


def fetch(url: str, referer: str | None = None) -> tuple[bytes, str, int]:
    return BrowserSession.get().fetch(url, referer)
