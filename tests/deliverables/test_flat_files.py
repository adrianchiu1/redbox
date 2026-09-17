"""The flat-file bundle and the derivation notebook.

Two things are being defended here. First, that `deliverables/` is a faithful
rendering of the gated canonical layer — same values, nothing lost, nothing
invented — so the simple files can be trusted as much as the wide ones.
Second, that the bundle is self-describing: every column documented, every
published series catalogued, and every chained value reproducible from the
flat file alone (the Gate 6 property, re-proved on the simplified shape).
"""

import json
import re

import pandas as pd
import pytest

from ggfiscal import config, manifest as M
from ggfiscal.publish import flatten
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")

ROOT = config.repo_root()
DELIV = ROOT / "deliverables"
CANONICAL = ROOT / "data" / "canonical"
VARIANTS = ("strict", "maximum_extension")


@pytest.fixture(scope="module", autouse=True)
def bundle():
    """Render the bundle once, from whatever the canonical layer holds now."""
    flatten.write()


def read(name: str) -> pd.DataFrame:
    # round_trip so a fidelity comparison is bit-exact, not ULP-approximate
    return pd.read_csv(DELIV / name, float_precision="round_trip")


def canonical(name: str) -> pd.DataFrame:
    return pd.read_csv(CANONICAL / name, float_precision="round_trip")


# ------------------------------------------------------------- completeness

def test_every_flat_file_is_written_and_populated():
    for rel in M.FLAT_FILES:
        path = ROOT / rel
        assert path.exists(), rel
        assert path.stat().st_size > 0, rel
        if path.suffix == ".csv":
            assert len(pd.read_csv(path)) > 0, rel


def test_run_manifest_pins_the_bundle():
    doc = json.loads(M.latest_run_path().read_text(encoding="utf-8"))
    assert set(doc["flat_files"]) == set(M.FLAT_FILES)
    for rel, entry in doc["flat_files"].items():
        assert entry["present"], rel
        assert entry["sha256"]
    # the §11.6 deliverable set is untouched by the bundle
    assert set(doc["deliverables"]) == set(M.DELIVERABLES)


# ---------------------------------------------------- fidelity to canonical

@pytest.mark.parametrize("flat,stem", [("expenditure_cofog.csv", "expenditure_long"),
                                       ("revenue_esa.csv", "revenue_long")])
def test_trees_carry_every_canonical_row_and_value_unchanged(flat, stem):
    got = read(flat)
    want = pd.concat([canonical(f"{stem}_{v}.csv").assign(variant=v)
                      for v in VARIANTS], ignore_index=True)
    assert len(got) == len(want)
    key = ["iso3", "variant", "line_code", "year"]
    assert not got.duplicated(key).any()
    merged = want.merge(got, on=key, suffixes=("_c", "_f"), validate="1:1")
    assert len(merged) == len(want)
    pd.testing.assert_series_equal(merged.value_lcu_mn_c, merged.value_lcu_mn_f,
                                   check_names=False)
    for col in ("pct_gdp", "quality_grade", "observation_type", "source_id",
                "growth_rate", "anchor_value"):
        left, right = merged[f"{col}_c"], merged[f"{col}_f"]
        assert (left.isna() == right.isna()).all(), col
        assert (left.dropna().to_numpy() == right.dropna().to_numpy()).all(), col


def test_ledger_carries_every_canonical_row():
    got = read("balance_ledger.csv")
    want = canonical("balance_ledger.csv")
    assert len(got) == len(want)
    for col in ("tr_lcu_mn", "te_lcu_mn", "nlb_lcu_mn"):
        assert got[col].sum() == pytest.approx(want[col].sum())


def test_reconciliation_carries_both_canonical_decompositions():
    got = read("weo_reconciliation.csv")
    hist = canonical("deficit_dynamics.csv")
    fc = canonical("weo_explanation.csv")
    assert len(got) == len(hist) + len(fc)
    assert set(got.block) == {"history", "forecast"}
    assert (got.block == "history").sum() == len(hist)
    assert got.component_meaning.notna().all()      # every component explained


def test_levels_bridge_carries_the_bridge_and_the_interest_check():
    got = read("weo_levels_bridge.csv")
    bridge = canonical("weo_base_bridge.csv")
    ni = canonical("net_interest_check.csv")
    assert len(got) == len(bridge) + len(ni)
    assert set(got.block) == {"history", "forecast_horizon"}
    hist = got[got.block == "history"]
    gaps = (hist.tr_ours_mn - hist.tr_weo_mn - hist.gap_tr_mn).abs()
    assert gaps.max() == pytest.approx(0, abs=1e-6)


# ------------------------------------------------------------- self-describing

def test_data_dictionary_covers_every_column_of_every_file():
    dic = read("data_dictionary.csv")
    assert dic.description.str.len().min() > 10
    for path in sorted(DELIV.glob("*.csv")):
        columns = set(pd.read_csv(path, nrows=1).columns)
        documented = set(dic[dic.file == path.name].column)
        assert columns == documented, (path.name, columns ^ documented)


def test_catalogue_covers_every_published_series_and_agrees_on_spans():
    cat = read("series_catalogue.csv")
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")])
    published = set(map(tuple, tree[["iso3", "line_code"]].drop_duplicates().values))
    assert set(map(tuple, cat[["iso3", "line_code"]].values)) == published
    # the 66 line series of §1 are all there, on top of the six totals
    assert {(iso3, line) for iso3, _, line in config.line_universe()} <= published
    assert len(cat) == 72

    for row in cat.itertuples():
        g = tree[(tree.iso3 == row.iso3) & (tree.line_code == row.line_code)]
        assert row.first_year == g.year.min()
        for variant, col in (("strict", "final_strict_year"),
                             ("maximum_extension", "final_maximum_year")):
            assert getattr(row, col) == g[g.variant == variant].year.max()
        assert row.final_actual_year == g[g.basis == "actual"].year.max()
        assert row.recipe_strict and row.recipe_maximum_extension


