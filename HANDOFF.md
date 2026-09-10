# HANDOFF.md

Rewritten 2026-09-10, end of session 9 (the debt-in-issue extension, on
`claude/stoic-dijkstra-bc42s1` branched from the merged `main` at 6441366).

## Current stage

**Debt extension (DEBT_KICKOFF.md v1.0): D0–D5 complete on the per-security
register for all three countries — Germany (D-S10-004), the United Kingdom
(D-S10-005), France (D-S10-006/007).** The aggregate layer (DD8) stays as the
register step before each register starts (FRA before 2000, DEU before
1995/2005 for the tests, GBR before 1987) and as the V31/V39 cross-check. The
parent package is untouched except: `config.sources()` merges
`config/debt_sources.yaml`; the snapshot store names pdf/html extensions;
pypdf, cffi, bs4 are dependencies. Parent baseline still 120 passed (the
three validation tests are order-sensitive when a build runs concurrently —
rerun alone).

## What session 9 did (D-S10-005)

- **DMO access.** The export endpoint clears the ShieldSquare challenge for
  `browser.py`; each report exports in exactly one presentation type
  (`families/debt_offices.DMO_FORMATS`), every other request returns a
  35-byte stub that the family, `ingest-incoming` and the desktop script now
  refuse. 14 reports snapshotted; D1D/D5I/D9C/D2.2A export in no format; the
  `COBDate` year-end snapshots do not work by URL.
- **`readers/dmo.py` + `register_gbr.py`**: 1,747 securities, 4,404 year-end
  positions 1981–2025 rolled from the operations record and anchored on D1A
  (in issue) / D1C (nominal at redemption), 8,173 flows, 10,562 index-ratio
  points recomputed from the ONS RPI (D10C reproduced to 5 dp). Recurrence
  exact on 3,499 year-end pairs; IL unindexed nominal = DMR to the million
  2023–2025; conventional gilts 8% above the consolidated ONS/DMR stock
  (OQ-9).
- **Chains**: `config/debt.yaml` `register_chain_items` — the register's
  interest basis and step-A bridges per country (GBR accrued, no value-date
  items; DEU cash with the two BMF items); new financing bridge
  `issuance_cash_less_nominal`. UK interest step A within ±3.3 £bn 2010–2024
  (three years 5–8); financing step A within ±13 £bn except 2022 and
  2008–09 (OQ-9 wedge).
- Tests: `tests/debt` 200 passed, 6 skipped (13 new GBR); deliverables and
  README regenerated; notebook re-executed with a register section.

## Session 9, third part (D-S10-007): France complete

- Three rounds of AFT files saved by the committee (pages, coefficient and
  index files, the auction histories) → `readers/aft.py` +
  `register_fra.py`: 1,603 securities, 2,069 year-end positions 1999–2025
  rolled back from the encours through the auction histories, 7,903 flows,
  92,139 ratio points (office daily). Σ BTF = AFT total to the euro
  2009–2020; linkers uplifted within 3%; fixed lines 1–4% above the AFT
  total in recent years (buybacks published only in aggregate). France in
  both chains from 2000; step A (État cash) remains blocked, the register
  meets S.1311 at step B.
- Tests: `tests/debt` 245 passed, 6 skipped.

## Session 9, second part (D-S10-006): France

- Nine AFT pages saved by the committee (Cloudflare challenges every
  automated navigation, static files included) → `readers/aft.py`,
  `register_fra.py`: 101 securities, positions at the retrieval date, the
  month's auctions as flows. Snapshot register: it does not enter the
  chains (full-year coverage rule in `register.register_sums`), France
  stays on the aggregate layer until the auction history is saved
  (DOWNLOAD_LIST.md second round).
- Maturity profile now also at each office's latest snapshot.

## Sessions 7–8 in brief

- Session 7: `DEBT_SCOPING.md` → `DEBT_KICKOFF.md` v1.0; `ggfiscal.debt`
  families, engines (§7 interest, DD7 maturity, §8 chain assembler), the
  aggregate layer, chains, validate, flatten, notebook (D-S10-001/002/003).
