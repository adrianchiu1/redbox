"""Regression probes for the engine's bookkeeping (D-S18-006), adapted from
the independent review of 12 October 2026: linker timing anchored on the
snapshot date, exact stock conservation, explicit surplus handling, input
validation, scenario subsets, and the constant-maturity-profile rule.
"""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from ggfiscal.debt import simulate as sim


def isolated_linker(maturity, **over):
    """EUR 100bn zero-coupon linker, no market rates, no other deficit, every
    euro of deficit financed: the only flows are its own uplift. The 2026
    interest anchor is set so that the bridge year's financed deficit equals
    the uplift accrued after the snapshot (the engine finances deficit ×
    share-of-year in 2026), so nothing is issued or in surplus."""
    share = (pd.Timestamp("2027-01-01") - pd.Timestamp(sim.SNAPSHOT)).days / 365
    uplift_2026 = 100.0 * (sim.index_factor("2027-01-01") - 1.0)
    base = replace(
        sim.BASELINE,
        bund_curve={0.25: 0.0, 30.0: 0.0}, spread_shape={0.25: 0.0, 30.0: 0.0},
        btf_stock=0.0, gg_wedge_pct=0.0, interest_receivable_pct=0.0,
        primary_balance={2025: 0.0, 2026: 0.0, 2027: 0.0},
        gg_interest_2026_bn=uplift_2026 / share, deficit_to_net_issuance=1.0, **over)
    sc = replace(sim.scenario(sim.REFERENCE), pb_change_bn={})
    reg = pd.DataFrame([{"security_id": "TEST", "name": "Test linker",
                         "instrument_class": "inflation_linked", "coupon": 0.0,
                         "maturity": pd.Timestamp(maturity), "nominal": 100.0, "uplift_ratio": 1.0}])
    mix = pd.Series({"7-10": 1.0}); mix.attrs["tenor"] = {"7-10": 10.0}
    return sim.run_scenario(sc, base, reg, mix).set_index("year")


def test_index_factor_is_anchored_on_the_snapshot_date():
    assert sim.index_factor(sim.SNAPSHOT) == 1.0
    one_year = pd.Timestamp(sim.SNAPSHOT) + pd.Timedelta(days=365)
    assert np.isclose(sim.index_factor(one_year), (1 + sim.BASELINE.inflation) ** (365 / 365.25), rtol=1e-9)
    f27 = sim.index_factor("2027-01-01")
    assert 1.0 < f27 < 1.01            # 113 days of 2% a year, not a whole year


def test_maturing_linker_redeems_at_its_maturity_index():
    r = isolated_linker("2027-07-02")
    f_start = sim.index_factor("2027-01-01")
    f_mat = sim.index_factor("2027-07-02")
    assert np.isclose(r.loc[2027, "uplift_bn"], 100 * (f_mat - f_start))
    assert np.isclose(r.loc[2027, "redemptions_bn"], 100 * f_mat)
    # what the review's probe meant: opening indexed principal plus the
    # uplift accrued to maturity is what is redeemed
    assert np.isclose(r.loc[2027, "redemptions_bn"], 100 * f_start + r.loc[2027, "uplift_bn"])


def test_surviving_linker_closes_at_the_year_end_index():
    r = isolated_linker("2040-07-02")
    f_start, f_end = sim.index_factor("2027-01-01"), sim.index_factor("2028-01-01")
    assert np.isclose(r.loc[2027, "uplift_bn"], 100 * (f_end - f_start))
    # no other deficit: the stock grows by exactly the uplift, nothing is issued
    assert np.isclose(r.loc[2027, "negotiable_stock_bn"], 100 * f_end)
    assert np.isclose(r.loc[2027, "negotiable_stock_bn"], 100 * f_start + r.loc[2027, "uplift_bn"])
    assert r.loc[2027, "mlt_gross_issuance_bn"] < 1e-9
    # 2026 bridge: the stock closes at the end-2026 index, not the snapshot's
    assert np.isclose(r.loc[2026, "negotiable_stock_bn"], 100 * sim.index_factor("2027-01-01"))


def test_stock_conservation_is_exact_in_every_scenario():
    res = sim.run_all()
    for _, g in res.groupby("scenario"):
        g = g.sort_values("year")
        resid = (g.negotiable_stock_bn.diff() - g.net_issuance_bn).dropna()
        assert np.allclose(resid, 0.0, atol=1e-8, rtol=0.0), resid.to_dict()


def test_financing_surplus_is_rejected_explicitly():
    sc = replace(sim.scenario(sim.REFERENCE), pb_change_bn={2028: 1000.0})
    with pytest.raises(sim.FinancingSurplus, match="(?i)buybacks"):
        sim.run_scenario(sc)
    assert issubclass(sim.FinancingSurplus, ValueError)


def test_missing_linker_index_is_rejected_before_aggregation():
    reg = sim.load_register()
    reg.loc[reg.instrument_class == "inflation_linked", "uplift_ratio"] = np.nan
    with pytest.raises(ValueError, match="(?i)(index|uplift)"):
        sim.run_scenario(sim.scenario(sim.REFERENCE), register=reg)


def test_missing_fixed_coupon_is_rejected(monkeypatch):
    original = sim._load

    def bad(name):
        frame = original(name)
        if name == "debt_securities":
            mask = (frame.iso3 == "FRA") & (frame.instrument_class == "fixed_bullet")
            frame.loc[mask, "coupon_pct"] = np.nan
        return frame

    monkeypatch.setattr(sim, "_load", bad)
    with pytest.raises(ValueError, match="(?i)coupon"):
        sim.load_register()


