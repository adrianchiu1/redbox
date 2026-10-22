"""Charts for the France brief's retirement-age section (D-S20-001): the
exposure the age moves, the cost per cohort-year each method implies, the
line-by-line matrix and its timing, the growth channel and the strict
file's forward paths with the shock on them. `render_all(out_dir)` writes
the PNGs and the CSVs (`pension_age_matrix.csv`, `pension_age_exposure.csv`,
`pension_age_units.csv`, `pension_age_published.csv`,
`pension_age_assumptions.csv`) next to them, and returns {key: path}.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ggfiscal.debt import pension_age as pa
from ggfiscal.debt import simulate as sim
from ggfiscal.report.briefing_fra_scenarios import (AXIS, BLUE, BROWN, FR_BLUE, GOLD, GREEN, HIST, INK, MUTED, ORANGE,
                                                    PURPLE, RED, SHADE, SURFACE, TEAL, DOTTED, DPI, _save, _source)

LINE_COLOUR = {"GF10_2": FR_BLUE, "GF10_X": TEAL, "GF10_5": GREEN, "R06": ORANGE, "R03": GOLD, "R01": PURPLE, "R02": BROWN, "R04": RED}
LINE_SHORT = {"GF10_2": "GF10_2 pensions", "GF10_X": "GF10_X other social protection", "GF10_5": "GF10_5 unemployment",
              "R06": "R06 social contributions", "R03": "R03 household income taxes", "R01": "R01 VAT",
              "R02": "R02 other production taxes", "R04": "R04 corporate tax"}
METHOD_COLOUR = {"m1_tresor": BROWN, "m1_cour": GOLD, "m1_cor": PURPLE, "m2_bottom_up": FR_BLUE, "m3_published": MUTED, "m4_growth": TEAL}
POLICY_STYLE = {"p62": {"color": FR_BLUE, "ls": "-"}, "p60": {"color": RED, "ls": "-"}, "p64": {"color": GREEN, "ls": "-"},
                "suspension": {"color": MUTED, "ls": DOTTED}}


def chart_exposure(ex: pd.DataFrame, out: Path):
    """Left: the cohorts in play. Right: extra retirees at year end under each policy."""
    pop = pa.population()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.4), gridspec_kw={"width_ratios": [1, 1.5]})
    yrs = list(range(2024, 2041))
    a1.bar(yrs, [pop.loc[y, 60] / 1000 for y in yrs], color=[SHADE if y < 2028 else FR_BLUE for y in yrs], width=0.8)
    a1.set_title("People turning 60 each year (thousands)")
    a1.set_ylim(700, 950); a1.grid(axis="y")
    a1.text(2024.2, 935, "cohorts 1964–1980; Eurostat observed to 2025,\nEUROPOP2023 baseline after", fontsize=7.2, color=MUTED, va="top")
    for pol in ("p62", "p60", "p64", "suspension"):
        s = ex[(ex.policy == pol) & (ex.variant == "central")].groupby("year").people_end_year.sum() / 1000
        s = s.reindex(range(2026, 2041), fill_value=0)
        a2.plot(s.index, s.values, lw=2.2 if pol != "suspension" else 1.6, label=pa.POLICIES[pol], **POLICY_STYLE[pol])
    a2.axhline(0, color=AXIS, lw=1)
    a2.set_title("Extra people in retirement at year end (thousands, central bound shares)")
    a2.grid(axis="y"); a2.legend(fontsize=7.2, loc="center right")
    a2.set_xlim(2025.6, 2040.4)
    _source(fig, "Source: ggfiscal.debt.pension_age.exposure on data/manual/FRA_population_by_age.csv; ages by cohort from COR 2026 Table 1.4 (LFSS 2026 path). "
                 "Policies start 1 Jan 2028 (the suspension 1 Sep 2026). Negative = fewer retirees than under the law as it stands.", y=-0.04)
    _save(fig, out); return out


def chart_units(pub: pd.DataFrame, units: pd.DataFrame, out: Path):
    """EUR bn per cohort-year: the published figures converted, and the methods."""
    fig, ax = plt.subplots(figsize=(8.0, 3.6))
    rows = []
    for r in pub.itertuples():
        rows.append((f"{r.source}: €{r.eur_bn:g}bn ({r.year}), {r.measure}", r.eur_bn_per_cohort_year, r.scope))
    for m, r in units.iterrows():
        rows.append((m, r.total_cost, "gg" if ("Trésor" in m or "bottom-up" in m or "GDP" in m or "published" in m) else "pension"))
    rows.sort(key=lambda t: t[1])
    y = np.arange(len(rows))
    for i, (lab, v, scope) in enumerate(rows):
        ax.plot([0, v], [i, i], color=AXIS, lw=1)
        ax.plot([v], [i], marker="o", ms=7, color=FR_BLUE if scope == "gg" else ORANGE)
        ax.text(v + 0.3, i, f"{v:.1f}", va="center", fontsize=8, color=INK)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=7.6)
    ax.set_xlabel("EUR bn a year per cohort-year of lower age (2030 prices and GDP)")
    ax.set_title("France · what one cohort-year of retirement age costs: every source on one scale")
    ax.plot([], [], marker="o", color=ORANGE, ls="", label="pension system only"); ax.plot([], [], marker="o", color=FR_BLUE, ls="", label="general government")
    ax.legend(loc="lower right", fontsize=7.5); ax.grid(axis="x")
    _source(fig, "Source: ggfiscal.debt.pension_age.published_units / units_table. Each published € figure is divided by the cohort-years of exposure of the measure it costs, "
                 "in the year it quotes, computed here; one cohort-year = a whole birth cohort (850k) retiring one year earlier.", y=-0.1)
    _save(fig, out); return out


def chart_matrix(mat: pd.DataFrame, out: Path):
    """Central bottom-up matrix by line for '62 for all' and '60 for early
    starters', with the band of totals across methods."""
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8), sharey=True)
    yrs = list(range(2028, 2041))
    for ax, pol in zip(axes, ("p62", "p60")):
        m = mat[(mat.policy == pol) & (mat.variant == "central")]
        bu = m[m.method == "m2_bottom_up"].pivot_table(index="year", columns="line_code", values="balance_bn").reindex(yrs).fillna(0)
        pos, neg = np.zeros(len(yrs)), np.zeros(len(yrs))
        for line in pa.LINES:
            v = bu[line].values if line in bu else np.zeros(len(yrs))
            base = np.where(v >= 0, pos, neg)
            ax.bar(yrs, v, bottom=base, color=LINE_COLOUR[line], width=0.75, label=LINE_SHORT[line])
            pos = pos + np.clip(v, 0, None); neg = neg + np.clip(v, None, 0)
        tot = m.groupby(["method", "year"]).balance_bn.sum().unstack("method").reindex(yrs)
        ax.plot(yrs, tot["m2_bottom_up"], color=INK, lw=1.6, marker="o", ms=3, label="total, bottom-up")
        ax.fill_between(yrs, tot.min(axis=1), tot.max(axis=1), color=INK, alpha=0.08, lw=0, label="range of totals across the six methods")
        ax.axhline(0, color=AXIS, lw=1); ax.grid(axis="y")
        ax.set_title(f"{pa.POLICIES[pol]}", fontsize=9.5)
        ax.set_xlim(2027.4, 2040.6)
    axes[0].set_ylabel("effect on the primary balance, EUR bn (negative = worse)")
    axes[0].legend(ncol=5, loc="upper center", bbox_to_anchor=(1.05, -0.1), fontsize=7)
    fig.suptitle("France · the retirement age line by line: bottom-up cohort arithmetic, central assumptions", x=0.01, y=1.03, ha="left", fontsize=10.5, fontweight="bold")
    _source(fig, "Source: ggfiscal.debt.pension_age.matrix. Bars: method 2 by Redbox line (GF10_X and GF10_5 are savings: fewer invalidity, sickness and unemployment benefits). "
                 "Band: lowest and highest total among methods 1a–4 in each year.", y=-0.2)
    _save(fig, out); return out


