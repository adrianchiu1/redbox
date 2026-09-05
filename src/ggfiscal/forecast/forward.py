"""Forward extension — strict forecasts (Stage 3) and maximum-extension
forecasts (Stage 4) (§7.2, §7.4-7.9, §7.12-7.13, §12, D2, D7, D12).

Y_t = Y_{t-1} × X_t / X_{t-1} for t > T: growth of the forecast source, never
its level (§7.2). Sources are applied sequentially per D12 — the short-term
source through its horizon, the long-term source only beyond it — and each
transition writes a boundary record (§7.4) to forecast_boundaries.csv.

%-of-GDP sources (§7.5): the implied nominal growth is
(ratio_t / ratio_{t-1}) × same-source nominal GDP growth, with the GDP path
constructed from the source's own real-growth and price assumptions where the
source publishes no nominal GDP (Ageing Report, DSM) —
`gdp_source_id = {source_id}_constructed`.

Grading (§9, §9.2, D6): coverage_share = source level / anchor level at the
last common year. A = direct forecast of the same ESA aggregate with
|share − 1| ≤ 0.005; B = 0.90-1.10; C = 0.50-0.90; else D. Variant routing
(Stage 4, D-S4-001): A/B non-proxy rows enter strict and maximum_extension;
C rows and §7.8 single-component proxies (`max_only`) enter
maximum_extension only; D is measured and recorded but never applied — with
one spec-mandated exception, §7.9's GF01-via-GF01_7 (`mandated`), which
enters maximum_extension at its measured D grade with an explicit
`residual_method` (D2/Q3).

Lines with no applicable source get a declaration row (D7 for "no identified
forecast"; blocked / below-strict-grade otherwise) in
forecast_declarations.csv — Gate 3's "every D7 line has its note".
"""

from __future__ import annotations

import dataclasses

import pandas as pd

from ggfiscal.standardise import readers as R

AMECO_REV_XWALK = "EC_AMECO_to_ESA_REV:1.0"
AMECO_INT_XWALK = "EC_AMECO_to_INTEREST:1.0"
AMECO_COFOG_XWALK = "EC_AMECO_to_COFOG:1.0"
DSM_XWALK = "EC_DSM_to_INTEREST:1.0"
AR_XWALK = "EC_AGEING_to_COFOG:1.0"
STSCH_XWALK = "DEU_STEUERSCHAETZUNG_to_ESA_REV:1.0"
OBR_REV_XWALK = "OBR_to_ESA_REV:1.0"
OBR_COFOG_XWALK = "OBR_PESA_to_COFOG:1.0"

CONSTRUCTED_NOTE = "constructed, not an official forecast"  # §7.8


@dataclasses.dataclass
class FcSource:
    """One forecast source for one line, ready to chain (§7.2)."""
    source_id: str
    series: pd.Series              # CY levels in LCU mn, or % of GDP ratios
    kind: str                      # 'level' | 'pct_gdp'
    horizon_year: int              # V10: no forecast beyond this
    last_actual_year: int          # source years <= this are actuals (§7.2)
    concept_note: str              # V13
    crosswalk_version: str
    direct_concept: bool = False   # §9 grade A eligible (same ESA aggregate)
    gdp_growth: pd.Series | None = None    # pct_gdp: nominal GDP growth factors (§7.5)
    gdp_levels: pd.Series | None = None    # level sources: same-source nominal GDP, LCU mn
    gdp_source_id: str = ""
    unit_factor: float = 1.0       # multiply source level -> LCU mn
    concept_flag: str = ""
    scenario_label: str | None = None
    observation_type: str = "direct_forecast"   # or composite_forecast / proxy_forecast
    interpolation_method: str | None = None     # D11, when benchmark-interpolated
    period_conversion_method: str | None = None  # §7.10, when FY->CY converted
    max_only: bool = False         # §7.8: single-component proxies never enter strict
    residual_method: str | None = None  # D2: recorded on every proxy/composite row
    mandated: bool = False         # §7.9 GF01-via-GF01_7: applied (maximum only)
    #                                even when measured coverage falls in the D band


@dataclasses.dataclass
class Declaration:
    """Why a line has no strict forecast (or a note beside one) — Gate 3."""
    iso3: str
    classification: str
    line_code: str
    status: str    # forecast_applied | no_official_forecast | source_blocked
    #              | grade_below_strict | no_machine_readable_source | not_extended
    note: str


# ---------- period conversion and interpolation primitives ----------

def fy_to_cy(fy: pd.Series) -> pd.Series:
    """§7.10 (GBR forecast sources only): CY_t = 0.25 × FY_{t-1/t} + 0.75 ×
    FY_{t/t+1}, with FY series indexed by the calendar year the fiscal year
    starts in (FY 2026-27 -> index 2026). Conversion consumes one horizon year.
    Exercised by the OBR/PESA sources since the OQ-6 partial unblock
    (D-S7-001/002)."""
    out = {}
    for t in fy.index:
        if (t - 1) in fy.index:
            out[t] = 0.25 * float(fy[t - 1]) + 0.75 * float(fy[t])
    return pd.Series(out).sort_index()


