"""Generate source_register.csv from config/sources.yaml (D-S0-005, §11.6 item 8)."""

from __future__ import annotations

import csv
from pathlib import Path

from ggfiscal import config

COLUMNS = ["source_id", "institution", "object", "countries", "trees", "role",
           "url", "verification_status", "verification_checked",
           "last_update_observed", "latest_vintage", "concept_note", "notes"]


def build(path: Path | None = None) -> Path:
    dest = path or config.repo_root() / "reports" / "source_register.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for sid, src in config.sources().items():
            ver = src.get("verification") or {}
            api = src.get("api") or {}
            w.writerow({
                "source_id": sid,
                "institution": src.get("institution", ""),
                "object": src.get("object", ""),
                "countries": ";".join(src.get("countries", [])),
                "trees": ";".join(src.get("trees", []) or [str(x) for x in src.get("lines", [])]),
                "role": src.get("role", ""),
                "url": api.get("base") or api.get("landing") or src.get("landing", ""),
                "verification_status": ver.get("status", ""),
                "verification_checked": ver.get("checked", ""),
                "last_update_observed": ver.get("last_update_observed", ""),
                "latest_vintage": ver.get("latest_vintage", ""),
                "concept_note": src.get("concept_note", ""),
                "notes": ver.get("note", ""),
            })
    return dest
