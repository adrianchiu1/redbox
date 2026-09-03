"""Run-manifest completeness (§11.1, §11.6 deliverable 11; D-S6-003).

`ggfiscal build` writes the base manifest for a run (run id, per-file config
and crosswalk hashes, environment, and the full snapshot set the build
consumed). The later pipeline steps — `reconcile` and `report` — call
`update_deliverables()` on the SAME file, so the latest run manifest ends up
recording the sha256, byte size and row count of every §11.6 deliverable
actually on disk. Unchanged config + snapshots → byte-identical canonical
outputs (§16), and the manifest is the proof: it pins every input hash and
every output hash of the run.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import platform
from pathlib import Path

from ggfiscal import config

PIPELINE_STAGE = 6

# §11.6 deliverables (numbers per the spec list) + supporting canonical files.
# Paths relative to the repo root; missing files are recorded as absent so a
# partial run is visible rather than silently incomplete.
DELIVERABLES = [
    "data/canonical/expenditure_long_strict.csv",
    "data/canonical/expenditure_long_strict.parquet",
    "data/canonical/expenditure_long_maximum_extension.csv",
    "data/canonical/expenditure_long_maximum_extension.parquet",
    "data/canonical/revenue_long_strict.csv",
    "data/canonical/revenue_long_strict.parquet",
    "data/canonical/revenue_long_maximum_extension.csv",
    "data/canonical/revenue_long_maximum_extension.parquet",
    "data/canonical/balance_ledger.csv",
    "data/canonical/balance_ledger.parquet",
    "data/canonical/weo_base_bridge.csv",
    "data/canonical/deficit_dynamics.csv",
    "data/canonical/weo_explanation.csv",
    "data/canonical/weo_residual_history.csv",
    "data/canonical/net_interest_check.csv",
    "data/canonical/coverage_matrix.csv",
    "data/canonical/crosswalks.csv",
    "data/canonical/exceptions.csv",
    "data/canonical/stitch_boundaries.csv",
    "data/canonical/forecast_boundaries.csv",
    "data/canonical/forecast_declarations.csv",
    "reports/source_register.csv",
    "reports/validation_report.html",
    "reports/reconciliation_report.html",
    "reports/vintage_diff.md",
    "README.md",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_hashes() -> dict[str, str]:
    root = config.repo_root() / "config"
    return {p.name: _sha256(p) for p in sorted(root.glob("*.yaml"))}


def crosswalk_hashes() -> dict[str, str]:
    root = config.repo_root() / "crosswalks"
    return {p.name: _sha256(p) for p in sorted(root.glob("*.csv"))}


def _rows(path: Path) -> int | None:
    if path.suffix != ".csv":
        return None
    with open(path, encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def deliverable_entries() -> dict[str, dict]:
    root = config.repo_root()
    out: dict[str, dict] = {}
    for rel in DELIVERABLES:
        p = root / rel
        if not p.exists():
            out[rel] = {"present": False}
            continue
        out[rel] = {"present": True, "sha256": _sha256(p),
                    "bytes": p.stat().st_size}
        rows = _rows(p)
        if rows is not None:
            out[rel]["rows"] = rows
    return out


def manifest_dir() -> Path:
    return config.repo_root() / "data" / "manifest"


def run_path(run_id: str) -> Path:
    return manifest_dir() / f"run_{run_id}.json"


def latest_run_path() -> Path | None:
    runs = sorted(manifest_dir().glob("run_*.json"))
    return runs[-1] if runs else None


def write_base(run_id: str, snapshots: dict[str, str]) -> Path:
    """Called by `ggfiscal build`: pin every input of the run."""
    dest = run_path(run_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    import pandas

    import ggfiscal
    dest.write_text(json.dumps({
        "run_id": run_id,
        "stage": PIPELINE_STAGE,
        "written_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "environment": {
            "python": platform.python_version(),
            "pandas": pandas.__version__,
            "ggfiscal": getattr(ggfiscal, "__version__", "0.0.1"),
        },
        "config_files": config_hashes(),
        "crosswalk_files": crosswalk_hashes(),
        "snapshots": snapshots,
        "deliverables": {},
    }, indent=1, sort_keys=True))
    return dest


def update_deliverables(path: Path | None = None) -> Path | None:
    """Called at the end of `build`, `reconcile` and `report`: refresh the
    deliverable hashes of the latest run manifest to what is on disk now."""
    dest = path or latest_run_path()
    if dest is None:
        return None
    doc = json.loads(dest.read_text(encoding="utf-8"))
    doc["deliverables"] = deliverable_entries()
    doc["deliverables_updated_at"] = dt.datetime.now(
        dt.timezone.utc).isoformat(timespec="seconds")
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True))
    return dest
