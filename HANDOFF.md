# HANDOFF.md

Rewritten 2026-09-19, end of session 11 (pensions, social benefits and the
economic tree, on `claude/redbox-social-benefits-pensions-f52j5a` branched
from `main` at 8b99c74).

## Current stage

**All parent-package stages 0–6 remain complete on a 123-line universe
(D-S13-001/005): three trees per country — 17 COFOG lines (ten Level I plus
the Level II splits GF01_7 interest, GF10_2 old age, GF10_5 unemployment,
GF04_5 transport, each with its remainder), 9 ESA_EXP lines (expenditure by
economic type) and 15 ESA_REV lines (ten ESA types plus R02_A excise duties
and the R06_E/R06_H employers'/households' contributions split, with
remainders).** The specification carries the v2.3 addendum (§4.1a, §4.1b,
§4.2a). The debt extension (DEBT_KICKOFF.md) is untouched.

## What session 11 did (D-S13-001..006; OQ-10 raised and resolved)

- **Fresh harvest** (`ggfiscal fetch --all`, 2026-09-19, 0 failures); the
  rebuild changed no value in the pre-existing 66 series (run_id only).
- **Level II is a config mechanism** for every tree: `config.level2_splits()`
  returns one entry per parent (ordered Level II lines, one remainder whose
  `minus` lists them all, per-line anchor cells / GFS indicator / OECD RS
  headings); build, coverage, V19, the stitched-year remainder derivation,
  the small multiples, the flat files and `tools/update_notebooks_s11.py`
  iterate it. A further group is one config entry plus its remainder,
  sources, crosswalk row and a re-run of the notebook script.
- **Pensions `GF10_2`** (COFOG 10.2): FRA/DEU strict to 2070 on the Ageing
  Report (1.07, B); GBR back to 1979 in maximum on the OBR historical
  pensioner series (0.665, C; committee-approved) and no forecast (EFO 4.9
  has no overlap year).
- **`GF10_5` unemployment, `GF04_5` transport**: anchors only (D7: no
  institution projects them); DEU from 2000.
- **`ESA_EXP` tree** E01–E09 + TE_ESA, identity exact; AMECO grade-A
  forecasts to 2027 and backward legs; **E05 now chains into the DSM to
  2036** beside GF01_7 (committee-approved config rows).
- **`R02_A` excise duties = D.214A + D.2122C** (Germany books its energy tax
  on imports under D.2122C — measured before choosing): GBR strict to 2030
  on six OBR duty series (0.986 B), DEU strict to 2030 on the
  Steuerschätzung excises (0.918 B), FRA declared; OECD 5121 backward
  (FRA/DEU B to 1965/1991, GBR C).
- **`R06_E` / `R06_H`** employers'/households' actual contributions,
  remainder R06_X (imputed and supplementary): GBR maximum to 2030 on EFO
  3.4 NICs by class (0.73/0.74 C — the anchor rows include public-service
  pension contributions); FRA/DEU declared (no split published); OECD
  2200 and 2100+2300 backward (FRA B, DEU B/C, GBR C).
- **Deliverables**: `expenditure_esa.csv`, `classification` column in every
  tree file, strict matrices widened, `statistical_forecasts.csv`
  regenerated; chartbook +Level II charts, `chartbook_esa.ipynb`
  companion, forecast books extended and three `forecasts_{cc}_esa.ipynb`.
- **Verification** that the previously built machinery still works after
  the splits: D-S13-006 lists what was checked (pytest 151 passed; validate
  OK=87 WARN=2092 no ERROR) (identities, the untouched
  20-line WEO decomposition and its explained shares, the benchmark
  forecasts covering exactly the series that need them, the catalogue /
  coverage matrix / strict matrices / chartbooks covering every series).

## Blocked on whom

- Nothing blocking. OQ-10 resolved. Open: OQ-6 (a) an FRS edition with
  state-pension / functional long-term projections would give GBR GF10_2
  (and GF07/GF09/GF10) a strict long-term leg; OQ-8/OQ-9 (debt) unchanged;
  `GF09_4` tertiary education is the one optional split not taken up.

