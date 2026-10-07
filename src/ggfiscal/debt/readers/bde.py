"""Banco de España Boletín Estadístico reader (`ESP_BDE_BE`, DE4).

The bulk zip `be.zip` holds one CSV per table (`be1101.csv` ... `be11b.csv`
for chapter 11, Administraciones Públicas), Latin-1, comma-separated, with
six header rows — series code, sequence number, alias, description, unit,
frequency — then one row per period labelled `"DIC 1994"`, `"ENE 1995"`
(monthly) or the quarter's last month (quarterly); `"_"` marks a missing
value; trailing `FUENTE` / `NOTAS` rows close the table.
"""

from __future__ import annotations

import csv
import io
import zipfile
from functools import lru_cache

import pandas as pd

from ggfiscal.debt.readers import snap_path

MONTHS_ES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
             "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}


@lru_cache(maxsize=None)
def be_table(table: str) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """(values: period-end timestamp x series code, meta: code -> {description,
    unit, frequency}) for one Boletín table, e.g. `be11b`."""
    with zipfile.ZipFile(snap_path("ESP_BDE_BE", "be_zip")) as z:
        text = z.read(f"{table}.csv").decode("latin-1")
    rows = list(csv.reader(io.StringIO(text)))
    codes = rows[0][1:]
    meta = {c: {"description": rows[3][i + 1], "unit": rows[4][i + 1],
                "frequency": rows[5][i + 1]} for i, c in enumerate(codes)}
    records, index = [], []
    for r in rows[6:]:
        if not r or r[0] in ("FUENTE", "NOTAS", ""):
            continue
        mon, _, year = r[0].partition(" ")
        if mon not in MONTHS_ES or not year.isdigit():
            raise ValueError(f"{table}: unexpected period label {r[0]!r}")
        index.append(pd.Timestamp(int(year), MONTHS_ES[mon], 1) + pd.offsets.MonthEnd(0))
        records.append([None if v in ("_", "") else float(v) for v in r[1:len(codes) + 1]])
    return pd.DataFrame(records, index=pd.DatetimeIndex(index), columns=codes), meta


def be_series(table: str, code: str) -> pd.Series:
    """One series of a Boletín table, in the table's own unit (chapter 11
    levels are thousand EUR), missing periods dropped."""
    values, meta = be_table(table)
    if code not in values.columns:
        raise KeyError(f"{table}: series {code} not in the table ({len(values.columns)} series)")
    s = values[code].dropna()
    s.attrs.update(meta[code])
    return s