def test_catalogue_spans_agree_with_the_coverage_matrix():
    """The catalogue derives its spans from the flat files; the coverage
    matrix derives its own from the canonical layer. They must agree on all
    66 line series — one of them drifting would be a rendering bug."""
    cat = read("series_catalogue.csv").set_index(["iso3", "line_code"])
    cov = canonical("coverage_matrix.csv").set_index(["iso3", "line_code"])
    assert len(cov) == 66
    cat = cat.reindex(cov.index)
    assert cat.line_label.notna().all()             # every line is catalogued
    for cov_col, cat_col in (("first_historical_year", "first_year"),
                             ("final_actual_year", "final_actual_year"),
                             ("final_strict_year", "final_strict_year"),
                             ("final_maximum_year", "final_maximum_year")):
        assert (cov[cov_col].to_numpy() == cat[cat_col].to_numpy()).all(), cov_col


# ------------------------------------------------------- self-reproducing

@pytest.mark.parametrize("flat", ["expenditure_cofog.csv", "revenue_esa.csv"])
def test_every_chained_value_reproduces_from_the_flat_file_alone(flat):
    df = read(flat)
    checked = 0
    for _, g in df.groupby(["iso3", "variant", "line_code"]):
        values = dict(zip(g.year, g.value_lcu_mn))
        for r in g[g.growth_rate.notna()].itertuples():
            neighbour = r.year + 1 if r.year < r.anchor_year else r.year - 1
            assert neighbour in values, (flat, r.iso3, r.line_code, r.year)
            assert values[neighbour] * r.growth_rate == pytest.approx(
                r.value_lcu_mn, rel=1e-9), (flat, r.iso3, r.line_code, r.year)
            assert values[r.anchor_year] == pytest.approx(r.anchor_value,
                                                          rel=1e-9)
            checked += 1
    assert checked > 400


@pytest.mark.parametrize("flat", ["expenditure_cofog.csv", "revenue_esa.csv"])
def test_derivation_states_the_arithmetic_it_used(flat):
    df = read(flat)
    assert df.derivation.notna().all()
    chained = df[df.growth_rate.notna()]
    for r in chained.itertuples():
        neighbour = r.year + 1 if r.year < r.anchor_year else r.year - 1
        assert f"value({r.year}) = value({neighbour})" in r.derivation
        assert f"{r.growth_rate:.6f}" in r.derivation
        assert str(r.growth_source_id) in r.derivation
        assert f"grade {r.quality_grade}" in r.derivation
    anchors = df[df.growth_rate.isna()]
    assert anchors.source_id.map(str).to_numpy().tolist() == [
        s for s, d in zip(anchors.source_id.map(str), anchors.derivation)
        if s in d], "anchor rows must name their publisher"


def test_ledger_identities_hold_in_the_flat_file():
    led = read("balance_ledger.csv")
    assert led.identity_check_lcu_mn.abs().max() == pytest.approx(0, abs=1e-6)
    complete = led[led.complete_both_sides]
    assert len(complete) > 0
    assert (complete.nlb_lcu_mn + complete.ni_lcu_mn
            - complete.pb_lcu_mn).abs().max() == pytest.approx(0, abs=1e-6)
    assert (led.nlb_lcu_mn - led.b9_anchor_lcu_mn).abs().max() == pytest.approx(
        0, abs=1e-6)
    pct = 100.0 * led.nlb_lcu_mn / led.gdp_lcu_mn
    assert (pct - led.nlb_pct_gdp).abs().max() == pytest.approx(0, abs=1e-9)
    assert set(led.basis) == {"actual"}     # outturn years only, by design


def test_history_line_contributions_are_additive_and_memos_are_labelled():
    """§8.3 history side: the line contributions add to the sum-based change
    exactly (V26), and the two memo rows beside them — the anchor-vs-sum wedge
    and the WEO's own change — are carried through with their meanings."""
    hist = read("weo_reconciliation.csv").query("block == 'history'")
    key = ["iso3", "variant", "year"]
    wide = hist.pivot_table(index=key, columns="component",
                            values="contribution_pp", aggfunc="sum")
    lines_sum = (hist.query("component == 'covered_line'")
                 .groupby(key).contribution_pp.sum())
    assert (lines_sum - wide.NLB_CHANGE_SUM).abs().max() == pytest.approx(
        0, abs=1e-9)
    # the anchor's own B.9 change differs from the sum-based change only by
    # the reported wedge — small beside the balance changes being decomposed,
    # and published rather than spread across the lines (D16)
    assert wide.ANCHOR_B9_DELTA.abs().max() < 1.0
    for memo in ("ANCHOR_B9_DELTA", "WEO_GGXCNL_DELTA", "NLB_CHANGE_SUM"):
        rows = hist[hist.component == memo]
        assert len(rows) > 0 and rows.line_code.isna().all()
        assert rows.component_meaning.notna().all()


def test_forecast_block_covers_every_registered_vintage_and_both_variants():
    from ggfiscal.ingest.endpoints import weo_vintages

    fc = read("weo_reconciliation.csv").query("block == 'forecast'")
    assert set(fc.weo_vintage) == set(weo_vintages())
    assert set(fc.variant) == set(VARIANTS)
    assert {"weo_change", "covered_line", "explained_share"} <= set(fc.component)


def test_maximum_extension_contains_strict_and_agrees_where_both_exist():
    """maximum_extension is strict plus extra legs at either end — a longer
    backward leg as well as a longer forecast — and never a different number
    for a year strict also publishes."""
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")])
    wide = tree.pivot_table(index=["iso3", "line_code", "year"],
                            columns="variant", values="value_lcu_mn")
    both = wide.dropna()
    assert len(both) > 0
    assert (both.strict - both.maximum_extension).abs().max() == pytest.approx(
        0, abs=1e-6)
    # containment: nothing is in strict alone
    assert not len(wide[wide.maximum_extension.isna() & wide.strict.notna()])
    only_max = wide[wide.strict.isna() & wide.maximum_extension.notna()]
    assert len(only_max) > 0
    span = tree[tree.variant == "strict"].groupby(["iso3", "line_code"]).year
    first, last = span.min(), span.max()
    for (iso3, line, year) in only_max.index:
        assert year > last[(iso3, line)] or year < first[(iso3, line)]


# --------------------------------------------------- per-country strict files

