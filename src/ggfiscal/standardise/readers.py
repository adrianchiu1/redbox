"""Readers: latest raw snapshot per (source_id, part) -> tidy year/value series.

Stage 0 scope: enough standardisation to measure first/last usable year per
(country, line, source) and to compute the §8.2 base-year bridge. Full
standardise (all fields of the §5 data model) is Stage 1.

A "usable year" is a year with a parseable, non-missing numeric observation
(§7.12: zeros count as observations; missing stays missing).
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ggfiscal import config

ISO3_TO_GEO = {"FRA": "FR", "DEU": "DE"}


def latest_snapshots() -> dict[tuple[str, str], dict]:
    """Latest manifest entry per (source_id, part); verifies the file exists."""
    manifest = config.repo_root() / "data" / "manifest" / "snapshots.jsonl"
    out: dict[tuple[str, str], dict] = {}
    if not manifest.exists():
        return out
    with open(manifest, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            out[(e["source_id"], e.get("part", ""))] = e  # later lines win
    return {k: e for k, e in out.items()
            if (config.repo_root() / e["path"]).exists()}


def _snap_path(source_id: str, part: str) -> Path | None:
    e = latest_snapshots().get((source_id, part))
    return (config.repo_root() / e["path"]) if e else None


def _year_series(pairs) -> pd.Series:
    """(year, value) pairs -> float Series indexed by int year, NaNs dropped."""
    s = pd.Series(dict(pairs), dtype=float).dropna()
    s.index = s.index.astype(int)
    return s.sort_index()


# ---------- Eurostat (SDMX-CSV: freq,unit,sector[,cofog99],na_item,geo) ----------

@lru_cache(maxsize=None)
def _eurostat_frame(source_id: str, iso3: str) -> pd.DataFrame:
    path = _snap_path(source_id, iso3)
    if path is None:
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    return df


def eurostat_cofog(iso3: str, cofog: str) -> pd.Series:
    """gov_10a_exp: total expenditure (na_item TE) of one COFOG code, MIO_NAC."""
    df = _eurostat_frame("EUROSTAT_GOV10A_EXP", iso3)
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[(df["cofog99"] == cofog) & (df["na_item"] == "TE")]
    return _year_series(zip(sel["TIME_PERIOD"], sel["OBS_VALUE"]))


def eurostat_main(iso3: str, na_item: str) -> pd.Series:
    df = _eurostat_frame("EUROSTAT_GOV10A_MAIN", iso3)
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[df["na_item"] == na_item]
    return _year_series(zip(sel["TIME_PERIOD"], sel["OBS_VALUE"]))


def eurostat_taxag(iso3: str, na_item: str) -> pd.Series:
    df = _eurostat_frame("EUROSTAT_GOV10A_TAXAG", iso3)
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[df["na_item"] == na_item]
    return _year_series(zip(sel["TIME_PERIOD"], sel["OBS_VALUE"]))


def eurostat_gdp(iso3: str) -> pd.Series:
    df = _eurostat_frame("EUROSTAT_NAMA10_GDP", iso3)
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[df["na_item"] == "B1GQ"]
    return _year_series(zip(sel["TIME_PERIOD"], sel["OBS_VALUE"]))


# ---------- ONS ----------

@lru_cache(maxsize=None)
def ons_t11() -> pd.DataFrame:
    """ESA Table 11: one sheet per year; rows 'GFxx - label'; column OTE = total
    expenditure of the function, £m. Returns long frame (cofog, year, value)."""
    path = _snap_path("ONS_ESA_T11", "current")
    if path is None:
        return pd.DataFrame(columns=["cofog", "year", "value"])
    xf = pd.ExcelFile(path, engine="openpyxl")
    rows = []
    for sheet in xf.sheet_names:
        if not sheet.isdigit():
            continue
        df = xf.parse(sheet, header=None)
        codes = df.iloc[5].astype(str).tolist()  # row 5 = transaction codes
        try:
            ote_col = codes.index("OTE")
        except ValueError:
            continue
        for _, r in df.iloc[6:].iterrows():
            label = str(r.iloc[0])
            m = re.match(r"^(GF\d{2,4}|_T)\s*-", label)
            if not m:
                continue
            val = pd.to_numeric(r.iloc[ote_col], errors="coerce")
            if pd.notna(val):
                rows.append({"cofog": m.group(1), "year": int(sheet), "value": float(val)})
    return pd.DataFrame(rows)


def ons_cofog(cofog: str) -> pd.Series:
    df = ons_t11()
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[df["cofog"] == cofog]
    return _year_series(zip(sel["year"], sel["value"]))


@lru_cache(maxsize=None)
def ons_t2() -> pd.DataFrame:
    """ESA Table 2 S13 sheet: rows = transactions (code col 1, label col 0),
    year columns from col 4. Returns long frame (code, direction, label, year, value).
    Direction from the label. Sub-item rows can repeat a code ('of which' rows,
    sub-sector splits); ons_t2_series resolves each (code, direction) to its
    first — headline — label, while codes that only appear as 'of which' rows
    (P11, P12) still resolve."""
    path = _snap_path("ONS_GG_RECEIPTS", "current")
    if path is None:
        return pd.DataFrame(columns=["code", "direction", "label", "year", "value"])
    df = pd.read_excel(path, sheet_name="S13", engine="xlrd", header=None)
    years = {c: int(float(y)) for c, y in df.iloc[4].items()
             if isinstance(c, int) and c >= 4 and str(y).strip().replace(".0", "").isdigit()}
    rows = []
    for _, r in df.iloc[5:].iterrows():
        code, label = str(r.iloc[1]).strip(), str(r.iloc[0]).strip()
        if code in ("nan", ""):
            continue
        direction = ("receivable" if "receivable" in label.lower()
                     else "payable" if "payable" in label.lower() else "")
        for col, year in years.items():
            val = pd.to_numeric(r.iloc[col], errors="coerce")
            if pd.notna(val):
                rows.append({"code": code, "direction": direction, "label": label,
                             "year": year, "value": float(val)})
    return pd.DataFrame(rows)


def ons_t2_series(code: str, direction: str = "") -> pd.Series:
    df = ons_t2()
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[(df["code"] == code) & (df["direction"] == direction)]
    # a (code, direction) can still match several headline rows; take the first label
    if not sel.empty:
        sel = sel[sel["label"] == sel["label"].iloc[0]]
    return _year_series(zip(sel["year"], sel["value"]))


@lru_cache(maxsize=None)
def ons_tax_detail() -> pd.DataFrame:
    """ESA questionnaire table 9 (NTL) S13 sheet: rows = tax codes; the first
    row per code is the code total, component rows follow. Years from col 3."""
    path = _snap_path("ONS_TAX_DETAIL", "current")
    if path is None:
        return pd.DataFrame(columns=["code", "year", "value"])
    df = pd.read_excel(path, sheet_name="S13", engine="xlrd", header=None)
    years = {c: int(float(y)) for c, y in df.iloc[4].items()
             if isinstance(c, int) and c >= 3
             and re.fullmatch(r"\d{4}(\.0)?", str(y).strip())}
    rows, seen = [], set()
    for _, r in df.iloc[5:].iterrows():
        code = str(r.iloc[0]).strip()
        if code in ("nan", "") or code in seen:
            continue
        seen.add(code)  # first row per code = the total
        for col, year in years.items():
            val = pd.to_numeric(r.iloc[col], errors="coerce")
            if pd.notna(val):
                rows.append({"code": code, "year": year, "value": float(val)})
    return pd.DataFrame(rows)


def ons_tax_series(code: str) -> pd.Series:
    df = ons_tax_detail()
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[df["code"] == code]
    return _year_series(zip(sel["year"], sel["value"]))


def ons_gdp() -> pd.Series:
    """YBHA nominal GDP, £m, calendar years."""
    path = _snap_path("ONS_GDP", "ybha")
    if path is None:
        return pd.Series(dtype=float)
    d = json.loads(path.read_text(encoding="utf-8"))
    return _year_series((int(y["year"]), pd.to_numeric(y["value"], errors="coerce"))
                        for y in d.get("years", []))


# ---------- OECD ----------

@lru_cache(maxsize=None)
def _oecd_frame(source_id: str, iso3: str) -> pd.DataFrame:
    path = _snap_path(source_id, iso3)
    if path is None:
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    return df


def _to_millions(sel: pd.DataFrame) -> pd.Series:
    """OBS_VALUE scaled to LCU millions via UNIT_MULT (10^mult units)."""
    mult = pd.to_numeric(sel.get("UNIT_MULT"), errors="coerce").fillna(0)
    values = sel["OBS_VALUE"] * (10.0 ** (mult - 6))
    return _year_series(zip(sel["TIME_PERIOD"], values))


def oecd_t11_cofog(iso3: str, cofog: str) -> pd.Series:
    """DF_TABLE11, S13, nominal LCU millions, total expenditure OTE per function."""
    df = _oecd_frame("OECD_T11", iso3)
    if df.empty:
        return pd.Series(dtype=float)
    return _to_millions(df[(df["EXPENDITURE"] == cofog) & (df["TRANSACTION"] == "OTE")])


def oecd_rs_heading(iso3: str, heading: str) -> pd.Series:
    """DF_RSOECD, S13 (general government), LCU millions, one OECD tax heading."""
    df = _oecd_frame("OECD_RS", iso3)
    if df.empty:
        return pd.Series(dtype=float)
    return _to_millions(df[(df["STANDARD_REVENUE"] == heading) & (df["SECTOR"] == "S13")
                           & (df["UNIT_MEASURE"] == "XDC")])


# ---------- IMF ----------

@lru_cache(maxsize=None)
def _gfs_frame(part: str) -> pd.DataFrame:
    path = _snap_path("IMF_GFS", part)
    if path is None:
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    return df


def gfs_series(iso3: str, kind: str, indicator: str) -> pd.Series:
    """GFS_COFOG / GFS_SOO, S13, LCU millions (XDC values arrive in raw units)."""
    df = _gfs_frame(f"{kind}_{iso3}")
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[(df["INDICATOR"] == indicator) & (df["TYPE_OF_TRANSFORMATION"] == "XDC")]
    return _year_series(zip(sel["TIME_PERIOD"], sel["OBS_VALUE"] / 1e6))


@lru_cache(maxsize=None)
def weo_frame(vintage: str) -> pd.DataFrame:
    """One WEO vintage assembled from its per-(country, subject) snapshots:
    COUNTRY, INDICATOR, year, value (LCU), plus LATEST_ACTUAL_ANNUAL_DATA and
    PUBLICATION_DATE (the API serves these attributes on single-series pulls only)."""
    sid = f"IMF_WEO_{vintage.replace('-', '_')}"
    frames = []
    for (source_id, part), e in latest_snapshots().items():
        # per-series parts only ("GBR_NGDP"); earlier bulk pulls (part = the
        # vintage label) stay in the immutable store but lack the attributes
        if source_id != sid or not re.fullmatch(r"[A-Z]{3}_[A-Z]+", part):
            continue
        df = pd.read_csv(config.repo_root() / e["path"], dtype=str)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df["TIME_PERIOD"] = pd.to_numeric(df["TIME_PERIOD"], errors="coerce")
    return df


def weo_series(vintage: str, iso3: str, indicator: str) -> pd.Series:
    df = weo_frame(vintage)
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[(df["COUNTRY"] == iso3) & (df["INDICATOR"] == indicator)].dropna(
        subset=["TIME_PERIOD"])
    return _year_series(zip(sel["TIME_PERIOD"].astype(int), sel["OBS_VALUE"]))


def weo_latest_actual(vintage: str, iso3: str, indicator: str) -> int | None:
    df = weo_frame(vintage)
    if df.empty or "LATEST_ACTUAL_ANNUAL_DATA" not in df.columns:
        return None
    sel = df[(df["COUNTRY"] == iso3) & (df["INDICATOR"] == indicator)]
    vals = pd.to_numeric(sel["LATEST_ACTUAL_ANNUAL_DATA"], errors="coerce").dropna()
    return int(vals.iloc[0]) if len(vals) else None


# ---------- Stage 3 forecast sources ----------

AR_CC = {"FRA": "FR", "DEU": "DE"}  # Ageing Report / DSM sheet codes


@lru_cache(maxsize=None)
def _ar_fiche_sheet(sheet: str) -> pd.DataFrame:
    path = _snap_path("EC_AGEING_2024", "country_fiches")
    if path is None:
        return pd.DataFrame()
    return pd.read_excel(path, sheet_name=sheet, engine="openpyxl", header=None)


_YEAR_RE = re.compile(r"(19|20)\d{2}(\.0)?$")


def _year_columns(row: pd.Series) -> dict[int, int]:
    """Column index -> year for every cell matching a 4-digit year."""
    return {j: int(float(str(v).strip())) for j, v in row.items()
            if isinstance(j, int) and _YEAR_RE.fullmatch(str(v).strip())}


def _first_label(row: pd.Series, max_col: int = 7) -> tuple[int, str]:
    """(column, text) of the first non-empty, non-numeric cell in a row."""
    for j, v in row.items():
        if not isinstance(j, int) or j > max_col:
            break
        s = str(v).strip()
        if s and s != "nan" and not _YEAR_RE.fullmatch(s):
            return j, s
    return -1, ""


def _ar_section_series(df: pd.DataFrame, section_prefix: str, row_label: str) -> pd.Series:
    """AR fiche layout: a section header row carries the section title, a
    'Ch 22-70'/'AVG 22-70' cell, then annual year columns 2022-2070; data rows
    below carry the row label in the title column. Column positions vary by
    sheet, so both are located by content. The first matching row after the
    matching section header wins (scenario blocks repeat titles with a
    '- (diff...)' suffix, which the exact title match excludes)."""
    years: dict[int, int] = {}
    label_col = 1
    in_section = False
    for i in range(len(df)):
        row = df.iloc[i]
        if any(str(v).strip() in ("Ch 22-70", "AVG 22-70") for v in row[:8]):
            col, title = _first_label(row)
            # scenario blocks repeat the title with a '- (diff. ...)' suffix
            in_section = title.startswith(section_prefix) and "diff" not in title
            if in_section:
                years = _year_columns(row)
                label_col = col
            continue
        if in_section and str(row.iloc[label_col]).strip() == row_label:
            vals = {}
            for j, y in years.items():
                v = pd.to_numeric(row.iloc[j], errors="coerce")
                if pd.notna(v):
                    vals[y] = float(v)
            return pd.Series(vals).sort_index()
    return pd.Series(dtype=float)


AR_ITEMS = {  # item -> (fiche sheet suffix, section header prefix, row label)
    "pensions": ("b", "Baseline as % of GDP", "Public pensions, gross"),
    "health": ("c", "Health care spending as % of GDP", "Baseline"),
    "ltc": ("c", "Long-term care spending as % of GDP", "Baseline"),
    "education": ("c", "Education spending as % of GDP", "Baseline"),
    "potential_gdp_growth": ("a", "Macroeconomic assumptions", "Potential GDP (growth rate)"),
    "hicp_growth": ("a", "Macroeconomic assumptions", "HICP (growth rate)"),
}


def ar_series(iso3: str, item: str) -> pd.Series:
    """2024 Ageing Report country-fiche series: expenditure items as % of GDP,
    assumptions as growth rates (%), annual 2022-2070."""
    cc = AR_CC.get(iso3)
    if cc is None:
        return pd.Series(dtype=float)
    suffix, section, label = AR_ITEMS[item]
    return _ar_section_series(_ar_fiche_sheet(cc + suffix), section, label)


def ar_nominal_gdp_growth(iso3: str) -> pd.Series:
    """§7.5: AR nominal GDP growth factors constructed from the AR's own
    real-growth (potential GDP) and price (HICP) assumptions."""
    real = ar_series(iso3, "potential_gdp_growth")
    price = ar_series(iso3, "hicp_growth")
    common = real.index.intersection(price.index)
    return ((1 + real[common] / 100) * (1 + price[common] / 100)).sort_index()


@lru_cache(maxsize=None)
def _dsm_sheet(iso3: str) -> pd.DataFrame:
    path = _snap_path("EC_DSM", "country_fiches_2025")
    cc = AR_CC.get(iso3)
    if path is None or cc is None:
        return pd.DataFrame()
    return pd.read_excel(path, sheet_name=cc, engine="openpyxl", header=None)


def dsm_series(iso3: str, row_label: str) -> pd.Series:
    """DSM 2025 country fiche: annual years (2024-2036) come from the nearest
    preceding header row ('... - baseline scenario ...' / '1. Baseline');
    row labels sit in the same column as the header title. Expenditure rows
    are % of GDP; assumption rows are growth rates (%). The first match after
    a header wins (later scenario blocks repeat the assumption labels)."""
    df = _dsm_sheet(iso3)
    if df.empty:
        return pd.Series(dtype=float)
    years: dict[int, int] = {}
    label_col = 3
    for i in range(len(df)):
        row = df.iloc[i]
        cand_years = _year_columns(row)
        if len(cand_years) >= 5:
            # the header title cell ('... baseline scenario ...' / '1. Baseline')
            # sits in the same column as the row labels below it; a scenario
            # key ('BASELINE') can precede it, so the rightmost match wins
            matches = [j for j, v in row.items()
                       if isinstance(j, int) and j <= 7 and "baseline" in str(v).lower()]
            if matches:
                years = cand_years
                label_col = matches[-1]
            continue
        if years and str(row.iloc[label_col]).strip() == row_label:
            vals = {}
            for j, y in years.items():
                v = pd.to_numeric(row.iloc[j], errors="coerce")
                if pd.notna(v):
                    vals[y] = float(v)
            return pd.Series(vals).sort_index()
    return pd.Series(dtype=float)


def dsm_nominal_gdp_growth(iso3: str) -> pd.Series:
    """DSM baseline nominal GDP growth factors from its own real growth and
    inflation (GDP deflator proxy) assumption rows (§7.5)."""
    real = dsm_series(iso3, "Real GDP growth")
    price = dsm_series(iso3, "Inflation rate")
    common = real.index.intersection(price.index)
    return ((1 + real[common] / 100) * (1 + price[common] / 100)).sort_index()


@lru_cache(maxsize=None)
def _steuerschaetzung_tab(sheet: str) -> dict[str, pd.Series]:
    """One Steuerschätzung tab -> {row label: series}. Layout: a year header
    row ('2024', '2025', ... under Ist/Schätzung), then labelled rows; labels
    repeat in the 'vH gegenüber Vorjahr' block — the first occurrence (levels,
    Mio EUR) wins."""
    path = _snap_path("DEU_STEUERSCHAETZUNG", "2026_05")
    if path is None:
        return {}
    df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl", header=None)
    years: dict[int, int] = {}
    rows: dict[str, pd.Series] = {}
    for i in range(len(df)):
        cells = df.iloc[i]
        if not years:
            cand = {j: str(v).strip() for j, v in cells.items()
                    if isinstance(j, int) and j >= 1 and str(v) != "nan"}
            if cand and re.fullmatch(r"2024(\.0)?", next(iter(cand.values()), "")):
                years = {j: int(float(v)) for j, v in cand.items()
                         if re.fullmatch(r"\d{4}(\.0)?", v)}
            continue
        label = str(cells.iloc[0]).strip()
        if label in ("nan", "") or label in rows:
            continue
        vals = {}
        for j, y in years.items():
            v = pd.to_numeric(cells.iloc[j], errors="coerce")
            if pd.notna(v):
                vals[y] = float(v)
        if vals:
            rows[label] = pd.Series(vals).sort_index()
    return rows


def steuerschaetzung_series(sheet: str, label: str) -> pd.Series:
    return _steuerschaetzung_tab(sheet).get(label, pd.Series(dtype=float))


def steuerschaetzung_gdp() -> pd.Series:
    """Tab 1 'BIP, nominal (Mrd. €)' -> EUR millions."""
    return steuerschaetzung_series("Tab 1", "BIP, nominal (Mrd. €)") * 1000.0


# ---------- AMECO ----------

@lru_cache(maxsize=None)
def _ameco_frame(chapter: int) -> pd.DataFrame:
    path = _snap_path("EC_AMECO", f"chapter{chapter}")
    if path is None:
        return pd.DataFrame()
    z = zipfile.ZipFile(path)
    name = z.namelist()[0]
    text = z.read(name).decode("latin-1")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    header = next(reader)
    years = [int(h) for h in header[5:] if h.strip().isdigit()]
    rows = []
    for rec in reader:
        if len(rec) < 6:
            continue
        code = rec[0].strip()
        for year, raw in zip(years, rec[5:5 + len(years)]):
            val = pd.to_numeric(raw.strip(), errors="coerce")
            if pd.notna(val):
                rows.append({"code": code, "year": year, "value": float(val)})
    return pd.DataFrame(rows)


def ameco_series(iso3: str, variable: str, chapter: int) -> pd.Series:
    """AMECO code pattern {ISO3}.1.0.0.0.{VARIABLE} ('standard aggregation')."""
    df = _ameco_frame(chapter)
    if df.empty:
        return pd.Series(dtype=float)
    sel = df[df["code"] == f"{iso3}.1.0.0.0.{variable}"]
    return _year_series(zip(sel["year"], sel["value"]))
