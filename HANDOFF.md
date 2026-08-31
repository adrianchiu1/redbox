# HANDOFF.md

Rewritten 2026-08-31, end of session 2 (network-enabled).

## Current stage

**Stage 0 (verify and harvest) — COMPLETE. Gate 0 PASSED.**

## Gate 0 status: PASSED

| Gate 0 requirement | Status |
|---|---|
| Endpoints confirmed (incl. IMF 2025 portal migration) | **Done.** All machine-readable §13 endpoints resolved against live catalogs and harvested; the 4 previously-open dataflow ids pinned (IMF `IMF.STA:GFS_COFOG(11.0.0)` + `GFS_SOO(12.0.0)`; OECD `DSD_NASEC10@DF_TABLE11,1.1`; ONS receipts = ESA Table 2; ONS interest = same file's D.41 rows). See D-S0-006 and `reports/source_verification.md`. |
| All anchors + WEO + GFS + OECD RS/T11 + AMECO pulled as D8 snapshots | **Done.** `ggfiscal fetch --all`: 75 pulls, 0 failures; content-hashed snapshots in `data/raw/` (gitignored per D-S0-004), provenance in `data/manifest/snapshots.jsonl` (committed). |
| 66 lines with programmatic coverage → `coverage_matrix_v0.csv` | **Done.** 66/66 lines measured from ≥1 source; 174 (line, source) rows with first/last usable year and n_years. `ggfiscal coverage` regenerates. |
| §8.2 base-year bridge, 3 countries, latest WEO vintage | **Done** — and for all 3 harvested vintages (9 country-vintage pairs). Latest (2026-04): GBR b=2025, FRA b=2024, DEU b=2025. `data/canonical/weo_base_bridge.csv`; `ggfiscal reconcile` regenerates. D-S0-009. |
| `reports/source_verification.md` | **Done**: every machine entry confirmed_live with release dates; stale/superseded items flagged (RSGLOBAL→RSOECD, ONS tax list stale, AMECO-UK envelope gap, WEO 3-vintage retention). |

Checks: `pytest` 28 passed; `ggfiscal validate` OK=5 SKIP=28, **no ERROR, no
WARN**. Stage 0 recon diagnostics: `reports/recon_anchor_vs_imf_v0.csv`
(anchor vs GFS ≈ 0%), `reports/recon_anchor_vs_oecd_rs_v0.csv` (concept
wedges quantified for the Stage 2 crosswalk).

## Q11 pinned (D-S0-007)

The IMF API exposes exactly **3** WEO vintages today — 2026-04 (WEO/9.0.0,
publication 2026-04-14), 2025-10 (WEO_2025_OCT_VINTAGE/1.0.0), 2025-04
(WEO/6.0.0) — fewer than the 5–10 target; per Q11's fallback all three are
retained, earliest 2025-04. Old editions can drop off the API, so
`detect-vintages` (Stage 6) must snapshot new editions promptly (WEO Oct 2026
lands ~mid-October).

## Blocked on whom

**Nothing blocks Stage 1.** Two standing notes for the committee, neither
blocking: OQ-3 (raw-snapshot archival location), OQ-4 (AMECO has no UK TR/TE
levels — Stage 3 cross-check will be balance/interest only).

## What exists and is verified working

- Everything from session 1 (repo skeleton, configs, D8 snapshot store,
  validation runner with stage-gated SKIP semantics, register generator).
- `ggfiscal fetch --all` — the full Stage 0 harvest, per-country filtered
  Eurostat/OECD/GFS pulls, per-(country,subject) WEO pulls (attributes intact),
  AMECO chapter zips, ONS files incl. the new ESA T2 / NTL / YBHA sources.
- `src/ggfiscal/standardise/readers.py` — snapshot → tidy series for every
  harvested source, with unit normalisation to LCU millions (GFS raw units,
  OECD UNIT_MULT) verified against anchors (test: FRA GF02 anchor-vs-GFS
  < 0.5% every year).
- `src/ggfiscal/coverage.py` — measured coverage matrix + Gate 0 check.
- `src/ggfiscal/reconcile/bridge.py` (§8.2) and `recon_v0.py` (diagnostics).
- Validation: S0_COVERAGE and S0_BRIDGE gate checks added; V1–V28 still
  stage-gated SKIPs.

## Exact next command

Stage 1 (canonical history, both trees — §12): build the §5 data model +
pandera schema, anchoring, GF01 split, revenue identity, balance ledger, and
V1–V4, V7–V9, V12, V14, V19–V23. Start from:

```
pip install -e .[dev] && pytest && ggfiscal validate
```

then implement `ggfiscal standardise` and `ggfiscal build` (they currently
exit 2 as "arrives with Stage 1"). The readers in
`src/ggfiscal/standardise/readers.py` already deliver anchor series in LCU
millions; Stage 1 wraps them in the §5 long format. Watch items for Stage 1:
Eurostat 2025 main-aggregate values are provisional (final actual for COFOG
lines is 2024); ONS T2's D51M/D51O give the GBR R03/R04 split directly, but
the crosswalk (`crosswalks/ONS_RECEIPTS_to_ESA_REV.csv`) must still document
income tax/NICs/CT treatment from ONS_TAX_DETAIL before Gate 1.

## §15 dependencies currently riding on defaults

Q1 (nominal LCU primitive), Q3 (`grow_with_proxy`), Q4 (tolerances as tabled),
Q7 (defence plans strict-B if ≥90% GG), Q8 (keep uplift), **Q11 now pinned:
3 vintages retained (D-S0-007)**, Q12 (OBR primary for GBR §8.3 — reinforced
by OQ-4), Q13 (R06 single line). No default has been overridden.
