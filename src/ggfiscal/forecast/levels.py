"""The statistical forecasts in currency, for the chartbook's levels charts.

`forecast.statistical` forecasts each granular line as a **share of GDP**,
because that is the quantity a univariate method can sensibly be fitted to.
The chartbook plots levels, in millions of national currency. Turning one
into the other needs a nominal GDP path, and the published bundle has none:
each forecast row in the trees carries the GDP denominator that came with
*that line's* source, and those sources disagree — Germany's 2030 spans
5.205 / 5.240 / 5.339 tn across three of them, and the United Kingdom has no
forecast GDP at 2031 at all.

So this module builds one path per country, and the choice is the one the
rest of the project makes everywhere else: **anchor an outturn, chain a
growth rate onto it.**

    anchor   the tree's own GDP at the last year every line agrees on it
             (2024: the expenditure tree ends there, and at 2025 the
             denominator forks by source — AMECO, Eurostat and ONS all
             publish a different 2025)
    growth   the IMF WEO's NGDP, one vintage, the same series §4 already
             reconciles our totals against

Chaining rather than substituting matters. The WEO's NGDP is not our GDP
anchor — over 2021-2025 it runs 0.97% below ours for Germany — so
multiplying a ratio by raw NGDP would step every German forecast level about
a point below what its own history implies, a seam at the join that is an
artefact of the denominator and nothing else. Growth rates carry no such
level difference, which is why every stitched series in this project is
built this way (§7, D-S4-002).

What this does NOT do is add uncertainty about GDP. The interval here is the
line's own interval multiplied by a single GDP path, so it is the
uncertainty of the **ratio** and not of the level: the GDP path is taken as
given. A level from this file is a joint statement — this ratio, on that
path — and the columns name the path so it can be replaced.

Nothing here enters the canonical layer. Like `statistical_forecasts.csv`
and `benchmark_balance.csv` this is a forecast-layer side-car; it reads the
published bundle plus the WEO snapshot through the standard reader, and is a
pure function of the two.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config

HORIZON = 2031
GROWTH_SOURCE = "IMF_WEO"
GROWTH_INDICATOR = "NGDP"

COLUMNS = [
    "iso3", "country", "classification", "line_code", "line_label", "method",
    "year", "pct_gdp", "gdp_lcu_mn", "currency", "value_lcu_mn",
    "lo80_lcu_mn", "hi80_lcu_mn", "lo95_lcu_mn", "hi95_lcu_mn",
    "gdp_basis", "gdp_anchor_year", "gdp_anchor_lcu_mn", "gdp_growth_source",
    "gdp_growth_vintage", "notes", "run_id",
]


def latest_vintage() -> str:
    from ggfiscal.ingest.endpoints import weo_vintages

    return sorted(weo_vintages())[-1]


def _tree() -> pd.DataFrame:
    deliv = config.repo_root() / "deliverables"
    read = lambda n: pd.read_csv(deliv / n, float_precision="round_trip")
    # all three trees (D-S13-007): the ESA_EXP lines are among the series
    # forecast, and the GDP anchor is the last year *every* line agrees on
    return pd.concat([read("expenditure_cofog.csv"), read("expenditure_esa.csv"),
                      read("revenue_esa.csv")],
                     ignore_index=True).query("variant == 'strict'")


def gdp_path(iso3: str, tree: pd.DataFrame, vintage: str):
    """One nominal GDP path per country: our own outturn to the last year the
    whole tree agrees on it, then chained forward on the WEO's NGDP growth.

    Returns (series indexed by year, anchor_year, anchor_value, note).
    """
    from ggfiscal.standardise.readers import weo_series

    actual = (tree.query("iso3 == @iso3 and basis == 'actual'")
              .dropna(subset=["gdp_lcu_mn"]))
    per_year = actual.groupby("year").gdp_lcu_mn
    # at the last outturn year the denominator forks — AMECO, Eurostat and
    # ONS each publish their own — so the anchor is the last year on which
    # every line still agrees, and no arbitrary pick is made
    agreed = per_year.nunique()
    anchor_year = int(agreed[agreed == 1].index.max())
    history = per_year.first().loc[:anchor_year]

    weo = weo_series(vintage, iso3, GROWTH_INDICATOR).dropna()
    if weo.empty:                               # pragma: no cover - guard
        raise RuntimeError(f"{iso3}: no {GROWTH_SOURCE} {GROWTH_INDICATOR} "
                           f"for vintage {vintage} in the snapshot store")
    forward, value = {}, float(history.loc[anchor_year])
    for year in range(anchor_year + 1, HORIZON + 1):
        if year not in weo.index or (year - 1) not in weo.index:
            break                               # pragma: no cover - guard
        value *= float(weo[year]) / float(weo[year - 1])
        forward[year] = value

    path = pd.concat([history, pd.Series(forward)])
    note = (f"outturn to {anchor_year} (the last year every line's "
            f"denominator agrees), then chained on {GROWTH_SOURCE} "
            f"{GROWTH_INDICATOR} {vintage} growth")
    return path, anchor_year, float(history.loc[anchor_year]), note


def compute(run_id: str = "", vintage: str = "") -> tuple[pd.DataFrame, list[str]]:
    vintage = vintage or latest_vintage()
    tree = _tree()
    deliv = config.repo_root() / "deliverables"
    forecasts = pd.read_csv(deliv / "statistical_forecasts.csv",
                            float_precision="round_trip")
    currency = dict(zip(tree.iso3, tree.currency))

    frames, notes = [], []
    for iso3 in sorted(forecasts.iso3.unique()):
        path, anchor_year, anchor, note = gdp_path(iso3, tree, vintage)
        notes.append(f"{iso3}: GDP {note}; {anchor_year} anchor "
                     f"{anchor:,.0f} -> {HORIZON} {path.loc[HORIZON]:,.0f} "
                     f"{currency[iso3]} mn")
        g = forecasts[forecasts.iso3 == iso3].copy()
        missing = sorted(set(g.year) - set(path.index))
        if missing:                             # pragma: no cover - guard
            notes.append(f"{iso3}: no GDP for {missing}, those rows dropped")
            g = g[g.year.isin(path.index)]
        gdp = g.year.map(path)
        g["gdp_lcu_mn"] = gdp
        g["currency"] = currency[iso3]
        for out, src in (("value_lcu_mn", "pct_gdp"),
                         ("lo80_lcu_mn", "lo80"), ("hi80_lcu_mn", "hi80"),
                         ("lo95_lcu_mn", "lo95"), ("hi95_lcu_mn", "hi95")):
            g[out] = g[src] / 100.0 * gdp
        g["gdp_basis"] = "anchored_outturn_chained_on_weo_ngdp"
        g["gdp_anchor_year"] = anchor_year
        g["gdp_anchor_lcu_mn"] = anchor
        g["gdp_growth_source"] = GROWTH_SOURCE
        g["gdp_growth_vintage"] = vintage
        g["notes"] = note
        g["run_id"] = run_id or g.run_id
        frames.append(g)

    frame = pd.concat(frames, ignore_index=True).reindex(columns=COLUMNS)
    frame = frame.sort_values(
        ["iso3", "classification", "line_code", "method", "year"],
        kind="stable").reset_index(drop=True)
    return frame, notes


def write(run_id: str = "", vintage: str = ""):
    frame, notes = compute(run_id, vintage)
    dest = config.repo_root() / "deliverables" / "forecast_levels.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(dest, index=False)
    return dest, notes
