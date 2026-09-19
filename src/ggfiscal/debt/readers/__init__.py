"""Readers for the debt extension: latest snapshot per (source_id, part) ->
tidy frames. One module per family; shared helpers here."""

from __future__ import annotations

from pathlib import Path

from ggfiscal import config
from ggfiscal.standardise.readers import latest_snapshots


def snap_path(source_id: str, part: str) -> Path:
    e = latest_snapshots().get((source_id, part))
    if e is None:
        raise FileNotFoundError(f"no snapshot for {source_id}/{part} — run `ggfiscal debt fetch`")
    return config.repo_root() / e["path"]
