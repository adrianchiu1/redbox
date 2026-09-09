# Debt-in-issue extension — scoping note and questions for the committee

Prepared 2026-09-09, before any build. This note records (a) what the
committee asked for, as understood, (b) what the official sources actually
offer and which of them this environment can reach, (c) the proposed design,
and (d) the questions whose answers change the work. It is the debt-side
analogue of `COFOG_KICKOFF.md` §0–§2 and will be folded into a
`DEBT_KICKOFF.md` specification once the questions are answered.

Nothing in this note changes the existing pipeline. No source has been
registered and no data pulled.

---

## 1. What is being asked for

Add, for GBR, FRA and DEU, the **register of central-government marketable
debt securities**: every bond and bill ever in issue over the covered years,
with its coupon, type, maturity, notional outstanding through time, and the
issuance, redemption and buy-back flows that changed it. For floating-rate
and inflation-linked securities, carry the reference series they pay on.

Three uses, each a reconciliation:

1. **Interest.** For each year, the interest on each security, summed by type,
   reconciled to the aggregate interest line already in the package
   (`GF01_7`, general-government COFOG 01.7 / ESA D.41 payable).
2. **Net financing.** For each year, issuance less redemptions and buy-backs
   per security, summed to net securities financing, reconciled to net
   lending/borrowing (`NLB` in the balance ledger).
3. **Maturity profile.** For each year, notional outstanding by type
   (fixed bullet / floating / inflation-linked) in residual-maturity buckets
   0–1, 1–2, 2–3, 3–5, 5–7, 7–10, 10–15, 15–20, 20–30, 30+ years; and gross
   issuance by the same buckets, so the maturity of issuance can be tracked
   through time.

Direction of travel (parked): simulating alternative yield-curve paths
through this register onto the interest line.

## 2. Three conceptual wedges the design must carry explicitly

The register is central-government (S.1311) marketable securities, on a cash
and contractual basis. The package's `GF01_7` and `NLB` are general
government (S.13), consolidated, ESA accrual. Neither reconciliation can be
an identity; each is a **bridge** with official intermediate totals and a
reported residual, in the spirit of D16 (decompose, never force).

**Perimeter.** `GF01_7` includes local/state government and social-security
interest (material for DEU: Länder debt ≈ 30% of general-government debt),
interest on non-marketable central debt (NS&I; Bundesschatzbriefe and
Schuldscheindarlehen; dépôts des correspondants du Trésor), loans, and is
consolidated for intra-government holdings. The bridge needs one official
intermediate on each side: central-government cash interest from the
finance ministry, then S.1311 D.41 payable from the national accounts, then
S.13.

**Accrual vs cash vs coupon.** ESA D.41 is accrued; it includes the
indexation uplift on linkers as it accrues, amortises issuance premia and
discounts over the life of the bond (material in 2020–22 and again now),
records bill discount as interest, and excludes swap flows. A per-bond
coupon calculation gives contractual cash on coupon dates, or a day-count
accrual; both will be computed. Budget interest figures differ again:
the UK National Loans Fund is cash; French programme 117 books the
"charge d'indexation" annually but coupons on a cash basis; the German
Kapitel 3205 booked agio/disagio at value date until 2024 and spreads them
from 2025.

**Net financing vs net lending.** `NLB` (S.13 accrual) reaches net
securities issuance only through: other subsectors' balances → S.1311 B.9
→ cash–accrual timing and financial transactions (the stock-flow
adjustment: loans, equity injections, student loans, deposits, cash
balances) → central-government net cash requirement / besoin de
financement / Nettokreditaufnahme → financing by instrument (securities,
bills, non-marketable, loans, cash). Each step has an official source
(ONS Appendix S and REC2/REC3; AFT tableau de financement; Kreditaufnahme-
bericht annex 4.10; Eurostat EDP tables and SFA), so the residual can be
narrowed to what those sources leave unexplained.

## 3. Source findings (2026-09-09)

Full catalogues from the four research passes are condensed here. Every
"reachable" claim was tested from this environment with curl or the
server-side fetch; "blocked" means the egress proxy refuses the CONNECT.

