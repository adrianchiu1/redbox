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

import datetime as dt
import hashlib
import json
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
    # GF01_7 (D10): Level II 01.7; years the anchor covers (GF01 exists) but
    # Level II lacks are filled from the same institution's GG D.41 payable,
    # observation_type level2_proxy_actual, grade B (DEU 1995-99 is the case).
    gf017 = cof("GF0107")
    gf01 = out[("COFOG", "GF01")]["series"]
    d41pay = (R.ons_t2_series("D41", "payable") if iso3 == "GBR"
              else R.eurostat_main(iso3, "D41PAY"))
    proxy_years = sorted(set(gf01.index) - set(gf017.index))
    per_year = {}
    for y in proxy_years:
        if y in d41pay.index:
            gf017.loc[y] = float(d41pay[y])
            per_year[y] = {
                "observation_type": "level2_proxy_actual", "quality_grade": "B",
                "notes": "D10 fallback: GG gross D.41 payable in place of missing "
                         "Level II 01.7 (same institution)"}
    gf017 = gf017.sort_index()
    out.update([m("COFOG", "GF01_7", gf017, exp_src, "anchor_actual", "2",
                  exp_meta["GF01_7"]["label"], concept="d41_gross_accrued",
                  notes="COFOG 01.7 from the anchor's Level II table (D10)",
                  per_year=per_year)])
    gf01x = (gf01 - gf017).dropna()
    x_per_year = {y: {"observation_type": "derived_actual", "quality_grade": "B",
                      "notes": "GF01 minus a D10 proxy GF01_7 year"}
                  for y in per_year}
    out.update([m("COFOG", "GF01_X", gf01x, exp_src, "derived_actual", "derived",
                  exp_meta["GF01_X"]["label"],
                  notes="derived GF01 - GF01_7; never forecast (D10)",
                  per_year=x_per_year)])
    out.update([m("COFOG", "TE", te_cofog, exp_src, "anchor_actual", "total",
                  "Total expenditure",
                  notes="the COFOG table's own total row (V2 baseline)")])
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
    """IMF GFS series for the same cell (COFOG lines only; ≈identical concept)."""
    if classification != "COFOG":
        return pd.Series(dtype=float)
    if line_code == "GF01_7":
        return R.gfs_series(iso3, "cofog", "GF0170_T")
    if line_code.startswith("GF") and line_code[2:].isdigit():
        return R.gfs_series(iso3, "cofog", f"{line_code}_T")
    return pd.Series(dtype=float)


_RS_HEADINGS = {"R01": "T_5111", "R03": "T_1100", "R04": "T_1200", "R06": "T_2000"}


def _oecd_recon(iso3: str, classification: str, line_code: str) -> pd.Series:
    if classification != "ESA_REV" or line_code not in _RS_HEADINGS:
        return pd.Series(dtype=float)
    return R.oecd_rs_heading(iso3, _RS_HEADINGS[line_code])


def build_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build(run_id: str | None = None) -> dict[str, Path]:
    run_id = run_id or build_run_id()
    canonical = config.repo_root() / "data" / "canonical"
    canonical.mkdir(parents=True, exist_ok=True)
    currency = {c: v["currency"] for c, v in config.countries().items()}

    frames: dict[str, list[dict]] = {"COFOG": [], "ESA_REV": []}
    ledger_rows: list[dict] = []
    for iso3 in config.COUNTRIES:
        series_map = anchor_series(iso3)
        gdp, gdp_src = gdp_series(iso3)
        te = series_map[("COFOG", "TE")]["series"]
        tr = series_map[("ESA_REV", "TR")]["series"]
        exp_src = series_map[("COFOG", "TE")]["source_id"]
        rev_src = series_map[("ESA_REV", "TR")]["source_id"]
        for (classification, line_code), meta in series_map.items():
            s = meta["series"]
            imf = _imf_recon(iso3, classification, line_code)
            rs = _oecd_recon(iso3, classification, line_code)
            total = te if classification == "COFOG" else tr
            total_src = exp_src if classification == "COFOG" else rev_src
            release, vintage = _release(meta["source_id"])
            for year, value in s.items():
                year = int(year)
                override = meta.get("per_year", {}).get(year, {})
                obs_type = override.get("observation_type", meta["observation_type"])
                grade = override.get("quality_grade", "A")
                notes = override.get("notes", meta["notes"]) or None
                gdp_v = float(gdp[year]) if year in gdp.index else None
                tot_v = (float(total[year])
                         if line_code not in ("TE", "TR") and year in total.index else None)
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
    for classification, stem in (("COFOG", "expenditure_long"), ("ESA_REV", "revenue_long")):
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

    # run manifest (§11.1): snapshots and config the build consumed
    snaps = {f"{sid}/{part}": e["sha256"] for (sid, part), e in R.latest_snapshots().items()}
    cfg_hash = hashlib.sha256(b"".join(
        (config.repo_root() / "config" / f"{n}.yaml").read_bytes()
        for n in ("countries", "lines", "sources", "residual"))).hexdigest()
    manifest = config.repo_root() / "data" / "manifest" / f"run_{run_id}.json"
    manifest.write_text(json.dumps({"run_id": run_id, "stage": 1,
                                    "config_sha256": cfg_hash,
                                    "snapshots": snaps}, indent=1, sort_keys=True))
    out["run_manifest"] = manifest
    return out


def load_canonical(classification: str, variant: str = "strict") -> pd.DataFrame:
    stem = {"COFOG": "expenditure_long", "ESA_REV": "revenue_long"}[classification]
    path = config.repo_root() / "data" / "canonical" / f"{stem}_{variant}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def load_ledger() -> pd.DataFrame:
    path = config.repo_root() / "data" / "canonical" / "balance_ledger.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()
