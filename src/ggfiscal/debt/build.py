"""`ggfiscal debt build` — Stage D1 today: the reference-series table and the
official intermediate totals of both chains, written to data/canonical/
as debt_*.csv (+ parquet), schema-checked (§5, DD12). Later stages add the
register, positions, flows, interest and the chain tables here.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from ggfiscal import config
from ggfiscal.debt import model
from ggfiscal.debt.aggregates import SCHEMA as AGG_SCHEMA, class_aggregates
from ggfiscal.debt.chains import build_chain
from ggfiscal.debt.intermediates import official_totals
from ggfiscal.debt.reference import build_reference_series


def run_id_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def canonical_dir() -> Path:
    return config.repo_root() / "data" / "canonical"


def _write(name: str, df: pd.DataFrame) -> Path:
    schema = model.TABLES.get(name) or {"debt_class_aggregates": AGG_SCHEMA}[name]
    df = schema.validate(df)
    dest = canonical_dir() / f"{name}.csv"
    df.to_csv(dest, index=False)
    try:
        df.to_parquet(dest.with_suffix(".parquet"), index=False)
    except Exception:      # pyarrow optional at runtime
        pass
    return dest


def build(run_id: str | None = None, include_curves: bool = True) -> dict[str, Path]:
    run_id = run_id or run_id_now()
    out: dict[str, Path] = {}
    out["debt_reference_series"] = _write("debt_reference_series",
                                          build_reference_series(run_id, include_curves))
    totals = official_totals(run_id)
    out["debt_official_totals"] = _write("debt_official_totals", totals)
    agg = class_aggregates(run_id)
    out["debt_class_aggregates"] = _write("debt_class_aggregates", agg)
    out["debt_interest_reconciliation"] = _write("debt_interest_reconciliation",
                                                 build_chain("interest", agg, totals, run_id))
    out["debt_financing_reconciliation"] = _write("debt_financing_reconciliation",
                                                  build_chain("financing", agg, totals, run_id))
    return out


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(canonical_dir() / f"{name}.csv", float_precision="round_trip")
