# Source family: eurostat_insee_oecd

Stage D0 harvest report for `EUROSTAT_GOV10A_MAIN_S1311`, `EUROSTAT_GOV10DD`,
`EUROSTAT_PRC_HICP`, `EUROSTAT_IRT`, `INSEE_IPC`, `INSEE_AFT_AGG`,
`OECD_T7PSD`, `OECD_FINMARK` (DEBT_KICKOFF.md §13). All 59 pulls in
`ggfiscal.debt.families.eurostat_insee_oecd.pulls()` succeeded on the first
`ggfiscal debt fetch --family eurostat_insee_oecd` run (2026-09-09) — no
`INVALID_QUERY_DIMENSION_VALUE` rejections, because every key was probed
live against the dataflow's SDMX 2.1 content-constraint before being wired
into `pulls()` (see §2 below). `tests/debt/test_eurostat_insee_oecd.py`:
13/13 green.

## 1. Per-part harvest record

All URLs `GET`, HTTP 200. `n` = data rows in the snapshot (INSEE: rows of
the `tableau-series` HTML table). Eurostat/OECD periods are the raw
`TIME_PERIOD` string (annual `"1995"`, monthly `"1999-12"`, quarterly
`"2000-Q1"`); INSEE periods are `YYYY-MM`.

### EUROSTAT_GOV10A_MAIN_S1311 — `gov_10a_main`, key `A.MIO_NAC.*.{na_item}.{geo}`

| part | bytes | sha256[:12] | n | first | last |
|---|---:|---|---:|---|---|
| gov_10a_main_D41PAY_FR | 12,584 | f68700424af5 | 172 | 1978 | 2025 |
| gov_10a_main_D41PAY_DE | 11,551 | 1270e74f9027 | 155 | 1995 | 2025 |
| gov_10a_main_B9_FR | 12,027 | be9b2fc46d10 | 172 | 1978 | 2025 |
| gov_10a_main_B9_DE | 11,076 | bd00fe0ae307 | 155 | 1995 | 2025 |

Sector wildcarded (`*`) returns all 5 subsectors (S13, S1311, S1312, S1313,
S1314) in one pull instead of one pull per subsector. FR is not uniformly
1995-: `S1312` (local government) D41PAY runs 1978-2025 (48 obs) while
S13/S1311/S1313/S1314 run 1995-2025 (31 obs each) — a genuine Eurostat
data-availability asymmetry, not a parsing artefact.

### EUROSTAT_GOV10DD — `gov_10dd_ggd`, `gov_10dd_rmd`, `gov_10dd_edpt1/2/3`, `gov_10dd_dcur`, `gov_10q_ggdebt`

| part | bytes | sha256[:12] | n | first | last |
|---|---:|---|---:|---|---|
| gov_10dd_ggd_S1311_FR | 69,041 | c6df3fa9b3a7 | 852 | 2020 | 2025 |
| gov_10dd_ggd_S1311_DE | 935,450 | df0b5281144a | 11,436 | 1995 | 2025 |
| gov_10dd_ggd_S13_FR | 35,633 | 9be83f81ecd4 | 444 | 2020 | 2025 |
| gov_10dd_ggd_S13_DE | 438,940 | 6f94f3d5bb9a | 5,454 | 1995 | 2025 |
| gov_10dd_rmd_FR | 12,651 | ef586d05bd39 | 168 | 2020 | 2025 |
| gov_10dd_rmd_DE | 54,839 | 1f3ac75f38fa | 732 | 1995 | 2025 |
| gov_10dd_edpt1_FR | 128,754 | a3c69ea37163 | 1,752 | 1995 | 2025 |
| gov_10dd_edpt1_DE | 135,228 | 8b3342ca8f2e | 1,845 | 1995 | 2025 |
| gov_10dd_edpt2_FR | 100,052 | b813a70fceb8 | 1,303 | 2009 | 2025 |
| gov_10dd_edpt2_DE | 54,623 | 52b19a9c2f78 | 714 | 2022 | 2025 |
| gov_10dd_edpt3_FR | 159,081 | 3febd47e3c75 | 2,115 | 2021 | 2025 |
| gov_10dd_edpt3_DE | 159,445 | 298ba0a0ebd0 | 2,121 | 2022 | 2025 |
| gov_10dd_dcur_FR | 8,072 | 7bc211e8b320 | 108 | 2020 | 2025 |
| gov_10dd_dcur_DE | 58,783 | db92bcdd8022 | 793 | 1995 | 2025 |
| gov_10q_ggdebt_FR | 417,058 | cbb44bcd35ee | 5,526 | 2000-Q1 | 2026-Q1 |
| gov_10q_ggdebt_DE | 421,937 | d8066883dc1a | 5,526 | 2000-Q1 | 2026-Q1 |