@pytest.mark.parametrize("iso3", ["GBR", "FRA", "DEU"])
def test_country_file_is_strict_only_and_carries_every_series(iso3):
    """One file per country, strict variant only. Every strict value lands in
    it unchanged, and — the point of the file — no maximum_extension value
    reaches it: the legs that exist only in that variant must be absent."""
    wide = read(f"strict_{iso3}.csv").set_index("year")
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")])
    strict = tree.query("iso3 == @iso3 and variant == 'strict'")
    maximum = tree.query("iso3 == @iso3 and variant == 'maximum_extension'")

    # columns are "<line_code> - <line_label>", plus year, GDP and the ledger
    column = {c.split(" - ")[0]: c for c in wide.columns}
    for c in wide.columns:
        assert " - " in c, c
    assert set(column) == set(strict.line_code) | {
        "GDP", "LEDGER_TR", "LEDGER_TE", "NLB", "NI", "PB"}

    # every strict value, cell for cell
    checked = 0
    for row in strict.itertuples():
        assert wide.at[row.year, column[row.line_code]] == row.value_lcu_mn, (
            iso3, row.line_code, row.year)
        checked += 1
    assert checked > 800

    # and nothing the strict variant does not publish
    for line in strict.line_code.unique():
        present = set(wide[column[line]].dropna().index)
        published = set(strict[strict.line_code == line].year)
        assert present == published, (iso3, line, present ^ published)

    # the maximum-only legs — forward AND backward — are absent
    only_max = maximum.merge(strict[["line_code", "year"]],
                             on=["line_code", "year"], how="left",
                             indicator=True).query("_merge == 'left_only'")
    assert len(only_max) > 0, "no maximum-only legs to exclude — check fixture"
    for row in only_max.itertuples():
        if row.year in wide.index:
            assert pd.isna(wide.at[row.year, column[row.line_code]]), (
                iso3, row.line_code, row.year, "maximum_extension leaked")


@pytest.mark.parametrize("iso3", ["GBR", "FRA", "DEU"])
def test_country_file_ledger_columns_match_the_ledger(iso3):
    """The ledger's TR/TE are the balance anchor's own totals, so they are
    prefixed rather than merged into the trees' TE/TR columns."""
    wide = read(f"strict_{iso3}.csv").set_index("year")
    column = {c.split(" - ")[0]: c for c in wide.columns}
    led = read("balance_ledger.csv").query(
        "iso3 == @iso3 and variant == 'strict'").set_index("year")
    for code, source in (("LEDGER_TR", "tr_lcu_mn"), ("LEDGER_TE", "te_lcu_mn"),
                         ("NLB", "nlb_lcu_mn"), ("NI", "ni_lcu_mn"),
                         ("PB", "pb_lcu_mn")):
        got = wide[column[code]].reindex(led.index)
        pd.testing.assert_series_equal(got, led[source], check_names=False)
    # the two TE series are genuinely different for GBR, so both are kept
    both = wide[[column["TE"], column["LEDGER_TE"]]].dropna()
    assert len(both) > 20
    if iso3 == "GBR":
        assert (both.iloc[:, 0] != both.iloc[:, 1]).any()


def test_forecast_decomposition_is_additive_in_the_bundle():
    """The property the forward-balance chart rests on: covered contributions
    plus the denominator effect plus the residuals ARE the WEO's change. That
    is what lets a change be decomposed where a level cannot be stated."""
    fc = read("weo_reconciliation.csv").query("block == 'forecast'")
    key = ["iso3", "variant", "weo_vintage", "year"]
    w = fc.pivot_table(index=key, columns="component", values="contribution_pp",
                       aggfunc="sum")
    # weo_internal_wedge belongs in the identity: the WEO's own GGR - GGX does
    # not exactly equal its GGXCNL, and that discrepancy is reported as its own
    # component rather than absorbed into ours (max 3.2e-05 pp of GDP).
    parts = w[["covered_total", "denom_effect", "resid_coverage",
               "resid_disagreement", "resid_total",
               "weo_internal_wedge"]].fillna(0).sum(axis=1)
    assert (parts - w.weo_change).abs().max() < 1e-9

    # a horizon with no covered line contributes nothing covered — the chart
    # must break its line there rather than draw it flat at the base year
    lines = (fc[fc.component == "covered_line"].groupby(key).size()
             .reindex(w.index, fill_value=0))
    assert (w.covered_total.fillna(0)[lines == 0] == 0).all()
    assert (lines == 0).any(), "no exhausted horizon — check the fixture"


# ------------------------------------------------- statistical forecasts

FORECAST_METHODS = {"auto.arima", "ets", "prophet", "uc", "combination"}


def test_statistical_forecasts_cover_exactly_the_series_that_need_them():
    """A benchmark exists for every granular line whose official strict
    series stops short of 2031, and for none that already reaches it."""
    fc = read("statistical_forecasts.csv")
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")])
    strict = tree.query("variant == 'strict'")
    granular = strict[~strict.line_code.isin(["TE", "TR"])]
    ends = granular.groupby(["iso3", "line_code"]).year.max()

    have = set(map(tuple, fc[["iso3", "line_code"]].drop_duplicates().values))
    want = set(ends[ends < 2031].index)
    already = set(ends[ends >= 2031].index)
    assert have == want, have ^ want
    assert already and not (have & already), "forecast a series that has one"

    for (iso3, line), g in fc.groupby(["iso3", "line_code"]):
        assert set(g.method) == FORECAST_METHODS, (iso3, line)
        last_actual = int(granular.query(
            "iso3 == @iso3 and line_code == @line and basis == 'actual'"
        ).year.max())
        for method, m in g.groupby("method"):
            years = sorted(m.year)
            assert years == list(range(last_actual + 1, 2032)), (iso3, line,
                                                                 method)
            # fitted on outturn only — never on the official forecast years
            assert (m.fit_last_year == last_actual).all(), (iso3, line, method)


def test_statistical_forecast_intervals_are_ordered_and_finite():
    fc = read("statistical_forecasts.csv")
    assert fc[["pct_gdp", "se", "lo80", "hi80", "lo95", "hi95"]].notna().all().all()
    assert (fc.se > 0).all()
    assert (fc.lo95 < fc.lo80).all() and (fc.lo80 < fc.pct_gdp).all()
    assert (fc.pct_gdp < fc.hi80).all() and (fc.hi80 < fc.hi95).all()
    # the bands are exactly the recorded standard error, not a redrawn number
    assert (fc.hi95 - fc.pct_gdp - 1.959964 * fc.se).abs().max() < 1e-9
    assert (fc.pct_gdp - fc.lo80 - 1.281552 * fc.se).abs().max() < 1e-9


