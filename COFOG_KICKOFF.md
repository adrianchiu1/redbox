# Long-Horizon General-Government Expenditure by Function, Revenue by Type, and WEO Reconciliation
## Claude Code kickoff package — specification v2.2 and gated build plan

Prepared 31 August 2026. Self-contained. Supersedes v1 (ChatGPT specification), v2.0 and v2.1 of this package. Where documents conflict, this one governs.

v2.2 changes: scope reduced to **GBR, FRA, DEU**; a **revenue-by-type tree** on the same engine; a **reconciliation module** relating the granular series to IMF WEO fiscal aggregates; interest receivable separated on the revenue side to mirror `GF01_7`.

---

## 0. How to read this document

| Section | Purpose |
|---|---|
| §1–§2 | Mission and design decisions already taken. Build to them. If you find one is wrong, stop, write it up in `OPEN_QUESTIONS.md`, and continue on the parts that do not depend on it. |
| §3–§5 | Target concepts, line codes, data model. |
| §6–§8 | Source hierarchy, stitching methodology, reconciliation methodology. |
| §9–§10 | Grading and validation. |
| §11 | Architecture, repo layout, stack. |
| §12 | Build stages with hard acceptance gates. Do not start stage N+1 until gate N passes. |
| §13 | Seed source register (unverified — Stage 0 verifies it). |
| §14 | Country traps. |
| §15 | Questions reserved for the committee (AC). Do not resolve these yourself. |
| §16 | Working conventions and model allocation. |

Vocabulary: "committee" = the human owner (AC). "Agent" = you.

---

## 1. Mission

Build a reproducible pipeline producing, for the United Kingdom (`GBR`), France (`FRA`) and Germany (`DEU`):

1. **Expenditure by function**: consolidated general-government total expenditure by COFOG Level I (`GF01`–`GF10`), plus `GF01_7` (public debt transactions — interest) and `GF01_X` (GF01 excluding GF01_7). Twelve lines per country.
2. **Revenue by type**: consolidated general-government total revenue by ESA 2010 economic category, ten lines per country (`R01`–`R10`, §4.2), with VAT, household income tax, corporate income tax and interest receivable each separated.
3. **Fiscal balance ledger and reconciliation**: total revenue (`TR`), total expenditure (`TE`), net lending/borrowing (`NLB = TR − TE`), and a reconciliation of their history and forecast dynamics to the IMF World Economic Outlook general-government aggregates.

Each line series is extended (a) backwards as far as compatible official history permits and (b) forwards as far as official projections permit — 66 line series in total, plus three balance ledgers.

Governing principle: **maximise length subject to transparency and conceptual integrity.** A shorter series with a documented endpoint beats a longer one built by disguising a demographic projection, budget target, partial-programme forecast or private extrapolation as an official forecast.

Reconciliation principle: **decompose, never force.** The pipeline never scales or adjusts a line to hit a WEO aggregate. It explains the difference.

---

## 2. Decisions taken

**D1 — Anchor is the national statistical source, parameterised per country. IMF GFS is a reconciliation test, not the level anchor.**

| Country | Expenditure anchor | Revenue anchor | Basis |
|---|---|---|---|
| GBR | ONS ESA Table 11 (GG expenditure by function, Level I and II) | ONS public sector finances / ESA tables, GG receipts by ESA code | Calendar year |
| FRA | Eurostat `gov_10a_exp` (INSEE-sourced), Level I and II | Eurostat `gov_10a_main` + `gov_10a_taxag` (INSEE-sourced) | Calendar year |
| DEU | Eurostat `gov_10a_exp` (Destatis-sourced), Level I and II | Eurostat `gov_10a_main` + `gov_10a_taxag` (Destatis-sourced) | Calendar year |

`anchor_source` is a per-country, per-tree config field. Every observation carries `imf_value` / `imf_diff_pct` where IMF GFS has the cell; validation V1 tests the reconciliation with tolerance. Eurostat no longer carries UK government-finance data; GBR runs entirely off ONS.

**D2 — The residual assumption in proxy extensions is explicit.** Applying a component's growth to a total is arithmetically identical to holding the uncovered residual at a constant share of that total. Every proxy or composite observation records `residual_method` ∈ {`grow_with_proxy`, `constant_pct_gdp`, `frozen_nominal`}. Default `grow_with_proxy`.

**D3 — Canonical period basis is calendar year for all three countries.** The only fiscal-year sources are UK forecast sources (OBR, HMT, defence plans, Apr–Mar). Convert them per §7.10 *before* computing growth.

**D4 — General-government total-expenditure and total-revenue envelopes are first-class sources.** Historical: the anchor's own TE and TR. Forecast: registered official GG paths — AMECO (all three), OBR (GBR), Commission DSM (FRA, DEU) — latest vintage wins. WEO aggregates are registered as sources for the reconciliation module (§8) but are **not** used as envelopes for extension, so that the reconciliation remains independent.

**D5 — Two published variants only:** `strict` and `maximum_extension`.

**D6 — Historical extensions are graded and perimeter-documented exactly like forecasts.**

**D7 — Lines with no identified forecast source are declared "no official forecast" at the outset.** Seed register: expenditure GF03, GF04, GF05, GF06, GF08, `GF01_X` in all three; revenue R05 (other taxes) partial, R08 (other property income), R10 (other transfers) and the imputed component of R06 in all three. Strict and maximum end at the last actual with a one-line note recording what was searched.

**D8 — Every raw pull is an immutable, content-hashed snapshot.** The build manifest records the hash used for every source.

**D9 — Hand-keyed PDF tables follow the manual-ingest protocol (§11.4).**

