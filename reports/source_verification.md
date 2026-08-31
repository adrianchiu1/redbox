# Source verification — Stage 0 (§12, §13)

Status date: 2026-08-31 (second session). Supersedes the first session's
search-only report. Every machine-readable §13 entry has now been **confirmed
live**: endpoint hit, D8 content-hashed snapshot taken (see
`data/manifest/snapshots.jsonl`), and first/last usable years measured
programmatically into `reports/coverage_matrix_v0.csv`.
**Stage 0 verification is COMPLETE for the machine-readable register.**
Forecast sources (Stage 3 inputs) remain registration-checked only, as §12
requires.

## Machine-readable sources — confirmed live 2026-08-31

| source_id | Verdict | Endpoint as resolved | Measured coverage / release evidence |
|---|---|---|---|
| EUROSTAT_GOV10A_EXP | **confirmed_live** | SDMX 3.0 `data/dataflow/ESTAT/gov_10a_exp/1.0/A.MIO_NAC.S13.*.*.{FR,DE}` (one pull per country; the key parser rejects multi-values) | FRA and DEU: 1995–2024 for all Level I and GF0107. §13's "from 1995" claim confirmed against data, not assumed. |
| EUROSTAT_GOV10A_MAIN | **confirmed_live** | same family, `gov_10a_main/1.0/A.MIO_NAC.S13.*.{geo}` | TR/TE/B9/D41REC/D41PAY/D61REC/P11_P12_P131 etc.: FRA & DEU 1995–2025 (2025 provisional). |
| EUROSTAT_GOV10A_TAXAG | **confirmed_live** | `gov_10a_taxag/1.0/A.MIO_NAC.S13.*.{geo}` | D211, D51A_C1, D51B_C2, D5, D59, D91: FRA & DEU 1995–2024. |
| EUROSTAT_NAMA10_GDP | **confirmed_live** | `nama_10_gdp/1.0/A.CP_MNAC.B1GQ.{geo}` | B1GQ: FRA 1975–2025, DEU 1991–2025. |
| ONS_ESA_T11 | **confirmed_live** | dataset page → `/current/esatable11generalgovernment.xlsx`; released 2026-04-22 | One sheet per year, 1995–2024; COFOG groups incl. GF0107; column OTE = total expenditure. |
| ONS_GG_RECEIPTS | **confirmed_live** (resolved: **ESA Table 2**, `esatable2mainaggregatesofgeneralgovernment`) | `/current/esatable0200.xls`; released 2026-06-18 (June 2026 EDP transmission) | S13 sheet 1990–2025: OTR/OTE/B9, all receipts by ESA code incl. D211, **D51M/D51O household–corporate splits directly**, D61, D41 both directions. TR−TE=B9 verified to £1m. |
| ONS_TAX_DETAIL | **confirmed_live** (new entry; `esaquestionnairedetailedtaxandsocialcontributions`, NTL table 9) | `/current/esantl0999.xls`; released 2026-06-18 | S13 sheet 1995–2025, per-tax detail with ESA codes: the R03/R04/R06 crosswalk evidence for income tax vs NICs vs CT. |
| ONS_TAX_LIST | **confirmed_live but FLAGGED STALE** (`esatable9listoftaxes`) | `/current/esatable0900.xls` | Workbook last saved 2023-10-26. Use only as mapping evidence; levels come from ONS_TAX_DETAIL. |
| ONS_PSF_INTEREST | **resolved into ESA Table 2** | same file as ONS_GG_RECEIPTS; D.41 payable & receivable rows, accrued | GG D.41 both directions 1990–2025 — longer than Table 11's 1995 start, satisfying the D10 fallback role. |
| ONS_GDP | **confirmed_live** (new entry; YBHA/QNA) | `/economy/grossdomesticproductgdp/timeseries/ybha/qna/data`; released 2026-06-29 | Nominal GDP £m, calendar years 1948–2025. Needed because ESA Table 2 carries no GDP row. |
| IMF_WEO | **confirmed_live** | `api.imf.org/external/sdmx/3.0`, agency IMF.RES; **one pull per (country, subject)** — the API drops the series-level attributes (LATEST_ACTUAL_ANNUAL_DATA, PUBLICATION_DATE) on multi-value keys | **The API exposes exactly 3 vintages (Q11)**: 2026-04 = `WEO/9.0.0` (publication 2026-04-14), 2025-10 = `WEO_2025_OCT_VINTAGE/1.0.0` (2025-10-14), 2025-04 = `WEO/6.0.0` (2025-04-22). GGR/GGX/GGXCNL/GGXONLB/NGDP pulled for all three countries in all three vintages, 1980–2031. |
| IMF_GFS | **confirmed_live** — dataflow ids resolved | COFOG: `IMF.STA:GFS_COFOG(11.0.0)`; main aggregates: `IMF.STA:GFS_SOO(12.0.0)`; key `{iso3}.S13.*.*.*.A`; XDC values arrive in raw LCU units (scaled to millions in the reader) | COFOG L1: GBR 1995–2024, FRA 1995–2023, DEU 1991–2024. Anchor-vs-GFS diffs ≈ 0% (see `recon_anchor_vs_imf_v0.csv`) — same national data, as D1 expects. |
| OECD_T11 | **confirmed_live** — dataflow id resolved | `OECD.SDD.NAD,DSD_NASEC10@DF_TABLE11,1.1`, key `A.{iso3}.S13..........` (13-dim DSD) | All three countries 1995–2024, S13, XDC (UNIT_MULT 6). |
| OECD_RS | **confirmed_live** — **flow superseded**: `DSD_REV_COMP_OECD@DF_RSOECD,2.0`, not the §13-era `DF_RSGLOBAL` | key `{iso3}......A`; UNIT_MULT 9 (billions, scaled in reader) | S13 XDC from **1965**–2024 for all three (D15 requirement); DF_RSGLOBAL only starts 1990 and is not used. Anchor-vs-RS wedges measured (`recon_anchor_vs_oecd_rs_v0.csv`): R01 ≈ 0.3–0.4%, R03 ≈ 2–2.5%, FRA R04 ≈ 14% (payable tax credits, D17), FRA R06 ≈ 11% — the crosswalk load, quantified. |
| EC_AMECO | **confirmed_live** | zips at `ec.europa.eu/economy_finance/db_indicators/ameco/documents/ameco{n}.zip`; chapters 6, 16–18 snapshotted; Spring 2026 vintage (published 2026-06-03) | FRA: URTG/UUTG/UYIG 1978–2027; DEU: 1991–2027. **GBR: URTG/UUTG levels exist only 2026–2027** (UBLG and UYIG from 1987) — the §13 "verify UK coverage" caution was warranted; AMECO is usable for GBR interest/balance but NOT as a UK TR/TE envelope. Q12's OBR-primary default is therefore also the only workable choice for levels. |

