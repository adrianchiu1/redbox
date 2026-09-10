"""Pure-logic engines of the debt extension on synthetic securities:
§7 interest (both bases), §7.1 nominal path with implied flows, DD7
bucketing and the maturity/issuance tables. No snapshots needed."""

import numpy as np
import pandas as pd
import pytest

from ggfiscal.debt import interest as I
from ggfiscal.debt import maturity as M

T = pd.Timestamp


def _sec(**kw) -> pd.Series:
    base = dict(iso3="GBR", security_id="X", isin=None, name="test", instrument_class="fixed_bullet",
                sub_type="gilt_conventional", currency="GBP", coupon_pct=4.0, coupon_frequency=2,
                day_count="ACT/ACT", first_issue_date=T("2010-01-15"), maturity_date=T("2030-06-07"),
                first_call_date=pd.NaT, dividend_dates="7 Jun/Dec", index_reference=None,
                index_lag_months=np.nan, base_index=np.nan, floating_reference=None,
                spread_bp=np.nan, is_green=False, issuer_unit="state")
    base.update(kw)
    return pd.Series(base)


def _positions(rows):
    return pd.DataFrame(rows, columns=["iso3", "security_id", "as_of", "nominal_lcu_mn",
                                       "nominal_uplifted_lcu_mn", "market_hands_lcu_mn",
                                       "position_type"])


def _flows(rows):
    return pd.DataFrame(rows, columns=["iso3", "security_id", "settlement_date", "flow_type",
                                       "nominal_lcu_mn", "cash_lcu_mn", "price_pct"])


# ------------------------------------------------------------------ §7.2/7.3

def test_fixed_bullet_full_year_accrues_and_pays_the_coupon():
    sec = _sec()
    pos = _positions([("GBR", "X", T("2019-12-31"), 1000.0, np.nan, np.nan, "office_snapshot")])
    fl = _flows([])
    rows = I.interest_for_security(sec, pos, fl, 2020)
    acc = next(r for r in rows if r["basis"] == "accrued")
    cash = next(r for r in rows if r["basis"] == "cash")
    assert acc["computability"] == "computed"
    assert acc["coupon_lcu_mn"] == pytest.approx(40.0, rel=1e-3)   # 4% of 1,000 over a full year
    assert cash["coupon_lcu_mn"] == pytest.approx(40.0)            # two 2% payments on 7 Jun / 7 Dec
    assert acc["total_lcu_mn"] == pytest.approx(40.0, rel=1e-3)


def test_issuance_mid_year_accrues_pro_rata_and_cash_pays_on_nominal_at_date():
    sec = _sec()
    pos = _positions([("GBR", "X", T("2019-12-31"), 1000.0, np.nan, np.nan, "office_snapshot")])
    fl = _flows([("GBR", "X", T("2020-06-07"), "auction", 1000.0, 1050.0, 105.0)])  # tap on the dividend date
    rows = I.interest_for_security(sec, pos, fl, 2020)
    acc = next(r for r in rows if r["basis"] == "accrued")
    cash = next(r for r in rows if r["basis"] == "cash")
    # accrued: 1,000 all year + 1,000 for Jun 7 -> Dec 31 (~57% of a year)
    assert 40.0 + 20.0 < acc["coupon_lcu_mn"] < 40.0 + 24.0
    # cash: Jun payment on 1,000 (tap settles that day), Dec payment on 2,000
    assert cash["coupon_lcu_mn"] == pytest.approx(20.0 + 40.0)
    # premium of 5% on 1,000 = 50, amortised over ~10 years -> ~2.8 in 2020's ~207 days
    assert 2.0 < acc["premium_discount_amort_lcu_mn"] < 3.5
    assert acc["total_lcu_mn"] == pytest.approx(acc["coupon_lcu_mn"] - acc["premium_discount_amort_lcu_mn"])


def test_redemption_year_stops_accrual_and_pays_final_coupon():
    sec = _sec(maturity_date=T("2020-06-07"))
    pos = _positions([("GBR", "X", T("2019-12-31"), 500.0, np.nan, np.nan, "office_snapshot")])
    fl = _flows([("GBR", "X", T("2020-06-07"), "redemption", 500.0, np.nan, np.nan)])
    rows = I.interest_for_security(sec, pos, fl, 2020)
    acc = next(r for r in rows if r["basis"] == "accrued")
    cash = next(r for r in rows if r["basis"] == "cash")
    assert cash["coupon_lcu_mn"] == pytest.approx(10.0)      # one final 2% payment on 500
    assert 8.5 < acc["coupon_lcu_mn"] < 10.5                  # Jan 1 -> Jun 7 accrual


