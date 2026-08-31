"""Coverage matrix (§11.6 deliverable 9; v0 per §12 Stage 0).

coverage_matrix_v0.csv is *programmatically determined* from harvested data:
first/last usable year per (country, line, source). It is deliberately NOT
producible before the harvest — writing one by hand would fabricate coverage
(D13). Until snapshots exist this module emits the frame with the line
universe and per-line candidate sources from the register, with year fields
empty and status `awaiting_harvest`, so the target shape is pinned and diffable.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ggfiscal import config

V0_COLUMNS = [
    "iso3", "classification", "line_code",
    "candidate_sources",
    "first_historical_year", "final_actual_year",
    "first_forecast_year", "final_strict_year", "final_maximum_year",
    "status", "notes",
]


def candidate_sources_for(iso3: str, classification: str, line_code: str) -> list[str]:
    out = []
    for sid, src in config.sources().items():
        if iso3 not in src.get("countries", []):
            continue
        trees = src.get("trees", [])
        if classification == "COFOG" and "expenditure" in trees:
            out.append(sid)
        elif classification == "ESA_REV" and "revenue" in trees:
            out.append(sid)
    return out


def build_v0(path: Path | None = None) -> Path:
    store_has_data = bool((config.repo_root() / "data" / "manifest" / "snapshots.jsonl").exists())
    no_fc = config.no_forecast_lines()
    dest = path or config.repo_root() / "reports" / "coverage_matrix_v0.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=V0_COLUMNS)
        w.writeheader()
        for iso3, classification, line_code in config.line_universe():
            notes = []
            if classification == "COFOG" and line_code in no_fc["expenditure"]:
                notes.append("D7: no identified forecast source; declared at outset")
            if classification == "ESA_REV" and line_code in no_fc["revenue"]:
                notes.append("D7: no identified forecast source; declared at outset")
            if classification == "ESA_REV" and line_code in no_fc.get("revenue_partial", {}):
                notes.append(f"D7 partial: {no_fc['revenue_partial'][line_code]}")
            w.writerow({
                "iso3": iso3, "classification": classification, "line_code": line_code,
                "candidate_sources": ";".join(candidate_sources_for(iso3, classification, line_code)),
                "first_historical_year": "", "final_actual_year": "",
                "first_forecast_year": "", "final_strict_year": "", "final_maximum_year": "",
                "status": "harvested_pending_measurement" if store_has_data else "awaiting_harvest",
                "notes": " | ".join(notes),
            })
    return dest