- Session 8: Finanzagentur harvested; `register_deu.py`; `register.py`
  assembles interest by security, maturity profile, issuance by bucket and
  the computed register sums; ECB/Bundesbank family (D-S10-004).

## Blocked on whom

- **OQ-8 (committee, residual)**: nothing blocking. Optional: the DMO
  page's own export link for a past close-of-business date; the AFT fiche
  titre pages (first coupon dates); budget.gouv.fr programme 117 tables
  (France's step A).
- **OQ-9 (committee)**: an official series of gilts held by CG bodies (DMA,
  CRND) would turn the register-vs-ONS wedge into a holdings overlay.
- Q-D7 (committee, later): PDF extraction rule for pre-register years.

## Exact next command

```
ggfiscal debt fetch --family debt_offices   # DMO through the browser session; AFT will FAIL until OQ-8
ggfiscal debt build && ggfiscal debt validate && ggfiscal flatten
python3 -m pytest tests/debt -q
```

Next build steps: (1) per-line buybacks for France if a source appears
(the AFT bulletins), and the État's step-A totals (programme 117); (2)
per-ISIN APF holdings from the BOE_APF snapshots into
`official_holdings_lcu_mn` (DD11); (3) the LIBID fixings for the two
floating-rate gilts if a source appears (DD10).

## Data facts future sessions must not rediscover (debt)

- DMO export endpoint: `GetDataExport?reportCode=X&exportFormatValue=xml|xls
  &parameters=&COBDate=` — one format per report (DMO_FORMATS); the report
  HTML pages re-challenge the headless browser, the export endpoint does not
  once the challenge has cleared on `XmlDataReport?reportCode=D1A`.
- D2.1E (issuance history) carries signed nominals: creations positive,
  cancellations/reverse auctions negative, conversions and switches both
  signs; `ACTUAL_DATE` is the settlement date; prices are clean. Tranche
  ISINs (`… 2007 A`) are assimilated into the parent — fold them.
- D1C lists redeemed gilts by name only (no ISIN): join on
  `readers.dmo.name_key` (coupon | IL/CV | years, tranche dropped). Gilts
  converted or switched out in full before 2000 appear nowhere.
- Index ratios: reference RPI(d) = RPI(m−3) + (d−1)/days(m) × (RPI(m−2) −
  RPI(m−3)), base = reference RPI at first issue; `UK_RPI` is on Jan 1987 =
  100 and reproduces D10C exactly. 8-month linkers: RPI(m−8).
- The NLF accounts are accruals-based: the UK register enters the interest
  chain on the accrued basis (uplift accrual and amortisation included);
  never add the BMF value-date bridges to the UK.
- ONS Appendix S / PSA8A_1 gilt rows (F.332) are consolidated within CG;
  HMT DMR table A.1 likewise. The register is gross (OQ-9).
- UK bills: one security per maturity date (fungible); bilateral/ad hoc
  bills are outside the tender history, so the register bill stock is
  below ONS BKPJ after 2006.
- The financing chain runs in NET-BORROWING sign: steps B and C carry
  −B.9 / −NLB (basis says so). Register selection per country lives in
  `config/debt.yaml`; DEU special funds are subtracted at step A and
  added back at step B; the Mitfinanzierung item is interest-only.
- Kreditaufnahmebericht annex 4.10: 2019–2025 parse and close to the
  euro; 2013–2018 have no annex (narrative-table NKA, narrower concept);
  rows may carry 2 cells (Soll blank) and labels wrap both ways.
- ONS REC2's RUUX is CGNCR incl. NRAM/B&B/Network Rail; PSA7C (M98W,
  MUI2, ABEC, ABEI) bridges it to M98R. PSA2 −NMOE is LG net borrowing;
  PSA6J NUGW is LG interest. No intra-GG consolidation line is published.
- Eurostat EDP identity: GD_CH = B9_T3 + F_ASS + ORADJ + YA3 (KX and K61
  are inside ORADJ); edpt3 starts FR 2021 / DE 2022.
