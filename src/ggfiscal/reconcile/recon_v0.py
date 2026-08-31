"""Stage 0 reconciliation tables (§12 Stage 0): anchor vs IMF GFS COFOG and
anchor vs OECD Revenue Statistics, per (country, line), over the overlap years.

These are diagnostics, not adjustments (D13): each row reports the overlap
span, the mean and max absolute percentage difference vs the anchor, and the
count of overlap years. Full V1/V25 tolerance testing lands in Stages 1-2.

The OECD RS comparison is heading-vs-line on deliberately different concepts
(cash timing, payable tax credits net, EU own resources — D15/D17); the
recorded diff is the size of the concept wedge the Stage 2 crosswalk must
carry, not an error measure.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from ggfiscal import config
from ggfiscal.standardise import readers as R

COLUMNS = ["iso3", "line_code", "comparator", "anchor_series", "comparator_series",
           "overlap_first", "overlap_last", "n_overlap",
           "mean_abs_diff_pct", "max_abs_diff_pct", "note"]


def _diff_row(iso3: str, line: str, comparator: str, a_name: str, c_name: str,
              a: pd.Series, c: pd.Series, note: str) -> dict | None:
    idx = a.index.intersection(c.index)
    idx = [t for t in idx if a[t] != 0]
    if len(idx) == 0:
        return None
    diffs = [abs(c[t] - a[t]) / abs(a[t]) * 100 for t in idx]
    return {"iso3": iso3, "line_code": line, "comparator": comparator,
            "anchor_series": a_name, "comparator_series": c_name,
            "overlap_first": int(min(idx)), "overlap_last": int(max(idx)),
            "n_overlap": len(idx),
            "mean_abs_diff_pct": round(sum(diffs) / len(diffs), 3),
            "max_abs_diff_pct": round(max(diffs), 3), "note": note}


def _anchor_cofog(iso3: str, cofog: str) -> tuple[str, pd.Series]:
    if iso3 == "GBR":
        return "ONS_ESA_T11", R.ons_cofog(cofog)
    return "EUROSTAT_GOV10A_EXP", R.eurostat_cofog(iso3, cofog)


def compute(dir_: Path | None = None) -> list[Path]:
    reports = dir_ or config.repo_root() / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    imf_rows, rs_rows = [], []
    for iso3 in config.COUNTRIES:
        # anchor vs IMF GFS COFOG (levels, XDC)
        for n in list(range(1, 11)) + ["0107"]:
            cofog = f"GF{n:02d}" if isinstance(n, int) else f"GF{n}"
            line = cofog if isinstance(n, int) else "GF01_7"
            gfs_ind = f"{cofog}_T" if isinstance(n, int) else "GF0170_T"
            a_name, a = _anchor_cofog(iso3, cofog)
            row = _diff_row(iso3, line, "IMF_GFS", a_name, gfs_ind, a,
                            R.gfs_series(iso3, "cofog", gfs_ind),
                            "same national data redistributed; expect near-zero")
            if row:
                imf_rows.append(row)
        # anchor vs OECD RS headings (concept wedge, D15/D17)
        if iso3 == "GBR":
            rev = {"R01": R.ons_t2_series("D211", "receivable"),
                   "R03": R.ons_t2_series("D51M", "receivable"),
                   "R04": R.ons_t2_series("D51O", "receivable"),
                   "R06": R.ons_t2_series("D61", "receivable")}
            a_name = "ONS_GG_RECEIPTS"
        else:
            rev = {"R01": R.eurostat_taxag(iso3, "D211"),
                   "R03": R.eurostat_taxag(iso3, "D51A_C1"),
                   "R04": R.eurostat_taxag(iso3, "D51B_C2"),
                   "R06": R.eurostat_main(iso3, "D61REC")}
            a_name = "EUROSTAT_GOV10A_TAXAG/MAIN"
        for line, heading in (("R01", "T_5111"), ("R03", "T_1100"),
                              ("R04", "T_1200"), ("R06", "T_2000")):
            row = _diff_row(iso3, line, "OECD_RS", a_name, heading, rev[line],
                            R.oecd_rs_heading(iso3, heading),
                            "concept wedge (cash timing, tax credits, own resources) "
                            "to be carried by the Stage 2 crosswalk")
            if row:
                rs_rows.append(row)
    out = []
    for name, rows in (("recon_anchor_vs_imf_v0.csv", imf_rows),
                       ("recon_anchor_vs_oecd_rs_v0.csv", rs_rows)):
        dest = reports / name
        with open(dest, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        out.append(dest)
    return out
