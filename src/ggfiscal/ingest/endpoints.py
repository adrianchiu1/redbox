"""URL builders for every registered machine-readable source.

D-S0-003 chose the access paths; D-S0-006 (2026-08-31, second session) resolved
every id against the live catalogs and switched the Eurostat/OECD/IMF pulls
from full-table to filtered extractions (the filter is part of the recorded
URL, so a snapshot remains a complete, reproducible extraction definition).

Confirmed live 2026-08-31:
  - Eurostat dissemination API, SDMX 3.0 SDMX-CSV; key order
    freq.unit.sector[.cofog99].na_item.geo (nama_10_gdp: freq.unit.na_item.geo).
    The key parser accepts single values only -> one pull per country.
  - IMF api.imf.org SDMX 3.0. WEO editions exposed as THREE vintages today:
    WEO/9.0.0 (April 2026), WEO_2025_OCT_VINTAGE/1.0.0 (October 2025),
    WEO/6.0.0 (April 2025). `+` multi-values accepted in keys.
  - IMF GFS COFOG dataflow: IMF.STA:GFS_COFOG(11.0.0); main-aggregates
    companion IMF.STA:GFS_SOO(12.0.0).
  - OECD Table 11: OECD.SDD.NAD,DSD_NASEC10@DF_TABLE11,1.1 (13-dim DSD).
  - OECD Revenue Statistics: OECD.CTP.TPS,DSD_REV_COMP_GLOBAL@DF_RSGLOBAL,2.1
    (7-dim DSD: REF_AREA.MEASURE.SECTOR.STANDARD_REVENUE.CTRY_SPECIFIC_REVENUE.
    UNIT_MEASURE.FREQ).
  - AMECO bulk zips: ec.europa.eu/economy_finance/db_indicators/ameco/documents/
    ameco{1..18}.zip; Stage 0 takes 6 (domestic product) and 16-18 (government).
  - ONS: dataset pages serve the latest file at
    /file?uri={dataset_uri}/current/{filename}.
"""

from __future__ import annotations

import dataclasses

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0"
IMF_BASE = "https://api.imf.org/external/sdmx/3.0"
OECD_BASE = "https://sdmx.oecd.org/public/rest"
AMECO_DOC_BASE = "https://ec.europa.eu/economy_finance/db_indicators/ameco/documents"
ONS_BASE = "https://www.ons.gov.uk"
ONS_DATASETS = "/economy/governmentpublicsectorandtaxes/publicspending/datasets"

# Eurostat country codes for our ISO3s
EUROSTAT_GEO = {"FRA": "FR", "DEU": "DE"}
ISO3 = ("GBR", "FRA", "DEU")
# WEO subject codes used by the reconciliation module (§6.3, §8.1)
WEO_SUBJECTS = ("GGR", "GGX", "GGXCNL", "GGXONLB", "NGDP")

# WEO vintages: vintage label -> (dataflow id, dataflow version), latest first.
# Since Stage 6 (D-S6-001) the mapping lives in config/sources.yaml
# (IMF_WEO.api.vintages) so that registering a new WEO edition is a config
# change plus rebuild, never a code change (§11.7); the API drops old
# editions, so new ones must be snapshotted promptly (D-S0-007).
def weo_vintages() -> dict[str, tuple[str, str]]:
    from ggfiscal import config

    reg = config.sources()["IMF_WEO"]["api"]["vintages"]
    return {label: (str(v["dataflow"]), str(v["version"]))
            for label, v in reg.items()}

GFS_COFOG_FLOW = ("IMF.STA", "GFS_COFOG", "11.0.0")
GFS_SOO_FLOW = ("IMF.STA", "GFS_SOO", "12.0.0")
OECD_T11_FLOW = "OECD.SDD.NAD,DSD_NASEC10@DF_TABLE11,1.1"
# DF_RSOECD (OECD members) not DF_RSGLOBAL: only the members flow carries the
# 1965– history D15 requires (global flow starts 1990; verified live 2026-08-31).
OECD_RS_FLOW = "OECD.CTP.TPS,DSD_REV_COMP_OECD@DF_RSOECD,2.0"
AMECO_CHAPTERS = (6, 16, 17, 18)

