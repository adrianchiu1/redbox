"""Stage R0 (REPLICATION_KICKOFF.md §12, D27; D-S15-001..): the package is
generalised by configuration and readers. These tests need no harvest —
they pin the config keys, the anchor-family protocol and registry, the
"family not configured" error, the period-basis helpers and the
structural-zero plumbing's empty state for the three existing countries."""

import pytest

from ggfiscal import config
from ggfiscal.standardise import families as F
from ggfiscal.standardise import readers as R


# ---------------------------------------------------------------- config keys

def test_country_list_is_read_from_countries_yaml_in_file_order():
    assert config.COUNTRIES == tuple(config.countries())
    assert config.COUNTRIES == ("GBR", "FRA", "DEU")


def test_every_country_carries_the_r0_keys():
    for iso3, cfg in config.countries().items():
        for key in ("name", "currency", "anchor_family", "anchors", "gdp_source",
                    "lines_absent", "period_basis", "fy_to_cy_weights",
                    "envelope_forecast", "weo_perimeter_gap_expected", "perimeter_break"):
            assert key in cfg, (iso3, key)
        assert config.country_names()[iso3] == cfg["name"]


def test_r0_values_for_the_three_countries_change_no_behaviour():
    assert config.country("GBR")["anchor_family"] == "ons"
    assert config.country("FRA")["anchor_family"] == "eurostat"
    assert config.country("DEU")["anchor_family"] == "eurostat"
    for iso3 in config.COUNTRIES:
        assert config.lines_absent(iso3) == {}
        assert config.fy_to_cy_weights(iso3) == (0.25, 0.75)
        for cls in config.TREES:
            assert config.tree_period_basis(iso3, cls) == "CY"
        assert config.period_basis(iso3)["anchor"] == "CY"
    assert config.perimeter_break("DEU") == 1991
    assert config.perimeter_break("GBR") is None and config.perimeter_break("FRA") is None
    assert config.weo_perimeter_gap_expected("GBR") is True
    assert not config.weo_perimeter_gap_expected("FRA")
    assert not config.weo_perimeter_gap_expected("DEU")
    assert config.currencies() == ["GBP", "EUR"]
    assert config.country_names() == {"GBR": "United Kingdom", "FRA": "France",
                                      "DEU": "Germany"}


def test_unconfigured_country_raises_a_clear_error_everywhere():
    with pytest.raises(KeyError, match="not configured in config/countries.yaml"):
        config.country("USA")
    with pytest.raises(KeyError):
        config.lines_absent("USA")
    with pytest.raises(KeyError):
        config.fy_to_cy_weights("JPN")


def test_the_schema_admits_exactly_the_configured_countries_and_currencies():
    import pandas as pd

    from ggfiscal.model import _in_countries, _in_currencies

    assert _in_countries(pd.Series(["GBR", "FRA", "DEU"])).all()
    assert not _in_countries(pd.Series(["USA"])).any()
    assert _in_currencies(pd.Series(["GBP", "EUR"])).all()
    assert not _in_currencies(pd.Series(["USD"])).any()


def test_country_name_copies_and_flat_files_come_from_config():
    from ggfiscal import manifest as M
    from ggfiscal.forecast import statistical
    from ggfiscal.publish import flatten

    assert flatten.COUNTRY_NAME == config.country_names()
    assert statistical.COUNTRY_NAME == config.country_names()
    strict = [f for f in M.FLAT_FILES if "/strict_" in f]
    assert strict == [f"deliverables/strict_{iso3}.csv" for iso3 in config.COUNTRIES]


# ------------------------------------------------------------ anchor families

PROTOCOL_METHODS = ("cofog", "cofog_total", "main", "tax", "d41_payable", "gdp",
                    "totals", "level2")
SITE_METHODS = ("d41_receivable", "revenue_lines", "revenue_total", "revenue_coverage",
                "revenue_level2", "esa_exp_parts", "recon_revenue", "bridge_aggregates")


def test_family_registry_and_protocol():
    assert set(F.FAMILIES) == {"ons", "eurostat"}
    for name, cls in F.FAMILIES.items():
        fam = cls()
        assert fam.name == name
        assert isinstance(fam, F.AnchorFamily)
        for m in PROTOCOL_METHODS + SITE_METHODS:
            assert callable(getattr(fam, m)), (name, m)
        for attr in ("expenditure_source", "main_source", "tax_source",
                     "interest_history_source", "revenue_cell_key", "esa_exp_key"):
            assert getattr(fam, attr), (name, attr)


