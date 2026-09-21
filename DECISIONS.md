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

## D-S17-001 — Stage U1 spec erratum: `REPLICATION_KICKOFF.md` §4.3 and §13.1 amended to the cells actually adopted (spec-first, COFOG_KICKOFF.md §16; serves kickoff §4.3, §13.1, D18, D26)

**Context.** The kickoff was written before the OECD tables were read. Stage
U0 measured every cell on USA 1970–2024 and adopted four cells that differ
from the document (D-S16-005). COFOG_KICKOFF §16 is spec-first and
append-only: the code follows the spec, so where the measurement wins, the
spec is amended and the amendment is a decision — not a silent divergence.

**Decision.** Four rows of the kickoff are amended in place, each carrying
the pointer `(as measured, D-S16-005)` so the reader can find the evidence.
Nothing else in the kickoff is rewritten.

| Where | Was | Now | Why (measured, D-S16-005) |
|---|---|---|---|
| §4.3 R02_A | `T10 D214A (+ D2122C where present)` | `T10 D214A` | Table 10 publishes no `D2122C` cell for the USA. Import duties are `D2121 = D212` (USD 83,587 mn in 2024) and stay in `R02_X`. The "where present" was written for Germany's energy tax on imported fuels (D-S13-005); it is simply absent here. |
| §4.3 R03 | `T10 D51A` | `T10 D51M`, incl. holding gains | The ESA_REV concept is `D51A_C1` (holding gains in) — what `gov_10a_taxag D51A_C1` (FRA/DEU) and ONS `D51M` (GBR) carry. `D51M + D51O = D51` exactly in every year (max \|diff\| 0.01 mn); `D51A + D51B` would leave `D51C1 + D51C2` (USD 502,624 mn in 2024) unallocated in `R05`. |
| §4.3 R04 | `T10 D51B` | `T10 D51O`, incl. holding gains | The `D51B_C2` concept, the R03 argument on the corporate side. 2024 = USD 663,685 mn (D51B 584,611 + D51C2 79,074). |
| §4.3 R09 | `T12 P1M + P1O + P131` | `T12 P1O` | `P1O` **is** the sales aggregate P.11 + P.12 + P.131 (the CL_TRANSACTION label); `P1M` and `P131` are its memo components and `P1O = P1M + P131` exactly (max \|diff\| 0.001 mn). Summing the three codes double counts. OTR = D2 + D5 + D61 + D4 + D7 + D9 + D39 + **P1O** closes to USD 0.002 mn in every year; with the kickoff's sum it does not close at all. |
| §13.1 `OECD_T10` | object `(D51A/B, D214A, D611/D613, D59, D91)` | `(D51M/D51O incl. holding gains, D214A; no D2122C cell)` | The same two corrections, plus the measured fact that Table 10 is **not** the source of `D611`/`D613`/`D59`/`D91`: `R06`/`R06_E`/`R06_H` take Table 12 (T10 `D61` differs by up to USD 724 mn) and `R05` takes Table 12 `D5` and `D91` so the `R01..R10 = OTR` identity closes (D-S16-005). Table 10 supplies the two income-tax cells and the excise cell, nothing else. |

**Scope.** Documentation only: every one of these cells is already what
`config/lines.yaml`, `standardise/families.py` and the two U0 crosswalks
implement and what the canonical layer carries. No value moves; the erratum
makes the spec agree with the built package instead of the reverse.

## D-S17-002 — OQ-15 taken on its default: the USA `GF04_5` proxy stays the NIPA current-expenditure cell; no capital part is constructed (serves kickoff D26, D13; OPEN_QUESTIONS.md OQ-15)

**Decision.** `GF04_5` = NIPA Table 3.16 line 14 (`T31600:14`, G16018
Transportation), current expenditures only, `level2_proxy_actual`, grade B,
`concept_flag = level2_bea_function`, the concept note on every row and in
`crosswalks/BEA_NIPA_to_COFOG.csv`. D26's "current plus gross investment" is
**not** constructible cell-for-cell: Table 3.17 publishes gross investment by
function for the nine Level I functions only (lines 105–133) and capital
transfers by function at 134–145; no transportation gross-investment cell
exists in the flat files (highways and transit investment sit inside
Economic affairs gross investment, line 109).

