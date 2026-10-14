"""Gate for the line-by-line sell-down ladder (D-S19-002): the lines carry
their valuation basis and the right-to-sell flag, the runs nest, the group
stocks reconcile to Eurostat's sub-sector totals where they should, and the
yields are the income over the stock."""
import numpy as np

from ggfiscal.debt import balance_sheet as bs
from ggfiscal.debt import ladder_detail as ld


def test_every_line_is_documented():
    d = ld.ladder_detail()
    assert set(d.group) == set(ld.GROUPS)
    assert d.can_sell.isin({"yes", "yes, pact", "law", "no"}).all()
    assert (d.basis.str.len() > 10).all() and (d.source.str.len() > 3).all()
    assert d.as_of.str.match(r"\d{4}-\d{2}-\d{2}").all()
    for name in ("Engie", "Orange", "Aéroports de Paris", "Renault", "Air France-KLM", "FDJ United", "Eramet", "Airbus", "Safran", "Thales", "Eutelsat",
                 "EDF", "SNCF", "La Poste SA", "Naval Group"):
        assert (d.line == name).any(), name


def test_runs_nest_and_never_exceed_the_stock():
    d = ld.ladder_detail()
    assert (d.sold_liquidity_bn <= d.sold_realistic_bn + 1e-9).all()
    assert (d.sold_realistic_bn <= d.sold_distress_bn + 1e-9).all()
    assert (d.sold_distress_bn <= d.stock_bn + 1e-9).all()
    assert (d.loc[d.can_sell == "no", ["sold_liquidity_bn", "sold_realistic_bn", "sold_distress_bn"]] == 0).all().all()
    law = d[(d.can_sell == "law") & ~d.line.str.startswith("Other central-government units' deposits")]
    assert (law[["sold_liquidity_bn", "sold_realistic_bn"]] == 0).all().all()
    assert np.allclose(law.sold_distress_bn, law.stock_bn / 2)
    listed = d[d.group == "listed"]
    pact = listed[listed.can_sell == "yes, pact"]; free = listed[listed.can_sell == "yes"]
    assert (pact.sold_realistic_bn == 0).all() and np.allclose(pact.sold_distress_bn, pact.stock_bn / 2)
    assert np.allclose(free.sold_realistic_bn, free.stock_bn / 2) and np.allclose(free.sold_distress_bn, free.stock_bn)
    unl = d[(d.group == "unlisted") & (d.can_sell == "yes")]
    assert (unl.sold_realistic_bn == 0).all() and np.allclose(unl.sold_distress_bn, unl.stock_bn)
    assert (d.loc[d.reference_only, ["sold_liquidity_bn", "sold_realistic_bn", "sold_distress_bn"]] == 0).all().all()


def test_groups_reconcile_to_eurostat():
    h = bs.history().loc[2025]
    t = ld.totals()
    assert abs(t.loc["cash", "stock_bn"] - h.f2_bn) < 1.0                      # built on the S13 F.2 total
    # loans + the Trésor's placements (booked in cash here, F.4 by Eurostat) = S13 F.4
    placements = ld.ladder_detail().query("line.str.startswith('Trésor short-term')").stock_bn.iloc[0]
    assert abs(t.loc["loans", "stock_bn"] + placements - h.f4_bn) < 6.0
    # the pension reserves by scheme add to the S.1314 bond and equity holdings
    s1314 = bs.financial_balance_sheet("S1314", "ASS").loc[2025]
    schemes = ld.ladder_detail().query("holder.str.contains('S.1314') and group in ['paper', 'funds']").stock_bn.sum()
    assert abs(schemes - (s1314["F3"] + s1314["F5"])) < 15.0
    # listed lines add to the APE's listed total plus Eutelsat, bought after its valuation date
    listed = t.loc["listed", "stock_bn"]
    assert abs(listed - (bs.APE_2025H1["listed_bn"] + 0.6)) < 0.5


def test_income_and_yields():
    d = ld.ladder_detail()
    s = d[~d.reference_only]
    assert np.allclose(s.yield_pct, 100 * s.income_bn / s.stock_bn)
    assert 9.0 < s.income_bn.sum() < 14.0            # D.41 + D.42 received by S13 in 2025 was €13.3bn
    edf = d[d.line == "EDF"].iloc[0]
    assert edf.income_bn == 2.0 and 2.5 < edf.yield_pct < 3.5
    t = ld.runs_from_detail()
    assert t["liquidity"] < t["realistic"] < t["distress"]