def interpolate_benchmarks(bench: pd.Series, method: str) -> pd.Series:
    """D11: fill the years between benchmark observations. `ratio_linear`
    interpolates linearly (for % of GDP sources); `level_compound` applies
    constant compound growth (for nominal sources). Benchmark years keep
    their values exactly. Unused by the 2024 AR (annual tables) but required
    machinery for benchmark-only sources."""
    years = sorted(int(y) for y in bench.index)
    out = {}
    for y0, y1 in zip(years, years[1:]):
        v0, v1 = float(bench[y0]), float(bench[y1])
        n = y1 - y0
        for k in range(n):
            t = y0 + k
            if method == "ratio_linear":
                out[t] = v0 + (v1 - v0) * k / n
            elif method == "level_compound":
                out[t] = v0 * (v1 / v0) ** (k / n)
            else:
                raise ValueError(f"unknown interpolation_method {method}")
    out[years[-1]] = float(bench[years[-1]])
    return pd.Series(out).sort_index()


# ---------- source construction ----------

def _ameco(iso3: str, variable: str, note: str, xwalk: str, *,
           direct: bool, flag: str = "") -> FcSource:
    return FcSource(
        source_id="EC_AMECO", series=R.ameco_series(iso3, variable, 16) * 1000.0,
        kind="level", horizon_year=2027, last_actual_year=2025,
        concept_note=note, crosswalk_version=xwalk, direct_concept=direct,
        gdp_levels=R.ameco_series(iso3, "UVGD", 6) * 1000.0,
        gdp_source_id="EC_AMECO", concept_flag=flag)


AMECO_UYIG_NOTE = ("AMECO UYIG (Spring 2026): ESA gross GG interest payable "
                   "(D.41), same gross accrued concept as the anchor; D.41 in "
                   "place of COFOG Level II 01.7 (D10 fallback concept)")
AMECO_UTSG_NOTE = ("AMECO UTSG (Spring 2026): net social contributions "
                   "received (D.61), general government — the anchor's own "
                   "ESA aggregate, Commission forecast vintage")
AMECO_SALES_NOTE = ("AMECO UTOG minus UROG (Spring 2026): other current "
                    "revenue including sales minus other current revenue = "
                    "sales of goods and services (P.11+P.12+P.131); complete "
                    "composite of two official GG aggregates (§6.2(3)); "
                    + CONSTRUCTED_NOTE)
DSM_NOTE = ("DSM 2025 baseline interest expenditure, % of GDP, gross accrued "
            "GG D.41 (EDP concept); nominal path via DSM real growth and "
            "inflation assumptions (§7.5); long-term leg beyond the AMECO "
            "horizon per D12")
AR_NOTE = {
    "GF07": ("2024 Ageing Report health care spending, % of GDP, baseline: "
             "public health spending on the AWG perimeter vs COFOG GF07 — "
             "coverage measured; nominal path constructed from AR potential "
             "growth and HICP assumptions (§7.5)"),
    "GF09": ("2024 Ageing Report education spending, % of GDP, baseline: AWG "
             "education perimeter vs COFOG GF09 — coverage measured; nominal "
             "path constructed per §7.5"),
    "GF10": ("2024 Ageing Report gross public pensions plus long-term care, "
             "% of GDP, baseline: pensions+LTC cover only part of COFOG GF10 "
             "(no family/housing/unemployment/social-exclusion projections); "
             "coverage measured; " + CONSTRUCTED_NOTE),
}
AMECO_GF01_NOTE = ("§7.9: GF01 total extended via GF01_7 growth (AMECO UYIG) "
                   "with explicit residual_method — the spec-mandated "
                   "maximum_extension construction; interest is the minor "
                   "share of GF01 (coverage measured, D band), so the "
                   "uncovered general-services residual rides the declared "
                   "residual assumption (D2); " + CONSTRUCTED_NOTE)
AMECO_GF10_NOTE = ("AMECO UYTGH: social benefits other than social transfers "
                   "in kind (D.62), general government — the dominant cash "
                   "component of COFOG GF10 (§6.2(4) single-component proxy, "
                   "maximum_extension only per §7.8); excludes in-kind social "
                   "protection and includes some non-GF10 cash benefits "
                   "(perimeter mismatch measured in coverage_share); "
                   + CONSTRUCTED_NOTE)
STSCH_NOTE = ("Arbeitskreis Steuerschätzungen (170th, May 2026), cash "
              "Finanzstatistik by tax, all government levels; growth only "
              "(§7.11); cash timing and Kindergeld/Zulagen netting differ "
              "from the anchor's accrued gross ESA treatment (D17); EU own "
              "resources are financing items outside the tax lines used")


def _dsm_interest(iso3: str) -> FcSource:
    return FcSource(
        source_id="EC_DSM", series=R.dsm_series(iso3, "(2.1) Interest expenditure"),
        kind="pct_gdp", horizon_year=2036, last_actual_year=2024,
        concept_note=DSM_NOTE, crosswalk_version=DSM_XWALK,
        gdp_growth=R.dsm_nominal_gdp_growth(iso3),
        gdp_source_id="EC_DSM_constructed", concept_flag="d41_gross_accrued")


