# Central-Government Debt Securities Register, Interest and Financing Reconciliation, Maturity Profile
## Specification v1.0 and gated build plan — extension to `COFOG_KICKOFF.md`

Prepared 9 September 2026 from `DEBT_SCOPING.md` after the committee accepted
its defaults (Q-D1–Q-D11). Self-contained for the debt extension; where it is
silent, `COFOG_KICKOFF.md` v2.2 governs (D8 snapshots, D13 prohibitions, §11.1
layers, §16 conventions). Where the two conflict on debt matters, this one
governs.

---

## 0. How to read this document

| Section | Purpose |
|---|---|
| §1–§2 | Mission and decisions taken. Build to them. |
| §3–§5 | Target concepts, instrument taxonomy, data model. |
| §6–§8 | Source hierarchy, computation methodology, reconciliation chains. |
| §9–§10 | Grading and validation. |
| §11 | Architecture and repo layout. |
| §12 | Build stages with hard gates. |
| §13 | Source register (per-entry verification status). |
| §14 | Country traps. |
| §15 | Committee questions and their resolution. |

Vocabulary as before: "committee" = AC; "agent" = the builder. "Register" =
the set of securities. "Position" = nominal outstanding of one security on
one date. "Flow" = one dated change in a position.

---

## 1. Mission

For GBR, FRA and DEU, build the register of **central-government marketable
debt securities** — every bond and bill in issue over the covered years —
with coupon, type, maturity, positions through time, the flows that changed
them, and the reference series that floating-rate and inflation-linked
securities pay on. From it, produce for every year:

1. **Interest by security**, summed by instrument class, reconciled in steps
   to the package's `GF01_7` (general-government interest, COFOG 01.7).
2. **Net securities financing** (issuance − redemptions − buy-backs ±
   conversions), reconciled in steps to the package's `NLB`.
3. **The maturity profile**: notional outstanding by instrument class in
   residual-maturity buckets 0–1, 1–2, 2–3, 3–5, 5–7, 7–10, 10–15, 15–20,
   20–30, 30+ years at each year-end; and gross issuance by the same
   buckets, measured by residual maturity at issue.

Governing principles carry over: **maximise length subject to transparency
and conceptual integrity**; **decompose, never force** — no bridge residual
is ever allocated to make a reconciliation close.

Out of scope now, but shaped for: simulating alternative yield-curve paths
through the register onto the interest line.

---

## 2. Decisions taken (DD = debt decision)

**DD1 — Perimeter is central-government marketable securities, including
bills and foreign-currency issues.** GBR: gilts (conventional, index-linked,
undated, double-dated, floating-rate) and sterling Treasury bills. FRA:
OAT (fixed, OATi, OAT€i, TEC10, green, zero-coupon where any), BTAN, BTF.
DEU: Bundesanleihen, Bundesobligationen, Bundesschatzanweisungen,
Unverzinsliche Schatzanweisungen, Bund/ei and Bobl/ei, green twins,
foreign-currency Bunds, and marketable securities of federal special funds
assumed by the Bund and listed by the Finanzagentur. Excluded from the
register and carried only as bridge lines: sub-national securities and
loans, non-marketable retail and institutional debt (NS&I, Bundesschatz-
briefe, Finanzierungsschätze, Schuldscheindarlehen, dépôts des
correspondants), loans, coin, deposits. Strips are not separate securities
(the issuer's obligation is unchanged).

**DD2 — Instrument classes are exactly five**: `fixed_bullet`, `floating`,
`inflation_linked`, `bill`, `other` (undated, callable/double-dated,
zero-coupon bonds). Sub-type carries the national name. The maturity
profile reports the committee's three classes (bullet / floating /
inflation-linked) with `bill` folded into `fixed_bullet` at 0–1 and `other`
shown separately.

**DD3 — Two interest bases are always computed**: `accrued` (day-count,
pro-rata to calendar year) and `cash` (paid on coupon and redemption
dates). Indexation uplift is interest (ESA 2010 §4.46), accrued as the
change in uplifted nominal, paid at redemption. Bill discount is interest,
accreted linearly. Premium/discount at issue is recorded per flow and
amortised straight-line as a separate `premium_discount_amortisation`
component, never netted into the coupon.

