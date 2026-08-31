# HANDOFF.md

Rewritten 2026-08-31, end of session 2 (Stages 0, 1 and 2 all completed this
session, sequentially, on `claude/gg-fiscal-stage-0-harvest-de9qld`).

## Current stage

**Stage 2 (backward extension) — COMPLETE. Gate 2 PASSED.**
(Gates 0 and 1 passed earlier this session; see git history.)

## Gate 2 status: PASSED (per country, per tree)

| Gate 2 requirement | Status |
|---|---|
| Every backward stitch has a boundary record | **Done.** `data/canonical/stitch_boundaries.csv` (committed): one record per (line, incoming source) transition — year, outgoing, incoming, anchor value, growth, scope note, break flag — including three `not_applied_grade_D` skip records. |
| Crosswalk version + grade on every stitch | **Done.** `OECD_RS_to_ESA_REV.csv`, `EC_AMECO_to_INTEREST.csv`, `IMF_GFS_to_COFOG.csv` (all v1.0, §11.5 format, measured coverage as evidence); every stitched row carries grade, crosswalk_version, coverage_share + year (§9.2). |
| V5 | **Done** (plus V6, V13, V25). V5 WARNs on the R04/R05 proxies (RMSE ~0.15) — consistent with their C/D grades; V6 (growth reproduces from raw sources) and V13 (concept note per stitch) green; V25 documents the known RS concept wedges (up to −25% on GBR R06). No ERROR anywhere. |
| DECISIONS.md records why each line stops | **Done** — D-S2-004 has the full per-country, per-line table with binding constraints. |

`pytest`: **42 passed.** `ggfiscal validate`: OK=47 SKIP=9 WARN=321, no ERROR
(WARNs = V1 GFS wedges, V21 interest wedges, V5 proxy diagnostics, V25 RS
wedges — all expected-tier documentation, nothing adjusted).

## What Stage 2 added

Strict variant: 212 stitched rows, all grade B — GBR interest to 1987 (two
stitches: ONS ESA T2 D.41 then AMECO), FRA interest to 1978, GBR R01 to 1973
(VAT introduction), R03/R04 to 1965; FRA R01/R03 to 1965; DEU everything to
1991 (hard reunification break, never below). Maximum adds 118 C-grade rows
(R04/R06 and GBR/FRA R02/R06 deeper history). Variants now genuinely diverge.
Three mappings measured out of bounds were NOT applied (grade D, recorded):
FRA R02 (47%), FRA R05 (348%), GBR R05 (145%).

## Blocked on whom

**Nothing blocks Stage 3.** Committee items outstanding (none blocking):
OQ-5 (pre-1995 GBR/FRA expenditure archives: manual-ingest authorisation or
machine-readable endpoints; quick win: ONS long-run PSF interest series),
OQ-4 (AMECO no UK TR/TE levels), OQ-3 (raw archival).

## Exact next command

Stage 3 (strict forecasts — §12): priority `GF01_7`, `R07`, GF02 (all
three) → R01/R03/R04/R06 (OBR; Steuerschätzung + BMAS; AMECO/LPFP) → GF07,
GF09 (Ageing Report; OBR) → GF10 composites → remaining AMECO lines → D7
declarations. Machine-readable first; PDF via §11.4. New harvest pulls needed
(obr.uk, webgate/circabc for AR annexes, bundesfinanzministerium.de,
Steuerschätzung tables) — hosts were listed in OQ-1's "later stages" set and
have NOT yet been probed; if blocked, that reopens OQ-1 for those hosts.
Implement §7.5 (% GDP paths), §7.10 (GBR FY→CY conversion), D11/D12, V10,
V11, V15, V16, V18.

```
pip install -e .[dev] && pytest && ggfiscal validate   # green baseline
```

## Data facts Stage 3+ must not rediscover

- FRA/DEU revenue lines run off `gov_10a_main` REC codes (D-S1-002); taxag is
  detail-only. DEU GF01_7 1995-99 are D10 proxy rows (grade B).
- DEU never extends below 1991 (D-S2-003); GBR R01 stops at 1973 by law of
  nature (VAT introduction).
- AMECO chapter values are Mrd (billions) — unit_factor 1000 in the stitch
  spec; growth unaffected.
- Grade bands: B 90-110%, C 50-90%, else D-not-applied (D-S2-001).
- AMECO has no UK TR/TE levels (OQ-4) — OBR is the only UK envelope.
- V5 thresholds are D-S2-002's choice, not spec-given.

## §15 dependencies currently riding on defaults

Unchanged: Q1, Q3, Q4 (+ D-S2-002 filling V5's gap), Q7, Q8, Q12, Q13 on
defaults; Q11 pinned at 3 vintages (D-S0-007). Stage 3 will exercise Q7
(defence plans strict-B) and Q12 (OBR primary) directly.
