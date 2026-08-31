"""Stage 2 checks: V5 (overlap-growth diagnostic), V6 (boundary growth equals
recorded source growth — recomputed independently from the raw sources),
V13 (concept compatibility note per stitch), V25 (OECD RS reconciliation on
tax lines in overlap years).

V5 thresholds are not numerically fixed by §10/Q4; the WARN trigger used here
(|bias| > 0.01 or RMSE > 0.05 on annual growth factors) is recorded in
DECISIONS D-S2-002 — below it the diagnostic is reported at OK severity.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.build import anchor_series, load_canonical
from ggfiscal.validate.runner import Finding

V5_BIAS_WARN = 0.01
V5_RMSE_WARN = 0.05


def _stitched(variant: str) -> pd.DataFrame:
    df = pd.concat([load_canonical("COFOG", variant),
                    load_canonical("ESA_REV", variant)], ignore_index=True)
    return df[df.observation_type == "stitched_actual"]


def _ext_series() -> dict[tuple[str, str, str], "pd.Series"]:
    """(iso3, line_code, source_id) -> extension source series (raw units)."""
    from ggfiscal.stitch.backward import extensions_for

    out = {}
    for iso3 in config.COUNTRIES:
        for (cls, line), sources in extensions_for(iso3).items():
            for src in sources:
                out[(iso3, line, src.source_id)] = src.series
    return out


def check_v5() -> list[Finding]:
    from ggfiscal.stitch.backward import extensions_for, overlap_diagnostics

    out = []
    for iso3 in config.COUNTRIES:
        anchors = anchor_series(iso3)
        for (cls, line), sources in extensions_for(iso3).items():
            anchor = anchors.get((cls, line), {}).get("series")
            if anchor is None or anchor.empty:
                continue
            for src in sources:
                d = overlap_diagnostics(anchor, src)
                if d is None:
                    continue
                sev = ("WARN" if abs(d["bias"]) > V5_BIAS_WARN
                       or d["rmse"] > V5_RMSE_WARN else "OK")
                out.append(Finding(
                    "V5", sev, f"{iso3}/{line}/{src.source_id}",
                    f"overlap growth: bias {d['bias']:+.4f}, rmse {d['rmse']:.4f} "
                    f"over {d['n_overlap_growth']} year-pairs"))
    return out or [Finding("V5", "OK", "-", "no stitches to diagnose")]


def check_v6() -> list[Finding]:
    """Recompute X_t/X_{t+1} from the raw extension series and compare with
    both the recorded growth_rate and the chained values."""
    ext = _ext_series()
    out = []
    for variant in ("strict", "maximum_extension"):
        st = _stitched(variant)
        for (iso3, line), g in st.groupby(["iso3", "line_code"]):
            g = g.sort_values("year")
            values = dict(zip(g.year, g.value_lcu_mn))
            for _, r in g.iterrows():
                x = ext.get((iso3, line, r.growth_source_id))
                if x is None:
                    out.append(Finding("V6", "ERROR", f"{iso3}/{line}/{r.year}",
                                       f"unknown growth source {r.growth_source_id}"))
                    continue
                t = int(r.year)
                if t not in x.index or (t + 1) not in x.index:
                    out.append(Finding("V6", "ERROR", f"{iso3}/{line}/{t}",
                                       "source lacks the boundary years"))
                    continue
                src_growth = float(x[t] / x[t + 1])
                if abs(src_growth - r.growth_rate) > 1e-9 * max(1.0, abs(src_growth)):
                    out.append(Finding("V6", "ERROR", f"{iso3}/{line}/{t}",
                                       f"recorded growth {r.growth_rate} != source "
                                       f"growth {src_growth}"))
                next_val = values.get(t + 1)
                if next_val is not None and abs(r.value_lcu_mn - next_val * src_growth) \
                        > 1e-6 * max(1.0, abs(next_val)):
                    out.append(Finding("V6", "ERROR", f"{iso3}/{line}/{t}",
                                       "chained value != Y_{t+1} x growth"))
    return out or [Finding("V6", "OK", "-",
                           "every stitched value reproduces from the raw source growth")]


def check_v13() -> list[Finding]:
    out = []
    for variant in ("strict", "maximum_extension"):
        st = _stitched(variant)
        bad = st[st.notes.isna() | (st.notes.astype(str).str.len() < 20)
                 | st.crosswalk_version.isna()]
        for _, r in bad.iterrows():
            out.append(Finding("V13", "ERROR",
                               f"{r.iso3}/{r.line_code}/{r.year}/{variant}",
                               "stitched row lacks a concept compatibility note "
                               "or crosswalk version"))
    return out or [Finding("V13", "OK", "-",
                           "every stitched row carries a concept note and crosswalk")]


def check_v25() -> list[Finding]:
    out = []
    tol = config.tolerances()["oecd_rs_reconciliation_pct"]
    df = load_canonical("ESA_REV", "strict")
    bad = df[df.oecd_rs_diff_pct.notna() & (df.oecd_rs_diff_pct.abs() > tol)]
    for _, r in bad.iterrows():
        out.append(Finding("V25", "WARN", f"{r.iso3}/{r.line_code}/{r.year}",
                           f"OECD RS diff {r.oecd_rs_diff_pct}% beyond {tol}% "
                           "(concept wedge carried by the crosswalk)"))
    return out or [Finding("V25", "OK", "-",
                           f"OECD RS within {tol}% on tax lines where present")]


IMPLEMENTED = {"V5": check_v5, "V6": check_v6, "V13": check_v13, "V25": check_v25}