**DD4 — The interest reconciliation has three named steps.** Σ register →
(A) central-government cash interest per the finance ministry → (B) S.1311
D.41 payable per the national accounts → (C) S.13 `GF01_7`. Each step's
bridge items come from an official source or are declared; the step
residual is published. The same shape applies to financing (DD5).

**DD5 — The financing reconciliation has three named steps.** Σ register
net flows → (A) central-government net cash requirement and its financing
by instrument → (B) S.1311 net lending/borrowing via stock-flow adjustment
items → (C) S.13 `NLB`.

**DD6 — Calendar year is canonical (D3).** Positions at 31 December; flows
by settlement date. GBR carries 31 March positions and April–March flows
as memorandum columns; the GBR step-A intermediates are financial-year and
are converted per §7.10 only where a calendar-year source is absent, with
`period_conversion_method` recorded.

**DD7 — Maturity conventions.** Stock: residual maturity at the as-of
date. Issuance: residual maturity at settlement date of the issue, not the
line's original maturity. Linkers: uplifted nominal primary, unindexed
nominal alongside. Undated: 30+. Callable/double-dated: final maturity,
with the first call date carried. Bills: 0–1. Market-hands (total less
holdings by the debt office, the central bank's asset-purchase vehicle,
and the issuer's own book) reported beside total.

**DD8 — Machine-readable sources only in this phase.** Per-security history
begins where the debt office's machine-readable record begins (GBR 1981
for redeemed securities and 1998 for positions; FRA the AFT Excel era;
DEU 1995). Earlier years carry aggregates only, graded C. PDF table
extraction is a later phase requiring a committee amendment to §11.4
(Q-D7).

**DD9 — The debt office's own published indexation figures are primary.**
Index ratios (DMO), coefficients d'indexation (AFT), Index Ratios
(Finanzagentur) are the contractual, unrevised values. Statistical indices
(ONS RPI, INSEE CPI ex-tobacco, Eurostat HICP ex-tobacco) are stored and
used to recompute them as a validation, and to extend where the office's
file has gaps, graded B.

**DD10 — Reference-rate gaps are declared, not filled.** Where a floating
security's fixing history is not obtainable from an official source (GBP
LIBOR for 1990s floating-rate gilts; TEC10; Euribor/€STR while ECB and
EMMI are unreachable), its interest is `not_computable` and the shortfall
sits in the step-A residual with the affected notional stated.

**DD11 — Central-bank and official holdings are an overlay, not a
consolidation.** BoE APF holdings per ISIN (from operation results),
DMO/CRND holdings, Finanzagentur Eigenbestand, and euro-area S.121
aggregate holdings are stored; the register's positions remain total
nominal in issue.

**DD12 — Same package, same conventions.** `ggfiscal.debt` subpackage;
register entries in `config/sources.yaml`; D8 snapshots; decisions in
`DECISIONS.md`; validation IDs V29 onward; flat files in `deliverables/`;
one notebook. Grades A–D as §9 of the parent spec, applied per §9 below.

**DD13 — Prohibited**: constructing a security's terms from secondary or
commercial data; inferring a flow that no official source records except
as a position difference (which is then graded B and typed `implied`);
allocating any residual; using yield or price data to estimate interest.

---

## 3. Statistical targets

**Register.** S.1311 issuer; every ISIN (or pre-ISIN identifier) of a
security within DD1 that was outstanding at any date in the covered span.
Nominal amounts in millions of the issue currency and of the national
currency (foreign-currency issues converted at the source's own rate where
published; otherwise the year-end reference rate, `fx_source_id` recorded).

**Positions.** Nominal outstanding (unindexed), uplifted nominal
(linkers), official holdings, market-hands, at month-ends where the source
allows and at every 31 December (and 31 March for GBR).

**Flows.** Nominal and cash, by settlement date, typed per §4.3.

**Interest.** Per security-year, both bases (DD3), components: coupon,
indexation uplift, bill discount, floating coupon, premium/discount
amortisation.

**Reconciliation intermediates.** Per §8, national-currency millions,
calendar year (DD6).

**Maturity profile.** Per §1(3), at each 31 December, nominal, uplifted
and market-hands.

---

## 4. Taxonomy

