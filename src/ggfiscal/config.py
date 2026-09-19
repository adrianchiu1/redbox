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


# The three published trees (D-S13-001): classification -> lines.yaml key and
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


def level2_lines(classification: str) -> dict[str, dict]:
    """The Level II lines of a tree: code -> meta (with `parent`)."""
    return {c: m for c, m in tree_lines(classification).items()
            if str(m.get("level")) == "2"}


def level2_splits(classification: str | None = None) -> list[dict]:
    """Every parent that carries Level II lines, with its derived remainder
    (D10: GF01_7/GF01_X; D-S13-002: GF10_2/GF10_X; D-S13-005: GF10_5,
    GF04_5, R02_A, R06_E/R06_H). One dict per parent: classification,
    parent, level2s (ordered codes), remainder, and per-Level II meta
    (anchor cell, GFS indicator, OECD RS heading, D10 fallback). The
    remainder is `parent - Σ level2s`, never forecast. Enumerated from
    lines.yaml so a further group is config only."""
    out = []
    for cls in (TREES if classification is None else [classification]):
        tree = tree_lines(cls)
        l2 = level2_lines(cls)
        parents = list(dict.fromkeys(m["parent"] for m in l2.values()))
        for parent in parents:
            codes = [c for c, m in l2.items() if m["parent"] == parent]
            remainder = next(c for c, m in tree.items()
                             if m.get("level") == "derived" and m.get("parent") == parent)
            minus = tree[remainder].get("minus")
            minus = [minus] if isinstance(minus, str) else list(minus)
            if set(minus) != set(codes):
                raise ValueError(f"{remainder}.minus {minus} != Level II lines {codes}")
            out.append({"classification": cls, "parent": parent, "level2s": codes,
                        "remainder": remainder,
                        "meta": {c: {"eurostat_cofog": l2[c].get("eurostat_cofog"),
                                     "gfs_indicator": l2[c].get("gfs_indicator"),
                                     "eurostat": l2[c].get("eurostat"),
                                     "ons": l2[c].get("ons"),
                                     "oecd_rs": l2[c].get("oecd_rs"),
                                     "fallback": l2[c].get("fallback"),
                                     "grade_on_fallback": l2[c].get("grade_on_fallback", "B")}
                                 for c in codes}})
    return out


def line_universe() -> list[tuple[str, str, str]]:
    """The (iso3, classification, line_code) series of §1 (D-S13-001): per
    country, the COFOG lines (Level I, the Level II splits and their
    remainders), the ESA_EXP economic lines and the ESA_REV lines. Totals
    (TE, TE_ESA, TR) and ledger quantities are not members."""
    out = []
    for iso3 in COUNTRIES:
        for classification in TREES:
            out += [(iso3, classification, c) for c in granular_lines(classification)]
    return out


def universe_size() -> int:
    """len(line_universe()) — the number §1 once fixed at 66 (D-S13-001)."""
    return len(line_universe())
