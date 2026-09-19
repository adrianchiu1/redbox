"""Stage D1 gate (DEBT_KICKOFF.md §12): reference series chained without
gaps; official totals present at steps B and C for every year they exist;
blocked sources carried as null rows, never fabricated."""

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.debt import model
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(), reason="no snapshots harvested")

CANON = config.repo_root() / "data" / "canonical"


@pytest.fixture(scope="module")
def ref():
    p = CANON / "debt_reference_series.csv"
    if not p.exists():
        pytest.skip("run `ggfiscal debt build` first")
    return pd.read_csv(p, parse_dates=["date"])


@pytest.fixture(scope="module")
def totals():
    p = CANON / "debt_official_totals.csv"
    if not p.exists():
        pytest.skip("run `ggfiscal debt build` first")
    return pd.read_csv(p)


def test_schemas_hold(ref, totals):
    model.REFERENCE_SERIES.validate(ref)
    model.OFFICIAL_TOTALS.validate(totals)


@pytest.mark.parametrize("sid,first,unit", [
    ("UK_RPI", "1947-06-01", "index"), ("FR_CPI_XT", "1990-01-01", "index"),
    ("EA_HICP_XT", "1999-12-01", "index"), ("UK_SONIA", "1997-01-02", "pct_pa"),
    ("UK_BANK_RATE", "1975-01-02", "pct_pa"), ("EA_MM_3M", "1990-01-01", "pct_pa"),
    ("DE_IR3", "1960-01-01", "pct_pa"), ("FR_IR3", "1970-01-01", "pct_pa"),
])
def test_reference_series_start_and_unit(ref, sid, first, unit):
    s = ref[ref["series_id"] == sid].sort_values("date")
    assert not s.empty
    assert s["date"].iloc[0] == pd.Timestamp(first)
    assert (s["unit"] == unit).all()
    assert s["date"].iloc[-1] >= pd.Timestamp("2026-01-01")


def test_monthly_indices_have_no_gaps(ref):
    for sid in ("UK_RPI", "FR_CPI_XT", "EA_HICP_XT"):
        s = ref[ref["series_id"] == sid].set_index("date")["value"].sort_index()
        months = pd.period_range(s.index.min(), s.index.max(), freq="M")
        assert len(s) == len(months), sid
        assert (s.pct_change().abs().dropna() < 0.05).all(), sid   # no base-break jump


def test_boe_curves_present(ref):
    assert (ref["series_id"] == "UK_GLC_NOMINAL_10Y").any()
    ten = ref[ref["series_id"] == "UK_GLC_NOMINAL_10Y"]
    assert ten["date"].min() <= pd.Timestamp("1980-01-31")


def test_steps_b_and_c_populated(totals):
    for iso3 in config.COUNTRIES:
        for chain, step in (("interest", "B_s1311_d41"), ("interest", "C_s13_gf01_7"),
                            ("financing", "B_s1311_b9"), ("financing", "C_s13_nlb")):
            s = totals[(totals["iso3"] == iso3) & (totals["chain"] == chain) & (totals["step"] == step)]
            lo = 1998 if (iso3, step) == ("GBR", "B_s1311_b9") else 1995   # ONS CG net borrowing CY block starts 1998
            assert s[(s["year"] >= lo) & (s["year"] <= 2024)]["value_lcu_mn"].notna().all(), (iso3, chain, step)


def test_blocked_sources_are_null_not_fabricated(totals):
    fra_a = totals[(totals["iso3"] == "FRA") & (totals["step"].isin(["A_cg_cash", "A_cg_cash_requirement"]))]
    assert fra_a["value_lcu_mn"].isna().all()
    assert (fra_a["quality_grade"] == "D").all()
    assert fra_a["item_source_id"].isin(["FRA_PLF_P117", "FRA_AFT_FINANCEMENT"]).all()


def test_gbr_step_a_is_fy_converted_and_close_to_step_b(totals):
    g = totals[(totals["iso3"] == "GBR") & (totals["chain"] == "interest")]
    a = g[g["step"] == "A_cg_cash"].set_index("year")
    b = g[g["step"] == "B_s1311_d41"].set_index("year")["value_lcu_mn"]
    assert a.loc[2024, "period_conversion_method"].startswith("0.25*FY")
    assert a.loc[2024, "period_basis"] == "FY"
    # NLF finance costs and ONS CG D.41 are the same concept from two accounts: within 10%
    for y in (2019, 2023, 2024):
        assert abs(a.loc[y, "value_lcu_mn"] / b[y] - 1) < 0.10, y


def test_step_c_matches_the_package(totals):
    from ggfiscal.debt.intermediates import package_gf01_7, package_nlb
    for iso3 in config.COUNTRIES:
        c = totals[(totals["iso3"] == iso3) & (totals["step"] == "C_s13_gf01_7")].set_index("year")["value_lcu_mn"]
        g = package_gf01_7(iso3)
        assert (c.reindex(g.index).round(6) == g.round(6)).all()
        assert c.index.min() <= g.index.min()
        pn = package_nlb(iso3)
        n = totals[(totals["iso3"] == iso3) & (totals["step"] == "C_s13_nlb")].set_index("year")["value_lcu_mn"]
        assert (n.reindex(pn.index).round(6) == pn.round(6)).all()