def test_config_family_routes_each_country_to_its_configured_family():
    assert isinstance(config.family("GBR"), F.OnsFamily)
    assert isinstance(config.family("FRA"), F.EurostatFamily)
    assert isinstance(config.family("DEU"), F.EurostatFamily)
    assert config.family("FRA") is config.family("DEU")        # one instance per family
    assert config.family("GBR").expenditure_source == "ONS_ESA_T11"
    assert config.family("FRA").expenditure_source == "EUROSTAT_GOV10A_EXP"
    assert config.family("GBR").gdp("GBR")[1] == "ONS_GDP"
    assert config.family("DEU").gdp("DEU")[1] == "EUROSTAT_NAMA10_GDP"


def test_unconfigured_family_raises_and_never_falls_through(monkeypatch):
    """Gate R0: a dry config.family("USA") raises a clear "family not
    configured" error — an unknown country, a country block without
    `anchor_family`, and a family name with no implementation all raise;
    none of them returns another country's family."""
    with pytest.raises(KeyError, match="not configured"):
        config.family("USA")
    base = config.countries()
    monkeypatch.setattr(config, "countries",
                        lambda: {**base, "USA": {"currency": "USD", "name": "United States"}})
    with pytest.raises(F.FamilyNotConfigured, match="no `anchor_family`"):
        config.family("USA")
    monkeypatch.setattr(config, "countries",
                        lambda: {**base, "USA": {"currency": "USD", "name": "United States",
                                                 "anchor_family": "oecd_sna"}})
    with pytest.raises(F.FamilyNotConfigured, match="not implemented"):
        config.family("USA")


def test_families_wrap_the_existing_readers_unchanged():
    """The family methods are the same reader calls the routing sites made
    before R0 (byte identity of the canonical layer rests on this)."""
    ons, eu = F.OnsFamily(), F.EurostatFamily()
    assert ons.cofog("GBR", "GF01").equals(R.ons_cofog("GF01"))
    assert ons.cofog_total("GBR").equals(R.ons_cofog("_T"))
    assert ons.main("GBR", "D41", "payable").equals(R.ons_t2_series("D41", "payable"))
    assert ons.d41_payable("GBR").equals(R.ons_t2_series("D41", "payable"))
    assert ons.tax("GBR", "D211").equals(R.ons_tax_series("D211"))
    assert ons.totals("GBR")["TE"].equals(R.ons_t2_series("OTE", ""))
    for iso3 in ("FRA", "DEU"):
        assert eu.cofog(iso3, "GF01").equals(R.eurostat_cofog(iso3, "GF01"))
        assert eu.cofog_total(iso3).equals(R.eurostat_cofog(iso3, "TOTAL"))
        assert eu.main(iso3, "D41PAY").equals(R.eurostat_main(iso3, "D41PAY"))
        assert eu.tax(iso3, "D211").equals(R.eurostat_taxag(iso3, "D211"))
        assert eu.totals(iso3)["B9"].equals(R.eurostat_main(iso3, "B9"))
        assert eu.gdp(iso3)[0].equals(R.eurostat_gdp(iso3))
    # Level II: a COFOG line's own cell; None for a line with no cell
    assert ons.level2("GBR", "GF01_7").equals(R.ons_cofog("GF0107"))
    assert eu.level2("FRA", "GF10_2").equals(R.eurostat_cofog("FRA", "GF1002"))
    assert eu.level2("FRA", "GF01") is None


