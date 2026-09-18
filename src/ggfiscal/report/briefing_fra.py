"""Briefing note charts for France, AFT snapshot 2026-09.

Reads only the flat files in ``deliverables/`` (no ggfiscal ingest/build
pipeline) and renders a set of PNG charts plus a ``key_figures.csv`` summary
for the briefing note ``reports/briefing_FRA_AFT_2026-09``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

ROOT = next(p for p in [Path(__file__).resolve(), *Path(__file__).resolve().parents]
            if (p / "deliverables" / "debt_reference_series.csv").exists())
DELIV = ROOT / "deliverables"

ISO3 = "FRA"

# ---------------------------------------------------------------------------
# Palette / rcParams — copied from notebooks/debtbook.ipynb setup cell so the
# briefing charts match the rest of the chartbook.
# ---------------------------------------------------------------------------
BLUE, ORANGE, GREEN, PURPLE, RED, TEAL, BROWN, GOLD = (
    "#2a78d6", "#eb6834", "#1baf7a", "#8456ce",
    "#d64550", "#2ba8a0", "#a8763e", "#d1a62b",
)
INK, MUTED, AXIS = "#0b0b0b", "#898781", "#c3c2b7"
SURFACE, SHADE = "#fcfcfb", "#eceae4"

CLASS_COLOR = {
    "fixed_bullet": BLUE, "bill": ORANGE, "inflation_linked": GREEN,
    "floating": PURPLE, "other": BROWN, "mixed": TEAL,
}
CLASS_LABEL = {
    "fixed_bullet": "Fixed-rate (OAT/BTAN)", "bill": "Bills (BTF)",
    "inflation_linked": "Inflation-linked (OATi/OAT€i)",
}

BUCKET_ORDER = ["0-1", "1-2", "2-3", "3-5", "5-7", "7-10", "10-15", "15-20",
                "20-30", "30+"]

plt.rcParams.update({
    "figure.figsize": (7.2, 3.3), "figure.dpi": 120,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK, "axes.titlecolor": INK,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 9, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "grid.color": AXIS, "grid.alpha": 0.45, "grid.linewidth": 0.6,
    "legend.frameon": False, "legend.fontsize": 8.5,
    "lines.linewidth": 1.8,
})

SNAPSHOT = "2026-09-10"


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------
def _load(name: str) -> pd.DataFrame:
    return pd.read_csv(DELIV / f"{name}.csv", low_memory=False)


def _thousands(ax, axis: str = "y") -> None:
    getattr(ax, f"{axis}axis").set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))


def _source(fig, text: str) -> None:
    fig.text(0.0, -0.04, f"Source: {text}", fontsize=7, color=MUTED, ha="left")


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


def _positions_fra() -> pd.DataFrame:
    pos = _load("debt_positions")
    pos = pos[pos.iso3 == ISO3].copy()
    sec = _load("debt_securities")
    sec = sec[sec.iso3 == ISO3][["security_id", "instrument_class", "sub_type",
                                  "maturity_date", "coupon_pct"]]
    return pos.merge(sec, on="security_id", how="left")


def _uplifted_or_nominal(df: pd.DataFrame) -> pd.Series:
    up = df["nominal_uplifted_lcu_mn"].fillna(0.0)
    nom = df["nominal_lcu_mn"].fillna(0.0)
    return np.where(up > 0, up, nom)


def _weighted_avg(values: pd.Series, weights: pd.Series) -> float:
    w = weights.sum()
    return float((values * weights).sum() / w) if w else float("nan")


def _annual_mean(series_id: str) -> pd.Series:
    ref = _load("debt_reference_series")
    sub = ref[ref.series_id == series_id].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    sub["year"] = sub["date"].dt.year
    return sub.groupby("year")["value"].mean()


def _monthly(series_id: str) -> pd.DataFrame:
    ref = _load("debt_reference_series")
    sub = ref[ref.series_id == series_id].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    return sub.sort_values("date")[["date", "value"]]


# ---------------------------------------------------------------------------
# 1. interest_gg
# ---------------------------------------------------------------------------
def _chart_interest_gg(out: Path) -> Path:
    df = _load("expenditure_cofog")
    fra = df[(df.iso3 == ISO3) & (df.variant == "strict")
             & (df.line_code == "GF01_7")].sort_values("year")
    fra = fra[fra.year <= 2036]
    outturn = fra[fra.year <= 2024]
    proj = fra[fra.year >= 2024]  # includes 2024 so the dashed line connects

    fig, ax = plt.subplots()
    ax.axvspan(2025, fra.year.max() + 0.3, color=SHADE, zorder=0)
    ax.plot(outturn.year, outturn.pct_gdp, color=BLUE, solid_capstyle="round",
            label="Outturn (EUROSTAT / stitched AMECO)")
    ax.plot(proj.year, proj.pct_gdp, color=BLUE, linestyle="--",
            label="Projection (AMECO 2026-27, DSM 2028-36)")

    for y in (2024, 2027, 2031, 2036):
        row = fra[fra.year == y]
        if row.empty:
            continue
        pct = float(row.pct_gdp.iloc[0])
        bn = float(row.value_lcu_mn.iloc[0]) / 1000
        ax.annotate(f"{pct:.1f}%\n€{bn:,.0f}bn", (y, pct),
                    textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=7.5, color=INK)
        ax.plot([y], [pct], marker="o", color=BLUE, ms=3.5, zorder=5)

    ax.set_ylabel("% of GDP")
    ax.set_ylim(0, fra.pct_gdp.max() * 1.25)
    ax.set_title("France · general-government interest (COFOG 01.7), % of GDP")
    ax.legend(loc="upper left")
    _source(fig, "deliverables/expenditure_cofog.csv (anchor EUROSTAT_GOV10A_EXP to "
                  "2024; stitched/forecast EC_AMECO 1978-94 & 2025-27, EC_DSM 2028-36)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 2. ledger
# ---------------------------------------------------------------------------
def _chart_ledger(out: Path) -> Path:
    df = _load("balance_ledger")
    fra = df[(df.iso3 == ISO3) & (df.variant == "strict")].sort_values("year")

    fig, ax = plt.subplots()
    ax.axhline(0, color=AXIS, linewidth=0.8)
    ax.axhline(-3, color=RED, linewidth=1.0, linestyle=":", zorder=1)
    ax.text(fra.year.min() + 0.3, -3, "Maastricht -3%", color=RED, fontsize=7.5,
            va="bottom")
    ax.plot(fra.year, fra.nlb_pct_gdp, color=BLUE, label="Net lending/borrowing (NLB)")
    ax.plot(fra.year, fra.pb_pct_gdp, color=ORANGE, label="Primary balance (PB)")
    ax.plot(fra.year, fra.ni_pct_gdp, color=GREEN, label="Net interest (NI)")
    ax.set_ylabel("% of GDP")
    ax.set_title("France · fiscal balance, primary balance and net interest")
    ax.legend(loc="lower left", ncol=3)
    _source(fig, "deliverables/balance_ledger.csv (EUROSTAT_GOV10A_MAIN, strict variant)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 3. stock_by_class
# ---------------------------------------------------------------------------
def _chart_stock_by_class(out: Path) -> Path:
    pos = _positions_fra()
    pos = pos[pos.as_of.str.endswith("-12-31")].copy()
    pos["year"] = pos.as_of.str[:4].astype(int)
    by_class = (pos.groupby(["year", "instrument_class"]).nominal_lcu_mn.sum()
                .unstack(fill_value=0.0) / 1000)
    classes = [c for c in ("bill", "fixed_bullet", "inflation_linked") if c in by_class]

    ca = _load("debt_class_aggregates")
    fra_ca = ca[(ca.iso3 == ISO3) & (ca.measure == "stock_year_end")]
    aft_total = (fra_ca[fra_ca.sub_type == "dette_negociable_total"]
                 .groupby("year").value_lcu_mn.sum() / 1000)
    eurostat_total = (fra_ca[fra_ca.sub_type.isin(
        ["f31_short_term_securities", "f32_long_term_securities"])]
        .groupby("year").value_lcu_mn.sum() / 1000)

    fig, ax = plt.subplots()
    bottom = np.zeros(len(by_class))
    for c in classes:
        ax.bar(by_class.index, by_class[c], bottom=bottom, color=CLASS_COLOR[c],
               width=0.75, label=CLASS_LABEL[c])
        bottom += by_class[c].to_numpy()
    ax.plot(aft_total.index, aft_total.values, color=INK, marker="o", ms=2.5,
            label="AFT détte négociable (total)")
    ax.plot(eurostat_total.index, eurostat_total.values, color=MUTED, linestyle="--",
            label="Eurostat F.31+F.32, S.1311")
    ax.set_ylabel("EUR bn")
    _thousands(ax)
    ax.set_title("France · negotiable debt in the register vs the AFT and Eurostat totals")
    ax.legend(loc="upper left", fontsize=7.5, ncol=1)
    _source(fig, "deliverables/debt_positions.csv + debt_securities.csv (register) vs "
                  "debt_class_aggregates.csv (AFT/INSEE, Eurostat gov_10q_ggdebt)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 4. maturity_profile
# ---------------------------------------------------------------------------
def _maturity_snapshot() -> pd.DataFrame:
    mp = _load("debt_maturity_profile")
    return mp[(mp.iso3 == ISO3) & (mp.as_of == SNAPSHOT)]


def _chart_maturity_profile(out: Path) -> Path:
    mp = _maturity_snapshot()
    pivot = (mp.groupby(["bucket", "instrument_class"]).nominal_lcu_mn.sum()
             .unstack(fill_value=0.0) / 1000).reindex(BUCKET_ORDER).fillna(0.0)
    classes = [c for c in ("bill", "fixed_bullet", "inflation_linked") if c in pivot]

    total = pivot.values.sum()
    short = pivot.loc[["0-1", "1-2", "2-3"]].values.sum()

    fig, ax = plt.subplots()
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))
    for c in classes:
        ax.bar(x, pivot[c], bottom=bottom, color=CLASS_COLOR[c], width=0.7,
               label=CLASS_LABEL[c])
        bottom += pivot[c].to_numpy()
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index)
    ax.set_xlabel("Residual maturity bucket (years)")
    ax.set_ylabel("EUR bn")
    _thousands(ax)
    ax.set_title("France · maturity profile of the register at 10 Sep 2026")
    ax.text(0.99, 0.95, f"Total stock: €{total:,.0f}bn\n0-3y share: {short / total:.0%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color=INK)
    ax.legend(loc="upper left")
    _source(fig, "deliverables/debt_maturity_profile.csv (register, as_of 2026-09-10; "
                  "linkers at unindexed nominal)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 5. redemption_calendar
# ---------------------------------------------------------------------------
def _redemption_by_year() -> pd.Series:
    pos = _positions_fra()
    snap = pos[pos.as_of == SNAPSHOT].copy()
    snap["maturity_year"] = pd.to_datetime(snap.maturity_date).dt.year
    return snap


def _chart_redemption_calendar(out: Path) -> Path:
    snap = _redemption_by_year()
    snap["bucket_year"] = np.where(snap.maturity_year >= 2046, 2046, snap.maturity_year)
    snap = snap[(snap.bucket_year >= 2026)]
    pivot = (snap.groupby(["bucket_year", "instrument_class"]).nominal_lcu_mn.sum()
             .unstack(fill_value=0.0) / 1000)
    years = list(range(2026, 2047))
    pivot = pivot.reindex(years, fill_value=0.0)
    classes = [c for c in ("bill", "fixed_bullet", "inflation_linked") if c in pivot]
    labels = [str(y) if y < 2046 else "2046+" for y in years]

    fig, ax = plt.subplots()
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))
    for c in classes:
        ax.bar(x, pivot[c], bottom=bottom, color=CLASS_COLOR[c], width=0.75,
               label=CLASS_LABEL[c])
        bottom += pivot[c].to_numpy()
    ax.set_xticks(x[::2])
    ax.set_xticklabels([labels[i] for i in range(0, len(labels), 2)], rotation=0)
    ax.set_ylabel("EUR bn")
    _thousands(ax)
    near = pivot.loc[[y for y in (2026, 2027, 2028) if y in pivot.index]].values.sum()
    ax.text(0.99, 0.95, f"2026-28 redemptions: €{near:,.0f}bn",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color=INK)
    ax.set_title("France · redemption calendar of the register at 10 Sep 2026")
    ax.legend(loc="center", bbox_to_anchor=(0.72, 0.42))
    _source(fig, "deliverables/debt_positions.csv + debt_securities.csv "
                  "(register, as_of 2026-09-10, by maturity_date)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 6. maturity_trend
# ---------------------------------------------------------------------------
def _chart_maturity_trend(out: Path) -> Path:
    mp = _load("debt_maturity_profile")
    fra = mp[(mp.iso3 == ISO3) & (mp.as_of.str.endswith("-12-31"))].copy()
    fra["year"] = fra.as_of.str[:4].astype(int)

    all_by_year = fra.groupby("year").apply(
        lambda d: _weighted_avg(d.weighted_residual_years, d.nominal_lcu_mn),
        include_groups=False)
    fixed_by_year = (fra[fra.instrument_class == "fixed_bullet"].groupby("year")
                      .apply(lambda d: _weighted_avg(d.weighted_residual_years,
                                                       d.nominal_lcu_mn),
                             include_groups=False))
    stock_by_year = fra.groupby("year").nominal_lcu_mn.sum()
    bill_share = (fra[fra.instrument_class == "bill"].groupby("year").nominal_lcu_mn.sum()
                  / stock_by_year * 100)

    ib = _load("debt_issuance_by_bucket")
    fixed_iss = ib[(ib.iso3 == ISO3) & (ib.instrument_class == "fixed_bullet")]
    gross_by_year = fixed_iss.groupby("year").gross_nominal_lcu_mn.sum() / 1000
    mat_at_issue = fixed_iss.groupby("year").apply(
        lambda d: _weighted_avg(d.weighted_residual_years_at_issue,
                                 d.gross_nominal_lcu_mn),
        include_groups=False)

    fig, (axl, axr) = plt.subplots(1, 2, figsize=(11, 3.3))

    axl.plot(all_by_year.index, all_by_year.values, color=BLUE, label="Whole stock")
    axl.plot(fixed_by_year.index, fixed_by_year.values, color=PURPLE,
             label="Fixed-rate only")
    axl.set_ylabel("Weighted avg residual maturity (years)")
    axl2 = axl.twinx()
    axl2.plot(bill_share.index, bill_share.values, color=ORANGE, linestyle="--",
              linewidth=1.4, label="Bill share of stock (rhs)")
    axl2.set_ylabel("Bill share (%)", color=ORANGE)
    axl2.tick_params(axis="y", colors=ORANGE)
    axl2.grid(False)
    axl2.spines["right"].set_visible(True)
    axl2.spines["right"].set_color(ORANGE)
    h1, l1 = axl.get_legend_handles_labels()
    h2, l2 = axl2.get_legend_handles_labels()
    axl.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=7.5)
    axl.set_title("Register stock · average residual maturity")

    axr.bar(gross_by_year.index, gross_by_year.values, color=BLUE, width=0.75,
            label="Gross issuance (lhs)")
    axr.set_ylabel("EUR bn")
    _thousands(axr)
    axr2 = axr.twinx()
    axr2.plot(mat_at_issue.index, mat_at_issue.values, color=INK, marker="o", ms=2.5,
              label="Avg maturity at issue (rhs)")
    axr2.set_ylabel("Years", color=INK)
    axr2.grid(False)
    h1, l1 = axr.get_legend_handles_labels()
    h2, l2 = axr2.get_legend_handles_labels()
    axr.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=7.5)
    axr.set_title("Fixed-rate issuance · maturity at issue")

    fig.suptitle("France · debt maturity trend, 1999-2026", x=0.01, ha="left",
                 fontsize=10.5, fontweight="bold", y=1.03)
    fig.subplots_adjust(wspace=0.42)
    _source(fig, "deliverables/debt_maturity_profile.csv & debt_issuance_by_bucket.csv "
                  "(register)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 7. coupon_vs_yield
# ---------------------------------------------------------------------------
def _chart_coupon_vs_yield(out: Path) -> Path:
    pos = _positions_fra()
    fixed = pos[pos.instrument_class == "fixed_bullet"].copy()
    dated = fixed[fixed.as_of.str.endswith("-12-31")].copy()
    dated["year"] = dated.as_of.str[:4].astype(float)
    avg_coupon = dated.groupby("year").apply(
        lambda d: _weighted_avg(d.coupon_pct.fillna(0.0), d.nominal_lcu_mn),
        include_groups=False)
    snap = fixed[fixed.as_of == SNAPSHOT]
    snap_year = 2026 + (9 / 12)
    snap_coupon = _weighted_avg(snap.coupon_pct.fillna(0.0), snap.nominal_lcu_mn)

    fr10 = _annual_mean("FR_LT10")
    ea3m = _annual_mean("EA_MM_3M")

    fig, ax = plt.subplots()
    ax.plot(avg_coupon.index, avg_coupon.values, color=BLUE, marker="o", ms=2.5,
            label="Avg coupon, fixed-rate stock")
    ax.plot([avg_coupon.index.max(), snap_year], [avg_coupon.values[-1], snap_coupon],
            color=BLUE, linestyle=":")
    ax.plot([snap_year], [snap_coupon], color=BLUE, marker="D", ms=4, zorder=5)
    years = [y for y in fr10.index if 1999 <= y <= 2026]
    ax.plot(years, [fr10[y] for y in years], color=ORANGE, label="FR 10y yield (avg)")
    years3m = [y for y in ea3m.index if 1999 <= y <= 2026]
    ax.plot(years3m, [ea3m[y] for y in years3m], color=MUTED, linestyle="--",
            label="EA 3m money-market rate (avg)")
    ax.set_ylabel("% p.a.")
    ax.set_title("France · average coupon on the fixed-rate stock vs the marginal "
                 "10-year yield")
    ax.legend(loc="upper right")
    _source(fig, "deliverables/debt_positions.csv + debt_securities.csv (register) vs "
                  "debt_reference_series.csv (OECD FR_LT10, EA_MM_3M)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 8. interest_by_security
# ---------------------------------------------------------------------------
def _chart_interest_by_security(out: Path) -> Path:
    ii = _load("debt_interest_by_security")
    fra = ii[(ii.iso3 == ISO3) & (ii.basis == "cash") & (ii.year.between(2000, 2026))]
    sec = _load("debt_securities")
    sec = sec[sec.iso3 == ISO3][["security_id", "instrument_class"]]
    fra = fra.merge(sec, on="security_id", how="left")
    pivot = (fra.groupby(["year", "instrument_class"]).total_lcu_mn.sum()
             .unstack(fill_value=0.0) / 1000)
    classes = [c for c in ("bill", "fixed_bullet", "inflation_linked") if c in pivot]

    ot = _load("debt_official_totals")
    fra_ot = ot[(ot.iso3 == ISO3) & (ot.chain == "interest")
                & (ot.year.between(2000, 2026))]
    step_b = fra_ot[fra_ot.step == "B_s1311_d41"].set_index("year").value_lcu_mn / 1000
    step_c = fra_ot[fra_ot.step == "C_s13_gf01_7"].set_index("year").value_lcu_mn / 1000

    fig, ax = plt.subplots()
    ax.axvspan(2025.5, 2026.5, color=SHADE, zorder=0)
    bottom = np.zeros(len(pivot))
    for c in classes:
        ax.bar(pivot.index, pivot[c], bottom=bottom, color=CLASS_COLOR[c], width=0.75,
               label=CLASS_LABEL[c])
        bottom += pivot[c].to_numpy()
    ax.plot(step_b.index, step_b.values, color=INK, label="B · S.1311 D.41")
    ax.plot(step_c.index, step_c.values, color=MUTED, linestyle="--",
            label="C · GF01_7 (S.13)")
    ax.set_ylabel("EUR bn")
    _thousands(ax)
    ax.set_title("France · cash interest by security class vs official aggregates")
    ax.legend(loc="upper left", fontsize=7.5)
    ax.annotate("2026: register only\n(existing positions)", xy=(2026, ax.get_ylim()[1] * 0.9),
                fontsize=7, color=MUTED, ha="center")
    _source(fig, "deliverables/debt_interest_by_security.csv (register, cash basis) vs "
                  "debt_official_totals.csv (EUROSTAT S.1311 D.41 / S.13 GF01_7)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 9. oat_bund_spread
# ---------------------------------------------------------------------------
def _chart_oat_bund_spread(out: Path) -> Path:
    fr = _monthly("FR_LT10")
    de = _monthly("DE_LT10")
    merged = fr.merge(de, on="date", suffixes=("_fr", "_de"))
    merged = merged[(merged.date.dt.year >= 1999) & (merged.date.dt.year <= 2026)]
    spread = (merged.value_fr - merged.value_de) * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.2, 4.2), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    ax1.plot(merged.date, spread, color=BLUE, linewidth=1.4)
    ax1.set_ylabel("OAT-Bund spread (bp)")
    ax1.set_title("France · OAT-Bund 10-year spread")

    events = [
        ("2011-11-01", "euro crisis"),
        ("2017-04-01", "presidential"),
        ("2024-06-01", "dissolution"),
        ("2025-09-01", "Bayrou falls"),
    ]
    ymax = spread.max()
    for date_str, label in events:
        d = pd.Timestamp(date_str)
        row = merged[merged.date == d]
        y = float(spread[merged.date == d].iloc[0]) if not row.empty else np.nan
        ax1.axvline(d, color=MUTED, linewidth=0.6, linestyle=":")
        ax1.annotate(label, xy=(d, ymax * 0.92), fontsize=6.8, color=INK,
                     rotation=90, ha="right", va="top")

    ax2.plot(merged.date, merged.value_fr, color=INK, linewidth=1.2)
    ax2.set_ylabel("FR 10y (%)")
    fig.align_ylabels([ax1, ax2])
    _source(fig, "deliverables/debt_reference_series.csv (OECD FR_LT10, DE_LT10, monthly)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# 10. issuance_by_bucket
# ---------------------------------------------------------------------------
def _chart_issuance_by_bucket(out: Path) -> Path:
    ib = _load("debt_issuance_by_bucket")
    fra = ib[(ib.iso3 == ISO3) & (ib.year.between(2010, 2026))]
    pivot = (fra.groupby(["year", "bucket"]).gross_nominal_lcu_mn.sum()
             .unstack(fill_value=0.0) / 1000).reindex(columns=BUCKET_ORDER, fill_value=0.0)

    cmap = plt.get_cmap("viridis", len(BUCKET_ORDER))
    fig, ax = plt.subplots()
    bottom = np.zeros(len(pivot))
    for i, b in enumerate(BUCKET_ORDER):
        ax.bar(pivot.index, pivot[b], bottom=bottom, color=cmap(i), width=0.75, label=b)
        bottom += pivot[b].to_numpy()
    ax.set_ylabel("EUR bn")
    _thousands(ax)
    ax.set_xticks([int(y) for y in pivot.index if int(y) % 2 == 0])
    ax.set_title("France · gross issuance by residual-maturity bucket at issue")
    ax.legend(loc="upper left", fontsize=6.8, ncol=5, title="Bucket (years)",
              title_fontsize=6.8)
    _source(fig, "deliverables/debt_issuance_by_bucket.csv (register, all classes; "
                  "2026 is year-to-date, to 10 Sep)")
    return _save(fig, out)


# ---------------------------------------------------------------------------
# key_figures.csv
# ---------------------------------------------------------------------------
def _key_figures(out_dir: Path) -> Path:
    rows: list[tuple[str, object]] = []

    pos = _positions_fra()
    snap = pos[pos.as_of == SNAPSHOT].copy()
    snap["uplifted_or_nominal"] = _uplifted_or_nominal(snap)
    total_nom = snap.nominal_lcu_mn.sum() / 1000
    total_upl = snap.uplifted_or_nominal.sum() / 1000
    rows.append(("stock_2026-09-10_total_nominal_eur_bn", round(total_nom, 1)))
    rows.append(("stock_2026-09-10_total_uplifted_eur_bn", round(total_upl, 1)))
    for c in ("bill", "fixed_bullet", "inflation_linked"):
        sub = snap[snap.instrument_class == c]
        rows.append((f"stock_2026-09-10_{c}_nominal_eur_bn",
                     round(sub.nominal_lcu_mn.sum() / 1000, 1)))
        rows.append((f"stock_2026-09-10_{c}_uplifted_eur_bn",
                     round(sub.uplifted_or_nominal.sum() / 1000, 1)))

    mp = _maturity_snapshot()
    total_mp = mp.nominal_lcu_mn.sum()
    for b in ("0-1", "1-2", "2-3"):
        v = mp[mp.bucket == b].nominal_lcu_mn.sum()
        rows.append((f"maturity_2026-09-10_bucket_{b}_eur_bn", round(v / 1000, 1)))
        rows.append((f"maturity_2026-09-10_bucket_{b}_share", round(v / total_mp, 4)))

    mp_all = _load("debt_maturity_profile")
    end2025 = mp_all[(mp_all.iso3 == ISO3) & (mp_all.as_of == "2025-12-31")]
    rows.append(("avg_residual_maturity_2025-12-31_all_years",
                 round(_weighted_avg(end2025.weighted_residual_years,
                                      end2025.nominal_lcu_mn), 2)))
    end2025_fixed = end2025[end2025.instrument_class == "fixed_bullet"]
    rows.append(("avg_residual_maturity_2025-12-31_fixed_bullet_years",
                 round(_weighted_avg(end2025_fixed.weighted_residual_years,
                                      end2025_fixed.nominal_lcu_mn), 2)))

    ib = _load("debt_issuance_by_bucket")
    fixed_iss = ib[(ib.iso3 == ISO3) & (ib.instrument_class == "fixed_bullet")]
    for y in (2021, 2024, 2025, 2026):
        d = fixed_iss[fixed_iss.year == y]
        label = "2026ytd" if y == 2026 else str(y)
        rows.append((f"avg_maturity_at_issue_fixed_bullet_{label}_years",
                     round(_weighted_avg(d.weighted_residual_years_at_issue,
                                          d.gross_nominal_lcu_mn), 2)))

    fixed = pos[pos.instrument_class == "fixed_bullet"].copy()
    for as_of, label in (("2022-12-31", "2022-12-31"), ("2025-12-31", "2025-12-31"),
                         (SNAPSHOT, SNAPSHOT)):
        d = fixed[fixed.as_of == as_of]
        rows.append((f"avg_coupon_fixed_stock_{label}_pct",
                     round(_weighted_avg(d.coupon_pct.fillna(0.0), d.nominal_lcu_mn), 3)))

    dated = pos[pos.as_of.str.endswith("-12-31")].copy()
    dated["year"] = dated.as_of.str[:4].astype(int)
    for y in (2019, 2022, 2025):
        d = dated[dated.year == y]
        total_y = d.nominal_lcu_mn.sum()
        bill_y = d[d.instrument_class == "bill"].nominal_lcu_mn.sum()
        rows.append((f"bill_share_of_stock_{y}", round(bill_y / total_y, 4)))

    snap_calendar = _redemption_by_year()
    snap_calendar["maturity_year"] = pd.to_datetime(snap_calendar.maturity_date).dt.year
    for y in (2026, 2027, 2028):
        v = snap_calendar[snap_calendar.maturity_year == y].nominal_lcu_mn.sum()
        rows.append((f"redemptions_{y}_eur_bn", round(v / 1000, 1)))

    fr10 = _annual_mean("FR_LT10")
    de10 = _annual_mean("DE_LT10")
    for y in range(2021, 2027):
        if y in fr10.index and y in de10.index:
            rows.append((f"oat_bund_spread_{y}_avg_bp", round((fr10[y] - de10[y]) * 100, 1)))
    fr_monthly = _monthly("FR_LT10")
    de_monthly = _monthly("DE_LT10")
    merged = fr_monthly.merge(de_monthly, on="date", suffixes=("_fr", "_de"))
    last = merged.sort_values("date").iloc[-1]
    rows.append(("oat_bund_spread_latest_bp",
                 round((last.value_fr - last.value_de) * 100, 1)))
    rows.append(("oat_bund_spread_latest_date", last.date.date().isoformat()))
    rows.append(("fr_lt10_latest_pct", round(float(last.value_fr), 3)))
    rows.append(("fr_lt10_latest_date", last.date.date().isoformat()))

    cofog = _load("expenditure_cofog")
    fra_cofog = cofog[(cofog.iso3 == ISO3) & (cofog.variant == "strict")
                       & (cofog.line_code == "GF01_7")].set_index("year")
    for y in (2024, 2025, 2027, 2029, 2031, 2036):
        rows.append((f"gf01_7_{y}_pct_gdp", round(float(fra_cofog.loc[y, "pct_gdp"]), 3)))
        rows.append((f"gf01_7_{y}_eur_bn",
                     round(float(fra_cofog.loc[y, "value_lcu_mn"]) / 1000, 1)))

    out_path = out_dir / "key_figures.csv"
    pd.DataFrame(rows, columns=["metric", "value"]).to_csv(out_path, index=False)
    return out_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
CHARTS = {
    "interest_gg": _chart_interest_gg,
    "ledger": _chart_ledger,
    "stock_by_class": _chart_stock_by_class,
    "maturity_profile": _chart_maturity_profile,
    "redemption_calendar": _chart_redemption_calendar,
    "maturity_trend": _chart_maturity_trend,
    "coupon_vs_yield": _chart_coupon_vs_yield,
    "interest_by_security": _chart_interest_by_security,
    "oat_bund_spread": _chart_oat_bund_spread,
    "issuance_by_bucket": _chart_issuance_by_bucket,
}


def render_all(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, fn in CHARTS.items():
        paths[key] = fn(out_dir / f"{key}.png")
    _key_figures(out_dir)
    return paths


if __name__ == "__main__":
    dest = ROOT / "reports" / "briefing_FRA_AFT_2026-09" / "figures"
    result = render_all(dest)
    for key, path in result.items():
        print(f"{key}: {path}")
