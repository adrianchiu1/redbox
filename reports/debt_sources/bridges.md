# Step-B (and step-C) official bridge items — verification report

`src/ggfiscal/debt/bridges.py`, `bridge_items(iso3, chain, year) -> list[ChainItem]`.
Built 2026-09-09 against the D8 snapshot store of that date (ONS PSF Appendix A
vintage 2026-08-20, `da9919a727d1`; Appendix S `21d7fd85ca0d`; Eurostat
`gov_10dd_edpt2/edpt3`, `gov_10q_ggdebt`, `gov_10a_main` pulls of 2026-09-09).

Every item is `item_type="official"` — one published cell, with a sign applied
and stated in the item's `basis`. Nothing is netted, interpolated or balanced;
whatever the published items do not explain stays in the step residual (D16).
Chain sign conventions are `chains.py`'s: the interest chain runs in D.41-payable
sign (+ = interest expenditure), the financing chain in **net-borrowing** sign
(+ = borrowing), so the step-B official total is −B.9 of S.1311 and the step-C
total is −NLB.

Step C for FRA and DEU is already assembled by `chains.py` from `gov_10a_main`
subsector D41PAY / B9 and is not repeated here.

---

## Summary

| iso3 | chain | step | items | source | years | residual after items |
|---|---|---|---|---|---|---|
| GBR | financing | B_s1311_b9 | 9 | ONS PSF Appendix A, REC2 + PSA7C | 1998–2025 | ≤ £2 mn (ONS rounding) |
| GBR | financing | C_s13_nlb | 1 | ONS PSF Appendix A, PSA2 | 1998–2025 | £0 to −£1,161 mn |
| GBR | interest | B_s1311_d41 | **none** | — | — | whole wedge (−£4.3 bn in 2024) |
| GBR | interest | C_s13_gf01_7 | 1 | ONS PSF Appendix A, PSA6J_1 | 1998–2025 | £122–£206 mn (COFOG-vs-D.41) |
| FRA | financing | B_s1311_b9 | 19 | Eurostat `gov_10dd_edpt3` + `gov_10q_ggdebt`, S1311 | 2021–2025 | −£0.6 bn to −£4.1 bn (EUR) |
| FRA | interest | B_s1311_d41 | **none** | — | — | step A blocked: no carried value |
| DEU | financing | B_s1311_b9 | 19 | Eurostat `gov_10dd_edpt3` + `gov_10q_ggdebt`, S1311 | 2022–2025 | +€7.7 bn to +€89.9 bn (see caveat) |
| DEU | interest | B_s1311_d41 | 1 | Eurostat `gov_10dd_edpt3` `ORD41A_ADJ`, S1311 | 2022–2025 | −€17.6 bn to +€7.0 bn |

---

## GBR — financing, step `B_s1311_b9`

Carried: `M98R`, central government net cash requirement excluding NRAM/B&B and
Network Rail, Appendix S table 1.2A, summed over the 12 calendar months
(`intermediates._gbr_financing`), + = borrowing.
Official total: central government net borrowing, the `-NMFJ` column
(transaction code `-B.9g`), + = borrowing.

Two published identities compose into the bridge.

**REC2** — "Reconciliation of central government net borrowing and net cash
requirement", note 74 ("Column H is equal to the sum of column B to column G"),
read through `cgncr_reconciliation()`:

    RUUX = -NMFJ + ANRH + ANRS + ANRU + ANRT + ANRV