def test_no_routing_site_decides_by_country_literal():
    """The twelve routing sites of REPLICATION_SCOPING.md §6 F1 call the
    family: no site reads an ONS or Eurostat anchor reader directly, and no
    `iso3 == "GBR"` anchor routing remains. The one country literal left in
    `coverage.line_sources` is the GF10_2 forecast-candidate declaration
    (Ageing Report for FRA/DEU, the OBR historical series for GBR) — a
    per-country source declaration of the kind forward.py and backward.py
    carry (kickoff C4/C5), not anchor routing."""
    import inspect

    from ggfiscal import build, coverage
    from ggfiscal.reconcile import bridge, recon_v0
    from ggfiscal.validate import stage1, stage3

    for mod, fn in ((build, "anchor_series"), (build, "_revenue_level2"),
                    (build, "gdp_series"), (build, "build"),
                    (coverage, "_cofog_sources"), (coverage, "line_sources"),
                    (bridge, "anchor_aggregates"), (recon_v0, "_anchor_cofog"),
                    (recon_v0, "compute"), (stage1, "check_v21"), (stage3, "_envelopes")):
        src = inspect.getsource(getattr(mod, fn))
        assert "R.ons_" not in src and "R.eurostat_" not in src, (mod.__name__, fn)
        literals = src.count('iso3 == "GBR"') + src.count('iso3 in ("FRA", "DEU")')
        allowed = 2 if (mod, fn) == (coverage, "line_sources") else 0
        assert literals == allowed, (mod.__name__, fn, literals)
    src = inspect.getsource(coverage.line_sources)
    for lit in ('iso3 == "GBR"', 'iso3 in ("FRA", "DEU")'):
        i = src.index(lit)
        assert 'l2 == "GF10_2"' in src[i - 40:i], "only the GF10_2 candidates may name a country"


def test_envelope_source_is_config_not_a_country_literal():
    from ggfiscal.forecast import envelopes as E

    assert E.envelope_source("GBR") == "OBR_EFO_LATEST"
    assert E.envelope_source("FRA") == "EC_AMECO"
    assert set(E.ENVELOPE_READERS) >= {"OBR_EFO_LATEST", "EC_AMECO"}
    with pytest.raises(KeyError):
        E.envelope_source("USA")


# ---------------------------------------------------------- structural zeros

def test_absent_lines_resolve_to_a_tree_and_reject_unknown_codes(monkeypatch):
    base = config.countries()
    assert config.absent_lines("GBR") == {}
    monkeypatch.setattr(config, "countries", lambda: {
        **base, "GBR": {**base["GBR"], "lines_absent": {"R01": "no VAT (test)",
                                                        "GF05": "no function (test)"}}})
    assert config.absent_lines("GBR") == {("ESA_REV", "R01"): "no VAT (test)",
                                          ("COFOG", "GF05"): "no function (test)"}
    monkeypatch.setattr(config, "countries", lambda: {
        **base, "GBR": {**base["GBR"], "lines_absent": {"TR": "a total"}}})
    with pytest.raises(ValueError, match="not a granular line"):
        config.absent_lines("GBR")


@pytest.mark.skipif(not R.latest_snapshots(), reason="no snapshots harvested")
def test_structural_zero_plumbing_is_exercised_on_a_declared_absence(monkeypatch):
    """D20 (empty for GBR/FRA/DEU): declare one absence on a copy of the
    config and check the anchor layer publishes zero rows in every anchor
    year of the tree, typed structural_zero, with the reason — and that the
    identity check treats the line as zero."""
    import pandas as pd

    from ggfiscal.build import anchor_series
    from ggfiscal.validate.stage1 import _with_structural_zeros

    base = config.countries()
    monkeypatch.setattr(config, "countries", lambda: {
        **base, "FRA": {**base["FRA"], "lines_absent": {"R01": "no VAT (test)",
                                                        "GF10_5": "no group (test)"}}})
    series = anchor_series("FRA")
    tr = series[("ESA_REV", "TR")]["series"]
    r01 = series[("ESA_REV", "R01")]
    assert r01["observation_type"] == "structural_zero"
    assert r01["notes"] == "structural zero (D20): no VAT (test)"
    assert list(r01["series"].index) == list(tr.index) and (r01["series"] == 0).all()
    assert r01["source_id"] == series[("ESA_REV", "TR")]["source_id"]
    gf10_5 = series[("COFOG", "GF10_5")]
    gf10 = series[("COFOG", "GF10")]["series"]
    assert gf10_5["observation_type"] == "structural_zero"
    assert list(gf10_5["series"].index) == list(gf10.index)
    # the remainder absorbs the whole parent less the other Level II line
    rem = series[("COFOG", "GF10_X")]["series"]
    gf10_2 = series[("COFOG", "GF10_2")]["series"]
    common = rem.index.intersection(gf10_2.index)
    assert ((gf10[common] - gf10_2[common]) - rem[common]).abs().max() < 1e-6
    piv = pd.DataFrame({"R02": [1.0, 2.0]}, index=[2000, 2001])
    filled = _with_structural_zeros(piv, "FRA", ["R01", "R02"])
    assert (filled["R01"] == 0).all()


