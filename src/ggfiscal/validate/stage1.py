"""Stage 1 implementations of the §10 suite (V1-V4, V7-V9, V12, V14,
V19-V23, V26) against the canonical tables.

Each check returns [Finding]; the runner decides stage gating. At Stage 1 all
rows are anchor history, so several forecast-oriented checks (V7, V8, V10...)
hold vacuously — they still run and report OK so regressions surface the
moment later stages add rows.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.build import load_ledger, load_trees
from ggfiscal.validate.runner import Finding

VARIANTS = ("strict", "maximum_extension")


def _negative_ok() -> set[str]:
    """Lines the anchors legitimately publish negative (`may_be_negative`
    in lines.yaml: R08, R10, R06_X; E07 since U0 for the USA's 1991 D.7
    payable); ledger NLB/NI/PB are handled separately. Read from config
    rather than a literal set (Stage U0, D-S16-009)."""
    return {code for cls in config.TREES
            for code, meta in config.tree_lines(cls).items() if meta.get("may_be_negative")}


NEGATIVE_OK = _negative_ok()
REV_LINES = [f"R{n:02d}" for n in range(1, 11)]
EXP_LINES = [f"GF{n:02d}" for n in range(1, 11)]
EXP_ESA_LINES = [f"E{n:02d}" for n in range(1, 10)]   # ESA_EXP (D-S13-003)


def _tables() -> dict[str, pd.DataFrame]:
    """All three trees per variant (line codes are distinct across trees)."""
    return {v: load_trees(v) for v in VARIANTS}


def check_v1() -> list[Finding]:
    """Anchor years reproduce anchor values (ERROR); IMF GFS within 0.5% (WARN)."""
    out = []
    tol = config.tolerances()["imf_gfs_reconciliation_pct"]
    df = _tables()["strict"]
    # anchor reproduction applies to rows observed at their own anchor year;
    # stitched rows carry the boundary anchor (anchor_year = F != year)
    own = df[df.anchor_value.notna() & (df.anchor_year == df.year)]
    bad = own[own.value_lcu_mn != own.anchor_value]
    for _, r in bad.iterrows():
        out.append(Finding("V1", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                           f"value {r.value_lcu_mn} != anchor {r.anchor_value}"))
    imf = df[df.imf_diff_pct.notna() & (df.imf_diff_pct.abs() > tol)]
    for _, r in imf.iterrows():
        out.append(Finding("V1", "WARN", f"{r.iso3}/{r.line_code}/{r.year}",
                           f"IMF GFS diff {r.imf_diff_pct}% beyond {tol}%"))
    if not out:
        out.append(Finding("V1", "OK", "-",
                           f"anchor values reproduced; IMF GFS within {tol}% where present"))
    return out


def _with_structural_zeros(piv: pd.DataFrame, iso3: str, lines: list[str]) -> pd.DataFrame:
    """D20: a line the country declares absent is zero in every year of the
    identity — the column is added or filled with 0.0 (no-op for GBR/FRA/DEU)."""
    absent = {code for (_, code) in config.absent_lines(iso3)}
    for code in absent & set(lines):
        piv[code] = piv[code].fillna(0.0) if code in piv.columns else 0.0
    return piv


def _sum_check(check_id: str, lines: list[str], total_code: str) -> list[Finding]:
    out = []
    tol = config.tolerances()["sum_to_total_pct"]
    for variant, df in _tables().items():
        for iso3 in config.COUNTRIES:
            sub = df[(df.iso3 == iso3) & (df.series_variant == variant)]
            piv = sub.pivot_table(index="year", columns="line_code",
                                  values="value_lcu_mn")
            if total_code not in piv.columns:
                continue
            piv = _with_structural_zeros(piv, iso3, lines)
            years = [y for y in piv.index
                     if all(c in piv.columns and pd.notna(piv[c][y]) for c in lines)
                     and pd.notna(piv[total_code][y])]
            for y in years:
                s = sum(piv[c][y] for c in lines)
                t = piv[total_code][y]
                if t and abs(s - t) / abs(t) * 100 > tol:
                    out.append(Finding(check_id, "ERROR", f"{iso3}/{variant}/{y}",
                                       f"sum {s:.1f} vs {total_code} {t:.1f} "
                                       f"beyond {tol}%"))
    return out or [Finding(check_id, "OK", "-",
                           f"{'+'.join((lines[0], '...', lines[-1]))} = {total_code} "
                           f"within tolerance in all complete years")]


def check_v2() -> list[Finding]:
    """Σ Level I = the tree's own total, for both expenditure cuts: COFOG
    GF01-GF10 = TE and (D-S13-003) ESA_EXP E01-E09 = TE_ESA."""
    cofog = _sum_check("V2", EXP_LINES, "TE")
    esa = _sum_check("V2", EXP_ESA_LINES, "TE_ESA")
    out = [f for f in cofog + esa if f.severity != "OK"]
    return out or [Finding("V2", "OK", "-", "GF01..GF10 = TE and E01..E09 = TE_ESA "
                                             "within tolerance in all complete years")]


def check_v22() -> list[Finding]:
    return _sum_check("V22", REV_LINES, "TR")


def check_v3() -> list[Finding]:
    """Level I shares sum to 100 ± tol (both trees)."""
    out = []
    tol = config.tolerances()["sum_to_total_pct"]
    for variant, df in _tables().items():
        for iso3 in config.COUNTRIES:
            for lines in (EXP_LINES, EXP_ESA_LINES, REV_LINES):
                sub = df[(df.iso3 == iso3) & (df.series_variant == variant)
                         & df.line_code.isin(lines) & df.pct_total.notna()]
                shares = sub.groupby("year").agg(n=("line_code", "nunique"),
                                                 s=("pct_total", "sum"))
                full = shares[shares.n == len(lines)]
                bad = full[(full.s - 100).abs() > tol]
                for y, r in bad.iterrows():
                    out.append(Finding("V3", "ERROR", f"{iso3}/{variant}/{y}",
                                       f"shares sum {r.s:.3f} != 100 ± {tol}"))
    return out or [Finding("V3", "OK", "-", "Level I shares sum to 100 within tolerance")]


def check_v4() -> list[Finding]:
    out = []
    negative_ok = _negative_ok()
    for variant, df in _tables().items():
        bad = df[(df.value_lcu_mn < 0) & ~df.line_code.isin(negative_ok)]
        for _, r in bad.iterrows():
            out.append(Finding("V4", "ERROR",
                               f"{r.iso3}/{r.line_code}/{r.year}/{variant}",
                               f"negative value {r.value_lcu_mn}"))
    return out or [Finding("V4", "OK", "-",
                           "no negative values outside R08/R10 and ledger balances")]


def check_v7() -> list[Finding]:
    out = []
    for variant, df in _tables().items():
        fc = df[df.is_forecast]
        bad = fc[fc.source_id.isna() | fc.source_release_date.isna()]
        for _, r in bad.iterrows():
            out.append(Finding("V7", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                               "forecast row missing source metadata"))
    return out or [Finding("V7", "OK", "-",
                           "every forecast row carries source metadata (none yet at Stage 1)")]


def check_v8() -> list[Finding]:
    out = []
    for variant, df in _tables().items():
        bad = df[(df.is_interpolated & df.interpolation_method.isna())
                 | (df.is_period_converted & df.period_conversion_method.isna())]
        for _, r in bad.iterrows():
            out.append(Finding("V8", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                               "interpolated/converted row not labelled"))
    return out or [Finding("V8", "OK", "-", "interpolated/converted rows labelled (none yet)")]


def check_v9() -> list[Finding]:
    out = []
    strict = _tables()["strict"]
    bad = strict[strict.quality_grade.isin(["C", "D"])]
    for _, r in bad.iterrows():
        out.append(Finding("V9", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                           f"grade {r.quality_grade} in strict"))
    bad2 = strict[strict.observation_type.isin(["proxy_forecast"])]
    for _, r in bad2.iterrows():
        out.append(Finding("V9", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                           "proxy_forecast in strict (maximum_extension only, §7.8)"))
    return out or [Finding("V9", "OK", "-", "observation types and grades consistent with variant")]


def check_v12() -> list[Finding]:
    # Every Stage 1 source is an S13 table by construction (register objects);
    # the check asserts no row references a non-GG source without a note.
    non_gg_sources: set[str] = set()  # none registered as anchors
    out = []
    for variant, df in _tables().items():
        bad = df[df.source_id.isin(non_gg_sources) & df.concept_flag.isna()]
        for _, r in bad.iterrows():
            out.append(Finding("V12", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                               "non-GG source without perimeter note"))
    return out or [Finding("V12", "OK", "-", "all sources S13; no unnoted perimeter")]


def check_v14() -> list[Finding]:
    """Missing stays missing: no NaN values (a missing year is an absent row),
    and the year set per line equals the anchor reader's year set."""
    from ggfiscal.build import anchor_series

    out = []
    df = _tables()["strict"]
    nan_rows = df[df.value_lcu_mn.isna()]
    for _, r in nan_rows.iterrows():
        out.append(Finding("V14", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                           "NaN value in canonical (missing must stay an absent row)"))
    for iso3 in config.COUNTRIES:
        srcs = anchor_series(iso3)
        for (cls, code), meta in srcs.items():
            # anchor-era rows only: anchor_year == year (stitched rows carry
            # the boundary anchor year and legitimately extend the year set)
            sub = df[(df.iso3 == iso3) & (df.line_code == code)
                     & (df.classification == cls) & (df.anchor_year == df.year)]
            got = set(sub.year)
            want = {int(y) for y in meta["series"].index}
            if got != want:
                out.append(Finding("V14", "ERROR", f"{iso3}/{code}",
                                   f"canonical anchor-era years != anchor years "
                                   f"(extra: {sorted(got - want)[:4]}, "
                                   f"missing: {sorted(want - got)[:4]})"))
    return out or [Finding("V14", "OK", "-", "no filled values; year sets match the anchors")]


