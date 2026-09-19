"""Stage 0 structural tests: the spec's line universe and register shape."""

from ggfiscal import config


def test_line_universe_is_123():
    """§1 fixed 66 (12 COFOG + 10 ESA_REV per country); D-S11-001 adds the
    nine-line ESA_EXP tree and the GF10_2 pension split; D-S11-005 adds
    GF10_5, GF04_5, R02_A and R06_E/R06_H with their remainders: 41 per
    country, 123 in all, enumerated from config rather than hard-coded."""
    universe = config.line_universe()
    assert len(universe) == 123 == config.universe_size()
    assert len(set(universe)) == 123
    for iso3 in config.COUNTRIES:
        mine = [u for u in universe if u[0] == iso3]
        assert len(mine) == 41
        assert sum(1 for u in mine if u[1] == "COFOG") == 17
        assert sum(1 for u in mine if u[1] == "ESA_EXP") == 9
        assert sum(1 for u in mine if u[1] == "ESA_REV") == 15
    # totals are never members
    assert not {u[2] for u in universe} & {"TE", "TE_ESA", "TR"}


def test_cofog_lines_match_spec():
    exp = config.lines()["expenditure"]
    expected = {f"GF{n:02d}" for n in range(1, 11)} | {"GF01_7", "GF01_X", "GF04_5", "GF04_X", "GF10_2", "GF10_5", "GF10_X"} | {"TE"}
    assert set(exp) == expected
    for rem in ("GF01_X", "GF04_X", "GF10_X"):
        assert exp[rem]["never_forecast"] is True  # D10 / D-S11-002 / D-S11-005


def test_level2_splits_enumerate_from_config():
    splits = {(s["classification"], s["parent"]): s for s in config.level2_splits()}
    assert set(splits) == {("COFOG", "GF01"), ("COFOG", "GF04"), ("COFOG", "GF10"),
                           ("ESA_REV", "R02"), ("ESA_REV", "R06")}
    gf01 = splits[("COFOG", "GF01")]
    assert gf01["level2s"] == ["GF01_7"] and gf01["remainder"] == "GF01_X"
    assert gf01["meta"]["GF01_7"]["fallback"] == "d41_payable"
    gf10 = splits[("COFOG", "GF10")]
    assert gf10["level2s"] == ["GF10_2", "GF10_5"] and gf10["remainder"] == "GF10_X"
    assert gf10["meta"]["GF10_2"]["eurostat_cofog"] == "GF1002"
    assert gf10["meta"]["GF10_2"]["gfs_indicator"] == "GF1020_T"
    assert gf10["meta"]["GF10_5"]["fallback"] is None
    assert splits[("COFOG", "GF04")]["level2s"] == ["GF04_5"]
    r06 = splits[("ESA_REV", "R06")]
    assert r06["level2s"] == ["R06_E", "R06_H"] and r06["remainder"] == "R06_X"
    assert r06["meta"]["R06_E"]["oecd_rs"] == ["T_2200"]
    assert r06["meta"]["R06_H"]["oecd_rs"] == ["T_2100", "T_2300"]
    assert splits[("ESA_REV", "R02")]["meta"]["R02_A"]["eurostat"]["codes"] == ["D214A", "D2122C"]
    rev = config.lines()["revenue"]
    for rem in ("R02_X", "R06_X"):
        assert rev[rem]["never_forecast"] is True


def test_esa_exp_lines_match_spec():
    esa = config.lines()["expenditure_esa"]
    assert set(esa) == {f"E{n:02d}" for n in range(1, 10)} | {"TE_ESA"}
    assert config.total_code("ESA_EXP") == "TE_ESA"
    assert config.level1_lines("ESA_EXP") == [f"E{n:02d}" for n in range(1, 10)]
    for code, meta in esa.items():
        assert meta["eurostat_main"]["plus"] and meta["ons_t2"]["plus"], code


def test_revenue_lines_match_spec():
    rev = config.lines()["revenue"]
    assert set(rev) == {f"R{n:02d}" for n in range(1, 11)} | {"R02_A", "R02_X", "R06_E", "R06_H", "R06_X"} | {"TR"}
    assert config.level1_lines("ESA_REV") == [f"R{i:02d}" for i in range(1, 11)]


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
                                         "GF01_X", "GF10_X", "GF04_5", "GF04_X", "GF10_5"}
    assert no_fc["expenditure_esa"] == []
    assert set(no_fc["revenue"]) == {"R08", "R10", "R02_X", "R06_X"}


def test_tolerances_q4_defaults():
    tol = config.tolerances()
    assert tol["imf_gfs_reconciliation_pct"] == 0.5
    assert tol["sum_to_total_pct"] == 0.1
    assert tol["oecd_rs_reconciliation_pct"] == 3.0
