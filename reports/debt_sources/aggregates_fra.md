# FRA class-level aggregates (`ggfiscal.debt.aggregates_fra`)

DD8 layer for France: `class_aggregates(run_id)` in the
`ggfiscal.debt.aggregates.COLUMNS` shape, one row per
(`iso3='FRA'`, `year`, `instrument_class`, `sub_type`, `measure`), calendar
years, EUR millions, validated by `aggregates.SCHEMA`. Built 2026-09-09 on
the snapshot vintage `20260909T163716Z–20260909T163759Z`; 340 rows,
2000–2025. Tests: `tests/debt/test_aggregates_fra.py` (16, green).

Everything here is second-hand relative to the debt office. **AFT
(`www.aft.gouv.fr`), Banque de France web-stat and
`www.budget.gouv.fr` / `www.performance-publique.budget.gouv.fr` are
outside the allowlist** (§15 Q-D1), so the État's own négociable-debt
aggregates reach the package only through INSEE's redistribution of them
(BDM `serie/ajax`, source `INSEE_AFT_AGG`) and the ESA instrument split
only through Eurostat (`gov_10q_ggdebt`, source `EUROSTAT_GOV10DD`).

---

## 1. Two perimeter findings that changed the plan

### 1.1 S13111 is not published for France

The brief specified Eurostat sector **S13111** (budgetary central
government) as the register perimeter. It does not exist in the data.
`gov_10q_ggdebt` for `geo=FR` carries exactly

```
S13, S1311, S1312, S1313, S1314
```

and nothing else — the same five for `geo=DE`. The snapshot was pulled with
`sector` fully wildcarded (`Q.*.*.MIO_NAC.FR`), so this is Eurostat's
published content, not a pull restriction. S13111/S13112 are optional
sub-subsectors in the quarterly government debt dataflow and France does not
report them. They are absent from `gov_10dd_ggd` and from OECD `DF_T7PSD_Q`
(FRA sectors there: `S1`, `S13`, `S1311`) as well.

**Substitution made.** The tightest reachable Eurostat perimeter is
`S1311` — central government **including ODAC** (CADES, SNCF Réseau, …),
the §14 FRA trap. It carries the unsuffixed sub_types
(`f31_short_term_securities`, `f32_long_term_securities`, `f4_loans`,
`f2_currency_deposits`); every one of those rows says so in `notes`
("S13111 budgetary central government is not published for FR"). The
wider-perimeter cross-check rows that the brief wanted as `_s1311` are
therefore one step out, **`S13` general government**, carried with the
suffix `_s13` and `in_register=False`. The S13111-vs-S1311 gap the brief
asked for cannot be measured from any reachable source; §2.3 reports
INSEE/AFT-vs-S1311 and S1311-vs-S13 instead.

### 1.2 No S121 holder rows for issuer S1311

Condition for the `own_holdings` rows: `debt_by_instrument('FRA','S1311')`
must carry holder `sector2 = S121`. It does not. The holder codes present
for issuing sector S1311 are `S11`, `S11_S14_S15`, `S12`, `S1311`, `S1312`,
`S1313`, `S1314`, `S14_S15`, `S1_S2`, `S2` — financial corporations only at
the `S12` level, never the central bank alone. **No `own_holdings` rows are
emitted.**

Near miss worth recording: the *general government* pull
(`debt_by_instrument('FRA','S13')`, snapshot `9be83f81ecd4`) does carry
`sector2 = S121`, annually 2020–2025, but only for `na_item ∈ {GD, F4,
GD_F4}` and only at `maturity = TOTAL` — no `GD_F3` instrument split:

| year-end | S121 holdings of S13 Maastricht debt (EUR mn) | of which loans (GD_F4) |
|---|---:|---:|
| 2020 | 486,041 | 0 |
| 2021 | 623,029 | 0 |
| 2022 | 667,717 | 0 |
| 2023 | 660,930 | 0 |
| 2024 | 636,628 | 0 |
| 2025 | 571,574 | 0 |