### 3.1 Reachability

| host | status | what it carries |
|---|---|---|
| dmo.gov.uk (+ pwlb.gov.uk, crnd.gov.uk) | **blocked** | the entire UK bond-level register |
| aft.gouv.fr, data.gouv.fr (all subdomains), webstat.banque-france.fr, budget.gouv.fr, performance-publique.budget.gouv.fr, legifrance.gouv.fr, bdm.insee.fr, api.insee.fr | **blocked** | the entire French bond-level register, budget interest tables, financing tables |
| deutsche-finanzagentur.de, bundesbank.de, api.statistiken.bundesbank.de, genesis.destatis.de, bundeshaushalt.de, govdata.de | **blocked** | the entire German bond-level register, auction history, index ratios |
| data-api.ecb.europa.eu, ecb.europa.eu, emmi-benchmarks.eu, fred.stlouisfed.org, web.archive.org | **blocked** | €STR, Euribor, ECB HICP, no archive fallback |
| bankofengland.co.uk | reachable | APF per-ISIN operations, yield curves 1979–, SONIA, Bank Rate, IADB, millennium dataset |
| ons.gov.uk | reachable | RPI (both bases), CG debt by instrument 1975–, CGNCR financing by instrument 1997–, PSF reconciliation tables |
| gov.uk, assets.publishing.service.gov.uk | reachable | Debt Management Report (financing arithmetic 2008-09–), NLF/CF accounts 1996-97–, DMO annual reports 2007-08–2013-14 only |
| insee.fr (`/fr/statistiques/serie/ajax/{idbank}`) | reachable | CPI ex-tobacco (base 2015: 1990-01–2025-12; base 2025: 1996-01–), AFT aggregate debt series 2009– |
| ec.europa.eu (Eurostat API) | reachable | S.1311/S.13 D.41 payable 1995–; debt by instrument × holder × maturity (`gov_10dd_ggd`, `gov_10dd_rmd`: DE 1995–, FR 2020–); quarterly debt incl. S.13111 budgetary CG 2000Q1–; HICP ex-tobacco EA (`prc_hicp_minr`, I25, 1999-12–); 3m/6m EA money-market rate 1990–; long yields 1980–. UK absent from all government-finance flows. |
| bundesfinanzministerium.de | reachable (behind a bot manager: retries, cookies, browser headers) | **BMF Datenportal**: monthly Bund debt stock, gross issuance, redemptions and interest by instrument, 1996-01–, xlsx/csv; **Kreditaufnahmebericht** annual PDF with Epl. 32 interest bridge (annex 4.5), exact NKA derivation (annex 4.10), stock 1990–94 (annex 4.1); BMF Monatsbericht monthly tables incl. Eigenbestand flows; Haushaltsrechnung 1998– |
| sdmx.oecd.org | reachable | quarterly public-sector debt by instrument and maturity (S.1311 and S.13) FRA 1980Q4–, DEU 1991Q4–, GBR 1995Q1–; national 3m rates FRA 1970–, DEU 1960–, GBR 1986–; long yields 1956/1960– |

### 3.2 Bond-level data per country (all on blocked hosts)

**GBR — DMO.** No public API; an Umbraco data layer serves each report as
HTML/Excel/XML by `reportCode`. Core set: `D1A` gilts in issue (ISIN, name,
maturity, first issue, dividend dates, nominal, uplifted nominal, base RPI,
3-/8-month lag; coupon must be parsed from the name); `D1C` redeemed gilts
since 1981; `D2.1E` issuance history per gilt (date, method, price);
`D2.1A` auctions since 1998; `D2.1PROF7` other operations (switches,
conversions, reverse auctions); `D10A` syndications; `D5I` index-linked
cash flows (published coupon, reference RPI, index ratio per payment);
`D10C` index ratios; `D4L` government holdings; `D8B` future redemptions.
Historical month-end snapshots of `D1A` via a `COBDate` parameter
(unverified depth, likely 1998). Aggregate gilt sales by type and maturity
band every financial year since 1960-61. Conventions: `yldeqns.pdf`,
`igcalc.pdf`.

