# HANDOFF.md

Rewritten 2026-09-10, end of session 9 (the debt-in-issue extension, on
`claude/stoic-dijkstra-bc42s1` branched from the merged `main` at 6441366).

## Current stage

**Debt extension (DEBT_KICKOFF.md v1.0): D0–D5 complete on the per-security
register for Germany (D-S10-004) and the United Kingdom (D-S10-005); France
has a snapshot register from the AFT pages (D-S10-006) and runs on the DD8
aggregate layer in the chains until the auction history arrives (OQ-8).** The
parent package is untouched except: `config.sources()` merges
`config/debt_sources.yaml`; the snapshot store names pdf/html extensions;
pypdf, cffi, bs4 are dependencies. Parent baseline still 120 passed (the
three validation tests are order-sensitive when a build runs concurrently —
rerun alone).

## What session 9 did (D-S10-005)

- **DMO access.** The export endpoint clears the ShieldSquare challenge for
  `browser.py`; each report exports in exactly one presentation type
  (`families/debt_offices.DMO_FORMATS`), every other request returns a
  35-byte stub that the family, `ingest-incoming` and the desktop script now
  refuse. 14 reports snapshotted; D1D/D5I/D9C/D2.2A export in no format; the
  `COBDate` year-end snapshots do not work by URL.
- **`readers/dmo.py` + `register_gbr.py`**: 1,747 securities, 4,404 year-end
  positions 1981–2025 rolled from the operations record and anchored on D1A
  (in issue) / D1C (nominal at redemption), 8,173 flows, 10,562 index-ratio
  points recomputed from the ONS RPI (D10C reproduced to 5 dp). Recurrence
  exact on 3,499 year-end pairs; IL unindexed nominal = DMR to the million
  2023–2025; conventional gilts 8% above the consolidated ONS/DMR stock
  (OQ-9).
- **Chains**: `config/debt.yaml` `register_chain_items` — the register's
  interest basis and step-A bridges per country (GBR accrued, no value-date
  items; DEU cash with the two BMF items); new financing bridge
  `issuance_cash_less_nominal`. UK interest step A within ±3.3 £bn 2010–2024
  (three years 5–8); financing step A within ±13 £bn except 2022 and
  2008–09 (OQ-9 wedge).
- Tests: `tests/debt` 200 passed, 6 skipped (13 new GBR); deliverables and
  README regenerated; notebook re-executed with a register section.

## Session 9, second part (D-S10-006): France

- Nine AFT pages saved by the committee (Cloudflare challenges every
  automated navigation, static files included) → `readers/aft.py`,
  `register_fra.py`: 101 securities, positions at the retrieval date, the
  month's auctions as flows. Snapshot register: it does not enter the
  chains (full-year coverage rule in `register.register_sums`), France
  stays on the aggregate layer until the auction history is saved
  (DOWNLOAD_LIST.md second round).
- Maturity profile now also at each office's latest snapshot.

## Sessions 7–8 in brief

- Session 7: `DEBT_SCOPING.md` → `DEBT_KICKOFF.md` v1.0; `ggfiscal.debt`
  families, engines (§7 interest, DD7 maturity, §8 chain assembler), the
  aggregate layer, chains, validate, flatten, notebook (D-S10-001/002/003).
- Session 8: Finanzagentur harvested; `register_deu.py`; `register.py`
  assembles interest by security, maturity profile, issuance by bucket and
  the computed register sums; ECB/Bundesbank family (D-S10-004).

## Blocked on whom

- **OQ-8 (committee)**: the AFT second round (DOWNLOAD_LIST.md): the OATi
  encours page, `historique-adjudications` and its files, the six
  coefficient/index files, the key-figure pages — saved by hand (the desktop
  script is challenged on every navigation), committed under
  `data/incoming/`, then `ggfiscal debt ingest-incoming`; and, when
  convenient, the DMO page's own export link for a past close-of-business
  date.
- **OQ-9 (committee)**: an official series of gilts held by CG bodies (DMA,
  CRND) would turn the register-vs-ONS wedge into a holdings overlay.
- Q-D7 (committee, later): PDF extraction rule for pre-register years.

## Exact next command

```
ggfiscal debt fetch --family debt_offices   # DMO through the browser session; AFT will FAIL until OQ-8
ggfiscal debt build && ggfiscal debt validate && ggfiscal flatten
python3 -m pytest tests/debt -q
```

Next build steps: (1) FRA history once the second round is ingested —
`register_fra.py` gains the auction history (`readers/aft.auctions_all`
already reads every adjudications page in the store), positions rolled back
from the snapshot through the flows as in `register_gbr.py`, ratios from the
coefficient files' base indices recomputed on `FR_CPI_XT` / `EA_HICP_XT`
(the DMO-style 3-month-lag formula is in `register_gbr.reference_rpi_3m`);
then the full-year rule in `register.register_sums` lets France into the
chains by itself; (2) per-ISIN APF holdings from the BOE_APF snapshots into
`official_holdings_lcu_mn` (DD11); (3) the LIBID fixings for the two
floating-rate gilts if a source appears (DD10).

## Data facts future sessions must not rediscover (debt)

- DMO export endpoint: `GetDataExport?reportCode=X&exportFormatValue=xml|xls
  &parameters=&COBDate=` — one format per report (DMO_FORMATS); the report
  HTML pages re-challenge the headless browser, the export endpoint does not
  once the challenge has cleared on `XmlDataReport?reportCode=D1A`.
