# HANDOFF.md

Rewritten 2026-08-31, end of session 2 (continued: Stage 1 in the same session).

## Current stage

**Stage 1 (canonical history, both trees) — COMPLETE. Gate 1 PASSED.**
(Gate 0 passed earlier this session; see git history and D-S0-006…009.)

## Gate 1 status: PASSED

| Gate 1 requirement | Status |
|---|---|
| 66 lines + ledgers built from anchors | **Done.** `ggfiscal build` → `data/canonical/{expenditure,revenue}_long_{strict,maximum_extension}.{csv,parquet}` (§5 long format, pandera-enforced) + `balance_ledger.csv` (TR/TE/NLB/NI/PB, `complete_both_sides`). Variants identical at this stage by design. |
| Data model, schemas, anchoring, GF01 split, revenue identity, IMF/OECD RS reconciliation fields | **Done.** §5 schema in `src/ggfiscal/model.py`; GF01_7/GF01_X split with the D10 proxy for DEU 1995–99 (grade B, D-S1-003); `imf_value`/`imf_diff_pct` on COFOG lines, `oecd_rs_value`/`oecd_rs_diff_pct` on R01/R03/R04/R06. |
| V1–V4, V7–V9, V12, V14, V19–V23 implemented and green | **Done.** `ggfiscal validate`: OK=18 SKIP=13 WARN=110, **no ERROR**. The WARNs are real diagnostics: V1 IMF-GFS wedges on FRA/DEU GF01/GF01_7 (up to ~6% — GFS vintage/consolidation differences), V21 L2-vs-D.41 wedges 5–10% in some FRA/DEU years. Both are expected-by-spec WARN tier; nothing was adjusted. |
| Small multiples render | **Done.** `ggfiscal report` → `reports/small_multiples_stage1.html` (22 lines × 3 countries + NLB, % of GDP). |
| History-side §8.3 decomposition runs and passes V26 | **Done.** `data/canonical/deficit_dynamics.csv`; additivity exact (V26 in the suite); anchor-B9 and WEO deltas carried as memo rows (D-S1-004). |

`pytest`: **35 passed** (stage_0 + stage_1). Canonical CSV deliverables are
now committed (gitignore keeps parquet + raw local; everything regenerates
from the hash-recorded snapshots).

## Data facts Stage 2+ must not rediscover

- FRA/DEU revenue lines are built from `gov_10a_main` REC codes, NOT
  `gov_10a_taxag` (D-S1-002: taxag drifts 0.5% from main in the freshest
  year and breaks V22). taxag = detail/verification only.
- DEU GF0107 starts 2000; 1995–99 are D10 proxy rows (grade B).
- Expenditure lines end 2024; FRA/DEU revenue lines reach provisional 2025;
  GBR revenue (ESA T2) spans 1990–2025 — so GBR R-lines already have five
  pre-1995 years in canonical while GF-lines start 1995.
- GBR: COFOG-tree TE is ONS Table 11's total (Apr 2026 release); the ledger
  runs on ESA Table 2 (Jun 2026). Different releases — do not force-align.
- AMECO has no UK TR/TE levels (OQ-4).

## Blocked on whom

**Nothing blocks Stage 2.** Standing committee notes: OQ-3 (raw archival),
OQ-4 (AMECO UK envelope), and the WEO 3-vintage retention note (OQ-2/D-S0-007).

## Exact next command

Stage 2 (backward extension — §12): revenue tax lines via OECD RS (crosswalk
`crosswalks/OECD_RS_to_ESA_REV.csv` to be written, D15/D17; RS harvested from
1965 already), then interest lines via GG D.41 history (GBR ESA T2 back to
1990 is in hand), then pre-1995 expenditure (INSEE/Destatis archives; GBR
archived T11 vintages — new pulls needed, hosts already allowlisted). Wire
V5/V6/V13/V25; every stitch gets a boundary record per §7.4.

```
pip install -e .[dev] && pytest && ggfiscal validate   # green baseline
```

Start in `src/ggfiscal/stitch/` (empty package). The stitch engine must write
boundary records (year, outgoing, incoming, anchor value, growth, scope,
break flag) and honour §7.2–7.4, §7.12 (no growth across missing/zero).

## §15 dependencies currently riding on defaults

Unchanged: Q1, Q3, Q4, Q7, Q8, Q12, Q13 on defaults; Q11 pinned at 3
vintages (D-S0-007). Nothing yet forces a committee call.