def test_duplicate_security_metadata_is_rejected(monkeypatch):
    original = sim._load
    sid = sim.load_register().security_id.iloc[0]

    def dup(name):
        frame = original(name)
        if name == "debt_securities":
            frame = pd.concat([frame, frame[(frame.iso3 == "FRA") & (frame.security_id == sid)]],
                              ignore_index=True)
        return frame

    monkeypatch.setattr(sim, "_load", dup)
    with pytest.raises(ValueError, match="(?i)duplicate"):
        sim.load_register()


def test_unmatched_position_and_unknown_class_are_rejected(monkeypatch):
    original = sim._load

    def orphan(name):
        frame = original(name)
        if name == "debt_positions":
            row = frame[(frame.iso3 == "FRA") & (frame.as_of == sim.SNAPSHOT)].iloc[[0]].copy()
            row["security_id"] = "FR_NOT_IN_SECURITIES"
            frame = pd.concat([frame, row], ignore_index=True)
        return frame

    monkeypatch.setattr(sim, "_load", orphan)
    with pytest.raises(ValueError, match="(?i)without security metadata"):
        sim.load_register()
    monkeypatch.undo()
    reg = sim.load_register()
    reg.loc[reg.index[0], "instrument_class"] = "floating"
    with pytest.raises(ValueError, match="(?i)unsupported instrument"):
        sim.validate_register(reg)


def test_run_all_accepts_subsets_and_keeps_the_order():
    subset = [sim.scenario("melenchon"), sim.scenario("philippe_majority")]
    r = sim.run_all(subset, feedback=False)
    assert list(dict.fromkeys(r.scenario)) == ["melenchon", "philippe_majority"]
    r = sim.run_all([sim.scenario("melenchon")])            # feedback on, coefficient zero
    assert set(r.scenario) == {"melenchon"}
    # with a live feedback the reference is resolved even when not requested
    live = replace(sim.BASELINE, spread_feedback_bp_per_pp=2.0)
    r = sim.run_all([sim.scenario("melenchon")], base=live)
    assert set(r.scenario) == {"melenchon"}
    assert (r.set_index("year").spread_bp.loc[2029:] > sim.scenario("melenchon").spread_2029_bp).any()


# ------------------------------------------------------------ issuance rules

def test_constant_profile_is_the_default_and_holds_the_bill_share():
    assert sim.BASELINE.issuance_rule == "constant_profile"
    w = sim.profile_weights(sim.load_register(), sim.BASELINE.profile_as_of)
    assert np.isclose(w.sum(), 1.0) and (w >= 0).all()
    r = sim.run_scenario(sim.scenario(sim.REFERENCE)).set_index("year")
    assert np.allclose(r.bill_share_of_stock, w["bill"])
    assert np.allclose(r.btf_stock, w["bill"] * r.negotiable_stock_bn)
    # buckets above their weight get nothing and keep their overshoot, which is
    # the reported deviation; the others are filled towards the target and
    # never beyond it
    assert (r.profile_deviation_bn >= 0).all()
    assert np.allclose(sum(r[f"profile_{b}"] for b in ["bill", *sim.BUCKETS]), 1.0)
    for y in r.index:
        over = sum(max(r.loc[y, f"profile_{b}"] - w[b], 0.0) for b in sim.BUCKETS) * r.loc[y, "negotiable_stock_bn"]
        assert np.isclose(over, r.loc[y, "profile_deviation_bn"], atol=1e-6)
    # the overshoot is mostly the two shortest buckets, fed by ageing (a
    # 26-year tranche also drops into 15–20 in one step, so not entirely)
    for y in r.index:
        short = sum(max(r.loc[y, f"profile_{b}"] - w[b], 0.0) for b in ("0-1", "1-2")) * r.loc[y, "negotiable_stock_bn"]
        assert short >= 0.5 * r.loc[y, "profile_deviation_bn"], y


def test_constant_mix_rule_is_selectable_and_reproduces_the_declared_rule():
    base = replace(sim.BASELINE, issuance_rule="constant_mix")
    r = sim.run_scenario(sim.scenario(sim.REFERENCE), base).set_index("year")
    assert np.allclose(r.btf_stock, base.btf_stock)
    assert (r.profile_deviation_bn == 0).all()
    mix = sim.issuance_mix()
    wam = sum(mix[b] * mix.attrs["tenor"][b] for b in mix.index)
    assert np.allclose(r.mlt_avg_maturity_at_issue.loc[2027:], wam)
    resid = (r.negotiable_stock_bn.diff() - r.net_issuance_bn).dropna()
    assert np.allclose(resid, 0.0, atol=1e-8)
    with pytest.raises(ValueError, match="issuance_rule"):
        sim.run_scenario(sim.scenario(sim.REFERENCE), replace(sim.BASELINE, issuance_rule="whatever"))


def test_tranches_land_in_their_bucket_at_the_year_end():
    mix = sim.issuance_mix()
    for b in sim.BUCKETS:
        T = sim.tranche_years(b, mix.attrs["tenor"].get(b, sim.BUCKET_TENOR[b]))
        assert str(sim._bucket_of([T - 0.5])[0]) == b