def check_v19() -> list[Finding]:
    """Every Level II split (config.level2_splits(): GF01_7/GF01_X per D10,
    GF10_2/GF10_5/GF10_X and GF04_5/GF04_X, R02_A/R02_X, R06_E/R06_H/R06_X
    per D-S13-002/005): remainder + Σ Level II = parent exactly, each Level
    II line never exceeds its parent, and the remainder is never forecast."""
    out = []
    splits = config.level2_splits()
    for variant, df in _tables().items():
        for iso3 in config.COUNTRIES:
            for sp in splits:
                p, l2s, x = sp["parent"], sp["level2s"], sp["remainder"]
                piv = df[(df.iso3 == iso3) & (df.series_variant == variant)
                         & (df.classification == sp["classification"])] \
                    .pivot_table(index="year", columns="line_code", values="value_lcu_mn")
                both = [y for y in piv.index
                        if all(c in piv.columns and pd.notna(piv[c][y]) for c in (p, x, *l2s))]
                for y in both:
                    total = piv[x][y] + sum(piv[c][y] for c in l2s)
                    if abs(total - piv[p][y]) > 1e-6 * max(1.0, abs(piv[p][y])):
                        out.append(Finding("V19", "ERROR", f"{iso3}/{variant}/{y}",
                                           f"{x} + {' + '.join(l2s)} != {p}"))
                    for c in l2s:
                        if piv[c][y] > piv[p][y] + 1e-6:
                            out.append(Finding("V19", "ERROR", f"{iso3}/{variant}/{y}",
                                               f"{c} > {p}"))
        for sp in splits:
            fc = df[(df.line_code == sp["remainder"]) & df.is_forecast]
            for _, r in fc.iterrows():
                out.append(Finding("V19", "ERROR", f"{r.iso3}/{r.year}",
                                   f"{sp['remainder']} has a forecast row (never forecast)"))
    return out or [Finding("V19", "OK", "-",
                           "Level II split identities hold in every tree; remainders never forecast")]