**FRA — AFT.** Current "encours détaillé" OAT / BTF / OAT€i pages with
Excel downloads (ISIN, libellé, encours, coefficient d'indexation, valeur
nominale, part démembrée, échéance). Auction history workbooks
(`..._hist_btf.xlsx` confirmed; OAT counterpart described but filename
unconfirmed) and monthly operations recaps (PDF) carrying the buy-back
leg. Indexation coefficients: OATi from 1998-07-25, OAT€i from 2001-07-25,
Excel, with a base-2015→base-2025 rebasing from the 2026-03-02
coefficients. **The only month-by-month historical line register is the
Bulletin mensuel, PDF only**, numbering consistent with a start around
1990 (inferred, not verified). No open-data mirror on data.gouv.fr. AFT
per-ISIN pages exist (`/fr/titre/{isin}`).

**DEU — Finanzagentur.** Downloadcenter with: **"Jährliche Einzelaufstellung
aller Bundeswertpapiere seit 1995" (xlsx, per ISIN, per year-end)**;
monthly "Umlaufende Bundeswertpapiere" (xlsx, incl. Eigenbestand);
"Emissionshistorie" (xlsx, per auction and ISIN, allotted and retained);
inflation-linked daily reference index and index ratios (two files: base
2015 and base 2025). No API. Pre-1995 per-bond data unlocated
(Bundesschuldenverwaltung era; Bundesbank Kapitalmarktstatistik PDFs at
best). Green twins carry separate ISINs. From 2025 the Bund's own
accounting spreads agio/disagio, so stock(t) ≠ stock(t−1) + gross − redemptions
in the BMF series from that year.

### 3.3 Aggregate targets for the three reconciliations (reachable)

| | GBR | FRA | DEU |
|---|---|---|---|
| CG cash interest | NLF Account (PDF, 1996-97–); ONS `NMFX` (accrued, 1946–), `MW7L` uplift (1981–) | programme 117 RAP (blocked); Compte général de l'État (blocked) | Kreditaufnahmebericht annex 4.5 incl. Kap. 3205 (1996–); BMF Datenportal `rpgZinsen` monthly |
| S.1311 D.41 payable | ONS PSA6B_2 | Eurostat `gov_10a_main` S1311 (1995–) | Eurostat `gov_10a_main` S1311 (1995–) |
| S.13 D.41 / `GF01_7` | in package | in package | in package |
| CG net cash requirement and financing by instrument | ONS Appendix S table 1.2A (1997-98–, ESA codes per column); `M98R` (1984–); DMR table 3.A/A.2 | AFT tableau de financement (blocked); Eurostat `F_GD` transactions | Kreditaufnahmebericht annex 4.10 (Soll/Ist to the cent, Eigenbestand line); BMF Datenportal |
| Debt stock by instrument | ONS PSA8A_1 (`BKPM` gilts 1975–) | Eurostat `gov_10q_ggdebt` S13111 (2000Q1–); INSEE/AFT aggregates (2009–, fixed vs linked) | BMF Datenportal (1995-12–, fine instrument tree, Eigenbestand, 3 maturity bands); Eurostat |
| Residual-maturity buckets (cross-check) | OECD T7PSD (short/long only) | Eurostat `gov_10dd_rmd` (2020–) | Eurostat `gov_10dd_rmd` (1995–) |
| Central-bank holdings | BoE APF purchases (2009–) and sales (2022–) per ISIN; maturity profile by gilt | Eurostat `gov_10dd_ggd` holder S121 (aggregate) | same |

### 3.4 Reference series

