"""§8 chain assembly: residual per step, never allocated; V32 additivity."""

import math

import pandas as pd

from ggfiscal.debt.reconcile import CARRIED, OFFICIAL_TOTAL, RESIDUAL, ChainItem, assemble, check_additivity
from ggfiscal.debt.model import INTEREST_STEPS


def _chain(official_b=None):
    items = [
        ChainItem("register", "sum_fixed_bullet", 40.0, "computed", None, "accrued"),
        ChainItem("register", "sum_inflation_linked", 15.0, "computed", None, "accrued"),
        ChainItem("A_cg_cash", "non_marketable_interest", 3.0, "official", "HMT_NLF"),
        ChainItem("A_cg_cash", "uplift_timing", -5.0, "declared"),
        ChainItem("A_cg_cash", OFFICIAL_TOTAL, 54.0, "official", "HMT_NLF", "cash"),
        ChainItem("B_s1311_d41", "premium_discount_amortisation", 2.0, "official", "ONS"),
        ChainItem("B_s1311_d41", OFFICIAL_TOTAL, official_b, "official", "ONS", "accrued"),
        ChainItem("C_s13_gf01_7", "subnational", 4.0, "official", "ONS"),
        ChainItem("C_s13_gf01_7", OFFICIAL_TOTAL, 62.0, "official", "package_GF01_7", "accrued"),
    ]
    return assemble("GBR", 2024, INTEREST_STEPS, items)


def test_residual_is_official_minus_carried_minus_bridges():
    ch = _chain(official_b=57.0)
    d = ch.set_index(["step", "item"])["value_lcu_mn"]
    assert d[("register", OFFICIAL_TOTAL)] == 55.0
    assert d[("A_cg_cash", CARRIED)] == 55.0
    assert d[("A_cg_cash", RESIDUAL)] == 54.0 - (55.0 + 3.0 - 5.0)
    assert d[("B_s1311_d41", CARRIED)] == 54.0
    assert d[("B_s1311_d41", RESIDUAL)] == 57.0 - (54.0 + 2.0)
    assert d[("C_s13_gf01_7", RESIDUAL)] == 62.0 - (57.0 + 4.0)
    assert check_additivity(ch) == []
    assert set(ch["item_type"]) <= {"computed", "official", "declared", "residual"}


def test_missing_official_total_gives_nan_residual_and_carries_forward():
    ch = _chain(official_b=None)
    d = ch.set_index(["step", "item"])["value_lcu_mn"]
    assert math.isnan(d[("B_s1311_d41", RESIDUAL)])
    assert math.isnan(d[("B_s1311_d41", OFFICIAL_TOTAL)])
    # step C carries A's total plus B's declared bridge (56), not a fabricated B total
    assert d[("C_s13_gf01_7", CARRIED)] == 56.0
    assert d[("C_s13_gf01_7", RESIDUAL)] == 62.0 - 60.0
    assert check_additivity(ch) == []


def test_additivity_check_catches_tampering():
    ch = _chain(official_b=57.0)
    ch.loc[(ch["step"] == "A_cg_cash") & (ch["item"] == RESIDUAL), "value_lcu_mn"] += 1.0
    assert any("A_cg_cash" in p for p in check_additivity(ch))
