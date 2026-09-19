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


def anchor_series(iso3: str) -> dict[tuple[str, str], dict]:
    """(classification, line_code) -> {series, source_id, observation_type,
    line_level, concept_flag, notes} — anchor cells only."""
    L = config.lines()
    exp_meta = L["expenditure"]
    rev_meta = L["revenue"]

    def m(cls, code, series, source_id, obs, level, label, concept="", notes="",
          per_year=None):
        return (cls, code), {"series": series, "source_id": source_id,
                             "observation_type": obs, "line_level": level,
                             "line_label": label, "concept_flag": concept,
                             "notes": notes, "per_year": per_year or {}}

    out = {}
    if iso3 == "GBR":
        cof = R.ons_cofog
        exp_src = "ONS_ESA_T11"
        t2 = lambda c, d="receivable": R.ons_t2_series(c, d)  # noqa: E731
        rev_src = "ONS_GG_RECEIPTS"
        rev = {
            "R01": (t2("D211"), "anchor_actual", ""),
            "R02": ((t2("D2") - t2("D211")).dropna(), "derived_actual",
                    "derived D.2 - D.211"),
            "R03": (t2("D51M"), "anchor_actual",
                    "D51M households incl. holding gains; crosswalk: NICs are D.61 not here"),
            "R04": (t2("D51O"), "anchor_actual", "D51O corporations incl. holding gains"),
            "R05": ((t2("D5") - t2("D51M") - t2("D51O") + t2("D91")).dropna(),
                    "derived_actual", "derived D.5 - R03 - R04 + D.91 (D.59 inside D.5)"),
            "R06": (t2("D61"), "anchor_actual", "NICs are D.61 (§14)"),
            "R07": (t2("D41"), "anchor_actual", ""),
            "R08": ((t2("D4") - t2("D41")).dropna(), "derived_actual",
                    "derived D.4 - D.41 resources"),
            "R09": ((t2("P11", "") + t2("P12", "") + t2("P131", "")).dropna(),
                    "derived_actual", "derived P.11 + P.12 + P.131"),
            "R10": ((t2("D39R") + t2("D7") + t2("D9") - t2("D91")).dropna(),
                    "derived_actual", "derived D.39 + D.7 + (D.9 - D.91) resources"),
        }
        tr = t2("OTR", "")
        te_cofog = cof("_T")
    else:
        cof = lambda c: R.eurostat_cofog(iso3, c)  # noqa: E731
        exp_src = "EUROSTAT_GOV10A_EXP"
        # All revenue lines from gov_10a_main's own REC codes: gov_10a_taxag
        # values drift from the main table in the freshest years (FRA 2024:
        # 0.5% on D.2), which breaks the V22 identity against the main table's
        # TR. Within gov_10a_main the identity is exact in every year,
        # provisional 2025 included. taxag remains the detail/verification
        # source (D59/D91 breakdowns) — see DECISIONS D-S1-002.
        em = lambda c: R.eurostat_main(iso3, c)  # noqa: E731
        rev_src = "EUROSTAT_GOV10A_MAIN"
        rev = {
            "R01": (em("D211REC"), "anchor_actual", ""),
            "R02": ((em("D2REC") - em("D211REC")).dropna(), "derived_actual",
                    "derived D.2 - D.211"),
            "R03": (em("D51A_C1REC"), "anchor_actual", "CSG is D.5 -> here, not R06 (§14)"
                    if iso3 == "FRA" else ""),
            "R04": (em("D51B_C2REC"), "anchor_actual", ""),
            "R05": ((em("D5REC") - em("D51A_C1REC") - em("D51B_C2REC")
                     + em("D91REC")).dropna(),
                    "derived_actual", "derived D.5 - R03 - R04 + D.91 (D.59 inside D.5)"),
            "R06": (em("D61REC"), "anchor_actual", ""),
            "R07": (em("D41REC"), "anchor_actual", ""),
            "R08": ((em("D4REC") - em("D41REC")).dropna(), "derived_actual",
                    "derived D.4 - D.41 resources"),
            "R09": (em("P11_P12_P131"), "anchor_actual", ""),
            "R10": ((em("D39REC") + em("D7REC") + em("D92REC") + em("D99REC")).dropna(),
                    "derived_actual", "derived D.39 + D.7 + D.92 + D.99 resources"),
        }
        tr = em("TR")
        te_cofog = cof("TOTAL")

    for n in range(1, 11):
        code = f"GF{n:02d}"
        out.update([m("COFOG", code, cof(code), exp_src,
                      "anchor_actual", "1", exp_meta[code]["label"])])
    # COFOG Level II splits (config.level2_splits(): GF01_7/GF01_X per D10,
    # GF10_2/GF10_X per D-S11-002). The Level II line comes from the anchor's
    # own Level II table; its remainder is parent minus Level II, derived and
    # never forecast. D10's fallback applies to the interest line only: years
    # the anchor covers (parent exists) but Level II lacks are filled from the
    # same institution's GG D.41 payable, level2_proxy_actual, grade B (DEU
    # 1995-99 is the case). Other groups simply start where Level II starts.
    for split in config.level2_splits():
        parent, l2, rem = split["parent"], split["level2"], split["remainder"]
        l2_series = cof(split["eurostat_cofog"])
        parent_series = out[("COFOG", parent)]["series"]
        per_year: dict[int, dict] = {}
        if split["fallback"] == "d41_payable":
            d41pay = (R.ons_t2_series("D41", "payable") if iso3 == "GBR"
                      else R.eurostat_main(iso3, "D41PAY"))
            for y in sorted(set(parent_series.index) - set(l2_series.index)):
                if y in d41pay.index:
                    l2_series.loc[y] = float(d41pay[y])
                    per_year[y] = {
                        "observation_type": "level2_proxy_actual",
                        "quality_grade": split["grade_on_fallback"],
                        "notes": "D10 fallback: GG gross D.41 payable in place of "
                                 "missing Level II 01.7 (same institution)"}
        l2_series = l2_series.sort_index()
        cofog_code = split["eurostat_cofog"]
        dotted = f"{cofog_code[2:4]}.{int(cofog_code[4:6])}"
        interest = l2 == "GF01_7"
        out.update([m("COFOG", l2, l2_series, exp_src, "anchor_actual", "2",
                      exp_meta[l2]["label"],
                      concept="d41_gross_accrued" if interest else "",
                      notes=(f"COFOG {dotted} from the anchor's Level II table "
                             + ("(D10)" if interest else "(D-S11-002)")),
                      per_year=per_year)])
        remainder = (parent_series - l2_series).dropna()
        x_per_year = {y: {"observation_type": "derived_actual",
                          "quality_grade": split["grade_on_fallback"],
                          "notes": f"{parent} minus a D10 proxy {l2} year"}
                      for y in per_year}
        out.update([m("COFOG", rem, remainder, exp_src, "derived_actual", "derived",
                      exp_meta[rem]["label"],
                      notes=f"derived {parent} - {l2}; never forecast "
                            + ("(D10)" if interest else "(D-S11-002)"),
                      per_year=x_per_year)])
    out.update([m("COFOG", "TE", te_cofog, exp_src, "anchor_actual", "total",
                  "Total expenditure",
                  notes="the COFOG table's own total row (V2 baseline)")])
    # --- ESA_EXP: expenditure by economic type (D-S11-003), from the same
    # institution's main-aggregates table: gov_10a_main payable items (FRA,
    # DEU), ONS ESA Table 2 payable rows (GBR). Sums are derived_actual;
    # the identity E01..E09 = TE_ESA is exact by construction (V2).
    esa_meta = L["expenditure_esa"]
    esa_src = "ONS_GG_RECEIPTS" if iso3 == "GBR" else "EUROSTAT_GOV10A_MAIN"
    for code, meta in esa_meta.items():
        if iso3 == "GBR":
            spec = meta["ons_t2"]
            plus = [R.ons_t2_series(c, d) for c, d in spec.get("plus", [])]
            minus = [R.ons_t2_series(c, d) for c, d in spec.get("minus", [])]
        else:
            spec = meta["eurostat_main"]
            plus = [R.eurostat_main(iso3, c) for c in spec.get("plus", [])]
            minus = [R.eurostat_main(iso3, c) for c in spec.get("minus", [])]
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
    return out