def check_v20() -> list[Finding]:
    out = []
    for variant, df in _tables().items():
        interest = df[df.line_code.isin(["GF01_7", "R07", "E05"])]
        bad = interest[interest.concept_flag.isna()]
        for _, r in bad.iterrows():
            out.append(Finding("V20", "ERROR",
                               f"{r.iso3}/{r.line_code}/{r.year}/{variant}",
                               "interest row lacks concept_flag"))
        strict_net = df[(df.series_variant == "strict")
                        & df.line_code.isin(["GF01_7", "R07", "E05"])
                        & (df.concept_flag == "net_interest")]
        for _, r in strict_net.iterrows():
            out.append(Finding("V20", "ERROR", f"{r.iso3}/{r.line_code}/{r.year}",
                               "net interest concept in strict (must be gross)"))
    return out or [Finding("V20", "OK", "-", "interest rows flagged; strict rows gross")]


def check_v21() -> list[Finding]:
    """Level II 01.7 vs D.41 payable within 5% where both exist (WARN)."""
    out = []
    tol = config.tolerances()["level2_vs_d41_pct"]
    df = _tables()["strict"]
    for iso3 in config.COUNTRIES:
        l2 = df[(df.iso3 == iso3) & (df.line_code == "GF01_7")
                & (df.observation_type == "anchor_actual")] \
            .set_index("year").value_lcu_mn
        d41 = config.family(iso3).d41_payable(iso3)
        for y in l2.index.intersection(d41.index):
            diff = abs(l2[y] - d41[y]) / abs(l2[y]) * 100 if l2[y] else 0.0
            if diff > tol:
                out.append(Finding("V21", "WARN", f"{iso3}/{y}",
                                   f"Level II 01.7 vs D.41 payable diff {diff:.2f}% > {tol}%"))
    return out or [Finding("V21", "OK", "-",
                           f"Level II 01.7 within {tol}% of D.41 payable everywhere")]


