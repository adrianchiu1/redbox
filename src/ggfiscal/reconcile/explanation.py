"""§8.3-8.5 forecast-side reconciliation: what the granular official
forecasts explain of each WEO balance path, and what they do not.

For each (country, variant, WEO vintage) and horizon year h > b, the WEO
balance-ratio change from base, ΔB = (GGXCNL/NGDP)_h − (GGXCNL/NGDP)_b, is
decomposed exactly (V26) into:

    covered-line contributions   r_i,h − r_i,b on the WEO NGDP path
                                 (signed: revenue +, expenditure −)
  + denominator effect per side  the same contributions on each line's own
                                 source GDP path minus the NGDP version
                                 (§8.3: reported, never absorbed)
  + resid_coverage per side      official-total change minus covered change,
                                 both on the national paths (the uncovered
                                 lines), where an independent total exists
  + resid_disagreement per side  WEO side change minus official-total change
  | resid_total per side         the two collapse where no independent total
                                 exists (§8.3), labelled as such
  + weo_internal_wedge           ΔB minus (ΔGGR/NGDP − ΔGGX/NGDP): rounding
                                 inside the WEO tables themselves, usually 0

The additivity is exact by construction (telescoping); V26 verifies it
numerically. Nothing is scaled or allocated (D13, D16, §8.6): residuals stay
lumps, and the "implied uncovered growth" memo rows are a plausibility
diagnostic, not a forecast (§8.3).

Independent totals (§8.1): AMECO URTG/UUTG with the AMECO UVGD GDP path —
for GBR too, because Q12's OBR-primary default is unreachable (OQ-6,
D-S3-001) and AMECO carries no UK levels at the base year (OQ-4), so GBR
sides carry `resid_total` at every horizon; FRA/DEU get the split through
the AMECO horizon (2027) and `resid_total` beyond.

§8.4: the net-interest cross-check is reported for every (country, variant,
vintage, horizon) even where it cannot be computed — R07 has no forecast
anywhere (declared; OQ-6), so `ni_ours` exists in no forecast year and the
receivable-side hole sits inside the revenue coverage residual. The rows
say so explicitly rather than being silently absent (V27).

§8.5: every table is keyed by (iso3, series_variant, weo_vintage,
source_vintage_set_hash); the residual time series across vintages is its
own deliverable (weo_residual_history.csv).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from ggfiscal import config
from ggfiscal.ingest.endpoints import weo_vintages
from ggfiscal.reconcile import bridge
from ggfiscal.standardise import readers as R

REV_LINES = [f"R{n:02d}" for n in range(1, 11)]
EXP_LINES = [f"GF{n:02d}" for n in range(1, 11)]

EXPLANATION_COLUMNS = [
    "iso3", "series_variant", "weo_vintage", "source_vintage_set_hash",
    "base_year", "horizon_year", "component_kind", "side", "line_code",
    "contribution_pp", "notes",
]
NI_COLUMNS = [
    "iso3", "series_variant", "weo_vintage", "source_vintage_set_hash",
    "base_year", "horizon_year", "ni_weo_mn", "gf01_7_mn", "r07_mn",
    "ni_ours_mn", "gap_mn", "notes",
]
RESIDUAL_COLUMNS = [
    "iso3", "series_variant", "weo_vintage", "source_vintage_set_hash",
    "base_year", "horizon_year", "side", "residual_kind", "contribution_pp",
]

VARIANTS = ("strict", "maximum_extension")


def source_vintage_set_hash(variant: str) -> str:
    """§8.5: hash of the forecast-source vintage set actually used by the
    variant — (source_id, recorded release) pairs from the register."""
    from ggfiscal.build import load_canonical

    df = pd.concat([load_canonical("COFOG", variant),
                    load_canonical("ESA_REV", variant)], ignore_index=True)
    used = sorted(set(df[df.is_forecast].growth_source_id.dropna()))
    reg = config.sources()
    parts = []
    for sid in used:
        ver = (reg.get(sid, {}).get("verification") or {})
        parts.append(f"{sid}:{ver.get('last_update_observed', '')}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def _line_frames(variant: str) -> pd.DataFrame:
    from ggfiscal.build import load_canonical

    df = pd.concat([load_canonical("COFOG", variant),
                    load_canonical("ESA_REV", variant)], ignore_index=True)
    return df[df.line_code.isin(REV_LINES + EXP_LINES)]


def _official_totals(iso3: str) -> dict[str, pd.Series]:
    """Independent official totals and their own GDP path, LCU mn (§8.1)."""
    return {"TR": R.ameco_series(iso3, "URTG", 16) * 1000.0,
            "TE": R.ameco_series(iso3, "UUTG", 16) * 1000.0,
            "GDP": R.ameco_series(iso3, "UVGD", 6) * 1000.0}


def _ratio_change(num: pd.Series, den: pd.Series, h: int, b: int) -> float | None:
    if any(t not in num.index or t not in den.index or not den[t]
           for t in (h, b)):
        return None
    return 100.0 * (float(num[h]) / float(den[h]) - float(num[b]) / float(den[b]))


def compute(vintages: list[str] | None = None
            ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (weo_explanation, net_interest_check, weo_residual_history)."""
    exp_rows, ni_rows, res_rows = [], [], []
    hashes = {v: source_vintage_set_hash(v) for v in VARIANTS}
    frames = {v: _line_frames(v) for v in VARIANTS}
    for vintage in (vintages or list(weo_vintages())):
        for iso3 in config.COUNTRIES:
            anchor = bridge.anchor_aggregates(iso3)
            weo = bridge.weo_aggregates(vintage, iso3)
            b = bridge.base_year(vintage, iso3, anchor)
            if b is None:
                continue
            off = _official_totals(iso3)
            horizon = int(weo["GGXCNL"].index.max())
            for variant in VARIANTS:
                svh = hashes[variant]
                df = frames[variant]
                sub = df[df.iso3 == iso3]
                piv_v = sub.pivot_table(index="year", columns="line_code",
                                        values="value_lcu_mn")
                piv_g = sub.pivot_table(index="year", columns="line_code",
                                        values="gdp_lcu_mn")
                # interest lines for §8.4 (GF01_7 sits inside GF01, not in the
                # Level I decomposition set)
                both = pd.concat([_load(variant, c) for c in ("COFOG", "ESA_REV")],
                                 ignore_index=True)
                interest = both[(both.iso3 == iso3)
                                & both.line_code.isin(["GF01_7", "R07"])]
                for h in range(b + 1, horizon + 1):
                    def add(kind, side, line, value, notes=None):
                        exp_rows.append({
                            "iso3": iso3, "series_variant": variant,
                            "weo_vintage": vintage,
                            "source_vintage_set_hash": svh, "base_year": b,
                            "horizon_year": h, "component_kind": kind,
                            "side": side, "line_code": line,
                            "contribution_pp": value, "notes": notes})

                    d_b = _ratio_change(weo["GGXCNL"], weo["NGDP"], h, b)
                    if d_b is None:
                        continue
                    w_side = {"revenue": _ratio_change(weo["GGR"], weo["NGDP"], h, b),
                              "expenditure": _ratio_change(weo["GGX"], weo["NGDP"], h, b)}
                    covered_total = 0.0
                    for side, lines, sign, off_key in (
                            ("revenue", REV_LINES, 1.0, "TR"),
                            ("expenditure", EXP_LINES, -1.0, "TE")):
                        c_weo = c_nat = 0.0
                        for line in lines:
                            if line not in piv_v.columns:
                                continue
                            v_b, v_h = piv_v[line].get(b), piv_v[line].get(h)
                            g_b, g_h = piv_g[line].get(b), piv_g[line].get(h)
                            if any(pd.isna(x) for x in (v_b, v_h, g_b, g_h)):
                                continue
                            contrib_weo = 100.0 * (v_h / float(weo["NGDP"][h])
                                                   - v_b / float(weo["NGDP"][b]))
                            contrib_nat = 100.0 * (v_h / g_h - v_b / g_b)
                            c_weo += contrib_weo
                            c_nat += contrib_nat
                            add("covered_line", side, line, sign * contrib_weo)
                            covered_total += sign * contrib_weo
                        de = c_nat - c_weo
                        add("denom_effect", side, None, sign * de,
                            "covered contributions on the lines' own source "
                            "GDP paths minus the WEO NGDP version (§8.3; "
                            "reported, never absorbed)")
                        o_change = _ratio_change(off[off_key], off["GDP"], h, b)
                        if o_change is not None:
                            rc = o_change - c_nat
                            rd = w_side[side] - o_change
                            add("resid_coverage", side, None, sign * rc,
                                "official total (EC_AMECO, Q12 deviation for "
                                "GBR per D-S3-001) minus covered lines, both "
                                "on national GDP paths: the uncovered lines")
                            add("resid_disagreement", side, None, sign * rd,
                                "WEO side change minus the official total's "
                                "change, each on its own GDP path")
                            # implied uncovered growth (plausibility memo)
                            _implied_memo(add, side, off, off_key, piv_v,
                                          lines, b, h)
                        else:
                            rt = w_side[side] - c_nat
                            add("resid_total", side, None, sign * rt,
                                "no independent official total at this "
                                "horizon (AMECO envelope ends 2027; GBR has "
                                "no level at the base year, OQ-4) — coverage "
                                "and disagreement residuals collapse (§8.3)")
                    wedge = d_b - (w_side["revenue"] - w_side["expenditure"])
                    add("weo_internal_wedge", "balance", None, wedge,
                        "GGXCNL change minus (GGR change - GGX change) inside "
                        "the WEO tables; rounding only")
                    add("weo_change", "balance", None, d_b,
                        "Δ((GGXCNL/NGDP)) from base year; the decomposition "
                        "target — components above sum to this exactly (V26)")
                    add("covered_total", "balance", None, covered_total,
                        "sum of signed covered-line contributions — what the "
                        "granular official forecasts explain of the WEO change")
                    if abs(d_b) > 1e-9:
                        add("explained_share", "balance", None,
                            covered_total / d_b,
                            "covered_total / weo_change (a ratio, not pp): "
                            "the Gate 5 headline number")
                    # §8.4 net-interest cross-check row (always present, V27)
                    ni_rows.append(_ni_row(iso3, variant, vintage, svh, b, h,
                                           weo, interest))
    exp_df = pd.DataFrame(exp_rows, columns=EXPLANATION_COLUMNS)
    ni_df = pd.DataFrame(ni_rows, columns=NI_COLUMNS)
    res = exp_df[exp_df.component_kind.isin(
        ["resid_coverage", "resid_disagreement", "resid_total"])]
    res_df = res.rename(columns={"component_kind": "residual_kind"})[
        ["iso3", "series_variant", "weo_vintage", "source_vintage_set_hash",
         "base_year", "horizon_year", "side", "residual_kind",
         "contribution_pp"]]
    return exp_df, ni_df, res_df