# --------------------------------------------------------------------- §7.4

def test_linker_uplift_accrued_equals_nominal_times_ratio_change():
    sec = _sec(security_id="L", instrument_class="inflation_linked", coupon_pct=1.0,
               index_reference="UK_RPI", index_lag_months=3, dividend_dates="22 Mar/Sep",
               maturity_date=T("2035-03-22"))
    pos = _positions([("GBR", "L", T("2019-12-31"), 1000.0, 1500.0, np.nan, "office_snapshot")])
    fl = _flows([])
    ratios = pd.DataFrame({"iso3": "GBR", "security_id": "L",
                           "date": [T("2019-12-31"), T("2020-12-31")],
                           "index_ratio": [1.50, 1.53], "ratio_source": "office"})
    rows = I.interest_for_security(sec, pos, fl, 2020, ratios=ratios)
    acc = next(r for r in rows if r["basis"] == "accrued")
    cash = next(r for r in rows if r["basis"] == "cash")
    assert acc["uplift_lcu_mn"] == pytest.approx(1000.0 * 0.03, rel=1e-6)
    assert cash["uplift_lcu_mn"] == 0.0                       # paid at redemption only
    # cash coupons: 0.5% x 1,000 x IR on 22 Mar and 22 Sep (interpolated between 1.50 and 1.53)
    assert 2 * 5.0 * 1.50 < cash["coupon_lcu_mn"] < 2 * 5.0 * 1.53


def test_linker_without_ratios_is_not_computable():
    sec = _sec(security_id="L", instrument_class="inflation_linked", coupon_pct=1.0)
    pos = _positions([("GBR", "L", T("2019-12-31"), 1000.0, np.nan, np.nan, "office_snapshot")])
    rows = I.interest_for_security(sec, pos, _flows([]), 2020, ratios=pd.DataFrame(
        columns=["iso3", "security_id", "date", "index_ratio", "ratio_source"]))
    assert all(r["computability"] == "not_computable" for r in rows)
    assert all(r["total_lcu_mn"] is None for r in rows)


# --------------------------------------------------------------------- §7.5

def test_bill_discount_accretes_linearly():
    sec = _sec(security_id="B", instrument_class="bill", coupon_pct=np.nan, coupon_frequency=np.nan,
               dividend_dates=None, first_issue_date=T("2020-10-01"), maturity_date=T("2021-04-01"))
    pos = _positions([])
    fl = _flows([("GBR", "B", T("2020-10-01"), "tender", 1000.0, 995.0, 99.5)])
    r20 = {r["basis"]: r for r in I.interest_for_security(sec, pos, fl, 2020)}
    r21 = {r["basis"]: r for r in I.interest_for_security(sec, pos, fl, 2021)}
    assert r20["accrued"]["discount_lcu_mn"] + r21["accrued"]["discount_lcu_mn"] == pytest.approx(5.0)
    assert r20["accrued"]["discount_lcu_mn"] == pytest.approx(5.0 * 91 / 182, rel=1e-6)  # Oct 1 -> Dec 31
    assert r20["cash"]["discount_lcu_mn"] == 0.0 and r21["cash"]["discount_lcu_mn"] == pytest.approx(5.0)
    assert r20["accrued"]["coupon_lcu_mn"] == 0.0


# --------------------------------------------------------------------- §7.6

def test_floater_uses_fixing_at_period_start_and_declares_gaps():
    sec = _sec(security_id="F", instrument_class="floating", coupon_pct=np.nan, coupon_frequency=4,
               dividend_dates="1 Mar/Jun/Sep/Dec", floating_reference="UK_SONIA", spread_bp=10.0,
               maturity_date=T("2025-03-01"))
    pos = _positions([("GBR", "F", T("2019-12-31"), 1000.0, np.nan, np.nan, "office_snapshot")])
    ref = pd.Series(5.0, index=pd.date_range("2019-01-01", "2020-12-31", freq="D"))
    rows = {r["basis"]: r for r in I.interest_for_security(sec, pos, _flows([]), 2020, reference=ref)}
    assert rows["cash"]["floating_lcu_mn"] == pytest.approx(4 * (0.051 / 4) * 1000.0)
    assert rows["accrued"]["floating_lcu_mn"] == pytest.approx(0.051 * 1000.0, rel=2e-3)
    assert rows["accrued"]["computability"] == "computed"
    gap = {r["basis"]: r for r in I.interest_for_security(sec, pos, _flows([]), 2020, reference=None)}
    assert gap["accrued"]["computability"] == "not_computable"


