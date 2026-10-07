# Extension to Italy, Spain and Belgium
## Specification v2.5 addendum and gated build plan — extension to `COFOG_KICKOFF.md`, `DEBT_KICKOFF.md` and `REPLICATION_KICKOFF.md`

Prepared 7 October 2026 at the committee's request ("take the current
approach for France and Germany and extend to Italy, Spain and Belgium").
The committee's answers to the four scoping questions are recorded as
DE1–DE4 below. Where this document is silent, `COFOG_KICKOFF.md` v2.2 with
the v2.3 addendum governs the fiscal package, `DEBT_KICKOFF.md` v1.0 the
debt extension, and `REPLICATION_KICKOFF.md` the generalised architecture
(anchor families, `countries.yaml`, stage gating). Nothing here changes a
number for GBR, FRA, DEU or USA: every stage's acceptance test is that it
does not (`tools/byte_identity.py --countries GBR,FRA,DEU,USA`).

---

## 1. Mission and scope

Produce for Italy (`ITA`), Spain (`ESP`) and Belgium (`BEL`), all EUR,
everything the package produces for FRA and DEU: the three trees (17 COFOG
lines, 9 ESA-economic-type lines, 15 ESA-revenue lines), the balance
ledger, both variants, backward and forward extension, the IMF WEO
reconciliation, the flat files and catalogue; then the debt extension.

The three countries are euro-area ESA 2010 reporters. Their anchors are the
same Eurostat tables as FRA/DEU (`gov_10a_exp`, `gov_10a_main`,
`gov_10a_taxag`, `nama_10_gdp`) served by the existing `EurostatFamily`;
their forecast sources are the same EU-wide sources (AMECO, the 2024
Ageing Report, the Debt Sustainability Monitor 2025). The work is
therefore configuration plus the removal of the remaining FRA/DEU literals,
not a new family.

**Build order (DE2).** These three countries go before the USA's U1.
Stages E0–E6 (fiscal) then ED0–ED5 (debt), built from `main`. The USA
stays at `stage_reached: 0` meanwhile and its numbers must not move.

---

## 2. Decisions taken

**DE1 — Debt layer for every country.** All three countries get the debt
extension (`DEBT_KICKOFF.md` §1 scope), not the fiscal package alone.

**DE2 — Order.** ITA/ESP/BEL before USA U1; built from `main`.

**DE3 — Level II before 2001 from IMF GFS, as for Germany.** Eurostat
`gov_10a_exp` publishes the four COFOG Level II groups (01.7, 04.5, 10.2,
10.5) for ITA and BEL from 2001 only (ESP from 1995; measured 2026-10-07).
The 1995–2000 years come from the generic IMF GFS COFOG backward leg
(`backward_legs.gfs_cofog`, R0 step 6, D-S15-006) exactly as DEU's
1995–99 do: the same national data redistributed, coverage measured at the
boundary, grade by the parent rules. Where GFS itself has no group series
for a year, the line starts where the data start; nothing is
interpolated. *Measured in Stage E (D-S17-005): the IMF GFS groups, and
OECD Table 11's, also start in 2001 for ITA and BEL, so — as for DEU,
whose groups start in 2000 — the leg is enabled and applies nothing;
GF01_7 has 1995–2000 from the D.41 fallback (OQ-18).*

**DE4 — Spain's debt from the Banco de España.** `www.tesoro.es` fails TLS
verification from this environment (the server does not send its
intermediate certificate). Spain's debt aggregates come from the Banco de
España Boletín Estadístico chapter 11 (`be.zip`, monthly PDE debt by
sub-sector and instrument; reachable, machine-readable). A per-security
Spanish register is out of scope until a reachable per-ISIN source exists
(the DD8 aggregate path applies).

**DE5 — EU-wide forecast sources apply by registration.** Whether a country
takes the Ageing Report and DSM legs is read from the `countries` list of
`EC_AGEING_2024` / `EC_DSM` in `config/sources.yaml` — the FRA/DEU
literals in `forecast/forward.py` and `coverage.py` are removed. National
forecast sources (AIReF, UPB, the Federal Planning Bureau) are not
reachable (egress policy) and are declared `source_blocked` where a line
would otherwise use them; the strict/maximum variants then rest on the
EU-wide sources as for FRA.

**DE6 — Eurostat geo codes from config.** `eurostat_geo` per country in
`countries.yaml` replaces the three `{"FRA": "FR", "DEU": "DE"}` maps
(`ingest/endpoints.py`, `standardise/readers.py` ×2).

---

## 3. Country traps

- **ITA** — Level II from 2001 (DE3). Large D.41 share; interest is the
  dominant GF01 component. BTP Italia / BTP€i / BTP Valore retail lines
  are inflation-linked or step-up — class mapping in `debt.yaml`
  `sub_types`. MEF publishes per-class composition monthly (CSV) and the
  12-month maturity schedule per class (CSV); per-ISIN outstanding is not
  published as a file (auction results are HTML per auction).
- **ESP** — Level II from 1995. Tesoro blocked (DE4). Regional
  government (S1312) is large; S1311 is the debt perimeter.
- **BEL** — Level II from 2001 (DE3). Federal/community/regional split:
  the Debt Agency issues for the federal state; S1312 issues separately.
  The BDA publishes the OLO lines with net outstanding per ISIN (HTML),
  the maturity schedule and the debt indicators (xlsx).

---

## 4. Build stages and gates

Each stage ends with `pytest` green on what this container can run,
`ggfiscal validate` with no ERROR, `DECISIONS.md` entries, `HANDOFF.md`
rewritten, and GBR/FRA/DEU/USA byte-identical (run_id excepted).

### Stage E0 — Verify and harvest
Register the three countries on every EU-wide source; pull; measure
first/last year per (line, source); WEO base-year bridge.
**Gate E0:** every line has programmatic coverage; bridge on the latest
WEO vintage; coverage report.

### Stage E1 — Canonical history
The three trees and ledger from the Eurostat anchors.
**Gate E1:** 41 lines + ledger 1995–2024; parent V-suite green.

### Stage E2 — Backward extension
IMF GFS COFOG legs for Level II 1995–2000 (DE3).
**Gate E2:** every stitch has a boundary record, grade and V5.

### Stage E3/E4 — Strict and maximum-extension forecasts
AMECO, Ageing Report and DSM legs by registration (DE5); declarations
for every line without a source.
**Gate E3/E4:** V10–V16 green; every unforecast line declared.

### Stage E5 — Reconciliation
§8.2 bridge and §8.3 decomposition on all WEO vintages.

### Stage E6 — Packaging
Flat files, catalogue, small multiples; notebooks by the R0 tooling.

### Stage ED0 — Debt sources verified
Register MEF (ITA), BDA (BEL), Banco de España (ESP) and Eurostat
`gov_10q_ggdebt` for the three; pull and record.

### Stage ED1–ED2 — Official totals and class aggregates
`intermediates.official_totals_{iso3}` and `aggregates_{iso3}` per
country (DD8 path); `config/debt.yaml` entries; the interest and
financing chains run on Eurostat S1311 D.41 / B.9.

### Stage ED3 — Per-security registers where published
BEL (BDA OLO lines), ITA (MEF auction results); ESP stays aggregate (DE4).

### Stage ED4–ED5 — Interest, maturity profile, packaging
As `DEBT_KICKOFF.md` D3–D5 for the registers built in ED3.
