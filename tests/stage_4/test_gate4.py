"""Gate 4: variants distinguishable row-by-row; no leakage; coverage matrix
complete. Plus the Stage 4 machinery: §7.9 GF01-via-GF01_7 with explicit
residual_method, §7.8 proxies maximum-only, C-tier application, V17."""

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.build import load_canonical
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")


def _rows(variant):
    return pd.concat([load_canonical("COFOG", variant),
                      load_canonical("ESA_REV", variant)], ignore_index=True)


@pytest.fixture(scope="module")
def matrix():
    path = config.repo_root() / "data" / "canonical" / "coverage_matrix.csv"
    if not path.exists():
        from ggfiscal.build import build
        build()
    return pd.read_csv(path)


def test_gate4_variants_distinguishable_row_by_row():
    key = ["iso3", "classification", "line_code", "year"]
    s = _rows("strict")
    m = _rows("maximum_extension")
    ks = set(map(tuple, s[key].values))
    km = set(map(tuple, m[key].values))
    assert ks < km  # strict is a strict subset: maximum adds rows
    extra = km - ks
    # the Stage 4 additions are present in maximum only
    extra_lines = {(i, l) for i, c, l, y in extra}
    for iso3 in config.COUNTRIES:
        assert (iso3, "GF01") in extra_lines
        assert (iso3, "GF10") in extra_lines
    assert ("FRA", "R05") in extra_lines
    # and every maximum-only row is flagged by grade or observation type
    m_only = m.merge(pd.DataFrame(list(extra), columns=key), on=key)
    assert ((m_only.quality_grade.isin(["C", "D"]))
            | (m_only.observation_type == "proxy_forecast")).all()


def test_gate4_no_leakage_into_strict():
    s = _rows("strict")
    assert set(s.quality_grade) <= {"A", "B"}
    assert "proxy_forecast" not in set(s.observation_type)
    # backward C rows stay maximum-only too (Stage 2 invariant intact)
    assert not ((s.observation_type == "stitched_actual")
                & (s.quality_grade == "C")).any()


def test_gf01_via_gf01_7_growth_with_residual_method():
    m = _rows("maximum_extension")
    for iso3 in config.COUNTRIES:
        gf01 = m[(m.iso3 == iso3) & (m.line_code == "GF01")
                 & m.growth_source_id.notna() & (m.year > m.anchor_year)]
        gf017 = m[(m.iso3 == iso3) & (m.line_code == "GF01_7")
                  & m.growth_source_id.notna() & (m.year > m.anchor_year)
                  & (m.growth_source_id == "EC_AMECO")]
        assert len(gf01) == 3  # 2025 stitched + 2026-27 forecast
        # §7.9: identical growth to the GF01_7 AMECO leg, year by year
        g1 = dict(zip(gf01.year, gf01.growth_rate))
        g7 = dict(zip(gf017.year, gf017.growth_rate))
        assert set(g1) == set(g7)
        for y in g1:
            assert g1[y] == pytest.approx(g7[y], rel=1e-12)
        assert (gf01.residual_method == config.residual_method(iso3, "GF01")).all()
        assert (gf01.quality_grade == "D").all()  # measured band, recorded
        assert gf01.coverage_share.notna().all()
        # strict never carries it
        s = _rows("strict")
        assert s[(s.iso3 == iso3) & (s.line_code == "GF01")
                 & (s.year > s.anchor_year)].empty


def test_gf10_proxy_and_d12_chain():
    m = _rows("maximum_extension")
    for iso3 in config.COUNTRIES:
        g = m[(m.iso3 == iso3) & (m.line_code == "GF10")
              & m.growth_source_id.notna() & (m.year > m.anchor_year)]
        ameco = g[g.growth_source_id == "EC_AMECO"]
        assert len(ameco) and max(ameco.year) == 2027
        assert (ameco[ameco.is_forecast].observation_type == "proxy_forecast").all()
        if iso3 in ("FRA", "DEU"):
            ar = g[g.growth_source_id == "EC_AGEING_2024"]
            assert len(ar) and min(ar.year) == 2028 and max(ar.year) == 2070
            assert (ar.observation_type == "composite_forecast").all()
        else:
            assert set(g.growth_source_id) == {"EC_AMECO"}


def test_proxies_carry_d2_and_78_requirements():
    m = _rows("maximum_extension")
    px = m[m.observation_type.isin(["proxy_forecast", "composite_forecast"])]
    assert len(px) > 0
    assert px.residual_method.notna().all()
    assert px.coverage_share.notna().all()
    assert px.coverage_share_year.notna().all()
    proxies = m[m.observation_type == "proxy_forecast"]
    assert proxies.notes.astype(str).str.contains(
        "constructed, not an official forecast").all()


def test_coverage_matrix_complete(matrix):
    assert len(matrix) == 66
    assert matrix.reason_series_ends.astype(str).str.len().ge(10).all()
    assert matrix.first_historical_year.notna().all()
    assert matrix.final_actual_year.notna().all()
    assert matrix.final_strict_year.notna().all()
    assert matrix.final_maximum_year.notna().all()
    assert (matrix.final_maximum_year >= matrix.final_strict_year).all()
    assert matrix.grades.astype(str).str.len().ge(1).all()
    assert matrix.principal_sources.astype(str).str.len().ge(1).all()
    # the Stage 4 proxies show up with their spans and residual methods
    gf01 = matrix[matrix.line_code == "GF01"]
    assert (gf01.final_maximum_year == 2027).all()
    assert (gf01.residual_method == "grow_with_proxy").all()
    gf10 = matrix[matrix.line_code == "GF10"].set_index("iso3")
    assert gf10.loc["GBR", "final_maximum_year"] == 2027
    assert gf10.loc["FRA", "final_maximum_year"] == 2070
    assert gf10.loc["DEU", "final_maximum_year"] == 2070
    # GF01_X is never forecast: final maximum = final actual
    gx = matrix[matrix.line_code == "GF01_X"]
    assert (gx.final_maximum_year == gx.final_actual_year).all()


def test_v17_and_suite_green_at_stage_4():
    from ggfiscal.validate.runner import current_stage, run_all

    assert current_stage() >= 4
    findings = run_all()
    by_id = {}
    for f in findings:
        by_id.setdefault(f.check_id, []).append(f)
    assert "V17" in by_id and by_id["V17"][0].severity != "SKIP"
    assert not [f for f in findings if f.severity == "ERROR"]
