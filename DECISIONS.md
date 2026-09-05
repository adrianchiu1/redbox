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