- BMF Datenportal flow sheets are cumulative year-to-date (December = full
  year); Tilgungen/Zinsen are negative; values in whole euro. Indent-0
  totals: "Kredite … inklusive Mitfinanzierung" is the wider total the
  instrument tree sums to. From 2025 stock(t) ≠ stock(t−1)+gross−redemptions
  (agio/disagio spreading, +9.9 EUR bn wedge in 2025).
- Kreditaufnahmebericht annex numbering moves by edition: match on title.
  Annex 4.5 (2025 edition) carries Verzinsung 1996–2025 and agrees with the
  Datenportal to 0.5 EUR mn; annex 4.10 parses 2020–2025 only.
- BMF host: Radware bot manager — fresh session, de-DE headers, Referer,
  same-host redirects only, up to 8 retries; large PDFs need Range resume;
  HTML carries per-request `__uzdbm_*` tokens (never hash-stable).
- ONS PSA sheets: locate header/CDID rows by column-A stub, never by
  offset; period labels are `1998`, `Apr 1997 to Mar 1998`, `Apr to Jun
  1997`, `2026 Jul`. PSA CY blocks start 1998; PUSF NMFX annual goes to
  1946; M98R monthly from 1984-04 sums to calendar years directly.
- NLF accounts: 18 of 20 editions parse (2006-07, 2007-08 have no
  ToUnicode map); 2012-13's printed total does not add up (restated in
  2013-14). Finance costs are accrual; "Interest paid" is the cash line.
- RPI: CHAW (Jan 1987=100) from 1987; CDKO (Jan 1974=100) from 1947-06;
  splice factor 100/394.5, constant to 4 dp over the 475-month overlap.
- INSEE: `serie/ajax/{idbank}` returns the full history as an HTML table;
  the csv route 500s; bdm.insee.fr is blocked. FR CPI ex-tobacco base
  2015→2025 chain factor 0.834606 over 360 months.
- Eurostat: gov_10dd_ggd key order freq.na_item.sector2.sector.maturity.
  unit.geo; FR structure-of-debt tables start 2020; DE rmd has 4 of 7
  bands and S1311 from 2004; HICP coicop code is TOT_X_TBC (dimension
  `coicop18` in prc_hicp_minr, `coicop` in the midx archive); UK absent.
- BoE: media CDN 403s a bare requests UA — send browser headers; IADB
  `_iadb-fromshowcolumns.asp` returns CSV when Datefrom ≥ series start,
  else HTML/302; curve workbooks: spot sheet, maturities row 4, dates from
  row 6.
- AFT files: `hist_mlt` / `hist_btf` (auction histories, EUR mn, yields
  and prices as fractions), `historique_syndications` (negative volume =
  buyback), coefficient files (header block rows 2–8: kind, coupon,
  maturity, base date, base index; daily data from row 10; the current
  files cover 1998/2001 → the coming month, the `histo` files stop in 2016
  and carry the lines matured since), `IPC` / `IPCH` (monthly index on
  every base). The daily reference index is the 3-month-lag interpolation
  of the monthly index (1.5e-5). Column 0 of a header list is falsy: never
  `_col(...) or _col(...)`.
- AFT: the encours pages are HTML tables (no Excel behind them); libellés
  carry coupon and maturity (`readers/aft.parse_libelle`); French amounts
  use space thousands and comma decimals, the English OAT€i page uses
  commas and a `.00`; auction pages are attribute rows × lines, ISIN last;
  `Volume total émis = adjugé + ONC`. The site challenges every automated
  navigation and its `/files/` downloads; a person's browser passes once
  per page.