### 4.1 Instrument class (DD2)
| class | definition | examples |
|---|---|---|
| `fixed_bullet` | fixed coupon, single redemption date, no option | conventional gilt, OAT, BTAN, Bund, Bobl, Schatz |
| `floating` | coupon reset to a reference rate | floating-rate gilt (1994–2001), OAT TEC10, Bund FRN |
| `inflation_linked` | principal and coupon indexed to a price index | index-linked gilt (8-month and 3-month lag), OATi, OAT€i, Bund/ei, Bobl/ei |
| `bill` | discount instrument ≤ 1 year at issue | Treasury bill, BTF, Bubill |
| `other` | undated, callable/double-dated, zero-coupon bond | War Loan, Consols, "Treasury 8% 2002–06" |

### 4.2 Reference series
| id | series | source | role |
|---|---|---|---|
| `UK_RPI` | RPI all items, Jan 1987 = 100 (`CHAW`), spliced to `CDKO` before 1987 | ONS | ILG index ratios |
| `FR_CPI_XT` | IPC ensemble des ménages, France entière, hors tabac; bases 1998 → 2015 → 2025 chained | INSEE | OATi coefficients |
| `EA_HICP_XT` | HICP euro area (changing composition) all items excluding tobacco, unrevised for contractual use | Eurostat (statistical), debt offices (contractual) | OAT€i, Bund/ei |
| `UK_SONIA`, `UK_BANK_RATE` | daily | BoE | floaters, simulation |
| `EA_MM_3M`, `EA_MM_6M` | euro-area money-market rates 1990– | Eurostat | floaters |
| `FR_IR3`, `DE_IR3`, `GB_IR3` | national 3-month rates 1960/1970/1986– | OECD | pre-EMU floaters |
| `FR_TEC10` | OAT TEC10 fixing | AFT / Banque de France | OAT TEC10 (blocked, DD10) |
| `UK_GLC_NOMINAL`, `UK_GLC_REAL`, `UK_OIS` | BoE yield curves | BoE | simulation (stored now, Q-D10) |

