# HANDOFF.md

Rewritten 2026-08-31, end of session 3 (Stage 3 completed on
`claude/repo-review-stage-3-xamnht`; Stages 0–2 were completed in session 2
and merged via PR #1).

## Current stage

**Stage 3 (strict forecasts) — COMPLETE. Gate 3 PASSED.**

## Gate 3 status: PASSED

| Gate 3 requirement | Status |
|---|---|
| Every strict forecast row A or B with measured coverage | **Done.** 215 strict forecast rows across 15 (country, line) series, every one grade A or B with `coverage_share` + year measured per §9.2 (see `data/canonical/forecast_boundaries.csv`); plus 3 newer-actual 2025 interest stitches (§7.2). C/D measurements recorded as `not_applied_*`, never applied. |
| Every D7 line has its note | **Done.** `data/canonical/forecast_declarations.csv`: 57 rows covering every (country, line) without an applied forecast — D7 declarations, blocked-source notes (OQ-6), below-strict-grade records, and the never-extended totals. Tested (tests/stage_3). |
| V-tests green | **Done.** V10, V11, V15, V18 implemented; V13 and V6 extended to forward stitches; V16 implemented and firing (see below). `pytest`: **56 passed**. `ggfiscal validate`: OK=49 SKIP=4 WARN=582, **no ERROR**. |

WARN tiers are all expected-documentation: V1 GFS wedges, V21 interest
wedges, V5 proxy diagnostics, V25 RS wedges (Stage 2 carry-overs, unchanged),
plus new **V16** (the withheld DSM join, OQ-7), **V18** (blocked/unverified
register entries — intended visibility of OQ-6), and S0_SNAPSHOTS notices for
session-2 manifest entries whose raw bytes were never committed (D-S0-004;
this session's fresh harvest verifies clean).

## What Stage 3 added

Strict forecasts (mirrored into maximum_extension, which Stage 4 will extend
further): GF01_7 to 2027 all three (AMECO UYIG, B; 2025 stitched as newer
actual); R06 to 2027 all three (AMECO UTSG, the one grade-A source: same
D.61 aggregate at coverage 0.999–1.000); R09 to 2027 FRA/DEU (AMECO
UTOG−UROG sales composite, coverage exactly 1.0); DEU R01/R03/R04 to 2030
(Steuerschätzung May 2026, B at 0.999/0.979/0.946 — Soli split by payer from
the source's own Tab 8.2, Gewerbesteuer in R04 per the national tax list);
FRA/DEU GF07 and GF09 annual to **2070** (Ageing Report 2024 baseline, %GDP
per §7.5 with constructed nominal GDP). Engine: `src/ggfiscal/forecast/`
(§7.2 chaining, §7.5, §7.8 composites, §7.10 FY→CY ready-but-unused, D11
both methods, D12 ordering with the V16 guard). New crosswalks v1.0:
EC_AMECO_to_ESA_REV, EC_DSM_to_INTEREST, EC_AGEING_to_COFOG,
DEU_STEUERSCHAETZUNG_to_ESA_REV.

Not applied, recorded with measurements: GF10 AR composites (C: 0.685/0.611),
R05 everywhere (0.11–0.76), GBR R09 (unmeasurable), and the DSM 2028–2036
interest leg (D12/V16 divergence — committee item OQ-7).

## Blocked on whom

- **OQ-6 (committee/infra):** obr.uk Cloudflare challenge + gov.uk/bmas.de
  egress denials block ALL GBR-specific forecasts (GF02, GF07, GF09, GF10,
  R01–R04, R07) and DEU GF10's BMAS leg. Q12's OBR-primary envelope runs on
  the AMECO cross-check meanwhile.
- **OQ-7 (committee):** approve/reject the AMECO→DSM interest join (options
  enumerated; any choice is config-only).
- **OQ-5 (standing):** §11.4 second keying — now also gates FRA tax lines
  and all three GF02 lines.
Nothing blocks Stage 4 (maximum-extension forecasts) on the harvested
sources: the C-grade records in `forecast_boundaries.csv` are its queue.

## Exact next command

Stage 4 (maximum-extension forecasts — §12): apply the recorded C-grade
sources (GF10 ← AR pensions+LTC for FRA/DEU; R05 ← UTKG for FRA), add
proxies with explicit `residual_method` from `config/residual.yaml` (§15 Q3
default `grow_with_proxy`), `GF01` via `GF01_7` growth (§7.9), grades C/D,
V17, and complete `coverage_matrix.csv` (§11.6 deliverable 9). Variants must
stay distinguishable row-by-row with no leakage (Gate 4).

```
pip install -e .[dev] && ggfiscal fetch --all && ggfiscal build && pytest && ggfiscal validate
```

(`fetch --all` is needed in a fresh container — raw snapshots are not
committed, D-S0-004. It now includes the four Stage 3 pulls; the EC document
store requires the browser-like headers already encoded in the pulls.)

## Data facts Stage 4+ must not rediscover

- AMECO Spring 2026: horizon 2027, last actual 2025; UTSG is D.61 exactly
  (A); UTOG−UROG is sales exactly (FRA/DEU); **no UK** UTOG/UROG/URTG/UUTG
  history (OQ-4) — UK envelope levels exist for 2026–27 only.
- AR 2024 statistical annex is ANNUAL 2022–2070 (no D11 interpolation
  needed); no nominal GDP or deflator published — construct growth as
  (1+potential)(1+HICP) per §7.5 (D-S3-002). AR total cost of ageing =
  pensions + health + LTC + education exactly (no unemployment item).
- Steuerschätzung xlsx: Kasse series (not Tab 8.1 brutto — D17 wedge puts
  brutto composites out of band); Tab 8.2 has the official Soli payer split;
  Tab 7 Gewerbesteuer brutto forecasts to 2030; Ländersteuern/Gemeindesteuern
  exist only as mixed-code aggregates (no R02/R05 path).
- DSM 2025 fiches: interest %GDP + real growth + inflation rows per country
  sheet to 2036; label column varies (readers handle it); published
  2026-02-12, superseded ~Feb 2027 (V11 watch, as is the next
  Steuerschätzung session and a possible 2027 AR).
- V6 is direction-aware: backward rows verified in stage2, forward rows in
  stage3 against the live forecast specs.
- Gate 2's stitch_boundaries.csv invariants are untouched — forward records
  live in forecast_boundaries.csv.

## §15 dependencies currently riding on defaults

Q1, Q3, Q4 (D-S2-002 for V5; **D-S3-005 for V16 = 0.02**), Q7 (defence
plans: moot until a source is reachable — OQ-6), Q8, Q13 on defaults;
Q11 pinned (D-S0-007); **Q12 deviated by necessity**: OBR-primary envelope
impossible while obr.uk is blocked, AMECO cross-check serving as the GBR
envelope (D-S3-001, OQ-6).
