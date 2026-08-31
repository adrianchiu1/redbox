"""Stage 4 checks: V17 (`coverage_share_year` on every proxy/composite row),
plus the Gate 4 no-leakage assertion run as part of the suite (proxy and
C/D-graded rows must never appear in strict — V9 covers grades; this check
covers the §7.8 variant restriction and the D2 residual_method requirement)."""

from __future__ import annotations

import pandas as pd

from ggfiscal.build import load_canonical
from ggfiscal.validate.runner import Finding

PROXYLIKE = ("proxy_forecast", "composite_forecast")


def _rows(variant: str) -> pd.DataFrame:
    return pd.concat([load_canonical("COFOG", variant),
                      load_canonical("ESA_REV", variant)], ignore_index=True)


def check_v17() -> list[Finding]:
    """Every proxy/composite row carries coverage_share_year (ERROR) — and,
    per D2, a residual_method; §7.8 proxies must be maximum_extension only."""
    out = []
    for variant in ("strict", "maximum_extension"):
        df = _rows(variant)
        px = df[df.observation_type.isin(PROXYLIKE)
                | (df.growth_source_id.notna() & df.residual_method.notna())]
        bad = px[px.coverage_share.isna() | px.coverage_share_year.isna()]
        for _, r in bad.iterrows():
            out.append(Finding("V17", "ERROR",
                               f"{r.iso3}/{r.line_code}/{r.year}/{variant}",
                               "proxy/composite row lacks measured coverage "
                               "share + year (§9.2)"))
        nores = df[df.observation_type.isin(PROXYLIKE) & df.residual_method.isna()]
        for _, r in nores.iterrows():
            out.append(Finding("V17", "ERROR",
                               f"{r.iso3}/{r.line_code}/{r.year}/{variant}",
                               "proxy/composite row lacks residual_method (D2)"))
    strict = _rows("strict")
    leaked = strict[strict.observation_type == "proxy_forecast"]
    for _, r in leaked.iterrows():
        out.append(Finding("V17", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                           "single-component proxy in strict (§7.8: "
                           "maximum_extension only)"))
    return out or [Finding("V17", "OK", "-",
                           "every proxy/composite row carries coverage share, "
                           "year and residual_method; no proxy in strict")]


IMPLEMENTED = {"V17": check_v17}
