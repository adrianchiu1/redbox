"""Stage E0 (EU3_KICKOFF.md): Italy, Spain and Belgium join on the Eurostat
family by configuration alone (DE5, DE6), and the FRA/DEU forecast
literals are gone (D-S17-001..005)."""

from __future__ import annotations

import inspect

import pytest

from ggfiscal import config
from ggfiscal.ingest import endpoints as E

EU3 = ("ITA", "ESP", "BEL")


def test_eu3_configured_on_the_eurostat_family():
    for iso3 in EU3:
        cfg = config.country(iso3)
        assert cfg["anchor_family"] == "eurostat"
        assert cfg["currency"] == "EUR"
        assert config.family(iso3).name == "eurostat"
        assert config.lines_absent(iso3) == {}
    assert config.eurostat_geos() == {"FRA": "FR", "DEU": "DE", "ITA": "IT", "ESP": "ES", "BEL": "BE"}
    assert config.eurostat_geo("GBR") is None and config.eurostat_geo("USA") is None


def test_eu3_registered_on_every_eu_wide_source():
    for sid in ("EUROSTAT_GOV10A_EXP", "EUROSTAT_GOV10A_MAIN", "EUROSTAT_GOV10A_TAXAG",
                "EUROSTAT_NAMA10_GDP", "EC_AGEING_2024", "EC_DSM"):
        assert E.registered_countries(sid) == ["FRA", "DEU", *EU3], sid
    for sid in ("IMF_GFS", "IMF_WEO", "OECD_RS", "OECD_T11", "EC_AMECO"):
        assert set(EU3) <= set(E.registered_countries(sid)), sid


def test_eurostat_pulls_follow_the_register():
    pulls = E.all_stage0_pulls()
    for ds in ("gov_10a_exp", "gov_10a_main", "gov_10a_taxag", "nama_10_gdp"):
        got = [(p.part, p.url) for p in pulls if f"/{ds}/" in p.url]
        assert [part for part, _ in got] == ["FRA", "DEU", *EU3], ds
        for part, url in got:
            assert url.endswith("." + config.eurostat_geo(part)) or f".{config.eurostat_geo(part)}?" in url, url


def test_level2_backward_legs_per_de3():
    # ITA and BEL publish Level II from 2001: the IMF GFS COFOG leg is enabled
    # as for DEU; ESP's Level II starts in 1995 in the anchor itself
    for iso3 in ("ITA", "BEL"):
        legs = config.backward_legs(iso3)
        assert "gfs_cofog" in legs and "{indicator}" in legs["gfs_cofog"]["level2_note"]
    assert config.backward_legs("ESP") == {}


def test_eu_projection_legs_are_registration_not_literals():
    from ggfiscal import coverage
    from ggfiscal.forecast import forward

    src = inspect.getsource(forward.forecasts_for)
    assert 'iso3 in ("FRA", "DEU")' not in src
    assert '_registered(iso3, "EC_DSM")' in src and '_registered(iso3, "EC_AGEING_2024")' in src
    assert 'iso3 in ("FRA", "DEU")' not in inspect.getsource(coverage.line_sources)
    for iso3 in ("FRA", "DEU", *EU3):
        assert forward._registered(iso3, "EC_DSM") and forward._registered(iso3, "EC_AGEING_2024")
    for iso3 in ("GBR", "USA"):
        assert not forward._registered(iso3, "EC_DSM")


def test_forecast_declarations_from_config():
    for iso3 in EU3:
        decl = config.forecast_declarations(iso3)
        assert decl, iso3
        for line, spec in decl.items():
            assert spec["status"] in {"no_official_forecast", "source_blocked",
                                      "no_machine_readable_source", "grade_below_strict"}
            assert len(spec["note"]) >= 30
    for iso3 in ("GBR", "FRA", "DEU", "USA"):
        assert config.forecast_declarations(iso3) == {}


def test_forecast_declarations_validated(monkeypatch):
    bad = {**config.countries(), "ITA": {**config.country("ITA"),
                                         "forecast_declarations": {"R01": {"status": "x"}}}}
    monkeypatch.setattr(config, "countries", lambda: bad)
    with pytest.raises(ValueError, match="lacks"):
        config.forecast_declarations("ITA")
