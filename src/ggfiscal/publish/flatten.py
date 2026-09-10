"""The plain-flat-file bundle: `deliverables/`.

The canonical layer (`data/canonical/`) is complete but wide — 47 columns
per observation, split across strict/maximum variants and a dozen
reconciliation tables at three different grains. This module renders the
same numbers, with nothing dropped that a reader needs and nothing added
that the pipeline did not measure, as flat files a person can open in a
spreadsheet:

    deliverables/expenditure_cofog.csv    12 COFOG lines + TE per country
    deliverables/revenue_esa.csv          10 ESA lines + TR per country
    deliverables/balance_ledger.csv       TR, TE, NLB, NI, PB per country-year
    deliverables/weo_levels_bridge.csv    our levels vs the WEO aggregates
    deliverables/weo_reconciliation.csv   history + forecast dynamics vs WEO
    deliverables/series_catalogue.csv     one row per published series
    deliverables/data_dictionary.csv      every column of every file above
    deliverables/strict_{GBR,FRA,DEU}.csv every series for one country,
                                          strict only, years down and series
                                          across

Two properties are deliberate. (1) No new numbers: every value is copied
from `data/canonical/`, never recomputed, so the bundle cannot drift from
the gated pipeline. (2) Self-describing rows: each observation carries a
`derivation` sentence that states the exact arithmetic behind it, in the
Gate 6 form `value(t) = value(t±1) x growth`, so a reader can reproduce
any stitched or forecast value from the flat file alone (D13/D16: the
residuals are reported, never allocated).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ggfiscal import config

COUNTRY_NAME = {"GBR": "United Kingdom", "FRA": "France", "DEU": "Germany"}

# Observation types that carry their own value (no growth chaining).
ANCHOR_TYPES = {"anchor_actual", "derived_actual", "level2_proxy_actual"}

OBS_LABEL = {
    "anchor_actual": "anchor outturn",
    "derived_actual": "derived by identity",
    "level2_proxy_actual": "anchor outturn on the D10 fallback concept",
    "stitched_actual": "stitch",
    "direct_forecast": "official forecast",
    "proxy_forecast": "proxy forecast",
    "composite_forecast": "composite forecast",
}

TREE_COLUMNS = [
    "iso3", "country", "variant", "line_code", "line_label", "line_level",
    "year", "basis", "value_lcu_mn", "currency", "pct_gdp", "pct_total",
    "gdp_lcu_mn", "observation_type", "quality_grade", "source_id",
    "anchor_source", "anchor_year", "anchor_value", "growth_source_id",
    "growth_rate", "residual_method", "coverage_share", "crosswalk_version",
    "derivation", "notes",
]


def _out_dir() -> Path:
    d = config.repo_root() / "deliverables"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _canonical(name: str) -> pd.DataFrame:
    """Read a canonical CSV without losing a bit. The default float parser
    trades an ULP for speed, and an ULP lost on every republication would
    make the bundle drift away from the layer it copies."""
    return pd.read_csv(config.repo_root() / "data" / "canonical" / name,
                       float_precision="round_trip")


def _num(x, fmt: str = "{:,.1f}") -> str:
    return "—" if pd.isna(x) else fmt.format(x)


# --------------------------------------------------------------------- trees

def _obs_label(observation_type: str, year, anchor_year) -> str:
    """Display name of how a row was made. `stitched_actual` covers both
    directions — backwards before the anchor, forwards for an outturn year
    the anchor has not yet published — so the direction is spelled out."""
    base = OBS_LABEL.get(observation_type, observation_type)
    if observation_type == "stitched_actual" and pd.notna(anchor_year):
        return f"{'backward' if year < anchor_year else 'forward'} {base}"
    return base


def _derivation(r: pd.Series) -> str:
    """One sentence per observation, stating the arithmetic that produced it.

    Anchor rows name the publisher. Every other row states the Gate 6
    recurrence explicitly — the neighbouring year's value times the growth
    factor recorded on the same row — plus the anchor the chain runs from,
    the measured coverage of the growth source, and the residual assumption
    where the maximum-extension variant carries one.
    """
    label = _obs_label(r.observation_type, r.year, r.anchor_year)
    if r.observation_type in ANCHOR_TYPES:
        head = f"{label}: {r.source_id} publishes {_num(r.value_lcu_mn)} for {int(r.year)}"
        if r.observation_type == "derived_actual":
            head = (f"{label}: {_num(r.value_lcu_mn)} = GF01 - GF01_7 in {int(r.year)}, "
                    f"both from {r.source_id}")
        return head
    back = r.year < r.anchor_year
    neighbour = int(r.year) + 1 if back else int(r.year) - 1
    parts = [
        f"{label}: value({int(r.year)}) = value({neighbour}) x {r.growth_rate:.6f} "
        f"({r.growth_source_id} growth), chained {'backwards' if back else 'forwards'} "
        f"from the {int(r.anchor_year)} anchor {_num(r.anchor_value)} ({r.anchor_source})"
    ]
    if pd.notna(r.coverage_share):
        yr = "" if pd.isna(r.coverage_share_year) else f" at {int(r.coverage_share_year)}"
        parts.append(f"growth source covers {r.coverage_share:.1%} of the line{yr}")
    if pd.notna(r.crosswalk_version):
        parts.append(f"crosswalk {r.crosswalk_version}")
    if pd.notna(r.residual_method):
        parts.append(f"uncovered remainder: {r.residual_method} (D2)")
    if pd.notna(r.period_conversion_method):
        parts.append(f"period conversion {r.period_conversion_method} (§7.10)")
    parts.append(f"grade {r.quality_grade}")
    return "; ".join(parts)


def _flat_tree(stem: str) -> pd.DataFrame:
    frames = []
    for variant in ("strict", "maximum_extension"):
        df = _canonical(f"{stem}_{variant}.csv").copy()
        df["variant"] = variant
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["country"] = df.iso3.map(COUNTRY_NAME)
    df["basis"] = df.is_forecast.map({True: "forecast", False: "actual"})
    df["derivation"] = df.apply(_derivation, axis=1)
    # Years are years, not measurements: keep them integral in the CSV so a
    # reader is not shown "1,995.00" for an anchor year.
    df["anchor_year"] = df.anchor_year.astype("Int64")
    out = df[TREE_COLUMNS].sort_values(
        ["iso3", "variant", "line_code", "year"], kind="stable")
    return out.reset_index(drop=True)


# -------------------------------------------------------------------- ledger

def _gdp_lookup(trees: list[pd.DataFrame]) -> pd.DataFrame:
    gdp = pd.concat([t[["iso3", "year", "gdp_lcu_mn"]] for t in trees])
    gdp = gdp.dropna().drop_duplicates(subset=["iso3", "year"])
    return gdp


def _flat_ledger(gdp: pd.DataFrame, currency: dict[str, str]) -> pd.DataFrame:
    led = _canonical("balance_ledger.csv").rename(
        columns={"series_variant": "variant"})
    led["country"] = led.iso3.map(COUNTRY_NAME)
    led["currency"] = led.iso3.map(currency)
    led = led.merge(gdp, on=["iso3", "year"], how="left")
    for col in ("tr", "te", "nlb", "ni", "pb"):
        led[f"{col}_pct_gdp"] = 100.0 * led[f"{col}_lcu_mn"] / led.gdp_lcu_mn
    led["identity_check_lcu_mn"] = (
        led.tr_lcu_mn - led.te_lcu_mn - led.nlb_lcu_mn)
    led["basis"] = "actual"
    led["derivation"] = (
        "TR and TE as published by " + led.source_id
        + "; NLB = TR - TE (B.9, cross-checked against the anchor's own B.9 in "
          "b9_anchor_lcu_mn); NI = GF01_7 - R07 from the two trees; PB = NLB + NI. "
          "Outturn years only: the ledger is never built from partially covered "
          "forecast lines (§4.3).")
    cols = ["iso3", "country", "variant", "year", "basis", "currency",
            "tr_lcu_mn", "te_lcu_mn", "nlb_lcu_mn", "ni_lcu_mn", "pb_lcu_mn",
            "b9_anchor_lcu_mn", "gdp_lcu_mn",
            "tr_pct_gdp", "te_pct_gdp", "nlb_pct_gdp", "ni_pct_gdp",
            "pb_pct_gdp", "identity_check_lcu_mn", "complete_both_sides",
            "source_id", "derivation"]
    return led[cols].sort_values(["iso3", "variant", "year"],
                                 kind="stable").reset_index(drop=True)


# ------------------------------------------------------------ WEO: levels

def _flat_levels_bridge() -> pd.DataFrame:
    br = _canonical("weo_base_bridge.csv").rename(columns={
        "tr_anchor_mn": "tr_ours_mn", "ggr_weo_mn": "tr_weo_mn",
        "te_anchor_mn": "te_ours_mn", "ggx_weo_mn": "te_weo_mn",
        "nlb_anchor_mn": "nlb_ours_mn", "ggxcnl_weo_mn": "nlb_weo_mn",
        "gdp_anchor_mn": "gdp_ours_mn", "ngdp_weo_mn": "gdp_weo_mn",
    })
    br["block"] = "history"
    br["variant"] = "both"
    base = (br[br.is_base_year].groupby(["iso3", "weo_vintage"]).year
            .max().rename("base_year"))
    br = br.merge(base, on=["iso3", "weo_vintage"], how="left")
    br["base_year"] = br.base_year.astype("Int64")
    br["derivation"] = (
        "§8.2 level bridge: our ledger (from the national anchor) beside the "
        "WEO aggregate for the same year and vintage; gap = ours - WEO, "
        "classified in gap_classification. Gaps are reported, never removed "
        "(D13/D16).")

    ni = _canonical("net_interest_check.csv").rename(columns={
        "series_variant": "variant", "horizon_year": "year",
        "gap_mn": "gap_ni_mn"})
    ni["block"] = "forecast_horizon"
    ni["is_base_year"] = False
    ni["gap_classification"] = None
    ni["derivation"] = (
        "§8.4 net-interest cross-check: our forward NI (GF01_7 - R07 on the "
        "published forecast legs) beside the WEO's implied net interest "
        "(GGXCNL - GGXONLB) at the same horizon. Blank ni_ours_mn means one "
        "leg has no forecast anywhere — reported as a hole, not filled.")

    br = br.rename(columns={"classification": "gap_classification"})
    cols = ["iso3", "country", "block", "variant", "weo_vintage", "base_year",
            "year", "is_base_year",
            "tr_ours_mn", "tr_weo_mn", "gap_tr_mn",
            "te_ours_mn", "te_weo_mn", "gap_te_mn",
            "nlb_ours_mn", "nlb_weo_mn", "gap_nlb_mn",
            "ni_ours_mn", "ni_weo_mn", "gap_ni_mn",
            "gdp_ours_mn", "gdp_weo_mn", "gap_gdp_mn",
            "gap_tr_pct_te", "gap_te_pct_te", "gap_nlb_pct_te",
            "gap_gdp_pct_gdp", "gf01_7_mn", "r07_mn",
            "gap_classification", "derivation", "notes"]
    out = pd.concat([br, ni], ignore_index=True)
    out["country"] = out.iso3.map(COUNTRY_NAME)
    for c in cols:
        if c not in out.columns:
            out[c] = None
    return out[cols].sort_values(
        ["iso3", "block", "weo_vintage", "variant", "year"],
        kind="stable").reset_index(drop=True)


# ----------------------------------------------------------- WEO: dynamics

HIST_MEMO = {
    "NLB_CHANGE_SUM": "the change in the sum-based balance, "
                      "d((sum R - sum E)/GDP) — equal to the sum of that "
                      "year's line contributions exactly (V26)",
    "ANCHOR_B9_DELTA": "the anchor's own change in B.9/GDP MINUS the "
                       "sum-based change: a rounding and vintage wedge, "
                       "reported and never allocated to lines (D16)",
    "WEO_GGXCNL_DELTA": "the IMF WEO's own change in GGXCNL/NGDP over the "
                        "same year — the history-side comparison with the "
                        "WEO (§8.3)",
}

LINE_CODE = re.compile(r"^(GF|R)\d\d$")

FORECAST_COMPONENT = {
    "covered_line": "one published forecast line's contribution to the change "
                    "in NLB/GDP from the base year",
    "covered_total": "sum of the covered-line contributions on that side",
    "weo_change": "the WEO's own change in NLB/GDP over the same span — the "
                  "quantity being explained",
    "weo_internal_wedge": "WEO-internal inconsistency between GGR-GGX and "
                          "GGXCNL at that horizon",
    "denom_effect": "effect of the GDP denominator path on the ratio",
    "resid_coverage": "part of the change attributable to lines with no "
                      "published forecast (a coverage hole, never allocated)",
    "resid_disagreement": "part attributable to covered lines moving "
                          "differently from the WEO aggregate",
    "resid_total": "coverage + disagreement, where the two cannot be split",
    "explained_share": "covered contributions as a share of the WEO change "
                       "(1.0 = fully explained by official granular forecasts)",
    "implied_uncovered_growth": "growth the uncovered remainder would need to "
                                "close the residual",
    "historical_uncovered_growth": "the same remainder's realised historical "
                                   "growth, for comparison",
}


def _flat_reconciliation() -> pd.DataFrame:
    hist = _canonical("deficit_dynamics.csv").rename(
        columns={"series_variant": "variant", "kind": "side"})
    hist["block"] = "history"
    hist["weo_vintage"] = None
    hist["base_year"] = hist.year - 1
    is_line = hist.line_code.map(lambda c: bool(LINE_CODE.match(str(c))))
    unknown = set(hist.loc[~is_line, "line_code"]) - set(HIST_MEMO)
    if unknown:
        raise ValueError(f"undocumented history components: {sorted(unknown)}")
    hist["component"] = hist.line_code.where(~is_line, "covered_line")
    hist.loc[~is_line, "line_code"] = None
    hist["measure"] = "pp of GDP, change on the previous year"
    hist["component_meaning"] = hist.component.map(
        lambda c: HIST_MEMO.get(c, "one line's contribution to the year's "
                                   "change in NLB/GDP"))

    fc = _canonical("weo_explanation.csv").rename(columns={
        "series_variant": "variant", "horizon_year": "year",
        "component_kind": "component"})
    fc["block"] = "forecast"
    fc["measure"] = fc.component.map(
        lambda c: "share (0-1)" if c == "explained_share"
        else "growth factor" if c.endswith("_growth")
        else "pp of GDP, change since the base year")
    fc["component_meaning"] = fc.component.map(FORECAST_COMPONENT)

    cols = ["iso3", "country", "block", "variant", "weo_vintage", "base_year",
            "year", "side", "component", "line_code", "contribution_pp",
            "measure", "component_meaning", "notes"]
    out = pd.concat([hist, fc], ignore_index=True)
    out["country"] = out.iso3.map(COUNTRY_NAME)
    out["base_year"] = out.base_year.astype("Int64")
    for c in cols:
        if c not in out.columns:
            out[c] = None
    return out[cols].sort_values(
        ["iso3", "block", "variant", "weo_vintage", "year", "side",
         "component", "line_code"], kind="stable").reset_index(drop=True)


# ---------------------------------------------------------------- catalogue

def _recipe(g: pd.DataFrame) -> str:
    """Compact construction history of one series: the ordered segments of
    (observation type, source), each with its year span and grade."""
    g = g.sort_values("year")
    labels = [_obs_label(ot, yr, ay) for ot, yr, ay
              in zip(g.observation_type, g.year, g.anchor_year)]
    key = list(zip(labels, g.source_id.fillna("—"), g.quality_grade.fillna("—")))
    segs: list[list] = []
    for (label, src, grade), yr in zip(key, g.year):
        if segs and tuple(segs[-1][:3]) == (label, src, grade):
            segs[-1][4] = yr
        else:
            segs.append([label, src, grade, yr, yr])
    parts = []
    for label, src, grade, y0, y1 in segs:
        span = f"{y0}" if y0 == y1 else f"{y0}-{y1}"
        parts.append(f"{span}: {label} ({src}, grade {grade})")
    return " | ".join(parts)


def _flat_catalogue(exp: pd.DataFrame, rev: pd.DataFrame) -> pd.DataFrame:
    tree = pd.concat([exp, rev], ignore_index=True)
    cov = _canonical("coverage_matrix.csv")
    decl = _canonical("forecast_declarations.csv")
    rows = []
    for (iso3, line), g in tree.groupby(["iso3", "line_code"], sort=False):
        strict = g[g.variant == "strict"]
        mx = g[g.variant == "maximum_extension"]
        actual = g[g.basis == "actual"]
        rows.append({
            "iso3": iso3,
            "country": COUNTRY_NAME[iso3],
            "line_code": line,
            "line_label": g.line_label.iloc[0],
            "line_level": g.line_level.iloc[0],
            "classification": "COFOG" if line.startswith(("GF", "TE")) else "ESA_REV",
            "currency": g.currency.iloc[0],
            "first_year": int(g.year.min()),
            "final_actual_year": int(actual.year.max()) if len(actual) else None,
            "final_strict_year": int(strict.year.max()) if len(strict) else None,
            "final_maximum_year": int(mx.year.max()) if len(mx) else None,
            "n_observations_strict": int(len(strict)),
            "n_observations_maximum": int(len(mx)),
            "grades": "".join(sorted(g.quality_grade.dropna().unique())),
            "sources": "+".join(sorted(g.source_id.dropna().unique())),
            "recipe_strict": _recipe(strict) if len(strict) else "",
            "recipe_maximum_extension": _recipe(mx) if len(mx) else "",
        })
    cat = pd.DataFrame(rows)
    keep = ["iso3", "line_code", "stitch_count", "principal_sources",
            "residual_method", "reason_series_ends"]
    cat = cat.merge(cov[keep], on=["iso3", "line_code"], how="left")
    cat = cat.merge(decl.rename(columns={"status": "forecast_status",
                                         "note": "forecast_note"})[
        ["iso3", "line_code", "forecast_status", "forecast_note"]],
        on=["iso3", "line_code"], how="left")
    return cat.sort_values(["iso3", "classification", "line_code"],
                           kind="stable").reset_index(drop=True)


# ------------------------------------------------- per-country strict matrix

# The balance ledger's TR and TE are the balance anchor's own totals, not the
# COFOG/ESA trees' TE and TR — for GBR they come from a different ONS table
# and differ by up to 0.5%. Prefixed so one wide file can carry both without
# the collision passing unnoticed.
LEDGER_COLUMNS = [
    ("LEDGER_TR", "tr_lcu_mn", "Total revenue (balance anchor)"),
    ("LEDGER_TE", "te_lcu_mn", "Total expenditure (balance anchor)"),
    ("NLB", "nlb_lcu_mn", "Net lending (+) / net borrowing (-)"),
    ("NI", "ni_lcu_mn", "Net interest (GF01_7 - R07)"),
    ("PB", "pb_lcu_mn", "Primary balance (NLB + NI)"),
]
GDP_COLUMN = ("GDP", "Gross domestic product at current market prices")


def _column_name(code: str, label: str) -> str:
    return f"{code} - {label}"


def _country_columns(exp: pd.DataFrame, rev: pd.DataFrame,
                     iso3: str) -> list[tuple[str, str]]:
    """(code, label) for every series the chartbook plots, in chart order."""
    out = [GDP_COLUMN]
    for tree in (exp, rev):
        g = tree[(tree.iso3 == iso3) & (tree.variant == "strict")]
        seen = g[["line_code", "line_label"]].drop_duplicates()
        out += [(r.line_code, r.line_label) for r in seen.itertuples()]
    out += [(code, label) for code, _, label in LEDGER_COLUMNS]
    return out


def _country_strict(exp: pd.DataFrame, rev: pd.DataFrame,
                    ledger: pd.DataFrame, iso3: str) -> pd.DataFrame:
    """One country, strict variant only, one column per series and one row
    per year — the shape you model with rather than the shape the pipeline
    stores. maximum_extension is excluded entirely: every value here comes
    from an official published source (§7, D13).
    """
    frames = {}
    for tree in (exp, rev):
        g = tree[(tree.iso3 == iso3) & (tree.variant == "strict")]
        for code, sub in g.groupby("line_code", sort=False):
            label = sub.line_label.iloc[0]
            frames[_column_name(code, label)] = sub.set_index("year").value_lcu_mn
        if "GDP" not in frames:
            gdp = g.dropna(subset=["gdp_lcu_mn"]).drop_duplicates("year")
            frames[_column_name(*GDP_COLUMN)] = gdp.set_index("year").gdp_lcu_mn

    led = ledger[(ledger.iso3 == iso3) & (ledger.variant == "strict")]
    for code, source, label in LEDGER_COLUMNS:
        frames[_column_name(code, label)] = led.set_index("year")[source]

    wide = pd.DataFrame(frames)
    order = [_column_name(c, l) for c, l in _country_columns(exp, rev, iso3)]
    wide = wide.reindex(columns=order)
    wide = wide.reindex(range(int(wide.index.min()), int(wide.index.max()) + 1))
    wide.index.name = "year"
    return wide.reset_index()


# ---------------------------------------------------------------- dictionary

_SHARED = {
    "iso3": "Country (GBR, FRA, DEU).",
    "country": "Country name, for readability.",
    "variant": "strict = official published sources only; maximum_extension = "
               "strict plus proxy, composite and partial-coverage legs, each "
               "with a declared residual assumption. maximum_extension always "
               "contains strict and equals it wherever both exist; it adds "
               "years at either end — a longer backward leg as well as a "
               "longer forecast. Pick one; never mix them in a series.",
    "line_code": "Series code. COFOG: GF01-GF10 (Level I), GF01_7 (Level II "
                 "interest), GF01_X (GF01 - GF01_7), TE (total expenditure). "
                 "ESA revenue: R01-R10, TR (total revenue).",
    "line_label": "Human-readable name of the line.",
    "line_level": "1 = COFOG Level I / ESA line; 2 = COFOG Level II; derived = "
                  "identity; total = TE or TR.",
    "year": "Calendar year. Sources on a fiscal year are converted first "
            "(§7.10) and flagged in derivation.",
    "basis": "actual = outturn (or an outturn-based backward stitch); "
             "forecast = projection.",
    "value_lcu_mn": "Value in millions of national currency, current prices, "
                    "general government, consolidated.",
    "currency": "GBP for GBR, EUR for FRA and DEU.",
    "notes": "The concept caveat recorded with the observation at build time.",
    "derivation": "Plain-language statement of the exact arithmetic behind the "
                  "row.",
    "source_id": "Publisher of the value (or of the growth applied).",
}

# Columns of the per-country files that need saying more than their label.
_COUNTRY_COLUMN_NOTE = {
    "GDP": "Gross domestic product at current market prices, from the "
           "country's registered GDP source. Divide by it for ratios.",
    "GF01_X": "General public services excluding interest (GF01_X): the "
              "identity GF01 - GF01_7, never forecast (D10).",
    "TE": "Total expenditure (TE) from the COFOG tree's expenditure anchor. "
          "Not the same series as LEDGER_TE — see that column.",
    "TR": "Total revenue (TR) from the ESA tree's revenue anchor. Not the "
          "same series as LEDGER_TR — see that column.",
    "LEDGER_TR": "Total revenue as published by the balance anchor. For GBR "
                 "this is a different ONS table from the TR column and the "
                 "two differ by up to ~0.5%; for FRA/DEU they agree to "
                 "rounding. Outturn years only.",
    "LEDGER_TE": "Total expenditure as published by the balance anchor. Same "
                 "caveat as LEDGER_TR against the TE column.",
    "NLB": "Net lending (+) / net borrowing (-) = LEDGER_TR - LEDGER_TE "
           "(ESA B.9). Outturn years only.",
    "NI": "Net interest = GF01_7 - R07. Blank where one leg has no value.",
    "PB": "Primary balance = NLB + NI. Outturn years only.",
}

DICTIONARY: list[tuple[str, str, str]] = []


def _dict_rows(fname: str, pairs: dict[str, str]) -> None:
    for col, desc in pairs.items():
        DICTIONARY.append((fname, col, desc))


def _build_dictionary(country_columns: dict[str, list[tuple[str, str]]]
                      ) -> pd.DataFrame:
    DICTIONARY.clear()
    tree_cols = {
        **{k: _SHARED[k] for k in ("iso3", "country", "variant", "line_code",
                                   "line_label", "line_level", "year", "basis",
                                   "value_lcu_mn", "currency")},
        "pct_gdp": "value_lcu_mn as a percentage of that country-year's GDP "
                   "(gdp_lcu_mn).",
        "pct_total": "value_lcu_mn as a percentage of the same year's total "
                     "(TE for COFOG lines, TR for revenue lines).",
        "gdp_lcu_mn": "GDP at current market prices, same currency and year, "
                      "from the country's registered GDP source.",
        "observation_type": "anchor_actual | derived_actual | "
                            "level2_proxy_actual | stitched_actual | "
                            "direct_forecast | proxy_forecast | "
                            "composite_forecast.",
        "quality_grade": "A = the anchor's own published value; B = a "
                         "conceptually equivalent official series; C = an "
                         "official series covering only part of the line; "
                         "D = a proxy with a declared residual assumption.",
        "source_id": _SHARED["source_id"],
        "anchor_source": "Publisher of the anchor the chain runs from.",
        "anchor_year": "Year of that anchor.",
        "anchor_value": "Value of that anchor, in value_lcu_mn units. It is "
                        "itself a row of this file.",
        "growth_source_id": "Publisher of the growth factor applied "
                            "(blank on anchor rows).",
        "growth_rate": "Growth factor applied at this year. Reproduce the "
                       "value as value(year) = value(neighbour) * growth_rate, "
                       "where neighbour is year+1 when year < anchor_year and "
                       "year-1 otherwise.",
        "residual_method": "Declared treatment of the part of the line the "
                           "growth source does not cover (maximum_extension "
                           "only).",
        "coverage_share": "Measured share of the line the growth source "
                          "covers, at coverage_share_year, on overlapping "
                          "data. This is measured, not assumed.",
        "crosswalk_version": "Version of the source-to-line mapping used "
                             "(files in crosswalks/).",
        "derivation": _SHARED["derivation"],
        "notes": _SHARED["notes"],
    }
    _dict_rows("expenditure_cofog.csv", tree_cols)
    _dict_rows("revenue_esa.csv", tree_cols)
    _dict_rows("balance_ledger.csv", {
        **{k: _SHARED[k] for k in ("iso3", "country", "variant", "year",
                                   "basis", "currency")},
        "tr_lcu_mn": "Total revenue, as published by the balance anchor.",
        "te_lcu_mn": "Total expenditure, as published by the balance anchor.",
        "nlb_lcu_mn": "Net lending (+) / net borrowing (-) = TR - TE (ESA B.9).",
        "ni_lcu_mn": "Net interest = GF01_7 (interest payable) - R07 "
                     "(interest receivable), from the two trees.",
        "pb_lcu_mn": "Primary balance = NLB + NI.",
        "b9_anchor_lcu_mn": "The anchor's own published B.9, for cross-check "
                            "against nlb_lcu_mn.",
        "gdp_lcu_mn": "GDP at current market prices.",
        "tr_pct_gdp": "TR as a percentage of GDP.",
        "te_pct_gdp": "TE as a percentage of GDP.",
        "nlb_pct_gdp": "NLB as a percentage of GDP.",
        "ni_pct_gdp": "NI as a percentage of GDP.",
        "pb_pct_gdp": "PB as a percentage of GDP.",
        "identity_check_lcu_mn": "TR - TE - NLB. Zero by construction; "
                                 "published so the identity is checkable.",
        "complete_both_sides": "True when both interest legs exist, so NI and "
                               "PB are defined.",
        "source_id": "Publisher of TR, TE and B.9.",
        "derivation": _SHARED["derivation"],
    })
    _dict_rows("weo_levels_bridge.csv", {
        **{k: _SHARED[k] for k in ("iso3", "country", "year")},
        "block": "history = overlap years, our ledger vs the WEO aggregates "
                 "(§8.2); forecast_horizon = the net-interest cross-check at "
                 "projection horizons (§8.4).",
        "variant": "both on history rows (the ledger is variant-independent "
                   "over history); strict / maximum_extension on forecast "
                   "rows.",
        "weo_vintage": "WEO edition the comparison uses (e.g. 2026-04).",
        "base_year": "Last year the WEO reports as an outturn for that country "
                     "and vintage — the year the forecast decomposition "
                     "starts from.",
        "is_base_year": "True on that base year.",
        "tr_ours_mn": "Our total revenue.",
        "tr_weo_mn": "WEO general-government revenue, GGR.",
        "gap_tr_mn": "tr_ours_mn - tr_weo_mn.",
        "te_ours_mn": "Our total expenditure.",
        "te_weo_mn": "WEO general-government expenditure, GGX.",
        "gap_te_mn": "te_ours_mn - te_weo_mn.",
        "nlb_ours_mn": "Our net lending/borrowing.",
        "nlb_weo_mn": "WEO net lending/borrowing, GGXCNL.",
        "gap_nlb_mn": "nlb_ours_mn - nlb_weo_mn.",
        "ni_ours_mn": "Our net interest (GF01_7 - R07); blank where a leg has "
                      "no value at that horizon.",
        "ni_weo_mn": "WEO net interest, GGXCNL - GGXONLB.",
        "gap_ni_mn": "ni_ours_mn - ni_weo_mn.",
        "gdp_ours_mn": "GDP from the country's registered source.",
        "gdp_weo_mn": "WEO nominal GDP, NGDP.",
        "gap_gdp_mn": "gdp_ours_mn - gdp_weo_mn.",
        "gap_tr_pct_te": "gap_tr_mn as a percentage of our TE.",
        "gap_te_pct_te": "gap_te_mn as a percentage of our TE.",
        "gap_nlb_pct_te": "gap_nlb_mn as a percentage of our TE.",
        "gap_gdp_pct_gdp": "gap_gdp_mn as a percentage of our GDP.",
        "gf01_7_mn": "Interest payable behind ni_ours_mn (forecast rows).",
        "r07_mn": "Interest receivable behind ni_ours_mn (forecast rows).",
        "gap_classification": "perimeter = a stable definitional difference; "
                              "revision = a vintage difference; unexplained = "
                              "neither, and flagged for review.",
        "derivation": _SHARED["derivation"],
        "notes": _SHARED["notes"],
    })
    _dict_rows("weo_reconciliation.csv", {
        **{k: _SHARED[k] for k in ("iso3", "country", "variant", "year",
                                   "line_code", "notes")},
        "block": "history = year-on-year decomposition of our own realised "
                 "change in NLB/GDP; forecast = decomposition of the WEO's "
                 "projected change from base_year to year.",
        "weo_vintage": "WEO edition (forecast rows only).",
        "base_year": "Year the change is measured from (previous year on "
                     "history rows; the WEO base year on forecast rows).",
        "side": "revenue | expenditure | balance | total | memo.",
        "component": "What the row is: covered_line for a published line, or "
                     "one of the reconciliation components named in "
                     "component_meaning.",
        "contribution_pp": "Contribution in percentage points of GDP, signed "
                           "so that contributions sum to the change in "
                           "NLB/GDP. Units differ for explained_share and the "
                           "growth components — see measure.",
        "measure": "Unit of contribution_pp on that row.",
        "component_meaning": "Plain-language meaning of component.",
    })
    _dict_rows("series_catalogue.csv", {
        **{k: _SHARED[k] for k in ("iso3", "country", "line_code",
                                   "line_label", "line_level", "currency")},
        "classification": "COFOG or ESA_REV.",
        "first_year": "First year published for the series.",
        "final_actual_year": "Last outturn year.",
        "final_strict_year": "Last year of the strict variant.",
        "final_maximum_year": "Last year of the maximum_extension variant.",
        "n_observations_strict": "Row count of the strict variant.",
        "n_observations_maximum": "Row count of the maximum_extension variant.",
        "grades": "Distinct quality grades appearing in the series.",
        "sources": "Every source_id appearing in the series.",
        "recipe_strict": "Ordered construction segments of the strict "
                         "variant: year span, how the segment was made, "
                         "source, grade.",
        "recipe_maximum_extension": "The same for maximum_extension.",
        "stitch_count": "Number of stitch boundaries in the series.",
        "principal_sources": "Sources named in the coverage matrix.",
        "residual_method": "Residual assumption where the series carries one.",
        "reason_series_ends": "Why the series stops where it does.",
        "forecast_status": "Recorded status when no strict forecast exists.",
        "forecast_note": "Why, in words.",
    })
    _dict_rows("data_dictionary.csv", {
        "file": "Flat file the column belongs to.",
        "column": "Name of the column, as it appears in that file's header.",
        "description": "What the column holds.",
    })
    for name, columns in country_columns.items():
        _dict_rows(name, {
            "year": "Calendar year. One row per year from the country's "
                    "first published year to the last year any strict "
                    "series reaches.",
            **{_column_name(code, label): _COUNTRY_COLUMN_NOTE.get(
                code, f"{label} ({code}), strict variant, millions of "
                      "national currency.")
               for code, label in columns},
        })
    return pd.DataFrame(DICTIONARY, columns=["file", "column", "description"])


# -------------------------------------------------------------------- README

def _readme(files: dict[str, pd.DataFrame], run_id: str) -> str:
    # No wall clock in the header: the run id already identifies the build,
    # and a timestamp would make an unchanged bundle look changed on every
    # re-render (§16 — unchanged inputs, byte-identical outputs).
    rows = "\n".join(
        f"| `{name}` | {len(df):,} | {len(df.columns)} | {DESCRIPTIONS[name]} |"
        for name, df in files.items())
    return f"""# deliverables/ — the flat-file bundle

