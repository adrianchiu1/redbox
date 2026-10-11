"""Gate for the register-based interest simulation (D-S12-001).

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


def test_five_scenarios_and_the_reference():
    names = [sc.name for sc in sim.SCENARIOS]
    assert names == ["statistical", "philippe_majority", "philippe_hung", "lepen_majority", "lepen_hung", "melenchon"]
    assert sim.REFERENCE in names


def test_spread_paths_are_the_declared_levels(results):
    """2026 at today's level, the 2027 level, a straight fade to 2029, flat
    after; no feedback moves them."""
    for sc in sim.SCENARIOS:
        s = results[results.scenario == sc.name].set_index("year").spread_bp
        assert s[2026] == sim.BASELINE.spread_today_bp
        assert s[2027] == sc.spread_2027_bp
        assert s[2028] == (sc.spread_2027_bp + sc.spread_2029_bp) / 2
        assert (s.loc[2029:] == sc.spread_2029_bp).all()
        assert np.allclose(results[results.scenario == sc.name].oat_10y_pct,
                           sim.BASELINE.bund_curve[10] + s.values / 100)
    assert sim.BASELINE.bund_curve[10] == 3.5


def test_primary_balance_moves_by_the_declared_euros(results):
    for sc in sim.SCENARIOS:
        if sc.pb_change_pp is not None:
            continue
        g = results[results.scenario == sc.name].set_index("year")
        d = g.primary_balance_bn.diff()
        assert np.allclose(d.loc[2028:2031], sc.consolidation_bn)
        assert np.allclose(d.loc[2032:], sc.consolidation_after_bn)
        # common to 2027, then nominal growth = real growth plus the deflator
        assert np.isclose(g.primary_balance_pct[2027], sim.BASELINE.primary_balance[2027])
        growth = g.gdp_bn.pct_change().loc[2028:]
        assert np.allclose(growth, (1 + sc.real_growth) * (1 + sim.BASELINE.deflator_after) - 1)


def test_statistical_takes_the_benchmark_changes_and_the_status_quo_market(results):
    sc, ref = sim.scenario("statistical"), sim.scenario(sim.REFERENCE)
    assert sc.spread_path() == ref.spread_path() and sc.real_growth == ref.real_growth
    g = results[results.scenario == "statistical"].set_index("year").primary_balance_pct
    d = sim.benchmark_pb_changes()
    assert set(d) == {2028, 2029, 2030, 2031}
    for y, v in d.items():
        assert np.isclose(g[y] - g[y - 1], v)
    assert np.allclose(g.loc[2032:], g[2031])           # flat after the benchmark ends


def test_melenchon_is_the_costliest_and_status_quo_the_next(results):
    at = results[results.year == 2032].set_index("scenario").gg_interest_bn
    others = at.drop(["melenchon", "philippe_hung", "statistical"])
    assert at["melenchon"] > at["philippe_hung"] > others.max()


def test_status_quo_is_near_the_ec_dsm_path(results):
    """The strict file carries the EC DSM interest path; a register roll in
    the status quo should land within a fifth of it in 2030 (it is above it:
    the spread starts at 135 bp)."""
    strict = pd.read_csv(sim.DELIV / "strict_FRA.csv").set_index("year")
    dsm_2030 = strict.loc[2030, "GF01_7 - Public debt transactions (interest)"] / 1000
    ours = results.query("scenario == @sim.REFERENCE and year == 2030").gg_interest_bn.iloc[0]
    assert abs(ours / dsm_2030 - 1) < 0.2


def test_decomposition_adds_up():
    d = sim.decompose_gap(sim.scenario("melenchon"))
    assert np.allclose(d.gap_bn, d.spread_effect_bn + d.volume_effect_bn + d.interaction_bn)
    assert (d.spread_effect_bn > 0).all()


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