**FRA's EDP-notification tables (`gov_10dd_ggd`, `gov_10dd_rmd`,
`gov_10dd_dcur`) only go back to 2020**, not 1995 as the kickoff / config
note implies for the family as a whole — DEU has the full 1995- history in
these three tables. `gov_10dd_edpt1` is 1995- for both countries;
`gov_10dd_edpt2`/`edpt3` (the stock-flow-adjustment tables) start later
still and asymmetrically (FR 2009/2021, DE 2022/2022). **Config correction**:
`config/debt_sources.yaml`'s `EUROSTAT_GOV10DD` entry should read "1995- for
DEU; FRA's gov_10dd_ggd/rmd/dcur are 2020- only, edpt2/3 2009-/2021-" rather
than a blanket "1995-".

### EUROSTAT_PRC_HICP — `prc_hicp_minr` (I25, current), `prc_hicp_midx` (I15, archive)

| part | bytes | sha256[:12] | n | first | last |
|---|---:|---|---:|---|---|
| prc_hicp_minr_EA | 22,711 | daa373810367 | 320 | 1999-12 | 2026-07 |
| prc_hicp_minr_FR | 26,047 | 0a1c30cfa07c | 367 | 1996-01 | 2026-07 |
| prc_hicp_minr_DE | 26,046 | 9dfbdc387d52 | 367 | 1996-01 | 2026-07 |
| prc_hicp_midx_EA | 21,292 | 8735b10406d7 | 301 | 2000-12 | 2025-12 |
| prc_hicp_midx_FR | 25,420 | d6795b5c828f | 360 | 1996-01 | 2025-12 |
| prc_hicp_midx_DE | 25,052 | 70f885abe480 | 360 | 1996-01 | 2025-12 |

**Correction**: `prc_hicp_minr`'s coicop dimension column is named
`coicop18`; `prc_hicp_midx`'s is named `coicop` (not `coicop18`) — the
reader's `eurostat()` lower-cases and keeps whatever the dataflow calls it,
so `debt_by_maturity`-style callers must not assume a fixed column name
across the two prc_hicp dataflows.

### EUROSTAT_IRT — `irt_st_m`, `irt_lt_mcby_m`

| part | bytes | sha256[:12] | n | first | last |
|---|---:|---|---:|---|---|
| irt_st_m_IRT_M3 | 26,608 | f6e7d537447c | 440 | 1990-01 | 2026-08 |
| irt_st_m_IRT_M6 | 23,682 | 458083c9d390 | 392 | 1994-01 | 2026-08 |
| irt_lt_mcby_m_FR | 35,405 | 036265a64d6c | 559 | 1980-01 | 2026-07 |
| irt_lt_mcby_m_DE | 35,346 | 73bb7701bf7e | 559 | 1980-01 | 2026-07 |
| irt_lt_mcby_m_EA | 27,766 | 03414dc3d486 | 439 | 1990-01 | 2026-07 |

### INSEE_IPC — `serie/ajax/{idbank}`