def _ar(iso3: str, line: str, items: list[str]) -> FcSource:
    from ggfiscal import config

    series = sum(R.ar_series(iso3, i) for i in items)
    composite = len(items) > 1
    return FcSource(
        source_id="EC_AGEING_2024", series=series, kind="pct_gdp",
        horizon_year=2070, last_actual_year=2022,
        concept_note=AR_NOTE[line], crosswalk_version=AR_XWALK,
        gdp_growth=R.ar_nominal_gdp_growth(iso3),
        gdp_source_id="EC_AGEING_2024_constructed",
        scenario_label="baseline",
        observation_type="composite_forecast" if composite else "direct_forecast",
        residual_method=config.residual_method(iso3, line) if composite else None)


def _stsch(labels: list[tuple[str, str]], note_extra: str = "") -> FcSource:
    series = sum(R.steuerschaetzung_series(sheet, label) for sheet, label in labels)
    parts = ", ".join(label for _, label in labels)
    return FcSource(
        source_id="DEU_STEUERSCHAETZUNG", series=series, kind="level",
        horizon_year=2030, last_actual_year=2025,
        concept_note=f"{STSCH_NOTE}; components: {parts}"
                     + (f"; {note_extra}" if note_extra else "")
                     + (f"; {CONSTRUCTED_NOTE}" if len(labels) > 1 else ""),
        crosswalk_version=STSCH_XWALK,
        gdp_levels=R.steuerschaetzung_gdp(),
        gdp_source_id="DEU_STEUERSCHAETZUNG",
        observation_type="composite_forecast" if len(labels) > 1 else "direct_forecast")


_SOLI_R03 = [("Tab 8.2", "- Lohnsteuer"), ("Tab 8.2", "- veranl. Einkommensteuer"),
             ("Tab 8.2", "- AbgSt. a. Zins- u. Veräuß.-ertr."),
             ("Tab 8.2", "- nicht veranl. Steuern v. Ertrag")]


# ---------- OBR (GBR — hand-retrieved EFO March 2026 + PSF databank, D-S7-001;
# ---------- PESA 2026 via the allowlisted gov.uk, D-S7-002; OQ-6 partial unblock) ----------

OBR_NOTE = ("OBR EFO March 2026 vintage via the PSF aggregates databank "
            "(August 2026 file, 'forecast as of March 2026'): per-tax series, "
            "National Accounts basis, accrued, fiscal years converted per "
            "§7.10; public sector receipts perimeter — individual taxes are "
            "GG in substance, coverage measured on the GG anchor (§7.11, "
            "§14); cash-timing and holding-gains wedges carried by the "
            "crosswalk (D17)")
PESA_NOTE = ("HMT PESA 2026 table 1.9: MoD total DEL (RDEL+CDEL), budgeting "
             "basis, cash-ish, central government — vs COFOG GF02 GG accrual "
             "(delivery-timing wedge, §7.13); outturns 2021-22..2025-26 + "
             "SR25 plans to 2028-29; FY converted per §7.10; §15 Q7: "
             "legislated defence plans strict at grade B where the measured "
             "share is >= 90%")


def _obr_gdp_levels() -> pd.Series:
    """OBR's own nominal GDP path (databank, FY -> CY per §7.10), £mn."""
    return fy_to_cy(R.obr_databank("Aggregates (£bn)",
                                   "Nominal GDP (£ billion)")) * 1000.0


def _obr_receipts(labels: list[str], note_extra: str, *,
                  extra_fy: pd.Series | None = None,
                  residual: str | None = None) -> FcSource:
    """Composite of OBR databank per-tax series (£bn FY), converted per
    §7.10. `extra_fy` adds a component available only in the EFO annex
    tables (business rates)."""
    fy = None
    for label in labels:
        s = R.obr_databank("Receipts (£bn)", label)
        fy = s if fy is None else fy + s
    if extra_fy is not None:
        fy = fy + extra_fy
    composite = len(labels) + (extra_fy is not None) > 1
    return FcSource(
        source_id="OBR_EFO_LATEST", series=fy_to_cy(fy.dropna()) * 1000.0,
        # horizon: FY 2030-31 touches calendar 2031; V10 nets the §7.10
        # conversion loss, and the CY series itself ends at 2030
        kind="level", horizon_year=2031, last_actual_year=2024,
        concept_note=f"{OBR_NOTE}; components: {', '.join(labels)}"
                     + (f"; {note_extra}" if note_extra else "")
                     + (f"; {CONSTRUCTED_NOTE}" if composite else ""),
        crosswalk_version=OBR_REV_XWALK,
        gdp_levels=_obr_gdp_levels(), gdp_source_id="OBR_EFO_LATEST",
        concept_flag="public_sector_perimeter",
        period_conversion_method="fy_weighted_quarters",
        observation_type="composite_forecast" if composite else "direct_forecast",
        residual_method=residual)


