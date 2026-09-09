"""DD8 aggregate layer and the two chains built on it: additivity (V32),
no fabricated register totals, subsector legs closing the S.13 step."""

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.debt import model
from ggfiscal.debt.aggregates import SCHEMA as AGG_SCHEMA
from ggfiscal.debt.reconcile import CARRIED, OFFICIAL_TOTAL, RESIDUAL, check_additivity
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(), reason="no snapshots harvested")
CANON = config.repo_root() / "data" / "canonical"


def _load(name):
    p = CANON / f"{name}.csv"
    if not p.exists():
        pytest.skip("run `ggfiscal debt build` first")
    return pd.read_csv(p)


@pytest.fixture(scope="module")
def agg():
    return _load("debt_class_aggregates")


@pytest.fixture(scope="module")
def chains():
    return {c: _load(f"debt_{c}_reconciliation") for c in ("interest", "financing")}


def test_schemas(agg, chains):
    AGG_SCHEMA.validate(agg)
    model.INTEREST_RECONCILIATION.validate(chains["interest"])
    model.FINANCING_RECONCILIATION.validate(chains["financing"])


def test_v32_additivity_exact(chains):
    for c, df in chains.items():
        assert check_additivity(df) == [], c


def test_deu_aggregates_cover_1995_onward(agg):
    d = agg[(agg["iso3"] == "DEU") & agg["in_register"]]
    for m in ("stock_year_end", "gross_issuance", "redemptions", "interest", "net_issuance"):
        yrs = d[d["measure"] == m]["year"]
        assert yrs.min() <= 1996 and yrs.max() >= 2024, m
    stock24 = d[(d["measure"] == "stock_year_end") & (d["year"] == 2024)]["value_lcu_mn"].sum()
    assert 1_600_000 < stock24 < 1_750_000


def test_deu_interest_register_close_to_step_a(chains):
    df = chains["interest"]
    for y in (2000, 2010, 2020, 2024):
        g = df[(df["iso3"] == "DEU") & (df["year"] == y)].set_index(["step", "item"])["value_lcu_mn"]
        reg = g[("register", OFFICIAL_TOTAL)]
        off = g[("A_cg_cash", OFFICIAL_TOTAL)]
        assert abs(g[("A_cg_cash", RESIDUAL)]) < 5.0, y     # leaves + Mitfinanzierung item = published total
        assert reg > 0 and off > 0


def test_subsector_b9_closes_the_s13_step_for_fra_deu(chains):
    df = chains["financing"]
    for iso3 in ("FRA", "DEU"):
        g = df[(df["iso3"] == iso3) & (df["step"] == "C_s13_nlb") & (df["item"] == RESIDUAL)]
        recent = g[(g["year"] >= 2010) & (g["year"] <= 2024)]["value_lcu_mn"]
        assert recent.notna().all()
        assert (recent.abs() < 1.0).all(), iso3      # S.13 B.9 = Σ subsector B.9 in the source


def test_no_register_means_null_residual_not_zero(chains):
    """FRA has no reachable class-level interest: the register total must be
    null and the step-B residual null, while step C still reconciles."""
    df = chains["interest"]
    g = df[(df["iso3"] == "FRA") & (df["year"] == 2024)].set_index(["step", "item"])["value_lcu_mn"]
    assert pd.isna(g[("register", OFFICIAL_TOTAL)])
    assert pd.isna(g[("A_cg_cash", OFFICIAL_TOTAL)]) and pd.isna(g[("A_cg_cash", RESIDUAL)])
    assert pd.isna(g[("B_s1311_d41", RESIDUAL)])
    assert pd.notna(g[("C_s13_gf01_7", RESIDUAL)])
    assert g[("C_s13_gf01_7", CARRIED)] == g[("B_s1311_d41", OFFICIAL_TOTAL)]