| part (idbank) | bytes | sha256[:12] | n | first | last | title |
|---|---:|---|---:|---|---|---|
| 001763852 | 91,882 | c72afa9b6cfb | 432 | 1990-01 | 2025-12 | IPC base 2015, France, ensemble hors tabac (arrêtée) |
| 011814056 | 78,221 | 6f56dedbe259 | 367 | 1996-01 | 2026-07 | IPC base 2025, France, ensemble hors Tabac |
| 001764305 | 77,600 | 6483a8d6ae37 | 432 | 1990-01 | 2025-12 | IPC base 2015, France métropolitaine, hors tabac (arrêtée) |

### INSEE_AFT_AGG — `serie/ajax/{idbank}`

All 16 idbanks: 211 monthly observations, 2009-01 to 2026-07 (bytes
37,589-39,416, listed in `data/manifest/snapshots.jsonl`).

### OECD_T7PSD — `DSD_NASEC20@DF_T7PSD_Q`, key `Q..{ISO3}...............`

| part | bytes | sha256[:12] | n | first | last |
|---|---:|---|---:|---|---|
| T7PSD_GBR | 28,703,252 | fdff9d82420b | 43,685 | 1995-Q1 | 2026-Q2 |
| T7PSD_FRA | 8,500,910 | 0d9c07ca8de0 | 13,333 | 1980-Q4 | 2026-Q2 |
| T7PSD_DEU | 5,363,919 | a28ddaa46847 | 8,510 | 1991-Q4 | 2026-Q2 |

`SECTOR=S1` (total economy) rows start at each country's file start (GBR
1995-Q1, FRA 1980-Q4, DEU 1991-Q4), matching the config note. `SECTOR=S1311`
(central government) itself starts later for two of the three: GBR
1995-Q1 (= file start), **FRA 1998-Q4** (not 1980-Q4 — S1311 is absent for
1980-1998, only `S1` is populated that far back), DEU 1995-Q1 (= S13
start). Confirmed by grouping `oecd_psd(iso3)` on `sector`.

### OECD_FINMARK — `DSD_STES@DF_FINMARK`, key `{ISO3}.M.{measure}.PA.......`

| part | bytes | sha256[:12] | n | first | last |
|---|---:|---|---:|---|---|
| FINMARK_IR3TIB_GBR | 136,609 | 94e6ed360853 | 482 | 1986-01 | 2026-02 |
| FINMARK_IR3TIB_FRA | 187,125 | 17526abab0ab | 680 | 1970-01 | 2026-08 |
| FINMARK_IR3TIB_DEU | 220,166 | 5a36f9bd1958 | 800 | 1960-01 | 2026-08 |
| FINMARK_IRLT_GBR | 222,904 | fe6c4241860e | 800 | 1960-01 | 2026-08 |
| FINMARK_IRLT_FRA | 215,447 | 1e0e7af295c0 | 799 | 1960-01 | 2026-07 |
| FINMARK_IRLT_DEU | 229,313 | db161074c1bf | 844 | 1956-05 | 2026-08 |

Matches the config note (`IR3TIB` FRA 1970-, DEU 1960-, GBR 1986-; `IRLT`
1956/1960-) exactly.

## 2. Key-order corrections found live (2026-09-09)

The kickoff's guessed key orders were verified against each dataflow's
SDMX 2.1 content-constraint (`.../contentconstraint/ESTAT/{DATASET}`, whose
`CubeRegion` lists dimensions in key order) and a live probe before wiring
`pulls()`. One correction was found:

* **`gov_10dd_ggd`**: actual key order is
  `freq.na_item.sector2.sector.maturity.unit.geo`. The kickoff note guessed
  `freq.na_item.sector.sector2.maturity.unit.geo` — **`sector` and `sector2`
  are swapped**. `sector2` is the debt *holder* (codelist: `S1_S2` holders
  total, `S1` total economy, `S11` non-financial corporations, `S12`/`S121`/
  `S122_S123`/`S124-S129` financial corporations incl. the central bank,
  `S1311..S1314` the four GG subsectors as holders of each other's debt,
  `S14_S15` households/NPISH, `S2` rest of world); `sector` is the *issuing*
  subsector (`S13`, `S1311`, `S1312`, `S1313`, `S1314`). Confirmed by fixing
  the third key position to `S1311` and observing the *fourth* CSV column
  (`sector`, not `sector2`) vary across S1311/S1312/S1313/S1314 while the
  third (`sector2`) stayed fixed. No `INVALID_QUERY_DIMENSION_VALUE` was hit
  because every key was probed with a wildcard-heavy test query before being
  placed in `pulls()` — an accidental wrong-order key with a real code in
  every position simply returns 0 rows rather than an error (seen when
  `gov_10dd_rmd`'s `S1311` was probed against FRA, which genuinely has no
  `S1311` rows there — worth flagging as a general hazard: an empty CSV can
  mean either "wrong key order" or "no data for this combination", and only
  a full-wildcard probe against a country/table known to have broad
  coverage (here DEU) disambiguates).
* All other key orders in the kickoff note (`gov_10dd_rmd`
  `freq.sector.maturity.na_item.unit.geo`; `gov_10dd_edpt1/2/3`
  `freq.unit.sector.na_item.geo`; `gov_10dd_dcur`
  `freq.sector.currency.na_item.unit.geo`; `gov_10q_ggdebt`
  `freq.na_item.sector.unit.geo`) were confirmed correct as stated.
* The SDMX 3.0 key parser accepts `*` independently per dimension (not just
  one wildcard total), so most `gov_10dd_*` pulls wildcard every dimension
  except `geo` (and, for `gov_10dd_ggd`, `sector`) — one pull per country
  returns the whole table.
* OECD's 18-dimension `DF_T7PSD_Q` key and 9-dimension `DF_FINMARK` key from
  the kickoff (`Q..{ISO3}...............` and
  `{ISO3}.M.{measure}.PA.......`) worked exactly as given, no correction
  needed. `format=csvfilewithlabels` returns a code column *and* a
  same-row label column per dimension (e.g. `SECTOR`, `Institutional
  sector`) with no explicit `Accept` header required.

## 3. Codelists discovered

### `na_item` (ESTAT NA_ITEM codelist), the items used in `gov_10a_main` / `gov_10dd_ggd`

| code | label |
|---|---|
| D41PAY | Interest, expenditure |
| B9 | Net lending (+)/net borrowing (-) |
| GD | Government consolidated gross debt |
| GD_F2 / F21 / F22 / F29 | ... at face value — currency and deposits / currency / transferable deposits / other deposits |
| GD_F3 | ... at face value — debt securities |
| GD_F32Z | ... long-term debt securities, of which zero-coupon |
| GD_F4 | ... at face value — loans |
| GD_VAR | ... at variable interest |
| F_GD | Transactions in Maastricht debt instruments at market value |
| F4 | Loans |

### `na_item` for `gov_10dd_edpt2` (working balance -> B.9, the §8 step-A/B financing bridge) and `gov_10dd_edpt3` (B.9 -> change in Maastricht debt, the stock-flow adjustment proper)

edpt2 reconciles the cash-based "working balance" to accrual B.9:

| code | label |
|---|---|
| B9 | Net lending (+)/net borrowing (-) |
| B9_OB | ... of other bodies of the subsector included in the working balance |
| ORWB | Working balance |
| ORWB_E | Working balance (+/-) of entities not part of the subsector |
| OROA_ORWB | Other adjustments (+/-) included in the working balance |
| FT | Financial transactions included in the working balance |
| F4_ORWB / F5_ORWB / FNDX_ORWB | ... loans / equity / other financial transactions included in the working balance |
| ORNF_ORWB | Non-financial transactions not included in the working balance |
| ORD41A_ORWB | Difference between interest (D.41) paid (+) and accrued (-) included in the working balance |
| F8_ASS_ORWB / F8_LIAB_ORWB | Other accounts receivable/payable included in the working balance |

edpt3 is B.9 to the change in gross debt — this **is** the `debt_financing_reconciliation` step-B stock-flow-adjustment source (§8):

