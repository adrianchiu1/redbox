"""Gate for the retirement-age sensitivity (D-S20-001).

Arithmetic and identities only: the assumptions are declared, so nothing
here tests that a unit cost is *right*, only that exposure and units
combine as the docstring says and that the calibrations land where the
published figures put them.
"""
import pandas as pd
import pytest

from ggfiscal.debt import pension_age as pa


@pytest.fixture(scope="module")
def mat():
    return pa.matrix("p62", "central")


def test_register_is_complete_and_every_assumption_has_a_status():
    r = pa.register()
    assert set(r.status) <= {"sourced", "inferred", "declared", "missing"}
    assert r.id.is_unique
    assert "B3" in set(r[r.status == "missing"].id)          # the early-starter share is flagged, not silent


def test_law_as_it_stands_matches_cor_table():
    assert pa.aod_current(1964, 6) == 62.75
    assert pa.aod_current(1965, 2) == 62.75 and pa.aod_current(1965, 9) == 63.0
    assert pa.aod_current(1969, 1) == 64.0 and pa.aod_reform(1968, 1) == 64.0
    assert pa.aod_reform(1964, 1) == 63.0


def test_exposure_signs_and_timing():
    e62 = pa.exposure_total("p62"); e60 = pa.exposure_total("p60"); e64 = pa.exposure_total("p64")
    assert (e62.loc[:2027] == 0).all() and e62.loc[2028] > 0          # policy starts 2028
    assert (e60 >= e62).all()                                          # 60 for early starters adds exposure
    assert (e64.loc[2028:2032] < 0).all() and abs(e64.loc[2034:]).max() < 1e-6   # the suspension ends with the 1969 cohort
    assert 0.4 < e62.loc[2028] / e62.loc[2033] < 0.6                   # a cut is front-loaded: half the steady state in year one
    assert 1.5 < e62.loc[2034] / 850_000 < 1.8                         # (1 − B4) × 2 cohort-years


def test_suspension_calibration_is_in_range_of_the_cour():
    s = pa.suspension_unit()
    assert 0.1 < s["cohort_years_2027_2031_avg"] < 0.4
    assert 5.0 < s["eur_bn_per_cohort_year"] < 12.0                   # COR/DREES 1.8bn ÷ exposure ≈ Cour's 5.8 × (1 + durée effect)


def test_matrix_signs_and_identity(mat):
    exp = mat[mat.side == "expenditure"]; rev = mat[mat.side == "revenue"]
    assert (exp[exp.line_code == "GF10_2"].eur_bn.loc[lambda s: s.index.isin(mat.index[mat.year >= 2028])] >= 0).all()
    assert (rev[(rev.line_code == "R06") & (rev.year >= 2028)].eur_bn <= 0).all()
    assert ((mat.balance_bn + mat.eur_bn.where(mat.side == "expenditure", -mat.eur_bn)).abs() < 1e-9).all()
    tot = mat.groupby(["method", "year"]).balance_bn.sum().unstack("year")
    assert (tot[2030] < 0).all() and (tot[2035] < 0).all()


def test_linearity_units_do_not_depend_on_the_plan():
    """The unit per cohort-year is the same under '62 for all' and '60 for
    early starters' for the groups both policies move (others, early_other)."""
    u = pa.bottom_up_units().set_index(["line_code", "group"]).eur_per_cohort_person_year
    assert u[("GF10_2", "others")] == pytest.approx(0.45 * 1600 * 12)
    m62 = pa.matrix("p62").query("method == 'm2_bottom_up' and year == 2035").groupby("line_code").eur_bn.sum()
    m60 = pa.matrix("p60").query("method == 'm2_bottom_up' and year == 2035").groupby("line_code").eur_bn.sum()
    # GF10_X is per cohort-person-year with no group difference, so it scales exactly with exposure
    k = pa.exposure_total("p60")[2035] / pa.exposure_total("p62")[2035]
    assert m60["GF10_X"] / m62["GF10_X"] == pytest.approx(k, rel=1e-6)


def test_variants_order():
    for pol in ("p62", "p60"):
        lo = pa.summary(pol, "low")[2035]; ce = pa.summary(pol, "central")[2035]; hi = pa.summary(pol, "high")[2035]
        assert (lo >= ce - 1e-9).all() and (hi <= ce + 1e-9).all()


def test_overlay_and_growth_haircut():
    o = pa.balance_overlay("p62")
    assert o[2027] == 0 and o[2030] < -5 and o[2035] < o[2030]
    h = pa.growth_haircut("p62")
    assert h[2028] < 0 and abs(h[2028]) < 0.1                        # a few basis points of growth a year (gdp_pct is in % of GDP)