### 4.3 Flow types
`auction`, `syndication`, `tap`, `tender`, `conversion_in`,
`conversion_out`, `switch_in`, `switch_out`, `buyback`, `redemption`,
`retention` (DEU: portion retained in the issuer's own book at auction),
`own_book_sale`, `own_book_purchase`, `implied` (position difference with
no recorded flow, grade B).

### 4.4 Maturity buckets
`0-1, 1-2, 2-3, 3-5, 5-7, 7-10, 10-15, 15-20, 20-30, 30+` in years,
left-open/right-closed on residual maturity in days / 365.25; undated → 30+.

---

## 5. Data model

All tables long format, pandera-enforced, `run_id`, `source_id`,
`snapshot_sha256`, `quality_grade`, `notes` on every row.

### 5.1 `debt_securities` — key (iso3, security_id)
| field | type | description |
|---|---|---|
| `security_id` | str | ISIN; pre-ISIN securities `{iso3}_{office_code}` |
| `isin` | str, nullable | |
| `name` | str | as published by the office |
| `instrument_class` | enum §4.1 | |
| `sub_type` | str | national name (gilt_conventional, ilg_8m, ilg_3m, oat, oati, oatei, oat_tec10, btan, btf, bund, bobl, schatz, bubill, bund_ei, bobl_ei, green_twin, …) |
| `currency` | str | issue currency |
| `coupon_pct` | float, nullable | annual coupon; null for bills, floaters (spread in `spread_bp`) |
| `coupon_frequency` | int | payments per year |
| `day_count` | str | `ACT/ACT`, `ACT/360`, `30/360` per the office's convention |
| `first_issue_date`, `maturity_date` | date | maturity null for undated |
| `first_call_date` | date, nullable | |
| `dividend_dates` | str | e.g. `22 Apr/Oct` |
| `index_reference` | enum §4.2, nullable | |
| `index_lag_months` | int, nullable | 8 or 3 (GBR); 3 (FRA, DEU) |
| `base_index` | float, nullable | base RPI / indice de base / Basisindex |
| `floating_reference` | enum §4.2, nullable | |
| `spread_bp` | float, nullable | |
| `is_green` | bool | |
| `issuer_unit` | str | `state`, `special_fund:{name}` |

### 5.2 `debt_positions` — key (iso3, security_id, as_of)
`nominal_lcu_mn`, `nominal_uplifted_lcu_mn`, `nominal_issue_ccy_mn`,
`official_holdings_lcu_mn` (nullable), `market_hands_lcu_mn` (nullable),
`position_type` ∈ {`office_snapshot`, `office_annual`, `rolled_from_flows`},
`fx_rate`, `fx_source_id`.

### 5.3 `debt_flows` — key (iso3, security_id, settlement_date, flow_type, seq)
`flow_type` §4.3, `nominal_lcu_mn`, `cash_lcu_mn` (nullable),
`price_pct` (nullable), `yield_pct` (nullable), `method` (nullable),
`counter_security_id` (conversions/switches), `operation_date`.

### 5.4 `debt_reference_series` — key (series_id, date)
`value`, `unit`, `base_period`, `vintage_note`.

### 5.5 `debt_index_ratios` — key (iso3, security_id, date)
`reference_index`, `index_ratio`, `ratio_source` ∈ {`office`, `recomputed`}.

### 5.6 `debt_interest_by_security` — key (iso3, security_id, year, basis)
`basis` ∈ {`accrued`, `cash`}; `coupon_lcu_mn`, `uplift_lcu_mn`,
`discount_lcu_mn`, `floating_lcu_mn`, `premium_discount_amort_lcu_mn`,
`total_lcu_mn`, `computability` ∈ {`computed`, `not_computable`},
`reference_values_used` (str), `derivation` (str).

### 5.7 `debt_interest_reconciliation` — key (iso3, year, step, item)
`step` ∈ {`register`, `A_cg_cash`, `B_s1311_d41`, `C_s13_gf01_7`};
`item` (e.g. `sum_fixed_bullet`, `sum_inflation_linked`, `uplift_accrual`,
`non_marketable_interest`, `loans_interest`, `swaps`,
`premium_discount_amortisation`, `other_cg_units`, `subnational`,
`social_security`, `consolidation`, `residual`, `official_total`);
`value_lcu_mn`, `item_source_id`, `item_type` ∈ {`computed`, `official`,
`declared`, `residual`}, `basis`.

### 5.8 `debt_financing_reconciliation` — key (iso3, year, step, item)
`step` ∈ {`register`, `A_cg_cash_requirement`, `B_s1311_b9`, `C_s13_nlb`};
items: `gross_issuance`, `redemptions`, `buybacks`, `conversions_net`,
`net_securities`, `bills_net`, `non_marketable_net`, `loans_net`,
`cash_and_deposits`, `official_cg_ncr`, `sfa_financial_transactions`,
`sfa_accrual_adjustments`, `sfa_other`, `other_subsectors`, `residual`,
`official_total`.

### 5.9 `debt_maturity_profile` — key (iso3, as_of, instrument_class, bucket)
`nominal_lcu_mn`, `nominal_uplifted_lcu_mn`, `market_hands_lcu_mn`,
`n_securities`, `weighted_residual_years`.

### 5.10 `debt_issuance_by_bucket` — key (iso3, year, instrument_class, bucket)
`gross_nominal_lcu_mn`, `gross_cash_lcu_mn`, `n_operations`,
`weighted_residual_years_at_issue`.

### 5.11 `debt_official_holdings` — key (iso3, holder, security_id or `AGG`, as_of)
`holder` ∈ {`BOE_APF`, `DMO_CRND`, `FINANZAGENTUR_OWN`, `EUROSYSTEM_S121`};
`nominal_lcu_mn`, `holding_type` ∈ {`per_isin_from_operations`,
`per_isin_published`, `aggregate`}.

---

## 6. Source hierarchy

### 6.1 Register, positions, flows
1. The debt office's machine-readable reports (DMO data reports; AFT Excel;
   Finanzagentur Downloadcenter). Grade A.
2. Finance-ministry publications carrying the same items (BMF Datenportal
   instrument tree; DMR; Kreditaufnahmebericht annexes). Aggregate
   cross-checks and pre-register aggregates, grade B/C.
3. National statistical office and Eurostat/OECD debt-by-instrument and
   maturity tables. Cross-checks only.
4. Central bank operation results for holdings (BoE APF). Overlay.

### 6.2 Reference series
Contractual: the debt office (DD9). Statistical: ONS, INSEE, Eurostat,
BoE, OECD. ECB/EMMI/Banque de France/Bundesbank when reachable.