# --------------------------------------------------------------------- §7.1

def test_nominal_path_rolls_flows_and_flags_implied_difference():
    pos = _positions([("GBR", "X", T("2019-12-31"), 1000.0, np.nan, np.nan, "office_snapshot"),
                      ("GBR", "X", T("2020-06-30"), 1300.0, np.nan, np.nan, "office_snapshot")])
    fl = _flows([("GBR", "X", T("2020-03-15"), "auction", 200.0, np.nan, np.nan),
                 ("GBR", "X", T("2020-09-15"), "buyback", 50.0, np.nan, np.nan)])
    path, implied = I.nominal_path("X", pos, fl, T("2020-01-01"), T("2020-12-31"))
    assert path[T("2020-01-01")] == 1000.0
    assert path[T("2020-03-15")] == 1200.0
    assert path[T("2020-06-30")] == 1300.0          # snapshot wins
    assert path[T("2020-12-31")] == 1250.0
    assert len(implied) == 1 and implied[0].nominal_lcu_mn == pytest.approx(100.0)


# ------------------------------------------------------------- DD7 buckets

def test_bucket_edges_are_right_closed_and_undated_is_30plus():
    assert M.bucket_of(0.5) == "0-1"
    assert M.bucket_of(1.0) == "0-1"
    assert M.bucket_of(1.0001) == "1-2"
    assert M.bucket_of(5.0) == "3-5"
    assert M.bucket_of(29.9) == "20-30"
    assert M.bucket_of(30.0) == "20-30"
    assert M.bucket_of(31.0) == "30+"
    assert M.bucket_of(float("inf")) == "30+"
    assert M.bucket_of(0.0) is None and M.bucket_of(-1.0) is None


def test_maturity_profile_and_issuance_by_residual_at_settlement():
    secs = pd.DataFrame([_sec(security_id="A", maturity_date=T("2021-06-07")),
                         _sec(security_id="B", maturity_date=T("2038-06-07")),
                         _sec(security_id="C", instrument_class="inflation_linked", maturity_date=T("2052-03-22")),
                         _sec(security_id="U", instrument_class="other", maturity_date=pd.NaT)])
    pos = _positions([("GBR", "A", T("2020-12-31"), 100.0, np.nan, 90.0, "office_snapshot"),
                      ("GBR", "B", T("2020-12-31"), 200.0, np.nan, 150.0, "office_snapshot"),
                      ("GBR", "C", T("2020-12-31"), 300.0, 450.0, np.nan, "office_snapshot"),
                      ("GBR", "U", T("2020-12-31"), 10.0, np.nan, np.nan, "office_snapshot")])
    prof = M.maturity_profile(secs, pos, T("2020-12-31"), "GBR")
    by = prof.set_index(["instrument_class", "bucket"])
    assert by.loc[("fixed_bullet", "0-1"), "nominal_lcu_mn"] == 100.0
    assert by.loc[("fixed_bullet", "15-20"), "nominal_lcu_mn"] == 200.0
    assert by.loc[("inflation_linked", "30+"), "nominal_uplifted_lcu_mn"] == 450.0
    assert by.loc[("other", "30+"), "nominal_lcu_mn"] == 10.0
    assert np.isnan(by.loc[("other", "30+"), "weighted_residual_years"])
    assert prof["nominal_lcu_mn"].sum() == 610.0

    fl = _flows([("GBR", "B", T("2024-03-01"), "tap", 50.0, 49.0, 98.0),       # 14.3y residual -> 10-15
                 ("GBR", "B", T("2024-09-01"), "auction", 50.0, 48.0, 96.0),   # 13.8y -> 10-15
                 ("GBR", "C", T("2024-03-01"), "syndication", 80.0, 100.0, np.nan),  # 28y -> 20-30
                 ("GBR", "A", T("2024-03-01"), "buyback", 5.0, np.nan, np.nan)])   # not issuance
    iss = M.issuance_by_bucket(secs, fl, 2024, "GBR")
    by = iss.set_index(["instrument_class", "bucket"])
    assert by.loc[("fixed_bullet", "10-15"), "gross_nominal_lcu_mn"] == 100.0
    assert by.loc[("fixed_bullet", "10-15"), "n_operations"] == 2
    assert by.loc[("inflation_linked", "20-30"), "gross_nominal_lcu_mn"] == 80.0
    assert iss["gross_nominal_lcu_mn"].sum() == 180.0
    assert 13.5 < by.loc[("fixed_bullet", "10-15"), "weighted_residual_years_at_issue"] < 14.5
