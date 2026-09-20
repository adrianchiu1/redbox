# Replication for the United States and Japan
## Specification v2.4 addendum and gated build plan — extension to `COFOG_KICKOFF.md` and `DEBT_KICKOFF.md`

Prepared 20 September 2026 from `REPLICATION_SCOPING.md` after the committee
took its ten questions (Q-R1–Q-R10) on the stated defaults (D-S14-001).
Self-contained for the two new countries; where it is silent, `COFOG_KICKOFF.md`
v2.2 with the v2.3 addendum governs for the fiscal package and
`DEBT_KICKOFF.md` v1.0 for the debt extension. Where this document conflicts
with either on USA or JPN matters, this one governs. Nothing here changes a
number for GBR, FRA or DEU: Stage R0's acceptance test is that it does not.

---

## 0. How to read this document

| Section | Purpose |
|---|---|
| §1–§2 | Mission, build order, and the decisions taken. Build to them. |
| §3–§5 | Targets, line universe per country, data-model additions. |
| §6–§8 | Source hierarchy, stitching and reconciliation amendments. |
| §9–§10 | Grading placements and the new validation tests. |
| §11 | Architecture: the config keys and the anchor-family interface. |
| §12 | Build stages with hard gates: R0, U0–U6, J0–J6, UD0–UD5, JD0–JD5. |
| §13 | Seed source register (verified live 2026-09-20; Stage U0/J0 re-verifies). |
| §14 | Country traps. |
| §15 | Committee questions reserved. |
| §16 | Model allocation and conventions. |

Vocabulary as before: "committee" = AC; "agent" = the builder. "Parent" =
`COFOG_KICKOFF.md`. "Anchor family" = the set of readers that serve one
institution's tables behind the interface in §11.3.

---

## 1. Mission and scope

Produce for the United States (`USA`, USD) and Japan (`JPN`, JPY) everything
the package produces for GBR, FRA and DEU: the three trees (17 COFOG lines,
9 ESA-economic-type lines, 15 ESA-revenue lines — 41 line series per
country, 205 in the universe), the balance ledger, both variants, backward
and forward extension under parent §6–§7, the IMF WEO reconciliation (§8),
the flat files, catalogue, notebooks and chart site; then the debt
extension: the central-government marketable-securities register, the
interest and financing chains, and the maturity profile.

**Build order (Q-R10).** Stage R0 (the one-off generalisation of the
package) first, against the existing three countries. Then the USA fiscal
package (U0–U6). A go/no-go at Gate U6 opens the JPN fiscal package
(J0–J6). The debt extensions follow each fiscal package (UD, JD). Both
countries are specified here so that R0 is designed once.

Governing principles carry over unchanged: **maximise length subject to
transparency and conceptual integrity**; **decompose, never force**. Two
corollaries matter more for these countries than for the European three:
a line that ends at 2027 because nobody official projects it is the
correct result, and a structural zero is a fact to publish, not a gap to
fill.

---

## 2. Decisions taken (D18 onward; parent decisions D1–D17 stand unless amended here)

**D18 — Anchor for a country without an ESA table (amends D1; Q-R1).** The
anchor is the national statistical office's own data as it re-presents them
on the SNA 2008 framework for the OECD: OECD Tables 11 (expenditure by
function), 12 (government non-financial accounts, the three flows
`DF_TABLE12_EXP/REV/BAL`) and 10 (taxes and social contributions detail),
sector S13, national currency. These are BEA's and ESRI's numbers (verified
cell-for-cell in `REPLICATION_SCOPING.md` §3–§4), so D1's principle — the
institution is the NSO, IMF GFS is a reconciliation test — holds. The
national publication (BEA NIPA; ESRI annual national accounts) is a
same-institution **secondary** source under parent §6.1(2): it fills years
and lines the OECD tables lack (NIPA 1929–1969 and 2025; ESRI 1994–2004 on
CY; the D.51 payer split for Japan) and never replaces an OECD anchor value
in a year the anchor covers.

| Country | Expenditure (COFOG) | Expenditure (ESA_EXP) | Revenue | Balance | Tax detail | GDP | Secondary national |
|---|---|---|---|---|---|---|---|
| USA | `OECD_T11` | `OECD_T12_EXP` | `OECD_T12_REV` | `OECD_T12_BAL` | `OECD_T10` | `OECD_T1` (B1GQ, same vintage) | `BEA_NIPA` |
| JPN | `OECD_T11` (FY, D19) | `OECD_T12_EXP` (CY, 2005–); `ESRI_SNA_I4`/`C3` (CY, 1994–2004, all lines but D.1/P.2) | `OECD_T12_REV` (CY, 2005–); `ESRI_SNA_I4` (CY, 1994–2004) | `OECD_T12_BAL`; `ESRI_SNA_C3` | `OECD_T10` (FY); `ESRI_SNA_S6_2` (FY, D.51 split) | `OECD_T1` | `ESRI_SNA_*` |

**D19 — Period basis where the anchor exists only on fiscal-year basis
(amends D3; Q-R2).** The canonical basis remains calendar year. Where a
tree's anchor is published only on a fiscal-year basis — Japan's COFOG tree
(ESRI Table 7, OECD Table 11, IMF GFS, all April–March labelled by the
starting year) — the tree is published **FY-labelled**, every row carrying
`source_period_basis = FY` and `native_period = "FY2023"`-style labels, and
the package publishes a **FY/CY bridge on total expenditure** (`TE_FY(t)`,
`TE_CY(t)`, the gap, and the quarterly-derived timing component from ESRI's
quarterly GG accounts) as a deliverable. No anchor is converted. The FY
tree enters the §8.3 decomposition through the bridge, never directly;
the ledger and the two CY trees are the CY canon. For Japan's revenue and
ESA_EXP trees the CY tables exist and are used. Parent §7.10 (forecast
conversion) is generalised: conversion weights are per country
(`fy_to_cy_weights`), 0.25/0.75 for April–March sources (GBR, JPN) and
0.75/0.25 for October–September sources (US federal), recorded per row as
today.

**D20 — Structural zeros (Q-R3).** A line the anchor institution defines
as identically zero for a country — USA `R01` (no VAT: D.211 = 0 in OECD
T12), `E04` (Medicare and Medicaid are D.62 cash benefits in the SNA
presentation; D.632 = 0), `GF05` (BEA has no environmental-protection
function; its components sit in 04 and 06) — is declared in
`countries.yaml.lines_absent` with its reason and published as zero rows
typed `structural_zero` (a new `observation_type`), grade A, in every
anchor year and in no forecast or stitched year. Identities (V2, V22,
V26), the decomposition and the balance run over them unchanged. The
catalogue and coverage matrix record the reason. A structural zero is
never interpolated, extended or forecast.

