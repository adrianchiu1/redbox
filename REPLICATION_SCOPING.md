# US and Japan replication — scoping note and questions for the committee

Prepared 2026-09-20, before any build. This note records (a) what
replicating the package for the United States (`USA`) and Japan (`JPN`)
would mean, (b) what the official sources actually offer and which of them
this environment can reach (every URL cited was requested live from the
sandbox on 2026-09-20), (c) what in the code and the specification stands
in the way, (d) an effort estimate and a proposed order of work, and (e)
the questions whose answers change the work. It is the replication-side
analogue of `DEBT_SCOPING.md`.

Nothing in this note changes the existing pipeline. No source has been
registered and no data pulled into the D8 store; research downloads sit
outside the repo.

Context: specification v1 covered both countries. v2.2 dropped them
(`COFOG_KICKOFF.md` §15 Q6 "Retired (JPN removed)", Q9 "Retired (USA
removed)") without recording why. The findings below are, in effect, the
reasons — and what it would take to overcome them.

---

## 0. Verdict in two paragraphs

**United States.** Feasible, and in some respects easier than the three
European countries: the SNA-format redistribution of BEA's NIPA that BEA
supplies to the OECD (Tables 11, 12 and 10 for `USA`) is machine-readable,
calendar-year, general government, and runs from **1970** (25 years
further back than the European anchors); the NIPA flat files add 1929–2025;
the Treasury securities register is complete from October 1979 through a
public API. Three things break the package's assumptions. (1) **No US
source publishes COFOG Level II**: 01.7, 10.2, 10.5 and 04.5 have to be
proxied from BEA's own sub-function lines (grade B, `level2_proxy_actual`).
(2) **No institution forecasts US general government**: the only
general-government forecasts are international (AMECO and OECD Economic
Outlook to 2027, IMF WEO aggregates to 2031); everything national is
federal-only, fiscal-year (Oct–Sep), budget-basis (CBO, OMB), or a
trust-fund component (Medicare trustees; the Social Security trustees'
site is bot-blocked from here, as is cbo.gov). (3) **Three lines are
structurally zero** — `R01` (no VAT), `E04` (Medicare and Medicaid are
booked as D.62 cash benefits, so D.632 is zero) and `GF05` (BEA has no
environmental-protection function) — and the package currently requires
every country to carry every line.

**Japan.** Feasible, with richer national data than the US (COFOG with all
69 groups from FY2005, in English; the general-government account with
full D-item detail from 1994 on both fiscal-year and calendar-year bases;
the only 100-year official pension projection in the set) but two
structural wedges. (1) **Period basis**: every Japanese functional and
subsector table — ESRI's COFOG table, OECD Table 11, IMF GFS, OECD
Revenue Statistics — is **fiscal-year (Apr–Mar) only**, while the
general-government totals, OECD Table 12, AMECO and the WEO are calendar
year. The COFOG tree therefore cannot be built on the package's
calendar-year canon without a §7.10-style conversion of the *anchor*
itself, which the spec has never allowed (D3 converts forecast sources
only). (2) **Official forecasts are thin and PDF-only** apart from the
MHLW pension valuation: the Cabinet Office medium-to-long-term projection
(to FY2040) covers central plus local government *excluding* social
security funds and publishes net, not gross, interest; MOF documents are
central general-account cash. The JGB register is fully documented for
terms and auctions from 1989 but **per-issue outstanding is not published
as a time series**, so positions would be reconstructed from flows
(grade B) or from National Diet Library web-archive snapshots.

Order of magnitude: **≈ 30 engineering-days for the first country and
≈ 20 for the second** (fiscal package plus debt extension, one builder,
excluding committee turnaround), of which roughly 40% is crosswalk and
grading judgement rather than code. About half the code work is a one-off
generalisation of the package that benefits both countries — and any
further one — and should be done first (§6).

---

## 1. What is being asked for

Replicate, for `USA` and `JPN`, everything the package produces for GBR,
FRA and DEU: the three trees (17 COFOG lines, 9 ESA-economic-type lines,
15 ESA-revenue lines), the balance ledger, both variants, backward and
forward extension under §6–§7, the IMF WEO reconciliation (§8), the flat
files, catalogue, notebooks and chart site, and the debt extension
(`DEBT_KICKOFF.md`): the central-government marketable-securities
register, the interest and financing chains, and the maturity profile.

Everything below is measured against that full scope. Where a component is
cheaper to drop than to build, §7 says so.

---

## 2. Where the two countries break the package's assumptions

The package is ESA 2010 / Eurostat-shaped: anchors are Eurostat
`gov_10a_*` or ONS ESA tables, line cells are Eurostat/ONS codes in
`config/lines.yaml`, forecasts default to AMECO/Ageing Report/DSM, and
period conversion exists only for UK April–March sources. Neither new
country has an ESA anchor; both are SNA 2008 with their own presentation.