### 6.3 Reconciliation intermediates (official, never adjusted)
| step | GBR | FRA | DEU |
|---|---|---|---|
| A interest | NLF Account (cash); ONS `NMFX` and `MW7L` (accrued) | Programme 117 RAP (charge de la dette, budgétaire) | Kreditaufnahmebericht annex 4.5 (Kap. 3205); BMF Datenportal `rpgZinsen` |
| B interest | ONS PSA6B_2 CG interest (D.41) | Eurostat `gov_10a_main` S1311 D41PAY | Eurostat `gov_10a_main` S1311 D41PAY |
| C interest | package `GF01_7` | package `GF01_7` | package `GF01_7` |
| A financing | ONS Appendix S table 1.2A; `M98R`; DMR 3.A/A.2 | AFT tableau de financement; PLF article d'équilibre | Kreditaufnahmebericht annex 4.10; BMF Datenportal |
| B financing | ONS REC2 (CG net borrowing ↔ CGNCR) | Eurostat EDP tables, S1311 B9 and SFA | Eurostat EDP tables, S1311 B9 and SFA |
| C financing | package `NLB` | package `NLB` | package `NLB` |
| stock cross-check | ONS PSA8A_1 (`BKPM` gilts, `BKPJ` bills) | Eurostat `gov_10q_ggdebt` S13111 F31/F32; INSEE/AFT aggregates | BMF Datenportal `rpgSchuldenstand`; Eurostat `gov_10dd_ggd` |
| maturity cross-check | OECD T7PSD short/long | Eurostat `gov_10dd_rmd` (2020–) | Eurostat `gov_10dd_rmd` (1995–) |

### 6.4 Latest-vintage rule
As parent §6.4. Each office report is snapshotted with its close-of-business
date; a re-pull that changes a historical position is a vintage event
logged by `detect-vintages`.

---

## 7. Computation methodology

Notation: security *s*, nominal *N_s(d)* on day *d*, coupon *c_s*,
frequency *f_s*, index ratio *IR_s(d)*, uplifted *U_s(d) = N_s(d)·IR_s(d)*.

- **7.1 Daily position path.** From the latest office snapshot on or before
  *d*, roll forward by recorded flows by settlement date. Where a later
  snapshot disagrees with the rolled value, insert an `implied` flow on the
  snapshot date (grade B) and log it (V30).
- **7.2 Accrued coupon.** Actual/actual by coupon period unless the office
  convention differs: for each coupon period overlapping the year, accrual
  = *c_s/f_s · N_s(d)* integrated daily over the days in the year, with
  the first short/long period per the office's rules. Ex-dividend and
  record-date conventions affect cash, not accrual.
- **7.3 Cash coupon.** On each dividend date in the year, *c_s/f_s · N_s
  (record date)* — for linkers multiplied by *IR_s(payment date)*; for
  ILG 8-month lag, the published coupon per £100 (DMO `D5I`) is primary.
- **7.4 Indexation uplift.** Accrued: *U_s(31 Dec) − U_s(1 Jan) −
  IR-weighted net flows*. Cash: paid at redemption, *(IR_s(maturity) − 1)·
  N_s* in the redemption year.
- **7.5 Bills.** Discount = issue cash − nominal, accreted linearly from
  settlement to maturity (accrued); cash at maturity.
- **7.6 Floaters.** Coupon per period = (reference fixing + spread)/f_s ·
  N_s per the security's terms (TEC10: previous-quarter fixing; FRG:
  3-month LIBID; Bund FRN: as published). Missing fixings → DD10.
- **7.7 Premium/discount.** Per issuance flow, *(price − 100)/100 · nominal*,
  amortised straight-line to maturity, as a separate component (DD3).
- **7.8 Residual maturity.** *(maturity − as_of)/365.25*; issuance uses
  settlement date as `as_of`.
- **7.9 Foreign-currency issues.** Converted per §3; interest converted at
  the average rate of the year (`fx_source_id`).
- **7.10 GBR period conversion.** Parent §7.10 where a calendar-year
  intermediate is unavailable; recorded per row.

---

## 8. Reconciliation chains (DD4, DD5)

For each country and year the tables in §5.7–5.8 hold, per step, the
computed sum, every official or declared bridge item, the official total,
and `residual = official_total − (computed + Σ bridge items)`.

**Interest, step A** (register → CG cash interest): items `uplift_timing`
(accrued − cash uplift where the intermediate is cash), `bills`,
`non_marketable_interest` (NS&I from ONS; Bundesschatzbriefe etc. from BMF
Datenportal; correspondants from programme 117), `loans_and_other`, `swaps`
(FRA, DEU: from the office/ministry where published), `premium_discount`
(where the intermediate books it at value date), residual.