**D21 — Interest concept for Japan (Q-R4).** `GF01_7`, `E05` and `R07`
carry the FISIM-adjusted D.41 (ESRI Table 4, OECD T12, AMECO), which is the
ESA 2010 concept, `concept_flag = d41_gross_accrued`. The FISIM-unadjusted
figure (IMF GFS G24, ESRI's GFS table) is carried in `imf_value` and the
wedge (≈ 17% in FY2023) is reported by V43; V1's 0.5% tolerance is
suspended for the Japanese interest lines with the wedge as the recorded
reason. The Level II cell `GF0107` in OECD T11 carries D4 by function on
the FISIM-adjusted basis and is the COFOG-tree value.

**D22 — Sub-perimeter national forecasts are maximum-only proxies
(Q-R5).** Federal-only (CBO baseline, OMB Budget, CMS trustees) and
central-only or CG+LG (MOF budget, MOF later-years estimate, Cabinet
Office medium-to-long-term projection) sources enter under parent
§6.2(4) as dominant-component proxies: `maximum_extension` only, grade C
(B where `coverage_share ≥ 0.90` is measured on the anchor line, which
Medicare-plus-Medicaid on GF07 and OASDI on GF10_2 may reach), with
`coverage_share`, `coverage_share_year`, the perimeter note and
`residual_method` recorded. They never enter strict. Strict for both
countries runs on the international official sources with direct
general-government lines (AMECO, OECD Economic Outlook) to their two-year
horizon, and on statutory actuarial projections where the line is a
general-government line (Japan's pension valuation for `GF10_2`, grade B,
per D-S13-002's treatment of the Ageing Report).

**D23 — Machine-extracted PDF tables (amends parent §11.4; Q-R6).** A
table extracted programmatically from an official PDF (Cabinet Office
projection tables; MHLW 2018 outlook; MOF later-years estimate) is
admitted without a second human keying when (a) the extraction script is
committed and re-runnable on the D8 snapshot, (b) every row and column
total printed in the document reproduces from the extracted cells to the
last digit, and (c) the `.meta.yaml` sidecar records the extraction
method as `checked_by = extraction_totals`. A table without printed
totals stays under the original §11.4 rule.

**D24 — Blocked hosts (Q-R7).** `www.cbo.gov` (DataDome) and `www.ssa.gov`
(Akamai) are recorded as blocked in the register, as `obr.uk` is. The US
build proceeds on CBO's own GitHub mirror of its baselines
(`raw.githubusercontent.com`, open) and on the Medicare trustees' CSVs
(`www.cms.gov`, open). The CBO 10-year workbooks, the NIPA-basis federal
tables and the 30-year Long-Term Budget Outlook, and the OASDI trustees'
tables, are registered with `status: blocked` and the hand-retrieval route
of D-S7-001 named as the unblock; they are the trigger for revisiting the
US `GF10_2`, `GF07` and `R06` long legs (OQ-13).

**D25 — Japanese per-security positions are reconstructed (Q-R8).** MOF
publishes one live snapshot of outstanding by issue. Year-end positions
per security are rolled from the auction, liquidity-enhancement, buy-back
and redemption flows (parent debt §7.1), typed `rolled_from_flows`, grade
B, and validated at every 31 March and 31 December against (i) the BoJ's
per-issue holdings (a lower bound), (ii) the annual report's outstanding
by bond type, and (iii) the one live snapshot. National Diet Library
web-archive captures of the MOF file are registered as `office_snapshot`
cross-checks where they exist, never as the primary path. The US register
takes MSPD per-CUSIP positions as `office_snapshot` from January 2001 and
rolls 1980–2000 from auctions and maturities the same way.

**D26 — US COFOG Level II from BEA sub-functions (Q-R9).** With no US
source publishing COFOG groups, the four Level II lines are built from
NIPA Table 3.16 sub-function lines (with Table 3.17's gross investment by
function where the group has capital spending), `observation_type =
level2_proxy_actual`, grade B, each with its concept note: `GF01_7` =
interest payments (equals GG D.41 by construction, so it is also the D10
fallback); `GF10_2` = retirement (OASI including survivors' benefits, i.e.
wider than 10.2 by 10.3's survivors); `GF10_5` = unemployment (benefits
plus administration); `GF04_5` = transportation (current plus gross
investment). Remainders derive as everywhere (V19). The IMF GFS `GF0170_T`
series (1980–1989 only) is the one external cross-check and is reported,
not used.

**D27 — Anchor routing is configuration (serves R0).** Every place that
today decides by `iso3 == "GBR"` which reader serves a line is replaced by
an anchor-family object built from `countries.yaml` (§11.3). The country
list, currency schema, structural zeros, period-basis weights, WEO
perimeter flag and perimeter break are read from config. R0's acceptance
is byte identity of `data/canonical/` and `deliverables/` for the three
existing countries (run_id excepted) and a green test suite.

---

## 3. Statistical targets

Unchanged from parent §3: S13 consolidated; ESA/SNA total expenditure and
total revenue; `NLB = TR − TE`; annual, current-price national currency,
millions. Concept notes that apply to whole countries:

- **USA.** The OECD presentation grosses up sales of goods and services
  (P.11 + P.12 + P.131 as revenue) that NIPA nets against consumption
  expenditure: TR and TE are each ≈ USD 1.17 trn (2024) above the NIPA
  totals; NLB is unaffected. Consumption of fixed capital is excluded from
  TE as in ESA. Government enterprises (Postal Service, TVA, utilities)
  are outside general government; their current surplus (negative in
  2024) sits in R10 and their gross investment is inside NIPA's
  government investment but not the OECD P.51G — a documented E08 wedge.
  Territories are outside NIPA's coverage. Only refundable tax credits
  are expenditure (partial net treatment vs D17; note on R03/E03).
- **JPN.** ESRI's functional table includes CFC in "final consumption"
  and allocates no interest to 01.7; OECD T11 already rebuilds the
  ESA-style total by function (CFC out, D.4 in). FILP agencies are public
  financial corporations, outside S13; FILP bonds are central-government
  liabilities. The local consumption tax is recorded at central
  government and transferred. Long-term-care benefits in kind sit in
  COFOG 10.2 rather than 07 in ESRI's allocation (to be measured at U/J1
  and noted on `GF07`/`GF10_2`).

---

## 4. Line universe per country

The 41 lines of `config/lines.yaml` apply to both countries. The anchor
cell per line comes from the family's tables via new keys in `lines.yaml`
(`oecd_t11`, `oecd_t12`, `oecd_t10`, and per-country secondary keys
`bea_nipa`, `esri`), added beside the existing `eurostat_*`/`ons_*` keys
so that the three existing families are untouched.

### 4.1 COFOG tree

| Line | USA cell | JPN cell | Note |
|---|---|---|---|
| GF01–GF10, TE | `OECD_T11` `GFxx` × `OTE`, `_T` | `OECD_T11` `GFxx` × `OTE`, `_T` (FY, D19) | USA `GF05` structural zero (D20) |
| GF01_7 | `BEA_NIPA` T3.16 interest payments (D26); cross-check `OECD_T11` `D4 × GF01` | `OECD_T11` `GF0107` × `OTE` (FY) | JPN also `D4 × GF0107` for the D21 concept |
| GF10_2, GF10_5, GF04_5 | `BEA_NIPA` T3.16 (+ T3.17 investment) sub-functions (D26) | `OECD_T11` `GF1002`, `GF1005`, `GF0405` × `OTE` | |
| GF01_X, GF04_X, GF10_X | derived | derived | never forecast |

### 4.2 ESA_EXP tree (`oecd_t12` cells, `DF_TABLE12_EXP`, S13, payable)

| Line | Cell | USA note | JPN note |
|---|---|---|---|
| E01 | D1 | | 2005– from T12; 1994–2004 FY-only in ESRI (Table 6(2)) → `maximum_extension` leg only |
| E02 | P2 | | as E01 |
| E03 | D62 | includes Medicare/Medicaid | |
| E04 | D632 | **structural zero** | purchased social transfers in kind |
| E05 | D41 | OECD vintage (1,384.6 bn 2024) vs NIPA/IMA 1,397.6 bn incl. imputed pension interest — note | FISIM-adjusted (D21) |
| E06 | D3 | | |
| E07 | D29 + D5 + (D4 − D41) + D7 + D8 | D29, D5, D8 = 0 in T12 | |
| E08 | P5 + NP | enterprise investment wedge (§3) | |
| E09 | D9 | | |
| TE_ESA | OTE | = COFOG TE | = COFOG TE only after the D19 bridge (FY vs CY) |

### 4.3 ESA_REV tree (`oecd_t12` cells from `DF_TABLE12_REV`; `oecd_t10` from `DF_TABLE10`)

| Line | Cell | USA note | JPN note |
|---|---|---|---|
| R01 | T12 D211 | **structural zero** | consumption tax incl. the local share |
| R02 | T12 D2 − D211 | general sales taxes (D.214) live here | |
| R02_A | T10 D214A (+ D2122C where present) | federal and state excises | |
| R03 | T10 D51A | personal current taxes; cash/withholding basis | T10/T12 carry no payer split: CY D5 × FY payer share from `ESRI_SNA_S6_2` (items 1111/1112), `derived_actual`, grade B |
| R04 | T10 D51B | corporate incl. rest-of-world (38.9 bn 2024) | as R03 (1112 share) |
| R05 | T12 D5 − R03 − R04 + D59 + D91 | | |
| R06 | T12 D61 | = NIPA contributions for government social insurance exactly | |
| R06_E, R06_H | T12 D611, D613 | | |
| R07 | T12 D41 (resources) | | FISIM-adjusted (D21) |
| R08 | T12 D4 − D41 | Federal Reserve remittances (D.42) swing it; negative 2023–24 allowed | |
| R09 | T12 P1M + P1O + P131 | the sales grossing (§3) | |
| R10 | residual | enterprise surplus (negative) | |
| TR | T12 OTR | | |

### 4.4 Balance ledger

`TR`, `TE`, `NLB` from `DF_TABLE12_BAL` B9 and the T12 totals (V23 as
before). For Japan, `TE` in the ledger is the CY `OTE`; the COFOG tree's FY
`TE` is reconciled to it by the D19 bridge, and V2 runs on the FY tree
against the FY total.

---

## 5. Data-model additions (parent §5)

| Field / value | Addition |
|---|---|
| `observation_type` | new value `structural_zero` (D20) |
| `source_period_basis` | stamped from the source register, no longer the `"CY"` literal; `FY` on every row of a FY-labelled tree (D19) |
| `native_period` | `FY2023` for Japanese FY rows; the fiscal-year label convention (`fy_label = start_year`, `fy_start_month = 4`) is in `countries.yaml` |
| `concept_flag` | new values `d41_fisim_adjusted`, `sales_grossed`, `level2_bea_function` |
| `currency` | schema check reads the set of currencies from `countries.yaml` (USD, JPY admitted) |
| `iso3` | schema check reads `config.COUNTRIES` |

New deliverable: `fy_cy_bridge.csv` — per (country, year): `TE_FY`,
`TE_CY`, `gap`, `timing_component` (from quarterly ESRI GG accounts),
`residual`, keyed by run and source vintage (D19). Empty for countries
without a FY tree.

---

## 6. Source hierarchy amendments (parent §6)

**6.1 Historical.** Rank 1 is the OECD anchor (D18). Rank 2 (same national
data redistributed) gains the national publication itself (BEA NIPA, ESRI
tables) for years the OECD tables lack. IMF GFS stays reconciliation
only; for Japan it is the FISIM-unadjusted cross-check (D21).

**6.2 Forecast.** The ranks are unchanged. Two facts change their
application: (a) no national institution forecasts general government in
either country, so rank 1 and 2 sources are international — AMECO
(ESA-named GG lines, values equal to OECD T12) and the OECD Economic
Outlook (SNA-like GG lines incl. gross interest paid, direct taxes by
payer, contributions, benefits, investment) to 2027 — and statutory
actuarial bodies where the line is general government (MHLW pension
valuation for `GF10_2`; CMS Medicare trustees for the Medicare component
of `GF07`); (b) every national fiscal projection is rank 4 by perimeter
(D22). "Official" gains: CBO, OMB, CMS and SSA actuaries (USA); Cabinet
Office, MOF, MHLW, the Council on Fiscal System (JPN); the OECD Economic
Outlook as a forecasting institution on a par with AMECO.

**6.3 Envelopes.** AMECO TR/TE (both) and OECD EO YPGT/YPG (both, with the
concept note that EO totals differ from T12 OTR/OTE) to 2027. No
independent national total exists beyond that: §8.3 collapses the two
residuals into `resid_total` per side, as the parent already provides.
For Japan the Cabinet Office CG+LG balance is registered as a
`sub_perimeter_envelope` for a memorandum comparison only.

**6.4 Latest-vintage rule.** Unchanged. Editions to track: AMECO Spring
and Autumn; OECD EO June and December; WEO April and October; Cabinet
Office January and July; MHLW valuation every five years (2024, next
2029); CBO February baseline (mirror) and OMB spring budget; BEA annual
NIPA update (late September) and ESRI annual estimates (December; 2020
benchmark since 2025-12).

---

## 7. Stitching amendments (parent §7)

- **7.10 generalised.** `CY_t = w_1 × FY_{t−1/t} + w_2 × FY_{t/t+1}` with
  `(w_1, w_2)` from `countries.yaml.fy_to_cy_weights`; the parent's
  0.25/0.75 is the April–March case. US federal sources (CBO, OMB, MTS)
  are October–September: 0.75/0.25. Where quarterly NIPA (Table 3.2)
  allows an exact FY sum, U3 uses it to compute like-for-like growth and
  records `period_conversion_method = fy_sum_quarterly`.
- **7.14 Basis discipline in stitching (new, D19).** Growth is computed
  on the anchor's basis. A FY source is chained onto a CY anchor only
  after §7.10 conversion with the country's weights (Japan's OECD RS
  1965–1993 onto the CY revenue tree; `period_conversion_method`
  recorded, one boundary year consumed), and a CY source onto a FY anchor
  likewise in reverse (`CY → FY` with the same weights transposed). On the
  FY COFOG tree the backward legs are FY-native (ESRI archive vintages,
  IMF GFS) and need no conversion. Where the only forecast of a FY line is
  a CY source with a two-year horizon (AMECO), conversion would consume
  the horizon: the line ends at the last actual in the FY tree and the
  forecast appears on the CY trees only. The MHLW valuation is FY-native
  and chains onto `GF10_2` directly.
