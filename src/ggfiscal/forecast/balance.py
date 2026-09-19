"""The benchmark balance: the line forecasts summed back into a deficit path.

`forecast.statistical` forecasts each granular line as a share of GDP.
This module puts them back together into the one number the lines exist to
explain — net lending/borrowing as a share of GDP — out to 2031, with an
interval around it.

§4.4 of the chartbook says a forward "our NLB" is impossible, because a level
needs every component and most lines had no forecast. That was true of the
official forecasts and is no longer true of the benchmark: every granular line
now carries a statistical path to 2031, so the sum is complete and
`resid_coverage` is zero by construction. What comes out is a **benchmark**
balance, on the same footing as the line forecasts it is built from — never a
rival to an official projection, and never part of the canonical layer.

The construction, in full:

* **Base year.** The latest year in which EVERY line has an outturn. The
  expenditure tree ends a year before the revenue tree, so this is the
  expenditure tree's last actual (2024 at the time of writing), not the
  ledger's last year. The path starts from the balance ledger's own published
  NLB/GDP at that year — a real published balance, not a sum.
* **Per line.** An official projection is used only where it covers the whole
  horizon to 2031; otherwise the line takes its statistical `combination`
  path throughout. This is deliberately NOT the chartbook panel's rule, which
  prefers an official projection at any horizon: a total needs every line at
  every year, and splicing a benchmark anchored at the last outturn onto an
  official path that has already moved away from it would invent a number
  that appears in no file. The lines where the two rules differ are reported.
* **The sum.** Expenditure is taken as GF01_7 + GF01_X + GF02..GF10, never as
  GF01..GF10. The two are the same identity in history, but in forecast the
  Level I set hides the interest line inside GF01, whose own univariate fit
  knows nothing about the official interest projection. For France that is
  worth over two points of GDP by 2031.
* **The interval.** Each line's published standard error, propagated with a
  correlation structure ESTIMATED from the outturn history of the same lines
  — one average correlation within a side and one across the two sides, per
  country and horizon. Independence would understate it (the lines move with
  the cycle together); perfect correlation would be wrong in both directions
  at once. Lines on an official path contribute no variance, because a
  published projection is not a distribution; that makes the interval an
  understatement wherever a country has official legs, and the count is
  published on every row.
* **The calibration.** Beside the interval, the spread of h-year moves in the
  ledger's own NLB/GDP over the whole outturn record. It is not a forecast
  interval and is not used to build one — it is there so a reader can see
  whether the model's band is wider or narrower than what the balance has
  actually done over six years.

Nothing here is written to the canonical layer, and the module reads only
`deliverables/`: the two trees, the balance ledger and the statistical
forecasts. It therefore runs anywhere the published bundle exists, without a
harvest.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from ggfiscal import config

HORIZON = 2031
Z95, Z80 = 1.959964, 1.281552

# Expenditure as the interest split, not the Level I set — see the module
# docstring. GF01 is deliberately absent: it is GF01_7 + GF01_X.
EXP_LINES = ["GF01_7", "GF01_X"] + [f"GF{i:02d}" for i in range(2, 11)]
REV_LINES = [f"R{i:02d}" for i in range(1, 11)]
LINES = EXP_LINES + REV_LINES

# Below this many overlapping h-year changes a pairwise correlation is noise;
# the estimate falls back to the longest horizon that does clear the bar.
MIN_CORR_OBS = 12

COLUMNS = [
    "iso3", "country", "base_year", "year", "horizon", "kind", "side",
    "line_code", "line_label", "anchor_year", "anchor_pct_gdp", "pct_gdp",
    "contribution_pp", "se", "lo80", "hi80", "lo95", "hi95",
    "source", "source_runs_to", "rho_within", "rho_between", "n_corr_obs",
    "history_sd_pp", "n_history_obs", "n_official", "n_statistical",
    "notes", "run_id",
]


def _deliverables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    deliv = config.repo_root() / "deliverables"
    read = lambda n: pd.read_csv(deliv / n, float_precision="round_trip")
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")],
                     ignore_index=True).query("variant == 'strict'")
    ledger = read("balance_ledger.csv").query("variant == 'strict'")
    forecasts = read("statistical_forecasts.csv").query("method == 'combination'")
    return tree, ledger, forecasts


def _leg(tree: pd.DataFrame, forecasts: pd.DataFrame, iso3: str, line: str):
    """One line's outturn, the path this construction takes forward, and the
    standard error of that path (zero where the path is a published one)."""
    g = tree.query("iso3 == @iso3 and line_code == @line").dropna(
        subset=["pct_gdp"])
    actual = (g[g.basis == "actual"].sort_values("year")
              .set_index("year").pct_gdp)
    official = g[g.basis == "forecast"].sort_values("year")
    if len(official) and official.year.max() >= HORIZON:
        path = official.set_index("year").pct_gdp
        return (actual, path, pd.Series(0.0, index=path.index), "official",
                int(official.year.max()))
    combo = (forecasts.query("iso3 == @iso3 and line_code == @line")
             .sort_values("year").set_index("year"))
    runs_to = int(combo.index.max()) if len(combo) else int(actual.index.max())
    return actual, combo.pct_gdp, combo.se, "statistical", runs_to


def _panel_source(tree: pd.DataFrame, iso3: str, line: str) -> str:
    """What the chartbook panel would use for the same line — official at any
    horizon. Reported where it differs, never used here."""
    g = tree.query("iso3 == @iso3 and line_code == @line").dropna(
        subset=["pct_gdp"])
    return "official" if len(g[g.basis == "forecast"]) else "statistical"


def _correlations(actuals: dict[str, pd.Series], h: int):
    """Average pairwise correlation of the lines' h-year changes in ratio:
    one within a side, one across the two sides."""
    frame = pd.DataFrame(actuals).dropna()
    for lag in [h, *range(h - 1, 0, -1)]:
        changes = (frame - frame.shift(lag)).dropna()
        if len(changes) >= MIN_CORR_OBS:
            break
    else:                                       # pragma: no cover - 30y history
        return float("nan"), float("nan"), 0
    corr = changes.corr()
    have = lambda names: [c for c in names if c in corr.columns]
    rev, exp = have(REV_LINES), have(EXP_LINES)
    within = [corr.loc[a, b] for group in (rev, exp)
              for a, b in itertools.combinations(group, 2)]
    between = [corr.loc[a, b] for a in rev for b in exp]
    return (float(np.nanmean(within)), float(np.nanmean(between)),
            int(len(changes)))


def _balance_se(se: pd.Series, rho_within: float, rho_between: float) -> float:
    """Var(ΣR − ΣE) under one within-side and one cross-side correlation.

    Each side's variance is the sum of its own variances plus the correlated
    cross terms; the two sides then covary, and that covariance is subtracted
    because the balance is their difference. A positive cross-side correlation
    therefore narrows the band — which is the whole reason the lines cannot be
    treated as independent.
    """
    def side(names):
        s = se.reindex(names).dropna()
        total, squares = float(s.sum()), float((s ** 2).sum())
        return squares + rho_within * (total ** 2 - squares), total

    var_rev, sum_rev = side(REV_LINES)
    var_exp, sum_exp = side(EXP_LINES)
    var = var_rev + var_exp - 2.0 * rho_between * sum_rev * sum_exp
    return float(np.sqrt(max(var, 0.0)))


def _history_spread(ledger: pd.DataFrame, iso3: str, h: int):
    """How far the ledger's own NLB/GDP has moved over h years, across the
    whole outturn record. A calibration reference, never an interval."""
    g = (ledger.query("iso3 == @iso3")
         .dropna(subset=["nlb_lcu_mn", "gdp_lcu_mn"]).sort_values("year"))
    nlb = (100.0 * g.nlb_lcu_mn / g.gdp_lcu_mn).set_axis(g.year.astype(int))
    moves = (nlb - nlb.shift(h)).dropna()
    if len(moves) < 2:                          # pragma: no cover
        return float("nan"), int(len(moves))
    return float(moves.std(ddof=1)), int(len(moves))


def compute(run_id: str = "") -> tuple[pd.DataFrame, list[str]]:
    tree, ledger, forecasts = _deliverables()
    rows: list[dict] = []
    notes: list[str] = []

    for iso3 in sorted(tree.iso3.unique()):
        country = tree.query("iso3 == @iso3").country.iloc[0]
        legs = {line: _leg(tree, forecasts, iso3, line) for line in LINES}
        labels = dict(zip(tree.line_code, tree.line_label))
        missing = [line for line, leg in legs.items() if not len(leg[1])]
        if missing:                             # pragma: no cover - guard
            notes.append(f"{iso3}: skipped — no forward path for {missing}")
            continue

        actuals = {line: leg[0] for line, leg in legs.items()}
        # the base is the last year EVERY line has an outturn, which the
        # expenditure tree sets a year earlier than the revenue tree
        base = min(int(s.index.max()) for s in actuals.values())
        led = (ledger.query("iso3 == @iso3")
               .dropna(subset=["nlb_lcu_mn", "gdp_lcu_mn"]).set_index("year"))
        if base not in led.index:               # pragma: no cover - guard
            notes.append(f"{iso3}: skipped — ledger has no NLB at {base}")
            continue
        nlb_base = 100.0 * led.loc[base, "nlb_lcu_mn"] / led.loc[base, "gdp_lcu_mn"]

        differs = [line for line in LINES
                   if _panel_source(tree, iso3, line) != legs[line][3]]
        if differs:
            notes.append(
                f"{iso3}: {len(differs)} line(s) take the statistical path "
                f"here but an official one in the chartbook panel, because "
                f"the official projection stops short of {HORIZON}: "
                + ", ".join(sorted(differs)))
        n_official = sum(leg[3] == "official" for leg in legs.values())
        n_statistical = len(LINES) - n_official

        for year in range(base + 1, HORIZON + 1):
            h = year - base
            level, delta, se = {}, {}, {}
            for line, (actual, path, path_se, _, _) in legs.items():
                # the outturn wherever there is one, the path after it: a
                # revenue line's 2025 is an actual even though an expenditure
                # line's is already a forecast
                if year in actual.index:
                    level[line], se[line] = float(actual.loc[year]), 0.0
                elif year in path.index:
                    level[line] = float(path.loc[year])
                    se[line] = float(path_se.loc[year])
                else:
                    level[line] = se[line] = float("nan")
                delta[line] = level[line] - float(actual.loc[base])
            level, delta, se = (pd.Series(level), pd.Series(delta),
                                pd.Series(se))
            if level.isna().any():              # pragma: no cover - guard
                notes.append(f"{iso3} {year}: incomplete cross-section, skipped")
                continue

            rho_w, rho_b, n_corr = _correlations(actuals, h)
            sd = _balance_se(se, rho_w, rho_b)
            hist_sd, n_hist = _history_spread(ledger, iso3, h)
            te, tr = float(level[EXP_LINES].sum()), float(level[REV_LINES].sum())
            nlb = nlb_base + float(delta[REV_LINES].sum()) - float(
                delta[EXP_LINES].sum())
            part_actual = [l for l in LINES if year in legs[l][0].index]

            shared = dict(
                iso3=iso3, country=country, base_year=base, year=year,
                horizon=h, rho_within=rho_w, rho_between=rho_b,
                n_corr_obs=n_corr, history_sd_pp=hist_sd, n_history_obs=n_hist,
                n_official=n_official, n_statistical=n_statistical,
                run_id=run_id)

            for line in LINES:
                side = "revenue" if line in REV_LINES else "expenditure"
                sign = 1.0 if side == "revenue" else -1.0
                actual, _, _, source, runs_to = legs[line]
                rows.append({
                    **shared, "kind": "line", "side": side,
                    "line_code": line, "line_label": labels.get(line),
                    "anchor_year": int(actual.index.max()),
                    "anchor_pct_gdp": float(actual.loc[base]),
                    "pct_gdp": level[line],
                    "contribution_pp": sign * delta[line],
                    "se": se[line],
                    "source": "outturn" if year in actual.index else source,
                    "source_runs_to": runs_to,
                    "notes": f"level and contribution measured from {base}",
                })
            for kind, side, value, contribution in (
                    ("expenditure_total", "expenditure", te,
                     -float(delta[EXP_LINES].sum())),
                    ("revenue_total", "revenue", tr,
                     float(delta[REV_LINES].sum()))):
                rows.append({
                    **shared, "kind": kind, "side": side,
                    "line_code": None, "line_label": None,
                    "anchor_year": base, "anchor_pct_gdp": None,
                    "pct_gdp": value, "contribution_pp": contribution,
                    "se": None, "source": None, "source_runs_to": None,
                    "notes": f"sum of the {side} lines at {year}",
                })
            rows.append({
                **shared, "kind": "balance", "side": "balance",
                "line_code": None, "line_label": None, "anchor_year": base,
                "anchor_pct_gdp": nlb_base, "pct_gdp": nlb,
                "contribution_pp": nlb - nlb_base, "se": sd,
                "lo80": nlb - Z80 * sd, "hi80": nlb + Z80 * sd,
                "lo95": nlb - Z95 * sd, "hi95": nlb + Z95 * sd,
                "source": "benchmark", "source_runs_to": HORIZON,
                "notes": (
                    f"ledger NLB/GDP at {base} plus the lines' changes since "
                    f"{base}; interval from the lines' own standard errors "
                    f"under rho_within/rho_between"
                    + (f"; {len(part_actual)} line(s) still outturn at {year}"
                       if part_actual else "")
                    + (f"; {n_official} line(s) on an official path "
                       "contribute no variance" if n_official else "")),
            })

    frame = pd.DataFrame(rows).reindex(columns=COLUMNS)
    frame = frame.sort_values(
        ["iso3", "year", "kind", "side", "line_code"],
        kind="stable", na_position="first").reset_index(drop=True)
    return frame, notes


def write(run_id: str = ""):
    frame, notes = compute(run_id)
    dest = config.repo_root() / "deliverables" / "benchmark_balance.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(dest, index=False)
    return dest, notes
