"""R0 step 8 (D-S15-008): the debt engine routes every country through
config/debt.yaml `countries` — no `else` branch, no country literal decides
a path, and an unconfigured country raises. Config and routing only: no
debt snapshot is needed."""

import inspect

import pytest

from ggfiscal import config
from ggfiscal.debt import aggregates, chains, countries as DC, intermediates, reference, register, validate


def test_every_country_is_declared_with_its_engine_modules():
    cfg = DC.configured()
    assert set(cfg) == set(config.COUNTRIES)
    assert list(cfg) == ["DEU", "GBR", "FRA"]        # the engines' historical concatenation order
    for iso3, c in cfg.items():
        for role in ("register", "aggregates", "official_totals"):
            assert c.get(role), (iso3, role)
        assert "subsector_source" in c and "v31_official" in c
    assert cfg["GBR"]["subsector_source"] is None
    assert cfg["FRA"]["subsector_source"] == cfg["DEU"]["subsector_source"] == "EUROSTAT_GOV10A_MAIN_S1311"
    assert cfg["GBR"]["v31_official"]["kind"] == "same_source"
    assert cfg["FRA"]["v31_official"]["kind"] == cfg["DEU"]["v31_official"]["kind"] == "eurostat_gd_f3"


def test_module_specs_resolve_to_the_existing_builders():
    assert DC.builder("GBR", "official_totals", "official_totals") is intermediates.official_totals_gbr
    assert DC.builder("FRA", "official_totals", "official_totals") is intermediates.official_totals_fra
    assert DC.builder("DEU", "official_totals", "official_totals") is intermediates.official_totals_deu
    assert DC.builder("DEU", "aggregates", "class_aggregates") is aggregates.deu_class_aggregates
    from ggfiscal.debt import aggregates_fra, aggregates_gbr, register_deu, register_fra, register_gbr
    assert DC.builder("GBR", "aggregates", "class_aggregates") is aggregates_gbr.class_aggregates
    assert DC.builder("FRA", "aggregates", "class_aggregates") is aggregates_fra.class_aggregates
    assert register.country_modules() == {"DEU": "register_deu", "GBR": "register_gbr", "FRA": "register_fra"}
    for iso3, mod in ((("DEU", register_deu)), ("GBR", register_gbr), ("FRA", register_fra)):
        assert DC.builder(iso3, "register", "build") is mod.build
    with pytest.raises(ImportError, match="cannot be imported"):
        DC.resolve("register_usa", "build")
    with pytest.raises(AttributeError):
        DC.resolve("intermediates:no_such_builder", "official_totals")


def test_unconfigured_country_raises_and_never_falls_through(monkeypatch):
    with pytest.raises(DC.DebtCountryNotConfigured, match="no entry in config/debt.yaml"):
        DC.country_cfg("USA")
    base = config.countries()
    # USA first, so official_totals meets it before any real builder runs
    monkeypatch.setattr(config, "countries", lambda: {
        "USA": {**base["DEU"], "name": "United States", "currency": "USD"}, **base})
    assert config.COUNTRIES[0] == "USA"
    with pytest.raises(DC.DebtCountryNotConfigured):
        chains._subsector_items("USA", "interest", 2020)
    with pytest.raises(DC.DebtCountryNotConfigured):
        intermediates.official_totals("test")


def test_official_totals_has_no_else_and_no_country_literal_routing():
    src = inspect.getsource(intermediates.official_totals)
    assert "else" not in src and 'iso3 == "' not in src and "elif" not in src
    for fn in (chains._subsector_items, validate.check_v31_stock_vs_official,
               aggregates.class_aggregates, register.collect):
        s = inspect.getsource(fn)
        assert '("FRA", "DEU")' not in s and 'iso3 == "' not in s and "aggregates_gbr" not in s, fn.__name__
    assert not hasattr(register, "COUNTRY_MODULES")
    assert chains._subsector_items("GBR", "interest", 2020) == []


def test_reference_finmark_rates_are_enumerated_from_debt_yaml():
    src = inspect.getsource(reference.build_reference_series)
    assert '("FRA", "FR_IR3")' not in src
    finmark = [(cfg["key"].split(".")[0], sid)
               for sid, cfg in config.debt()["reference_series"].items()
               if cfg.get("statistical") == "OECD_FINMARK" and str(cfg.get("key", "")).endswith("IR3TIB")]
    assert finmark == [("FRA", "FR_IR3"), ("DEU", "DE_IR3"), ("GBR", "GB_IR3")]