def forecasts_for(iso3: str) -> dict[tuple[str, str], list[FcSource]]:
    """Ordered (short-term first, D12) forecast sources per (classification,
    line_code) — §12 Stage 3 priority (interest, defence, big revenue lines,
    health/education, GF10, remaining AMECO lines) plus the Stage 4
    maximum-extension proxies (§7.8-7.9, D-S4-002/003)."""
    from ggfiscal import config

    out: dict[tuple[str, str], list[FcSource]] = {}
    uyig = _ameco(iso3, "UYIG", AMECO_UYIG_NOTE, AMECO_INT_XWALK,
                  direct=False, flag="d41_gross_accrued")
    out[("COFOG", "GF01_7")] = [uyig] + (
        [_dsm_interest(iso3)] if iso3 in ("FRA", "DEU") else [])
    # §7.9 (Stage 4): GF01 via GF01_7 growth — mandated, maximum only, with
    # the explicit D2 residual assumption; measured coverage is D band
    # everywhere (interest is the minor share of GF01)
    gf01 = _ameco(iso3, "UYIG", AMECO_GF01_NOTE, AMECO_COFOG_XWALK, direct=False)
    gf01.observation_type = "proxy_forecast"
    gf01.max_only = True
    gf01.mandated = True
    gf01.residual_method = config.residual_method(iso3, "GF01")
    out[("COFOG", "GF01")] = [gf01]
    out[("ESA_REV", "R06")] = [_ameco(iso3, "UTSG", AMECO_UTSG_NOTE,
                                      AMECO_REV_XWALK, direct=True)]
    # R09 via AMECO sales = UTOG - UROG (complete composite; GBR lacks the series)
    sales = (R.ameco_series(iso3, "UTOG", 16) - R.ameco_series(iso3, "UROG", 16)).dropna()
    if not sales.empty:
        src = _ameco(iso3, "UTOG", AMECO_SALES_NOTE, AMECO_REV_XWALK, direct=False)
        src.series = sales * 1000.0
        src.observation_type = "composite_forecast"
        src.residual_method = config.residual_method(iso3, "R09")
        out[("ESA_REV", "R09")] = [src]
    # R05: AMECO UTKG covers only the D.91 component — a §7.8 single-component
    # proxy: maximum_extension where the C band is met (FRA), recorded
    # otherwise (GBR/DEU are D)
    r05 = _ameco(
        iso3, "UTKG", "AMECO UTKG: capital taxes (D.91) only — one component "
        "of R05 (D.51 other + D.59 + D.91); §6.2(4) single-component proxy, "
        "maximum_extension only per §7.8; " + CONSTRUCTED_NOTE, AMECO_REV_XWALK,
        direct=False)
    r05.observation_type = "proxy_forecast"
    r05.max_only = True
    r05.residual_method = config.residual_method(iso3, "R05")
    out[("ESA_REV", "R05")] = [r05]
    # GF10 (Stage 4): AMECO D.62 dominant-component proxy (short-term, C band,
    # all three countries), chained per D12 into the AR pensions+LTC composite
    # beyond 2027 for FRA/DEU (overlap divergence under the V16 threshold)
    gf10 = _ameco(iso3, "UYTGH", AMECO_GF10_NOTE, AMECO_COFOG_XWALK, direct=False)
    gf10.observation_type = "proxy_forecast"
    gf10.max_only = True
    gf10.residual_method = config.residual_method(iso3, "GF10")
    out[("COFOG", "GF10")] = [gf10]
    if iso3 in ("FRA", "DEU"):
        out[("COFOG", "GF07")] = [_ar(iso3, "GF07", ["health"])]
        out[("COFOG", "GF09")] = [_ar(iso3, "GF09", ["education"])]
        out[("COFOG", "GF10")] = [gf10, _ar(iso3, "GF10", ["pensions", "ltc"])]
    if iso3 == "DEU":
        out[("ESA_REV", "R01")] = [_stsch(
            [("Tab 2", "Steuern vom Umsatz")],
            "Steuern vom Umsatz = Umsatzsteuer + Einfuhrumsatzsteuer -> D.211")]
        r03 = _stsch(
            [("Tab 2", "Lohnsteuer"), ("Tab 2", "veranl. Einkommensteuer"),
             ("Tab 2", "nicht veranl. St. v. Ertrag*"),
             ("Tab 2", "AbgSt. a. Zins- u. V.-ertr.")] + _SOLI_R03,
            "household income taxes incl. the Solidaritätszuschlag parts "
            "levied on them (payer-type split per Tab 8.2, §14)")
        r03.residual_method = config.residual_method(iso3, "R03")
        r04 = _stsch(
            [("Tab 2", "Körperschaftsteuer"), ("Tab 2", "Mindeststeuer"),
             ("Tab 7", "Gewerbesteuer brutto"),
             ("Tab 8.2", "- Körperschaftsteuer")],
            "corporate income taxes: KSt + Mindeststeuer + Gewerbesteuer "
            "(gross, D.51 corporations per the national tax list) + Soli on "
            "KSt (payer-type split per Tab 8.2, §14)")
        r04.residual_method = config.residual_method(iso3, "R04")
        out[("ESA_REV", "R03")] = [r03]
        out[("ESA_REV", "R04")] = [r04]
    if iso3 == "GBR":
        # OQ-6 partial unblock (D-S7-001/002): OBR EFO March 2026 receipts
        # composites (membership per the ONS national tax list evidence,
        # validated by measured §9.2 coverage) and the PESA MoD DEL plan.
        out[("ESA_REV", "R01")] = [_obr_receipts(
            ["VAT (net of VAT refunds)", "VAT refunds"],
            "D.211 = VAT plus VAT refunds (the anchor's accrued D.211 "
            "includes refunded VAT; measured 0.99 on the GG anchor)",
            residual=config.residual_method(iso3, "R01"))]
        out[("ESA_REV", "R02")] = [_obr_receipts(
            ["Fuel duties", "Stamp duty land tax", "Stamp taxes on shares",
             "Tobacco duties", "Alcohol duties", "Vehicle excise duties",
             "Air passenger duty", "Insurance premium tax",
             "Climate change levy and carbon price floor",
             "Environmental levies", "Emissions trading scheme", "Bank levy"],
            "D.2 minus D.211: production/product taxes per the national tax "
            "list; business rates come from EFO annex table A.5 (not in the "
            "databank), so the composite starts at FY 2024-25",
            extra_fy=R.obr_fy("annex-tables", "TA.5", "Business rates"),
            residual=config.residual_method(iso3, "R02"))]
        out[("ESA_REV", "R03")] = [_obr_receipts(
            ["Pay as your earn (PAYE) income tax",
             "Self assessed (SA) income tax", "Other income tax",
             "Capital gains tax"],
            "D.51 households incl. holding gains (D51M): income tax streams "
            "plus CGT per the national tax list",
            residual=config.residual_method(iso3, "R03"))]
        out[("ESA_REV", "R04")] = [_obr_receipts(
            ["Onshore corporation tax", "Offshore corporation tax",
             "Petroleum revenue tax", "Energy profits levy",
             "Diverted profits tax"],
            "D.51 corporations (D51O): CT onshore (incl. bank surcharge and "
            "EGL per the databank definition) + offshore + PRT + EPL + DPT",
            residual=config.residual_method(iso3, "R04"))]
        out[("ESA_REV", "R05")] = [_obr_receipts(
            ["Council tax", "Inheritance tax", "Licence fee receipts"],
            "partial composite for D.5-other + D.59 + D.91: council tax and "
            "licence fee (D.59) plus inheritance tax (D.91); no forecast "
            "exists for the remaining small D.59/D.91 items — coverage "
            "measured (C band, maximum_extension only)",
            residual=config.residual_method(iso3, "R05"))]
        # D12 chains: AMECO (later vintage) through 2027, OBR beyond
        out[("ESA_REV", "R06")].append(_obr_receipts(
            ["National insurance contributions (NICs)"],
            "NICs only — the anchor's D.61 additionally includes imputed "
            "(unfunded public service) and voluntary contributions, so the "
            "measured share sits in the C band; long-term leg beyond the "
            "AMECO D.61 horizon per D12"))
        # candidates recorded even where the concept mismatch is expected to
        # fail the bands: the non-application boundary is the documentation
        cg_di = R.obr_databank("Aggregates (£bn)",
                               "Central government debt interest")
        out[("COFOG", "GF01_7")].append(FcSource(
            source_id="OBR_EFO_LATEST", series=fy_to_cy(cg_di) * 1000.0,
            kind="level", horizon_year=2031, last_actual_year=2024,
            concept_note="OBR central government debt interest, net of APF "
                         "(PSF basis): differs from GG gross accrued D.41 by "
                         "the APF netting, LG interest and PSF/ESA recording "
                         "— measured share drifts 0.67-1.28 across the "
                         "overlap, outside every band",
            crosswalk_version=OBR_COFOG_XWALK,
            gdp_levels=_obr_gdp_levels(), gdp_source_id="OBR_EFO_LATEST",
            concept_flag="public_sector_perimeter",
            period_conversion_method="fy_weighted_quarters"))
        out[("ESA_REV", "R07")] = [_obr_receipts(
            ["Public sector interest and dividend receipts"],
            "PS interest AND dividends receivable vs the anchor's GG D.41 "
            "resources — dividends and the PS perimeter push the share "
            "outside the bands; recorded, not applied")]
        welfare = R.obr_fy("annex-tables", "TA.7", "Welfare spending")
        gf10_obr = FcSource(
            source_id="OBR_EFO_LATEST", series=fy_to_cy(welfare) * 1000.0,
            kind="level", horizon_year=2031, last_actual_year=2024,
            concept_note="EFO welfare spending (AME): dominant cash-benefit "
                         "component of GF10, but the EFO table starts at FY "
                         "2024-25 so the converted series has no year in "
                         "common with the GG anchor — coverage not "
                         "measurable (§9.2), not applied; a welfare series "
                         "in the PSF databank would fix this",
            crosswalk_version=OBR_COFOG_XWALK,
            gdp_levels=_obr_gdp_levels(), gdp_source_id="OBR_EFO_LATEST",
            concept_flag="public_sector_perimeter",
            period_conversion_method="fy_weighted_quarters",
            observation_type="proxy_forecast", max_only=True,
            residual_method=config.residual_method(iso3, "GF10"))
        out[("COFOG", "GF10")] = [gf10, gf10_obr]
        out[("COFOG", "GF02")] = [FcSource(
            source_id="HMT_PESA",
            series=fy_to_cy(R.obr_fy("chapter-1", "Table_1_9", "Defence",
                                     source_id="HMT_PESA")),
            # FY 2028-29 touches calendar 2029; V10 nets the conversion loss
            kind="level", horizon_year=2029, last_actual_year=2025,
            concept_note=PESA_NOTE, crosswalk_version=OBR_COFOG_XWALK,
            gdp_levels=_obr_gdp_levels(), gdp_source_id="OBR_EFO_LATEST",
            concept_flag="public_sector_perimeter",
            period_conversion_method="fy_weighted_quarters")]
    return out


