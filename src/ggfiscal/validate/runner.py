"""Validation runner (§10). ERROR blocks the gate; WARN does not.

V1–V28 operate on built data layers and register themselves with the stage
that first makes them runnable; until that stage's artifacts exist they are
reported as SKIP (not silently omitted, not ERROR). Stage 0 adds structural
checks S0_* that are runnable from config and the snapshot manifest alone.

All rows go to data/canonical/exceptions.csv (§11.6 deliverable 8).
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from ggfiscal import config
from ggfiscal.ingest.store import SnapshotStore


@dataclasses.dataclass
class Finding:
    check_id: str
    severity: str          # ERROR | WARN | SKIP | OK
    scope: str             # e.g. "GBR/GF02/2019" or "register/IMF_WEO" or "-"
    message: str


# The full §10 suite with the earliest stage at which each becomes runnable.
V_SUITE_STAGE = {
    "V1": 1, "V2": 1, "V3": 1, "V4": 1, "V5": 2, "V6": 2, "V7": 1, "V8": 1,
    "V9": 1, "V10": 3, "V11": 3, "V12": 1, "V13": 2, "V14": 1, "V15": 3,
    "V16": 3, "V17": 4, "V18": 3, "V19": 1, "V20": 1, "V21": 1, "V22": 1,
    "V23": 1, "V24": 5, "V25": 2, "V26": 1, "V27": 5, "V28": 5,
}


def current_stage() -> int:
    """Highest stage whose artifacts exist. Stage 0 until canonical data lands."""
    canonical = config.repo_root() / "data" / "canonical"
    if (canonical / "stitch_boundaries.csv").exists():
        return 2
    if (canonical / "expenditure_long_strict.parquet").exists():
        return 1
    return 0


def check_s0_line_universe() -> list[Finding]:
    universe = config.line_universe()
    n = len(universe)
    if n != 66:
        return [Finding("S0_LINES", "ERROR", "-",
                        f"line universe has {n} series; §1 requires 66")]
    return [Finding("S0_LINES", "OK", "-", "66 line series enumerated (3 countries x 22)")]


def check_s0_register() -> list[Finding]:
    out = []
    for sid, src in config.sources().items():
        ver = src.get("verification") or {}
        if not ver.get("status"):
            out.append(Finding("S0_REGISTER", "ERROR", f"register/{sid}",
                               "no verification status recorded"))
        if src.get("role") in ("anchor", "anchor_detail", "gdp", "reconciliation",
                               "reconciliation_only", "envelope", "backward_extension",
                               "secondary", "interest_history") \
                and not (src.get("api") or src.get("landing")):
            out.append(Finding("S0_REGISTER", "ERROR", f"register/{sid}",
                               "no api or landing recorded for a Stage 0 source"))
    if not out:
        out.append(Finding("S0_REGISTER", "OK", "-",
                           f"{len(config.sources())} register entries structurally complete"))
    return out


def check_s0_manifest_hashes() -> list[Finding]:
    store = SnapshotStore()
    entries = store.entries()
    if not entries:
        return [Finding("S0_SNAPSHOTS", "WARN", "-",
                        "no raw snapshots in manifest — harvest not yet run (OQ-1: egress blocked)")]
    out = []
    root = config.repo_root()
    for e in entries:
        path = root / e["path"]
        if not path.exists():
            out.append(Finding("S0_SNAPSHOTS", "WARN", e["source_id"],
                               f"snapshot file missing locally: {e['path']} (raw store not synced)"))
        elif not store.verify(path, e["sha256"]):
            out.append(Finding("S0_SNAPSHOTS", "ERROR", e["source_id"],
                               f"snapshot hash mismatch — immutability violated (D8): {e['path']}"))
    if not out:
        out.append(Finding("S0_SNAPSHOTS", "OK", "-", f"{len(entries)} snapshots verified"))
    return out


def check_s0_coverage() -> list[Finding]:
    """Gate 0: all 66 lines must have programmatically measured coverage."""
    from ggfiscal.coverage import gate0_line_coverage
    from ggfiscal.standardise.readers import latest_snapshots

    if not latest_snapshots():
        return [Finding("S0_COVERAGE", "WARN", "-",
                        "no snapshots — coverage not measurable yet")]
    covered, uncovered = gate0_line_coverage()
    if uncovered:
        return [Finding("S0_COVERAGE", "ERROR", f"{i}/{c}/{l}",
                        "line has no measurable source in the harvest (Gate 0)")
                for i, c, l in uncovered]
    return [Finding("S0_COVERAGE", "OK", "-",
                    f"{covered}/66 lines have measured coverage from >=1 source")]


def check_s0_bridge() -> list[Finding]:
    """Gate 0: §8.2 bridge computed for all three countries, latest WEO vintage."""
    import csv as _csv

    from ggfiscal.ingest.endpoints import WEO_VINTAGES

    latest = next(iter(WEO_VINTAGES))
    path = config.repo_root() / "data" / "canonical" / "weo_base_bridge.csv"
    if not path.exists():
        return [Finding("S0_BRIDGE", "WARN", "-",
                        "weo_base_bridge.csv not yet computed (run: ggfiscal reconcile)")]
    with open(path, encoding="utf-8") as f:
        rows = [r for r in _csv.DictReader(f) if r["weo_vintage"] == latest]
    out = []
    for iso3 in config.COUNTRIES:
        base = [r for r in rows if r["iso3"] == iso3 and r["is_base_year"] == "True"]
        if not base:
            out.append(Finding("S0_BRIDGE", "ERROR", f"{iso3}/{latest}",
                               "no base-year row in the §8.2 bridge (Gate 0)"))
    if not out:
        out.append(Finding("S0_BRIDGE", "OK", "-",
                           f"§8.2 bridge computed for all 3 countries on WEO {latest}"))
    return out


def run_all() -> list[Finding]:
    stage = current_stage()
    findings: list[Finding] = []
    findings += check_s0_line_universe()
    findings += check_s0_register()
    findings += check_s0_manifest_hashes()
    findings += check_s0_coverage()
    findings += check_s0_bridge()
    from ggfiscal.validate.stage1 import IMPLEMENTED as S1
    from ggfiscal.validate.stage2 import IMPLEMENTED as S2
    IMPLEMENTED = {**S1, **S2}
    for vid, first_stage in sorted(V_SUITE_STAGE.items(), key=lambda kv: int(kv[0][1:])):
        if stage < first_stage:
            findings.append(Finding(vid, "SKIP", "-",
                                    f"not runnable before stage {first_stage} (current stage {stage})"))
        elif vid in IMPLEMENTED:
            findings += IMPLEMENTED[vid]()
        else:
            findings.append(Finding(vid, "ERROR", "-",
                                    f"{vid} is due at stage {first_stage} but not yet implemented"))
    return findings


def write_exceptions(findings: list[Finding], path: Path | None = None) -> Path:
    dest = path or config.repo_root() / "data" / "canonical" / "exceptions.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["check_id", "severity", "scope", "message"])
        for fnd in findings:
            w.writerow([fnd.check_id, fnd.severity, fnd.scope, fnd.message])
    return dest