## Forecast sources (Stage 3 registration checks only)

Unchanged from the first session — not required for Gate 0; verify before
Stage 3 use: OBR EFO/FRS (claimed July 2026 FRS), EC Ageing 2024 (2027 edition
risk), EC DSM (pin edition), FRA LPFP/PSTAB (currency risk after the 2025–26
budget cycle), COR, LPM, LFSS, Steuerschätzung (May 2026 round expected),
BMAS RVB, BMF Finanzplan.

## Stale / superseded / flagged

1. **OECD `DF_RSGLOBAL` superseded by `DF_RSOECD`** for this repo: only the
   members flow carries the 1965– history D15 requires.
2. **ONS_TAX_LIST (`esatable9listoftaxes`) is stale** (last saved 2023-10):
   mapping evidence only.
3. **AMECO has no UK TR/TE level history** (2026–27 only) — flag against any
   Stage 3 plan to use AMECO as a UK envelope; UBLG/UYIG are fine from 1987.
4. **WEO API retains only 3 vintages** — below the Q11 target of 5–10; the
   earliest is 2025-04. Recorded in DECISIONS.md (D-S0-007); `detect-vintages`
   must snapshot each new edition promptly since old editions may drop off.
5. **WEO October 2026** (~mid-October) and **AMECO Autumn 2026** (~November)
   land mid-project; both are keyed-by-vintage re-runs, planned for.
6. Legacy IMF `dataservices.imf.org` paths remain banned and untested-for by
   `tests/stage_0/test_endpoints.py`.
7. Eurostat 2025 values in `gov_10a_main` are provisional (t+11 months rule);
   the COFOG tables end 2024 everywhere — final actual year is 2024 for
   expenditure lines, 2025 (provisional) for main-aggregate revenue lines.

## Gate 0 evidence

- `reports/coverage_matrix_v0.csv`: 66/66 lines measured from ≥1 source
  (174 (line, source) rows), `ggfiscal coverage`.
- `data/canonical/weo_base_bridge.csv`: §8.2 bridge, all three countries ×
  all three WEO vintages, `ggfiscal reconcile`. Latest vintage (2026-04):
  GBR base 2025 (36 overlap years, mean NLB gap −0.10% of TE, σ 0.36 —
  stable perimeter gap as §14 predicts; 1995–96 outliers flagged
  unexplained); FRA base 2024 (gaps ≈ 0, revisions only); DEU base 2025
  (gaps exactly 0).
- `reports/recon_anchor_vs_imf_v0.csv`, `reports/recon_anchor_vs_oecd_rs_v0.csv`:
  Stage 0 reconciliation diagnostics.
- `pytest`: 28 passed. `ggfiscal validate`: OK=5 SKIP=28, no ERROR, no WARN.