**D10 — Interest is separated on both sides, gross, and these are the only sub-Level I lines.**
- `GF01_7` = COFOG 01.7 from the anchor's Level II table; where a year lacks Level II, use GG gross interest payable (D.41) from the same institution's non-financial accounts, `observation_type = level2_proxy_actual`, grade B.
- `R07` = GG interest receivable (D.41 resources), from the anchor's revenue table.
- `GF01_X = GF01 − GF01_7` in every year where both exist; never forecast.
- Forecast concept for `GF01_7`: gross accrued interest payable. OBR publishes gross and net; AMECO and the DSM publish ESA gross interest (GG). Net-only sources are graded no better than B where receipts are small, C where material.
- Net interest `NI = GF01_7 − R07` is a derived ledger quantity used in §8.

**D11 — Benchmark interpolation.** % of GDP sources: interpolate the ratio linearly, multiply by the annual nominal GDP path. Nominal sources: constant compound growth. Record `interpolation_method` ∈ {`ratio_linear`, `level_compound`}.

**D12 — Short-term/long-term chaining.** Use short-term growth through the short-term horizon, long-term growth only beyond it. Report overlap divergence (V16); above threshold, flag for committee review rather than auto-joining.

**D13 — Prohibited methods:** no ARIMA or private statistical forecasts; no consensus or commercial forecasts; no analyst judgement entered as growth or elasticity; no constant-share or constant-real-per-capita extrapolation except as an explicit `residual_method` under D2 or where the official source itself assumes it; no unidentified chart-read data; no silent filling; no central-government or public-sector series presented as general government without a documented adjustment; no caseload, beneficiary or enrolment forecast presented as expenditure; no tax base or elasticity applied to a macro path to manufacture a revenue forecast; **no scaling of any line to a WEO aggregate.**

**D14 — Volume series are out of scope** unless an official deflator or official real series exists.

**D15 — Revenue tree.** Ten ESA-economic lines per §4.2, summing to ESA total revenue (TR) by identity. OECD Revenue Statistics is the backward-extension source for the tax lines (from 1965), chain-linked with a versioned crosswalk and graded B/C for concept differences (cash timing, payable tax credits, EU own-resources treatment).

**D16 — Reconciliation is a first-difference decomposition on a common denominator (§8).** A base-year level bridge is computed once per vintage pair; all forecast-period reconciliation is expressed as changes from the base year, in pp of WEO nominal GDP, with the denominator effect reported as its own line. Residuals are split into coverage and source-disagreement components wherever an independent official total permits.

**D17 — Payable tax credits follow the anchor's ESA treatment** (gross: the credit is expenditure, the tax is unreduced). OECD Revenue Statistics and some forecast sources report net; the crosswalk records the adjustment and the affected lines (R03 chiefly) carry a concept note.

---

## 3. Statistical targets

**Expenditure.** Sector S13 consolidated; ESA 2010 total expenditure (TE) — current expenditure plus gross capital formation, capital transfers and net acquisitions of non-produced assets; excludes consumption of fixed capital. COFOG Level I plus D10 lines. Annual, calendar year, current-price national currency, millions.

**Revenue.** Sector S13 consolidated; ESA 2010 total revenue (TR) = P.11 + P.12 + P.131 + D.2 + D.39 + D.4 + D.5 + D.61 + D.7 + D.91 + D.92 + D.99 (resources). Lines per §4.2. Same frequency, basis, unit.

**Balance.** `NLB = TR − TE` = ESA B.9 net lending (+) / net borrowing (−). `NI = GF01_7 − R07`. `PB = NLB + NI` (primary balance).

Derived measures per observation: `pct_gdp`, `pct_total` (of TE or TR as appropriate).

---

## 4. Line codes

### 4.1 Expenditure (`classification = COFOG`)
| Code | Level | Label |
|---|---|---|
| GF01 | 1 | General public services |
| GF01_7 | 2 | Public debt transactions (interest) |
| GF01_X | derived | General public services excluding interest |
| GF02 | 1 | Defence |
| GF03 | 1 | Public order and safety |
| GF04 | 1 | Economic affairs |
| GF05 | 1 | Environmental protection |
| GF06 | 1 | Housing and community amenities |
| GF07 | 1 | Health |
| GF08 | 1 | Recreation, culture and religion |
| GF09 | 1 | Education |
| GF10 | 1 | Social protection |
| TE | total | Total expenditure |

### 4.2 Revenue (`classification = ESA_REV`)
| Code | ESA | Label | Eurostat / ONS reference (verify) |
|---|---|---|---|
| R01 | D.211 | Value added tax | `gov_10a_taxag` D211 |
| R02 | D.2 − D.211 | Other taxes on production and imports (excises, duties, other product and production taxes) | D2 minus D211 |
| R03 | D.51 (households) | Taxes on household income (incl. holding gains) | `gov_10a_taxag` D51A_C1 |
| R04 | D.51 (corporations) | Taxes on corporate income (incl. holding gains) | D51B_C2 |
| R05 | D.51 other + D.59 + D.91 | Other current taxes and capital taxes | residual of D.5 plus D91 |
| R06 | D.61 | Net social contributions (actual employers', actual households', imputed, supplements) | `gov_10a_main` D61 |
| R07 | D.41 (resources) | Interest receivable | `gov_10a_main` D41 (resources) |
| R08 | D.4 − D.41 | Other property income (dividends, rent, reinvested earnings) | D4 minus D41 |
| R09 | P.11 + P.12 + P.131 | Sales of goods and services | `gov_10a_main` P11_P12_P131 |
| R10 | D.39 + D.7 + D.92 + D.99 | Other current and capital transfers receivable (incl. EU flows) | residual |
| TR | total | Total revenue | `gov_10a_main` TR |

