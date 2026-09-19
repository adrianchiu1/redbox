"""`ggfiscal debt fetch`: run every family's pulls into the D8 snapshot store.

Reuses `ingest.fetch` for the HTTP path and the manifest record shape, so
debt snapshots sit in `data/raw/{source_id}/` and `data/manifest/
snapshots.jsonl` exactly like the parent package's, keyed by (source_id,
part). A family may supply `get(pull) -> bytes` for publishers that a
plain GET cannot serve (BMF's bot manager needs cookies, referer and
retries; the BoE IADB returns an HTML table that we store as-is and parse
in the reader).
"""

from __future__ import annotations

from ggfiscal.debt import endpoints
from ggfiscal.ingest.fetch import FetchBlocked, FetchError, _ext_for, _get
from ggfiscal.ingest.store import SnapshotStore


def fetch_pull(family_name: str, pull: endpoints.Pull,
               store: SnapshotStore | None = None) -> dict:
    store = store or SnapshotStore()
    fam = endpoints.family(family_name)
    if hasattr(fam, "get"):
        content, content_type, status = fam.get(pull)
        ext = _ext_for(pull.url, _FakeResp(content_type))
    else:
        resp = _get(pull.url, pull.accept, pull.headers)
        content, content_type, status = resp.content, resp.headers.get("content-type", ""), resp.status_code
        ext = _ext_for(pull.url, resp)
    snap = store.save(pull.source_id, content, url=pull.url, ext=ext,
                      extra={"part": pull.part, "http_status": status,
                             "content_type": content_type, "family": family_name})
    return {"source_id": pull.source_id, "part": pull.part, "sha256": snap.sha256,
            "path": str(snap.path), "size": snap.size}


class _FakeResp:
    """Minimal stand-in so `_ext_for` can be reused for family-fetched bytes."""

    def __init__(self, content_type: str):
        self.headers = {"content-type": content_type}


def fetch_all(families: tuple[str, ...] | None = None,
              store: SnapshotStore | None = None) -> tuple[list[dict], list[dict]]:
    store = store or SnapshotStore()
    ok, failed = [], []
    for fam, pull in endpoints.all_debt_pulls(families):
        try:
            ok.append(fetch_pull(fam, pull, store))
        except (FetchBlocked, FetchError) as e:
            failed.append({"source_id": pull.source_id, "part": pull.part,
                           "url": pull.url, "family": fam,
                           "error": type(e).__name__, "detail": str(e)})
    return ok, failed
