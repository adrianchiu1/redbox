# HANDOFF.md

Rewritten 2026-09-08, end of session 6 (the flat-file bundle and the
derivation notebook, on `claude/gbr-fra-deu-govt-expenditure-0lc1w1`
branched from the merged `main` at 7cf4a83).

## Current stage

**All §12 stages complete. This session was product work, not methodology:
the committee asked for the end product to be "extremely simple: flat files
with all the series ... and a python notebook explaining how each series was
derived".** Nothing in the engine changed; no number moved that the
2026-09-08 source vintages did not move.

## What session 6 did (D-S9-001)

- **`deliverables/` — the flat-file bundle**, written by the new
  `ggfiscal flatten` (`src/ggfiscal/publish/flatten.py`; also the last step
  of `ggfiscal report`, so it cannot fall behind a reported run). Seven
  files: `expenditure_cofog.csv`, `revenue_esa.csv`, `balance_ledger.csv`,
  `weo_levels_bridge.csv`, `weo_reconciliation.csv`, `series_catalogue.csv`,
  `data_dictionary.csv`, plus a generated README. Both variants sit in one
  file behind a `variant` column; each row carries a `derivation` sentence
  in the Gate 6 form `value(t) = value(t±1) × growth`.
- **`notebooks/derivation.ipynb`** — executed with outputs committed,
  reading only the bundle (never `data/canonical/` or `data/raw/`). It
  prints the recipe of all 72 published series, re-proves the chain
  arithmetic, checks the ledger identities, and walks the §8.2/§8.3
  reconciliation. Re-run it with
  `pip install -e .[notebook] && jupyter nbconvert --execute --inplace
  notebooks/*.ipynb`.
- **`notebooks/chartbook.ipynb`** (D-S9-002) — 102 figures, one per series,
  laid out country → category → series, plus the WEO comparison (levels
  above, gap as % of TE below) for revenue, expenditure and NLB per
  country. Seams (source or method changes) are drawn as dotted rules and
  projection years shaded, so construction quality can be eyeballed; §6
  tabulates every seam with the change across it, sorted, as a triage list.
  Its opening section lists the ten things that do not fit a flat
  country/category/series layout — read that before the charts. Revised
  per D-S9-003: one x-axis per country (GBR 1965-2030, FRA 1965-2070, DEU
  1991-2070) so charts read side by side; projection shading on every
  chart, not only those with a forecast; and a per-variant caption saying
  how far each projects or why it does not — 44 of 72 series carry no
  projection at all, across five recorded statuses, tabulated up front.
- **`tests/deliverables/test_flat_files.py`** (24 tests) enforces the three
  invariants: nothing recomputed (bit-exact copy, `float_precision=
  "round_trip"`), every chained value reproducible from the flat file alone,
  and the data dictionary covering every column of every file by set
  equality. Both notebooks are checked for committed, error-free outputs,
  and the chartbook for charting every catalogued series.
- **Packaging fixes**: `openpyxl` and `xlrd` are now real dependencies (the
  committed OBR snapshots are unreadable without them — session 5 left them
  as a manual install step), plus a `notebook` extra.

## Headline result

`pytest`: **114 passed** (90 + 24 new). `validate`: **OK=55 WARN=820, no
ERROR, no SKIP**. The WARN count is up from 661 on source-vintage drift
alone (V25/V1 concept wedges against refreshed Eurostat/OECD/AMECO pulls of
2026-09-08); no new check, no new tier, no ERROR.

## Two documentation errors this session corrected

- The variants do **not** differ only forward. `maximum_extension` also
  carries longer **backward** legs wherever the backward source grades C:
  GBR R02 to 1965, FRA R04/R06 to 1965, DEU R04/R06 to 1991. Any text
  saying "identical over history" is wrong; the true statement is
  "maximum_extension contains strict and equals it wherever both exist".
- `ANCHOR_B9_DELTA` in `deficit_dynamics.csv` is the anchor's change in
  B.9/GDP **minus** the sum-based change — a wedge, ~0 in most years and
  0.36pp at its worst (GBR 2024) — not the anchor's own change. The third
  memo, `WEO_GGXCNL_DELTA`, is the WEO's own year-on-year change and is the
  history-side leg of the WEO reconciliation. Do not re-derive this.

