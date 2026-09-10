# GBR aggregate class-level layer (DD8) — build report

`src/ggfiscal/debt/aggregates_gbr.py` → `class_aggregates(run_id)`, in the
`ggfiscal.debt.aggregates.COLUMNS` shape, validated by `aggregates.SCHEMA`.
Built 2026-09-09 against the snapshot vintage of the same day (ONS release
2026-08-20; DMR 2026-27; NLF 2024-25; BoE APF 2026-09-09).

**818 rows**, one per (`iso3='GBR'`, `year`, `instrument_class`, `sub_type`,
`measure`), calendar years (DD6), £ millions, from official UK aggregates only.
Every value is a publisher's own figure or the §7.10 conversion of one; nothing
is estimated, hand-keyed or allocated (DD13). Tests:
`tests/debt/test_aggregates_gbr.py` — 18 passing.

---

## 1. Coverage by measure

| measure | class / sub_type | source | table / series | years | n | grade |
|---|---|---|---|---|---|---|
| `stock_year_end` | `mixed`/`gilts_all` | ONS_PSF_APPENDIX_A | PSA8A_1 `BKPM`, December month-end | 1997–2025 | 29 | B |
| `stock_year_end` | `mixed`/`gilts_all_march` | ONS_PSF_TIMESERIES | PUSF `BKPM`, **end-March** | 1975–1996 | 22 | C |
| `stock_year_end` | `bill`/`treasury_bills` | ONS_PSF_APPENDIX_A | PSA8A_1 `BKPJ` | 1997–2025 | 29 | A |
| `stock_year_end` | `out_of_register`/`national_savings`, `tax_instruments`, `other_sterling_and_foreign_currency`, `nram_and_bb`, `network_rail` | ONS_PSF_APPENDIX_A | PSA8A_1 `ACUA`, `ACRV`, `KW6Q`, `KW6R`, `MDL3` | 1997–2025 | 5 × 29 | A |
| `stock_year_end` | `fixed_bullet`/`gilts_conventional` | HMT_DMR | table A.1 | 2023–2025 | 3 | B |
| `stock_year_end` | `inflation_linked`/`gilts_index_linked` (uplifted), `…_unindexed`, `…_accrued_uplift` | HMT_DMR | table A.1 | 2023–2025 | 3 × 3 | B |
| `stock_year_end` | `bill`/`treasury_bills_debt_management` | HMT_DMR | table A.1 | 2023–2025 | 3 | B |
| `stock_year_end` | `out_of_register`/`national_savings_dmr`, `ways_and_means`, `sovereign_sukuk` | HMT_DMR | table A.1 | 2023–2025 | 3 × 3 | B |
| `own_holdings` | `fixed_bullet`/`gilts_conventional`, `inflation_linked`/`gilts_index_linked` | HMT_DMR | table A.1 "less government holdings" | 2023–2025 | 2 × 3 | B |
| `own_holdings` | `mixed`/`boe_apf_net_operations` | BOE_APF | operation results, cumulative to 31 Dec | 2009–2025 | 17 | C |
| `own_holdings` | `mixed`/`boe_apf_published_stock` | BOE_APF | maturity-profile table | 2026 (snapshot date) | 1 | B |
| `net_issuance` | `mixed`/`gilts_all` | ONS_PSF_APPENDIX_S | table 1.2A `ANTA` (F.332), 12 months summed | 1997–2025 | 29 | B |
| `net_issuance` | `bill`/`treasury_bills` | ONS_PSF_APPENDIX_S | `NAVG` (F.331) | 1997–2025 | 29 | A |
| `net_issuance` | `out_of_register` × 12 sub_types | ONS_PSF_APPENDIX_S | `-AACE`, `-AACF`, `-EYMW`, `ANTB`, `-AACH`, `-AACI`, `ANTC`, `-AACL`, `-AACM`, `ANTD`, `AIPA`, `ANSZ` | 1997–2025 | 12 × 29 | A |
| `gross_issuance` | `mixed`/`gilts_all` | HMT_DMR | table A.2 gross gilt sales, FY→CY | 2009–2024 | 16 | B |
| `redemptions` | `mixed`/`gilts_all` | HMT_DMR | table A.2 redemptions, FY→CY | 2009–2024 | 16 | B |
| `gross_issuance` | `fixed_bullet`/`gilts_conventional`, `inflation_linked`/`gilts_index_linked`, `mixed`/`gilts_unallocated` | HMT_DMR | table 3.A, FY→CY | 2025 only | 3 | C |
| `interest` | `mixed`/`gilts_all` | HMT_NLF | note 2 finance costs, FY→CY | 2009–2024 | 16 | B |
| `interest` | `bill`/`treasury_bills` | HMT_NLF | note 2, FY→CY | 2009–2021 | 13 | B |
| `interest` | `out_of_register`/`national_savings` | HMT_NLF | note 2, FY→CY | 2009–2024 | 16 | B |
| `interest` | `out_of_register`/`other_nlf_finance_costs` | HMT_NLF | note 2, FY→CY | 2011–2024 | 14 | B |
| `uplift_accrued` | `inflation_linked`/`gilts_index_linked` | ONS_PSF_TIMESERIES | PUSF `MW7L`, annual = calendar year | 1981–2025 | 45 | A |

