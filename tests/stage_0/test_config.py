"""Stage 0 structural tests: the spec's line universe and register shape."""

from ggfiscal import config


def test_line_universe_is_66():
    universe = config.line_universe()
    assert len(universe) == 66
    # 22 per country: 12 COFOG + 10 ESA_REV (§1)
    for iso3 in config.COUNTRIES:
        mine = [u for u in universe if u[0] == iso3]
        assert len(mine) == 22
        assert sum(1 for u in mine if u[1] == "COFOG") == 12
        assert sum(1 for u in mine if u[1] == "ESA_REV") == 10


def test_cofog_lines_match_spec():
    exp = config.lines()["expenditure"]
    expected = {"GF01", "GF01_7", "GF01_X", "GF02", "GF03", "GF04", "GF05",
                "GF06", "GF07", "GF08", "GF09", "GF10", "TE"}
    assert set(exp) == expected
    assert exp["GF01_X"]["never_forecast"] is True  # D10


def test_revenue_lines_match_spec():
    rev = config.lines()["revenue"]
    assert set(rev) == {f"R{i:02d}" for i in range(1, 11)} | {"TR"}


def test_anchors_per_d1():
    c = config.countries()
    assert c["GBR"]["anchors"]["expenditure"] == "ONS_ESA_T11"
    assert c["FRA"]["anchors"]["expenditure"] == "EUROSTAT_GOV10A_EXP"
    assert c["DEU"]["anchors"]["expenditure"] == "EUROSTAT_GOV10A_EXP"
    # Eurostat carries no UK government-finance data (D1)
    assert "EUROSTAT" not in c["GBR"]["anchors"]["revenue"]


def test_weo_registered_reconciliation_only():
    src = config.sources()["IMF_WEO"]
    assert src["role"] == "reconciliation_only"  # D4/D13: never an envelope or extension


def test_d7_no_forecast_lines_declared():
    no_fc = config.no_forecast_lines()
    assert set(no_fc["expenditure"]) == {"GF03", "GF04", "GF05", "GF06", "GF08", "GF01_X"}
    assert set(no_fc["revenue"]) == {"R08", "R10"}


def test_tolerances_q4_defaults():
    tol = config.tolerances()
    assert tol["imf_gfs_reconciliation_pct"] == 0.5
    assert tol["sum_to_total_pct"] == 0.1
    assert tol["oecd_rs_reconciliation_pct"] == 3.0
