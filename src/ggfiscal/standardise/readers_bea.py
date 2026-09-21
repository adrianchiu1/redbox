"""BEA NIPA flat-file reader — the United States' secondary national source
(REPLICATION_KICKOFF.md D18 rank-2 secondary, D26 Level II proxies, §7.16
backward legs; Stage U0, D-S16-003).

`apps.bea.gov/national/Release/TXT/` publishes every NIPA table as three
flat files: `SeriesRegister.txt` (series code -> label, metric, scale and
the `TableId:LineNo` cells the series occupies), `NipaDataA.txt` (annual
values per series code, 1929-) and `NipaDataQ.txt` (quarterly). The BEA
API needs a registered key and is not used (§14). Lookup is
register-driven: a cell is addressed as (table id, line number), e.g.
Table 3.16 line 5 = `T31600:5` = interest payments, total government.

This is an ordinary reader module used by the coverage, Level II and (later)
backward code — not an anchor family (§11.3): NIPA "current expenditures"
(Table 3.16) is not the ESA total-expenditure concept (CFC in, investment
out; §14), so its cells enter as `level2_proxy_actual` (D26) and as growth
legs (§7.16), never as anchor values.

Units: "Current Dollars, Level" series carry DefaultScale -6, i.e. the file
values are USD millions already (A001RC 1929 = 105,322 = USD 105.3 bn GNP).
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache

import pandas as pd

from ggfiscal.standardise.readers import _snap_path, _year_series

SOURCE_ID = "BEA_NIPA"
PART_REGISTER = "register"
PART_ANNUAL = "annual"

# Table 3.16 (government current expenditures by function) and 3.17
# (selected current and capital expenditures by function): the total-
# government block of each table, as line numbers of the register.
T316 = "T31600"
T317 = "T31700"


def _text(part: str) -> list[str]:
    path = _snap_path(SOURCE_ID, part)
    if path is None:
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


@lru_cache(maxsize=None)
def register() -> pd.DataFrame:
    """One row per (series_code, table_id, line_no): series_code, label,
    metric, calc, scale, table_id, line_no, parents. Empty when the register
    snapshot is absent."""
    lines = _text(PART_REGISTER)
    rows = []
    for rec in csv.reader(lines):
        if not rec or rec[0].startswith("%") or len(rec) < 6:
            continue
        code, label, metric, calc, scale, cells = rec[:6]
        parents = rec[6] if len(rec) > 6 else ""
        for cell in cells.split("|"):
            if ":" not in cell:
                continue
            table, line = cell.split(":", 1)
            if not line.isdigit():
                continue
            rows.append({"series_code": code, "label": label, "metric": metric,
                         "calc": calc, "scale": int(scale) if re.fullmatch(r"-?\d+", scale) else 0,
                         "table_id": table, "line_no": int(line), "parents": parents})
    return pd.DataFrame(rows, columns=["series_code", "label", "metric", "calc", "scale",
                                       "table_id", "line_no", "parents"])


@lru_cache(maxsize=None)
def annual() -> pd.DataFrame:
    """NipaDataA.txt as (series_code, year, value) with the thousands
    separators removed; values as published (USD millions for the
    `Current Dollars, Level` series)."""
    path = _snap_path(SOURCE_ID, PART_ANNUAL)
    if path is None:
        return pd.DataFrame(columns=["series_code", "year", "value"])
    df = pd.read_csv(path, names=["series_code", "year", "value"], skiprows=1,
                     dtype={"series_code": str, "year": str, "value": str},
                     thousands=",", quotechar='"')
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"].astype(str).str.replace(",", "", regex=False),
                                errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    return df


def cell(table_id: str, line_no: int) -> dict | None:
    """The register row of one table cell (series code, label, metric)."""
    reg = register()
    if reg.empty:
        return None
    sel = reg[(reg.table_id == table_id) & (reg.line_no == int(line_no))
              & (reg.metric == "Current Dollars") & (reg.calc == "Level")]
    if sel.empty:
        sel = reg[(reg.table_id == table_id) & (reg.line_no == int(line_no))]
    if sel.empty:
        return None
    return sel.iloc[0].to_dict()


def series_by_code(code: str) -> pd.Series:
    """Annual values of one series code, USD millions, indexed by year."""
    df = annual()
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[df.series_code == code]
    return _year_series(zip(sel["year"], sel["value"]))


def nipa_series(table_id: str, line_no: int) -> pd.Series:
    """Annual values of one table cell (register-driven), USD millions."""
    c = cell(table_id, line_no)
    if c is None:
        return pd.Series(dtype=float)
    return series_by_code(c["series_code"])


def nipa_label(table_id: str, line_no: int) -> str:
    c = cell(table_id, line_no)
    return "" if c is None else f"{c['series_code']} {c['label']}"


def cell_series(spec: dict) -> pd.Series:
    """Sum of the cells of one lines.yaml `bea_nipa` spec:
    {table, lines: [..], plus: [{table, lines}, ...]} — the first cell sets
    the year set, later cells add where present (a component published for
    fewer years cannot shorten the line)."""
    parts = [nipa_series(spec["table"], n) for n in spec.get("lines", [])]
    for extra in spec.get("plus", []) or []:
        parts += [nipa_series(extra["table"], n) for n in extra.get("lines", [])]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.Series(dtype=float)
    total = parts[0].copy()
    for p in parts[1:]:
        total = total.add(p.reindex(total.index, fill_value=0.0), fill_value=0.0)
    return total.dropna().sort_index()


def level2_proxy(line_code: str, spec: dict) -> tuple[pd.Series, str]:
    """(series, concept note) of a COFOG Level II line's D26 proxy from its
    `bea_nipa` cells: NIPA Table 3.16 sub-function lines (current
    expenditures, total government), plus any Table 3.17 cells the spec
    names. The note names every cell by its register label."""
    labels = [nipa_label(spec["table"], n) for n in spec.get("lines", [])]
    for extra in spec.get("plus", []) or []:
        labels += [nipa_label(extra["table"], n) for n in extra.get("lines", [])]
    table = spec["table"]
    cells = [f"{table}:{n}" for n in spec.get("lines", [])]
    cells += [f"{e['table']}:{n}" for e in (spec.get("plus") or []) for n in e.get("lines", [])]
    label_txt = "; ".join(l for l in labels if l)
    note = (f"D26 Level II proxy for {line_code}: NIPA {' + '.join(cells)} ({label_txt})"
            + (f"; {spec['note']}" if spec.get("note") else ""))
    return cell_series(spec), note