# ---------- declarations (D7 and access notes; Gate 3) ----------

_D7_NOTE = ("D7: no official forecast identified anywhere (seed register and "
            "Stage 3 search: AMECO GG aggregates, AR 2024, DSM 2025, "
            "Steuerschätzung); strict and maximum end at the last actual")
_PDF_BLOCKED = ("identified source {src} is PDF-only; §11.4 manual ingestion "
                "requires an independent second keying unavailable to a "
                "single-agent session (OQ-5 precedent) — OQ-6; strict ends at "
                "the last actual")


def declarations_for(iso3: str) -> list[Declaration]:
    """One note per line that carries no strict forecast after Stage 3 (plus
    the totals, which are never extended). Lines with applied forecasts get
    their row from the build itself."""
    def d(cls, line, status, note):
        return Declaration(iso3, cls, line, status, note)

    out = [
        d("COFOG", "GF01", "no_official_forecast",
          "§7.9: GF01 total has no direct forecast source; strict ends at the "
          "last actual — maximum_extension carries the mandated GF01_7-growth "
          "proxy (grade D, coverage measured, residual_method recorded; "
          "D-S4-002)"),
        d("COFOG", "GF01_X", "no_official_forecast",
          "never forecast by construction (D10); derived only"),
        d("COFOG", "TE", "not_extended",
          "totals are envelopes (§6.1, D4): the envelope constrains V15 but "
          "is not published as a stitched TE path"),
        d("ESA_REV", "TR", "not_extended",
          "totals are envelopes (§6.1, D4): used in V15 only"),
        d("ESA_REV", "R07", "no_machine_readable_source",
          "no usable GG interest-receivable forecast: AMECO has no D.41 "
          "resources series (UYVG is subsidies); DSM publishes payable "
          "interest only; the OBR 'PS interest and dividend receipts' "
          "candidate (D-S7-003) mixes dividends and the PS perimeter into "
          "the line and measures outside every band — recorded, not "
          "applied; NI/PB forecast ledger therefore stays empty (§4.3)"),
        d("ESA_REV", "R08", "no_official_forecast", _D7_NOTE),
        d("ESA_REV", "R10", "no_official_forecast", _D7_NOTE),
    ]
    for line in ("GF03", "GF04", "GF05", "GF06", "GF08"):
        out.append(d("COFOG", line, "no_official_forecast", _D7_NOTE))
    if iso3 == "GBR":
        # OQ-6 partially unblocked 2026-09-03 (D-S7-001/002): the OBR EFO
        # March 2026 receipts composites and the PESA MoD DEL now carry
        # R01-R04 and GF02 in strict; what remains declared is below.
        out += [
            d("COFOG", "GF07", "source_blocked",
              "FRS July 2025 (hand-retrieved, D-S7-001) is thematic — "
              "pensions, balance sheet, climate — and carries no long-term "
              "health projection; the FRS edition with functional long-term "
              "projections (2024, or 2026 if published) is not in hand and "
              "obr.uk remains challenge-blocked (OQ-6); strict ends at the "
              "last actual"),
            d("COFOG", "GF09", "source_blocked",
              "as GF07: no education long-term projection in the FRS July "
              "2025 edition in hand (OQ-6); strict ends at the last actual"),
            d("COFOG", "GF10", "grade_below_strict",
              "maximum_extension carries the AMECO D.62 dominant-component "
              "proxy to 2027 (grade C, §7.8); the EFO welfare-spending "
              "series was measured as a longer C-band candidate but its "
              "table starts at FY 2024-25, leaving no year in common with "
              "the GG anchor to measure §9.2 coverage on — recorded, not "
              "applied (D-S7-003)"),
            d("ESA_REV", "R05", "grade_below_strict",
              "OBR council tax + inheritance tax + licence fee composite "
              "measured at 79% of the line (C) — applied in "
              "maximum_extension to 2030; the remaining D.59/D.91 items "
              "have no forecast anywhere (D7 lists R05 as partial); AMECO "
              "UTKG (11%, D) recorded, not applied"),
            d("ESA_REV", "R09", "no_machine_readable_source",
              "AMECO publishes no UK UTOG/UROG history (OQ-4 pattern) and "
              "the EFO receipts tables do not separate P.11+P.12+P.131 "
              "sales (GOS and 'other receipts' are different concepts) — "
              "no measurable composite"),
        ]
    if iso3 == "FRA":
        out += [
            d("COFOG", "GF02", "source_blocked",
              _PDF_BLOCKED.format(src="FRA_LPM_2030 (military programming law)")),
            d("COFOG", "GF10", "grade_below_strict",
              "AR pensions+LTC composite measured at 69% of GF10 (grade C: "
              "no official projection of family/housing/unemployment "
              "components) — no strict forecast; maximum_extension chains the "
              "AMECO D.62 proxy (to 2027) into the AR composite (to 2070) per "
              "D12, overlap divergence under the V16 threshold"),
            d("ESA_REV", "R01", "source_blocked",
              _PDF_BLOCKED.format(src="FRA_LPFP_PSTAB (prélèvements obligatoires)")),
            d("ESA_REV", "R02", "source_blocked",
              _PDF_BLOCKED.format(src="FRA_LPFP_PSTAB")),
            d("ESA_REV", "R03", "source_blocked",
              _PDF_BLOCKED.format(src="FRA_LPFP_PSTAB")),
            d("ESA_REV", "R04", "source_blocked",
              _PDF_BLOCKED.format(src="FRA_LPFP_PSTAB")),
            d("ESA_REV", "R05", "grade_below_strict",
              "AMECO UTKG covers 76% of the line (grade C) — no strict "
              "forecast; applied in maximum_extension as a §7.8 "
              "single-component proxy to 2027; D7 lists R05 as partial"),
        ]
    if iso3 == "DEU":
        out += [
            d("COFOG", "GF02", "source_blocked",
              _PDF_BLOCKED.format(src="DEU_BMF_FINPLAN (Epl. 14 + "
                                  "Sondervermögen Bundeswehr)")),
            d("COFOG", "GF10", "grade_below_strict",
              "AR pensions+LTC composite measured at 61% of GF10 (grade C); "
              "BMAS Rentenversicherungsbericht blocked (bmas.de egress, "
              "OQ-6) — no strict forecast; maximum_extension chains the AMECO "
              "D.62 proxy (to 2027) into the AR composite (to 2070) per D12"),
            d("ESA_REV", "R02", "no_machine_readable_source",
              "Steuerschätzung publishes Länder-/Gemeindesteuern only as "
              "cash aggregates mixing D.2, D.59 and D.91 — no ESA-complete "
              "component set for D.2 minus D.211; AMECO UTVG is total D.2 "
              "only"),
            d("ESA_REV", "R05", "grade_below_strict",
              "AMECO UTKG covers 34% of the line (D, not applied); "
              "Erbschaftsteuer is not separately published in the "
              "Steuerschätzung tables; D7 lists R05 as partial"),
        ]
    return out


