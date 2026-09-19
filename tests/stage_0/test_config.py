"""Stage 0 structural tests: the spec's line universe and register shape."""

from ggfiscal import config


def test_line_universe_is_99():
    """§1 fixed 66 (12 COFOG + 10 ESA_REV per country); D-S11-001 adds the
    GF10_2/GF10_X pension split and the nine-line ESA_EXP tree: 33 per
    country, 99 in all, enumerated from config rather than hard-coded."""
    universe = config.line_universe()
    assert len(universe) == 99 == config.universe_size()
    assert len(set(universe)) == 99
    for iso3 in config.COUNTRIES:
        mine = [u for u in universe if u[0] == iso3]
        assert len(mine) == 33
        assert sum(1 for u in mine if u[1] == "COFOG") == 14
        assert sum(1 for u in mine if u[1] == "ESA_EXP") == 9
        assert sum(1 for u in mine if u[1] == "ESA_REV") == 10
    # totals are never members
    assert not {u[2] for u in universe} & {"TE", "TE_ESA", "TR"}


def test_cofog_lines_match_spec():
    exp = config.lines()["expenditure"]
    expected = {"GF01", "GF01_7", "GF01_X", "GF02", "GF03", "GF04", "GF05",
                "GF06", "GF07", "GF08", "GF09", "GF10", "GF10_2", "GF10_X", "TE"}
    assert set(exp) == expected
    assert exp["GF01_X"]["never_forecast"] is True  # D10
    assert exp["GF10_X"]["never_forecast"] is True  # D-S11-002


def test_level2_splits_enumerate_from_config():
    splits = {s["level2"]: s for s in config.level2_splits()}
    assert set(splits) == {"GF01_7", "GF10_2"}
    assert splits["GF01_7"]["remainder"] == "GF01_X" and splits["GF01_7"]["fallback"] == "d41_payable"
    assert splits["GF10_2"]["remainder"] == "GF10_X" and splits["GF10_2"]["fallback"] is None
    assert splits["GF10_2"]["eurostat_cofog"] == "GF1002"
    assert splits["GF10_2"]["gfs_indicator"] == "GF1020_T"


def test_esa_exp_lines_match_spec():
    esa = config.lines()["expenditure_esa"]
    assert set(esa) == {f"E{n:02d}" for n in range(1, 10)} | {"TE_ESA"}
    assert config.total_code("ESA_EXP") == "TE_ESA"
    assert config.level1_lines("ESA_EXP") == [f"E{n:02d}" for n in range(1, 10)]
    for code, meta in esa.items():
        assert meta["eurostat_main"]["plus"] and meta["ons_t2"]["plus"], code


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
    assert set(no_fc["expenditure"]) == {"GF03", "GF04", "GF05", "GF06", "GF08",
                                         "GF01_X", "GF10_X"}
    assert no_fc["expenditure_esa"] == []
    assert set(no_fc["revenue"]) == {"R08", "R10"}


def test_tolerances_q4_defaults():
    tol = config.tolerances()
    assert tol["imf_gfs_reconciliation_pct"] == 0.5
    assert tol["sum_to_total_pct"] == 0.1
    assert tol["oecd_rs_reconciliation_pct"] == 3.0
