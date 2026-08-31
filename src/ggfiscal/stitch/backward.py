"""Stage 2 backward extension (§7.3-7.4, §7.11-7.12, D6, D15).

Y_t = Y_{t+1} × X_t / X_{t+1} for t < F: growth of the extension source,
never its level. Sources are applied sequentially (§7.4) — each transition
writes a boundary record. Extension stops (§7.12) at a missing, zero or
negative source value, or at a configured perimeter break (DEU 1991:
pre-reunification data is West Germany — a different universe, §14).

Grading (§9, D6): coverage_share = extension_value / anchor_value in the
last common year (§9.2, unit-adjusted). 0.9 <= share <= 1.1 -> B (minor
documented concept differences: OECD RS with crosswalk, D.41 in place of
Level II); otherwise C (material tax-credit / timing / perimeter wedge, D17).
Grade B rows enter both variants; C rows enter maximum_extension only (§9).
"""

from __future__ import annotations

import dataclasses

import pandas as pd

from ggfiscal.standardise import readers as R

DEU_BREAK = 1991  # reunification: never extend a DEU line below this (§14)

RS_XWALK = "OECD_RS_to_ESA_REV:1.0"
AMECO_XWALK = "EC_AMECO_to_INTEREST:1.0"
GFS_XWALK = "IMF_GFS_to_COFOG:1.0"

RS_NOTE = ("OECD Revenue Statistics heading, growth only (§7.11): historical "
           "years cash-basis; payable tax credits net where the anchor is gross "
           "(D17); EU own resources treated as revenue reductions in some "
           "years vs D.7 payable in ESA")


@dataclasses.dataclass
class ExtSource:
    source_id: str
    series: pd.Series
    concept_note: str            # V13: concept compatibility note
    crosswalk_version: str
    unit_factor: float = 1.0     # multiply source level -> LCU mn (coverage only)
    break_before: int | None = None
    concept_flag: str = ""


def _rs(iso3: str, heading: str, label: str) -> ExtSource:
    return ExtSource(
        source_id="OECD_RS", series=R.oecd_rs_heading(iso3, heading),
        concept_note=f"{label}: {RS_NOTE}", crosswalk_version=RS_XWALK,
        break_before=DEU_BREAK if iso3 == "DEU" else None)


def extensions_for(iso3: str) -> dict[tuple[str, str], list[ExtSource]]:
    """Ordered backward-extension sources per (classification, line_code)."""
    out: dict[tuple[str, str], list[ExtSource]] = {}
    # --- tax lines via OECD RS (D15; §12 Stage 2 order) ---
    out[("ESA_REV", "R01")] = [_rs(iso3, "T_5111", "OECD 5111 VAT")]
    out[("ESA_REV", "R02")] = [ExtSource(
        "OECD_RS",
        (R.oecd_rs_heading(iso3, "T_5000") - R.oecd_rs_heading(iso3, "T_5111")).dropna(),
        "OECD 5000 minus 5111 (goods & services taxes excl. VAT): " + RS_NOTE
        + "; excludes D.29-type recurrent property taxes on producers "
          "(OECD 4000) — coverage measured", RS_XWALK,
        break_before=DEU_BREAK if iso3 == "DEU" else None)]
    out[("ESA_REV", "R03")] = [_rs(iso3, "T_1100", "OECD 1100 personal income taxes")]
    out[("ESA_REV", "R04")] = [_rs(iso3, "T_1200", "OECD 1200 corporate income taxes")]
    out[("ESA_REV", "R05")] = [_rs(
        iso3, "T_4000", "OECD 4000 property taxes (recurrent, estate/gift, "
        "transaction) as proxy for other current + capital taxes")]
    out[("ESA_REV", "R06")] = [_rs(
        iso3, "T_2000", "OECD 2000 compulsory social security contributions; "
        "anchor D.61 additionally includes imputed and voluntary contributions")]
    # --- interest via GG D.41 history (D10, §6.1(3)) ---
    ameco = ExtSource(
        "EC_AMECO", R.ameco_series(iso3, "UYIG", 16),
        "AMECO UYIG: ESA gross GG interest payable (D.41), Commission "
        "redistribution of national accounts; same gross accrued concept",
        AMECO_XWALK, unit_factor=1000.0,  # AMECO chapter files are Mrd (bn)
        break_before=DEU_BREAK if iso3 == "DEU" else None,
        concept_flag="d41_gross_accrued")
    if iso3 == "GBR":
        out[("COFOG", "GF01_7")] = [
            ExtSource("ONS_PSF_INTEREST", R.ons_t2_series("D41", "payable"),
                      "GG D.41 payable, accrued, ESA Table 2 (same institution; "
                      "D10 fallback concept for COFOG 01.7)", AMECO_XWALK,
                      concept_flag="d41_gross_accrued"),
            ameco]
    else:
        out[("COFOG", "GF01_7")] = [ameco]
    # --- DEU expenditure 1991-94 via IMF GFS COFOG (§6.1(2): same national data) ---
    if iso3 == "DEU":
        for n in range(1, 11):
            code = f"GF{n:02d}"
            out[("COFOG", code)] = [ExtSource(
                "IMF_GFS", R.gfs_series(iso3, "cofog", f"{code}_T"),
                "IMF GFS COFOG: redistribution of the same Destatis ESA data "
                "(boundary ratio ~1.0 at 1995); XDC levels", GFS_XWALK,
                break_before=DEU_BREAK)]
    return out