def test_combination_is_the_mean_of_the_four_and_never_narrower_than_them():
    """Point = mean of the four. Variance = average within-model variance
    plus the variance across their point forecasts, so agreement is never
    mistaken for information."""
    fc = read("statistical_forecasts.csv")
    key = ["iso3", "line_code", "year"]
    parts = fc[fc.method != "combination"]
    comb = fc[fc.method == "combination"].set_index(key)
    assert len(parts) == 4 * len(comb)

    means = parts.groupby(key).pct_gdp.mean()
    assert (means - comb.pct_gdp).abs().max() < 1e-9

    within = parts.assign(v=parts.se ** 2).groupby(key).v.mean()
    between = parts.groupby(key).pct_gdp.var(ddof=1)
    assert ((within + between) - comb.se ** 2).abs().max() < 1e-9
    assert (comb.se ** 2 >= within - 1e-12).all()


# ------------------------------------------- the forecasts in currency

def _weo_available() -> bool:
    from ggfiscal.standardise.readers import weo_series
    from ggfiscal.forecast.levels import latest_vintage, GROWTH_INDICATOR
    try:
        return not weo_series(latest_vintage(), "GBR", GROWTH_INDICATOR).empty
    except Exception:                           # pragma: no cover - guard
        return False


needs_weo = pytest.mark.skipif(
    not _weo_available(),
    reason="the WEO snapshot is not harvested in this environment")


def test_forecast_levels_is_the_ratio_times_one_gdp_path_per_country():
    """A level here is pct_gdp x GDP and nothing else, and every line of a
    country is multiplied by the SAME path — the whole reason the file
    exists, since the trees' own forecast denominators are per-source."""
    lv = read("forecast_levels.csv")
    for out, src in (("value_lcu_mn", "pct_gdp"),
                     ("lo80_lcu_mn", "lo80"), ("hi80_lcu_mn", "hi80"),
                     ("lo95_lcu_mn", "lo95"), ("hi95_lcu_mn", "hi95")):
        if src not in lv.columns:               # the ratio columns are joined
            continue                            # pragma: no cover
        assert (lv[out] - lv[src] / 100 * lv.gdp_lcu_mn).abs().max() < 1e-6

    fc = read("statistical_forecasts.csv")
    key = ["iso3", "line_code", "method", "year"]
    merged = lv.merge(fc[key + ["pct_gdp", "lo80", "hi80", "lo95", "hi95"]],
                      on=key, suffixes=("", "_fc"))
    assert len(merged) == len(lv) == len(fc), "the currency twin lost rows"
    assert (merged.pct_gdp - merged.pct_gdp_fc).abs().max() == 0
    for out, src in (("value_lcu_mn", "pct_gdp_fc"), ("lo80_lcu_mn", "lo80"),
                     ("hi80_lcu_mn", "hi80"), ("lo95_lcu_mn", "lo95"),
                     ("hi95_lcu_mn", "hi95")):
        assert (merged[out] - merged[src] / 100
                * merged.gdp_lcu_mn).abs().max() < 1e-6, out

    # one path per country-year, shared by every line and every method
    assert (lv.groupby(["iso3", "year"]).gdp_lcu_mn.nunique() == 1).all()
    assert (lv.groupby("iso3").gdp_basis.nunique() == 1).all()
    assert (lv.gdp_lcu_mn > 0).all()


def test_forecast_levels_anchors_on_our_own_gdp_and_grows_from_there():
    """The anchor is the tree's own outturn GDP at the last year every line
    agrees on it — a year before the last outturn, where the denominator
    forks by source. The WEO supplies growth after that, never the level."""
    lv = read("forecast_levels.csv")
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")])
    actual = tree.query("variant == 'strict' and basis == 'actual'").dropna(
        subset=["gdp_lcu_mn"])

    for iso3, g in lv.groupby("iso3"):
        anchor_year = int(g.gdp_anchor_year.iloc[0])
        ours = actual.query("iso3 == @iso3").groupby("year").gdp_lcu_mn
        agreed = ours.nunique()
        assert anchor_year == int(agreed[agreed == 1].index.max()), iso3
        # the last outturn really is ambiguous — that is why the anchor is
        # a year earlier, and a test that never sees it would not notice
        assert int(agreed.index.max()) > anchor_year, iso3
        assert agreed.loc[int(agreed.index.max())] > 1, iso3

        assert abs(float(g.gdp_anchor_lcu_mn.iloc[0])
                   - float(ours.first().loc[anchor_year])) < 1e-6, iso3
        path = g.drop_duplicates("year").set_index("year").gdp_lcu_mn.sort_index()
        assert path.index.min() > anchor_year
        assert (path.diff().dropna() > 0).all(), iso3   # nominal, so rising
        assert g.gdp_growth_source.eq("IMF_WEO").all()
        assert g.gdp_growth_vintage.nunique() == 1


@needs_weo
def test_forecast_levels_chains_weo_growth_and_never_its_level():
    """The distinction that keeps a German chart from stepping at the join:
    the WEO's growth is used, its level is not."""
    from ggfiscal.standardise.readers import weo_series
    from ggfiscal.forecast.levels import GROWTH_INDICATOR

    lv = read("forecast_levels.csv")
    for iso3, g in lv.groupby("iso3"):
        vintage = g.gdp_growth_vintage.iloc[0]
        weo = weo_series(vintage, iso3, GROWTH_INDICATOR).dropna() / 1e6
        anchor_year = int(g.gdp_anchor_year.iloc[0])
        path = g.drop_duplicates("year").set_index("year").gdp_lcu_mn.sort_index()
        before = float(g.gdp_anchor_lcu_mn.iloc[0])
        for year, value in path.items():
            growth = float(weo[year]) / float(weo[year - 1])
            assert abs(value - before * growth) < 1e-6, (iso3, year)
            before = value
        # and it is NOT the WEO level: for at least one country the two
        # differ materially, which is the whole point of chaining
    diffs = []
    for iso3, g in lv.groupby("iso3"):
        vintage = g.gdp_growth_vintage.iloc[0]
        weo = weo_series(vintage, iso3, GROWTH_INDICATOR).dropna() / 1e6
        path = g.drop_duplicates("year").set_index("year").gdp_lcu_mn
        diffs.append(max(abs(v - float(weo[y])) / float(weo[y])
                         for y, v in path.items()))
    assert max(diffs) > 1e-3, "chained path is indistinguishable from the level"