def _load(variant: str, cls: str) -> pd.DataFrame:
    from ggfiscal.build import load_canonical

    return load_canonical(cls, variant)


def _implied_memo(add, side, off, off_key, piv_v, lines, b, h) -> None:
    """§8.3: resid_coverage re-expressed as the implied annualised nominal
    growth of the uncovered lines under the official total, with the same
    lines' historical growth alongside. Diagnostic, not a forecast."""
    cov_b = sum(float(piv_v[ln].get(b)) for ln in lines
                if ln in piv_v.columns and pd.notna(piv_v[ln].get(b))
                and pd.notna(piv_v[ln].get(h)))
    cov_h = sum(float(piv_v[ln].get(h)) for ln in lines
                if ln in piv_v.columns and pd.notna(piv_v[ln].get(b))
                and pd.notna(piv_v[ln].get(h)))
    if any(t not in off[off_key].index for t in (b, h)):
        return
    uncov_b = float(off[off_key][b]) - cov_b
    uncov_h = float(off[off_key][h]) - cov_h
    if uncov_b > 0 and uncov_h > 0 and h > b:
        implied = 100.0 * ((uncov_h / uncov_b) ** (1.0 / (h - b)) - 1.0)
        add("implied_uncovered_growth", side, None, implied,
            "annualised nominal growth of the uncovered lines implied by the "
            "official total, % per year (NOT pp of GDP; §8.3 plausibility "
            "diagnostic, not a forecast)")
        # historical growth of the same uncovered set over the 5 years to b
        t0 = b - 5
        cols = [ln for ln in lines if ln in piv_v.columns
                and pd.notna(piv_v[ln].get(b)) and pd.notna(piv_v[ln].get(h))]
        all_cols = [ln for ln in lines if ln in piv_v.columns]
        hist_b = sum(float(piv_v[ln].get(b)) for ln in all_cols
                     if ln not in cols and pd.notna(piv_v[ln].get(b)))
        hist_0 = sum(float(piv_v[ln].get(t0)) for ln in all_cols
                     if ln not in cols and pd.notna(piv_v[ln].get(t0)))
        if hist_0 > 0 and hist_b > 0:
            hist = 100.0 * ((hist_b / hist_0) ** (1.0 / 5) - 1.0)
            add("historical_uncovered_growth", side, None, hist,
                "annualised nominal growth of the same uncovered lines over "
                f"the five anchor years to {b}, % per year")