def chart_timing(mat: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(8.0, 3.4))
    yrs = list(range(2026, 2041))
    for pol, lw in (("p62", 2.2), ("p64", 1.8)):
        m = mat[(mat.policy == pol) & (mat.variant == "central")]
        tot = m.groupby(["method", "year"]).balance_bn.sum().unstack("method").reindex(yrs).fillna(0)
        for meth in pa.METHODS:
            ax.plot(yrs, tot[meth], color=METHOD_COLOUR[meth], lw=lw if pol == "p62" else 1.2, ls="-" if pol == "p62" else DOTTED,
                    label=pa.METHODS[meth] if pol == "p62" else None)
    ax.axhline(0, color=AXIS, lw=1); ax.grid(axis="y")
    ax.axvspan(2027.5, 2031.5, color=SHADE, lw=0, zorder=0)
    ax.text(2027.6, ax.get_ylim()[0] * 0.95, "the scenarios' 2028–2031 consolidation window", fontsize=7.2, color=MUTED, va="bottom")
    ax.set_ylabel("primary balance, EUR bn"); ax.set_xlim(2026.6, 2040.4)
    ax.set_title("France · when the age bites: '62 for all' (solid) and '64 resumed' (dotted), by method")
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    _source(fig, "Source: ggfiscal.debt.pension_age.matrix, central variant. A cut is front-loaded (everyone past the new age retires at once); the second-round revenue of method 1a "
                 "and the GDP channel of method 4 build over ten to fifteen years, so those two keep worsening after the exposure has levelled off in 2033.", y=-0.3)
    _save(fig, out); return out