| need | source | status |
|---|---|---|
| UK RPI, Jan-1987=100 (`CHAW`, 1987–) and long run (`CDKO`, 1947–, Jan-1974=100; rescale for pre-1987 base RPIs) | ONS | reachable |
| France CPI ex-tobacco, France entière (base 2015 idbank 001763852, 1990–2025; base 2025 idbank 011814056, 1996–) | INSEE ajax endpoint | reachable; chaining across bases must be done here (INSEE publishes no link) |
| Euro-area HICP ex-tobacco (`prc_hicp_minr`, coicop18 `TOT_X_TBC`, I25, EA changing composition, 1999-12–) | Eurostat | reachable; the contractual references are the debt offices' unrevised daily index ratios, this is the cross-check |
| SONIA (1997–), Bank Rate (1975–, and 1694– in `baserate.xls`) | BoE IADB | reachable (HTML table, not CSV on the wire) |
| GBP LIBOR history | none official reachable | gap (1990s floating-rate gilts) |
| EA 3m/6m money-market (1990–), national 3m FRA 1970– / DEU 1960– | Eurostat, OECD | reachable |
| €STR, Euribor fixings | ECB, EMMI | blocked |
| TEC10 (OAT TEC10 reference, 1996–) | AFT, Banque de France | blocked; Eurostat/OECD 10y yields are not substitutes for the fixing |
| Yield curves | BoE nominal 1979–, real 1985–, OIS 2009– | reachable; Bundesbank Svensson curve blocked; no French official curve reachable |

### 3.5 Achievable history depth (machine-readable, if the hosts are opened)

| | positions per security | flows per security | aggregate only |
|---|---|---|---|
| GBR | 1998– (month-end, `COBDate`, to verify); redeemed register 1981– | issuance history per gilt (full), auctions 1998–, other ops 1998– | issuance by type/band 1960-61–; gilt stock 1975– |
| FRA | current snapshot as xlsx; history only via Bulletin mensuel PDFs (~1990–, inferred) | BTF auction history xlsx; OAT auction history (unconfirmed filename); buy-backs from monthly PDFs | 2009– (INSEE), 1995– (Eurostat) |
| DEU | 1995– (year-end, one xlsx); month-end current | Emissionshistorie xlsx (depth unverified, likely ≥2000) | 1996-01– monthly (BMF), 1990–94 year-end (annex 4.1) |

## 4. Proposed design

Same package, same conventions. A new subpackage `ggfiscal.debt` with the
existing layering (register → immutable snapshots → standard → canonical →
validation → flatten → notebook), so the data is called the way the rest
of the package is called: flat CSVs in `deliverables/`, catalogued in the
data dictionary, with a derivation sentence per row, and a notebook that
reproduces the reconciliations from the flat files alone.

**Config.** `config/debt.yaml`: per-country perimeter, instrument taxonomy,
reference-series mapping, bucket edges, reconciliation chain (which
official total sits at each bridge step). `config/sources.yaml` gains the
new register entries (`UK_DMO_*`, `FRA_AFT_*`, `DEU_FINANZAGENTUR_*`,
`BOE_APF`, `BOE_YIELD_CURVES`, `BOE_IADB`, `BMF_DATENPORTAL`,
`BMF_KREDITAUFNAHMEBERICHT`, `ONS_PSF_APPENDIX_A`, `ONS_PSF_APPENDIX_S`,
`HMT_DMR`, `HMT_NLF`, `EUROSTAT_GOV10DD_*`, `EUROSTAT_PRC_HICP`,
`INSEE_IPC`, `OECD_T7PSD`, `OECD_FINMARK`).

**Canonical tables** (long format, pandera-enforced, one grade column,
`source_id` + snapshot hash on every row):