@needs_weo
def test_forecast_levels_is_reproducible_from_the_bundle_and_the_snapshot():
    from ggfiscal.forecast import levels

    published = read("forecast_levels.csv")
    again, notes = levels.compute(str(published.run_id.iloc[0]))
    pd.testing.assert_frame_equal(
        published.reset_index(drop=True), again.reset_index(drop=True),
        check_dtype=False, atol=0, rtol=1e-12)
    assert all("chained on IMF_WEO" in n for n in notes)


# ------------------------------------------------- the benchmark balance

BAL_EXP = ["GF01_7", "GF01_X"] + [f"GF{i:02d}" for i in range(2, 11)]
BAL_REV = [f"R{i:02d}" for i in range(1, 11)]


def test_benchmark_balance_is_reproducible_from_the_published_bundle():
    """The file is a function of `deliverables/` and nothing else — no
    harvest, no canonical layer, no wall clock. Recomputing it from the
    committed bundle has to give the committed bytes back."""
    from ggfiscal.forecast import balance

    published = read("benchmark_balance.csv")
    again, notes = balance.compute(str(published.run_id.iloc[0]))
    pd.testing.assert_frame_equal(
        published.reset_index(drop=True), again.reset_index(drop=True),
        check_dtype=False, atol=0, rtol=1e-12)
    # the rule it had to bend is reported rather than left for the reader
    assert any("stops short" in n for n in notes)


def test_benchmark_balance_sums_the_lines_back_into_the_balance():
    """Every line's signed contribution, the two side totals and the balance
    are the same arithmetic three ways. If they ever disagree the section is
    claiming a decomposition it does not have."""
    bal = read("benchmark_balance.csv")
    for (iso3, year), g in bal.groupby(["iso3", "year"]):
        lines = g[g.kind == "line"]
        sides = g[g.kind.isin(["revenue_total", "expenditure_total"])]
        row = g[g.kind == "balance"]
        assert len(row) == 1 and len(sides) == 2, (iso3, year)
        row = row.iloc[0]

        assert abs(lines.contribution_pp.sum() - row.contribution_pp) < 1e-9
        assert abs(sides.contribution_pp.sum() - row.contribution_pp) < 1e-9
        assert abs(row.pct_gdp - row.anchor_pct_gdp
                   - row.contribution_pp) < 1e-9
        # a side total is the level of its lines, and the signs are the ones
        # that make a rise in revenue narrow the deficit
        for kind, names, sign in (("revenue_total", BAL_REV, 1.0),
                                  ("expenditure_total", BAL_EXP, -1.0)):
            side = lines[lines.line_code.isin(names)]
            total = sides[sides.kind == kind].iloc[0]
            assert abs(side.pct_gdp.sum() - total.pct_gdp) < 1e-9, (iso3, year)
            assert abs(side.contribution_pp.sum()
                       - total.contribution_pp) < 1e-9
            # and the sign is the one that makes a rise in revenue narrow the
            # deficit and a rise in spending widen it
            moved = sign * (side.pct_gdp - side.anchor_pct_gdp)
            assert (side.contribution_pp - moved).abs().max() < 1e-9


def test_benchmark_balance_takes_the_interest_split_not_the_level_i_set():
    """Expenditure is GF01_7 + GF01_X + GF02..GF10. GF01 must be absent: it
    is their sum, and its own univariate fit knows nothing about the official
    interest projection inside it."""
    bal = read("benchmark_balance.csv")
    lines = bal[bal.kind == "line"]
    for iso3, g in lines.groupby("iso3"):
        codes = set(g.line_code)
        assert codes == set(BAL_EXP + BAL_REV), (iso3, codes)
        assert "GF01" not in codes and not codes & {"TE", "TR"}, iso3
    assert set(lines.source) <= {"outturn", "official", "statistical"}


def test_benchmark_balance_only_takes_an_official_path_that_reaches_the_end():
    """A total needs every line in every year, so an official projection that
    stops short is not used at all — never spliced onto a statistical tail."""
    bal = read("benchmark_balance.csv")
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")])
    strict = tree.query("variant == 'strict'").dropna(subset=["pct_gdp"])
    horizon = int(bal.year.max())

    for (iso3, line), g in bal[bal.kind == "line"].groupby(
            ["iso3", "line_code"]):
        official = strict.query("iso3 == @iso3 and line_code == @line and "
                                "basis == 'forecast'")
        covers = len(official) and official.year.max() >= horizon
        chosen = set(g.source) - {"outturn"}
        assert chosen == {"official" if covers else "statistical"}, (iso3, line)
        # an outturn year is an outturn on every line that still has one
        actual = strict.query("iso3 == @iso3 and line_code == @line and "
                              "basis == 'actual'")
        years = set(actual.year.astype(int))
        for row in g.itertuples():
            assert (row.source == "outturn") == (int(row.year) in years)


def test_benchmark_balance_base_year_is_the_last_year_every_line_has_one():
    """The expenditure tree ends a year before the revenue tree, so the base
    is the expenditure tree's last actual — and the path starts from the
    ledger's own published balance there, not from a sum of lines."""
    bal = read("benchmark_balance.csv")
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")])
    strict = tree.query("variant == 'strict' and basis == 'actual'").dropna(
        subset=["pct_gdp"])
    ledger = read("balance_ledger.csv").query("variant == 'strict'")

    for iso3, g in bal.groupby("iso3"):
        base = int(g.base_year.iloc[0])
        ends = (strict.query("iso3 == @iso3")
                .query("line_code in @BAL_EXP or line_code in @BAL_REV")
                .groupby("line_code").year.max())
        assert base == int(ends.min()), (iso3, base, ends.min())
        assert sorted(g.year.unique()) == list(range(base + 1,
                                                     int(bal.year.max()) + 1))

        led = ledger.query("iso3 == @iso3 and year == @base").iloc[0]
        anchor = 100.0 * led.nlb_lcu_mn / led.gdp_lcu_mn
        row = g[g.kind == "balance"].iloc[0]
        assert abs(row.anchor_pct_gdp - anchor) < 1e-9, iso3