def _ni_row(iso3, variant, vintage, svh, b, h, weo, interest) -> dict:
    ni_weo = (float(weo["GGXONLB"][h]) - float(weo["GGXCNL"][h])
              if h in weo["GGXONLB"].index and h in weo["GGXCNL"].index else None)
    piv = interest.pivot_table(index="year", columns="line_code",
                               values="value_lcu_mn")
    gf = piv["GF01_7"].get(h) if "GF01_7" in piv.columns else None
    r07 = piv["R07"].get(h) if "R07" in piv.columns else None
    gf = float(gf) if gf is not None and pd.notna(gf) else None
    r07 = float(r07) if r07 is not None and pd.notna(r07) else None
    ni_ours = gf - r07 if gf is not None and r07 is not None else None
    gap = (ni_ours - ni_weo) if ni_ours is not None and ni_weo is not None else None
    if ni_ours is not None:
        note = "gap contributes to resid_disagreement (§8.4)"
    elif gf is not None:
        note = ("R07 has no forecast anywhere (declared, "
                "forecast_declarations.csv; OQ-6): NI_ours not computable — "
                "gross GF01_7 reported alone; the receivable-side hole sits "
                "in the revenue coverage residual")
    else:
        note = (f"neither interest line has a value at {h} (GF01_7 horizon "
                "2027, OQ-7 withheld DSM leg; R07 declared) — WEO NI reported "
                "alone")
    return {"iso3": iso3, "series_variant": variant, "weo_vintage": vintage,
            "source_vintage_set_hash": svh, "base_year": b, "horizon_year": h,
            "ni_weo_mn": ni_weo, "gf01_7_mn": gf, "r07_mn": r07,
            "ni_ours_mn": ni_ours, "gap_mn": gap, "notes": note}


