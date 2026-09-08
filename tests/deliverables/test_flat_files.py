"""The flat-file bundle and the derivation notebook.

Two things are being defended here. First, that `deliverables/` is a faithful
rendering of the gated canonical layer — same values, nothing lost, nothing
invented — so the simple files can be trusted as much as the wide ones.
Second, that the bundle is self-describing: every column documented, every
published series catalogued, and every chained value reproducible from the
flat file alone (the Gate 6 property, re-proved on the simplified shape).
"""

import json

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


# ----------------------------------------------------------------- notebooks

NOTEBOOKS = ("derivation.ipynb", "chartbook.ipynb")


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
    assert len(code) >= 15 and len(markdown) > 3000

    # executed, with outputs committed, and no cell raised
    assert all(c["outputs"] for c in code), f"{name} has unexecuted cells"
    assert not [o for c in code for o in c["outputs"]
                if o["output_type"] == "error"]

    # reads the published bundle, never the canonical layer or the raw data
    assert "deliverables" in source
    assert "data/canonical" not in source and "data/raw" not in source


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

    figures = [o for c in code for o in c["outputs"]
               if "data" in o and "image/png" in o["data"]]
    assert len(figures) >= len(cat) + 15 + 9, "a chart is missing"
    # the schema caveats are stated, not left for the reader to discover
    for topic in ("GF01_X", "outturn-only", "two different TE numbers",
                  "explained_share", "seam"):
        assert topic in markdown, topic
