"""Gate for the balance-sheet module (D-S19-001): the net-debt rebuild
matches INSEE, the identities hold, the ladder is declared and consistent,
and a sale moves the engine the way the docstring says."""
import numpy as np
import pandas as pd
import pytest

from ggfiscal.debt import balance_sheet as bs
from ggfiscal.debt import simulate as sim


@pytest.fixture(scope="module")
def history():
    return bs.history()


@pytest.fixture(scope="module")
def runs():
    return bs.run_all()


def test_manual_file_carries_provenance():
    d = bs.eurostat()
    assert set(d.dataset) == {"gov_10a_ggfa", "gov_10a_main", "gov_10dd_edpt1", "nama_10_nfa_bs"}
    assert d.updated.str.match(r"\d{4}-\d{2}-\d{2}").all() and d.retrieved.str.match(r"\d{4}-\d{2}-\d{2}").all()
    assert (d.iso3 == "FRA").all()


def test_net_debt_rebuilt_from_eurostat_matches_insee(history):
    chk = bs.insee_check()
    assert abs(chk["gap_bn"]) < 5.0                    # €1bn on €3,245bn in the October 2026 vintages
    assert np.isclose(chk["redbox_gross_2025_bn"], bs.INSEE_2025["gross_bn"], atol=1.0)
    assert abs(history.loc[2025].net_pct - bs.INSEE_2025["net_pct"]) < 0.3


def test_history_identities(history):
    h = history.dropna(subset=["gross_bn", "liquid_bn"])
    assert np.allclose(h.net_bn, h.gross_bn - (h.f2_bn + h.f3_bn + h.f4_bn))
    assert np.allclose(h.net_fin_bn, h.net_bn - h.f5_bn)
    assert np.allclose(h.net_interest_bn.dropna(), (h.interest_paid_bn - h.interest_recv_bn - h.dividends_bn).dropna())
    s = h.dropna(subset=["sfa_bn"])
    assert np.allclose(s.sfa_bn, history.gross_bn.diff().loc[s.index] + s.nlb_bn)
    assert (h.f5_bn > h.liquid_bn).loc[2015:].all()     # equity is the big asset class
    assert 1.0 < history.loc[2025].liquid_yield_pct < 3.0 and 0.5 < history.loc[2025].equity_yield_pct < 2.5


def test_sfa_components_flip_the_chain_sign():
    comp = bs.sfa_components_s1311()
    assert list(comp.index) == [2021, 2022, 2023, 2024, 2025]
    f = pd.read_csv(sim.DELIV / "debt_financing_reconciliation.csv", low_memory=False)
    v = f.query("iso3 == 'FRA' and year == 2023 and step == 'B_s1311_b9' and item == 'less_net_acquisition_currency_and_deposits'").value_lcu_mn.iloc[0]
    assert np.isclose(comp.cash_and_deposits[2023], -v / 1000)
    assert np.allclose(comp.total, comp.drop(columns="total").sum(axis=1))


def test_ladder_is_declared_and_consistent():
    lad = bs.ladder()
    assert set(lad.key) == {"cash", "paper", "loans", "listed", "funds", "unlisted", "cdc", "gold", "nonfin"}
    for run in ("liquidity", "realistic", "maximal", "extreme"):
        assert (lad[f"sold_{run}_bn"] <= lad.stock_bn + 1e-9).all(), run
        assert (lad[f"sold_{run}_bn"] >= 0).all()
    assert (lad.sold_liquidity_bn <= lad.sold_realistic_bn).all()
    assert (lad.sold_realistic_bn <= lad.sold_maximal_bn).all()
    assert (lad.sold_maximal_bn <= lad.sold_extreme_bn).all()
    assert lad.set_index("key").loc["nonfin", "sold_extreme_bn"] == 0.0
    assert lad.set_index("key").loc["gold", "sold_maximal_bn"] == 0.0      # off balance sheet only in the extreme run
    sold = bs.sales("maximal").sold_bn.sum()
    on_bs = lad[lad["where"] != "off balance sheet"].sold_maximal_bn.sum()
    assert np.isclose(sold, on_bs)


def test_runs_nest_and_the_identities_hold(runs):
    years = set(range(sim.FIRST_YEAR, sim.LAST_YEAR + 1))
    for run, g in runs.groupby("run"):
        assert set(g.year) == years, run
        g = g.set_index("year")
        assert np.allclose(g.net_debt_bn, g.debt_bn - g.liquid_assets_bn)
        assert np.allclose(g.net_fin_debt_bn, g.net_debt_bn - g.equity_assets_bn)
        assert np.allclose(g.net_interest_bn, g.gg_interest_bn - g.asset_income_bn)
        assert (g.liquid_assets_bn >= 0).all() and (g.equity_assets_bn >= 0).all()
    sq = runs[runs.run == "status_quo"].set_index("year")
    assert (sq.sfa_bn == 0).all()
    block = bs.asset_block()
    assert np.isclose(sq.liquid_assets_bn[2035], block.liquid_bn)                       # flat in euros
    assert np.isclose(sq.equity_assets_bn[2035], block.equity_bn * sq.gdp_bn[2035] / sim.BASELINE.gdp[2025])
    d35 = {run: g.set_index("year").debt_pct_gdp[2035] for run, g in runs.groupby("run")}
    assert d35["status_quo"] > d35["liquidity"] > d35["realistic"] > d35["maximal"] > d35["extreme"]
    # the sale is the SFA: liquid + equity sold in a year equals −sfa, off-balance-sheet rungs included
    for run in ("liquidity", "realistic", "maximal", "extreme"):
        g = runs[runs.run == run].set_index("year")
        s = bs.sales(run).groupby("year").sold_bn.sum()
        assert np.allclose(-g.sfa_bn.reindex(s.index), s)
        # income forgone lowers the primary balance against the status quo
        assert (g.primary_balance_bn.loc[2028:] < sq.primary_balance_bn.loc[2028:]).all()
        assert (g.asset_income_bn.loc[2028:] < sq.asset_income_bn.loc[2028:]).all()


def test_selling_a_low_yield_asset_against_a_high_coupon_debt_improves_net_interest(runs):
    sq = runs[runs.run == "status_quo"].set_index("year")
    r = runs[runs.run == "realistic"].set_index("year")
    assert (r.net_interest_bn.loc[2030:] < sq.net_interest_bn.loc[2030:]).all()
    assert (r.deficit_pct_gdp.loc[2030:] < sq.deficit_pct_gdp.loc[2030:]).all()


def test_stabilising_primary_balance_arithmetic():
    assert np.isclose(bs.stabilising_pb(100.0, 3.0, 3.0), 0.0)
    assert np.isclose(bs.stabilising_pb(120.0, 4.0, 2.0), 100 * 0.02 / 1.02 * 1.2)


def test_summary_has_the_quoted_keys():
    s = bs.summary()
    for k in ("net_2025_pct", "liquid_2025_bn", "asset_income_2025_bn", "sq_2030_pb_star_gross", "sq_2030_pb_star_net",
              "realistic_sold_bn", "realistic_2035_debt_gap", "maximal_2035_net_interest_gain_bn", "extreme_2035_debt"):
        assert k in s and np.isfinite(s[k]), k
    assert s["sq_2030_pb_star_net"] < s["sq_2030_pb_star_gross"]