**Why the default and not a construction.** Splitting the Level I investment
line onto 04.5 by any share would be a constructed value, which D13 forbids;
the alternative in OQ-15 (the NIPA underlying-detail flat file) returned 403
on 2026-09-20 and is not in the D8 store. So the under-coverage is
documented rather than closed: measured share of the parent 0.2685 (2024),
0.2418 (2000), 0.2556 (1990), and the note travels with the row. If the
underlying detail ever becomes reachable it is a U2 harvest question.
OQ-15 is marked resolved.

## D-S17-003 — OQ-16 taken on its default: the §8.2 stability rule and its V24 WARN stay for the USA; nothing absorbed; revisited at U5 (serves kickoff §8.2, V24 amended; OPEN_QUESTIONS.md OQ-16)

**Decision.** `weo_perimeter_gap_expected: true` stays for the USA and
`tolerances.perimeter_sigma_pct_te` stays 0.5 for every country. The
tolerance is **not** widened to the measured 1.51, and no third
classification rule is introduced at U1. The V24 WARN on every WEO vintage
is the intended visibility of a real GFSM-vs-SNA basis difference, not a
defect to silence (D13, D16): the WEO's US series start in 2001, carry the
IMF's documented per-year adjustments (the 2017 repatriation tax among
them), and the NLB gap ratio averages −2.34 % of TE with sigma 1.51, so 12
of 24 overlap years classify `unexplained`.

**Nothing absorbed.** The year-by-year rows stay in
`data/canonical/weo_base_bridge.csv`; no line value is adjusted to close the
gap. **Revisited at Stage U5**, where §8.2–§8.5 run for both variants on
every vintage and the IMF's documented adjustments can be tested as a third
rule against the measured series. Until then the WARN is a standing,
expected USA finding and `tools/byte_identity.py --check-now-scoped V24`
names it on the gate command line. OQ-16 is marked resolved.

## D-S17-004 — V44 lives in `validate/u1.py`, registered at stage 1, and is scoped to what D26 actually builds: the COFOG Level II proxies, with V19 delegated and the GFS comparison at OK (serves kickoff §10 V44, D26, §12 Gate U1)

**Where.** A new `src/ggfiscal/validate/u1.py`, `"V44": 1` in
`runner.V_SUITE_STAGE` and its `IMPLEMENTED` merged into the runner beside
R0's. The kickoff offered `validate/r0.py` as an alternative home; a file
per replication stage keeps each stage's additions reviewable on their own
and matches `stage1.py .. stage5.py`.

**Scope, and why each boundary is where it is.** V44 runs for every country
whose `countries.yaml` names a `level2_source` — the config key, never a
country literal — and reports **OK with an explicit "no proxied Level II"
message** for the countries that do not, so three quarters of the package
does not silently skip the check.

1. **COFOG only.** The USA's *revenue* Level II lines (`R02_A`, `R06_E`,
   `R06_H`) come from the anchor institution's own tables at
   `anchor_actual` grade A (T10 `D214A`; T12 `D611`/`D613`). D26, and V44
   with it, is about the COFOG groups that no US source publishes. A V44
   that demanded grade B of the revenue splits would be wrong about the
   data, and V1/V19 already police them.
2. **Anchor-year rows.** Every row observed at its own anchor year and not
   forecast must be `level2_proxy_actual`, grade B, with a concept note.
   Stitched rows (`anchor_year != year`) and forecast rows are U2/U3 rows
   with their own checks (V5, V13, V17); V44 counts them in its OK message
   so their first arrival is visible rather than silently admitted. At U1
   there are none: all 440 USA Level II rows (4 lines x 55 years x 2
   variants) are anchor rows.
