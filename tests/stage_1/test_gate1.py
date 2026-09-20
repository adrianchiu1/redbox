"""Gate 1: canonical history built from anchors; identities hold; V-tests
green; the history-side §8.3 decomposition passes V26 (skip when the harvest
or build is absent)."""

import pytest

from ggfiscal import config
from ggfiscal.build import load_canonical, load_ledger
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")


@pytest.fixture(scope="module", autouse=True)
def built():
    if load_canonical("COFOG").empty:
        from ggfiscal.build import build
        build()


def test_all_lines_plus_totals_present_in_both_variants():
    """Every granular line of every tree plus the tree's total, per country
    (the 123-line universe of D-S13-001/005 for the three countries). A line
    the country declares absent (D20) is present too — as structural_zero
    rows, zero in every anchor year — so the expected set is the tree's
    full line list either way."""
    assert {f"GF{n:02d}" for n in range(1, 11)} | {"GF01_7", "GF01_X", "GF04_5", "GF04_X",
                                                   "GF10_2", "GF10_5", "GF10_X"} \
        == set(config.granular_lines("COFOG"))
    for variant in ("strict", "maximum_extension"):
        for cls in config.TREES:
            df = load_canonical(cls, variant)
            want = set(config.granular_lines(cls)) | {config.total_code(cls)}
            for iso3 in config.COUNTRIES:
                sub = df[df.iso3 == iso3]
                assert set(sub.line_code) == want, (iso3, cls, variant)
                zeros = sub[sub.observation_type == "structural_zero"]
                assert set(zeros.line_code) == {c for (k, c) in config.absent_lines(iso3)
                                                if k == cls}, (iso3, cls, variant)


def test_schema_validates():
    from ggfiscal.model import SCHEMA
    for cls in config.TREES:
        SCHEMA.validate(load_canonical(cls, "strict"))


def test_esa_exp_identity_and_every_level2_split_hold_in_every_anchor_year():
    """D-S13-002/003/005: E01..E09 = TE_ESA exactly, and for every Level II
    split remainder + Σ Level II = parent exactly wherever the anchor
    publishes them, both variants."""
    for variant in ("strict", "maximum_extension"):
        esa = load_canonical("ESA_EXP", variant)
        trees = {cls: load_canonical(cls, variant) for cls in config.TREES}
        for iso3 in config.COUNTRIES:
            e = esa[(esa.iso3 == iso3) & (esa.anchor_year == esa.year)].pivot_table(
                index="year", columns="line_code", values="value_lcu_mn")
            lines = [f"E{n:02d}" for n in range(1, 10)]
            full = e.dropna(subset=lines + ["TE_ESA"])
            assert len(full) >= 25, (iso3, variant)
            assert (full[lines].sum(axis=1) - full.TE_ESA).abs().max() < 1e-6 * full.TE_ESA.max()
            for sp in config.level2_splits():
                df = trees[sp["classification"]]
                g = df[(df.iso3 == iso3) & (df.anchor_year == df.year)].pivot_table(
                    index="year", columns="line_code", values="value_lcu_mn")
                cols = [sp["parent"], sp["remainder"], *sp["level2s"]]
                full = g.dropna(subset=cols)
                assert len(full) >= 25, (iso3, variant, sp["parent"])
                total = full[sp["remainder"]] + full[sp["level2s"]].sum(axis=1)
                assert (total - full[sp["parent"]]).abs().max() < 1e-6 * full[sp["parent"]].abs().max()
                for c in sp["level2s"]:
                    assert (full[c] <= full[sp["parent"]]).all(), (iso3, c)
            # old age is the largest single COFOG group everywhere
            g = trees["COFOG"]
            g = g[(g.iso3 == iso3) & (g.anchor_year == g.year)].pivot_table(
                index="year", columns="line_code", values="value_lcu_mn").dropna(subset=["GF10", "GF10_2"])
            assert (g.GF10_2 / g.GF10 > 0.4).all(), (iso3, variant)


def test_history_only_all_grade_a_or_b_no_forecasts():
    for cls in config.TREES:
        df = load_canonical(cls, "strict")
        # history side: no anchor-era or backward-stitched row is a forecast
        # (Stage 3 adds forward rows beyond the anchor; those are is_forecast
        # and covered by tests/stage_3 — the Stage 1 invariant is that nothing
        # at or before the anchor frontier is one)
        assert not df[df.year <= df.anchor_year].is_forecast.any()
        # strict carries only A anchors and B extensions/proxies (V9: no C/D)
        assert set(df.quality_grade) <= {"A", "B"}
        # anchor-era rows are A except the D10 proxy years (DEU GF01_7 1995-99
        # and their GF01_X); every other B row is a Stage 2 backward stitch
        anchor_era = df[df.anchor_year == df.year]
        b_anchor = anchor_era[anchor_era.quality_grade == "B"]
        assert set(b_anchor.iso3) <= {"DEU"}
        assert set(b_anchor.line_code) <= {"GF01_7", "GF01_X"}


def test_v_suite_green_at_stage_1():
    from ggfiscal.validate.runner import current_stage, run_all
    assert current_stage() >= 1
    findings = run_all()
    errors = [f for f in findings if f.severity == "ERROR"]
    assert errors == [], [f"{f.check_id} {f.scope}: {f.message}" for f in errors]
    ran = {f.check_id for f in findings if f.severity in ("OK", "WARN", "ERROR")}
    for vid in ("V1", "V2", "V3", "V4", "V19", "V22", "V23", "V26"):
        assert vid in ran, vid


def test_ledger_identity_and_flags():
    led = load_ledger()
    strict = led[led.series_variant == "strict"]
    assert (strict.nlb_lcu_mn == strict.tr_lcu_mn - strict.te_lcu_mn).all()
    complete = strict[strict.complete_both_sides]
    assert (complete.pb_lcu_mn == complete.nlb_lcu_mn + complete.ni_lcu_mn).all()
    for iso3 in config.COUNTRIES:
        assert len(complete[complete.iso3 == iso3]) >= 25


def test_history_decomposition_v26_exact():
    from ggfiscal.reconcile.dynamics import decompose, v26_check
    assert v26_check("strict") == []
    df = decompose("strict")
    assert set(df.iso3) == set(config.COUNTRIES)
    # every decomposed year carries all 20 line contributions
    for (_, _), g in df.groupby(["iso3", "year"]):
        assert len(g[g.kind.isin(["revenue", "expenditure"])]) == 20


def test_small_multiples_render(tmp_path):
    from ggfiscal.report.small_multiples import write
    dest = write(path=tmp_path / "sm.html")
    html = dest.read_text(encoding="utf-8")
    assert len(html) > 50_000 and "plotly" in html and "scatter" in html