- **7.15 Payer shares for Japan's D.51 split (new).** `R03_t = D5_CY,t ×
  s_t`, `s_t` = 1111 / (1111 + 1112) from ESRI Table 6(2) for the fiscal
  year starting in `t`; `R04` likewise; `R05` takes the residual. Grade B,
  `derived_actual`, `concept_note` naming the share source; V22 holds by
  construction.
- **7.16 Backward legs on the national publication.** USA 1929–1969: NIPA
  Table 3.1/3.2/3.3 growth for E01, E03, E05, E06, E08, E09, R02–R04, R06,
  R07, R08 (grade B: presentation differences do not touch these items;
  TE/TR/E02/R09 are affected by the sales grossing and stop at 1970 unless
  the committee accepts a C leg); COFOG 1959–1969 via NIPA 3.16 functions
  (grade C: current-expenditure basis). JPN 1980–1993 (2000-base 93SNA
  vintage, FY): COFOG Level I (C), GG account items (C); 1994–2004 CY for
  the two CY trees from ESRI Tables 4 and 3 (A; D.1/P.2 excepted).
  Nothing before 1980 for Japan; the 68SNA vintage is D and declined.

---

## 8. Reconciliation amendments (parent §8)

- **8.2** The gap classification reads
  `countries.yaml.weo_perimeter_gap_expected` (D27): `true` for USA (WEO's
  GFSM-basis US series carry documented adjustments, e.g. the 2017
  repatriation tax removed from revenue) applies the GBR stability rule;
  `false` for JPN applies the FRA/DEU level rule (WEO Japan is the Cabinet
  Office's CY sector accounts and should reproduce the CY anchor). V24
  follows the flag.
- **8.3** For Japan the anchor `TR`, `TE`, `NLB` in the bridge and the
  decomposition are the CY values; the COFOG lines enter through the D19
  bridge (their CY share of the FY total by function is not constructed;
  the history decomposition on the expenditure side runs on the ESA_EXP
  tree for Japan, and the coverage note says so). US WEO fiscal series
  start in 2001, so the history decomposition starts there.
- **8.4** Net-interest cross-check unchanged; for Japan on the D21
  concept.

---

## 9. Grading placements (parent §9 unchanged)

| Row type | Grade | Variant |
|---|---|---|
| OECD anchor cells | A | both |
| BEA/ESRI secondary cells in non-anchor years | A (identical concept) / B (presentation differs) | both |
| USA Level II proxies (D26) | B | both |
| JPN D.51 payer-share split (§7.15) | B | both |
| AMECO / OECD EO direct GG lines to 2027 | A/B (OECD EO totals B) | strict |
| MHLW pension valuation → GF10_2 | B (measured share; 1.0x–1.1x expected) | strict |
| CMS Medicare → GF07 component | B if ≥ 0.90 else C | maximum (C) / strict (B only if the composite closes) |
| CBO/OMB/MOF/Cabinet Office sub-perimeter | C | maximum |
| NIPA 1929–1969 legs | B | both (C legs maximum only) |
| ESRI 2000-base 1980–1993 legs | C | maximum |
| Reconstructed JGB positions | B | debt |

---

## 10. Validation additions (parent V1–V28, debt V29–V40 continue)

| ID | Test | Sev |
|---|---|---|
| V41 | Every `lines_absent` line has `structural_zero` rows in every anchor year and no rows elsewhere; every `structural_zero` row is in `lines_absent`; V2/V22/V26 identities hold with them | ERROR |
| V42 | FY-labelled tree: every row carries `source_period_basis = FY` and a `native_period` label; no CY source chained onto it (§7.14); `fy_cy_bridge.csv` additive per year | ERROR |
| V43 | JPN interest lines: FISIM-adjusted vs unadjusted wedge reported per year; strict rows carry `d41_fisim_adjusted`; V1 tolerance exemption recorded | WARN |
| V44 | USA Level II rows are `level2_proxy_actual`, grade B, with concept note; `remainder + Σ level2 = parent` (V19) holds; `GF0170_T` comparison reported for 1980–89 | ERROR |
| V45 | Debt: every reconstructed position is typed `rolled_from_flows`; at every year-end BoJ holdings ≤ position per issue, Σ by type within `v31` tolerance of the annual-report total, and the live snapshot reproduced | ERROR / WARN (tolerance) |
| V17 (amended) | `coverage_share`, `coverage_share_year` and a perimeter note on every sub-perimeter proxy row (D22); no such row in strict | ERROR |
| V24 (amended) | Rule chosen by `weo_perimeter_gap_expected` (§8.2) | WARN |
| V9 (amended) | `structural_zero` admitted in both variants | ERROR |

---

## 11. Architecture

### 11.1 Config keys (`config/countries.yaml`, per country)

```yaml
USA:
  currency: USD
  anchor_family: oecd_sna
  anchors: {expenditure: OECD_T11, expenditure_esa: OECD_T12_EXP,
            revenue: OECD_T12_REV, balance: OECD_T12_BAL, tax_detail: OECD_T10}
  gdp_source: OECD_T1
  secondary_national: BEA_NIPA
  interest_anchor: d41            # no Level II table; D26 proxy = D.41
  level2_source: BEA_NIPA_T316    # D26
  lines_absent:                   # D20
    R01: "no value-added tax; D.211 = 0 in OECD T12"
    E04: "Medicare and Medicaid are D.62 in the SNA presentation; D.632 = 0"
    GF05: "BEA has no environmental-protection function; components in 04 and 06"
  period_basis: {anchor: CY, trees: {expenditure: CY, expenditure_esa: CY, revenue: CY}}
  fy_to_cy_weights: [0.75, 0.25]  # federal Oct–Sep sources
  envelope_forecast: [EC_AMECO, OECD_EO]
  weo_perimeter_gap_expected: true
  perimeter_break: null
