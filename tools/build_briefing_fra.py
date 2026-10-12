"""Fill the AFT briefing template with the numbers the modules produced.

Reads `reports/briefing_FRA_AFT_2026-09/briefing_template.html` and the CSVs
under `figures/`, runs the engine's summary functions, and writes two files
next to the template: `briefing.html` (figures by relative path, for the
repo) and `briefing_inline.html` (figures embedded as data URIs, a single
self-contained page to publish or mail). Fails loudly if a placeholder is
left unfilled.

    python3 -m ggfiscal.report.briefing_fra
    python3 -m ggfiscal.report.briefing_fra_scenarios
    python3 tools/build_briefing_fra.py
"""
from __future__ import annotations

import base64
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ggfiscal.debt import simulate as sim  # noqa: E402

OUT = ROOT / "reports" / "briefing_FRA_AFT_2026-09"
FIG = OUT / "figures"


def fmt(key: str, v) -> str:
    if isinstance(v, str):
        return v
    if key.endswith("_round"):
        return f"{v:,.0f}"
    if key.endswith("_1"):
        return f"{v:.1f}"
    if "coupon" in key and "pct" in key:
        return f"{v:.2f}"
    if "years" in key:
        return f"{v:.1f}"
    if "eur_bn" in key:
        return f"{v:,.0f}"
    if key.endswith("_bp"):
        return f"{v:.0f}"
    if "pct_gdp" in key or key.endswith("_pct"):
        return f"{v:.1f}"
    if key.endswith("_share"):
        return f"{100 * v:.1f}"
    return f"{v}"


def template() -> str:
    return (OUT / "briefing_template.html").read_text()


