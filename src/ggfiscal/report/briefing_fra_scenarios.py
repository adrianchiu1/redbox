"""Scenario charts for the AFT briefing (D-S12-001): the register-based
interest simulation of `ggfiscal.debt.simulate` drawn in the debtbook's
palette. `render_all(out_dir)` writes the PNGs, `scenarios_FRA.csv` (every
scenario-year the engine produced), `scenario_decomposition.csv` and
`duration_by_bucket.csv` next to them, and returns {key: path}.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ggfiscal.debt import simulate as sim

BLUE, ORANGE, GREEN, PURPLE, RED, TEAL, BROWN, GOLD = (
    "#2a78d6", "#eb6834", "#1baf7a", "#8456ce", "#d64550", "#2ba8a0", "#a8763e", "#d1a62b")
INK, MUTED, AXIS = "#0b0b0b", "#898781", "#c3c2b7"
SURFACE, SHADE = "#fcfcfb", "#eceae4"

SCEN_STYLE = {                       # one colour per scenario, never reused
    "current": (INK, "-"), "philippe_majority": (GREEN, "-"), "philippe_hung": (TEAL, "--"),
    "lepen_hung": (GOLD, "--"), "lepen_majority": (RED, "-"), "lepen_rupture": (RED, ":"),
}

plt.rcParams.update({
    "figure.figsize": (7.2, 3.3), "figure.dpi": 120,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK, "axes.titlecolor": INK,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 9, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "grid.color": AXIS, "grid.alpha": 0.45, "grid.linewidth": 0.6,
    "legend.frameon": False, "legend.fontsize": 8, "lines.linewidth": 1.8,
})

DELIV = sim.DELIV


def _source(fig, text, y=-0.02):
    fig.text(0.01, y, text, fontsize=7, color=MUTED, ha="left", va="top")


def _save(fig, path):
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def _history():
    strict = pd.read_csv(DELIV / "strict_FRA.csv").set_index("year")
    gf = strict["GF01_7 - Public debt transactions (interest)"]
    gdp = strict["GDP - Gross domestic product at current market prices"]
    led = pd.read_csv(DELIV / "balance_ledger.csv").query("iso3 == 'FRA' and variant == 'strict'").set_index("year")
    exp = pd.read_csv(DELIV / "expenditure_cofog.csv", low_memory=False).query(
        "iso3 == 'FRA' and variant == 'strict' and line_code == 'GF01_7'").set_index("year")
    return gf, gdp, led, exp


def chart_interest(res, out):
    gf, gdp, led, exp = _history()
    fig, ax = plt.subplots()
    ax.axvspan(2025.5, 2035.5, color=SHADE, lw=0, zorder=0)
    h = exp.loc[2010:2024, "pct_gdp"]
    ax.plot(h.index, h.values, color=BLUE, lw=2.2, label="outturn (Eurostat, GF01_7)")
    d = exp.loc[2025:2035, "pct_gdp"]
    ax.plot(d.index, d.values, color=MUTED, ls=":", lw=1.6, label="EC AMECO / DSM path in the strict file")
    for name, (c, ls) in SCEN_STYLE.items():
        s = res[res.scenario == name].set_index("year")
        s = pd.concat([pd.Series({2025: exp.loc[2025, "pct_gdp"]}), s.gg_interest_pct_gdp])
        ax.plot(s.index, s.values, color=c, ls=ls, lw=1.8 if name != "current" else 2.2, label=s.name or sim.SCENARIOS[[x.name for x in sim.SCENARIOS].index(name)].label)
    ax.set_ylabel("% of GDP"); ax.set_xlim(2010, 2035.5); ax.grid(axis="y")
    ax.set_title("France · general-government interest, outturn and six paths from the register")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    for name in ("current", "lepen_majority", "philippe_majority"):
        s = res[(res.scenario == name) & (res.year == 2035)].iloc[0]
        ax.annotate(f"{s.gg_interest_pct_gdp:.1f}%  €{s.gg_interest_bn:,.0f}bn", (2035, s.gg_interest_pct_gdp),
                    xytext=(4, 0), textcoords="offset points", fontsize=7.5, color=SCEN_STYLE[name][0], va="center")
    _source(fig, "Source: ggfiscal.debt.simulate on deliverables/debt_positions.csv at 2026-09-10; strict_FRA.csv. Interest on the accrual basis; wedge to GF01_7 held at 0.34% of GDP.", y=-0.2)
    _save(fig, out); return out


def chart_paths(res, out, col, ylabel, title, ref=None, hist=None):
    fig, ax = plt.subplots()
    ax.axvspan(2025.5, 2035.5, color=SHADE, lw=0, zorder=0)
    if hist is not None:
        ax.plot(hist.index, hist.values, color=BLUE, lw=2.2, label="outturn")
    for name, (c, ls) in SCEN_STYLE.items():
        s = res[res.scenario == name].set_index("year")[col]
        if hist is not None and 2025 in hist.index:
            s = pd.concat([pd.Series({2025: hist.loc[2025]}), s])
        lab = sim.SCENARIOS[[x.name for x in sim.SCENARIOS].index(name)].label
        ax.plot(s.index, s.values, color=c, ls=ls, lw=2.2 if name == "current" else 1.8, label=lab)
    if ref is not None:
        ax.axhline(ref, color=AXIS, ls="--", lw=1)
    ax.set_ylabel(ylabel); ax.grid(axis="y"); ax.set_title(title)
    ax.set_xlim((hist.index.min() if hist is not None else 2025) - 0.3, 2035.5)
    ax.legend(ncol=2, loc="upper left")
    _source(fig, "Source: ggfiscal.debt.simulate (declared scenarios, see the assumptions table); balance_ledger.csv for the outturn.")
    _save(fig, out); return out


def chart_spread(res, out):
    ref = pd.read_csv(DELIV / "debt_reference_series.csv", low_memory=False)
    p = ref[ref.series_id.isin(["FR_LT10", "DE_LT10"])].pivot_table(index="date", columns="series_id", values="value")
    p.index = pd.to_datetime(p.index)
    sp = ((p.FR_LT10 - p.DE_LT10) * 100).dropna()
    sp = sp[sp.index >= "2019-01-01"]
    fig, ax = plt.subplots()
    ax.axvspan(2026.7, 2035.5, color=SHADE, lw=0, zorder=0)
    x = sp.index.year + (sp.index.month - 0.5) / 12
    ax.plot(x, sp.values, color=BLUE, lw=1.4, label="OAT–Bund 10y, monthly (OECD long-term rates)")
    for name, (c, ls) in SCEN_STYLE.items():
        s = res[res.scenario == name].set_index("year").spread_bp
        lab = sim.SCENARIOS[[x.name for x in sim.SCENARIOS].index(name)].label
        ax.plot(s.index + 0.5, s.values, color=c, ls=ls, lw=2.2 if name == "current" else 1.8, label=lab, marker="o", ms=3)
    ax.set_ylabel("basis points"); ax.grid(axis="y"); ax.set_xlim(2019, 2035.9)
    ax.set_title("France · the OAT–Bund spread, history and the paths each scenario declares")
    ax.legend(ncol=2, loc="upper left")
    _source(fig, "Source: deliverables/debt_reference_series.csv (FR_LT10 − DE_LT10); scenario paths are declared inputs, with a +3 bp per pp debt-ratio feedback.")
    _save(fig, out); return out


def chart_decomposition(dec, out):
    d = dec[dec.year == 2030].set_index("scenario").drop(index="current", errors="ignore")
    order = ["philippe_majority", "philippe_hung", "lepen_hung", "lepen_majority", "lepen_rupture"]
    d = d.reindex([o for o in order if o in d.index])
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    x = range(len(d))
    ax.bar(x, d.spread_effect_bn, color=ORANGE, width=0.6, label="spread (price of new debt)")
    neg = d.spread_effect_bn < 0
    ax.bar(x, d.volume_effect_bn, bottom=d.spread_effect_bn.where(~neg, 0).where(d.volume_effect_bn >= 0, d.spread_effect_bn.clip(upper=0)), color=BLUE, width=0.6, label="primary balance & issuance strategy (volume)")
    ax.bar(x, d.interaction_bn, bottom=(d.spread_effect_bn.clip(lower=0) + d.volume_effect_bn.clip(lower=0)), color=MUTED, width=0.6, label="interaction (the loop)")
    top = d.gap_bn.max() + max(d.interaction_bn.clip(lower=0).max(), 0)
    lo = min(d.spread_effect_bn.clip(upper=0).sum(), 0) - 1
    ax.set_ylim(min(d.gap_bn.min(), 0) - 5, top * 1.35)
    for i, (_, r) in enumerate(d.iterrows()):
        y = r.gap_bn + 1.0 if r.gap_bn >= 0 else min(r.spread_effect_bn, 0) + min(r.volume_effect_bn, 0) - 1.0
        ax.text(i, y, f"{r.gap_bn:+.0f}", ha="center", va="bottom" if r.gap_bn >= 0 else "top", fontsize=8.5, color=INK, fontweight="bold")
    ax.axhline(0, color=AXIS, lw=1)
    ax.set_xticks(list(x)); ax.set_xticklabels([r.label.replace(", ", "\n") for _, r in d.iterrows()], fontsize=8)
    ax.set_ylabel("EUR bn, 2030, vs current path"); ax.grid(axis="y")
    ax.set_title("France · what the 2030 interest gap to the current path is made of")
    ax.legend(loc="upper left")
    _source(fig, "Source: ggfiscal.debt.simulate.decompose_gap — each lever re-run alone against the current path, feedback off.")
    _save(fig, out); return out


def chart_issuance(res, out):
    fig, ax = plt.subplots()
    ax.axvspan(2026.5, 2035.5, color=SHADE, lw=0, zorder=0)
    for name, (c, ls) in SCEN_STYLE.items():
        s = res[(res.scenario == name) & (res.year >= 2027)].set_index("year")
        lab = sim.SCENARIOS[[x.name for x in sim.SCENARIOS].index(name)].label
        ax.plot(s.index, s.mlt_gross_issuance_bn, color=c, ls=ls, lw=2.2 if name == "current" else 1.8, label=lab)
    ax.axhline(310, color=AXIS, ls="--", lw=1); ax.text(2027.1, 313, "2026 programme €310bn (net of buybacks)", fontsize=7.5, color=MUTED)
    ax.set_ylabel("EUR bn, gross medium/long-term"); ax.grid(axis="y"); ax.set_xlim(2026.6, 2035.4)
    ax.set_title("France · gross OAT issuance the register implies (redemptions + net financing)")
    ax.legend(ncol=2, loc="upper left")
    _source(fig, "Source: ggfiscal.debt.simulate. Register redemptions overstate the AFT's by the buybacks it publishes only in aggregate (1–4% of the fixed stock).")
    _save(fig, out); return out


def chart_coupon(res, out):
    fig, ax = plt.subplots()
    ax.axvspan(2025.5, 2035.5, color=SHADE, lw=0, zorder=0)
    pos = pd.read_csv(DELIV / "debt_positions.csv", low_memory=False).query("iso3 == 'FRA'")
    sec = pd.read_csv(DELIV / "debt_securities.csv", low_memory=False).query("iso3 == 'FRA'")
    ye = pos[pos.as_of.str.endswith("12-31")].merge(sec[["security_id", "instrument_class", "coupon_pct"]], on="security_id")
    fb = ye[ye.instrument_class == "fixed_bullet"]
    w = fb.groupby("as_of").apply(lambda g: (g.coupon_pct * g.nominal_lcu_mn).sum() / g.nominal_lcu_mn.sum(), include_groups=False)
    w.index = pd.to_datetime(w.index).year
    w = w.loc[2010:]
    ax.plot(w.index, w.values, color=BLUE, lw=2.2, label="average coupon, fixed-rate stock (register)")
    for name, (c, ls) in SCEN_STYLE.items():
        s = res[res.scenario == name].set_index("year")
        lab = sim.SCENARIOS[[x.name for x in sim.SCENARIOS].index(name)].label
        ax.plot([2025, *s.index], [w.loc[2025], *s.avg_coupon_fixed_pct], color=c, ls=ls, lw=2.2 if name == "current" else 1.6, label=lab)
        if name in ("current", "lepen_majority", "philippe_majority"):
            ax.plot(s.index, s.oat_10y_pct, color=c, ls=ls, lw=0.9, alpha=0.6)
    ax.text(2026.0, 5.35, "thin lines: the 10y OAT yield each scenario implies", fontsize=7.5, color=MUTED)
    ax.set_ylabel("%"); ax.grid(axis="y"); ax.set_xlim(2010, 2035.5); ax.set_ylim(1.2, 5.6)
    ax.set_title("France · the average coupon keeps rising whoever wins: the refinancing drag")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    _source(fig, "Source: deliverables/debt_positions.csv × debt_securities.csv; ggfiscal.debt.simulate for the paths.", y=-0.2)
    _save(fig, out); return out


def chart_duration(out, spread_bp=90.0):
    d = sim.duration_table(spread_bp)
    bins = [0, 1, 2, 3, 5, 7, 10, 15, 20, 30, 100]
    labels = ["0-1", "1-2", "2-3", "3-5", "5-7", "7-10", "10-15", "15-20", "20-30", "30+"]
    d["bucket"] = pd.cut(d.years_to_maturity, bins, labels=labels, right=True)
    g = d.groupby(["bucket", "class"], observed=True).agg(mv=("market_value_bn", "sum"), dv=("value_per_bp_mn", "sum")).reset_index()
    p = g.pivot_table(index="bucket", columns="class", values="dv", aggfunc="sum").reindex(labels).fillna(0)
    fig, ax = plt.subplots()
    bottom = 0
    for klass, c in (("fixed_bullet", BLUE), ("inflation_linked", GREEN)):
        if klass in p.columns:
            ax.bar(p.index, p[klass] / 1000 * 100, bottom=bottom, color=c, label=klass, width=0.7)
            bottom = bottom + p[klass] / 1000 * 100
    ax.set_ylabel("EUR bn of market value per 100 bp"); ax.set_xlabel("years to maturity"); ax.grid(axis="y")
    s = sim.duration_summary(spread_bp)
    ax.set_title(f"France · where the rate risk sits: €{s['loss_per_100bp_bn']:,.0f}bn per 100 bp on €{s['market_value_bn']:,.0f}bn of OATs (mod. duration {s['modified_duration_years']:.1f}y)")
    ax.legend()
    _source(fig, f"Source: ggfiscal.debt.simulate.duration_table at Bund curve + {spread_bp:.0f} bp; annual coupons; linkers on real yields. Bills excluded.")
    _save(fig, out)
    g.to_csv(out.parent / "duration_by_bucket.csv", index=False)
    return out


def render_all(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    res = sim.run_all()
    res.to_csv(out_dir / "scenarios_FRA.csv", index=False)
    dec = pd.concat([sim.decompose_gap(sc) for sc in sim.SCENARIOS[1:]], ignore_index=True)
    dec.to_csv(out_dir / "scenario_decomposition.csv", index=False)
    gf, gdp, led, exp = _history()
    figs = {}
    figs["scen_interest"] = chart_interest(res, out_dir / "scen_interest.png")
    figs["scen_deficit"] = chart_paths(res, out_dir / "scen_deficit.png", "deficit_pct_gdp", "% of GDP (deficit, positive)",
                                       "France · general-government deficit each scenario implies", ref=3.0,
                                       hist=(-led.loc[2015:2025, "nlb_pct_gdp"]))
    figs["scen_debt"] = chart_paths(res, out_dir / "scen_debt.png", "debt_pct_gdp", "% of GDP",
                                    "France · Maastricht debt ratio each scenario implies", ref=None,
                                    hist=pd.Series({2025: sim.BASELINE.debt_2025_pct}))
    figs["scen_spread"] = chart_spread(res, out_dir / "scen_spread.png")
    figs["scen_decomposition"] = chart_decomposition(dec, out_dir / "scen_decomposition.png")
    figs["scen_issuance"] = chart_issuance(res, out_dir / "scen_issuance.png")
    figs["scen_coupon"] = chart_coupon(res, out_dir / "scen_coupon.png")
    figs["duration"] = chart_duration(out_dir / "duration.png")
    return figs


if __name__ == "__main__":       # pragma: no cover
    root = sim.ROOT
    figs = render_all(root / "reports" / "briefing_FRA_AFT_2026-09" / "figures")
    for k, p in figs.items():
        print(k, p, f"{p.stat().st_size / 1024:.0f} KB")