JPN:
  currency: JPY
  anchor_family: oecd_sna
  anchors: {expenditure: OECD_T11, expenditure_esa: OECD_T12_EXP,
            revenue: OECD_T12_REV, balance: OECD_T12_BAL, tax_detail: OECD_T10}
  gdp_source: OECD_T1
  secondary_national: ESRI_SNA
  interest_anchor: level2
  d41_concept: fisim_adjusted     # D21
  lines_absent: {}
  period_basis: {anchor: CY, trees: {expenditure: FY, expenditure_esa: CY, revenue: CY},
                 fy_start_month: 4, fy_label: start_year}   # D19
  fy_to_cy_weights: [0.25, 0.75]
  envelope_forecast: [EC_AMECO, OECD_EO]
  weo_perimeter_gap_expected: false
  perimeter_break: null
```

GBR, FRA and DEU gain `anchor_family: ons` / `eurostat`, `lines_absent:
{}`, `fy_to_cy_weights: [0.25, 0.75]` (GBR) and `perimeter_break: 1991`
(DEU) so that no behaviour changes in R0.

### 11.2 Endpoint additions (`ingest/endpoints.py`, all verified 200 on 2026-09-20)

```
OECD_T12_FLOWS = {EXP: "OECD.SDD.NAD,DSD_NASEC10@DF_TABLE12_EXP,1.1",
                  REV: "…@DF_TABLE12_REV,1.1", BAL: "…@DF_TABLE12_BAL,1.1"}
OECD_T10_FLOW  = "OECD.SDD.NAD,DSD_NASEC10@DF_TABLE10,1.1"      # key A.{iso3}.S13..........
OECD_T1_FLOW   = (resolve in U0: DF_TABLE1_EXPENDITURE, B1GQ)
OECD_EO_FLOW   = "OECD.ECO.MAD,DSD_EO@DF_EO,1.5"                # key {iso3}.<M1>+<M2>….A
BEA_TXT_BASE   = "https://apps.bea.gov/national/Release/TXT"     # NipaDataA.txt, NipaDataQ.txt, SeriesRegister.txt
FISCALDATA_BASE= "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
NYFED_SOMA_BASE= "https://markets.newyorkfed.org/api/soma"
FRB_Z1_ZIP     = "https://www.federalreserve.gov/releases/z1/current/z1_csv_files.zip"
OMB_UPLOADS    = "https://www.whitehouse.gov/wp-content/uploads/2026/04/"  # BROWSER_HEADERS
CBO_RAW        = "https://raw.githubusercontent.com/US-CBO/eval-projections/main/input_data/"
CMS_TR_ZIP     = "https://www.cms.gov/files/zip/2026-expanded-supplementary-tables-figures.zip"
ESRI_TABLES    = "https://www.esri.cao.go.jp/en/sna/data/kakuhou/files/{yyyy}/tables/{yyyy}{table}_en.xlsx"
ESRI_ARCHIVE   = "https://www.esri.cao.go.jp/jp/sna/data/data_list/kakuhou/files/h{nn}/tables/{file}.xls"
MOF_JGB_APPX   = "https://www.mof.go.jp/jgbs/reference/appendix/"         # jgb_historical_data.xls, fb_historical_data.xls, maturity.xlsx, …
MOF_ANNUAL     = "https://www.mof.go.jp/jgbs/publication/annual_report/{yyyy}/{yyyy}nenpou{nn}.xlsx"
MOF_JGBI_KEISUU= "https://www.mof.go.jp/jgbs/topics/bond/10year_inflation-indexed/keisuu/"
BOJ_MEI        = "https://www.boj.or.jp/en/statistics/boj/other/mei/release/{yyyy}/mei{yymmdd}.xlsx"
BOJ_FOF_ZIP    = "https://www.stat-search.boj.or.jp/info/fof.zip"
MHLW_ZAISEI    = "https://www.mhlw.go.jp/content/001286770.zip"
CAO_CEFP       = "https://www5.cao.go.jp/keizai-shimon/kaigi/minutes/{yyyy}/{mmdd}shiryo_{nn}.pdf"
NDL_WARP       = "https://warp.ndl.go.jp/web/{timestamp}/{url}"
```

Fiscal Data needs `curl -g`-style literal brackets in `page[size]`; OMB
needs browser headers; the BEA API needs a registered key and is not
used.

### 11.3 The anchor-family interface (D27, R0)

```python
class AnchorFamily(Protocol):
    def cofog(self, iso3, code) -> pd.Series            # GFxx / GFxxyy / "_T", LCU mn, CY or FY per config
    def main(self, iso3, item, direction) -> pd.Series  # T12-style items, "payable" | "receivable"
    def tax(self, iso3, code) -> pd.Series              # T10 / taxag / NTL cells
    def d41_payable(self, iso3) -> pd.Series
    def gdp(self, iso3) -> tuple[pd.Series, str]
    def totals(self, iso3) -> dict[str, pd.Series]      # TR, TE, B9
    def level2(self, iso3, line_code) -> pd.Series | None   # None -> fallback / proxy path