## Blocked on whom (all committee items, unchanged from session 5)

- **OQ-6 remaining asks**: (a) an FRS edition WITH functional long-term
  projections → GBR GF07/GF09/GF10 long legs; (b) an OBR welfare-spending FY
  history → makes the EFO welfare series measurable for GF10; (c) BMAS RVB
  is PDF-only, an OQ-5 second-keying question; (d) obr.uk remains
  challenge-blocked — the next EFO (~Nov 2026) needs the same hand-retrieval
  route (`ggfiscal ingest-file`).
- **OQ-7 — RESOLVED 2026-09-05 (D-S8-001)** via
  `tolerances.v16_approved_joins`. V16 keeps WARNing on the seams by design;
  the DSM 2026 (~Feb 2027) and next EFO vintages should shrink them.
- **OQ-5**: pre-1995 archives / second keying; unworked.

## Exact next command

Maintenance cadence unchanged:

```
ggfiscal detect-vintages   # WEO October 2026 expected mid-October — register promptly (D-S0-007)
```

Fresh container: `pip install -e .[dev]` (openpyxl/xlrd now come with it;
use `python3 -m pytest`), `ggfiscal fetch --all`, then
`build`, `reconcile`, `report` (which now also writes `deliverables/`),
`validate`. The OBR raw bytes come with the clone (D-S7-001) — do NOT expect
`fetch` to produce them. Expected green baseline on the 2026-09-08 harvest:
114 passed; validate no ERROR, no SKIP. **After any rebuild, re-execute both
notebooks** (`jupyter nbconvert --execute --inplace notebooks/*.ipynb`) so
their committed outputs match the bundle.

## Data facts future sessions must not rediscover

- Everything in the session-4 and session-5 HANDOFFs (git history at PR #2
  and PR #3), plus:
- `pd.read_csv` loses ~1 ULP per round trip at its default float precision.
  The bundle reads the canonical layer with `float_precision="round_trip"`
  so the published decimal text IS the canonical decimal text; drop that and
  the bit-exact fidelity test fails on FRA R05 first.
- `pytest` does not rebuild when `data/canonical/` is already populated (the
  Gate 1 fixture builds only if it is empty), so the suite does not churn
  run manifests — but it also will NOT pick up a stale canonical layer.
  Rebuild explicitly when sources change.
- A pytest run against a canonical layer built from OLDER snapshots fails
  Stage 0's V14 (`canonical anchor-era years != anchor years`). That is the
  vintage-drift signal, not a code defect: rebuild, then re-run.
- **Notebook size is a hard constraint** (D-S9-004): GitHub's renderer is
  client-side and gives up on large `.ipynb`, showing "Loading" forever —
  the chartbook did this at 3.28 MB. It is now 0.88 MB and must stay under
  a megabyte: small figures, and PNGs quantised onto the FIXED palette in
  the setup cell. Do not switch that to an adaptive palette — adaptive
  allocates slots by pixel count and crushes the dashed orange series to a
  muddy brown. The threshold cannot be measured from a session here
  (fetching a blob page returns "Loading" at any size); nbviewer is the
  documented fallback, and splitting per country is the next step if 0.88
  MB still fails.
- Capping a chart's x-axis does NOT cap its y-axis: matplotlib autoscales
  over all plotted data, so the window must be applied to the DATA, not
  just to `set_xlim`, or a 2070 value flattens the visible history.
- `ggfiscal flatten` is deterministic given the canonical layer (D-S9-003):
  no wall clock in any generated header. Keep it that way — the
  `tests/deliverables` fixture re-renders the bundle on every pytest run,
  so a timestamp there dirties the tree every time the suite is run.
- The tree TE/TR lines and the balance ledger use DIFFERENT anchors for GBR
  (ONS_ESA_T11 vs ONS_GG_RECEIPTS), so their final actual years differ
  (2024 vs 2025). Expected; documented in the notebook.

## §15 dependencies currently riding on defaults

Unchanged from session 5: Q1, Q3, Q4, Q8, Q10, Q13 on defaults; Q11 pinned
(D-S6-001); Q7 and Q12 exercised.