<!-- GENERATED by `ggfiscal flatten` from run {run_id}. Do not hand-edit. -->

Everything the project produces, as flat CSVs: for the United Kingdom,
France and Germany, general-government **expenditure by COFOG function**
(12 lines per country including the GF01_7 / GF01_X interest split),
**revenue by ESA type** (10 lines per country), the **balance ledger**
(TR, TE, NLB, NI, PB), and the **reconciliation of history and forecast
dynamics to the IMF WEO** general-government aggregates.

| file | rows | columns | contents |
|---|---|---|---|
{rows}

Start with `data_dictionary.csv` (every column of every file) and
`series_catalogue.csv` (one row per published series: span, grades,
sources, and the ordered recipe that built it). Two notebooks read this
bundle and nothing else:
[`notebooks/derivation.ipynb`](../notebooks/derivation.ipynb) walks
through how each series was derived and reproduces the arithmetic, and
[`notebooks/chartbook.ipynb`](../notebooks/chartbook.ipynb) plots every
series one chart at a time — seams and projection years marked — plus
our totals against the IMF WEO.

## Reading the files

```python
import pandas as pd
exp = pd.read_csv("deliverables/expenditure_cofog.csv")
uk  = exp.query("iso3 == 'GBR' and variant == 'strict'")
uk.pivot_table(index="year", columns="line_code", values="pct_gdp")
```

