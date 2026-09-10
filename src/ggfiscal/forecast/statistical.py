"""Statistical forecasts of each granular line as a share of GDP (§ committee
request, D-S9-007).

The published `strict` series stop where their official source stops, which
for most lines is the last outturn. This module answers a different question:
what would four standard univariate methods say, on the history alone, out to
2031? It is a benchmark to read the official forecasts against, never a
substitute for them — nothing here enters the canonical layer or the trees.

Four methods, chosen to mirror the R `forecast` package where one exists:

    auto.arima   pmdarima.auto_arima, AICc, non-seasonal (the direct port)
    ets          statsmodels ETSModel, AICc over the error/trend/damped grid
    prophet      prophet, linear trend, no seasonality (annual data)
    uc           statsmodels UnobservedComponents, local linear trend with a
                 damped stochastic cycle (the statespace "cycles" example)

plus a fifth, `combination`: the mean of the four point forecasts, with a
standard error that carries BOTH the average within-model variance and the
variance across the four point forecasts, so it widens honestly when the methods
disagree rather than pretending their agreement is information.

Two deliberate choices, both committee-approved:

* **Fitted on outturn only.** The sample ends at the last actual, never at
  the last official forecast, so where a line carries an official projection
  the two can be read against each other on the same axes.
* **Series whose official strict forecast already reaches 2031 are skipped**
  (FRA/DEU GF01_7, GF07, GF09). Nothing to benchmark: the official source
  already covers the horizon.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from ggfiscal import config

HORIZON = 2031
Z95, Z80 = 1.959964, 1.281552
TOTALS = {"TE", "TR"}

COLUMNS = [
    "iso3", "country", "classification", "line_code", "line_label", "method",
    "year", "pct_gdp", "se", "lo80", "hi80", "lo95", "hi95",
    "model", "fit_first_year", "fit_last_year", "n_obs", "run_id",
]

COUNTRY_NAME = {"GBR": "United Kingdom", "FRA": "France", "DEU": "Germany"}


def _quiet() -> None:
    warnings.filterwarnings("ignore")
    for name in ("cmdstanpy", "prophet"):
        logging.getLogger(name).setLevel(logging.ERROR)


# ------------------------------------------------------------------ methods

def _positional(y: pd.Series) -> pd.Series:
    """The same values on a 0..n-1 RangeIndex — the only integer index
    statsmodels will forecast beyond."""
    return pd.Series(np.asarray(y, dtype=float), index=pd.RangeIndex(len(y)))


def _auto_arima(y: pd.Series, h: int):
    import pmdarima as pm

    m = pm.auto_arima(y.values, seasonal=False, stepwise=True,
                      suppress_warnings=True, error_action="ignore",
                      information_criterion="aicc")
    point, ci = m.predict(n_periods=h, return_conf_int=True, alpha=0.05)
    se = (ci[:, 1] - ci[:, 0]) / (2 * Z95)
    label = f"ARIMA{m.order}" + ("+drift" if m.with_intercept else "")
    return np.asarray(point, float), np.asarray(se, float), label


def _ets(y: pd.Series, h: int):
    """R's `ets` picks a model by AICc; statsmodels fits one you name, so the
    grid is walked here. Annual data, so no seasonal component.

    The series is re-indexed onto a plain RangeIndex first. statsmodels will
    only forecast past the end of a RangeIndex, and whether a year index
    comes back from pandas as a RangeIndex or a plain Index is incidental —
    re-indexing makes the fit depend on the data rather than on that
    accident. Years are put back by the caller.
    """
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    values = _positional(y)
    best = None
    for error in ("add", "mul"):
        if error == "mul" and (values <= 0).any():
            continue
        for trend in (None, "add"):
            for damped in ((False,) if trend is None else (False, True)):
                try:
                    fit = ETSModel(values, error=error, trend=trend,
                                   damped_trend=damped, seasonal=None
                                   ).fit(disp=False)
                except Exception:
                    continue
                k, n = fit.params.size, len(values)
                aicc = fit.aic + (2 * k * (k + 1)) / max(n - k - 1, 1)
                if best is None or aicc < best[0]:
                    shape = "Ad" if damped else ("A" if trend else "N")
                    best = (aicc, fit, f"ETS({error[0].upper()},{shape},N)")
    if best is None:
        raise RuntimeError("no ETS specification converged")
    _, fit, label = best
    frame = fit.get_prediction(start=len(values), end=len(values) + h - 1
                               ).summary_frame(alpha=0.05)
    se = (frame["pi_upper"] - frame["pi_lower"]).to_numpy() / (2 * Z95)
    return frame["mean"].to_numpy(), se, label


def _prophet(y: pd.Series, h: int):
    from prophet import Prophet

    history = pd.DataFrame({
        "ds": pd.to_datetime(y.index.astype(int).astype(str) + "-12-31"),
        "y": y.to_numpy(float)})
    model = Prophet(yearly_seasonality=False, weekly_seasonality=False,
                    daily_seasonality=False, interval_width=0.95)
    model.fit(history)
    last = int(y.index.max())
    future = pd.DataFrame({"ds": pd.to_datetime(
        [f"{year}-12-31" for year in range(last + 1, last + 1 + h)])})
    p = model.predict(future)
    se = (p["yhat_upper"] - p["yhat_lower"]).to_numpy() / (2 * Z95)
    return p["yhat"].to_numpy(), se, "Prophet(linear trend)"


def _uc(y: pd.Series, h: int):
    """The statespace "cycles" specification, falling back as the series gets
    too short or too flat for the richer models to identify."""
    from statsmodels.tsa.statespace.structural import UnobservedComponents

    values = _positional(y)                      # RangeIndex, as in _ets
    specs = [
        (dict(level="local linear trend", cycle=True, stochastic_cycle=True,
              damped_cycle=True), "UC(local linear trend + damped cycle)"),
        (dict(level="local linear trend", cycle=True, stochastic_cycle=True),
         "UC(local linear trend + cycle)"),
        (dict(level="local linear trend"), "UC(local linear trend)"),
        (dict(level="local level"), "UC(local level)"),
    ]
    for spec, label in specs:
        try:
            fit = UnobservedComponents(values, **spec
                                       ).fit(disp=False, maxiter=500)
            frame = fit.get_forecast(h).summary_frame(alpha=0.05)
        except Exception:
            continue
        point, se = frame["mean"].to_numpy(), frame["mean_se"].to_numpy()
        if np.isfinite(point).all() and np.isfinite(se).all():
            return point, se, label
    raise RuntimeError("no UC specification converged")


METHODS = {"auto.arima": _auto_arima, "ets": _ets,
           "prophet": _prophet, "uc": _uc}


# -------------------------------------------------------------------- driver

def _strict_tree() -> pd.DataFrame:
    canonical = config.repo_root() / "data" / "canonical"
    frames = []
    for stem, classification in (("expenditure_long", "COFOG"),
                                 ("revenue_long", "ESA_REV")):
        df = pd.read_csv(canonical / f"{stem}_strict.csv",
                         float_precision="round_trip")
        frames.append(df.assign(classification=classification))
    tree = pd.concat(frames, ignore_index=True)
    return tree[~tree.line_code.isin(TOTALS)]


def forecast_series(y: pd.Series, h: int) -> tuple[dict, list[str]]:
    """Run every method on one history. Returns {method: (point, se, label)}
    plus the combination, and a list of any failures (reported, not raised —
    one awkward series must not take the run down)."""
    out, failures = {}, []
    for name, fn in METHODS.items():
        try:
            out[name] = fn(y, h)
        except Exception as exc:                      # noqa: BLE001
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    if out:
        points = np.vstack([v[0] for v in out.values()])
        ses = np.vstack([v[1] for v in out.values()])
        between = points.var(axis=0, ddof=1) if len(points) > 1 else 0.0
        out["combination"] = (
            points.mean(axis=0),
            np.sqrt((ses ** 2).mean(axis=0) + between),
            f"mean of {len(points)} + between-model variance")
    return out, failures


def compute(run_id: str = "") -> tuple[pd.DataFrame, list[str]]:
    _quiet()
    tree = _strict_tree()
    rows, notes = [], []
    for (iso3, line), g in tree.groupby(["iso3", "line_code"], sort=True):
        final_strict = int(g.year.max())
        if final_strict >= HORIZON:
            notes.append(f"{iso3}/{line}: skipped — official strict forecast "
                         f"already reaches {final_strict}")
            continue
        actual = g[~g.is_forecast].dropna(subset=["pct_gdp"])
        y = actual.set_index("year").pct_gdp.sort_index()
        last = int(y.index.max())
        h = HORIZON - last
        if h < 1 or len(y) < 10:
            notes.append(f"{iso3}/{line}: skipped — {len(y)} usable "
                         f"observations, horizon {h}")
            continue
        fits, failures = forecast_series(y, h)
        notes += [f"{iso3}/{line}: {f}" for f in failures]
        years = list(range(last + 1, HORIZON + 1))
        for method, (point, se, label) in fits.items():
            for year, mu, sigma in zip(years, point, se):
                rows.append({
                    "iso3": iso3, "country": COUNTRY_NAME[iso3],
                    "classification": g.classification.iloc[0],
                    "line_code": line, "line_label": g.line_label.iloc[0],
                    "method": method, "year": year,
                    "pct_gdp": mu, "se": sigma,
                    "lo80": mu - Z80 * sigma, "hi80": mu + Z80 * sigma,
                    "lo95": mu - Z95 * sigma, "hi95": mu + Z95 * sigma,
                    "model": label, "fit_first_year": int(y.index.min()),
                    "fit_last_year": last, "n_obs": len(y), "run_id": run_id,
                })
    frame = pd.DataFrame(rows, columns=COLUMNS).sort_values(
        ["iso3", "classification", "line_code", "method", "year"],
        kind="stable").reset_index(drop=True)
    return frame, notes


def write(run_id: str = "") -> tuple[Path, list[str]]:
    frame, notes = compute(run_id)
    dest = config.repo_root() / "deliverables" / "statistical_forecasts.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(dest, index=False)
    return dest, notes
