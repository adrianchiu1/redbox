"""FRA per-security register (DEBT_KICKOFF.md §5, §14 FRA): the AFT page
readers and the snapshot register. Skipped where the store has no AFT pages."""

import pandas as pd
import pytest

from ggfiscal.debt import register_fra as R
from ggfiscal.debt.model import TABLES
from ggfiscal.debt.readers import aft as A

RUN_ID = "TEST_REGISTER_FRA"
needs_encours = pytest.mark.skipif(not A.have(A.SOURCE_ENCOURS, "oat"), reason="no AFT encours snapshot")
needs_auctions = pytest.mark.skipif(not A.have(A.SOURCE_ADJUDICATIONS, "dernieres"), reason="no AFT auctions page")


@pytest.fixture(scope="module")
def tables():
    return R.build(RUN_ID)


def test_libelle_parser_reads_every_naming_variant():
    assert A.parse_libelle("OAT 2,50 % 24 septembre 2026")["coupon_pct"] == 2.5
    assert A.parse_libelle("OAT 2,50 % 24 septembre 2026")["maturity_date"] == pd.Timestamp("2026-09-24")
    p = A.parse_libelle("GREEN OAT€i 0.10% 25 JULY 2038")
    assert p["kind"] == "OAT€i" and p["is_green"] and p["maturity_date"] == pd.Timestamp("2038-07-25")
    assert A.parse_libelle("OAT zéro coupon 28 mars 2028")["coupon_pct"] == 0.0
    assert A.parse_libelle("OATi 0,10 % 1er mars 2029")["kind"] == "OATi"


def test_amounts_read_french_and_english_formats():
    assert A.eur("24 030 000 000") == 24_030_000_000
    assert A.eur("22,162,000,000.00") == 22_162_000_000
    assert A.eur("3 300") == 3300
    assert A.pct("2,540 %") == 2.54 and A.pct("76,96 %") == 76.96


@needs_encours
def test_encours_pages_list_every_line_with_terms():
    e = A.encours_all()
    assert e["isin"].is_unique
    assert e["maturity_date"].notna().all() and (e["outstanding_eur"] >= 0).all()   # a BTF line can be listed before its first tender
    oat = e[e["part"] == "oat"]
    assert oat["coupon_pct"].notna().all()
    assert 50 <= len(oat) <= 80 and 2e12 < oat["outstanding_eur"].sum() < 3.5e12


@needs_auctions
def test_auction_page_pivots_attribute_rows_per_line():
    a = A.auctions(A.SOURCE_ADJUDICATIONS, "dernieres")
    assert len(a) >= 4 and a["isin"].str.match(r"^FR").all()
    assert (a["total_issued_mn"] >= a["allotted_mn"]).all()
    oat = a[a["family"] == "OAT"]
    assert oat["avg_price_pct"].between(30, 130).all() and oat["settlement_date"].notna().all()
    btf = a[a["family"] == "BTF"]
    assert btf["maturity_date"].notna().all() and btf["avg_yield_pct"].abs().lt(15).all()


@needs_encours
def test_every_table_validates_and_positions_match_the_pages(tables):
    for name, df in tables.items():
        TABLES[name].validate(df)
    pos, secs = tables["debt_positions"], tables["debt_securities"]
    assert set(pos["security_id"]) <= set(secs["security_id"])
    e = A.encours_all()
    snap = pos[pos["position_type"] == "office_snapshot"]
    assert abs(snap["nominal_lcu_mn"].sum() - e["outstanding_eur"].sum() / 1e6) < 1.0
    assert secs.loc[secs["instrument_class"] == "inflation_linked", "index_reference"].isin(
        ["FR_CPI_XT", "EA_HICP_XT"]).all()


# ------------------------------------------------------------ the history

needs_history = pytest.mark.skipif(not A.have(A.SOURCE_ADJUDICATIONS, A.HIST_MLT_PART), reason="no AFT auction history")


@needs_history
def test_history_files_read_and_total_issued_is_competitive_plus_onc():
    m = A.history_mlt()
    assert m["auction_date"].min().year == 1999 and len(m) > 2000
    assert ((m["allotted_mn"].fillna(0) + m["onc_mn"].fillna(0) - m["total_issued_mn"]).abs() <= 0.5).all()
    b = A.history_btf()
    assert len(b) > 3500 and b["maturity_date"].notna().all() and b["isin"].notna().mean() > 0.99
    s = A.history_syndications()
    assert (s["volume_mn"] < 0).sum() == 2                       # the two 2001/2002 buybacks


@needs_history
def test_year_end_positions_roll_and_bills_match_the_aft_total(tables):
    """31 December positions from 1999; Σ BTF at 31 Dec equals the AFT's own
    BTF total in the aggregate layer to the euro, 2009–2020."""
    pos, secs = tables["debt_positions"], tables["debt_securities"]
    ye = pos[pos["position_type"] == "rolled_from_flows"]
    assert ye["as_of"].min().year == 1999 and ye["as_of"].max().year >= 2025
    agg = R.class_aggregates_rows()
    btf = agg[(agg["measure"] == "stock_year_end") & (agg["sub_type"] == "btf")].set_index("year")["value_lcu_mn"]
    bills = set(secs.loc[secs["instrument_class"] == "bill", "security_id"])
    reg = ye[ye["security_id"].isin(bills)].groupby(ye["as_of"].dt.year)["nominal_lcu_mn"].sum()
    for y in range(2009, 2021):
        if y in btf.index and y in reg.index:
            assert abs(reg[y] - btf[y]) < 1.0, (y, reg[y], btf[y])


@needs_history
def test_linkers_uplifted_within_three_percent_of_the_aft_total(tables):
    pos, secs = tables["debt_positions"], tables["debt_securities"]
    agg = R.class_aggregates_rows()
    off = agg[(agg["measure"] == "stock_year_end") & (agg["sub_type"] == "oati_oatei")].set_index("year")["value_lcu_mn"]
    il = set(secs.loc[secs["instrument_class"] == "inflation_linked", "security_id"])
    ye = pos[(pos["position_type"] == "rolled_from_flows") & pos["security_id"].isin(il)]
    up = ye.groupby(ye["as_of"].dt.year)["nominal_uplifted_lcu_mn"].sum(min_count=1)
    checked = 0
    for y, v in off.items():
        if y in up.index and pd.notna(up[y]):
            assert abs(up[y] / v - 1) < 0.03, (y, up[y], v)
            checked += 1
    assert checked >= 10


@needs_history
def test_register_ratios_reproduce_the_auction_coefficients(tables):
    """The indexation coefficient the AFT prints for each linker auction is
    the register's ratio at settlement (office daily or recomputed)."""
    h = A.history_mlt()
    h = h[h["coefficient"].notna()]
    look = R._ratio_series(tables["debt_index_ratios"])
    diffs = [abs(r.coefficient - look(r.isin, r.settlement_date)) for r in h.itertuples(index=False)
             if look(r.isin, r.settlement_date) is not None]
    assert len(diffs) > 500 and max(diffs) < 1e-4


@needs_history
def test_stubs_are_dated_by_their_cause(tables):
    fl = tables["debt_flows"]
    imp = fl[fl["flow_type"] == "implied"]
    assert (imp["quality_grade"] == "C").all() and imp["notes"].str.contains("never allocated").all()
    early = imp[imp["settlement_date"] == R.REGISTER_START]
    assert (early["nominal_lcu_mn"] > 0).all()                    # pre-1999 issuance only
