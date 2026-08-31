"""§8.2 base-year level bridge: anchor aggregates vs one WEO vintage.

For each (country, WEO vintage): base year b = last year in which WEO reports
an actual (LATEST_ACTUAL_ANNUAL_DATA on the fiscal series) AND the anchor has
an observation. For every overlap year t <= b, in LCU millions:

    gap_TR  = TR_anchor - GGR_w      gap_TE  = TE_anchor - GGX_w
    gap_NLB = NLB_anchor - GGXCNL_w  gap_GDP = GDP_anchor - NGDP_w
    NI_weo  = GGXONLB_w - GGXCNL_w   NI_ours = GF01_7 - R07   gap_NI

Nothing is scaled or adjusted (D13, D16): the bridge explains, it never forces.

Gap classification (§8.2) is a documented heuristic at Stage 0, refined by
V24 at Stage 5:
  - FRA/DEU: 'revision' where |gap|/TE_anchor is within the base-bridge
    tolerance (anchor vintage is newer than the WEO cut-off), else 'unexplained'.
  - GBR: a perimeter gap is expected (§14); years where the NLB gap ratio sits
    within tolerance of the country mean are 'perimeter', else 'unexplained'.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from ggfiscal import config
from ggfiscal.ingest.endpoints import WEO_VINTAGES
from ggfiscal.standardise import readers as R

COLUMNS = [
    "iso3", "weo_vintage", "year", "is_base_year",
    "tr_anchor_mn", "ggr_weo_mn", "gap_tr_mn",
    "te_anchor_mn", "ggx_weo_mn", "gap_te_mn",
    "nlb_anchor_mn", "ggxcnl_weo_mn", "gap_nlb_mn",
    "ni_ours_mn", "ni_weo_mn", "gap_ni_mn",
    "gdp_anchor_mn", "ngdp_weo_mn", "gap_gdp_mn",
    "gap_tr_pct_te", "gap_te_pct_te", "gap_nlb_pct_te", "gap_gdp_pct_gdp",
    "classification", "notes",
]


def anchor_aggregates(iso3: str) -> dict[str, pd.Series]:
    """TR, TE, NLB, GDP, GF01_7, R07 from the country's anchors, LCU millions."""
    if iso3 == "GBR":
        return {
            "TR": R.ons_t2_series("OTR", ""),
            "TE": R.ons_t2_series("OTE", ""),
            "NLB": R.ons_t2_series("B9", ""),
            "GDP": R.ons_gdp(),
            "GF01_7": R.ons_cofog("GF0107"),
            "R07": R.ons_t2_series("D41", "receivable"),
        }
    return {
        "TR": R.eurostat_main(iso3, "TR"),
        "TE": R.eurostat_main(iso3, "TE"),
        "NLB": R.eurostat_main(iso3, "B9"),
        "GDP": R.eurostat_gdp(iso3),
        "GF01_7": R.eurostat_cofog(iso3, "GF0107"),
        "R07": R.eurostat_main(iso3, "D41REC"),
    }


def weo_aggregates(vintage: str, iso3: str) -> dict[str, pd.Series]:
    """GGR, GGX, GGXCNL, GGXONLB, NGDP in LCU millions (raw WEO units / 1e6)."""
    return {ind: R.weo_series(vintage, iso3, ind) / 1e6
            for ind in ("GGR", "GGX", "GGXCNL", "GGXONLB", "NGDP")}


def base_year(vintage: str, iso3: str, anchor: dict[str, pd.Series]) -> int | None:
    """b = last WEO-actual year that the anchor also covers (§8.1)."""
    actuals = [R.weo_latest_actual(vintage, iso3, ind)
               for ind in ("GGR", "GGX", "GGXCNL", "NGDP")]
    actuals = [a for a in actuals if a is not None]
    if not actuals or anchor["TR"].empty or anchor["TE"].empty:
        return None
    b = min(actuals)
    anchor_last = int(min(anchor["TR"].index.max(), anchor["TE"].index.max(),
                          anchor["NLB"].index.max(), anchor["GDP"].index.max()))
    return min(b, anchor_last)