# ---------- grading and chaining ----------

def _grade(src: FcSource, anchor: pd.Series, anchor_gdp: pd.Series
           ) -> tuple[str, float | None, int | None]:
    """(grade, coverage_share, coverage_share_year) at the last common year
    (§9.2). %-of-GDP sources are levelled with the anchor-vintage GDP for the
    measurement. A only for a direct forecast of the same ESA aggregate that
    reproduces the anchor within 0.5% (D-S3-002)."""
    if src.kind == "pct_gdp":
        levels = (src.series / 100.0).mul(anchor_gdp, fill_value=float("nan")).dropna()
    else:
        levels = src.series * src.unit_factor
    common = [y for y in anchor.index.intersection(levels.index)
              if levels[y] > 0 and anchor[y] > 0]
    if not common:
        return "D", None, None
    y = int(max(common))
    share = float(levels[y] / anchor[y])
    if src.direct_concept and abs(share - 1.0) <= 0.005:
        grade = "A"
    elif 0.9 <= share <= 1.1:
        grade = "B"
    elif 0.5 <= share < 0.9:
        grade = "C"
    else:
        grade = "D"
    return grade, round(share, 4), y


def _growth(src: FcSource, t: int) -> float | None:
    """Growth factor of the source at year t (§7.2, §7.5), None where §7.12
    stops the chain (missing, zero or negative source values)."""
    x = src.series
    if t not in x.index or (t - 1) not in x.index or x[t] <= 0 or x[t - 1] <= 0:
        return None
    g = float(x[t] / x[t - 1])
    if src.kind == "pct_gdp":
        if src.gdp_growth is None or t not in src.gdp_growth.index:
            return None
        g *= float(src.gdp_growth[t])
    return g


