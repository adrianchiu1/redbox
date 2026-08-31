"""Gate 5 report: reconciliation_report.html — stacked-contribution charts
per country with the WEO balance path overlaid (history and forecast, strict
and maximum), residuals shaded (§10 Reports), plus the explained-share
summary, the §8.4 net-interest cross-check and the §8.5 residual history.

Same conventions as the Stage 1 report: plotly, one HTML, plotly.js from CDN."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from ggfiscal import config
from ggfiscal.ingest.endpoints import WEO_VINTAGES

# residual/denominator components render in greys so the covered-line story
# stays in colour ("residuals shaded", §10)
RESID_COLORS = {
    "resid_coverage": "#9e9e9e",
    "resid_disagreement": "#616161",
    "resid_total": "#757575",
    "denom_effect": "#bdbdbd",
    "weo_internal_wedge": "#e0e0e0",
}
LINE_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
               "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f"]


def _canonical(name: str) -> pd.DataFrame:
    return pd.read_csv(config.repo_root() / "data" / "canonical" / f"{name}.csv")


def _history_fig(iso3: str, variant: str) -> go.Figure:
    dyn = _canonical("deficit_dynamics")
    g = dyn[(dyn.iso3 == iso3) & (dyn.series_variant == variant)]
    lines = g[g.kind.isin(["revenue", "expenditure"])]
    top = (lines.groupby("line_code").contribution_pp
           .apply(lambda s: s.abs().mean()).nlargest(8).index)
    fig = go.Figure()
    for i, code in enumerate(top):
        sub = lines[lines.line_code == code]
        fig.add_trace(go.Bar(x=sub.year, y=sub.contribution_pp, name=code,
                             marker_color=LINE_COLORS[i % len(LINE_COLORS)]))
    other = (lines[~lines.line_code.isin(top)]
             .groupby("year").contribution_pp.sum())
    fig.add_trace(go.Bar(x=other.index, y=other.values, name="other lines",
                         marker_color="#c7c7c7"))
    total = g[g.line_code == "NLB_CHANGE_SUM"]
    fig.add_trace(go.Scatter(x=total.year, y=total.contribution_pp,
                             mode="lines+markers", name="Δ(NLB/GDP)",
                             line={"color": "black", "width": 2}))
    weo = g[g.line_code == "WEO_GGXCNL_DELTA"]
    fig.add_trace(go.Scatter(x=weo.year, y=weo.contribution_pp,
                             mode="lines", name="WEO Δ(GGXCNL/NGDP)",
                             line={"color": "black", "width": 1, "dash": "dot"}))
    fig.update_layout(barmode="relative", title=f"{iso3} — history ({variant}): "
                      "drivers of the change in the balance ratio (pp of GDP)",
                      height=420, legend={"orientation": "h", "y": -0.2})
    return fig


def _forecast_fig(iso3: str, variant: str, vintage: str) -> go.Figure | None:
    exp = _canonical("weo_explanation")
    g = exp[(exp.iso3 == iso3) & (exp.series_variant == variant)
            & (exp.weo_vintage == vintage)]
    if g.empty:
        return None
    fig = go.Figure()
    cov = g[g.component_kind == "covered_line"]
    for i, code in enumerate(sorted(cov.line_code.dropna().unique())):
        sub = cov[cov.line_code == code]
        fig.add_trace(go.Bar(x=sub.horizon_year, y=sub.contribution_pp,
                             name=code,
                             marker_color=LINE_COLORS[i % len(LINE_COLORS)]))
    for kind, color in RESID_COLORS.items():
        sub = g[g.component_kind == kind]
        if sub.empty:
            continue
        agg = sub.groupby("horizon_year").contribution_pp.sum()
        fig.add_trace(go.Bar(x=agg.index, y=agg.values, name=kind,
                             marker_color=color))
    target = g[g.component_kind == "weo_change"]
    fig.add_trace(go.Scatter(x=target.horizon_year, y=target.contribution_pp,
                             mode="lines+markers",
                             name="WEO Δ balance from base",
                             line={"color": "black", "width": 2}))
    b = int(g.base_year.iloc[0])
    fig.update_layout(barmode="relative",
                      title=f"{iso3} — forecast ({variant}, WEO {vintage}, "
                            f"base {b}): components of the WEO balance change "
                            "(pp of WEO GDP; residuals in grey)",
                      height=420, legend={"orientation": "h", "y": -0.25})
    return fig


def _explained_table(vintage: str) -> str:
    exp = _canonical("weo_explanation")
    es = exp[(exp.component_kind == "explained_share")
             & (exp.weo_vintage == vintage)]
    piv = es.pivot_table(index="horizon_year", columns=["iso3", "series_variant"],
                         values="contribution_pp")
    piv.columns = [f"{a}/{'strict' if b == 'strict' else 'max'}"
                   for a, b in piv.columns]
    return piv.round(3).to_html(border=0, na_rep="—")


def _ni_table(vintage: str) -> str:
    ni = _canonical("net_interest_check")
    g = ni[(ni.weo_vintage == vintage) & (ni.series_variant == "strict")]
    cols = ["iso3", "horizon_year", "ni_weo_mn", "gf01_7_mn", "r07_mn",
            "ni_ours_mn", "gap_mn", "notes"]
    return g[cols].round(1).to_html(border=0, index=False, na_rep="—")


def _residual_history_table() -> str:
    rh = _canonical("weo_residual_history")
    g = rh[rh.residual_kind.isin(["resid_disagreement", "resid_total"])]
    piv = g.pivot_table(index=["iso3", "side", "horizon_year"],
                        columns="weo_vintage", values="contribution_pp",
                        aggfunc="first")
    return piv.round(3).to_html(border=0, na_rep="—")


def write(path: Path | None = None) -> Path:
    dest = path or config.repo_root() / "reports" / "reconciliation_report.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    latest = next(iter(WEO_VINTAGES))
    parts = [
        "<html><head><meta charset='utf-8'><title>gg-fiscal reconciliation "
        "report (Stage 5)</title></head><body>",
        "<h1>Reconciliation report — §8.2–8.5</h1>",
        f"<p>Latest WEO vintage: <b>{latest}</b>. Charts follow §10: stacked "
        "contributions per country, WEO balance path overlaid, residuals in "
        "grey — the residuals are reported, never allocated (D16, §8.6).</p>",
        "<h2>How much of each WEO balance change the granular official "
        "forecasts explain</h2>",
        "<p>explained_share = covered-line contributions / WEO change "
        f"(vintage {latest}; a negative or &gt;1 share means the covered "
        "lines move against or beyond the WEO path):</p>",
        _explained_table(latest),
    ]
    include = "cdn"
    for iso3 in config.COUNTRIES:
        parts.append(f"<h2>{iso3}</h2>")
        for variant in ("strict", "maximum_extension"):
            fig = _history_fig(iso3, variant)
            parts.append(fig.to_html(full_html=False, include_plotlyjs=include))
            include = False
            ffig = _forecast_fig(iso3, variant, latest)
            if ffig is not None:
                parts.append(ffig.to_html(full_html=False, include_plotlyjs=False))
    parts += [
        "<h2>Net-interest cross-check (§8.4, strict)</h2>", _ni_table(latest),
        "<h2>Residual history across WEO vintages (§8.5)</h2>",
        "<p>resid_disagreement (resid_total where no independent official "
        "total exists), pp of WEO GDP:</p>",
        _residual_history_table(),
        "</body></html>",
    ]
    dest.write_text("\n".join(parts), encoding="utf-8")
    return dest