# ONS dataset slug -> current filename (resolved live via {slug}/current/data JSON)
ONS_FILES = {
    "ONS_ESA_T11": ("esatable11annualexpenditureofgeneralgovernment",
                    "esatable11generalgovernment.xlsx"),
    "ONS_GG_RECEIPTS": ("esatable2mainaggregatesofgeneralgovernment",
                        "esatable0200.xls"),
    "ONS_TAX_DETAIL": ("esaquestionnairedetailedtaxandsocialcontributions",
                       "esantl0999.xls"),
    "ONS_TAX_LIST": ("esatable9listoftaxes", "esatable0900.xls"),
}


@dataclasses.dataclass(frozen=True)
class Pull:
    source_id: str     # register id (config/sources.yaml)
    part: str          # sub-identifier within the source (country, vintage, chapter)
    url: str
    accept: str = ""   # optional Accept header (IMF needs the sdmx csv media type)
    headers: tuple = ()  # extra (name, value) headers (EC document store needs
    #                      browser-like headers or it serves a "Sorry" JS page)


def eurostat_data_url(dataset: str, key: str) -> str:
    return (f"{EUROSTAT_BASE}/data/dataflow/ESTAT/{dataset}/1.0/{key}"
            f"?format=csvdata&compress=false")


def imf_dataflow_catalog_url(agency: str = "IMF.RES") -> str:
    """Enumerate an agency's dataflows (all ids, all versions): WEO editions
    appear both as WEO versions and as *_VINTAGE flows (Q11)."""
    return f"{IMF_BASE}/structure/dataflow/{agency}/%2A/%2A"


def imf_weo_data_url(flow: str, version: str, iso3: str, subject: str) -> str:
    """One (country, subject) per pull: the API only serves series-level
    attributes (LATEST_ACTUAL_ANNUAL_DATA, PUBLICATION_DATE — needed for the
    §8.1 base year) on single-series queries; multi-value keys drop them."""
    return (f"{IMF_BASE}/data/dataflow/IMF.RES/{flow}/{version}/"
            f"{iso3}.{subject}.A?attributes=all")


def imf_gfs_data_url(flow: tuple[str, str, str], iso3: str) -> str:
    agency, flow_id, version = flow
    return (f"{IMF_BASE}/data/dataflow/{agency}/{flow_id}/{version}/"
            f"{iso3}.S13.%2A.%2A.%2A.A?attributes=none")


def oecd_rs_data_url(iso3: str) -> str:
    return f"{OECD_BASE}/data/{OECD_RS_FLOW}/{iso3}......A?format=csvfile"


def oecd_t11_data_url(iso3: str) -> str:
    # 13-dim key: FREQ.REF_AREA.SECTOR then 10 wildcards
    return f"{OECD_BASE}/data/{OECD_T11_FLOW}/A.{iso3}.S13..........?format=csvfile"


def ameco_chapter_url(chapter: int) -> str:
    return f"{AMECO_DOC_BASE}/ameco{chapter}.zip"


def ons_file_url(slug: str, filename: str) -> str:
    return f"{ONS_BASE}/file?uri={ONS_DATASETS}/{slug}/current/{filename}"


def ons_dataset_meta_url(slug: str) -> str:
    """Landing-page JSON: carries the dataset title and latest releaseDate."""
    return f"{ONS_BASE}{ONS_DATASETS}/{slug}/data"


def ons_gdp_url() -> str:
    """YBHA — nominal GDP at market prices, £m, calendar years from 1948 (QNA).
    The GBR anchor-vintage GDP denominator (§6.3); ESA Table 2 has no GDP row."""
    return f"{ONS_BASE}/economy/grossdomesticproductgdp/timeseries/ybha/qna/data"


SDMX_CSV = "application/vnd.sdmx.data+csv"


# ---------- Stage 3 forecast sources (resolved live 2026-08-31, session 3) ----------
# The EC document store (economy-finance.ec.europa.eu/document/download) serves
# an anti-bot "Sorry" interstitial to bare clients; browser-like headers are
# required and are part of the recorded pull definition. Blocked Stage 3 hosts
# (obr.uk Cloudflare challenge; gov.uk, circabc.europa.eu, bmas.de egress
# policy) are documented in OPEN_QUESTIONS OQ-6 — no Pull entries exist for
# them until access is granted.

EC_DOC_BASE = "https://economy-finance.ec.europa.eu/document/download"
BMF_BASE = "https://www.bundesfinanzministerium.de"

BROWSER_HEADERS = (
    ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ("Accept-Language", "en-GB,en;q=0.9"),
)

