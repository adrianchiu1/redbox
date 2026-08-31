"""Immutable content-hashed raw snapshot store (D8, §11.1).

Layout: data/raw/{source_id}/{retrieved_at}_{sha256[:12]}.{ext}
Manifest: data/manifest/snapshots.jsonl — one JSON record per pull, append-only,
carrying the full sha256 so any snapshot can be re-verified byte-for-byte.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
from pathlib import Path

from ggfiscal.config import repo_root


@dataclasses.dataclass(frozen=True)
class Snapshot:
    source_id: str
    path: Path
    sha256: str
    retrieved_at: str
    url: str
    size: int


class SnapshotStore:
    def __init__(self, root: Path | None = None):
        base = root or repo_root() / "data"
        self.raw = base / "raw"
        self.manifest = base / "manifest" / "snapshots.jsonl"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.manifest.parent.mkdir(parents=True, exist_ok=True)

    def save(self, source_id: str, content: bytes, url: str, ext: str,
             extra: dict | None = None) -> Snapshot:
        sha = hashlib.sha256(content).hexdigest()
        retrieved_at = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest_dir = self.raw / source_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{retrieved_at}_{sha[:12]}.{ext.lstrip('.')}"
        if dest.exists():
            # Same second, same content: the store is content-addressed, keep the original.
            existing = dest.read_bytes()
            if hashlib.sha256(existing).hexdigest() != sha:
                raise RuntimeError(f"snapshot collision at {dest}; refusing to overwrite (D8)")
        else:
            dest.write_bytes(content)
        snap = Snapshot(source_id=source_id, path=dest, sha256=sha,
                        retrieved_at=retrieved_at, url=url, size=len(content))
        record = {**dataclasses.asdict(snap), "path": str(dest.relative_to(self.raw.parent.parent)),
                  **(extra or {})}
        with open(self.manifest, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
        return snap

    def verify(self, snap_path: Path, expected_sha256: str) -> bool:
        return hashlib.sha256(snap_path.read_bytes()).hexdigest() == expected_sha256

    def entries(self) -> list[dict]:
        if not self.manifest.exists():
            return []
        with open(self.manifest, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