def chart_gdp(out: Path):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.3))
    for v, c, lab in (("low", GREEN, "low: OFCE e-mod (−0.15% per cohort-year)"), ("central", FR_BLUE, "central: Mésange (−0.35%)"), ("high", RED, "high: Rexecode (−0.55%)")):
        for pol, ls in (("p62", "-"), ("p60", DOTTED)):
            g = pa.gdp_channel(pol, v).set_index("year")
            a1.plot(g.index, g.gdp_pct, color=c, ls=ls, lw=2 if pol == "p62" else 1.6, label=f"{lab}, {pa.POLICIES[pol]}" if pol == "p62" else None)
            if v == "central":
                h = pd.Series(pa.growth_haircut(pol, v))
                a2.bar(h.index + (0.2 if pol == "p60" else -0.2), 100 * h.values, width=0.4, color=c if pol == "p62" else RED, label=pa.POLICIES[pol])
    a1.axhline(0, color=AXIS, lw=1); a1.grid(axis="y"); a1.set_ylabel("% of GDP, level"); a1.set_xlim(2026.6, 2040.4)
    a1.set_title("GDP level effect (solid 62 for all, dotted with 60)", fontsize=9.5); a1.legend(fontsize=6.8, loc="lower left")
    a2.axhline(0, color=AXIS, lw=1); a2.grid(axis="y"); a2.set_ylabel("basis points of real growth a year"); a2.set_xlim(2026.6, 2040.4)
    a2.set_title("The growth haircut the engine would carry (central)", fontsize=9.5); a2.legend(fontsize=7)
    fig.suptitle("France · method 4, the growth channel", x=0.01, y=1.04, ha="left", fontsize=10.5, fontweight="bold")
    _source(fig, "Source: ggfiscal.debt.pension_age.gdp_channel / growth_haircut: G1 per cohort-year of exposure, linear to full effect after ten years (G2). "
                 "Revenue moves at unit elasticity (G3): R01, R02, R03, R04, R06.", y=-0.08)
    _save(fig, out); return out