| table | key | content |
|---|---|---|
| `debt_securities` | (iso3, isin) | static: name, sub-type, instrument class {fixed_bullet, floating, inflation_linked, bill, undated, callable}, coupon, frequency, day count, first issue, maturity, currency, index reference and lag, base index, floating reference and spread, green flag |
| `debt_positions` | (iso3, isin, as_of) | nominal outstanding, uplifted nominal, official/own holdings, market outstanding; month-end where the source allows, year-end (31 Dec; 31 Mar memorandum for GBR) always |
| `debt_flows` | (iso3, isin, date, flow_type) | auction / syndication / tap / tender / conversion in and out / switch / buy-back / redemption / retention; nominal, cash proceeds, price, yield |
| `debt_reference_series` | (series_id, date) | RPI (spliced bases), FR CPI ex-tobacco (chained bases), EA HICP ex-tobacco, index ratios and coefficients as published, SONIA, Bank Rate, EA 3m, national 3m, TEC10 if obtained |
| `debt_interest_by_security` | (iso3, isin, year, basis) | basis ∈ {accrued, cash}: coupon interest, indexation uplift, bill discount accretion, floating coupon; with the reference values used |
| `debt_interest_reconciliation` | (iso3, year, step) | Σ securities by class → CG cash interest (official) → S.1311 D.41 (official) → S.13 `GF01_7` (package); each bridge item from its source, one residual per step |
| `debt_financing_reconciliation` | (iso3, year, step) | Σ (issuance − redemption − buy-back ± conversion) → CG net cash requirement and its financing by instrument (official) → S.1311 B.9 via SFA components (official) → S.13 `NLB` (package) |
| `debt_maturity_profile` | (iso3, as_of, class, bucket) | nominal, uplifted, market-hands; residual maturity at the as-of date |
| `debt_issuance_by_bucket` | (iso3, year, class, bucket) | gross nominal and cash; residual maturity at issue date |
| `debt_central_bank_holdings` | (iso3, isin or aggregate, as_of) | BoE APF per ISIN from operations; EA aggregates from Eurostat holder S121 |

**Validation** (new IDs continuing the §10 numbering): register
completeness (every position has a security; every flow has a security);
position recurrence per ISIN (`pos(t) = pos(t−1) + Σflows`, tolerance, with
the 2025 German accounting switch and index uplift handled explicitly);
sum of positions vs official debt-by-instrument stock; sum of interest vs
each bridge total with the residual reported; bucket sums equal totals;
cross-check of buckets against Eurostat `gov_10dd_rmd` and OECD; reference
index cross-check (published index ratio vs ratio recomputed from the
statistical index).

**Grades.** Debt-office row = A. Flow derived from a position difference =
B. Aggregate-only year (pre-register) = C, carried only where the
committee wants the aggregate history. Bridge residuals are reported, not
graded.

**Deliverables.** `deliverables/debt_securities.csv`, `debt_positions.csv`,
`debt_flows.csv`, `debt_interest_by_security.csv`,
`debt_interest_reconciliation.csv`, `debt_financing_reconciliation.csv`,
`debt_maturity_profile.csv`, `debt_issuance_by_bucket.csv`,
`debt_reference_series.csv`; the aggregate interest-by-class and
outstanding-by-class series appended as columns to `strict_{ISO}.csv`;
`notebooks/debtbook.ipynb` (register walk-through, the three
reconciliations reproduced from the bundle, maturity-bucket charts by year).

**Interest computation.** Accrued: actual/actual by coupon period, pro-rata
to calendar year, on the nominal outstanding on each day (positions
interpolated from month-end snapshots and dated flows). Cash: coupon on
each dividend date on the nominal outstanding at the record date. Linkers:
coupon × index ratio on the payment date, uplift accrual = Δ(uplifted −
nominal) over the year; the debt office's published ratios are primary,
the statistical index recomputation the cross-check. Bills: discount
accreted linearly. Floating: reference fixing per the security's terms;
where the fixing history is not obtainable (GBP LIBOR 1990s) the
security's interest is carried as `not_computable` and the gap goes to the
bridge residual, never filled.

**Yield-curve simulation (parked).** The register carries what the
simulation will need: per-security terms, day counts, positions, and the
issuance-by-bucket history for a refinancing rule. Yield-curve history is
stored only where reachable (BoE).

## 5. Questions for the committee

Each with the default the build will assume if the committee simply says
"defaults".

**Q-D1 — Access.** Nothing bond-level is reachable. Options: (a) allowlist
`dmo.gov.uk`, `aft.gouv.fr`, `deutsche-finanzagentur.de`, and ideally
`bundesbank.de`, `webstat.banque-france.fr`, `data-api.ecb.europa.eu`,
`budget.gouv.fr`; (b) hand-retrieve the file sets listed in §6 via
`ggfiscal ingest-file`, as was done for OBR. Default: (a). The UK month-end
position history alone is a loop of several hundred pulls, and every
vintage refresh repeats it; hand retrieval does not scale to that.