Identity: `R01 + … + R10 = TR` exactly in anchor years (V22). For GBR, build the same lines from ONS ESA-basis receipts; the household/corporate split of D.51 comes from ONS income tax + NICs treatment (NICs are D.61) and corporation tax lines — document the mapping in the crosswalk.

### 4.3 Balance ledger (`classification = BALANCE`)
`TR`, `TE`, `NLB`, `NI`, `PB` — derived, never stitched. Populated in every year where both sides exist for the given variant (in forecasts, only where every line on both sides has a value; see §8.3 for the covered-sum alternative).

---

## 5. Data model

Long format, one row per (`iso3`, `classification`, `line_code`, `year`, `series_variant`).

| Field | Type | Description |
|---|---|---|
| `series_id` | str | `{iso3}_{line_code}_{series_variant}` |
| `iso3` | str | GBR, FRA, DEU |
| `classification` | str | `COFOG`, `ESA_REV`, `BALANCE` |
| `line_code` | str | Per §4 |
| `line_level` | str | `1`, `2`, `derived`, `total` |
| `line_label` | str | |
| `year` | int | Calendar year |
| `native_period` | str | Source period before conversion |
| `source_period_basis` | str | `CY` or `FY` |
| `value_lcu_mn` | float | Millions LCU |
| `currency` | str | GBP, EUR |
| `gdp_lcu_mn` / `gdp_source_id` | float / str | Denominator and its source |
| `pct_gdp` | float | |
| `total_lcu_mn` / `total_source_id` | float / str | TE or TR used for the share |
| `pct_total` | float | |
| `series_variant` | str | `strict` / `maximum_extension` |
| `observation_type` | str | `anchor_actual`, `level2_proxy_actual`, `derived_actual`, `imf_actual`, `stitched_actual`, `direct_forecast`, `composite_forecast`, `proxy_forecast`, `official_benchmark_interpolation` |
| `anchor_source`, `anchor_year`, `anchor_value` | | Stitch provenance |
| `growth_source_id`, `growth_rate` | | Growth applied |
| `residual_method` | str | D2 |
| `interpolation_method` | str | D11 |
| `period_conversion_method` | str | §7.10 |
| `coverage_share`, `coverage_share_year` | float / int | §9.2 |
| `quality_grade` | str | A–D |
| `crosswalk_version` | str | |
| `source_id`, `source_release_date`, `source_vintage`, `source_status`, `scenario_label` | | Register link |
| `concept_flag` | str | e.g. `d41_gross_accrued`, `net_interest`, `tax_credits_net`, `public_sector_perimeter` |
| `imf_value`, `imf_diff_pct` | float | IMF GFS reconciliation |
| `oecd_rs_value`, `oecd_rs_diff_pct` | float | Revenue lines: OECD Revenue Statistics reconciliation |
| `is_interpolated`, `is_period_converted`, `is_forecast` | bool | |
| `run_id` | str | |
| `notes` | str | |

Schema enforced with `pandera`.

---

## 6. Source hierarchy

### 6.1 Historical
1. Anchor per D1 (Level II / ESA sub-items from the same source).
2. Other redistributions of the same national data (IMF GFS, OECD Table 11, OECD National Accounts) — reconciliation and gap-filling.
3. OECD Revenue Statistics (tax lines) and GG D.41 series (interest lines) for backward extension.
4. Earlier official national series mappable via a versioned crosswalk.
5. Archived official vintages where the current publication drops history.

Anchor values are unchanged in years the anchor covers. Others extend; they do not replace.

### 6.2 Forecast
1. Direct GG forecast of the line (ESA basis).
2. Official projection closely matching the line.
3. Complete composite of official sub-item forecasts.
4. Official forecast of a dominant component — `maximum_extension` only.
5. Legislated multi-year plan.
6. Official target with enough information to derive a path.

"Official": statistical agencies; independent fiscal institutions (OBR, HCFP, Beirat/Steuerschätzung); statutory actuarial bodies (COR, DRV/BMAS); European Commission; IMF, OECD.

### 6.3 Envelopes, denominators, reconciliation sources
- Historical GDP: anchor's own national-accounts GDP, same vintage.
- Forecast GDP: same-source where the line forecast is in % GDP; otherwise the registered national macro forecast.
- Envelopes (extension): AMECO TR/TE; OBR (GBR); DSM (FRA, DEU).
- Reconciliation (never extension): IMF WEO `GGR`, `GGX`, `GGXCNL`, `GGXONLB`, `NGDP` in LCU and % GDP; WEO vintage recorded.

### 6.4 Latest-vintage rule
Record per source: title, institution, release date, vintage/cut-off, retrieval date, URL, snapshot hash, forecast base year, end year, `supersedes`, `scenario_label`, `concept_note`. Latest official release wins in overlapping years; still-current long-term publications may extend beyond newer short-term ones (D12); superseded sources are not used beyond the newer horizon; baseline/current-policy scenario preferred; alternatives preserved, never averaged.

---

## 7. Stitching methodology

Notation: `A_t` anchor; `T` last anchor year; `F` first anchor year; `X_t` extension source on calendar-year basis; `Y_t` output.