Since `GD_F4 = 0` throughout, this is effectively Eurosystem holdings of
French general-government *securities*. It is one perimeter too wide for
`aggregates_fra` (S13, not S1311/État) and unsplit by instrument, so it is
reported here rather than emitted. It is available as a DD11 overlay if the
committee wants it under a clearly-named `_s13` sub_type.

---

## 2. What is emitted

### 2.1 `stock_year_end` — INSEE/AFT (source `INSEE_AFT_AGG`, grade B)

December observations, 2009–2025 (the BDM series begin 2009-01; the
harvested vintage ends 2026-07, so 2025 is the last December). Basis
`nominal`. Every row's `notes` carries the exact BDM/AFT title, and
`_aft_december()` **raises** if any of the eight titles differs from the
verified 2026-09-09 vintage — the idbank→instrument-class mapping is only as
good as the title, so a re-labelled or re-numbered series fails the build
rather than silently re-classifying debt.

| sub_type | class | in_register | idbank | sha256[:12] | AFT title (verbatim) |
|---|---|---|---|---|---|
| `dette_negociable_total` | mixed | True | 001711531 | 274ce06e24ba | Encours de la dette négociable totale de l'État en euros |
| `btf` | bill | True | 001711532 | ea450ea4d256 | Encours de la dette négociable de l'État à court terme (maturité d'un an et moins) en euros |
| `oat_btan_all` | mixed | True | 001711533 | ca12d06eb9ec | Encours de la dette négociable de l'État à moyen et long terme (maturité de plus d'un an) en euros |
| `taux_fixe` | mixed | True | 001738853 | 630b0414857b | Encours de la dette négociable de l'État à taux fixe |
| `oati_oatei` | inflation_linked | True | 001738854 | 435708582268 | Encours de la dette négociable de l'État indexée sur l'inflation |
| `oat_btan_fixed` | fixed_bullet | True | *derived* | 630b0414857b | 001738853 − 001711532 |

`taux_fixe` is `mixed`, not `fixed_bullet`, because **the AFT fixed-rate
aggregate includes BTF** — discount bills, not coupon-bearing bonds. Its
`notes` say so.

**Derivation `oat_btan_fixed` = taux fixe − BTF** (grade B, not an
AFT-published aggregate; `snapshot_sha256` is that of 001738853, the BTF
snapshot subtracted is 001711532). 2024: 2,312,580 − 201,163 =
**2,111,417**.

Three identities, all exact (0.0 EUR mn) at every December 2009–2025 —
verified in the tests, not merely asserted:

* `taux_fixe` + `oati_oatei` = `dette_negociable_total` — **the measured gap
  is 0.0 at every year**, far inside the 0.5% tolerance the brief allowed.
* `btf` + `oat_btan_all` = `dette_negociable_total`.
* `oat_btan_fixed` (= taux fixe − BTF) = `oat_btan_all` − `oati_oatei`.
  This holds only if every BTF is fixed-rate and every inflation-linked
  security is medium/long term, which is the case over 2009–2025 (no
  floating BTF, no BTANi outstanding after 2009 that is short-term). It is
  an independent route to the derived number and is asserted in the tests.

Inflation-linked share of État négociable debt: 12.9% (2009) → 11.2%
(2025).

**Foreign-currency series (001719708 total / 001719709 CT / 001719710 MLT):
identically 0.0 at every December 2009–2025.** The État issued no
foreign-currency négociable debt over the covered period. Per the brief,
`out_of_register` rows are emitted only where non-zero, so **no FX rows
exist**; a test asserts both the zeros and their absence from the output, so
a future non-zero observation will start producing rows.

### 2.2 `stock_year_end` — Eurostat `gov_10q_ggdebt` (source `EUROSTAT_GOV10DD`, grade B)

Q4 observations, 2000–2025, `unit = MIO_NAC`, snapshot
`gov_10q_ggdebt_FR` sha256 `cbb44bcd35ee`. Basis `nominal` (Maastricht
gross debt at face value). Note that Eurostat's F31/F32 is the ESA
**original-maturity** split (≤1y / >1y at issue), while the AFT CT/MLT split
is on the same original-maturity basis — the two are conceptually aligned,
which is why §2.3's F31/BTF ratio is so close to 1.