**Q-D2 — Perimeter.** Central-government marketable securities including
bills (T-bills, BTF, Bubills) and foreign-currency issues; excluding
sub-national bonds (Länder, collectivités), non-marketable instruments
(NS&I, Bundesschatzbriefe, Schuldscheine, correspondants du Trésor) and
loans, which appear only as bridge lines in the reconciliations. Default:
as stated. Alternative: Länder bonds as a second register for DEU (large,
but no reachable per-bond source was found).

**Q-D3 — Interest concept and target.** Compute both accrued and cash per
security; treat indexation uplift as interest (ESA); reconcile in three
steps ending at `GF01_7`, with the finance-ministry cash figure and the
S.1311 D.41 figure as the official intermediates. Default: as stated.
Alternative: stop at the S.1311 step and show the S.13 gap as one line.

**Q-D4 — Net financing target.** `NLB` cannot be matched directly; the
chain is net securities financing → CG net cash requirement (and its
financing by instrument) → S.1311 B.9 (via stock-flow adjustment items) →
S.13 `NLB`, residual reported at each step, never allocated. Default: as
stated. Alternative: reconcile only to the CG cash requirement and report
the `NLB` gap as one unexplained line.

**Q-D5 — Period basis.** Calendar year throughout (D3); positions at
31 December; flows by settlement date. For GBR, 31 March positions and
financial-year flows as memorandum columns, since ONS, DMO and the DMR are
all financial-year. Default: as stated.

**Q-D6 — Maturity conventions.** Stock bucketed by residual maturity at the
as-of date; issuance bucketed by residual maturity at issue date (a tap of
a 2038 line in 2024 is a 14-year issue), not by the line's original
maturity; linkers at uplifted nominal with unindexed nominal alongside;
undated gilts in 30+; callable and double-dated at final maturity; bills in
0–1; market-hands (net of DMO/APF/Eigenbestand holdings) shown beside
total. Default: as stated. If the committee wants original-maturity
bucketing for issuance as well, both can be produced.

**Q-D7 — History depth and the PDF rule.** Machine-readable only gives
per-security history from 1981/1998 (GBR), ~2001 (FRA), 1995 (DEU) and
aggregates from 1960-61 / 1995 / 1990. Earlier per-security history exists
only in PDF (AFT Bulletin mensuel ~1990–, Bundesbank Kapitalmarktstatistik).
§11.4 requires independent second keying of hand-keyed tables, which
OQ-5 has never been able to supply. Options: (a) phase 1 machine-readable
only, aggregates carried at grade C for earlier years; (b) authorise
machine table extraction from PDFs under a relaxed §11.4 (extraction plus
a totals check against the published aggregate, instead of second keying),
graded B. Default: (a), with (b) as a later phase if wanted.

**Q-D8 — Central-bank holdings.** Include the BoE APF per-ISIN overlay
(reachable, 2009–) and euro-area aggregate holdings by S.121 (Eurostat)?
Default: yes. It is cheap, it is needed for market-hands, and the APF
unwind matters for the eventual simulation.

**Q-D9 — Packaging and process.** Same package (`ggfiscal.debt`), a
`DEBT_KICKOFF.md` specification written for sign-off first, decisions
logged in `DECISIONS.md`, validation IDs continuing the §10 numbering,
gated build stages as before. Default: as stated. Alternative: a sibling
package sharing the config and store.

**Q-D10 — Yield-curve history now or later.** Store the BoE curves
(nominal 1979–, real 1985–, OIS 2009–) in this phase as reference series,
and leave FRA/DEU curves until their hosts are reachable? Default: yes to
BoE now.

**Q-D11 — Reference-rate gaps.** GBP LIBOR (for the 1990s floating-rate
gilts), €STR/Euribor fixings and TEC10 have no reachable official source.
Accept `not_computable` on the affected securities' interest with the gap
in the residual, or hand-retrieve the fixings? Default: accept, and
revisit when hosts are opened. (The affected notional is small: FRGs were
a few £bn; OAT TEC10 peaked around €20bn; no German floaters of note.)

