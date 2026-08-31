"""§8.3 dynamics decomposition — history side (Stage 1 scope).

For years where all 20 Level I lines exist (10 COFOG + 10 ESA_REV) plus GDP:
r_i,t = 100 * V_i,t / GDP_t; the contribution of line i to the change in the
balance ratio is c_i,t = +Δr_i,t for revenue lines, −Δr_i,t for expenditure
lines. By construction Σ_i c_i,t = Δ((ΣR − ΣE)/GDP)_t exactly (V26).

ΣR − ΣE is the sum-based balance. It differs from the anchor's own B.9 only
by the anchor's internal rounding (V2/V22/V23 police that at 0.1%); the
difference is reported as its own row (`ANCHOR_B9_DELTA`), never allocated
to lines (D16). The WEO comparison column (Δ(GGXCNL/NGDP) per §8.3) is
attached for the latest vintage where the year is covered.

Forecast-side decomposition (residuals, denominator effect) arrives at Stage 5.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from ggfiscal import config
from ggfiscal.ingest.endpoints import WEO_VINTAGES
from ggfiscal.standardise import readers as R

REV_LINES = [f"R{n:02d}" for n in range(1, 11)]
EXP_LINES = [f"GF{n:02d}" for n in range(1, 11)]
COLUMNS = ["iso3", "series_variant", "year", "line_code", "contribution_pp",
           "kind", "notes"]


def decompose(variant: str = "strict") -> pd.DataFrame:
    from ggfiscal.build import load_canonical, load_ledger

    exp = load_canonical("COFOG", variant)
    rev = load_canonical("ESA_REV", variant)
    if exp.empty or rev.empty:
        return pd.DataFrame(columns=COLUMNS)
    latest_vintage = next(iter(WEO_VINTAGES))
    ledger = load_ledger()
    rows = []
    for iso3 in config.COUNTRIES:
        e = exp[exp.iso3 == iso3].pivot_table(index="year", columns="line_code",
                                              values="value_lcu_mn")
        r = rev[rev.iso3 == iso3].pivot_table(index="year", columns="line_code",
                                              values="value_lcu_mn")
        gdp = exp[exp.iso3 == iso3].groupby("year").gdp_lcu_mn.first()
        led = ledger[(ledger.iso3 == iso3) & (ledger.series_variant == variant)] \
            .set_index("year")
        years = sorted(set(e.index) & set(r.index) & set(gdp.dropna().index))
        years = [y for y in years
                 if all(pd.notna(e.get(c, pd.Series(dtype=float)).get(y))
                        for c in EXP_LINES)
                 and all(pd.notna(r.get(c, pd.Series(dtype=float)).get(y))
                         for c in REV_LINES)]
        weo_cnl = R.weo_series(latest_vintage, iso3, "GGXCNL") / 1e6
        weo_gdp = R.weo_series(latest_vintage, iso3, "NGDP") / 1e6
        for t0, t1 in zip(years, years[1:]):
            if t1 - t0 != 1:
                continue  # no growth across a gap (§7.12)
            total = 0.0
            for c in REV_LINES:
                contrib = 100 * (r[c][t1] / gdp[t1] - r[c][t0] / gdp[t0])
                total += contrib
                rows.append({"iso3": iso3, "series_variant": variant, "year": t1,
                             "line_code": c, "contribution_pp": contrib,
                             "kind": "revenue", "notes": None})
            for c in EXP_LINES:
                contrib = -100 * (e[c][t1] / gdp[t1] - e[c][t0] / gdp[t0])
                total += contrib
                rows.append({"iso3": iso3, "series_variant": variant, "year": t1,
                             "line_code": c, "contribution_pp": contrib,
                             "kind": "expenditure", "notes": None})
            rows.append({"iso3": iso3, "series_variant": variant, "year": t1,
                         "line_code": "NLB_CHANGE_SUM", "contribution_pp": total,
                         "kind": "total",
                         "notes": "Δ((ΣR-ΣE)/GDP); V26: equals the line sum exactly"})
            if t0 in led.index and t1 in led.index:
                anchor_delta = 100 * (led.nlb_lcu_mn[t1] / gdp[t1]
                                      - led.nlb_lcu_mn[t0] / gdp[t0])
                rows.append({"iso3": iso3, "series_variant": variant, "year": t1,
                             "line_code": "ANCHOR_B9_DELTA",
                             "contribution_pp": anchor_delta - total,
                             "kind": "memo",
                             "notes": "anchor Δ(B9/GDP) minus the sum-based change; "
                                      "rounding/vintage wedge, never allocated (D16)"})
            if all(t in weo_cnl.index and t in weo_gdp.index for t in (t0, t1)):
                weo_delta = 100 * (weo_cnl[t1] / weo_gdp[t1]
                                   - weo_cnl[t0] / weo_gdp[t0])
                rows.append({"iso3": iso3, "series_variant": variant, "year": t1,
                             "line_code": "WEO_GGXCNL_DELTA",
                             "contribution_pp": weo_delta, "kind": "memo",
                             "notes": f"WEO {latest_vintage} Δ(GGXCNL/NGDP), "
                                      "comparison column per §8.3"})
    return pd.DataFrame(rows, columns=COLUMNS)


def write(path: Path | None = None) -> Path:
    dest = path or config.repo_root() / "data" / "canonical" / "deficit_dynamics.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    frames = [decompose(v) for v in ("strict", "maximum_extension")]
    df = pd.concat(frames, ignore_index=True)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for rec in df.to_dict("records"):
            w.writerow(rec)
    return dest


def v26_check(variant: str = "strict") -> list[tuple[str, int, float]]:
    """(iso3, year, |sum of line contributions − NLB_CHANGE_SUM|) violations."""
    df = decompose(variant)
    bad = []
    for (iso3, year), g in df.groupby(["iso3", "year"]):
        lines_sum = g[g.kind.isin(["revenue", "expenditure"])].contribution_pp.sum()
        total = g[g.line_code == "NLB_CHANGE_SUM"].contribution_pp
        if len(total) != 1:
            bad.append((iso3, int(year), float("nan")))
            continue
        err = abs(lines_sum - float(total.iloc[0]))
        if err > 1e-9:
            bad.append((iso3, int(year), err))
    return bad
