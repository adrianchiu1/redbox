"""Stage R0 validation additions (REPLICATION_KICKOFF.md §10): V41 on
structural zeros (D20) and V42 on FY-labelled trees and the FY/CY bridge
(D19). Both run from Stage 1 and report OK with an explicit "nothing
declared" message for the countries that declare no absence and no FY tree
(GBR, FRA, DEU), so the plumbing is exercised on every run."""

from __future__ import annotations

import re

import pandas as pd

from ggfiscal import config
from ggfiscal.validate.runner import Finding

FY_LABEL = re.compile(r"^FY\d{4}$")


def check_v41() -> list[Finding]:
    """V41 (ERROR): every `lines_absent` line has structural_zero rows in
    every anchor year of its tree and no rows elsewhere, each zero, grade A,
    with the declared reason; every structural_zero row is in lines_absent;
    the V2/V22 identities run over them (they are checked by V2/V22
    themselves, with absent lines treated as zero)."""
    from ggfiscal.validate.stage1 import _tables

    out = []
    n_declared = 0
    for variant, df in _tables().items():
        for iso3 in config.COUNTRIES:
            absent = config.absent_lines(iso3)
            n_declared += len(absent) if variant == "strict" else 0
            sub = df[(df.iso3 == iso3) & (df.series_variant == variant)]
            zeros = sub[sub.observation_type == "structural_zero"]
            for (cls, code), g in zeros.groupby(["classification", "line_code"]):
                if (cls, code) not in absent:
                    out.append(Finding("V41", "ERROR", f"{iso3}/{code}/{variant}",
                                       "structural_zero rows for a line not declared in lines_absent"))
            for (cls, code), reason in absent.items():
                rows = sub[(sub.classification == cls) & (sub.line_code == code)]
                total = sub[(sub.classification == cls)
                            & (sub.line_code == config.total_code(cls))
                            & (sub.anchor_year == sub.year)]
                want_years = set(total.year)
                got = rows[rows.observation_type == "structural_zero"]
                other = rows[rows.observation_type != "structural_zero"]
                scope = f"{iso3}/{code}/{variant}"
                if not other.empty:
                    out.append(Finding("V41", "ERROR", scope,
                                       f"{len(other)} non-structural_zero row(s) on a declared absence "
                                       f"(a structural zero is never extended or forecast)"))
                if set(got.year) != want_years:
                    out.append(Finding("V41", "ERROR", scope,
                                       f"structural_zero years != anchor years of the tree "
                                       f"(missing {sorted(want_years - set(got.year))[:4]}, "
                                       f"extra {sorted(set(got.year) - want_years)[:4]})"))
                if (got.value_lcu_mn != 0).any() or (got.quality_grade != "A").any():
                    out.append(Finding("V41", "ERROR", scope,
                                       "structural_zero rows must be 0.0 at grade A"))
                if not got.notes.astype(str).str.contains(re.escape(reason)).all():
                    out.append(Finding("V41", "ERROR", scope,
                                       "structural_zero rows do not carry the declared reason"))
    if out:
        return out
    if n_declared == 0:
        return [Finding("V41", "OK", "-",
                        "no lines_absent declared for any country; no structural_zero rows (D20)")]
    return [Finding("V41", "OK", "-",
                    f"{n_declared} declared structural zero(s): zero rows in every anchor "
                    "year, nowhere else, reasons carried (D20)")]


def check_v42() -> list[Finding]:
    """V42 (ERROR): a FY-labelled tree (countries.yaml period_basis.trees)
    carries source_period_basis = FY and a FY#### native_period on every
    row, and no CY-basis source is chained onto it (§7.14: every growth
    source's register period_basis is FY); a CY tree carries CY labels; the
    fy_cy_bridge is additive per (country, year)."""
    from ggfiscal.validate.stage1 import _tables

    out = []
    n_fy = 0
    for variant, df in _tables().items():
        for iso3 in config.COUNTRIES:
            for cls in config.TREES:
                basis = config.tree_period_basis(iso3, cls)
                sub = df[(df.iso3 == iso3) & (df.series_variant == variant)
                         & (df.classification == cls)]
                if sub.empty:
                    continue
                scope = f"{iso3}/{cls}/{variant}"
                if basis == "FY":
                    n_fy += 1 if variant == "strict" else 0
                    if (sub.source_period_basis != "FY").any():
                        out.append(Finding("V42", "ERROR", scope,
                                           "FY-labelled tree carries rows not stamped FY"))
                    if not sub.native_period.astype(str).str.match(FY_LABEL).all():
                        out.append(Finding("V42", "ERROR", scope,
                                           "FY-labelled tree carries rows without a FY#### label"))
                    chained = sub[sub.growth_source_id.notna()]
                    for sid in sorted(set(chained.growth_source_id)):
                        if config.source_period_basis(sid) != "FY":
                            out.append(Finding("V42", "ERROR", f"{scope}/{sid}",
                                               "CY-basis source chained onto a FY-labelled tree (§7.14)"))
                else:
                    bad = sub[(sub.source_period_basis != "CY")
                              & ~sub.is_period_converted.astype(bool)]
                    # an unconverted FY-basis source may only appear on a FY tree
                    if not bad.empty:
                        out.append(Finding("V42", "ERROR", scope,
                                           f"{len(bad)} row(s) on a CY tree stamped FY without conversion"))
    bridge_path = config.repo_root() / "data" / "canonical" / "fy_cy_bridge.csv"
    if not bridge_path.exists():
        out.append(Finding("V42", "ERROR", "fy_cy_bridge", "fy_cy_bridge.csv not written by the build"))
    else:
        br = pd.read_csv(bridge_path)
        for _, r in br.iterrows():
            gap = r.te_fy_lcu_mn - r.te_cy_lcu_mn
            timing = 0.0 if pd.isna(r.timing_component_lcu_mn) else r.timing_component_lcu_mn
            if abs(r.gap_lcu_mn - gap) > 1e-6 or abs(r.residual_lcu_mn - (gap - timing)) > 1e-6:
                out.append(Finding("V42", "ERROR", f"{r.iso3}/{int(r.year)}",
                                   "fy_cy_bridge not additive (gap = TE_FY - TE_CY = timing + residual)"))
        n_bridge = len(br)
    if out:
        return out
    if n_fy == 0:
        return [Finding("V42", "OK", "-",
                        "no FY-labelled tree configured; every row CY-labelled; "
                        "fy_cy_bridge.csv empty (D19)")]
    return [Finding("V42", "OK", "-",
                    f"{n_fy} FY-labelled tree(s) stamped and labelled FY, no CY source chained; "
                    f"fy_cy_bridge additive in {n_bridge} rows (D19)")]


IMPLEMENTED = {"V41": check_v41}   # V42 registered with the D19 plumbing (step 4)
