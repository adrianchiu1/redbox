"""Scenario charts for the AFT briefing (D-S12-001): the register-based
interest simulation of `ggfiscal.debt.simulate` drawn in the debtbook's
palette. `render_all(out_dir)` writes the PNGs, `scenarios_FRA.csv` (every
scenario-year the engine produced), `scenario_decomposition.csv`,
`scenario_loop.csv` and `duration_by_bucket.csv` next to them, and returns
{key: path}.
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

# One hue per candidate, the Assembly outcome as the line style (D-S18-004):
# majority solid, hung dotted. Grey is the statistical benchmark; history is
# near-black ink. The three party hues pass the dataviz validator against
# SURFACE (lightness, chroma, CVD and normal-vision separation); the yellow is
# below 3:1 contrast, so every chart carries a legend and the end labels.
FR_BLUE, PH_YELLOW, MEL_RED, STAT_GREY, HIST = "#0055A4", "#D4A200", "#A51E22", "#8A8A85", "#1C1F24"
DOTTED = (0, (1.0, 1.7))
SCEN_STYLE = {
    "statistical": (STAT_GREY, "-"),
    "philippe_majority": (PH_YELLOW, "-"), "philippe_hung": (PH_YELLOW, DOTTED),
    "lepen_majority": (FR_BLUE, "-"), "lepen_hung": (FR_BLUE, DOTTED),
    "melenchon": (MEL_RED, "-"),
}
SHORT = {"statistical": "Statistical", "philippe_majority": "Philippe, maj.",
         "philippe_hung": "Philippe, hung", "lepen_majority": "Le Pen, maj.",
         "lepen_hung": "Le Pen, hung", "melenchon": "Mélenchon"}
DPI = 220
HIST_FROM = 2010                     # every history line starts here (D-S18-001)
REF = sim.REFERENCE


def _label(name):
    return sim.scenario(name).label


def _style(name):
    """Line keywords for a scenario. Dotted lines are drawn a little heavier
    and on top, so the solid grey benchmark shows through the gaps where it
    shares a path with Philippe, hung."""
    c, ls = SCEN_STYLE[name]
    dotted = ls is DOTTED
    return {"color": c, "ls": ls, "lw": 2.5 if dotted else 2.0, "zorder": 4 if dotted else 3,
            "dash_capstyle": "round", "solid_capstyle": "round"}


plt.rcParams.update({
    "figure.figsize": (7.2, 3.3), "figure.dpi": DPI,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK, "axes.titlecolor": INK,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 9, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "grid.color": AXIS, "grid.alpha": 0.45, "grid.linewidth": 0.6,
    "legend.frameon": False, "legend.fontsize": 8, "legend.handlelength": 3.2, "lines.linewidth": 1.8,
})

DELIV = sim.DELIV


def _source(fig, text, y=-0.02):
    fig.text(0.01, y, text, fontsize=7, color=MUTED, ha="left", va="top")


def _save(fig, path):
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def _history():
    strict = pd.read_csv(DELIV / "strict_FRA.csv").set_index("year")
    gf = strict["GF01_7 - Public debt transactions (interest)"]
    gdp = strict["GDP - Gross domestic product at current market prices"]
    led = pd.read_csv(DELIV / "balance_ledger.csv").query("iso3 == 'FRA' and variant == 'strict'").set_index("year")
    exp = pd.read_csv(DELIV / "expenditure_cofog.csv", low_memory=False).query(
        "iso3 == 'FRA' and variant == 'strict' and line_code == 'GF01_7'").set_index("year")
    return gf, gdp, led, exp


def debt_history() -> pd.Series:
    """Maastricht debt, % of GDP, general government (Eurostat gov_10dd_edpt1,
    S13 GD), from the hand-keyed file under data/manual."""
    d = pd.read_csv(sim.ROOT / "data" / "manual" / "FRA_maastricht_debt_pct_gdp.csv")
    return d.set_index("year").value.astype(float)


def chart_interest(res, out):
    gf, gdp, led, exp = _history()
    fig, ax = plt.subplots()
    ax.axvspan(2025.5, 2035.5, color=SHADE, lw=0, zorder=0)
    h = exp.loc[HIST_FROM:2024, "pct_gdp"]
    ax.plot(h.index, h.values, color=HIST, lw=2.2, label="outturn (Eurostat, GF01_7)")
    d = exp.loc[2025:2035, "pct_gdp"]
    ax.plot(d.index, d.values, color=BROWN, ls="-.", lw=1.2, label="EC AMECO / DSM path in the strict file")
    for name in SCEN_STYLE:
        s = res[res.scenario == name].set_index("year")
        s = pd.concat([pd.Series({2025: exp.loc[2025, "pct_gdp"]}), s.gg_interest_pct_gdp])
        ax.plot(s.index, s.values, **_style(name), label=_label(name))
    ax.set_ylabel("% of GDP"); ax.set_xlim(HIST_FROM - 0.3, 2039.5); ax.grid(axis="y")
    ax.set_title("France · general-government interest, outturn and six paths from the register")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    for name in ("melenchon", "philippe_hung", "lepen_majority"):
        s = res[(res.scenario == name) & (res.year == 2035)].iloc[0]
        ax.annotate(f"{SHORT[name]} {s.gg_interest_pct_gdp:.1f}%, €{s.gg_interest_bn:,.0f}bn", (2035, s.gg_interest_pct_gdp),
                    xytext=(4, 0), textcoords="offset points", fontsize=7.5, color=INK, va="center")
    _source(fig, "Source: ggfiscal.debt.simulate on deliverables/debt_positions.csv at 2026-09-10; strict_FRA.csv. Interest on the accrual basis; wedge to GF01_7 held at 0.34% of GDP.", y=-0.2)
    _save(fig, out); return out


def chart_paths(res, out, col, ylabel, title, ref=None, hist=None, annotate=False, source=None):
    fig, ax = plt.subplots()
    ax.axvspan(2025.5, 2035.5, color=SHADE, lw=0, zorder=0)
    ends = {}
    if hist is not None:
        ax.plot(hist.index, hist.values, color=HIST, lw=2.2, label="outturn")
    for name in SCEN_STYLE:
        s = res[res.scenario == name].set_index("year")[col]
        if hist is not None and 2025 in hist.index:
            s = pd.concat([pd.Series({2025: hist.loc[2025]}), s])
        ax.plot(s.index, s.values, **_style(name), label=_label(name))
        ends[name] = float(s.iloc[-1])
    if annotate:                     # end labels, nudged apart so none overlap
        span = ax.get_ylim()[1] - ax.get_ylim()[0]
        placed = []
        for name, v in sorted(ends.items(), key=lambda kv: kv[1]):
            y = max(v, placed[-1] + 0.045 * span) if placed else v
            placed.append(y)
            ax.annotate(f"{SHORT[name]} {v:.0f}%", (2035, v), xytext=(2035.25, y), textcoords="data",
                        fontsize=7.5, color=INK, va="center")
    if ref is not None:
        ax.axhline(ref, color=AXIS, ls="--", lw=1)
    ax.set_ylabel(ylabel); ax.grid(axis="y"); ax.set_title(title)
    ax.set_xlim((hist.index.min() if hist is not None else 2025) - 0.3, 2038.8 if annotate else 2035.5)
    ax.legend(ncol=2, loc="upper left")
    _source(fig, source or "Source: ggfiscal.debt.simulate (declared scenarios, see the assumptions table); balance_ledger.csv for the outturn.")
    _save(fig, out); return out


def chart_spread(res, out):
    ref = pd.read_csv(DELIV / "debt_reference_series.csv", low_memory=False)
    p = ref[ref.series_id.isin(["FR_LT10", "DE_LT10"])].pivot_table(index="date", columns="series_id", values="value")
    p.index = pd.to_datetime(p.index)
    sp = ((p.FR_LT10 - p.DE_LT10) * 100).dropna()
    sp = sp[sp.index >= f"{HIST_FROM}-01-01"]
    b = sim.BASELINE
    today = pd.Timestamp(b.spread_today_date)
    xt = today.year + (today.dayofyear - 0.5) / 365
    fig, ax = plt.subplots()
    ax.axvspan(2026.85, 2035.5, color=SHADE, lw=0, zorder=0)
    x = sp.index.year + (sp.index.month - 0.5) / 12
    ax.plot(x, sp.values, color=HIST, lw=1.3, label="OAT–Bund 10y, monthly (OECD) and today (Bloomberg)")
    ax.plot([x[-1], xt], [sp.values[-1], b.spread_today_bp], color=HIST, lw=1.3)
    ax.plot([xt], [b.spread_today_bp], marker="o", ms=5, color=HIST)
    ax.annotate(f"{b.spread_today_bp:.0f} bp, {today:%-d %b %Y}", (xt, b.spread_today_bp), xytext=(-6, 8),
                textcoords="offset points", fontsize=7.5, color=INK, ha="right")
    for name in SCEN_STYLE:
        s = res[(res.scenario == name) & (res.year >= 2027)].set_index("year").spread_bp
        ax.plot([xt, *(s.index + 0.5)], [b.spread_today_bp, *s.values], **_style(name),
                label=_label(name), marker="o", ms=3, markevery=list(range(1, len(s) + 1)))
    ax.set_ylabel("basis points"); ax.grid(axis="y"); ax.set_xlim(HIST_FROM - 0.3, 2035.9)
    ax.set_title("France · the OAT–Bund spread, history and the paths each scenario declares")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    _source(fig, f"Source: debt_reference_series.csv (FR_LT10 − DE_LT10, OECD monthly to Sep 2026); {today:%-d %b %Y} spot, Bloomberg.\n"
                 "Scenario paths are declared annual averages: the 2027 level, a straight fade to 2029, flat after; no feedback.", y=-0.24)
    _save(fig, out); return out


def chart_decomposition(dec, out):
    d = dec[dec.year == 2030].set_index("scenario").drop(index=REF, errors="ignore")
    order = ["statistical", "philippe_majority", "lepen_majority", "lepen_hung", "melenchon"]
    d = d.reindex([o for o in order if o in d.index])
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    x = range(len(d))
    ax.bar(x, d.spread_effect_bn, color=ORANGE, width=0.6, label="spread (price of new debt)")
    neg = d.spread_effect_bn < 0
    ax.bar(x, d.volume_effect_bn, bottom=d.spread_effect_bn.where(~neg, 0).where(d.volume_effect_bn >= 0, d.spread_effect_bn.clip(upper=0)), color=TEAL, width=0.6, label="primary balance & growth (volume)")
    ax.bar(x, d.interaction_bn, bottom=(d.spread_effect_bn.clip(lower=0) + d.volume_effect_bn.clip(lower=0)), color=MUTED, width=0.6, label="interaction (the loop)")
    top = d.gap_bn.max() + max(d.interaction_bn.clip(lower=0).max(), 0)
    lo = min(d.spread_effect_bn.clip(upper=0).sum(), 0) - 1
    ax.set_ylim(min(d.gap_bn.min(), 0) - 5, top * 1.35)
    for i, (_, r) in enumerate(d.iterrows()):
        y = r.gap_bn + 1.0 if r.gap_bn >= 0 else min(r.spread_effect_bn, 0) + min(r.volume_effect_bn, 0) - 1.0
        ax.text(i, y, f"{r.gap_bn:+.1f}" if abs(r.gap_bn) < 1 else f"{r.gap_bn:+.0f}", ha="center", va="bottom" if r.gap_bn >= 0 else "top", fontsize=8.5, color=INK, fontweight="bold")
    ax.axhline(0, color=AXIS, lw=1)
    ax.set_xticks(list(x)); ax.set_xticklabels([r.label.replace(", ", "\n") for _, r in d.iterrows()], fontsize=8)
    ax.set_ylabel("EUR bn, 2030, vs Philippe hung"); ax.grid(axis="y")
    ax.set_title("France · what the 2030 interest gap to the status quo (Philippe, hung) is made of")
    ax.legend(loc="upper left")
    _source(fig, "Source: ggfiscal.debt.simulate.decompose_gap — each lever re-run alone against the status quo, feedback off.")
    _save(fig, out); return out


def chart_issuance(res, out):
    fig, ax = plt.subplots()
    ax.axvspan(2026.5, 2035.5, color=SHADE, lw=0, zorder=0)
    for name in SCEN_STYLE:
        s = res[(res.scenario == name) & (res.year >= 2027)].set_index("year")
        ax.plot(s.index, s.mlt_gross_issuance_bn, **_style(name), label=_label(name))
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
    w = w.loc[HIST_FROM:]
    ax.plot(w.index, w.values, color=HIST, lw=2.2, label="average coupon, fixed-rate stock (register)")
    for name in SCEN_STYLE:
        s = res[res.scenario == name].set_index("year")
        ax.plot([2025, *s.index], [w.loc[2025], *s.avg_coupon_fixed_pct], **_style(name), label=_label(name))
        if name in ("philippe_hung", "melenchon"):          # thin 10y-yield lines
            ax.plot(s.index, s.oat_10y_pct, color=SCEN_STYLE[name][0], ls=SCEN_STYLE[name][1], lw=1.0, alpha=0.6)
    ax.text(2011.0, 6.55, "thin lines: the 10y OAT yield, status quo and Mélenchon", fontsize=7.5, color=MUTED)
    ax.set_ylabel("%"); ax.grid(axis="y"); ax.set_xlim(HIST_FROM - 0.3, 2035.5); ax.set_ylim(1.2, 6.9)
    ax.set_title("France · the average coupon keeps rising whoever wins: the refinancing drag")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    _source(fig, "Source: deliverables/debt_positions.csv × debt_securities.csv; ggfiscal.debt.simulate for the paths.", y=-0.2)
    _save(fig, out); return out


def chart_duration(out, spread_bp=sim.BASELINE.spread_today_bp):
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


def chart_tree(res, out):
    """The scenario decision tree: who is president, then whether the Assembly
    gives a majority, and the three assumptions each branch carries (primary
    balance, spread, growth). Drawn from sim.SCENARIOS, not typed in."""
    from matplotlib.patches import FancyBboxPatch, Rectangle

    sc = {x.name: x for x in sim.SCENARIOS}
    leaves = ["philippe_majority", "philippe_hung", "lepen_majority", "lepen_hung", "melenchon"]
    fig = plt.figure(figsize=(9.6, 5.1))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    top, row_h = 0.80, 0.112                       # first leaf row centre, row pitch
    y_of = {n: top - i * row_h for i, n in enumerate(leaves)}
    y_stat = y_of["melenchon"] - row_h * 1.12

    def box(x0, x1, yc, h, text, edge=AXIS, ls="-", lw=1.0, accent=None, size=9.5, weight="normal", fill="#ffffff"):
        ax.add_patch(FancyBboxPatch((x0, yc - h / 2), x1 - x0, h, boxstyle="round,pad=0,rounding_size=0.008",
                                    fc=fill, ec=edge, lw=lw, ls=ls, zorder=2))
        if accent:
            ax.add_patch(Rectangle((x0, yc - h / 2), 0.008, h, fc=accent, ec="none", zorder=3))
        ax.text((x0 + x1) / 2 + (0.004 if accent else 0), yc, text, ha="center", va="center", fontsize=size,
                color=INK, fontweight=weight, zorder=4, linespacing=1.25)

    def elbow(x0, y0, x1, y1):
        xm = (x0 + x1) / 2
        ax.plot([x0, xm, xm, x1], [y0, y0, y1, y1], color=AXIS, lw=1.1, zorder=1, solid_joinstyle="round")

    # columns
    X_ROOT, X_PRES, X_ASM, X_TAB = (0.012, 0.135), (0.175, 0.300), (0.335, 0.470), 0.505
    COLS = [(0.505, 0.665), (0.665, 0.835), (0.835, 0.988)]

    ax.text(0.012, 0.965, "France · the 2027 scenario tree and the three assumptions each branch carries",
            fontsize=11.5, fontweight="bold", color=INK, va="center")
    for (x0, x1), head in zip(COLS, ["Primary balance\n€bn a year, 2028–31 / after",
                                     "OAT–Bund 10y spread, bp\n2027 → 2029 onward",
                                     "Real GDP growth\na year from 2028"]):
        ax.text((x0 + x1) / 2, top + row_h * 0.78, head, ha="center", va="center", fontsize=8.6, color=MUTED,
                linespacing=1.2)
    for lbl, xs in (("President", X_PRES), ("Assembly", X_ASM)):
        ax.text(sum(xs) / 2, top + row_h * 0.78, lbl, ha="center", va="center", fontsize=8.6, color=MUTED)

    y_root = (y_of["philippe_majority"] + y_of["melenchon"]) / 2
    box(*X_ROOT, y_root, 0.16, "2027\npresidential\nelection", size=9.5, weight="bold", fill="#f4f3ef")

    pres = {"Philippe": (["philippe_majority", "philippe_hung"], PH_YELLOW),
            "Le Pen": (["lepen_majority", "lepen_hung"], FR_BLUE),
            "Mélenchon": (["melenchon"], MEL_RED)}
    for name, (kids, colour) in pres.items():
        yc = sum(y_of[k] for k in kids) / len(kids)
        elbow(X_ROOT[1], y_root, X_PRES[0], yc)
        box(*X_PRES, yc, 0.075, name, edge=colour, lw=1.6, accent=colour, size=10.5, weight="bold")
        for k in kids:
            hung = k.endswith("hung")
            label = ("Hung Assembly" if hung else "Majority") if name != "Mélenchon" else "Majority or hung\n(one case)"
            elbow(X_PRES[1], yc, X_ASM[0], y_of[k])
            box(*X_ASM, y_of[k], 0.075, label, edge=colour, ls=(0, (1.0, 1.6)) if hung else "-",
                lw=1.6, size=9.2)
            elbow(X_ASM[1], y_of[k], X_TAB, y_of[k])

    def row(yc, cells, colour, ls="-", tag=None):
        ax.add_patch(FancyBboxPatch((X_TAB, yc - 0.042), COLS[-1][1] - X_TAB, 0.084,
                                    boxstyle="round,pad=0,rounding_size=0.008", fc="#ffffff", ec=colour,
                                    lw=1.6, ls=ls, zorder=2))
        for (x0, x1), (main, sub) in zip(COLS, cells):
            ax.text((x0 + x1) / 2, yc + (0.011 if sub else 0), main, ha="center", va="center", fontsize=12,
                    fontweight="bold", color=INK, zorder=4)
            if sub:
                ax.text((x0 + x1) / 2, yc - 0.022, sub, ha="center", va="center", fontsize=7.6, color=MUTED, zorder=4)
        if tag:
            ax.text(COLS[-1][1] - 0.006, yc + 0.031, tag, ha="right", va="center", fontsize=7.2, color=MUTED, zorder=4)

    for k in leaves:
        x = sc[k]
        row(y_of[k], [(f"{x.consolidation_bn:+.0f} / {x.consolidation_after_bn:+.0f}",
                       "looser" if x.consolidation_bn < 0 else None),
                      (f"{x.spread_2027_bp:.0f} → {x.spread_2029_bp:.0f}", None),
                      (f"{100 * x.real_growth:.1f}%", None)],
            SCEN_STYLE[k][0], ls=(0, (1.0, 1.6)) if k.endswith("hung") else "-",
            tag="status quo" if k == REF else None)

    # the no-politics reference
    st = res[res.scenario == "statistical"].set_index("year").primary_balance_bn.diff()
    lo, hi = st.loc[2028:2031].min(), st.loc[2028:2031].max()
    x = sc["statistical"]
    box(X_PRES[0], X_ASM[1], y_stat, 0.075, "Statistical benchmark\n(no politics: Redbox line forecasts)",
        edge=STAT_GREY, lw=1.6, accent=STAT_GREY, size=9.0)
    elbow(X_ASM[1], y_stat, X_TAB, y_stat)
    row(y_stat, [(f"{lo:+.0f} to {hi:+.0f}", "trend, then ratio flat"),
                 (f"{x.spread_2027_bp:.0f} → {x.spread_2029_bp:.0f}", "as status quo"),
                 (f"{100 * x.real_growth:.1f}%", "as status quo")], STAT_GREY)

    b = sim.BASELINE
    ax.set_ylim(y_stat - 0.135, 1.0)
    ax.text(0.012, y_stat - 0.085, f"Common to every branch: Bund 10y {b.bund_curve[10]:.2f}% flat; spread {b.spread_today_bp:.0f} bp today "
            f"(Bloomberg, 11 Oct 2026); primary balance {b.primary_balance[2027]:.1f}% of GDP in 2027, policy from 2028; "
            f"GDP deflator {100 * b.deflator_after:.0f}%; same issuance mix and bill stock.",
            fontsize=7.6, color=MUTED, va="center")
    ax.text(0.012, y_stat - 0.115, "Solid border: majority. Dotted border: hung Assembly. Positive primary-balance change = smaller primary deficit. "
            "Source: ggfiscal.debt.simulate.SCENARIOS.", fontsize=7.0, color=MUTED, va="center")
    _save(fig, out); return out


def render_all(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    res = sim.run_all()
    res.to_csv(out_dir / "scenarios_FRA.csv", index=False)
    dec = pd.concat([sim.decompose_gap(sc) for sc in sim.SCENARIOS if sc.name != REF], ignore_index=True)
    dec.to_csv(out_dir / "scenario_decomposition.csv", index=False)
    loop = pd.concat([sim.loop_size(sc) for sc in sim.SCENARIOS if sc.name != REF], ignore_index=True)
    loop.to_csv(out_dir / "scenario_loop.csv", index=False)
    gf, gdp, led, exp = _history()
    figs = {}
    figs["scen_interest"] = chart_interest(res, out_dir / "scen_interest.png")
    figs["scen_deficit"] = chart_paths(res, out_dir / "scen_deficit.png", "deficit_pct_gdp", "% of GDP (deficit, positive)",
                                       "France · general-government deficit each scenario implies", ref=3.0,
                                       hist=(-led.loc[HIST_FROM:2025, "nlb_pct_gdp"]))
    figs["scen_debt"] = chart_paths(res, out_dir / "scen_debt.png", "debt_pct_gdp", "% of GDP",
                                    "France · Maastricht debt ratio, outturn and the path each scenario implies", ref=None,
                                    hist=debt_history().loc[HIST_FROM:2025], annotate=True,
                                    source="Source: Eurostat gov_10dd_edpt1 (S13, GD) to 2025, data/manual; ggfiscal.debt.simulate from 2026 (declared scenarios).")
    figs["scen_spread"] = chart_spread(res, out_dir / "scen_spread.png")
    figs["scen_tree"] = chart_tree(res, out_dir / "scen_tree.png")
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
