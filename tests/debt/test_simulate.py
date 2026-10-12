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
    b = sim.BASELINE
    # interest = register + wedge; wedge is a share of GDP
    wedge = b.gg_wedge_pct / 100 * r.gdp_bn
    assert np.allclose(r.gg_interest_bn, r.register_interest_bn + wedge)
    # the deficit is the primary balance plus net interest, in every year
    # including the bridge year (the first version added the half-year on the
    # 2026 issuance on top of the AMECO bill that already contained it)
    recv = b.interest_receivable_pct / 100 * r.gdp_bn
    assert np.allclose(r.deficit_bn, -r.primary_balance_bn + r.gg_interest_bn - recv)
    # the interest components add up to the register interest
    parts = (r.coupon_fixed_bn + r.coupon_linker_bn + r.uplift_bn + r.bill_interest_bn
             - r.premium_amort_bn + r.new_issue_interest_bn)
    after = r.year > sim.FIRST_YEAR
    assert np.allclose(r.register_interest_bn[after], parts[after])
    assert (r.new_issue_interest_bn[~after] == 0).all()
    # debt accumulates the deficit exactly (no stock-flow adjustment declared)
    for _, g in r.groupby("scenario"):
        g = g.sort_values("year")
        d0 = b.debt_2025_pct / 100 * b.gdp[2025]
        assert np.allclose(g.debt_bn.values, d0 + g.deficit_bn.cumsum().values)


def test_financing_identities_hold(results):
    """Gross MLT issuance = redemptions + the financed share of the deficit −
    the uplift accrual (indexed, not issued) − the change in bills; so the
    negotiable stock grows by exactly the financed share of the deficit, and
    the uplift is in the stock once (through the indexed nominal), not twice."""
    b = sim.BASELINE
    for _, g in results.groupby("scenario"):
        g = g.sort_values("year").set_index("year")
        d_btf = g.btf_stock.diff()
        later = g.index > sim.FIRST_YEAR
        need = (g.redemptions_bn + b.deficit_to_net_issuance * g.deficit_bn - g.uplift_bn - d_btf)[later]
        assert np.allclose(g.mlt_gross_issuance_bn[later], need)
        assert np.allclose(g.net_issuance_bn[later], b.deficit_to_net_issuance * g.deficit_bn[later])
        # the stock is valued at the start-of-year uplift and a maturing linker
        # accrues its uplift pro rata but redeems in full, so the identity holds
        # to a few hundred million, not to the cent
        assert np.allclose(g.negotiable_stock_bn.diff()[later], g.net_issuance_bn[later], atol=0.7)
    # bridge year: only the remainder of 2026 after the snapshot is financed
    g = results[results.scenario == sim.REFERENCE].set_index("year")
    share = (pd.Timestamp("2027-01-01") - pd.Timestamp(sim.SNAPSHOT)).days / 365
    assert 0.3 < share < 0.32
    assert np.isclose(g.net_issuance_bn[2026], b.deficit_to_net_issuance * g.deficit_bn[2026] * share)


def test_gdp_is_the_ledger_level_chained_on_ameco_growth(results):
    """The level is the ledger's 2025 outturn (the denominator of the 115.6%
    debt ratio); 2026–2027 take AMECO's growth, not AMECO's levels, so the
    0.4% by which AMECO's own 2025 exceeds the ledger is never booked as
    growth (D-S4-002)."""
    b = sim.BASELINE
    led = pd.read_csv(sim.DELIV / "balance_ledger.csv").query("iso3 == 'FRA' and variant == 'strict'").set_index("year")
    assert np.isclose(b.gdp[2025], led.gdp_lcu_mn[2025] / 1000, rtol=1e-4)
    for sc in sim.SCENARIOS:
        g = results[results.scenario == sc.name].set_index("year").gdp_bn
        assert np.isclose(g[2026] / b.gdp[2025], b.gdp_ameco[2026] / b.gdp_ameco[2025])
        assert np.isclose(g[2027] / g[2026], b.gdp_ameco[2027] / b.gdp_ameco[2026])
    strict = pd.read_csv(sim.DELIV / "strict_FRA.csv").set_index("year")
    ameco = strict["GDP - Gross domestic product at current market prices"] / 1000
    for y in (2025, 2026, 2027):
        assert np.isclose(b.gdp_ameco[y], ameco[y], rtol=2e-4)


def test_loop_size_is_a_small_positive_part_of_the_gap():
    """The arithmetic loop (interest on the interest) is positive and well
    below the gap itself; it is NOT decompose_gap's interaction term."""
    sc = sim.scenario("melenchon")
    loop = sim.loop_size(sc).set_index("year")
    assert (loop.loop_bn > 0).all()
    assert (loop.loop_share < 0.25).all()
    assert loop.loop_bn[2035] > loop.loop_bn[2030]
    dec = sim.decompose_gap(sc).set_index("year")
    assert np.allclose(loop.gap_bn, dec.gap_bn)
    assert not np.isclose(loop.loop_bn[2030], dec.interaction_bn[2030], rtol=0.05)


def test_wedge_is_declared_on_the_register_accrued_basis():
    """The wedge the engine adds is GF01_7 less the register's accrued D.41,
    the concept the roll reproduces (coupons + uplift + bill discount −
    premium amortisation). The cash figure the first version used is
    reported beside it; the gap between the accrued total and the roll's
    pre-amortisation concept is the bonds' premium amortisation, which the
    roll carries forward line by line."""
    c = sim.calibration()
    assert abs(sim.BASELINE.gg_wedge_pct - c["wedge_2025_accrued_pct_gdp"]) < 0.005
    assert c["wedge_2025_accrued_pct_gdp"] > c["wedge_2025_pct_gdp"] > c["wedge_2025_engine_concept_pct_gdp"]
    reg = sim.load_register()
    assert (reg.loc[reg.instrument_class == "bill", "premium_amort"] == 0).all()
    assert 0 < reg.premium_amort.sum() < 5          # EUR bn a year of net premium on the bonds
    r = sim.run_all().query("scenario == @sim.REFERENCE").set_index("year")
    # carried line by line to maturity: in a year every line is outstanding
    # for the whole of, the engine's figure is exactly the register's sum
    # over those lines (premiums and discounts net, so the path need not be
    # monotone — a discount line maturing raises the net)
    bonds = reg[reg.instrument_class != "bill"]
    frac = bonds.maturity.map(lambda m: sim._year_fraction_outstanding(m, 2028))
    assert np.isclose(r.premium_amort_bn[2028], (bonds.premium_amort * frac).sum())
    assert r.premium_amort_bn.abs().max() <= bonds.premium_amort.abs().sum()


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
