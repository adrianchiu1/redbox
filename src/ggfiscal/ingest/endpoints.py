"""URL builders for every registered machine-readable source (D-S0-003).

These encode the endpoint decisions verified in reports/source_verification.md.
Anything still marked `confirm live` must be checked against the live catalog
before its first pull is trusted (Stage 0 gate item).
"""

from __future__ import annotations

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0"
IMF_BASE = "https://api.imf.org/external/sdmx/3.0"
OECD_BASE = "https://sdmx.oecd.org/public/rest"
AMECO_LANDING = ("https://economy-finance.ec.europa.eu/economic-research-and-databases/"
                 "economic-databases/ameco-database/"
                 "download-annual-data-set-macro-economic-database-ameco_en")

# Eurostat country codes for our ISO3s
EUROSTAT_GEO = {"FRA": "FR", "DEU": "DE"}
# WEO subject codes used by the reconciliation module (§6.3, §8.1)
WEO_SUBJECTS = ("GGR", "GGX", "GGXCNL", "GGXONLB", "NGDP")


def eurostat_data_url(dataset: str, params: str = "") -> str:
    """Full-dataset SDMX-CSV pull; filtering happens in standardise so the raw
    snapshot is the complete table (simpler provenance, stable hash per vintage)."""
    url = f"{EUROSTAT_BASE}/data/dataflow/ESTAT/{dataset}/1.0/?format=csvdata&compress=false"
    return url + (f"&{params}" if params else "")


def imf_dataflow_catalog_url(agency: str = "IMF.RES", dataflow: str = "WEO") -> str:
    """Enumerate available editions: WEO editions are dataflow versions (Q11)."""
    return f"{IMF_BASE}/structure/dataflow/{agency}/{dataflow}/%2A"


def imf_weo_data_url(version: str) -> str:
    """One WEO edition = one dataflow version; full pull, filter downstream."""
    return f"{IMF_BASE}/data/dataflow/IMF.RES/WEO/{version}/?format=csv"


def imf_gfs_cofog_data_url() -> str:
    # Dataflow id to confirm live against the migrated portal catalog (source_verification.md)
    return f"{IMF_BASE}/data/dataflow/IMF.STA/GFS_COFOG/+/?format=csv"


def oecd_rs_data_url() -> str:
    """OECD Revenue Statistics (global), SDMX-CSV; version resolved as latest."""
    return (f"{OECD_BASE}/data/OECD.CTP.TPS,DSD_REV_COMP_GLOBAL@DF_RSGLOBAL,"
            f"/all?format=csvfile")


def oecd_dataflow_catalog_url() -> str:
    """Full catalog — used once, live, to pin the Table 11 / National Accounts flow ids."""
    return f"{OECD_BASE}/dataflow/all/all/latest"


def all_stage0_probe_urls() -> dict[str, str]:
    """The endpoints Stage 0 must confirm, keyed by register source_id."""
    return {
        "EUROSTAT_GOV10A_EXP": eurostat_data_url("gov_10a_exp"),
        "EUROSTAT_GOV10A_MAIN": eurostat_data_url("gov_10a_main"),
        "EUROSTAT_GOV10A_TAXAG": eurostat_data_url("gov_10a_taxag"),
        "EUROSTAT_NAMA10_GDP": eurostat_data_url("nama_10_gdp"),
        "IMF_WEO": imf_dataflow_catalog_url(),
        "IMF_GFS": imf_gfs_cofog_data_url(),
        "OECD_RS": oecd_rs_data_url(),
        "OECD_T11": oecd_dataflow_catalog_url(),
        "EC_AMECO": AMECO_LANDING,
        "ONS_ESA_T11": ("https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/"
                        "publicspending/datasets/esatable11annualexpenditureofgeneralgovernment"),
    }
