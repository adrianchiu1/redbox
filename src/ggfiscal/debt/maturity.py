"""DEBT_KICKOFF.md §5.9–5.10, §7.8, DD7: residual maturity, bucketing, the
year-end maturity profile and gross issuance by residual maturity at issue.

Pure functions over the canonical frames (securities, positions, flows);
no I/O. Bucket edges and labels come from config/debt.yaml.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ggfiscal import config

DAYS_PER_YEAR = 365.25
GROSS_ISSUANCE_FLOWS = ("auction", "syndication", "tap", "tender")


def bucket_edges() -> tuple[list[float], list[str], str]:
    cfg = config.debt()["maturity_buckets"]
    return [float(x) for x in cfg["edges"]], list(cfg["labels"]), cfg["undated_bucket"]


def residual_years(as_of: pd.Timestamp, maturity: pd.Timestamp | None) -> float:
    """Years to maturity on `as_of`; +inf for undated (NaT maturity)."""
    if maturity is None or pd.isna(maturity):
        return math.inf
    return (pd.Timestamp(maturity) - pd.Timestamp(as_of)).days / DAYS_PER_YEAR


def bucket_of(years: float) -> str | None:
    """Right-closed buckets on the config edges: (0,1] -> '0-1', (1,2] -> '1-2',
    ..., (30, inf) -> '30+'. Non-positive residual (matured) -> None."""
    edges, labels, undated = bucket_edges()
    if years is None or (isinstance(years, float) and math.isnan(years)):
        return None
    if years <= 0:
        return None
    if math.isinf(years):
        return undated
    for lo, hi, label in zip(edges[:-1], edges[1:], labels[:-1]):
        if lo < years <= hi:
            return label
    return labels[-1]


def _bucket_series(years: pd.Series) -> pd.Series:
    return years.map(bucket_of)


def maturity_profile(securities: pd.DataFrame, positions: pd.DataFrame,
                     as_of: pd.Timestamp, iso3: str) -> pd.DataFrame:
    """§5.9: nominal, uplifted and market-hands outstanding by instrument
    class and residual-maturity bucket at `as_of`, from the positions dated
    exactly `as_of` (the caller supplies year-end positions)."""
    as_of = pd.Timestamp(as_of)
    pos = positions[(positions["iso3"] == iso3) & (positions["as_of"] == as_of)]
    sec = securities[securities["iso3"] == iso3].set_index("security_id")
    if pos.empty:
        return _empty_profile()
    df = pos.join(sec[["instrument_class", "maturity_date"]], on="security_id", how="left")
    missing = df["instrument_class"].isna()
    if missing.any():
        raise KeyError(f"positions reference unknown securities: "
                       f"{sorted(df.loc[missing, 'security_id'].unique())[:5]} (V29)")
    df["residual_years"] = [residual_years(as_of, m) for m in df["maturity_date"]]
    df["bucket"] = _bucket_series(df["residual_years"])
    df = df[df["bucket"].notna()]
    if df.empty:
        return _empty_profile()
    df["_w"] = df["nominal_lcu_mn"] * df["residual_years"].replace(math.inf, np.nan)
    g = df.groupby(["instrument_class", "bucket"], sort=False)
    out = g.agg(nominal_lcu_mn=("nominal_lcu_mn", "sum"),
                nominal_uplifted_lcu_mn=("nominal_uplifted_lcu_mn", "sum"),
                market_hands_lcu_mn=("market_hands_lcu_mn", "sum"),
                n_securities=("security_id", "nunique"),
                _w=("_w", lambda s: s.sum(min_count=1))).reset_index()
    out["weighted_residual_years"] = out["_w"] / out["nominal_lcu_mn"].where(out["nominal_lcu_mn"] != 0)
    out = out.drop(columns="_w")
    # sums over all-NaN columns must stay NaN, not 0
    for col in ("nominal_uplifted_lcu_mn", "market_hands_lcu_mn"):
        all_nan = g[col].apply(lambda s: s.isna().all()).reset_index(drop=True)
        out.loc[all_nan.values, col] = np.nan
    out.insert(0, "as_of", as_of)
    out.insert(0, "iso3", iso3)
    return _ordered(out)


def issuance_by_bucket(securities: pd.DataFrame, flows: pd.DataFrame,
                       year: int, iso3: str,
                       flow_types: tuple[str, ...] = GROSS_ISSUANCE_FLOWS) -> pd.DataFrame:
    """§5.10, DD7: gross issuance in `year` by instrument class and the
    residual maturity of the security at the settlement date of each
    operation — a tap of a 2038 line in 2024 is a 14-year issue."""
    fl = flows[(flows["iso3"] == iso3) & (flows["flow_type"].isin(flow_types))
               & (flows["settlement_date"].dt.year == year)]
    sec = securities[securities["iso3"] == iso3].set_index("security_id")
    if fl.empty:
        return _empty_issuance()
    df = fl.join(sec[["instrument_class", "maturity_date"]], on="security_id", how="left")
    missing = df["instrument_class"].isna()
    if missing.any():
        raise KeyError(f"flows reference unknown securities: "
                       f"{sorted(df.loc[missing, 'security_id'].unique())[:5]} (V29)")
    df["residual_years"] = [residual_years(d, m) for d, m in zip(df["settlement_date"], df["maturity_date"])]
    df["bucket"] = _bucket_series(df["residual_years"])
    df = df[df["bucket"].notna()]
    if df.empty:
        return _empty_issuance()
    df["_w"] = df["nominal_lcu_mn"] * df["residual_years"].replace(math.inf, np.nan)
    g = df.groupby(["instrument_class", "bucket"], sort=False)
    out = g.agg(gross_nominal_lcu_mn=("nominal_lcu_mn", "sum"),
                gross_cash_lcu_mn=("cash_lcu_mn", "sum"),
                n_operations=("nominal_lcu_mn", "size"),
                _w=("_w", lambda s: s.sum(min_count=1))).reset_index()
    out["weighted_residual_years_at_issue"] = out["_w"] / out["gross_nominal_lcu_mn"].where(out["gross_nominal_lcu_mn"] != 0)
    out = out.drop(columns="_w")
    all_nan = g["cash_lcu_mn"].apply(lambda s: s.isna().all()).reset_index(drop=True)
    out.loc[all_nan.values, "gross_cash_lcu_mn"] = np.nan
    out.insert(0, "year", year)
    out.insert(0, "iso3", iso3)
    return _ordered(out)


def _ordered(df: pd.DataFrame) -> pd.DataFrame:
    _, labels, _ = bucket_edges()
    df = df.copy()
    df["_b"] = df["bucket"].map({b: i for i, b in enumerate(labels)})
    return df.sort_values(["instrument_class", "_b"]).drop(columns="_b").reset_index(drop=True)


def _empty_profile() -> pd.DataFrame:
    return pd.DataFrame(columns=["iso3", "as_of", "instrument_class", "bucket",
                                 "nominal_lcu_mn", "nominal_uplifted_lcu_mn",
                                 "market_hands_lcu_mn", "n_securities",
                                 "weighted_residual_years"])


def _empty_issuance() -> pd.DataFrame:
    return pd.DataFrame(columns=["iso3", "year", "instrument_class", "bucket",
                                 "gross_nominal_lcu_mn", "gross_cash_lcu_mn",
                                 "n_operations", "weighted_residual_years_at_issue"])
