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
    return _load("sources")["sources"]


def no_forecast_lines() -> dict:
    return _load("sources")["no_forecast_lines"]


def line_universe() -> list[tuple[str, str, str]]:
    """The 66 (iso3, classification, line_code) series of §1: per country,
    12 COFOG lines (GF01..GF10, GF01_7, GF01_X) + 10 ESA_REV lines (R01..R10).
    TE/TR/ledger quantities are totals, not members of the 66."""
    cfg = lines()
    exp = [c for c in cfg["expenditure"] if c != "TE"]
    rev = [c for c in cfg["revenue"] if c != "TR"]
    out = []
    for iso3 in COUNTRIES:
        out += [(iso3, "COFOG", c) for c in exp]
        out += [(iso3, "ESA_REV", c) for c in rev]
    return out