def test_structural_zero_plumbing_is_empty_for_the_three_countries():
    from ggfiscal.model import OBSERVATION_TYPES

    assert "structural_zero" in OBSERVATION_TYPES
    for iso3 in config.COUNTRIES:
        assert config.absent_lines(iso3) == {}


# ------------------------------------------------------------- period basis

def test_fy_to_cy_takes_the_country_weights():
    """§7.10 generalised (D19): the weights are per country. The default pair
    is the April–March one the GBR sources always used; an October–September
    source (US federal) takes 0.75/0.25."""
    import pandas as pd

    from ggfiscal.forecast.forward import fy_to_cy

    fy = pd.Series({2025: 100.0, 2026: 200.0, 2027: 300.0})
    default = fy_to_cy(fy)
    gbr = fy_to_cy(fy, config.fy_to_cy_weights("GBR"))
    assert default.equals(gbr)
    assert gbr[2026] == 0.25 * 100 + 0.75 * 200
    us = fy_to_cy(fy, (0.75, 0.25))
    assert list(us.index) == [2026, 2027]
    assert us[2026] == 0.75 * 100 + 0.25 * 200 and us[2027] == 0.75 * 200 + 0.25 * 300
    from ggfiscal.debt.intermediates import fy_to_cy as debt_fy_to_cy
    assert debt_fy_to_cy(fy, (0.25, 0.75)).to_dict() == gbr.to_dict()


def test_source_period_basis_comes_from_the_register():
    for sid in ("OBR_EFO_LATEST", "OBR_PSF_DATABANK", "OBR_HIST_PF", "HMT_PESA", "OBR_FRS"):
        assert config.source_period_basis(sid) == "FY", sid
    for sid in ("EC_AMECO", "EUROSTAT_GOV10A_MAIN", "ONS_ESA_T11", "IMF_GFS", "EC_DSM"):
        assert config.source_period_basis(sid) == "CY", sid
    assert config.source_period_basis("NOT_A_SOURCE") == "CY"


def test_row_labels_follow_the_tree_basis(monkeypatch):
    """D19: a CY tree labels rows by calendar year; a FY-labelled tree by
    FY + starting year, stamped FY on every row."""
    assert config.fy_label("GBR", 2023, "COFOG") == "2023"
    base = config.countries()
    monkeypatch.setattr(config, "countries", lambda: {
        **base, "GBR": {**base["GBR"], "period_basis": {
            "anchor": "CY", "trees": {"expenditure": "FY"}, "fy_start_month": 4,
            "fy_label": "start_year"}}})
    assert config.tree_period_basis("GBR", "COFOG") == "FY"
    assert config.tree_period_basis("GBR", "ESA_REV") == "CY"     # defaults stay CY
    assert config.fy_label("GBR", 2023, "COFOG") == "FY2023"
    assert config.fy_label("GBR", 2023, "ESA_REV") == "2023"


@pytest.mark.skipif(not R.latest_snapshots(), reason="no snapshots harvested")
def test_fy_cy_bridge_is_built_and_empty_for_cy_trees(monkeypatch):
    """The FY/CY bridge (D19) is empty while every tree is CY, and fills —
    additively — the moment a tree is declared FY-labelled."""
    from ggfiscal.build import FY_CY_BRIDGE_COLUMNS, anchor_series, fy_cy_bridge_rows

    series = anchor_series("FRA")
    assert fy_cy_bridge_rows("FRA", series, "test") == []
    base = config.countries()
    monkeypatch.setattr(config, "countries", lambda: {
        **base, "FRA": {**base["FRA"], "period_basis": {
            "anchor": "CY", "trees": {"expenditure": "FY"}}}})
    rows = fy_cy_bridge_rows("FRA", series, "test")
    assert rows and set(rows[0]) == set(FY_CY_BRIDGE_COLUMNS)
    te = series[("COFOG", "TE")]["series"]
    assert [r["year"] for r in rows] == [int(y) for y in te.index]
    for r in rows:
        assert r["fy_label"] == f"FY{r['year']}"
        assert r["te_fy_lcu_mn"] == float(te[r["year"]])
        if r["te_cy_lcu_mn"] is not None:
            assert abs(r["gap_lcu_mn"] - (r["te_fy_lcu_mn"] - r["te_cy_lcu_mn"])) < 1e-9
            assert r["timing_component_lcu_mn"] is None
            assert r["residual_lcu_mn"] == r["gap_lcu_mn"]


