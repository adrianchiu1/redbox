"""Readers for family `ecb_bbk` (DEBT_KICKOFF.md §13).

Snapshot -> tidy Series conventions:

* `ecb_series(part)` is the generic loader for every ECB Data Portal
  SDMX-CSV pull in this family (`EST`, `FM`, `ICP` dataflows): `TIME_PERIOD`
  (raw string — daily `"2026-09-08"` for €STR/DFR, monthly `"2026-07"` for
  EONIA/Euribor/HICP) parsed with `pd.to_datetime` (which resolves a
  year-month string to that month's first day with no extra format string
  needed) and `OBS_VALUE` coerced to float. Duplicate timestamps (should not
  occur for a single-key pull) keep the last row.
* `bbk_series(part)` parses the Bundesbank SDW REST CSV export, which is
  *not* SDMX-CSV: a metadata preamble (`Comment (in english)`, `Decimals`,
  `Time format code`, `category`, `unit`, `unit multiplier`, `last update`,
  one `key,value` pair per row) precedes the data rows once the first
  column starts looking like a date (`YYYY-MM-DD` for the daily series
  pulled here); missing observations are the literal string `"."`. Rows are
  selected by matching the first column against a date pattern rather than
  by a fixed skip-row count, since the preamble's length is not documented
  and is not worth depending on.

See `reports/debt_sources/ecb_bbk.md` for the full harvest record and the
key-discovery notes (EONIA/Euribor monthly-only, the HICP `X02200`
ex-tobacco code, the Bundesbank `BBSIS` key for the 10y Svensson yield).
"""

from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from ggfiscal.debt.readers import snap_path

_BBK_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@lru_cache(maxsize=None)
def ecb_series(part: str) -> pd.Series:
    """One ECB Data Portal SDMX-CSV pull (`ECB_EMMI_RATES`) -> float Series,
    DatetimeIndex, sorted ascending. Raises `FileNotFoundError` (via
    `snap_path`) if the snapshot is missing — callers that must tolerate a
    partial harvest (`reference.build_reference_series`) catch that."""
    path = snap_path("ECB_EMMI_RATES", part)
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.upper() for c in df.columns]
    idx = pd.to_datetime(df["TIME_PERIOD"])
    val = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    s = pd.Series(val.to_numpy(), index=idx).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()


@lru_cache(maxsize=None)
def bbk_series(part: str) -> pd.Series:
    """One Bundesbank SDW REST CSV pull (`BBK_KAPITALMARKT`) -> float Series,
    DatetimeIndex, sorted ascending. `"."` (no value available) rows are
    dropped. Raises `FileNotFoundError` if the snapshot is missing."""
    path = snap_path("BBK_KAPITALMARKT", part)
    raw = pd.read_csv(path, header=None, dtype=str, encoding="utf-8-sig",
                       skip_blank_lines=True)
    data_rows = raw[raw[0].astype(str).str.match(_BBK_DATE_RE)]
    idx = pd.to_datetime(data_rows[0])
    val = pd.to_numeric(data_rows[1].str.strip(), errors="coerce")
    s = pd.Series(val.to_numpy(), index=idx).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()