def chart_lines(mat: pd.DataFrame, out: Path):
    """Method 5: the strict file's GF10_2 forward path with the central shock on
    it (left) and the primary-balance effect in % of GDP (right)."""
    c = pd.read_csv(sim.DELIV / "expenditure_cofog.csv", low_memory=False).query("iso3 == 'FRA' and variant == 'strict' and line_code == 'GF10_2'").set_index("year").pct_gdp
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.3))
    a1.axvspan(2025.5, 2036.5, color=SHADE, lw=0, zorder=0)
    h = c.loc[2010:2024]; f = c.loc[2024:2036]
    a1.plot(h.index, h.values, color=HIST, lw=2.2, label="outturn (Eurostat)")
    a1.plot(f.index, f.values, color=BROWN, ls="-.", lw=1.3, label="strict file forward path (EC Ageing 2024 growth)")
    for pol in ("p62", "p60", "p64"):
        m = mat[(mat.policy == pol) & (mat.variant == "central") & (mat.method == "m2_bottom_up") & (mat.line_code == "GF10_2")].set_index("year").pct_gdp
        s_ = (f.loc[2027:2036] + m.reindex(f.loc[2027:2036].index).fillna(0))
        a1.plot(s_.index, s_.values, lw=2.0, label=pa.POLICIES[pol], **POLICY_STYLE[pol])
    a1.set_ylabel("% of GDP"); a1.grid(axis="y"); a1.set_xlim(2009.7, 2036.5); a1.set_title("GF10_2 old age (pensions), strict file with the shock", fontsize=9.5)
    a1.legend(fontsize=6.8, loc="upper left")
    a2.axvspan(2027.5, 2036.5, color=SHADE, lw=0, zorder=0)
    for pol in ("p62", "p60", "p64"):
        m = mat[(mat.policy == pol) & (mat.variant == "central")]
        tot = m.groupby(["method", "year"]).balance_bn.sum().unstack("method").loc[2027:2036]
        g = pd.Series({y: pa.gdp(y) for y in tot.index})
        bu = 100 * tot["m2_bottom_up"] / g
        a2.plot(bu.index, bu.values, lw=2.0, label=pa.POLICIES[pol], **POLICY_STYLE[pol])
        a2.fill_between(bu.index, 100 * tot.min(axis=1) / g, 100 * tot.max(axis=1) / g, color=POLICY_STYLE[pol]["color"], alpha=0.12, lw=0)
    a2.axhline(0, color=AXIS, lw=1); a2.set_ylabel("% of GDP"); a2.grid(axis="y"); a2.set_xlim(2026.7, 2036.5)
    a2.set_title("Primary-balance effect, bottom-up (line) and the range of methods (band)", fontsize=9.5)
    a2.legend(fontsize=6.8, loc="lower left")
    fig.suptitle("France · method 5: the shock on the strict file's forward path and on the primary balance", x=0.01, y=1.04, ha="left", fontsize=10.5, fontweight="bold")
    _source(fig, "Source: deliverables/expenditure_cofog.csv (strict, FRA; a 64-year path with the 2023 law in force and no suspension); ggfiscal.debt.pension_age.matrix in % of the engine's GDP. "
                 "The strict file carries no revenue forward path beyond 2027, so R06 cannot be drawn the same way.", y=-0.08)
    _save(fig, out); return out


def render_all(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    mat = pa.matrix_all()
    mat.to_csv(out_dir / "pension_age_matrix.csv", index=False)
    ex = pd.concat([pa.exposure(p, v) for p in ("p62", "p60", "p64", "suspension") for v in ("low", "central", "high")], ignore_index=True)
    ex.to_csv(out_dir / "pension_age_exposure.csv", index=False)
    units = pa.units_table()
    units.to_csv(out_dir / "pension_age_units.csv")
    pub = pa.published_units()
    pub.to_csv(out_dir / "pension_age_published.csv", index=False)
    pa.register().to_csv(out_dir / "pension_age_assumptions.csv", index=False)
    figs = {}
    figs["pa_exposure"] = chart_exposure(ex, out_dir / "pa_exposure.png")
    figs["pa_units"] = chart_units(pub, units, out_dir / "pa_units.png")
    figs["pa_matrix"] = chart_matrix(mat, out_dir / "pa_matrix.png")
    figs["pa_timing"] = chart_timing(mat, out_dir / "pa_timing.png")
    figs["pa_gdp"] = chart_gdp(out_dir / "pa_gdp.png")
    figs["pa_lines"] = chart_lines(mat, out_dir / "pa_lines.png")
    return figs


if __name__ == "__main__":       # pragma: no cover
    figs = render_all(sim.ROOT / "reports" / "briefing_FRA_AFT_2026-09" / "figures")
    for k, p in figs.items():
        print(k, p, f"{p.stat().st_size / 1024:.0f} KB")
