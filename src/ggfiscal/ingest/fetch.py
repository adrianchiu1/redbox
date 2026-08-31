"""Fetch orchestration: pull registered sources into the snapshot store.

Every pull is a Pull(source_id, part, url) from endpoints.all_stage0_pulls();
`part` (country, vintage, chapter, ...) is recorded in the manifest so the
standardise step can address individual extractions. FetchBlocked marks an
egress-policy denial (OQ-1 in the first session; resolved by allowlisting in
the second) as distinct from a source-side failure.
"""

from __future__ import annotations

import time

import requests

from ggfiscal.ingest import endpoints
from ggfiscal.ingest.store import SnapshotStore

TIMEOUT = 300
RETRIES = 3


class FetchBlocked(RuntimeError):
    """Egress-policy denial (proxy 403 on CONNECT) — do not retry (OQ-1)."""


class FetchError(RuntimeError):
    pass


def _get(url: str, accept: str = "", extra_headers: tuple = ()) -> requests.Response:
    last: Exception | None = None
    headers = {"Accept": accept} if accept else {}
    headers.update(dict(extra_headers))
    for attempt in range(RETRIES):
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers=headers)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (407,):
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
    if url.endswith(".zip") or "zip" in ctype:
        return "zip"
    if url.endswith(".xlsx") or "officedocument.spreadsheetml" in ctype:
        return "xlsx"
    if url.endswith(".xls") or "application/vnd.ms-excel" in ctype:
        return "xls"
    if "csv" in ctype or "format=csv" in url:
        return "csv"
    if "json" in ctype:
        return "json"
    if "xml" in ctype or "sdmx" in ctype:
        return "xml"
    return "bin"


def fetch_pull(pull: endpoints.Pull, store: SnapshotStore | None = None) -> dict:
    """Execute one Pull into the store. Returns a manifest-style record."""
    store = store or SnapshotStore()
    resp = _get(pull.url, pull.accept, pull.headers)
    snap = store.save(pull.source_id, resp.content, url=pull.url,
                      ext=_ext_for(pull.url, resp),
                      extra={"part": pull.part,
                             "http_status": resp.status_code,
                             "content_type": resp.headers.get("content-type", "")})
    return {"source_id": pull.source_id, "part": pull.part, "sha256": snap.sha256,
            "path": str(snap.path), "size": snap.size}


def fetch_one(source_id: str, url: str, store: SnapshotStore | None = None) -> dict:
    """Back-compat single-URL pull."""
    return fetch_pull(endpoints.Pull(source_id, "", url), store)


def fetch_all(store: SnapshotStore | None = None) -> tuple[list[dict], list[dict]]:
    """Run every Stage 0 pull. Returns (successes, failures); failures carry
    the reason so source_verification.md can name blocked hosts."""
    store = store or SnapshotStore()
    ok, failed = [], []
    for pull in endpoints.all_stage0_pulls() + endpoints.all_stage3_pulls():
        try:
            ok.append(fetch_pull(pull, store))
        except (FetchBlocked, FetchError) as e:
            failed.append({"source_id": pull.source_id, "part": pull.part,
                           "url": pull.url, "error": type(e).__name__,
                           "detail": str(e)})
    return ok, failed
