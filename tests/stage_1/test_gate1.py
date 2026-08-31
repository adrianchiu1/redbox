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


def test_all_66_lines_plus_totals_present_in_both_variants():
    for variant in ("strict", "maximum_extension"):
        exp = load_canonical("COFOG", variant)
        rev = load_canonical("ESA_REV", variant)
        for iso3 in config.COUNTRIES:
            exp_lines = set(exp[exp.iso3 == iso3].line_code)
            rev_lines = set(rev[rev.iso3 == iso3].line_code)
            assert exp_lines == {f"GF{n:02d}" for n in range(1, 11)} | \
                {"GF01_7", "GF01_X", "TE"}, (iso3, variant)
            assert rev_lines == {f"R{n:02d}" for n in range(1, 11)} | {"TR"}, \
                (iso3, variant)


def test_schema_validates():
    from ggfiscal.model import SCHEMA
    for cls in ("COFOG", "ESA_REV"):
        SCHEMA.validate(load_canonical(cls, "strict"))


def test_history_only_all_grade_a_or_b_no_forecasts():
    for cls in ("COFOG", "ESA_REV"):
        df = load_canonical(cls, "strict")
        assert not df.is_forecast.any()
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
