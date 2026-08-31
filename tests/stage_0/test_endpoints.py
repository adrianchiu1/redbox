"""Endpoint builders encode the D-S0-003 decisions; no legacy IMF paths."""

from ggfiscal.ingest import endpoints


def test_no_legacy_imf_dataservices():
    # §12 Stage 0: the IMF portal migrated in 2025; legacy paths must not appear.
    for url in endpoints.all_stage0_probe_urls().values():
        assert "dataservices.imf.org" not in url


def test_imf_weo_uses_new_portal():
    assert endpoints.imf_weo_data_url("4.0.0").startswith(
        "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.RES/WEO/")
    assert "IMF.RES/WEO" in endpoints.imf_dataflow_catalog_url()


def test_eurostat_datasets_covered():
    urls = endpoints.all_stage0_probe_urls()
    for ds in ("gov_10a_exp", "gov_10a_main", "gov_10a_taxag", "nama_10_gdp"):
        assert any(ds in u for u in urls.values()), ds


def test_probe_covers_all_stage0_machine_sources():
    urls = endpoints.all_stage0_probe_urls()
    for sid in ("IMF_WEO", "IMF_GFS", "OECD_RS", "EC_AMECO", "ONS_ESA_T11"):
        assert sid in urls
