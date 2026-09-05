"""Stage 3 checks: V10 (no forecast beyond source horizon), V11 (no
superseded source), V13 extended to forward stitches, V15 (envelope), V16
(short/long-term overlap divergence), V18 (register URLs resolve or archived
copy present).

V16's WARN threshold is not numerically fixed by §10/Q4; the trigger used here
(|annual growth divergence| > 0.02 between the short- and long-term source in
an overlap year) is recorded in DECISIONS D-S3-005 — below it the diagnostic
reports at OK severity with its stats.

V18 is evaluated offline by design: a URL counts as resolving when the live
harvest snapshotted it this session (an archived copy exists, D8) or its
register verification records a live resolution; gate runs must not depend on
network availability. Blocked hosts therefore surface as WARN entries naming
the block (OQ-6), which is the intended visibility.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.build import anchor_series, load_canonical
from ggfiscal.validate.runner import Finding

def _v16_threshold() -> float:
    """D-S3-005: configurable in countries.yaml tolerances (Q4 space)."""
    return config.tolerances().get("v16_overlap_divergence", 0.02)

VERIFIED_STATUSES = {"resolved_live", "verified", "confirmed_search", "confirmed_live"}


def _forecast_rows(variant: str) -> pd.DataFrame:
    df = pd.concat([load_canonical("COFOG", variant),
                    load_canonical("ESA_REV", variant)], ignore_index=True)
    return df[df.is_forecast]


def _horizons() -> dict[tuple[str, str, str], int]:
    """(iso3, line_code, source_id) -> horizon year, from the live specs."""
    from ggfiscal.forecast.forward import forecasts_for

    out = {}
    for iso3 in config.COUNTRIES:
        for (cls, line), sources in forecasts_for(iso3).items():
            for src in sources:
                out[(iso3, line, src.source_id)] = src.horizon_year
    return out


def check_v10() -> list[Finding]:
    """No forecast beyond the source horizon, minus the §7.10 conversion loss
    (one year, for FY-converted rows)."""
    horizons = _horizons()
    out = []
    for variant in ("strict", "maximum_extension"):
        for _, r in _forecast_rows(variant).iterrows():
            h = horizons.get((r.iso3, r.line_code, r.growth_source_id))
            if h is None:
                out.append(Finding("V10", "ERROR",
                                   f"{r.iso3}/{r.line_code}/{r.year}/{variant}",
                                   f"forecast row from unregistered source "
                                   f"{r.growth_source_id}"))
                continue
            if pd.notna(r.period_conversion_method):
                h -= 1  # §7.10: conversion consumes one horizon year
            if r.year > h:
                out.append(Finding("V10", "ERROR",
                                   f"{r.iso3}/{r.line_code}/{r.year}/{variant}",
                                   f"forecast year {r.year} beyond source "
                                   f"horizon {h} ({r.growth_source_id})"))
    return out or [Finding("V10", "OK", "-",
                           "no forecast row beyond its source horizon")]


def check_v11() -> list[Finding]:
    """No superseded source where a newer applicable vintage exists: every
    source used by a forecast row must be current in the register (§6.4) —
    no `superseded_by`, and the row itself must not be marked superseded."""
    sources = config.sources()
    out = []
    for variant in ("strict", "maximum_extension"):
        fc = _forecast_rows(variant)
        for sid in sorted(set(fc.growth_source_id.dropna())):
            entry = sources.get(sid, {})
            if not entry:
                out.append(Finding("V11", "ERROR", f"register/{sid}",
                                   "forecast source missing from the register"))
                continue
            if entry.get("superseded_by"):
                out.append(Finding("V11", "ERROR", f"register/{sid}",
                                   f"superseded by {entry['superseded_by']} but "
                                   "still used in forecast rows"))
        bad = fc[fc.source_status.notna() & (fc.source_status != "current")]
        for _, r in bad.iterrows():
            out.append(Finding("V11", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                               f"row carries source_status {r.source_status}"))
    return out or [Finding("V11", "OK", "-",
                           "every forecast source is the latest registered vintage")]


def check_v6() -> list[Finding]:
    """V6 extended: backward stitches per Stage 2, plus every forward row
    (newer-actual stitches and forecasts) re-verified against the forecast
    specs — recorded growth must equal the source growth (§7.2/§7.5) and each
    chained value must equal Y_{t-1} × growth."""
    from ggfiscal.forecast.forward import _growth, forecasts_for
    from ggfiscal.validate.stage2 import check_v6 as backward_v6

    specs = {}
    for iso3 in config.COUNTRIES:
        for (cls, line), sources in forecasts_for(iso3).items():
            for src in sources:
                specs[(iso3, line, src.source_id)] = src
    anchors = {iso3: anchor_series(iso3) for iso3 in config.COUNTRIES}
    out = [f for f in backward_v6() if f.severity != "OK"]
    for variant in ("strict", "maximum_extension"):
        df = pd.concat([load_canonical("COFOG", variant),
                        load_canonical("ESA_REV", variant)], ignore_index=True)
        fwd = df[df.growth_source_id.notna() & (df.year > df.anchor_year)]
        for (iso3, cls, line), g in fwd.groupby(["iso3", "classification", "line_code"]):
            g = g.sort_values("year")
            anchor = anchors[iso3][(cls, line)]["series"]
            values = dict(zip(g.year, g.value_lcu_mn))
            values[int(anchor.index.max())] = float(anchor[anchor.index.max()])
            for _, r in g.iterrows():
                src = specs.get((iso3, line, r.growth_source_id))
                if src is None:
                    out.append(Finding("V6", "ERROR", f"{iso3}/{line}/{r.year}",
                                       f"unknown forecast source {r.growth_source_id}"))
                    continue
                t = int(r.year)
                src_growth = _growth(src, t)
                if src_growth is None:
                    out.append(Finding("V6", "ERROR", f"{iso3}/{line}/{t}",
                                       "source lacks the boundary years"))
                    continue
                if abs(src_growth - r.growth_rate) > 1e-9 * max(1.0, abs(src_growth)):
                    out.append(Finding("V6", "ERROR", f"{iso3}/{line}/{t}",
                                       f"recorded growth {r.growth_rate} != source "
                                       f"growth {src_growth}"))
                prev_val = values.get(t - 1)
                if prev_val is not None and abs(r.value_lcu_mn - prev_val * src_growth) \
                        > 1e-6 * max(1.0, abs(prev_val)):
                    out.append(Finding("V6", "ERROR", f"{iso3}/{line}/{t}",
                                       "chained value != Y_{t-1} x growth"))
    return out or [Finding("V6", "OK", "-",
                           "every stitched and forecast value reproduces from "
                           "the recorded source growth, both directions")]


def check_v13() -> list[Finding]:
    """Concept compatibility note per stitch — backward stitches (Stage 2
    scope, delegated) plus every forward/forecast row."""
    from ggfiscal.validate.stage2 import check_v13 as backward_v13

    out = [f for f in backward_v13() if f.severity != "OK"]
    for variant in ("strict", "maximum_extension"):
        fc = _forecast_rows(variant)
        bad = fc[fc.notes.isna() | (fc.notes.astype(str).str.len() < 20)
                 | fc.crosswalk_version.isna()]
        for _, r in bad.iterrows():
            out.append(Finding("V13", "ERROR",
                               f"{r.iso3}/{r.line_code}/{r.year}/{variant}",
                               "forecast row lacks a concept compatibility "
                               "note or crosswalk version"))
    return out or [Finding("V13", "OK", "-",
                           "every stitched and forecast row carries a concept "
                           "note and crosswalk")]


def _envelopes(iso3: str) -> tuple[pd.Series, pd.Series]:
    """(TR, TE) envelope levels in LCU mn per year (D4). FRA/DEU: AMECO
    URTG/UUTG. GBR: OBR PS current receipts / TME per §15 Q12's OBR-primary
    default, exercisable since the OQ-6 partial unblock (D-S7-002) — public
    sector perimeter (PSCR ≈ 0.97 × GG TR, TME ≈ 0.95 × GG TE, stable), FY
    converted per §7.10; AMECO remains the cross-check."""
    from ggfiscal.forecast.forward import fy_to_cy
    from ggfiscal.standardise.readers import ameco_series, obr_databank

    if iso3 == "GBR":
        return (fy_to_cy(obr_databank("Aggregates (£bn)",
                                      "Public sector current receipts")) * 1000.0,
                fy_to_cy(obr_databank("Aggregates (£bn)",
                                      "Total managed expenditure")) * 1000.0)
    return (ameco_series(iso3, "URTG", 16) * 1000.0,
            ameco_series(iso3, "UUTG", 16) * 1000.0)


def check_v15() -> list[Finding]:
    """Forecast: Σ covered Level I ≤ envelope TE × (1 + tol); Σ covered
    revenue ≤ envelope TR × (1 + tol). Checked in every forecast year where
    the envelope has a value (the AMECO envelope ends 2027)."""
    tol = config.tolerances()["envelope_excess_pct"] / 100.0
    out = []
    checked = 0
    for variant in ("strict", "maximum_extension"):
        fc = _forecast_rows(variant)
        for iso3 in config.COUNTRIES:
            tr_env, te_env = _envelopes(iso3)
            sub = fc[fc.iso3 == iso3]
            for year, g in sub.groupby("year"):
                exp_sum = g[(g.classification == "COFOG")
                            & (g.line_level == "1")].value_lcu_mn.sum()
                rev_sum = g[g.classification == "ESA_REV"].value_lcu_mn.sum()
                if year in te_env.index and exp_sum:
                    checked += 1
                    if exp_sum > float(te_env[year]) * (1 + tol):
                        out.append(Finding("V15", "WARN", f"{iso3}/{variant}/{year}",
                                           f"covered Level I sum {exp_sum:.0f} exceeds "
                                           f"envelope TE {te_env[year]:.0f} + {tol:.0%}"))
                if year in tr_env.index and rev_sum:
                    checked += 1
                    if rev_sum > float(tr_env[year]) * (1 + tol):
                        out.append(Finding("V15", "WARN", f"{iso3}/{variant}/{year}",
                                           f"covered revenue sum {rev_sum:.0f} exceeds "
                                           f"envelope TR {tr_env[year]:.0f} + {tol:.0%}"))
    return out or [Finding("V15", "OK", "-",
                           f"covered sums within the envelope in all {checked} "
                           "checked (country, variant, year, side) cells")]


def check_v16() -> list[Finding]:
    """Short/long-term overlap divergence (D12): annual growth of the
    long-term source vs the short-term source in the years both cover."""
    from ggfiscal.forecast.forward import forecasts_for, overlap_divergence

    threshold = _v16_threshold()
    out = []
    for iso3 in config.COUNTRIES:
        for (cls, line), sources in forecasts_for(iso3).items():
            if len(sources) < 2:
                continue
            recs = overlap_divergence(iso3, cls, line, sources)
            if not recs:
                continue
            worst = max(recs, key=lambda r: abs(r["divergence"]))
            sev = "WARN" if abs(worst["divergence"]) > threshold else "OK"
            out.append(Finding(
                "V16", sev, f"{iso3}/{line}",
                f"{worst['st_source']} vs {worst['lt_source']} growth over "
                f"{len(recs)} overlap years: max divergence "
                f"{worst['divergence']:+.4f} in {worst['year']} "
                f"(threshold {threshold}; D12: above it the long-term leg is "
                "withheld pending committee review, not auto-joined — see "
                "forecast_boundaries.csv 'not_applied_v16_divergence' and "
                "OQ-7)"))
    return out or [Finding("V16", "OK", "-",
                           "no line carries both a short- and long-term source")]


def check_v18() -> list[Finding]:
    """Register URLs resolve or an archived copy is present. Offline
    evaluation (see module docstring): a session snapshot (D8) or a recorded
    live resolution counts; blocked/unverified entries WARN."""
    from ggfiscal.standardise.readers import latest_snapshots

    snapped = {sid for (sid, _part) in latest_snapshots()}
    out = []
    for sid, src in config.sources().items():
        has_url = bool((src.get("api") or {}).get("landing")
                       or (src.get("api") or {}).get("url")
                       or src.get("landing"))
        status = str((src.get("verification") or {}).get("status", ""))
        if sid in snapped or status in VERIFIED_STATUSES:
            continue
        note = str((src.get("verification") or {}).get("note", ""))
        out.append(Finding("V18", "WARN", f"register/{sid}",
                           (f"no archived copy and unresolved URL "
                            f"(status: {status or 'none'}"
                            + (f"; {note}" if note else "") + ")")
                           if has_url else
                           f"no URL recorded and no archived copy "
                           f"(status: {status or 'none'}"
                           + (f"; {note}" if note else "") + ")"))
    return out or [Finding("V18", "OK", "-",
                           "every register entry resolves live or has an "
                           "archived snapshot")]


IMPLEMENTED = {"V6": check_v6, "V10": check_v10, "V11": check_v11,
               "V13": check_v13, "V15": check_v15, "V16": check_v16,
               "V18": check_v18}