| code | label | maps to §8 item |
|---|---|---|
| B9_T3 | Net lending(-)/borrowing(+), reversed sign | (sign convention check) |
| GD_CH | Change in consolidated gross debt | target of the bridge |
| F4_ASS / F3_ASS / F5_ASS / F2_ASS | Net acquisition of financial assets by instrument | `sfa_financial_transactions` |
| KX | Other volume changes in financial liabilities | `sfa_other` |
| K61 | Changes in sector classification and structure | `sfa_other` |
| ORINV | Issuances above/below nominal value | `sfa_accrual_adjustments` (premium/discount) |
| ORRNV | Redemptions/repurchase above/below nominal value | `sfa_accrual_adjustments` |
| ORD41A_ADJ | Interest (D.41) accrued vs paid | `sfa_accrual_adjustments` |
| ORFCD | FX appreciation/depreciation of foreign-currency debt | `sfa_other` |
| YA3 / YA3O | Statistical discrepancies | `residual` |
| ORADJ | Total adjustments | (checksum) |

Full code -> label mapping is embedded in
`src/ggfiscal/debt/readers/eurostat_insee_oecd.py::NA_ITEM_LABELS` and
attached to `sfa_components()`'s output as `na_item_label`.

### `maturity` (gov_10dd_rmd, gov_10dd_ggd)

`TOTAL` (all), `Y_LE1` (<=1y), `Y1-5` (1-5y), `Y_GT1` (>1y), `Y5-10`
(5-10y), `Y10-30` (10-30y), `Y_GT30` (>30y) — 7 codes in the ESTAT codelist,
confirmed present in full for e.g. Belgium. **DEU only publishes 4 of the
7** (`TOTAL`, `Y_LE1`, `Y1-5`, `Y_GT1`) in `gov_10dd_rmd` for both S13 and
S1311 — `Y5-10`/`Y10-30`/`Y_GT30` are simply absent from DEU's rows, not a
reader bug. **Correction to the kickoff task brief**: the expected test
"`debt_by_maturity('DEU')` has 1995 rows and the 7 maturity codes" does not
hold for DEU with the default `sector='S1311'` (which only starts 2004 in
`gov_10dd_rmd`) nor with `sector='S13'` (1995-, but only 4 maturity codes).
`tests/debt/test_eurostat_insee_oecd.py::test_debt_by_maturity_deu_s13_has_1995_and_maturity_codes`
uses `sector='S13'` and asserts the 4 codes actually present, documenting
the gap rather than papering over it.

### OECD `DF_T7PSD_Q` dimension codelists (`SECTOR`, `INSTR_ASSET`, `MATURITY`, `DEBT_BREAKDOWN`, `UNIT_MEASURE`), from the GBR file's label columns

| SECTOR | label |
|---|---|
| S1311 | Central government |
| S13 | General government |
| S1311B | Budgetary Central Government |
| S1ZS | Public sector |
| S11001 / S12001 | Public non-financial / financial corporations |
| S1 | Total economy |

| INSTR_ASSET | label |
|---|---|
| F2 | Currency and deposits |
| F3 | Debt securities |
| F4 | Loans |
| F6 | Insurance, pension and standardized guarantee schemes |
| F8 | Other accounts receivable/payable |
| F12 | Special Drawing Rights |
| FD4 | Total gross debt |
| FLD / FLE | Total gross debt held by domestic / external creditors |
| B1GC | GDP rolling sum |

| MATURITY | label |
|---|---|
| S | Short-term original maturity (<=1y) |
| L | Long-term original maturity (>1y) |
| LS | Long-term with residual maturity <=1y |
| LL | Long-term with residual maturity >1y |
| T | All original maturities |

| DEBT_BREAKDOWN | label |
|---|---|
| INST | Financial instrument |
| RES | Creditor residence |
| CUR | Currency of denomination |
| _Z | Not applicable |

## 4. Chaining factors

### `fr_cpi_ex_tobacco_chained()` — INSEE 001763852 (base 2015) -> 011814056 (base 2025)