| sub_type | class | in_register | sector | na_item |
|---|---|---|---|---|
| `f31_short_term_securities` | bill | True | S1311 | F31 |
| `f32_long_term_securities` | mixed | True | S1311 | F32 |
| `f4_loans` | out_of_register | False | S1311 | F4 |
| `f2_currency_deposits` | out_of_register | False | S1311 | F2 |
| `f31_short_term_securities_s13` | bill | False | S13 | F31 |
| `f32_long_term_securities_s13` | mixed | False | S13 | F32 |

F32 is `mixed`: it lumps fixed-rate, inflation-linked and floating bonds
together, so it can never be a DD2 class on its own. S1311 `F2` (currency
and deposits, 128,671 EUR mn at end-2025) is the dépôts des correspondants
family and S1311 `F4` (78,473) the loans — both DD1 bridge items, hence
`out_of_register`.

### 2.3 Measured perimeter gaps

INSEE/AFT (État négociable) < Eurostat S1311 (CG incl. ODAC) < Eurostat S13
(general government) at every common year-end, on the securities lines:

| year | INSEE/AFT total | S1311 F31+F32 | S1311 − INSEE | % | F31 / BTF | S13 F31+F32 | S13 − S1311 | % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2000 | | 661,857 | | | | 687,575 | 25,719 | 3.89 |
| 2001 | | 705,059 | | | | 728,699 | 23,640 | 3.35 |
| 2002 | | 767,605 | | | | 793,443 | 25,838 | 3.37 |
| 2003 | | 847,754 | | | | 878,533 | 30,778 | 3.63 |
| 2004 | | 892,126 | | | | 949,313 | 57,186 | 6.41 |
| 2005 | | 934,497 | | | | 1,010,787 | 76,290 | 8.16 |
| 2006 | | 927,348 | | | | 1,006,569 | 79,222 | 8.54 |
| 2007 | | 973,460 | | | | 1,049,592 | 76,131 | 7.82 |
| 2008 | | 1,078,138 | | | | 1,164,698 | 86,560 | 8.03 |
| 2009 | 1,147,985 | 1,279,592 | 131,607 | 11.46 | 1.0411 | 1,385,284 | 105,692 | 8.26 |
| 2010 | 1,228,971 | 1,344,960 | 115,989 | 9.44 | 1.0222 | 1,461,499 | 116,539 | 8.66 |
| 2011 | 1,312,980 | 1,409,451 | 96,471 | 7.35 | 1.0086 | 1,570,402 | 160,951 | 11.42 |
| 2012 | 1,386,154 | 1,455,595 | 69,441 | 5.01 | 1.0087 | 1,617,438 | 161,844 | 11.12 |
| 2013 | 1,457,220 | 1,527,516 | 70,296 | 4.82 | 1.0067 | 1,692,246 | 164,730 | 10.78 |
| 2014 | 1,527,562 | 1,576,482 | 48,920 | 3.20 | 1.0123 | 1,747,612 | 171,130 | 10.86 |
| 2015 | 1,576,372 | 1,626,490 | 50,118 | 3.18 | 1.0085 | 1,806,470 | 179,980 | 11.07 |
| 2016 | 1,620,597 | 1,673,597 | 53,000 | 3.27 | 1.0115 | 1,866,737 | 193,140 | 11.54 |
| 2017 | 1,686,112 | 1,741,767 | 55,655 | 3.30 | 1.0145 | 1,938,071 | 196,304 | 11.27 |
| 2018 | 1,756,400 | 1,812,102 | 55,702 | 3.17 | 1.0276 | 1,991,717 | 179,615 | 9.91 |
| 2019 | 1,822,805 | 1,879,288 | 56,483 | 3.10 | 1.0481 | 2,052,146 | 172,858 | 9.20 |
| 2020 | 2,001,014 | 2,053,043 | 52,029 | 2.60 | 1.0210 | 2,321,848 | 268,805 | 13.09 |
| 2021 | 2,145,121 | 2,196,381 | 51,260 | 2.39 | 1.0341 | 2,480,556 | 284,175 | 12.94 |
| 2022 | 2,277,811 | 2,326,702 | 48,892 | 2.15 | 1.0003 | 2,608,842 | 282,140 | 12.13 |
| 2023 | 2,429,973 | 2,478,252 | 48,279 | 1.99 | 1.0000 | 2,760,269 | 282,017 | 11.38 |
| 2024 | 2,601,637 | 2,645,782 | 44,145 | 1.70 | 1.0020 | 2,952,882 | 307,100 | 11.61 |
| 2025 | 2,737,125 | 2,779,836 | 42,711 | 1.56 | 1.0021 | 3,096,188 | 316,352 | 11.38 |