| Assumption | GBR/FRA/DEU | USA | JPN |
|---|---|---|---|
| Anchor is the national statistical office's ESA table (D1) | ONS / Eurostat | BEA publishes NIPA (own presentation, sales netted); the SNA-format GG tables exist only as BEA's submission to the OECD (Tables 11/12/10) | ESRI publishes full SNA tables (JP and EN xlsx); OECD Tables 11/12/10 carry the same cells |
| COFOG Level II from the anchor's Level II table | yes (DEU from 2000) | **none** (OECD T11 Level I only; IMF GFS has 01.7 for 1980–89 only); BEA sub-functions are the proxy | yes, all groups, FY2005–FY2024 |
| Calendar-year anchors (D3) | yes | yes (BEA converts state FY itself) | **COFOG, subsector, RS and Table 10 are FY only**; GG totals, T12, AMECO, WEO are CY |
| Period conversion only for UK Apr–Mar forecasts (§7.10) | 0.25/0.75 weights | federal FY Oct–Sep → different weights (0.75/0.25); anchors need none | Apr–Mar weights reusable, but applied to an *anchor* tree, not a forecast |
| Every country carries every line (`config.line_universe`) | yes | `R01`=0, `E04`=0, `GF05`=0 by construction | all lines exist |
| Default forecasts: AMECO + Ageing Report + DSM | yes | AMECO has USA to 2027; no AR/DSM | AMECO has JPN to 2027; no AR/DSM |
| An independent official TR/TE total for §8.3 (OBR / AMECO / DSM) | yes | AMECO (2 yrs); nothing national | AMECO (2 yrs); Cabinet Office is CG+LG only |
| WEO history reproduces the anchor within 1% of TE (V24) | FRA/DEU yes, GBR perimeter gap | WEO is GFSM-basis with documented adjustments (e.g. the 2017 repatriation tax); expect a stable wedge | WEO is CY Cabinet Office data — should match the CY anchor |
| D.41 concept | gross accrued ESA | NIPA/IMA interest includes imputed interest on unfunded federal pension liabilities (1,397.6 bn 2024) vs OECD T12 D41 (1,384.6 bn) | FISIM-adjusted (7,368 bn FY2023, ESRI/OECD/AMECO) vs FISIM-unadjusted (8,657 bn, IMF GFS/ESRI GFS table): a 17% wedge on `GF01_7`/`E05` |
| Language and format | English, xlsx/SDMX | English, JSON/CSV/SDMX | ESRI/BoJ bilingual xlsx; MOF auction files bilingual; **annual report, debt-service statistics, index ratios, floater coupons, Cabinet Office and MHLW projections Japanese-only, several PDF-only** |
| Debt office publishes per-security positions | DMO/AFT/Finanzagentur | Treasury MSPD per CUSIP monthly from Jan 2001; earlier implied from auctions | one live March-end snapshot; history only via web-archive captures or reconstruction |
| Currency schema | GBP, EUR | USD (`model.py` rejects it today) | JPY (values ≈ 10³ larger in millions; chart scales) |

The three concept wedges to carry explicitly, in the spirit of D16:

**Presentation.** NIPA nets sales of goods and services against consumption
expenditure; the SNA presentation grosses them up (2024: OTE 11,592 bn vs
NIPA total expenditures 10,424 bn, same gap on receipts, NLB unaffected).
ESRI's functional table includes consumption of fixed capital inside
"final consumption" and allocates no interest to 01.7; the OECD/IMF rebuild
of the ESA-style total by function from ESRI tables 7 and 8 is what the
package's TE concept needs (04.5 transport FY2023: 12,984 bn in the ESRI
columns vs 7,781 bn on the ESA-style basis).

**Perimeter.** US federal outlays are ≈ 60–65% of general-government TE,
so every CBO/OMB-based forecast is a §6.2 rank-4 dominant-component proxy
(maximum only). Japan's Cabinet Office projection excludes social security
funds (≈ half of TE); MOF budget lines are the central general account.
FILP agencies are outside S13 in Japan, but FILP bonds are central-government
liabilities.

**Period.** Japan's fiscal year runs April–March and labels years by their
starting April; OECD Table 11 and IMF GFS carry those FY values under the
starting-year label without flagging it (verified cell-for-cell against
ESRI). The register must record the basis per source, and the COFOG tree's
canonical basis for Japan is a committee decision (§8, Q-R2).

---

## 3. Source findings — United States (tested 2026-09-20)

### 3.1 Reachability

