"""Gate for the register-based interest simulation (D-S11-001).

Arithmetic and accounting identities only: the scenarios are declared
inputs, so nothing here tests that a path is *right*, only that the engine
does what its docstring says with the bundle it is given.
"""
import numpy as np
import pandas as pd
import pytest

from ggfiscal.debt import simulate as sim


@pytest.fixture(scope="module")
def results():
    return sim.run_all()


def test_register_loads_at_snapshot():
    reg = sim.load_register()
    assert set(reg.instrument_class) == {"bill", "fixed_bullet", "inflation_linked"}
    assert (reg.nominal > 0).all()
    # linkers carry an uplift ratio above one, everything else exactly one
    assert (reg.loc[reg.instrument_class == "inflation_linked", "uplift_ratio"] > 1).all()
    assert (reg.loc[reg.instrument_class != "inflation_linked", "uplift_ratio"] == 1).all()


def test_issuance_mix_sums_to_one_with_office_tenors():
    m = sim.issuance_mix()
    assert abs(m.sum() - 1) < 1e-9
    assert set(m.attrs["tenor"]) == set(m.index)
    assert all(v > 0 for v in m.attrs["tenor"].values())


def test_calibration_matches_the_bundle():
    c = sim.calibration()
    assert 0.8 < c["net_issuance_over_deficit_2015_2025"] < 1.1
    assert abs(c["wedge_2025_bn"] - (c["gf01_7_2025_bn"] - c["register_cash_interest_2025_bn"])) < 0.15


def test_every_scenario_runs_every_year(results):
    years = set(range(sim.FIRST_YEAR, sim.LAST_YEAR + 1))
    for name, g in results.groupby("scenario"):
        assert set(g.year) == years, name
        assert g.gg_interest_bn.notna().all()


def test_bridge_year_takes_the_strict_interest(results):
    y = results[results.year == sim.FIRST_YEAR]
    assert np.allclose(y.gg_interest_bn, sim.BASELINE.gg_interest_2026_bn)


def test_identities_hold(results):
    r = results
    # interest = register + wedge; wedge is a share of GDP
    wedge = sim.BASELINE.gg_wedge_pct / 100 * r.gdp_bn
    assert np.allclose(r.gg_interest_bn, r.register_interest_bn + wedge)
    # debt accumulates the deficit exactly (no stock-flow adjustment declared)
    for _, g in r.groupby("scenario"):
        g = g.sort_values("year")
        d0 = sim.BASELINE.debt_2025_pct / 100 * sim.BASELINE.gdp[2025]
        assert np.allclose(g.debt_bn.values, d0 + g.deficit_bn.cumsum().values)


def test_ordering_of_the_political_scenarios(results):
    at = results[results.year == 2032].set_index("scenario").gg_interest_bn
    assert at["philippe_majority"] < at["current"] < at["lepen_hung"] < at["lepen_majority"] < at["lepen_rupture"]


def test_current_path_is_near_the_ec_dsm_path(results):
    """The strict file carries the EC DSM interest path; a register roll under
    the current spread should land within a fifth of it in 2030."""
    strict = pd.read_csv(sim.DELIV / "strict_FRA.csv").set_index("year")
    dsm_2030 = strict.loc[2030, "GF01_7 - Public debt transactions (interest)"] / 1000
    ours = results.query("scenario == 'current' and year == 2030").gg_interest_bn.iloc[0]
    assert abs(ours / dsm_2030 - 1) < 0.2


def test_decomposition_adds_up():
    d = sim.decompose_gap(sim.SCENARIOS[3])
    assert np.allclose(d.gap_bn, d.spread_effect_bn + d.volume_effect_bn + d.interaction_bn)


def test_duration_table_prices_sensibly():
    d = sim.duration_table(90.0)
    # the 0.50% May 2072 prices near 20 at a 4%+ yield; nothing prices above 160
    assert (d.price > 10).all() and (d.price < 160).all()
    assert (d.modified_duration >= 0).all()
    long = d[d.years_to_maturity > 20].modified_duration.mean()
    short = d[d.years_to_maturity < 3].modified_duration.mean()
    assert long > short
    s = sim.duration_summary(90.0)
    assert 3 < s["modified_duration_years"] < 10
