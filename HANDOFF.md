# HANDOFF.md

Rewritten 2026-08-31, end of session 3 (Stages 3 AND 4 completed this
session, sequentially, on `claude/repo-review-stage-3-xamnht`; Stages 0–2
merged earlier via PR #1).

## Current stage

**Stage 4 (maximum-extension forecasts) — COMPLETE. Gate 4 PASSED.**
(Gate 3 passed earlier this session; see git history and D-S3-001..005.)

## Gate 4 status: PASSED

| Gate 4 requirement | Status |
|---|---|
| Variants distinguishable row-by-row | **Done.** Strict is a proper subset of maximum_extension (tested). Maximum adds: GF01 to 2027 (§7.9 mandated proxy, grade D, all three), GF10 to 2027 (GBR) / **2070** (FRA/DEU: AMECO D.62 proxy chained into the AR pensions+LTC composite per D12 — this join's overlap divergence is 0.010, under the V16 threshold, unlike the withheld interest join), FRA R05 to 2027 (C proxy). 315 maximum forecast rows vs 215 strict. |
| No leakage | **Done.** No C/D grade, no `proxy_forecast`, no maximum-only row in strict (Gate 4 tests + V9 + V17's §7.8 check). |
| Coverage matrix complete | **Done.** `data/canonical/coverage_matrix.csv` (§11.6 deliverable 9): 66 rows, spans per variant, stitch counts, grades, principal sources, residual_method, reason-series-ends — assembled from canonical + boundaries + declarations in the build. |

`pytest`: **63 passed.** `ggfiscal validate`: OK=52 SKIP=3 WARN=582, **no
ERROR** (V17 implemented and green; remaining SKIPs are V24/V27/V28, Stage 5).
WARN tiers unchanged and documented (V1/V21/V25/V5 wedges, V16 the withheld
DSM join OQ-7, V18 blocked sources OQ-6, S0_SNAPSHOTS old-manifest notices).

## What Stage 4 added

Engine: grade/§7.8 variant routing (D-S4-001) — C tier and single-component
proxies apply to maximum only; D measured-never-applied except §7.9's
mandated GF01-via-GF01_7 (applied at measured D: coverage 0.17–0.50,
D-S4-002); `residual_method` on every proxy/composite row (D2/Q3
`grow_with_proxy`, no overrides in `config/residual.yaml` yet); GF01_X
deliberately NOT derived from the proxy GF01 (D-S4-002). New crosswalk
`EC_AMECO_to_COFOG.csv` v1.0 (UYIG→GF01, UYTGH→GF10). V17 implemented
(coverage year + residual_method on proxy/composite rows; §7.8 strict ban).
Coverage matrix builder in `src/ggfiscal/coverage.py::write_matrix`, wired
into `ggfiscal build`.

## Blocked on whom

Unchanged from Stage 3 — nothing blocks Stage 5:
- **OQ-6:** obr.uk (Cloudflare) + gov.uk/bmas.de (egress) block all
  GBR-specific sources, GF02 everywhere, and the BMAS leg of DEU GF10.
- **OQ-7:** AMECO→DSM interest join awaiting committee (options are
  config-only). The GF10 join shows the same rule joining when vintages
  agree.
- **OQ-5:** §11.4 second keying (PDF sources).

## Exact next command

Stage 5 (reconciliation module — §8.2–8.5 in full): extend
`src/ggfiscal/reconcile/` — chained-at-b GDP path (§8.3), forecast-side
decomposition with `resid_coverage`/`resid_disagreement`/`denom_effect`
(exact additivity, V26), net-interest cross-check (§8.4, V27; note R07 has
no forecast so NI_ours forecast years come only from maximum GF01_7 minus a
missing R07 — §8.4 says report the gap, expect the coverage residual to
carry it), vintage keys + `weo_residual_history.csv` (§8.5, V28),
`weo_explanation.csv`, contribution charts, `reconciliation_report.html`.
Implement V24 (formalising D-S0-009's heuristic), V26 forecast side, V27,
V28. Gate 5: additivity exact; net-interest cross-check present; residual
history populated; a reader can state how much of each WEO balance change
the granular forecasts explain. Independent totals: OBR unavailable (OQ-6) —
use AMECO for all three and record the Q12 deviation for GBR.

```
pip install -e .[dev] && ggfiscal fetch --all && ggfiscal build && pytest && ggfiscal validate
```

(fresh container: raw snapshots are not committed, D-S0-004; `fetch --all`
includes the Stage 3 pulls with their required browser-like headers.)

## Data facts Stage 5+ must not rediscover

- Everything in the Stage 3 list (AMECO horizons/units, AR annual tables +
  constructed GDP, Steuerschätzung Kasse/Tab 8.2, DSM sheet quirks, V6
  direction-awareness, boundary-file separation) — see git history of this
  file at commit 80f877f.
- Variant routing lives in `extend_forward` (rows carry `variants`); the
  §7.9 GF01 proxy is `mandated=True` and is the only D-grade application.
- Coverage matrix "final_actual_year" counts stitched actuals (a 2025
  D-grade proxy-stitched year counts as actual — grades column disambiguates).
- WEO vintages in store: 2026-04, 2025-10, 2025-04 (D-S0-007); §8.5 keys by
  (weo_vintage, source_vintage_set_hash) — the source vintage set now
  includes EC_AMECO Spring 2026, EC_AGEING_2024, EC_DSM 2025,
  DEU_STEUERSCHAETZUNG 2026-05.
- Forecast-side §8.3 "covered" means the line has a forecast value in the
  given variant — strict and maximum now genuinely differ per year (the
  decomposition must be computed per variant).

## §15 dependencies currently riding on defaults

Q1, Q3 (`grow_with_proxy` everywhere — first real exercise at Stage 4), Q4
(D-S2-002 V5; D-S3-005 V16 = 0.02), Q7 (moot, OQ-6), Q8, Q13 defaults; Q11
pinned (D-S0-007); Q12 deviated by necessity (AMECO envelope while obr.uk
blocked — D-S3-001; Stage 5's independent-total choice inherits this);
Q10 (envelope-consistent third variant) remains "No" — the Stage 5 residuals
stay lumps.
