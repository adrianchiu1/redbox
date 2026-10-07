# Next steps — Italy, Spain, Belgium (Stage E follow-up)

Working list after session 17 (2026-10-07). Tick items off as they land.
Background: `EU3_KICKOFF.md`, `DECISIONS.md` D-S17-001..011,
`OPEN_QUESTIONS.md` OQ-17..19, `HANDOFF.md`.

## Decisions only you can make

- [ ] **Ageing Report join for social protection (GF10), ITA/ESP/BEL.**
  The AMECO → Ageing Report switch diverges by +0.021 / −0.021 / +0.031
  (threshold 0.02). Approving it extends GF10 in the maximum variant from
  2027 to 2070, as for France and Germany. To approve: add
  `{iso3: ITA, line_code: GF10, incoming_source: EC_AGEING_2024}` (and ESP,
  BEL) to `tolerances.v16_approved_joins` in `config/countries.yaml`, then
  rebuild. (OQ-17)
- [ ] **Italy/Belgium sub-categories before 2001.** Accept a 2001 start for
  pensions, unemployment and transport, or name a national source
  (ISTAT / Belgian ICN historical COFOG tables) to verify. (OQ-18)
- [ ] **Spain vs the IMF WEO.** Revenue and spending levels differ by
  1.5–1.7% of spending (the deficit matches). Keep the warning (default) or
  treat Spain like the UK with an expected perimeter gap. (OQ-19)
- [ ] **Network access** (only if you want national forecasts or Spain's
  bond register): allow `www.airef.es`, `www.upbinfo.it`,
  `www.planbureau.be`, `stat.nbb.be` in the environment's network
  settings. `www.tesoro.es` fails its certificate check from here; it
  needs either the missing intermediate certificate added to the trust
  bundle, or a Tesoro data mirror.

## Build work (next sessions)

1. [ ] **Belgium bond register (Stage ED3).** Build
   `src/ggfiscal/debt/register_bel.py` from the snapshot
   `BEL_BDA/olo_outstanding_html` (38 OLO lines, 13 Treasury Certificates,
   56 EMTN/other: ISIN, coupon, maturity, outstanding). Add `register:` to
   BEL in `config/debt.yaml`. Gives a per-bond maturity profile and
   interest by security. Make sure the snapshot date does not add a
   register step to a year the chains do not cover.
2. [ ] **Belgium auction history** (for year-end positions): look on the
   BDA site under `datafederalstateissues` for a machine-readable history.
3. [ ] **Italy bond register.** No per-bond outstanding file exists.
   Candidates: the archived auction-results spreadsheets
   (`Risultati-aste-BTP-*.xls`) plus the per-auction HTML pages, anchored
   on a per-ISIN snapshot (try the MEF quarterly bulletin). Same method as
   France's AFT register.
4. [ ] **Italy year-end class history.** The MEF composition CSVs only
   cover the current year; the December edition will be picked up
   automatically from early 2027 (`ITA_MEF_COMPOSIZIONE`). Older years
   exist as PDFs in the MEF archive only.
5. [ ] **Step A of the debt chains** (cash interest and cash borrowing
   requirement) is empty for all three. Find machine-readable sources, or
   accept that they stay null.
6. [ ] **Then the USA** — Stage U1 per `REPLICATION_KICKOFF.md` (paused for
   this work).

## Housekeeping

- [ ] **Seed the statistical forecast intervals.** Prophet and ETS
  intervals are unseeded, so `se`/lo/hi change on every run
  (`src/ggfiscal/forecast/statistical.py`). Fixing it makes byte-identity
  checks clean on the downstream files.
- [ ] **Three UK debt tests fail on today's DMO data** (also on `main`):
  `tests/debt/test_register_gbr.py` (2) and
  `test_bridges.py::test_gbr_step_c_items_shrink_the_residual[financing]`.
  Find what changed in the DMO export.
- [ ] **README prose is stale.** Generated text still says "United Kingdom,
  France and Germany" and "14 lines per country"
  (`src/ggfiscal/report/readme.py`, `src/ggfiscal/publish/flatten.py`
  ~line 938). Derive the country list from config.
- [ ] **Notebook tool leaves stale cells.** `tools/update_notebooks_s11.py`
  only adds cells to an existing forecast book. When a line gains an
  official forecast (as interest did after the approval), its old
  statistical-forecast charts stay until the book is deleted and re-seeded.
  Make the tool drop `fan(...)` cells for series no longer in
  `statistical_forecasts.csv`.
- [ ] **Open a pull request** for `claude/serene-thompson-soiwhn` when ready.

## How to rebuild everything

See "Exact commands" in `HANDOFF.md`. `ggfiscal debt fetch` takes over 30
minutes (the French Treasury's bot challenges) and needs `pip install
playwright`.