| CDID | transaction code | published column label | emitted item | sign |
|---|---|---|---|---|
| `-NMFJ` | `-B.9g` | Net borrowing | *(the step's official total)* | — |
| `ANRH` | F.4 | Net lending to private sector and rest of world | `less_net_lending_to_private_sector_and_rest_of_world` | −1 |
| `ANRS` | F.5 | Net acquisition of company securities | `less_net_acquisition_of_company_securities` | −1 |
| `ANRU` | F.3 | Adjustment for interest on gilts | `less_adjustment_for_interest_on_gilts` | −1 |
| `ANRT` | no code | Accounts receivable/payable | `less_accounts_receivable_payable` | −1 |
| `ANRV` | no code | Other financial transactions | `less_other_financial_transactions` | −1 |
| `RUUX` | no code | Net cash requirement [note 74] | *(not emitted — reached via PSA7C)* | — |

**PSA7C** — "Central government net cash requirement", notes 83–86 — supplies the
coverage difference between REC2's `RUUX` (which is the *own-account* CGNCR
*including* NRAM/B&B and Network Rail) and the carried `M98R`:

    RUUX = M98R + M98W + MUI2 - ABEC - ABEI

| CDID | published column label | emitted item | sign |
|---|---|---|---|
| `M98W` | NRAM and B&B | `nram_and_bb_net_cash_requirement` | +1 |
| `MUI2` | Network Rail | `network_rail_net_cash_requirement` | +1 |
| `ABEC` | … of which, payments to local government | `less_payments_to_local_government` | −1 |
| `ABEI` | … of which, payments to non-financial public corporations | `less_payments_to_public_corporations` | −1 |

Substituting gives the emitted set, and

    M98R + M98W + MUI2 - ABEC - ABEI - ANRH - ANRS - ANRU - ANRT - ANRV = -NMFJ

**Verification.** Both sheets publish a calendar-year block (1998–2025), so no
period conversion is used; `_gbr_cell` falls back to summing the 12 calendar
months of the monthly block only if a future vintage drops the CY block, and the
item's `basis` then says so. The reconstructed net borrowing equals the published
`-NMFJ` for **every calendar year 1998 to 2025**, maximum absolute departure
**£2 mn** (ONS publishes to £1 mn, and the two sheets round independently). The
PSA7C `M98R` calendar-year column is identical to the Appendix S 12-month sum in
all 28 years, so the carried value and the bridge sit on the same measure.

| year | carried M98R | Σ items | official −NMFJ | residual |
|---|---|---|---|---|
| 2015 | 88,147 | −2,468 | 85,679 | **0** |
| 2020 | 315,825 | −38,064 | 277,761 | **0** |
| 2024 | 183,661 | −23,977 | 159,684 | **0** |

(Before these items the step-B residual was −2,468 / −38,064 / −23,977 £ mn.)

## GBR — interest, step `B_s1311_d41`: no official bridge

Carried is the National Loans Fund Account's **total finance costs of borrowing**
(accrued; includes the index-linked capital uplift, NS&I and the other NLF costs),
converted FY→CY per §7.10. The official total is ONS `NMFX`, S.1311 D.41 payable.
Neither ONS nor HM Treasury publishes a reconciliation of the NLF account to the
national-accounts interest line — REC2/REC3 reconcile the *cash requirement* and
*net debt*, not interest, and the NLF account has no ESA bridge note. **No item is
emitted**; the whole wedge (−£2.0 bn 2020, −£4.3 bn 2024) stays in the residual.
The pieces that would be needed — accrual timing, ESA premium/discount
amortisation, the uplift accrual, other central-government units and
within-CG consolidation (§8) — are exactly the ones with no published source.

## GBR — step C (S.1311 → S.13)

UK general government is central plus local government: there is no state
government and no separate social security funds subsector. PSA2 shows the
sub-sector columns are additive — `-NMFJ` + `-NMOE` = `-NNBK` (general government
net borrowing, the Maastricht deficit) to **£0** in every calendar year
1998–2025 — so one item closes each chain.

| chain | step | sheet | CDID | published label | emitted item | sign |
|---|---|---|---|---|---|---|
| interest | `C_s13_gf01_7` | PSA6J_1 | `NUGW` | Interest (local government current expenditure) | `local_government_d41` | +1 |
| financing | `C_s13_nlb` | PSA2 | `-NMOE` | Local government net borrowing | `local_government_net_borrowing` | +1 |

