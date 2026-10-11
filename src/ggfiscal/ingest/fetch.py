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

# Hosts whose server omits an intermediate certificate from its TLS chain, so
# no client can verify it (D-S17-012): the missing intermediate, fetched
# from the issuer's own AIA URL and committed under config/certs/, is
# appended to the normal trust bundle for those hosts only. Verification
# stays fully on. FNMT-RCM "AC Componentes Informáticos"
# (http://www.cert.fnmt.es/certs/ACCOMP.crt, SHA-256 F0:38:42:1F:...:76:AB,
# valid to 2028-06-24), chained to the standard root AC RAIZ FNMT-RCM.
EXTRA_INTERMEDIATES = {
    "tesoro.es": "fnmt_ac_componentes_informaticos.pem",
    "airef.es": "fnmt_ac_componentes_informaticos.pem",
}


def verify_for(url: str) -> str | bool:
    """The `verify` argument for a request to `url`: True (the default trust
    bundle) or a path to that bundle plus the host's missing intermediate."""
    import os
    import tempfile
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    name = next((f for suffix, f in EXTRA_INTERMEDIATES.items()
                 if host == suffix or host.endswith("." + suffix)), None)
    if name is None:
        return True
    from ggfiscal import config

    base = os.environ.get("REQUESTS_CA_BUNDLE") or requests.certs.where()
    extra = config.repo_root() / "config" / "certs" / name
    dest = os.path.join(tempfile.gettempdir(), f"ggfiscal_bundle_{name}")
    with open(dest, "w", encoding="ascii") as out:
        out.write(open(base, encoding="ascii", errors="ignore").read())
        out.write("\n" + extra.read_text(encoding="ascii"))
    return dest


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
            resp = requests.get(url, timeout=TIMEOUT, headers=headers, verify=verify_for(url))
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
    if url.lower().split("?")[0].endswith(".pdf") or "application/pdf" in ctype:
        return "pdf"
    if "text/html" in ctype:
        return "html"
    if url.lower().split("?")[0].endswith(".txt") or "text/plain" in ctype:
        return "txt"     # BEA NIPA flat files (U0)
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


def ingest_local(path, source_id: str, part: str, url: str, note: str = "",
                 store: SnapshotStore | None = None) -> dict:
    """Store a hand-retrieved file as a D8 snapshot (D-S7-001).

    For publishers no available client can reach (obr.uk's bot challenge,
    OQ-6), the committee downloads the file in a browser and it enters the
    store here: content-hashed and immutable like any pull, with the
    publication's landing URL and a provenance note recorded in the manifest.
    Unlike ordinary snapshots these bytes cannot be re-fetched by a fresh
    container, so they are committed to git (the §11.4 PDF-in-raw/ rule
    extended to hand-retrieved machine-readable files)."""
    from pathlib import Path

    p = Path(path)
    store = store or SnapshotStore()
    snap = store.save(source_id, p.read_bytes(), url=url,
                      ext=p.suffix.lstrip("."),
                      extra={"part": part, "ingest": "manual_upload",
                             "original_filename": p.name, "note": note})
    return {"source_id": source_id, "part": part, "sha256": snap.sha256,
            "path": str(snap.path), "size": snap.size}


def fetch_all(store: SnapshotStore | None = None) -> tuple[list[dict], list[dict]]:
    """Run every Stage 0 pull. Returns (successes, failures); failures carry
    the reason so source_verification.md can name blocked hosts."""
    store = store or SnapshotStore()
    ok, failed = [], []
    for pull in (endpoints.all_stage0_pulls() + endpoints.all_stage3_pulls()
                 + endpoints.all_u0_pulls()):
        try:
            ok.append(fetch_pull(pull, store))
        except (FetchBlocked, FetchError) as e:
            failed.append({"source_id": pull.source_id, "part": pull.part,
                           "url": pull.url, "error": type(e).__name__,
                           "detail": str(e)})
    return ok, failed