def test_benchmark_balance_interval_is_the_lines_own_errors_propagated():
    """The cone is re-derived here from the published per-line standard
    errors and the published correlations — it is not a number the file gets
    to assert about itself."""
    from ggfiscal.forecast.balance import _balance_se

    bal = read("benchmark_balance.csv")
    rows = bal[bal.kind == "balance"]
    assert (rows.se > 0).all()
    assert (rows.lo95 < rows.lo80).all() and (rows.lo80 < rows.pct_gdp).all()
    assert (rows.pct_gdp < rows.hi80).all() and (rows.hi80 < rows.hi95).all()
    assert (rows.hi95 - rows.pct_gdp - 1.959964 * rows.se).abs().max() < 1e-9
    assert (rows.pct_gdp - rows.lo80 - 1.281552 * rows.se).abs().max() < 1e-9

    for row in rows.itertuples():
        lines = bal[(bal.kind == "line") & (bal.iso3 == row.iso3)
                    & (bal.year == row.year)]
        se = lines.set_index("line_code").se
        assert abs(_balance_se(se, row.rho_within, row.rho_between)
                   - row.se) < 1e-9, (row.iso3, row.year)
        # a line on an official path or still an outturn carries no variance,
        # and the count of those is published so the reader can discount it
        assert (lines[lines.source != "statistical"].se == 0).all()
        # n_official counts the country's official LEGS, which is a property
        # of the line and not of the year: in an early year such a line can
        # still be showing an outturn
        ever = bal[(bal.kind == "line") & (bal.iso3 == row.iso3)
                   & (bal.source == "official")].line_code.nunique()
        assert row.n_official == ever, row.iso3
        assert row.n_statistical + row.n_official == len(lines)

    # the calibration reference is present and is not the interval
    assert rows.history_sd_pp.notna().all()
    assert (rows.n_history_obs > 10).all()


# ----------------------------------------------------------------- notebooks

FORECAST_NOTEBOOKS = tuple(
    f"forecasts_{iso3}_{tree}.ipynb"
    for iso3 in ("GBR", "FRA", "DEU")
    for tree in ("expenditure", "revenue"))
NOTEBOOKS = ("derivation.ipynb", "chartbook.ipynb", *FORECAST_NOTEBOOKS)


def _notebook(name: str):
    nb = json.loads((ROOT / "notebooks" / name).read_text(encoding="utf-8"))
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    return (nb, code,
            "\n".join("".join(c["source"]) for c in code),
            "\n".join("".join(c["source"]) for c in nb["cells"]
                      if c["cell_type"] == "markdown"))


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_is_executed_error_free_and_reads_only_the_flat_files(name):
    nb, code, source, markdown = _notebook(name)
    assert nb["nbformat"] == 4
    # enough prose to be a document rather than a bare chart dump; the
    # forecast books carry one long preamble and short per-series headings
    assert len(code) >= 15 and len(markdown) > 2000

    # executed, with outputs committed, and no cell raised
    assert all(c["outputs"] for c in code), f"{name} has unexecuted cells"
    assert not [o for c in code for o in c["outputs"]
                if o["output_type"] == "error"]

    # reads the published bundle, never the canonical layer or the raw data
    assert "deliverables" in source
    assert "data/canonical" not in source and "data/raw" not in source


@pytest.mark.parametrize("name", FORECAST_NOTEBOOKS)
def test_forecast_notebook_charts_every_series_seven_ways(name):
    """Per series: the levels chart, the same series as a share of GDP, and a
    fan for each of the five methods — unless the official strict forecast
    already reaches 2031, in which case levels and share only."""
    _, code, source, markdown = _notebook(name)
    iso3, tree = name[len("forecasts_"):-len(".ipynb")].split("_")
    stem = {"expenditure": "expenditure_cofog", "revenue": "revenue_esa"}[tree]
    lines = (read(f"{stem}.csv").query("iso3 == @iso3 and variant == 'strict'")
             .query("line_code not in ['TE', 'TR']").line_code.unique())
    forecast = read("statistical_forecasts.csv").query("iso3 == @iso3")

    charted = 0
    for line in lines:
        assert f'levels("{iso3}", "{line}")' in source, line
        assert f'share("{iso3}", "{line}")' in source, line
        charted += 2
        has = not forecast.query("line_code == @line").empty
        for method in sorted(FORECAST_METHODS):
            call = f'fan("{iso3}", "{line}", "{method}")'
            assert (call in source) == has, (line, method)
        charted += 5 * has
    figures = [o for c in code for o in c["outputs"]
               if "data" in o and "image/png" in o["data"]]
    assert len(figures) == charted, (len(figures), charted)

    # the caveats a reader needs before believing any of it
    for topic in ("fitted on outturn only", "benchmark", "random walk",
                  "Prophet's intervals are the narrowest"):
        assert topic in markdown, topic


def test_derivation_notebook_explains_the_whole_ask():
    _, code, source, markdown = _notebook("derivation.ipynb")
    for needed in ("expenditure_cofog", "revenue_esa", "balance_ledger",
                   "weo_levels_bridge", "weo_reconciliation",
                   "series_catalogue", "data_dictionary"):
        assert needed in source, needed
    for topic in ("COFOG", "ESA", "balance ledger", "WEO", "strict",
                  "maximum_extension", "resid_coverage", "explained_share"):
        assert topic in markdown, topic


def test_chartbook_charts_every_published_series():
    """One chart per series, country by country, plus the WEO comparison and
    the ledger — a series that gains a chart nowhere would be invisible."""
    _, code, source, markdown = _notebook("chartbook.ipynb")
    cat = read("series_catalogue.csv")

    for row in cat.itertuples():
        call = f'chart("{row.iso3}", "{row.line_code}")'
        assert call in source, call
    for iso3 in ("GBR", "FRA", "DEU"):
        for q in ("TR", "TE", "NLB", "NI", "PB"):
            assert f'ledger_chart("{iso3}", "{q}")' in source
        for q in ("revenue", "expenditure", "nlb"):
            assert f'weo_chart("{iso3}", "{q}")' in source

        assert f'weo_forward("{iso3}")' in source or "weo_forward(iso3)" in source

    figures = [o for c in code for o in c["outputs"]
               if "data" in o and "image/png" in o["data"]]
    # every series, the 15 ledger charts, the 9 WEO ones, the 3 TE
    # diagnostics, and the 9 forecast-panel figures (3 per country)
    assert len(figures) >= len(cat) + 15 + 9 + 3 + 9 + 2, "a chart is missing"
    # the schema caveats are stated, not left for the reader to discover
    for topic in ("GF01_X", "outturn-only", "two different TE numbers",
                  "explained_share", "seam"):
        assert topic in markdown, topic


