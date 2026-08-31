"""Endpoint builders encode D-S0-003/D-S0-006; no legacy IMF paths."""

from ggfiscal.ingest import endpoints


def test_no_legacy_imf_dataservices():
    # §12 Stage 0: the IMF portal migrated in 2025; legacy paths must not appear.
    for pull in endpoints.all_stage0_pulls():
        assert "dataservices.imf.org" not in pull.url


def test_imf_weo_uses_new_portal():
    assert endpoints.imf_weo_data_url("WEO", "9.0.0", "GBR", "NGDP").startswith(
        "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.RES/WEO/")
    assert "IMF.RES" in endpoints.imf_dataflow_catalog_url()


def test_weo_vintages_pinned():
    # D-S0-006 / Q11: the API exposes exactly these three vintages (2026-08-31).
    assert list(endpoints.WEO_VINTAGES) == ["2026-04", "2025-10", "2025-04"]
    ids = {f"IMF_WEO_{v.replace('-', '_')}" for v in endpoints.WEO_VINTAGES}
    pulled = {p.source_id for p in endpoints.all_stage0_pulls()}
    assert ids <= pulled


def test_eurostat_datasets_covered_per_country():
    pulls = endpoints.all_stage0_pulls()
    for ds in ("gov_10a_exp", "gov_10a_main", "gov_10a_taxag", "nama_10_gdp"):
        geos = {p.part for p in pulls if ds in p.url}
        assert geos == {"FRA", "DEU"}, ds


def test_probe_covers_all_stage0_machine_sources():
    sids = {p.source_id for p in endpoints.all_stage0_pulls()}
    for sid in ("IMF_WEO", "IMF_GFS", "OECD_RS", "OECD_T11", "EC_AMECO",
                "ONS_ESA_T11", "ONS_GG_RECEIPTS", "ONS_TAX_DETAIL", "ONS_TAX_LIST"):
        assert sid in sids, sid


def test_gfs_pulls_cover_cofog_and_main_aggregates_per_country():
    parts = {p.part for p in endpoints.all_stage0_pulls() if p.source_id == "IMF_GFS"}
    assert parts == {f"{k}_{c}" for k in ("cofog", "soo") for c in ("GBR", "FRA", "DEU")}