def _grade(src: ExtSource, anchor: pd.Series) -> tuple[str, float | None, int | None]:
    """(grade, coverage_share, coverage_share_year) at the last common year (§9.2).

    §9 bands: B = 90-110% (close source, minor documented differences);
    C = 50-90% (major-component proxy); anything else = D (a source covering
    <50% or materially MORE than the line is a weak crosswalk, not a
    component) — D sources are never applied as extensions (D15 grades
    extensions B/C only); the line stops and the skip is recorded."""
    common = anchor.index.intersection(src.series.index)
    common = [y for y in common if src.series[y] > 0 and anchor[y] > 0]
    if not common:
        return "D", None, None
    y = int(max(common))
    share = float(src.series[y] * src.unit_factor / anchor[y])
    if 0.9 <= share <= 1.1:
        grade = "B"
    elif 0.5 <= share < 0.9:
        grade = "C"
    else:
        grade = "D"
    return grade, round(share, 4), y


def extend_line(iso3: str, classification: str, line_code: str,
                anchor: pd.Series, sources: list[ExtSource]
                ) -> tuple[list[dict], list[dict]]:
    """Backward-stitch one line. Returns (stitched value rows, boundary records).

    Row dicts: year, value, growth_rate, source + grading metadata; the §5
    packaging happens in build."""
    rows, boundaries = [], []
    if anchor.empty:
        return rows, boundaries
    first = int(anchor.index.min())
    value_next = float(anchor[first])   # Y_{t+1} at the current frontier
    frontier = first                    # deepest year with a value so far
    outgoing = "anchor"
    for src in sources:
        grade, share, share_year = _grade(src, anchor)
        if grade == "D":
            # source unusable as an extension (D15: B/C only); record the skip
            # so Gate 2's "why each line stops" is machine-documented
            boundaries.append({
                "iso3": iso3, "classification": classification,
                "line_code": line_code, "boundary_year": frontier,
                "outgoing_source": outgoing, "incoming_source": src.source_id,
                "anchor_value_lcu_mn": value_next, "growth_applied": None,
                "scope": src.concept_note, "break_flag": False,
                "grade": "D", "crosswalk_version": src.crosswalk_version,
                "coverage_share": share, "coverage_share_year": share_year,
                "variants": "not_applied_grade_D",
            })
            continue
        x = src.series
        t = frontier - 1
        started = False
        while (t in x.index and (t + 1) in x.index
               and x[t] > 0 and x[t + 1] > 0
               and (src.break_before is None or t >= src.break_before)):
            growth = float(x[t] / x[t + 1])
            value_t = value_next * growth
            rows.append({
                "year": t, "value": value_t, "growth_rate": growth,
                "source": src, "grade": grade, "coverage_share": share,
                "coverage_share_year": share_year,
                "anchor_year": first, "anchor_value": float(anchor[first]),
            })
            if not started:
                boundaries.append({
                    "iso3": iso3, "classification": classification,
                    "line_code": line_code, "boundary_year": frontier,
                    "outgoing_source": outgoing, "incoming_source": src.source_id,
                    "anchor_value_lcu_mn": value_next,
                    "growth_applied": growth,
                    "scope": src.concept_note,
                    "break_flag": bool(src.break_before is not None
                                       and src.break_before > int(x.index.min())),
                    "grade": grade, "crosswalk_version": src.crosswalk_version,
                    "coverage_share": share, "coverage_share_year": share_year,
                    "variants": "strict+maximum" if grade == "B" else "maximum_only",
                })
                started = True
            value_next = value_t
            frontier = t
            t -= 1
        if started:
            outgoing = src.source_id
    return rows, boundaries


def overlap_diagnostics(anchor: pd.Series, src: ExtSource) -> dict | None:
    """V5: growth bias and RMSE over overlap years (both series, consecutive)."""
    x = src.series
    years = sorted(set(anchor.index) & set(x.index))
    diffs = []
    for t0, t1 in zip(years, years[1:]):
        if t1 - t0 != 1:
            continue
        if anchor[t0] > 0 and x[t0] > 0 and anchor[t1] > 0 and x[t1] > 0:
            diffs.append((x[t1] / x[t0]) - (anchor[t1] / anchor[t0]))
    if not diffs:
        return None
    s = pd.Series(diffs)
    return {"n_overlap_growth": len(diffs), "bias": float(s.mean()),
            "rmse": float((s ** 2).mean() ** 0.5)}