AR_2024_FICHES_URL = (f"{EC_DOC_BASE}/e248db46-f876-4e72-8821-efae678e81ea_en"
                      "?filename=2024_Ageing_Report-Statistical_annex_all_countryfiches.xlsx")
AR_2024_HORIZONTAL_URL = (f"{EC_DOC_BASE}/403cc04f-9487-406b-a48a-22538e0d461c_en"
                          "?filename=2024_Ageing_Report-Statistical_annex_all_horizontal_tables.xlsx")
DSM_2025_FICHES_URL = (f"{EC_DOC_BASE}/19852ffb-d8c5-4d47-a402-aa6179dc8051_en"
                       "?filename=DSM%202025%20country%20fiches%20tables%20and%20graphs.xlsx")
STEUERSCHAETZUNG_2026_05_URL = (
    f"{BMF_BASE}/Content/DE/Standardartikel/Themen/Steuern/"
    "Steuerschaetzungen_und_Steuereinnahmen/Steuerschaetzung/"
    "2026-05-07-ergebnisse-170-steuerschaetzung-dl-xlsx.xlsx?__blob=publicationFile")


def all_stage3_pulls() -> list[Pull]:
    """Stage 3 forecast-source pulls (machine-readable, reachable hosts only)."""
    return [
        Pull("EC_AGEING_2024", "country_fiches", AR_2024_FICHES_URL,
             headers=BROWSER_HEADERS),
        Pull("EC_AGEING_2024", "horizontal_tables", AR_2024_HORIZONTAL_URL,
             headers=BROWSER_HEADERS),
        Pull("EC_DSM", "country_fiches_2025", DSM_2025_FICHES_URL,
             headers=BROWSER_HEADERS),
        Pull("DEU_STEUERSCHAETZUNG", "2026_05", STEUERSCHAETZUNG_2026_05_URL,
             headers=BROWSER_HEADERS),
    ]


def all_stage0_pulls() -> list[Pull]:
    """Every Stage 0 pull: anchors, GDP, WEO vintages, GFS, OECD RS/T11, AMECO, ONS."""
    pulls: list[Pull] = []
    for dataset, sid, key_fmt in (
        ("gov_10a_exp", "EUROSTAT_GOV10A_EXP", "A.MIO_NAC.S13.*.*.{geo}"),
        ("gov_10a_main", "EUROSTAT_GOV10A_MAIN", "A.MIO_NAC.S13.*.{geo}"),
        ("gov_10a_taxag", "EUROSTAT_GOV10A_TAXAG", "A.MIO_NAC.S13.*.{geo}"),
        ("nama_10_gdp", "EUROSTAT_NAMA10_GDP", "A.CP_MNAC.B1GQ.{geo}"),
    ):
        for iso3, geo in EUROSTAT_GEO.items():
            pulls.append(Pull(sid, iso3, eurostat_data_url(dataset, key_fmt.format(geo=geo))))

    pulls.append(Pull("IMF_WEO", "catalog", imf_dataflow_catalog_url(),
                      "application/vnd.sdmx.structure+json"))
    for vintage, (flow, version) in weo_vintages().items():
        for iso3 in ISO3:
            for subject in WEO_SUBJECTS:
                pulls.append(Pull(f"IMF_WEO_{vintage.replace('-', '_')}",
                                  f"{iso3}_{subject}",
                                  imf_weo_data_url(flow, version, iso3, subject),
                                  SDMX_CSV))
    for iso3 in ISO3:
        pulls.append(Pull("IMF_GFS", f"cofog_{iso3}", imf_gfs_data_url(GFS_COFOG_FLOW, iso3), SDMX_CSV))
        pulls.append(Pull("IMF_GFS", f"soo_{iso3}", imf_gfs_data_url(GFS_SOO_FLOW, iso3), SDMX_CSV))
        pulls.append(Pull("OECD_RS", iso3, oecd_rs_data_url(iso3)))
        pulls.append(Pull("OECD_T11", iso3, oecd_t11_data_url(iso3)))
    for ch in AMECO_CHAPTERS:
        pulls.append(Pull("EC_AMECO", f"chapter{ch}", ameco_chapter_url(ch)))
    for sid, (slug, filename) in ONS_FILES.items():
        pulls.append(Pull(sid, "current", ons_file_url(slug, filename)))
    pulls.append(Pull("ONS_GDP", "ybha", ons_gdp_url()))
    return pulls


