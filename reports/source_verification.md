# Source verification — Stage 0 (§12, §13)

Status date: 2026-08-31. The §13 seed register was drafted from secondary
information; this report records what has actually been verified and how.

**Verification method caveat.** This session's execution environment denies
outbound HTTPS to every statistical host (egress-policy 403 at the proxy —
confirmed live by `ggfiscal fetch --all` on 2026-08-31; see OQ-1 in
`OPEN_QUESTIONS.md`). Web *search* was available. Entries below marked
`confirmed_search` are corroborated by current search results but have not
been hit live; nothing here counts as a D8 snapshot. **Stage 0 verification
is therefore INCOMPLETE by the spec's standard** and Gate 0 remains open.

## Machine-readable sources

| source_id | Verdict | Evidence (2026-08-31) |
|---|---|---|
| EUROSTAT_GOV10A_EXP | confirmed_search — endpoint pattern and dataset alive | Eurostat metadata: last update 2026-07-23, observations to 2025 (t+11m transmission means 2024 firm, 2025 partial/provisional — check per country at pull). Dissemination API base `ec.europa.eu/eurostat/api/dissemination/sdmx/3.0`. |
| EUROSTAT_GOV10A_MAIN | confirmed_search | Same API family; dataset browsable on the data browser. |
| EUROSTAT_GOV10A_TAXAG | confirmed_search | Same API family. |
| EUROSTAT_NAMA10_GDP | confirmed_search | Standard national-accounts dataset, same API. |
| IMF_WEO | confirmed_search — **portal migration confirmed** | New API base `https://api.imf.org/external/sdmx/3.0` (SDMX 3.0), agency `IMF.RES`, dataflow `WEO`, **editions exposed as dataflow versions** (enumerate live via `structure/dataflow/IMF.RES/WEO/*`). Latest vintage: **April 2026, published 2026-04-08** (October 2026 not yet released as of today). Legacy `dataservices.imf.org` paths are superseded — not used anywhere in this repo (tested in `tests/stage_0/test_endpoints.py`). Number of prior vintages the API exposes (Q11): unknowable without a live call. |
| IMF_GFS | confirmed_search (dataset), dataflow id **unconfirmed** | `GFS_COFOG` dataset exists on the migrated `data.imf.org` portal (agency `IMF.STA`). Exact SDMX dataflow id and the main-aggregates companion flow must be read from the live catalog before ingestion is trusted. |
| OECD_RS | confirmed_search | Dataflow `OECD.CTP.TPS,DSD_REV_COMP_GLOBAL@DF_RSGLOBAL` on `sdmx.oecd.org` (dimension set REF_AREA/MEASURE/UNIT_MEASURE/REVENUE_CODE seen in third-party docs). Dataflow *version* to resolve live. |
| OECD_T11 | **unverified** | COFOG/Table 11 dataflow id could not be pinned by search (SDD.NAD family). One live catalog query (`/dataflow/all/all/latest`) resolves it. Secondary source only — not blocking. |
| EC_AMECO | confirmed_search | Bulk zip-per-chapter CSV from `economy-finance.ec.europa.eu`; **current vintage: Spring 2026 Economic Forecast, published 2026-06-03**. Autumn 2026 vintage expected ~Nov; `detect-vintages` must watch this. UK coverage in current AMECO to verify at pull (register note stands). |
| ONS_ESA_T11 | confirmed_search | GG dataset page alive, last updated **2026-04-23** (annual COFOG release lands each April alongside EDP). Versioned xlsx + "previous versions" archive for older vintages. |
| ONS_GG_RECEIPTS | **unverified** | Candidate: PSF/ESA receipts datasets under the ONS public-sector-finance area; the exact dataset serving ESA-coded GG receipts (with the income-tax/NICs/CT split needed for R03/R04/R06) must be chosen live. |
| ONS_PSF_INTEREST | **unverified** | Same area; needs live identification. |

## Forecast sources (Stage 3 registration checks only)

Not required for Gate 0; noted for staleness only.

- **OBR_EFO_LATEST / OBR_FRS_2026** — not yet verified; the spec claims an FRS July 2026 edition, plausible (annual cadence) but unconfirmed. Verify before Stage 3.
- **EC_AGEING_2024** — 2024 Ageing Report is on a 3-year cycle; a 2027 edition would supersede it mid-project. Watch.
- **EC_DSM** — annual; latest edition to pin live.
- **FRA_LPFP_PSTAB / COR_2026 / FRA_LPM_2030 / FRA_LFSS** — unverified; note France's 2025-26 budget-cycle turbulence makes the LPFP's currency a real staleness risk — check which programmation law is in force before use.
- **DEU_STEUERSCHAETZUNG** — Arbeitskreis meets ~May and ~Oct/Nov; a May 2026 round should exist. Verify.
- **DEU_BMAS_RVB / DEU_BMF_FINPLAN** — annual; verify.

## Stale / superseded / flagged

1. **Any legacy IMF `dataservices.imf.org` URL is superseded** (portal migrated 2025). The §13 seed did not carry one, and the codebase is tested to contain none.
2. **§13 claims Eurostat data "from 1995"** — search shows `gov_10a_exp` observations from 1990 for some countries; the usable FRA/DEU start must be measured from data, not assumed (feeds `coverage_matrix_v0.csv`).
3. **WEO October 2026** will land mid-project (~mid-October); the reconciliation module keys by vintage (§8.5) so this is planned-for, not a risk.
4. **AMECO Autumn 2026** likewise (~November).

## What remains for Gate 0

All of it requires network egress (OQ-1): live catalog confirmation of the
flagged dataflow ids; `ggfiscal fetch --all` producing D8 snapshots; per-line
first/last usable years measured into `coverage_matrix_v0.csv`; §8.2 base-year
bridge on WEO 2026-04 for all three countries. The pipeline for the first two
exists; the last two are the next build items once data lands.