`-NMOE` is published with the sign already applied (+ = borrowing), matching the
chain's convention; no re-signing is done.

**No consolidation line is emitted.** Appendix A publishes no intra-general-
government interest flow. The nearest candidates are PSA6I `ANPZ` "Interest and
dividends (net) from public sector" (a local-government *net receipt* from the
whole public sector, dividends included, so not the D.41 leg consolidated out of
general government) and PSA6E_2 `QYJR` (current *grants* to local government).
Neither is the required item, and adding either would widen the wedge rather than
close it — the unconsolidated CG + LG sum is already *below* `GF01_7`.

**Residual before → after the item** (£ mn; official totals are
`package_gf01_7('GBR')` and `−package_nlb('GBR')`):

| year | interest before | interest after | financing before | financing after |
|---|---|---|---|---|
| 2015 | 696 | **122** | 1,756 | **0** |
| 2016 | 1,011 | **323** | 7,810 | **0** |
| 2017 | 858 | **145** | 10,143 | **0** |
| 2018 | 683 | **124** | 7,327 | **0** |
| 2019 | 878 | **127** | 10,373 | **0** |
| 2020 | 786 | **142** | −3,399 | **0** |
| 2021 | 940 | **175** | −2,763 | **0** |
| 2022 | 1,079 | **208** | 11,111 | **0** |
| 2023 | 1,155 | **131** | 12,465 | **13** |
| 2024 | 1,311 | **206** | 14,893 | **−10** |
| 2025 | 1,131 | **−163** | 13,923 | **−1,161** |

Remaining wedges:

* **interest, £122–£206 mn** — the `cofog_vs_d41` wedge of §8: `GF01_7` is COFOG
  01.7 "public debt transactions" for consolidated S.13, which is not identical to
  `NMFX + NUGW` (D.41 payable of the two subsectors, unconsolidated as published).
  It is ~0.2–0.4 % of the total and has no published decomposition.
* **financing, £0** to 2022; **+13 / −10 / −1,161** in 2023/2024/2025 — the
  package-vintage wedge: the package `NLB` leg is not the same vintage as this
  Appendix A snapshot (ONS `-NNBK` for 2025 is 158,643 against the package's
  157,482). Nothing to bridge; it is a vintage difference, published as residual.

---

## FRA / DEU — financing, step `B_s1311_b9`

Source: Eurostat EDP notification tables through `sfa_components(iso3)` —
`gov_10dd_edpt3` (B.9 → change in Maastricht debt, the stock-flow adjustment
proper), **sector S1311**, unit `MIO_NAC` — plus `gov_10q_ggdebt` (S1311,
`MIO_NAC`) end-of-Q4 stocks for the instrument split of the debt change. S1311 is
published for both countries, so the S13 fallback in `_edpt3` never fires here.

**The published identity.** For both countries and every covered year,

    GD_CH = B9_T3 + F_ASS + ORADJ + YA3

exactly (≤ 0.2 mn), with

    F_ASS = F2_ASS + F3_ASS + F4_ASS + F5_ASS + F71_ASS + F8_ASS + FN_ASS
    ORADJ = ORINV + ORRNV + ORFCD + ORD41A_ADJ + F8_ADJ_LIAB + F71_ADJ_LIAB
            + FV_ADJ_LIAB + KX + K61

`B9_T3` is already "net lending (−)/net borrowing (+) (reversed sign)", i.e. the
chain's own sign, so the step-B official total needs no flipping. `KX` and `K61`
are *inside* `ORADJ` (verified: FR 2021 component sum −793.8 + KX −134 + K61 1,050
= ORADJ 122.2), so they are emitted as ORADJ components, never twice.

**From net securities issuance to net borrowing.** The chain arrives at step B
carrying net issuance of *securities*, so the change in gross debt is split by
instrument on the same face-value basis:
`ΔF2 + ΔF3 + ΔF4 = GD_CH` (verified to ≤ 0.3 mn for every covered year), and

    B9_T3 = ΔF3 + [ ΔF2 + ΔF4 − ΣF*_ASS − ΣORADJ-components − YA3 ]