**Interest, step B** (CG cash → S.1311 D.41): items `accrual_timing`,
`premium_discount_amortisation` (ESA), `uplift_accrual`, `other_cg_units`
(ODAC; extra budgets/FMS), `consolidation_within_cg`, residual.

**Interest, step C** (S.1311 → S.13 `GF01_7`): `state_and_local`,
`social_security`, `consolidation_intra_gg`, `cofog_vs_d41` (V21 wedge),
residual.

**Financing, step A** (register net flows → CG net cash requirement):
`bills_net`, `non_marketable_net`, `loans_net`, `cash_and_deposits`,
`official_holdings_change` (Eigenbestand; DMO), `premium_discount_cash`,
residual; official total = CGNCR / besoin de financement / NKA.

**Financing, step B** (CG cash requirement → S.1311 B.9): stock-flow
adjustment components as published (financial transactions: loans, equity,
student loans; accrual adjustments; other), residual.

**Financing, step C** (S.1311 → S.13 `NLB`): `state_and_local_b9`,
`social_security_b9`, residual.

The notebook shows each chain as a waterfall per year.

---

## 9. Grading

| Grade | Register/positions/flows | Interest | Bridge items |
|---|---|---|---|
| A | office record | computed from A terms and office index ratios | official published item |
| B | position difference (`implied`); ministry aggregate matching the class; recomputed index ratio | computed with a B input | official item on a nearby concept, documented |
| C | aggregate-only year, pre-register | class-level only | — |
| D | not published | `not_computable` | declared, no source |

Residuals are not graded.

---

## 10. Validation (continues parent §10)

| ID | Test | Sev |
|---|---|---|
| V29 | Every position and flow references a security in the register; every security has ≥1 position | ERROR |
| V30 | Position recurrence per security: snapshot(t) = snapshot(t−1) + Σ flows, tolerance 0.5 mn or 0.01%; violations become `implied` flows and are listed | WARN |
| V31 | Σ positions by class at 31 Dec vs official stock by instrument (§6.3), tolerance per country config | WARN |
| V32 | Each reconciliation step: `official_total − computed − Σ items = residual` exactly; residual reported for every (iso3, year, step) | ERROR |
| V33 | Bucket sums equal class totals; bucket ∈ §4.4; undated in 30+ | ERROR |
| V34 | Recomputed index ratio vs office ratio within 0.01% where both exist | WARN |
| V35 | `GF01_7` and `NLB` used at step C are the package's canonical values, same run | ERROR |
| V36 | No `not_computable` security lacks a DD10 declaration; affected notional reported | ERROR |
| V37 | Every snapshot has close-of-business date, source, sha256; every derived row names its inputs | ERROR |
| V38 | Maturity profile vs Eurostat `gov_10dd_rmd` / OECD where available: reported | WARN |
| V39 | Interest by class vs ministry interest by instrument (BMF; programme 117; DMR) where published: reported | WARN |
| V40 | Year-end market-hands ≤ total; holdings overlay never exceeds nominal in issue | ERROR |

---

## 11. Architecture

```
config/debt.yaml                 perimeter, taxonomy map per office code, buckets,
                                 reconciliation chain items and their sources, tolerances
config/sources.yaml              new register entries (§13)
src/ggfiscal/debt/
  endpoints.py                   Pull definitions per family (BoE, ONS, HMT, BMF,
                                 Eurostat gov_10dd/prc_hicp, INSEE, OECD; DMO/AFT/
                                 Finanzagentur when reachable)
  readers/                       one module per family → tidy frames
  register.py                    securities, positions, flows → canonical
  reference.py                   reference series, index ratios
  interest.py                    §7
  financing.py                   flows → §5.8 step register
  maturity.py                    §5.9–5.10
  reconcile.py                   §8 chains
  validate.py                    V29–V40
  flatten.py                     deliverables/debt_*.csv, dictionary rows, strict_* columns
tests/debt/
notebooks/debtbook.ipynb
```

CLI: `ggfiscal debt fetch | build | validate | flatten`; `ggfiscal report`
and `ggfiscal flatten` include the debt bundle; `detect-vintages` covers the
new register entries.

---

## 12. Build stages and gates

