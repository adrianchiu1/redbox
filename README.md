# gg-fiscal

<!-- GENERATED FILE (§11.6 deliverable 10): written by `ggfiscal report` at 2026-09-03 03:37 UTC, run 20260903T033630Z. Do not hand-edit — edits are overwritten on the next report run. -->

Reproducible pipeline producing, for the United Kingdom (GBR), France (FRA) and Germany (DEU): consolidated general-government **expenditure by COFOG function** (12 lines per country incl. the GF01_7/GF01_X interest split), **revenue by ESA type** (10 lines per country), the **balance ledger** (TR, TE, NLB, NI, PB), and a **reconciliation of history and forecast dynamics to the IMF WEO** general-government aggregates — 66 line series plus three ledgers, each extended backwards and forwards as far as compatible official sources permit (§1).

Governing principles: **maximise length subject to transparency and conceptual integrity**, and **decompose, never force** — no line is ever scaled or adjusted to hit a WEO aggregate (D13, D16).

**The specification is [`COFOG_KICKOFF.md`](COFOG_KICKOFF.md) (v2.2). It governs.** Working state lives in [`HANDOFF.md`](HANDOFF.md); the append-only decision log in [`DECISIONS.md`](DECISIONS.md); committee items in [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md).

## Setup and pipeline

```
pip install -e .[dev]
ggfiscal fetch --all        # harvest every registered source (D8 snapshots)
ggfiscal build              # standard layer -> canonical trees, ledger, stitches, forecasts
ggfiscal reconcile          # §8.2-8.5: bridge, decomposition, residual history
ggfiscal report             # small multiples, reconciliation + validation reports, README
ggfiscal validate           # §10 suite -> exceptions.csv (exit 1 on ERROR)
ggfiscal detect-vintages    # §11.7 live-metadata diff -> reports/vintage_diff.md
pytest                      # per-stage gate tests
```

Raw snapshots are content-addressed and **not committed** (D-S0-004): a fresh clone needs `ggfiscal fetch --all` before building; provenance is preserved in `data/manifest/` (full sha256 per pull and per deliverable).

## Layout (§11.2)

```
config/          countries.yaml, lines.yaml, sources.yaml (incl. the WEO vintage register), residual.yaml
crosswalks/      versioned source-to-target mappings (§11.5)
data/            raw -> manual -> standard -> canonical -> manifest (§11.1)
src/ggfiscal/    ingest | standardise | stitch | forecast | reconcile | validate | report
tests/           per-stage gate suites (tests/stage_0 ... tests/stage_6)
reports/         verification, validation, reconciliation, vintage diff
```

## Stage status

Stages 0–6 complete, all hard gates passed (§12): harvest and source verification; canonical history for both trees; backward extension; strict forecasts; maximum-extension forecasts; the WEO reconciliation module; packaging and vintage re-run. Every stitched value is reproducible from its anchor and recorded growth using the deliverables alone (Gate 6, tested in `tests/stage_6`).

## Deliverables (§11.6)

| file | rows | description |
|---|---|---|
| `data/canonical/expenditure_long_strict.csv` | 1436 | COFOG tree, §5 long format (12 lines + TE per country) |
| `data/canonical/expenditure_long_strict.parquet` | — | COFOG tree, §5 long format (12 lines + TE per country) |
| `data/canonical/expenditure_long_maximum_extension.csv` | 1540 | COFOG tree, §5 long format (12 lines + TE per country) |
| `data/canonical/expenditure_long_maximum_extension.parquet` | — | COFOG tree, §5 long format (12 lines + TE per country) |
| `data/canonical/revenue_long_strict.csv` | 1246 | ESA revenue tree, §5 long format (10 lines + TR per country) |
| `data/canonical/revenue_long_strict.parquet` | — | ESA revenue tree, §5 long format (10 lines + TR per country) |
| `data/canonical/revenue_long_maximum_extension.csv` | 1366 | ESA revenue tree, §5 long format (10 lines + TR per country) |
| `data/canonical/revenue_long_maximum_extension.parquet` | — | ESA revenue tree, §5 long format (10 lines + TR per country) |
| `data/canonical/balance_ledger.csv` | 196 | TR, TE, NLB, NI, PB per (country, year, variant), §4.3 |
| `data/canonical/balance_ledger.parquet` | — | TR, TE, NLB, NI, PB per (country, year, variant), §4.3 |
| `data/canonical/weo_base_bridge.csv` | 286 | §8.2 base-year level bridge per (country, WEO vintage) |
| `data/canonical/deficit_dynamics.csv` | 4002 | §8.3 history decomposition (drivers of Δ(NLB/GDP)) |
| `data/canonical/weo_explanation.csv` | 1636 | §8.3 forecast decomposition with residuals + denominator effect |
| `data/canonical/weo_residual_history.csv` | 296 | §8.5 residual time series across WEO vintages |
| `data/canonical/net_interest_check.csv` | 112 | §8.4 net-interest cross-check per (country, vintage, horizon) |
| `data/canonical/coverage_matrix.csv` | 66 | §11.6(9): span, grades, sources, why each of the 66 series ends |
| `data/canonical/crosswalks.csv` | 38 | §11.5 crosswalks concatenated (one row per mapping, keyed by file) |
| `data/canonical/exceptions.csv` | 716 | §10 validation findings (all rows, all severities) |
| `data/canonical/stitch_boundaries.csv` | 32 | §7.4 backward-stitch boundary records incl. non-applications |
| `data/canonical/forecast_boundaries.csv` | 29 | §7.4 forward boundary records incl. withheld joins (V16) |
| `data/canonical/forecast_declarations.csv` | 57 | D7/Gate 3: why each line carries no strict forecast |
| `reports/source_register.csv` | 29 | §6.4 register generated from config/sources.yaml |
| `reports/validation_report.html` | — | §10 suite rendered (summary, per-check outcomes, WARN tiers) |
| `reports/reconciliation_report.html` | — | §10/Gate 5 contribution charts + explained shares |
| `reports/vintage_diff.md` | — | §11.7 live-metadata diff against the register |
| `README.md` | — | this file (generated) |