def test_chartbook_explains_why_there_is_no_forward_balance_of_our_own():
    """The asymmetry a reader will ask about: a forward `explained_share`
    exists while a forward `ours vs WEO` level does not. The notebook has to
    say why, and show the comparison the data does support."""
    _, code, source, markdown = _notebook("chartbook.ipynb")
    for phrase in ("a level needs every component and a change does not",
                   "resid_coverage", "covered-forecast path"):
        assert phrase in markdown, phrase
    # and it must not let the covered path be read as a balance forecast
    assert "not a forecast of our balance" in markdown
    assert "covered_total" in source


def test_chartbook_shares_one_x_axis_per_country_and_shades_every_chart():
    """The projection region is drawn whether or not the series reaches into
    it, on a per-country axis, so charts can be read side by side."""
    _, code, source, markdown = _notebook("chartbook.ipynb")
    setup = next(c for c in code if "XLIM" in "".join(c["source"]))
    body = "".join(setup["source"])
    # one span per country, from its first published year to a common 2031
    assert "XMAX = 2031" in body
    assert "XLIM[_iso] = (" in body and "LEDGER.query" in body
    assert body.count("XMAX + _pad") == 1
    # shading is unconditional — every chart-drawing helper draws the band,
    # and the old "only if a forecast exists" guard is gone
    assert body.count("axvspan(") == 3, "a chart family stopped shading"
    te = next(c for c in code if "def te_compare" in "".join(c["source"]))
    assert "axvspan(" in "".join(te["source"])
    # the panel facets are the fourth family: their own 2000-2031 window, the
    # same shading, and the window applied to the DATA and not only to
    # set_xlim, or a 2070 value would flatten the history to nothing
    facet = "".join(next(c for c in code
                         if "def _facet(" in "".join(c["source"]))["source"])
    assert "axvspan(" in facet
    assert "PANEL_FROM = 2000" in facet and "XMAX + 0.8" in facet
    assert "hist[hist.year >= PANEL_FROM]" in facet
    assert "if mx.year.max() > actual" not in body, "shading is still conditional"
    assert "ax.set_xlim(lo, hi)" in body and "ax.set_xlim(*XLIM[iso3])" in body
    assert "to 2031" in markdown


PANEL_ROW = re.compile(
    r"^(GF\S+|R\d\d)\s+.*?"
    r"(-?\d+\.\d\d) \((\d{4})\)\s+(-?\d+\.\d\d) \((\d{4})\)\s+"
    r"([-+\u00b1]\d+\.\d\d)\s+(official|statistical)")


def test_chartbook_panels_quote_one_forecast_per_category():
    """Each country section opens with a panel of every category forward, as a
    share of GDP, carrying exactly one forecast per line: the official
    projection where one is published and the statistical `combination` where
    none is — never both, and never a single one of the four methods alone.

    The printed table under `changes()` is the panel's table view, so it is
    re-derived here from the flat files, row by row.
    """
    _, code, source, markdown = _notebook("chartbook.ipynb")
    tree = pd.concat([read("expenditure_cofog.csv"), read("revenue_esa.csv")])
    strict = tree.query("variant == 'strict'")
    combination = read("statistical_forecasts.csv").query(
        "method == 'combination'")

    for iso3 in ("GBR", "FRA", "DEU"):
        for what in ("expenditure", "revenue"):
            assert f'panel("{iso3}", "{what}")' in source, (iso3, what)
        assert f'changes("{iso3}")' in source, iso3

        cell = next(c for c in code
                    if "".join(c["source"]).strip() == f'changes("{iso3}")')
        text = "".join("".join(o["text"]) for o in cell["outputs"]
                       if o["output_type"] == "stream")
        rows = {m.group(1): m for m in map(PANEL_ROW.match, text.splitlines())
                if m}

        granular = strict.query("iso3 == @iso3").dropna(subset=["pct_gdp"])
        want = set(granular.line_code.unique()) - {"TE", "TR"}
        assert set(rows) == want, (iso3, set(rows) ^ want)

        for line, m in rows.items():
            g = granular.query("line_code == @line")
            actual = g[g.basis == "actual"].sort_values("year")
            official = g[(g.basis == "forecast") & (g.year <= 2031)]

            # the anchor: every path starts at that line's own last outturn
            assert int(m.group(3)) == int(actual.year.max()), (iso3, line)
            assert abs(float(m.group(2))
                       - float(actual.pct_gdp.iloc[-1])) < 5e-3, (iso3, line)

            if len(official):
                source_kind, path = "official", official
            else:
                source_kind = "statistical"
                path = combination.query("iso3 == @iso3 and line_code == @line")
                assert len(path), (iso3, line)
            assert m.group(7) == source_kind, (iso3, line)

            end = path.sort_values("year").iloc[-1]
            assert int(m.group(5)) == int(end.year), (iso3, line)
            assert abs(float(m.group(4)) - float(end.pct_gdp)) < 5e-3, (iso3, line)
            change = float(end.pct_gdp) - float(actual.pct_gdp.iloc[-1])
            said = m.group(6)
            # a change that rounds to nothing is printed ±0.00, never -0.00
            if said.startswith("\u00b1"):
                assert abs(round(change, 2)) == 0, (iso3, line, change)
            else:
                assert abs(float(said) - change) < 5e-3, (iso3, line)

    # the rule, and the caveats it carries, are stated before any panel is drawn
    for topic in ("How to read a forecast panel", "statistical combination",
                  "last outturn level", "need not add up",
                  "Nothing here is spliced or recomputed"):
        assert topic in markdown, topic