**Stage D0 — Register and harvest (reachable sources).** Register entries;
`debt fetch` for BoE, ONS, HMT, BMF, Eurostat, INSEE, OECD; snapshot every
pull; reachability report for the blocked hosts. **Gate D0:** every
reachable §13 entry snapshotted; `reports/debt_source_verification.md`.

**Stage D1 — Reference series and official intermediates.** All §4.2
reachable series and all §6.3 reachable intermediates standardised;
cross-checked against the package's `GF01_7`/`NLB`. **Gate D1:** step
B and C official totals present for every year they exist; RPI/CPI/HICP
chained without gaps.

**Stage D2 — Register, positions, flows.** Per country as data allows
(DEU first: one file; GBR when DMO opens or files arrive; FRA likewise).
V29–V31. **Gate D2:** Σ positions reproduces official stock within
tolerance at every year-end covered.

**Stage D3 — Interest and the interest chain.** §7, §8 interest. V32,
V34–V36, V39. **Gate D3:** every step residual tabulated; DD10
declarations complete.

**Stage D4 — Financing chain, maturity profile, issuance buckets.** V33,
V38, V40. **Gate D4:** bucket tables reproduce the register; chain
additivity exact.

**Stage D5 — Packaging.** Flatten, dictionary, notebook, README, vintage
detection, HANDOFF. **Gate D5:** every flat value reproducible from the
bundle and the notebook; `tests/debt` green.

---

## 13. Source register seed (status as of 2026-09-09)

| source_id | institution | object | reachable |
|---|---|---|---|
| UK_DMO_GILTS | DMO | D1A, D1C, D1D, D2.1E, D2.1A, D2.1PROF7, D10A, D2.1PROF9, D4L, D8B, D5I, D10C, D9C; D1A by COBDate; gross/net issuance page; conventions PDFs | no |
| UK_DMO_BILLS | DMO | D2.2A/D/E/G | no |
| BOE_APF | BoE | APF gilt purchases (2009–), sales (2022–), FS purchases/sales (2022), maturity profile | yes |
| BOE_YIELD_CURVES | BoE | nominal, real, inflation, OIS daily and month-end archives | yes |
| BOE_IADB | BoE | IUDSOIA, IUDBEDR, gilt holdings by sector; baserate.xls | yes |
| ONS_PSF_APPENDIX_A | ONS | PSA tables 1–10 (PSA8A_1, PSA6B_2, REC2, REC3, PSA9A/B) | yes |
| ONS_PSF_APPENDIX_S | ONS | CGNCR financing by instrument, table 1.2A | yes |
| ONS_PSF_TIMESERIES | ONS | BKPM, BKPJ, NMFX, MW7L, M98R, ANTA, L6BD, ANSK | yes |
| ONS_RPI | ONS | CHAW, CDKO | yes |
| HMT_DMR | HM Treasury | Debt Management Report 2023-24 → 2026-27 (financing arithmetic) | yes |
| HMT_NLF | HM Treasury | National Loans Fund Account 2005-06 →; combined CF/NLF 1996-97 → | yes (PDF) |
| FRA_AFT_ENCOURS | AFT | encours détaillé OAT/BTF/OAT€i (xlsx) | no |
| FRA_AFT_ADJUDICATIONS | AFT | hist_btf.xlsx, OAT history, monthly recaps | no |
| FRA_AFT_INDEXATION | AFT | OATi and OAT€i coefficients, current and historical | no |
| FRA_AFT_FINANCEMENT | AFT | tableau de financement, rapport d'activité | no |
| FRA_PLF_P117 | DB / budget.gouv.fr | programme 117 RAP | no |
| INSEE_IPC | INSEE | 001763852 (base 2015), 011814056 (base 2025) via serie/ajax | yes |
| INSEE_AFT_AGG | INSEE | dette négociable aggregates 001711531–3, 001719708–10, 001738853–62 | yes |
| DEU_FINANZAGENTUR | Finanzagentur | Einzelaufstellung seit 1995, monthly Umlauf, Emissionshistorie, Emissionskalender, index ratios base 2015 and 2025 | no |
| BMF_DATENPORTAL | BMF | Kreditbestand/Bruttokreditaufnahme/Tilgungen/Zinsen xlsx (monthly 1996–), sibling CSVs | yes (bot manager) |
| BMF_KREDITAUFNAHMEBERICHT | BMF | annual PDF 2013 → 2025 | yes |
| BMF_MONATSBERICHT | BMF | monthly Kreditaufnahme tables incl. Eigenbestand flows | yes |
| BMF_HAUSHALTSRECHNUNG | BMF | Epl. 32 outturn 1998 → | yes (PDF) |
| EUROSTAT_GOV10A_MAIN_S1311 | Eurostat | D41PAY, B9 by subsector | yes |
| EUROSTAT_GOV10DD | Eurostat | gov_10dd_ggd, gov_10dd_rmd, gov_10dd_edpt1/2/3, gov_10dd_dcur, gov_10q_ggdebt | yes |
| EUROSTAT_PRC_HICP | Eurostat | prc_hicp_minr TOT_X_TBC I25 EA (and FR, DE); prc_hicp_midx I15 archive | yes |
| EUROSTAT_IRT | Eurostat | irt_st_m EA M3/M6; irt_lt_mcby_m FR/DE/EA | yes |
| OECD_T7PSD | OECD | quarterly public-sector debt by instrument and maturity, S1311 and S13 | yes |
| OECD_FINMARK | OECD | IR3TIB, IRLT for FRA/DEU/GBR | yes |
| ECB_FM, EMMI | ECB / EMMI | €STR, Euribor | no |
| BDF_WEBSTAT | Banque de France | SC1 securities series; TEC10 | no |
| BBK | Bundesbank | Kapitalmarktstatistik; yields; Umlauf | no |