3. **`level2_bea_function` is required of the rows that came from the
   national table, not of all four lines.** `GF01_7` is the D10 fallback:
   the build puts it on the anchor institution's own gross D.41 payable,
   `concept_flag = d41_gross_accrued`, which D-S16-005 measured equal to
   T11 `D4 x GF01` to USD 3 mn. It is a Level II proxy row — typed
   `level2_proxy_actual` at grade B, and checked as one — sourced from the
   anchor, not from NIPA, so stamping it with NIPA's concept flag or NIPA's
   crosswalk would be a false provenance claim. The 330 rows that *are*
   BEA-sourced carry both.
4. **V19 is delegated, not duplicated.** `remainder + Σ level2 = parent`
   is V19's arithmetic. V44 calls `check_v19()` and re-reports its ERRORs
   for the country under V44's id; it never recomputes the same sums a
   second way, so the two checks cannot drift apart.
5. **The IMF GFS comparison is a memo at OK.** `GF0170_T` (USA 1980–89, the
   only years it exists) is reported as its own OK row naming the span and
   the measured range: the GFSM series runs **−48.2 % to −34.0 %** against
   the built Level II value. Never WARN, never ERROR — D26 says reported,
   not used, and V1 already carries the per-year WARN rows.

**Negative-case coverage.** `tests/stage_1/test_u1_usa.py` breaks one
column at a time on one USA Level II line (`observation_type`,
`quality_grade`, `notes`, `concept_flag`, `crosswalk_version`) and asserts
V44 ERRORs, scoped to that line. A check that only passes on good data is
not a check.

## D-S17-005 — The §11.5 crosswalk that documents a row's mapping travels with the row: `crosswalk_version` on the USA D26 proxy rows (serves COFOG_KICKOFF.md §11.5, kickoff §11.4, D26)

**Decision.** `crosswalks/OECD_T11_to_COFOG.csv` (11 rows) and
`crosswalks/BEA_NIPA_to_COFOG.csv` (4 rows) complete the §11.4 list for the
USA history, on the §11.5 columns, at `crosswalk_version` **1.0** with
`reviewer` **stage-u1-build**. `build.write_crosswalks` picks both up with
no change (it globs `crosswalks/*.csv`); `crosswalks.csv` goes 93 → 108
rows over 17 files.

*On the version string.* The session brief asked for "crosswalk_version
stage-u1-1.0" and, in the same breath, for the rows to point at
`BEA_NIPA_to_COFOG:**1.0**`. Those agree only if the file's version is
`1.0`, so the stage marker is recorded where the existing files record it —
the `reviewer` column (`stage-u0-build`, `stage2-build`, `stage11-build`
are the precedents) — and the version column stays a bare version, which is
what a "version bump → rebuild" rule needs it to be.

**The row stamp.** `standardise/proxies.py` gains a `Level2Proxy` record
(source_id, cell key, reader, **crosswalk**) so the mapping's documentation
is part of the same config-keyed routing, and `config.crosswalk_version()`
reads the version out of the file itself (raising if a file carries none or
several) rather than repeating it in code. `build.anchor_series` stamps
`<stem>:<version>` on the proxy rows through the existing `per_year`
override, and the row assembly reads `crosswalk_version` from that override
instead of hard-coding `None`.

**Measured consequence, checked before and after.** 330 USA rows (GF10_2,
GF10_5, GF04_5 x 55 years x 2 variants) gain one metadata column, `''` →
`BEA_NIPA_to_COFOG:1.0`, in `expenditure_long_{strict,maximum_extension}.csv`
and `deliverables/expenditure_cofog.csv`. **No value moves**: a column-by-
column diff of all seven canonical CSVs against the session baseline shows
`crosswalk_version` as the only differing column and `USA` as the only
differing `iso3`; `value_lcu_mn`, `pct_gdp`, grades, types and notes are
identical in every row, for the USA as for the other three.
`deliverables/strict_USA.csv` is a wide values file and is unchanged.
So U1 added documentation, not values — the stage's one allowed USA change
was not needed.