Grades as used here (§9, DD8):

* **A** — calendar-year, published exactly, and the source's own label maps 1:1
  onto one DD2 class or one named bridge line.
* **B** — published exactly, but either the DD2 class split is missing (`mixed`
  gilts: ONS never splits conventional from index-linked) or the figure is a
  §7.10 conversion of a financial year, or the perimeter differs from the
  national-accounts one (DMR A.1).
* **C** — the period basis departs from the calendar year (pre-1997 end-March
  `BKPM`; the APF maturity-profile snapshot date), or a component of the value
  is the publisher's own forecast (DMR 3.A remit years), or the figure is
  structurally incomplete (APF cumulative operations, no redemption deduction).

---

## 2. Conversions

**FY → CY (§7.10, `intermediates.fy_to_cy`).** `CY_t = 0.25 × FY_{t−1/t} +
0.75 × FY_{t/t+1}`, financial year indexed by its starting calendar year.
Applied to DMR A.2, DMR 3.A and the NLF account. Every converted row's `notes`
name the two financial years and the two editions used, e.g.
*"FY→CY per §7.10 from DMR A.2 2026-27: 0.25×FY2023-24 + 0.75×FY2024-25
(editions 2026-27 and 2026-27)"*. The conversion consumes one year at each end,
which is why A.2's FY 2008-09 start becomes CY 2009 and its last outturn FY
2024-25 becomes CY 2024.

**Monthly → CY.** Appendix S table 1.2A has **no calendar-year block** (period
types are FY, Q, M only), so calendar years are the sum of the 12 monthly rows.
A year with fewer than 12 published months is omitted — 2026 has 7 in this
vintage and is not emitted. Signs are ONS's own: a CDID printed with a leading
minus (`-AACE`) is published already negated so the financing row sums to
`M98R`; nothing is re-signed here.

**December month-end, not the annual block.** PSA8A_1's own annual block is the
*financial* year (`Apr 1997 to Mar 1998`), so the calendar-year stock is taken
from the monthly block at month 12. Verified equal to the PUSF `BKPM` annual
(calendar-year) block over 1997–2025.

**Units.** All three DMR tables are £ billion and are multiplied by 1000. ONS
workbooks and time series are already £ million.

---

## 3. Known wedges (declared, never closed)

### 3.1 Uplifted vs unindexed nominal (index-linked gilts)

DMR table A.1 prints index-linked gilts at **unindexed** nominal with the
accrued inflation uplift on a line of its own, and its net line adds them back:

```
Index-linked gilts              393.5     <- unindexed nominal, gross
less government holdings          2.1
plus accrued inflation uplift   227.6     <- the wedge
(blank label)                   619.0     <- uplifted, net of holdings
```

All three are emitted (`gilts_index_linked_unindexed`,
`gilts_index_linked_accrued_uplift`, `gilts_index_linked`), so the wedge is
visible rather than buried. The table's own footnote (1) reads only *"Figures
may not sum due to rounding."*; the **chart** A.1 footnote in the same annex is
the one that states the basis: *"Figures may not sum due to rounding. Nominal
uplifted values."* Table A.1's footnote (4), on average time to maturity, says
the ATM is *"Calculated on a nominal weighted basis, excluding government
holdings, including accrued inflation uplift and Treasury bills for debt
management purposes"* — i.e. the DMR's working measure is the uplifted,
net-of-government-holdings one, which is what `gilts_index_linked` carries.