Readings:

* **S1311 − INSEE/AFT** narrows monotonically from 131.6 bn (11.5%) in 2009
  to 42.7 bn (1.6%) in 2025, and is ≤ 3.3% from 2014. The residue is ODAC
  securities — chiefly CADES, whose stock has been amortising away over
  exactly this period — plus the small non-négociable securities content of
  the Maastricht measure. This is the §14 FRA step-B item, and it is now
  quantified per year.
* **F31 / BTF** is between 1.0000 and 1.0481 over 2009–2025; **1.0020 at
  2024-Q4**, i.e. the État's BTF are essentially the whole of
  central-government short-term securities. Comfortably inside the brief's
  10% tolerance (asserted in the tests).
* **S13 − S1311** is 3–4% before 2004, then steps up to 8–13% — the rise of
  local-government and social-security securities issuance (S1313/S1314) and
  of the CADES/Unédic complex. It is the step-C perimeter item.

### 2.4 `net_issuance` (grade B, basis `nominal_change`)

Year-on-year change of the year-end stock. Notes on every row: *"Δ year-end
stock; buy-backs, indexation of principal and FX effects not separated"*.

| sub_type | class | source | years |
|---|---|---|---|
| `f31_short_term_securities` | bill | Eurostat S1311 F31 Q4 | 2001–2025 |
| `f32_long_term_securities` | mixed | Eurostat S1311 F32 Q4 | 2001–2025 |
| `btf` | bill | INSEE/AFT 001711532 December | 2010–2025 |
| `oat_btan_all` | mixed | INSEE/AFT 001711533 December | 2010–2025 |

A useful confirmation found while building: AFT also publishes *"Variations
depuis le début de l'année"* series for the same aggregates (001738855
total, 001738856 CT, 001738857 MLT). Their December observation equals the
change in the December stock to **0.0 EUR mn at every year 2010–2025**, so
the INSEE/AFT `net_issuance` rows are the office's own published annual net
figure arrived at by a second route, not merely a difference this package
took. A test asserts the equality; the rows' notes name the variation
idbank. (2024: total +171,664; CT +31,946; MLT +139,718.)

**Gross issuance and redemptions are not emitted.** No reachable source
carries them: the AFT tableau de financement and the *Bulletin mensuel* are
on the blocked host, the INSEE redistribution stops at stocks and YTD
variations, and Eurostat's EDP tables give transactions in Maastricht debt
(`F_GD`) net, not gross. This is the §6.3 step-A "AFT tableau de
financement" cell, still empty for France.

---

## 3. What is *not* emitted, and why