def write(canonical: Path | None = None) -> dict[str, Path]:
    root = canonical or config.repo_root() / "data" / "canonical"
    root.mkdir(parents=True, exist_ok=True)
    exp_df, ni_df, res_df = compute()
    out = {}
    for name, df in (("weo_explanation", exp_df),
                     ("net_interest_check", ni_df),
                     ("weo_residual_history", res_df)):
        dest = root / f"{name}.csv"
        df.to_csv(dest, index=False)
        out[name] = dest
    return out


def v26_forecast_check() -> list[tuple[str, str, str, int, float]]:
    """(iso3, variant, vintage, horizon, |components − weo_change|) failures.
    Exact additivity per §8.3/V26."""
    path = config.repo_root() / "data" / "canonical" / "weo_explanation.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    bad = []
    parts = df[df.component_kind.isin(
        ["covered_line", "denom_effect", "resid_coverage",
         "resid_disagreement", "resid_total", "weo_internal_wedge"])]
    target = df[df.component_kind == "weo_change"]
    key = ["iso3", "series_variant", "weo_vintage", "horizon_year"]
    sums = parts.groupby(key).contribution_pp.sum()
    for _, r in target.iterrows():
        k = (r.iso3, r.series_variant, r.weo_vintage, r.horizon_year)
        err = abs(sums.get(k, float("nan")) - r.contribution_pp)
        if not (err < 1e-9):
            bad.append((r.iso3, r.series_variant, r.weo_vintage,
                        int(r.horizon_year), float(err)))
    return bad