Open from the sandbox: `apps.bea.gov` flat files (the API needs a free
registered key; not needed), `api.fiscaldata.treasury.gov`,
`www.treasurydirect.gov` web service, `www.whitehouse.gov` (OMB, browser
User-Agent), `www.cms.gov`, `www.federalreserve.gov` (Z.1),
`markets.newyorkfed.org` (SOMA), `sdmx.oecd.org`, `api.imf.org`,
`ec.europa.eu` (AMECO), `api.bls.gov`, `raw.githubusercontent.com`
(CBO's own mirror of every baseline since 1982). **Blocked:** `www.cbo.gov`
(DataDome challenge, 403 under every header set), `www.ssa.gov` (Akamai,
403 on every path), `github.com`/`api.github.com` (403), the NIPA
underlying-detail flat file (403).

### 3.2 Anchors and history

| source_id (proposed) | Object | Years | Basis | Role | Grade |
|---|---|---|---|---|---|
| `OECD_T11` (existing id, add USA) | `DSD_NASEC10@DF_TABLE11` A.USA.S13: Level I GF01–GF10 and `_T`, 19 transactions incl. OTE, D4-by-function | 1970–2024 | CY, USD mn, S13 | **COFOG anchor** (Level I). `GF05` is zero. 2024 OTE = 11,593,449 = IMF TOTOUT | A |
| `OECD_T12_EXP` / `_REV` / `_BAL` (new) | `DF_TABLE12_EXP/REV/BAL` (the successors of Table 12): D1, P2, D62, **D632=0**, D41, D3, D7, D9, P5, NP, OTE; D2 (D21, **D211=0**, D29), D5, D61 (D611/D613/D612_D614), D4/D41/D4N, D7, D9/D91, P1M/P1O/P131, OTR; B9 | 1970–2024 | CY | **ESA_EXP and ESA_REV anchor** (identities exact) | A |
| `OECD_T10` (new) | `DF_TABLE10` taxes and contributions detail: D51A households / D51B corporations, D51C, D59, D91, D214A excises, D611/D613 | 1970–2024 | CY | R03/R04 split, R05, R02_A, R06_E/R06_H cells | A |
| `BEA_NIPA` (new) | `NipaDataA.txt` + `SeriesRegister.txt` (559,570 rows): Tables 3.1/3.2/3.3 from 1929; **3.16/3.17 by function from 1959** with sub-function lines (interest = GG D.41; unemployment; retirement; transportation) | 1929/1959–2025 | CY, NIPA presentation | Level II proxies (B); 1929–1969 backward legs; the one source with 2025 | A/B |
| `FRB_Z1` (new) | Z.1 CSV bundle: S1311 integrated accounts (federal SNA-format), F.106/L.210 Treasury securities by holder | 1945–2025 | CY | debt step B (S.1311 D.41, NLB, SFA) | A |
| `IMF_GFS` (existing, add USA) | GFS_COFOG 1972–2024 (Level I; GF0170 1980–89 only), GFS_SOO 1972–2025 | CY | reconciliation only | A |
| `OECD_RS` (existing, add USA) | Revenue Statistics 1965–2024, S13 and subsectors | CY | 1965–69 tax legs | B |
| `EC_AMECO` (existing, add USA) | chapters 6/16/18 carry USA on ESA names; values equal OECD T12 | 1960–2027 | CY | E-tree, D.2/D.5/D.61 totals, TR/TE/B9 forecast to 2027; envelope | A/B |
| `IMF_WEO` (existing, add USA) | GGR/GGX/GGXCNL/GGXONLB 2001–2031, NGDP 1980–2031; latest actual 2025 | CY | §8 only | A |

### 3.3 Forecasts

| source_id (proposed) | Institution | Lines | Horizon | Basis | Reach | Grade |
|---|---|---|---|---|---|---|
| `EC_AMECO` | Commission | E01–E09 (E04=0), R02/D.5/R06 totals, R05 via UTKG, TR, TE, NLB | 2027 | CY, ESA | yes | A/B |
| `OECD_EO_119` (new) | OECD Economic Outlook, `DSD_EO@DF_EO`: GGINTP (gross interest), GGINTR, TYH/TYB (household/corporate direct taxes), TIND, SSRG, SSPG, IGAA, TKPG, CGAA, YPGT/YPG | 2027 | CY, SNA-like; totals differ from T12 by concept | yes | A/B |
| `CBO_BASELINE` (new) | CBO baseline via its GitHub mirror (every baseline 1982–2026-02): Social Security, Medicare, Medicaid, other mandatory, defence/non-defence discretionary, net interest; revenues by source | FY2036 | **federal FY Oct–Sep, unified-budget cash** | mirror yes; cbo.gov (10-year workbooks, NIPA-basis tables, 30-year LTBO) **blocked** | B/C, maximum only |
| `OMB_BUDGET_FY2027` (new) | OMB Historical Tables with estimates (incl. subfunction 901 **gross** interest), Public Budget Database | FY2031 | federal FY, budget, policy scenario | yes | C |
| `CMS_TRUSTEES_2026` (new) | Medicare Trustees expanded tables (CSV): HI/SMI operations by **calendar year**, 75-year % GDP | 2034 nominal / 2100 % GDP | CY, trust-fund | yes | B (component of GF07, R06) |
| `SSA_TRUSTEES` | OASDI Trustees (OASI benefits → GF10_2; payroll tax → R06) | 2100 | CY | **blocked** | — |
| State and local | — | none exists | — | — | — | — |

Lines with no official forecast (D7 declarations): GF03, GF05, GF06, GF08,
GF09, GF01_X, GF04_X, GF10_X, GF10_5, the state share of GF07/GF10; R01,
R05, R08, R10, the D.611/D.613 split, E04, E07 (partial). Direct GG
forecasts to 2027 exist for E01–E03, E05, E06, E08, E09, R02, R03, R04,
R06, R07, TR, TE, NLB. Longer horizons are federal-only (CBO 2036, OMB
2031) or trust-fund components (Medicare).

### 3.4 Debt register

| source_id (proposed) | Object | Years | Reach | Grade |
|---|---|---|---|---|
| `US_FD_AUCTIONS` | Fiscal Data `auctions_query`: every auction with CUSIP, term, dates, amounts, yields, TIPS index ratio at issue, FRN spread and index rate, SOMA add-ons — **11,124 auctions, 4,648 CUSIPs, 1979-10 → 2026-09** | 1979– | yes | A |
| `US_FD_MSPD_T3` | MSPD Table III per-CUSIP month-end positions (outstanding, inflation adjustment, redeemed) — 154,292 rows, 206→472 securities per month-end | **2001-01–** | yes | A (2001–), B implied 1980–2000 |
| `US_FD_TIPS_CPI` | TIPS reference CPI and index ratios per CUSIP, daily | 2008-05– (1997–2008 recomputable from BLS CPI-U, reachable) | yes | A / B |
| `US_FD_FRN_INDEX` | FRN daily indexes (the 13-week bill rate is also in the auction file from 2014, so the fixing history is complete — no DD10 gap) | 2014– | yes | A |
| `US_FD_INTEREST_EXPENSE` | Interest expense on the public debt by category, monthly (Treasury accrual) | 2010-05– (earlier: OMB subfunction 901 FY1962–; NIPA 3.18B budget↔NIPA bridge FY1952–) | yes | A / B |
| `US_FD_MTS` | Monthly Treasury Statement tables incl. means of financing | 2015-03– (earlier PDF/annual) | yes | A / C |
| `FRB_SOMA` | NY Fed SOMA holdings per CUSIP, weekly | 2003-07– | yes | A |
| `FRB_Z1` | Z.1 S1311 accounts and Treasury-securities-by-holder tables | 1945– | yes | A |

Register depth under DD8: terms and flows from 1980; positions from 2001
(implied 1980–2000, buy-backs were negligible: $67.5 bn in 2000–02). The
US register is the largest of the five (≈ 5,000 securities; the UK has
1,747) but structurally simplest: one issuer, bullet coupons, TIPS on a
3-month-lag daily interpolation like the 3-month ILG regime, FRNs on a
published daily index.

---

## 4. Source findings — Japan (tested 2026-09-20)

### 4.1 Reachability

**Everything is reachable**: `www.esri.cao.go.jp`, `www5.cao.go.jp`,
`www.mof.go.jp`, `www.mhlw.go.jp`, `www.boj.or.jp`,
`www.stat-search.boj.or.jp`, `sdmx.oecd.org`, `api.imf.org`,
`ec.europa.eu`, and `warp.ndl.go.jp` (the National Diet Library web archive,
needed for MOF back-issues). No bot walls. The e-Stat API needs a free
application id but is not needed: ESRI serves every table as xlsx at stable
URLs (`/en/sna/data/kakuhou/files/{YYYY}/tables/{YYYY}{table}_en.xlsx`).

### 4.2 Anchors and history

| source_id (proposed) | Object | Years | Basis | Role | Grade |
|---|---|---|---|---|---|
| `ESRI_SNA_S7` + `ESRI_SNA_S8` (new) | Annual national accounts Table 7 "General government total outlays by function" (10 divisions, **all 69 groups**, 9 economic columns) and Table 8 (final consumption by function: D.1, CFC, P.2, sales, D.632) — EN and JP | FY2005–FY2024 (2020 benchmark, 2008SNA) | **FY only** | national COFOG anchor once assembled to the ESA-style total (strip CFC, add D.4) | A (FY) |
| `OECD_T11` (existing, add JPN) | Level I and all groups, OTE etc. — **equals IMF GFS and ESRI FY cell-for-cell** (GF0405 2023 = 7,781.3 bn; GF1002 = 62,147.8 bn) | 2005–2024 | **FY labelled by starting year** | the practical COFOG anchor (already ESA-style) | A (FY) |
| `ESRI_SNA_I4` + `ESRI_SNA_C3` (new) | Table 4 general-government income accounts and capital account: D.41 both ways (FISIM-adjusted and a FISIM-unadjusted memo), D.2 incl. VAT, D.3, D.5, D.61 split (employers'/households'/imputed), D.62, D.632, D.7, D.9 (of which D.91), P.51, NP, NLB | 1994–2024 | **FY and CY** and quarterly | ESA_REV anchor and most of ESA_EXP on CY (D.1/P.2 are FY-only in ESRI; CY from OECD T12 from 2005) | A |
| `OECD_T12_EXP/REV/BAL` (new) | as for the US: every E-line and R-line item incl. D211, D611/D613, P1M/P1O/P131; B9 = ESRI CY NLB | 2005–2024 | CY | ESA_EXP/ESA_REV anchor 2005+ | A |
| `ESRI_SNA_S6_2` (new) | Table 6(2) GFS presentation by central / local / social-security / GG: **taxes on individuals vs corporations (1111/1112)**, VAT, contributions by payer, interest, sales; expense by GFS item; subsector D.41 (CG 7,657 / LG 996 / SSF 5 bn FY2023) | FY1994–FY2024 | FY | R03/R04 split; debt step B intermediates | A (FY) |
| `OECD_T10` (existing pattern, add JPN) | taxes detail incl. D211, D214, D611/D613 — but **no D.51 household/corporate split** | 1994–2024 | FY | secondary | B |
| `ESRI_ARCHIVE_2000BASE` (new) | 2009 annual report vintage (93SNA, 2000 base): COFOG **Level I** FY1980–FY2009, GG account and subsectors; Japanese-only xls | FY1980–FY2009 | FY | backward legs 1980–1993 (2004) | C |
| `ESRI_ARCHIVE_68SNA` | 1998 vintage: GG by subsector FY1970–1998, 68SNA items (indirect/direct tax, no D.632) | 1955/1970–1998 | FY | D at best; no functional table | D |
| `IMF_GFS` (existing, add JPN) | GFS_COFOG 2005–2024 with all groups; GFS_SOO 1994–2024 (tax items from 1972) — **FY, equals ESRI** | FY | reconciliation only; and the source of the FISIM-unadjusted interest concept | A |
| `OECD_RS` (existing, add JPN) | 1965–2024 — **FY** (5111 VAT 2023 = ESRI FY VAT exactly) | FY | 1965–1993 tax legs | B |
| `EC_AMECO` (existing, add JPN) | 138 JPN variables on ESA names, values = OECD T12; **2025 column is NA** in the Spring 2026 file | 1981–2027 | CY | E-tree/R-tree 2-year forecast; envelope | A / B |
| `IMF_WEO` (existing, add JPN) | 1980–2031, latest actual 2024, **CY** (Cabinet Office CY sector accounts via Haver), full S13 | CY | §8 only | A |

### 4.3 Forecasts

| source_id (proposed) | Institution | Object | Horizon | Basis | Format | Grade |
|---|---|---|---|---|---|---|
| `EC_AMECO` | Commission | full E/R trees, TR/TE/B9 | 2027 | CY | txt | B |
| `CAO_CHUCHOKI` (new) | Cabinet Office, Council on Economic and Fiscal Policy — "Economic and Fiscal Projections for Medium to Long-Term Analysis", Jan and Jul editions | FY2040, three scenarios | FY; SNA basis; **central + local only (no social security funds)**; PB, **net** interest, fiscal balance, debt; macro incl. long rate and effective rate | **PDF, Japanese only** (tables extract cleanly) | C (sub-perimeter envelope) |
| `MHLW_ZAISEI_KENSHO_2024` (new) | MHLW statutory pension valuation, 36 scenario workbooks | **FY2024–FY2120** | FY; Employees' and National Pension benefits, contributions, state subsidy | xlsx (zip, cp932 names), Japanese | B for GF10_2 (dominant component); C for R06 |
| `MHLW_2040_OUTLOOK_2018` (new) | "Social security outlook toward 2040": pensions / health / LTC / children, benchmark years FY2018/2025/2040 | 2040 | FY; social-security-benefit concept | PDF, Japanese, 2018 vintage | C |
| `MOF_KOUNENDO` (new) | MOF "impact on later years" projection: debt service incl. interest, social security, local transfer | 3 yrs | FY, central general-account cash | PDF, Japanese | C/D |
| `MOF_BUDGET` | annual budget: debt service, defence, tax revenue by tax (central) | 1 yr | FY cash | PDF (EN highlights) | C/D |
| Council on Fiscal System long-term estimate | to FY2060 | — | — | not located live (2018/2022 material pages 404) | D |
| OECD Economic Outlook | GG aggregates | 2027 | CY | SDMX (not pulled) | B |

Lines with no official forecast beyond AMECO's two years: GF01_X, GF03,
GF04 (and splits), GF05, GF06, GF08, GF09, GF10_5, GF10_X; GF02 only as
the FY2023–27 defence build-up plan (central cash, C); GF07 only via the
2018 outlook; R01/R03/R04 only via central-cash budget documents (C);
R05, R07, R08, R09, R10 and the contribution split: none. No source
projects gross S13 D.41.

### 4.4 Debt register

| source_id (proposed) | Object | Years | Format | Grade |
|---|---|---|---|---|
| `JP_MOF_AUCTION_JGB` | auction results, one sheet per type (40y, 30y, 20y, 15y floater, 10y, 10y JGBi, 5y, 2y, GX bonds, discontinued 6y/4y/3y-discount, TB): issue number, dates, coupon, amounts, prices, yields — **≈ 1,370 coupon-bond issues 1990–2025** | 2y from 1979, 20y from 1987, **10y from 1989** (issue 119; 1–118 absent), JGBi 2004–, floaters 2000–08 | bilingual xls (BIFF8) | A (terms, issuance) |
| `JP_MOF_AUCTION_TBILL` | T-bill/FB auctions, issues 1–1397 | FY1999– | xls | A |
| `JP_MOF_LIQUIDITY_BUYBACK` | liquidity-enhancement reopenings, buy-backs | 2006– / 2002– | xls | A |
| `JP_MOF_OUTSTANDING_BY_ISSUE` | outstanding by issue (565 lines) — **one live March-end snapshot only**; history only as NDL web-archive captures of the same URL | 2026-03 | xlsx | B/C |
| `JP_MOF_ANNUAL_REPORT` | JGB statistical annual report: outstanding, issuance and redemption by bond type; **interest paid by bond type (Debt Consolidation Fund)** — FY2024 domestic bonds 8,736.7 bn | FY2020– live, FY2011– via web archive | xlsx, Japanese | A (step A cash interest, by type) |
| `JP_MOF_ZAISEI_TOKEI` | budget statistics: national debt service (redemption + interest) by FY | FY1967– | xlsx | B |
| `JP_MOF_JGBI_INDEX_RATIO` | JGBi applicable CPI and index ratio per issue, daily, one xls per month | 2023-05– live; 2004– via web archive | xls, Japanese | A / B |
| `JP_MOF_FRN15_COUPONS` | 15-year floater: every coupon fixing (base = 10y auction yield) for issues 8–48 (all matured) | 2000–2023 | xls | A |
| `JP_BOJ_HOLDINGS_BY_ISSUE` | BoJ JGB holdings by issue, 2–3 releases a month; the only official per-issue series (a lower bound on outstanding) | 2001– (xlsx from 2015; xls-in-zip 2013–14; HTML/PDF earlier) | JP/EN | A (2013–) |
| `JP_BOJ_FOF` | Flow of Funds bulk flat file (1.27 M rows, quarterly and FY, 1979–2026): CG securities by holder, SFA | 2005– on 2008SNA | CSV (JIS) | A |
| `ESRI_SNA_S243` | financial transactions of general government by subsector | FY1994– | xlsx | A (FY) |

Register depth under DD8: terms and flows from 1989 (10-year) with older
lines from 1979–87; per-issue positions must be reconstructed from flows
and validated against the BoJ series and the by-type totals (grade B
`implied`), unless the committee accepts web-archive snapshots (Q-R8).
Pre-1989 10-year issues need the annual report back-issues (PDF, §11.4).

---

## 5. Expected coverage per line (what the built series would look like)

Assuming the OECD tables as anchor (Q-R1), calendar-year canon for the US
and the committee's choice of basis for Japan's COFOG tree (Q-R2), and
AMECO/OECD EO as the two-year forecast layer:

| Line group | USA first year | USA last actual | USA strict forecast | USA maximum | JPN first year | JPN last actual | JPN strict forecast | JPN maximum |
|---|---|---|---|---|---|---|---|---|
| COFOG Level I (GF01–GF10; GF05 = 0 for USA) | 1970 (A); 1959 via BEA functions (C) | 2024 | GF07/GF10 none strict; GF01 via interest as today | GF02 CBO defence, GF07 Medicare+Medicaid, GF10 Social Security (FY, federal, C) | FY2005 (A); FY1980 via 2000-base archive (C) | FY2024 | none beyond AMECO | GF02 defence plan (C); GF07 2018 outlook (C) |
| GF01_7 interest | 1959 BEA (B proxy = GG D.41); 1970 T11 D4-by-function | 2024 (2025 via NIPA) | AMECO/OECD EO gross to 2027 (A/B) | OMB gross federal interest to 2031 (C) | FY2005 L2 (A) | FY2024 | AMECO 2027 | Cabinet Office **net** CG+LG to 2040 (C) |
| GF10_2 / GF10_5 / GF04_5 | 1959 BEA sub-functions (B; 10.2 includes survivors) | 2024 | none | CBO Social Security (C), UI in "other mandatory" — none | FY2005 (A) | FY2024 | none | MHLW pensions to 2120 (B) |
| ESA_EXP E01–E09 (E04 = 0 for USA) | 1970 (A); 1929/1959 NIPA legs (B) | 2024 | AMECO/OECD EO 2027 (A/B) | — | 2005 CY (A); 1994 CY from ESRI for all but D.1/P.2 | 2024 | AMECO 2027 (B) | — |
| ESA_REV R01–R10 (R01 = 0 for USA) | 1970 (A); 1965 RS (B); 1929 NIPA (B) | 2024 | AMECO/OECD EO 2027 for R02, R03, R04, R06, R07 | CBO revenues (C) | 1994 CY (A; R03/R04 from FY GFS table → B); 1965 RS (B, FY) | 2024 | AMECO 2027 totals | central-cash budget (C) |
| Balance ledger | 1970 | 2024 | 2027 | — | 1994 CY | 2024 | 2027 | — |
| WEO reconciliation | 2001– (WEO GG fiscal series start 2001) | | resid_total only (no independent national total) | | 1980– | | resid_total only | |

Explained shares in §8.3 would be dominated by the two-year AMECO/EO
layer; beyond 2027 both countries would show the WEO change almost entirely
in the residual — the honest result, and the reason §7 recommends
registering the federal/central long-horizon sources as maximum-only
proxies rather than pretending to a strict long leg.

---

## 6. What has to change in the code

A file-by-file audit of `src/ggfiscal`, `config/`, `tests/`, `tools/` and
the notebooks (2026-09-20) found the engines country-agnostic and the
routing not. Three findings drive the plan.

**F1 — `config/countries.yaml` is not wired.** Of its per-country keys,
only `currency` is read (`build.py:307`, `publish/flatten.py:1023`).
`anchors`, `gdp_source`, `interest_anchor`, `envelope_forecast`,
`period_basis_forecast`, `weo_perimeter_gap_expected` are documentary.
Routing is `if iso3 == "GBR": ONS … else: Eurostat` in at least twelve
places: `build.py:68,103,172,230,264,544`; `coverage.py:43,66,89,184,208`;
`reconcile/bridge.py:46,147`; `reconcile/recon_v0.py:45,67`;
`validate/stage1.py:263`; `validate/stage3.py:189`; `validate/stage5.py:31`.
A fourth `elif` in every one of them is the wrong fix.

**F2 — the line universe is a cross product.** `config.line_universe()`
(`config.py:149-158`) is countries × lines; `S0_COVERAGE` errors on any
missing line (`validate/runner.py:117-121`); `dynamics.decompose` requires
all twenty Level I lines per year (`reconcile/dynamics.py:52-57`) and the
benchmark balance skips a country otherwise (`forecast/balance.py:80-83`);
`tests/stage_1/test_gate1.py:31-34` asserts the exact set. A US build with
`R01`, `E04` and `GF05` absent fails Gate 0 and yields no decomposition.

**F3 — forecast coverage collapses to zero outside the EU.** Every default
`FcSource` is AMECO, Ageing Report or DSM (`forecast/forward.py:313-385`);
AMECO does carry USA and JPN, so the default block would work, but
`tests/stage_4/test_gate4.py:40-42` assumes AMECO proxies exist for every
country's `GF01`/`GF10`, and `fy_to_cy` (`forward.py:90-100`) is hard-wired
to April–March weights.

Change list, grouped by whether it is a one-off generalisation or
per-country work:

| # | Change | Kind | Files | Days |
|---|---|---|---|---|
| G1 | `COUNTRIES` from config; pandera `iso3`/`currency` checks from `countries.yaml` (`model.py:42,51`); `COUNTRY_NAME` maps unified (`flatten.py:40`, `statistical.py:54`, `tools/build_chartsite.py:65`, `tools/update_notebooks_s11.py:31`); `manifest.FLAT_FILES` | one-off | config, model, flatten, statistical, manifest, tools | 0.5 |
| G2 | **Anchor family object** read from `countries.yaml.anchors`: `cofog(code)`, `main(item, direction)`, `tax(code)`, `d41_payable()`, `gdp()`, `totals()` — Eurostat, ONS and a new OECD family behind one interface; the twelve routing sites call it | one-off | build, coverage, bridge, recon_v0, stage1, stage3 | 1.5 |
| G3 | **Per-country line universe**: a `lines_absent` list per country with a reason; V2/V22/V26 treat absent lines as zero rows typed `structural_zero`; decomposition and balance tolerate them; catalogue and coverage matrix carry the reason | one-off | config, runner, stage1, dynamics, balance, flatten, test_gate1 | 2 |
| G4 | **Period basis per country**: `fy_to_cy(weights)` from `countries.yaml` (0.25/0.75 Apr–Mar; 0.75/0.25 Oct–Sep); `source_period_basis` stamped from the source register instead of the `"CY"` literal (`build.py:348,403,460`); an anchor-level FY→CY path if Q-R2 chooses conversion | one-off | forward, build, intermediates | 1 |
| G5 | WEO gap classification and V24 read `weo_perimeter_gap_expected` (`bridge.py:147-156`, `stage5.py:31`) instead of `iso3 == "GBR"`; `perimeter_break` (DEU 1991) from config (`backward.py:25`) | one-off | bridge, stage5, backward | 0.5 |
| G6 | GFS COFOG/SOO history promoted to generic backward `ExtSource`s (today DEU-only, `backward.py:95-116`); GFS SOO codes already sit in `lines.yaml` | one-off | backward | 0.5 |
| G7 | Notebook and chart-site tooling: seed `forecasts_{ISO}_*` books by copying (`update_notebooks_s11.py:427` edits an existing book), chartbook per-country cell blocks for a new country (`:119-121` raises on none), `build_chartsite` ISO maps | one-off | tools, notebooks | 1 |
| C1 | OECD Table 12/10 endpoint and reader (`_oecd_frame` family, ~100 lines), `lines.yaml` `oecd_t12`/`oecd_t10` cells for ESA_EXP and revenue, GDP from OECD Table 1 or the NSO | per country (shared reader) | endpoints, readers, lines.yaml | 1.5 + 1 judgement |
| C2 | National readers: BEA NIPA flat file (register-driven series lookup, ~150 lines) / ESRI xlsx tables s7, s8, i4, c3, s6_2 and the 2000-base archive (~300 lines, Japanese sheet parsing) | per country | readers | 1.5 (USA) / 3 (JPN) |
| C3 | Level II: USA proxies from BEA sub-functions with concept notes (10.2 includes survivors; 04.5 current+investment); JPN from OECD T11 groups | per country | build, coverage, crosswalks | 0.5 + 1 judgement |
| C4 | Backward legs and crosswalks: `OECD_RS_to_ESA_REV` rows with measured USA/JPN evidence; `BEA_NIPA_to_COFOG` / `ESRI_2000BASE_to_COFOG`; 1929–69 NIPA legs; JPN 1980–93 archive legs | per country | backward, crosswalks | 1 + 2 judgement |
| C5 | Forward legs: OECD EO reader and `FcSource`s; CBO mirror / OMB / CMS readers with FY conversion and `coverage_share` on the anchor (USA); Cabinet Office PDF table extraction under §11.4, MHLW valuation reader, 2018 outlook benchmark rows (JPN); D7 declaration blocks (≈ 20–30 entries each) | per country | forward, readers, sources.yaml, crosswalks | 2 + 3 judgement (USA) / 2.5 + 3 judgement (JPN) |
| C6 | Register entries in `sources.yaml` with verification status; `vintages.py` check paths for the new hosts | per country | config, vintages | 0.5 |
| C7 | Tests: ~15 literal sites (`test_endpoints.py:30,42`, `test_harvest_outputs.py:40-56`, `test_gate2.py:71,100`, `test_gate3.py:72,106`, `test_gate4.py:43,91,125-145`, `test_gate5.py:73`, `test_flat_files.py:271,314,604,748-763,793`); new reader tests; gate expectations per country | per country | tests | 1.5 |
| D1 | Debt engine edits: explicit branch in `intermediates.official_totals` (the `else` today runs the DEU path), `register.COUNTRY_MODULES`, `aggregates.class_aggregates`, `chains._subsector_items` for SNA subsectors, `reference.py` iterating `debt.yaml`, `validate.check_v31` list | one-off | debt/* | 1 |
| D2 | USA debt: Fiscal Data readers (auctions, MSPD, TIPS, FRN, interest expense, MTS), SOMA overlay, Z.1 step B, register builder, aggregates, `debt.yaml` perimeter/sub-types/year-ends (30 Sep memo), tests | per country | debt/readers, register_usa, aggregates_usa | 5 + 2 judgement |
| D3 | JPN debt: MOF xls readers (auctions, buy-backs, annual report, index ratios, floater coupons), BoJ holdings and FoF, position reconstruction with V30 `implied` flows, step A/B intermediates, tests | per country | debt/readers, register_jpn, aggregates_jpn | 6 + 3 judgement |

Totals (one builder, engineering-days): generalisation G1–G7 + D1 ≈ 8;
USA fiscal C1–C7 ≈ 12 (of which ≈ 6 judgement); USA debt ≈ 7; JPN fiscal
≈ 14 (≈ 7 judgement); JPN debt ≈ 9. First country ≈ 27–30 days including
the generalisation; second ≈ 20–23. Committee decisions (§8) gate the
judgement items and are not in these numbers.

Structural risks, in order: the cross-product universe (F2); the ESA-keyed
line cells in `lines.yaml` (no OECD/SNA key exists); Japan's FY anchor;
the collapse of strict forecasts to two years for both countries; the JPY
scale in charts and `_num` formatting; the debt `else` branch (D1).

---

## 7. Proposed order of work

1. **Generalise first (G1–G7, D1), against the existing three countries,
   with byte-identical `canonical/` as the acceptance test.** This is
   ≈ 8 days, changes no number, and turns "add a country" from a scatter
   of `elif`s into config plus readers. Session-sized.
2. **USA fiscal package** (C1–C7): the cleanest data, no language barrier,
   and it exercises every generalisation (structural zeros, a third anchor
   family, Oct–Sep conversion, a large stable WEO wedge). Stages 0–6 as in
   §12 of the kickoff, with Gate 3 expected to pass on the AMECO/OECD EO
   layer and the D7 declarations, and every federal source in maximum
   only.
3. **JPN fiscal package**: reuses the OECD family; adds the ESRI readers,
   the FY decision and the PDF ingestion (§11.4 second keying for the
   Cabinet Office and 2018 outlook tables, or the committee waives it for
   machine-extracted PDF tables — Q-R6).
4. **Debt extensions** in the same order. The US register is a stage on its
   own (largest register, but the Treasury API removes every access
   question the European offices raised). The Japanese register depends on
   Q-R8 (positions).
5. Notebooks, chart site and README regenerate from config once G7 is
   done; the forecast books need a seed copy per country and tree.

What is cheap to drop if the committee wants a smaller first cut: the debt
extensions (≈ 16 of ≈ 50 days); the pre-1970 US legs and the pre-2005
Japanese COFOG legs (all grade C, ≈ 3 days of crosswalk work); the federal
and central-cash maximum-only forecasts (≈ 4 days), leaving both countries
strict to 2027 on AMECO/OECD EO and pensions to 2120 for Japan.

---

## 8. Questions for the committee (Q-R)

Build defaults are stated; the build proceeds on them and records the
dependency in `HANDOFF.md`.

| # | Question | Default |
|---|---|---|
| Q-R1 | **D1 for non-ESA countries.** Anchor on the OECD SNA tables (11/12/10) — the national office's own data, re-presented on the SNA framework — or on the national publication (BEA NIPA / ESRI) with a documented re-grossing to the ESA total? | OECD tables as anchor (grade A); NIPA/ESRI as same-institution secondary and for years/lines the OECD tables lack. D1 amended, not contradicted: the institution is still the NSO. |
| Q-R2 | **Japan's COFOG basis.** (a) Convert the FY anchor to CY per §7.10 (grade B on every COFOG row, one year lost); (b) publish the Japanese COFOG tree on FY basis, labelled, with the CY trees beside it and a FY/CY bridge on TE; (c) CY throughout using quarterly ESRI totals to apportion by function (constructed, D13-adjacent). | (b): the FY tree is the official one; D3 is amended to "canonical basis is CY except where the anchor exists only on FY, in which case the tree is published FY-labelled and the bridge to the CY ledger is a deliverable". |
| Q-R3 | **Structural zeros.** Publish `R01`, `E04`, `GF05` for the US as zero rows typed `structural_zero` with a note, or omit them and make the line universe per-country? | Zero rows: identities, the decomposition and the flat-file shape stay uniform; the catalogue explains. |
| Q-R4 | **D.41 concept for Japan**: FISIM-adjusted (ESRI/OECD/AMECO, ESA-consistent) or FISIM-unadjusted (IMF GFS, ESRI GFS table)? A 17% wedge on `GF01_7`/`E05`. | FISIM-adjusted (ESA D.41); the unadjusted figure carried in `imf_value` and V21 warns on the wedge. |
| Q-R5 | **Federal- and central-only sources** (CBO, OMB, MOF, Cabinet Office CG+LG): register as §6.2 rank-4 dominant-component proxies in `maximum_extension` (as the OBR public-sector sources are treated, with `coverage_share` measured), or exclude them and let both countries end at 2027? | Register, maximum only, grade C; none in strict. |
| Q-R6 | **PDF-only Japanese sources** (Cabinet Office projection, 2018 outlook, MOF later-years estimate): §11.4 requires independent second keying. Waive it for tables extracted programmatically and verified against the document's own totals, or defer these sources to a manual-ingest phase? | Waive for machine-extracted tables whose row and column totals reproduce; log the extraction as the second check. |
| Q-R7 | **Blocked US hosts**: `www.cbo.gov` (10-year workbooks, NIPA-basis federal tables, the 30-year Long-Term Budget Outlook) and `www.ssa.gov` (OASDI trustees). Allowlist, hand-retrieve as with the OBR (D-S7-001), or proceed on the CBO GitHub mirror and Medicare only? | Proceed on the mirror and CMS; hand-retrieval route for CBO LTBO and SSA when the committee wants the long US legs (like OQ-6). |
| Q-R8 | **Japanese per-issue positions**: reconstruct from auction, buy-back and redemption flows (grade B `implied`, validated against BoJ holdings and by-type totals), or harvest the National Diet Library web-archive captures of the MOF outstanding-by-issue file as annual snapshots? | Reconstruct; register the web-archive captures as a cross-check where they exist. |
| Q-R9 | **Level II for the US** from BEA sub-functions (10.2 = retirement incl. survivors; 04.5 = transportation current + investment; 10.5 = unemployment; 01.7 = interest = GG D.41): accept as `level2_proxy_actual` grade B, or leave the US Level II lines empty (D7-style declaration)? | Accept, grade B, with the concept note per line; V19 identities hold by construction. |
| Q-R10 | **Scope of the first cut**: full replication (fiscal + debt, both countries, ≈ 50 days) or the fiscal package for the US first (≈ 20 days including the generalisation) with a go/no-go before Japan and the registers? | US fiscal first; decide the rest on its Gate 6. |

Access list for the record (all open today unless stated): BEA, Fiscal
Data, TreasuryDirect, OMB (browser headers), CMS, Federal Reserve, NY Fed,
BLS API, CBO GitHub mirror; **blocked**: cbo.gov, ssa.gov, github.com.
Japan: ESRI, Cabinet Office, MOF, MHLW, BoJ, BoJ time-series portal, NDL
web archive — all open.