- Playwright/Chromium through the agent proxy: `--disable-quic`,
  `--disable-features=PostQuantumKyber,UseMLKEM,EncryptedClientHello`,
  `--ssl-version-max=tls1.2`; never `pkill -f` a pattern that matches your
  own shell command line (it kills the session's shell).

## Parent package state carried from `main` (session 9, chartbook — D-S9-006)

Kept verbatim from main's HANDOFF at the merge of 2026-09-10; the debt
extension above does not change any of it.

### Deliverables, notebooks and tests of the parent package (D-S9-002…006)

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
- **`deliverables/strict_{GBR,FRA,DEU}.csv`** (D-S9-005) — one file per
  country, every charted series as a column, every year as a row, STRICT
  ONLY. Column names are `line_code - line_label`. The ledger's TR/TE are
  prefixed `LEDGER_` because they are the balance anchor's own totals, not
  the trees' TE/TR (they differ by up to 0.5% for GBR). Rows run to the
  last year any strict series reaches (GBR 2030, FRA/DEU 2070), not the
  chartbook's 2031 display cap.
- **Statistical benchmark forecasts** (D-S9-007) —
  `ggfiscal statistical-forecasts` writes
  `deliverables/statistical_forecasts.csv` (60 series x 5 methods to
  2031: auto.arima, ets, prophet, unobserved components, and their
  combination), and six notebooks
  `forecasts_{GBR,FRA,DEU}_{expenditure,revenue}.ipynb` chart them. Fitted
  on OUTTURN ONLY so the official projection can be read against the
  model; a benchmark, never a rival — nothing enters the canonical layer.
  Needs `pip install -e .[forecast]`.
- **The forward-balance section** (D-S9-006, chartbook §4.4) — why a
  forward `explained_share` exists where a forward "our NLB" does not: a
  level needs every component, a change does not. Plus the chart that
  makes the forward comparison honestly (WEO path vs the base year moved
  only by covered lines). Do not re-derive this; the answer is written up
  in the notebook.
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
- **`tests/deliverables/test_flat_files.py`** (47 tests) enforces the three
  invariants: nothing recomputed (bit-exact copy, `float_precision=
  "round_trip"`), every chained value reproducible from the flat file alone,
  and the data dictionary covering every column of every file by set
  equality. Both notebooks are checked for committed, error-free outputs,
  and the chartbook for charting every catalogued series.
- **Packaging fixes**: `openpyxl` and `xlrd` are now real dependencies (the
  committed OBR snapshots are unreadable without them — session 5 left them
  as a manual install step), plus a `notebook` extra.

### Parent baseline

`pytest`: **122 passed** (90 + 32 new). `validate`: **OK=55 WARN=820, no
ERROR, no SKIP**. The WARN count is up from 661 on source-vintage drift
alone (V25/V1 concept wedges against refreshed Eurostat/OECD/AMECO pulls of
2026-09-08); no new check, no new tier, no ERROR.

### Fresh container (parent package)

Fresh container: `pip install -e .[dev]` (openpyxl/xlrd now come with it;
use `python3 -m pytest`), `ggfiscal fetch --all`, then
`build`, `reconcile`, `report` (which now also writes `deliverables/`),
`validate`. The OBR raw bytes come with the clone (D-S7-001) — do NOT expect
`fetch` to produce them. Expected green baseline on the 2026-09-08 harvest:
122 passed; validate no ERROR, no SKIP. **After any rebuild, re-execute both
notebooks** (`jupyter nbconvert --execute --inplace notebooks/*.ipynb`) so
their committed outputs match the bundle.

### Parent data facts (sessions 4–9)

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
- **`main` is red for reasons that are not the fiscal work's** (checked at
  7003193, D-S9-007): `ggfiscal report` aborts with `KeyError: nan` in
  `validate/runner.py:166`, the non-debt suite is 16 failed / 106 passed
  and `tests/debt` 33 failed / 21 errors, all identically with and without
  the fiscal branch applied. Regenerate the README with
  `report.readme.write()` directly until `report` runs again.
- statsmodels only forecasts past a `RangeIndex`. ETS and UC must be
  handed a 0..n-1 indexed Series (`forecast.statistical._positional`), not
  a year-indexed one and not a bare ndarray; the year index is put back by
  the caller. Whether pandas hands back a RangeIndex or a plain Index for
  a year column is incidental, which is what made this look like a
  per-series flake.
- The §8.3 forecast decomposition is additive ONLY with
  `weo_internal_wedge` in the identity: covered_total + denom_effect +
  residuals + wedge = weo_change (to 1e-9). The WEO's own GGR - GGX does
  not equal its GGXCNL exactly, and that is reported, not absorbed.
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

