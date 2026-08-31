"""Stage 5 checks: V24 (base-year bridge tolerances, formalising the
D-S0-009 heuristic), V26 extended to the forecast side (exact additivity of
the §8.3 decomposition), V27 (net-interest cross-check present for every
(country, vintage, horizon)), V28 (every reconciliation table keyed by both
vintages)."""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.validate.runner import Finding


def _canonical(name: str) -> pd.DataFrame:
    path = config.repo_root() / "data" / "canonical" / f"{name}.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def check_v24() -> list[Finding]:
    """§8.2/V24 (WARN): FRA/DEU level gaps (TR, TE, NLB) within the
    base-bridge tolerance (% of TE) in all overlap years; GBR perimeter
    component stable — sigma of the NLB gap ratio below config."""
    tol = config.tolerances()["base_bridge_pct_of_te"]
    sigma_tol = config.tolerances()["gbr_perimeter_sigma_pct_te"]
    br = _canonical("weo_base_bridge")
    if br.empty:
        return [Finding("V24", "SKIP", "-", "no bridge computed")]
    out = []
    for (iso3, vintage), g in br.groupby(["iso3", "weo_vintage"]):
        if iso3 == "GBR":
            ratios = g.gap_nlb_pct_te.dropna()
            sigma = float(ratios.std()) if len(ratios) > 1 else 0.0
            if sigma > sigma_tol:
                out.append(Finding("V24", "WARN", f"{iso3}/{vintage}",
                                   f"NLB gap sigma {sigma:.3f}% of TE exceeds "
                                   f"{sigma_tol}% — perimeter component not "
                                   "stable"))
            continue
        for col in ("gap_tr_pct_te", "gap_te_pct_te", "gap_nlb_pct_te"):
            bad = g[g[col].abs() > tol]
            for _, r in bad.iterrows():
                out.append(Finding("V24", "WARN",
                                   f"{iso3}/{vintage}/{int(r.year)}",
                                   f"{col} = {r[col]:.3f}% beyond {tol}% of TE"))
    return out or [Finding("V24", "OK", "-",
                           f"FRA/DEU level gaps within {tol}% of TE in all "
                           f"overlap years; GBR NLB-gap sigma below {sigma_tol}%")]


def check_v26() -> list[Finding]:
    """History additivity (Stage 1 scope, delegated) plus §8.3 forecast-side
    additivity: covered + residuals + denominator (+ WEO internal wedge)
    equals the WEO change exactly."""
    from ggfiscal.reconcile.explanation import v26_forecast_check
    from ggfiscal.validate.stage1 import check_v26 as history_v26

    out = [f for f in history_v26() if f.severity != "OK"]
    for iso3, variant, vintage, h, err in v26_forecast_check():
        out.append(Finding("V26", "ERROR", f"{iso3}/{variant}/{vintage}/{h}",
                           f"forecast decomposition additivity error {err}"))
    return out or [Finding("V26", "OK", "-",
                           "history contributions sum to Δ(NLB/GDP) exactly; "
                           "forecast components sum to the WEO change exactly")]


def check_v27() -> list[Finding]:
    """Net-interest cross-check reported for every (country, variant,
    vintage, horizon) that the explanation table covers (§8.4)."""
    exp = _canonical("weo_explanation")
    ni = _canonical("net_interest_check")
    if exp.empty or ni.empty:
        return [Finding("V27", "ERROR", "-",
                        "reconciliation tables missing — run: ggfiscal reconcile")]
    want = set(map(tuple, exp[["iso3", "series_variant", "weo_vintage",
                               "horizon_year"]].drop_duplicates().values))
    have = set(map(tuple, ni[["iso3", "series_variant", "weo_vintage",
                              "horizon_year"]].values))
    out = []
    for key in sorted(want - have):
        out.append(Finding("V27", "ERROR", "/".join(map(str, key)),
                           "no net-interest cross-check row (§8.4)"))
    unnoted = ni[ni.ni_ours_mn.isna() & (ni.notes.astype(str).str.len() < 20)]
    for _, r in unnoted.iterrows():
        out.append(Finding("V27", "ERROR",
                           f"{r.iso3}/{r.weo_vintage}/{int(r.horizon_year)}",
                           "NI not computable but the row does not say why"))
    return out or [Finding("V27", "OK", "-",
                           f"net-interest cross-check present for all "
                           f"{len(want)} (country, variant, vintage, horizon) "
                           "cells; non-computable cells carry their reason "
                           "(R07 declared, OQ-6)")]


def check_v28() -> list[Finding]:
    """Every reconciliation table keyed by both vintages: weo_vintage on all
    rows everywhere; source_vintage_set_hash on the forecast-side tables."""
    out = []
    for name, needs_hash in (("weo_base_bridge", False),
                             ("weo_explanation", True),
                             ("net_interest_check", True),
                             ("weo_residual_history", True)):
        df = _canonical(name)
        if df.empty:
            out.append(Finding("V28", "ERROR", name, "table missing or empty"))
            continue
        if "weo_vintage" not in df.columns or df.weo_vintage.isna().any():
            out.append(Finding("V28", "ERROR", name,
                               "rows lack weo_vintage (§8.5)"))
        if needs_hash and ("source_vintage_set_hash" not in df.columns
                           or df.source_vintage_set_hash.isna().any()):
            out.append(Finding("V28", "ERROR", name,
                               "rows lack source_vintage_set_hash (§8.5)"))
    return out or [Finding("V28", "OK", "-",
                           "all reconciliation tables keyed by weo_vintage; "
                           "forecast tables carry source_vintage_set_hash")]


IMPLEMENTED = {"V24": check_v24, "V26": check_v26, "V27": check_v27,
               "V28": check_v28}