def gdp_series(iso3: str) -> tuple[pd.Series, str]:
    if iso3 == "GBR":
        return R.ons_gdp(), "ONS_GDP"
    return R.eurostat_gdp(iso3), "EUROSTAT_NAMA10_GDP"


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


_RS_HEADINGS = {"R01": "T_5111", "R03": "T_1100", "R04": "T_1200", "R06": "T_2000"}


def _oecd_recon(iso3: str, classification: str, line_code: str) -> pd.Series:
    if classification != "ESA_REV" or line_code not in _RS_HEADINGS:
        return pd.Series(dtype=float)
    return R.oecd_rs_heading(iso3, _RS_HEADINGS[line_code])


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
    for iso3 in config.COUNTRIES:
        series_map = anchor_series(iso3)
        gdp, gdp_src = gdp_series(iso3)
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
                        "native_period": str(year), "source_period_basis": "CY",
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
        for (classification, line_code), sources in extensions_for(iso3).items():
            meta = series_map.get((classification, line_code))
            if meta is None:
                continue
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
                        "native_period": str(year), "source_period_basis": "CY",
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
        for (classification, line_code), sources in forecasts_for(iso3).items():
            meta = series_map.get((classification, line_code))
            if meta is None:
                continue
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
                        "native_period": str(year), "source_period_basis": "CY",
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
        # Level II remainders (GF01_X, GF10_X) in stitched years: derive where
        # both the parent and the Level II line were stitched (D10, D-S11-002)
        for variant, vals in stitched_vals.items():
            for split in config.level2_splits():
                parent_v = vals.get(("COFOG", split["parent"]), {})
                l2_v = vals.get(("COFOG", split["level2"]), {})
                rem = split["remainder"]
                meta_x = series_map[("COFOG", rem)]
                for year in sorted(set(parent_v) & set(l2_v)):
                    vp, gp = parent_v[year]
                    vl, gl = l2_v[year]
                    grade = max(gp, gl)  # worst grade ('C' > 'B' lexically)
                    gdp_v = float(gdp[year]) if year in gdp.index else None
                    value = vp - vl
                    frames["COFOG"].append({
                        "series_id": f"{iso3}_{rem}_{variant}",
                        "iso3": iso3, "classification": "COFOG",
                        "line_code": rem, "line_level": "derived",
                        "line_label": meta_x["line_label"], "year": year,
                        "native_period": str(year), "source_period_basis": "CY",
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
                        "notes": f"derived {split['parent']} - {split['level2']} in "
                                 "backward-stitched years (D10 / D-S11-002)",
                    })
        # balance ledger from the balance anchor's own TR/TE/B9 (V23 exact)
        if iso3 == "GBR":
            btr, bte, b9 = (R.ons_t2_series("OTR", ""), R.ons_t2_series("OTE", ""),
                            R.ons_t2_series("B9", ""))
            bal_src = "ONS_GG_RECEIPTS"
        else:
            btr, bte, b9 = (R.eurostat_main(iso3, "TR"), R.eurostat_main(iso3, "TE"),
                            R.eurostat_main(iso3, "B9"))
            bal_src = "EUROSTAT_GOV10A_MAIN"
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