Three things to know before using the numbers:

1. **Two variants.** `strict` uses official published sources only.
   `maximum_extension` adds proxy, composite and partial-coverage legs,
   each with a declared residual assumption. It always contains `strict`
   and equals it wherever both exist, adding years at either end — a
   longer backward leg as well as a longer forecast. Pick one variant;
   never mix them in a single series.
2. **Every row states its own derivation.** Anchor rows name the
   publisher. Stitched and forecast rows record the recurrence
   `value(year) = value(neighbour) * growth_rate`, so any value is
   reproducible from this file alone.
3. **Residuals are reported, never allocated.** No line is scaled to hit a
   WEO aggregate. Where official forecasts do not cover a line, the gap
   appears as a residual in `weo_reconciliation.csv` rather than being
   filled in.

The three `strict_*.csv` files are the modelling shape: one country per
file, one column per series, one row per year, and **nothing but the
strict variant** — no proxy, composite or partial-coverage leg, so every
number in them comes from an official published source. Where a series has
no official forecast the column simply stops; the ragged right-hand edge
is the coverage, not a gap in the file.

Regenerate with `ggfiscal flatten` after any `build` / `reconcile`; the
bundle copies the gated canonical layer and never recomputes a value.
"""


DESCRIPTIONS = {
    "expenditure_cofog.csv":
        "COFOG expenditure: 12 lines + TE per country, both variants, one row "
        "per country-variant-line-year",
    "revenue_esa.csv":
        "ESA revenue: 10 lines + TR per country, both variants, same shape",
    "balance_ledger.csv":
        "TR, TE, NLB, NI, PB per country-year in levels and % of GDP",
    "weo_levels_bridge.csv":
        "our levels beside the IMF WEO aggregates, with the gap classified "
        "(§8.2) and the forward net-interest cross-check (§8.4)",
    "weo_reconciliation.csv":
        "dynamics: the year-on-year history decomposition and the "
        "forecast decomposition of the WEO balance change, with residuals",
    "series_catalogue.csv":
        "one row per published series: span, grades, sources, the recipe that "
        "built it, and why it ends",
    "data_dictionary.csv":
        "every column of every file above, described",
    **{f"strict_{iso3}.csv":
       f"{name}, strict variant only: one column per series, one row per "
       "year — the same series the chartbook plots, in the shape you model "
       "with"
       for iso3, name in COUNTRY_NAME.items()},
}


# ---------------------------------------------------------------------- main

def write() -> dict[str, Path]:
    """Render `deliverables/` from the canonical layer. Returns {name: path}."""
    from ggfiscal import manifest as M

    dest = _out_dir()
    currency = {iso3: cfg["currency"] for iso3, cfg in config.countries().items()}

    exp = _flat_tree("expenditure_long")
    rev = _flat_tree("revenue_long")
    gdp = _gdp_lookup([exp, rev])
    ledger = _flat_ledger(gdp, currency)
    countries = {f"strict_{iso3}.csv": _country_strict(exp, rev, ledger, iso3)
                 for iso3 in COUNTRY_NAME}
    country_columns = {f"strict_{iso3}.csv": _country_columns(exp, rev, iso3)
                       for iso3 in COUNTRY_NAME}
    # The debt extension's tables join the bundle verbatim (DEBT_KICKOFF.md
    # DD12): files, dictionary rows and README descriptions come from
    # ggfiscal.debt.flatten and are absent when the debt layer is not built.
    from ggfiscal.debt.flatten import bundle as debt_bundle
    debt_files, debt_dict, debt_desc = debt_bundle()
    DESCRIPTIONS.update(debt_desc)
    dictionary = _build_dictionary(country_columns)
    if debt_dict:
        dictionary = pd.concat([dictionary, pd.DataFrame(debt_dict, columns=dictionary.columns)],
                               ignore_index=True)
    files = {
        "expenditure_cofog.csv": exp,
        "revenue_esa.csv": rev,
        "balance_ledger.csv": ledger,
        "weo_levels_bridge.csv": _flat_levels_bridge(),
        "weo_reconciliation.csv": _flat_reconciliation(),
        "series_catalogue.csv": _flat_catalogue(exp, rev),
        **countries,
        **debt_files,
        "data_dictionary.csv": dictionary,
    }
    written: dict[str, Path] = {}
    for name, df in files.items():
        path = dest / name
        df.to_csv(path, index=False)
        written[name] = path

    run = M.latest_run_path()
    import json
    run_id = json.loads(run.read_text())["run_id"] if run else "—"
    readme = dest / "README.md"
    readme.write_text(_readme(files, run_id), encoding="utf-8")
    written["README.md"] = readme
    M.update_flat_files()
    return written