- **7.1 Anchor years:** `Y_t = A_t`, `t ∈ [F, T]`.
- **7.2 Forward:** `Y_t = Y_{t-1} × X_t / X_{t-1}`, `t > T`. Growth, never level. Newer national actuals first, then forecast growth.
- **7.3 Backward:** `Y_t = Y_{t+1} × X_t / X_{t+1}`, `t < F`.
- **7.4 Multiple stitches:** sequential; each boundary logged (year, outgoing, incoming, anchor value, growth, scope, break flag).
- **7.5 % of GDP forecasts:** same-source nominal GDP → implied nominal → growth → apply. Ageing Report nominal GDP is constructed from its real-growth and deflator assumptions; `gdp_source_id = {source_id}_constructed`.
- **7.6 Benchmark years:** D11; denominator interpolated the same way.
- **7.7 Short/long-term chaining:** D12.
- **7.8 Composites and proxies:** composite strict-eligible if `coverage_share ≥ 0.90`, weights = component nominal levels in the overlap year, residual per `residual_method`; single-component proxy is `maximum_extension` only. Every such row records components, coverage, perimeter mismatch, residual method, grade, and the note "constructed, not an official forecast".
- **7.9 Interest and derived lines:** `GF01_7` and `R07` are extended like direct forecasts. `GF01_X` is derived only. `GF01` total in `maximum_extension` is extended via `GF01_7` growth with explicit `residual_method`; in `strict` it ends at the last actual. Never construct interest from a debt path × rate assumption.
- **7.10 Period conversion (GBR forecast sources only):** `CY_t = 0.25 × FY_{t-1/t} + 0.75 × FY_{t/t+1}`. Convert the source before computing growth. Conversion consumes one horizon year; record it.
- **7.11 Revenue-specific:** OECD RS backward extension uses growth of the matching OECD tax heading; crosswalk carries the payable-tax-credit adjustment (D17) and the EU own-resources treatment (VAT- and GNI-based contributions are D.7 payable to the EU in ESA, not revenue reductions). Steuerschätzung is cash Finanzstatistik; bridge to ESA via the Destatis/Bundesbank reconciliation tables — use growth only. OBR "current receipts" are public sector (includes public corporations' gross operating surplus, absent from GG TR) — measure `coverage_share` on the GG anchor.
- **7.12 Missing and non-positive values:** no growth across missing, zero, negative, or flagged breaks. Leave missing; log.
- **7.13 Accrual vs cash:** forecast sources are mostly cash/budgetary; anchors are accrual ESA. Record `concept_note`; material cases are defence (delivery timing), interest (accrual, index-linked uplift), corporation tax (time-adjusted cash vs accrued).

---

## 8. Reconciliation methodology (WEO)

Purpose: (1) establish whether the history of the WEO GG balance matches the anchor `TR − TE` and expose what drove its dynamics line by line; (2) express each WEO forecast path in terms of what the granular official forecasts explain and what they do not. Never force agreement (D13, D16).

### 8.1 Inputs
- Anchor and stitched lines (both variants).
- WEO vintage `w`: `GGR`, `GGX`, `GGXCNL`, `GGXONLB`, `NGDP` (LCU levels; % GDP recomputed, not taken from WEO).
- Independent official totals `TR_off`, `TE_off` per country (AMECO; OBR for GBR; DSM for FRA/DEU), with their own GDP paths.
- Base year `b` = last year in which WEO reports an actual and the anchor has an observation, per (country, vintage).

### 8.2 Base-year level bridge (once per (country, WEO vintage))
For `t ≤ b`, in LCU:
- `gap_TR_t = TR_anchor,t − GGR_w,t`; `gap_TE_t = TE_anchor,t − GGX_w,t`; `gap_NLB_t = NLB_anchor,t − GGXCNL_w,t`.
- `NI_weo,t = GGXONLB_w,t − GGXCNL_w,t` (primary minus overall = net interest paid); `NI_ours,t = GF01_7,t − R07,t`; `gap_NI_t`.
- `gap_GDP_t = GDP_anchor,t − NGDP_w,t`.
Classify each gap: `revision` (anchor vintage newer than WEO cut-off), `perimeter` (persistent, documented — expected non-zero for GBR only), `unexplained`. Test V24: for FRA and DEU the level gaps should be within tolerance in all overlap years; for GBR the perimeter component must be stable.

### 8.3 Dynamics decomposition (history and forecast, both variants)
All ratios use a **single** GDP path per (country, vintage): WEO `NGDP_w` for `t ≥ b` and anchor GDP for `t < b`, chained at `b`.

Define `r_i,t = V_i,t / GDP_t × 100` for every line `i`.

*History (`t ≤ b`):* contribution of line `i` to the change in the balance ratio, `c_i,t = ± (r_i,t − r_i,t−1)`, sign + for revenue lines, − for expenditure lines. By identity `Σ_i c_i,t = Δ(NLB/GDP)_t` (V26). Output one table: year × line, plus the WEO `Δ(GGXCNL/NGDP)` for comparison. This is the "drivers of the change in the deficit" decomposition and answers question (1) at line level.

*Forecast (`h > b`):* for each horizon year, the WEO change from base `ΔB_w,h = (GGXCNL_w,h − GGXCNL_w,b) / NGDP_w,h`-style ratio difference, i.e. `r_B,h − r_B,b`. Decompose:

```
ΔB_w,h = Σ_{i ∈ covered rev} (r_i,h − r_i,b)  −  Σ_{j ∈ covered exp} (r_j,h − r_j,b)
       + resid_coverage_h + resid_disagreement_h + denom_effect_h
```

where "covered" means the line has a forecast value in the given variant, and:
- `denom_effect_h` = Σ over covered lines of the difference between contributions computed with the national source's own GDP path and with `NGDP_w`. Reported, never absorbed.
- Where an independent official total exists for a side: `resid_coverage,side,h = (T_off,h/GDP_h − T_off,b/GDP_b) − Σ_{covered on that side}(r_i,h − r_i,b)`; `resid_disagreement,side,h = (WEO side change) − (official total change)`. Sum the two sides with signs.
- Where no independent total exists for a side, the two residuals collapse into one `resid_total,side,h`, labelled as such.
Output: year × (covered lines, residuals, denominator effect) per (country, variant, WEO vintage, source vintage set). V26 requires exact additivity.

*Implied path of uncovered lines:* `resid_coverage,side,h` is also reported as the implied nominal growth of the uncovered lines from `b` to `h` under the official total, with the historical growth of the same lines alongside. This is a plausibility diagnostic, not a forecast.

### 8.4 Net-interest cross-check in forecasts
`NI_weo,h` vs `GF01_7,h − R07,h` (strict) — the one line WEO identifies directly. Report the gap and its contribution to `resid_disagreement`.

### 8.5 Vintage handling
Every reconciliation table is keyed by `(iso3, weo_vintage, source_vintage_set_hash, series_variant)`. `detect-vintages` re-runs the module when either side changes. Retain all vintage pairs; the time series of `resid_disagreement` across WEO vintages is itself a deliverable (`weo_residual_history.csv`).

### 8.6 What the module does not do
It does not allocate residuals to lines, does not adjust any line, does not translate GDP-assumption gaps into revenue via elasticities, and does not publish an "envelope-consistent" variant (see §15 Q10 if the committee wants one).

---

## 9. Quality grading

| Grade | Definition |
|---|---|
| A | Direct observation or forecast of the complete GG line, compatible ESA concept |
| B | Close official source or composite covering ≥ 90% of the line; minor documented perimeter/concept differences (public-sector receipts; D.41 in place of Level II; gross cash vs accrued; OECD RS with crosswalk) |
| C | Major-component proxy 50–90%; net interest where receipts are material; cash Finanzstatistik with bridge; OECD RS lines with material tax-credit or timing differences |
| D | < 50%, material perimeter uncertainty, weak crosswalk, or coverage not credibly estimable |

C and D appear only in `maximum_extension`.

### 9.2 Coverage share is measured
`coverage_share = component_official / anchor_line` in the last common year; store the year; no overlap → D.

---

## 10. Validation suite

`ERROR` blocks the gate; `WARN` does not. All rows to `exceptions.csv`.

| ID | Test | Sev |
|---|---|---|
| V1 | Anchor years reproduce anchor values; IMF GFS reconciliation within tolerance (0.5%) where available | ERROR/WARN |
| V2 | History: Σ GF01–GF10 = TE (0.1%); `GF01_7`, `GF01_X` excluded | ERROR |
| V3 | History: Level I expenditure shares sum to 100 ± tol; revenue shares likewise | ERROR |
| V4 | All values ≥ 0 except lines that can legitimately be negative (R08, R10, NLB, NI, PB) | ERROR |
| V5 | Overlap-growth diagnostic per stitch (bias, RMSE) | WARN |
| V6 | Boundary growth equals recorded source growth | ERROR |
| V7 | Every forecast row has source, release date, URL, snapshot hash | ERROR |
| V8 | Interpolated / converted rows labelled | ERROR |
| V9 | `observation_type` consistent with variant; no C/D in strict | ERROR |
| V10 | No forecast beyond source horizon (minus conversion loss) | ERROR |
| V11 | No superseded source where a newer applicable vintage exists | ERROR |
| V12 | S13 everywhere; non-GG sources carry a perimeter note | ERROR |
| V13 | Concept compatibility note per stitch | ERROR |
| V14 | Missing stays missing | ERROR |
| V15 | Forecast: Σ covered Level I ≤ envelope TE × (1 + tol); Σ covered revenue ≤ envelope TR × (1 + tol) | WARN |
| V16 | Short/long-term overlap divergence | WARN |
| V17 | `coverage_share_year` on every proxy/composite row | ERROR |
| V18 | Register URLs resolve or archived copy present | WARN |
| V19 | `GF01_X + GF01_7 = GF01`; `GF01_X` has no forecast rows; `GF01_7 ≤ GF01` | ERROR |
| V20 | Interest rows carry `concept_flag`; strict rows gross | ERROR |
| V21 | Level II GF01.7 vs D.41 payable within 5% where both exist | WARN |
| V22 | History: Σ R01–R10 = TR (0.1%) | ERROR |
| V23 | History: `TR − TE` = anchor B.9 net lending (0.1%) | ERROR |
| V24 | Base-year bridge: FRA, DEU level gaps within tolerance (default 1% of TE) in all overlap years; GBR perimeter component stable (σ of gap/TE < config) | WARN |
| V25 | OECD RS reconciliation on tax lines in overlap years within tolerance (config, default 3%) | WARN |
| V26 | Decomposition additivity: history contributions sum to `Δ(NLB/GDP)` exactly; forecast covered + residuals + denominator = WEO change exactly | ERROR |
| V27 | Net-interest cross-check reported for every (country, vintage, horizon) | ERROR |
| V28 | Reconciliation tables keyed by both vintages; no table lacks `weo_vintage` | ERROR |

Reports: boundary plots per stitched series; small multiples (66 lines + 3 ledgers); stacked-contribution charts per country with the WEO balance path overlaid (history and forecast, strict and maximum), residuals shaded.

---

## 11. Architecture

### 11.1 Layers
`raw/` immutable snapshots (`{source_id}/{retrieved_at}_{sha256[:12]}.{ext}`) → `manual/` hand-keyed CSVs → `standard/` tidy per-source tables → `canonical/` deliverables → `manifest/run_{run_id}.json`.

### 11.2 Repo layout
```
gg-fiscal/
  config/
    countries.yaml        # anchors per tree, tolerances, interest_anchor (level2 | d41)
    lines.yaml            # §4 line definitions and ESA/Eurostat/ONS code mappings
    sources.yaml          # register seed (§13)
    residual.yaml         # residual_method per (iso3, line_code) for maximum_extension
  crosswalks/             # OECD_RS→ESA_REV, Steuerschätzung→ESA_REV, OBR→COFOG/ESA_REV, PESA→COFOG, ...
  data/{raw,manual,standard,canonical,manifest}/
  src/ggfiscal/
    ingest/               # eurostat, ons, imf (gfs, weo), oecd (t11, rs, na), ameco, destatis, insee, manual
    standardise/
    stitch/               # anchoring, chain-linking, conversion, interpolation, GF01 split
    forecast/             # composites, proxies, residuals, ST/LT join
    reconcile/            # §8: bridge, dynamics, weo_explanation, vintage keys
    validate/             # V1–V28
    report/
    cli.py                # fetch | standardise | build | reconcile | validate | report | detect-vintages
  tests/
  reports/
  README.md  DECISIONS.md  OPEN_QUESTIONS.md  HANDOFF.md
```

### 11.3 Stack
Python 3.12; pandas + pyarrow; `pandera`; `pytest`; `typer`; `requests` with on-disk cache; `matplotlib` (boundary plots), `plotly` (small multiples, contribution charts); `pyyaml`. No notebooks in `src/`.

### 11.4 Manual-ingest protocol
`data/manual/{source_id}/{table_id}.csv` with `native_period, item, value, unit, page, table_ref, keyed_by, keyed_at, checked_by, checked_at`, sidecar `.meta.yaml` (URL, PDF sha256, page range, concept note). Independent second keying must match to the last published digit; mismatch blocks. PDF stored in `raw/`.

### 11.5 Crosswalks
One CSV per non-native source: `source_code, source_label, target_line, allocation_pct, inclusion_note, consolidation_treatment, evidence, reviewer, crosswalk_version`. Weights supported by official data only. Version bump → rebuild.

### 11.6 Deliverables
1. `expenditure_long_{strict,maximum_extension}.{csv,parquet}`
2. `revenue_long_{strict,maximum_extension}.{csv,parquet}`
3. `balance_ledger.{csv,parquet}` — TR, TE, NLB, NI, PB per (country, year, variant), with a `complete_both_sides` flag
4. `weo_base_bridge.csv` — §8.2
5. `deficit_dynamics.csv` — §8.3 history and forecast contributions
6. `weo_explanation.csv` — §8.3 forecast decomposition with residuals and denominator effect
7. `weo_residual_history.csv` — §8.5
8. `source_register.csv`, `crosswalks.csv`, `exceptions.csv`
9. `coverage_matrix.csv` — 66 lines × (first historical year, final actual, first forecast, final strict, final maximum, stitch count, grades, principal sources, reason series ends, residual_method)
10. Generated `README.md`; `reports/validation_report.html`; `reports/reconciliation_report.html`
11. Code, tests, manifest

### 11.7 Vintage detection
`detect-vintages` compares landing pages / API metadata / hashes against the register and writes `reports/vintage_diff.md`. A new vintage is a config change plus rebuild, never a methodology change. WEO vintages are tracked the same way and trigger the reconciliation module.

---

## 12. Build stages and gates

Each stage ends with `pytest tests/stage_{N}` green, `ggfiscal validate` with no `ERROR`, and an updated `HANDOFF.md`. Gates are hard.

### Stage 0 — Verify and harvest
- Confirm the current IMF data-portal SDMX endpoints for GFS (COFOG, main aggregates) and WEO (the portal and API migrated in 2025; do not assume legacy `dataservices` paths). Confirm Eurostat `gov_10a_exp`, `gov_10a_main`, `gov_10a_taxag`; OECD Table 11, Revenue Statistics, National Accounts; AMECO bulk download; ONS dataset endpoints.
- Pull all anchors, both trees, Level II GF01.7, D.41 both directions, TE, TR, B.9, GDP; IMF GFS; OECD RS; WEO (latest vintage plus the preceding 4–9, per §15 Q11; record which vintages the API actually exposes); AMECO.
- Determine first/last usable year per (country, line, source) programmatically; set `interest_anchor`; produce `coverage_matrix_v0.csv` and reconciliation tables (anchor vs IMF, anchor vs OECD RS, anchor vs WEO history).
- Verify every §13 URL; write `reports/source_verification.md` naming stale, missing or superseded entries.
- **Gate 0:** all 66 lines have programmatically determined coverage from at least one source; §8.2 base-year bridge computed for all three countries on the latest WEO vintage; source verification complete.

### Stage 1 — Canonical history, both trees
- Data model, schemas, anchoring, GF01 split, revenue identity, balance ledger, IMF/OECD RS reconciliation fields.
- V1–V4, V7–V9, V12, V14, V19–V23.
- **Gate 1:** 66 lines + ledgers built from anchors; V-tests green; small multiples render; history-side §8.3 decomposition runs and passes V26.

### Stage 2 — Backward extension
Order: revenue tax lines via OECD RS (all three, mechanical with crosswalk) → interest lines via GG D.41 history → expenditure pre-1995 (FRA, DEU: INSEE / Destatis archived ESA tables; GBR: archived ONS Table 11 vintages, PESA only if reconcilable).
- **Gate 2 (per country, per tree):** every backward stitch has boundary record, crosswalk version, grade, V5; `DECISIONS.md` records why each line stops.

### Stage 3 — Strict forecasts
Priority: `GF01_7`, `R07`, GF02 (all three) → R01, R03, R04, R06 (OBR; Steuerschätzung + BMAS; AMECO/LPFP) → GF07, GF09 (Ageing Report; OBR) → GF10 composites (OBR; COR + AMECO; BMAS + AR) → remaining revenue lines from AMECO where ESA-complete → declare the rest per D7.
- Machine-readable first; PDF via §11.4. Envelope, % GDP handling, interpolation, chaining, composites, conversion (GBR).
- V10, V11, V13, V15, V16, V18.
- **Gate 3:** every strict forecast row A or B with measured coverage; every D7 line has its note; V-tests green.

### Stage 4 — Maximum-extension forecasts
- Proxies with explicit `residual_method`; `GF01` via `GF01_7`; grades C/D; `residual.yaml` per §15 Q3.
- V17. **Gate 4:** variants distinguishable row-by-row; no leakage; coverage matrix complete.

### Stage 5 — Reconciliation module
- §8.2–8.5 in full for both variants and every retrieved WEO vintage; contribution charts; `reconciliation_report.html`.
- V24–V28. **Gate 5:** additivity exact; net-interest cross-check present; residual history populated; a reader can state, for each country and horizon, how much of the WEO balance change the official granular forecasts explain.

### Stage 6 — Packaging and vintage re-run
- Generated README, validation and reconciliation reports, manifest; `detect-vintages` with a simulated new vintage (fixture) showing rebuild without code change.
- **Gate 6:** any stitched value reproducible from anchor and recorded growth using only deliverables; all §1 objectives met.

---

## 13. Seed source register (UNVERIFIED — Stage 0 verifies)

Drafted 31 August 2026 from secondary information; not verified against live publications.

### Historical / anchor / reconciliation
| source_id | Institution | Object | Trees | Notes |
|---|---|---|---|---|
| EUROSTAT_GOV10A_EXP | Eurostat | `gov_10a_exp`, COFOG L1+L2, S13 | Exp | FRA, DEU anchor; from 1995 |
| EUROSTAT_GOV10A_MAIN | Eurostat | `gov_10a_main`, ESA main aggregates incl. TR, TE, B9, D41 both ways, D61, P11_P12_P131 | Rev, Bal | FRA, DEU |
| EUROSTAT_GOV10A_TAXAG | Eurostat | `gov_10a_taxag`, D211, D51A_C1, D51B_C2, D59, D91 | Rev | FRA, DEU |
| ONS_ESA_T11 | ONS | ESA Table 11 GG expenditure by function, L1+L2 | Exp | GBR anchor; archived vintages for pre-1995 |
| ONS_GG_RECEIPTS | ONS | ESA-basis GG receipts by code (PSF and national accounts) | Rev, Bal | GBR; document income tax / NICs / CT mapping |
| ONS_PSF_INTEREST | ONS | GG interest payable and receivable, accrued | Exp, Rev | GBR interest history |
| INSEE_COFOG / INSEE_APU | INSEE | Dépenses et recettes des APU | Exp, Rev | Check pre-1995 base series |
| DESTATIS_81000 | Destatis | GENESIS 81000 family; Fachserie 18 R1.4 archived | Exp, Rev | Check 1991 start |
| IMF_GFS | IMF | GFS COFOG and main aggregates | Exp, Rev | Reconciliation only |
| OECD_T11 | OECD | Table 11 | Exp | Secondary |
| OECD_RS | OECD | Revenue Statistics, 1965– | Rev | Backward extension for R01–R06 via crosswalk |
| IMF_WEO | IMF | WEO database: GGR, GGX, GGXCNL, GGXONLB, NGDP; latest plus 4–9 prior vintages (Q11) | Recon | §8 only; one `source_id` per vintage, e.g. `IMF_WEO_2026_04` |
| EC_AMECO | Commission | AMECO: TR, TE, B9, interest, D2, D5, D61 and sub-items, nominal GDP; 2-year forecast | Env, Rev, Exp | All three (verify UK coverage) |

### Forecast
| source_id | Country | Lines | Object | Horizon (claimed) | Concept note |
|---|---|---|---|---|---|
| OBR_EFO_LATEST | GBR | R01–R06 (receipts by tax), `GF01_7`, GF10 components, envelope | Economic and Fiscal Outlook + supplementary tables | 5 yrs | Public sector, FY, accrued incl. index-linked uplift |
| OBR_FRS_2026 | GBR | GF07, GF09, GF10 components, `GF01_7`, major receipts | Fiscal Risks and Sustainability, July 2026 (% GDP) | 50 yrs | Public sector |
| UK_DEFENCE_PLAN | GBR | GF02 | Spending Review / defence investment plan | per plan | Cash plans |
| EC_AGEING_2024 | FRA, DEU | GF07, GF09, GF10 components | 2024 Ageing Report (benchmark years, % GDP) | 2070 | Construct nominal GDP per §7.5 |
| EC_DSM | FRA, DEU | `GF01_7`, envelope | Debt Sustainability Monitor, baseline | ~10 yrs | GG, ESA |
| FRA_LPFP / PSTAB | FRA | R01–R06 aggregates, envelope | Loi de programmation / programme de stabilité, prélèvements obligatoires | 4–5 yrs | ESA-ish; central + social security detail |
| COR_2026 | FRA | GF10 (pensions) | COR annual report | long-term | |
| FRA_LPM_2030 | FRA | GF02 | Military programming law | 2030 | Central budgetary |
| FRA_LFSS | FRA | GF07, GF10, R06 | LFSS projections | short-term | |
| DEU_STEUERSCHAETZUNG | DEU | R01–R05 | Arbeitskreis Steuerschätzung, revenue by tax, all levels | ~5 yrs | Cash Finanzstatistik; bridge to ESA |
| DEU_BMAS_RVB | DEU | GF10 (GRV), R06 (GRV contributions) | Rentenversicherungsbericht | 15 yrs | GRV only |
| DEU_BMF_FINPLAN | DEU | GF02 (Epl. 14 + Sondervermögen), federal interest | Federal budget and financial plan | 2030 | Federal only |

No identified forecast anywhere: GF03, GF04, GF05, GF06, GF08, `GF01_X`, R08, R10, imputed contributions within R06. Declare per D7.

---

## 14. Country notes and known traps

**GBR.** Anchors are GG, calendar year, ESA 2010, from 1995 (Table 11) and longer for receipts and interest (PSF). All forecast sources are public sector and April–March: convert per §7.10 and measure `coverage_share` on the GG anchor. Interest: ESA accrues the RPI uplift on index-linked gilts; OBR debt interest includes it, gross and net of APF and other receipts — use gross; §15 Q8. Receipts: OBR "current receipts" include public corporations' gross operating surplus and are net of certain payable tax credits — crosswalk per D17. NICs are D.61 (R06), not income tax. GF10 composite = state pension + pensioner benefits + other welfare + adult social care + public-service pensions (FRS). WEO history for the UK is ONS GG data; expect a small stable perimeter gap in §8.2 and document it.

**FRA.** Eurostat/INSEE from 1995 with Level II and tax detail; investigate earlier INSEE base-year series (APU perimeter, pre-ESA95). Interest: AMECO and DSM give ESA gross GG interest; the LPFP "charge de la dette" is state budgetary — central only, coverage measured. Revenue: prélèvements obligatoires in the LPFP/PSTAB are ESA-based aggregates; CSG is D.5 (household income tax, R03) not D.61 — check the anchor's treatment and keep the crosswalk consistent. Ageing Report LTC split between GF07/GF10 per the AR's own allocation. COR covers all regimes; 2023 reform post-dates AR 2024 assumptions — expect V16 divergence. LPM credits are central; gendarmerie (GF03) excluded. WEO history for France is Eurostat EDP data; §8.2 gaps should be revisions only.

**DEU.** Eurostat from 1995 with Level II and tax detail; check Destatis for 1991 start on ESA basis; pre-1991 or non-ESA Finanzstatistik by Aufgabenbereich is cash-based and a different universe — D at best, likely stop. Interest: Länder and municipal interest is material (measure); BMF plan is federal (Epl. 32) — AMECO/DSM preferred. Revenue: Steuerschätzung is cash, by tax, all levels, including the EU's VAT- and GNI-based own resources as deductions — bridge to ESA gross treatment (own resources are D.7 payable in ESA); Gemeindesteuern included; use growth by tax heading mapped to R01–R05. Solidarity surcharge and trade tax (Gewerbesteuer) map to R03/R04 by payer type per the crosswalk; document. Social contributions: BMAS covers GRV only; health, LTC and unemployment insurance contributions need their own sources or fall to composite/proxy. Education, public order, housing, culture are predominantly Länder/municipal; federal proxies are D. Defence: Epl. 14 plus Sondervermögen Bundeswehr.

---

## 15. Open questions reserved for the committee (AC)

Build with the default and list dependencies in `HANDOFF.md`.

| # | Question | Default |
|---|---|---|
| Q1 | Consumer and primary unit (signpost instrument implies % GDP as product). | Nominal LCU primitive; % GDP primary view |
| Q2 | Confirm D1 (NSO anchor; IMF as reconciliation). | D1 as written |
| Q3 | `residual_method` per line for `maximum_extension`, incl. `GF01` via `GF01_7`. | `grow_with_proxy` |
| Q4 | Tolerances: IMF 0.5%; sum-to-total 0.1%; L2 vs D.41 5%; OECD RS 3%; base bridge 1% of TE; V5/V16 thresholds. | As stated |
| Q5 | GDP-deflator real view? | No |
| Q6 | Retired (JPN removed). | — |
| Q7 | Legislated defence plans in strict (grade B) or maximum only? | Strict, B, if GG share ≥ 90% |
| Q8 | UK `GF01_7`: keep index-linked uplift (ESA-consistent) or add an ex-uplift memorandum series? | Keep uplift; no memorandum |
| Q9 | Retired (USA removed). | — |
| Q10 | Publish an envelope-consistent third variant allocating `resid_coverage` across uncovered lines by last-actual shares (grade D, maximum only)? | No — the reconciliation tables carry the residual as a lump |
| Q11 | Resolved: retain 5–10 WEO vintages (2.5–5 years at the April/October cadence), i.e. latest plus the preceding 4–9. If the API exposes fewer, take what it has and note the earliest; if it exposes more, stop at 10. | 5–10 vintages, latest first |
| Q12 | For GBR, use OBR TME/current receipts or AMECO UK as the independent official total in §8.3? | OBR (converted to CY); AMECO as cross-check |
| Q13 | R06 split into employers'/households'/imputed as published lines, or keep one line with the imputed component flagged? | One line; imputed flagged in `notes` |

---

## 16. Working conventions and model allocation

- Spec-first. This document plus `config/` is the spec; `DECISIONS.md` is the append-only decision log with reasons. Never edit an earlier decision; supersede it.
- `HANDOFF.md` rewritten before every stop: stage, gate status, blockers and owners, exact next command.
- `OPEN_QUESTIONS.md` collects committee items, referencing §15 IDs or adding new ones.
- Content-addressed raw store; never mutate a snapshot. Unchanged config + snapshots → byte-identical `canonical/`.
- Hard gates. A stage with a failing gate is not done; write up why.
- No ARIMA or other private benchmark forecasts in this repo. A benchmark, if wanted, lives elsewhere.
- Model allocation (committee's standard pattern): the strongest available model for Stage 0 (source verification and the anchor/interest decisions), all crosswalk adjudication, §8 reconciliation design and every gate review; the mid tier for implementation in Stages 1–6; the small tier for mechanical ingestion modules, fixtures and test scaffolding. Judgement calls on grading or perimeter always go to the strongest model, with reasoning recorded in `DECISIONS.md`.
