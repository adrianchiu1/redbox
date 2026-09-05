# HANDOFF.md

Rewritten 2026-09-05, end of session 5 (OQ-6 partial unblock: OBR/PESA
GBR forecasts, on `claude/stage-6-gg-fiscal-51xbzu` restarted from the
merged `main`; Stage 6 merged via PR #2 at a738b6d).

## Current stage

**All §12 stages complete (Gate 6 passed in session 4). This session was
maintenance-mode source work: the OQ-6 unblock for GBR.** No methodology
changed; every addition is a source + crosswalk + measured grade under the
existing engine (D13-clean).

## What session 5 did (D-S7-001..004)

- **Hand-retrieved OBR snapshots** (obr.uk stays Cloudflare-blocked): the
  committee uploaded the EFO March 2026 tables, FRS July 2025, the PSF
  aggregates databank (Aug 2026) and the historical public finances
  database; ingested via the new `ggfiscal ingest-file` (D8 hashes +
  provenance notes), and — because no machine fetch path exists —
  `data/raw/OBR_*` is COMMITTED to git (D-S7-001, narrowing D-S0-004).
- **Allowlist expansion**: gov.uk / assets.publishing / bmas.de (+
  insee.fr, destatis, cor-retraites) now reachable. PESA 2026 chapter 1
  registered (`HMT_PESA`, supersedes the UK_DEFENCE_PLAN seed) and pulled
  live. BMAS RVB reachable but PDF-only → OQ-5 gate (D-S7-002).
- **GBR forecast map** (D-S7-003, crosswalks OBR_to_ESA_REV.csv +
  OBR_PESA_to_COFOG.csv v1.0, all shares measured on the GG anchor):
  strict R01 (0.991) / R02 (0.923, incl. EFO business rates) / R03
  (1.032) / R04 (0.988) to 2030; GF02 ← PESA MoD DEL (0.9005, §15 Q7's
  ≥90% met) to 2028; maximum R05 (0.787) to 2030. Recorded-not-applied:
  R07 (2.63 — dividends + PS perimeter), GF01_7 ← CG debt interest
  (0.67-1.28 drift, PSF vs ESA), GF10 ← EFO welfare (no overlap year to
  measure). D12/V16 withheld the AMECO→OBR NICs join for R06 (→ OQ-7).
- **§15 Q12 exercised**: GBR V15 envelope and §8.3 independent totals =
  OBR PSCR/TME + OBR GDP path (perimeter ratio 0.95-0.97, stable,
  documented); AMECO remains the cross-check.

## Headline result

`pytest`: **90 passed.** `validate`: **OK=55 WARN=661, no ERROR, no
SKIP.** GBR explained share (WEO 2026-04): **strict 0.55-0.67, maximum
0.60-0.76 across 2026-2030** (was 0.04-0.06); full coverage/disagreement
residual split for GBR through 2030 (resid_total only at 2031). FRA/DEU
unchanged.

## Blocked on whom (all committee items)

- **OQ-6 remaining asks**: (a) an FRS edition WITH functional long-term
  projections (2024 edition, or 2026 if published) → GBR GF07/GF09/GF10
  long legs; (b) an OBR welfare-spending FY history → makes the EFO
  welfare series measurable for GF10; (c) BMAS RVB is an OQ-5
  second-keying question now, not network; (d) obr.uk challenge-capable
  access — the next EFO (~Nov 2026) otherwise needs the same
  hand-retrieval route (`ggfiscal ingest-file`).
- **OQ-7 — RESOLVED 2026-09-05 (D-S8-001)**: the committee approved both
  withheld joins via the new `tolerances.v16_approved_joins` config list.
  FRA/DEU GF01_7 strict now runs to 2036 (DSM, grade B); GBR R06 maximum
  to 2030 (OBR NICs, grade C — stays out of strict by grade). V16 keeps
  WARNing on the seams; the DSM 2026 (~Feb 2027) and next EFO (~Nov 2026)
  vintages should shrink them — refresh via detect-vintages + rebuild,
  no re-adjudication needed.
- **OQ-5**: pre-1995 archives / second keying; insee+destatis+cor now
  reachable, and OBR_HIST_PF is snapshotted as the GBR pre-1987 interest
  candidate — unworked.

## Exact next command

Maintenance cadence unchanged (see session-4 HANDOFF in git history):

```
ggfiscal detect-vintages   # WEO October 2026 expected mid-October — register promptly (D-S0-007)
```

Fresh container: `pip install -e .[dev]` (+ xlrd openpyxl pytest; use
`python3 -m pytest`), `ggfiscal fetch --all`, then build/reconcile/report.
The OBR raw bytes come with the clone (D-S7-001) — do NOT expect
`fetch` to produce them; re-ingest via `ggfiscal ingest-file` only for
new OBR editions. Expected green baseline: 90 passed; validate no ERROR,
no SKIP.

## Data facts future sessions must not rediscover

- Everything in the session-4 HANDOFF (git history at PR #2) plus:
- OBR tables are FY (Apr-Mar), £bn (PESA: £mn). `fy_to_cy` indexes FY by
  START year; CY_t needs FY_{t-1} AND FY_t, so a table whose first year
  is FY 2024-25 yields no CY year the expenditure anchor (ends 2024)
  covers — that is why the EFO welfare and 4.7/4.8 defence tables alone
  are unmeasurable, and why the PSF databank (history to 1946-47) and
  PESA (outturns from 2021-22) matter.
- `FcSource.horizon_year` = last calendar year the source's native FY
  periods touch (FY 2030-31 → 2031); V10 nets the §7.10 conversion loss.
- The databank's per-tax "Receipts (£bn)" sheet runs 1999-00..2030-31 on
  the EFO March 2026 vintage — history AND forecast in one series; it
  lacks business rates (in the R02 composite from EFO annex A.5, which is
  why R02's coverage year is 2025 only) and lacks welfare.
- OBR/PSF "CG debt interest net of APF" is NOT ESA D.41 (share drifts
  0.67→1.28 vs the anchor) — do not retry it for GF01_7 without a
  concept bridge.
- The anchor's D.211 includes VAT refunds; D51O includes bank
  surcharge/EGL inside the databank's onshore CT; NICs alone is only
  ~0.76 of D.61 (imputed + voluntary missing).
- `wb.sheetnames`/`wb.worksheets` misalign when a workbook has
  chartsheets (the PSF databank does) — iterate `wb.worksheets` by
  `.title`.
- gov.uk content API (`/api/content/...`, `/api/search.json`) resolves
  publication attachments cleanly — used to find PESA; works for future
  HMT/DWP sources.
- Today's date matters: sessions 4 and 5 were 2026-09-03 and 2026-09-05;
  Eurostat updated nama_10_gdp on 2026-09-03 (register refreshed).

## §15 dependencies currently riding on defaults

Q1, Q3 (grow_with_proxy), Q4 (V5/V16 thresholds; GBR sigma 0.5), Q8, Q10,
Q13 as before; Q11 pinned (config vintage register, D-S6-001); **Q7
exercised** (PESA defence at 0.9005 ≥ 0.90 → strict B); **Q12 exercised
as written** (OBR envelope + independent totals, AMECO cross-check —
supersedes the D-S5-002 forced deviation).