def values() -> dict[str, object]:
    """Every {{placeholder}} of the template, from the CSVs under figures/
    and the engine's summaries."""
    kf = pd.read_csv(FIG / "key_figures.csv").set_index("metric").value
    kf = kf.map(lambda v: float(v) if re.fullmatch(r"-?\d+(\.\d+)?", str(v)) else v)
    V: dict[str, object] = {}
    for k, v in kf.items():
        V[k] = fmt(k, v)
        V[k + "_round"] = fmt(k + "_round", v)
        V[k + "_1"] = fmt(k + "_1", v)
    V["bill_share_of_stock_2025_pct"] = f"{100 * kf['bill_share_of_stock_2025']:.1f}"
    V["mat_0_3_bn"] = f"{kf['maturity_2026-09-10_bucket_0-1_eur_bn'] + kf['maturity_2026-09-10_bucket_1-2_eur_bn'] + kf['maturity_2026-09-10_bucket_2-3_eur_bn']:,.0f}"

    # scenarios
    res = pd.read_csv(FIG / "scenarios_FRA.csv")
    dec = pd.read_csv(FIG / "scenario_decomposition.csv")
    R = {(r.scenario, int(r.year)): r for r in res.itertuples()}
    D = {(r.scenario, int(r.year)): r for r in dec.itertuples()}
    short = {"statistical": "stat", "philippe_majority": "pm", "philippe_hung": "ph", "lepen_majority": "lp",
             "lepen_hung": "lph", "melenchon": "mel"}
    for name, s in short.items():
        for y in (2027, 2028, 2029, 2030, 2031, 2032, 2035):
            r = R[(name, y)]
            V[f"{s}_{y}_bn"] = f"{r.gg_interest_bn:,.0f}"
            V[f"{s}_{y}_pct"] = f"{r.gg_interest_pct_gdp:.1f}"
            V[f"{s}_{y}_debt"] = f"{r.debt_pct_gdp:.0f}"
            V[f"{s}_{y}_deficit"] = f"{r.deficit_pct_gdp:.1f}"
            V[f"{s}_{y}_pb"] = f"{r.primary_balance_pct:+.1f}"
            V[f"{s}_{y}_oat10"] = f"{r.oat_10y_pct:.1f}"
            V[f"{s}_{y}_iss"] = f"{r.mlt_gross_issuance_bn:,.0f}"
            V[f"{s}_{y}_profile_dev"] = f"{r.profile_deviation_bn:,.0f}"
            V[f"{s}_{y}_cpn"] = f"{r.avg_coupon_fixed_pct:.1f}"
        for y in (2030, 2035):
            if (name, y) in D:
                d = D[(name, y)]
                V[f"{s}_{y}_gap"] = f"{d.gap_bn:,.0f}"
                V[f"{s}_{y}_gap_abs"] = f"{abs(d.gap_bn):,.0f}"
                V[f"{s}_{y}_spread"] = f"{d.spread_effect_bn:,.0f}"
                V[f"{s}_{y}_volume"] = f"{d.volume_effect_bn:,.0f}"
                V[f"{s}_{y}_interaction"] = f"{d.interaction_bn:,.1f}"
                V[f"{s}_{y}_interaction_round"] = f"{math.ceil(d.interaction_bn):,.0f}"

    # the arithmetic loop, measured directly (simulate.loop_size): the gap
    # less the gap with issuance sized on the status quo's interest bill
    for name, s in short.items():
        if name == sim.REFERENCE:
            continue
        for r in sim.loop_size(sim.scenario(name)).itertuples():
            V[f"{s}_{int(r.year)}_loop"] = f"{r.loop_bn:,.1f}" if abs(r.loop_bn) < 10 else f"{r.loop_bn:,.0f}"
            V[f"{s}_{int(r.year)}_loop_share"] = f"{100 * r.loop_share:.0f}"

    # the status quo against the EC DSM path carried in the strict file
    strict = pd.read_csv(sim.DELIV / "strict_FRA.csv").set_index("year")
    dsm = strict["GF01_7 - Public debt transactions (interest)"] / 1000
    V["dsm_2030_bn"] = f"{dsm.loc[2030]:,.0f}"
    V["ph_dsm_2030_gap"] = f"{R[('philippe_hung', 2030)].gg_interest_bn - dsm.loc[2030]:,.0f}"
    # RN promise against the Le Pen-majority path: savings to 2032 vs 2027
    lp = sim.scenario("lepen_majority")
    V["lp_savings_2032_bn"] = f"{sum(v for y, v in lp.pb_changes().items() if y <= 2032):,.0f}"

    # engine summaries
    b = sim.BASELINE
    V["profile_bill_share_pct"] = f"{100 * sim.profile_weights(sim.load_register(), b.profile_as_of)['bill']:.1f}"
    V["profile_as_of"] = b.profile_as_of
    V["spread_today_bp"] = f"{b.spread_today_bp:.0f}"
    V["oat10_today_pct"] = f"{b.bund_curve[10] + b.spread_today_bp / 100:.2f}"
    V["bund10_pct"] = f"{b.bund_curve[10]:.2f}"
    ref = pd.read_csv(sim.DELIV / "debt_reference_series.csv", low_memory=False)
    p10 = ref[ref.series_id.isin(["FR_LT10", "DE_LT10"])].pivot_table(index="date", columns="series_id", values="value").dropna()
    V["spread_latest_month_bp"] = f"{(p10.FR_LT10.iloc[-1] - p10.DE_LT10.iloc[-1]) * 100:.0f}"
    V["spread_latest_month"] = pd.Timestamp(p10.index[-1]).strftime("%B %Y")
    from ggfiscal.report.briefing_fra_scenarios import debt_history  # noqa: E402
    dh = debt_history()
    for y in (2000, 2007, 2010, 2019, 2020, 2023, 2025):
        V[f"debt_hist_{y}"] = f"{dh.loc[y]:.1f}"
    ds = sim.duration_summary(b.spread_today_bp)
    V["dur_mod"] = f"{ds['modified_duration_years']:.1f}"
    V["dur_loss100"] = f"{ds['loss_per_100bp_bn']:,.0f}"
    V["dur_loss100_pct"] = f"{ds['loss_per_100bp_pct_gdp']:.1f}"
    V["dur_mv"] = f"{ds['market_value_bn']:,.0f}"
    V["dur_nom"] = f"{ds['nominal_bn']:,.0f}"
    cal = sim.calibration()
    V["cal_wedge"] = f"{cal['gf01_7_2025_bn'] - cal['register_accrued_interest_2025_bn']:.1f}"
    V["wedge_pct_gdp"] = f"{sim.BASELINE.gg_wedge_pct:.2f}"
    # S.13 − S.1311 D.41 in 2025 from the interest chain: local government +
    # social security funds, less the consolidation residual
    chain = pd.read_csv(sim.DELIV / "debt_interest_reconciliation.csv", low_memory=False)
    c25 = chain.query("iso3 == 'FRA' and year == 2025 and step == 'C_s13_gf01_7'").set_index("item").value_lcu_mn
    V["cal_wedge_s13"] = f"{(c25['official_total'] - c25['carried_from_previous_step']) / 1000:.1f}"
    V["cal_ratio"] = f"{cal['net_issuance_over_deficit_2015_2025']:.2f}"

    # register bill stock at end-2025 and the Eurostat-minus-AFT wedge
    pos = pd.read_csv(sim.DELIV / "debt_positions.csv", low_memory=False)
    sec = pd.read_csv(sim.DELIV / "debt_securities.csv", low_memory=False)
    p25 = pos.query("iso3 == 'FRA' and as_of == '2025-12-31'").merge(sec[["security_id", "instrument_class"]], on="security_id")
    V["btf_2025_bn"] = f"{p25.loc[p25.instrument_class == 'bill', 'nominal_lcu_mn'].sum() / 1000:,.0f}"
    agg = pd.read_csv(sim.DELIV / "debt_class_aggregates.csv", low_memory=False).query("iso3 == 'FRA' and year == 2025 and measure == 'stock_year_end'").set_index("sub_type").value_lcu_mn
    V["eurostat_minus_aft"] = f"{(agg['f31_short_term_securities'] + agg['f32_long_term_securities'] - agg['dette_negociable_total']) / 1000:,.0f}"

    # holders table (external shares, register sensitivity)
    total_aft = 2903.8
    loss = ds["loss_per_100bp_bn"]
    holders = [
        ("Non-residents", 57.5, "About half euro-area. The non-euro half (Japan, Asian reserve managers) sold €30bn in 2024 and is the swing buyer now; the group that leaves first and returns last."),
        ("Other French residents, incl. Banque de France (Eurosystem: €488bn at end-June 2026)", 20.6, "The Eurosystem is a passive seller: ≈€10bn a month of run-off, no reinvestment. The TPI is the only conditional buyer."),
        ("French banks", 10.5, "Mostly amortised cost, held for liquidity ratios; insensitive to mark-to-market, sensitive to ratings, repo haircuts and the sovereign-bank loop."),
        ("French insurers", 9.6, "Euro-fund books, long duration (above-average loss). Buy on inflows; inflows reverse with rates and with any assurance-vie or wealth-tax proposal."),
        ("French funds (OPCVM)", 1.8, "Money-market funds in bills; price-insensitive, size-limited."),
    ]
    rows = []
    for name, share, beh in holders:
        rows.append(f"<tr><td class='l'>{name}</td><td>{share:.1f}%</td><td>{share / 100 * total_aft:,.0f}</td><td>{share / 100 * loss:,.0f}</td><td class='l'>{beh}</td></tr>")
    V["holders_rows"] = "\n".join(rows)

    # scenario results table
    rows = []
    for sc in sim.SCENARIOS:
        r30, r28, r35 = R[(sc.name, 2030)], R[(sc.name, 2028)], R[(sc.name, 2035)]
        cls = " class='hl'" if sc.name == sim.REFERENCE else ""
        rows.append(f"<tr{cls}><td class='l'>{sc.label}</td><td>{r30.spread_bp:.0f}</td><td>{r30.oat_10y_pct:.1f}%</td>"
                    f"<td>{r28.gg_interest_bn:,.0f}</td><td>{r30.gg_interest_bn:,.0f}</td><td>{r30.gg_interest_pct_gdp:.1f}</td>"
                    f"<td>{r35.gg_interest_bn:,.0f}</td><td>{r35.gg_interest_pct_gdp:.1f}</td><td>{r30.deficit_pct_gdp:.1f}</td>"
                    f"<td>{r30.debt_pct_gdp:.0f}</td><td>{r35.debt_pct_gdp:.0f}</td><td>{r30.mlt_gross_issuance_bn:,.0f}</td></tr>")
    V["scenario_rows"] = "\n".join(rows)

    # scenario assumptions table (section 5) and its narrative twin (section 8)
    rows, notes = [], []
    for sc in sim.SCENARIOS:
        sp = sc.spread_path(b)
        cls = " class='hl'" if sc.name == sim.REFERENCE else ""
        if sc.pb_change_pp is not None:      # the statistical benchmark: a pp-of-GDP path
            g = {y: R[(sc.name, y)].primary_balance_bn - R[(sc.name, y - 1)].primary_balance_bn for y in range(2028, 2036)}
            during = f"{min(g[y] for y in range(2028, 2032)):+.0f} to {max(g[y] for y in range(2028, 2032)):+.0f}*"
            after = "ratio flat*"
        else:
            during, after = f"{sc.consolidation_bn:+.0f}", f"{sc.consolidation_after_bn:+.0f}"
        rows.append(f"<tr{cls}><td class='l'>{sc.label}</td><td>{sc.spread_2027_bp:.0f}</td><td>{sp[2028]:.1f}</td>"
                    f"<td>{sc.spread_2029_bp:.0f}</td><td>{during}</td><td>{after}</td>"
                    f"<td>{100 * sc.real_growth:.1f}%</td><td>{100 * ((1 + sc.real_growth) * (1 + b.deflator_after) - 1):.1f}%</td>"
                    f"<td>{R[(sc.name, 2031)].primary_balance_pct:+.1f}</td><td>{R[(sc.name, 2035)].primary_balance_pct:+.1f}</td></tr>")
        notes.append(f"<tr><td class='l'>{sc.label}</td><td class='l'>{sc.note}</td></tr>")
    V["assumption_rows"] = "\n".join(rows)
    V["assumption_notes"] = "\n".join(notes)

    # the statistical benchmark, year by year: what the engine takes from it
    bb = pd.read_csv(sim.DELIV / "benchmark_balance.csv", low_memory=False).query("iso3 == 'FRA'")
    nlb = bb[bb.kind == "balance"].set_index("year")
    gi = bb[(bb.kind == "line") & (bb.line_code == "GF01_7")].set_index("year").pct_gdp
    dpp = sim.benchmark_pb_changes(first=2026)
    rows = []
    for y in nlb.index:
        pbv = nlb.pct_gdp[y] + gi[y] - b.interest_receivable_pct
        used = 2028 <= y
        d = f"{dpp[y]:+.2f}" if y in dpp else "–"
        eng = f"{R[('statistical', y)].primary_balance_pct:+.1f}" if ("statistical", y) in R else "–"
        rows.append(f"<tr{' class=hl' if used else ''}><td class='l'>{y}</td><td>{-nlb.pct_gdp[y]:.1f}</td>"
                    f"<td>{-nlb.hi80[y]:.1f} to {-nlb.lo80[y]:.1f}</td><td>{gi[y]:.1f}</td><td>{pbv:+.1f}</td>"
                    f"<td>{d}</td><td>{'yes' if used else 'no'}</td><td>{eng}</td></tr>")
    V["benchmark_rows"] = "\n".join(rows)
    V["benchmark_run"] = str(bb.run_id.iloc[0])
    V["benchmark_base_year"] = str(int(bb.base_year.iloc[0]))
    V["stat_2031_pb_bn"] = f"{R[('statistical', 2031)].primary_balance_bn:,.0f}"

    return V