---

## 14. Country traps

**GBR.** Coupon is not a field in `D1A`; parse from the name (vulgar
fractions). Two indexation regimes (8-month lag, whole-month RPI, no
interpolation; 3-month lag, daily interpolation, 5 dp rounding) — use
`igcalc.pdf`. Base RPIs of pre-1987 ILGs are on the Jan-1987 base but RPI
before 1987 lives in `CDKO` (Jan 1974 = 100): rescale. Double-dated and
undated gilts redeemed 2014–15. Floating-rate gilts 1994–2001 paid 3-month
LIBID: no official fixing series reachable (DD10). Financial-year sources
everywhere at step A; `M98R` excludes NRAM/B&B/Network Rail. APF gilts are
outside general government: full coupons count in `GF01_7`; APF income
returns via `L6BD`. Premia on 2020–21 reopenings are large (`LSIW`).

**FRA.** BTAN discontinued 2013 (2y/5y issued as OAT). OATi reference is
France entière CPI ex-tobacco; OAT€i is euro-area HICP ex-tobacco; both
rebased 2026-03-02. Coefficients published by AFT with base 1998/2005
historical files. Buy-backs have no standalone file: derive from monthly
recaps or position differences. Programme 117 books indexation charge
annually (closer to accrual) and excludes swaps (programme "swaps" line
separate). S.1311 includes ODAC (CADES, etc.): CADES debt is not État debt
but is S.1311 — expect a material step-B item on both chains.

**DEU.** Retention at auction (Marktpflegequote ≈ 20%) means allotted ≠
issued: positions are gross of Eigenbestand; market-hands = gross −
Eigenbestand. Green twins are separate ISINs with identical terms. From
2025 the Bund spreads agio/disagio: BMF stock series no longer equals
stock + gross − redemptions (annex 4.10 shows the derivation). Special
funds (Treuhand MTNs, Entschädigungsfonds, Fonds Deutsche Einheit) sit in
the BMF instrument tree; include those the Finanzagentur lists. Kap. 3205
interest is net of interest income and excludes swaps and cash management.
Länder debt is out of register (DD1) and is the dominant step-C item.

---

## 15. Committee questions and resolution

All Q-D1–Q-D11 resolved on the `DEBT_SCOPING.md` defaults, 2026-09-09.
Standing items: **Q-D1 access** — hosts to allowlist: `www.dmo.gov.uk`,
`www.aft.gouv.fr`, `www.deutsche-finanzagentur.de`; recommended also
`www.bundesbank.de`, `api.statistiken.bundesbank.de`,
`webstat.banque-france.fr`, `data-api.ecb.europa.eu`, `www.budget.gouv.fr`,
`www.performance-publique.budget.gouv.fr`, `bdm.insee.fr`. Until then,
D2–D4 proceed on DEU aggregates and whatever files arrive via
`ggfiscal ingest-file`. **Q-D7** PDF extraction: later phase, needs a §11.4
amendment.