## Coverage (66 line series)

Spans per line and variant, from `coverage_matrix.csv` (which adds stitch counts, principal sources, residual methods and the recorded reason each series ends). A *final strict* / *final maximum* year no later than the final actual means the series ends at its last actual — a D7 declaration or a blocked/withheld source, with the reason recorded per line in `forecast_declarations.csv`.

### GBR

| line | first year | final actual | final strict | final maximum | grades |
|---|---|---|---|---|---|
| GF01 | 1995 | 2025 | 2024 | 2027 | AD |
| GF01_7 | 1987 | 2025 | 2027 | 2027 | AB |
| GF01_X | 1995 | 2024 | 2024 | 2024 | A |
| GF02 | 1995 | 2024 | 2024 | 2024 | A |
| GF03 | 1995 | 2024 | 2024 | 2024 | A |
| GF04 | 1995 | 2024 | 2024 | 2024 | A |
| GF05 | 1995 | 2024 | 2024 | 2024 | A |
| GF06 | 1995 | 2024 | 2024 | 2024 | A |
| GF07 | 1995 | 2024 | 2024 | 2024 | A |
| GF08 | 1995 | 2024 | 2024 | 2024 | A |
| GF09 | 1995 | 2024 | 2024 | 2024 | A |
| GF10 | 1995 | 2025 | 2024 | 2027 | AC |
| R01 | 1973 | 2025 | 2025 | 2025 | AB |
| R02 | 1965 | 2025 | 2025 | 2025 | AC |
| R03 | 1965 | 2025 | 2025 | 2025 | AB |
| R04 | 1965 | 2025 | 2025 | 2025 | AB |
| R05 | 1990 | 2025 | 2025 | 2025 | A |
| R06 | 1965 | 2025 | 2027 | 2027 | AC |
| R07 | 1990 | 2025 | 2025 | 2025 | A |
| R08 | 1990 | 2025 | 2025 | 2025 | A |
| R09 | 1990 | 2025 | 2025 | 2025 | A |
| R10 | 1990 | 2025 | 2025 | 2025 | A |

### FRA

| line | first year | final actual | final strict | final maximum | grades |
|---|---|---|---|---|---|
| GF01 | 1995 | 2025 | 2024 | 2027 | AD |
| GF01_7 | 1978 | 2025 | 2027 | 2027 | AB |
| GF01_X | 1995 | 2024 | 2024 | 2024 | A |
| GF02 | 1995 | 2024 | 2024 | 2024 | A |
| GF03 | 1995 | 2024 | 2024 | 2024 | A |
| GF04 | 1995 | 2024 | 2024 | 2024 | A |
| GF05 | 1995 | 2024 | 2024 | 2024 | A |
| GF06 | 1995 | 2024 | 2024 | 2024 | A |
| GF07 | 1995 | 2024 | 2070 | 2070 | AB |
| GF08 | 1995 | 2024 | 2024 | 2024 | A |
| GF09 | 1995 | 2024 | 2070 | 2070 | AB |
| GF10 | 1995 | 2025 | 2024 | 2070 | AC |
| R01 | 1965 | 2025 | 2025 | 2025 | AB |
| R02 | 1995 | 2025 | 2025 | 2025 | A |
| R03 | 1965 | 2025 | 2025 | 2025 | AB |
| R04 | 1965 | 2025 | 2025 | 2025 | AC |
| R05 | 1995 | 2025 | 2025 | 2027 | AC |
| R06 | 1965 | 2025 | 2027 | 2027 | AC |
| R07 | 1995 | 2025 | 2025 | 2025 | A |
| R08 | 1995 | 2025 | 2025 | 2025 | A |
| R09 | 1995 | 2025 | 2027 | 2027 | AB |
| R10 | 1995 | 2025 | 2025 | 2025 | A |

