"""GBR per-security register (DEBT_KICKOFF.md §5, §14 GBR): the DMO readers,
the four canonical frames, and the reconciliation to the office's own anchors
(V29, V30, V31).

Everything that touches a snapshot is skipped where the D8 store lacks the
DMO parts (a checkout before `ggfiscal debt fetch --family debt_offices`).
"""

import numpy as np
import pandas as pd
import pytest

from ggfiscal.debt import register_gbr as R
from ggfiscal.debt.model import TABLES
from ggfiscal.debt.readers import dmo as D

RUN_ID = "TEST_REGISTER_GBR"

needs_register = pytest.mark.skipif(not D.have_register_parts(), reason="no DMO register snapshots")
needs_ratios = pytest.mark.skipif(not D.have(D.SOURCE_GILTS, D.PART_RATIOS), reason="no DMO D10C snapshot")


@pytest.fixture(scope="module")
def tables() -> dict[str, pd.DataFrame]:
    return R.build(RUN_ID)


# --------------------------------------------------------------------- names

def test_parse_name_reads_fractions_years_and_tranches():
    p = D.parse_name("8½% Treasury Loan 2007 A")
    assert p["coupon_pct"] == 8.5 and p["years"] == ["2007"] and p["tranche"] == "A"
    p = D.parse_name("0 1/8% Index-linked Treasury Gilt 2028")
    assert p["coupon_pct"] == 0.125 and p["is_linker"]
    p = D.parse_name("12% Exchequer Stock 2013-2017")
    assert p["years"] == ["2013", "2017"]


def test_name_key_folds_tranches_and_separates_undated_stock():
    assert D.name_key("8½% Treasury Loan 2007 A") == D.name_key("8½% Treasury Loan 2007")
    assert D.name_key("3½% War Loan") != D.name_key("3½% Conversion Loan")
    assert D.name_key("2% Treasury Gilt 2025") != D.name_key("2% Index-linked Treasury Stock 2025")


# ------------------------------------------------------------------ readers

@needs_register
def test_issuance_history_reproduces_the_nominal_in_issue():
    """Σ signed operations per ISIN vs D1A: the operations record is complete
    for the gilts in issue (the two exceptions are documented stubs)."""
    g = D.gilts_in_issue().set_index("isin")["amount_mn"]
    s = D.issuance_history().groupby("isin")["nominal_mn"].sum().reindex(g.index)
    off = (g - s).abs() > 1.0
    assert off.sum() <= 2, g[off]


@needs_register
def test_redemptions_list_every_redeemed_gilt_since_1981():
    r = D.redemptions()
    assert r["redemption_date"].min().year == 1981
    assert r["nominal_mn"].notna().all() and (r["nominal_mn"] > 0).all()


@needs_ratios
def test_index_ratios_recompute_from_the_ons_rpi():
    """The DMO 3-month-lag formula on the ONS RPI gives the office's
    reference RPI (5 dp) and, with the base at first issue, its ratio."""
    rpi = R._rpi()
    office = D.index_ratios()
    # a settlement day in month m needs RPI(m-2): keep the days the RPI series reaches
    office = office[office["date"] < rpi.index.max() + pd.DateOffset(months=3)]
    ref = np.array([R.reference_rpi_3m(d, rpi) for d in office["date"]])
    assert np.nanmax(np.abs(ref - office["reference_rpi"].values)) < 1e-4
    first = D.gilts_in_issue().set_index("isin")["first_issue_date"]
    ok = office["isin"].isin(first.index)
    base = np.array([R.reference_rpi_3m(first[i], rpi) for i in office.loc[ok, "isin"]])
    assert np.nanmax(np.abs(ref[ok.values] / base - office.loc[ok, "index_ratio"].values)) < 1e-4


# ------------------------------------------------------------------- frames

@needs_register
def test_every_table_validates_against_its_schema(tables):
    for name, df in tables.items():
        TABLES[name].validate(df)
        assert (df["iso3"] == "GBR").all()


@needs_register
def test_register_holds_gilts_in_issue_redeemed_and_bills(tables):
    secs = tables["debt_securities"]
    isins = set(D.gilts_in_issue()["isin"])
    assert isins <= set(secs["isin"].dropna())
    assert len(secs[secs["instrument_class"] == "bill"]) == D.bill_tenders()["maturity_date"].nunique()
    assert secs.loc[secs["instrument_class"] == "inflation_linked", "index_lag_months"].isin([3.0, 8.0]).all()


