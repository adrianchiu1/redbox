"""Load and interrogate the config/ spec files."""

from __future__ import annotations

import functools
from pathlib import Path

import yaml

COUNTRIES = ("GBR", "FRA", "DEU")


def repo_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for candidate in (p, *p.parents):
        if (candidate / "COFOG_KICKOFF.md").exists() and (candidate / "config").is_dir():
            return candidate
    raise FileNotFoundError("repo root not found (no COFOG_KICKOFF.md + config/ above cwd)")


@functools.lru_cache(maxsize=None)
def _load(name: str) -> dict:
    path = repo_root() / "config" / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def countries() -> dict:
    return _load("countries")["countries"]


def tolerances() -> dict:
    return _load("countries")["tolerances"]


def lines() -> dict:
    return _load("lines")


def sources() -> dict:
    """The parent register plus the debt-extension register
    (`config/debt_sources.yaml`, DD12) — one mapping, so source_register.csv
    and detect-vintages cover both."""
    merged = dict(_load("sources")["sources"])
    debt_path = repo_root() / "config" / "debt_sources.yaml"
    if debt_path.exists():
        for sid, src in (_load("debt_sources").get("sources") or {}).items():
            if sid in merged:
                raise ValueError(f"source_id {sid} defined in both sources.yaml and debt_sources.yaml")
            merged[sid] = src
    return merged


def debt() -> dict:
    """DEBT_KICKOFF.md configuration (perimeter, taxonomy, buckets, chains)."""
    return _load("debt")


def debt_sources() -> dict:
    return _load("debt_sources").get("sources") or {}


def no_forecast_lines() -> dict:
    return _load("sources")["no_forecast_lines"]


def residual_method(iso3: str, line_code: str) -> str:
    """D2/§15 Q3: residual_method per (iso3, line_code) for maximum_extension
    proxies — the Q3 default unless config/residual.yaml overrides it."""
    cfg = _load("residual")
    return ((cfg.get("overrides") or {}).get(iso3) or {}).get(
        line_code, cfg.get("default", "grow_with_proxy"))


# The three published trees (D-S11-001): classification -> lines.yaml key and
# canonical file stem. Order is publication order (expenditure by function,
# expenditure by economic type, revenue by type).
TREES = {"COFOG": "expenditure", "ESA_EXP": "expenditure_esa", "ESA_REV": "revenue"}
STEMS = {"COFOG": "expenditure_long", "ESA_EXP": "expenditure_esa_long",
         "ESA_REV": "revenue_long"}


def tree_lines(classification: str) -> dict:
    """Line definitions of one tree, totals included."""
    return lines()[TREES[classification]]


def is_total(meta: dict) -> bool:
    return meta.get("level") == "total" or meta.get("esa") == "total"


def total_code(classification: str) -> str:
    """The tree's own total line (TE, TE_ESA, TR)."""
    return next(c for c, m in tree_lines(classification).items() if is_total(m))


def granular_lines(classification: str) -> list[str]:
    """Every line of the tree except its total."""
    return [c for c, m in tree_lines(classification).items() if not is_total(m)]


def level1_lines(classification: str) -> list[str]:
    """The lines that sum to the tree's total (V2/V22): Level I for COFOG,
    every non-total line for the ESA trees."""
    return [c for c, m in tree_lines(classification).items()
            if not is_total(m) and str(m.get("level", "1")) == "1"]


def level2_splits() -> list[dict]:
    """Every COFOG Level II line with its parent and derived remainder
    (GF01_7/GF01_X per D10; GF10_2/GF10_X per D-S11-002): one dict per
    split — parent, level2, remainder, eurostat_cofog, gfs_indicator,
    fallback. Enumerated from lines.yaml so a further group is config only."""
    exp = lines()["expenditure"]
    out = []
    for code, meta in exp.items():
        if str(meta.get("level")) != "2":
            continue
        parent = meta["parent"]
        remainder = next(c for c, m in exp.items()
                         if m.get("level") == "derived" and m.get("parent") == parent
                         and m.get("minus") == code)
        out.append({"parent": parent, "level2": code, "remainder": remainder,
                    "eurostat_cofog": meta["eurostat_cofog"],
                    "gfs_indicator": meta.get("gfs_indicator"),
                    "fallback": meta.get("fallback"),
                    "grade_on_fallback": meta.get("grade_on_fallback", "B")})
    return out


def line_universe() -> list[tuple[str, str, str]]:
    """The (iso3, classification, line_code) series of §1 (D-S11-001): per
    country, the COFOG lines (Level I, the Level II splits and their
    remainders), the ESA_EXP economic lines and the ESA_REV lines. Totals
    (TE, TE_ESA, TR) and ledger quantities are not members."""
    out = []
    for iso3 in COUNTRIES:
        for classification in TREES:
            out += [(iso3, classification, c) for c in granular_lines(classification)]
    return out


def universe_size() -> int:
    """len(line_universe()) — the number §1 once fixed at 66 (D-S11-001)."""
    return len(line_universe())