def test_chartbook_levels_charts_carry_the_benchmark_where_nothing_is_published():
    """The levels charts gain a violet leg in currency — but only where the
    strict series carries no official forecast. Where one exists the
    published number is the answer, exactly as in the forecast panels.

    Checked against the executed captions, so this is what the book actually
    printed and not what the code looks like it would print.
    """
    _, code, source, markdown = _notebook("chartbook.ipynb")
    assert 'load("forecast_levels")' in source
    setup = "".join(next(c for c in code
                         if "def chart(" in "".join(c["source"]))["source"])
    # the leg is keyed on strict and anchored on strict's own last outturn
    assert 'method == \'combination\'' in setup
    assert "int(strict.year.max()) <= actual" in setup
    assert "lo80_lcu_mn" in setup and "lo95_lcu_mn" not in setup

    cat = read("series_catalogue.csv").set_index(["iso3", "line_code"])
    levels = read("forecast_levels.csv").query("method == 'combination'")
    have = set(map(tuple, levels[["iso3", "line_code"]].drop_duplicates().values))

    drawn = 0
    for cell in code:
        call = "".join(cell["source"]).strip()
        if not call.startswith("chart(") or not call.endswith(")"):
            continue
        iso3, line = [t.strip().strip('"') for t in
                      call[len("chart("):-1].split(",")]
        text = "".join("".join(o["text"]) for o in cell["outputs"]
                       if o["output_type"] == "stream")
        row = cat.loc[(iso3, line)]
        expected = (row.final_strict_year <= row.final_actual_year
                    and (iso3, line) in have)
        assert ("benchmark:" in text) == bool(expected), (iso3, line)
        if expected:
            drawn += 1
            # the caption names the horizon, the band and the GDP path, so a
            # reader never has to guess which of the two objects they are on
            said = next(ln for ln in text.splitlines()
                        if ln.startswith("benchmark:"))
            assert "80%" in said
            assert "not a published forecast" in text
            assert "anchored_outturn_chained_on_weo_ngdp" in text
    assert drawn == 46, drawn

    # and the reading guide says what the new leg is and what its band is not
    for topic in ("statistical benchmark", "80% interval of the *ratio*",
                  "taken as given", "no official forecast"):
        assert topic in markdown, topic


def test_chartbook_states_the_benchmark_balance_and_what_it_is_not():
    """§4.5 draws the balance the line forecasts imply. It has to read the
    published file rather than sum the lines itself, carry the cone, and say
    plainly that a benchmark is not a forecast of the deficit."""
    _, code, source, markdown = _notebook("chartbook.ipynb")
    assert 'load("benchmark_balance")' in source
    assert "balance_path()" in source and "balance_contributions()" in source

    body = "".join(next(c for c in code
                        if "def balance_path(" in "".join(c["source"]))["source"])
    for needed in ("lo80", "hi80", "lo95", "hi95", "history_sd_pp",
                   "axvspan("):
        assert needed in body, needed
    # the cone comes out of the file; the notebook does not build one
    assert "rho_within" in body and "_balance_se" not in body

    for topic in ("benchmark", "not our forecast of the deficit",
                  "zero by construction", "GF01_7 + GF01_X + GF02",
                  "covers the whole horizon",
                  "contribute **no** variance"):
        assert topic in markdown, topic

    # §4.4 said there is no forward balance; it must now point at §4.5 rather
    # than be quietly contradicted by it
    assert "a level needs every component and a change does not" in markdown
    assert "§4.5" in markdown


def test_chartbook_panel_never_draws_a_single_method_or_a_95_band():
    """The panel carries the combination and nothing else: quoting one of the
    four methods, or widening it to 95%, would be a different claim."""
    _, code, source, _ = _notebook("chartbook.ipynb")
    body = "".join(next(c for c in code
                        if "def panel(" in "".join(c["source"]))["source"])
    # the cell's prose names all four methods, which is the point of it; the
    # code it runs must name only the one it draws
    runs = "\n".join(ln for ln in body.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert 'method == \'combination\'' in runs
    for method in FORECAST_METHODS - {"combination"}:
        assert method not in runs, method
    assert "lo80" in runs and "hi80" in runs
    assert "lo95" not in runs and "hi95" not in runs


def test_chartbook_says_why_each_series_without_a_projection_has_none():
    """Every series that stops at its last outturn must say so in its own
    caption, and none that projects may claim it does not."""
    _, code, source, markdown = _notebook("chartbook.ipynb")
    cat = read("series_catalogue.csv").set_index(["iso3", "line_code"])

    checked = 0
    for cell in code:
        call = "".join(cell["source"]).strip()
        if not call.startswith("chart(") or not call.endswith(")"):
            continue
        iso3, line = [p.strip().strip('"') for p in
                      call[len("chart("):-1].split(",")]
        text = "".join("".join(o["text"]) for o in cell["outputs"]
                       if o["output_type"] == "stream")
        assert text.strip(), f"{iso3} {line} printed no caption"
        row = cat.loc[(iso3, line)]
        # one caption line per variant, each saying NO PROJECTION exactly when
        # that variant stops at the last outturn — the eight lines that project
        # only in maximum_extension say it on the strict line alone
        for variant, final in (("strict", row.final_strict_year),
                               ("maximum", row.final_maximum_year)):
            # the caption collapses to one "both:" line when the two variants
            # say the same thing, which is the common case
            lines = text.splitlines()
            said = next((ln for ln in lines
                         if ln.startswith(f"{variant}:")), None)
            if said is None:                    # collapsed to one "both:" line
                said = next(ln for ln in lines if ln.startswith("both:"))
            projects = final > row.final_actual_year
            assert ("NO PROJECTION" in said) != bool(projects), (iso3, line,
                                                                variant)
            if projects:
                assert str(int(final)) in said, (iso3, line, variant)
        if row.final_maximum_year <= row.final_actual_year:
            # the reason is given, not just the absence
            assert row.forecast_status in (
                "no_official_forecast", "source_blocked", "grade_below_strict",
                "no_machine_readable_source", "not_extended"), (iso3, line)
            assert len(text.split("NO PROJECTION —")[1].strip()) > 40
        checked += 1
    assert checked == len(cat)

    # the taxonomy is spelled out once, up front
    for status in ("no_official_forecast", "source_blocked",
                   "grade_below_strict", "no_machine_readable_source",
                   "not_extended"):
        assert status in markdown, status