def extend_forward(iso3: str, classification: str, line_code: str,
                   anchor: pd.Series, sources: list[FcSource],
                   anchor_gdp: pd.Series) -> tuple[list[dict], list[dict]]:
    """Forward-stitch one line through its sources in D12 order. Returns
    (value rows, boundary records); §5 packaging happens in build. Only A/B
    sources are applied at Stage 3 (strict tier, §9); C and D measurements
    are recorded as non-applications."""
    from ggfiscal import config

    v16_threshold = config.tolerances().get("v16_overlap_divergence", 0.02)
    # OQ-7 adjudications (D-S8-001): joins the committee has approved despite
    # above-threshold divergence — application changes, V16 keeps warning
    approved_joins = {(a["iso3"], a["line_code"], a["incoming_source"])
                      for a in config.tolerances().get("v16_approved_joins", [])}
    rows, boundaries = [], []
    if anchor.empty:
        return rows, boundaries
    T = int(anchor.index.max())
    value_prev = float(anchor[T])
    frontier = T
    outgoing = "anchor"
    applied_sources: list[FcSource] = []
    gdp_prev = float(anchor_gdp[T]) if T in anchor_gdp.index else None
    for src in sources:
        grade, share, share_year = _grade(src, anchor, anchor_gdp)
        scope_prefix = ""
        # D12: a long-term leg whose growth diverges from the short-term
        # source beyond the V16 threshold in their overlap years is NOT
        # auto-joined — recorded and flagged for committee review (OQ-7),
        # unless the committee has approved that exact join in config
        if applied_sources:
            divs = overlap_divergence(iso3, classification, line_code,
                                      [applied_sources[-1], src])
            worst = max((abs(d["divergence"]) for d in divs), default=0.0)
            if worst > v16_threshold \
                    and (iso3, line_code, src.source_id) in approved_joins:
                scope_prefix = (f"D12/V16: overlap divergence up to "
                                f"{worst:+.4f} exceeds the {v16_threshold} "
                                "threshold; joined under committee approval "
                                "(OQ-7 resolution, D-S8-001) — V16 keeps "
                                "warning on the seam; ")
            elif worst > v16_threshold:
                boundaries.append({
                    "iso3": iso3, "classification": classification,
                    "line_code": line_code, "boundary_year": frontier,
                    "outgoing_source": outgoing, "incoming_source": src.source_id,
                    "anchor_value_lcu_mn": value_prev, "growth_applied": None,
                    "scope": (f"D12/V16: overlap growth divergence up to "
                              f"{worst:+.4f} vs {outgoing} exceeds the "
                              f"{v16_threshold} threshold — long-term leg "
                              "withheld pending committee review (OQ-7); "
                              + src.concept_note),
                    "break_flag": False, "grade": grade,
                    "crosswalk_version": src.crosswalk_version,
                    "coverage_share": share, "coverage_share_year": share_year,
                    "variants": "not_applied_v16_divergence",
                })
                continue
        if grade == "D" and not src.mandated:
            boundaries.append({
                "iso3": iso3, "classification": classification,
                "line_code": line_code, "boundary_year": frontier,
                "outgoing_source": outgoing, "incoming_source": src.source_id,
                "anchor_value_lcu_mn": value_prev, "growth_applied": None,
                "scope": src.concept_note, "break_flag": False,
                "grade": grade, "crosswalk_version": src.crosswalk_version,
                "coverage_share": share, "coverage_share_year": share_year,
                "variants": "not_applied_grade_D",
            })
            continue
        # variant routing (D-S4-001): C-grade and §7.8 proxies (and the §7.9
        # mandated D) are maximum_extension only; A/B direct/composite rows
        # enter both variants
        max_only = grade in ("C", "D") or src.max_only
        variants_label = "maximum_only" if max_only else "strict+maximum"
        t = frontier + 1
        started = False
        gdp_running: float | None = None
        while t <= src.horizon_year:
            growth = _growth(src, t)
            if growth is None:
                break
            value_t = value_prev * growth
            # per-source GDP for the row (§6.3/§7.5): source levels where
            # published, else a constructed path chained from anchor GDP at T
            # through the source's own nominal-growth factors (all of T+1..t,
            # not just the years this source contributes values for)
            if src.gdp_levels is not None and t in src.gdp_levels.index:
                gdp_t = float(src.gdp_levels[t])
            elif src.kind == "pct_gdp" and gdp_prev is not None \
                    and src.gdp_growth is not None:
                if gdp_running is None:
                    gdp_running = gdp_prev
                    chain = [s for s in range(T + 1, t + 1)]
                    if all(s in src.gdp_growth.index for s in chain):
                        for s in chain:
                            gdp_running *= float(src.gdp_growth[s])
                    else:
                        gdp_running = None
                elif t in src.gdp_growth.index:
                    gdp_running *= float(src.gdp_growth[t])
                else:
                    gdp_running = None
                gdp_t = gdp_running
            else:
                gdp_t = None
            is_forecast = t > src.last_actual_year
            rows.append({
                "year": t, "value": value_t, "growth_rate": growth,
                "source": src, "grade": grade, "coverage_share": share,
                "coverage_share_year": share_year, "anchor_year": T,
                "anchor_value": float(anchor[T]), "is_forecast": is_forecast,
                "gdp_lcu_mn": gdp_t,
                "variants": (("maximum_extension",) if max_only
                             else ("strict", "maximum_extension")),
            })
            if not started:
                boundaries.append({
                    "iso3": iso3, "classification": classification,
                    "line_code": line_code, "boundary_year": t,
                    "outgoing_source": outgoing, "incoming_source": src.source_id,
                    "anchor_value_lcu_mn": value_prev, "growth_applied": growth,
                    "scope": scope_prefix + src.concept_note, "break_flag": False,
                    "grade": grade, "crosswalk_version": src.crosswalk_version,
                    "coverage_share": share, "coverage_share_year": share_year,
                    "variants": variants_label,
                })
                started = True
            value_prev = value_t
            frontier = t
            t += 1
        if started:
            outgoing = src.source_id
            applied_sources.append(src)
    return rows, boundaries


def overlap_divergence(iso3: str, classification: str, line_code: str,
                       sources: list[FcSource]) -> list[dict]:
    """V16 / D12: annual growth divergence between consecutive sources in the
    years both cover. Reported per overlap year; the threshold lives in the
    validator."""
    out = []
    for st, lt in zip(sources, sources[1:]):
        years = [t for t in range(2020, 2101)
                 if _growth(st, t) is not None and _growth(lt, t) is not None
                 and t <= st.horizon_year]
        for t in years:
            g_st, g_lt = _growth(st, t), _growth(lt, t)
            out.append({"iso3": iso3, "classification": classification,
                        "line_code": line_code, "year": t,
                        "st_source": st.source_id, "lt_source": lt.source_id,
                        "st_growth": g_st, "lt_growth": g_lt,
                        "divergence": g_lt - g_st})
    return out