The bracket is what `bridge_items` emits, so the residual left at step B is
exactly **ΔF3 − carried**: the wedge between the change in the subsector's
Maastricht debt securities and the chain's carried value.

**The 19 items** (Eurostat code → item name; the full codelist label is carried in
each item's `basis`):

| # | code | Eurostat label (NA_ITEM codelist) | item | sign |
|---|---|---|---|---|
| 1 | `F2` (Q4 stock Δ) | gross debt at face value — currency and deposits | `net_issuance_other_liabilities_currency_and_deposits` | +1 |
| 2 | `F4` (Q4 stock Δ) | gross debt at face value — loans | `net_issuance_other_liabilities_loans` | +1 |
| 3 | `F2_ASS` | Net acquisition (+) of financial assets - currency and deposits | `less_net_acquisition_currency_and_deposits` | −1 |
| 4 | `F3_ASS` | … - debt securities | `less_net_acquisition_debt_securities` | −1 |
| 5 | `F4_ASS` | … - loans | `less_net_acquisition_loans` | −1 |
| 6 | `F5_ASS` | … - equity and investment fund shares/units | `less_net_acquisition_equity_and_investment_fund_shares` | −1 |
| 7 | `F71_ASS` | … - financial derivatives | `less_net_acquisition_financial_derivatives` | −1 |
| 8 | `F8_ASS` | … - other accounts receivable (+) | `less_net_acquisition_other_accounts_receivable` | −1 |
| 9 | `FN_ASS` | … - other financial assets (F.1, F.6) | `less_net_acquisition_other_financial_assets` | −1 |
| 10 | `ORINV` | Adjustments: issuances above (−)/below (+) nominal value | `less_sfa_adjustment_issuance_above_below_par` | −1 |
| 11 | `ORRNV` | Adjustments: redemptions/repurchase of debt above (+)/below (−) nominal value | `less_sfa_adjustment_redemption_above_below_nominal` | −1 |
| 12 | `ORFCD` | Adjustments: appreciation (+)/depreciation (−) of foreign currency debt | `less_sfa_adjustment_foreign_currency_debt_revaluation` | −1 |
| 13 | `ORD41A_ADJ` | Adjustments: difference between interest expenditure (D.41) accrued (−) and paid (+) | `less_sfa_adjustment_interest_accrued_less_paid` | −1 |
| 14 | `F8_ADJ_LIAB` | Adjustments: net incurrence (−) of other accounts payable | `less_sfa_adjustment_other_accounts_payable` | −1 |
| 15 | `F71_ADJ_LIAB` | Adjustments: net incurrence (−) of liabilities in financial derivatives | `less_sfa_adjustment_derivative_liabilities` | −1 |
| 16 | `FV_ADJ_LIAB` | Adjustments: net incurrence (−) of other liabilities (F.1, F.5, F.6 and F.72) | `less_sfa_adjustment_other_liabilities` | −1 |
| 17 | `KX` | Adjustments: other volume changes in financial liabilities (−) | `less_sfa_adjustment_other_volume_changes` | −1 |
| 18 | `K61` | Changes in sector classification and structure (+/−) | `less_sfa_adjustment_sector_reclassification` | −1 |
| 19 | `YA3` | Total statistical discrepancies | `less_statistical_discrepancy` | −1 |

Items 10–12 are the §8 "valuation effects" (issuance above/below par, redemption
premia, FX revaluation of the debt); item 13 is the accrual (including
index-linked principal indexation, which enters D.41 accrued and not cash); items
3–9 are the §8 "financial transactions"; items 1–2 are the §8 "net issuance of
other liabilities". The indexation of principal is **not** a separate published
line — it sits inside `ORD41A_ADJ`.

**Coverage.** `gov_10dd_edpt3` S1311 runs **FR 2021–2025** and **DE 2022–2025**;
`gov_10q_ggdebt` runs from 2000-Q4 for both, so the binding constraint is edpt3.
`gov_10dd_edpt2` (working balance → B.9) additionally covers **FR 2009–2025** but
is not used — see the DEU caveat below. Years outside coverage emit nothing.

**Residual after items** (LCU mn; carried is the chain's own step-B carried value,
official is −B.9 of S1311):

| iso3 | year | carried | Σ items | official −B.9 | residual after | residual before |
|---|---|---|---|---|---|---|
| FRA | 2021 | 144,107 | 1,209 | 144,547 | **−769** | 440 |
| FRA | 2022 | 132,690 | 2,926 | 133,247 | **−2,369** | 557 |
| FRA | 2023 | 152,162 | 2,269 | 153,819 | **−612** | 1,657 |
| FRA | 2024 | 171,664 | −15,066 | 152,464 | **−4,134** | −19,200 |
| FRA | 2025 | 135,488 | −3,817 | 130,237 | **−1,434** | −5,251 |
| DEU | 2022 | 115,442 | 49,292 | 111,159 | **−53,575** | −4,283 |
| DEU | 2023 | 27,177 | −24,379 | 92,720 | **+89,922** | 65,543 |
| DEU | 2024 | 33,320 | 19,868 | 60,916 | **+7,728** | 27,596 |
| DEU | 2025 | 66,893 | −12,581 | 79,561 | **+25,250** | 12,669 |

(2015 and 2020 are outside `gov_10dd_edpt3` coverage for both countries: no items,
residual unchanged.)

* **FRA** — carried is the register itself (step A is blocked, OQ-8), so the
  residual is now the clean "register net issuance vs Δ Maastricht debt
  securities" wedge: **−0.6 to −4.1 EUR bn**, 0.4 %–2.4 % of net borrowing, and
  smaller than the pre-item residual in three of the five years (much smaller in
  2024, where the raw gap was −19.2 bn).
* **DEU — caveat.** Carried is the **core-budget Nettokreditaufnahme** (BMF
  Kreditaufnahmebericht annex 4.10), which excludes the Sondervermögen whose debt
  *is* inside S.1311's Maastricht debt. The residual therefore now carries that
  scope difference (`ΔF3 − NKA`) on top of the register wedge, and is larger than
  the pre-item residual in 2022, 2023 and 2025. The items themselves are correct
  and self-consistent; the mismatch is between the step-A anchor and the
  debt-side identity, not inside the bridge.

  The published alternative is `gov_10dd_edpt2`, whose identity
  `B9 = ORWB + ORWB_E + B9_OB + FT + ORNF_ORWB + ORD41A_ORWB + F8_ASS_ORWB +
  F8_LIAB_ORWB + OROA_ORWB` (verified exactly for DE 2022–2025) starts from the
  **working balance**. But Germany's reported working balance also spans the
  Sondervermögen, so it does not equal the NKA either: `−ORWB − NKA` = **34,541 /
  55,809 / 13,436 / 18,470** for 2022–2025. Neither published anchor matches the
  core-budget NKA, and no official item bridges NKA → S.1311 working balance.
  The clean fix is upstream, in the chain rather than in this module: carry the
  register-side special-fund borrowing (already computed as the
  `less_sondervermoegen_*` items at step A) back in at step B, or move DEU's
  step-A official total onto an S.1311-wide cash measure.

## DEU — interest, step `B_s1311_d41`

Carried: BMF Kreditaufnahmebericht annex 4.5 "Insgesamt", Verzinsung des Bundes
(cash-like; agio/disagio booked at value date until 2024). Official total:
Eurostat `gov_10a_main` S1311 `D41PAY` (accrued).

`gov_10dd_edpt3` **does** publish an interest-accrual item for DE/S1311:
`ORD41A_ADJ`, "Adjustments: difference between interest expenditure (D.41)
accrued (−) and paid (+)" = *paid − accrued*. Hence `accrued = paid −
ORD41A_ADJ`, and one item is emitted, `d41_accrued_less_paid_adjustment`, with
sign −1. It is the only official accrued-vs-paid interest item for the subsector.

| year | carried (Kap. 3205) | item | official D41PAY | residual after | residual before |
|---|---|---|---|---|---|
| 2022 | 15,894 | −6,060 | 16,835 | **+7,001** | 941 |
| 2023 | 39,858 | +2,336 | 24,620 | **−17,574** | −15,238 |
| 2024 | 33,238 | −229 | 31,644 | **−1,365** | −1,594 |
| 2025 | 29,853 | −465 | 33,064 | **+3,676** | 3,211 |

It shrinks the residual in 2024 only. `ORD41A_ADJ` is the S.1311-wide
accrued-vs-paid wedge as it affects the *debt stock*; the carried value is the
Bund core budget's Verzinsung, which additionally books agio/disagio at value
date (the −15 bn 2023 wedge is overwhelmingly that, not accrual timing) and
excludes the Sondervermögen. The item is emitted because it is the published
official bridge for this step and D16 requires decomposition rather than closure,
but it should not be read as explaining the German interest wedge. Available
2022–2025 only.

## FRA — interest, step `B_s1311_d41`: none

Step A is blocked (`FRA_PLF_P117`, OQ-8), so there is no carried value to bridge
from and the step's residual is null by construction. `gov_10dd_edpt3` `ORD41A_ADJ`
*is* published for FR/S1311 (2021–2025) and can be emitted the moment programme
117 becomes readable.

---

## What has no official bridge at all

| gap | why |
|---|---|
| GBR interest, NLF finance costs → ONS `NMFX` | no publisher reconciles the National Loans Fund account to the national-accounts D.41 line |
| GBR interest step C, intra-GG interest consolidation | Appendix A publishes no intra-general-government D.41 flow (PSA6I `ANPZ` is a net receipt from the whole public sector, dividends included) |
| GBR interest step C, COFOG-vs-D.41 | `GF01_7` (COFOG 01.7, consolidated S.13) has no published decomposition against `NMFX + NUGW`; £122–£206 mn |
| DEU financing, NKA → S.1311 working balance / Maastricht debt | the Sondervermögen scope difference; neither `edpt2` `ORWB` nor `edpt3` `GD_CH` is anchored on the core-budget NKA |
| DEU interest, Kap. 3205 agio/disagio at value date | `ORD41A_ADJ` is accrued-vs-paid only; the value-date treatment of agio/disagio has no published counterpart |
| FRA both chains, step A | programme 117 / AFT financement unreachable (OQ-8) |
| FRA/DEU financing, pre-2021/2022 | `gov_10dd_edpt3` S1311 does not go back further in the SDMX pull |

## Tests

`tests/debt/test_bridges.py` (17 tests, all skip without snapshots):

* GBR financing step-B identity closes within £100 mn for 2010–2024, computed
  from the readers directly (`cgncr_financing()` M98R vs `cg_interest()` −NMFJ);
* the GBR step-B item set is exactly the documented nine, in order;
* GBR interest step B emits nothing; FRA interest emits nothing;
* GBR step-C items strictly reduce |residual| for 2020–2024 in both chains,
  against `package_gf01_7('GBR')` / `package_nlb('GBR')`;
* Eurostat items exist for FR and DE for the latest three published years, with
  the expected names and a finite sum;
* the sign convention is pinned by recomputing `GD_CH = B9_T3 + F_ASS + ORADJ +
  YA3` (and the `F_ASS` / `ORADJ` component sums) from the raw
  `eurostat('gov_10dd_edpt3_DE')` pull for DE 2023, then checking that
  `ΔF3 + Σ items == B9_T3` and that three sampled items are the published cell
  negated;
* DEU interest step B is `−ORD41A_ADJ`;
* every emitted item is `official`, carries a `source_id`, a `basis` naming its
  sign, a known step and a finite value.
