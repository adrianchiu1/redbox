"""Fetch orchestration: pull registered sources into the snapshot store.

Designed to run in a network-enabled environment; in this repo's current
remote environment every statistical host is denied by the egress proxy
(OQ-1), which surfaces here as FetchBlocked so the CLI can report the
blocked hosts instead of pretending a source is missing.
"""

from __future__ import annotations

import time

import requests

from ggfiscal.ingest import endpoints
from ggfiscal.ingest.store import SnapshotStore

TIMEOUT = 120
RETRIES = 3


class FetchBlocked(RuntimeError):
    """Egress-policy denial (proxy 403 on CONNECT) — do not retry (OQ-1)."""


class FetchError(RuntimeError):
    pass


def _get(url: str) -> requests.Response:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 407):
                raise FetchBlocked(f"{resp.status_code} for {url} (egress policy or auth)")
            last = FetchError(f"HTTP {resp.status_code} for {url}")
        except requests.exceptions.ProxyError as e:
            raise FetchBlocked(f"proxy denied CONNECT for {url}: {e}") from e
        except requests.exceptions.RequestException as e:
            last = e
        time.sleep(2 ** attempt)
    raise FetchError(f"failed after {RETRIES} attempts: {url}") from last


def _ext_for(url: str, resp: requests.Response) -> str:
    ctype = resp.headers.get("content-type", "").lower()
    if "csv" in ctype or "format=csv" in url:
        return "csv"
    if "json" in ctype:
        return "json"
    if "xml" in ctype or "sdmx" in ctype:
        return "xml"
    if "zip" in ctype:
        return "zip"
    if "spreadsheet" in ctype or url.endswith(".xlsx"):
        return "xlsx"
    return "bin"


def fetch_one(source_id: str, url: str, store: SnapshotStore | None = None) -> dict:
    """Pull one URL into the store. Returns a manifest-style record."""
    store = store or SnapshotStore()
    resp = _get(url)
    snap = store.save(source_id, resp.content, url=url, ext=_ext_for(url, resp),
                      extra={"http_status": resp.status_code,
                             "content_type": resp.headers.get("content-type", "")})
    return {"source_id": source_id, "sha256": snap.sha256, "path": str(snap.path),
            "size": snap.size}


def fetch_all(store: SnapshotStore | None = None) -> tuple[list[dict], list[dict]]:
    """Pull every Stage 0 probe endpoint. Returns (successes, failures);
    failures carry the reason so source_verification.md can name blocked hosts."""
    store = store or SnapshotStore()
    ok, failed = [], []
    for source_id, url in endpoints.all_stage0_probe_urls().items():
        try:
            ok.append(fetch_one(source_id, url, store))
        except (FetchBlocked, FetchError) as e:
            failed.append({"source_id": source_id, "url": url,
                           "error": type(e).__name__, "detail": str(e)})
    return ok, failed