## 6. Hand-retrieval lists if the hosts stay blocked

Ordered by necessity; page URLs where the export button lives, direct
export URLs where the report code is known.

**GBR — dmo.gov.uk.** `D1A` (XML preferred: `/data/XmlDataReport?reportCode=D1A`),
`D2.1E`, `D1C`, `D1D`, `D5I`, `D2.1A`, `D2.1PROF7`, `D10A`, `D2.1PROF9`,
`D4L`, `D8B`, `D10C`, `D9C` (all `/data/ExportReport?reportCode=…`); the
four reports on `/data/gilt-market/gross-and-net-issuance-data/`
(especially cash sales by type and maturity since 1960-61); month-end
`D1A` snapshots via
`/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=DD%2FMM%2FYYYY`;
`/media/1sljygul/yldeqns.pdf`, `/media/0ltegugd/igcalc.pdf`; annual
reviews and DMA accounts from `/publications/`.

**FRA — aft.gouv.fr.** The Excel behind `/fr/encours-detaille-oat`,
`/fr/encours-detaille-btf`, `/en/encours-detaille-oatei`; the whole
Bulletin mensuel archive from `/fr/bulletins-mensuels` (modern files under
`/files/medias-aft/7_Publications/7.2_BM/`, legacy under
`/files/archives/attachments/`); auction workbooks from
`/fr/dernieres-adjudications` and `/fr/dernieres-adjudications-archives`
(BTF example: `/files/medias-aft/3_Dette/3.4_BTF/2025-01_hist_btf.xlsx`);
monthly operations recaps under
`/files/medias-aft/3_Dette/3.5_Adjudications et autres opé/3.5.6_Recap mensuels/`;
indexation coefficients (current and historical files) from
`/fr/oati-principaux-chiffres` and `/en/oateuroi-key-figures`; annual
reports from `/fr/rapports-activite`; the tableau de financement from
`/fr/plf-{year}`. From budget.gouv.fr: programme 117 RAP per year.

**DEU — deutsche-finanzagentur.de.** From `/downloadcenter`: "Jährliche
Einzelaufstellung aller Bundeswertpapiere seit 1995" (xlsx),
"Einzelaufstellung aller umlaufenden Bundeswertpapiere zum Monatsultimo"
(xlsx), "Emissionsergebnisse Jahreshistorie" and "aktuelles Jahr" (xlsx),
Emissionskalender; from
`/bundeswertpapiere/bundeswertpapierarten/inflationsindexierte-bundeswertpapiere`:
both index-ratio files (base 2015 and base 2025). Indexed direct paths
worth trying first:
`/fileadmin/user_upload/Institutionelle-investoren/auktionen/emissionshistorie_dt.xlsx`,
`/fileadmin/user_upload/Institutionelle-investoren/auktionen/emissionsergebnisse_aktuell_dt.pdf`.

## 7. Build phases once the questions are answered

1. `DEBT_KICKOFF.md` (spec addendum) for sign-off; register entries;
   fetch layer for every reachable source; hand-retrieval or allowlist for
   the rest.
2. Reference series and aggregate targets (all reachable today): RPI, CPI,
   HICP, rates, BoE APF and curves, ONS PSF tables, BMF Datenportal and
   Kreditaufnahmebericht, Eurostat and OECD debt tables. Gate: every
   aggregate target loaded and cross-checked against the package's
   `GF01_7` and `NLB`.
3. Register and positions per country; validation of recurrence and stock
   totals. Gate: Σ positions reproduces the official debt-by-instrument
   stock within tolerance every year-end.
4. Interest by security and the interest bridge. Gate: each bridge step's
   residual tabulated and explained or declared.
5. Flows and the financing bridge; maturity profile and issuance buckets.
   Gate: bucket totals reproduce the register; cross-checks against
   Eurostat/OECD reported.
6. Flatten, dictionary, notebook, README; vintage detection for the new
   sources.

Model allocation follows §16: readers, fixtures and tests to the smaller
tier; perimeter, grading, bridge design and gate reviews to the strongest.