**A.1 against ONS `BKPM`.** The brief expected a material wedge here. There is
almost none once the table's own net lines are used:

| end-December | DMR conventional net | DMR index-linked net (uplifted) | sum | ONS `BKPM` | ratio |
|---|---|---|---|---|---|
| 2023 | 1,683,400 | 610,000 | 2,293,400 | 2,293,355 | 1.00002 |
| 2024 | 1,832,900 | 619,000 | 2,451,900 | 2,452,458 | 0.99977 |
| 2025 | 1,953,500 | 688,500 | 2,642,000 | 2,642,112 | 0.99996 |

The residual is the DMR's £0.1bn rounding. ONS `BKPM` is therefore the *same*
concept: gilts at uplifted nominal, net of government holdings. The test
asserts the ratio is in (0.90, 1.15) as briefed, and additionally that the
wedge is under 2% — which it is, by two orders of magnitude. **This makes the
DMR A.1 rows a genuine class split of the ONS gilt total, not an alternative
measure of it.** The pairing that would show a large wedge is the *gross*
index-linked line against `BKPM` (2024: 1,996.9 + 393.5 = 2,390.4 against
2,452.5, i.e. −2.5%, and +227.6 of uplift on top): both halves of that
comparison are emitted so the user can make it, but neither is the headline
row.

### 3.2 APF redemptions

The Bank publishes APF gilt **purchases** and **sales** per ISIN but not
redemptions. Cumulative purchases − sales is therefore *not* a holding, and no
redemption schedule is inferred (DD13): `apf_maturity_profile()` lists only
gilts still held, so it cannot recover what has already matured out of the
facility. Two separate rows are emitted instead:

* `mixed`/`boe_apf_net_operations`, grade C, at each 31 December 2009–2025.
  2021 peak £964,560 m; 2025 £864,365 m. Its `notes` say, in capitals, that
  redemptions are not deducted.
* `mixed`/`boe_apf_published_stock`, grade B, for the snapshot year only:
  £406,153 m, the sum of the maturity-profile table's per-gilt
  `Total Nominal (£bn)` column over its 40 gilts.

The gap between them at the near-adjacent dates is **£458,212 m** — that is the
nominal redeemed out of the APF since 2009, and it is exactly the quantity the
Bank does not publish. Anyone needing a year-by-year APF holding must get it
from the register step (per-ISIN maturities against per-ISIN APF positions),
not from this layer.

### 3.3 FY → CY

