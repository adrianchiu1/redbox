"""Charts for the France brief's balance-sheet section (D-S19-001): the
asset side of the general-government balance sheet drawn beside the gross
stock, in the briefing's palette. `render_all(out_dir)` writes the PNGs and
`balance_sheet_FRA.csv` (the history), `sfa_components_FRA.csv`,
`ladder_FRA.csv` and `selldown_FRA.csv` (every run-year with the net view)
next to them, and returns {key: path}.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ggfiscal.debt import balance_sheet as bs
from ggfiscal.debt import simulate as sim
from ggfiscal.report.briefing_fra_scenarios import (AXIS, BLUE, GOLD, HIST, INK, MUTED, ORANGE, PH_YELLOW, PURPLE, RED,
                                                    SHADE, SURFACE, TEAL, DOTTED, DPI, HIST_FROM, _save, _source)

RUN_STYLE = {
    "status_quo": {"color": PH_YELLOW, "ls": DOTTED, "lw": 2.5, "zorder": 4},
    "liquidity": {"color": TEAL, "ls": "-", "lw": 2.0},
    "realistic": {"color": BLUE, "ls": "-", "lw": 2.0},
    "maximal": {"color": PURPLE, "ls": "-", "lw": 2.0},
    "extreme": {"color": RED, "ls": "-", "lw": 2.0},
}
CLASS_COLOURS = {"f2_pct": TEAL, "f3_pct": BLUE, "f4_pct": ORANGE, "f51_pct": PURPLE, "f52_pct": GOLD, "f8_pct": "#b9b7ae"}
CLASS_LABELS = {"f2_pct": "currency and deposits (F.2)", "f3_pct": "debt securities (F.3)", "f4_pct": "loans (F.4)",
                "f51_pct": "equity (F.51)", "f52_pct": "investment fund shares (F.52)", "f8_pct": "other receivables (F.8)"}
UPD = bs.updated()


def chart_gross_net(h, runs, out):
    sq = runs[runs.run == "status_quo"].set_index("year")
    fig, ax = plt.subplots()
    ax.axvspan(2025.5, 2035.5, color=SHADE, lw=0, zorder=0)
    hh = h.loc[HIST_FROM:2025]
    ax.plot(hh.index, hh.gross_pct, color=HIST, lw=2.2, label="Maastricht debt, gross (face value)")
    ax.plot(hh.index, hh.net_pct, color=BLUE, lw=2.0, label="net debt: less cash, paper and loans held (INSEE definition)")
    ax.plot(hh.index, hh.net_fin_pct, color=PURPLE, lw=2.0, label="also net of equity holdings at market value")
    f = pd.concat([pd.Series({2025: hh.gross_pct[2025]}), sq.debt_pct_gdp])
    ax.plot(f.index, f.values, color=HIST, ls=DOTTED, lw=2.4, label="status quo (Philippe, hung), gross")
    f = pd.concat([pd.Series({2025: hh.net_pct[2025]}), sq.net_debt_pct_gdp])
    ax.plot(f.index, f.values, color=BLUE, ls=DOTTED, lw=2.4, label="status quo, net")
    f = pd.concat([pd.Series({2025: hh.net_fin_pct[2025]}), sq.net_fin_debt_pct_gdp])
    ax.plot(f.index, f.values, color=PURPLE, ls=DOTTED, lw=2.4, label="status quo, net of equity too")
    for v, lab, dy in ((hh.gross_pct[2025], "gross", 4), (hh.net_pct[2025], "net", -9), (hh.net_fin_pct[2025], "net of equity", 4)):
        ax.annotate(f"{lab} {v:.0f}%", (2025, v), xytext=(-4, dy), textcoords="offset points", fontsize=7.5, color=INK, ha="right")
    ax.text(2026.0, 62, f"Rebuilt from Eurostat: net debt €{hh.net_bn[2025]:,.0f}bn at end-2025;\nINSEE publishes €{bs.INSEE_2025['net_bn']:,.1f}bn, {bs.INSEE_2025['net_pct']:.1f}% of GDP.",
            fontsize=7.2, color=MUTED, va="center")
    ax.set_ylabel("% of GDP"); ax.set_xlim(HIST_FROM - 0.3, 2035.8); ax.grid(axis="y")
    ax.set_title("France · the gross stock and two net measures, outturn and the status quo")
    ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    _source(fig, f"Source: Eurostat gov_10dd_edpt1 (debt), gov_10a_ggfa (financial assets, S13 consolidated, market value; updated {UPD['gov_10a_ggfa']}), data/manual; "
                 "ggfiscal.debt.balance_sheet on the status-quo run from 2026 (liquid assets flat in euros, equity with nominal GDP).", y=-0.26)
    _save(fig, out); return out


def chart_assets(h, out):
    hh = h.loc[2000:2025]
    cols = ["f2_pct", "f3_pct", "f4_pct", "f51_pct", "f52_pct", "f8_pct"]
    fig, ax = plt.subplots()
    bottom = np.zeros(len(hh))
    for c in cols:
        ax.bar(hh.index, hh[c].values, bottom=bottom, color=CLASS_COLOURS[c], width=0.8, lw=0, label=CLASS_LABELS[c])
        bottom += hh[c].fillna(0).values
    ax.plot(hh.index, hh.cash_cg_pct, color=INK, lw=1.6, marker="o", ms=2.5, label="of which the État's cash (S.1311 F.2)")
    ax.set_ylabel("% of GDP"); ax.grid(axis="y"); ax.set_xlim(1999.3, 2025.7)
    ax.set_title("France · general-government financial assets by instrument, market value")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    r = hh.loc[2025]
    ax.annotate(f"end-2025: €{r.f_bn:,.0f}bn, {r.f_pct:.0f}% of GDP\nliquid (F.2–F.4) €{r.liquid_bn:,.0f}bn · equity €{r.f5_bn:,.0f}bn",
                (2025, r.f_pct), xytext=(-8, 8), textcoords="offset points", fontsize=7.5, color=INK, ha="right", va="bottom")
    _source(fig, f"Source: Eurostat gov_10a_ggfa, S13 consolidated, assets at market value (updated {UPD['gov_10a_ggfa']}); S1311 F.2 for the État's cash. data/manual/FRA_balance_sheet_eurostat.csv.", y=-0.24)
    _save(fig, out); return out


def chart_sfa(h, comp, out):
    hh = h.loc[1999:2025]
    fig, ax = plt.subplots()
    colours = [RED if v > 0 else TEAL for v in hh.sfa_pct]
    ax.bar(hh.index, hh.sfa_pct, color=colours, width=0.8, lw=0, label="stock-flow adjustment: Δdebt + net lending (S13)")
    ax.axhline(0, color=AXIS, lw=0.8)
    m = hh.sfa_pct.mean()
    ax.axhline(m, color=MUTED, lw=0.9, ls="--", label=f"1999–2025 mean, {m:+.2f}% of GDP")
    c = 100 * comp.cash_and_deposits / h.gdp_bn.reindex(comp.index)
    ax.plot(c.index, c.values, color=INK, marker="D", ms=4, lw=0, label="of which the État's net cash acquisition (S.1311, EDP table 3)")
    for y in (2020, 2024):
        ax.annotate(f"{y}: €{hh.sfa_bn[y]:,.0f}bn", (y, hh.sfa_pct[y]), xytext=(0, 3), textcoords="offset points", fontsize=7.5, color=INK, ha="center")
    ax.set_ylabel("% of GDP"); ax.grid(axis="y"); ax.set_xlim(1998.3, 2025.7)
    ax.set_title("France · debt that moved without a deficit: the stock-flow adjustment")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    _source(fig, "Source: Eurostat gov_10dd_edpt1 debt levels and balance_ledger.csv (strict NLB); deliverables/debt_financing_reconciliation.csv step B for the S.1311 components (Eurostat gov_10dd_edpt3). Positive = debt rose more than the deficit.", y=-0.24)
    _save(fig, out); return out


def chart_net_interest(h, runs, out):
    sq = runs[runs.run == "status_quo"].set_index("year")
    hh = h.loc[HIST_FROM:2025]
    fig, ax = plt.subplots()
    ax.axvspan(2025.5, 2035.5, color=SHADE, lw=0, zorder=0)
    ax.plot(hh.index, hh.interest_paid_pct, color=HIST, lw=2.2, label="interest paid (D.41)")
    ax.plot(hh.index, hh.asset_income_pct, color=TEAL, lw=2.0, label="interest and dividends received (D.41 + D.42)")
    ax.plot(hh.index, hh.net_interest_pct, color=BLUE, lw=2.0, label="net interest: paid less received")
    f = pd.concat([pd.Series({2025: hh.interest_paid_pct[2025]}), sq.gg_interest_pct_gdp])
    ax.plot(f.index, f.values, color=HIST, ls=DOTTED, lw=2.4, label="status quo, interest paid (engine)")
    f = pd.concat([pd.Series({2025: hh.asset_income_pct[2025]}), 100 * sq.asset_income_bn / sq.gdp_bn])
    ax.plot(f.index, f.values, color=TEAL, ls=DOTTED, lw=2.4, label="status quo, asset income")
    f = pd.concat([pd.Series({2025: hh.net_interest_pct[2025]}), sq.net_interest_pct_gdp])
    ax.plot(f.index, f.values, color=BLUE, ls=DOTTED, lw=2.4, label="status quo, net interest")
    for col, lab in (("gg_interest_bn", "paid"), ("net_interest_bn", "net")):
        v = sq[col][2035]
        ax.annotate(f"2035 {lab}: €{v:,.0f}bn", (2035, 100 * v / sq.gdp_bn[2035]), xytext=(4, 0), textcoords="offset points", fontsize=7.5, color=INK, va="center")
    ax.set_ylabel("% of GDP"); ax.set_xlim(HIST_FROM - 0.3, 2039.5); ax.grid(axis="y")
    ax.set_title("France · the interest bill gross and net of what the assets pay")
    ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    _source(fig, f"Source: Eurostat gov_10a_main D41PAY, D41REC, D42REC (S13; updated {UPD['gov_10a_main']}); ggfiscal.debt.simulate for the status quo interest; "
                 "ggfiscal.debt.balance_sheet for the asset income (2025 yields on the stocks). Rents (D.45) excluded.", y=-0.26)
    _save(fig, out); return out


def chart_ladder(lad, out):
    d = lad[lad.key != "nonfin"].iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    y = np.arange(len(d))
    ax.barh(y, d.stock_bn, color="#e4e2db", height=0.72, lw=0, label="stock at end-2025")
    ax.barh(y, d.sold_extreme_bn, color="#f3c6c9", height=0.72, lw=0, label="counted in the extreme run")
    ax.barh(y, d.sold_maximal_bn, color="#cdb7ea", height=0.72, lw=0, label="counted in 'everything financial'")
    ax.barh(y, d.sold_realistic_bn, color=BLUE, height=0.72, lw=0, label="counted in the realistic sell-down")
    ax.barh(y, d.sold_liquidity_bn, color=TEAL, height=0.72, lw=0, label="counted in the liquidity drawdown")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{lab}{' (ext)' if e else ''}" for lab, e in zip(d.label, d.ext)], fontsize=8.5)
    for yy, (stock, liq, where) in enumerate(zip(d.stock_bn, d.liquidity, d["where"])):
        ax.annotate(f"€{stock:,.0f}bn · {liq} · {where}", (stock, yy), xytext=(5, 0), textcoords="offset points", fontsize=7.3, color=MUTED, va="center")
    ax.set_xlim(0, d.stock_bn.max() * 1.75)
    ax.set_xlabel("EUR bn, end-2025"); ax.grid(axis="x")
    ax.set_title("France · the sell-down ladder: what is there, and how much each run sells")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=7.5)
    _source(fig, f"Source: Eurostat gov_10a_ggfa S13 consolidated, market value; ext: APE (30 Jun 2025), CDC results 2025, Banque de France rapport annuel 2025. "
                 f"Non-financial assets (€{lad.loc[lad.key == 'nonfin', 'stock_bn'].iloc[0]:,.0f}bn) are not drawn and not counted. Amounts are declared (ggfiscal.debt.balance_sheet.LADDER).", y=-0.3)
    _save(fig, out); return out


def chart_selldown(runs, h, out):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw={"wspace": 0.28})
    for ax in (ax1, ax2):
        ax.axvspan(2025.5, 2035.5, color=SHADE, lw=0, zorder=0); ax.grid(axis="y")
    hh = h.loc[2019:2025]
    ax1.plot(hh.index, hh.gross_pct, color=HIST, lw=2.0)
    ax2.plot(hh.index, hh.net_interest_bn, color=HIST, lw=2.0)
    for run, st in RUN_STYLE.items():
        r = runs[runs.run == run].set_index("year")
        s = pd.concat([pd.Series({2025: hh.gross_pct[2025]}), r.debt_pct_gdp])
        ax1.plot(s.index, s.values, label=bs.RUNS[run][0], **st)
        s = pd.concat([pd.Series({2025: hh.net_interest_bn[2025]}), r.net_interest_bn])
        ax2.plot(s.index, s.values, **st)
        ax1.annotate(f"{r.debt_pct_gdp[2035]:.0f}%", (2035, r.debt_pct_gdp[2035]), xytext=(3, 0), textcoords="offset points", fontsize=7.2, color=st["color"], va="center")
        ax2.annotate(f"{r.net_interest_bn[2035]:,.0f}", (2035, r.net_interest_bn[2035]), xytext=(3, 0), textcoords="offset points", fontsize=7.2, color=st["color"], va="center")
    ax1.set_title("Maastricht debt, gross, % of GDP", fontsize=9.5)
    ax2.set_title("Net interest: paid less asset income, EUR bn", fontsize=9.5)
    for ax in (ax1, ax2):
        ax.set_xlim(2018.7, 2037.5)
    fig.suptitle("France · selling the assets: the status quo with each rung of the ladder deployed", x=0.01, y=1.04, ha="left", fontsize=10.5, fontweight="bold", color=INK)
    ax1.legend(ncol=3, loc="upper center", bbox_to_anchor=(1.12, -0.14), fontsize=7.5)
    _source(fig, "Source: ggfiscal.debt.simulate with the sales as a stock-flow adjustment (D-S19-001) on the Philippe-hung scenario; income forgone taken off the primary balance at the 2025 yields; "
                 "spreads as the status quo. ggfiscal.debt.balance_sheet.RUNS for the sale years.", y=-0.26)
    _save(fig, out); return out


def render_all(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    h = bs.history()
    h.to_csv(out_dir / "balance_sheet_FRA.csv")
    comp = bs.sfa_components_s1311()
    comp.to_csv(out_dir / "sfa_components_FRA.csv")
    lad = bs.ladder()
    lad.to_csv(out_dir / "ladder_FRA.csv", index=False)
    runs = bs.run_all()
    runs.to_csv(out_dir / "selldown_FRA.csv", index=False)
    figs = {}
    figs["bs_gross_net"] = chart_gross_net(h, runs, out_dir / "bs_gross_net.png")
    figs["bs_assets"] = chart_assets(h, out_dir / "bs_assets.png")
    figs["bs_sfa"] = chart_sfa(h, comp, out_dir / "bs_sfa.png")
    figs["bs_net_interest"] = chart_net_interest(h, runs, out_dir / "bs_net_interest.png")
    figs["bs_ladder"] = chart_ladder(lad, out_dir / "bs_ladder.png")
    figs["bs_selldown"] = chart_selldown(runs, h, out_dir / "bs_selldown.png")
    return figs


if __name__ == "__main__":       # pragma: no cover
    figs = render_all(sim.ROOT / "reports" / "briefing_FRA_AFT_2026-09" / "figures")
    for k, p in figs.items():
        print(k, p, f"{p.stat().st_size / 1024:.0f} KB")