**What the two files record.** `OECD_T11_to_COFOG` is the identity mapping
(D18: the OECD Table 11 codes *are* the COFOG divisions, no allocation
judgement), and carries the two findings a reader must not miss: `GF05` is a
**structural zero** — Table 11 publishes no environmental-protection rows
for the USA at all, the nine published functions sum to `_T` to USD 0.002
mn, so 05 is zero by additivity, not missing (D20, V41) — and `_T` is **not**
Table 12's `OTE`: the wedge runs −665.0 mn (2002) to +1,334.8 mn (2010), at
most 261 ppm of `_T`, measured, reported, and never absorbed (D13/D16; the
COFOG tree publishes `_T`, the ledger publishes `OTE`, and no identity mixes
them). `BEA_NIPA_to_COFOG` records the four D26 cells with their measured
shares of the parent (2024 / 2000 / 1990): GF01_7 0.6962 / 0.7260 / 0.7773
**registered but NOT applied** (the build takes the D10 fallback so the line
stays on the anchor's ESA concept; the NIPA cell is the cross-check, ratio
1.0000–1.0321 against T12 D.41), GF10_2 0.5815 / 0.5459 / 0.5689 (wider than
10.2 by 10.3's survivors), GF10_5 0.0161 / 0.0315 / 0.0457 (cyclical, no
stable share assumed), GF04_5 0.2685 / 0.2418 / 0.2556 with the OQ-15 note
(a floor on 04.5, not an estimate of it — D-S17-002).

## D-S17-006 — `stage_reached: 1` for the USA; the small multiples and the §8.3 history decomposition need no change for a USD country (serves kickoff §12 Stage U1, D-S16-008)

**Stage.** `countries.yaml` USA `stage_reached: 0 → 1`. Behaviourally inert
by design: no site in the package gates on stage 1 (`build.build` runs
backward legs from 2 and forecast legs from 3; `explanation.compute`
decomposes the forecast side for `countries_at_stage(3)`), so
`countries_at_stage(2)` and `(3)` remain `GBR, FRA, DEU` and the canonical
layer is unchanged by the switch. U2 and U3 raise it after reviewing the
legs it turns on.

**Small multiples — inspected, not assumed, and not changed.**
`report/small_multiples.py` already renders one column per configured
country and plots **`pct_gdp`** in every panel (the ledger row plots
NLB/GDP x 100), each subplot on its own y axis. The USD-vs-EUR scale
difference therefore never reaches the chart: USA TE is 39.6 % of GDP
beside FRA 57.0 %, on figures of USD 11.6 tn and EUR 1.67 tn. The rendered
`reports/small_multiples_stage1.html` carries 42 USA traces — all 41 lines
plus NLB — the same as every other country, and the column title `USA`.
The brief's conditional ("if the small multiples need a change for the USD
scale, make it in the renderer, never in the data") does not arise, and no
change was made for its own sake.

**§8.3 history decomposition — runs wider than the gate asks.**
`reconcile/dynamics.decompose` iterates `config.COUNTRIES` and needs only
the 20 Level I lines plus GDP, all of which the USA has from 1970. It
produces **1971–2024** for the USA (2,422 rows per the two variants),
comfortably covering Gate U1's 2001–2024, and **V26 passes with exact
additivity in both variants** (0 failures; 2024 strict: line contributions
sum to −0.090417 pp = `NLB_CHANGE_SUM`, with `ANCHOR_B9_DELTA` +0.003576
and the WEO `GGXCNL` change +0.028700 reported beside it as memos, never
allocated to lines).

## D-S17-007 — Gate U1 record: what was built, what was measured, and what is unchanged (serves kickoff §12 Gate U1)