DMR A.2/3.A and the NLF account are financial-year. The §7.10 quarter/three-
quarter weighting is a *timing* approximation, not a measurement: it assumes
flows are uniform within the financial year. For gilt issuance in particular
that is a strong assumption (remits are front- and back-loaded), so all FY-
converted rows are grade B (grade C where a component financial year is still
the publisher's forecast). The unconverted alternative — the ONS Appendix S
monthly `ANTA` — is emitted alongside as `net_issuance`, and is the row to
prefer where a true calendar-year figure is wanted.

### 3.4 NLF gilts interest against ONS `NMFX`

The briefed check (NLF gilts CY 2024 within 15% of the `NMFX` calendar-year
value) **passes at 12.7%** (NLF gilts 71,501 against `NMFX` 81,920; ratio
0.873). No loosening was needed. The two are not the same concept and should
not be expected to converge:

* `NMFX` is *all* central-government interest payable, accrued, D.41 — every
  instrument, including the index-linked uplift accrual.
* The NLF note-2 `gilts` line is one instrument of the National Loans Fund's
  own finance costs, on the account's effective-interest basis.

Summing all four NLF items (gilts + Treasury bills + NS&I + other) tracks
`NMFX` much more closely — ratio 1.053 in 2024, 1.042 in 2023, 1.000 in 2021 —
which is the expected relationship and a better cross-check. The worst year in
the overlap is 2022 (gilts alone 0.852 of `NMFX`; all items 0.906), when the
uplift accrual inside `NMFX` was at its largest (`MW7L` 2022 = £59,124 m).
A 15% band on the *gilts-only* comparison would fail for 2022, so the test
pins 2024 as briefed and this report records the full ratio series rather than
widening the band silently.

---

## 4. Departures from the brief, and why

1. **"BKPM from the PUSF series, annual, from 1975" is not available.** In this
   vintage the `BKPM` JSON's `years` array is **blank before 1997** (`{'date':
   '1975', 'value': ''}`); the only pre-1997 observations are **end-March**,
   published in the `months` array as `1975 MAR` … `1996 MAR` and repeated in
   `quarters` as `1975 Q1` …. From 1997 the annual block is identical to the
   PSA8A_1 December month-end and adds nothing. So there is no pre-1997
   calendar-year gilt stock in this source. Rather than drop 22 years or label
   a March stock as a 31 December position (DD6), they are emitted under their
   own `sub_type` **`gilts_all_march`**, `basis='nominal_end_march'`, grade C,
   with `notes` saying in capitals that the observation is end-MARCH. They do
   not overlap the `gilts_all` years, and a consumer filtering on
   `sub_type == 'gilts_all'` never sees them.

2. **DMR 3.A yields one calendar year, not several.** Each edition carries two
   financial years — the estimate for the year ending and the remit for the
   year starting — so 2025-26 gives FY 2024-25/2025-26 and 2026-27 gives
   FY 2025-26/2026-27. Taking the latest edition per financial year leaves
   FY 2024-25 (outturn), FY 2025-26 (DMR estimate) and FY 2026-27 (plan), from
   which §7.10 can build CY 2025 and CY 2026. **CY 2026 is skipped**: both of
   its financial years are the publisher's own forecast, so it would be a
   projection for a year that has not happened. CY 2025 is emitted at grade C
   because its 0.75 weight sits on the FY 2025-26 remit estimate. The rule
   coded is "emit CY *t* only if FY *t−1* is an A.2 outturn row"; A.2 flags its
   forecast years with a footnote marker in the row label (`2025-26(3)`,
   footnoted *"Spring Statement 2025 projections"*).

3. **DMR A.2 forecast rows are dropped, not carried.** The table runs to
   2026-27 but the last two rows are projections. The aggregates table has no
   `is_forecast` column, so carrying them would silently mix outturn and
   forecast. Outturn financial years only → CY 2009–2024.

4. **`M98R` (the CGNCR total) from Appendix S is not emitted here.** It is not
   an instrument, and `intermediates.official_totals` already carries it as the
   financing step-A official total. Emitting it in a table of instrument
   components would invite double counting.

5. **PSA8A_1's `BKPW` total is likewise not emitted**, for the same reason; the
   seven instrument rows sum to it.

6. **Treasury-bill interest is emitted although the brief listed only gilts,
   NS&I and other.** `bill` is a DD1/DD2 register class and the NLF prints an
   explicit Treasury bills line from 2008-09 to 2021-22. It is *not* emitted
   for 2022-23 onward: those editions print no Treasury bills line at all, and
   treating an absent line as zero would be an inference, not a reading.

---

## 5. Reader behaviour that needed working around

1. **`dmr_tables()` column headings carry footnote markers.** A.2's gross-sales
   column is headed `Gross gilt sales(2)`, so an exact-match column lookup
   silently finds nothing (this cost one debugging cycle — the layer built
   redemptions but no gross issuance). Headings are matched on the *prefix* of
   their letters-and-digits key, and the module raises if either expected A.2
   column is missing rather than emitting a half table.

2. **A.1's net lines have empty row labels.** The conventional and index-linked
   blocks each end in a row whose label cell is blank and whose figure is the
   net. `_a1_blocks()` reads the block positionally from its heading and
   *validates the table's own arithmetic* (`gross − holdings + uplift = net`,
   tolerance £0.2bn) before emitting, raising if a future edition changes the
   shape.

3. **`nlf_interest_summary()` can return more than one row per `item`.** The
   note prints several lines that classify to the same bucket: 2012-13 and
   2013-14 carry "Loss on cancellation of Royal Mail gilts" under gilts
   (£3,082 m and nil), and 2012-13 splits "FLS Treasury Bills" from "SLS
   Treasury Bills". Taking the first row would drop £3,082 m of 2012-13 gilt
   finance costs and mis-state the note. The layer **sums** the rows of each
   item, which is what reconciles to the note's own printed total.

4. **NLF 2006-07 and 2007-08 have no usable PDF text layer**, so
   `nlf_interest_summary()` returns an empty frame for them (documented in
   `reports/debt_sources/ons_hmt.md`). §7.10 needs consecutive editions, so
   **CY 2006, 2007 and 2008 cannot be built** and are omitted. Every NLF row's
   `notes` says so. `interest` for `other` additionally starts at CY 2011,
   because the 2008-09 and 2009-10 accounts print "Other finance costs" as a
   heading with no sub-total, so the reader leaves those components
   unclassified (again, present but not summed by the reader — not imputed
   here either).

5. **`apf_maturity_profile()` drops the workbook's header total.** The brief
   asked for that total. Inspecting the sheet shows the dropped row
   ("Current stock of holdings", £489.026 bn) is a cumulation of the *Total
   Purchase Proceeds* column — i.e. holdings at initial purchase price, not at
   nominal — and the reader exposes neither the proceeds column nor the header
   row, so the total cannot be reconstructed from the reader's output.
   The layer therefore uses the **sum of the per-gilt `Total Nominal (£bn)`
   column, £406,153 m**, which is the nominal holding and is directly
   comparable with the operations row; the `notes` state all of this.
   *Suggestion for the boe reader*: keep `Total Purchase Proceeds` as a column
   and return the header total in `DataFrame.attrs`, so a caller can quote the
   Bank's own published figure without re-parsing the snapshot.

6. **The APF maturity-profile table carries no as-of date.** It is a *current*
   stock. The row is keyed to the year of the snapshot's `retrieved_at`
   (2026) with `notes` saying explicitly that it is not a 31 December position.
   The cumulative-operations series stops at 2025 because 2026 is a part year
   (operations run to 2026-08-17).

7. **`intermediates.fy_to_cy` handles the NLF gap correctly.** Because it
   requires *t−1* to be present, the 2006/2007 hole simply removes CY 2006–2008
   without any special-casing.

---

## 6. Vintage observations worth recording

* **DMR A.2 restates history between editions.** FY 2022-23 gross gilt sales
  are £169.5 bn in the 2025-26 edition and **£196.5 bn** in the 2026-27
  edition; FY 2011-12 moves £179.4 bn → £179.5 bn. The layer prefers the latest
  edition for each financial year, as briefed. The 2022-23 move is 16% and
  looks like a correction rather than a revision, but both editions are the
  publisher's and nothing here adjudicates between them.
* **A.1's `Public sector net debt` row is mangled in the 2026-27 edition**
  (`Public sector net debt Z 2,815.2`, the label having swallowed a figure).
  It is not a row this layer emits, so it does not matter here; it is recorded
  in `reports/debt_sources/ons_hmt.md`.
* **ONS `BKPJ` (Treasury bills, £91,127 m at end-2024) is wider than DMR A.1's
  `Treasury bills for debt management` (£70,500 m).** The difference is bills
  issued for cash management. Both are emitted, under different `sub_type`s
  (`treasury_bills`, `treasury_bills_debt_management`); they are not
  alternatives to be reconciled but two published perimeters.
* Likewise ONS `ACUA` NS&I (£237,191 m at end-2024) against DMR A.1's NS&I
  (£239,400 m): emitted as `national_savings` and `national_savings_dmr`.

---

## 7. Cross-country build

`aggregates.class_aggregates(run_id)` concatenates DEU + GBR + FRA and
validates. `tests/debt/test_aggregates_gbr.py::
test_combined_class_aggregates_still_validates` runs that build; if it ever
fails on a duplicate key, the test asserts the duplicates are **not** GBR's and
skips with the offending country named, so a defect in a sibling country module
cannot be mistaken for one here. (During this build the DEU module briefly
emitted duplicate keys — two distinct BMF *Verwendung* labels collapsing to the
same truncated `sub_type` — which was resolved in `aggregates.py` while this
layer was being written.)
