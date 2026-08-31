# HANDOFF.md

Rewritten 2026-08-31, end of session 3 (Stages 3, 4 AND 5 completed this
session, sequentially, on `claude/repo-review-stage-3-xamnht`; Stages 0–2
merged earlier via PR #1).

## Current stage

**Stage 5 (reconciliation module) — COMPLETE. Gate 5 PASSED.**
(Gates 3 and 4 passed earlier this session; see git history, D-S3-*, D-S4-*.)

## Gate 5 status: PASSED

| Gate 5 requirement | Status |
|---|---|
| Additivity exact | **Done.** §8.3 forecast decomposition (`weo_explanation.csv`, 1,636 rows: 3 countries × 2 variants × 3 WEO vintages × horizons to 2030/2031) sums covered lines + denominator effect + residuals + WEO-internal wedge to the WEO balance change to 1e-9 — exact by telescoping construction (D-S5-001); history side unchanged and exact (V26 covers both). |
| Net-interest cross-check present | **Done.** `net_interest_check.csv`: a row for every (country, variant, vintage, horizon); non-computable cells (R07 has no forecast anywhere — declared, OQ-6) state the reason; FRA h=2025 is computable (gap ≈ V21-tier). V27 enforces presence + reasons. |
| Residual history populated | **Done.** `weo_residual_history.csv` across all three harvested WEO vintages, keyed per §8.5 by (iso3, series_variant, weo_vintage, source_vintage_set_hash); V28 checks the keys on every reconciliation table. |
| Reader can state how much is explained | **Done.** Explicit `explained_share` rows per (country, variant, vintage, horizon) + the summary table in `reports/reconciliation_report.html`. Headline (D-S5-004): GBR ~0–6% (OBR blocked), DEU ~40–56% in maximum, FRA's projected consolidation entirely in the residuals — the covered French forecasts move the other way. |

`pytest`: **71 passed.** `ggfiscal validate`: **OK=55 WARN=582, no ERROR, no
SKIP — all 28 V-checks now run.** V24 formalised and green (FRA/DEU gaps
within 1% of TE; GBR NLB-gap sigma 0.36–0.42 < 0.5 threshold, D-S5-002).
WARN tiers unchanged (documented wedges + OQ-6/OQ-7 visibility).

## What Stage 5 added

`src/ggfiscal/reconcile/explanation.py` (§8.3–8.5: decomposition with
per-side denominator effect and coverage/disagreement residuals collapsing
to labelled resid_total where no independent total exists; §8.4 NI check;
§8.5 vintage keys + residual history; the §8.3 implied-uncovered-growth
plausibility memos). `src/ggfiscal/report/reconciliation.py`
(`reconciliation_report.html`: 12 stacked-contribution charts — history and
forecast, strict and maximum, WEO path overlaid, residuals in grey — plus
explained-share, NI and residual-history tables). Validators
`validate/stage5.py` (V24, V26 forecast side, V27, V28); new tolerance
`gbr_perimeter_sigma_pct_te: 0.5`. Independent totals: AMECO for all three
(Q12 deviation for GBR made concrete — both GBR sides are resid_total,
D-S5-002). `ggfiscal reconcile` and `ggfiscal report` write everything.

## Blocked on whom

Unchanged — nothing blocks Stage 6:
- **OQ-6:** obr.uk/gov.uk/bmas.de blocks (GBR granular forecasts + GF02 +
  BMAS). Unblocking OBR would transform the GBR explained share.
- **OQ-7:** AMECO→DSM interest join awaiting committee (config-only).
- **OQ-5:** §11.4 second keying (PDF sources).

## Exact next command

Stage 6 (packaging and vintage re-run — §12): generated README (§11.6
deliverable 10), `validation_report.html`, run manifest completeness,
`detect-vintages` with a simulated new-vintage fixture showing rebuild
without code change (§11.7), plus Gate 6's reproducibility proof: any
stitched value reproducible from anchor + recorded growth using only
deliverables. Remaining §11.6 gaps to close: parquet twins for the Stage 5
tables if wanted (CSVs committed), `source_register.csv` already
generated, `crosswalks.csv` concatenation, `exceptions.csv` committed ✓.

```
pip install -e .[dev] && ggfiscal fetch --all && ggfiscal build && ggfiscal reconcile && ggfiscal report && pytest && ggfiscal validate
```

(fresh container: raw snapshots are not committed, D-S0-004.)

## Data facts Stage 6 must not rediscover

- All Stage 3/4 facts (see this file's history at commits 80f877f, f32d7a7).
- WEO forecast horizons: 2031 (2026-04), 2030 (2025-10, 2025-04); §8.1 base
  years per vintage from the bridge (GBR/DEU 2025, FRA 2024 on the latest).
- WEO raw units are LCU singles — ÷1e6 to millions (bridge.weo_aggregates
  does this; ratios cancel scale but NI levels do not).
- GBR has no AMECO level at any base year → resid_total both sides, every
  horizon (not a bug; D-S5-002).
- explained_share rows are ratios, implied/historical growth memos are
  % per year — neither enters the V26 additivity set (component kinds are
  the six listed in explanation.py).
- The §8.3 history table stays on anchor GDP per D-S1-004/D-S5-001; the
  forecast tables are the t ≥ b leg on unscaled NGDP_w.
- detect-vintages (§11.7) must snapshot new WEO editions promptly — the API
  drops old ones (D-S0-007) — and re-run reconcile when either side changes.

## §15 dependencies currently riding on defaults

Q1, Q3 (grow_with_proxy), Q4 (D-S2-002 V5; D-S3-005 V16; **D-S5-002 GBR
sigma 0.5**), Q7 (moot, OQ-6), Q8, Q10 (**exercised**: residuals published
as lumps, no envelope-consistent variant), Q13 defaults; Q11 pinned
(D-S0-007); Q12 deviated by necessity (AMECO independent total for GBR —
D-S5-002; revisit when OBR is reachable).