### DEU

| line | first year | final actual | final strict | final maximum | grades |
|---|---|---|---|---|---|
| GF01 | 1991 | 2025 | 2024 | 2027 | ABD |
| GF01_7 | 1991 | 2025 | 2027 | 2027 | AB |
| GF01_X | 1991 | 2024 | 2024 | 2024 | AB |
| GF02 | 1991 | 2024 | 2024 | 2024 | AB |
| GF03 | 1991 | 2024 | 2024 | 2024 | AB |
| GF04 | 1991 | 2024 | 2024 | 2024 | AB |
| GF05 | 1991 | 2024 | 2024 | 2024 | AB |
| GF06 | 1991 | 2024 | 2024 | 2024 | AB |
| GF07 | 1991 | 2024 | 2070 | 2070 | AB |
| GF08 | 1991 | 2024 | 2024 | 2024 | AB |
| GF09 | 1991 | 2024 | 2070 | 2070 | AB |
| GF10 | 1991 | 2025 | 2024 | 2070 | ABC |
| R01 | 1991 | 2025 | 2030 | 2030 | AB |
| R02 | 1991 | 2025 | 2025 | 2025 | AB |
| R03 | 1991 | 2025 | 2030 | 2030 | AB |
| R04 | 1991 | 2025 | 2030 | 2030 | ABC |
| R05 | 1991 | 2025 | 2025 | 2025 | AB |
| R06 | 1991 | 2025 | 2027 | 2027 | AC |
| R07 | 1995 | 2025 | 2025 | 2025 | A |
| R08 | 1995 | 2025 | 2025 | 2025 | A |
| R09 | 1995 | 2025 | 2027 | 2027 | AB |
| R10 | 1995 | 2025 | 2025 | 2025 | A |

## Validation

Last `ggfiscal validate`: **ERROR=0, WARN=661, OK=55, SKIP=0** (all 28 §10 checks run; ERROR blocks the gate, WARN does not). The WARN tiers are intended visibility: documented concept wedges (V1/V21/V25), the withheld DSM interest join flagged for the committee (V16 → OQ-7), blocked register URLs (V18 → OQ-6), stitch diagnostics at measured grades (V5), and unsynced raw bytes of earlier sessions (S0_SNAPSHOTS, D-S0-004). Details: `reports/validation_report.html`.

## WEO reconciliation headline

How much of the WEO balance change (latest vintage 2026-04) the covered official granular forecasts explain — `explained_share` range across horizon years (D-S5-004):

| country | strict | maximum_extension |
|---|---|---|
| GBR | 0.00 … 0.05 | -0.01 … 0.06 |
| FRA | -0.05 … 1.13 | -2.70 … 0.11 |
| DEU | -0.20 … 0.17 | 0.38 … 0.56 |

Residuals are reported, never allocated or forced (D13, D16, §8.6): GBR is nearly unexplained while OBR is unreachable (OQ-6), and the projected French consolidation sits entirely in the residuals — the covered French forecasts move the other way. Charts and tables: `reports/reconciliation_report.html`.

## Vintage re-run (§11.7)

WEO vintages registered and reconciled: 2026-04, 2025-10, 2025-04 (the IMF API exposes exactly these; earliest noted per Q11/D-S0-007). `ggfiscal detect-vintages` diffs live source metadata against the register (`--hash` re-downloads and compares content hashes); a new WEO edition is registered by adding one entry to `config/sources.yaml` (`IMF_WEO.api.vintages`) and re-running fetch/build/reconcile/report — **a config change plus rebuild, never a code change** — and must be snapshotted promptly because the API drops old editions (D-S0-007). The demonstration with a simulated new edition lives in `tests/stage_6/test_vintages.py`.

## Known limits awaiting the committee

- **OQ-6** — obr.uk (Cloudflare challenge), gov.uk, bmas.de (egress policy) are unreachable: every GBR-specific forecast source is blocked, so GBR strict forecasts are AMECO-only and the GBR explained share is ~0. Unblocking OBR would transform it.
- **OQ-7** — the AMECO→DSM long-term interest join is withheld (V16 overlap divergence above threshold, D12): FRA/DEU GF01_7 strict ends 2027 pending adjudication.
- **OQ-5** — pre-1995 expenditure archives need §11.4 manual ingestion (independent second keying) or machine-readable archive endpoints.
