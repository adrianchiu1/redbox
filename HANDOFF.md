# HANDOFF.md

Rewritten 2026-09-19, end of session 11 (pensions, social benefits and the
economic tree, on `claude/redbox-social-benefits-pensions-f52j5a` branched
from `main` at 8b99c74).

## Current stage

**All parent-package stages 0–6 remain complete on a 99-line universe
(D-S11-001): three trees per country — 14 COFOG lines (the GF01_7/GF01_X
interest split and the new GF10_2/GF10_X old-age pension split), 9 ESA_EXP
lines (expenditure by economic type, new) and 10 ESA_REV lines.** The
specification carries a v2.3 addendum (§4.1a, §4.1b) recording both. The
debt extension (DEBT_KICKOFF.md) is untouched.

## What session 11 did (D-S11-001..004; OQ-10)

- **Fresh harvest** (`ggfiscal fetch --all`, 2026-09-19, 0 failures): the
  parent-package raw snapshots were absent from this container; the rebuild
  on the new pulls changed no value in any tree (run_id only).
- **Level II is a config mechanism**: `config.level2_splits()` enumerates
  every `level: "2"` line and its derived remainder from `config/lines.yaml`;
  build, coverage, V19, stitched-year derivation and the flat files iterate
  it. A further COFOG group is one config entry plus its remainder.
- **`GF10_2` Old age (COFOG 10.2) = pensions**, remainder `GF10_X`. Anchors
  GBR/FRA 1995–2024, DEU 2000–2024 (Eurostat DEU Level II lacks 1995–99 and
  the GFS group series also starts 2000). FRA/DEU strict to 2070 on the
  Ageing Report's gross public pensions (measured 1.07 of the line, grade B);
  GBR has no applicable forecast (EFO 4.9 State pension starts FY 2024-25 —
  no overlap year; declared `source_blocked`).
- **`ESA_EXP` tree** E01–E09 + `TE_ESA` from gov_10a_main payable items
  (FRA/DEU) and ONS ESA Table 2 payable rows (GBR); identity to TE exact
  everywhere (V2). AMECO is the direct grade-A forecast (to 2027) and the
  backward source (FRA 1978, DEU 1991, GBR 1987) for E01–E07; E08/E09 are
  §7.8 proxies (maximum); GBR E01/E02/E07 have no AMECO history (declared).
  `E03` D.62 is the social-benefits line the committee asked for. FRA/DEU
  `E05` ← DSM is withheld by V16 (the approval list names GF01_7 only;
  OQ-10 c).
- **Validators**: `build.load_trees()` feeds every classification-agnostic
  check; V2 now also checks E01..E09 = TE_ESA; V19 checks every split; V20
  covers E05; V15 has an ESA_EXP arm against the same TE envelope. Counts
  (66/72/12/10) are derived from config everywhere.
- **Deliverables**: `expenditure_esa.csv` (new), `classification` column in
  every tree file, catalogue and coverage matrix keyed by classification,
  `strict_{cc}.csv` columns GDP → COFOG → ESA_EXP → revenue → ledger,
  `statistical_forecasts.csv` regenerated (91 series). Notebooks:
  chartbook +6 charts (pension split), `chartbook_esa.ipynb` (new
  companion, 30 charts), `forecasts_{cc}_expenditure` +2 series each,
  `forecasts_{cc}_esa.ipynb` (new ×3); cell surgery scripted in
  `tools/update_notebooks_s11.py`.
- **Review of every line for further breakdowns** → OQ-10, with measured
  shares: recommended `GF10_5` unemployment, `GF04_5` transport, `R02_A`
  excise duties and the R06 employers'/households' split; no further GF01
  split (its non-interest groups are coded differently across the three
  offices; the transfer content is now `E07`).

## Blocked on whom

- **OQ-10 (committee)**: (a) confirm the four recommended breakdowns;
  (b) approve the OBR historical pensioner-spending series as a C-band
  backward leg for GBR GF10_2 (to 1978); (c) one config row each to let
  FRA/DEU E05 chain into the DSM path like GF01_7.
- OQ-6 (a) unchanged: an FRS edition with long-term state-pension /
  functional projections would give GBR GF10_2 (and GF07/GF09/GF10) a
  strict long-term leg.
- OQ-8/OQ-9 (debt) unchanged.

## Exact next command

```
pip install -e ".[dev,forecast,notebook]"
ggfiscal fetch --all && ggfiscal build && ggfiscal reconcile && ggfiscal validate
ggfiscal report && ggfiscal statistical-forecasts
jupyter nbconvert --execute --inplace notebooks/chartbook*.ipynb notebooks/derivation.ipynb notebooks/forecasts_*.ipynb
python3 -m pytest -q --ignore=tests/debt
```

To add the next Level II group (OQ-10 a): one `level: "2"` entry with its
`parent`, `eurostat_cofog` and `gfs_indicator` in `config/lines.yaml`, its
`level: derived` remainder with `minus:` and `never_forecast: true`, the
sources in `forecast/forward.py` and `stitch/backward.py`, a crosswalk row,
a `chart(...)` cell per country (`tools/update_notebooks_s11.py` shows the
pattern), then rebuild and re-execute.

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
- `statistical_forecasts.csv` is not in (iso3, line_code) sorted order once
  the trees are concatenated by classification; the combination test
  reindexes `within`/`between` onto the combination's index.
- The pandas comparison `series_a >= series_b` raises on identically-set,
  differently-ordered indexes — reindex first.
- `pip install -e .[forecast]` (pmdarima, prophet, statsmodels) and
  `.[notebook]` (jupyter, nbconvert, ipykernel) both install cleanly in this
  image; `ggfiscal statistical-forecasts` takes ~3 minutes for 91 series.
- The chartbook must stay under ~1 MB (D-S9-004): the pension split fits;
  the economic tree does not, hence `chartbook_esa.ipynb`.

## Parent data facts carried forward

Everything in the session-9 HANDOFF (git history at 8b99c74: `latest_snapshots`
shadowing, float round-trip, notebook size, statsmodels RangeIndex, the two
GBR TE numbers, `weo_internal_wedge`) still holds and is not repeated here.

## §15 dependencies currently riding on defaults

Unchanged: Q1, Q3, Q4, Q8, Q10, Q13 on defaults (Q13 revisited in OQ-10);
Q11 pinned (D-S6-001); Q7 and Q12 exercised.