@needs_register
def test_tranches_are_folded_into_their_parent(tables):
    secs = tables["debt_securities"]
    assert not secs["name"].str.match(r".*\s[A-D]$").any()
    parent = secs[secs["name"] == "8½% Treasury Loan 2007"]
    assert len(parent) == 1 and "tranches folded" in parent["notes"].iloc[0]


@needs_register
def test_office_snapshot_and_rolled_year_end_agree(tables):
    """31 Dec 2025 rolled from the flows + 2026 flows = the D1A close of business."""
    pos, fl = tables["debt_positions"], tables["debt_flows"]
    snap = pos[pos["position_type"] == "office_snapshot"].set_index("security_id")
    cob = snap["as_of"].max()
    ye = pos[(pos["position_type"] == "rolled_from_flows") & (pos["as_of"] == pd.Timestamp(f"{cob.year - 1}-12-31"))]
    ye = ye.set_index("security_id")["nominal_lcu_mn"]
    f = fl[(fl["settlement_date"] > pd.Timestamp(f"{cob.year - 1}-12-31")) & (fl["settlement_date"] <= cob)]
    f = f.assign(_v=f["nominal_lcu_mn"] * f["flow_type"].map(R.SIGN)).groupby("security_id")["_v"].sum()
    rolled = ye.reindex(snap.index).fillna(0.0) + f.reindex(snap.index).fillna(0.0)
    assert (rolled - snap["nominal_lcu_mn"]).abs().max() < 1.0


@needs_register
def test_redeemed_gilts_close_at_their_published_nominal(tables):
    """The position the day before redemption equals the D1C nominal for every
    gilt whose operations the history carries in full (no opening stub)."""
    pos, fl, secs = tables["debt_positions"], tables["debt_flows"], tables["debt_securities"]
    red = fl[(fl["flow_type"] == "redemption") & ~fl["security_id"].str.startswith("UKTB-")]
    stub = set(fl.loc[fl["flow_type"] == "implied", "security_id"])
    checked = 0
    for r in red[~red["security_id"].isin(stub)].itertuples(index=False):
        p = pos[(pos["security_id"] == r.security_id) & (pos["as_of"] < r.settlement_date)]
        if p.empty:
            continue
        last = p.sort_values("as_of").iloc[-1]
        later = fl[(fl["security_id"] == r.security_id) & (fl["settlement_date"] > last["as_of"])
                   & (fl["settlement_date"] < r.settlement_date)]
        later = (later["nominal_lcu_mn"] * later["flow_type"].map(R.SIGN)).sum()
        assert abs(last["nominal_lcu_mn"] + later - r.nominal_lcu_mn) < 1.0, r.security_id
        checked += 1
    assert checked > 50


@needs_register
def test_opening_stubs_are_published_not_allocated(tables):
    fl = tables["debt_flows"]
    imp = fl[fl["flow_type"] == "implied"]
    assert (imp["settlement_date"] == R.REGISTER_START).all()
    assert imp["quality_grade"].isin(["B", "C"]).all()
    assert imp["notes"].str.contains("never allocated").all()


@needs_register
def test_index_linked_unindexed_stock_matches_the_dmr(tables):
    """End-December 2023-2025 unindexed nominal of index-linked gilts vs HMT
    DMR table A.1 (the aggregate layer), within 0.5%."""
    agg = R.class_aggregates(RUN_ID)
    dmr = agg[(agg["measure"] == "stock_year_end") & (agg["sub_type"] == "gilts_index_linked_unindexed")]
    if dmr.empty:
        pytest.skip("no DMR rows in the aggregate layer")
    secs, pos = tables["debt_securities"], tables["debt_positions"]
    il = set(secs.loc[secs["instrument_class"] == "inflation_linked", "security_id"])
    ye = pos[(pos["position_type"] == "rolled_from_flows") & pos["security_id"].isin(il)]
    reg = ye.groupby(ye["as_of"].dt.year)["nominal_lcu_mn"].sum()
    for r in dmr.itertuples(index=False):
        if r.year in reg.index:
            assert abs(reg[r.year] / r.value_lcu_mn - 1) < 0.005, (r.year, reg[r.year], r.value_lcu_mn)


@needs_register
def test_bills_reconcile_to_the_ons_stock_when_tenders_are_the_only_issuance(tables):
    """2001-2006 (tenders only): Σ bills outstanding at 31 Dec = ONS BKPJ."""
    rec = R.reconciliation(RUN_ID, tables)["stock"].set_index("year")
    r = rec.loc[2001:2006, "ratio_bills_over_official"].dropna()
    assert len(r) >= 4 and (r - 1).abs().max() < 0.002
