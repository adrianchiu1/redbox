"""Gate 1 report: small multiples — 22 lines x 3 countries plus the balance
ledger, strict variant, anchor history. Plotly, one self-contained HTML
(plotly.js from CDN to keep the file reviewable in git)."""

from __future__ import annotations

from pathlib import Path

from plotly.subplots import make_subplots
import plotly.graph_objects as go

from ggfiscal import config

LINE_ORDER = (["GF%02d" % n for n in range(1, 11)] + ["GF01_7", "GF01_X"]
              + ["R%02d" % n for n in range(1, 11)])


def write(path: Path | None = None, variant: str = "strict") -> Path:
    from ggfiscal.build import load_canonical, load_ledger

    dest = path or config.repo_root() / "reports" / "small_multiples_stage1.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df = load_canonical("COFOG", variant)
    df = df.set_index(["iso3", "line_code"]).sort_index()
    rv = load_canonical("ESA_REV", variant).set_index(["iso3", "line_code"]).sort_index()
    led = load_ledger()
    led = led[led.series_variant == variant]

    n_rows = len(LINE_ORDER) + 1  # + ledger row
    fig = make_subplots(rows=n_rows, cols=3,
                        column_titles=list(config.COUNTRIES),
                        row_titles=LINE_ORDER + ["NLB"],
                        shared_xaxes=False, vertical_spacing=0.004)
    for col, iso3 in enumerate(config.COUNTRIES, start=1):
        for row, code in enumerate(LINE_ORDER, start=1):
            table = df if code.startswith("GF") else rv
            try:
                sub = table.loc[(iso3, code)].sort_values("year")
            except KeyError:
                continue
            fig.add_trace(go.Scatter(x=sub.year, y=sub.pct_gdp, mode="lines",
                                     line={"width": 1}, showlegend=False,
                                     name=f"{iso3} {code}"), row=row, col=col)
        sub = led[led.iso3 == iso3].sort_values("year")
        gdp = df.loc[(iso3, "GF01")].set_index("year").gdp_lcu_mn
        years = [y for y in sub.year if y in gdp.index]
        nlb = [float(sub[sub.year == y].nlb_lcu_mn.iloc[0]) / gdp[y] * 100
               for y in years]
        fig.add_trace(go.Scatter(x=years, y=nlb, mode="lines",
                                 line={"width": 1}, showlegend=False,
                                 name=f"{iso3} NLB"), row=n_rows, col=col)
    fig.update_layout(height=110 * n_rows, width=1100,
                      title=f"gg-fiscal Stage 1 — anchor history, % of GDP ({variant})",
                      margin={"l": 40, "r": 90, "t": 60, "b": 20})
    fig.update_annotations(font_size=9)
    fig.update_xaxes(tickfont_size=7)
    fig.update_yaxes(tickfont_size=7)
    fig.write_html(dest, include_plotlyjs="cdn")
    return dest
