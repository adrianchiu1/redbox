"""Generated README.md (§11.6 deliverable 10, Stage 6; D-S6-004).

`ggfiscal report` regenerates README.md from the spec constants, the config,
and the canonical deliverables on disk — coverage spans from
coverage_matrix.csv, deliverable inventory from the manifest module's list,
validation counts from exceptions.csv, the reconciliation headline from
weo_explanation.csv. Hand-edits do not survive a rebuild; the narrative
documents live in COFOG_KICKOFF.md / HANDOFF.md / DECISIONS.md /
OPEN_QUESTIONS.md.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from ggfiscal import config
from ggfiscal import manifest as M
from ggfiscal.ingest.endpoints import weo_vintages

DESCRIPTIONS = {
    "expenditure_long": "COFOG tree, §5 long format (12 lines + TE per country)",
    "revenue_long": "ESA revenue tree, §5 long format (10 lines + TR per country)",
    "balance_ledger": "TR, TE, NLB, NI, PB per (country, year, variant), §4.3",
    "weo_base_bridge": "§8.2 base-year level bridge per (country, WEO vintage)",
    "deficit_dynamics": "§8.3 history decomposition (drivers of Δ(NLB/GDP))",
    "weo_explanation": "§8.3 forecast decomposition with residuals + denominator effect",
    "weo_residual_history": "§8.5 residual time series across WEO vintages",
    "net_interest_check": "§8.4 net-interest cross-check per (country, vintage, horizon)",
    "coverage_matrix": "§11.6(9): span, grades, sources, why each of the 66 series ends",
    "crosswalks": "§11.5 crosswalks concatenated (one row per mapping, keyed by file)",
    "exceptions": "§10 validation findings (all rows, all severities)",
    "stitch_boundaries": "§7.4 backward-stitch boundary records incl. non-applications",
    "forecast_boundaries": "§7.4 forward boundary records incl. withheld joins (V16)",
    "forecast_declarations": "D7/Gate 3: why each line carries no strict forecast",
    "source_register": "§6.4 register generated from config/sources.yaml",
    "validation_report": "§10 suite rendered (summary, per-check outcomes, WARN tiers)",
    "reconciliation_report": "§10/Gate 5 contribution charts + explained shares",
    "vintage_diff": "§11.7 live-metadata diff against the register",
    "README": "this file (generated)",
}


def _describe(rel: str) -> str:
    stem = Path(rel).stem
    for key, desc in DESCRIPTIONS.items():
        if stem.startswith(key):
            return desc
    return ""


def _fmt_int(v) -> str:
    try:
        if pd.isna(v):
            return "—"
        return str(int(v))
    except (TypeError, ValueError):
        return "—"


def _coverage_section(root: Path) -> list[str]:
    cm = pd.read_csv(root / "data" / "canonical" / "coverage_matrix.csv")
    out = []
    for iso3 in config.COUNTRIES:
        out += [f"### {iso3}", "",
                "| line | first year | final actual | final strict | "
                "final maximum | grades |",
                "|---|---|---|---|---|---|"]
        sub = cm[cm.iso3 == iso3]
        for _, r in sub.iterrows():
            out.append("| {} | {} | {} | {} | {} | {} |".format(
                r.line_code, _fmt_int(r.first_historical_year),
                _fmt_int(r.final_actual_year), _fmt_int(r.final_strict_year),
                _fmt_int(r.final_maximum_year),
                r.grades if isinstance(r.grades, str) else "—"))
        out.append("")
    return out


def _validation_section(root: Path) -> list[str]:
    exc = root / "data" / "canonical" / "exceptions.csv"
    if not exc.exists():
        return ["`exceptions.csv` not yet written — run `ggfiscal validate`.", ""]
    with open(exc, encoding="utf-8", newline="") as f:
        counts = Counter(r["severity"] for r in csv.DictReader(f))
    line = ", ".join(f"{k}={counts.get(k, 0)}" for k in ("ERROR", "WARN", "OK", "SKIP"))
    return [
        f"Last `ggfiscal validate`: **{line}** (all 28 §10 checks run; ERROR "
        "blocks the gate, WARN does not). The WARN tiers are intended "
        "visibility: documented concept wedges (V1/V21/V25), the withheld "
        "DSM interest join flagged for the committee (V16 → OQ-7), blocked "
        "register URLs (V18 → OQ-6), stitch diagnostics at measured grades "
        "(V5), and unsynced raw bytes of earlier sessions (S0_SNAPSHOTS, "
        "D-S0-004). Details: `reports/validation_report.html`.",
        "",
    ]


def _reconciliation_section(root: Path) -> list[str]:
    exp = pd.read_csv(root / "data" / "canonical" / "weo_explanation.csv")
    latest = next(iter(weo_vintages()))
    es = exp[(exp.component_kind == "explained_share")
             & (exp.weo_vintage == latest)]
    out = [
        f"How much of the WEO balance change (latest vintage {latest}) the "
        "covered official granular forecasts explain — `explained_share` "
        "range across horizon years (D-S5-004):",
        "",
        "| country | strict | maximum_extension |",
        "|---|---|---|",
    ]
    for iso3 in config.COUNTRIES:
        cells = []
        for variant in ("strict", "maximum_extension"):
            s = es[(es.iso3 == iso3) & (es.series_variant == variant)
                   ].contribution_pp
            cells.append(f"{s.min():.2f} … {s.max():.2f}" if len(s) else "—")
        out.append(f"| {iso3} | {cells[0]} | {cells[1]} |")
    out += [
        "",
        "Residuals are reported, never allocated or forced (D13, D16, §8.6): "
        "the GBR share runs on the hand-retrieved OBR EFO March 2026 "
        "composites through 2030 (D-S7-003; ~0 beyond the OBR horizon), and "
        "the projected French consolidation sits entirely in the residuals — "
        "the covered French forecasts move the other way. Charts and tables: "
        "`reports/reconciliation_report.html`.",
        "",
    ]
    return out


def write(path: Path | None = None) -> Path:
    root = config.repo_root()
    dest = path or root / "README.md"
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run = M.latest_run_path()
    run_id = (json.loads(run.read_text())["run_id"] if run else "—")
    vintages = ", ".join(weo_vintages())

    lines = [
        "# gg-fiscal",
        "",
        f"<!-- GENERATED FILE (§11.6 deliverable 10): written by `ggfiscal "
        f"report` at {now}, run {run_id}. Do not hand-edit — edits are "
        "overwritten on the next report run. -->",
        "",
        "Reproducible pipeline producing, for the United Kingdom (GBR), "
        "France (FRA) and Germany (DEU): consolidated general-government "
        "**expenditure by COFOG function** (12 lines per country incl. the "
        "GF01_7/GF01_X interest split), **revenue by ESA type** (10 lines "
        "per country), the **balance ledger** (TR, TE, NLB, NI, PB), and a "
        "**reconciliation of history and forecast dynamics to the IMF WEO** "
        "general-government aggregates — 66 line series plus three ledgers, "
        "each extended backwards and forwards as far as compatible official "
        "sources permit (§1).",
        "",
        "Governing principles: **maximise length subject to transparency and "
        "conceptual integrity**, and **decompose, never force** — no line is "
        "ever scaled or adjusted to hit a WEO aggregate (D13, D16).",
        "",
        "**The specification is [`COFOG_KICKOFF.md`](COFOG_KICKOFF.md) "
        "(v2.2). It governs.** Working state lives in "
        "[`HANDOFF.md`](HANDOFF.md); the append-only decision log in "
        "[`DECISIONS.md`](DECISIONS.md); committee items in "
        "[`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md).",
        "",
        "## Setup and pipeline",
        "",
        "```",
        "pip install -e .[dev]",
        "ggfiscal fetch --all        # harvest every registered source (D8 snapshots)",
        "ggfiscal build              # standard layer -> canonical trees, ledger, stitches, forecasts",
        "ggfiscal reconcile          # §8.2-8.5: bridge, decomposition, residual history",
        "ggfiscal report             # small multiples, reconciliation + validation reports, README",
        "ggfiscal validate           # §10 suite -> exceptions.csv (exit 1 on ERROR)",
        "ggfiscal detect-vintages    # §11.7 live-metadata diff -> reports/vintage_diff.md",
        "pytest                      # per-stage gate tests",
        "```",
        "",
        "Raw snapshots are content-addressed and **not committed** "
        "(D-S0-004): a fresh clone needs `ggfiscal fetch --all` before "
        "building; provenance is preserved in `data/manifest/` (full sha256 "
        "per pull and per deliverable).",
        "",
        "## Layout (§11.2)",
        "",
        "```",
        "config/          countries.yaml, lines.yaml, sources.yaml (incl. the WEO vintage register), residual.yaml",
        "crosswalks/      versioned source-to-target mappings (§11.5)",
        "data/            raw -> manual -> standard -> canonical -> manifest (§11.1)",
        "src/ggfiscal/    ingest | standardise | stitch | forecast | reconcile | validate | report",
        "tests/           per-stage gate suites (tests/stage_0 ... tests/stage_6)",
        "reports/         verification, validation, reconciliation, vintage diff",
        "```",
        "",
        "## Stage status",
        "",
        "Stages 0–6 complete, all hard gates passed (§12): harvest and source "
        "verification; canonical history for both trees; backward extension; "
        "strict forecasts; maximum-extension forecasts; the WEO "
        "reconciliation module; packaging and vintage re-run. Every stitched "
        "value is reproducible from its anchor and recorded growth using the "
        "deliverables alone (Gate 6, tested in `tests/stage_6`).",
        "",
        "## Deliverables (§11.6)",
        "",
        "| file | rows | description |",
        "|---|---|---|",
    ]
    for rel, entry in M.deliverable_entries().items():
        if not entry.get("present"):
            lines.append(f"| `{rel}` | — | MISSING |")
            continue
        rows = entry.get("rows")
        lines.append(f"| `{rel}` | {rows if rows is not None else '—'} "
                     f"| {_describe(rel)} |")
    lines += [
        "",
        "## Coverage (66 line series)",
        "",
        "Spans per line and variant, from `coverage_matrix.csv` (which adds "
        "stitch counts, principal sources, residual methods and the recorded "
        "reason each series ends). A *final strict* / *final maximum* year "
        "no later than the final actual means the series ends at its last "
        "actual — a D7 declaration or a blocked/withheld source, with the "
        "reason recorded per line in `forecast_declarations.csv`.",
        "",
        *_coverage_section(root),
        "## Validation",
        "",
        *_validation_section(root),
        "## WEO reconciliation headline",
        "",
        *_reconciliation_section(root),
        "## Vintage re-run (§11.7)",
        "",
        f"WEO vintages registered and reconciled: {vintages} (the IMF API "
        "exposes exactly these; earliest noted per Q11/D-S0-007). "
        "`ggfiscal detect-vintages` diffs live source metadata against the "
        "register (`--hash` re-downloads and compares content hashes); a new "
        "WEO edition is registered by adding one entry to "
        "`config/sources.yaml` (`IMF_WEO.api.vintages`) and re-running "
        "fetch/build/reconcile/report — **a config change plus rebuild, "
        "never a code change** — and must be snapshotted promptly because "
        "the API drops old editions (D-S0-007). The demonstration with a "
        "simulated new edition lives in `tests/stage_6/test_vintages.py`.",
        "",
        "## Known limits awaiting the committee",
        "",
        "- **OQ-6 (partially resolved 2026-09-05)** — gov.uk and bmas.de "
        "are allowlisted and OBR files were hand-retrieved (D-S7-001/002), "
        "so GBR strict now runs on OBR EFO March 2026 + PESA 2026. Still "
        "open: obr.uk itself remains challenge-blocked (each new EFO needs "
        "the manual route), an FRS edition with functional long-term "
        "projections would unlock GBR GF07/GF09/GF10 long legs, and the "
        "BMAS Rentenversicherungsbericht is PDF-only (OQ-5 gate).",
        "- **OQ-7 (resolved 2026-09-05, D-S8-001)** — the committee "
        "approved the above-threshold D12 joins via "
        "`tolerances.v16_approved_joins`: FRA/DEU GF01_7 runs to 2036 "
        "(DSM, strict) and GBR R06 to 2030 (OBR NICs, maximum — grade C "
        "stays out of strict). V16 keeps warning on the seams by design; "
        "the next DSM/EFO vintages should shrink them.",
        "- **OQ-5** — pre-1995 expenditure archives need §11.4 manual "
        "ingestion (independent second keying) or machine-readable archive "
        "endpoints.",
        "",
    ]
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest
