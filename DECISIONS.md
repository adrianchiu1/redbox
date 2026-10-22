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

## D-S2-001 — Backward-extension engine and §9 grade bands; D-graded mappings are never applied (serves §7.3-7.4, §7.12, §9, D6, D15)
2026-08-31. `src/ggfiscal/stitch/backward.py` implements §7.3 (growth, never
level), §7.4 (sequential sources, boundary record per transition) and §7.12
(stop at missing/zero/negative or a configured perimeter break). Grades from
the measured coverage share at the last common year (§9.2):
**B = 90-110%**, **C = 50-90%**, anything else **D**. B rows enter both
variants; C rows enter maximum_extension only (§9); **D-graded mappings are
not applied at all** — D15 grades RS extensions "B/C", and a source covering
<50% or materially more than the line (FRA T_4000 at 348% of R05) is a weak
crosswalk whose growth would fabricate dynamics. D skips are still written to
`stitch_boundaries.csv` (`variants = not_applied_grade_D`) so the stop is
machine-documented. All boundary records land in
`data/canonical/stitch_boundaries.csv` (committed).

## D-S2-002 — V5 WARN thresholds (Q4 space, undefined in §10)
2026-08-31. §10 gives V5 no numeric threshold. Chosen: WARN when |bias| >
0.01 or RMSE > 0.05 on annual growth factors over the overlap; below that the
diagnostic reports at OK severity with its stats. Fired for R04/R05 proxies
(DEU R04 RMSE 0.149, GBR R05 0.148) — consistent with their C/D grades.
Supersede via config if the committee sets different values.

## D-S2-003 — Extension map actually applied (serves §12 Stage 2 order)
2026-08-31. Tax lines via OECD RS (`DF_RSOECD`, growth of the matching
heading, crosswalk `OECD_RS_to_ESA_REV.csv` v1.0): R01←5111, R02←5000−5111,
R03←1100, R04←1200, R05←4000, R06←2000. Interest via GG D.41 history
(`EC_AMECO_to_INTEREST.csv` v1.0): GBR GF01_7 ← ONS ESA T2 D.41 payable
1990-94 then AMECO UYIG 1987-89 (two stitches); FRA ← UYIG to 1978;
DEU ← UYIG to 1991. DEU expenditure GF01-GF10 1991-94 via IMF GFS COFOG
(`IMF_GFS_to_COFOG.csv` v1.0; boundary ratios 0.994-1.000). GF01_X derived in
stitched years where both components exist (DEU 1991-94, grade B). DEU has a
hard break at 1991: pre-reunification data is West Germany, a different
universe (§14) — no DEU line extends below 1991.

## D-S2-004 — Why each line stops where it does (Gate 2 record)
2026-08-31. First year per line after Stage 2, with the binding constraint.
"OQ-5" = pre-1995 archives need either §11.4 manual ingestion (independent
second keying unavailable to a single-agent session) or a machine-readable
archive endpoint — committee item.

**GBR** — GF01-GF10, GF01_X: 1995 (ONS T11 starts 1995; pre-1995 functional
spending is PESA, "only if reconcilable" → OQ-5). GF01_7: 1987 (AMECO UYIG
begins 1987; earlier D.41 would need ONS long-run PSF series — candidate for
a Stage 2 follow-up pull). R01: 1973 (VAT introduced 1973; no tax exists
before — final stop). R02: strict 1990 / maximum 1965 (C-grade RS composite).
R03, R04: 1965 (RS series start — earliest machine-readable history). R05:
1990 (RS 4000 mapping grade D, 145% coverage — not applied; no other source
harvested). R06: strict 1990 / maximum 1965 (C: imputed+voluntary wedge).
R07-R10: 1990 (ESA Table 2 start; no receivable-side history source in the
harvest).

**FRA** — GF01-GF10, GF01_X: 1995 (Eurostat starts 1995; INSEE pre-ESA95
base series are non-SDMX archives → OQ-5). GF01_7: 1978 (AMECO UYIG start).
R01: 1965 (RS start). R02: 1995 (RS composite grade D, 47% coverage — French
production taxes sit largely outside 5000-ex-VAT). R03: 1965. R04: strict
1995 / maximum 1965 (C: payable tax credits, D17). R05: 1995 (RS 4000 grade
D, 348% coverage). R06: strict 1995 / maximum 1965 (C). R07-R10: 1995
(gov_10a_main start).

**DEU** — every extended line stops at 1991 (reunification perimeter break;
pre-1991 is D-at-best per §14 — deliberate stop, not a data gap): GF01-GF10,
GF01_7, GF01_X, R01, R02, R03, R05 at 1991 (strict); R04, R06 at 1991 in
maximum only (C). R07-R10: 1995 (gov_10a_main start; no earlier D.41
receivable source).

Totals (TE, TR) and the ledger are not extended: §6.1 ties envelopes to the
anchor's own aggregates; a stitched total would not be an anchor total.

## D-S3-001 — Stage 3 source access: what resolved, what is blocked, and the forced Q12 deviation (serves §12 Stage 3, §6.4; reopens OQ-1 as OQ-6)
2026-08-31, third session. The OQ-1 "later stages" hosts were probed live:
  - **Resolved and harvested (D8 snapshots)**: `economy-finance.ec.europa.eu`
    (2024 Ageing Report statistical annexes — country fiches + horizontal
    tables, ANNUAL 2022–2070, not benchmark-only; DSM 2025 country fiches to
    2036; the EC document store needs browser-like headers, which are part of
    the recorded pull), `www.bundesfinanzministerium.de` (Steuerschätzung
    May 2026 results, xlsx edition, per-tax to 2030 including the Tab 8.2
    Soli payer-type split), plus the already-harvested EC_AMECO Spring 2026
    (forecast horizon 2027; last actual 2025).
  - **Blocked**: `obr.uk` (Cloudflare JS challenge to every available client —
    curl, WebFetch, and headless Chromium, which cannot tunnel through the
    egress proxy at all); `www.gov.uk` + `assets.publishing.service.gov.uk`,
    `circabc.europa.eu`, `www.bmas.de` (egress-policy CONNECT denials).
    PDF-only sources (LPFP/PSTAB, LPM, LFSS, COR, BMF Finanzplan) stay
    blocked by §11.4's second-keying requirement (OQ-5 precedent).
Consequence: every GBR-specific forecast source is unreachable, so GBR
strict forecasts are limited to AMECO lines (GF01_7, R06), and §15 Q12's
OBR-primary envelope cannot be exercised — the AMECO UK TR/TE levels
(2026–27 only, OQ-4) serve as the V15 envelope until OBR access exists.
Recorded as OQ-6; nothing was scraped around the blocks (D13-clean: no
mirror, no cached third-party copy).

## D-S3-002 — Forward-forecast engine, grading and non-application records (serves §7.2, §7.4-7.5, §7.8, §9, §12 Stage 3)
2026-08-31. `src/ggfiscal/forecast/forward.py` implements §7.2 (growth, never
level, chained from the last anchor year), §7.4 (sequential sources, boundary
record per transition — in `forecast_boundaries.csv`, separate from the
backward file so Gate 2's invariants stay closed), §7.5 (%-GDP sources
levelled with same-source nominal GDP; AR/DSM publish none, so it is
constructed from their own real-growth and price assumptions,
`gdp_source_id = {source}_constructed`; HICP stands in for the AR deflator —
both converge to the same 2% assumption), §7.10 (FY→CY, exercised by tests
only until a GBR source is reachable) and D11 (both interpolation methods;
unused by the annual AR tables). Grades from measured §9.2 coverage at the
last common year: **A** only for a direct forecast of the same ESA aggregate
within 0.5% of the anchor (AMECO UTSG→R06: 0.999–1.000); **B** 90–110%;
**C** 50–90% and **D** otherwise are measured and recorded
(`not_applied_grade_*`) but never applied at Stage 3 — strict carries A/B
only (V9), and the C records are Stage 4's worked queue. Source years at or
before the source's last actual stitch as `stitched_actual` (§7.2 "newer
national actuals first": the 2025 GF01_7 values), not as forecasts.
Every line without an applied forecast carries a declaration row
(`forecast_declarations.csv`: D7 / blocked / below-strict-grade / not
extended) — Gate 3's note requirement, tested.

## D-S3-003 — Forecast map actually applied and the crosswalk calls (serves §12 Stage 3 order, §11.5, §14, D17)
2026-08-31. Applied (all coverage shares in `forecast_boundaries.csv`):
  - **GF01_7 ← AMECO UYIG** growth to 2027, grade B (coverage GBR 1.044,
    FRA 1.021, DEU 0.930 — the D.41-for-Level-II wedge V21 already monitors);
    2025 stitched as newer actual. The DSM long-term leg was measured
    (B-coverage) but withheld per D-S3-005/OQ-7.
  - **R06 ← AMECO UTSG** (D.61 direct) grade A everywhere (0.9987–1.0000).
  - **R09 ← AMECO UTOG − UROG** (sales of goods and services as the exact
    difference of two official aggregates, §6.2(3) composite) grade B at
    coverage 1.0000 for FRA/DEU; GBR has no UTOG/UROG history (OQ-4 pattern)
    → unmeasurable → not applied, declared.
  - **DEU R01 ← Steuerschätzung "Steuern vom Umsatz"** (0.999), **R03 ←**
    Lohnsteuer + veranl. ESt + nicht veranl. StvE + AbgSt + their Soli parts
    (0.979), **R04 ←** KSt + Mindeststeuer + Gewerbesteuer brutto + Soli auf
    KSt (0.946) — all B, growth only (§7.11), horizon 2030. Crosswalk calls
    (`DEU_STEUERSCHAETZUNG_to_ESA_REV.csv` v1.0): the **Kasse** series are
    used, not the Tab 8.1 brutto series — measured: brutto composites
    overshoot the anchor beyond the B band because ESA's netting of
    Kindergeld/Zulagen sits between cash and brutto (D17 wedge documented);
    the **Soli split is the source's own Tab 8.2 decomposition** (official
    weights, §11.5) resolving §14's payer-type requirement; **Gewerbesteuer
    sits in the corporate D.51 block** per the national tax list (measured:
    without it R04 coverage is 0.33, with it 0.95). No R02/R05 application:
    the source's Länder-/Gemeindesteuern aggregates mix D.2/D.59/D.91.
  - **FRA/DEU GF07 ← AR health baseline** (0.942/1.021) and **GF09 ← AR
    education baseline** (0.920/0.974), grade B, annual to 2070. LTC is NOT
    added to GF07: the AR gives no GF07/GF10 split of LTC and its
    institutional/home/cash split does not map to COFOG functions.
  - **GF10 ← AR pensions+LTC** measured 0.685 (FRA) / 0.611 (DEU) → C →
    recorded, not applied (no official projection of family, housing,
    unemployment or social-exclusion benefits exists in the harvest; BMAS
    blocked). Stage 4 maximum_extension candidate.
  - **R05 ← AMECO UTKG** measured 0.108 (GBR, D) / 0.763 (FRA, C) / 0.336
    (DEU, D) — recorded, not applied.
Envelope for V15: AMECO URTG/UUTG ×1000 per country-year (through 2027).

## D-S3-004 — Where each line's strict forecast ends, and why (Gate 3 record)
2026-08-31. Horizon per line after Stage 3 (strict; "—" = ends at last
actual, reason in `forecast_declarations.csv`):
**All three** — GF01_7: 2027 (AMECO horizon; DSM leg to 2036 withheld per
OQ-7 for FRA/DEU; no UK DSM). R06: 2027 (AMECO). GF01, GF01_X, GF03–GF06,
GF08, R08, R10: — (D7, declared). R07: — (no reachable machine-readable
receivable-interest forecast anywhere: AMECO has none, DSM is payable-only,
OBR blocked; NI/PB ledger therefore has no forecast years, §4.3). R05: —
(component coverage below strict everywhere). TE/TR: — (envelopes, never
stitched).
**GBR** — GF02, GF07, GF09, GF10, R01–R04: — (OBR/gov.uk blocked, OQ-6);
R09: — (no AMECO UK series).
**FRA** — GF07, GF09: 2070 (AR). R09: 2027 (AMECO). GF02 (LPM), R01–R04
(LPFP/PSTAB): — (PDF-only, §11.4). GF10: — (composite C).
**DEU** — GF07, GF09: 2070 (AR). R01, R03, R04: 2030 (Steuerschätzung).
R09: 2027 (AMECO). GF02 (BMF Finanzplan PDF), R02 (no ESA-complete set),
GF10 (composite C; BMAS blocked): —.

## D-S3-005 — V16 threshold and the first firing: the DSM interest leg is withheld (Q4 space; serves D12, §10 V16)
2026-08-31. §10 gives V16 no numeric threshold. Chosen: 0.02 on annual
growth-factor divergence between consecutive sources in their overlap years
(`tolerances.v16_overlap_divergence`, committee-adjustable). First firing:
AMECO Spring 2026 vs DSM 2025 interest growth diverges up to **−0.065 (FRA)**
and **+0.040 (DEU)** in 2025–27 — the DSM predates the Spring 2026 forecast
and the 2026 rate repricing, so the two vintages disagree exactly where they
would be joined. D12 is explicit ("flag for committee review rather than
auto-joining"), so the engine withholds any long-term leg whose overlap
divergence exceeds the threshold (`not_applied_v16_divergence` boundary
record) and V16 WARNs. FRA/DEU GF01_7 therefore ends at 2027 pending the
committee's call (OQ-7); approving the join or raising the threshold is a
config change plus rebuild, no code change.

## D-S4-001 — Maximum-extension routing: C tier applied, D never applied except the §7.9 mandate (serves §9, §12 Stage 4, D-S2-001 lineage)
2026-08-31, session 3 (continued). The forward engine now routes by grade and
§7.8 status: A/B direct/composite rows enter strict and maximum_extension
(unchanged); grade-C rows and single-component proxies (`max_only`, §7.8)
enter maximum_extension only; grade-D sources stay measured-but-not-applied
(D-S2-001's reasoning: a sub-50% or over-110% mapping fabricates dynamics) —
with exactly one exception, the §7.9-mandated GF01-via-GF01_7 construction
(D-S4-002). Boundary records now carry three applied tiers
(`strict+maximum`, `maximum_only`) plus the non-application records. D2 is
now fully honoured: every proxy/composite row records `residual_method`
(from `config/residual.yaml`, §15 Q3 default `grow_with_proxy` everywhere —
no overrides yet), including the Stage 3 composites that previously carried
None (backfilled; V17 enforces it).

## D-S4-002 — GF01 via GF01_7 growth: applied at its measured D grade (serves §7.9, D2)
2026-08-31. Measured coverage of AMECO UYIG against the GF01 anchor: GBR
0.499, FRA 0.332, DEU 0.165 — all in the D band (interest is the minor share
of general public services). §7.9 nonetheless mandates this exact
construction for maximum_extension ("GF01 total in maximum_extension is
extended via GF01_7 growth with explicit residual_method"), so it is applied
as `proxy_forecast`, grade D, `residual_method = grow_with_proxy`, horizon
2027, with the measured share on every row — the one D-grade application in
the repo, sanctioned by the spec rather than by the grade bands. GF01_X is
NOT derived in these years (D10 "never forecast" read strictly: deriving it
from a proxy GF01 would launder proxy noise into a "derived" observation;
V19's identity check simply has no complete year to bite on). Strict GF01
still ends at the last actual (§7.9).

## D-S4-003 — GF10 dominant-component proxy and the D12 chain that DID join (serves §6.2(4), §7.8, D12; complements D-S3-005)
2026-08-31. AMECO UYTGH (D.62 social benefits other than in kind) measured
against GF10: GBR 0.848, FRA 0.813, DEU 0.803 — clean C-band §6.2(4)
proxies, maximum_extension only per §7.8, horizon 2027. This gives GBR its
only GF10 path (OBR blocked, OQ-6). For FRA/DEU the engine chains UYTGH
(short-term) into the AR pensions+LTC composite (long-term, to 2070) per
D12: overlap divergence measured at most 0.010/yr (2025-27) — UNDER the
0.02 V16 threshold, so this join proceeds where the AMECO→DSM interest join
(D-S3-005) was withheld; both outcomes come from the same rule, which is the
point. Crosswalk `EC_AMECO_to_COFOG.csv` v1.0 carries both mappings.
Not added: a D.62 proxy for lines other than GF10 (no other function is
dominated by cash benefits), and any superset mapping (UTVG→R01/R02,
UTYG→R03/R04 — coverage >110%, grade D by construction).

## D-S4-004 — Gate 4 record: coverage matrix and where maximum now ends
2026-08-31. `data/canonical/coverage_matrix.csv` (§11.6 deliverable 9, 66
rows) is assembled in the build from the canonical tables, both boundary
files and the declarations — never hand-filled. Maximum-extension horizons
beyond strict: GF01 2027 (D proxy, all three); GF10 GBR 2027 / FRA+DEU 2070
(C chain); FRA R05 2027 (C proxy). Everything else: maximum = strict
horizon (the A/B sources) or the last actual (declared lines). Variant
divergence is now two-sided: maximum is deeper in history (Stage 2 C-grade
backward stitches) and longer in the forecast (Stage 4 C/D applications);
strict remains a proper subset row-by-row (Gate 4 leakage tests + V9/V17).

## D-S5-001 — §8.3 forecast decomposition: exact-additive construction and the GDP-path choices (serves §8.3, D16, V26)
2026-08-31, session 3 (continued). `src/ggfiscal/reconcile/explanation.py`
decomposes each WEO balance change ΔB = Δ(GGXCNL/NGDP) from base year b
(per country, variant, vintage, horizon) into: covered-line contributions on
the WEO NGDP path (signed), a per-side denominator effect (the same
contributions on each line's own source-GDP path minus the NGDP version —
§6.3's per-line forecast GDP is taken from the rows' gdp_lcu_mn), per-side
resid_coverage (official total minus covered lines, both on national paths)
and resid_disagreement (WEO minus official total, each on its own path) —
collapsing to a labelled resid_total where no independent total exists —
plus a weo_internal_wedge (GGXCNL vs GGR−GGX rounding inside WEO, ~1e-8).
The construction telescopes, so V26's forecast-side additivity is exact by
identity and verified numerically to 1e-9. §8.3's single-GDP-path rule is
read per table: the forecast tables live entirely at t ≥ b and use NGDP_w
unscaled (comparing shares of WEO GDP with WEO's own path); the history
table (deficit_dynamics) lives at t ≤ b on anchor GDP (D-S1-004) — the two
legs of the chained-at-b path. The §8.3 plausibility memo (implied
annualised growth of the uncovered lines under the official total, with the
same lines' 5-year historical growth alongside) rides as memo rows, marked
% per year, never entering the additivity. Nothing is scaled or allocated
(§8.6): residual rows carry no line_code, tested.

## D-S5-002 — Independent totals, the Q12 deviation made concrete, and the V24 sigma threshold (serves §8.1, §15 Q12/Q4)
2026-08-31. Independent official totals: AMECO URTG/UUTG with the AMECO
UVGD GDP path, all three countries. GBR consequence (OQ-4 + OQ-6): AMECO
has no UK level at any base year, so both GBR sides carry resid_total at
every horizon — the OBR-primary Q12 default remains impossible while obr.uk
is blocked; the rows say so. FRA/DEU get the full coverage/disagreement
split through the AMECO horizon (2027) and resid_total beyond. V24
formalised from D-S0-009's heuristic: FRA/DEU TR/TE/NLB gaps within 1% of
TE in all overlap years; GBR NLB-gap sigma threshold set at 0.5% of TE
(`gbr_perimeter_sigma_pct_te`, Q4 space — measured 0.36–0.42 across
vintages, so green with headroom). All green on the current harvest.

## D-S5-003 — §8.4 net-interest check reported even where not computable; §8.5 keys (serves §8.4-8.5, V27, V28)
2026-08-31. `net_interest_check.csv` carries a row for every (country,
variant, vintage, horizon): NI_weo = GGXONLB − GGXCNL always; NI_ours only
where both GF01_7 and R07 have values — which in forecast years is nowhere
(R07 is declared no-source, OQ-6), so those rows state the reason instead of
being silently absent (V27 enforces both presence and stated reasons). The
one computable class: FRA at h=2025 under the b=2024 vintages (stitched
GF01_7 + anchor R07), gap ≈ −0.5 to +2.1bn EUR — the V21-tier wedge, as
expected. §8.5: every forecast-side table is keyed by (iso3, series_variant,
weo_vintage, source_vintage_set_hash) where the hash digests the
(source_id, release) set actually used by the variant's forecast rows;
`weo_residual_history.csv` extracts the residual time series across the
three harvested vintages (V28 checks the keys on every table).

## D-S5-004 — Gate 5 record: what the granular forecasts explain (headline, WEO 2026-04)
2026-08-31. explained_share = covered contributions / WEO change, strict
(maximum in brackets): **GBR** ≈ 0.04–0.06 (same) through 2027, 0 beyond —
only AMECO lines are covered while OBR is blocked; the WEO's projected
3.8pp-of-GDP consolidation to 2031 is essentially unexplained by reachable
granular forecasts. **DEU** ≈ −0.2–0.2 strict (0.38–0.56 maximum): the
maximum variant's D.62+interest proxies explain roughly half of the WEO's
deficit widening. **FRA** 1.13 at h=2025 (covered actuals slightly
over-explain), then strict ≈ 0.13–0.16 in 2026-27; maximum −2.1 to −2.7:
the covered official forecasts (interest and social benefits, both rising)
move AGAINST the WEO's projected 1.0–2.9pp consolidation — the entire
projected French improvement sits in the uncovered/disagreement residuals.
That directional finding is the module's point (decompose, never force) and
is now stated in reconciliation_report.html for the committee.

## D-S6-001 — WEO vintage register moved into config (serves §11.7, §8.5; narrows D-S0-006's code-side pin; honours D-S0-007)
2026-09-03, session 4. The vintage map (label → dataflow, version,
publication date) now lives in `config/sources.yaml` under
`IMF_WEO.api.vintages`, read by `endpoints.weo_vintages()`; every consumer
(the fetch pull set, §8.2 bridge, §8.3–8.5 explanation, reports, V-checks)
enumerates vintages from it. Registering a new WEO edition is therefore
literally what §11.7 requires — **one config entry plus rebuild, never a
code change**. Proven with a simulated 2026-October edition
(`tests/stage_6/test_vintages.py`): a temporary repo differing from the real
one ONLY in that config entry yields the 15 new IMF_WEO_2026_10 pulls, the
extended reconciliation vintage list, and a clean detect-vintages diff — on
the installed, unmodified code (the temp repo contains no src/ at all).

## D-S6-002 — detect-vintages check paths, and rebuild stays an explicit decision (serves §11.7, §8.5, D-S0-007)
2026-09-03. `ggfiscal detect-vintages` writes `reports/vintage_diff.md`
from two tiers. Metadata tier (default): IMF.RES catalog diffed against the
config vintage register (new_vintage / vanished — a vanished edition is
expected once superseded, its D8 snapshots are the archive); IMF.STA catalog
against the pinned GFS dataflow versions (structural revisions); Eurostat
SDMX 2.1 dataflow annotations (UPDATE_DATA, OBS_PERIOD_OVERALL_LATEST); ONS
dataset-landing releaseDate. Hash tier (`--hash`): every machine-readable
pull re-downloaded and content-hashed against the latest manifest entry,
nothing saved; the IMF catalog document is excluded there because its bytes
embed a per-request timestamp (the WEO check compares it semantically).
Blocked and PDF-only sources are reported with their OQ-5/OQ-6 reference
rather than silently skipped. The command detects and names the exact
config change + rebuild; it does not fetch or rebuild on its own, so
registering a vintage remains a recorded decision (§16), not a side effect.
First live run (2026-09-03): no new WEO edition; the register's
search-derived metadata had drifted from live (Eurostat UPDATE_DATA
2026-07-21 / nama_10_gdp 2026-09-02 vs the recorded 2026-07-23; ONS T11
releaseDate 2026-04-22 vs 2026-04-23) — the verification fields in
sources.yaml were refreshed to the observed values, after which the diff is
clean: 0 findings need action.

## D-S6-003 — Run-manifest completeness (serves §11.1, §11.6 deliverable 11, §16, D8)
2026-09-03. `src/ggfiscal/manifest.py`: `ggfiscal build` writes the base
run manifest pinning every input — per-file sha256 of config/ and
crosswalks/, the full snapshot set consumed, and the environment (python,
pandas, package version) — and each later step (`reconcile`, `report`,
`detect-vintages`, `validate`) re-invokes `update_deliverables()`, so the
latest run manifest ends with the sha256, byte size and CSV row count of
every §11.6 deliverable on disk (absent files recorded as absent, not
omitted). §16's byte-reproducibility claim is thereby checkable from the
manifest alone: same input hashes → same output hashes.

## D-S6-004 — Generated README and the packaging calls (serves §11.6 deliverables 8 and 10)
2026-09-03. `ggfiscal report` now regenerates README.md
(`report/readme.py`) from the deliverables themselves — §11.6 inventory
with row counts from disk, the 66-line coverage table from
coverage_matrix.csv, validation counts from exceptions.csv, the
explained-share headline from weo_explanation.csv, the vintage protocol —
replacing the hand-written stub; hand-edits do not survive a rebuild by
design, with a GENERATED marker saying so. `reports/validation_report.html`
(`report/validation.py`) renders the §10 suite fresh: severity summary,
per-check outcomes with the §10 descriptions, every ERROR, WARN tiers
grouped with examples and their by-design explanations, tolerances in
force. `data/canonical/crosswalks.csv` is the concatenation of
crosswalks/*.csv (identical §11.5 headers, keyed by file stem), written by
the build. Parquet twins for the Stage 5 reconciliation tables were NOT
added: §11.6 lists parquet only for the three long tables and the ledger
(all have twins); the reconciliation tables stay CSV-only, committed.

## D-S6-005 — Gate 6 record: the reproducibility proof (serves §12 Gate 6, §1)
2026-09-03. `tests/stage_6/test_gate6.py` proves Gate 6 from the published
CSVs alone, no pipeline code, no raw data: every stitched or forecast row
records its per-year growth factor and its anchor (§5), so the test
reconstructs each value as the neighbouring year's value × the recorded
growth — backward rows from year+1, forward rows from year−1 — chained down
to the anchor row, which itself must carry its own anchor_value; >900
derived observations verified to 1e-9 across both trees and both variants,
and every derived row is checked to name its growth source, rate and anchor.
§1 objectives asserted: all 66 series built in both variants, the ledger
identities (NLB = TR − TE, PB = NLB + NI where complete), and the
reconciliation tables covering every registered vintage and both variants.
pytest 90 passed; validate OK=55 WARN=661 (no ERROR, no SKIP) — the WARN
delta vs Stage 5's 582 is the append-only manifest carrying three sessions
of snapshot records whose old raw bytes are not in this container
(S0_SNAPSHOTS, by design D-S0-004) plus data-driven counts on the fresher
2026-09-03 harvest.

## D-S7-001 — Hand-retrieved OBR snapshots: ingest-file path, raw bytes committed (serves D8, §11.1, §11.4; narrows D-S0-004; session 5, OQ-6 partial unblock)
2026-09-05, session 5. obr.uk remains behind a Cloudflare challenge no
client here can pass, so the committee hand-retrieved the OBR files in a
browser and they entered the store via the new `ggfiscal ingest-file`
command: content-hashed immutable snapshots like any pull, with the
publication landing URL, original filename and a provenance note recorded
in the manifest. Unlike ordinary snapshots these bytes cannot be
re-fetched by a fresh container, so — extending §11.4's
store-the-PDF-in-raw rule to hand-retrieved xlsx — `data/raw/OBR_*` IS
committed to git (~15 MB: EFO March 2026 annex + detailed tables and
long-term determinants, FRS July 2025 chapter files, PSF aggregates
databank August 2026, historical public finances database). D-S0-004
stands for everything refetchable. Register: OBR_EFO_LATEST resolved to
the March 2026 edition; OBR_FRS supersedes the §13 seed id OBR_FRS_2026
(the edition in hand is July 2025; whether a July 2026 edition exists is
uncheckable from here); OBR_PSF_DATABANK and OBR_HIST_PF added
(history-complement roles; OBR_HIST_PF snapshotted for the OQ-5 pre-1987
interest quick win, no rows built from it yet).

## D-S7-002 — Egress allowlist expanded; PESA 2026 registered; what each unblocked host yields (serves §12 Stage 3, §13, §15 Q7/Q12; updates OQ-6)
2026-09-05. The committee allowlisted www.gov.uk,
assets.publishing.service.gov.uk, www.bmas.de (and the OQ-5-adjacent
www.insee.fr, www-genesis.destatis.de, www.cor-retraites.fr) — all now
reachable; obr.uk stays publisher-blocked (D-S7-001 covers it). Yields:
  - **gov.uk**: PESA 2026 (July 2026) resolved via the content API and
    pulled live (`HMT_PESA`, chapter 1 tables). Table 1.9 Defence = MoD
    total DEL (RDEL+CDEL, £mn): outturns 2021-22..2025-26 + SR25 plans to
    2028-29 — the machine-readable successor to the §13 UK_DEFENCE_PLAN
    seed entry, which it supersedes in the register.
  - **bmas.de**: reachable, but the Rentenversicherungsbericht is a PDF
    publication — ingestion stays gated by §11.4's independent second
    keying (OQ-5), not by the network. DEU GF10/R06 unchanged.
  - **insee/destatis/cor**: reachable; OQ-5 archive work not attempted
    this session (recorded for a future session).

## D-S7-003 — GBR forecast map from OBR/PESA: composites, measured grades, and the non-applications (serves §12 Stage 3 order, §7.8, §7.10-7.11, §9, §11.5, §14, D12, D17, §15 Q7)
2026-09-05. All composites assembled per the ONS national tax list
evidence and validated by measured §9.2 coverage on the GG anchor;
fiscal years converted per §7.10 (first real exercise of `fy_to_cy`);
per-tax series from the PSF databank (August 2026 file, "forecast as of
March 2026" — the EFO vintage), which carries history to 1999 so coverage
is measured on a real overlap. Applied (shares in
forecast_boundaries.csv; crosswalks OBR_to_ESA_REV.csv v1.0,
OBR_PESA_to_COFOG.csv v1.0):
  - **R01 ← VAT + VAT refunds** (0.991, B; the anchor's accrued D.211
    includes refunds — without them the share is ~0.85): strict to 2030.
  - **R02 ← 12 databank duties/levies + EFO A.5 business rates** (0.923
    at CY2025, the single overlap year — business rates exist only in the
    annex table; without them 0.70-0.73): strict to 2030.
  - **R03 ← PAYE + SA + other income tax + CGT** (1.032, B) and
    **R04 ← CT onshore (incl. bank surcharge/EGL) + offshore + PRT + EPL
    + DPT** (0.988, B): strict to 2030.
  - **R05 ← council tax + IHT + licence fee** (0.787, C):
    maximum_extension to 2030 — GBR R05's first forecast of any kind.
  - **GF02 ← PESA 1.9 MoD DEL** (0.9005 at CY2024 — §15 Q7's ≥90% strict
    condition met, just): strict to 2028, grade B; CY2025 lands as a
    stitched newer actual (both underlying FYs are PESA outturns).
Measured and NOT applied (boundary records carry the shares):
  - **R07 ← PS interest and dividend receipts** (2.63: dividends + PS
    perimeter inside a D.41-resources line — D).
  - **GF01_7 ← CG debt interest net of APF** (share drifts 0.67→1.28
    across the overlap: PSF vs ESA recording — D; AMECO UYIG stays the
    strict source, still ending 2027, OQ-7 unchanged).
  - **GF10 ← EFO welfare spending**: the table starts FY 2024-25, so the
    converted series shares no year with the GG anchor — §9.2 coverage
    unmeasurable; the AMECO D.62 proxy (C, 2027) remains.
  - **R06 ← NICs** (0.756, C): the D12 chain beyond AMECO's 2027 was
    withheld by the V16 overlap-divergence rule — same rule, same outcome
    class as OQ-7's DSM join; committee can approve either via config.
FRS July 2025 (in hand) is thematic — pensions/balance-sheet/climate —
and carries NO functional long-term projections, so GBR GF07/GF09 stay
declared; the FRS edition with them (2024, or 2026 if it exists) is a
named ask in OQ-6. §15 Q12 is now exercised as written: the GBR V15
envelope and §8.3 independent totals are OBR PS current receipts / TME
with the OBR GDP path (stable 0.95-0.97 perimeter ratio to the GG totals,
documented; AMECO remains the cross-check).

## D-S7-004 — Session 5 gate record: what the OQ-6 unblock changed (serves §8.3, §12, D-S5-004 lineage)
2026-09-05. Full rebuild green: pytest 90 passed; validate OK=55 WARN=661,
no ERROR, no SKIP. Two defects the suite caught on the first rebuild and
their fixes, for the record: V10 flagged the FcSource horizon convention
(now stated as the last calendar year the source's native FY periods
touch, with V10 netting the §7.10 conversion loss), and V17 flagged the
R01 composite's missing D2 residual_method (added). GBR explained share
(WEO 2026-04, from weo_explanation.csv): **strict 0.55-0.67 and maximum
0.60-0.76 across 2026-2030**, up from 0.04-0.06 — the D-S5-004 headline
that "the WEO's projected UK consolidation is essentially unexplained" is
superseded for horizons through 2030; 2031 stays ~0 (beyond the OBR
horizon). GBR also gains the full §8.3 coverage/disagreement residual
split through 2030 (previously resid_total everywhere per D-S5-002 —
that reading is superseded by Q12's OBR totals; resid_total remains only
at 2031). Strict horizons: R01-R04 2030, GF02 2028 (grade B, Q7),
GF01_7/R06 2027 (AMECO; OBR legs withheld per D/V16 — OQ-7). Maximum
adds R05 to 2030. GBR GF07/GF09/GF10 long-term legs remain the biggest
open item (OQ-6 asks a/b).

## D-S8-001 — OQ-7 RESOLVED by the committee: above-threshold joins approved and applied (serves D12, §10 V16, §15 Q4 space; resolves OQ-7; supersedes the stops in D-S3-005 and D-S7-003's R06 leg)
2026-09-05, session 5 (continued). The committee (AC) instructed "do
OQ-7", read as OQ-7's option (a): approve the withheld joins, accepting
the vintage seam. Mechanism: a new committee-controlled config list,
`tolerances.v16_approved_joins` in `config/countries.yaml` — one row per
(iso3, line_code, incoming_source). The engine applies a listed join
despite above-threshold overlap divergence, with three invariants kept
deliberately: (1) grade rules still hold, so an approved C-band leg
enters maximum_extension only; (2) V16 keeps WARNing on the divergence —
approval changes application, never visibility — with the message
switched to "committee-approved and APPLIED, seam flagged"; (3) the
applied boundary record carries the approval note and the measured
divergence. D-S3-005 promised config-only approval; the granular per-join
knob did not exist, so this entry adds the one generic mechanism — any
future approval is now genuinely one config row plus rebuild.
Approved and applied:
  - **FRA GF01_7 ← EC_DSM** and **DEU GF01_7 ← EC_DSM** (grade B):
    strict AND maximum now run to **2036** (join at 2028; divergence up
    to −6.5pp/yr FRA, +4.0 DEU in the 2025-27 overlap — the DSM 2025
    predates the Spring 2026 repricing; re-examine the seam when DSM 2026
    arrives ~Feb 2027, which is a vintage refresh, not a re-adjudication).
  - **GBR R06 ← OBR NICs** (grade C): maximum_extension to **2030**
    (strict correctly still ends at AMECO's 2027 — approval does not
    launder a C grade into strict).
NOT approved (not listed): GBR GF01_7 ← OBR CG debt interest — that
candidate fails on concept (grade D, D-S7-003), which no join approval
can cure. Also out of scope: the §7.9 GF01-via-GF01_7 maximum proxy
keeps its 2027 horizon — its source is AMECO UYIG directly, and
extending it through the DSM leg would be a new join the committee has
not been asked about.
Observed effect, rebuilt and tested (90 passed; validate OK=55 WARN=661,
no ERROR/SKIP): the published GF01_7 series for FRA/DEU now runs to 2036
in both variants — a deliverable in its own right (§1, and the §8.4
NI-check numerator) — while the §8.3 explained shares for FRA/DEU are
UNCHANGED by construction: the decomposition operates on the 20 Level-I
lines (D-S1-004) and interest sits inside GF01, whose strict series
still ends at the last actual (§7.9). The GBR R06 maximum leg does move
its share: maximum explained_share 2028-2030 rises to 0.68/0.71/0.75
(from 0.65/0.66/0.69). The Gate 3 D12 test now asserts whichever state
`v16_approved_joins` declares, so removing an approval row restores the
withheld assertions without a code change.

## D-S9-001 — The end product is a flat-file bundle plus a derivation notebook; `deliverables/` and `notebooks/derivation.ipynb` (serves §1, §11.6; extends D-S6-003)
2026-09-08, session 6. The committee (AC) asked for the end product to be
"extremely simple: flat files with all the series ... and a python notebook
explaining how each series was derived". The canonical layer already holds
every number, but at 47 columns across four variant files and six
reconciliation tables at three grains it is a pipeline artefact, not a
readable product. Two additions, no methodology change:
  - **`deliverables/`**, written by the new `ggfiscal flatten` (module
    `src/ggfiscal/publish/flatten.py`, also run as the last step of
    `ggfiscal report` so the bundle cannot fall behind a reported run):
    `expenditure_cofog.csv`, `revenue_esa.csv`, `balance_ledger.csv`,
    `weo_levels_bridge.csv`, `weo_reconciliation.csv`,
    `series_catalogue.csv`, `data_dictionary.csv` and a README. Both
    variants live in one file behind a `variant` column; the two WEO files
    unify tables the pipeline keeps apart (base bridge + net-interest check;
    history decomposition + forecast decomposition) behind a `block` column,
    with the differing bases spelled out per row rather than blended.
  - **`notebooks/derivation.ipynb`** — executed, outputs committed, reading
    only the flat files (never `data/canonical/` or `data/raw/`), so it is
    readable on its own and re-runnable with pandas + matplotlib. It prints
    the derivation of all 72 published series from `series_catalogue.csv`
    and re-proves the chain arithmetic in-place.
Three invariants make the bundle safe to trust as much as the canonical
layer, and `tests/deliverables` enforces all three: (1) **no value is
recomputed** — every number is copied, and the canonical CSVs are read with
`float_precision="round_trip"` so the published decimal text is the
canonical decimal text, bit for bit (the default parser loses an ULP per
round trip, which would compound on every republication); (2) **every row
carries its own derivation** in the Gate 6 form
`value(t) = value(t±1) × growth`, so the flat file alone reproduces every
stitched and forecast value; (3) **the data dictionary covers every column
of every file**, tested by set equality against the headers on disk.
The bundle is tracked in the run manifest under a new `flat_files` key
rather than inside `DELIVERABLES`, so a run that legitimately stops at
`reconcile` is still a complete §11.6 run.
Two documentation errors this work exposed and corrects: the variants do
**not** differ only forward — `maximum_extension` also carries longer
*backward* legs where the backward source grades C (GBR R02 to 1965,
FRA R04/R06 to 1965, DEU R04/R06 to 1991) — and `ANCHOR_B9_DELTA` in
`deficit_dynamics.csv` is the anchor-minus-sum *wedge*, not the anchor's own
change; a third history memo, `WEO_GGXCNL_DELTA`, carries the WEO's own
year-on-year change and is the history-side leg of the WEO reconciliation.
All three are now stated in the dictionary and the notebook.
Also fixed while making the bundle reproducible from a clean clone:
`openpyxl` and `xlrd` moved from "install them yourself" (session-5 HANDOFF)
into `pyproject` dependencies — the committed OBR snapshots cannot be read
without them — and a `notebook` extra added for re-executing the notebook.
Rebuild green on the 2026-09-08 harvest: **pytest 109 passed** (90 + 19 new),
`validate` **OK=55 WARN=820, no ERROR, no SKIP** (WARN up from 661 on
vintage drift alone — V25/V1 concept wedges on refreshed Eurostat/OECD
pulls; no new check and no new tier).

## D-S9-002 — A second notebook: `chartbook.ipynb`, one chart per series (serves §1, extends D-S9-001)
2026-09-08, session 6 (continued). The committee asked for "a very chart
heavy notebook ... so that I can eyeball work quality", laid out country →
category → series, with the WEO reconciliation shown separately as our
series against the WEO's on shared axes, for revenue, expenditure and NLB
per country. Delivered as `notebooks/chartbook.ipynb`: 102 figures, 101
code cells, reading the flat bundle and nothing else (the D-S9-001
invariant), executed with outputs committed.
Design choices that carry information rather than decoration:
  - **Seams are drawn.** Each series chart marks with a dotted rule every
    year where `observation_type` or `source_id` changes — the exact
    points where a stitch could show a step. A seam with no visible kink
    is the pass condition; §6 tabulates all of them with the year-on-year
    change across each, sorted by size, as a triage list.
  - **Projection years are shaded**, so a chart that is two thirds
    projection (FRA/DEU GF07/GF09/GF10 to 2070) cannot be misread as data.
  - **Both variants on one chart**, orange drawn only where
    maximum_extension goes beyond strict — so the reader sees at a glance
    which part of a series is officially sourced.
  - **The WEO charts are two-panel**: levels above, gap as % of TE below.
    The gap panel is where the answer is: flat means a definitional
    perimeter wedge, drift means a vintage difference. Two panels, never
    two y-axes.
  - Palette: categorical slots 1-3 of the validated default (blue #2a78d6
    = our strict series, orange #eb6834 = maximum_extension, aqua #1baf7a
    = the IMF WEO), assigned by entity and never reused, with line style
    repeating the distinction so identity never rests on colour alone.
    Validated all-pairs; the aqua step's sub-3:1 contrast is relieved by
    direct end-of-line labels on the charts that use it.
Ten things do not fit a flat country → category → series layout, and are
listed in the notebook's own §"Series that do not fit this schema" rather
than left for a reader to trip over: the two-variant duplication; GF01_X as
an identity with no forecast leg by construction; TE/TR as envelopes rather
than members of the 66; the ledger as outturn-only with anchor totals
rather than line sums; the two GBR TE numbers (charted in §5 — under 0.02%
apart until 2023, 0.51% in 2024; FRA ≤0.055%, DEU 0); the WEO level
comparison existing only over the overlap years; `weo_reconciliation.csv`
being contributions rather than a time series, so only `explained_share` is
chartable; the 1991/1995→2070 horizon asymmetry; interior gaps in NI/PB (16
ledger rows); and `pct_gdp` not spanning what levels span (60 rows, FRA
pre-1975, where Eurostat GDP starts after the OECD tax series).
`tests/deliverables` gains three tests: both notebooks are executed,
error-free and read only the bundle; and the chartbook charts every one of
the 72 catalogued series plus all 15 ledger and 9 WEO comparisons — a
series that gained a chart nowhere would otherwise be invisible.
pytest 112 passed; validate unchanged (OK=55 WARN=820, no ERROR, no SKIP);
no data file changed.

## D-S9-003 — Chartbook revisions: one x-axis per country, projection shading on every chart, and the reason a series has no forecast stated on it (serves D-S9-002)
2026-09-08, session 6 (continued). Three committee asks on
`notebooks/chartbook.ipynb`, all delivered:
  - **One x-axis per country** across sections 1-3 (every series chart and
    every ledger chart), spanning every year that country publishes on any
    series or in its ledger: **GBR 1965-2030, FRA 1965-2070, DEU
    1991-2070**. Charts can now be laid beside each other and read against
    the same calendar. The cost is stated rather than hidden: France's
    axis runs to 2070 because 4 of its 24 series do, so a 1995-2024 series
    occupies under a third of the width. Two escape hatches, both in the
    setup cell — `xlim=` on any single chart, and two commented lines that
    put all three countries on one shared calendar. Sections 4 (WEO) and 5
    (the two TE totals) deliberately keep their own spans: they compare
    two lines *inside* one chart, and stretching them to 2070 would
    squeeze the gap panel — the part carrying the answer — into a quarter
    of the width.
  - **Projection shading on every chart**, whether or not the series
    reaches into it. Previously it was drawn only where a forecast
    existed, which made "no forecast" look like "chart ends here". Now the
    band starts at that series' own last outturn and runs to the axis
    edge, and a series with nothing to put in it is tagged `no projection
    published` on the plot. Sections 4 and 5 are outturn-only comparisons
    with no projection region at all, and say so.
  - **Every series states why it has no forecast.** The caption under each
    chart now gives one line per variant — `strict:` and `maximum:` —
    saying either "projects to YYYY — <why it stops>" or "NO PROJECTION —
    <plain-language reason>. <the pipeline's own note>". A new section
    before the charts gives the taxonomy and the full table: **44 of 72
    series carry no projection at all** and 8 more project only in
    `maximum_extension`, across five recorded statuses —
    `no_official_forecast` (24), `source_blocked` (8), `not_extended` (6,
    the TE/TR envelopes), `no_machine_readable_source` (5),
    `grade_below_strict` (1). This is a statement about what official
    bodies publish, not a gap in the work (D13/D16).
Also, `deliverables/README.md` loses the wall clock from its generated
header, keeping the run id: re-rendering an unchanged bundle was producing
a one-line diff every time, including on every `pytest` run through the
`tests/deliverables` fixture. `ggfiscal flatten` is now deterministic given
the canonical layer, as §16 requires of the rest of the pipeline.
Two new tests lock the behaviour in: the shading is unconditional and the
axis is per-country (asserted against the setup cell, including that the
old `if mx.year.max() > actual` guard is gone), and — the substantive one —
every `chart()` cell's committed output says NO PROJECTION on exactly the
variants that stop at the last outturn, checked per variant against the
catalogue for all 72 series, with a recorded status behind each. pytest 114
passed; no data file changed.

## D-S9-004 — Chartbook: axis capped at 2031, and made small enough for GitHub to render (serves D-S9-002/003)
2026-09-08, session 6 (continued). Two committee reports, both real.
**(1) The 2070 axis was wrong.** D-S9-003 aligned each country's charts on
its full span, which meant 1965-2070 for France because four of its 24
series carry Ageing-Report legs to 2070. The committee asked for
**start date until 2031** on every chart. Applied everywhere — sections
1-3, the WEO comparison in §4 and the TE diagnostic in §5 all now run
from the country's first published year to 2031 (GBR/FRA 1965, DEU 1991);
the only exception is §4.4, whose data exists only for the 2026-2031
horizons. The four long-horizon series per country leave the right edge
with a `continues to 2070 →` marker and their true final year in the
caption; the values are unchanged in the flat files.
  Capping the axis exposed a defect the previous version had hidden:
matplotlib autoscales y over ALL plotted data, so clipping x to 2031 left
FRA GF10's y-axis running to 3,000,000 — the 2070 value — flattening the
1995-2025 history into the bottom fifth of the chart. Fixed by plotting
only the data inside the window plus one point past the edge, so the
y-axis follows what is actually visible.
**(2) The notebook could not be rendered on github.com.** At 3.28 MB
(94% of it embedded PNGs) GitHub's client-side notebook renderer shows
"Loading" forever. Confirmed it is size, not structure: both notebooks
pass `nbformat.validate`, carry no error outputs and no unexecuted cells.
Reduced to **0.88 MB** — a 3.7x cut — by three measures, none of which
touches what the charts say: figures at 497x194 px (from 648x261),
palette-quantised PNGs, and a caption that says a variant's horizon once
rather than twice when both variants agree.
  The quantisation needed care. An *adaptive* palette allocates slots by
pixel count, and a dashed line has few pixels: at 32 colours it crushed
the orange series to #927670, a muddy brown 108 units off the validated
hue — the palette discipline of D-S9-002 silently broken. So the notebook
quantises onto a **fixed** palette built from the chart colours
themselves (each mark colour exactly, plus its blends toward the two
backgrounds for antialiasing). Verified numerically: every brand hue is
present at distance 0.0 in the figures that use it.
  GitHub's threshold could not be verified from this environment —
notebook rendering is client-side, so fetching the blob page returns
"Loading" for any size, including the 0.22 MB derivation notebook that
renders fine in a browser. 0.88 MB is therefore a judged margin, not a
measured one. The generated README now names nbviewer as the fallback for
any notebook GitHub declines, and if the chartbook still fails the next
step is splitting it one notebook per country (~250 KB each).
Two tests updated and strengthened: the axis assertions now pin
`XMAX = 2031` and that every chart family still shades; the projection
test handles the collapsed `both:` caption line. That test also had a bug
of its own — `next(gen, next(gen2))` evaluates the fallback eagerly, so it
raised StopIteration on any series that did have a `strict:` line. pytest
114 passed; no data file changed.

## D-S9-005 — Three per-country strict matrices: `deliverables/strict_{GBR,FRA,DEU}.csv` (serves §1, D-S9-001)
2026-09-09, session 6 (continued). The committee asked for one file per
country holding every series the chartbook plots, **strict variant only —
no maximum_extension**. Added to `ggfiscal flatten`, so they are part of
the bundle and regenerate with it.
Shape: one row per year, one column per series, column names the
concatenation of `line_code` and `line_label` as requested (`GF01_7 -
Public debt transactions (interest)`). Columns in chart order: GDP, the
12 COFOG lines + TE, the 10 ESA lines + TR, then the ledger. Levels in
millions of national currency; GDP is carried so ratios are one division
away.
Two design points worth the record:
  - **The ledger's TR and TE are prefixed `LEDGER_`.** They are the
    balance anchor's own totals, not the trees' TE and TR, and for GBR
    they come from a different ONS table and differ by up to 0.5%
    (D-S9-002 §5). Merging them into one column would have silently
    picked a winner; both are published side by side instead.
  - **Rows run to the last year any strict series reaches**, not to the
    chartbook's 2031 display cap: GBR 1965-2030, FRA 1965-2070, DEU
    1991-2070. FRA/DEU carry only GF07 and GF09 after 2036 — the Ageing
    Report legs, which are strict (grade B). Truncating real data because
    a chart axis was truncated would be the wrong trade.
The ragged right-hand edge is the point, not a defect: a column stops
where its official forecast stops, which is why 44 of 72 series end at
their last outturn (D-S9-003).
Verified cell for cell before shipping: all 2,724 strict values reproduce
exactly, no year/series present that the strict variant does not publish,
and none of the maximum-only legs — forward or backward — leaks in. Five
new tests hold it, including an explicit assertion that the maximum-only
legs are absent and a guard that fails if the fixture ever stops having
any. pytest 120 passed; no data file changed.

## D-S9-006 — The forward balance: why `explained_share` exists where a forward "our NLB" does not, and the chart that shows it (serves §8.3, D-S9-002)
2026-09-10, session 6 (continued). The committee asked a fair question of
the chartbook: §4.4 reports a share of the WEO balance change explained,
for both variants and all three countries, while §1-3 show no NLB
projection and §4.1-4.3 stop at the last outturn. How can one exist
without the other?
The answer is a real asymmetry and is now stated in the notebook rather
than left implicit: **a level needs every component, a change does not.**
Our NLB is TR - TE on the balance anchor's own published totals, and
those anchors publish outturns only; the sole way to state a forward
level would be to sum our forecast lines, and 44 of 72 series carry no
forecast at all (D-S9-003). For GBR 2028 that would mean adding defence,
interest and four tax lines and calling the result "expenditure". The
ledger therefore stops (§4.3) and the honest answer is that we have no
forward NLB. A *change* survives the same gaps because the missing part
is named: each covered line contributes its own d(line/GDP), each
uncovered line contributes nothing to the covered total and is booked as
`resid_coverage`. Nothing is set to zero by accident — the hole is a
number in the table. That is precisely what D13/D16 buy.
Added, since the comparison the levels charts cannot make can be made in
one honest form: a **forward-balance chart per country** — the WEO's
projected NLB/GDP path from its base year, and beside it the base year
moved only by the lines we hold an official forecast for, for both
variants. The vertical gap is the residual. Labelled emphatically as NOT
a forecast of our balance: it is the base year plus the part of the WEO's
move our lines account for, and the gap is the subject.
Two presentation decisions the data forced:
  - **The covered path breaks where coverage runs out.** GBR 2031 has
    ZERO covered_line rows (every source horizon has expired), so
    covered_total is 0 there — which drawn naively is a cliff back to the
    base year, reading as a projected deterioration. It is undefined, not
    flat, so the line stops and is annotated "no covered forecast from
    2031".
  - **A three-year run-in, not ten.** A decade of history drags 2020 onto
    the axis (GBR -12.6% of GDP) and squashes the forward fork flat.
Headline readings at the latest vintage (2026-04): GBR, the covered
strict forecasts account for +2.12pp of the WEO's +3.68pp consolidation
to 2030 and nothing at 2031; FRA, +0.13pp of +2.89pp to 2031 — the
projected French consolidation sits almost entirely in residuals, and the
maximum-extension path moves the other way; DEU, the WEO projects a
widening deficit (-0.99pp) while the covered lines improve slightly, so
the share is negative.
Verified while building it: the forecast decomposition is additive in the
bundle to 1e-9 — but ONLY once `weo_internal_wedge` is in the identity.
The WEO's own GGR - GGX does not exactly equal its GGXCNL (max 3.2e-05 pp
of GDP), and the pipeline reports that discrepancy as its own component
rather than absorbing it into ours. A test now pins the full identity,
and a second pins that a horizon with no covered line contributes nothing
covered. pytest 122 passed; no data file changed.
## D-S10-001 — Debt-in-issue extension scoped; committee accepted the defaults; `DEBT_KICKOFF.md` v1.0 governs the debt side (serves §1 extension, §16; new decisions DD1–DD13)
2026-09-09. The committee asked for the register of central-government
marketable debt securities per country, with per-security interest,
issuance/redemption/buy-back flows and a residual-maturity profile, each
reconciled to the package's `GF01_7` and `NLB`. A research pass (four
source catalogues, condensed in `DEBT_SCOPING.md`) established that every
bond-level publisher (DMO, AFT, Finanzagentur) and every central-bank data
host is denied by the egress policy, while the statistical and
finance-ministry sources around them are reachable and verified. The
committee accepted all eleven scoping defaults (Q-D1–Q-D11), recorded as
DD1–DD13 in `DEBT_KICKOFF.md` v1.0: central-government marketable
securities incl. bills; accrued and cash interest both computed, uplift as
interest; three-step reconciliation chains with official intermediates and
published residuals (never allocated); calendar year with GBR financial-
year memoranda; residual-maturity bucketing at settlement for issuance;
machine-readable sources only in this phase; BoE APF overlay and BoE yield
curves stored now; reference-rate gaps declared `not_computable`. Build
proceeds in the same package as `ggfiscal.debt` with register entries in
`config/debt_sources.yaml` merged into `config.sources()`, so the source
register and vintage detection cover the extension without a second
mechanism. The access question is OQ-8; harvest of reachable sources
(Stage D0) does not wait for it.

## D-S10-002 — Stages D0 and D1 complete on the reachable sources; the debt-office hosts remain the D2 blocker (serves DEBT_KICKOFF.md §12 D0–D1, §13; depends on OQ-8)
2026-09-09. Four source families harvested into the D8 store with readers
and tests: BoE (18 pulls: APF operations per ISIN 2009–, yield curves
1979–, SONIA, Bank Rate), ONS/HMT (41: PSF Appendix A and S, PUSF and RPI
series, Debt Management Reports, National Loans Fund accounts 2005-06–),
BMF (20: Datenportal monthly Bund debt/issuance/redemptions/interest by
instrument 1996–, Kreditaufnahmeberichte 2013–2025, Monatsbericht,
Haushaltsrechnung), Eurostat/INSEE/OECD (59: D.41 and B.9 by subsector,
debt by instrument/holder/maturity, quarterly debt, HICP and CPI
ex-tobacco, money-market and long rates, OECD quarterly public-sector
debt). The debt-office family carries complete pull definitions (incl.
the month-end D1A COBDate loop) that fail on the egress denial and are
reported, not skipped. `ggfiscal debt build` writes two schema-checked
canonical tables: `debt_reference_series` (350 series incl. the BoE
curves) and `debt_official_totals` — the step A/B/C intermediates of both
chains per country-year. Findings that shape D2–D4: (i) the two GBR
step-A/B measures (NLF finance costs, ONS NMFX) agree within 10% and the
package's GF01_7 sits 1–2% above NMFX; (ii) DEU step A is cash-like
(disagio at value date until 2024) and swings against S.1311 D.41 by up
to 15 EUR bn in 2023, exactly the bridge item the chain must carry;
(iii) FRA has no reachable step A; (iv) Eurostat's remaining-maturity
table starts 2020 for FRA and carries four of seven bands for DEU, so
the maturity cross-check is thin outside the register; (v) BMF HTML
carries per-request bot-manager tokens, so hash-based vintage detection
must normalise it. Per DD8 the next step while OQ-8 is open is an
aggregate class-level layer (ministry instrument-type totals, grade B/C)
feeding the register step of both chains, so the reconciliations can be
published for every year the aggregates cover and replaced security by
security as the offices become reachable.

## D-S10-003 — Both reconciliation chains published on the aggregate class layer; what closes, what remains, and the DEU perimeter choice (serves DEBT_KICKOFF.md §8, §12 D2–D5, DD4/DD5/DD8; depends on OQ-8)
2026-09-09. With the debt offices still denied (OQ-8), the register step of
both chains is the ministries' own instrument-class aggregates (DD8; config
`register_selection` names the one consistent row set per country so a
source's total is never added to its components). Results, residual by step:
  - **DEU interest**: step A closes to zero 1996–2025 (BMF instrument
    leaves + the Mitfinanzierung item = Kreditaufnahmebericht annex 4.5);
    step B is the cash-vs-accrual wedge (agio/disagio at value date until
    2024; Eurostat's ORD41A_ADJ item is applied where published); step C
    carries Länder, local and social-security D.41 and leaves the
    consolidation/COFOG-vs-D.41 wedge (≈ 2–4 EUR bn).
  - **DEU financing**: step A closes to zero 2019–2025 (special funds
    subtracted, annex 4.10 derivation items applied; the 2023 edition's
    correction-booking rows and 2019's reversed wrapping are parsed);
    2009–2018 use the narrative-table NKA (narrower concept, whole EUR mn)
    with the derivation items unavailable, residual published. Step B adds
    the special funds back (they are S.1311) and the Eurostat EDP
    stock-flow items 2022–; what remains is the S.1311 perimeter beyond the
    Bund and its funds (FMS-Wertmanagement and other federal units) and is
    left as residual, not allocated. Step C closes exactly.
  - **GBR interest**: step A is the NLF finance costs (FY→CY per §7.10)
    with NS&I and other costs as items, closing by construction 2009–2024;
    step B (NLF → ONS NMFX) has no published bridge and swings ±£10 bn with
    the index-linked uplift; step C carries local-government D.41 (PSA6J)
    and leaves the COFOG-vs-D.41 wedge (≈ £0.1–0.2 bn).
  - **GBR financing**: step A closes to zero 1997–2025 (ONS Appendix S is
    an identity); step B closes to £2 mn (REC2 columns + PSA7C coverage
    items); step C closes to ≤ £13 mn (PSA2 local-government net borrowing).
  - **FRA**: no step A on either chain (programme 117, AFT blocked);
    interest step B has no carried value and step C closes to the
    consolidation/COFOG wedge (≈ 1.5–4 EUR bn); financing register = Δ
    year-end stock (INSEE/AFT, Eurostat), step B via Eurostat EDP items
    2021– leaves −0.6 to −4 EUR bn (buy-backs and ODAC perimeter), step C
    closes exactly.
Decision on the DEU step-A concept: the core-budget Nettokreditaufnahme is
kept as the step-A total (it is the published, audited figure) and the
special funds are re-added at step B, rather than inventing an S.1311-wide
cash measure. All residuals are published per (country, year, step); V32
additivity is exact; `ggfiscal debt validate` reports 19 OK, 25 WARN (V31
Bund-vs-S.1311 perimeter, ≤ 8% narrowing to 1%), 8 SKIP (register checks).
Deliverables: `deliverables/debt_*.csv` (five files, in the dictionary and
README) and `notebooks/debtbook.ipynb`.

## D-S10-004 — Germany's per-security register built and reconciled; the DMO and AFT need a browser and now serve interactive captchas (serves DEBT_KICKOFF.md §12 D2–D4; updates OQ-8)
2026-09-10. With every domain allowlisted, the Finanzagentur served all
its files on plain HTTP: the per-ISIN annual list since 1995, the monthly
list, the auction history, the three index-ratio archives and the
Kreditaufnahmeberichte 2004–2012. `register_deu.py` builds 1,654
securities, 5,348 year-end positions (1995–2025), 6,163 flows and 31,102
index ratios; Σ nominal reproduces the office's Umlaufvolumen exactly
(1.0000 in 2024) and the recurrence snapshot(t) = snapshot(t−1) + Σ flows
holds to the cent on the sampled Bunds. The engine now computes interest
per security (13,866 security-years, one not computable), the maturity
profile and issuance by bucket for every year, and the chains take the
computed register sums at Germany's register step with three computed
step-A items derived from the same flows: issue premia/discounts at value
date, accrued interest received on reopenings, and the change in the
Bund's own book. What remains at step A (2005–2025) is −1 to −8 EUR bn:
largest in the negative-yield years, where the ministry's net figure
includes interest income the register cannot see. Decisions: (i) the
computed register uses the CASH basis at the register step because the
ministries' step-A totals are cash; the accrued figures are published
alongside in `debt_interest_by_security`; (ii) securities issued before
the auction history (1999) lack coupons in some cases, so the register
step is short before ~2003 — the aggregate layer remains the better
register for those years and the tests start at 2005; (iii) retail paper
listed by the office (Bundesschatzbriefe, Finanzierungsschätze) stays in
`other` so the office's own total reproduces, flagged for a strict DD1
consumer. The DMO and AFT: reachable, but both answer with JavaScript
challenges; the committee authorised a browser session (browser.py: TLS
capped at 1.2 through the proxy, one landing navigation per host, polite
interval), which cleared both challenges on first contact but, after the
repeated automated visits needed to debug the route, both sites now
serve interactive captchas. Automated attempts are stopped; the hand-
download list (`DOWNLOAD_LIST.md`, `ggfiscal debt ingest-incoming`) and a
cooled-off retry are the two ways forward, recorded in OQ-8.

## D-S10-005 — The UK register from the DMO's own reports: positions rolled from the operations record, ratios recomputed from the RPI, chains on the accrued basis (serves DEBT_KICKOFF.md §12 D2–D4 GBR; updates OQ-8, raises OQ-9)
2026-09-10. **Access.** The DMO's export endpoint
(`/umbraco/surface/DataExport/GetDataExport?reportCode=…&exportFormatValue=…`)
is reachable from the build box through the committee-authorised browser
session: the ShieldSquare challenge clears for it, while the HTML report
pages keep re-challenging. Each report exports in exactly one presentation
type — xml for D1A, D2.1E, D4L, D10C, D2.2D; xls for D1C, D2.1A, D2.1PROF7,
D2.1PROF9, D10A (an HTML table under the .xls name), D8B, D2.2E, D2.2G —
and every other pair, the plain `ExportReport` form and the `COBDate`
year-end snapshots answer with the 35-byte stub "Unable to fulfil the report
request" under a 200 (the committee's desktop run had saved 37 of these as
data; the family, the ingest command and the desktop script now refuse
them). D1D, D5I, D9C and D2.2A export in no format. Fourteen reports are
snapshotted; the AFT still needs the desktop run.
**Method.** With no positions table by date, the register takes the office's
two anchors — nominal in issue at the close of business (D1A) and nominal
outstanding at redemption for every gilt redeemed since 1981 (D1C) — and
walks them back through the complete operations record (D2.1E, signed
nominal per operation since 1981-03-27). Σ operations reproduces D1A for
102 of 104 gilts in issue and D1C for every redeemed gilt the record covers
(tranches such as `8½% Treasury Loan 2007 A` folded into their parent);
where the sum falls short — pre-1981 issues, early-1990s tenders the extract
omits, and the 154 older stocks with no operation at all — the difference is
one `implied` flow dated 1981-01-01, graded B/C and never allocated to a
later date, so the year-end positions are exact from each security's first
recorded operation and constant before it. Bills are one security per
maturity date from the tender history (D2.2D, from April 2000), redeemed at
par. Index ratios: the DMO's 3-month-lag formula on the ONS RPI reproduces
every D10C reference RPI and ratio to 5 dp, so ratios are recomputed for the
whole life of every linker (monthly points; the formula is linear within the
month, as the engine interpolates); 8-month linkers use RPI(m−8) on the base
of the issue month. **Result.** 1,747 securities (283 conventional, 56
index-linked, 2 floating, 1,406 bills), 4,404 year-end positions 1981–2025
plus 104 office snapshots, 8,173 flows, 10,562 ratio points; the recurrence
snapshot(t) = snapshot(t−1) + Σ flows holds on all 3,499 year-end pairs. The
unindexed nominal of index-linked gilts equals HMT's DMR table A.1 to the
million at end-2023/2024/2025 (382.0 / 393.5 / 433.4 £bn) and the uplifted
nominal is within 0.7–1.3%; bills equal ONS BKPJ exactly 2001–2006 (later
years carry bilateral/ad hoc bills outside the tender history, 0.6–1.0).
Conventional gilts exceed the DMR/ONS figure by 150–171 £bn (8%) in
2023–2025 and the ONS gilt stock by 7–17% from 2008: the ONS and DMR
figures are consolidated within central government (gilts held by the DMA,
CRND funds and other CG bodies netted), the register is the DMO's gross
creation — raised as OQ-9, published as V31, never adjusted. Before 2005
the register is short of the ONS stock (0.85 in 1997): gilts converted or
switched out in full before 2000 appear in neither D1C nor D2.1E.
**Chains.** (i) The UK register enters the interest chain on the ACCRUED
basis: the NLF accounts are accruals-based, so HMT's step-A total carries
accrued uplift and effective-interest amortisation, and the BMF-style
value-date bridges do not apply; the basis and the bridge items are now per
country in `config/debt.yaml` `register_chain_items` (DEU unchanged: cash
with the two value-date items). Step A then closes to within ±3.3 £bn
(≤ 6%) in every year 2010–2024 except 2009 (+8.4, the deflation year's
negative uplift), 2012 (+4.8) and 2021 (+6.3), with National Savings and
the other NLF finance costs as the only out-of-register items. (ii) The
financing chain gains one computed bridge, `issuance_cash_less_nominal` (Σ
cash raised − nominal created, from the priced operations: −19.7 £bn in
2022, +34.5 in 2020); step A then closes within ±13 £bn 2010–2025 except
2022 (−61) and 2008–2009 (−53, −41), the years in which the ONS F.332
financing row (net of gilts acquired by CG bodies) departs furthest from the
DMO's gross issuance — the same OQ-9 wedge. `ggfiscal debt validate`: 22 OK,
2 SKIP, 28 WARN (V29 bills between year-ends, V30 DEU pre-1999, V31 DEU
perimeter, V36 three floaters); 13 new GBR tests. **Not done:** the UK
year-end positions panel from the office itself (needs the page's own
export link, see DOWNLOAD_LIST.md), per-ISIN APF holdings (DD11 overlay,
BOE_APF snapshots are in the store), the two floating-rate gilts' LIBID
fixings (DD10), France.

## D-S10-006 — France: the AFT pages saved by the committee are the register; a snapshot register until the auction history arrives (serves DEBT_KICKOFF.md §12 D2 FRA; updates OQ-8)
2026-09-10 (evening). **Access.** The AFT challenges every navigation of an
automated browser and even its static Excel files from this box, so the
committee saved nine pages by hand (Ctrl+S, "HTML only") and pushed them;
`ggfiscal debt ingest-incoming` accepts the page parts (`oat`, `btf`,
`oatei`, `dernieres`, `archives`, `oati_page`, `oatei_page`, `rapports`,
`bulletins_index`) and files linked from a page as `{page}_file_{name}`.
The pages are the data: the encours détaillé tables (ISIN, libellé, encours
by maturity year) are what the DMO publishes as D1A. **Reader**
(`readers/aft.py`): the libellé carries the terms (``OAT 2,50 % 24
septembre 2026``, ``GREEN OAT€i 0.10% 25 JULY 2038``, ``OAT zéro coupon 28
mars 2028``), amounts come in French and English formats, the adjudications
tables are pivoted from attribute rows to one row per (auction, ISIN) with
``Volume total émis = adjugé + ONC``. **Register** (`register_fra.py`): 101
securities (59 OAT incl. 5 green, 12 OAT€i, 30 BTF; the OATi page is on the
committee's list), positions at the pages' retrieval date
(`office_snapshot`; the page states no date), the current month's eight
auctions as flows; no ratios yet (the base indices are in the AFT
coefficient files, also listed). Σ OAT 2,404 EUR bn, OAT€i 184, BTF 218;
the aggregate layer's 307 for all linkers at end-2025 is the OATi gap.
**Chains.** A register enters a chain year only when it covers the whole
year (a position on or before 1 January: a 31 December anchor), so the
French snapshot register contributes nothing to the chains — France stays
on the DD8 aggregate layer — and its partial-year 2026 interest lives only
in `debt_interest_by_security`. Same rule for every country
(`register.register_sums`). The maturity profile is now also computed at
each office's latest snapshot (the current profile), which is the French
register's first DD7 output. **Next** (OQ-8, DOWNLOAD_LIST.md second
round): the OATi encours page, the `historique-adjudications` page and its
files (flows since 2018, the archives before), the six coefficient / index
files, the key-figure pages; with the history the positions are rolled
back from the snapshot as for the UK.

## D-S10-007 — France complete on the per-security register: the AFT histories, the coefficient files, positions rolled back from the encours (serves DEBT_KICKOFF.md §12 D2–D4 FRA; closes the AFT part of OQ-8)
2026-09-10 (night). The committee saved the second and third rounds by hand
(OATi page, key-figure pages, six coefficient/index files, five auction
history files). **Readers** (`readers/aft.py`): `coefficient_file` (daily
reference index and coefficient per line, terms in the header block:
kind, coupon, maturity, base date = date de jouissance, base index),
`price_index` (the AFT monthly IPC / IPCH on every base), `history_mlt`
(2,288 OAT/BTAN/OATi/OAT€i auctions 1999-01 → 2026-07), `history_btf`
(4,029 tenders 1999 → 2026-07), `history_syndications` (45, two negative
= buybacks). **Register** (`register_fra.py`): 1,603 securities (166 OAT/
BTAN, 35 linkers, 1,402 BTF), 2,069 year-end positions 1999–2025 plus 106
office snapshots, 7,903 flows, 92,139 ratio points (office daily for every
linker in the coefficient files, recomputed monthly for the lines matured
before the 2016 history files with the base at the coupon anniversary on
or before the first settlement). Anchoring as for the UK: the encours
walked back through the operations; a positive shortfall for a line first
seen before 1999 is dated 1999-01-01 (pre-1999 issuance), a positive
shortfall for a later line at its first operation, a negative one (bought
back; the AFT publishes rachats only in aggregate) at the snapshot, so the
year-ends before it are gross of the buyback; matured lines are Σ
operations, redeemed at that amount (grade B). **Checks**: Σ BTF at 31
December equals the AFT's own BTF total to the euro 2009–2020 and within
0.3% 2021–2024; the uplifted linkers are within 3% of the AFT's
oati_oatei total every year 2009–2025; the recomputed ratios reproduce the
coefficient the AFT prints for each linker auction to 1e-5 (878 auctions);
fixed-rate lines run 0.96 of the AFT total in 2009 (pre-1999 issues of
lines matured 2009–2015 unseen) and 1.01–1.04 in 2014–2025 (the unseen
buybacks). **Chains**: France enters both chains from 2000 (the full-year
rule); the register meets S.1311 D.41 directly at step B (the État's own
totals, step A, remain blocked): the interest residual falls from +31 EUR
bn in 2000 to ≈0 in 2012 and stays within ±6 EUR bn 2013–2025 except 2020
(−14); the financing residual at B is the whole cash/accrual wedge plus
the aggregate-only buybacks and premia, published. `ggfiscal debt
validate` 22 OK, 2 SKIP, 28 WARN unchanged. Ten French tests.
**Open**: per-line buybacks, the pre-1999 lines, step A (OQ-8 residual
asks: the PLF programme 117 tables), the ISIN "fiche titre" pages
(first coupon dates: the register uses the base date from the
coefficient files where available and the first auction otherwise).

## D-S9-007 — Statistical benchmark forecasts of every granular line to 2031, and six notebooks that chart them (serves §1, D-S9-002; new deliverable)
2026-09-10, session 6 (continued). The committee asked, for each granular
COFOG/ESA strict series: keep the levels chart, add the series as a share
of GDP (call it X), then forecast X to 2031 four ways — R `auto.arima`,
R `ets`, Facebook `prophet`, and the statsmodels unobserved-components
("statespace cycles") model — each as a fan chart, plus a fifth chart
combining the four.
**Built.** `src/ggfiscal/forecast/statistical.py` +
`ggfiscal statistical-forecasts` write
`deliverables/statistical_forecasts.csv` (1,940 rows: 60 series x 5
methods x 6-7 horizon years). Six notebooks —
`forecasts_{GBR,FRA,DEU}_{expenditure,revenue}.ipynb` — read that CSV and
plot, 0.57-0.72 MB each, all executed with outputs committed.
Four committee decisions, taken before building:
  - **Six notebooks, not one.** 366 new charts is ~2.9 MB in a single
    file, back above the size that stopped GitHub rendering (D-S9-004).
    One book per country per tree lands each at ~0.6 MB. The committee
    confirmed the existing 0.91 MB chartbook now renders, so ~0.6 MB has
    real headroom.
  - **Fitted on outturn only**, never on the official forecast years, so
    where a line carries an official projection the two sit on the same
    axes and can be read against each other. The alternative (fit on the
    full strict series, gap-fill the remainder) was rejected as losing
    that comparison.
  - **Series whose official strict forecast already reaches 2031 are
    skipped** — FRA/DEU GF01_7 (2036), GF07 and GF09 (2070). Six series;
    they get the levels and share charts only.
  - **Combination** = mean of the four point forecasts, with variance =
    average within-model variance PLUS the variance across the four point
    forecasts, so agreement between methods is never mistaken for
    information. Inverse-variance weighting was rejected: it would let
    Prophet dominate, and Prophet's intervals are the narrowest here for
    reasons that have nothing to do with these series.
Scope and status of the numbers: these are a **benchmark, not a rival
forecast**. Nothing enters the canonical layer, the trees, the strict
matrices or any other bundle file; `statistical_forecasts.csv` is the one
file in `deliverables/` that is not a copy of the gated layer, and it says
so in the bundle README.
Two defects found and fixed while building, both worth not rediscovering:
  - **statsmodels only forecasts past a `RangeIndex`.** Whether a year
    index comes back from pandas as `RangeIndex` or plain `Index` is
    incidental to the data, and ETS and UC failed on exactly the series
    that got the latter ("No supported index is available"). Both methods
    now re-index onto 0..n-1 via `_positional` and the caller puts years
    back. Passing a bare ndarray instead does NOT work — statsmodels 0.15
    then raises `'numpy.ndarray' object has no attribute 'index'`.
  - **Prophet, `auto.arima` and `ets` behave as the data deserves, not as
    a demo.** On 30-61 annual points `auto.arima` picks ARIMA(0,1,0) for
    ~16 series and `ets` picks (A,N,N)/(M,N,N) for most — flat point
    forecasts. That is the honest answer and the notebooks say so up
    front rather than leaving a reader to think the chart is broken.
Verified: 47 tests in `tests/deliverables` (15 new), covering that the
forecast set is exactly the series that need one, that intervals are
ordered and equal the recorded standard error, that the combination is
the mean with within+between variance, and that each notebook charts
every series seven ways (or two, for the six skipped).
**Pre-existing breakage NOT caused by this work, recorded for whoever owns
it:** on clean `main` at 7003193, `ggfiscal report` aborts with
`KeyError: nan` in `validate/runner.py:166` (`run_all`), and the non-debt
suite is 16 failed / 106 passed with `tests/debt` at 33 failed / 21 errors
— unchanged with this branch applied (16 failed / 121 passed, the extra
15 being this work's new passing tests). The README here was regenerated
by calling `report.readme.write()` directly, since `ggfiscal report` cannot
complete.

## D-S9-008 — `main` repaired: the append-only manifest and the per-machine raw store had come apart (serves §11.1, D8, D-S0-004; fixes the breakage flagged in D-S9-007)
2026-09-11, session 6 (continued). The committee asked for the breakage on
`main` to be dug into and resolved. It was not a merge conflict and not
the debt work's fault; it was a latent defect in
`standardise.readers.latest_snapshots` that only shows once two
workstreams harvest on different machines.
**The defect.** `snapshots.jsonl` is append-only and travels in git. The
raw store does not (D-S0-004). `latest_snapshots` took the LAST manifest
line per (source_id, part) and only then filtered for the file existing —
so a newer pull made in another container shadowed an older, usable pull
sitting on disk here, and the source came back unharvested. The debt
workstream fetched on 2026-09-09; this container had the 2026-09-08 pulls.
The two are byte-identical — same sha256, same size, only the fetch
timestamp in the filename differs — and every fiscal anchor was being
discarded over that. Fixed by selecting the last manifest line WHOSE FILE
EXISTS: snapshots are content-addressed, so an older entry with the same
hash is the same bytes, not a stale vintage.
Effect: usable snapshots 57 -> 137, sources 10 -> 31; the non-debt suite
goes from **16 failed / 106 passed to 137 passed, zero failures**, and
`ggfiscal report` — which had been aborting with `KeyError: nan` — runs to
completion. The rebuild that followed changed `run_id` and nothing else:
every value in all four trees and the ledger is byte-identical, which is
the proof that the 09-08 snapshots the fix now selects are the same data.
**Three further defects found and fixed on the way:**
  - `validate.stage3.check_v6` crashed with `KeyError: nan` on an empty
    anchor (`anchor[anchor.index.max()]` with an empty series). A harvest
    gap should report a Finding naming the source, not surface as a stack
    trace four layers from its cause. That crash is what made the original
    diagnosis expensive.
  - `playwright` is imported by `debt/browser.py` but was declared nowhere
    in `pyproject.toml`, so `ggfiscal debt fetch` could not run from a
    clean install. Added as a `debt` extra.
  - `debt/browser.py` raised a bare `RuntimeError` when a Cloudflare
    challenge would not clear. `debt.fetch.fetch_all` catches
    `FetchBlocked`/`FetchError` and skips past, so the bare error escaped
    that net and **stranded every source queued behind the blocked host** —
    which is why five German and French rate sources had no snapshot at
    all. A challenge that will not clear IS the publisher refusing us, so
    it now raises `FetchBlocked` and the harvest continues.
**Debt suite**, after the fix plus a debt harvest in this container and
installing the already-declared `pypdf`: **33 failed / 70 passed / 21
errors -> 6 failed, 179 passed, 0 errors.** The 20 largest remaining
failures were only `pypdf` missing from this image (declared in
`pyproject` since the debt merge, but the environment predated it).
Nothing in `deliverables/debt_*.csv` changed: `flatten` copies the debt
canonical layer, and all twelve files are byte-identical after the rebuild.

## D-S11-001 — The chartbook carries the forecasts: a panel of every category per country, one forecast per line (serves D-S9-002, consumes D-S9-007; costs the D-S9-004 size margin)
2026-09-17, session 11. The six `forecasts_*.ipynb` books (D-S9-007) put
seven charts under every granular line — levels, the share of GDP, and a
fan for each of `auto.arima`, `ets`, `prophet`, `uc` and their
combination. That is the right shape for interrogating one line and the
wrong shape for the question "what is actually being forecast here?",
which needs every category of a country on one page. The chartbook now
answers that question first: each country section opens with §*x*.1
**Forecast panel — every category at a glance**, and the per-series charts
it already had follow as the evidence.
**What is drawn, and the one rule that decides it.** Per line, as a share
of GDP from 2000 to 2031:
  - an **official projection exists** -> that projection, blue dashed, no
    band. It is a published number, not a distribution, and where it exists
    it is the answer; the statistical benchmark is not drawn against it.
  - **none exists** -> the statistical `combination`, violet dashed, with
    its 80% interval. The four underlying methods are never drawn here.
    One line stands for all four, which is what `combination` is for
    (mean of the four, variance = mean within-model variance + variance
    across their point forecasts). The method-by-method comparison, and
    the benchmark-against-official reading, stay in the forecast books.
That splits 66 granular lines into 20 official and 46 statistical.
**Three judgements inside the rule.**
  1. *An official forecast that stops short of 2031 is not topped up.* The
     UK's R01-R04 stop at 2030, GF02 at 2028, five lines at 2027. Carrying
     them on with the statistical path would mean splicing a benchmark
     anchored at the last **outturn** onto an official path that has
     already moved away from it — a number that appears in no file. The
     panel draws the official path to where it ends and the readout names
     the year, so horizons differ across a panel and say so.
  2. *The 95% band is drawn in the forecast books, not here.* At facet size
     it swamps the y-axis of every statistical line and the panel stops
     showing what it exists to show. The 80% band is drawn and labelled as
     the 80% band; nothing is implied about the 95% one.
  3. *`TE` and `TR` are out.* They are envelopes, not categories, and carry
     no forecast path (`not_extended`), as in the forecast books.
**The identity that does not close, said out loud.** `GF01 = GF01_7 +
GF01_X` in the trees, but each of the three takes its forecast from
whichever source it has. France is the case: official interest **+1.55 pp**
and a statistical `GF01_X` of **+0.01** come to +1.56, against a
statistical `GF01` of **-0.50** — a 2.07 pp gap, because a univariate fit
of the whole knows nothing about the official projection of the interest
line inside it. The caption under each ranked chart does that arithmetic
from the data rather than asserting the identity holds.
**A second figure per country, `changes(iso3)`**, ranks every line by the
change it is forecast to make between its last outturn and its horizon,
expenditure and revenue in separate blocks on one x-axis. Separate blocks
deliberately: a rise is a rise in both, and it moves the balance in
opposite directions, so one merged ranking would invite exactly that
misreading. Bars are coloured by source, never by direction — direction is
already carried by the side of zero, and D-S9-002's rule that a hue means
an entity and nothing else holds. Under it, the same numbers as a printed
table, because a bar length is not a value.
**Palette.** VIOLET `#4a3aa7` joins the chartbook's fixed quantisation
palette as slot 4 — the same violet the forecast books already use for the
same thing. Appended **last** in `_palette()` on purpose: inserting it
earlier renumbers every index and rewrites every figure in the book for no
change in what any of them shows. Re-validated all-pairs against the
surface: lightness, chroma and CVD separation pass; worst normal-vision
adjacent pair is VIOLET/BLUE at dE 16.3, and line style repeats the
distinction anyway.
**Cost: the D-S9-004 size margin is spent.** Nine new figures (three per
country) add 182 KB of PNG and take the chartbook from 0.94 MB to
**1.19 MB**, past the 0.9 MB margin D-S9-004 judged — not measured — safe
for GitHub's client-side notebook renderer. Confirmed there is no cheaper
rendering: the figures are already palette-quantised and PIL-optimised
(recompression at every level returns the same bytes to the byte), and 66
facets cost 1.9 KB each against 5.4 KB for a full-size chart. The margin
was a judgement, the panel is content, and the panel wins; the README now
states the real size and points at D-S9-004's own fallback — split the
chartbook one notebook per country — if GitHub declines it.
**Nothing recomputed, nothing spliced.** Every path is anchored at its own
line's last outturn, every value is read from `deliverables/`, and the
window is applied to the DATA and not only to `set_xlim` (the D-S9-004
lesson: FRA `GF07`/`GF09` run to 2070, and leaving those years in would
flatten the visible history).
Tests: two new — one re-derives every row of the printed table from the
flat files and checks the official-beats-statistical rule line by line,
the other pins that the panel's *code* names `combination` and no other
method and draws `lo80`/`hi80` and never `lo95`/`hi95`; the axis/shading
test learns the fourth chart family and that its window is applied to the
data. `tests/deliverables` 49 passed (was 47); the full-suite failure set
is byte-identical before and after (this container has an incomplete
harvest, so the debt and stage gates fail either way).

## D-S11-002 — The benchmark balance: the line forecasts summed back into an NLB path to 2031, with the cone their own errors imply (serves §4.3, §8.3, D-S9-006; consumes D-S9-007, D-S11-001; new deliverable `benchmark_balance.csv`)
2026-09-17, session 11. D-S9-006 settled that there is no forward "our NLB"
because **a level needs every component and a change does not**, and 44 of
72 series carried no forecast at all. The first half of that is unchanged.
The second half is not: D-S9-007's benchmark reaches every granular line to
2031, so a balance can now be summed with `resid_coverage` **zero by
construction** — the hole the argument turned on is closed. New module
`forecast/balance.py`, new command `ggfiscal benchmark-balance`, new file
`deliverables/benchmark_balance.csv`, new chartbook §4.5. It is a
**benchmark** balance on exactly the footing of the lines it is built from:
not in the canonical layer, not in the trees, and never the number where an
official projection of the balance exists.
**Four choices, each recoverable from the file.**
  1. *Base year = the last year EVERY line has an outturn.* The expenditure
     tree ends a year before the revenue tree, so that is 2024, not the
     ledger's 2025. The path starts from the balance ledger's own published
     NLB/GDP at that year — a published balance, not a sum of lines.
  2. *Expenditure is `GF01_7 + GF01_X + GF02..GF10`, never the Level I set.*
     Identical in history (checked: Σ = TE to the last digit in every
     outturn year, all three countries). Not identical in forecast, because
     the Level I set hides interest inside `GF01`, whose univariate fit knows
     nothing about the official interest projection inside it. France 2031:
     **-6.13% of GDP on the split against -3.85% on `GF01`** — a 2.25 pp
     difference, and the largest single judgement in the section. Germany
     1.31 pp, the UK 0.63 pp. `reconcile/explanation.py` keeps the Level I
     set for the history decomposition, where the two agree; this is the one
     place they do not.
  3. *An official projection is used only where it covers the whole horizon.*
     Deliberately NOT the D-S11-001 panel rule, which prefers an official
     projection at any horizon. A total needs every line in every year, and
     splicing a benchmark anchored at the last outturn onto an official path
     that has already left it would invent a number in no file. Seven UK
     lines, five German and two French take their statistical path here and
     show official in the panel above; the `source` column names them and
     `compute()` reports them as notes.
  4. *The cone is the lines' own published standard errors, propagated* under
     one average correlation within a side and one across the two, both
     ESTIMATED from the outturn history of the same lines (h-year changes in
     ratio, per country and horizon). Estimated, not assumed: independence
     would understate a set of lines that move with the cycle together, and
     the cross-side term enters with a minus sign, so it is what lets a
     revenue miss and a spending miss cancel. Measured at ρ_within ≈ +0.11 to
     +0.19, ρ_between ≈ 0.00 to +0.06 — low, which is itself the finding:
     these lines do not cancel much. Lines on an official path contribute
     **no** variance (a published projection is not a distribution), so the
     cone understates wherever a country has official legs; `n_official` is
     on every row.
**The cone is wide and that is the answer, not a defect.** UK 2031:
-7.27% of GDP, 80% -15.2 to +0.6. Every row carries, beside it, the standard
deviation of h-year moves in that country's own ledger NLB/GDP across the
whole outturn record — a yardstick, never used to build the interval. At
h=7 the model band is 6.16 pp against history's 4.74 (UK), 4.17 against 2.28
(FRA), 4.83 against 3.05 (DEU): the same order, a little wider. A balance
six years out is genuinely this uncertain, and 2009 and 2020 are both inside
the record the yardstick is measured on.
**One free mark.** Because the revenue tree runs a year past the expenditure
tree, the first forecast year already has a published balance beside it —
the only outturn this construction can so far be scored against. Benchmark
vs ledger at 2025: UK -6.34 against -5.18, France -5.70 against -5.12,
Germany -1.36 against -2.67. Misses of -1.16, -0.58 and +1.30 pp, all well
inside the one-year band, and all reported in the section's caption.
**Where it runs.** The module reads `deliverables/` and nothing else — the
two trees, the ledger and the statistical forecasts — so it needs no
harvest and no canonical layer, and the file is a pure function of the
published bundle. It is a side-car like `statistical_forecasts.csv`: not in
`M.FLAT_FILES`, so it does not enter the run manifest, but it IS in the data
dictionary, which the coverage test requires of every CSV in the directory.
**What was NOT done.** A single nominal GDP path is still not published. The
WEO's `NGDP` is ingested and used at every forecast horizon by
`reconcile/explanation.py`, but `weo_levels_bridge.csv` emits `gdp_weo_mn`
only on history rows, so a currency-level version of this path cannot be
built from the bundle. Deliberately deferred: this section needs no GDP
forecast, because the components are ratios and a balance is a difference of
ratios. The per-source denominators that ARE in the trees disagree — Germany
2030 carries 5.205 / 5.240 / 5.339 tn from three sources, a 2.6% spread —
so publishing "a" GDP path is a choice that needs making, not a copy.
Tests: six new — reproducibility of the file from the published bundle,
the three-way sum identity (lines, sides, balance), the interest split and
the absence of `GF01`, the official-only-where-it-reaches rule, the base
year and its ledger anchor, and the cone re-derived from the published
per-line errors and correlations. A seventh pins §4.5's prose and that §4.4
now points at it instead of being quietly contradicted. `tests/deliverables`
56 passed (was 49); the full-suite failure set is unchanged.

## D-S11-003 — The levels charts carry the benchmark: one nominal GDP path per country, our outturn anchored and chained on WEO NGDP growth (serves D-S9-002, D-S11-001; new deliverable `forecast_levels.csv`; answers the gap left open by D-S11-002)
2026-09-17, session 11. The chartbook's per-series charts are levels in
millions of national currency; the statistical forecasts are shares of GDP.
Putting one on the other needs a nominal GDP path, and D-S11-002 recorded
that the bundle has none — each forecast row in the trees carries the
denominator that came with *that line's* source, and the sources disagree
(DEU 2030 spans 5.205 / 5.240 / 5.339 tn, a 2.57% spread worth EUR 27bn on
GF10 alone; GBR has no forecast GDP at 2031 at all). That is now closed.
**The blocker was smaller than recorded.** D-S11-002 said this needed a
container with the WEO harvest. `api.imf.org` is in fact reachable from the
build environment: the 46 `IMF_WEO*` pulls were fetched here and **48 of the
49 (source, part) keys came back byte-identical to the earlier harvest** —
only the dataflow `catalog` part churned, which is a listing and not data.
So the NGDP used here is exactly the series the committed bundle was
reconciled against; there is no vintage drift to reason about.
**The construction: anchor an outturn, chain a growth rate** — the same rule
as every stitched series in the project (§7, D-S4-002), not a substitution.
  - *anchor*: the tree's own GDP at the last year on which every line's
    denominator agrees. That is **2024**, a year before the last outturn: at
    2025 the denominator forks by source (GBR three values, DEU two at a
    1.34% spread), and picking one would be arbitrary.
  - *growth*: IMF WEO `NGDP`, one vintage, the series §4 already reconciles
    our totals against.
  Chaining rather than substituting is the whole point. Over 2021-2025 the
  WEO's NGDP runs **0.97% below our GDP anchor for Germany**, so multiplying
  a ratio by the raw level would step every German forecast level about a
  point below what its own history implies — a seam that is an artefact of
  the denominator and nothing else. Growth rates carry no level difference.
  Cross-check: the chained 2025 lands within 0.001-0.61% of the published
  2025 denominators it deliberately does not choose between.
**What this does NOT do is add uncertainty about GDP.** The interval is the
line's own interval times a single path, so it is the uncertainty of the
RATIO with the path taken as given. A level in this file is a joint
statement — this ratio, on that path — and the columns name the path so it
can be replaced. Said on the chart, in the caption and in the dictionary.
**In the chartbook**, `chart()` gains a violet dashed leg and its 80% band
(the 95% swamps a levels axis and stays in the forecast books), drawn on
**46 of the 72** charts. The rule is D-S11-001's: only where the **strict**
series carries no official forecast — where one exists the published number
is the answer. Two details that bit:
  - keyed on strict, not on the furthest variant. GBR GF10's
    `maximum_extension` carries a proxy leg to 2027 while strict stops at
    2024; a proxy extension is not an official forecast, so that chart gets
    the benchmark as well as the orange leg.
  - anchored on **strict's own last outturn**, not on the chart's `actual`,
    which comes from both variants and is a year later wherever
    maximum_extension carries a stitched 2025 the strict series does not.
    The first version crashed on exactly that.
  `no projection published` now appears on **six** charts — the `TE`/`TR`
totals, the only ones left with nothing in the projection region — so the
reading guide and two of the schema notes were rewritten rather than left
quietly false (`GF01_X`'s chart no longer "always stops at the last
outturn").
**Where it lives.** `forecast/levels.py`, `ggfiscal forecast-levels`,
`deliverables/forecast_levels.csv` — the currency twin of
`statistical_forecasts.csv`, same key, all five methods. A forecast-layer
side-car like its two neighbours: outside `M.FLAT_FILES` and the run
manifest, inside the data dictionary. Unlike `benchmark_balance.csv` it is
**not** a pure function of the published bundle — it needs the WEO snapshot
— so its reproducibility test is skipped where that snapshot is absent.
Cost: the chartbook goes 1.30 -> 1.34 MB (+48 KB), already past the
D-S9-004 margin.
Tests: five new — the level is the ratio times the path and nothing else and
the path is shared by every line of a country; the anchor is our own outturn
at the last agreed year AND that the last outturn really is ambiguous (a
test that never saw the fork would not notice if the anchor moved); the
chain is WEO growth and is measurably not the WEO level; the file
reproduces from the bundle plus the snapshot; and the chartbook draws the
leg on exactly the 46 charts where nothing is published, checked against the
executed captions rather than the source. `tests/deliverables` 61 passed
(was 56).

## D-S11-004 — The benchmark balance read against the WEO's own deficit projection, and the difference decomposed (serves §8.3, D-S9-006, D-S11-002; new deliverable `benchmark_vs_weo.csv`)
2026-09-17, session 11. §4.1-4.3 compare our totals with the WEO's over the
overlap years and stop at the last outturn. D-S11-002 carried a benchmark
balance to 2031 and the WEO publishes GGXCNL over exactly that horizon, so
the comparison §4 could never make is now available. New
`forecast/weo_compare.py`, `ggfiscal benchmark-vs-weo`,
`deliverables/benchmark_vs_weo.csv`, chartbook §4.6.
**The comparison is clean at the base year.** Balance gap at 2024: GBR
**+0.017 pp** of GDP, FRA -0.001, DEU +0.000. Nothing in the section is a
definitional wedge in disguise, which is what makes the rest worth reading.
**By side it is not, and that drove the design.** The UK's TR and TE are each
about **2.6 pp of GDP larger** than the WEO's (revenue +2.60, expenditure
+2.58) — a stable perimeter difference, sd 0.21-0.25 pp over ten overlap
years, classified `perimeter` in §8.2, which cancels in the balance because
it sits on both sides. So the side comparison is made on **changes since the
base year**, where a stable wedge cancels, and `perimeter_gap_pp` and its
standard deviation are published on every row rather than left to be
discovered by whoever first compares two levels.
**The decomposition closes exactly**, and is tested to 1e-6:
    balance gap = revenue gap + expenditure gap - weo_internal_wedge
The wedge is the WEO's own Δ((GGR - GGX - GGXCNL)/NGDP). It is **zero to four
decimals on the 2026-04 vintage** and is carried anyway: the HANDOFF note
from session 9 says it is reported and never absorbed, and a row that is
usually zero is the cheapest way to keep that true.
**What it says.** At 2031, in % of GDP:
  - **GBR** benchmark -7.27 against WEO -1.60, **-5.67 pp apart**. Almost all
    of it is revenue: the WEO has GGR going 37.6% -> 42.1% of GDP, a 4.5 pp
    rise, with spending flat. Split: revenue -3.28, expenditure -2.40.
  - **FRA** -6.13 against -2.89, -3.23 pp. Revenue nearly agrees (+0.23); the
    story is spending, which the WEO has FALLING 1.2 pp while the benchmark
    has it rising 2.3. Split: revenue +0.23, expenditure -3.49.
  - **DEU** -2.47 against -3.66, **+1.19 pp the other way** — the only country
    where the benchmark is less pessimistic, because the WEO embeds the
    announced defence and infrastructure expansion (GGX 49.4% -> 51.6%) and a
    model fitted on history does not. Split: revenue +0.53, expenditure +0.62.
**And the statistic that reframes all of it:** the WEO sits inside the
benchmark's 80% interval in **21 of 21 country-years**, never more than
**0.97** of the benchmark's own standard errors away. A five-point gap sounds
like a disagreement; on this cone it is not one. That is a statement about
how wide six-year fiscal uncertainty is, not about how close the two
forecasts are, and the section says so in those words.
**What it deliberately does not do is judge.** The benchmark knows only each
line's own history; the WEO's projection embeds announced policy. Where they
part company the difference IS the policy. The file reports how far apart
they are and whether the WEO is inside the interval — never which one is
right — and §4.6's prose and the chart captions both say so.
**Charts.** Two, in the book's existing palette with no new hue: aqua is the
IMF WEO as everywhere else, violet the benchmark, blue the published balance.
§4.6's first figure is the three paths on one shared axis with the
benchmark's 80/95 cone; the second is the side decomposition as six panels
(two sides x three countries) of cumulative change since the base year, ours
against the WEO's, with the gap shaded between the two lines. Aqua is below
3:1 on this surface, so the WEO line carries a direct text label as it does
in §4.1-4.3 — the relief the palette validator requires, not an afterthought.
Cost: the chartbook goes 1.34 -> 1.39 MB.
Tests: five new — the decomposition closes on the balance for every
country-year; the `ours` side is the published benchmark rather than a
recomputation, and the interval flags and `weo_z` are re-derived; the
perimeter gap is published, is large on the UK's two sides, is ~0 on the
balance, and is absent only on the wedge memo; the WEO side quotes the
snapshot unchanged and the file reproduces from the bundle; and §4.6's prose
claim that the WEO is always inside the 80% interval is checked against the
data rather than taken on trust. `tests/deliverables` 66 passed (was 61).
## D-S12-001 — The AFT briefing: the register rolled forward through declared yield paths onto the interest line, and the note built on it (serves DEBT_KICKOFF.md §1 "shaped for: simulating alternative yield-curve paths through the register", DD7; new deliverable under `reports/`)
2026-09-18, session 10. The committee asked for a briefing note for a
meeting with the Agence France Trésor's Chief Economist, built from the
chartbook and the debt book, addressing three concerns — the interest bill
and its wrong-way loop with politics, the shortening maturity of the stock,
and the rate sensitivity of the end holders — under the current path and
under the four 2027 configurations (Le Pen / Édouard Philippe × majority /
hung National Assembly).
**What was built.**
  - `src/ggfiscal/debt/simulate.py` — the yield-path simulation the debt
    spec left as "out of scope now, but shaped for". It loads the French
    register at the AFT's latest office snapshot (2026-09-10) from the
    bundle and rolls it forward 2026–2035 year by year: coupons pro rata,
    bill discount on the bill stock, uplift accrued on the linkers, the
    general-government deficit (primary balance declared, interest
    endogenous) financed at the marginal OAT yield in the AFT's 2025 tenor
    mix, interest fed back into next year's deficit. A Bund curve, a spread
    term structure, a bill-stock path and a tenor tilt are declared inputs;
    six scenarios (`SCENARIOS`) state the primary-balance deviation, the
    10y spread path, the bill stock and the tilt, with a +3 bp per pp
    debt-ratio feedback. `decompose_gap` re-runs one lever at a time to
    split a scenario's interest gap into spread, volume and interaction;
    `duration_table` prices every bond at the curve for the mark-to-market
    sensitivity of the stock. Two calibrations are computed from the
    bundle and printed, never fitted silently: the share of the
    general-government deficit the État's negotiable debt has financed
    (Δ(F.31+F.32)/−NLB 2015–2025 = 0.90) and the wedge GF01_7 − register
    interest (10.1 EUR bn in 2025, 0.34% of GDP). 2026 is a bridge year:
    the register already holds the issuance to the snapshot, so only the
    remainder of the year is financed and the 2026 interest is the strict
    file's AMECO value. The tenor of each issuance bucket is the AFT's own
    nominal-weighted residual maturity at issue in that bucket, not the
    bucket midpoint (the midpoint overstated the 2025 mix by a year).
  - `src/ggfiscal/report/briefing_fra.py` (descriptive charts and
    `key_figures.csv`, drawn by a delegated model to the debtbook's
    palette) and `src/ggfiscal/report/briefing_fra_scenarios.py` (scenario
    charts, `scenarios_FRA.csv`, `scenario_decomposition.csv`,
    `duration_by_bucket.csv`). Both read `deliverables/` only.
  - `reports/briefing_FRA_AFT_2026-09/` — the note: `briefing_template.html`
    (prose with placeholders), `tools/build_briefing_fra.py` (fills every
    number from the CSVs and the engine and fails on an unfilled
    placeholder), `briefing.html` (figures by path) and
    `briefing_inline.html` (self-contained, the published artifact), the
    figures and CSVs. `notebooks/briefing_FRA_AFT.ipynb` (via
    `tools/make_briefing_notebook.py`) regenerates every chart and table,
    executed with outputs committed at 0.58 MB (D-S9-004 size rule kept by
    quantising the PNGs).
  - `tests/debt/test_simulate.py` (10 tests): register loads, mix sums to
    one with office tenors, calibrations agree with the bundle, every
    scenario-year present, bridge-year identity, interest = register +
    wedge and debt = Σ deficits exactly, the political ordering, the
    current path within a fifth of the EC DSM path in 2030, the
    decomposition adds up, prices and durations sensible.
**What the numbers say** (all in the note; here for the log). Current path:
general-government interest 2.54% of GDP in 2026 → 3.0% (2028) → 3.5%
(2030) → 4.2% (2035), within a few EUR bn of the EC DSM path already in the
strict file, which is the cross-check that the engine is doing the same
arithmetic. Politics adds 10–19 EUR bn a year by 2030 and 34–62 by 2035 in
the Le Pen cases, two-thirds spread and one-third primary balance; the
interaction (the loop proper) is under 2 EUR bn by 2035. A Philippe
majority saves 16 EUR bn by 2035. The register's average residual maturity
peaked at 8.5 years in 2022 (8.3 at end-2025); maturity at issue of fixed
paper fell from 12.6 years (2021) to 10.3 (2026 ytd); 32% of the stock
matures within three years. The OAT stock has a modified duration of 6.2
years and loses 151 EUR bn per 100 bp.
**Where the note leaves the repo's rules.** Holder shares, ratings, the
spread level of September 2026, the political calendar and the AFT's
programme figures are external (a web search of 2026-09-18 by a delegated
model; the AFT's own site returned 503 throughout, so its figures come via
press reproductions) and are tagged `ext` in the note with the source list
in §8; nothing external enters any module or CSV. The scenarios are
declared, not forecast, and say so. Nothing enters the canonical layer or
`deliverables/`: the outputs live under `reports/` and the notebook, and
`ggfiscal flatten`, `report`, `validate` and the parent tests are untouched.
**Known limits.** The register is gross of buybacks (1–4% above the AFT on
the fixed lines), so redemptions and gross issuance in the engine are high
by the buyback volume; net issuance and interest are barely affected.
Growth, inflation and the Bund curve are common to all scenarios. France
has no holdings overlay (DD11 is UK-only), so the holder sensitivities are
share × the register's duration, an approximation the note states. The
`tests/debt` suite in this container still carries the pre-existing
failures for sources without a local snapshot (INSEE idbanks, German and
French rate sources — D-S9-008); none involve the new module.
## D-S13-001 — The line universe is enumerated from config and grows from 66 to 99: a third tree and a generic Level II mechanism (serves §1, §4, §5, §11.2; supersedes the "twelve lines per country" and "66 series" counts of §1/§4.1 and D10's "these are the only sub-Level I lines"; session 11, 2026-09-19)
2026-09-19, session 11. The committee asked for social benefits and pensions,
which the spec's COFOG tree carries only as the undivided GF10 lump, and for
a review of every Level I line and every revenue line for further breakdowns.
Two structural changes carry both asks without touching the methodology:
  - **COFOG Level II is now a config mechanism, not two hand-built lines.**
    `config/lines.yaml` declares any `level: "2"` line with its `parent`, and
    a `level: derived` remainder (`parent - level2`, `never_forecast`);
    `config.level2_splits()` enumerates them and the build, the coverage
    matrix, V19, the stitched-year derivation and the flat files iterate over
    that list. GF01_7/GF01_X (D10) are the first split; GF10_2/GF10_X
    (D-S13-002) the second; a further group is one config entry plus its
    remainder — the §11.7 standard of "config change plus rebuild, never a
    code change". D10's sentence "these are the only sub-Level I lines" is
    superseded; its substance (interest separated gross on both sides, the
    D.41 fallback for missing Level II 01.7) is unchanged and remains the
    only split with a fallback concept.
  - **A third tree, `ESA_EXP`** (expenditure by ESA economic type, D-S13-003),
    stored in its own canonical files (`expenditure_esa_long_{variant}`) and
    flat file (`deliverables/expenditure_esa.csv`), with `classification`
    now a published column of every tree file. `config.TREES`/`STEMS` name
    the three trees in publication order; `config.line_universe()` is built
    from them, totals excluded by their `level: total` mark rather than by
    the literal codes "TE"/"TR".
Consequences, all mechanical: `model.py` admits `ESA_EXP`; `build.load_trees`
concatenates the three trees for the classification-agnostic validators
(V1, V4-V14, V17, V6/V13 both directions); every count that was hard-coded
(66 in S0_LINES, S0_COVERAGE, the CLI, the README, six tests; 72 catalogue
rows; 12/10 lines) is derived from config or restated as 99 / 108 / 14-9-10.
The §8.3 decomposition is untouched by design: it works on the 20 Level I
lines by literal code, so the ESA_EXP tree — a second cut of the same TE —
is never double counted, and GF10_2 sits inside GF10 exactly as GF01_7 sits
inside GF01 (D-S8-001's reasoning). `series_catalogue.csv` and the coverage
matrix are keyed by classification as well as line code, so the two TE
concepts (COFOG `TE`, ESA `TE_ESA`) never collide.

## D-S13-002 — Pensions = COFOG 10.2 Old age, as a Level II line `GF10_2` with remainder `GF10_X`; the Ageing Report pension path enters strict for FRA/DEU at grade B (serves §4.1, §6.2(2), §7.5, §9; new lines)
2026-09-19. Three candidate concepts were measured before choosing:
(a) the function total of COFOG 10.2 (old-age cash benefits plus the
function's administration and in-kind old-age services), (b) 10.2 + 10.3
(adding survivors), (c) the D.62 cash benefits of 10.2 alone (the
`D62PAY_GF1002` cell of gov_10a_main, the purest "pensions paid"). Chosen:
**(a)**, for three reasons. It is a published Level II cell of the anchor's
own table for all three countries (ONS Table 11 carries GF1002 from 1995;
Eurostat FRA from 1995, DEU from 2000), so it fits the D10 pattern exactly
and V19's identity with GF10 is checkable; it is the largest single COFOG
group anywhere (2024: 18.5% of TE in GBR, 23.4% FRA, 20.0% DEU — bigger
than any Level I division bar GF10 itself and GF07); and the 2024 Ageing
Report's gross public pensions (AWG definition: old-age, early, disability
and survivor pensions) measure against it at 1.07-1.09 in 2022-24 for both
France and Germany — the B band — so the AR projection to 2070 enters
**strict** at grade B, where the AR pensions+LTC composite against GF10
stays C (D-S3-003). Against (b) the same series would measure 0.97-0.99
(FRA) and 0.90-0.92 (DEU), also B; (b) was not chosen because a two-group
sum is a constructed line, and survivors is 0.1% of TE in the UK. (c) is
short for Germany (D62 by COFOG group from 2012 only) and is the concept a
reader can already take from `E03` × the function shares if wanted.
Sources and what happened per country (`forecast_boundaries.csv`,
`stitch_boundaries.csv`, `forecast_declarations.csv`):
  - **FRA/DEU GF10_2 ← EC_AGEING_2024 "Public pensions, gross"**, % of GDP,
    §7.5 nominal path as for GF07/GF09: coverage 1.070 (FRA) / 1.068 (DEU)
    at 2024, grade B, `direct_forecast`, strict and maximum to 2070.
    Crosswalk `EC_AGEING_to_COFOG.csv` row `pensions_baseline`. The AR's
    disability and survivor components explain the ~7% over-coverage; the
    concept note carries it.
  - **DEU starts 2000, not 1995**: Eurostat DEU Level II lacks 1995-99 for
    GF1002 as it does for GF0107 (D-S1-003), but there is no fallback
    concept for old age as there is for interest. The IMF GFS old-age group
    (`GF1020_T`) was registered as the 1995-99 candidate; measured live it
    also starts in 2000 for DEU (1995 for FRA/GBR), so nothing is applied;
    the crosswalk row records the stop. GF10_X therefore also starts 2000.
  - **GBR GF10_2 has no applicable forecast**: EFO table 4.9 State pension
    starts at FY 2024-25, so after §7.10 conversion it shares no year with
    the anchor — §9.2 unmeasurable, grade D, recorded not applied (the
    welfare-spending problem of D-S7-003). The OBR historical public
    finances database carries pensioner spending 1978-79 to 2022-23, which
    cannot bridge 2023-24; declared `source_blocked` with the FRS ask
    (OQ-6 a). It would be a C-band backward-extension candidate for GF10_2
    to 1978 (public-sector, FY) — not built this session, listed in OQ-10.
  - **GF10_X = GF10 − GF10_2**, derived, never forecast, both variants in
    every year both exist (GBR/FRA from 1995, DEU from 2000), V19-checked.
GF10 itself is unchanged (still the AMECO D.62 C-proxy chained into the AR
composite, maximum only). The §8.3 explained shares are unchanged by
construction (D-S8-001's argument).

## D-S13-003 — The `ESA_EXP` tree: total expenditure by ESA economic type, nine lines summing to TE, AMECO as the direct forecast and backward source (serves §3, §4, §6.1-6.2, §7.2-7.3, §9; new tree)
2026-09-19. Lines (`config/lines.yaml` `expenditure_esa`): E01 D.1
compensation of employees, E02 P.2 intermediate consumption, **E03 D.62
social benefits other than social transfers in kind** (the "social
benefits" line the committee asked for: every cash benefit across every
function), E04 D.632 social transfers in kind via market producers, E05 D.41
interest payable (the economic twin of GF01_7, carrying the same
`d41_gross_accrued` flag and V20 check), E06 D.3 subsidies, E07 other
current expenditure (D.29 + D.5 + D.4 excl. D.41 + D.7 + D.8), E08 P.5 + NP
capital formation, E09 D.9 capital transfers, and the total TE_ESA.
Anchors are the same institution as each country's balance anchor:
gov_10a_main payable items for FRA/DEU (`D1PAY`, `P2`, `D62PAY`, `D632PAY`,
`D41PAY`, `D3PAY`, `D29PAY`+`D5PAY`+`D4PAY`−`D41PAY`+`D7PAY`+`D8`, `P5`+`NP`,
`D9PAY`, `TE`) and ONS ESA Table 2 payable rows for GBR (`D1`, `P2`, `D62`,
`D632`, `D41`, `D3P`, `D29`+`D5`+`D4N`+`D7`, `P5`+`NP`, `D9`, `OTE`). The
identity E01 + … + E09 = TE_ESA closes to 0.000% in every year of every
country (verified 1995/2010/2024 before building; V2 now checks it every
year alongside GF01-GF10 = TE). TE_ESA equals the COFOG TE for FRA/DEU and
the ESA Table 2 total (= LEDGER_TE) for GBR; it is published as its own
total so the GBR wedge (D-S1-001) stays visible rather than blended.
Forecasts and extensions (crosswalk `EC_AMECO_to_ESA_EXP.csv` v1.0): AMECO
chapter 16 carries every line on the anchor's own ESA concept — UWCG,
UCTGI, UYTGH, UYTGM, UYIG, UYVG, UUOG — measured at 1.000 for FRA/DEU
(grade **A**, the first A-grade expenditure forecasts in the repo) and, for
GBR, 1.001 (E03), 1.000 (E04), 1.043 (E05), 1.028 (E06) — A/B; strict to
2027, and backward to 1978 (FRA), 1991 (DEU, the reunification stop) and
1987 (GBR, where the UK AMECO history exists). E08 and E09 have partial
components only: UIGG0 (P.51G, 0.96-1.03 of P.5+NP) and UKOG (D.9 + NP and
other capital items, 0.95-1.13) are §7.8 proxies, maximum_extension only
where in band (FRA E09 at 1.133 is D, not applied). AMECO publishes no UK
history for UWCG, UCTGI and UUOG (2026-27 only, the OQ-4 pattern), so GBR
E01/E02/E07 are declared `no_machine_readable_source`: EFO table 6.1's
economic breakdown starts at FY 2025-26 and has the same no-overlap
problem. The AMECO D.62 series that was usable only as a C-band proxy for
GF10 (D-S4-003) is now the direct grade-A forecast of E03 — the concrete
gain the committee asked about: a social-benefits line with an official
short-term forecast in strict, for all three countries.
Two things deliberately NOT done: (i) **FRA/DEU E05 does not chain into the
DSM interest path.** The engine offers the same DSM leg as for GF01_7; the
overlap divergence is the same −6.5pp/+4.0pp that OQ-7 adjudicated, and the
committee's approval list (`tolerances.v16_approved_joins`) names GF01_7,
not E05. The join is therefore withheld with a V16 WARN (D12 read
strictly); approving it is one config row (OQ-10 c). (ii) No long-term leg
for E03: the AR pensions+LTC composite covers only ~65-70% of D.62.
WARN tiers rose as intended visibility, no ERROR: V1 +278 (the GFSM SOO
expense items registered for E01/E02/E05/E06 differ from ESA by 3-7% for
FRA/DEU and more for GBR — concept wedges between GFSM and ESA, WARN by
design), V16 +2 (the withheld E05 joins), V5 +3 (new backward legs),
S0_SNAPSHOTS +494 (the append-only manifest now carries this session's
fetch on top of the earlier machines' entries, D-S0-004).

## D-S13-004 — Packaging: a companion chartbook for the economic tree, three more forecast books, and the notebook cell surgery scripted (serves §11.6, D-S9-002/004/007)
2026-09-19. The chartbook gains the six GF10_2/GF10_X charts in place
(after GF10 in each country's COFOG section) and stays under the size
GitHub renders; the 30 ESA_EXP charts live in `notebooks/chartbook_esa.ipynb`,
a companion with the same setup cell, its own seams table and a header that
says what the tree is and that an `E` line is never added to a `GF` line.
`tests/deliverables` now requires every catalogued series to be charted in
exactly one of the two books and the caption discipline (D-S9-003) in both.
The six forecast books gain GF10_2/GF10_X sections (levels, share, and the
five fans where a benchmark exists — none for FRA/DEU GF10_2, whose official
path reaches 2070) and three new books `forecasts_{GBR,FRA,DEU}_esa.ipynb`
cover E01-E09. `deliverables/statistical_forecasts.csv` is regenerated:
91 series (99 less the eight whose strict path reaches 2031) × 5 methods.
The cell surgery is `tools/update_notebooks_s11.py` (idempotent) so the
next line added can be wired the same way; execution is nbconvert as before.
`derivation.ipynb` enumerates from the catalogue and needed only its prose
counts updated. Gate record and the committee items from the review are in
HANDOFF.md and OQ-10.
Gate record (session 11): `pytest --ignore=tests/debt` **149 passed** (137
before + 12 new/extended: the 99-line universe, the Level II enumeration,
the ESA_EXP spec, the identities in every anchor year, the pension and
social-benefits horizons in the coverage matrix, the companion chartbook
and the three esa forecast books); `validate` **OK=77 WARN=1885, no ERROR,
no SKIP** (WARN delta explained in D-S13-003). `chartbook.ipynb` executed
at 1.01 MB, 5% over the judged 1 MB margin of D-S9-004 (0.96 MB before the
six pension charts); GitHub's threshold is unmeasurable from here — if it
declines to render, the documented fallback is one book per country, and
nbviewer renders it regardless. The rebuild on the 2026-09-19 harvest
changed no value in the 66 pre-existing series (run_id only).

## D-S13-005 — OQ-10 resolved by the committee: four further Level II splits (GF10_5, GF04_5, R02_A, R06_E/R06_H), the E05–DSM join, and the OBR pensioner leg for UK pensions (serves §4.1a, §4.2a, D12, D15, §7.8, §9; supersedes §15 Q13; resolves OQ-10 a–c)
2026-09-19, session 11 (continued). The committee approved all of OQ-10.
Mechanism first: `config.level2_splits()` now returns one entry per
parent with an ordered list of Level II lines and one remainder whose
`minus` names them all; it enumerates every tree, so the revenue tree
gets the same treatment as COFOG (anchor cells named per line: `eurostat`
dataset + codes, `ons` table + codes, `oecd_rs` headings). Build,
coverage, V19, the stitched-year remainder derivation, the small
multiples, the flat files and the notebook cell surgery iterate it.
Universe 99 → **123** series (41 per country: 17 COFOG, 9 ESA_EXP, 15
ESA_REV); catalogue 132 rows.
**Splits and what was measured** (shares at the last common year,
boundary files):
  - **GF10_5 Unemployment (COFOG 10.5)** and **GF04_5 Transport (04.5)**,
    remainders GF10_X (= GF10 − GF10_2 − GF10_5) and GF04_X. Anchors from
    the Level II tables (GBR/FRA 1995, DEU 2000). No institution projects
    either group (AMECO's UUTZ105 is the cyclical component of the balance,
    not the line), so both are D7 declarations everywhere; the GFS group
    GF1050_T is registered for DEU 1995-99 and, like GF1020_T, starts in
    2000; there is no GFS series for 04.5. The UK 10.5 is small by
    construction (Universal Credit is booked under 10.7) — the dictionary
    says so.
  - **R02_A Excise duties = D.214A + D.2122C**, remainder R02_X. The
    concept had to be widened after measuring: Germany books its energy
    tax on imported fuels under D.2122C (28.7 of 65.1 EUR bn in 2024), so
    D.214A alone measured 1.65 (Steuerschätzung) and 1.79 (OECD 5121) —
    D band — while the sum is what OECD 5121 and the national forecasts
    describe (D.2122C is zero for the UK, 9 EUR mn for France). Anchor
    cells from NTL table 9 / gov_10a_taxag; the drift between those detail
    tables and the main aggregate lands in R02_X, never in V22. Forecasts:
    GBR ← OBR fuel + tobacco + alcohol + air passenger duty + climate
    change levy + environmental levies (the NTL D214A content; measured
    0.986 at CY2025, B, strict to 2030); DEU ← Steuerschätzung Tab 3
    Energie/Tabak/Alkohol/Schaumwein/Kaffee/Strom + Tab 2 Bier (0.918 at
    2024, B, strict to 2030); FRA declared (LPFP PDF, OQ-5). Backward:
    OECD 5121 — FRA 1.015 and DEU 1.000 (B, to 1965 / 1991), GBR 0.731
    (C, maximum only, to 1965: the UK row carries the environmental and
    consumption levies the OECD books outside 5121).
  - **R06_E Employers' actual (D.611) and R06_H Households' actual (D.613)
    contributions**, remainder R06_X = D.612 + D.614 − D.61SC (imputed and
    supplementary; `may_be_negative`). Anchors from the main aggregates
    tables (gov_10a_main D611REC/D613REC; ONS ESA Table 2 D611/D613
    receivable), so the split is exact within the anchor. Forecasts: GBR
    ← EFO table 3.4 Class 1 employer NICs (R06_E) and Class 1 employee +
    Classes 2/4 self-employed NICs (R06_H) — measured 0.73/0.74 at CY2025
    (the anchor's D.611/D.613 include employer and employee contributions
    to public-service pension schemes, outside NICs): C, maximum only, to
    2030. FRA/DEU: no institution publishes the split (AMECO UTAG/UTIG are
    actual/imputed totals) — declared. Backward: OECD 2200 (employers) and
    2100 + 2300 (employees plus self-/non-employed = D.613): FRA 0.99/0.99
    B to 1965; DEU 1.00 B / 0.84 C; GBR 0.74/0.73 C (NICs vs the wider
    D.61x concept, as for the forecast).
  §15 Q13 ("one line, imputed flagged in notes") is superseded: the
  imputed component is a published remainder line.
**Approvals applied**: (c) `tolerances.v16_approved_joins` gains FRA/DEU
E05 ← EC_DSM — the economic tree's interest line now runs to 2036 in
strict beside GF01_7, same source, concept and seam (V16 keeps warning,
as for GF01_7). (b) GBR GF10_2 ← OBR historical public finances database
"Social Security o/w pensioners" (IFS-based, FY 1978-79 to 2022-23,
public sector), read by `readers.obr_hist_pf_fy/_cy` and converted per
§7.10 before growth: measured 0.665 of COFOG 10.2 at 2022 (state pension
and pensioner benefits against the function total, which also carries
public-service pensions and in-kind old-age services; the share drifts
from 0.82 in 1995 as those grow) — grade C, `maximum_extension` only,
UK pensions now run 1979-2024 in maximum (crosswalk
`OBR_HIST_PF_to_COFOG.csv` v1.0). V5 reports the drift.
Gate record and the end-to-end verification the committee asked for are
in D-S13-006.

## D-S13-006 — Gate record and the end-to-end verification the committee asked for: the previously built machinery works unchanged on the 123-line universe (serves §12 gates, §11.6; session 11 close)
2026-09-19. Full chain re-run after D-S13-005 on the 2026-09-19 harvest:
`build` → `reconcile` → `validate` → `report` (incl. `flatten`) →
`statistical-forecasts` → notebook execution → `pytest`. What was checked,
and how, so the "does it still work" question has a recorded answer:
  - **Identities (roll-ups).** V2: Σ GF01–GF10 = TE and Σ E01–E09 =
    TE_ESA in every complete year; V22: Σ R01–R10 = TR (the Level II
    revenue lines are `level: "2"` and stay out of the Level I sum); V19:
    remainder + Σ Level II = parent for all five splits (GF01, GF04, GF10,
    R02, R06) in every year, both variants, and no remainder carries a
    forecast row; V3 shares to 100 on the three Level I sets; V23 ledger.
    `validate`: **OK=87 WARN=2092, no ERROR, no SKIP** (WARN +207 on the
    new lines' V1 GFS/OECD comparisons and V5 stitch diagnostics, all
    intended visibility).
  - **The WEO reconciliation is untouched.** `weo_explanation.csv` and its
    `explained_share` rows (112) are bit-identical to the committed
    version before any split and to `main` at 8b99c74 (max |Δ| = 0.0):
    the §8.3 decomposition works on the 20 Level I lines by literal code,
    so neither the Level II lines nor the second cut of TE can enter it.
    `deficit_dynamics.csv` carries the same 20 lines plus memo rows.
  - **Statistical benchmark forecasts.** `ggfiscal statistical-forecasts`
    regenerated: 113 series × 5 methods (123 less the ten whose official
    strict path reaches 2031: FRA/DEU GF01_7, E05, GF07, GF09, GF10_2);
    `tests/deliverables` re-proves that the set is exactly the series that
    need one, that each fits on outturn only, and that the combination is
    the mean with within-plus-between variance (the index-alignment fix
    of D-S13-004 holds for the new ordering).
  - **Presentation.** `series_catalogue.csv` 132 rows (123 + 9 totals) with
    spans agreeing with `coverage_matrix.csv` (123 rows) on every series;
    `strict_{GBR,FRA,DEU}.csv` 51 columns each (GDP, 17 COFOG + TE, 9
    ESA_EXP + TE_ESA, 15 ESA_REV + TR, 5 ledger); `data_dictionary.csv`
    covers every column of every file (set equality, tested); every
    chained value reproduces from the flat file alone (Gate 6 form,
    all three tree files). The chartbook split into three books so each
    renders: `chartbook.ipynb` 0.79 MB (COFOG tree, ledger, WEO, seams),
    `chartbook_revenue.ipynb` 0.44 MB, `chartbook_esa.ipynb` 0.29 MB —
    every catalogued series charted in exactly one of them, every caption
    stating its projection status (tested per book). Nine forecast books
    (`forecasts_{cc}_{expenditure,revenue,esa}`) chart every granular
    series seven ways where a benchmark exists; `forecasts_GBR_expenditure`
    is 1.06 MB, the one notebook over the 1 MB rendering margin (17 COFOG
    lines × 7 charts) — nbviewer renders it regardless; splitting it is the
    documented fallback if GitHub declines. `derivation.ipynb` re-executed
    over all 132 series. 75 of the 132 series carry no projection at all,
    stated in the chartbook's opening table.
  - **Tests**: `pytest --ignore=tests/debt` **151 passed** (149 + the split
    enumeration and the revenue chartbook).
Nothing in the debt extension changed; `tests/debt` were not re-run.

## D-S13-007 — The session-11 benchmark methodology of `main` (D-S11-001..004) integrated on the 123-line universe; the benchmark balance takes the pension split as it takes the interest split (serves D-S11-002/003, D-S13-002, D-S9-004; session 11 close, 2026-09-19)

**Context.** Four branches had not landed on `main` when this branch was
started, and three of them carry methodology this branch had to reflect:
`friendly-archimedes` (D-S11-001..004: forecast panels in the chartbook, the
benchmark balance `benchmark_balance.csv`, the levels benchmark
`forecast_levels.csv`, the WEO comparison `benchmark_vs_weo.csv`),
`charts-ios` (the phone chart site), `french-debt-aft-briefing` (D-S12-001,
the AFT briefing and debt simulator) and `cofog-cyclical-adjustment-check`
(OQ-11, informational). They were merged into `main` in that order as PRs
#14–#17 after each was rebased onto `main` and its clashing identifiers
renumbered (this branch's decisions D-S11-00N → D-S13-00N in commit
3cd0c75; the briefing's D-S11-001 → D-S12-001; the cyclical check's OQ-8 →
OQ-11). `main` was then merged into this branch twice (after #14, after #17)
and the benchmark chain re-run on the full universe.

**Decisions.**

1. **The benchmark balance splits `GF10` exactly as D-S11-002 split `GF01`.**
   D-S11-002's rule is that an official projection must not be hidden inside
   a statistical parent. Checked against every Level II line of D-S13-002/005
   (catalogue spans, strict variant): three parents hide an official strict
   path in some country — `GF01` (GF01_7, all three countries, as before),
   **`GF10`** (GF10_2, France and Germany: the Ageing Report's pension path is
   grade B and enters strict to 2070, whereas GF10's own Ageing Report leg is
   grade C and lives in `maximum_extension` only, so strict GF10 is a
   statistical fit) and `R02` (R02_A, Germany, Steuerschätzung to 2030 — one
   year short of the 2031 horizon, so the balance would take the statistical
   path anyway). Expenditure in the sum is therefore
   `GF01_7 + GF01_X + GF02..GF09 + GF10_2 + GF10_5 + GF10_X`; revenue stays
   `R01..R10`. `GF04` (no official path on either side) and the revenue splits
   stay as their parents; the trigger for revisiting is written into
   `balance.py` (a Level II line with an official strict path to the horizon
   while its parent has none — the German excise path reaching 2031 in a later
   vintage would be the first case). Effect on the 2031 benchmark balance
   (% of GDP, with the 80% interval): France −6.13 → **−6.46** [−10.61, −2.31]
   (GF10_2 official −0.02 pp, GF10_5 −0.34, GF10_X −0.14, against GF10's
   statistical −0.18); Germany −2.47 → **−2.86** [−9.97, +4.26] (GF10_2
   official −0.48, GF10_5 +0.28, GF10_X −0.16, against +0.03); the United
   Kingdom −7.27 → −6.95 (all three parts statistical, as GF10 was; the
   difference is three fits against one). `n_official` rises from 3 to 4 in
   France and Germany. The WEO still sits inside the 80% interval in 21 of 21
   country-years (D-S11-004).
2. **`forecast_levels.csv` covers all three trees.** The statistical
   benchmarks already covered the ESA_EXP lines (113 series); `levels._tree()`
   now reads `expenditure_esa.csv` too, so the currency lookup and the GDP
   anchor ("the last year every line's denominator agrees") are taken over
   every line. The anchor is unchanged at 2024 in all three countries. The
   levels charts of `chartbook_esa.ipynb` and `chartbook_revenue.ipynb` carry
   the benchmark leg (D-S11-003) exactly as the main book's do — the three
   books share the setup cell — and the caption test runs per book.
3. **Forecast panels (D-S11-001) in three books.** The main book keeps the
   COFOG and revenue panels and the ranked `changes()` picture across both
   (the revenue per-series charts live in `chartbook_revenue.ipynb` under
   D-S13-006, but the panel is the summary and `changes()` pairs the two sides
   of the balance, so both stay). `chartbook_esa.ipynb` gains its own panel of
   the nine `E` lines (`panel(iso3, "economic")`, the same cell with `TREE_OF`
   pointed at the economic tree) and no `changes()`: the economic tree is the
   same money as the COFOG tree cut a second way and would double-count in a
   ranked picture that feeds the balance. The panel table's row pattern in
   the tests now admits Level II codes (`R02_A`, `E03`).
4. **Size.** `chartbook.ipynb` is 1.31 MB with the panels (1.39 MB on `main`,
   0.79 MB on this branch before the merge): the D-S11-001 title already
   records that the panels cost the D-S9-004 margin, and the revenue tree's
   per-series charts are already out. Moving the revenue panel to its book
   would save 0.12 MB and split the summary; not done. nbviewer renders
   regardless; the chart site (`tools/build_chartsite.py`) now carries the
   two companion books beside the main book and the debtbook.
5. **Nothing else in the merged methodology needed a line assumption
   changed**: `weo_compare.py` reads the balance file by side; the §8.3
   decomposition stays on its 20 lines (D-S13-006); the chart site's
   forecast books are deliberately not on the phone site (D-S11 notes).

**Verification.** Full chain re-run (`build`, `reconcile`, `validate`,
`report`, `statistical-forecasts`, `forecast-levels`, `benchmark-balance`,
`benchmark-vs-weo`), `tools/update_notebooks_s11.py`, all thirteen
notebooks re-executed; `pytest --ignore=tests/debt` **173 passed** (151
before the merge, plus `main`'s panel / balance / levels / WEO tests, the
caption and benchmark-leg tests now run per book, and the ESA tree in the
fidelity test). One merged test was loosened to its own claim: the WEO's
z-score against the benchmark cone is asserted inside the 80% band
(|z| < 1.28, which is what §4.6 says) rather than below 1.0 — France 2031
is 1.10 after the pension split, still inside.

## D-S14-001 — The committee took the replication scoping note's ten questions on their defaults; `REPLICATION_KICKOFF.md` (specification v2.4 addendum) adopted as the governing plan for the United States and Japan (serves parent §0–§2, §16; resolves OQ-12; session 12, 2026-09-20)

**Context.** `REPLICATION_SCOPING.md` (2026-09-20) set out, from sources
tested live, what replicating the package for `USA` and `JPN` requires,
audited the code, estimated the effort and tabled ten questions
Q-R1–Q-R10 with build defaults. The committee answered "let's do this" on
the defaults and asked for the plan to be written here.

**Decision.** `REPLICATION_KICKOFF.md` governs USA and JPN matters; where
it is silent the parent and the debt specification govern. Its decisions
D18–D27 record the ten answers:

| Q | Answer (default) | Kickoff decision |
|---|---|---|
| Q-R1 anchor | OECD SNA Tables 11/12/10 (the NSO's own data on the SNA framework); NIPA/ESRI as same-institution secondary | D18 |
| Q-R2 Japan's COFOG basis | published FY-labelled with a FY/CY bridge on TE as a deliverable; no anchor converted | D19 |
| Q-R3 structural zeros | zero rows typed `structural_zero` (USA R01, E04, GF05) | D20 |
| Q-R4 Japan's D.41 | FISIM-adjusted (ESA concept); unadjusted reported as the wedge | D21 |
| Q-R5 sub-perimeter forecasts | rank-4 proxies, maximum only, grade C (B at ≥ 0.90 coverage) | D22 |
| Q-R6 PDF tables | admitted when machine-extracted with reproduced printed totals | D23 |
| Q-R7 blocked hosts | proceed on CBO's mirror and CMS; cbo.gov and ssa.gov registered blocked with the hand-retrieval route | D24 |
| Q-R8 Japanese positions | reconstructed from flows, grade B, validated against BoJ holdings, by-type totals and the live snapshot | D25 |
| Q-R9 US Level II | BEA sub-functions as `level2_proxy_actual`, grade B | D26 |
| Q-R10 scope | both countries specified; build order R0 → USA fiscal → go/no-go → JPN fiscal → debt extensions | §1, D27 |

Both countries are in the specification so that the one-off
generalisation (Stage R0) is designed once for fiscal-year anchors, a
third anchor family and structural zeros; the Japanese build is staged
behind the US Gate U6 (Q-K6 default lets J0's harvest run earlier).

**Consequences.** Six new committee questions (Q-K1–Q-K6) carry defaults
in kickoff §15. New validation tests V41–V45 and amendments to V9, V17,
V24. New `observation_type` value `structural_zero`; new deliverable
`fy_cy_bridge.csv`. No number changes for GBR, FRA or DEU: Gate R0's
acceptance is byte identity of the canonical layer and the bundle.
`OPEN_QUESTIONS.md` OQ-12 is resolved by this entry; OQ-13 (the blocked
US hosts as the trigger for the long US legs) is opened.

**Nothing built.** No source registered in `config/sources.yaml`, no
snapshot taken, no code changed in this session.

## D-S15-001 — Stage R0 opened: `config/countries.yaml` is the single source of country routing; the country list, currency schema, display names and per-country flat files come from it (serves REPLICATION_KICKOFF.md §11.1, §12 Stage R0, D27; session 13, 2026-09-20)

**Context.** Kickoff §12 Stage R0 and the scoping note's F1: the country
list was a tuple in `config.py`, the pandera `iso3`/`currency` checks were
literals, the display-name map was copied three times, and
`manifest.FLAT_FILES` named `strict_{GBR,FRA,DEU}.csv` by hand. R0's
acceptance is that none of the three countries' numbers moves.

**Decision.** `countries.yaml` carries, per country, `name`, `prose_name`,
`aliases`, `currency`, `anchor_family`, `lines_absent`, `period_basis`
(anchor and per-tree), `fy_to_cy_weights`, `weo_perimeter_gap_expected`,
`perimeter_break` and `backward_legs`, beside the keys it already had.
`config.COUNTRIES` is read from the file in file order (a lazy module
attribute, so importing the package outside a checkout still works), and
every new key has an accessor (`config.country`, `country_names`,
`prose_names`, `country_aliases`, `currencies`, `lines_absent`,
`absent_lines`, `period_basis`, `tree_period_basis`, `fy_label`,
`fy_to_cy_weights`, `weo_perimeter_gap_expected`, `perimeter_break`,
`backward_legs`, `source_period_basis`, `family`). An unconfigured
country raises `KeyError` naming the file and the configured countries.
The pandera `iso3` and `currency` checks (parent and debt schemas) are
evaluated against config at validation time; `publish.flatten`,
`forecast.statistical`, `report.readme`, `tools/build_chartsite.py` and
`tools/update_notebooks_s11.py` take their country lists and names from
`config.country_names()`; `manifest.FLAT_FILES` enumerates
`strict_{iso3}.csv` from `config.COUNTRIES`.

**Values for GBR/FRA/DEU** are the ones that change no behaviour
(kickoff §11.1's closing paragraph): `anchor_family: ons | eurostat`,
`lines_absent: {}`, every tree `CY`, `fy_to_cy_weights: [0.25, 0.75]`,
`perimeter_break: 1991` for DEU and null otherwise, `backward_legs`
enabling only DEU's existing GFS COFOG leg.

**Evidence.** Chain re-run after the step: `data/canonical/` and
`deliverables/` byte-identical to the session baseline except `run_id`;
`ggfiscal validate` OK=87 WARN=2218 ERROR=0 (the baseline counts).

## D-S15-002 — Anchor families: the `AnchorFamily` interface of kickoff §11.3, `OnsFamily` and `EurostatFamily` wrapping the existing readers unchanged, and every routing site calling `config.family(iso3)` (serves D27, kickoff §11.3, scoping §6 F1)

**Decision.** `standardise/families.py` defines the protocol (`cofog`,
`cofog_total`, `main`, `tax`, `d41_payable`, `gdp`, `totals`, `level2`)
and the two implementations. Beyond the protocol, a family also carries
the institution-specific cell arithmetic that used to sit inline at the
routing sites — the D1 revenue mapping (`revenue_lines`, `revenue_total`),
the ESA_EXP item lists (`esa_exp_parts`), the revenue Level II cells
(`revenue_level2`), the reconciliation and coverage candidate lists
(`recon_revenue`, `revenue_coverage`), the §8.2 aggregates
(`bridge_aggregates`) and its source ids — because those are exactly the
places that decided by `iso3 == "GBR"`, and a family is meant to be the
complete answer to "which cells build this country's trees". Every
series a family returns is the same reader call the site made before, so
the canonical layer is byte-identical (a test pins each wrapper against
its reader). `config.family(iso3)` resolves `anchor_family` through the
registry `families.FAMILIES`; a country without the key, or naming a
family the module does not implement, raises `FamilyNotConfigured` — the
gate's dry `config.family("USA")` — and nothing falls through.

**Sites.** `build.anchor_series` / `_revenue_level2` / `gdp_series` /
`build` (ledger totals), `coverage._cofog_sources` / `line_sources`,
`reconcile/bridge.anchor_aggregates`, `reconcile/recon_v0._anchor_cofog`
/ `compute`, `validate/stage1.check_v21`. The forecast-envelope choice in
`validate/stage3._envelopes` and its twin
`reconcile/explanation._official_totals` (both `iso3 == "GBR"`) now go
through `forecast/envelopes.py`, keyed by the first entry of the
country's `envelope_forecast` (OBR databank / AMECO readers; an envelope
source with no reader raises). The GF10_2 forecast-candidate declaration
in `coverage.line_sources` (Ageing Report for FRA/DEU, the OBR historical
series for GBR) keeps its country names: it is a per-country *source*
declaration of the kind `forward.py` and `backward.py` carry (kickoff
C4/C5 per-country work), not anchor routing; the test says so.

**Not done, deliberately.** The GBR revenue cell codes (D51M, D51O, D39R,
…) stay in `OnsFamily.revenue_lines` rather than moving into `lines.yaml`
`ons:` blocks: moving them is a per-line config refactor with its own
review, and the OECD family for USA/JPN will need SNA cell codes that do
not exist in `lines.yaml` either (scoping §6, "ESA-keyed line cells").
The family is where a third institution's mapping will live, and the
`lines.yaml` `oecd_t12` cells of §11.4 land with U1/J1.

**Evidence.** Anchors, coverage candidates and bridge aggregates dumped
from the step-1 code and from the family-routed code are identical for
all three countries; chain byte-identical; validate OK=87 WARN=2218
ERROR=0.

## D-S15-003 — Structural zeros (D20) are plumbed end to end and produce nothing for GBR/FRA/DEU (serves kickoff D20, §5, §10 V41, §12 Stage R0)

**Decision.** `lines_absent` (line -> reason) resolves through
`config.absent_lines(iso3)` to (classification, line); a code that is not
a granular line of exactly one tree is a config error. The build
publishes such a line as `structural_zero` rows (new
`observation_type`): 0.0 in every anchor year of its tree — the years the
tree's own total covers, or the parent's years for a Level II line —
grade A, from the tree's total's source, the reason as the note, in both
variants; it is never extended backward, never forecast, and gets a
`structural_zero` declaration row (so the reason reaches the coverage
matrix's `reason_series_ends` and the catalogue's `forecast_note`). The
D10 D.41 fallback does not run on an absent interest line. V41 (ERROR,
`validate/r0.py`) checks: every declared line has structural_zero rows in
exactly the anchor years, none elsewhere, zero at grade A, reason carried;
every structural_zero row is declared. The identities tolerate declared
absences by treating the line as zero: `stage1._sum_check` (V2/V22),
`reconcile/dynamics.decompose` (§8.3), `forecast/balance._leg` (a zero
leg with no error); `S0_LINES` names the declared absences and keeps them
in the universe (published lines); `coverage.line_sources` counts a
declaration as coverage (Gate U0's "or a `lines_absent` entry");
`tests/stage_1/test_gate1.py` derives its expected line sets from config.
`publish.flatten` labels the type ("structural zero (D20)"). The data
dictionary's text listing the observation types is unchanged until a
bundle carries one — the dictionary describes the bundle.

**Exercised.** A test declares `R01` and `GF10_5` absent on a
monkeypatched copy of the config and checks the zero rows, the remainder
arithmetic and the identity fill; for the real config every helper is
empty and V41 reports "no lines_absent declared".

**Evidence.** Chain byte-identical except the one new `V41` OK row in
`exceptions.csv`; validate OK=88 WARN=2218 ERROR=0.

## D-S15-004 — Period basis per country and per tree (D19, §7.10): conversion weights from config, `source_period_basis` and `native_period` from the tree's published basis, the register's `period_basis` policed by V42, and `fy_cy_bridge.csv` published empty (serves kickoff D19, §5, §7.10, §10 V42, §11.4)

**Decision.**
- `forward.fy_to_cy(fy, weights)` takes the country's `fy_to_cy_weights`;
  every OBR/PESA conversion in `forward.py`, the OBR pensioner leg in
  `backward.py`/`coverage.py` (`readers.obr_hist_pf_cy(column, weights)`),
  the envelope readers and the debt engine's NLF conversion
  (`debt/intermediates.fy_to_cy`, now delegating to the one
  implementation) pass them. The default pair stays 0.25/0.75, so the
  parent §7.10 numbers are unchanged; 0.75/0.25 is a config value for an
  October–September country.
- `sources.yaml` gains `period_basis` (FY on OBR_EFO_LATEST, OBR_FRS,
  OBR_PSF_DATABANK, OBR_HIST_PF, HMT_PESA; CY by default);
  `config.source_period_basis(sid)` reads it.
- Every canonical row is stamped `source_period_basis` = the published
  basis of its tree (`countries.yaml period_basis.trees`) and
  `native_period` = `FY{start_year}` on a FY-labelled tree, the calendar
  year otherwise. **Why the tree's basis and not the source's:** the rows
  the OBR sources produce are calendar-year values (converted per §7.10,
  flagged `is_period_converted` with `period_conversion_method`), and
  stamping them FY from the register would both misdescribe the value and
  change ~700 published cells. The register basis is what V42 polices:
  no CY-basis source is chained onto a FY-labelled tree (§7.14), and a
  FY-basis register source enters a CY tree only through a conversion
  (checked on forecast rows, which carry the flag; the OBR pensioner
  backward leg converts inside its reader and its stitched rows carry no
  conversion flag — a pre-existing gap noted, not changed).
- `fy_cy_bridge.csv` (canonical and bundle, in `manifest.DELIVERABLES`
  and `FLAT_FILES`, described in the data dictionary): one row per
  (country, FY-labelled tree, year) with TE on the FY basis (the tree's
  total), TE on the CY basis (the balance anchor's TE from the family),
  the gap, `timing_component_lcu_mn` from
  `build.fy_cy_timing_component` (a hook returning None until a quarterly
  reader exists — the whole gap is residual, never allocated) and the
  residual. V42 checks additivity per row. Header only for the three
  countries; a test declares FRA's COFOG tree FY on a copy of the config
  and checks the rows fill additively.

**Evidence.** Forecast and extension source registries dumped before and
after are identical; chain byte-identical except the `V42` OK row, the
new empty file and the 14 data-dictionary rows and README lines that
describe it; validate OK=89 WARN=2218 ERROR=0.

## D-S15-005 — The WEO perimeter rule and the perimeter break are config (serves kickoff §8.2, §10 V24 amended, §7.12; scoping G5)

`reconcile/bridge.compute` classifies the base-year NLB gap by
`weo_perimeter_gap_expected` (stability about the country mean where a
perimeter gap is expected; size against the base-bridge tolerance
otherwise); `validate/stage5.check_v24` picks its rule the same way, and
the tolerance key is renamed `perimeter_sigma_pct_te` (it applies to any
country with the flag). `stitch/backward.py` stops every extension source
at `config.perimeter_break(iso3)`; `DEU_BREAK` is gone. Chain
byte-identical; validate OK=89 WARN=2218 ERROR=0.

## D-S15-006 — The IMF GFS COFOG and SOO backward legs are generic and enabled per country (serves kickoff §12 Stage R0 "GFS COFOG/SOO backward legs generic"; scoping G6)

`countries.yaml backward_legs.gfs_cofog` enables, for a country, the IMF
GFS COFOG Level I legs (`{code}_T`) and the Level II group legs
(`gfs_indicator` lines other than GF01_7), with the country's own concept
notes in config (they carry measured facts — "boundary ratio ~1.0 at
1995" is DEU's); `backward_legs.gfs_soo` enables the GFS SOO legs of the
ESA_EXP lines (`gfs_soo` codes in `lines.yaml`), appended after AMECO so
they only ever extend below AMECO's own start. DEU enables `gfs_cofog`
(its existing 1991–94 leg, notes and registry order unchanged); no
country enables `gfs_soo` — AMECO reaches every configured break, and
enabling it would add a leg, i.e. a number. The `iso3 == "DEU"` block is
gone; a test enables `gfs_soo` for FRA on a copy of the config and checks
the appended sources. Chain byte-identical; validate OK=89 WARN=2218
ERROR=0.

## D-S15-007 — Notebook and chart-site tooling take their countries from config; a new country's books are seeded by copy (serves kickoff §11.4 "notebooks seeded by copy", §12 Stage R0; scoping G7)

`tools/update_notebooks_s11.py`: the country list, names and section
numbers come from `countries.yaml`. A country with no chartbook block is
seeded by copying the last configured country's section (panel, COFOG
charts, revenue heading, ledger charts) and its WEO sub-section,
retargeted (ISO literal, name, section number), outputs stripped, with
the later top-level sections renumbered — prose cross-references such as
"§4.4" are left for the author of the country's U6 pass. A country with
no forecast books gets each book from the last configured country's
preamble and setup cells plus one section per line (`_series_cells`, so
fan cells appear only where a benchmark exists); the ESA book follows
from the expenditure book as before. `tools/build_chartsite.py` reads
names, prose names and title aliases (`prose_name`, `aliases` in
`countries.yaml`) from config. A test seeds a fourth country on a
temporary copy of the notebooks and pins that the existing books are
unchanged cell for cell (modulo section numbers) and that the tool is
idempotent on the committed books; the committed notebooks and their
outputs are untouched.

## D-S15-008 — The debt engine is explicit per country through `config/debt.yaml countries`; the `else` branch of `intermediates.official_totals` is removed (serves kickoff §12 Stage R0 "Debt engine"; scoping D1)

`config/debt.yaml` gains `countries`: per country the register module,
the aggregates builder, the official-totals builder (`module` or
`module:function` under `ggfiscal.debt`, resolved by
`debt/countries.py`), the sub-sector chain source and the V31
cross-check kind. `intermediates.official_totals` calls the country's
builder (`official_totals_gbr` / `_fra` / `_deu`, the former branches as
functions) after the package's step C, and raises
`DebtCountryNotConfigured` for a country without one — checked before
any data is read. `register.country_modules()` replaces
`COUNTRY_MODULES`; `aggregates.class_aggregates` iterates the configured
builders; `chains._subsector_items` reads `subsector_source` (None for
GBR); `validate.check_v31` runs the Eurostat GD_F3 comparison where the
kind is `eurostat_gd_f3` and reports the same-source note where it is
`same_source`; `reference.py` enumerates the OECD FINMARK rates from the
`reference_series` entries. The mapping is listed in the engines'
historical order (DEU, GBR, FRA) so a rebuild keeps its row order. A
stale import of the removed `debt.model.ISO3` in `debt/aggregates.py`
(from D-S15-001's schema change) is fixed here — it was masked by the
debt tests failing on absent snapshots (D-S15-009).

**Not verified by rebuild.** The debt layer is not part of the R0 chain
and its inputs (`ggfiscal debt fetch`) are not harvested in this
container, so `debt_*.csv` were not regenerated; the routing is verified
by tests that resolve every configured builder to the function that ran
before and by reading the diff. The committed `debt_*.csv` are unchanged.

## D-S15-009 — Gate R0 record: what was measured, what is byte-identical, and the two exceptions (serves kickoff §12 Gate R0)

**Baseline (this container, 2026-09-20).** The refetchable D8 snapshots
were absent; `ggfiscal fetch --all` ran once (80 pulls, 0 failures,
manifest appended). The rebuilt canonical layer was identical to the
committed one except `run_id`. Baseline `ggfiscal validate`: OK=87
WARN=2218 ERROR=0 (session 11 recorded WARN=2092 on its own harvest; the
count is vintage- and container-dependent, see S0_SNAPSHOTS). Baseline
`python3 -m pytest -q`: 253 passed, 80 skipped, 33 failed, 21 errors —
every failure and error in `tests/debt/`, all `FileNotFoundError` /
empty-frame `KeyError` for debt snapshots (`run ggfiscal debt fetch`),
none in the parent package.

**After the eight steps.** Each step's chain (`build`, `reconcile`,
`validate`, `report`, `flatten`) ran against a frozen copy of `src/` and
was diffed against the baseline copy of `data/canonical/` and
`deliverables/`: every file byte-identical except `run_id`, with exactly
these additions — (a) `exceptions.csv` gains the OK rows of the two new
checks V41 and V42 (OK=89, WARN and ERROR unchanged), (b) the new
`fy_cy_bridge.csv` (canonical and bundle, header only), its 14 rows in
`data_dictionary.csv` and the two README lines that list it and the
dictionary's row count. No value of any series, ledger, bridge,
decomposition, catalogue or matrix moved. `ggfiscal validate` ERROR=0
with the baseline WARN count. `python3 -m pytest -q`: 285 passed, 80 skipped, 33 failed, 21 errors — the 253 passed of the baseline plus the 32 new R0 tests, and the same 54 debt tests failing for the same absent snapshots; two pre-R0 tests were updated to the R0 spec (the flat-file completeness test admits the header-only bridge while no tree is FY-labelled; the suite-count test lists V41/V42 beside V1–V28) — the
baseline plus the new R0 tests (`tests/stage_0/test_r0_generalisation.py`
24 tests: config keys, family protocol and registry, the
unconfigured-family error, structural zeros, period basis, perimeter
rules, GFS legs; `tests/deliverables/test_r0_notebook_tooling.py` 3;
`tests/debt/test_r0_debt_config.py` 5), the same debt tests failing for
the same absent snapshots. The gate's "pytest green" therefore holds for
everything this container can run and is stated, not claimed, for
`tests/debt/` — OPEN_QUESTIONS.md OQ-14 records it.

**No country added, no source registered, no data pulled beyond the
parent harvest, no notebook output touched.**

## D-S16-001 — Stage U0 opened: the United States is configured (kickoff §11.1 verbatim), the country list is four, and a dry `config.family("USA")` raised `FamilyNotConfigured` until the family landed (serves REPLICATION_KICKOFF.md §11.1, §12 Stage U0; session 14, 2026-09-21)

**Context.** HANDOFF.md (session 13) and kickoff §12 Stage U0: verify and
harvest the United States on the generalised package of R0. Baseline in
this container before any change: `pip install -e ".[dev,forecast,notebook]"`,
`ggfiscal fetch --all` (80 pulls, 0 failures — the D8 snapshots were absent),
the chain, `pytest`. The rebuilt canonical layer and bundle were identical
to the committed ones except `run_id` and the container-dependent
`S0_SNAPSHOTS` WARN rows (`exceptions.csv`: 2387 rows vs 2307 committed —
80 more "snapshot file missing locally", the pulls recorded in the previous
container); `ggfiscal validate` OK=89 WARN=2298 ERROR=0 (HANDOFF expected
WARN≈2218: the difference is those 80 rows); `python3 -m pytest -q` 285
passed, 80 skipped, 33 failed, 21 errors — every failure in `tests/debt/`
(OQ-14, absent debt snapshots). Baseline copies of `data/canonical/`,
`deliverables/`, `data/standard/` and the v0 reports were taken to
`/tmp/gg_baseline` before any edit.

**Decision.** `config/countries.yaml` gains the `USA` block of kickoff
§11.1 — `currency: USD`, `anchor_family: oecd_sna`, the five anchors,
`gdp_source: OECD_T1`, `secondary_national: BEA_NIPA`, `interest_anchor:
d41`, `level2_source: BEA_NIPA_T316` (D26), `lines_absent` R01/E04/GF05
with their reasons (D20), every tree CY, `fy_to_cy_weights: [0.75, 0.25]`,
`envelope_forecast: [EC_AMECO, OECD_EO]`, `weo_perimeter_gap_expected:
true`, `perimeter_break: null`, `backward_legs: {}` — plus `name`,
`prose_name`, `aliases` and `stage_reached: 0` (D-S16-008). Two accessors:
`config.level2_source(iso3)` and (D-S16-008) `config.stage_reached` /
`countries_at_stage`; `config.level2_splits` carries the new cell keys
(`oecd_t11`, `oecd_t12`, `oecd_t10`, `bea_nipa`) in its per-line meta.
`config.COUNTRIES` is `("GBR", "FRA", "DEU", "USA")`; before step 3
`config.family("USA")` raised `FamilyNotConfigured("USA: anchor family
'oecd_sna' is not implemented …")` (checked; no fall-through).

## D-S16-002 — `readers_oecd.py`: the OECD SNA tables on the `_oecd_frame` pattern, UNIT_MULT-scaled to LCU millions; the Table 1 GDP flow resolved live (serves kickoff D18, §11.2, §11.3)

**Decision.** `standardise/readers_oecd.py` reads `OECD_T12_{EXP,REV,BAL}`
(`oecd_t12(iso3, item, flow)`, TRANSACTION × XDC), `OECD_T10`
(`oecd_t10`), the Table 11 transactions by function (`oecd_t11_item`, for
the D4 × GF01 cross-check; OTE per function stays `readers.oecd_t11_cofog`),
`OECD_T1` (`oecd_t1_gdp`: B1GQ, XDC, PRICE_BASE V) and `OECD_EO`
(`oecd_eo`: XDC measures scaled, PT_B1GQ ratios as published). All reuse
`readers._oecd_frame` / `_to_millions` unchanged; the readers of the three
existing families are untouched.

**Resolved live 2026-09-21.** The OECD.SDD.NAD catalog carries no plain
"DF_TABLE1" GDP flow: `DSD_NAMAIN10@DF_TABLE1_EXPENDITURE,2.0` (12-dim
key `A.{iso3}...B1GQ.......`) serves B1GQ in national currency at current
prices, UNIT_MULT 6, USA 1970–2025 (2024 = USD 29,298,013 mn, equal to the
EO GDP series). The EO flow `DSD_EO@DF_EO,1.5` (key `{iso3}.<M1>+….A`)
serves the fifteen USA measures 1960–2027 in units (UNIT_MULT 0). Table 12
for the USA: EXP 27 transactions, REV 26, BAL 8, all 1970–2024, UNIT_MULT
6; Table 10 43 transactions; Table 11 nine functions (no GF05 rows) plus
`_T`, eighteen transactions incl. D4 by function. The codelist labels used
in the crosswalks (P1O = "Market output, output for own final use and
payments for other non-market output"; D51M/D51O "including holding
gains"; D6M; D9N; P5L) come from `CL_TRANSACTION` of DSD_NASEC10 1.1.

## D-S16-003 — `readers_bea.py`: the NIPA flat files, register-driven, a secondary reader and not a family (serves kickoff D18 secondary, D26, §7.16, §11.3)

`SeriesRegister.txt` (15,619 (series, table:line) cells) and `NipaDataA.txt`
(annual, 1929–2025, USD millions for the "Current Dollars, Level" series —
A001RC 1929 = 105,322) are snapshotted with `NipaDataQ.txt`; a cell is
addressed as (table id, line number): `nipa_series("T31600", 5)`. The reader
serves the D26 Level II proxies (`level2_proxy(line_code, spec)` over the
lines.yaml `bea_nipa` cells) and, later, the §7.16 legs; it is never an
anchor (Table 3.16 "current expenditures" is CFC-in, investment-out — §14).
The BEA API needs a key and is not used.

## D-S16-004 — Endpoints and register: per-country pulls enumerate the register's `countries`; every §13.1 USA entry registered with its verification status; the blocked hosts recorded (serves kickoff §11.2, §13.1, D24)

**Decision.** `ingest/endpoints.py`: the `ISO3 = ("GBR", "FRA", "DEU")`
literal is gone — `registered_countries(source_id)` reads
`config/sources.yaml countries` (restricted to `config.COUNTRIES`), so
adding the USA to `IMF_WEO`, `IMF_GFS`, `OECD_RS`, `OECD_T11` and
`EC_AMECO` is a register change (19 more Stage 0 pulls: 15 WEO, 2 GFS, RS,
T11). `all_u0_pulls()` adds the §11.2 endpoints, again keyed by the
register: OECD T12 EXP/REV/BAL, T10, T1, EO (USA), the three BEA flat
files, the Fed Z.1 zip, the six OMB Historical Tables workbooks
(`hist01z1, hist01z3, hist03z1, hist03z2, hist14z1, hist15z1` of the FY2027
Budget, resolved from the historical-tables page; `BROWSER_HEADERS`), the
CBO mirror's `baselines.csv` / `actuals.csv`, the CMS 2026 expanded tables
zip — 19 pulls; `fetch_all` runs them after the Stage 0 and Stage 3 pulls
(118 in all). `fiscaldata_url()` keeps the literal `page[size]` brackets
(nothing pulled in U0; UD0). BEA `.txt` files snapshot with a `txt`
extension. **Harvest 2026-09-21: 118 pulls, 0 failures.** `www.cbo.gov`
and `www.ssa.gov` re-tested with browser headers: HTTP 403 (DataDome,
Akamai) — `CBO_SITE` and `SSA_TRUSTEES` are registered `status: blocked`
with the D-S7-001 hand-retrieval route named (`ggfiscal ingest-file`),
which V18 reports as WARN (intended visibility, as for obr.uk).

`config/sources.yaml`: OECD_T12_EXP/REV/BAL, OECD_T10, OECD_T1 (was
"to_verify", now confirmed_live with the resolved flow), BEA_NIPA, FRB_Z1,
OECD_EO (EO 119), OECD_EO_LTB (memorandum, not pulled — Q-K1), CBO_BASELINE,
CBO_SITE (blocked), OMB_BUDGET, CMS_TRUSTEES, SSA_TRUSTEES (blocked),
CENSUS_GOVFIN (not used, D), BLS_CPI (debt reference, UD0). `period_basis:
FY` on CBO_BASELINE, CBO_SITE and OMB_BUDGET (federal October–September),
CY otherwise. `reports/source_register.csv` now publishes the R0
`period_basis` column (HANDOFF session 13 asked for it at the next
regeneration).

## D-S16-005 — The SNA-to-ESA cell mapping of the USA revenue and economic trees (the judgement item), recorded per cell in `crosswalks/OECD_T12_to_ESA_EXP.csv` and `crosswalks/OECD_T12_T10_to_ESA_REV.csv` (serves kickoff §4.2, §4.3, §11.4; scoping §6 C1)

**Decision.** `config/lines.yaml` gains `oecd_t11` (COFOG codes, identical
to the ESA ones), `oecd_t12` (Table 12 items per line, expenditure flow for
ESA_EXP, revenue flow for ESA_REV) and `oecd_t10` (tax detail) cells, and
`bea_nipa` cells on the four Level II lines. Every choice was measured on
USA 1970–2024 before it was written:

- **ESA_EXP** = the same items as gov_10a_main (D1, P2, D62, D632, D41,
  D3, D29 + D5 + D4 − D41 + D7 + D8, P5 + NP, D9, OTE): E01..E09 = OTE to
  USD 0.002 mn in every year. D29, D5, D8, D39, D92, D4N and P5M are
  identically zero for the USA (so E07 = D7; P5 = P51G).
- **R09 = P1O**, not "P1M + P1O + P131": OTR closes only with P1O (OTR = D2 +
  D5 + D61 + D4 + D7 + D9 + D39 + P1O to 0.002 mn), and P1O = P1M + P131
  exactly — the codelist label says P1O IS the sales aggregate P.11 + P.12
  + P.131; P1M and P131 are its memo components. Kickoff §4.3's "P1M + P1O
  + P131" would double count.
- **R03 = T10 D51M, R04 = T10 D51O** (including holding gains), not the
  kickoff's D51A / D51B (excluding them): the ESA_REV concept is D51A_C1 /
  D51B_C2, which include holding gains (what gov_10a_taxag and ONS D51M/D51O
  carry); D51M + D51O = D51 exactly in every year, whereas D51A + D51B would
  leave the holding-gains taxes (USD 502,624 mn in 2024) unallocated, in R05.
- **R05 = T12 D5 − R03 − R04 + T12 D91** (the existing families' formula;
  D.59 inside D.5). D5 and D91 from Table 12 so the identity closes; the
  Table 10 vs Table 12 D5 drift (up to USD 5.8 bn in some years, 1.3 mn in
  2024) lands in R05 as the Eurostat taxag/main drift does (D-S1-002).
- **R06, R06_E, R06_H = T12 D61, D611, D613** (D611 + D613 + D612_D614 =
  D61; Table 10's D61 differs by up to 0.7 bn); **R02_A = T10 D214A** (no
  D2122C cell for the USA; import duties D2121 stay in R02_X); **R07 = T12
  D41 (REV)**; **R08 = D4 − D41 = D4N**; **R10 = D39 + D7 + D9 − D91**
  (residual; the enterprise surplus of kickoff §4.3 is B2N, a balancing
  item outside OTR — measured and not found in the revenue flow); **R01 =
  D211 = 0** (structural zero); **TR = OTR**.
- **COFOG** = Table 11 OTE per function, total `_T` (differs from OTE by
  −665 to +1,335 mn across the years — two tables of the same institution;
  the ledger takes OTE); GF05 has no rows and the nine published functions
  sum to `_T`, so it is zero by additivity (D20).
- **Interest**: T11 D4 × GF01 = T12 D41 to table rounding (≤ USD 3 mn), so
  GF01_7 = D.41 by construction (D26; the D10 fallback builds it,
  `level2_proxy_actual` B). OECD EO GGINTP (1,397,625) and NIPA interest
  payments (1,397,636) are the NIPA/IMA concept incl. imputed pension
  interest: +0.94% on T12 D41 in 2024, 1.00–1.03 over 1970–2024 — the
  wedge kickoff §4.2 asks to note.
- **GF04_5 = NIPA T3.16 line 14 (transportation, current expenditures)**:
  Table 3.17 publishes gross investment by function at Level I only, so
  D26's "current plus gross investment" is not constructible cell-for-cell
  — OQ-15. GF10_2 = line 38 (retirement, OASI incl. survivors), GF10_5 =
  line 40 (unemployment).

## D-S16-006 — `OecdSnaFamily` registered as `FAMILIES["oecd_sna"]`; per-flow source ids on the family base (serves kickoff §11.3, D18, D27)

`standardise/families.py`: `OecdSnaFamily` implements the protocol
(`cofog`, `cofog_total`, `main` — flow by direction —, `tax`, `d41_payable`,
`gdp`, `totals`, `level2` → None) and the site methods (`d41_receivable`,
`revenue_lines`, `revenue_total`, `revenue_coverage`, `revenue_level2`,
`esa_exp_parts`, `recon_revenue`, `bridge_aggregates` — GF01_7 = D.41)
from the lines.yaml cells. Because the OECD publishes the main aggregates
as three flows, `_Base` gains `esa_exp_source` / `revenue_source` /
`balance_source` properties defaulting to `main_source`; the build stamps
each tree's rows and the ledger with its flow (OECD_T12_EXP / _REV / _BAL)
and the coverage matrix labels the ESA_EXP anchor by it — nothing changes
for ONS and Eurostat (identity holds). `coverage._cofog_sources` no longer
lists OECD_T11 as a *secondary* candidate for a family whose anchor IS
Table 11 (a family-attribute check, not a country literal).

## D-S16-007 — D26 in the build: the USA Level II lines are `level2_proxy_actual` (B) from the NIPA cells over the parent's anchor years; `standardise/proxies.py` is the config-keyed registry (serves kickoff D26, §9, §11.3; anticipates U1's "Level II proxies")

**Why in U0.** The build runs for every configured country; with the
family's `level2()` returning None the four USA Level II lines and their
remainders would have no rows, and the full-universe gate tests
(`test_coverage_matrix_complete`, the flat-file completeness tests) would
fail for the USA. Rather than weaken those tests, the D26 proxy path is
built: `standardise/proxies.py` maps `countries.yaml level2_source`
(`BEA_NIPA_T316`) to (register source_id `BEA_NIPA`, cell key `bea_nipa`,
`readers_bea.level2_proxy`); `build.anchor_series` asks the family for its
Level II cell and, where None and the country names a source, takes the
proxy restricted to the parent's anchor years (1970–2024; the 1959–1969
NIPA years are U2 legs), typed `level2_proxy_actual`, grade B, concept
flag `level2_bea_function` (kickoff §5), the cell-by-cell concept note; the
remainder rows carry B and "parent minus a D26 proxy year". The interest
line keeps the D10 fallback (D.41). `coverage.line_sources` adds the same
proxy as a candidate (`BEA_NIPA`) and the remainder's coverage takes the
first measurable candidate of each Level II line, so `GF01_X`, `GF04_X`
and `GF10_X` are covered for the USA. Measured shares of the parent
(2024): GF01_7 0.696, GF10_2 0.581, GF10_5 0.016, GF04_5 0.269. V44 (U1)
will police the rows; V19 holds exactly now.

## D-S16-008 — Per-country stage gating: `stage_reached` in countries.yaml; the build runs backward legs from stage 2 and forecast legs from stage 3, the forecast-side reconciliation runs for stage-3 countries, and the stage-gate tests iterate the countries at their stage (serves kickoff §12 "one stage per session", U2/U3 scope)

**Context.** The generic AMECO and OECD RS blocks of `forward.py` /
`backward.py` (which the U0 remit says not to touch) apply to every
country, so the first U0 chain produced unreviewed USA strict forecasts
and RS legs; and the Stage 3–6 gate tests (`declarations cover every
line`, `all three countries stitch 2025`, residual history per country,
notebooks per country) cannot hold for a country whose U2–U6 have not run.

**Decision.** `stage_reached` (0–6, the kickoff §12 stages; missing = 6,
the parent build) is a per-country config value: GBR/FRA/DEU 6 (implicit),
USA 0. `build.build` runs `extensions_for` from stage 2 and
`declarations_for` / `forecasts_for` from stage 3 (the structural-zero
declarations always); `reconcile/explanation.compute` decomposes the
forecast side for `countries_at_stage(3)` (the §8.2 bridge and the §8.3
history decomposition run for every country); the stage-3/4/5/6 tests
iterate `config.countries_at_stage(n)` where they assert that stage's
behaviour (declarations, AMECO stitches, GF01/GF10 proxies, residual
history, notebooks, maximum-only legs), and the per-country strict-file
tests cover all four. The USA canonical layer at U0 is therefore anchors
only: 44 lines × 1970–2024 (2,420 strict rows: anchor_actual A,
derived_actual A/B, level2_proxy_actual B, structural_zero A), the ledger
1970–2024 with NI complete. Nothing changes for the three (their legs run
as before; identity holds). Raising the USA to stage 2/3 is the U2/U3
config change that switches its legs on — after their review.

## D-S16-009 — V4 reads `may_be_negative` from lines.yaml; USA E07 is negative in 1991 in the anchor (serves parent §10 V4, D13)

The first U0 chain's only ERROR: `USA/E07/1991 negative value −25,625` —
Table 12 D.7 payable is −25,625 USD mn in 1991 (the allied Gulf War
contributions netted against current transfers in the SNA presentation),
a published anchor fact (D13: never altered). V4's admitted-negative set
was a literal `{R08, R10, R06_X}`; it now derives from `may_be_negative` in
lines.yaml (the same three plus, since U0, E07 with the reason in the
comment). GBR/FRA/DEU E07 are positive in every year, so the three
countries' findings are unchanged.

## D-S16-010 — `tools/byte_identity.py --countries`: the gate restricted to the existing countries' rows, with every allowed exception named on the command line (serves kickoff §12 "no number moves for GBR/FRA/DEU")

`--countries GBR,FRA,DEU` filters every CSV with an `iso3` column on both
sides, drops the other country's scoped rows from `exceptions.csv` and
compares its unscoped OK rows on (check_id, severity) — their messages
carry country counts —, drops `--new-crosswalk` rows from `crosswalks.csv`,
admits a non-empty per-country `--new-file strict_USA.csv`, and normalises
row counts and the excluded country's lines in the READMEs. Two further
explicit allowances: `--new-scope register/CBO_SITE --new-scope
register/SSA_TRUSTEES` (the V18 WARN rows of the blocked hosts, never at
ERROR) and `--check-now-scoped V24` (the unscoped V24 OK row of the
baseline is replaced by the USA's scoped V24 WARN rows; the three
countries' V24 findings are unchanged = none). The gate reports OK for
GBR/FRA/DEU on the U0 chain (D-S16-012).

## D-S16-011 — `reports/source_verification_USA.md` is generated by `tools/source_verification_usa.py` from the snapshots and the canonical layer (serves kickoff §12 Stage U0 "measure and record", Gate U0)

The report carries the harvest record, first/last year per (line, source)
for all 41 USA lines (80 (line, source) rows from `ggfiscal coverage`),
the anchor identities, the three structural zeros, the D26 proxy shares,
the §3 wedges against NIPA — sales grossing 2024: OTE − NIPA total
expenditures 1,168,098 and OTR − NIPA total receipts 1,179,025 (P1O
1,134,952); B9 − NIPA net lending 10,926 (kickoff §3 expected NLB
unaffected: a small vintage/consolidation wedge, recorded); enterprise
investment 63,582 (NIPA gross government investment − OECD P5) —, the §8.2
bridge on every vintage with the perimeter rule (latest 2026-04: base 2024,
24 overlap years from 2001, mean NLB gap −2.34% of TE, sigma 1.51 → 12
unexplained, V24 WARN; OQ-16) and the reconciliation sources measured for
U2/U5 (IMF GFS COFOG 1972–2024 with GF0170_T 1980–89 only; OECD RS from
1965; AMECO USA E-lines reproducing T12 growth exactly except E09; OECD EO
1960–2027 with SSPG = D62, SSRG = D61, TIND = D2 exactly). Re-run the tool
after any rebuild; never hand-edit the report.

## D-S16-012 — Gate U0 record: what was measured, what is byte-identical, and the exceptions (serves kickoff §12 Gate U0)

**Gate criteria.**
- All 41 USA lines have programmatic coverage from ≥ 1 source or a
  `lines_absent` entry: `ggfiscal coverage` 164/164 lines (USA: 80 (line,
  source) rows — OECD_T11 12, OECD_T12_EXP 9, OECD_T12_REV 11, OECD_T10 5,
  BEA_NIPA 4, EC_AMECO 9, OECD_RS 9, IMF_GFS 18, structural_zero 3);
  `S0_COVERAGE` OK. **Holds.**
- The §8.2 bridge has a USA base-year row on the latest WEO vintage:
  2026-04 base 2024 (also 2025-10 and 2025-04), 24 overlap years from 2001;
  `S0_BRIDGE` OK. **Holds** (V24 WARN on the perimeter sigma — OQ-16).
- `reports/source_verification_USA.md` written (generated, D-S16-011).
- GBR/FRA/DEU byte-identical, run_id excepted: `tools/byte_identity.py
  /tmp/gg_baseline --countries GBR,FRA,DEU --new-file strict_USA.csv
  --new-crosswalk OECD_T12_to_ESA_EXP --new-crosswalk
  OECD_T12_T10_to_ESA_REV --new-scope register/CBO_SITE --new-scope
  register/SSA_TRUSTEES --check-now-scoped V24` → OK: every canonical CSV
  and deliverable equal on the three countries' rows; `exceptions.csv`
  differs only by the two named V18 WARN rows and the V24 OK row the USA's
  scoped WARNs replace; the READMEs only by row counts and the USA lines.
  **Holds.**
- `ggfiscal validate`: **ERROR=0**, WARN=2761, OK=101 (baseline OK=89
  WARN=2298 ERROR=0). The 463 added WARNs are USA-scoped: V1 258 (IMF GFS
  wedges per line-year), V25 196 (OECD RS wedges), V5 4 (extension-source
  overlap diagnostics; 13 OK), V24 3 (one per vintage), plus V18 2 (the
  blocked registers). OK rose by 12: the USA-scoped V5 OK rows (13) less
  the unscoped V24 OK row.
- `python3 -m pytest -q`: 285 passed in the baseline; after U0 **299
  passed, 80 skipped, 33 failed, 21 errors** — the 285 plus the 12 new
  `tests/stage_0/test_u0_usa.py` tests plus the two USA cases of the
  parametrised per-country strict-file tests, and the identical set of 54
  `tests/debt/` failures/errors for absent debt snapshots (OQ-14; the
  debt engine untouched). Pre-U0 tests changed
  to the U0 state: the three-country literals now derive from
  `config.COUNTRIES` / `config.countries_at_stage(n)` (D-S16-008), the
  notebook-tooling test seeds a synthetic JPN, `test_gate1`'s pension-share
  floor is 0.3 for a D26-proxy country, the flat-file ledger identity admits
  the OECD balancing item's USD 0.001 mn rounding, `test_gate6`'s anchor
  types include `structural_zero`, and the two debt tests that iterated the
  fiscal country list iterate `config/debt.yaml` (the USA joins with UD0).
  Final full run 2026-09-21 after the last chain: as stated above.

**Rules held.** No `elif iso3 ==` anywhere (a test greps the package for a
USA literal); every USA routing decision is config or `OecdSnaFamily`;
the readers of GBR/FRA/DEU untouched; `forward.py` and `backward.py`
untouched; no notebook touched; the debt engine untouched.

**Blocked, written up, not weakened.** `www.cbo.gov` and `www.ssa.gov`
(OQ-13; register `blocked`, V18 WARN); the NIPA transportation
gross-investment cell (OQ-15); the WEO perimeter rule for the USA (OQ-16).
None of them is a Gate U0 criterion.

---

# Session 17 (2026-10-07) — Stage E: Italy, Spain and Belgium (`EU3_KICKOFF.md`)

The committee asked for the France/Germany approach to be extended to
Italy, Spain and Belgium, with the debt layer, before the USA's U1, built
from `main`, with Level II before 2001 filled from IMF GFS as for Germany,
and with Spain's debt from the Banco de España. `EU3_KICKOFF.md` records
those answers as DE1–DE6.

## D-S17-001 — ITA, ESP and BEL join `config/countries.yaml` on the Eurostat family; every EU-wide source registers them (serves EU3_KICKOFF.md §1, DE5, DE6)

Three blocks after DEU, `anchor_family: eurostat`, the FRA/DEU anchors and
GDP source, `envelope_forecast: [EC_AMECO, EC_DSM]`, CY throughout, no
structural zeros, no perimeter break, `stage_reached: 6`. The country
order is GBR, FRA, DEU, ITA, ESP, BEL, USA. `EUROSTAT_GOV10A_{EXP,MAIN,
TAXAG}`, `EUROSTAT_NAMA10_GDP`, `IMF_GFS`, `IMF_WEO`, `OECD_RS`,
`OECD_T11`, `EC_AMECO`, `EC_AGEING_2024` and `EC_DSM` list the three
countries; the pulls follow the register (69 new pulls, all 200 on
2026-10-07; `fetch --all` is 187 pulls). DE6: `eurostat_geo` per country
replaces the three `{"FRA": "FR", "DEU": "DE"}` maps
(`ingest/endpoints.py`, `standardise/readers.py` ×2) and the debt
engine's two (`debt/families/eurostat_insee_oecd.py`,
`debt/intermediates.py`); `config.eurostat_geo(s)`.

## D-S17-002 — The Ageing Report and DSM legs apply by registration, not by ISO3 literal (serves DE5)

`forward._registered(iso3, source_id)` reads the register's `countries`;
the four `iso3 in ("FRA", "DEU")` gates of `forecasts_for` (DSM interest
for GF01_7 and E05, the AR legs for GF07/GF09/GF10/GF10_2) and the one in
`coverage.line_sources` (the GF10_2 AR candidate) use it. FRA/DEU outputs
are byte-identical. The remaining FRA/DEU literals in `forward.py` are
declarations about those countries' own national sources (D7 notes),
which stay where they are.

## D-S17-003 — R10 for a country without the D.92/D.99 split: D.39 + D.7 + (D.9 − D.91) (serves parent §4.3 R10)

Spain publishes no `D92REC`/`D99REC` in `gov_10a_main` (the first E0 chain's
only ERROR: `S0_COVERAGE ESP/ESA_REV/R10`). D.92 + D.99 = D.9 − D.91 is an
identity (measured on FRA to 1e-12), so `EurostatFamily._r10_parts` uses
it only where the split is missing, with the note saying so. FRA/DEU/ITA/
BEL keep the published split and an unchanged series.

## D-S17-004 — ESP's D.51 payer split from `gov_10a_taxag`; BEL's main aggregates do not close exactly (serves D-S1-002, parent §4.3 R03/R04)

`gov_10a_main` carries no `D51A_C1REC`/`D51B_C2REC` for Spain; the
tax-detail table does (1995–2024). D-S1-002 chose the main table because
taxag drifts in the freshest years; for Spain taxag D.5 and D.2 equal the
main table's in every common year (max |diff| 0.0%), and lack only the
main table's 2025. `EurostatFamily._d51` falls back to taxag only where
the main table publishes no split; the rows carry
`source_id = EUROSTAT_GOV10A_TAXAG` (a revenue line may now name its own
table as a 4th tuple element). R03/R04/R05 for ESP end in 2024; 2025
waits for Eurostat's next taxag release.
Belgium's `gov_10a_main` TR − TE differs from its own B.9 by up to
EUR 0.8 mn (2024–25, provisional; 2.4e-6 of TE) — inside V23's 0.1%; the
flat-file test now bounds the difference at 1e-5 of TE and keeps exact
closure for every other country.

## D-S17-005 — DE3 measured: no reachable source carries ITA/BEL COFOG Level II before 2001; measured grades and V16 outcomes (serves DE3, D12, §7.8, §9.2)

The generic IMF GFS COFOG leg is enabled for ITA and BEL as for DEU. As for
DEU (whose groups start in 2000), it applies nothing: IMF GFS `GF1020_T` /
`GF1050_T` start in 2001 for both (the IMF redistributes the same national
data), there is no GFS group for 04.5, and OECD Table 11's Level II rows
also start in 2001. GF10_2, GF10_5 and GF04_5 (and their remainders)
therefore start in 2001 for ITA and BEL; GF01_7 has 1995–2000 from the D10
fallback (D.41 payable, B), as DEU's 1995–99. Spain's anchor publishes
Level II from 1995.
Measured on the forward side (2024 coverage at the boundary):
AR health 87.9% of GF07 (ITA, C), 77.1% (BEL, C), 91.2% (ESP, B);
AR education 92.8% (ITA, B), 98.4% (ESP, B), 87.4% (BEL, C);
AR gross pensions 115.8% / 132.3% / 129.5% of COFOG 10.2 (ITA/ESP/BEL,
grade D, not applied — the AWG perimeter includes disability and
survivors' pensions COFOG books in 10.1/10.3);
AMECO UTKG 20.2% of R05 (ITA, D), 51.4% (ESP, C), 52.3% (BEL, C);
the §7.9 GF01-via-GF01_7 proxy measures C for ITA (interest is a larger
share of GF01) and D elsewhere.
V16 withholds every long-term join for the three countries: AMECO vs DSM
interest growth diverges by −0.053 (ITA), +0.062 (ESP), +0.061 (BEL) and
AMECO vs AR on GF10 by +0.021, −0.021, +0.031 — above 0.02, and the
committee's `v16_approved_joins` list names FRA/DEU only. GF01_7/E05 end
at 2027 and GF10 at 2027 in maximum for ITA/ESP/BEL until the committee
rules (OQ-17). The declarations are config (`forecast_declarations` in
countries.yaml), one per line without a strict forecast.

## D-S17-006 — Debt sources for the three countries (serves EU3_KICKOFF.md ED0, DE1, DE4)

New family `debt/families/eu3_offices.py` (registered in
`debt/endpoints.FAMILIES`): MEF composition and maturity CSVs (one part per
monthly edition, read from the listing page at pull time — 2026-01..08 on
2026-10-07; older editions are PDF), BDA OLO lines (HTML), maturity
schedule, indicators and implicit yield (xlsx; point-in-time only), the
Banco de España Boletín zip. `ESP_TESORO` is registered `blocked` (TLS
chain incomplete) and `ITA_MEF_FABBISOGNO` `not_machine_readable`; both
add one V18 WARN. `EUROSTAT_GOV10A_MAIN_S1311` and `EUROSTAT_GOV10DD`
list the three countries. 117 debt pulls of those three families, 0
failures.

## D-S17-007 — The debt layer of the three countries is the DD8 aggregate path; step A is unavailable and says why (serves ED1–ED2, DD8)

`config/debt.yaml` `countries` gains ITA/ESP/BEL with
`aggregates_eu3:{ita,esp,bel}_class_aggregates`,
`intermediates:official_totals_{ita,esp,bel}`, the S1311 sub-sector chain
items and V31 against Eurostat GD_F3 — the FRA pattern. No `register`
(ED3). Aggregates: Eurostat `gov_10q_ggdebt` Q4 S1311 F31/F32/F4/F2 and
the S13 securities cross-check for all three (ITA 2000–2025, ESP
1995–2025, BEL 1995–2025); ESP adds the Banco de España Estado PDE total
at December (1994–2025, `ESP_BDE_BE`); ITA adds the MEF December edition
when one is in the store (none yet). Step A of both chains is a grade-D
null row naming the missing source and the reason (MEF and BDA publish
cash outturns in PDF only; the Tesoro is unreachable). Fixed in passing:
`intermediates.official_totals` iterated every fiscal country, so `ggfiscal
debt build` had raised for the USA since U0; it now iterates the
debt-configured countries plus every stage-6 fiscal country (a packaged
country without a debt entry still raises; the USA at stage 0 is skipped).
V31 for the three compares `gov_10q_ggdebt` Q4 against `gov_10dd_ggd`
GD_F3 — two Eurostat tables of the same data, 0.00% in every year: a
consistency check, not an independent one (the independent stock arrives
with the ED3 registers; ESP's Banco de España Estado total is out of
register by perimeter).

## D-S17-008 — Packaging is gated by stage 6; the three countries are packaged (serves Stage E6, D-S16-008)

`statistical-forecasts` and `benchmark-balance` read only the countries
at `stage_reached` 6, and `tools/update_notebooks_s11.py` seeds books for
those only — the USA (stage 0) had entered the downstream files the first
time they ran after U0. The notebook tool seeded the ITA/ESP/BEL chartbook
sections and forecast books by copy; every notebook executes error-free.
Belgium's GDP agrees across sources in 2025, so its forecast-levels anchor
is the last outturn (2025), not the year before; the tests now admit that
and still require the fork for GBR/FRA/DEU.
Pre-existing, not changed here: the Prophet and ETS interval widths (and
the ensemble's) are simulation-based and unseeded, so `se`/intervals in
`statistical_forecasts.csv`, `forecast_levels.csv` and the benchmarks move
on every run (two runs of the unchanged code differ on the same 2,565
rows; point forecasts identical). Those four files are compared on their
point columns only (D-S17-010).

## D-S17-009 — Debt layer built and gated (serves ED0–ED2)

`ggfiscal debt fetch` (all families): every pull 200 except the three DMO
reports the config lists `not_exportable` (D1D, D5I, D9C — unchanged).
`ggfiscal debt build`: the interest and financing chains run 1995–2025 for
ITA, ESP and BEL (steps A null-D with reasons, B Eurostat S1311, C the
package, S.1312–S.1314 items). Every debt table's GBR/FRA/DEU rows are
identical (run_id excepted) to a same-vintage baseline built by the main
code with only the official_totals iteration fix applied.
`ggfiscal debt validate`: OK=73, WARN=28, SKIP=2 (new countries: V31 OK 43,
V35 OK 6). `tests/debt`: 3 GBR register/bridge tests fail on the
2026-10-07 DMO vintage with the unchanged main code too (not this change);
all other debt tests pass — the 54 snapshot-absent failures of OQ-14 are
gone in a container that has run `ggfiscal debt fetch`.

## D-S17-010 — Gate record, Stage E (EU3_KICKOFF.md §4)

- Fiscal: `ggfiscal validate` ERROR=0, OK=177, WARN=3711 (the new
  countries' WARNs: V1 463, V25 243, V21 28, V16 9, V5 5, V24 2 — IMF GFS
  and OECD RS concept wedges, the withheld V16 joins of OQ-17, Spain's V24
  of OQ-19; plus V18 for the two new blocked/PDF registers).
- `tools/byte_identity.py /tmp/gg_baseline --countries GBR,FRA,DEU,USA
  --new-file strict_{ITA,ESP,BEL}.csv --new-scope register/ESP_TESORO
  --new-scope register/ITA_MEF_FABBISOGNO` → OK on every canonical CSV and
  flat file built by build/reconcile/validate/report/flatten, against a
  baseline built from main on the same 2026-10-07 vintages. The four
  downstream files (statistical_forecasts, forecast_levels,
  benchmark_balance, benchmark_vs_weo) differ from that baseline only by
  the USA rows the stage-6 gate removes and by the unseeded interval
  columns (D-S17-008); every other column of the GBR/FRA/DEU rows is
  identical.
- The committed GBR and USA values move against the previously committed
  files because the 2026-10-07 vintages differ (e.g. UK history revisions,
  BEA 2025 data); that is the fresh harvest, not this change.
- Notebooks: the ITA/ESP/BEL chartbook sections and nine forecast books
  seeded and every notebook executed without error.
- `python3 -m pytest -q` (after `ggfiscal debt fetch`): **473 passed, 6
  skipped, 3 failed** — the 3 are `tests/debt/test_register_gbr.py` (2)
  and `test_bridges.py::test_gbr_step_c_items_shrink_the_residual[financing]`,
  which fail identically on the unchanged main code with the 2026-10-07 DMO
  vintage (not this change; follow-up). Previously 33 failed + 21 errors
  for absent debt snapshots (OQ-14).

## D-S17-011 — The committee approves the DSM interest joins for ITA, ESP and BEL (resolves OQ-17 in part; serves D12, D-S8-001)

2026-10-07: "Approve interest switch." `tolerances.v16_approved_joins` gains
GF01_7 and E05 with `EC_DSM` for ITA, ESP and BEL — the FRA/DEU treatment.
GF01_7 and E05 now run to 2036 in both variants for the three countries;
V16 keeps WARNing on the seam (−0.053 / +0.062 / +0.061). The AR GF10 join
was not part of the approval and stays withheld (GF10 maximum ends 2027).
GBR/FRA/DEU/USA unchanged (byte identity against the pre-change build).

## D-S17-012 — No host is blocked: two Spanish servers omit an intermediate certificate; the other three were wrong or retired addresses (serves DE4, OQ-13 pattern)

Re-tested 2026-10-09 in an environment with full network access.
`www.tesoro.es` and `www.airef.es` present only their leaf certificate,
issued by FNMT-RCM "AC Componentes Informáticos", without that
intermediate — no client can build the chain ("unable to get local issuer
certificate"). The intermediate, downloaded from the URL the certificates
themselves name (`http://www.cert.fnmt.es/certs/ACCOMP.crt`, SHA-256
F0:38:42:1F:07:F2:0D:63:…:76:AB, chaining to the standard root AC RAIZ
FNMT-RCM), is committed as `config/certs/fnmt_ac_componentes_informaticos.pem`;
`ingest.fetch.verify_for` appends it to the normal trust bundle for those
two hosts only. Verification stays on; both return 200.
The other three were the scoping's mistakes, not blocks:
`www.planbureau.be` → the Federal Planning Bureau is `www.plan.be` (200);
`www.upbinfo.it` → the Ufficio parlamentare di bilancio is
`www.upbilancio.it` (200); `stat.nbb.be` is the retired NBB.Stat — the
National Bank of Belgium serves data from `dataexplorer.nbb.be` and
`nsidisseminate-stat.nbb.be` (200). `infostat.bancaditalia.it` still
requires a login (not a network matter).

## D-S17-013 — The committee approves the AR GF10 joins for ITA, ESP and BEL (closes OQ-17)

2026-10-09. Three `v16_approved_joins` rows (`EC_AGEING_2024`, GF10).
GF10 maximum now chains the AMECO D.62 proxy (to 2027) into the AR
pensions+LTC composite to 2070 for the three countries, as for FRA/DEU;
strict still ends at the last actual (the composite is grade C). V16
keeps WARNing on the seam.

## D-S17-014 — Spain's WEO gap is a known perimeter gap (closes OQ-19)

2026-10-09. `weo_perimeter_gap_expected: true` for ESP: the bridge
classifies Spain's GGR/GGX level gap by its stability (the GBR rule)
instead of the 1%-of-TE revision band. On the 2026-04 vintage every year
classifies `perimeter`; V24 no longer WARNs for Spain.

## D-S17-015 — Italy and Belgium's COFOG Level II lines start in 2001 (closes OQ-18)

2026-10-09: the committee accepts the 2001 start for GF10_2, GF10_5,
GF04_5 and their remainders in ITA and BEL; no national back-series is
sought. GF01_7 keeps 1995–2000 from the D.41 fallback.

## D-S17-016 — Belgium's per-security register from the Debt Agency's outstanding page (Stage ED3)

`debt/register_bel.py`, registered in `config/debt.yaml`. Four tables, each
at its own date: 37 OLO lines (net outstanding 01.10.2026, buy-backs in
the Treasury's portfolio as `official_holdings_lcu_mn`; lines sum to the
page total 478,340 EUR mn), 12 Treasury Certificates (30.09.2026, 53,693),
45 EMTN/other ISINs from 55 taps (10.06.2026; EUR equivalent as
published, issue-currency amount alongside; 3 Euribor-6M floaters, 4
inflation-linked, 7 currencies — AUD and NOK added to the debt schema's
currency list). The page's own EMTN rows sum to 12,315.5 EUR mn while its
total line says 12,615.5 — exactly 300 more; the rows are registered.
BE6367588231 is listed with a maturity that moves a day per tap
(16–22/08/2035); the first tap's date is kept and the note says so.
Schuldscheine (no ISIN, loans) stay outside DD1. Positions are
`office_snapshot` only — no auction history file is published — so the
register enters no chain year (`register_sums` needs a 1 January anchor)
and the latest-date maturity profile covers the OLOs.

## D-S17-017 — Spain: the Tesoro's outstanding by instrument enters the aggregates; no per-security register is possible

`ESP_TESORO` (reachable since D-S17-012) adds four pulls from the monthly
bulletin; `readers/tesoro.py` reads "Deuda del Estado en circulación"
(year-ends 2007– and month-ends; components checked against the total)
and `aggregates_eu3.esp_tesoro_rows` publishes every 31 December by
instrument and tenor (Letras by tenor → bill; Bonos y Obligaciones by
tenor → fixed_bullet; index-linked, uplifted; euro-bonds, foreign
currency; "resto", assumed debt and Banco de España loans out of
register). End-2025 total 1,516,859 EUR mn. Neither the bulletin nor the
auction history (2001–) identifies an issue by ISIN (tenor and coupon
only), so a per-security register for Spain stays out of reach.

## D-S17-018 — Housekeeping: seeded forecast intervals, README prose from config, notebook fan cells follow the forecasts

`statistical._ets` passes a fixed `random_state` to the interval
simulation and `_prophet` seeds numpy before fitting: two runs now give
identical intervals (the D-S17-008 caveat no longer applies). The
generated READMEs take their country list from
`config.packaged_countries_prose()` and their line counts from
`config.granular_lines`. `tools/update_notebooks_s11._sync_fans` drops a
line's fan cells when it loses its statistical forecast and adds them when
it gains one.

## D-S17-019 — UK register: operations after the D1A close of business are not part of the opening stub; Italy's register is PDF-only

The three GBR debt tests that failed on the 2026-10 DMO vintage (also on
main): the issuance history (D2.1E) runs ahead of the gilts-in-issue
snapshot (D1A, close of business 2026-10-06) — auctions of GB00BT7HZZ68
(1,250, 2026-10-07) and GB00BMGR2809 (1,000, 2026-10-08) were counted
against the anchor, creating false opening stubs. `_opening_rows` now
compares each anchor only with operations settled on or before its own
date; the test does the same. GBR debt figures for those two gilts change
accordingly. The financing step-C test now requires the bridge items to
narrow the gap in 4 of 5 years and in total: on the current ONS vintage
local-government net borrowing (−2,889) over-explains 2021's −1,188 gap.
Italy: the MEF publishes recent auction results as one PDF per auction and
no per-ISIN outstanding file (archive spreadsheets stop in 2000–2007); per
the OQ-5 rule a PDF-only source is not machine-readable, so no Italian
register is built.

## D-S17-020 — Belgium's R03/R04 from the Federal Planning Bureau's medium-term outlook

The Bureau's "Perspectives économiques 2026-2031" (June 2026) statistical
annex (`BEL_FPB_OUTLOOK`, `www.plan.be`) carries the general-government
account T17 to 2031 on the national-accounts basis, with direct taxes
split households / corporations / other. GDP agrees with Eurostat (2025:
642,012 vs 642,015 EUR mn). `forward._fpb` builds level legs, growth only,
taken by registration (`_registered(iso3, "BEL_FPB_OUTLOOK")`), crosswalk
`crosswalks/BEL_FPB_to_ESA_REV.csv`. Measured at the 2025 boundary: R03
1.026 and R04 1.021 of the anchor — grade B, so both run strict and
maximum to 2031 (they had ended at the last actual). The other T17 rows
(indirect taxes in total, contributions in total, interest, spending
categories) are aggregates that do not map one-to-one onto the remaining
declared lines; they are a candidate for chaining after AMECO on E-lines
and GF01_7 (V16 decides), not used here. The Belgian, Italian and Spanish
declarations no longer call the national forecasters egress-denied
(D-S17-012): they say what was found.

## D-S17-021 — Correction to D-S17-018: the ETS seed goes through `rng`

`ETSResults.get_prediction` passes extra keywords to `simulate`, whose
generator argument is `rng`, not `random_state`; the first version raised
inside the ETS fit for every specification, and the ensemble silently ran
without ETS for 812 of 1,456 series rows. Now
`rng=np.random.default_rng(SEED)`: every method runs and two runs give
identical intervals (checked on additive and multiplicative
specifications).

## D-S17-022 — Gate record, second pass

Full chain (build, reconcile, validate, report, flatten, the four
downstream steps, notebook update and execution, debt build and
validate, flatten) on the committed code: `validate` ERROR=0;
`debt validate` OK=73, WARN=28, SKIP=2; **pytest 480 passed, 6 skipped, 0
failed**. GBR/FRA/DEU/USA against the previous commit: unchanged except
the seeded interval columns, the vintage-set hash and the two UK gilts of
D-S17-019 (all intended).

## D-S17-023 — The chartbook's balance charts cover every packaged country, at print resolution

`balance_path`, `balance_contributions`, `weo_compare_path` and
`weo_compare_split` had `COUNTRIES = ["GBR", "FRA", "DEU"]` and a 1×3 grid
written into their cell, which the notebook tool never rewrites (it only
inserts per-country blocks), so ITA/ESP/BEL were left out. They now take
`COUNTRIES = [c for c in BOOK_ORDER if c in set(BAL.iso3)]` and lay out
three panels a row (six countries: two rows; the side split: four).
`BOOK_ORDER`, the book's section order from config, is written into the
setup cell by `tools/update_notebooks_s11._set_book_order` — the flat files
are sorted by iso3, so the order cannot come from them. `show(fig, dpi=)`
renders these four charts at 220 dpi (2,420 px wide, displayed at 1,056 px)
instead of 72; every other chart is unchanged. The §7.6 and §8 prose now
names all five Eurostat countries.
Found by the new charts, not changed here: Italy's GF06 (housing — the
2021-23 Superbonus credits) has an ETS(M,A,N) member forecasting −24.9% of
GDP by 2031 (se 82) and an ARIMA member reaching −3.0%; the ensemble's
between-model variance then gives Italy's benchmark balance a ±84 pp 95%
interval in 2031. Inadmissible for a non-negative line; the remedy is a
committee choice (OQ-20).

## D-S17-024 — Ensemble admission by calibration ratio (closes OQ-20)

Committee 2026-10-10: the problem is width, not sign — a forecast error far
wider than the series has ever moved means the model is misspecified. For
each member, the calibration ratio = standard error at the horizon h / the
standard deviation of the series' own h-year changes over the fit window.
Measured over the 900 member-series pairs of the 2026-10 run: median 0.97,
95th percentile 1.99, 99th 3.41, 99.5th 4.41; ITA GF06 ETS(M,A,N) 75.9
(next 7.3). Rule (`statistical.MAX_CALIBRATION_RATIO = 5`,
`MIN_MEMBERS = 2`): a member above 5 stays in `statistical_forecasts.csv`
but leaves the combination, worst first, never below two members; the
combination's `model` label names it with its ratio. On that run four
members qualify: ITA GF06 ets, GBR GF01_X uc, ITA R06_X uc, GBR R10 uc.
Not addressed here (a separate question): ITA GF06's remaining members
still read the 2021–23 Superbonus spike into the level (2.1% of GDP in 2031
against 0.4% before 2020 and 0.8% in 2024).
Gate (2026-10-10): full regeneration on the committed code; the existing
countries' outputs differ from the previous commit only in the two UK
combinations the rule changes (13 rows) and what derives from them —
every other value reproduces exactly (seeded intervals). pytest: 486 passed
+ the updated combination test = 487 passed, 6 skipped, 0 failed; the
forecast books' method table describes the admission rule.

## D-S17-025 — Amendment to D-S17-024: no two-member floor; forward fill when no member qualifies

Committee 2026-10-10: every member with a calibration ratio above 5 is
skipped from the combination, however many that leaves. If none qualifies,
the combination forward-fills the line's last observed % of GDP; its
standard error at horizon k is the standard deviation of the history's own
k-year changes (the yardstick the ratio already uses), so a line with no
admissible model is not presented as certain. The label reads "forward
fill of the last observation; no admissible member (excluded …)".
On the 2026-10 vintage no series reaches the fallback and the floor never
bound (each of the four affected series keeps three members), so the
published values are unchanged by this amendment.
Gate (D-S17-025): full regeneration byte-identical for all seven countries against the previous commit; pytest 487 passed, 6 skipped, 0 failed.

## D-S18-001 — The AFT briefing's scenarios revised: five configurations, declared spread and fiscal paths, history from 2010 (amends D-S12-001)

Committee 2026-10-11. The scenario section of `reports/briefing_FRA_AFT_2026-09/`
is rebuilt on the latest fiscal announcements, assuming slippage against
what each camp promises.

**Scenarios.** Five, replacing D-S12-001's six (the "current path" and the
"rupture" stress are dropped): Philippe majority, Philippe hung Assembly (the
status quo and the new `REFERENCE` for `decompose_gap`), Le Pen majority,
Le Pen hung, Mélenchon.

| Scenario | 10y spread 2027 → 2029 on, bp | Primary balance 2028–2031, EUR bn a year | From 2032 | Real growth |
|---|---|---|---|---|
| Philippe, majority | 150 → 125 | +10 | +5 | 1.0% |
| Philippe, hung | 175 → 150 | +2 | +5 | 0.5% |
| Le Pen, majority | 190 → 125 | +25 | +5 | 0.0% |
| Le Pen, hung | 175 → 125 | +15 | +5 | 0.5% |
| Mélenchon | 250 → 300 | −10 | +5 | 0.0% |

**Rules.**
1. The spread is an annual average declared outright: the 2027 level, a
   straight line to the 2029 level (2028 is the midpoint), flat to 2035. The
   rest of 2026 is financed at 135 bp in every scenario (Bloomberg spot,
   11 Oct 2026; the bundle's OECD monthly series ends at about 100 bp in
   September 2026). The debt-ratio feedback is set to zero.
2. The 10-year Bund is 3.50% flat through the horizon; the rest of the curve
   moves with it by 10 bp (2y 3.00, 5y 3.25, 30y 3.85), the 3-month stays at
   2.50%.
3. The primary balance is common to 2027 (−2.7% of GDP in 2026, −2.5% in
   2027: the 2027 budget is voted before the election). From 2028 it is the
   previous year's balance in EUR bn plus the declared change, as an outturn:
   growth acts on the ratios through nominal GDP only.
4. Nominal GDP is common to 2027 (EC AMECO), then grows at the scenario's
   real growth times a 2% deflator.
5. The issuance mix (the AFT's 2025 tenors) and the bill stock (EUR 215bn)
   are the same in every scenario; the Le Pen bill and tenor tilts of
   D-S12-001 are removed.
6. Every history line in the scenario charts starts in 2010. The debt chart's
   history is Maastricht debt, S13, % of GDP, from Eurostat
   `gov_10dd_edpt1`, hand-keyed under `data/manual/FRA_maastricht_debt_pct_gdp.csv`
   (retrieved 11 Oct 2026; 2025 = 115.6, matching INSEE). The bundle has no
   clean S13 series: `debt_class_aggregates` carries S13 securities but S1311
   loans and deposits.

**External facts added to the note** (ext): the RN counter-budget of 6 October
2026 (EUR 140bn of net savings by 2032 against 2026, deficit below 3% in 2030,
debt 121% → 112% of GDP 2027–2032; franceinfo, Public Sénat); Odoxa-Mascaret
for Public Sénat, 20–21 May 2026 (Bardella 32, Philippe 17, Mélenchon 16);
Midi Libre, 8 Oct 2026.

**Results (2035).** Debt: Le Pen majority 130.0%, Philippe majority 130.9%,
Le Pen hung 132.5%, status quo 143.5%, Mélenchon 166.1%; none stabilises.
Interest: 4.8–4.9% of GDP in the first three, 5.6% in the status quo, 7.8%
under Mélenchon.

**Not regenerated.** The descriptive charts and `key_figures.csv` (sections
1–4) and the executed `notebooks/briefing_FRA_AFT.ipynb` were left at the
D-S12-001 run: re-rendering them against the current bundle (run
20261010) moves numbers outside this change (e.g. 2029 term redemptions
8.6% → 10.8% of the stock). `tools/make_briefing_notebook.py` is updated
for the new scenario fields, so the next full regeneration is consistent.

Gate (2026-10-11): `tests/debt/test_simulate.py` 13 passed (new: five
scenarios and the reference, declared spread levels and Bund 3.5%, primary
balance moves by the declared euros, ordering, status quo within a fifth of
the EC DSM path). Full suite on a clean worktree identical before and after
this change (68 failed, 29 errors, all pre-existing and unrelated; +3 passed).

## D-S18-002 — The statistical benchmark restored to the AFT briefing as a sixth path (amends D-S18-001)

Committee 2026-10-11, after D-S18-001 dropped D-S12-001's "current path".
That path was not statistics-based: it was a declared 0.4 pp-of-GDP-a-year
consolidation with the spread easing from 85 to 70 bp. The committee asked
for the statistics-based forecast, which is the benchmark balance
(`benchmark_balance.csv`, D-S11-002), so that is what returns.

1. **Primary balance.** Benchmark NLB + benchmark `GF01_7` interest − 0.2% of
   GDP interest receivable. The benchmark is anchored on 2024 and does not see
   the 2025 outturn (NLB −5.7% against the actual −5.1%), so its level is not
   used: only its year-on-year changes, 2028–2031 (+0.17, +0.18, +0.06,
   +0.06 pp), applied in pp of GDP from the common 2027 starting point. After
   2031, where the benchmark ends, the primary balance is held constant as a
   share of GDP (`simulate.benchmark_pb_changes`, `Scenario.pb_change_pp`).
2. **Spread and growth** as Philippe, hung Assembly (175 → 150 bp, 0.5% real).
3. **Style.** Dotted grey on every scenario chart, drawn above the status quo
   it shadows. The status quo (Philippe, hung) moves from black to solid
   orange; the EC AMECO/DSM line in Figure 8, previously dotted grey, becomes a
   brown dash-dot so the two cannot be confused.
4. Philippe, hung stays the reference for `decompose_gap`.
5. **Assumptions as tables.** Section 5 of the note now carries four tables:
   the scenario assumptions (six rows), the assumptions common to every
   scenario, the statistical benchmark year by year, and the RN counter-budget
   against the Le Pen-majority path.

**Result.** The benchmark sits on the status quo to 2031 (debt 130.4% vs
130.6%, interest within €1bn in 2030), then drifts above it as the
status quo keeps consolidating by €5bn a year and the benchmark does not:
debt 145.3% and interest 5.6% of GDP in 2035.

Gate (2026-10-11): `tests/debt/test_simulate.py` 14 passed (new: the
benchmark's changes are applied exactly, the ratio is flat after 2031, the
spread and growth equal the status quo's).

## D-S18-003 — The France fiscal brief notebook: the briefing note reproduced from the flat files, full refresh

Committee 2026-10-11: a new notebook, `notebooks/France_fiscal_brief_20261013.ipynb`,
from which `reports/briefing_FRA_AFT_2026-09/briefing_inline.html` can be
reproduced, on a full refresh of every chart. All the charts and the analysis stay;
the questions for the AFT go.

1. **What the notebook does.** It renders every chart (`briefing_fra_scenarios`,
   then `briefing_fra`). It shows each section of the note in order, using
   `ggfiscal.report.france_brief`: text and tables as HTML, the 18 charts as
   images quantised for GitHub (D-S9-004), and the loop diagram as SVG. The
   key-figure tiles become a table. Section 7 and the "To ask the AFT" boxes
   are dropped. The last cell runs the HTML builder and checks that all 18
   charts are embedded. Re-running it reproduces `briefing_inline.html` byte
   for byte (checked against a separate rebuild). Generator:
   `tools/make_france_brief_notebook.py`.
2. **Builder split.** `tools/build_briefing_fra.py` now exposes `template()`,
   `values()` and `fill()`, and `main()` uses them. The output was
   byte-identical before and after the split.
3. **Full refresh.** The descriptive charts and `key_figures.csv` are
   re-rendered on the current bundle. The only value changes are the new
   OECD months: the 2026 spread average is 74.9 bp, not 68.7; the latest
   month is September at 100.8 bp, not July at 78.0; earlier annual averages
   moved by 0.2–0.6 bp. There are also two consequences of D-S18-001: 2029
   redemptions are 8.53% of the stock, not 8.57%, and 2030 is 6.06%, not 6.13%.
4. **Fix.** `briefing_fra._refinancing_by_year` took its forward stock from the
   "current" scenario in `scenarios_FRA.csv`. Once D-S18-001 removed that
   scenario, it silently held the stock flat, which would have shown 2029
   redemptions at 10.8% of the stock. It now runs the reference scenario
   (status quo) directly, so it no longer depends on rendering order. A
   chart typo is also fixed: "détte" → "dette".
5. `notebooks/briefing_FRA_AFT.ipynb` is regenerated and re-executed on the
   same refresh.

Gate (2026-10-11): `tests/debt/test_france_brief.py` (new, 3) and
`tests/debt/test_simulate.py` (14) pass. The notebook executes in about 15 s
with no errors.

## D-S18-004 — Briefing charts: one colour per candidate, dotted for a hung Assembly, higher resolution, and the scenario tree

Committee 2026-10-11.

1. **Colours.** Philippe is yellow `#D4A200`, Le Pen is French blue `#0055A4` and
   Mélenchon is dark red `#A51E22`. A majority is a solid line and a hung
   Assembly a dotted one. The statistical benchmark is solid grey `#8A8A85`.
   History and outturn lines are near-black ink, so none of them reads as Le
   Pen's blue. The EC DSM path stays a thin brown dash-dot.
   - The three party hues pass the dataviz validator against the chart surface:
     lightness band, chroma, colour-blind and normal-vision separation (all
     pairs, ΔE ≥ 20.9). The dark red was stepped up from `#8B1A1A`, which fell
     below the lightness band.
   - The yellow is below 3:1 contrast. As relief, every chart has a legend, and
     the end labels on the debt and interest charts are in ink and name their
     scenario.
   - Dotted lines are drawn heavier and on top. Where Philippe hung and the
     benchmark share a path (the spread chart), the grey shows through the dots.
   - In Figure 9 the "volume" component changes from blue to teal, so no bar
     carries a party hue.
2. **Resolution.** Every briefing chart is saved at 220 dpi instead of 120.
   The notebooks show charts at 1,200 px with 96 colours instead of 880 px with
   48. `briefing_inline.html` grows from 1.9 to 4.3 MB.
3. **The scenario tree** (`scen_tree.png`, `briefing_fra_scenarios.chart_tree`,
   section 5 of the note and the notebook).
   - The tree runs from the election to the president to the Assembly outcome
     (Mélenchon is one case).
   - Each branch carries its three assumptions: the primary-balance change in
     EUR bn a year (2028–31 and after), the 10y spread from 2027 to 2029, and
     real growth.
   - The statistical benchmark sits below as the no-politics reference.
   - Every value is read from `sim.SCENARIOS` and the benchmark run, so the
     tree cannot drift from the engine.

Gate (2026-10-11): `tests/debt/test_simulate.py` and
`tests/debt/test_france_brief.py` pass (17). Both notebooks are re-executed,
and the HTML the France brief notebook writes is byte-identical to a separate
build.

## D-S18-005 — Hardening the France scenario engine: four arithmetic defects fixed, the loop measured, the feedback stated (amends D-S18-001)

Session 18, 2026-10-12, a line-by-line audit of `ggfiscal.debt.simulate`
and of the chain that feeds it (`forecast.statistical` → `forecast.balance`
→ `simulate`). The scenario definitions of D-S18-001/002 are unchanged; what
changed is the engine's bookkeeping. Every identity the engine is now held
to is listed in its module docstring and checked by
`tests/debt/test_simulate.py`.

**Defects fixed in `simulate.py`.**

1. *Bridge-year double count.* 2026's deficit was the primary balance plus
   the EC AMECO interest bill (77.66) PLUS the half-year interest on the
   issuance of the rest of 2026 — which the AMECO bill already contains.
   2.5 EUR bn too much in the 2026 deficit, carried in the debt of every
   later year; the deficit also failed the identity
   deficit = −PB + interest − receivable in that year. The bridge year now
   takes the AMECO bill as the whole year's interest and finances
   0.90 × deficit × (days after the snapshot / 365).
2. *Uplift financed twice.* Net issuance was 0.90 × the deficit, the deficit
   contains the indexation uplift accrued on linkers (D.41), and the stock
   also grew by that uplift through the indexed nominal — so the negotiable
   stock rose by the uplift twice (about 6 EUR bn a year of issuance that
   is never made: the uplift is paid at redemption, not issued against; in
   ESA it is a reinvestment in F.32, so the 0.90 calibration already holds
   it). Gross MLT issuance is now redemptions + 0.90 × deficit − uplift
   accrual − Δbills, and Δ(negotiable stock) = 0.90 × deficit from 2027.
3. *GDP level seam.* 2025 was the ledger's Eurostat level (2,979.1) and 2026
   AMECO's level (3,055.8); AMECO's own 2025 is 2,991.1, so the 0.4% between
   the two 2025s was booked as 2026 growth and every debt ratio from 2026 was
   about 0.4 pp too low. The engine now chains AMECO's growth rates on the
   ledger level (D-S4-002, as `forecast.levels` does): 2026 3,043.6,
   2027 3,138.1. `Baseline.gdp` holds the level, `Baseline.gdp_ameco` the
   AMECO path the growth is read from.
4. *Wedge basis.* The GF01_7 − register wedge (0.34% of GDP) was the register's
   CASH 2025 total against an accrual roll. On the roll's own concept
   (coupon pro rata + uplift accrued + bill discount accreted) the 2025 wedge
   is 65.2 − 55.8 = 9.5 EUR bn = 0.32% of GDP, which is now the declared
   value. `calibration()` reports the three bases side by side.

**Also fixed.** `interest.py`: `premium_discount_amortisation` ran on bills,
so on the accrued basis every bill's issue discount was counted twice
(accreted by §7.5 and amortised by §7.7 — e.g. BTF 2 Dec 2026: discount
298.4, amortisation −298.4, total 596.8). Bills are excluded; the accrued
totals in `debt_interest_by_security.csv` are overstated by the bill
discount (4.0 EUR bn in 2026 for France) until `ggfiscal debt build` is
re-run. The register's accrued wedge (0.29%) is therefore not used.
`linker_share_of_mlt` (declared, never read) is removed; the dead
expression in `duration_table` is removed; `duration_summary` reads GDP
from `gdp_path`.

**Measured, not changed.**

- The roll's fixed-coupon accrual reproduces the register's own accrued
  coupon exactly for the 24 bonds not reopened in 2026 (13.28 vs 13.28 EUR
  bn); linkers differ by 0.2 EUR bn from the declared 2% inflation against
  the realised index ratios.
- The "interaction" of `decompose_gap` is the price × volume cross-effect,
  not the loop. The loop proper — the interest the extra interest costs
  once refinanced — is now measured by `loop_size` (the scenario re-run with
  issuance sized on the status quo's interest bill): Mélenchon 1.6 EUR bn
  in 2030 and 15 EUR bn in 2035 (19% of the gap), against an interaction of
  0.7 and 4.9. The briefing template and `tools/build_briefing_fra.py` now
  say and fill this; `render_all` writes `scenario_loop.csv`.
- What feeds back: interest → deficit → issuance → interest only. The
  spread path, real growth and the primary-balance changes are declared and
  do not respond to the debt ratio, to each other or to the bill. With the
  primary balance declared in EUR, weaker growth does not cut revenue: a
  budget semi-elasticity of 0.6 against 0.8% potential growth would move
  2035 debt from 129.7 to 147.2% in Le Pen majority (0% growth), 130.7 to
  126.6% in Philippe majority (1%), 143.4 to 149.8% in the status quo, and
  would reorder the five. Left as declared (D-S18-001 rule 3), recorded as
  the engine's largest modelling caveat.
- Holding the wedge at a share of GDP is within 0.1 EUR bn of letting it
  grow with the non-negotiable debt (the 10% of each deficit the État does
  not issue against): both grow at about 2.5–3% a year.
- The primary balance of 2026–2027 (−2.7, −2.5% of GDP) cannot be verified
  from the bundle: the strict file has no NLB forecast and the AMECO
  snapshot is not committed. It is consistent with the Commission's 5.1%
  deficit for 2026 that the note quotes.
- Up the chain: the benchmark's line sets add to TE and TR exactly in
  history and GF01/GF10 split exactly; (ΣR − ΣE) − NLB ≤ 0.03 pp except
  GBR (0.36, perimeter). The trees carry one GDP per source, so `pct_gdp`
  across lines in a forecast year sit on different denominators (FRA 2025:
  2,979 Eurostat for GF01_7, 2,991 Eurostat for the revenue lines, 3,028
  Ageing Report for GF07/GF09/GF10_2; ≈0.1–0.2 pp on the benchmark NLB);
  the strict matrix's GDP column from 2025 is whichever source comes first.

**Results (2035, old → new).** Interest % of GDP: Philippe majority
4.88 → 4.80, status quo 5.55 → 5.47, Le Pen majority 4.84 → 4.76, Le Pen
hung 4.95 → 4.87, Mélenchon 7.84 → 7.75, benchmark 5.61 → 5.53. Debt:
within ±0.2 pp of D-S18-001 (the 0.4 pp seam and the 0.1 pp less interest
offset). 2026 deficit 5.12 → 5.05%, debt 117.8 → 118.2%. Gross issuance
about 8–11 EUR bn a year lower. Ordering unchanged; "none stabilises"
unchanged.

**Regenerated** (2026-10-12, second commit): every chart under
`reports/briefing_FRA_AFT_2026-09/figures/` (`briefing_fra_scenarios`, then
`briefing_fra`), `key_figures.csv` (the 2027–2030 redemptions as a share of
the stock move by 0.01–0.05 pp with the smaller forward stock),
`scenarios_FRA.csv`, `scenario_decomposition.csv`, the new
`scenario_loop.csv`, `briefing.html`, `briefing_inline.html`, and both
notebooks re-executed. The HTML the France brief notebook writes is
byte-identical to a rebuild from the figures on disk. Note for the next
refresh: the descriptive charts' bytes depend on whether
`briefing_fra_scenarios` was imported first in the same process (its
`rcParams.update` at import is inherited), so run them as the notebook does,
in one process, or accept a byte-level difference in those PNGs.
**Not regenerated:** `debt_interest_by_security.csv` and the files derived
from it keep the bill double count until `ggfiscal debt build`.

Gate (2026-10-12): `tests/debt/test_simulate.py` 21 passed (new: the
deficit identity in every year, the financing identities, GDP chaining,
loop size, wedge basis); `tests/debt/test_engines.py` and
`tests/debt/test_france_brief.py` pass.

### D-S18-005, addendum (2026-10-12, same day): the debt layer rebuilt where the bundle allows, the wedge moved to the register's accrued basis

1. **Rebuilt.** `debt_interest_by_security.csv` from the committed canonical
   register (securities, positions, flows, index ratios, reference series)
   with `interest.py` fixed: 34,048 rows, the same keys; only bill rows on
   the accrued basis change (FRA −43.4, GBR −26.0, DEU −20.0 EUR/GBP bn over
   all years; no bond row moves). France's accrued total: 2025 56.6 → 51.8,
   2026 66.2 → 62.2. The full `ggfiscal debt build` cannot run in this
   container (the ONS, ECB/Bundesbank, Eurostat and MEF snapshots are not
   committed), so the interest chain was not rebuilt from scratch: the only
   rows it takes from the register are the register-step sums, and only the
   UK's chain is on the accrued basis, so its `sum_bill`, the register
   `official_total`, and step A's `carried_from_previous_step` and `residual`
   were recomputed for 2000–2027 (112 rows, new run_id; the step identities
   hold as before). France, Germany and Belgium chain on the cash basis and
   are unchanged. `ggfiscal debt validate` raises KeyError 'variant' in V35
   (`intermediates.package_nlb`) on inputs this work does not touch;
   recorded, not fixed.
2. **Linkers checked, not a bug.** The auction prices in `debt_flows` are
   real clean prices (OAT€i 0.10% 2053 at 56.3, OAT€i 1.80% 2040 at 100.1),
   so the premium/discount amortisation on linkers is in real terms, as it
   should be; the index-ratio scaling to nominal is a refinement left open.
3. **Wedge, third and last basis.** With the bill double count gone the
   register's accrued D.41 for 2025 is 51.8 EUR bn, and the chain shows what
   the wedge to GF01_7 is made of: S.1311 D.41 53.5 (Eurostat), local
   government 7.4, social security 5.9, consolidation −1.6, GF01_7 65.2. So
   GF01_7 − register = 13.4 EUR bn = 0.45% of GDP, of which 11.7 is the
   S.13 − S.1311 wedge and 1.7 the register's shortfall to the État's D.41.
   The roll now carries the one D.41 component it lacked — the straight-line
   amortisation of premiums and discounts on the lines in the stock, from the
   register's 2026 figures line by line to maturity (+1.3 EUR bn a year in
   2026–27, almost all on linkers, running to −0.5 by 2035 as discount lines
   mature) — and `gg_wedge_pct` is 0.45. Check against the strict matrix:
   the register at the snapshot plus this wedge gives 75.9 for 2026 against
   AMECO's 77.7 (the snapshot lacks the last quarter's issuance); the two
   earlier bases gave 73.5 and 74.1.
4. **Results (2035, D-S18-005 first pass → now).** Interest % of GDP: status
   quo 5.47 → 5.67, Philippe majority 4.80 → 4.99, Le Pen majority
   4.76 → 4.96, Le Pen hung 4.87 → 5.07, Mélenchon 7.75 → 7.96, benchmark
   5.53 → 5.73. Debt: +1.1–1.4 pp (status quo 144.6, Le Pen majority 131.0,
   Mélenchon 167.3). The 2027 bill is 2.8 EUR bn higher in every scenario.
   Against D-S18-001 the net change is therefore +0.1 pp of GDP of interest
   and +1 pp of debt by 2035; ordering unchanged.
5. The briefing template reads the wedge and its S.13 − S.1311 part from the
   engine and the chain (`{{wedge_pct_gdp}}`, `{{cal_wedge}}`,
   `{{cal_wedge_s13}}`); Figure 8's caption reads it from `BASELINE`. Figures,
   HTML and both notebooks regenerated.

Gate: `tests/debt/test_simulate.py` 18, `test_engines.py` 10,
`test_france_brief.py` 3 pass; the wedge test now asserts the accrued basis
and the line-by-line amortisation carry.

## D-S18-006 — Constant maturity profile as the issuance rule; linker timing anchored on the snapshot date; the engine validates its inputs (amends D-S18-001 rule 5, D-S18-005)

Committee 2026-10-12, with the independent review of the engine handed over
the same day (audit of commit 92ef962; `BUG_REPORT.md`, eight probes).

**1. Issuance rule.** D-S18-001 rule 5 (the AFT's 2025 issuance shares every
year, bills at 215 EUR bn) is replaced as the default by a constant
maturity profile: the share of the negotiable stock in bills and in each
DD7 residual-maturity bucket is held at the stock's own profile, and each
year the AFT is assumed to issue into bills and into every bucket exactly
what restores its share after a year of ageing and the year's redemptions.
Tranches are issued at the AFT's 2025 residual maturity at issue for the
bucket (`tranche_years`: whole years, so that at the year end the tranche
sits in its bucket). A bucket already above its share receives nothing —
buybacks are not modelled — and the shortfall is reported
(`profile_deviation_bn`). The profile is measured at the year end the roll
starts from (`Baseline.profile_as_of = 2026-12-31`, the snapshot stock seen
from that date): the engine books by calendar year, so the 0–1 bucket at a
year end holds a whole year of maturities, which the mid-September snapshot
does not (5.8% against 7.4%); anchored on the snapshot date the overshoot
in the two shortest buckets is twice as large (130–240 EUR bn against
62–110) and the stock's average maturity drifts. Weights (end-2026 view):
bills 7.6%, 0–1 7.4, 1–2 8.7, 2–3 10.4, 3–5 14.6, 5–7 10.7, 7–10 14.7,
10–15 9.2, 15–20 4.9, 20–30 9.7, 30+ 2.2. `Baseline.issuance_rule =
"constant_mix"` restores rule 5 exactly (bills 215, the 2025 shares, the
same closed-form fixed point). Within-year interest on the new issuance,
the bill interest and the deficit are solved jointly by iteration under
both rules.

**2. Linkers.** The index ratio at the snapshot grows at the declared
inflation from the snapshot DATE (`index_factor`: (1+π)^(days/365.25)).
Opening index of a year = index(1 January); uplift accrued = nominal ×
(index(stop) − index(start)) where stop is 31 December or the maturity;
coupon pro rata on the geometric mean of the two indexed nominals;
redemption at nominal × index(maturity); closing stock at nominal ×
index(31 December). The first version advanced the September ratio by a
whole year for 2027 (1.4% too much index on 315 EUR bn), redeemed maturing
linkers without their maturity-year uplift, and closed the stock at the
opening index; the stock identity then held only to 0.6 EUR bn a year
(cumulative 1.6 by 2035) and was tested with that tolerance. It now holds
to 1e-13 and is tested at 1e-8. Effect on the results: under 0.1 EUR bn of
interest a year (the review's F1/F2; the "1.57 bn" was a bookkeeping
residual, not a bias in the debt).

**3. Validation and API** (review F3–F6). `validate_register` runs on every
register the engine is given: one row per security, supported classes
only (bill, fixed_bullet, inflation_linked — `link_mask = ~fixed` no longer
turns an unknown class into a linker), dated maturities after the
snapshot, finite positive nominals, a finite coupon on every bond (a
fixed bond's unknown coupon is no longer read as zero), a finite positive
index ratio on every linker (no longer dropped from the sums by NaN
arithmetic). `load_register` rejects duplicate metadata, duplicate
positions, positions without metadata and negative positions
(one-to-one checked merge). A negative gross requirement raises
`FinancingSurplus` (a ValueError) instead of clipping issuance to zero and
losing the residual: buybacks and cash balances are out of scope.
`run_all` runs any subset in the order requested and resolves the status
quo itself only when the spread feedback is live.

**4. Review of the review.** Agreed and done: F1, F2 (with the snapshot
anchoring they asked for; their probes' hard-coded 102.0 opening index is
replaced by the derived index, as they allowed), F3 (reject), F4, F5, F6.
Their perimeter note (AFT stock changes give 0.909 against the 0.904
used: +0.9 EUR bn of 2035 interest) is recorded, not adopted. Two of their
statements were already superseded at the audited commit's successor
(be1c1e2): the wedge is 0.45% of GDP on the register's accrued basis with
the premium amortisation carried line by line, not 0.32%. Their isolated
linker probe also assumed no 2026 financing while declaring a 2026
interest bill of 2 EUR bn; the ported test sets the bill to the
post-snapshot uplift so the bridge year is clean. What the review did not
reach: the issuance rule (this decision's point 1), which moves the
results an order of magnitude more than F1–F6 together.

**5. Results (2035, D-S18-005 addendum → now; the linker fixes alone move
interest by ≤ 0.1 EUR bn, the rest is the rule).** Interest, EUR bn:
status quo 216.8 → 209.9 (5.67 → 5.49% of GDP), Philippe majority
198.8 → 193.1, Le Pen majority 182.2 → 177.0, Le Pen hung 193.6 → 187.9,
Mélenchon 292.6 → 280.4, benchmark 219.0 → 212.0. Debt/GDP: status quo
144.6 → 143.7, Mélenchon 167.3 → 165.7, Le Pen majority 131.0 → 130.2.
Gross MLT issuance 2030: 430 → 470 (status quo; the bill stock now grows
with the stock, 215 → 275 EUR bn in 2030 and 355 in 2035, and the
issuance is shorter: 8.4–10.4 years at issue against 10.6). 2026 and
2027 are within 1 EUR bn. Ordering unchanged; `decompose_gap` and
`loop_size` move in proportion (Mélenchon 2035 loop 14.7 → 13.0). Stock
residual 2027+: 0.58 EUR bn max → 4e-13.

**Regenerated.** Figures, `scenarios_FRA.csv` (new columns:
issuance_rule, bill_share_of_stock, profile_deviation_bn,
linker_index_factor, profile_* by bucket), `scenario_decomposition.csv`,
`scenario_loop.csv`, `key_figures.csv`, both HTML files and both
notebooks; the template's assumption tables and section 5 describe the
rule and the status quo's overshoot.

Gate: `tests/debt/test_simulate_review.py` (new, 14),
`tests/debt/test_simulate.py` (18), `test_france_brief.py` (3),
`test_engines.py` (10) pass.


## D-S19-001 — The other side of the balance sheet in the France brief: cash, net debt, stock-flow adjustments and a sell-down ladder (serves the France fiscal brief; adds a declared SFA to the engine of D-S12-001)

Committee 2026-10-12. The question put: if the French government accounted
for the income its assets pay, how would the sustainability assessment
change, and what could it sell down — on the balance sheet and off it (the
Caisse des dépôts, the public enterprises, the gold) — in an extreme stress?
Be as generous to France as the official numbers allow.

**1. Data.** The general-government financial balance sheet (Eurostat
gov_10a_ggfa: S13 consolidated and S1311/S1313/S1314, assets and
liabilities by ESA instrument, market value, 1998–2025, updated
2026-07-21), the property-income flows (gov_10a_main D41PAY/D41REC/D42REC/
D45REC), the non-financial balance sheet (nama_10_nfa_bs, 2026-09-28) and
the Maastricht levels by sub-sector (gov_10dd_edpt1) are retrieved on
2026-10-12 into `data/manual/FRA_balance_sheet_eurostat.csv` (long, one
row per dataset-sector-finpos-item-year, with the Eurostat `updated` stamp
and the retrieval date), the same shape as the debt history of D-S18-001.
Raw JSON-stat is not kept: the API answers one sector-finpos per call and
the file is the pull. INSEE's net-debt release (end-2025: gross 3,460.5,
net 3,245.5 EUR bn, 108.4% of GDP, by sub-sector), the État's own accounts
(Compte général de l'État 2025: bilan, trésorerie active 22.9 EUR bn,
participations 394.5, engagements hors bilan 1,428 of pensions at 2.21%,
guarantees), the APE portfolio (209.1 EUR bn at 30 June 2025, listed 67.9),
the Caisse des dépôts' own funds (76 EUR bn) and the Banque de France's
gold (2,436.8 t, 257 EUR bn book) are declared external facts in
`balance_sheet.py` (INSEE_2025, CGE_2025, APE_2025H1, CDC_2025,
BDF_GOLD_2025, EXTERNAL) and marked ext in the brief.

**2. Net debt rebuilt, not keyed.** Net debt on INSEE's definition (gross
less F.2, F.3, F.4 held) is computed from the Eurostat tables: 3,244.5 EUR
bn at end-2025 against INSEE's 3,245.5, 108.5% against 108.4%
(`insee_check`, tested to 5 EUR bn). A second measure, net of the equity
book at market (F.5), is shown for the generous case (82.6%). The
stock-flow adjustment history is Δ(Maastricht debt) + NLB from the levels
and the strict ledger (1999–2025 mean +0.21% of GDP; 2020 +69 EUR bn,
2024 +34); its 2021–2025 S.1311 components are read from the financing
chain (`debt_financing_reconciliation.csv` step B, sign flipped back).

**3. The engine carries a declared stock-flow adjustment.** `Scenario.sfa_bn`
(EUR bn by year, zero unless declared) enters the Maastricht stock and the
negotiable stock in full — the État sells, the État issues less — not
through the 0.90 deficit share: debt_t = debt_{t−1} + deficit_t + sfa_t,
Δ negotiable = 0.90 × deficit + sfa, MLT gross = redemptions + 0.90 ×
deficit + sfa − uplift − Δbills. The six committee scenarios declare none,
so no number in sections 1–6 moves (`scenarios_FRA.csv` gains an `sfa_bn`
column, all zero). `test_simulate.py` identities carry the term; a new
test sells 40 EUR bn in 2028 and 2029 and checks the stock, the primary
balance and the interest.

**4. The asset block and the net view (`balance_sheet.net_view`).** Liquid
assets (216 EUR bn) held flat in euros; equity (774) grows with nominal
GDP; each earns the yield its 2025 income implied (1.8% and 1.3%); a sale
removes the stock and, from the half-year of sale, its income, which comes
off the primary balance (dividends and interest receivable are revenue);
the proceeds retire debt through the SFA; spreads are the scenario's own.
Net interest = GG interest − asset income; net debt = gross − liquid; net
financial debt also − equity; the primary balance before asset income is
reported. The engine's fixed 0.2%-of-GDP interest receivable is left as
is (the net view measures the asset income separately; the two overlap by
the interest-receivable share and the brief says so).

**5. The ladder (`LADDER`, declared).** Nine rungs with end-2025 stock,
where it sits, liquidity, asset class and the amount four runs count:
cash above a 30 EUR bn floor (45), paper (36), loans (0/50/105), listed
equity (0/68 ext), fund shares (0/80/161), unlisted at own funds
(0/100/545), CDC own funds (extreme only, 40), gold (extreme only, 128),
non-financial assets (2,945; never). Runs on the status quo (Philippe,
hung): liquidity 81 EUR bn (2027–28), realistic 379 (12.7% of GDP,
2027–29), everything financial 960 (32%, 2027–31), extreme 1,128 (38%).
On the enterprises and the CDC the brief answers the committee's question
directly: the public enterprises are already on the balance sheet as F.51
equity at own funds (a sale is a sale of that line); the CDC is S.12, its
own funds are not the État's except by a law and the État's claim is
partly inside F.51 already; the gold is the Banque's and a Eurosystem
matter.

**6. Results.** Net debt 108.5% vs gross 115.7% at end-2025; the gap is
constant in euros, so the net measures rise exactly as fast as the gross
(status quo 2035: 143.7 gross, 138.0 net). Asset income 13.3 EUR bn (0.4%
of GDP); net interest 53.3 (1.8%) against 66.6 paid (2.2%); effective rate
1.74% net against 2.02% gross. The stabilising primary balance in 2030 on
the status quo is +0.96% of GDP gross and +0.68% net against −2.1% run:
the generous view narrows the required adjustment by 0.3 points. Sales:
the liquidity run is worth 2.8 points of GDP in 2035; the realistic run
holds the ratio near 116% to 2030 and ends at 130.6% in 2035 (−13.1
points), saving 23 EUR bn of interest and forgoing 5.9 of income, a net
17.1 EUR bn (0.5% of GDP) off the deficit; everything financial reaches
103% in 2030 and 112% in 2035, rising; the extreme run 99% and 106%. The
carry is positive (assets yield 1–2%, marginal OATs about 4%) so selling
helps the deficit by about 4.5 EUR bn a year per 100 sold; the level effect
is one-off and the slope is untouched. Conclusion put in the brief: the
asset side is true and beside the point for solvency, true and to the
point for a refinancing scare.

**7. Where it lives.** `src/ggfiscal/debt/balance_sheet.py` (data, history,
ladder, runs, summary), `src/ggfiscal/report/briefing_fra_balance.py` (six
charts: bs_assets, bs_gross_net, bs_net_interest, bs_sfa, bs_ladder,
bs_selldown, and `balance_sheet_FRA.csv`, `sfa_components_FRA.csv`,
`ladder_FRA.csv`, `selldown_FRA.csv` under figures/), a new section 7 in
the template (id `s9`; the AFT questions become 8 and the method 9, the
TOC and cross-references renumbered), `balance_sheet_values()` in
`tools/build_briefing_fra.py` (prefix `bs_`), `france_brief.SECTIONS`
and `tools/make_france_brief_notebook.py` (the section plus two data
cells), both HTML files and `notebooks/France_fiscal_brief_20261013.ipynb`
re-executed. Not done: the older `notebooks/briefing_FRA_AFT.ipynb` is
untouched; a UK twin on PSND/PSNFL/PSNW, which would make the point about
the choice of measure across the bundle, is the natural next step.

Gate: `tests/debt/test_balance_sheet.py` (new, 9), `test_simulate.py`
(19, one new), `test_france_brief.py` (3), `test_simulate_review.py`
(14) pass.


## D-S19-002 — The sell-down ladder line by line: valuations on the CGE, the APE and the schemes' accounts, who holds what, the État's right to sell, the income each line pays, and proposed amounts for three runs (review table; amends the ladder of D-S19-001)

Committee 2026-10-13. The first-pass ladder (D-S19-001) counted Eurostat
instrument totals. The committee asked for every line: debt securities by
holder with the État's right to sell made explicit for the social-security
funds; loans by loan; the listed portfolio by holding (Engie, Orange, ADP,
Renault, Air France-KLM, FDJ, Eramet, Airbus, Safran, Thales, Eutelsat);
fund shares by fund with their status; the unlisted book by holding (EDF,
SNCF, La Poste, Naval Group and the rest); the Caisse des dépôts and the
Banque de France with what the État can mobilise; non-financial assets by
category; a dividend yield on every line; and proposed sale amounts for
the liquidity, realistic and everything-financial runs, to be reviewed
before anything is recomputed. The extreme run is dropped.

**Sources and valuation rules** (`src/ggfiscal/debt/ladder_detail.py`,
docstring): unlisted at the CGE 2025 valeur d'équivalence (EDF 68.5, SNCF
27.8, EPIC Bpifrance 15.5, RATP 5.6, CCR 3.4, Orano 2.7, GIAT/KNDS 2.3,
Naval Group 1.2, Chantiers de l'Atlantique 0.8 EUR bn; La Poste 4.9 and
Dexia 2.3 at net book value; the public establishments, 100 EUR bn, and the
international institutions, 43.1, listed as unsaleable); listed at the
APE's 30 June 2025 values for the five lines it publishes (Airbus 15.2,
Thales 13.7, Safran 13.5, Engie 11.5, Orange 4.6) and a Redbox split of
the published 9.4 EUR bn residual by stake × market capitalisation for
ADP, Renault, FDJ, Air France-KLM and Eramet, Eutelsat at the CGE's net
book value (bought in July 2025); loans from CGE note 8.3 (Greece 5.7,
Natixis-managed 4.0, development aid 1.4, conditional advances 4.2, IdF
Mobilités 2.0, other 4.6) with the ODAC loan books (50 EUR bn, Action
Logement et al.) as the Eurostat residual, not itemised; cash from CGE
note 15 (the Trésor's account at the Banque de France 0.9 EUR bn, its
placements 24.1) with the ODAC and sub-sector residuals from Eurostat;
pension reserves by scheme (AGIRC-ARRCO 91.2 from its 2025 accounts, ERAFP
53.6 and FRR 20.7 from their 2025 reports, Ircantec 12.9 and the
professional schemes 36 from the Cour des comptes' 2022 report, end-2020)
split between direct bonds and fund shares so that the schemes add to
Eurostat's S.1314 F.3 + F.5 (219 EUR bn); CDC Section générale own funds
25.7 and Fonds d'épargne 17.7 from the 2025 rapport financier, with the
December 2025 prélèvement rule (50% of the current result, floored at 0.10%
of centralised deposits, capped by the ACPR ratio plus 5%); Banque de
France gold 257 and situation nette 283.4 from its 2025 results, dividend
nil since 2022; non-financial from Eurostat (reference) and CGE note 7
(buildings 59.1, land 11.2, roads 153.6, concessions 276.1 of which
motorways 200.4, equipment 51.0; 0.9 EUR bn booked as ready for sale).
Income: EDF 2.0 (paid 2025), the listed lines at stake × shares × the
dividend per share paid in 2025 (Engie 1.48, Thales 3.70, Safran 2.90,
Airbus 3.00, Orange 0.75, ADP 3.00, Renault 2.20, FDJ 2.05; AF-KLM,
Eramet, Eutelsat nil), the CDC's versement 3.3, SNCF's dividend shown but
recycled through the fonds de concours. The lines pay the État 10.6 EUR
bn a year against 13.3 of D.41 + D.42 received by general government.

**Right to sell.** yes / law / no on every line. Yes: the État's cash and
paper, its loans, the listed lines (with pacts noted on Airbus, Thales and
Air France-KLM), EDF, CCR, Orano, KNDS, Naval Group, Chantiers, the SLI,
buildings. Law: SNCF (2018 law, capital inalienable; subsidiaries
saleable), La Poste (2010 law, wholly public), EPIC Bpifrance, RATP, the
FRR (assets earmarked to CADES, Parliament has redirected them twice),
Ircantec, the ODAC deposits and loan books, the CDC's own funds, the
motorway concessions. No: AGIRC-ARRCO (paritarian, the 2023 attempt
failed), ERAFP (funded rights), RCI and the professional schemes, local
and social-security cash, loans and equity, the public establishments,
the international institutions, the Banque de France's gold (art. 123
TFEU, art. 31 ESCB Statute), the road network and the military equipment.

**Proposed amounts (EUR bn), pending review.** Liquidity 25: Trésor
placements 10, ODAC deposits 5, FRR bonds 8, paper 2. Realistic 94.5:
cash 15, FRR 20.7, FSPJ 2, État loans 1, listed 32.5 (Engie, Orange, ADP,
Renault, FDJ, AF-KLM, Eramet whole, half of Safran; Airbus, Thales and
Eutelsat kept), unlisted 20.3 (a quarter of EDF at 15, SNCF subsidiaries
3, RATP Dev 1, Chantiers 0.8, SLI 0.5), buildings 1. Everything financial
393: cash 33 (incl. 10 of sub-sector cash by law), FRR 20.7, AGIRC-ARRCO
86 and Ircantec 13 by a law the Conseil constitutionnel might not allow,
FSPJ 5, loans 21 (Greece and the foreign loans securitised, 10 of the
ODAC books), every listed line 68.7, the enterprises at book 136.8 (EDF,
SNCF, Bpifrance, La Poste, RATP, CCR, Orano, KNDS, Naval, Chantiers, the
vehicles), a 5 EUR bn exceptional CDC distribution, buildings 2; ERAFP,
RCI, the professional schemes, the gold, the public establishments and
the international institutions at zero. Against the first pass (81 / 379
/ 960) the realistic run is a quarter of its former size, because the
first pass sold a third of a book that is mostly public establishments,
hospitals, local bodies and funded pension rights.

**Where it lives.** `ladder_detail.py` (declared rows, `ladder_detail()`,
`totals()`, `runs_from_detail()`), `ladder_detail_FRA.csv` under figures/,
Figure 21 redrawn from it (one bar per line, grouped, clipped at 100 EUR
bn), the section-7 table replaced by the grouped line table with subtotals,
a notebook data cell, `tests/debt/test_ladder_detail.py` (4). The engine
runs (`balance_sheet.RUNS`, Figure 22) are unchanged and say so in the
text; the recomputation on the reviewed amounts is the next decision.


## D-S19-003 — The committee's rules for the three runs; the runs recomputed from the line-by-line ladder; the third run renamed "distress" (amends D-S19-001/002)

Committee 2026-10-14. Rules, applied by `ladder_detail.apply_rules` to
every line and printed under each amount in the brief's table: "no" →
0/0/0; "law" → 0/0/half the stock; "yes": the Trésor's placements 10/10/
the whole buffer (24.1), the ODAC deposits 0/0/10, loans 0/0/half (nothing
where nothing is recoverable), listed with a pact 0/0/half, listed free
0/half/whole, unlisted 0/0/whole; everything else as declared (the État's
paper 2/2/2, the Bpifrance- and CDC-managed State funds 0/2/5, État
buildings 0/1/2). The extreme run is dropped; the third run is "distress:
everything the État can reach". Totals: liquidity 12, realistic 34.6,
distress 417.3 EUR bn (14.0% of GDP), of which the largest single item is
half the motorway and other concession assets (138, "law"), then EDF at
book (68.5), the cash buffer (34.1), the listed lines (53.9), the ODAC loan
books (25), the CDC's two sections (21.7) and SNCF (13.9).

**Engine.** `balance_sheet.sales(run)` now reads the line table: each line
sold spreads evenly over the run's years with its own asset class (liquid
/ equity / nonfin) and its own yield (income to the État over stock), so
the income forgone is what that line paid the État, not a class average;
non-financial proceeds retire debt and forgo nothing. `net_view` takes
the lost income off the status-quo income path cumulatively. `RUNS`:
status_quo, liquidity, realistic, distress. The coarse rung ladder and
`ladder_FRA.csv` are gone; `ladder()` returns the line table.

**Results (status quo 143.7% in 2035, net interest 193.8 EUR bn).**
Liquidity: 143.3%, 0.4 points. Realistic: 142.6%, 1.1 points, net
interest gain 0.9 EUR bn a year by 2035 (1.9 saved, 1.1 forgone).
Distress: 117.3% in 2030 and 130.2% in 2035, 13.5 points, 23.7 EUR bn of
interest saved for 7.6 of income forgone, deficit 6.2% against 6.6%. The
reading in the brief is unchanged in kind and sharper in degree: within
the rules, what the État can actually sell without a law is a rounding
error on the path; what it can reach with a law buys thirteen points and
a year of redemptions, and the ratio climbs at the same slope afterwards.

**Regenerated.** Figure 21 (legend and source), Figure 22 (three runs),
the section-7 table (rule under each amount), the bottom-line point, the
method table; `selldown_FRA.csv`, both HTML files, the notebook. Gate:
`test_ladder_detail.py` (4, the rules asserted line class by line class),
`test_balance_sheet.py` (9), `test_france_brief.py` (3), `test_simulate.py`
(19), `test_simulate_review.py` (14) pass.


## D-S19-005 — Official baselines beside the scenario paths: the EC DSM 2025 baseline and the IMF WEO October 2026 on the deficit and debt-ratio charts (serves the France brief; extends the AMECO/DSM line of Figure 4 to Figures 14a and 14b)

Committee 2026-10-15. The interest chart carries the strict file's EC
AMECO/DSM path as a benchmark; the committee asked for the same on the
deficit and the Maastricht ratio. Two official paths are now drawn on
both, from `data/manual/FRA_benchmark_paths.csv` (retrieved 2026-10-15,
with provenance): the EC Debt Sustainability Monitor 2025 baseline for
France (country fiches tables, published 2026-02-12; calculatedDebt,
primaryBalance and (2.1) interest expenditure 2024–2036, the headline
deficit derived as interest less primary balance), and the IMF WEO of
October 2026 (IMF data API, dataflow IMF.RES:WEO 9.0.0, publication
2026-10-13, latest actual 2025; GGXWDG_NGDP and GGXCNL_NGDP, 2020–2031).
The bundle's WEO reconciliation stays on the April 2026 vintage; the API
now serves October 2026 under the same dataflow version, which is why the
two differ (2031 deficit 3.9% against 2.9%).

Numbers: DSM deficit 5.5% (2025), 5.6% (2030), 7.2% (2035), 7.5% (2036);
DSM debt 116.3 → 126.5 (2030) → 140.8 (2035) → 144.0 (2036), rising every
year; WEO deficit 5.1 → 4.2 (2030) → 3.9 (2031); WEO debt 115.5 → 123.2
(2030) → 123.6 (2031). The status quo here: 6.0% and 127.9% in 2030, 6.6%
and 143.7% in 2035 — on the DSM's path on debt, above both on the deficit.

Implementation: `briefing_fra_scenarios.benchmark_paths()`, `BENCH_STYLE`
(DSM in the brown dash-dot of the interest chart, WEO in gold dots),
`chart_paths(bench=...)`; captions of Figures 14a and 14b carry the
numbers through placeholders; method table row and sources list;
`tests/debt/test_benchmark_paths.py`. Notebook, HTML, picture book
regenerated.


## D-S20-001 — The retirement age in the France brief: a per-line, per-year impact matrix across five methods, the exposure engine and the assumptions register (serves the France fiscal brief; adds section 8)

Committee 2026-10-20/22. The Le Pen branches of D-S18-001 fold pensions
into one declared number a year. The committee asked for the sensitivity
of each category of expenditure and revenue to the legal retirement age
(62 against 60, against the 64 of the 2023 law), line by line on the
Redbox COFOG/ESA lines, the timing, the range across methodologies, and
every assumption floated rather than silent; scope general government,
not the pension system alone; starting point the law as it stands (the
LFSS 2026 suspension, 62 years 9 months frozen, 64 from the 1969 cohort);
a linear loading, each cohort-year of age moving line X by y, invariant to
whose plan it is, to be loaded on the scenarios afterwards.

**Design (`ggfiscal.debt.pension_age`).** impact(line, year) =
Σ_groups exposure(group, year, policy) × unit(line, group, year, method).
*Exposure* is computed month by month on Eurostat population by single
year of age (demo_pjan 2024–25, proj_23np baseline 2027–45, retrieved
2026-10-22, `data/manual/FRA_population_by_age.csv`) and the age each
birth cohort faces under the LFSS 2026 path (COR June 2026, Tableau 1.4),
in cohort-person-years; a cohort is split into early starters already on
carrière longue (17%, CNAV 2024), other early starters (B3, 35%,
**missing**: nobody publishes it) and the rest; bound shares 45% / 80%.
Policies: p62 "62 for all" from 1 Jan 2028; p60 "62, and 60 with 40
annuités for a start before 20"; p64 "the 2023 law resumed"; plus the
suspension, the repeal and repeal+60 as the exposures the published
costings refer to. *Units* per cohort-person-year by line are where the
methods differ: 1a DG Trésor/COR Jan 2022 decomposition (pensions 0.4,
contributions 0.1, other benefits 0.2, other levies 0.6% GDP for two
years) with the Mésange time path; 1b Cour des comptes Feb 2025 (63 vs
64: €5.8bn in 2035); 1c the DREES €1.8bn a year of the suspension divided
by the suspension's own exposure (0.21 cohort-years); 2 bottom-up cohort
arithmetic (pension €1,600 a month, wage €36,700, contributions 50% of
gross, income taxes 15.5% / 11%, ARE €16k, DREES spillover €2,250 per
cohort-person-year); 3 the published costings (RN €9bn, OFCE €15.6bn,
CNAV €16bn, Zemmour €21bn, Montaigne €34.7bn) each converted to € per
cohort-year on the exposure of the measure it costs; 4 the growth channel
(−0.35% of GDP per cohort-year at ten years, Mésange; OFCE −0.15,
Rexecode −0.55) with revenue at unit elasticity; 5 the central matrix on
the strict file's GF10_2 path. 36 assumptions in `ASSUMPTIONS`, each with
a source and a status (15 sourced, 10 inferred, 8 declared, 3 missing:
B3, U2, U10); `register()` prints them and the brief carries them in full.

**Linearity, confirmed with limits.** The unit is plan-invariant by
construction; the plan is only an exposure schedule. Limits recorded:
asymmetry (the Cour's 5.8 vs 8.4), group heterogeneity (early starters'
fuller careers), the macro second round (not linear in the stock), the
durée (42 vs 43 annuités, omitted, more cost), the lower pension for life
(omitted to 2040, less cost over time).

**Results (central, bottom-up; the range is across methods 1a–4).** Unit:
€13.4bn per cohort-year in 2030 (€5.3–13.4 across methods; pension-system
part €5.6bn, between the Cour and the DREES unit). "62 for all": €10.9bn
in 2028, €16.0bn (6.3–16.0) in 2030, €25.9bn (10.1–25.9) in 2035; with 60
for early starters €23.5bn, €30.3bn (9.8–30.3), €42.9bn (14.4–42.9). By
line in 2030, "62 for all": GF10_2 +11.4, R06 −7.2, GF10_X −2.8 and
GF10_5 −0.7 (savings), R03 −1.0. "64 resumed" saves €3.0–3.5bn a year to
2032 and nothing after 2033. Timing: a cut is front-loaded (49% of the
steady-state exposure in 2028, 69% in 2030, plateau 2033 when the law's
own path reaches 64); the pension cheque and lost contributions are
immediate, the second-round revenue (methods 1a, 4) builds over ten to
fifteen years. Growth channel: −0.49% of GDP by 2035 for "62 for all"
(−0.21 to −0.77), a haircut of up to 9 bp of growth a year.

**Brief.** New section 8 (template id `s10`; the questions become 9, the
method 10), Figures 23–28 (`briefing_fra_pensions`), the timing table,
the two line-by-line matrices (bottom-up with the min–max across methods
and the low–high of its own assumptions), the units table, the published
costings conversion, the "where this is uncertain" box and the assumptions
register. Placeholders `pa_*` from `ggfiscal.report.pension_values` on the
CSVs under figures/ (`pension_age_matrix.csv`, `_exposure`, `_units`,
`_published`, `_assumptions`). Notebook cells for the section and the
data; `france_brief.SECTIONS` carries `s10`. Not yet done, by design: the
matrix is not loaded on the scenarios (`pension_age.balance_overlay` and
`growth_haircut` are the hooks); that waits on the committee's reading of
the assumptions and on the RN's costed plan of 17 November 2026.

Gate: `tests/debt/test_pension_age.py` (8: register statuses, the COR
table, exposure signs and front-loading, the suspension calibration in
5–12 €bn per cohort-year, matrix identities, plan-invariance of the unit,
variant ordering, the overlay hooks), `test_france_brief.py` (3).
Notebook executed end to end; the full regeneration left every existing
figure and CSV byte-identical.
