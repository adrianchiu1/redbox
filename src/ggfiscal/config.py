"""Load and interrogate the config/ spec files."""

from __future__ import annotations

import functools
from pathlib import Path

import yaml


def __getattr__(name: str):
    """`config.COUNTRIES` — the country list, read from config/countries.yaml
    in file order (D27, D-S15-001). Lazy (PEP 562) so importing the package
    outside a checkout still works; every routing site iterates this."""
    if name == "COUNTRIES":
        return tuple(countries())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


def country(iso3: str) -> dict:
    """One country's block of countries.yaml; a clear error for a country
    that is not configured (never a fall-through to another country)."""
    try:
        return countries()[iso3]
    except KeyError:
        raise KeyError(f"country {iso3!r} is not configured in config/countries.yaml "
                       f"(configured: {', '.join(countries())})") from None


def country_names() -> dict[str, str]:
    """iso3 -> display name (the one COUNTRY_NAME map, D-S15-001)."""
    return {iso3: cfg["name"] for iso3, cfg in countries().items()}


def prose_names() -> dict[str, str]:
    """iso3 -> the name as prose joins it ("the United Kingdom")."""
    return {iso3: cfg.get("prose_name", cfg["name"]) for iso3, cfg in countries().items()}


def country_aliases() -> dict[str, tuple[str, ...]]:
    """iso3 -> the strings a chart title may use for the country."""
    return {iso3: tuple(cfg.get("aliases") or [cfg["name"]]) for iso3, cfg in countries().items()}


def currencies() -> list[str]:
    """The set of currencies the schema admits (§5: read from config)."""
    return list(dict.fromkeys(cfg["currency"] for cfg in countries().values()))


def lines_absent(iso3: str) -> dict[str, str]:
    """D20: line_code -> reason for every line the anchor institution defines
    as identically zero for this country (published as structural_zero rows;
    empty for GBR/FRA/DEU)."""
    return dict(country(iso3).get("lines_absent") or {})


def absent_lines(iso3: str) -> dict[tuple[str, str], str]:
    """lines_absent resolved to (classification, line_code) -> reason. Every
    declared code must be a granular line of one tree (a total or an unknown
    code is a config error, raised here)."""
    out = {}
    for code, reason in lines_absent(iso3).items():
        cls = [c for c in TREES if code in granular_lines(c)]
        if len(cls) != 1:
            raise ValueError(f"{iso3}: lines_absent entry {code!r} is not a granular line "
                             f"of exactly one tree (found in {cls})")
        out[(cls[0], code)] = str(reason)
    return out


def fy_to_cy_weights(iso3: str) -> tuple[float, float]:
    """§7.10 conversion weights [FY t-1/t, FY t/t+1] for the country's
    fiscal-year sources (0.25/0.75 April–March; 0.75/0.25 October–September)."""
    w = country(iso3).get("fy_to_cy_weights")
    if not w or len(w) != 2 or abs(sum(w) - 1.0) > 1e-9:
        raise ValueError(f"{iso3}: fy_to_cy_weights must be two weights summing to 1, got {w!r}")
    return float(w[0]), float(w[1])


def perimeter_break(iso3: str) -> int | None:
    """§7.12 / §14: the year below which no line of this country is extended
    (DEU 1991, reunification); None where there is no break."""
    b = country(iso3).get("perimeter_break")
    return int(b) if b is not None else None


def backward_legs(iso3: str) -> dict:
    """R0 step 6: the generic backward legs enabled for the country
    (`backward_legs` in countries.yaml): `gfs_cofog` (IMF GFS COFOG Level I
    and Level II group series, with the country's concept notes) and
    `gfs_soo` (IMF GFS SOO items of the ESA_EXP lines). Empty = none."""
    return dict(country(iso3).get("backward_legs") or {})


def weo_perimeter_gap_expected(iso3: str) -> bool:
    """§8.2 / V24: True where the anchor perimeter differs from the WEO's
    (GBR: public sector vs general government), so the NLB gap is classified
    by its stability rather than its size."""
    return bool(country(iso3).get("weo_perimeter_gap_expected", False))


def period_basis(iso3: str) -> dict:
    """D19: {anchor: CY|FY, trees: {expenditure|expenditure_esa|revenue: CY|FY},
    fy_start_month, fy_label} — every tree CY unless the country says otherwise."""
    pb = dict(country(iso3).get("period_basis") or {})
    pb.setdefault("anchor", "CY")
    pb["trees"] = {**{key: "CY" for key in TREES.values()}, **(pb.get("trees") or {})}
    return pb


def source_period_basis(source_id: str) -> str:
    """The register's period basis of a source (`period_basis` in
    sources.yaml; CY unless declared FY). R0: the build stamps every row
    with its tree's published basis; V42 uses this to police §7.14 (no
    CY-basis source chained onto a FY-labelled tree, and a FY-basis source
    enters a CY tree only converted per §7.10)."""
    basis = (sources().get(source_id) or {}).get("period_basis", "CY")
    if basis not in ("CY", "FY"):
        raise ValueError(f"{source_id}: period_basis must be CY or FY, got {basis!r}")
    return basis


def fy_label(iso3: str, year: int, classification: str) -> str:
    """native_period label of a row: the calendar year on a CY tree; on a
    FY-labelled tree `FY{start_year}` (D19: fy_label = start_year)."""
    if tree_period_basis(iso3, classification) == "FY":
        return f"FY{int(year)}"
    return str(int(year))


def tree_period_basis(iso3: str, classification: str) -> str:
    """The published basis of one tree for one country (CY or FY)."""
    basis = period_basis(iso3)["trees"][TREES[classification]]
    if basis not in ("CY", "FY"):
        raise ValueError(f"{iso3}/{classification}: period basis must be CY or FY, got {basis!r}")
    return basis


def family(iso3: str):
    """The country's anchor family (kickoff §11.3, D27): the object every
    routing site asks for a reader. Raises standardise.families.
    FamilyNotConfigured for an unconfigured or unimplemented family."""
    from ggfiscal.standardise.families import for_country

    return for_country(iso3)


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
    for iso3 in countries():
        for classification in TREES:
            out += [(iso3, classification, c) for c in granular_lines(classification)]
    return out


def universe_size() -> int:
    """len(line_universe()) — the number §1 once fixed at 66 (D-S13-001)."""
    return len(line_universe())
