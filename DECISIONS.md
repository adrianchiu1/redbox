# DECISIONS.md — append-only decision log

Per §16: never edit an earlier decision; supersede it with a new entry.
Spec references are to `COFOG_KICKOFF.md` v2.2.

---

## D-S0-001 — Python 3.11 runtime accepted for now (serves §11.3)
2026-08-31. The build environment provides Python 3.11.15; §11.3 specifies 3.12.
`pyproject.toml` sets `requires-python >= 3.11` and the code avoids 3.12-only
syntax, so it runs identically on 3.12. No behavioural dependence on the minor
version. Revisit only if a dependency forces 3.12.

## D-S0-002 — Stage 0 harvest blocked by network egress policy; fetch layer built to run when unblocked (serves §12 Stage 0, D8)
2026-08-31. This execution environment routes all outbound HTTPS through an
organisation egress proxy that returns 403 (policy denial) for every
statistical host needed by Stage 0: `ec.europa.eu`, `sdmx.oecd.org`,
`api.imf.org`, `data.imf.org`, `www.imf.org`, `www.ons.gov.uk`,
`economy-finance.ec.europa.eu`. Server-side page fetching is blocked by the
same policy; only web *search* is available. Per D13 (no fabrication, no
silent filling) no data was invented and no secondary mirror was used as a
substitute anchor. What was done instead:
  - endpoint verification via web search, recorded with per-entry confidence
    in `reports/source_verification.md`;
  - the full ingestion layer (`ggfiscal fetch`) written against the verified
    endpoints, storing every pull as an immutable content-hashed snapshot per
    D8, ready to run unchanged in a network-enabled environment.
Gate 0 is therefore **open/blocked**, not failed: see `HANDOFF.md` for the
exact unblock request and next command.

## D-S0-003 — Endpoint selections for the register (serves §13, §12 Stage 0)
2026-08-31. Chosen access paths (verification status in
`reports/source_verification.md`):
  - **Eurostat**: dissemination API, SDMX-CSV via
    `https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/data/dataflow/ESTAT/{ds}/1.0/?format=csvdata`
    (SDMX 2.1 XML kept as fallback). Datasets `gov_10a_exp`, `gov_10a_main`,
    `gov_10a_taxag`, plus `nama_10_gdp` for the FRA/DEU GDP denominator.
  - **IMF**: the 2025-migrated portal API, base
    `https://api.imf.org/external/sdmx/3.0` (legacy
    `dataservices.imf.org` paths deliberately NOT used, per §12 Stage 0
    warning). WEO: agency `IMF.RES`, dataflow `WEO`, editions exposed as
    dataflow versions — enumerate versions live, take latest + preceding 4–9
    per §15 Q11. GFS COFOG: `data.imf.org` dataset `GFS_COFOG` (agency
    `IMF.STA`); exact dataflow id to confirm live.
  - **OECD**: `https://sdmx.oecd.org/public/rest/data/{flow}` SDMX-CSV.
    Revenue Statistics: `OECD.CTP.TPS,DSD_REV_COMP_GLOBAL@DF_RSGLOBAL`.
    COFOG Table 11 and National Accounts flow ids to confirm live.
  - **AMECO**: bulk zip-per-chapter download from
    `economy-finance.ec.europa.eu` (Spring 2026 vintage, published
    2026-06-03); no stable REST API identified, bulk file is the snapshot.
  - **ONS**: dataset landing pages under
    `www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicspending/datasets/`
    serving versioned xlsx; the xlsx file is the snapshot. Archived vintages
    for pre-1995 via the same pages' "previous versions".

## D-S0-004 — Raw snapshots content-addressed but not committed to git (serves D8, §11.1, §16)
2026-08-31. `data/raw/` follows `{source_id}/{retrieved_at}_{sha256[:12]}.{ext}`
and snapshots are never mutated, but the raw files themselves are gitignored:
the repository records provenance through `data/manifest/` (full sha256 per
pull) while the bytes live in the working store. Rationale: WEO/AMECO/Eurostat
bulk pulls are tens of MB per vintage and git is a poor archive for them;
reproducibility is preserved because any snapshot can be re-verified against
its recorded hash. `data/manual/` (hand-keyed CSVs, §11.4) IS committed.
Supersede this if the committee wants raw bytes in-repo or in LFS/object
storage.

## D-S0-005 — Source register is YAML seed + generated CSV (serves §13, §11.6 deliverable 8)
2026-08-31. `config/sources.yaml` is the editable register seeded from §13,
extended with the verification fields §6.4 requires (release date, vintage,
retrieval date, URL, snapshot hash, supersedes, scenario_label, concept_note,
plus `verification` status). `source_register.csv` is generated from it at
build time, never hand-edited.

## D-S0-006 — Live endpoint resolution and filtered pulls (serves §12 Stage 0, §13; supersedes the "confirm live" placeholders in D-S0-003)
2026-08-31, second session (network-enabled). Every machine-readable endpoint
was resolved against the live catalogs and harvested as D8 snapshots
(`ggfiscal fetch --all`, 0 failures). Resolutions:
  - **IMF GFS**: COFOG dataflow `IMF.STA:GFS_COFOG(11.0.0)`; main-aggregates
    companion `IMF.STA:GFS_SOO(12.0.0)` (GFSM Statement of Operations).
    GFS XDC observations arrive in raw LCU units; readers scale to millions.
  - **OECD Table 11**: `OECD.SDD.NAD,DSD_NASEC10@DF_TABLE11,1.1` (13-dim
    DSD_NASEC10), filtered to S13 per country.
  - **OECD Revenue Statistics**: `OECD.CTP.TPS,DSD_REV_COMP_OECD@DF_RSOECD,2.0`
    — NOT the §13-era candidate `DF_RSGLOBAL`: only the members flow carries
    S13 XDC from 1965 as D15 requires (global flow starts 1990; both checked
    live). UNIT_MULT 9 (billions); readers scale to millions.
  - **ONS_GG_RECEIPTS** resolved to **ESA Table 2**
    (`esatable2mainaggregatesofgeneralgovernment`, June 2026 EDP transmission):
    OTR/OTE/B9 plus receipts by ESA code 1990–2025, including direct
    D51M/D51O household–corporate splits. **ONS_TAX_DETAIL** (new):
    `esaquestionnairedetailedtaxandsocialcontributions` (NTL table 9),
    per-tax ESA-coded detail 1995–2025 — the R03/R04/R06 mapping evidence.
    **ONS_TAX_LIST** (new): `esatable9listoftaxes`, flagged stale (2023-10),
    mapping evidence only. **ONS_PSF_INTEREST** resolved into the same ESA
    Table 2 file (GG D.41 payable/receivable, accrued, 1990–2025); kept as a
    distinct register entry because its D10 role differs.
  - **ONS_GDP** (new): timeseries YBHA (QNA), nominal GDP £m CY 1948–2025;
    needed because ESA Table 2 has no GDP row. `countries.yaml` GBR
    `gdp_source` updated accordingly.
  - **AMECO**: chapter zips at
    `ec.europa.eu/economy_finance/db_indicators/ameco/documents/ameco{n}.zip`;
    chapters 6 (GDP) and 16–18 (GG accounts, EDP, debt) snapshotted, Spring
    2026 vintage. Finding: **no UK TR/TE level history** (2026–27 only;
    UBLG/UYIG from 1987) — AMECO cannot serve as a UK envelope, reinforcing
    the Q12 OBR-primary default.
  - **Pull granularity**: Eurostat pulls are country-filtered (the SDMX 3.0
    key parser accepts single values only) and unit-filtered to MIO_NAC; the
    full-table pull attempted first proved impractical (>1 GB stream). The
    filter is part of the recorded snapshot URL, so each snapshot remains a
    complete, reproducible extraction definition. This narrows D-S0-003's
    "full-dataset pull" note; provenance guarantees are unchanged.

## D-S0-007 — WEO vintages: the API exposes 3; Q11 satisfied by taking all of them (serves §15 Q11, §8.5)
2026-08-31. Enumerating `api.imf.org` live: WEO editions are exposed partly as
dataflow versions and partly as named vintage flows. Exactly three are
available today: **2026-04 = WEO/9.0.0** (publication date 2026-04-14, per the
API's own attributes; the first session's search-derived 2026-04-08 is
superseded), **2025-10 = WEO_2025_OCT_VINTAGE/1.0.0** (2025-10-14), and
**2025-04 = WEO/6.0.0** (2025-04-22). Q11's rule for this case ("if the API
exposes fewer than 5, take what it has and note the earliest") applies: all 3
retained, earliest 2025-04, one source_id per vintage. Consequence for §8.5:
old editions can disappear from the API, so `detect-vintages` must snapshot
each new edition promptly. WEO pulls are one per (country, subject): the API
only serves the series-level attributes that pin the §8.1 base year
(LATEST_ACTUAL_ANNUAL_DATA) on single-series queries.

## D-S0-008 — interest_anchor stays `level2` for all three countries (serves D10, §12 Stage 0)
2026-08-31. Stage 0 was to set `interest_anchor` from measured Level II
coverage. Measured: GF0107 available from the anchor's own COFOG table for
every year of every country's expenditure history (GBR 1995–2024 ONS T11;
FRA/DEU 1995–2024 Eurostat). The `level2` default in `countries.yaml` is
therefore confirmed, not changed. The D.41-payable fallback series
(ONS ESA T2 / gov_10a_main D41PAY, both from 1990/1995, AMECO UYIG from
1978/1987/1991) are measured and registered for years outside Level II
coverage in Stage 2.

## D-S0-009 — §8.2 bridge computed for all three vintages; classification heuristic at Stage 0 (serves §8.2, D16)
2026-08-31. `ggfiscal reconcile` writes `data/canonical/weo_base_bridge.csv`
for every (country, harvested WEO vintage) — 9 pairs, not just the latest,
since §8.5 keys everything by vintage anyway. Base year per §8.1 =
min(WEO LATEST_ACTUAL_ANNUAL_DATA across GGR/GGX/GGXCNL/NGDP, last anchor
year). Latest vintage (2026-04): GBR b=2025, FRA b=2024, DEU b=2025.
Gap classification at Stage 0 is a documented heuristic (FRA/DEU: 'revision'
within the 1%-of-TE tolerance, else 'unexplained'; GBR: 'perimeter' where the
NLB gap ratio is within tolerance of the country mean, else 'unexplained') —
V24 formalises this at Stage 5. Results match §14's priors: GBR TR/TE gaps
≈ 6% of TE but NLB gap mean −0.10% of TE with σ 0.36 (stable perimeter);
FRA/DEU gaps ≈ 0 (revisions only); GBR 1995–96 flagged unexplained (early-year
WEO history divergence, to revisit in Stage 5). Nothing was scaled or
adjusted (D13).

## D-S1-001 — Stage 1 build shape: §5 long format for the trees, compact wide ledger (serves §5, §4.3, §11.6)
2026-08-31. `ggfiscal build` writes `expenditure_long_{variant}` and
`revenue_long_{variant}` in the full §5 long format (pandera-enforced,
`src/ggfiscal/model.py`), containing the 66 lines plus each tree's own total
row (TE from the COFOG table's total; TR from the revenue anchor). The balance
ledger (§11.6 deliverable 3) is a compact wide file
(`balance_ledger.csv`: TR, TE, NLB, NI, PB, `complete_both_sides`) built from
the balance anchor's own TR/TE/B9, so V23 is an exact within-source identity;
NI = GF01_7 − R07 only where both sides exist. Both variants carry identical
anchor history at this stage; they diverge when forecasts arrive (Stages 3–4).
COFOG-tree TE for GBR comes from ONS Table 11's own total row (V2 is a
within-table identity), while the GBR ledger runs on ESA Table 2 — the two
totals are different releases of the same accounts (Apr vs Jun 2026); any
wedge shows up in V2/V23 diagnostics, never silently reconciled.

## D-S1-002 — FRA/DEU revenue lines built from gov_10a_main's own REC codes; gov_10a_taxag demoted to detail/verification (serves §4.2, V22; narrows D-S0-003's dataset roles)
2026-08-31. Root-caused a V22 failure: for FRA 2024, `gov_10a_taxag` D.2
differs from `gov_10a_main` D2REC by 0.54% (transmission-timing drift in the
freshest year), which breaks R01..R10 = TR at the 0.1% tolerance when tax
lines come from taxag but TR from main. `gov_10a_main` itself carries
D211REC, D51A_C1REC, D51B_C2REC, D5REC, D91REC — building every revenue line
from the main table makes the identity exact in every year for both
countries, provisional 2025 included, and extends the tax lines to 2025.
taxag remains registered as the detail/verification source (D.59/D.91
breakdowns, national tax lists). No value was adjusted; the source cell
choice changed (D13-clean).

## D-S1-003 — D10 Level II gap handling: DEU 1995–99 GF01_7 from D.41 payable, grade B (serves D10)
2026-08-31. Measured during the build: Eurostat DEU `gov_10a_exp` lacks
GF0107 for 1995–99 while GF01 exists. Exactly D10's fallback case: those five
years carry GG gross D.41 payable from `gov_10a_main` (same institution),
`observation_type = level2_proxy_actual`, grade B; the derived GF01_X years
that use them are likewise grade B with a note. FRA and GBR need no proxy
(full Level II coverage). V21 monitors the L2-vs-D.41 wedge (5–10% for
FRA/DEU in some years — FISIM/consolidation differences, WARN tier).

## D-S1-004 — §8.3 history decomposition: exact additivity via the sum-based balance; wedges reported, never allocated (serves §8.3, D16, V26)
2026-08-31. The history decomposition (`deficit_dynamics.csv`) decomposes
Δ((ΣR − ΣE)/GDP) over the 20 Level I lines, so V26 additivity is exact by
construction. The wedge to the anchor's own Δ(B9/GDP) (rounding-level;
policed by V2/V22/V23 at 0.1%) is reported as `ANCHOR_B9_DELTA`, and the
latest WEO vintage's Δ(GGXCNL/NGDP) rides along as `WEO_GGXCNL_DELTA` — both
memo rows, never allocated to lines. Denominator: anchor GDP throughout the
history side; the chained-at-b path and forecast-side residuals arrive with
Stage 5.

## D-S1-005 — GBR receipts crosswalk documented from the anchor's own splits (serves §4.2, §11.5, D17)
2026-08-31. `crosswalks/ONS_RECEIPTS_to_ESA_REV.csv` v1.0: ONS ESA Table 2
provides D51M (households incl. holding gains) and D51O (corporations) as
direct rows, so R03/R04 need no constructed split; NICs sit in D.61 → R06 per
§14; payable tax credits follow the anchor's gross ESA treatment (D17). NTL
table 9 (ONS_TAX_DETAIL) is the per-tax evidence trail. Allocation is 100%
cell-to-line; no weights were estimated.