def fill(html: str, V: dict, inline: bool, figures: bool = True) -> str:
    """Substitute the figures (by path, or embedded as data URIs) and the
    values. With figures=False the {{fig:key}} markers are left in place."""
    def img(m):
        key = m.group(1)
        path = FIG / f"{key}.png"
        if not path.exists():
            raise SystemExit(f"missing figure {path}")
        if inline:
            b64 = base64.b64encode(path.read_bytes()).decode()
            return f'<img src="data:image/png;base64,{b64}" alt="{key}" loading="lazy">'
        return f'<img src="figures/{key}.png" alt="{key}" loading="lazy">'
    if figures:
        html = re.sub(r"\{\{fig:([a-z_0-9]+)\}\}", img, html)

    def var(m):
        key = m.group(1)
        if key.startswith("fig:"):
            return m.group(0)
        if key not in V:
            raise SystemExit(f"unfilled placeholder {{{{{key}}}}}")
        return str(V[key])
    return re.sub(r"\{\{([^{}]+)\}\}", var, html)


def main() -> Path:
    tpl, V = template(), values()
    (OUT / "briefing.html").write_text(fill(tpl, V, inline=False))
    inline = OUT / "briefing_inline.html"
    inline.write_text(fill(tpl, V, inline=True))
    print(f"wrote {OUT / 'briefing.html'} and {inline} ({inline.stat().st_size / 1e6:.2f} MB)")
    return inline


if __name__ == "__main__":
    main()