def compute(path: Path | None = None,
            vintages: list[str] | None = None) -> tuple[Path, list[dict]]:
    """Write weo_base_bridge.csv for every requested vintage (default: all
    harvested). Returns (path, per-(country,vintage) summary records)."""
    tol_pct = config.tolerances()["base_bridge_pct_of_te"]
    dest = path or config.repo_root() / "data" / "canonical" / "weo_base_bridge.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows, summaries = [], []
    for vintage in (vintages or list(WEO_VINTAGES)):
        for iso3 in config.COUNTRIES:
            anchor = anchor_aggregates(iso3)
            weo = weo_aggregates(vintage, iso3)
            b = base_year(vintage, iso3, anchor)
            if b is None:
                summaries.append({"iso3": iso3, "weo_vintage": vintage,
                                  "base_year": None, "n_overlap": 0})
                continue
            years = sorted(y for y in anchor["TR"].index
                           if y <= b and y in weo["GGXCNL"].index
                           and y in anchor["TE"].index and y in anchor["NLB"].index)
            country_rows = []
            for t in years:
                te = anchor["TE"].get(t)
                gdp_a = anchor["GDP"].get(t)
                ni_ours = (anchor["GF01_7"].get(t) - anchor["R07"].get(t)
                           if t in anchor["GF01_7"].index and t in anchor["R07"].index
                           else None)
                ni_weo = (weo["GGXONLB"].get(t) - weo["GGXCNL"].get(t)
                          if t in weo["GGXONLB"].index and t in weo["GGXCNL"].index
                          else None)
                rec = {
                    "iso3": iso3, "weo_vintage": vintage, "year": t,
                    "is_base_year": t == b,
                    "tr_anchor_mn": anchor["TR"].get(t), "ggr_weo_mn": weo["GGR"].get(t),
                    "te_anchor_mn": te, "ggx_weo_mn": weo["GGX"].get(t),
                    "nlb_anchor_mn": anchor["NLB"].get(t),
                    "ggxcnl_weo_mn": weo["GGXCNL"].get(t),
                    "ni_ours_mn": ni_ours, "ni_weo_mn": ni_weo,
                    "gdp_anchor_mn": gdp_a, "ngdp_weo_mn": weo["NGDP"].get(t),
                }
                for gap, a, w in (("gap_tr_mn", "tr_anchor_mn", "ggr_weo_mn"),
                                  ("gap_te_mn", "te_anchor_mn", "ggx_weo_mn"),
                                  ("gap_nlb_mn", "nlb_anchor_mn", "ggxcnl_weo_mn"),
                                  ("gap_ni_mn", "ni_ours_mn", "ni_weo_mn"),
                                  ("gap_gdp_mn", "gdp_anchor_mn", "ngdp_weo_mn")):
                    va, vw = rec.get(a), rec.get(w)
                    rec[gap] = (va - vw) if va is not None and vw is not None \
                        and pd.notna(va) and pd.notna(vw) else None
                for pct, gap, den in (("gap_tr_pct_te", "gap_tr_mn", te),
                                      ("gap_te_pct_te", "gap_te_mn", te),
                                      ("gap_nlb_pct_te", "gap_nlb_mn", te),
                                      ("gap_gdp_pct_gdp", "gap_gdp_mn", gdp_a)):
                    g = rec.get(gap)
                    rec[pct] = round(100 * g / den, 4) if g is not None and den else None
                country_rows.append(rec)
            # classification (§8.2 heuristic; V24 formalises at Stage 5)
            nlb_ratios = [r["gap_nlb_pct_te"] for r in country_rows
                          if r["gap_nlb_pct_te"] is not None]
            mean_ratio = sum(nlb_ratios) / len(nlb_ratios) if nlb_ratios else 0.0
            for r in country_rows:
                ratio = r["gap_nlb_pct_te"]
                if ratio is None:
                    r["classification"], r["notes"] = "", "gap not computable"
                elif iso3 == "GBR":
                    stable = abs(ratio - mean_ratio) <= tol_pct
                    r["classification"] = "perimeter" if stable else "unexplained"
                    r["notes"] = (f"perimeter gap expected (§14); country mean "
                                  f"{mean_ratio:.2f}% of TE")
                else:
                    within = abs(ratio) <= tol_pct
                    r["classification"] = "revision" if within else "unexplained"
                    r["notes"] = "anchor vintage newer than WEO cut-off" if within else \
                        f"NLB gap {ratio:.2f}% of TE exceeds tolerance {tol_pct}%"
            rows.extend(country_rows)
            sigma = (pd.Series(nlb_ratios).std() if len(nlb_ratios) > 1 else 0.0)
            summaries.append({
                "iso3": iso3, "weo_vintage": vintage, "base_year": b,
                "n_overlap": len(country_rows),
                "mean_gap_nlb_pct_te": round(mean_ratio, 3),
                "sigma_gap_nlb_pct_te": round(float(sigma), 3),
                "n_unexplained": sum(1 for r in country_rows
                                     if r["classification"] == "unexplained"),
            })
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})
    return dest, summaries