```

Implementations: `EurostatFamily`, `OnsFamily` (wrapping today's readers
unchanged), `OecdSnaFamily` (new: `_oecd_frame` over T11/T12/T10/T1,
UNIT_MULT-scaled, FY-labelling per config). Secondary national readers
(`bea_nipa.py`, `esri.py`) are ordinary reader modules used by the
backward, Level II and payer-share code, not families. The twelve routing
sites listed in `REPLICATION_SCOPING.md` §6 F1 call `config.family(iso3)`.

### 11.4 Repo layout additions

```
config/countries.yaml          keys per §11.1
config/lines.yaml              oecd_t11 / oecd_t12 / oecd_t10 / bea_nipa / esri cells
config/sources.yaml            §13 entries
crosswalks/OECD_T11_to_COFOG.csv, OECD_T12_to_ESA_EXP.csv, OECD_T12_T10_to_ESA_REV.csv,
           BEA_NIPA_to_COFOG.csv, BEA_NIPA_to_ESA_EXP.csv, BEA_NIPA_to_ESA_REV.csv,
           ESRI_S6_2_to_ESA_REV.csv, ESRI_2000BASE_to_COFOG.csv, OECD_EO_to_LINES.csv,
           CBO_to_COFOG.csv, OMB_to_COFOG.csv, CMS_to_COFOG.csv, MHLW_to_COFOG.csv,
           CAO_to_ENVELOPE.csv, MOF_to_COFOG.csv