360 overlap months (1996-01 to 2025-12, the full run of both series before
001763852 stops). Ratio `new/old` over the overlap: min 0.83452, max
0.83470, mean **0.8346** — constant to 4 decimal places for all but a
handful of boundary months (the ±0.0002 spread is consistent with the
published index values' own 2-decimal-place rounding, not a base-year
drift). `fr_cpi_ex_tobacco_chained()` rescales 001763852 by the mean factor
0.8346 and switches to 011814056 at its first observation (1996-01), giving
a continuous series 1990-01 to 2026-07 with no month-on-month move
exceeding 1.45% (test asserts <5%).

### `hicp_ex_tobacco_chained(geo)` — Eurostat prc_hicp_midx (I15) -> prc_hicp_minr (I25)

Same method, computed per call and exposed via `.attrs["chain_factor"]` /
`.attrs["overlap_months"]` on the returned Series (not hardcoded, since the
I15/I25 overlap length differs by geo: EA overlap starts 2000-12, FR/DE
1996-01, all running to 2025-12).

## 5. Config corrections (for `config/debt_sources.yaml` / DEBT_KICKOFF.md §13, §6.3)

1. **`EUROSTAT_GOV10DD`** object line should note that `gov_10dd_ggd`,
   `gov_10dd_rmd` and `gov_10dd_dcur` are **2020- only for FRA** (DEU has
   1995-); `gov_10dd_edpt2`/`edpt3` start later still, asymmetrically by
   country (FR 2009-/2021-, DE 2022-/2022-). Only `gov_10a_main` (separate
   source id) and `gov_10dd_edpt1` are 1995- for both countries.
2. **`gov_10dd_ggd` key order**: `freq.na_item.sector2.sector.maturity.unit.geo`,
   not `freq.na_item.sector.sector2...` — §2 above.
3. **`prc_hicp_minr` vs `prc_hicp_midx`**: the coicop dimension is named
   `coicop18` in the former and `coicop` in the latter; code `TOT_X_TBC` is
   correct for both as stated.
4. **DEU `gov_10dd_rmd`**: `sector=S1311` only starts 2004 (not 1995); use
   `sector=S13` for the full 1995- history. Only 4 of the 7 standard
   maturity bands are published for DEU (no `Y5-10`/`Y10-30`/`Y_GT30`).
5. **`OECD_T7PSD`**: the config note "FRA 1980Q4-" is true only for
   `SECTOR=S1` (total economy); `SECTOR=S1311` (central government, the one
   the debt register actually needs) starts **1998-Q4** for FRA. GBR and DEU
   have no such gap (S1311 starts at the file's own start).
6. No dimension value was ever rejected by the API
   (`INVALID_QUERY_DIMENSION_VALUE`) once keys were probed against each
   dataflow's content-constraint before being wired into `pulls()` — see §2
   for the general hazard (a wrong key order can return an empty-but-valid
   CSV rather than an error) and how it was avoided.

## 6. Function surface (`src/ggfiscal/debt/readers/eurostat_insee_oecd.py`)

`eurostat(part)`, `d41pay(iso3, sector)`, `b9(iso3, sector)`,
`debt_by_maturity(iso3, sector='S1311')`, `debt_by_instrument(iso3, sector)`,
`quarterly_debt(iso3, sector)`, `sfa_components(iso3)`,
`hicp_ex_tobacco(geo='EA', base='I25')`, `hicp_ex_tobacco_chained(geo='EA')`,
`ea_money_market(tenor='3M')`, `long_term_yield(geo)`,
`insee_series(idbank)`, `fr_cpi_ex_tobacco_chained()`, `aft_aggregates()`,
`oecd_psd(iso3)`, `oecd_rate(iso3, measure)`. All covered by
`tests/debt/test_eurostat_insee_oecd.py` (13 tests, green against the
harvested snapshots; the module `pytest.mark.skipif`s cleanly when the
snapshot store is empty).
