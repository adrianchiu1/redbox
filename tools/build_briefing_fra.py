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


def main() -> Path:
    tpl = (OUT / "briefing_template.html").read_text()
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
    short = {"current": "cur", "philippe_majority": "pm", "philippe_hung": "ph",
             "lepen_majority": "lp", "lepen_hung": "lph", "lepen_rupture": "rup"}
    for name, s in short.items():
        for y in (2027, 2028, 2030, 2032, 2035):
            r = R[(name, y)]
            V[f"{s}_{y}_bn"] = f"{r.gg_interest_bn:,.0f}"
            V[f"{s}_{y}_pct"] = f"{r.gg_interest_pct_gdp:.1f}"
            V[f"{s}_{y}_debt"] = f"{r.debt_pct_gdp:.0f}"
            V[f"{s}_{y}_deficit"] = f"{r.deficit_pct_gdp:.1f}"
        for y in (2030, 2035):
            if (name, y) in D:
                d = D[(name, y)]
                V[f"{s}_{y}_gap"] = f"{d.gap_bn:,.0f}"
                V[f"{s}_{y}_gap_abs"] = f"{abs(d.gap_bn):,.0f}"
                V[f"{s}_{y}_spread"] = f"{d.spread_effect_bn:,.0f}"
                V[f"{s}_{y}_volume"] = f"{d.volume_effect_bn:,.0f}"
                V[f"{s}_{y}_interaction"] = f"{d.interaction_bn:,.1f}"
                V[f"{s}_{y}_interaction_round"] = f"{math.ceil(d.interaction_bn):,.0f}"

    # engine summaries
    ds = sim.duration_summary(90.0)
    V["dur_mod"] = f"{ds['modified_duration_years']:.1f}"
    V["dur_loss100"] = f"{ds['loss_per_100bp_bn']:,.0f}"
    V["dur_loss100_pct"] = f"{ds['loss_per_100bp_pct_gdp']:.1f}"
    V["dur_mv"] = f"{ds['market_value_bn']:,.0f}"
    V["dur_nom"] = f"{ds['nominal_bn']:,.0f}"
    cal = sim.calibration()
    V["cal_wedge"] = f"{cal['wedge_2025_bn']:.1f}"
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
        cls = " class='hl'" if sc.name == "current" else ""
        rows.append(f"<tr{cls}><td class='l'>{sc.label}</td><td>{r30.spread_bp:.0f}</td><td>{r30.oat_10y_pct:.1f}%</td>"
                    f"<td>{r28.gg_interest_bn:,.0f}</td><td>{r30.gg_interest_bn:,.0f}</td><td>{r30.gg_interest_pct_gdp:.1f}</td>"
                    f"<td>{r35.gg_interest_bn:,.0f}</td><td>{r35.gg_interest_pct_gdp:.1f}</td><td>{r30.deficit_pct_gdp:.1f}</td>"
                    f"<td>{r30.debt_pct_gdp:.0f}</td><td>{r35.debt_pct_gdp:.0f}</td><td>{r30.mlt_gross_issuance_bn:,.0f}</td></tr>")
    V["scenario_rows"] = "\n".join(rows)

    # assumptions table
    def dpath(d, unit=""):
        return ", ".join(f"{y} {v:+.1f}{unit}" if isinstance(v, float) and unit == "" else f"{y} {v:g}{unit}" for y, v in sorted(d.items()))
    rows = []
    for sc in sim.SCENARIOS:
        r = R[(sc.name, 2030)]
        rows.append(f"<tr><td class='l'>{sc.label}</td><td class='l'>{dpath(sc.pb_deviation)}</td><td class='l'>{dpath(sc.spread_bp)}</td>"
                    f"<td class='l'>{dpath(sc.btf_stock)}</td><td>{sc.maturity_tilt:.2f}</td><td>{r.mlt_avg_maturity_at_issue:.1f}y</td><td class='l'>{sc.note}</td></tr>")
    V["assumption_rows"] = "\n".join(rows)

    def fill(html: str, inline: bool) -> str:
        def img(m):
            key = m.group(1)
            path = FIG / f"{key}.png"
            if not path.exists():
                raise SystemExit(f"missing figure {path}")
            if inline:
                b64 = base64.b64encode(path.read_bytes()).decode()
                return f'<img src="data:image/png;base64,{b64}" alt="{key}" loading="lazy">'
            return f'<img src="figures/{key}.png" alt="{key}" loading="lazy">'
        html = re.sub(r"\{\{fig:([a-z_0-9]+)\}\}", img, html)

        def var(m):
            key = m.group(1)
            if key not in V:
                raise SystemExit(f"unfilled placeholder {{{{{key}}}}}")
            return str(V[key])
        html = re.sub(r"\{\{([^{}]+)\}\}", var, html)
        return html

    (OUT / "briefing.html").write_text(fill(tpl, inline=False))
    inline = OUT / "briefing_inline.html"
    inline.write_text(fill(tpl, inline=True))
    print(f"wrote {OUT / 'briefing.html'} and {inline} ({inline.stat().st_size / 1e6:.2f} MB)")
    return inline


if __name__ == "__main__":
    main()