src/ggfiscal/standardise/families.py      AnchorFamily + three implementations
src/ggfiscal/standardise/readers_oecd.py  T11/T12/T10/T1/EO
src/ggfiscal/standardise/readers_bea.py   NIPA flat file (register-driven)
src/ggfiscal/standardise/readers_esri.py  ESRI xlsx (current + archive vintages), pdf tables
src/ggfiscal/debt/readers/{fiscaldata,nyfed,frb_z1}.py, register_usa.py, aggregates_usa.py
src/ggfiscal/debt/readers/{mof,boj}.py, register_jpn.py, aggregates_jpn.py
tools/extract_pdf_tables.py               D23 extractor (Cabinet Office, MHLW 2018, MOF)
notebooks/forecasts_{USA,JPN}_{expenditure,esa,revenue}.ipynb (seeded by copy)
deliverables/strict_USA.csv, strict_JPN.csv, fy_cy_bridge.csv
```

---

## 12. Build stages and gates

Each stage ends with `pytest` green, `ggfiscal validate` with no ERROR,
`DECISIONS.md` entries, and `HANDOFF.md` rewritten. Gates are hard.

### Stage R0 — Generalise the package (no new country)
- D27: `AnchorFamily` and the three existing implementations; the twelve
  routing sites call it. Country list, currency and iso3 schema checks,
  `COUNTRY_NAME` maps (three copies), `manifest.FLAT_FILES` from config.
- D20 plumbing: `lines_absent`, `structural_zero`, V41; identities,
  `dynamics.decompose`, `balance.py` and `test_gate1` tolerate declared
  absences (empty for the existing three).
- §7.10 weights and `source_period_basis` from config/register; D19
  plumbing (`period_basis.trees`, FY labelling, `fy_cy_bridge.csv`,
  V42) with no FY tree yet.
- `weo_perimeter_gap_expected` and `perimeter_break` read from config
  (`bridge.py`, `stage5.py`, `backward.py`).
- GFS COFOG/SOO backward legs generic (today DEU-only).
- Notebook tooling seeds a new country's forecast books by copy and
  inserts its chartbook cell blocks; chart site reads countries from
  config.
- Debt engine: explicit per-country branches (`intermediates.official_totals`
  `else` removed; `register.COUNTRY_MODULES`, `aggregates.class_aggregates`,
  `chains._subsector_items`, `reference.py`, `validate.check_v31` read
  config or per-country modules).
- **Gate R0:** `data/canonical/` and `deliverables/` byte-identical to the
  committed versions for GBR/FRA/DEU except `run_id`; `pytest` green
  (existing 328 tests plus the new R0 tests); `validate` ERROR = 0 with
  the same WARN count; a dry `config.family("USA")` raising a clear
  "family not configured" error, not an `elif` fall-through.

### Stage U0 — Verify and harvest (USA)
- Register every §13 USA entry; `ggfiscal fetch --all` pulls OECD
  T11/T12/T10/T1 (USA), OECD EO, IMF GFS/WEO (USA), OECD RS (USA), AMECO
  chapters with USA rows, NIPA flat files and register, Z.1 zip, OMB
  workbooks, CBO mirror, CMS zip; snapshots and manifest. Record the
  blocked hosts (D24).
- Measure first/last year per (line, source); the Level II proxy shares
  (D26); the sales-grossing and enterprise wedges (§3); the WEO base-year
  bridge (§8.2) with the perimeter rule.
- **Gate U0:** all 41 USA lines have programmatic coverage from at least
  one source or a `lines_absent` entry; base-year bridge computed on the
  latest WEO vintage; `reports/source_verification_USA.md`.

### Stage U1 — Canonical history (USA)
- `OecdSnaFamily` for USA; the three trees, ledger, Level II proxies
  (D26), structural zeros (D20), IMF/OECD-RS reconciliation fields;
  crosswalks `OECD_T11_to_COFOG`, `OECD_T12_to_ESA_EXP`,
  `OECD_T12_T10_to_ESA_REV`, `BEA_NIPA_to_COFOG`.
- **Gate U1:** 41 lines + ledger 1970–2024 from anchors; V1–V4, V7–V9,
  V12, V14, V19–V23, V41, V44 green; small multiples render; history-side
  §8.3 decomposition 2001–2024 runs and passes V26.

### Stage U2 — Backward extension (USA)
- OECD RS 1965–1969 tax legs; NIPA 1929/1959–1969 legs (§7.16); Level II
  proxies back to 1959.
- **Gate U2:** every stitch has boundary record, crosswalk version,
  grade, V5; `DECISIONS.md` records why each line stops (1970 for
  TE/TR/E02/R09; 1965 or 1929/1959 otherwise).

### Stage U3 — Strict forecasts (USA)
- AMECO and OECD EO direct lines to 2027 (E01–E03, E05, E06, E08, E09,
  R02, R03, R04, R06, R07, TR, TE, NLB); `GF01_7`/`GF01` via UYIG/GGINTP
  as for the European three; MHLW-style statutory sources: none for the
  US in strict beyond CMS where the composite closes (D22).
  Declarations (D7) for every other line.
- **Gate U3:** every strict row A or B with measured coverage; every
  undeclared line has its note; V10, V11, V13, V15, V16, V18 green.

### Stage U4 — Maximum-extension forecasts (USA)
- CBO baseline (mirror), OMB Historical Tables incl. subfunction 901
  gross interest, CMS Medicare trustees: rank-4 proxies with
  `coverage_share` on the anchor, 0.75/0.25 conversion or quarterly FY
  sums, `residual_method`, grade C (B where ≥ 0.90).
- **Gate U4:** V17 (amended) green; variants distinguishable row by row;
  coverage matrix complete.

### Stage U5 — Reconciliation (USA)
- §8.2–8.5 for both variants and every WEO vintage; perimeter rule
  (§8.2); `resid_total` per side beyond the international horizon;
  net-interest cross-check on the OECD/AMECO concept with the NIPA
  imputed-interest wedge noted.
- **Gate U5:** additivity exact; residual history populated; the reader
  can state per horizon how much of the WEO change the covered lines
  explain (expected: most to 2027, near zero beyond).

### Stage U6 — Packaging and go/no-go
- `strict_USA.csv`, catalogue, dictionary rows, README regeneration,
  forecast books seeded and executed, chartbook and chart-site blocks,
  `statistical-forecasts`/`forecast-levels`/`benchmark-*` chain including
  USA, `detect-vintages` covering the new hosts.
- **Gate U6:** every stitched value reproducible from the bundle;
  `tests/deliverables` green with USA; the committee's go/no-go for J0
  recorded in `DECISIONS.md`.

### Stages J0–J6 — Japan fiscal package
Mirror U0–U6 with these specifics:
- **J0:** ESRI current-vintage tables (7, 8, 4, 3, 6(2), 24(3)), the
  2000-base archive vintage, OECD T11/T12/T10/T1 (JPN), IMF, RS, AMECO,
  OECD EO, MHLW valuation zip, Cabinet Office and 2018 outlook PDFs
  (D23 extraction), MOF budget documents. Verify cell-for-cell that OECD
  T11 = ESRI FY and T12 = ESRI CY (the scoping note's evidence, re-run).
  Gate J0 as U0, plus the FY/CY basis recorded per source.
- **J1:** COFOG tree FY-labelled (D19) with `fy_cy_bridge.csv`; CY trees
  2005–2024 from T12 and 1994–2004 from ESRI Tables 4/3; payer-share
  split (§7.15); D21 concept; V42, V43. Gate J1 as U1 with V42/V43.
- **J2:** OECD RS 1965–1993 (FY) for the tax lines of the CY revenue
  tree, converted per §7.14 before growth (B, both variants); ESRI 2000-base
  archive legs 1980–1993 for the CY trees' GG-account items (converted,
  C, maximum) and 1980–2004 FY-native for the COFOG tree (C, maximum;
  Q-K4). Gate J2 as U2.
- **J3:** AMECO/OECD EO to 2027 on the CY trees; MHLW pension valuation
  → `GF10_2` strict B to 2120 on the FY tree (its own nominal path;
  `gdp_source_id = MHLW_constructed` per §7.5 from the valuation's
  wage/price assumptions); declarations. Gate J3 as U3.
- **J4:** Cabinet Office CG+LG (net interest, PB; `sub_perimeter_envelope`
  memorandum and a maximum-only C proxy for `GF01_7` net → gross declared
  not constructed, i.e. **declined**: a net-only source at C is admitted
  for `NI` memorandum only), 2018 outlook benchmark years for `GF07`
  (C), MOF budget/later-years (C/D), defence plan (C). Gate J4 as U4.
- **J5:** reconciliation on CY totals; COFOG side via the bridge (§8.3).
  Gate J5 as U5.
- **J6:** packaging as U6, plus the FY-labelled charts (the chartbook
  states the basis in every Japanese COFOG title). Gate J6 as U6.

### Stages UD0–UD5 — US debt extension (mirror parent debt D0–D5)
- **UD0:** register Fiscal Data endpoints (auctions, MSPD Table III,
  TIPS CPI detail/summary, FRN indexes, interest expense, average rates,
  MTS tables), NY Fed SOMA, Z.1, BLS CPI-U, NIPA 3.18B; harvest;
  `debt.yaml` perimeter (marketable Treasuries: bills incl. CMBs, notes,
  bonds, TIPS, FRNs; excluded: savings bonds, SLGS, Government Account
  Series, FFB), sub-types, year-ends (31 Dec; 30 Sep memorandum),
  chain sources.
- **UD1:** reference series (CPI-U NSA; 13-week bill rate from the
  auction file; SOFR when reachable), intermediates: step A Treasury
  interest expense (2010–; OMB 901 FY1962–2009 with 3.18B bridge), MTS
  means of financing (2015–; Z.1 F.106 earlier); step B Z.1 S1311 IMA
  interest paid and NLB; step C package `GF01_7`/`NLB`.
- **UD2:** register from `auctions_query` (terms, reopenings as taps,
  CMBs as bills), positions from MSPD 2001– and rolled 1980–2000 (D25),
  TIPS uplift from index ratios (2008–) and recomputed 1997–2008 (DD9,
  B), FRN coupons from the daily index, SOMA overlay per CUSIP 2003–.
  V29–V31, V45.
- **UD3:** interest by security both bases; chain with items
  `intragovernmental_interest` (removed), `nonmarketable_interest`,
  `imputed_pension_interest` (step B→C), `state_and_local`, residual.
- **UD4:** financing chain (net issuance → MTS/Z.1 net borrowing → S1311
  B.9 via IMA discrepancy → S13 NLB with state/local B.9), maturity
  profile, issuance buckets (US 20-year bond in 20–30; bills 0–1).
- **UD5:** packaging into the debt bundle; debtbook section; tests.
  Gates per parent D0–D5.

### Stages JD0–JD5 — Japanese debt extension
- **JD0:** MOF auction files (JGB types, T-bills, liquidity enhancement,
  buy-backs), outstanding-by-issue snapshot, annual report workbooks
  (FY2020– live; FY2011–2019 via web archive), JGBi index-ratio files
  (2023– live; earlier via web archive), 15-year floater coupon file,
  constant-maturity yields, BoJ holdings by issue (2013– machine-readable),
  BoJ Flow of Funds zip, ESRI Tables 6(2) and 24(3); `debt.yaml`
  perimeter (marketable JGBs incl. FILP bonds and T-bills; excluded:
  retail JGBs, borrowings, government-guaranteed bonds), sub-types
  (40y/30y/20y/10y/5y/2y fixed, GX, JGBi 10y, 15y floater, discount
  bonds, T-bills), year-ends (31 Dec; 31 Mar memorandum).
- **JD1:** reference series (CPI ex fresh food from e-Stat or the index
  files themselves; 10-year auction yield for floaters); intermediates:
  step A Debt Consolidation Fund interest by bond type (FY2011–; total
  debt service FY1967–, B), issuance/redemption by FY (annual report
  table 13); step B ESRI 6(2) CG D.41 and 24(3) CG securities flows, BoJ
  FoF; step C package values. FY→CY at step A by the §7.10 weights.
- **JD2:** register from auctions (10-year from 1989; pre-1989 issues
  as aggregate-only, C); positions reconstructed (D25); JGBi uplift from
  the coefficient files; floater coupons from the fixing file; BoJ
  overlay. V29–V31, V45.
- **JD3:** interest chain with `retail_jgb_interest`, `borrowings`,
  `fy_cy_timing`, `local_government`, `social_security_funds`, residual.
- **JD4:** financing chain, maturity profile (40-year in 30+), issuance
  buckets.
- **JD5:** packaging. Gates per parent D0–D5.

---

## 13. Seed source register (status 2026-09-20; U0/J0 re-verify)

Entries the existing register already carries (`OECD_T11`, `OECD_RS`,
`IMF_GFS`, `IMF_WEO`, `EC_AMECO`) gain `USA`/`JPN` in `countries`.

### 13.1 USA — fiscal

| source_id | Institution | Object | Years | Basis | Role | Grade | Status |
|---|---|---|---|---|---|---|---|
| OECD_T12_EXP / _REV / _BAL | OECD (BEA) | `DF_TABLE12_{EXP,REV,BAL}` A.USA.S13 | 1970–2024 | CY | anchor | A | confirmed_live |
| OECD_T10 | OECD (BEA) | `DF_TABLE10` taxes/contributions detail (D51A/B, D214A, D611/D613, D59, D91) | 1970–2024 | CY | anchor cells | A | confirmed_live |
| OECD_T1 | OECD | GDP B1GQ (flow id to resolve in U0) | | CY | denominator | A | to_verify |
| BEA_NIPA | BEA | `NipaDataA.txt`, `NipaDataQ.txt`, `SeriesRegister.txt`; Tables 3.1/3.2/3.3 (1929–2025), 3.16/3.17/3.15.5 (1959–2024), 3.18B (FY1952–2024) | 1929–2025 | CY (3.18B FY) | secondary, Level II (D26), backward | A/B | confirmed_live |
| FRB_Z1 | Federal Reserve/BEA | Z.1 CSV bundle: S1311 IMA, F.106, L.210 | 1945–2025 | CY | debt step B | A | confirmed_live |
| OECD_EO | OECD | `DSD_EO@DF_EO,1.5` USA GG measures (YPGT, YPG, GGINTP, GGINTR, TYH, TYB, TIND, SSRG, SSPG, IGAA, TKPG, CGAA, NLGQ, GGFLQ) | 1960–2027 | CY | forecast rank 1/2; envelope | A/B | confirmed_live |
| OECD_EO_LTB | OECD | long-term scenarios (balance, debt, rates) | 1990–2100 | %GDP | memorandum only (§15 Q-K1) | C | confirmed_live |
| CBO_BASELINE | CBO via GitHub mirror | `baselines.csv` (every baseline 1982–2026-02), `actuals.csv` | FY1982–FY2036 | federal FY, cash | maximum proxy (D22) | C | confirmed_live (cbo.gov blocked) |
| CBO_SITE | CBO | 10-year workbooks, NIPA-basis tables, LTBO | | | trigger for long US legs | — | **blocked** (D24) |
| OMB_BUDGET | OMB | Historical Tables with estimates (hist01–03, 03z2 incl. 901 gross interest, 14, 15), Public Budget Database | FY1940/1962–FY2031 | federal FY, policy | maximum proxy; federal gross interest | C | confirmed_live (browser headers) |
| CMS_TRUSTEES | CMS OACT | Medicare Trustees expanded tables (CSV): HI/SMI operations CY, 75-yr %GDP | 1967–2034 / 2100 | CY | GF07 component, R06 component | B/C | confirmed_live |
| SSA_TRUSTEES | SSA OACT | OASDI single-year tables | 2100 | CY | GF10_2 / R06 components | — | **blocked** (D24) |
| CENSUS_GOVFIN | Census | State & local finances | 1992– online | state FY, cash | not used (D) | D | confirmed_live |
| BLS_CPI | BLS | CPI-U NSA `CUUR0000SA0` API | 1913– | monthly | TIPS recompute (DD9) | A | confirmed_live |

### 13.2 USA — debt

| source_id | Object | Years | Status |
|---|---|---|---|
| US_FD_AUCTIONS | `v1/accounting/od/auctions_query` — 11,124 auctions, 4,648 CUSIPs | 1979-10– | confirmed_live |
| US_TD_TAWS | TreasuryDirect `TA_WS/securities/search` (cross-check feed) | 1980– | confirmed_live |
| US_FD_MSPD_T3 | `v1/debt/mspd/mspd_table_3_market` per-CUSIP month-end | 2001-01– | confirmed_live |
| US_FD_MSPD_T1 | `mspd_table_1` by class, public vs intragovernmental | 2001-01– | confirmed_live |
| US_FD_TIPS_CPI | `tips_cpi_data_detail` / `_summary` | 2008-05– | confirmed_live |
| US_FD_FRN_INDEX | `frn_daily_indexes` | 2024-10– (13-week rate in auctions from 2014) | confirmed_live |
| US_FD_INTEREST_EXPENSE | `v2/accounting/od/interest_expense` by category | 2010-05– | confirmed_live |
| US_FD_AVG_RATES | `v2/accounting/od/avg_interest_rates` | 2001-01– | confirmed_live |
| US_FD_MTS | `v1/accounting/mts/mts_table_{1..9}` incl. 6/6a–6d means of financing | 2015-03– | confirmed_live |
| US_FD_DEBT_OUTSTANDING / DEBT_TO_PENNY | annual FY 1790–; daily 1993– | | confirmed_live |
| FRB_SOMA | NY Fed SOMA per CUSIP, weekly | 2003-07– | confirmed_live |

### 13.3 JPN — fiscal

| source_id | Institution | Object | Years | Basis | Role | Grade | Status |
|---|---|---|---|---|---|---|---|
| OECD_T12_EXP / _REV / _BAL | OECD (ESRI) | as USA | 2005–2024 | CY | anchor (CY trees) | A | confirmed_live |
| OECD_T10 | OECD (ESRI) | tax detail (no payer split) | 1994–2024 | FY | secondary | B | confirmed_live |
| ESRI_SNA_S7 / S8 | ESRI | Table 7 outlays by function (69 groups), Table 8 final consumption by function | FY2005–FY2024 | FY | COFOG cross-check and D.1/P.2 by function | A | confirmed_live |
| ESRI_SNA_I4 / C3 | ESRI | Table 4 GG income accounts (D.41 both concepts, D.2 incl. VAT, D.3, D.5, D.61 split, D.62, D.632, D.7, D.9); Table 3 capital account (P.51, NP, D.9, NLB) | 1994–2024 | FY + CY + Q | CY anchor 1994–2004; bridge timing | A | confirmed_live |
| ESRI_SNA_S6_2 | ESRI | Table 6(2) GFS presentation by subsector (1111/1112 payer split, subsector D.41, sales) | FY1994–FY2024 | FY | payer shares (§7.15); debt step B | A (FY) | confirmed_live |
| ESRI_SNA_S6 / S243 | ESRI | subsector SNA accounts; financial transactions by subsector | FY1994– | FY | debt step B | A | confirmed_live |
| ESRI_ARCHIVE_2000BASE | ESRI | 2009 vintage (93SNA, 2000 base): COFOG L1, GG account, subsectors (JP xls) | FY1980–FY2009 | FY | backward legs | C | confirmed_live |
| ESRI_SDDSPLUS | ESRI | quarterly GG operations (2015–), gross debt (2012–) | | Q | bridge timing cross-check | B | confirmed_live |
| OECD_EO | OECD | JPN GG measures | –2027 | CY | forecast rank 1/2; envelope | A/B | to_verify (JPN key not pulled) |
| MHLW_ZAISEI_KENSHO_2024 | MHLW | 2024 pension valuation, 36 scenario workbooks | FY2024–FY2120 | FY | GF10_2 strict B; R06 memorandum | B | confirmed_live |
| MHLW_2040_OUTLOOK_2018 | MHLW/CEFP | social security benefits by branch, benchmark FY2018/2025/2040 (PDF, D23) | 2040 | FY | GF07/GF10 maximum C | C | confirmed_live |
| CAO_CHUCHOKI | Cabinet Office | medium-to-long-term projection, Jan/Jul (PDF, D23): CG+LG PB, net interest, balance, debt; macro | FY2040 | FY | sub-perimeter envelope memorandum; NI memorandum | C | confirmed_live |
| MOF_KOUNENDO | MOF | later-years estimate (PDF, D23) | 3 yrs | FY, central cash | maximum C/D | C/D | confirmed_live |
| MOF_BUDGET | MOF | annual budget documents (PDF) | 1 yr | FY, central cash | maximum C/D; defence plan | C/D | confirmed_live |
| MOF_FSC_LONGTERM | Council on Fiscal System | long-term estimate to FY2060 | | | not located | D | to_locate (web archive) |

### 13.4 JPN — debt

| source_id | Object | Years | Format | Status |
|---|---|---|---|---|
| JP_MOF_AUCTION_JGB | auction results by type (≈ 1,370 issues 1990–2025) | 1979/1987/1989– | xls (bilingual) | confirmed_live |
| JP_MOF_AUCTION_TBILL | T-bill/FB auctions, issues 1–1397 | FY1999– | xls | confirmed_live |
| JP_MOF_LIQUIDITY_BUYBACK | liquidity-enhancement reopenings; buy-backs | 2006–/2002– | xls | confirmed_live |
| JP_MOF_OUTSTANDING_BY_ISSUE | outstanding by issue (live snapshot; web-archive captures) | 2026-03 | xlsx | confirmed_live |
| JP_MOF_ANNUAL_REPORT | JGB statistical annual report (interest by bond type; outstanding/issuance/redemption by type) | FY2011– | xlsx (JP) | confirmed_live (FY2011–19 via web archive) |
| JP_MOF_ZAISEI_TOKEI | national debt service by FY | FY1967– | xlsx | confirmed_live |
| JP_MOF_JGBI_INDEX_RATIO | JGBi applicable CPI and index ratio per issue, daily | 2023-05– (2004– via web archive) | xls | confirmed_live |
| JP_MOF_FRN15_COUPONS | 15-year floater fixings, issues 8–48 | 2000–2023 | xls | confirmed_live |
| JP_MOF_CM_YIELDS | constant-maturity yields (Shift_JIS, Japanese-era dates) | 1974– | csv | confirmed_live |
| JP_MOF_ISSUANCE_PLAN / TAIMIN / GBB / REDEMPTION | issuance plans (PDF), treasury funds vs private sector, quarterly outstanding, redemption schedule | various | pdf/xls | confirmed_live |
| JP_BOJ_HOLDINGS_BY_ISSUE | BoJ JGB holdings by issue | 2001– (xlsx 2015–) | xlsx/xls/PDF/HTML | confirmed_live |
| JP_BOJ_FOF | Flow of Funds bulk zip (1.27 M rows) | 1979– (2008SNA 2005–) | csv | confirmed_live |
| NDL_WARP | National Diet Library web archive for MOF back-issues | | | confirmed_live |

---

## 14. Country traps

**USA.** The BEA API needs a registered key; use the flat files. Fiscal
Data paging needs literal square brackets. NIPA "total expenditures" is
already the ESA TE concept; NIPA "current expenditures" (Table 3.16) is
not (CFC in, investment out) — never mix them in a Level II share without
Table 3.17. Interest: three concepts in play (OECD T12 D41; NIPA/IMA
interest incl. imputed pension interest and TIPS accrual; Treasury
"interest expense" incl. intragovernmental) — name the concept on every
row. WEO US fiscal series start 2001 and carry documented adjustments;
the perimeter rule applies. Federal FY is October–September (July–June
before FY1977 with a transition quarter in 1976). State fiscal years vary
and are already converted by BEA. Personal taxes are largely cash;
corporate taxes accrual. Federal Reserve remittances are dividends and
swing R08. Puerto Rico and territories are outside NIPA. CBO baseline is
current law; OMB is administration policy — `scenario_label` both, CBO
preferred where both cover a line. Treasury 20-year bonds sit in the
20–30 bucket; CMBs are bills; the FRN index is the 13-week bill high
rate; TIPS index ratios before May 2008 are recomputed (B).

**JPN.** Every functional and subsector table is fiscal-year, labelled by
the starting April; OECD T11, IMF GFS, OECD RS and OECD T10 carry FY
values under CY-looking labels with no flag — register the basis from
the ESRI cell match, not from the file. Two D.41 concepts (D21). CFC sits
inside ESRI's functional "final consumption". The 2020 benchmark
(December 2025) shifted history; snapshot vintages. AMECO's 2025 column
is NA in the Spring 2026 file. The local consumption tax is booked at
central government. LTC benefits in kind are in 10.2. FILP bonds are
central-government securities but not "ordinary JGBs"; the Cabinet
Office debt figure excludes them. Pre-1989 10-year issues and per-issue
positions are not machine-readable (D25). MOF xls files are BIFF8 with
Japanese labels (xlrd reads them); `jgbcm_all.csv` is Shift_JIS with
Japanese-era dates; the MHLW zip has cp932 member names; the BoJ flat
file is JIS. MOF back-issues live in the National Diet Library web
archive under the original URL. e-Stat needs an application id and is
not needed.

---

## 15. Committee questions reserved (Q-K, new)

| # | Question | Default |
|---|---|---|
| Q-K1 | OECD EO long-term scenarios (balance, debt, interest-rate paths to 2100): admit as a memorandum benchmark beside the WEO in §4.6 of the chartbook, or ignore? | Memorandum only; never a line source (D13). |
| Q-K2 | US TE/TR before 1970: accept a grade C leg from NIPA totals (sales-netting wedge measured and held constant), maximum only, or stop at 1970? | Stop at 1970; the component lines carry the history. |
| Q-K3 | Japan's `GF01_7` long leg: the Cabinet Office publishes net interest for CG+LG; constructing gross from the effective-rate path is D13-prohibited. Accept `NI` memorandum only? | Yes; no gross construction. |
| Q-K4 | Japanese COFOG tree backward legs from the 2000-base vintage: chain 1980–2004 on the archive throughout, or 1980–1993 only (2020 benchmark from 1994 for the CY trees, 2005 for COFOG)? | 1980–2004 for COFOG (the current COFOG series starts 2005), 1980–1993 for the CY trees; overlap divergence reported (V5). |
| Q-K5 | US register perimeter: include Federal Financing Bank and agency securities held by the public? | No: marketable Treasuries only, as DD1 excludes non-marketable and sub-national. |
| Q-K6 | Pin the go/no-go for Japan to Gate U6, or start J0 (harvest and verification only) in parallel once R0 passes? | J0 in parallel after R0 (harvest only); J1+ after U6. |

---

## 16. Model allocation and conventions

Parent §16 conventions apply (spec-first, append-only decisions, hard
gates, content-addressed snapshots, `HANDOFF.md` before every stop).
Model allocation for this extension:

| Work | Tier |
|---|---|
| R0 design and review; U0/J0 source verification and every anchor, concept and crosswalk decision (D18–D26 applications); D23 extraction verification; every gate review | strongest available model |
| U1–U6, J1–J6, UD, JD implementation (readers, families, legs, chains, tests) | mid tier |
| Notebook seeding, chart-site maps, fixture and literal-site edits, README prose regeneration | small tier |

One stage per session. Every stage's session opens by reading
`HANDOFF.md`, this document, and the sections of the parent it cites, and
closes with the verification chain re-run and the gate record in
`DECISIONS.md`.