| measure | status | reason |
|---|---|---|
| `interest` | **none** | Programme 117 (charge de la dette, §6.3 step A) is on `www.budget.gouv.fr` / `www.performance-publique.budget.gouv.fr`, both blocked. Eurostat `gov_10a_main` D41PAY S1311 exists (46,851 EUR mn in 2024) but is a single whole-subsector number with no instrument split — it is the step-B intermediate, handled by the reconciliation layer, and has no place in a *class-level* table. Nothing reachable splits French interest by instrument class. |
| `uplift_accrued` | **none — confirmed absent** | Searched: AFT coefficients d'indexation (blocked host); programme 117's "charge d'indexation" line (blocked host); INSEE_AFT_AGG (16 idbanks: 6 stock, 2 rate-type stock, 8 YTD variations — no indexation charge, no uplifted-vs-unindexed nominal pair); Eurostat `gov_10dd_edpt2/3` (`ORD41A_ADJ` is the accrued-minus-paid interest adjustment for *all* interest, not indexation uplift, and is not a class-level item). **No reachable official French uplift series exists.** The `oati_oatei` stock rows are the AFT aggregate, which is already the *uplifted* nominal, so the uplift is embedded in them and cannot be separated at this level. |
| `own_holdings` | **none** | §1.2 above: `gov_10dd_ggd` has no `S121` holder rows for issuer S1311. |
| `stock_gross_umlauf` | none | France has no Eigenbestand analogue in the reachable aggregates; the AFT encours is nominal in issue. |
| `gross_issuance`, `redemptions` | none | §2.4 above. |
| FX `out_of_register` rows | none | §2.1: series are identically zero. |

---

## 4. What remains impossible without AFT

1. **Gross issuance and redemptions by instrument** — the whole of §6.3's
   FRA step-A financing cell (tableau de financement, PLF article
   d'équilibre). Only the net change is reachable.
2. **Interest by instrument class** and the cash/accrued split — programme
   117 RAP.
3. **Indexation uplift accrued per year** and the uplifted/unindexed nominal
   pair (DD7, DD9) — coefficients d'indexation.
4. **Buy-backs** (§14 FRA: "no standalone file; derive from monthly recaps
   or position differences") — the monthly recaps are on the blocked host,
   so buy-backs stay inside the Δstock net figure, which is exactly what the
   `net_issuance` note declares.
5. **The OAT/BTAN split** — INSEE/AFT gives only MLT as one aggregate.
   BTAN were discontinued in 2013 (§14 FRA) and the residual lines ran off
   over the following years, so recent `oat_btan_all` / `oat_btan_fixed` are
   effectively pure OAT; for the early years they are genuinely mixed and
   the sub_type name says so. Only the register (OQ-8) can separate them.
6. **Floating-rate stock** (OAT TEC10) — no reachable aggregate isolates it.
   The AFT rate-type split is exhaustively two-way, taux fixe + indexée =
   total to 0.0 at every year (§2.1), so whatever floating stock exists is
   folded into one of those two and cannot be lifted out at class level.
   This is why the derived `oat_btan_fixed` is `fixed_bullet` only on the
   AFT taxonomy's own terms; the DD2 `floating` class has no French
   class-level source.
7. **A true budgetary-central-government (S13111) ESA perimeter** — §1.1;
   not published for France by Eurostat or OECD.

Items 1–4 all resolve the moment `www.aft.gouv.fr` and
`www.performance-publique.budget.gouv.fr` are allowlisted (§15 Q-D1), or a
file arrives via `ggfiscal ingest-file`.

---

## 5. Function surface and tests

`ggfiscal.debt.aggregates_fra.class_aggregates(run_id) -> DataFrame`
(`aggregates.COLUMNS`), picked up automatically by
`ggfiscal.debt.aggregates.class_aggregates`. Module constants
`AFT_STOCK`, `AFT_FX`, `AFT_YTD_VARIATION`, `EUROSTAT_ITEMS`,
`EUROSTAT_S13_ITEMS` are the mapping tables.

`tests/debt/test_aggregates_fra.py` — 16 tests, skipped when the snapshot
store is empty: schema and key uniqueness; the combined multi-country
`class_aggregates` still validating; AFT title verification; 2024 total in
2.3–2.9 mn range and equal to 2,601,637; the three exact identities of
§2.1; the FX zeros; S13111 absence and the substitution note; F31/BTF ratio
at 2024; the perimeter ordering INSEE < S1311 < S13 with the 2024 percentage
pinned; `net_issuance` recomputed from the stock rows and matched against
AFT's published YTD variation; no `interest` / `uplift_accrued` /
`own_holdings` rows; and the S121-holder condition (absent for S1311,
present for S13).
