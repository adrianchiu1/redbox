"""Stage 1 build: anchors -> canonical history, both trees, §5 long format.

Every value is an anchor cell or an arithmetic combination of anchor cells
from the same institution (observation_type anchor_actual / derived_actual,
grade A). Nothing is stitched, filled, or scaled (D13); a year missing in the
anchor is simply absent (§7.12, V14). Both variants carry identical history at
this stage — they diverge when forecasts arrive (Stages 3-4).

Line construction (documented against §4):
  GF01..GF10   anchor COFOG Level I, na_item TE
  GF01_7       anchor COFOG Level II 01.7 (D10; level2 per D-S0-008)
  GF01_X       GF01 - GF01_7, derived, never forecast
  GF10_2/GF10_5/GF04_5 and R02_A/R06_E/R06_H: further Level II splits with
               remainders GF10_X/GF04_X/R02_X/R06_X (config.level2_splits(),
               D-S13-002/005) — one config entry each
  TE (COFOG)   the COFOG table's own total row (V2 tests Level I against it)
  R01          D211            R02  D2 - D211
  R03          D51 households (FRA/DEU D51A_C1; GBR D51M — incl. holding gains)
  R04          D51 corporations (D51B_C2 / D51O)
  R05          D5 - R03 - R04 + D91   (D59 is inside D5)
  R06          D61             R07  D41 resources (gross, accrued)
  R08          D4 - D41 resources     R09  P11 + P12 + P131
  R10          D39 + D7 + D92 + D99 resources (GBR: D39R + D7 + (D9 - D91))
  TR (ESA_REV) the anchor's own TR (V22 tests R01..R10 against it)

The balance ledger (TR, TE, NLB, NI, PB) is written as a compact wide file
per §11.6 deliverable 3, from the balance anchor's own TR/TE/B9 so V23 is an
exact within-source identity; NI = GF01_7 - R07 exists only where both sides
do (complete_both_sides flag).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import pandas as pd

from ggfiscal import config
from ggfiscal.model import COLUMNS, SCHEMA
from ggfiscal.standardise import readers as R


def _release(source_id: str) -> tuple[str, str]:
    ver = (config.sources().get(source_id, {}).get("verification") or {})
    return (str(ver.get("last_update_observed", "") or ""),
            str(ver.get("checked", "") or ""))


def _sum_codes(series: list[pd.Series]) -> pd.Series:
    """Sum of anchor cells where a secondary cell may be absent in some years
    (D.2122C is not published for every country-year): the first code sets
    the year set, later codes add where present."""
    total = series[0].copy()
    for extra in series[1:]:
        total = total.add(extra.reindex(total.index, fill_value=0.0), fill_value=0.0)
    return total.dropna()


def _revenue_level2(iso3: str, code: str, meta: dict) -> tuple[pd.Series, str, str]:
    """(series, source_id, concept note) for a revenue Level II line from its
    lines.yaml anchor cells, served by the country's anchor family (ONS ESA
    Table 2 receivable rows or NTL table 9 codes; gov_10a_main or
    gov_10a_taxag items). A detail-table cell sits in a different table from
    the parent's aggregate, so its transmission-timing drift (D-S1-002) lands
    in the derived remainder, never in the identity."""
    return config.family(iso3).revenue_level2(iso3, meta)


def _zero_series(years) -> pd.Series:
    """A structural zero (D20): 0.0 in every given year."""
    return pd.Series(0.0, index=sorted(int(y) for y in years), dtype=float)


def structural_zero_note(reason: str) -> str:
    return f"structural zero (D20): {reason}"


def anchor_series(iso3: str) -> dict[tuple[str, str], dict]:
    """(classification, line_code) -> {series, source_id, observation_type,
    line_level, concept_flag, notes} — anchor cells only. Lines the country
    declares in `lines_absent` (D20) are zero in every anchor year of their
    tree (the years the tree's total covers), typed structural_zero, grade A,
    with the declared reason as the note; the identities run over them
    unchanged. Empty for GBR/FRA/DEU."""
    L = config.lines()
    absent = config.absent_lines(iso3)
    exp_meta = L["expenditure"]
    rev_meta = L["revenue"]

    def m(cls, code, series, source_id, obs, level, label, concept="", notes="",
          per_year=None):
        return (cls, code), {"series": series, "source_id": source_id,
                             "observation_type": obs, "line_level": level,
                             "line_label": label, "concept_flag": concept,
                             "notes": notes, "per_year": per_year or {}}

    out = {}
    # every anchor cell comes from the country's anchor family (D27, R0):
    # the COFOG table, the main-aggregates table (revenue lines per the D1
    # mapping, the ESA_EXP items, the balance totals) and the tax detail
    fam = config.family(iso3)
    cof = lambda c: fam.cofog(iso3, c)  # noqa: E731
    exp_src = fam.expenditure_source
    rev_src = fam.revenue_source      # the flow the revenue rows come from (= main_source
    #                                   for ONS/Eurostat; OECD_T12_REV for the OECD family)
    rev = fam.revenue_lines(iso3)
    tr = fam.revenue_total(iso3)
    te_cofog = fam.cofog_total(iso3)

    for n in range(1, 11):
        code = f"GF{n:02d}"
        out.update([m("COFOG", code, cof(code), exp_src,
                      "anchor_actual", "1", exp_meta[code]["label"])])
    out.update([m("COFOG", "TE", te_cofog, exp_src, "anchor_actual", "total",
                  "Total expenditure",
                  notes="the COFOG table's own total row (V2 baseline)")])
    # --- ESA_EXP: expenditure by economic type (D-S13-003), from the same
    # institution's main-aggregates table: gov_10a_main payable items (FRA,
    # DEU), ONS ESA Table 2 payable rows (GBR). Sums are derived_actual;
    # the identity E01..E09 = TE_ESA is exact by construction (V2).
    esa_meta = L["expenditure_esa"]
    esa_src = fam.esa_exp_source
    for code, meta in esa_meta.items():
        plus, minus = fam.esa_exp_parts(iso3, meta)
        series = plus[0]
        for s in plus[1:]:
            series = series + s
        for s in minus:
            series = series - s
        series = series.dropna()
        n_parts = len(plus) + len(minus)
        obs = "anchor_actual" if n_parts == 1 else "derived_actual"
        level = "total" if config.is_total(meta) else "1"
        notes = "" if n_parts == 1 else f"derived {meta['esa']} (sum of the anchor's own items)"
        concept = "d41_gross_accrued" if "d41_gross_accrued" in meta.get("concept_flags", []) else ""
        out.update([m("ESA_EXP", code, series, esa_src, obs, level, meta["label"],
                      concept=concept, notes=notes)])
    for code, (series, obs, notes) in rev.items():
        concept = "d41_gross_accrued" if code == "R07" else ""
        out.update([m("ESA_REV", code, series, rev_src, obs, "1",
                      rev_meta[code]["label"], concept=concept, notes=notes)])
    out.update([m("ESA_REV", "TR", tr, rev_src, "anchor_actual", "total",
                  "Total revenue")])
    # D20 structural zeros on Level I / revenue lines: zero in every anchor
    # year of the tree, from the tree's total's source (Level II lines are
    # handled inside the split loop, over the parent's years)
    for (cls, code), reason in absent.items():
        meta = L[config.TREES[cls]][code]
        if str(meta.get("level", "1")) == "2":
            continue
        tot = out[(cls, config.total_code(cls))]
        out.update([m(cls, code, _zero_series(tot["series"].index), tot["source_id"],
                      "structural_zero", str(meta.get("level", "1")), meta["label"],
                      notes=structural_zero_note(reason))])
    # Level II splits (config.level2_splits(): GF01_7/GF01_X per D10,
    # GF10_2 per D-S13-002, GF10_5/GF04_5 and the revenue splits R02_A,
    # R06_E/R06_H per D-S13-005). Each Level II line comes from the anchor's
    # own table (COFOG Level II; a taxag/NTL or main/T2 cell for revenue);
    # the remainder is parent minus every Level II line, derived and never
    # forecast. D10's fallback applies to the interest line only: years the
    # anchor covers (parent exists) but Level II lacks are filled from the
    # same institution's GG D.41 payable, level2_proxy_actual, grade B (DEU
    # 1995-99). Other groups simply start where their cell starts.
    for split in config.level2_splits():
        cls, parent, rem = split["classification"], split["parent"], split["remainder"]
        tree_meta = L[config.TREES[cls]]
        src_id = exp_src if cls == "COFOG" else rev_src
        parent_series = out[(cls, parent)]["series"]
        l2_series_all: dict[str, pd.Series] = {}
        fallback_years: dict[int, dict] = {}
        for l2 in split["level2s"]:
            meta = split["meta"][l2]
            per_year: dict[int, dict] = {}
            interest = l2 == "GF01_7"
            if (cls, l2) in absent:
                series = _zero_series(parent_series.index)
                src_line = src_id
                concept_txt = structural_zero_note(absent[(cls, l2)])
            elif cls == "COFOG":
                # the family's own Level II cell; None where the family
                # publishes no Level II table (kickoff §11.3: the D26 proxy
                # path, which is U1 work — nothing is built here, so the
                # remainder stays empty and the D10 fallback below still
                # serves the interest line)
                l2_cell = fam.level2(iso3, l2)
                series = l2_cell if l2_cell is not None else pd.Series(dtype=float)
                cofog_code = meta["eurostat_cofog"]
                concept_txt = (f"COFOG {cofog_code[2:4]}.{int(cofog_code[4:6])} from the "
                               "anchor's Level II table")
                src_line = src_id
            else:
                series, src_line, concept_txt = _revenue_level2(iso3, l2, meta)
            if meta["fallback"] == "d41_payable" and (cls, l2) not in absent:
                d41pay = fam.d41_payable(iso3)
                for y in sorted(set(parent_series.index) - set(series.index)):
                    if y in d41pay.index:
                        series.loc[y] = float(d41pay[y])
                        per_year[y] = {
                            "observation_type": "level2_proxy_actual",
                            "quality_grade": meta["grade_on_fallback"],
                            "notes": "D10 fallback: GG gross D.41 payable in place of "
                                     "missing Level II 01.7 (same institution)"}
                fallback_years.update(per_year)
            series = series.sort_index()
            l2_series_all[l2] = series
            out.update([m(cls, l2, series, src_line,
                          "structural_zero" if (cls, l2) in absent else "anchor_actual", "2",
                          tree_meta[l2]["label"],
                          concept="d41_gross_accrued" if interest else "",
                          notes=concept_txt + (" (D10)" if interest else ""),
                          per_year=per_year)])
        remainder = parent_series.copy()
        for series in l2_series_all.values():
            remainder = remainder - series
        remainder = remainder.dropna()
        x_per_year = {y: {"observation_type": "derived_actual",
                          "quality_grade": v["quality_grade"],
                          "notes": f"{parent} minus a D10 proxy year"}
                      for y, v in fallback_years.items()}
        out.update([m(cls, rem, remainder, src_id, "derived_actual", "derived",
                      tree_meta[rem]["label"],
                      notes=f"derived {tree_meta[rem]['derived']}; never forecast",
                      per_year=x_per_year)])
    return out


def gdp_series(iso3: str) -> tuple[pd.Series, str]:
    """(nominal GDP, source_id) from the country's anchor family."""
    return config.family(iso3).gdp(iso3)


def _imf_recon(iso3: str, classification: str, line_code: str) -> pd.Series:
    """IMF GFS series for the same cell: COFOG Level I and Level II lines
    (≈identical concept) and the GFSM expense items registered for ESA_EXP
    lines in lines.yaml (`gfs_soo`; close but not identical concepts — the
    V1 comparison is WARN-tier)."""
    if classification == "COFOG":
        meta = config.tree_lines("COFOG").get(line_code, {})
        if meta.get("gfs_indicator"):
            return R.gfs_series(iso3, "cofog", meta["gfs_indicator"])
        if line_code.startswith("GF") and line_code[2:].isdigit():
            return R.gfs_series(iso3, "cofog", f"{line_code}_T")
        return pd.Series(dtype=float)
    if classification == "ESA_EXP":
        ind = config.tree_lines("ESA_EXP").get(line_code, {}).get("gfs_soo")
        return R.gfs_series(iso3, "soo", ind) if ind else pd.Series(dtype=float)
    return pd.Series(dtype=float)


_RS_HEADINGS = {"R01": "T_5111", "R03": "T_1100", "R04": "T_1200", "R06": "T_2000",
                "R02_A": "T_5121", "R06_E": "T_2200", "R06_H": "T_2100"}


def _oecd_recon(iso3: str, classification: str, line_code: str) -> pd.Series:
    if classification != "ESA_REV" or line_code not in _RS_HEADINGS:
        return pd.Series(dtype=float)
    return R.oecd_rs_heading(iso3, _RS_HEADINGS[line_code])


FY_CY_BRIDGE_COLUMNS = [
    "iso3", "classification", "year", "fy_label", "te_fy_lcu_mn", "te_cy_lcu_mn",
    "gap_lcu_mn", "timing_component_lcu_mn", "residual_lcu_mn",
    "fy_source_id", "cy_source_id", "source_vintage", "run_id",
]


def fy_cy_timing_component(iso3: str, year: int) -> float | None:
    """D19: the timing component of the FY/CY gap on total expenditure,
    derived from the institution's quarterly general-government accounts.
    No quarterly reader exists yet (the ESRI reader arrives with Stage J1),
    so the component is None and the whole gap is published as residual —
    never allocated."""
    return None


def fy_cy_bridge_rows(iso3: str, series_map: dict, run_id: str) -> list[dict]:
    """D19: for every FY-labelled tree of the country, TE on the FY basis
    (the tree's own total, labelled by the starting year) beside TE on the
    CY basis (the balance anchor's TE, from the anchor family), the gap, the
    quarterly-derived timing component where a reader provides one, and
    the residual. Additive per year (V42). Empty for a country whose trees
    are all CY (GBR, FRA, DEU)."""
    rows = []
    fam = config.family(iso3)
    for cls in config.TREES:
        if config.tree_period_basis(iso3, cls) != "FY":
            continue
        total = config.total_code(cls)
        te_fy = series_map[(cls, total)]["series"]
        fy_src = series_map[(cls, total)]["source_id"]
        te_cy = fam.totals(iso3)["TE"]
        cy_src = fam.esa_exp_source
        release, vintage = _release(fy_src)
        for year in sorted(int(y) for y in te_fy.index):
            cy_v = float(te_cy[year]) if year in te_cy.index else None
            fy_v = float(te_fy[year])
            gap = (fy_v - cy_v) if cy_v is not None else None
            timing = fy_cy_timing_component(iso3, year)
            residual = (gap - (timing or 0.0)) if gap is not None else None
            rows.append({"iso3": iso3, "classification": cls, "year": year,
                         "fy_label": config.fy_label(iso3, year, cls),
                         "te_fy_lcu_mn": fy_v, "te_cy_lcu_mn": cy_v, "gap_lcu_mn": gap,
                         "timing_component_lcu_mn": timing, "residual_lcu_mn": residual,
                         "fy_source_id": fy_src, "cy_source_id": cy_src,
                         "source_vintage": vintage, "run_id": run_id})
    return rows


def build_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build(run_id: str | None = None) -> dict[str, Path]:
    from ggfiscal.stitch.backward import extend_line, extensions_for

    run_id = run_id or build_run_id()
    canonical = config.repo_root() / "data" / "canonical"
    canonical.mkdir(parents=True, exist_ok=True)
    currency = {c: v["currency"] for c, v in config.countries().items()}

    frames: dict[str, list[dict]] = {cls: [] for cls in config.TREES}
    total_codes = {cls: config.total_code(cls) for cls in config.TREES}
    ledger_rows: list[dict] = []
    boundary_rows: list[dict] = []
    forecast_boundary_rows: list[dict] = []
    declaration_rows: list[dict] = []
    bridge_rows: list[dict] = []
    for iso3 in config.COUNTRIES:
        series_map = anchor_series(iso3)
        gdp, gdp_src = gdp_series(iso3)
        bridge_rows += fy_cy_bridge_rows(iso3, series_map, run_id)
        # each tree's share denominator is its own total (TE, TE_ESA, TR)
        totals = {cls: series_map[(cls, code)]["series"] for cls, code in total_codes.items()}
        total_srcs = {cls: series_map[(cls, code)]["source_id"]
                      for cls, code in total_codes.items()}
        te = totals["COFOG"]
        for (classification, line_code), meta in series_map.items():
            s = meta["series"]
            imf = _imf_recon(iso3, classification, line_code)
            rs = _oecd_recon(iso3, classification, line_code)
            total = totals[classification]
            total_src = total_srcs[classification]
            release, vintage = _release(meta["source_id"])
            for year, value in s.items():
                year = int(year)
                override = meta.get("per_year", {}).get(year, {})
                obs_type = override.get("observation_type", meta["observation_type"])
                grade = override.get("quality_grade", "A")
                notes = override.get("notes", meta["notes"]) or None
                gdp_v = float(gdp[year]) if year in gdp.index else None
                tot_v = (float(total[year])
                         if line_code != total_codes[classification]
                         and year in total.index else None)
                imf_v = float(imf[year]) if year in imf.index else None
                rs_v = float(rs[year]) if year in rs.index else None
                for variant in ("strict", "maximum_extension"):
                    frames[classification].append({
                        "series_id": f"{iso3}_{line_code}_{variant}",
                        "iso3": iso3, "classification": classification,
                        "line_code": line_code, "line_level": meta["line_level"],
                        "line_label": meta["line_label"], "year": year,
                        "native_period": config.fy_label(iso3, year, classification),
                        "source_period_basis": config.tree_period_basis(iso3, classification),
                        "value_lcu_mn": float(value), "currency": currency[iso3],
                        "gdp_lcu_mn": gdp_v, "gdp_source_id": gdp_src,
                        "pct_gdp": round(100 * value / gdp_v, 6) if gdp_v else None,
                        "total_lcu_mn": tot_v, "total_source_id": total_src,
                        "pct_total": round(100 * value / tot_v, 6) if tot_v else None,
                        "series_variant": variant,
                        "observation_type": obs_type,
                        "anchor_source": meta["source_id"], "anchor_year": float(year),
                        "anchor_value": float(value),
                        "growth_source_id": None, "growth_rate": None,
                        "residual_method": None, "interpolation_method": None,
                        "period_conversion_method": None,
                        "coverage_share": None, "coverage_share_year": None,
                        "quality_grade": grade, "crosswalk_version": None,
                        "source_id": meta["source_id"],
                        "source_release_date": release, "source_vintage": vintage,
                        "source_status": "current", "scenario_label": None,
                        "concept_flag": meta["concept_flag"] or None,
                        "imf_value": imf_v,
                        "imf_diff_pct": (round(100 * (imf_v - value) / value, 4)
                                         if imf_v is not None and value else None),
                        "oecd_rs_value": rs_v,
                        "oecd_rs_diff_pct": (round(100 * (rs_v - value) / value, 4)
                                             if rs_v is not None and value else None),
                        "is_interpolated": False, "is_period_converted": False,
                        "is_forecast": False, "run_id": run_id,
                        "notes": notes,
                    })
        # --- Stage 2: backward extension (§7.3-7.4, D6, D15) ---
        stitched_vals: dict[str, dict[tuple[str, str], dict[int, tuple[float, str]]]] = {
            "strict": {}, "maximum_extension": {}}
        absent = config.absent_lines(iso3)
        for (classification, line_code), sources in extensions_for(iso3).items():
            meta = series_map.get((classification, line_code))
            if meta is None or (classification, line_code) in absent:
                continue   # a structural zero is never extended (D20)
            ext_rows, bnds = extend_line(iso3, classification, line_code,
                                         meta["series"], sources)
            boundary_rows += bnds
            for er in ext_rows:
                src = er["source"]
                release, vintage = _release(src.source_id)
                year = er["year"]
                gdp_v = float(gdp[year]) if year in gdp.index else None
                variants = (("strict", "maximum_extension") if er["grade"] == "B"
                            else ("maximum_extension",))
                for variant in variants:
                    stitched_vals[variant].setdefault((classification, line_code), {})[
                        year] = (er["value"], er["grade"])
                    frames[classification].append({
                        "series_id": f"{iso3}_{line_code}_{variant}",
                        "iso3": iso3, "classification": classification,
                        "line_code": line_code, "line_level": meta["line_level"],
                        "line_label": meta["line_label"], "year": year,
                        "native_period": config.fy_label(iso3, year, classification),
                        "source_period_basis": config.tree_period_basis(iso3, classification),
                        "value_lcu_mn": er["value"], "currency": currency[iso3],
                        "gdp_lcu_mn": gdp_v, "gdp_source_id": gdp_src,
                        "pct_gdp": (round(100 * er["value"] / gdp_v, 6)
                                    if gdp_v else None),
                        "total_lcu_mn": None, "total_source_id": None,
                        "pct_total": None,
                        "series_variant": variant,
                        "observation_type": "stitched_actual",
                        "anchor_source": meta["source_id"],
                        "anchor_year": float(er["anchor_year"]),
                        "anchor_value": er["anchor_value"],
                        "growth_source_id": src.source_id,
                        "growth_rate": er["growth_rate"],
                        "residual_method": None, "interpolation_method": None,
                        "period_conversion_method": None,
                        "coverage_share": er["coverage_share"],
                        "coverage_share_year": (float(er["coverage_share_year"])
                                                if er["coverage_share_year"] else None),
                        "quality_grade": er["grade"], "crosswalk_version":
                            src.crosswalk_version,
                        "source_id": src.source_id,
                        "source_release_date": release, "source_vintage": vintage,
                        "source_status": "current", "scenario_label": None,
                        "concept_flag": src.concept_flag or None,
                        "imf_value": None, "imf_diff_pct": None,
                        "oecd_rs_value": None, "oecd_rs_diff_pct": None,
                        "is_interpolated": False, "is_period_converted": False,
                        "is_forecast": False, "run_id": run_id,
                        "notes": src.concept_note,
                    })
        # --- Stage 3: forward extension, strict forecasts (§7.2, §12 Stage 3) ---
        # A/B rows only; strict rows are mirrored into maximum_extension so the
        # strict set stays a subset (V9); C/D measurements are recorded in
        # forecast_boundaries.csv without value rows (Stage 4 decides the Cs).
        from ggfiscal.forecast.forward import declarations_for, extend_forward, forecasts_for

        declaration_rows.extend(dataclasses.asdict(dec) for dec in declarations_for(iso3))
        declaration_rows.extend(
            {"iso3": iso3, "classification": cls, "line_code": code,
             "status": "structural_zero", "note": structural_zero_note(reason)}
            for (cls, code), reason in absent.items())
        for (classification, line_code), sources in forecasts_for(iso3).items():
            meta = series_map.get((classification, line_code))
            if meta is None or (classification, line_code) in absent:
                continue   # a structural zero is never forecast (D20)
            fc_rows, fbnds = extend_forward(iso3, classification, line_code,
                                            meta["series"], sources, gdp)
            forecast_boundary_rows += fbnds
            for er in fc_rows:
                src = er["source"]
                release, vintage = _release(src.source_id)
                year = er["year"]
                gdp_v = er["gdp_lcu_mn"]
                obs_type = (src.observation_type if er["is_forecast"]
                            else "stitched_actual")
                for variant in er["variants"]:
                    frames[classification].append({
                        "series_id": f"{iso3}_{line_code}_{variant}",
                        "iso3": iso3, "classification": classification,
                        "line_code": line_code, "line_level": meta["line_level"],
                        "line_label": meta["line_label"], "year": year,
                        "native_period": config.fy_label(iso3, year, classification),
                        "source_period_basis": config.tree_period_basis(iso3, classification),
                        "value_lcu_mn": er["value"], "currency": currency[iso3],
                        "gdp_lcu_mn": gdp_v, "gdp_source_id": src.gdp_source_id or None,
                        "pct_gdp": (round(100 * er["value"] / gdp_v, 6)
                                    if gdp_v else None),
                        "total_lcu_mn": None, "total_source_id": None,
                        "pct_total": None,
                        "series_variant": variant,
                        "observation_type": obs_type,
                        "anchor_source": meta["source_id"],
                        "anchor_year": float(er["anchor_year"]),
                        "anchor_value": er["anchor_value"],
                        "growth_source_id": src.source_id,
                        "growth_rate": er["growth_rate"],
                        "residual_method": src.residual_method,
                        "interpolation_method": src.interpolation_method,
                        "period_conversion_method": src.period_conversion_method,
                        "coverage_share": er["coverage_share"],
                        "coverage_share_year": (float(er["coverage_share_year"])
                                                if er["coverage_share_year"] else None),
                        "quality_grade": er["grade"],
                        "crosswalk_version": src.crosswalk_version,
                        "source_id": src.source_id,
                        "source_release_date": release, "source_vintage": vintage,
                        "source_status": "current",
                        "scenario_label": src.scenario_label,
                        "concept_flag": src.concept_flag or None,
                        "imf_value": None, "imf_diff_pct": None,
                        "oecd_rs_value": None, "oecd_rs_diff_pct": None,
                        "is_interpolated": src.interpolation_method is not None,
                        "is_period_converted": src.period_conversion_method is not None,
                        "is_forecast": er["is_forecast"], "run_id": run_id,
                        "notes": src.concept_note,
                    })
        # Level II remainders in stitched years: derive where the parent and
        # every Level II line were stitched (D10, D-S13-002/005), any tree
        for variant, vals in stitched_vals.items():
            for split in config.level2_splits():
                cls, rem = split["classification"], split["remainder"]
                parent_v = vals.get((cls, split["parent"]), {})
                l2_vs = [vals.get((cls, c), {}) for c in split["level2s"]]
                meta_x = series_map[(cls, rem)]
                years = set(parent_v)
                for lv in l2_vs:
                    years &= set(lv)
                for year in sorted(years):
                    vp, gp = parent_v[year]
                    value, grade = vp, gp
                    for lv in l2_vs:
                        vl, gl = lv[year]
                        value -= vl
                        grade = max(grade, gl)  # worst grade ('C' > 'B' lexically)
                    gdp_v = float(gdp[year]) if year in gdp.index else None
                    frames[cls].append({
                        "series_id": f"{iso3}_{rem}_{variant}",
                        "iso3": iso3, "classification": cls,
                        "line_code": rem, "line_level": "derived",
                        "line_label": meta_x["line_label"], "year": year,
                        "native_period": config.fy_label(iso3, year, cls),
                        "source_period_basis": config.tree_period_basis(iso3, cls),
                        "value_lcu_mn": value, "currency": currency[iso3],
                        "gdp_lcu_mn": gdp_v, "gdp_source_id": gdp_src,
                        "pct_gdp": round(100 * value / gdp_v, 6) if gdp_v else None,
                        "total_lcu_mn": None, "total_source_id": None, "pct_total": None,
                        "series_variant": variant, "observation_type": "derived_actual",
                        "anchor_source": meta_x["source_id"], "anchor_year": None,
                        "anchor_value": None, "growth_source_id": None,
                        "growth_rate": None, "residual_method": None,
                        "interpolation_method": None, "period_conversion_method": None,
                        "coverage_share": None, "coverage_share_year": None,
                        "quality_grade": grade, "crosswalk_version": None,
                        "source_id": meta_x["source_id"],
                        "source_release_date": _release(meta_x["source_id"])[0],
                        "source_vintage": _release(meta_x["source_id"])[1],
                        "source_status": "current", "scenario_label": None,
                        "concept_flag": None,
                        "imf_value": None, "imf_diff_pct": None,
                        "oecd_rs_value": None, "oecd_rs_diff_pct": None,
                        "is_interpolated": False, "is_period_converted": False,
                        "is_forecast": False, "run_id": run_id,
                        "notes": f"derived {split['parent']} - "
                                 f"{' - '.join(split['level2s'])} in backward-stitched "
                                 "years (D10 / D-S13-005)",
                    })
        # balance ledger from the balance anchor's own TR/TE/B9 (V23 exact)
        fam = config.family(iso3)
        totals_b = fam.totals(iso3)
        btr, bte, b9 = totals_b["TR"], totals_b["TE"], totals_b["B9"]
        bal_src = fam.balance_source
        gf017 = series_map[("COFOG", "GF01_7")]["series"]
        r07 = series_map[("ESA_REV", "R07")]["series"]
        for year in sorted(set(btr.index) & set(bte.index)):
            year = int(year)
            ni = (float(gf017[year] - r07[year])
                  if year in gf017.index and year in r07.index else None)
            nlb = float(btr[year] - bte[year])
            for variant in ("strict", "maximum_extension"):
                ledger_rows.append({
                    "iso3": iso3, "year": year, "series_variant": variant,
                    "tr_lcu_mn": float(btr[year]), "te_lcu_mn": float(bte[year]),
                    "nlb_lcu_mn": nlb,
                    "b9_anchor_lcu_mn": float(b9[year]) if year in b9.index else None,
                    "ni_lcu_mn": ni,
                    "pb_lcu_mn": (nlb + ni) if ni is not None else None,
                    "complete_both_sides": ni is not None,
                    "source_id": bal_src, "run_id": run_id,
                })

    out: dict[str, Path] = {}
    for classification, stem in config.STEMS.items():
        df = pd.DataFrame(frames[classification], columns=COLUMNS)
        df = SCHEMA.validate(df)
        for variant in ("strict", "maximum_extension"):
            sub = df[df["series_variant"] == variant].reset_index(drop=True)
            base = canonical / f"{stem}_{variant}"
            sub.to_parquet(base.with_suffix(".parquet"), index=False)
            sub.to_csv(base.with_suffix(".csv"), index=False)
            out[f"{stem}_{variant}"] = base.with_suffix(".parquet")
    ledger = pd.DataFrame(ledger_rows)
    ledger.to_parquet(canonical / "balance_ledger.parquet", index=False)
    ledger.to_csv(canonical / "balance_ledger.csv", index=False)
    out["balance_ledger"] = canonical / "balance_ledger.parquet"
    boundaries = pd.DataFrame(boundary_rows).sort_values(
        ["iso3", "classification", "line_code", "boundary_year"])
    boundaries.to_csv(canonical / "stitch_boundaries.csv", index=False)
    out["stitch_boundaries"] = canonical / "stitch_boundaries.csv"
    fboundaries = pd.DataFrame(forecast_boundary_rows).sort_values(
        ["iso3", "classification", "line_code", "boundary_year"])
    fboundaries.to_csv(canonical / "forecast_boundaries.csv", index=False)
    out["forecast_boundaries"] = canonical / "forecast_boundaries.csv"
    declarations = pd.DataFrame(declaration_rows).sort_values(
        ["iso3", "classification", "line_code"])
    declarations.to_csv(canonical / "forecast_declarations.csv", index=False)
    out["forecast_declarations"] = canonical / "forecast_declarations.csv"
    # D19: the FY/CY bridge on total expenditure — one row per (country,
    # year) of every FY-labelled tree; empty (header only) while no country
    # publishes a FY tree
    bridge = pd.DataFrame(bridge_rows, columns=FY_CY_BRIDGE_COLUMNS)
    bridge.to_csv(canonical / "fy_cy_bridge.csv", index=False)
    out["fy_cy_bridge"] = canonical / "fy_cy_bridge.csv"
    # §11.6 deliverable 9 (Stage 4): the final coverage matrix, assembled from
    # what was just written
    from ggfiscal.coverage import write_matrix
    out["coverage_matrix"] = write_matrix()

    # §11.6 deliverable 8 (Stage 6): crosswalks.csv — the concatenation of
    # every versioned crosswalk in crosswalks/, keyed by its file name
    out["crosswalks"] = write_crosswalks()

    # run manifest (§11.1, D-S6-003): every input hash the build consumed,
    # completed with deliverable hashes as the later pipeline steps run
    from ggfiscal import manifest as M
    snaps = {f"{sid}/{part}": e["sha256"] for (sid, part), e in R.latest_snapshots().items()}
    out["run_manifest"] = M.write_base(run_id, snaps)
    M.update_deliverables(out["run_manifest"])
    return out


def write_crosswalks(path: Path | None = None) -> Path:
    """Concatenate crosswalks/*.csv (identical §11.5 headers) into the
    canonical crosswalks.csv deliverable, keyed by source file."""
    dest = path or config.repo_root() / "data" / "canonical" / "crosswalks.csv"
    frames = []
    for p in sorted((config.repo_root() / "crosswalks").glob("*.csv")):
        df = pd.read_csv(p, dtype=str)
        df.insert(0, "crosswalk", p.stem)
        frames.append(df)
    pd.concat(frames, ignore_index=True).to_csv(dest, index=False)
    return dest


def load_canonical(classification: str, variant: str = "strict") -> pd.DataFrame:
    stem = config.STEMS[classification]
    path = config.repo_root() / "data" / "canonical" / f"{stem}_{variant}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def load_trees(variant: str = "strict") -> pd.DataFrame:
    """All three trees of one variant in one frame (COFOG, ESA_EXP, ESA_REV).
    Line codes are distinct across trees (TE / TE_ESA / TR), so the frame can
    be pivoted by line_code within a country. The §8.3 decomposition does NOT
    use this: it works on the 20 Level I lines by literal code, so the
    ESA_EXP tree (a second cut of the same TE) is never double counted."""
    return pd.concat([load_canonical(cls, variant) for cls in config.TREES],
                     ignore_index=True)


def load_ledger() -> pd.DataFrame:
    path = config.repo_root() / "data" / "canonical" / "balance_ledger.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()