## Exact next command

```
pip install -e ".[dev,forecast,notebook]"
ggfiscal fetch --all && ggfiscal build && ggfiscal reconcile && ggfiscal validate
ggfiscal report && ggfiscal statistical-forecasts
jupyter nbconvert --execute --inplace notebooks/chartbook*.ipynb notebooks/derivation.ipynb notebooks/forecasts_*.ipynb
python3 -m pytest -q --ignore=tests/debt
```

To add the next Level II group: one `level: "2"` entry with its `parent`
and anchor cell (`eurostat_cofog` + `gfs_indicator` for COFOG; `eurostat`
dataset + codes, `ons` table + codes, `oecd_rs` headings for revenue) in
`config/lines.yaml`, the remainder's `minus` list extended (or a new
`level: derived` remainder with `never_forecast: true`), the forecast
sources in `forecast/forward.py` if any, a crosswalk row, then rebuild,
`python3 tools/update_notebooks_s11.py` (inserts the chart and forecast
cells after the parent's), and re-execute the notebooks.

## Data facts future sessions must not rediscover (session 11)

- `gov_10a_exp` is pulled with both `cofog99` and `na_item` wildcarded: the
  snapshot already holds every COFOG group × every ESA transaction (D.62 by
  function included); `readers.eurostat_cofog` reads `na_item == "TE"`. ONS
  Table 11 row 5 carries the transaction codes (P2, D1, D62, D632, …, OTE)
  and the Level II rows; `ons_t11()` reads the OTE column. `gov_10a_main`
  also carries `D62PAY_GF1002/GF1003/GF1005` (cash benefits by function).
- Eurostat DEU Level II starts 2000 for every group (GF0107 has the D.41
  fallback for 1995–99; GF1002 has none). IMF GFS COFOG group indicators are
  `GF{dd}{g}0_T` (GF1020_T = 10.2) and for DEU also start 2000.
- The Ageing Report's "Public pensions, gross" measures 1.07–1.09 of COFOG
  10.2 (B band), 0.97–0.99 (FRA) / 0.90–0.92 (DEU) of 10.2+10.3, 0.61/0.52
  of GF10.
- AMECO chapter 16 has the full economic breakdown for FRA/DEU (UWCG,
  UCTGI, UYTGH, UYTGM, UYIG, UYVG, UUOG, UIGG0, UKTGT, UKOG, UUTG) with
  history from 1978/1991; for the UK only UYTGH, UYTGM, UYIG, UYVG, UIGG0,
  UKTGT carry history (from 1987) — UWCG, UCTGI, UUOG, UUTG are 2026–27
  only. UKTGT (D.9) has no forecast years; UKOG is the forecast candidate.
- ONS ESA Table 2 payable codes: D1, D29, D3P, D4, D41, D4N, D5, D62, D632,
  D7, D9, D92, D99 (+ P2, P5, NP, OTE with no direction). Sum of the twelve
  ESA items = OTE to 0.000% every year 1990–2025.
- The ESA identity in gov_10a_main: TE = P2 + D1PAY + D29PAY + D3PAY + D4PAY
  + D5PAY + D62PAY + D632PAY + D7PAY + D8 + D9PAY + P5 + NP, exact; D8 is
  zero for FRA/DEU government.
- EFO detailed expenditure tables (part `detailed-expenditure`, sheet 4.9
  State pension; 4.10 pensioner spending; 4.13 public service pensions) and
  TA.7 all start FY 2024-25; table 6.1 (economic categories: net social
  benefits) starts FY 2025-26. OBR historical PF database "Spending (£m)"
  has Social Security and "o/w pensioners" 1978-79 → 2022-23 (public
  sector); no 2023-24, so it cannot bridge to the EFO tables.
- Excise duties: Germany's `gov_10a_taxag` D214A (36 EUR bn, 2024) is only
  the domestic part — the energy tax on imported fuels sits in D2122C
  (29 bn); D214A + D2122C = 65 bn = OECD 5121 exactly. The UK NTL D214A
  row ("excise duties and consumption taxes", 62 £bn) also holds air
  passenger duty, the climate change levy, the renewables obligation and
  contracts for difference, landfill, aggregates, soft-drinks and
  plastic-packaging levies — the OBR databank covers 92% of it.
- Contributions: ONS ESA Table 2 has D611 and D613 receivable;
  `gov_10a_main` has D611REC/D613REC (no D612/D614). EFO detailed receipts
  table 3.4 splits NICs by class from FY 2024-25, so CY 2025 overlaps the
  anchor (unlike the welfare and state-pension tables). The anchors'
  D.611/D.613 include employer and employee contributions to public-service
  pension schemes, so NICs cover ~73%.
- OBR historical PF "Spending (£m)": header row 4, FY labels in column B,
  `readers.obr_hist_pf_fy(column)`; the pensioner column is IFS-based from
  1978-79; converted per §7.10 it runs 1979–2022.
- `statistical_forecasts.csv` is not in (iso3, line_code) sorted order once
  the trees are concatenated by classification; the combination test
  reindexes `within`/`between` onto the combination's index.
- The pandas comparison `series_a >= series_b` raises on identically-set,
  differently-ordered indexes — reindex first.
- `pip install -e .[forecast]` (pmdarima, prophet, statsmodels) and
  `.[notebook]` (jupyter, nbconvert, ipykernel) both install cleanly in this
  image; `ggfiscal statistical-forecasts` takes ~4 minutes for 113 series.
- Notebook sizes (D-S9-004, ~1 MB to render on GitHub): the chartbook is
  now three books — `chartbook.ipynb` 0.79 MB (COFOG, ledger, WEO, seams),
  `chartbook_revenue.ipynb` 0.44, `chartbook_esa.ipynb` 0.29. The nine
  forecast books are 0.54–0.96 MB except `forecasts_GBR_expenditure` at
  1.06 MB — split it per the D-S9-004 fallback if GitHub declines to render
  it. `tools/update_notebooks_s11.py` rebuilds the two companion chartbooks
  and the three esa forecast books WITHOUT outputs every run: re-execute
  them (nbconvert) after every run of the script.

## Parent data facts carried forward
## Session 11 (D-S11-001): the forecasts are in the chartbook

`notebooks/chartbook.ipynb` now opens every country section with a forecast
panel — all 22 of that country's categories as a share of GDP from 2000 to
2031, each carrying one forecast, plus a ranked chart of what each line is
forecast to change and a printed table of the same numbers. Facts worth not
rediscovering:

- **The rule is official-beats-statistical, per line, with no top-up.** 20 of
  the 66 granular lines carry an official projection and take it; the other 46
  take the `combination` row of `deliverables/statistical_forecasts.csv`. An
  official path that stops at 2027/2028/2030 stops there on the chart too —
  continuing it with the statistical path would splice a benchmark anchored at
  the last **outturn** onto an official path that has already left it, which is
  a number in no file. Horizons therefore differ across a panel, and every
  readout names its own year.
- **`GF01 = GF01_7 + GF01_X` does not close in the panel, and must not be made
  to.** The three lines can take their forecasts from different sources; for
  France the components come to +1.56 pp against the whole's −0.50 pp. The
  caption computes that gap from the data on every run.
- **VIOLET is appended last in the setup cell's `_palette()`.** The palette is
  positional — put a colour anywhere but the end and every index shifts and
  every figure in the book is rewritten for no visible change. (PIL's
  `optimize=True` drops unused entries when saving, which is why adding it cost
  the existing 105 figures about a kilobyte in total rather than re-encoding
  them.)
- **The chartbook is 1.19 MB, past D-S9-004's 0.9 MB judged margin.** There is
  no cheaper rendering left: figures are palette-quantised and PIL-optimised,
  and recompressing every PNG in the notebook at any level returns the same
  bytes. If GitHub ever declines to render it, take D-S9-004's own fallback and
  split the chartbook one notebook per country — do not shrink the existing
  charts to buy room.
- Re-executing the chartbook in a clean container reproduces its figures
  **byte for byte** (verified against the committed outputs before any edit),
  so a diff in an existing figure means a real change, not a font or version
  wobble.

## Session 11, second part (D-S11-002): the benchmark balance

`ggfiscal benchmark-balance` sums the line forecasts back into an NLB path to
2031 (`forecast/balance.py` → `deliverables/benchmark_balance.csv`), and
chartbook §4.5 plots it. Facts worth not rediscovering:

- **It reads `deliverables/` and nothing else.** Two trees, the ledger, the
  statistical forecasts. No harvest, no canonical layer — so it runs in any
  container that has the bundle, and a test re-derives the committed file from
  the committed bundle.
- **Expenditure is the interest split, never the Level I set.** `GF01_7 +
  GF01_X + GF02..GF10`. Identical to `GF01..GF10` in history to the last
  digit; in forecast it is worth 2.25 pp of GDP for France, because `GF01`'s
  own fit knows nothing about the official interest projection inside it.
  `reconcile/explanation.py` keeps the Level I set for the history
  decomposition — that is correct there and must not be "made consistent".
- **The balance rule is not the panel rule.** §4.5 uses an official projection
  only where it reaches 2031; §*x*.1 prefers one at any horizon. Both are
  deliberate and the file's `source` column names every line where they part.
  Do not splice a statistical tail onto a truncated official path.
- **ρ_within ≈ +0.15, ρ_between ≈ +0.02, estimated per country and horizon**
  from the lines' h-year ratio changes. The cross-side term enters the
  variance with a minus sign, so a larger ρ_between narrows the cone; the
  measured value is near zero, which is why the cone stays wide.
- **The cone is wide and calibrated.** Every row carries the SD of h-year
  moves in that country's own ledger NLB/GDP as a yardstick. At h=7 the model
  band is a little wider than history (UK 6.16 vs 4.74). Do not "fix" it.
- **The 2025 row is a free backtest** — the revenue tree runs a year past the
  expenditure tree, so the first forecast year already has a published balance
  beside it. Misses: UK -1.16, FRA -0.58, DEU +1.30 pp.
- **Still not published: a single nominal GDP forecast.** WEO `NGDP` is
  ingested and used at every forecast horizon, but `weo_levels_bridge.csv`
  emits `gdp_weo_mn` on history rows only. The trees' own forecast-year
  `gdp_lcu_mn` is per-source and the sources disagree (DEU 2030 spans 2.6%),
  so there is no single path to multiply a %-of-GDP forecast by. A currency
  version of §4.5 needs that decision made first.
- `benchmark_balance.csv` is a side-car like `statistical_forecasts.csv`: not
  in `M.FLAT_FILES` (so not in the run manifest), but it **is** in the data
  dictionary, which `test_data_dictionary_covers_every_column_of_every_file`
  requires of every CSV in `deliverables/`.

## Session 11, third part (D-S11-003): the levels charts carry the benchmark

`ggfiscal forecast-levels` puts the statistical forecasts into currency
(`forecast/levels.py` → `deliverables/forecast_levels.csv`) and `chart()` draws
them. Facts worth not rediscovering:

- **api.imf.org IS reachable from the build environment.** D-S11-002 recorded
  otherwise. The 46 `IMF_WEO*` pulls fetch in about a minute, and 48 of the 49
  (source, part) keys came back byte-identical to the earlier harvest — only the
  dataflow `catalog` churns. Re-fetching the WEO is therefore safe and does not
  revise anything.
- **Do not run `ggfiscal reconcile` in a fresh container.** It needs the ONS and
  Eurostat snapshots too — `bridge.anchor_aggregates` reads them, not the
  canonical layer — and without them it writes the reconciliation files back
  EMPTY. Restore with `git checkout -- data/canonical` if it happens.
- **The GDP anchor is 2024, not 2025.** At the last outturn the denominator
  forks by source (GBR three values, DEU two, 1.34% apart), so the anchor is the
  last year every line agrees. A test asserts the fork still exists, so if the
  trees ever agree at the last outturn the anchor should move and the test will
  say so.
- **Chain the WEO's growth, never its level.** NGDP runs 0.97% below our German
  GDP anchor over 2021-2025; substituting the level would step every German
  forecast at the join. This is the same anchor-and-chain rule as every stitched
  series in the project.
- **The band is the ratio's, not the level's.** The GDP path is taken as given,
  so the interval carries no GDP uncertainty. Do not present it as a level
  interval.
- **The chart leg is keyed on `strict`, and anchored on strict's own last
  outturn** — not on `chart()`'s `actual`, which comes from both variants and
  can be a year later where `maximum_extension` carries a stitched 2025. The
  first version raised `IndexError` on GBR GF10 for exactly that reason.
- `forecast_levels.csv` needs the WEO snapshot to regenerate, unlike
  `benchmark_balance.csv` which is a pure function of the bundle. Its
  reproducibility test carries a `needs_weo` skip.
- `no projection published` is now only the six `TE`/`TR` charts. Two schema
  notes were rewritten to match; `GF01_X`'s chart no longer stops at the last
  outturn.

## Session 11, fourth part (D-S11-004): the benchmark against the WEO

`ggfiscal benchmark-vs-weo` (`forecast/weo_compare.py` →
`deliverables/benchmark_vs_weo.csv`) and chartbook §4.6. Facts worth not
rediscovering:

- **Compare CHANGES by side, never levels.** The UK's TR and TE are each ~2.6 pp
  of GDP larger than the WEO's and the balance gap is +0.017 pp — the wedge
  sits on both sides and cancels. It is stable (sd 0.21–0.25 pp over ten years,
  classified `perimeter`), which is what licenses the change comparison, and
  `perimeter_gap_pp` plus its sd are on every row so nobody has to rediscover
  this by comparing two levels.
- **The decomposition includes the WEO's own internal wedge**, Δ((GGR − GGX −
  GGXCNL)/NGDP). It is zero to four decimals on the 2026-04 vintage. Keep the
  row: session 9's note says the wedge is reported and never absorbed, and a
  usually-zero row is the cheap way to keep that true. The identity closes to
  1e-6, not 1e-9 — that is float accumulation on values around 5e12, not a bug.
