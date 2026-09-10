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
    assert abs(pos["nominal_lcu_mn"].sum() - e["outstanding_eur"].sum() / 1e6) < 1.0
    assert secs.loc[secs["instrument_class"] == "inflation_linked", "index_reference"].isin(
        ["FR_CPI_XT", "EA_HICP_XT"]).all()
