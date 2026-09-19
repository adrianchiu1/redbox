"""Coverage matrix (§11.6 deliverable 9; v0 per §12 Stage 0).

coverage_matrix_v0.csv is *programmatically measured* from harvested snapshots:
one row per (country, line, source) with the first/last usable year and
observation count — never hand-filled (D13). A derived or composite line's
usable years are the intersection of its components' years, so the matrix
reflects what can actually be built.

Until snapshots exist the frame is emitted with year fields empty and status
`awaiting_harvest` (that was the first session's state).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from ggfiscal import config
from ggfiscal.standardise import readers as R

V0_COLUMNS = [
    "iso3", "classification", "line_code", "source_id",
    "first_usable_year", "last_usable_year", "n_years",
    "status", "notes",
]


def _intersect(*series: pd.Series) -> pd.Series:
    """Years where every component has an observation (composite coverage)."""
    if not series or any(s.empty for s in series):
        return pd.Series(dtype=float)
    idx = series[0].index
    for s in series[1:]:
        idx = idx.intersection(s.index)
    return series[0].loc[idx]


def _cofog_sources(iso3: str, gf: str, gfs_ind: str) -> list[tuple[str, pd.Series, str]]:
    """(source_id, series, note) candidates for one COFOG line."""
    out = []
    if iso3 == "GBR":
        out.append(("ONS_ESA_T11", R.ons_cofog(gf), "anchor; OTE per function"))
    else:
        out.append(("EUROSTAT_GOV10A_EXP", R.eurostat_cofog(iso3, gf), "anchor; na_item TE"))
    out.append(("OECD_T11", R.oecd_t11_cofog(iso3, gf), "secondary; S13 XDC OTE"))
    out.append(("IMF_GFS", R.gfs_series(iso3, "cofog", gfs_ind),
                "reconciliation; GFSM XDC"))
    return out


def line_sources(iso3: str) -> dict[tuple[str, str], list[tuple[str, pd.Series, str]]]:
    """All measured source series per (classification, line_code) for a country."""
    out: dict[tuple[str, str], list[tuple[str, pd.Series, str]]] = {}

    # --- COFOG Level I ---
    for n in range(1, 11):
        gf = f"GF{n:02d}"
        out[("COFOG", gf)] = _cofog_sources(iso3, gf, f"{gf}_T")

    # --- COFOG Level II splits (GF01_7/GF01_X per D10; GF10_2/GF10_X per
    # D-S11-002) and their derived remainders, enumerated from lines.yaml ---
    for split in config.level2_splits():
        l2 = _cofog_sources(iso3, split["eurostat_cofog"], split["gfs_indicator"])
        if split["level2"] == "GF01_7":
            if iso3 == "GBR":
                l2.append(("ONS_PSF_INTEREST", R.ons_t2_series("D41", "payable"),
                           "D10 fallback concept: GG D.41 payable, accrued"))
            else:
                l2.append(("EUROSTAT_GOV10A_MAIN", R.eurostat_main(iso3, "D41PAY"),
                           "D10 fallback concept: GG D.41 payable"))
            l2.append(("EC_AMECO", R.ameco_series(iso3, "UYIG", 16),
                       "envelope forecast source; ESA gross GG interest (D.41 pay)"))
        if split["level2"] == "GF10_2" and iso3 in ("FRA", "DEU"):
            l2.append(("EC_AGEING_2024", R.ar_series(iso3, "pensions"),
                       "forecast source; AWG gross public pensions, % GDP"))
        out[("COFOG", split["level2"])] = l2
        if iso3 == "GBR":
            parent, child = R.ons_cofog(split["parent"]), R.ons_cofog(split["eurostat_cofog"])
            anchor = "ONS_ESA_T11"
        else:
            parent = R.eurostat_cofog(iso3, split["parent"])
            child = R.eurostat_cofog(iso3, split["eurostat_cofog"])
            anchor = "EUROSTAT_GOV10A_EXP"
        out[("COFOG", split["remainder"])] = [
            (anchor, _intersect(parent, child),
             f"derived {split['parent']} - {split['level2']}; years where both exist")]

    # --- ESA_EXP: expenditure by economic type (D-S11-003) ---
    for code, meta in config.tree_lines("ESA_EXP").items():
        if config.is_total(meta):
            continue
        if iso3 == "GBR":
            spec = meta["ons_t2"]
            parts = [R.ons_t2_series(c, d) for c, d in spec.get("plus", [])] + \
                    [R.ons_t2_series(c, d) for c, d in spec.get("minus", [])]
            anchor_id = "ONS_GG_RECEIPTS"
        else:
            spec = meta["eurostat_main"]
            parts = [R.eurostat_main(iso3, c) for c in spec.get("plus", [])] + \
                    [R.eurostat_main(iso3, c) for c in spec.get("minus", [])]
            anchor_id = "EUROSTAT_GOV10A_MAIN"
        entries = [(anchor_id, _intersect(*parts) if len(parts) > 1 else parts[0],
                    f"anchor; {meta['esa']}")]
        if meta.get("ameco"):
            entries.append(("EC_AMECO", R.ameco_series(iso3, meta["ameco"], 16),
                            f"AMECO {meta['ameco']}; backward extension and forecast"
                            + (" (partial component, §7.8 proxy)"
                               if meta.get("ameco_partial") else "")))
        if meta.get("gfs_soo"):
            entries.append(("IMF_GFS", R.gfs_series(iso3, "soo", meta["gfs_soo"]),
                            f"reconciliation; GFSM {meta['gfs_soo']}"))
        out[("ESA_EXP", code)] = entries

    # --- Revenue ---
    if iso3 == "GBR":
        t2 = lambda c, d="receivable": R.ons_t2_series(c, d)  # noqa: E731
        ntl = R.ons_tax_series
        rev: dict[str, list[tuple[str, pd.Series, str]]] = {
            "R01": [("ONS_GG_RECEIPTS", t2("D211"), "anchor; D.211 receivable"),
                    ("ONS_TAX_DETAIL", ntl("D211"), "NTL detail")],
            "R02": [("ONS_GG_RECEIPTS", _intersect(t2("D2"), t2("D211")),
                     "derived D.2 - D.211")],
            "R03": [("ONS_GG_RECEIPTS", t2("D51M"),
                     "D51M = household income taxes incl. holding gains"),
                    ("ONS_TAX_DETAIL", ntl("D51M"), "NTL detail")],
            "R04": [("ONS_GG_RECEIPTS", t2("D51O"),
                     "D51O = corporate income taxes incl. holding gains"),
                    ("ONS_TAX_DETAIL", ntl("D51O"), "NTL detail")],
            "R05": [("ONS_GG_RECEIPTS",
                     _intersect(t2("D5"), t2("D51M"), t2("D51O"), t2("D59"), t2("D91")),
                     "derived D.5 - D.51M - D.51O + D.59 + D.91")],
            "R06": [("ONS_GG_RECEIPTS", t2("D61"), "anchor; D.61 receivable")],
            "R07": [("ONS_GG_RECEIPTS", t2("D41"), "anchor; D.41 receivable, accrued")],
            "R08": [("ONS_GG_RECEIPTS", _intersect(t2("D4"), t2("D41")),
                     "derived D.4 - D.41 receivable")],
            "R09": [("ONS_GG_RECEIPTS",
                     _intersect(t2("P11", ""), t2("P12", ""), t2("P131", "")),
                     "derived P.11 + P.12 + P.131")],
            "R10": [("ONS_GG_RECEIPTS",
                     _intersect(t2("D39R"), t2("D7"), t2("D9"), t2("D91")),
                     "derived D.39 + D.7 + (D.9 - D.91) receivable")],
        }
    else:
        em = lambda c: R.eurostat_main(iso3, c)  # noqa: E731
        et = lambda c: R.eurostat_taxag(iso3, c)  # noqa: E731
        rev = {
            "R01": [("EUROSTAT_GOV10A_MAIN", em("D211REC"), "anchor; D.211 (D-S1-002)"),
                    ("EUROSTAT_GOV10A_TAXAG", et("D211"), "detail/verification")],
            "R02": [("EUROSTAT_GOV10A_MAIN", _intersect(em("D2REC"), em("D211REC")),
                     "derived D.2 - D.211")],
            "R03": [("EUROSTAT_GOV10A_MAIN", em("D51A_C1REC"),
                     "anchor; household income taxes incl. holding gains"),
                    ("EUROSTAT_GOV10A_TAXAG", et("D51A_C1"), "detail/verification")],
            "R04": [("EUROSTAT_GOV10A_MAIN", em("D51B_C2REC"),
                     "anchor; corporate income taxes incl. holding gains"),
                    ("EUROSTAT_GOV10A_TAXAG", et("D51B_C2"), "detail/verification")],
            "R05": [("EUROSTAT_GOV10A_MAIN",
                     _intersect(em("D5REC"), em("D51A_C1REC"), em("D51B_C2REC"),
                                em("D91REC")),
                     "derived D.5 - R03 - R04 + D.91 (D.59 inside D.5)")],
            "R06": [("EUROSTAT_GOV10A_MAIN", em("D61REC"), "anchor; D.61 resources")],
            "R07": [("EUROSTAT_GOV10A_MAIN", em("D41REC"), "anchor; D.41 resources")],
            "R08": [("EUROSTAT_GOV10A_MAIN", _intersect(em("D4REC"), em("D41REC")),
                     "derived D.4 - D.41 resources")],
            "R09": [("EUROSTAT_GOV10A_MAIN", em("P11_P12_P131"), "anchor")],
            "R10": [("EUROSTAT_GOV10A_MAIN",
                     _intersect(em("D39REC"), em("D7REC"), em("D92REC"), em("D99REC")),
                     "derived D.39 + D.7 + D.92 + D.99 resources")],
        }

    # OECD RS headings (backward extension, D15) and GFS SOO (reconciliation)
    rs = lambda h: R.oecd_rs_heading(iso3, h)  # noqa: E731
    soo = lambda i: R.gfs_series(iso3, "soo", i)  # noqa: E731
    rs_map = {
        "R01": ("T_5111", "OECD heading 5111 VAT"),
        "R02": ("T_5000", "OECD heading 5000 taxes on goods and services (minus VAT in crosswalk)"),
        "R03": ("T_1100", "OECD heading 1100 taxes on income of individuals"),
        "R04": ("T_1200", "OECD heading 1200 corporate taxes on income"),
        "R05": ("T_4000", "OECD heading 4000 property taxes (partial concept)"),
        "R06": ("T_2000", "OECD heading 2000 social security contributions"),
    }
    soo_map = {
        "R01": ("G11411_T", "GFSM 11411 VAT"),
        "R03": ("G1111_T", "GFSM 1111 income taxes, individuals"),
        "R04": ("G1112_T", "GFSM 1112 income taxes, corporations"),
        "R06": ("G12_T", "GFSM 12 social contributions"),
        "R07": ("G1411_T", "GFSM 1411 interest revenue"),
    }
    for line, (heading, note) in rs_map.items():
        rev[line].append(("OECD_RS", rs(heading), f"backward extension; {note}"))
    for line, (ind, note) in soo_map.items():
        rev[line].append(("IMF_GFS", soo(ind), f"reconciliation; {note}"))

    for line, entries in rev.items():
        out[("ESA_REV", line)] = entries
    return out


def measure(path: Path | None = None) -> Path:
    """Write the measured coverage matrix. Falls back to the empty frame when
    no snapshots exist (first-session behaviour)."""
    dest = path or config.repo_root() / "reports" / "coverage_matrix_v0.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not R.latest_snapshots():
        return build_v0(dest)

    no_fc = config.no_forecast_lines()
    rows = []
    for iso3 in config.COUNTRIES:
        srcs = line_sources(iso3)
        for (classification, line_code) in [(c, l) for (i, c, l) in config.line_universe()
                                            if i == iso3]:
            notes_d7 = []
            if line_code in no_fc.get(config.TREES[classification], []):
                notes_d7.append("D7: no identified forecast source")
            if classification == "ESA_REV" and line_code in no_fc.get("revenue_partial", {}):
                notes_d7.append(f"D7 partial: {no_fc['revenue_partial'][line_code]}")
            entries = srcs.get((classification, line_code), [])
            any_cov = False
            for source_id, series, note in entries:
                if series.empty:
                    continue
                any_cov = True
                rows.append({
                    "iso3": iso3, "classification": classification,
                    "line_code": line_code, "source_id": source_id,
                    "first_usable_year": int(series.index.min()),
                    "last_usable_year": int(series.index.max()),
                    "n_years": int(series.notna().sum()),
                    "status": "measured",
                    "notes": " | ".join([note] + notes_d7),
                })
            if not any_cov:
                rows.append({
                    "iso3": iso3, "classification": classification,
                    "line_code": line_code, "source_id": "",
                    "first_usable_year": "", "last_usable_year": "", "n_years": 0,
                    "status": "NO_COVERAGE",
                    "notes": " | ".join(["no measurable source in harvest"] + notes_d7),
                })
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=V0_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return dest


def gate0_line_coverage() -> tuple[int, list[tuple[str, str, str]]]:
    """(covered_line_count, uncovered_lines) across the line universe."""
    covered, uncovered = 0, []
    for iso3 in config.COUNTRIES:
        srcs = line_sources(iso3)
        for (i, classification, line_code) in config.line_universe():
            if i != iso3:
                continue
            entries = srcs.get((classification, line_code), [])
            if any(not s.empty for _, s, _ in entries):
                covered += 1
            else:
                uncovered.append((iso3, classification, line_code))
    return covered, uncovered


def build_v0(path: Path | None = None) -> Path:
    """Pre-harvest frame: line universe with empty year fields (D13-safe)."""
    dest = path or config.repo_root() / "reports" / "coverage_matrix_v0.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    no_fc = config.no_forecast_lines()
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=V0_COLUMNS)
        w.writeheader()
        for iso3, classification, line_code in config.line_universe():
            notes = []
            if line_code in no_fc.get(config.TREES[classification], []):
                notes.append("D7: no identified forecast source; declared at outset")
            if classification == "ESA_REV" and line_code in no_fc.get("revenue_partial", {}):
                notes.append(f"D7 partial: {no_fc['revenue_partial'][line_code]}")
            w.writerow({
                "iso3": iso3, "classification": classification, "line_code": line_code,
                "source_id": "", "first_usable_year": "", "last_usable_year": "",
                "n_years": 0, "status": "awaiting_harvest", "notes": " | ".join(notes),
            })
    return dest


# ---------- §11.6 deliverable 9: the final coverage matrix (Stage 4) ----------

MATRIX_COLUMNS = [
    "iso3", "classification", "line_code",
    "first_historical_year", "final_actual_year", "first_forecast_year",
    "final_strict_year", "final_maximum_year",
    "stitch_count", "grades", "principal_sources",
    "residual_method", "reason_series_ends",
]


def build_matrix() -> pd.DataFrame:
    """One row per §1 line series (config.universe_size()): span per variant,
    stitch counts, grades, principal sources, residual method, and why the
    series ends — assembled from the canonical tables, both boundary files
    and the declarations, never hand-filled (D13)."""
    from ggfiscal.build import load_trees

    root = config.repo_root() / "data" / "canonical"
    bwd = pd.read_csv(root / "stitch_boundaries.csv")
    fwd = pd.read_csv(root / "forecast_boundaries.csv")
    dec = pd.read_csv(root / "forecast_declarations.csv")
    frames = {v: load_trees(v) for v in ("strict", "maximum_extension")}
    rows = []
    for iso3, classification, line in config.line_universe():
        mx = frames["maximum_extension"]
        st = frames["strict"]
        m = mx[(mx.iso3 == iso3) & (mx.line_code == line)
               & (mx.classification == classification)]
        s = st[(st.iso3 == iso3) & (st.line_code == line)
               & (st.classification == classification)]
        fc = m[m.is_forecast]
        applied_b = bwd[(bwd.iso3 == iso3) & (bwd.line_code == line)
                        & (bwd.classification == classification)
                        & (~bwd.variants.str.startswith("not_applied"))]
        applied_f = fwd[(fwd.iso3 == iso3) & (fwd.line_code == line)
                        & (fwd.classification == classification)
                        & (~fwd.variants.str.startswith("not_applied"))]
        d = dec[(dec.iso3 == iso3) & (dec.line_code == line)
                & (dec.classification == classification)]
        if not d.empty:
            reason = "; ".join(f"[{r.status}] {r.note}" for _, r in d.iterrows())
        elif not fc.empty:
            src = fc.sort_values("year").iloc[-1]
            reason = (f"source horizon: {src.source_id} ends "
                      f"{int(src.year)} (V10)")
        else:
            reason = "no rows built"
        rows.append({
            "iso3": iso3, "classification": classification, "line_code": line,
            "first_historical_year": int(m.year.min()) if len(m) else None,
            "final_actual_year": (int(m[~m.is_forecast].year.max())
                                  if len(m[~m.is_forecast]) else None),
            "first_forecast_year": int(fc.year.min()) if len(fc) else None,
            "final_strict_year": int(s.year.max()) if len(s) else None,
            "final_maximum_year": int(m.year.max()) if len(m) else None,
            "stitch_count": len(applied_b) + len(applied_f),
            "grades": "".join(sorted(set(m.quality_grade.dropna()))),
            "principal_sources": "+".join(dict.fromkeys(
                list(applied_b.incoming_source) + list(applied_f.incoming_source)
                or list(m.source_id.dropna().unique()[:1]))),
            "residual_method": "+".join(sorted(set(m.residual_method.dropna()))),
            "reason_series_ends": reason,
        })
    return pd.DataFrame(rows, columns=MATRIX_COLUMNS)


def write_matrix(path: Path | None = None) -> Path:
    dest = path or config.repo_root() / "data" / "canonical" / "coverage_matrix.csv"
    build_matrix().to_csv(dest, index=False)
    return dest