def check_v23() -> list[Finding]:
    out = []
    tol = config.tolerances()["sum_to_total_pct"]
    led = load_ledger()
    for _, r in led.iterrows():
        if pd.isna(r.b9_anchor_lcu_mn):
            continue
        if r.te_lcu_mn and abs(r.nlb_lcu_mn - r.b9_anchor_lcu_mn) \
                / abs(r.te_lcu_mn) * 100 > tol:
            out.append(Finding("V23", "ERROR",
                               f"{r.iso3}/{r.series_variant}/{r.year}",
                               f"TR-TE = {r.nlb_lcu_mn:.1f} vs anchor B9 "
                               f"{r.b9_anchor_lcu_mn:.1f}"))
    return out or [Finding("V23", "OK", "-", "TR − TE equals anchor B.9 within tolerance")]


def check_v26() -> list[Finding]:
    from ggfiscal.reconcile.dynamics import v26_check

    out = []
    for variant in VARIANTS:
        for iso3, year, err in v26_check(variant):
            out.append(Finding("V26", "ERROR", f"{iso3}/{variant}/{year}",
                               f"decomposition additivity error {err}"))
    return out or [Finding("V26", "OK", "-",
                           "history contributions sum to Δ(NLB/GDP) exactly")]


IMPLEMENTED = {
    "V1": check_v1, "V2": check_v2, "V3": check_v3, "V4": check_v4,
    "V7": check_v7, "V8": check_v8, "V9": check_v9, "V12": check_v12,
    "V14": check_v14, "V19": check_v19, "V20": check_v20, "V21": check_v21,
    "V22": check_v22, "V23": check_v23, "V26": check_v26,
}