| criterion | result |
|---|---|
| 41 USA lines plus the ledger 1970–2024 from anchors | **holds**: 41 granular (line, tree) series x 55 years, 2,420 strict rows — `anchor_actual` 1,430, `derived_actual` 605, `level2_proxy_actual` 220, `structural_zero` 165; grades A 2,035 / B 385; no forecast row and no stitched row. Ledger 1970–2024, 55 rows, `NI` complete. Coverage matrix 41/41 USA lines, 164/164 overall |
| V1–V4, V7–V9, V12, V14, V19–V23, V41, V44 green for the USA | **holds**: zero USA-scoped ERRORs on every one of them, and zero ERRORs anywhere. V2/V3/V4/V7/V8/V9/V12/V14/V19/V20/V22/V23/V41 each report one OK row covering all four countries; V44 reports its OK summary plus the GFS memo. WARN-tier findings that remain are the intended visibility recorded at U0: V1 258 USA rows (the GFSM-vs-SNA wedges on E01/E02/E05/GF01/GF01_7/GF03/GF04/GF08/GF09) and V21's 30 rows, which are the pre-existing FRA/DEU interest seams — the USA has no V21 row because its `GF01_7` *is* D.41 by the D10 fallback, so the comparison V21 makes is degenerate, not skipped |
| small multiples render | **holds**: 42 USA traces (41 lines + NLB) in `reports/small_multiples_stage1.html`, one column per country, all panels in % of GDP (D-S17-006) |
| §8.3 history decomposition 2001–2024 runs and passes V26 | **holds**: USA 1971–2024, V26 exact in both variants (D-S17-006) |
| GBR/FRA/DEU byte-identical (run_id excepted) | **holds**: `python3 tools/byte_identity.py /tmp/gg_baseline --countries GBR,FRA,DEU --new-crosswalk OECD_T11_to_COFOG --new-crosswalk BEA_NIPA_to_COFOG --new-checks V44` → OK. Verified adversarially: the same command **fails** with either allowance dropped (`crosswalks.csv` shape 108 vs 93; `exceptions.csv` rows other than the new OK checks differ), so the gate is passing on the named exceptions, not on a loosened comparison. `tools/byte_identity.py` itself is untouched at U1 |
| no USA anchor value changes | **holds**: column-by-column diff of all seven canonical CSVs and every deliverable against the pre-change baseline — the only difference anywhere is `crosswalk_version` on 330 USA rows (D-S17-005). Every `value_lcu_mn` identical |
| `ggfiscal validate` ERROR = 0 | **holds**: ERROR=0, WARN=2959, OK=103, SKIP=0 (baseline this session: ERROR=0, WARN=2959, OK=101; the two added OK rows are V44's summary and its memo). The WARN count is container-dependent through `S0_SNAPSHOTS` and is identical to this session's own baseline |
| `python3 -m pytest -q` | **317 passed**, 80 skipped — the session baseline's 299 plus the 18 new `tests/stage_1/test_u1_usa.py` tests. 33 failed / 21 errors, every one in `tests/debt/` for absent debt snapshots, identical to the baseline run before any U1 change (OQ-14; `ggfiscal debt fetch` was deliberately not run, so `exceptions.csv` and the snapshot manifest stay comparable across the stage) |

**Baseline this session** (established before any edit, after `ggfiscal
fetch --all`: 118 pulls, 0 failures): chain green; ERROR=0, WARN=2959,
OK=101; pytest 299 passed / 80 skipped / 33 failed / 21 errors; and all
seven canonical CSVs reproduced the committed layer byte-for-byte except
`run_id` — for the USA as for GBR/FRA/DEU, confirming the U0 layer is
reproducible in a fresh container.

**Rules held.** No `elif iso3 ==` anywhere (the U0 test greps the package
for a USA literal and still passes); V44 and the crosswalk stamp are keyed
by `countries.yaml level2_source` through `proxies.LEVEL2_PROXY_READERS`,
never by a country; `forward.py` and `backward.py` untouched; the readers
of GBR/FRA/DEU untouched; no notebook touched; the debt engine untouched;
`tools/byte_identity.py` untouched.

**Nothing blocked.** Every Gate U1 criterion is met; no criterion was
weakened and no test skipped. OQ-13 (the blocked US hosts) still gates the
U4 long legs and is not a U1 criterion; OQ-14 is unchanged and is the only
reason the full `pytest` is not green in this container.