- **The WEO is inside the benchmark's 80% interval in 21 of 21 country-years**,
  max |z| 0.97. Do not present the gap as a disagreement; it is a statement
  about how wide six-year fiscal uncertainty is.
- **The gaps at 2031**: GBR −5.67 pp (revenue −3.28, expenditure −2.40), FRA
  −3.23 (+0.23 / −3.49), DEU +1.19 (+0.53 / +0.62). Germany is the one country
  where the benchmark is less pessimistic, because the WEO embeds the announced
  spending expansion.
- **The section must not judge.** The benchmark knows only history, the WEO
  embeds policy; where they differ the difference is the policy. A test pins
  that the prose says so.
- Aqua stays the IMF WEO and carries a direct text label, because it is below
  3:1 on this surface. Do not solve that by changing the hue.

## Parent package state carried from `main` (session 9, chartbook — D-S9-006)

Everything in the session-9 HANDOFF (git history at 8b99c74: `latest_snapshots`
shadowing, float round-trip, notebook size, statsmodels RangeIndex, the two
GBR TE numbers, `weo_internal_wedge`) still holds and is not repeated here.

## §15 dependencies currently riding on defaults

Unchanged: Q1, Q3, Q4, Q8, Q10, Q13 on defaults (Q13 revisited in OQ-10);
Q11 pinned (D-S6-001); Q7 and Q12 exercised.