- D2.1E (issuance history) carries signed nominals: creations positive,
  cancellations/reverse auctions negative, conversions and switches both
  signs; `ACTUAL_DATE` is the settlement date; prices are clean. Tranche
  ISINs (`… 2007 A`) are assimilated into the parent — fold them.
- D1C lists redeemed gilts by name only (no ISIN): join on
  `readers.dmo.name_key` (coupon | IL/CV | years, tranche dropped). Gilts
  converted or switched out in full before 2000 appear nowhere.
- Index ratios: reference RPI(d) = RPI(m−3) + (d−1)/days(m) × (RPI(m−2) −
  RPI(m−3)), base = reference RPI at first issue; `UK_RPI` is on Jan 1987 =
  100 and reproduces D10C exactly. 8-month linkers: RPI(m−8).
- The NLF accounts are accruals-based: the UK register enters the interest
  chain on the accrued basis (uplift accrual and amortisation included);
  never add the BMF value-date bridges to the UK.
- ONS Appendix S / PSA8A_1 gilt rows (F.332) are consolidated within CG;
  HMT DMR table A.1 likewise. The register is gross (OQ-9).
- UK bills: one security per maturity date (fungible); bilateral/ad hoc
  bills are outside the tender history, so the register bill stock is
  below ONS BKPJ after 2006.
- The financing chain runs in NET-BORROWING sign: steps B and C carry
  −B.9 / −NLB (basis says so). Register selection per country lives in
  `config/debt.yaml`; DEU special funds are subtracted at step A and
  added back at step B; the Mitfinanzierung item is interest-only.
- Kreditaufnahmebericht annex 4.10: 2019–2025 parse and close to the
  euro; 2013–2018 have no annex (narrative-table NKA, narrower concept);
  rows may carry 2 cells (Soll blank) and labels wrap both ways.
- ONS REC2's RUUX is CGNCR incl. NRAM/B&B/Network Rail; PSA7C (M98W,
  MUI2, ABEC, ABEI) bridges it to M98R. PSA2 −NMOE is LG net borrowing;
  PSA6J NUGW is LG interest. No intra-GG consolidation line is published.
- Eurostat EDP identity: GD_CH = B9_T3 + F_ASS + ORADJ + YA3 (KX and K61
  are inside ORADJ); edpt3 starts FR 2021 / DE 2022.
- BMF Datenportal flow sheets are cumulative year-to-date (December = full
  year); Tilgungen/Zinsen are negative; values in whole euro. Indent-0
  totals: "Kredite … inklusive Mitfinanzierung" is the wider total the
  instrument tree sums to. From 2025 stock(t) ≠ stock(t−1)+gross−redemptions
  (agio/disagio spreading, +9.9 EUR bn wedge in 2025).
- Kreditaufnahmebericht annex numbering moves by edition: match on title.
  Annex 4.5 (2025 edition) carries Verzinsung 1996–2025 and agrees with the
  Datenportal to 0.5 EUR mn; annex 4.10 parses 2020–2025 only.
- BMF host: Radware bot manager — fresh session, de-DE headers, Referer,
  same-host redirects only, up to 8 retries; large PDFs need Range resume;
  HTML carries per-request `__uzdbm_*` tokens (never hash-stable).
- ONS PSA sheets: locate header/CDID rows by column-A stub, never by
  offset; period labels are `1998`, `Apr 1997 to Mar 1998`, `Apr to Jun
  1997`, `2026 Jul`. PSA CY blocks start 1998; PUSF NMFX annual goes to
  1946; M98R monthly from 1984-04 sums to calendar years directly.
- NLF accounts: 18 of 20 editions parse (2006-07, 2007-08 have no
  ToUnicode map); 2012-13's printed total does not add up (restated in
  2013-14). Finance costs are accrual; "Interest paid" is the cash line.
- RPI: CHAW (Jan 1987=100) from 1987; CDKO (Jan 1974=100) from 1947-06;
  splice factor 100/394.5, constant to 4 dp over the 475-month overlap.
- INSEE: `serie/ajax/{idbank}` returns the full history as an HTML table;
  the csv route 500s; bdm.insee.fr is blocked. FR CPI ex-tobacco base
  2015→2025 chain factor 0.834606 over 360 months.
- Eurostat: gov_10dd_ggd key order freq.na_item.sector2.sector.maturity.
  unit.geo; FR structure-of-debt tables start 2020; DE rmd has 4 of 7
  bands and S1311 from 2004; HICP coicop code is TOT_X_TBC (dimension
  `coicop18` in prc_hicp_minr, `coicop` in the midx archive); UK absent.
- BoE: media CDN 403s a bare requests UA — send browser headers; IADB
  `_iadb-fromshowcolumns.asp` returns CSV when Datefrom ≥ series start,
  else HTML/302; curve workbooks: spot sheet, maturities row 4, dates from
  row 6.
- AFT: the encours pages are HTML tables (no Excel behind them); libellés
  carry coupon and maturity (`readers/aft.parse_libelle`); French amounts
  use space thousands and comma decimals, the English OAT€i page uses
  commas and a `.00`; auction pages are attribute rows × lines, ISIN last;
  `Volume total émis = adjugé + ONC`. The site challenges every automated
  navigation and its `/files/` downloads; a person's browser passes once
  per page.
- Playwright/Chromium through the agent proxy: `--disable-quic`,
  `--disable-features=PostQuantumKyber,UseMLKEM,EncryptedClientHello`,
  `--ssl-version-max=tls1.2`; never `pkill -f` a pattern that matches your
  own shell command line (it kills the session's shell).