def test_v41_and_v42_are_registered_from_stage_1():
    from ggfiscal.validate import r0
    from ggfiscal.validate.runner import V_SUITE_STAGE

    assert V_SUITE_STAGE["V41"] == 1 and V_SUITE_STAGE["V42"] == 1
    assert set(r0.IMPLEMENTED) == {"V41", "V42"}


# ------------------------------------------------ perimeter rules from config

def test_perimeter_rules_are_read_from_config_not_country_literals():
    import inspect

    from ggfiscal.reconcile import bridge
    from ggfiscal.stitch import backward
    from ggfiscal.validate import stage5

    for mod, fn in ((bridge, "compute"), (stage5, "check_v24")):
        src = inspect.getsource(getattr(mod, fn))
        assert 'iso3 == "GBR"' not in src, (mod.__name__, fn)
    # the backward registry keeps per-country *source* declarations (the
    # ONS D.41 and OBR pensioner legs are GBR sources); the break is config
    assert "DEU_BREAK" not in inspect.getsource(backward)
    assert not hasattr(backward, "DEU_BREAK")
    assert "perimeter_sigma_pct_te" in config.tolerances()
    assert "gbr_perimeter_sigma_pct_te" not in config.tolerances()


@pytest.mark.skipif(not R.latest_snapshots(), reason="no snapshots harvested")
def test_every_extension_source_stops_at_the_configured_perimeter_break():
    from ggfiscal.stitch.backward import extensions_for

    for iso3 in config.COUNTRIES:
        want = config.perimeter_break(iso3)
        for key, sources in extensions_for(iso3).items():
            for src in sources:
                assert src.break_before == want, (iso3, key, src.source_id)


# ------------------------------------------- generic IMF GFS backward legs

def test_gfs_backward_legs_are_config_enabled():
    assert config.backward_legs("GBR") == {} and config.backward_legs("FRA") == {}
    deu = config.backward_legs("DEU")
    assert set(deu) == {"gfs_cofog", "gfs_soo"} and deu["gfs_soo"] is None
    assert "{indicator}" in deu["gfs_cofog"]["level2_note"]


@pytest.mark.skipif(not R.latest_snapshots(), reason="no snapshots harvested")
def test_gfs_legs_follow_the_config_not_a_country_literal(monkeypatch):
    import inspect

    from ggfiscal.stitch import backward

    assert 'iso3 == "DEU"' not in inspect.getsource(backward.extensions_for)
    deu = backward.extensions_for("DEU")
    for n in range(1, 11):
        srcs = deu[("COFOG", f"GF{n:02d}")]
        assert [s.source_id for s in srcs] == ["IMF_GFS"] and srcs[0].break_before == 1991
        assert srcs[0].concept_note == config.backward_legs("DEU")["gfs_cofog"]["level1_note"]
    assert deu[("COFOG", "GF10_2")][0].concept_note.startswith("IMF GFS COFOG group GF1020_T")
    assert ("COFOG", "GF04_5") not in deu                       # no GFS group series for 04.5
    for iso3 in ("GBR", "FRA"):
        ext = backward.extensions_for(iso3)
        assert ("COFOG", "GF02") not in ext
        assert all(s.source_id != "IMF_GFS" for v in ext.values() for s in v)
    # enabling the SOO leg for a country appends it after AMECO on every ESA_EXP line with a code
    base = config.countries()
    monkeypatch.setattr(config, "countries", lambda: {
        **base, "FRA": {**base["FRA"], "backward_legs": {
            "gfs_soo": {"note": "IMF GFS SOO {indicator}: {label} (test)"}}}})
    ext = backward.extensions_for("FRA")
    e01 = ext[("ESA_EXP", "E01")]
    assert [s.source_id for s in e01] == ["EC_AMECO", "IMF_GFS"]
    assert e01[1].concept_note == "IMF GFS SOO G21_T: Compensation of employees (test)"
    assert [s.source_id for s in ext[("ESA_EXP", "E03")]] == ["EC_AMECO"]   # no gfs_soo code
